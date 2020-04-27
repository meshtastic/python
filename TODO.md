# TODO

- protobuf docs https://developers.google.com/protocol-buffers/docs/pythontutorial

## Primary API: MeshInterface

Contains a reader thread that is always trying to read on the serial port.

methods:

- constructor(serialPort)
- send(meshPacket) - throws errors if we have errors talking to the device
- close() - shuts down the interface
- init() - starts the enumeration process to download NodeDB etc... - we will not publish to topics until this enumeration completes
- radioConfig
- nodeDB
- myNodeInfo
- myNodeId

## PubSub topics

Use a pubsub model to communicate events [https://pypubsub.readthedocs.io/en/v4.0.3/ ]

- meshtastic.send(MeshPacket) - Not implemented, instead call send(packet) on MeshInterface
- meshtastic.connection.established - published once we've successfully connected to the radio and downloaded the node DB
- meshtastic.connection.lost - published once we've lost our link to the radio
- meshtastic.receive.position(MeshPacket)
- meshtastic.receive.user(MeshPacket)
- meshtastic.receive.data(MeshPacket)
- meshtastic.debugMessage(string)

## Wire encoding

When sending protobuf packets over serial or TCP each packet is preceded by uint32_t sent in network byte order (big endian).
The upper 16 bits must be 0x4403. The lower 16 bits are packet length (this encoding gives room to eventually allow quite large packets).

Implementations validate length against the maximum possible size of a BLE packet (our lowest common denominator) of 512 bytes. If the
length provided is larger than that we assume the packet is corrupted and begin again looking for 0x4403 framing.

The packets flowing towards the device are ToRadio protobufs, the packets flowing from the device are FromRadio protobufs.
The 0x4403 marker can be used as framing to (eventually) resync if packets are corrupted over the wire.
