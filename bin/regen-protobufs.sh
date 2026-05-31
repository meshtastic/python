#!/bin/bash

set -e

#Uncomment to run hack
#gsed -i 's/import "\//import ".\//g' ./protobufs/meshtastic/*
#gsed -i 's/package meshtastic;//g' ./protobufs/meshtastic/*

POETRYDIR=$(poetry env info --path)

if [[ -z "${POETRYDIR}" ]]; then
	poetry install
fi

# protoc looks for mypy plugin in the python path
source $(poetry env info --path)/bin/activate

# Put our temp files in the poetry build directory
TMPDIR=./build/meshtastic/protofixup
echo "Fixing up protobuf paths in ${TMPDIR} temp directory"


# Ensure a clean build
[ -e "${TMPDIR}" ] && rm -r "${TMPDIR}"

INDIR=${TMPDIR}/in/meshtastic/protobuf
OUTDIR=${TMPDIR}/out
PYIDIR=${TMPDIR}/out
mkdir -p "${OUTDIR}" "${INDIR}" "${PYIDIR}"
cp ./protobufs/meshtastic/*.proto "${INDIR}"
cp ./protobufs/meshtastic/*.options "${INDIR}"
cp ./protobufs/nanopb.proto "${INDIR}"

# OS-X sed is apparently a little different and expects an arg for -i
if [[ $OSTYPE == 'darwin'* ]]; then
	SEDCMD="sed -i '' -E"
else
	SEDCMD="sed -i -E"
fi


# change the package names to meshtastic.protobuf
$SEDCMD 's/^package meshtastic;/package meshtastic.protobuf;/' "${INDIR}/"*.proto
# fix the imports to match
$SEDCMD 's/^import "meshtastic\//import "meshtastic\/protobuf\//' "${INDIR}/"*.proto

$SEDCMD 's/^import "nanopb.proto"/import "meshtastic\/protobuf\/nanopb.proto"/' "${INDIR}/"*.proto

# Inject nanopb .options constraints as inline proto field options so that
# protoc --python_out embeds them in the generated descriptors.  Python code
# can then read them via:
#   field.GetOptions().Extensions[nanopb_pb2.nanopb].max_size
echo "Injecting nanopb options into proto files..."
for OPTS_FILE in "${INDIR}"/*.options; do
	BASENAME=$(basename "${OPTS_FILE}" .options)
	PROTO_FILE="${INDIR}/${BASENAME}.proto"
	if [ -f "${PROTO_FILE}" ]; then
		python3 ./bin/inject_nanopb_options.py "${OPTS_FILE}" "${PROTO_FILE}"
	fi
done

# Generate the python files
./nanopb-0.4.8/generator-bin/protoc -I=$TMPDIR/in --python_out "${OUTDIR}" "--mypy_out=${PYIDIR}" $INDIR/*.proto

# Change "from meshtastic.protobuf import" to "from . import"
$SEDCMD 's/^from meshtastic.protobuf import/from . import/' "${OUTDIR}"/meshtastic/protobuf/*pb2*.py[i]

# Create a __init__.py in the out directory
touch "${OUTDIR}/meshtastic/protobuf/__init__.py"

# Copy to the source controlled tree
mkdir -p meshtastic/protobuf
rm -rf meshtastic/protobuf/*pb2*.py
cp "${OUTDIR}/meshtastic/protobuf"/* meshtastic/protobuf

exit 0
