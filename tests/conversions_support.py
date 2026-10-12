"""Shared fixtures for the conversions tests. Not a test module itself.

Addresses are RFC 5737 / RFC 3849 documentation ranges; hosts example.com.
The secrets are made up for the tests and protect nothing.
"""
from __future__ import annotations

import ipaddress
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SECRET = "test-secret-not-real"
VID = "skv_" + "Q" * 22
MARKER = b"\xab\xcd\xefMaxMind.com"


# ------------------------------------------------- a tiny MaxMind DB writer

def _enc(value) -> bytes:
    if isinstance(value, str):
        raw = value.encode()
        return bytes([(2 << 5) | len(raw)]) + raw
    if isinstance(value, dict):
        out = bytes([(7 << 5) | len(value)])
        for k, v in value.items():
            out += (k if isinstance(k, bytes) else _enc(k)) + _enc(v)
        return out
    if isinstance(value, tuple) and value[0] == "u16":
        return bytes([(5 << 5) | 2]) + struct.pack(">H", value[1])
    if isinstance(value, tuple) and value[0] == "u32":
        return bytes([(6 << 5) | 4]) + struct.pack(">I", value[1])
    raise TypeError(value)


def mmdb(prefixes: dict[str, str], ip_version: int = 6, record_size: int = 24) -> bytes:
    """A MaxMind-format file mapping each network to {"country": {"iso_code"}}.
    The key "country" is stored once and reached by a pointer."""
    nodes: list[list] = [[None, None]]
    for net, code in prefixes.items():
        network = ipaddress.ip_network(net)
        value, length, total = int(network.network_address), network.prefixlen, \
            network.max_prefixlen
        if ip_version == 6 and network.version == 4:     # IPv4 sits at ::a.b.c.d
            total, length = 128, length + 96
        bits = [(value >> (total - 1 - i)) & 1 for i in range(length)]
        node = 0
        for i, bit in enumerate(bits):
            if i == len(bits) - 1:
                nodes[node][bit] = ("data", code)
                break
            child = nodes[node][bit]
            if not isinstance(child, int):
                nodes.append([None, None])
                child = nodes[node][bit] = len(nodes) - 1
            node = child
    data = _enc("country")                              # offset 0
    pointer = bytes([(1 << 5) | 0, 0])                  # -> offset 0
    offsets = {}
    for code in sorted(set(prefixes.values())):
        offsets[code] = len(data)
        data += _enc({pointer: {"iso_code": code}})
    count = len(nodes)

    def record(v) -> int:
        if v is None:
            return count
        if isinstance(v, int):
            return v
        return count + 16 + offsets[v[1]]

    tree = b""
    for left, right in nodes:
        a, b = record(left), record(right)
        if record_size == 24:
            tree += a.to_bytes(3, "big") + b.to_bytes(3, "big")
        elif record_size == 28:
            tree += (a & 0xFFFFFF).to_bytes(3, "big") + bytes(
                [((a >> 24) & 0xF) << 4 | ((b >> 24) & 0xF)]) + (b & 0xFFFFFF).to_bytes(3, "big")
        else:
            tree += a.to_bytes(4, "big") + b.to_bytes(4, "big")
    meta = _enc({"node_count": ("u32", count), "record_size": ("u16", record_size),
                 "ip_version": ("u16", ip_version), "database_type": "Test-Country"})
    return tree + b"\0" * 16 + data + MARKER + meta


# ------------------------------------------------------------ a fake request

class FakeHandler:
    """Enough of BaseHTTPRequestHandler for Receiver.http."""

    def __init__(self, path: str, body: bytes = b"", headers: dict | None = None,
                 command: str = "POST") -> None:
        import io
        from email.message import Message
        self.path, self.command = path, command
        self.headers = Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v
        if "Content-Length" not in (headers or {}):
            self.headers["Content-Length"] = str(len(body))
        self.rfile = io.BytesIO(body)
