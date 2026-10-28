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
import re
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
        self.kind = str(meta.get("database_type") or "")
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
            got = (mtime, Reader(_mapped(path)))
            _CACHE[path] = got
        return got[1]


def _mapped(path: str):
    """The file mapped read-only, not copied into memory: a city file is
    about 120 MB, and every Skald process reading it shares the same pages.
    A file replaced by the monthly update gets a new inode, so a mapping of
    the old one stays valid until the reader is rebuilt (on its new mtime).
    Falls back to reading it whole where mmap is not available."""
    import mmap
    try:
        with open(path, "rb") as handle:
            return mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    except (OSError, ValueError):
        return Path(path).read_bytes()


def database(config: dict) -> str | None:
    """The .mmdb file for this config: `logs.country_db`, else
    `conversions.country_db`. One file serves both, so a site whose log
    carries no country field (Caddy, a plain combined log) gets one from the
    address, and a lead hook's `ip` is looked up in the same file."""
    for section in ("logs", "conversions"):
        got = ((config or {}).get(section) or {}).get("country_db")
        if got not in (None, "", []):
            return str(got)
    return None


# DB-IP's free files (CC BY 4.0) ask for this credit wherever their data shows.
DBIP_CREDIT = ("IP Geolocation by DB-IP", "https://db-ip.com")


def credit(path, *more) -> tuple[str, str] | None:
    """The credit a GeoIP file's licence asks for, when this file is one of
    DB-IP's (its metadata says DBIP-...); None for any other or no file.
    More files (the city file beside the country file): any of DB-IP's."""
    for one in (path, *more):
        try:
            found = reader(one) if one else None
        except (ValueError, KeyError, IndexError, struct.error):
            continue
        if found is not None and found.kind.upper().startswith("DBIP"):
            return DBIP_CREDIT
    return None


_V4_PORT = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}):\d{1,5}$")
_V6_BRACKETS = re.compile(r"^\[([0-9A-Fa-f:.]+)\](?::\d{1,5})?$")


def address(value) -> str | None:
    """The visitor's address from what a lead sent as `ip`: an IPv4 or IPv6
    address, or the first entry of a list as an X-Forwarded-For header holds
    it ("192.0.2.10, 198.51.100.1"), a port after it taken off ("192.0.2.10:443",
    "[2001:db8::1]:443"). None for anything else. The lead files read the
    address the same way (kit/leads/)."""
    got = str(value or "").split(",", 1)[0].strip()
    m = _V4_PORT.match(got) or _V6_BRACKETS.match(got)
    if m:
        got = m.group(1)
    try:
        return str(ipaddress.ip_address(got))
    except ValueError:
        return None


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


# ------------------------------------------------------------------- cities
#
# `logs.city_db` names a city file in the same MaxMind format: DB-IP's free
# "IP to City Lite" (CC BY 4.0, monthly), whose record is
#   {"city": {"names": {"en": ...}}, "subdivisions": [{"names": {"en": ...}}],
#    "country": {"iso_code": "CA", ...}, "location": {"latitude", "longitude"}}
# (db-ip.com/db/format/ip-to-city-lite/mmdb.html; MaxMind's GeoLite2-City has
# the same keys). The reader is tolerant: a key missing or of another type is
# "not recorded", never a guess. A city is coarse: the city's own point, not
# the visitor's.

def city_database(config: dict) -> str | None:
    """The city .mmdb for this config (`logs.city_db`), or None."""
    got = ((config or {}).get("logs") or {}).get("city_db")
    return str(got) if got not in (None, "", []) else None


def _english(node) -> str:
    """A record part's name: names.en, else the first name it has."""
    names = node.get("names") if isinstance(node, dict) else None
    if not isinstance(names, dict):
        return ""
    got = names.get("en")
    if not isinstance(got, str) or not got.strip():
        got = next((v for v in names.values() if isinstance(v, str) and v.strip()), "")
    return " ".join(got.split())[:80]


def _degrees(value, limit: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return round(value, 3) if -limit <= value <= limit else None


def city(path, ip: str) -> dict | None:
    """{city, region, country, lat, lon} for the address, or None (no file,
    no answer, not an address, or a record without a city name). region and
    country are "", lat and lon None, when the record lacks them."""
    if not path or not ip:
        return None
    try:
        found = reader(path)
        record = found.lookup(str(ip).strip()) if found else None
    except (ValueError, KeyError, IndexError, struct.error):
        return None
    if not isinstance(record, dict):
        return None
    name = _english(record.get("city"))
    if not name:
        return None
    subs = record.get("subdivisions")
    region = _english(subs[0]) if isinstance(subs, list) and subs else ""
    cc = record.get("country")
    cc = str(cc.get("iso_code") or "").upper() if isinstance(cc, dict) else ""
    if not (len(cc) == 2 and cc.isalpha() and cc not in ("XX", "ZZ")):
        cc = ""
    where = record.get("location") if isinstance(record.get("location"), dict) else {}
    lat, lon = _degrees(where.get("latitude"), 90), _degrees(where.get("longitude"), 180)
    if lat is None or lon is None:
        lat = lon = None
    return {"city": name, "region": region, "country": cc, "lat": lat, "lon": lon}


def city_label(found: dict | None) -> str:
    """"Toronto, Ontario, CA": the city, its region (left out when missing or
    the same as the city), the country code. "" for no city. The one name a
    city has everywhere it is counted, stored and shown."""
    if not found or not found.get("city"):
        return ""
    parts = [" ".join(found["city"].replace(",", " ").split())]
    region = " ".join((found.get("region") or "").replace(",", " ").split())
    if region and region != parts[0]:
        parts.append(region)
    if found.get("country"):
        parts.append(found["country"])
    return ", ".join(parts)


class Cities:
    """address -> city label, looked up once per address per read (as the
    country fill is), and each label's point (lat, lon) for the map.

    A line whose own country (the log's cc=, or the country file's) differs
    from the city's country gets no city: a visit is never shown in a city
    of another country than its own."""

    def __init__(self, path) -> None:
        self.path = str(path)
        self.seen: dict[str, tuple[str, str]] = {}
        self.points: dict[str, tuple[float, float]] = {}

    def __call__(self, address: str, country: str = "") -> str:
        got = self.seen.get(address)
        if got is None:
            found = city(self.path, address)
            label = city_label(found)
            if label and found["lat"] is not None:
                self.points.setdefault(label, (found["lat"], found["lon"]))
            got = self.seen[address] = (label, found["country"] if found else "")
        label, cc = got
        if label and cc and country and country.upper() != cc:
            return ""
        return label


def cities(config: dict) -> Cities | None:
    """A city fill for this config, or None without `logs.city_db`."""
    path = city_database(config)
    return Cities(path) if path else None
