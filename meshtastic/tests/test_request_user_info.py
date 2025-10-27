"""Test request_user_info functionality."""

import logging
import pytest
from unittest.mock import MagicMock, patch

from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import mesh_pb2, portnums_pb2
from meshtastic import BROADCAST_ADDR


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_request_user_info_missing_node_info():
    """Test request_user_info when local node info is not available"""
    iface = MeshInterface(noProto=True)
    with pytest.raises(MeshInterface.MeshInterfaceError) as exc_info:
        iface.request_user_info(destinationId=1)
    assert "Could not get local node user info" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_request_user_info_valid(caplog):
    """Test request_user_info with valid node info"""
    with caplog.at_level(logging.DEBUG):
        iface = MeshInterface(noProto=True)
        
        # Mock getMyNodeInfo to return valid user data
        mock_user = {
            "user": {
                "id": "!12345678",
                "long_name": "Test Node",
                "short_name": "TN",
                "hw_model": 1,
                "is_licensed": False,
                "role": 0,
                "public_key": b"testkey"
            }
        }
        iface.getMyNodeInfo = MagicMock(return_value=mock_user)
        
        # Call request_user_info
        result = iface.request_user_info(destinationId=1)
        
        # Verify a mesh packet was created with correct fields
        assert isinstance(result, mesh_pb2.MeshPacket)
        assert result.decoded.portnum == portnums_pb2.PortNum.NODEINFO_APP_VALUE
        assert result.want_response == True
        assert result.to == 1
        
        # Verify the serialized user info was sent as payload
        decoded_user = mesh_pb2.User()
        decoded_user.ParseFromString(result.decoded.payload)
        assert decoded_user.id == "!12345678"
        assert decoded_user.long_name == "Test Node"
        assert decoded_user.short_name == "TN"
        assert decoded_user.hw_model == 1
        assert decoded_user.is_licensed == False
        assert decoded_user.role == 0
        assert decoded_user.public_key == b"testkey"


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_request_user_info_response_handling(caplog):
    """Test handling of responses to user info requests"""
    with caplog.at_level(logging.DEBUG):
        iface = MeshInterface(noProto=True)
        iface.nodes = {}  # Initialize nodes dict
        
        # Mock user info in response packet
        user_info = mesh_pb2.User()
        user_info.id = "!abcdef12"
        user_info.long_name = "Remote Node"
        user_info.short_name = "RN"
        
        # Create response packet
        packet = mesh_pb2.MeshPacket()
        packet.from_ = 123  # Note: Using from_ to avoid Python keyword
        packet.decoded.portnum = portnums_pb2.PortNum.NODEINFO_APP_VALUE
        packet.decoded.payload = user_info.SerializeToString()
        
        # Process the received packet
        iface._handlePacketFromRadio(packet)
        
        # Verify node info was stored correctly
        assert "!abcdef12" in iface.nodes
        stored_node = iface.nodes["!abcdef12"]
        assert stored_node["user"]["id"] == "!abcdef12"
        assert stored_node["user"]["longName"] == "Remote Node"
        assert stored_node["user"]["shortName"] == "RN"