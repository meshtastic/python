#!/bin/bash


protoc -I=proto --python_out meshtastic mesh.proto
