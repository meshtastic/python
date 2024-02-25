#!/bin/bash

#Uncomment to run hack
#gsed -i 's/import "\//import ".\//g' ./protobufs/meshtastic/*
#gsed -i 's/package meshtastic;//g' ./protobufs/meshtastic/*

./nanopb-0.4.7/generator-bin/protoc -I=protobufs --python_out ./ ./protobufs/meshtastic/*.proto

# workaround for import bug in protoc https://github.com/protocolbuffers/protobuf/issues/1491#issuecomment-690618628
mv ./meshtastic/*_pb2.py ./meshtastic/PbDefinitions

if [[ $OSTYPE == 'darwin'* ]]; then
	sed -i '' -E 's/^(import.*_pb2)/from . \1/' meshtastic/PbDefinitions/*.py
	# automate the current workaround (may be related to Meshtastic-protobufs issue #27 https://github.com/meshtastic/protobufs/issues/27)
	sed -i '' -E "s/^None = 0/globals()['None'] = 0/" meshtastic/PbDefinitions/mesh_pb2.py
	# change from meshtastic to meshtastic.PbDefinitions
	sed -i -E 's/^from meshtastic(.*_pb2.*)/from meshtastic.PbDefinitions\1/' meshtastic/PbDefinitions/*.py
else
	sed -i -e 's/^import.*_pb2/from . \0/' meshtastic/PbDefinitions/*.py
	# automate the current workaround (may be related to Meshtastic-protobufs issue #27 https://github.com/meshtastic/protobufs/issues/27)
	sed -i -e "s/^None = 0/globals()['None'] = 0/" meshtastic/PbDefinitions/mesh_pb2.py
	# change from meshtastic to meshtastic.PbDefinitions
	sed -i -E 's/^from meshtastic(.*_pb2.*)/from meshtastic.PbDefinitions\1/' meshtastic/PbDefinitions/*.py
fi