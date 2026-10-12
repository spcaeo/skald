"""Country from an address, read from a MaxMind-format (.mmdb) file such as
the free DB-IP country file the web server already uses for the log.

Only for a site's own signed lead push that passes the visitor's address
(`ip`): the country is looked up and the address dropped at once. Hooks from
tools come from the tool's servers, so their address says nothing about the
visitor and is never looked up.

`conversions.country_db` names the file; without it the country is not
recorded (NULL), never guessed. A small reader of the MaxMind DB format
(https://maxmind.github.io/MaxMind-DB/), standard library only.
"""
from __future__ import annotations

import ipaddress
import struct
import threading
from pathlib import Path

MARKER = b"\xab\xcd\xefMaxMind.com"
_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, "Reader"]] = {}


class Reader:
    def __init__(self, data: bytes) -> None:
        at = data.rfind(MARKER)
        if at < 0:
            raise ValueError("not a MaxMind DB file")
        meta = _Decoder(data, at + len(MARKER)).decode(0)[0]
        if not isinstance(meta, dict):
            raise ValueError("no metadata")
        self.nodes = int(meta["node_count"])
        self.size = int(meta["record_size"])
        if self.size not in (24, 28, 32):
            raise ValueError(f"record size {self.size} not supported")
        self.version = int(meta["ip_version"])
        self.node_bytes = self.size * 2 // 8
        self.data = data
        self.decoder = _Decoder(data, self.nodes * self.node_bytes + 16)
        self._v4 = None

    def _record(self, node: int, bit: int) -> int:
        b, base = self.data, node * self.node_bytes
        if self.size == 24:
            off = base + bit * 3
            return int.from_bytes(b[off:off + 3], "big")
        if self.size == 28:
            if bit == 0:
                return ((b[base + 3] & 0xF0) << 20) | int.from_bytes(b[base:base + 3], "big")
            return ((b[base + 3] & 0x0F) << 24) | int.from_bytes(b[base + 4:base + 7], "big")
        off = base + bit * 4
        return int.from_bytes(b[off:off + 4], "big")

    def _v4_start(self) -> int:
        if self._v4 is None:
            node = 0
            for _ in range(96):
                if node >= self.nodes:
                    break
                node = self._record(node, 0)
            self._v4 = node
        return self._v4

    def lookup(self, ip: str):
        """The record for an address, or None."""
        addr = ipaddress.ip_address(ip)
        if addr.version == 6 and self.version == 4:
            return None
        node = self._v4_start() if addr.version == 4 and self.version == 6 else 0
        packed = addr.packed
        for i in range(len(packed) * 8):
            if node >= self.nodes:
                break
            node = self._record(node, (packed[i >> 3] >> (7 - (i & 7))) & 1)
        if node <= self.nodes:
            return None
        return self.decoder.decode(node - self.nodes - 16)[0]


class _Decoder:
    def __init__(self, data: bytes, base: int) -> None:
        self.data, self.base = data, base

    def decode(self, offset: int, depth: int = 0):
        """(value, next offset), offsets relative to the section's start."""
        if depth > 32:
            raise ValueError("nested too deep")
        d, pos = self.data, self.base + offset
        ctrl = d[pos]
        pos += 1
        kind = ctrl >> 5
        if kind == 1:
            size, low = (ctrl >> 3) & 3, ctrl & 7
            if size == 0:
                ptr = (low << 8) | d[pos]
            elif size == 1:
                ptr = ((low << 16) | int.from_bytes(d[pos:pos + 2], "big")) + 2048
            elif size == 2:
                ptr = ((low << 24) | int.from_bytes(d[pos:pos + 3], "big")) + 526336
            else:
                ptr = int.from_bytes(d[pos:pos + 4], "big")
            pos += size + 1
            return self.decode(ptr, depth + 1)[0], pos - self.base
        if kind == 0:
            kind = 7 + d[pos]
            pos += 1
        size = ctrl & 0x1F
        if size >= 29:
            extra = size - 28
            n = int.from_bytes(d[pos:pos + extra], "big")
            size = (29, 285, 65821)[extra - 1] + n
            pos += extra
        if kind == 7:
            out, off = {}, pos - self.base
            for _ in range(size):
                k, off = self.decode(off, depth + 1)
                v, off = self.decode(off, depth + 1)
                out[k] = v
            return out, off
        if kind == 11:
            items, off = [], pos - self.base
            for _ in range(size):
                v, off = self.decode(off, depth + 1)
                items.append(v)
            return items, off
        if kind == 14:
            return bool(size), pos - self.base
        raw = d[pos:pos + size]
        nxt = pos + size - self.base
        if kind == 2:
            return raw.decode("utf-8", "replace"), nxt
        if kind == 3:
            return struct.unpack(">d", raw)[0], nxt
        if kind == 15:
            return struct.unpack(">f", raw)[0], nxt
        if kind == 8:
            return int.from_bytes(raw.rjust(4, b"\0"), "big", signed=True), nxt
        if kind in (5, 6, 9, 10):
            return int.from_bytes(raw, "big"), nxt
        return bytes(raw), nxt


def reader(path) -> Reader | None:
    """The file's reader, read again when the file changes. None when absent."""
    path = str(path)
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return None
    with _LOCK:
        got = _CACHE.get(path)
        if got is None or got[0] != mtime:
            got = (mtime, Reader(Path(path).read_bytes()))
            _CACHE[path] = got
        return got[1]


def country(path, ip: str) -> str | None:
    """A two-letter country code for the address, or None (no file, no
    answer, not an address, or DB-IP's "ZZ" unknown)."""
    if not path or not ip:
        return None
    try:
        found = reader(path)
        record = found.lookup(str(ip).strip()) if found else None
    except (ValueError, KeyError, IndexError, struct.error):
        return None
    if not isinstance(record, dict):
        return None
    code = (record.get("country") or {}).get("iso_code") if isinstance(
        record.get("country"), dict) else None
    code = str(code or "").upper()
    return code if len(code) == 2 and code.isalpha() and code not in ("XX", "ZZ") else None
