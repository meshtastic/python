"""Classes for logging power consumption of meshtastic devices."""

import logging
import threading
import time
from typing import Optional

from ppk2_api import ppk2_api  # type: ignore[import-untyped]

from .power_supply import PowerError, PowerSupply

class PPK2PowerSupply(PowerSupply):
    """Interface for talking with the NRF PPK2 high-resolution micro-power supply.
    Power Profiler Kit II is what you should google to find it for purchase.
    """

    def __init__(self, portName: Optional[str] = None):
        """Initialize the PowerSupply object.

        portName (str, optional): The port name of the power supply. Defaults to "/dev/ttyACM0".
        """
        if not portName:
            devs = ppk2_api.PPK2_API.list_devices()
            if not devs or len(devs) == 0:
                raise PowerError("No PPK2 devices found")
            elif len(devs) > 1:
                raise PowerError(
                    "Multiple PPK2 devices found, please specify the portName"
                )
            else:
                portName = devs[0]

        self.measuring = False
        self.current_max = 0
        self.current_min = 0
        self.current_sum = 0
        self.current_num_samples = 0

        # for tracking avera data read length (to determine if we are sleeping efficiently in measurement_loop)
        self.total_data_len = 0
        self.num_data_reads = 0
        self.max_data_len = 0

        self.r = r = ppk2_api.PPK2_API(
            portName
        )  # serial port will be different for you
        r.get_modifiers()

        self.measurement_thread = threading.Thread(
            target=self.measurement_loop, daemon=True, name="ppk2 measurement"
        )
        logging.info("Connected to Power Profiler Kit II (PPK2)")
        super().__init__()  # we call this late so that the port is already open and _getRawWattHour callback works

    def measurement_loop(self):
        """Endless measurement loop will run in a thread."""
        while self.measuring:
            # always reads 4096 bytes, even if there is no new samples - or possibly the python single thread (because of global interpreter lock)
            # is always behind and thefore we are inherently dropping samples semi randomly!!!
            read_data = self.r.get_data()
            if read_data != b"":
                samples, _ = self.r.get_samples(read_data)

                # update invariants
                if len(samples) > 0:
                    if self.current_num_samples == 0:
                        self.current_min = samples[
                            0
                        ]  # we need at least one sample to get an initial min
                    self.current_max = max(self.current_max, max(samples))
                    self.current_min = min(self.current_min, min(samples))
                    self.current_sum += sum(samples)
                    self.current_num_samples += len(samples)
                    # logging.debug(f"PPK2 data_len={len(read_data)}, sample_len={len(samples)}")

            self.num_data_reads += 1
            self.total_data_len += len(read_data)
            self.max_data_len = max(self.max_data_len, len(read_data))

            time.sleep(0.01)  # FIXME figure out correct sleep duration

    def get_min_current_mA(self):
        """Returns max current in mA (since last call to this method)."""
        return self.current_min / 1000

    def get_max_current_mA(self):
        """Returns max current in mA (since last call to this method)."""
        return self.current_max / 1000

    def get_average_current_mA(self):
        """Returns average current in mA (since last call to this method)."""
        if self.current_num_samples == 0:
            return 0
        else:
            return (
                self.current_sum / self.current_num_samples / 1000
            )  # measurements are in microamperes, divide by 1000

    def reset_measurements(self):
        """Reset current measurements."""
        # Use the last reading as the new only reading (to ensure we always have a valid current reading)
        self.current_max = 0
        self.current_min = 0
        self.current_sum = 0
        self.current_num_samples = 0

        # if self.num_data_reads:
        #    logging.debug(f"max data len = {self.max_data_len},avg {self.total_data_len/self.num_data_reads}, num reads={self.num_data_reads}")
        # Summary stats for performance monitoring
        self.num_data_reads = 0
        self.total_data_len = 0
        self.max_data_len = 0

    def close(self) -> None:
        """Close the power meter."""
        self.measuring = False
        self.r.stop_measuring()  # send command to ppk2
        self.measurement_thread.join()  # wait for our thread to finish
        super().close()

    def setIsSupply(self, s: bool):
        """If in supply mode we will provide power ourself, otherwise we are just an amp meter."""

        self.r.set_source_voltage(
            int(self.v * 1000)
        )  # set source voltage in mV BEFORE setting source mode
        # Note: source voltage must be set even if we are using the amp meter mode

        # must be after setting source voltage and before setting mode
        self.r.start_measuring()  # send command to ppk2

        if (
            not s
        ):  # min power outpuf of PPK2.  If less than this assume we want just meter mode.
            self.r.use_ampere_meter()
        else:
            self.r.use_source_meter()  # set source meter mode

        if not self.measurement_thread.is_alive():
            self.measuring = True
            self.reset_measurements()

            # We can't start reading from the thread until vdd is set, so start running the thread now
            self.measurement_thread.start()
            time.sleep(
                0.2
            )  # FIXME - crufty way to ensure we do one set of reads to discard bogus fake power readings in the FIFO
            self.reset_measurements()

    def powerOn(self):
        """Power on the supply."""
        self.r.toggle_DUT_power("ON")

    def powerOff(self):
        """Power off the supply."""
        self.r.toggle_DUT_power("OFF")
