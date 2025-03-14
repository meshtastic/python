"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""

import builtins
import google.protobuf.descriptor
import google.protobuf.internal.enum_type_wrapper
import google.protobuf.message
import sys
import typing

if sys.version_info >= (3, 10):
    import typing as typing_extensions
else:
    import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

class _Team:
    ValueType = typing.NewType("ValueType", builtins.int)
    V: typing_extensions.TypeAlias = ValueType

class _TeamEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[_Team.ValueType], builtins.type):
    DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
    Unspecifed_Color: _Team.ValueType  # 0
    """
    Unspecifed
    """
    White: _Team.ValueType  # 1
    """
    White
    """
    Yellow: _Team.ValueType  # 2
    """
    Yellow
    """
    Orange: _Team.ValueType  # 3
    """
    Orange
    """
    Magenta: _Team.ValueType  # 4
    """
    Magenta
    """
    Red: _Team.ValueType  # 5
    """
    Red
    """
    Maroon: _Team.ValueType  # 6
    """
    Maroon
    """
    Purple: _Team.ValueType  # 7
    """
    Purple
    """
    Dark_Blue: _Team.ValueType  # 8
    """
    Dark Blue
    """
    Blue: _Team.ValueType  # 9
    """
    Blue
    """
    Cyan: _Team.ValueType  # 10
    """
    Cyan
    """
    Teal: _Team.ValueType  # 11
    """
    Teal
    """
    Green: _Team.ValueType  # 12
    """
    Green
    """
    Dark_Green: _Team.ValueType  # 13
    """
    Dark Green
    """
    Brown: _Team.ValueType  # 14
    """
    Brown
    """

class Team(_Team, metaclass=_TeamEnumTypeWrapper): ...

Unspecifed_Color: Team.ValueType  # 0
"""
Unspecifed
"""
White: Team.ValueType  # 1
"""
White
"""
Yellow: Team.ValueType  # 2
"""
Yellow
"""
Orange: Team.ValueType  # 3
"""
Orange
"""
Magenta: Team.ValueType  # 4
"""
Magenta
"""
Red: Team.ValueType  # 5
"""
Red
"""
Maroon: Team.ValueType  # 6
"""
Maroon
"""
Purple: Team.ValueType  # 7
"""
Purple
"""
Dark_Blue: Team.ValueType  # 8
"""
Dark Blue
"""
Blue: Team.ValueType  # 9
"""
Blue
"""
Cyan: Team.ValueType  # 10
"""
Cyan
"""
Teal: Team.ValueType  # 11
"""
Teal
"""
Green: Team.ValueType  # 12
"""
Green
"""
Dark_Green: Team.ValueType  # 13
"""
Dark Green
"""
Brown: Team.ValueType  # 14
"""
Brown
"""
global___Team = Team

class _MemberRole:
    ValueType = typing.NewType("ValueType", builtins.int)
    V: typing_extensions.TypeAlias = ValueType

class _MemberRoleEnumTypeWrapper(google.protobuf.internal.enum_type_wrapper._EnumTypeWrapper[_MemberRole.ValueType], builtins.type):
    DESCRIPTOR: google.protobuf.descriptor.EnumDescriptor
    Unspecifed: _MemberRole.ValueType  # 0
    """
    Unspecifed
    """
    TeamMember: _MemberRole.ValueType  # 1
    """
    Team Member
    """
    TeamLead: _MemberRole.ValueType  # 2
    """
    Team Lead
    """
    HQ: _MemberRole.ValueType  # 3
    """
    Headquarters
    """
    Sniper: _MemberRole.ValueType  # 4
    """
    Airsoft enthusiast
    """
    Medic: _MemberRole.ValueType  # 5
    """
    Medic
    """
    ForwardObserver: _MemberRole.ValueType  # 6
    """
    ForwardObserver
    """
    RTO: _MemberRole.ValueType  # 7
    """
    Radio Telephone Operator
    """
    K9: _MemberRole.ValueType  # 8
    """
    Doggo
    """

class MemberRole(_MemberRole, metaclass=_MemberRoleEnumTypeWrapper):
    """
    Role of the group member
    """

Unspecifed: MemberRole.ValueType  # 0
"""
Unspecifed
"""
TeamMember: MemberRole.ValueType  # 1
"""
Team Member
"""
TeamLead: MemberRole.ValueType  # 2
"""
Team Lead
"""
HQ: MemberRole.ValueType  # 3
"""
Headquarters
"""
Sniper: MemberRole.ValueType  # 4
"""
Airsoft enthusiast
"""
Medic: MemberRole.ValueType  # 5
"""
Medic
"""
ForwardObserver: MemberRole.ValueType  # 6
"""
ForwardObserver
"""
RTO: MemberRole.ValueType  # 7
"""
Radio Telephone Operator
"""
K9: MemberRole.ValueType  # 8
"""
Doggo
"""
global___MemberRole = MemberRole

@typing.final
class TAKPacket(google.protobuf.message.Message):
    """
    Packets for the official ATAK Plugin
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    IS_COMPRESSED_FIELD_NUMBER: builtins.int
    CONTACT_FIELD_NUMBER: builtins.int
    GROUP_FIELD_NUMBER: builtins.int
    STATUS_FIELD_NUMBER: builtins.int
    PLI_FIELD_NUMBER: builtins.int
    CHAT_FIELD_NUMBER: builtins.int
    DETAIL_FIELD_NUMBER: builtins.int
    is_compressed: builtins.bool
    """
    Are the payloads strings compressed for LoRA transport?
    """
    detail: builtins.bytes
    """
    Generic CoT detail XML
    May be compressed / truncated by the sender (EUD)
    """
    @property
    def contact(self) -> global___Contact:
        """
        The contact / callsign for ATAK user
        """

    @property
    def group(self) -> global___Group:
        """
        The group for ATAK user
        """

    @property
    def status(self) -> global___Status:
        """
        The status of the ATAK EUD
        """

    @property
    def pli(self) -> global___PLI:
        """
        TAK position report
        """

    @property
    def chat(self) -> global___GeoChat:
        """
        ATAK GeoChat message
        """

    def __init__(
        self,
        *,
        is_compressed: builtins.bool = ...,
        contact: global___Contact | None = ...,
        group: global___Group | None = ...,
        status: global___Status | None = ...,
        pli: global___PLI | None = ...,
        chat: global___GeoChat | None = ...,
        detail: builtins.bytes = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["chat", b"chat", "contact", b"contact", "detail", b"detail", "group", b"group", "payload_variant", b"payload_variant", "pli", b"pli", "status", b"status"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["chat", b"chat", "contact", b"contact", "detail", b"detail", "group", b"group", "is_compressed", b"is_compressed", "payload_variant", b"payload_variant", "pli", b"pli", "status", b"status"]) -> None: ...
    def WhichOneof(self, oneof_group: typing.Literal["payload_variant", b"payload_variant"]) -> typing.Literal["pli", "chat", "detail"] | None: ...

global___TAKPacket = TAKPacket

@typing.final
class GeoChat(google.protobuf.message.Message):
    """
    ATAK GeoChat message
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    MESSAGE_FIELD_NUMBER: builtins.int
    TO_FIELD_NUMBER: builtins.int
    TO_CALLSIGN_FIELD_NUMBER: builtins.int
    message: builtins.str
    """
    The text message
    """
    to: builtins.str
    """
    Uid recipient of the message
    """
    to_callsign: builtins.str
    """
    Callsign of the recipient for the message
    """
    def __init__(
        self,
        *,
        message: builtins.str = ...,
        to: builtins.str | None = ...,
        to_callsign: builtins.str | None = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["_to", b"_to", "_to_callsign", b"_to_callsign", "to", b"to", "to_callsign", b"to_callsign"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["_to", b"_to", "_to_callsign", b"_to_callsign", "message", b"message", "to", b"to", "to_callsign", b"to_callsign"]) -> None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_to", b"_to"]) -> typing.Literal["to"] | None: ...
    @typing.overload
    def WhichOneof(self, oneof_group: typing.Literal["_to_callsign", b"_to_callsign"]) -> typing.Literal["to_callsign"] | None: ...

global___GeoChat = GeoChat

@typing.final
class Group(google.protobuf.message.Message):
    """
    ATAK Group
    <__group role='Team Member' name='Cyan'/>
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    ROLE_FIELD_NUMBER: builtins.int
    TEAM_FIELD_NUMBER: builtins.int
    role: global___MemberRole.ValueType
    """
    Role of the group member
    """
    team: global___Team.ValueType
    """
    Team (color)
    Default Cyan
    """
    def __init__(
        self,
        *,
        role: global___MemberRole.ValueType = ...,
        team: global___Team.ValueType = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing.Literal["role", b"role", "team", b"team"]) -> None: ...

global___Group = Group

@typing.final
class Status(google.protobuf.message.Message):
    """
    ATAK EUD Status
    <status battery='100' />
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    BATTERY_FIELD_NUMBER: builtins.int
    battery: builtins.int
    """
    Battery level
    """
    def __init__(
        self,
        *,
        battery: builtins.int = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing.Literal["battery", b"battery"]) -> None: ...

global___Status = Status

@typing.final
class Contact(google.protobuf.message.Message):
    """
    ATAK Contact
    <contact endpoint='0.0.0.0:4242:tcp' phone='+12345678' callsign='FALKE'/>
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    CALLSIGN_FIELD_NUMBER: builtins.int
    DEVICE_CALLSIGN_FIELD_NUMBER: builtins.int
    callsign: builtins.str
    """
    Callsign
    """
    device_callsign: builtins.str
    """
    Device callsign

    IP address of endpoint in integer form (0.0.0.0 default)
    """
    def __init__(
        self,
        *,
        callsign: builtins.str = ...,
        device_callsign: builtins.str = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing.Literal["callsign", b"callsign", "device_callsign", b"device_callsign"]) -> None: ...

global___Contact = Contact

@typing.final
class PLI(google.protobuf.message.Message):
    """
    Position Location Information from ATAK
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    LATITUDE_I_FIELD_NUMBER: builtins.int
    LONGITUDE_I_FIELD_NUMBER: builtins.int
    ALTITUDE_FIELD_NUMBER: builtins.int
    SPEED_FIELD_NUMBER: builtins.int
    COURSE_FIELD_NUMBER: builtins.int
    latitude_i: builtins.int
    """
    The new preferred location encoding, multiply by 1e-7 to get degrees
    in floating point
    """
    longitude_i: builtins.int
    """
    The new preferred location encoding, multiply by 1e-7 to get degrees
    in floating point
    """
    altitude: builtins.int
    """
    Altitude (ATAK prefers HAE)
    """
    speed: builtins.int
    """
    Speed
    """
    course: builtins.int
    """
    Course in degrees
    """
    def __init__(
        self,
        *,
        latitude_i: builtins.int = ...,
        longitude_i: builtins.int = ...,
        altitude: builtins.int = ...,
        speed: builtins.int = ...,
        course: builtins.int = ...,
    ) -> None: ...
    def ClearField(self, field_name: typing.Literal["altitude", b"altitude", "course", b"course", "latitude_i", b"latitude_i", "longitude_i", b"longitude_i", "speed", b"speed"]) -> None: ...

global___PLI = PLI
