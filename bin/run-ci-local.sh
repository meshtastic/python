#!/bin/bash

# This script lets you run github ci actions locally
# You need to have act installed.  You can get it at https://nektosact.com/

# by default it simulates a push event
# other useful options
# -j build-and-publish-ubuntu

# also: we only run one of the 4 matrix tests, because otherwise it absolutely hammers the CPU (so many containers and threads)
act -P ubuntu-latest=-self-hosted --matrix "python-version:3.8" "$@"