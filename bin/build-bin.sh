#!/bin/bash

set -e

echo Building ubuntu binary
poetry install
source $(poetry env info --path)/bin/activate
pyinstaller -F -n meshtastic --collect-all meshtastic meshtastic/__main__.py

