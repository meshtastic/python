#!/bin/bash


protoc -I=proto --python_out meshtastic `ls proto/*.proto`

# workaround for import bug in protoc https://github.com/protocolbuffers/protobuf/issues/1491#issuecomment-690618628

sed -i -E 's/^import.*_pb2/from . \0/' meshtastic/*.py

# automate the current workaround (may be related to Meshtastic-protobufs issue #27 https://github.com/meshtastic/Meshtastic-protobufs/issues/27)
sed -i "s/^None = 0/globals()['None'] = 0/" meshtastic/mesh_pb2.py
