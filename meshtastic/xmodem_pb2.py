# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: meshtastic/xmodem.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x17meshtastic/xmodem.proto\x12\nmeshtastic"\xb6\x01\n\x06XModem\x12+\n\x07\x63ontrol\x18\x01 \x01(\x0e\x32\x1a.meshtastic.XModem.Control\x12\x0b\n\x03seq\x18\x02 \x01(\r\x12\r\n\x05\x63rc16\x18\x03 \x01(\r\x12\x0e\n\x06\x62uffer\x18\x04 \x01(\x0c"S\n\x07\x43ontrol\x12\x07\n\x03NUL\x10\x00\x12\x07\n\x03SOH\x10\x01\x12\x07\n\x03STX\x10\x02\x12\x07\n\x03\x45OT\x10\x04\x12\x07\n\x03\x41\x43K\x10\x06\x12\x07\n\x03NAK\x10\x15\x12\x07\n\x03\x43\x41N\x10\x18\x12\t\n\x05\x43TRLZ\x10\x1a\x42\x61\n\x13\x63om.geeksville.meshB\x0cXmodemProtosZ"github.com/meshtastic/go/generated\xaa\x02\x14Meshtastic.Protobufs\xba\x02\x00\x62\x06proto3'
)

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "meshtastic.xmodem_pb2", globals())
if _descriptor._USE_C_DESCRIPTORS == False:

    DESCRIPTOR._options = None
    DESCRIPTOR._serialized_options = b'\n\023com.geeksville.meshB\014XmodemProtosZ"github.com/meshtastic/go/generated\252\002\024Meshtastic.Protobufs\272\002\000'
    _XMODEM._serialized_start = 40
    _XMODEM._serialized_end = 222
    _XMODEM_CONTROL._serialized_start = 139
    _XMODEM_CONTROL._serialized_end = 222
# @@protoc_insertion_point(module_scope)
