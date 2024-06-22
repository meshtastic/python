#!/bin/bash

# This script lets you run github ci actions locally

# also: we only run one of the 4 matrix tests, because otherwise it absolutely hammers the CPU (so many containers and threads)
act -P ubuntu-latest=-self-hosted --matrix "python-version:3.8"