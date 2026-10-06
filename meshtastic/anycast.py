"""Anycast groups (protobufs SCHEMA.md section 8, "Anycast").

A group is an X25519 key pair whose id, crc32 of the public key, lives in the node number
space. A sender holds the public half; a member also holds the private half and delivers what
is sent to the group. Key generation is pure Python (RFC 7748), so no crypto dependency.
"""

import os
import zlib
from typing import Tuple

_P = 2**255 - 19
_A24 = 121665
_BASE_POINT = (9).to_bytes(32, "little")

# Node numbers 0-3 are reserved and 0xFFFFFFFF is the broadcast address: firmware refuses them.
RESERVED_IDS = {0, 1, 2, 3, 0xFFFFFFFF}


def group_id(public_key: bytes) -> int:
    """The group's id in the node number space."""
    return zlib.crc32(public_key) & 0xFFFFFFFF


def _clamp(scalar: bytes) -> int:
    k = bytearray(scalar)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    return int.from_bytes(k, "little")


def x25519(scalar: bytes, u_point: bytes) -> bytes:
    """RFC 7748 X25519: scalar times the point with u-coordinate u_point."""
    k = _clamp(scalar)
    x1 = int.from_bytes(u_point, "little") & ((1 << 255) - 1)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in reversed(range(255)):
        bit = (k >> t) & 1
        swap ^= bit
        if swap:
            x2, x3, z2, z3 = x3, x2, z3, z2
        swap = bit
        a, b = (x2 + z2) % _P, (x2 - z2) % _P
        aa, bb = a * a % _P, b * b % _P
        e = (aa - bb) % _P
        c, d = (x3 + z3) % _P, (x3 - z3) % _P
        da, cb = d * a % _P, c * b % _P
        x3 = (da + cb) ** 2 % _P
        z3 = x1 * (da - cb) ** 2 % _P
        x2 = aa * bb % _P
        z2 = e * (aa + _A24 * e) % _P
    if swap:
        x2, z2 = x3, z3
    return (x2 * pow(z2, _P - 2, _P) % _P).to_bytes(32, "little")


def public_key(private_key: bytes) -> bytes:
    """The public half of an X25519 private key."""
    return x25519(private_key, _BASE_POINT)


def generate_keypair() -> Tuple[bytes, bytes]:
    """A fresh group key pair, (private, public), whose id firmware accepts."""
    while True:
        priv = bytearray(os.urandom(32))
        priv[0] &= 248
        priv[31] &= 127
        priv[31] |= 64
        pub = public_key(bytes(priv))
        if group_id(pub) not in RESERVED_IDS:
            return bytes(priv), pub
