set -e

echo "Running (crude) prerelease tests to verify sanity"
python3 tests/hello_world.py
bin/run.sh --help
bin/run.sh --info
bin/run.sh --sendtext "Sanity complete"