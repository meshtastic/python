#!/usr/bin/env python
"""Show the version number"""

version_filename = "setup.py"

lines = None

with open(version_filename, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    if line.lstrip().startswith("version="):
        # get rid of quotes around the version
        line2 = line.replace('"', "")
        # get rid of the trailing comma
        line2 = line2.replace(",", "")
        # split on =
        words = line2.split("=")
        # Note: This format is for github actions
        print(f"::set-output name=version::{words[1].strip()}")
