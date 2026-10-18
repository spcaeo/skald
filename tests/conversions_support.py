"""Shared fixtures for the conversions tests. Not a test module itself.

Addresses are RFC 5737 / RFC 3849 documentation ranges; hosts example.com.
The secrets are made up for the tests and protect nothing.
"""
from __future__ import annotations

import ipaddress
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SECRET = "test-secret-not-real"
VID = "skv_" + "Q" * 22
MARKER = b"\xab\xcd\xefMaxMind.com"


# ------------------------------------------------- a tiny MaxMind DB writer

def _size(kind: int, n: int) -> bytes:
    """A control byte (and extended type byte) for `kind` holding `n` items."""
    head = (kind << 5) if kind <= 7 else 0
    if n < 29:
        out, extra = bytes([head | n]), b""
    elif n < 285:
        out, extra = bytes([head | 29]), bytes([n - 29])
    else:
        out, extra = bytes([head | 30]), (n - 285).to_bytes(2, "big")
    return out + (bytes([kind - 7]) if kind > 7 else b"") + extra


def _enc(value) -> bytes:
    if isinstance(value, str):
        raw = value.encode()
        return _size(2, len(raw)) + raw
    if isinstance(value, float):                        # a double
        return bytes([(3 << 5) | 8]) + struct.pack(">d", value)
    if isinstance(value, list):                         # an array (extended type 11)
        return _size(11, len(value)) + b"".join(_enc(v) for v in value)
    if isinstance(value, int) and not isinstance(value, bool):
        return bytes([(6 << 5) | 4]) + struct.pack(">I", value)
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


def city_record(city: str, region: str, country: str, lat: float, lon: float) -> dict:
    """A record shaped as DB-IP's "IP to City Lite" file has it."""
    return {"city": {"names": {"en": city}},
            "country": {"iso_code": country, "names": {"en": country}},
            "location": {"latitude": float(lat), "longitude": float(lon)},
            "subdivisions": [{"names": {"en": region}}] if region else []}


def mmdb(prefixes: dict, ip_version: int = 6, record_size: int = 24,
         kind: str = "Test-Country") -> bytes:
    """A MaxMind-format file mapping each network to {"country": {"iso_code"}}
    (a country code) or to a whole record (a dict, e.g. city_record()).
    The key "country" of a country code is stored once and reached by a
    pointer."""
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
                nodes[node][bit] = ("data", json.dumps(code, sort_keys=True))
                break
            child = nodes[node][bit]
            if not isinstance(child, int):
                nodes.append([None, None])
                child = nodes[node][bit] = len(nodes) - 1
            node = child
    data = _enc("country")                              # offset 0
    pointer = bytes([(1 << 5) | 0, 0])                  # -> offset 0
    offsets = {}
    for key in sorted({json.dumps(v, sort_keys=True) for v in prefixes.values()}):
        value = json.loads(key)
        offsets[key] = len(data)
        data += _enc({pointer: {"iso_code": value}} if isinstance(value, str) else value)
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
                 "ip_version": ("u16", ip_version), "database_type": kind})
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
