set -e

echo "Running (crude) prerelease tests to verify sanity"
echo running hello
python3 tests/hello_world.py
# bin/run.sh --help
echo toggling router
bin/run.sh --set is_router true
bin/run.sh --set is_router false
echo setting channel
bin/run.sh --seturl "https://www.meshtastic.org/c/#GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
echo setting time
bin/run.sh --settime
echo setting owner
bin/run.sh --setowner "Test Build"
echo setting position
bin/run.sh --setlat 32.7767 --setlon -96.7970 --setalt 1337
echo dumping info
bin/run.sh --info
echo sending closing message
bin/run.sh --sendtext "Sanity complete"
