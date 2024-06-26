set -e

# You may consider running: "pytest -m smoke1" instead of this test.

echo "Running (crude) prerelease tests to verify sanity"

# Use the python environment created by poetry
source $(poetry env info --path)/bin/activate

echo running hello
python3 tests/hello_world.py
# meshtastic --help
echo toggling router
meshtastic --set is_router true
meshtastic --set is_router false
# TODO: This does not seem to work.
echo setting channel
meshtastic --seturl "https://www.meshtastic.org/c/#GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
echo setting owner
meshtastic --set-owner "Test Build"
echo setting position
meshtastic --setlat 32.7767 --setlon -96.7970 --setalt 1337
echo dumping info
meshtastic run meshtastic --info
echo sending closing message
meshtastic --sendtext "Sanity complete"
