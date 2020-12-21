# delete me eventually

from tuntap import TunTap

tun = TunTap(nic_type="Tun",nic_name="tun0")
tun.config(ip="10.115.1.2",mask="255.255.0.0")