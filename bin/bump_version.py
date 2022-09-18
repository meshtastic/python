#!/usr/bin/env python
"""Bump the version number"""
import re

version_filename = "setup.py"

lines = None

with open(version_filename, 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(version_filename, 'w', encoding='utf-8') as f:
    for line in lines:
        if line.lstrip().startswith("version="):
            # get rid of quotes around the version
            line = line.replace('"', '')
            # get rid of trailing comma
            line = line.replace(",", "")
            # split on '='
            words = line.split("=")
            # split the version into parts (by period)
            v = words[1].split(".")
            build_num = re.findall(r"\d+", v[2])[0]
            new_build_num = str(int(build_num)+1)
            ver = f'{v[0]}.{v[1]}.{v[2].replace(build_num, new_build_num)}'
            f.write(f'    version="{ver}",\n')
        else:
            f.write(line)
