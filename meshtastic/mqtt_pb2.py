# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: mqtt.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . 0


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\nmqtt.proto\x1a\nmesh.proto\"V\n\x0fServiceEnvelope\x12\x1b\n\x06packet\x18\x01 \x01(\x0b\x32\x0b.MeshPacket\x12\x12\n\nchannel_id\x18\x02 \x01(\t\x12\x12\n\ngateway_id\x18\x03 \x01(\tBF\n\x13\x63om.geeksville.meshB\nMQTTProtosH\x03Z!github.com/meshtastic/gomeshprotob\x06proto3')



_SERVICEENVELOPE = DESCRIPTOR.message_types_by_name['ServiceEnvelope']
ServiceEnvelope = _reflection.GeneratedProtocolMessageType('ServiceEnvelope', (_message.Message,), {
  'DESCRIPTOR' : _SERVICEENVELOPE,
  '__module__' : 'mqtt_pb2'
  # @@protoc_insertion_point(class_scope:ServiceEnvelope)
  })
_sym_db.RegisterMessage(ServiceEnvelope)

if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\023com.geeksville.meshB\nMQTTProtosH\003Z!github.com/meshtastic/gomeshproto'
  _SERVICEENVELOPE._serialized_start=26
  _SERVICEENVELOPE._serialized_end=112
# @@protoc_insertion_point(module_scope)
