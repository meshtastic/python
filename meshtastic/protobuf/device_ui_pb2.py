# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: meshtastic/protobuf/device_ui.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n#meshtastic/protobuf/device_ui.proto\x12\x13meshtastic.protobuf\"\xeb\x03\n\x0e\x44\x65viceUIConfig\x12\x0f\n\x07version\x18\x01 \x01(\r\x12\x19\n\x11screen_brightness\x18\x02 \x01(\r\x12\x16\n\x0escreen_timeout\x18\x03 \x01(\r\x12\x13\n\x0bscreen_lock\x18\x04 \x01(\x08\x12\x15\n\rsettings_lock\x18\x05 \x01(\x08\x12\x10\n\x08pin_code\x18\x06 \x01(\r\x12)\n\x05theme\x18\x07 \x01(\x0e\x32\x1a.meshtastic.protobuf.Theme\x12\x15\n\ralert_enabled\x18\x08 \x01(\x08\x12\x16\n\x0e\x62\x61nner_enabled\x18\t \x01(\x08\x12\x14\n\x0cring_tone_id\x18\n \x01(\r\x12/\n\x08language\x18\x0b \x01(\x0e\x32\x1d.meshtastic.protobuf.Language\x12\x34\n\x0bnode_filter\x18\x0c \x01(\x0b\x32\x1f.meshtastic.protobuf.NodeFilter\x12:\n\x0enode_highlight\x18\r \x01(\x0b\x32\".meshtastic.protobuf.NodeHighlight\x12\x18\n\x10\x63\x61libration_data\x18\x0e \x01(\x0c\x12*\n\x08map_data\x18\x0f \x01(\x0b\x32\x18.meshtastic.protobuf.Map\"\xa7\x01\n\nNodeFilter\x12\x16\n\x0eunknown_switch\x18\x01 \x01(\x08\x12\x16\n\x0eoffline_switch\x18\x02 \x01(\x08\x12\x19\n\x11public_key_switch\x18\x03 \x01(\x08\x12\x11\n\thops_away\x18\x04 \x01(\x05\x12\x17\n\x0fposition_switch\x18\x05 \x01(\x08\x12\x11\n\tnode_name\x18\x06 \x01(\t\x12\x0f\n\x07\x63hannel\x18\x07 \x01(\x05\"~\n\rNodeHighlight\x12\x13\n\x0b\x63hat_switch\x18\x01 \x01(\x08\x12\x17\n\x0fposition_switch\x18\x02 \x01(\x08\x12\x18\n\x10telemetry_switch\x18\x03 \x01(\x08\x12\x12\n\niaq_switch\x18\x04 \x01(\x08\x12\x11\n\tnode_name\x18\x05 \x01(\t\"=\n\x08GeoPoint\x12\x0c\n\x04zoom\x18\x01 \x01(\x05\x12\x10\n\x08latitude\x18\x02 \x01(\x05\x12\x11\n\tlongitude\x18\x03 \x01(\x05\"U\n\x03Map\x12+\n\x04home\x18\x01 \x01(\x0b\x32\x1d.meshtastic.protobuf.GeoPoint\x12\r\n\x05style\x18\x02 \x01(\t\x12\x12\n\nfollow_gps\x18\x03 \x01(\x08*%\n\x05Theme\x12\x08\n\x04\x44\x41RK\x10\x00\x12\t\n\x05LIGHT\x10\x01\x12\x07\n\x03RED\x10\x02*\x9a\x02\n\x08Language\x12\x0b\n\x07\x45NGLISH\x10\x00\x12\n\n\x06\x46RENCH\x10\x01\x12\n\n\x06GERMAN\x10\x02\x12\x0b\n\x07ITALIAN\x10\x03\x12\x0e\n\nPORTUGUESE\x10\x04\x12\x0b\n\x07SPANISH\x10\x05\x12\x0b\n\x07SWEDISH\x10\x06\x12\x0b\n\x07\x46INNISH\x10\x07\x12\n\n\x06POLISH\x10\x08\x12\x0b\n\x07TURKISH\x10\t\x12\x0b\n\x07SERBIAN\x10\n\x12\x0b\n\x07RUSSIAN\x10\x0b\x12\t\n\x05\x44UTCH\x10\x0c\x12\t\n\x05GREEK\x10\r\x12\r\n\tNORWEGIAN\x10\x0e\x12\r\n\tSLOVENIAN\x10\x0f\x12\r\n\tUKRAINIAN\x10\x10\x12\x16\n\x12SIMPLIFIED_CHINESE\x10\x1e\x12\x17\n\x13TRADITIONAL_CHINESE\x10\x1f\x42\x63\n\x13\x63om.geeksville.meshB\x0e\x44\x65viceUIProtosZ\"github.com/meshtastic/go/generated\xaa\x02\x14Meshtastic.Protobufs\xba\x02\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'meshtastic.protobuf.device_ui_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\023com.geeksville.meshB\016DeviceUIProtosZ\"github.com/meshtastic/go/generated\252\002\024Meshtastic.Protobufs\272\002\000'
  _globals['_THEME']._serialized_start=1002
  _globals['_THEME']._serialized_end=1039
  _globals['_LANGUAGE']._serialized_start=1042
  _globals['_LANGUAGE']._serialized_end=1324
  _globals['_DEVICEUICONFIG']._serialized_start=61
  _globals['_DEVICEUICONFIG']._serialized_end=552
  _globals['_NODEFILTER']._serialized_start=555
  _globals['_NODEFILTER']._serialized_end=722
  _globals['_NODEHIGHLIGHT']._serialized_start=724
  _globals['_NODEHIGHLIGHT']._serialized_end=850
  _globals['_GEOPOINT']._serialized_start=852
  _globals['_GEOPOINT']._serialized_end=913
  _globals['_MAP']._serialized_start=915
  _globals['_MAP']._serialized_end=1000
# @@protoc_insertion_point(module_scope)
