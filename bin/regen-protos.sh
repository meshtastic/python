#!/bin/bash


protoc -I=proto --python_out meshtastic mesh.proto portnums.proto

# workaround for import bug in protoc https://github.com/protocolbuffers/protobuf/issues/1491#issuecomment-690618628

sed -i -E 's/^import.*_pb2/from . \0/' meshtastic/*.py