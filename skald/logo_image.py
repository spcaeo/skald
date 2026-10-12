"""What a site logo's bytes really are: the type, the size, and for SVG
whether it is safe to show (site_logos.py fetches and stores them).

Nothing here trusts a file name or a Content-Type: the type comes from the
first bytes (PNG, ICO, GIF, JPEG, WebP), or, for SVG, from parsing it.

SVG can carry script, so it cannot simply be passed on. The standard library
cannot draw an SVG into a PNG, so instead a risky SVG is refused: a DOCTYPE
or entity, a processing instruction, an element outside SVG's own namespace
(the usual editors' notes in <metadata> excepted), <script>, <foreignObject>,
animation (it can rewrite a link), an attribute starting with "on", a link
(href, xlink:href, src) that is not "#..." inside the file, or url(...),
@import or "javascript:" pointing anywhere else. What passes is still served
as an image with a sandbox CSP (logo_api.py), and pages only ever show it in
<img>, where no script runs.
"""
from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET

# kind -> the Content-Type the logo route sends
CTYPES = {"png": "image/png", "ico": "image/x-icon", "gif": "image/gif",
          "jpg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}
UPLOAD_KINDS = ("png", "ico", "svg")
UPLOAD_MIN = 64                       # px, the smaller side
SQUARE = (0.9, 1.1)                   # width / height an upload may have
MAX_ELEMENTS = 5000

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
# Notes that drawing programs leave in an SVG; never drawn, never run.
EDITOR_NS = ("http://www.inkscape.org/namespaces/inkscape",
             "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
             "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "http://creativecommons.org/ns#",
             "http://purl.org/dc/elements/1.1/", "http://ns.adobe.com/AdobeIllustrator/10.0/",
             "http://www.bohemiancoding.com/sketch/ns")
REFUSED_TAGS = {"script", "foreignobject", "iframe", "embed", "object", "audio", "video",
                "canvas", "animate", "animatemotion", "animatetransform", "animatecolor",
                "set", "discard", "handler", "listener", "a"}
LINK_ATTRS = {"href", "src"}
OUTSIDE = re.compile(r"url\(\s*['\"]?\s*(?!#)|@import|javascript:|vbscript:|data:", re.I)


class Refused(ValueError):
    """Not a logo Skald will keep, in plain words."""


def kind_of(body: bytes) -> str | None:
    """The image type by its first bytes; "svg" only for text that starts
    like XML or <svg; None otherwise."""
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if body[:4] == b"\x00\x00\x01\x00":
        return "ico"
    if body[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if body[:3] == b"\xff\xd8\xff":
        return "jpg"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "webp"
    head = body[:512].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith((b"<?xml", b"<svg", b"<!--", b"<!doctype svg")):
        return "svg" if b"<svg" in body[:4096].lower() else None
    return None


# ------------------------------------------------------------------ sizes

def _png(body: bytes):
    if len(body) < 24 or body[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", body[16:24])


def _ico(body: bytes):
    if len(body) < 6:
        return None
    count = struct.unpack("<H", body[4:6])[0]
    if not 1 <= count <= 64 or len(body) < 6 + 16 * count:
        return None
    best = None
    for i in range(count):
        entry = body[6 + 16 * i: 22 + 16 * i]
        w, h = entry[0] or 256, entry[1] or 256
        size, offset = struct.unpack("<II", entry[8:16])
        if offset + size > len(body) or size == 0:
            return None                 # a directory that points outside the file
        if best is None or w * h > best[0] * best[1]:
            best = (w, h)
    return best


def _gif(body: bytes):
    return struct.unpack("<HH", body[6:10]) if len(body) >= 10 else None


def _jpg(body: bytes):
    i = 2
    while i + 9 < len(body):
        if body[i] != 0xFF:
            return None
        marker = body[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", body[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", body[i + 5:i + 9])
            return w, h
        i += 2 + length
    return None


def _webp(body: bytes):
    chunk = body[12:16]
    if chunk == b"VP8X" and len(body) >= 30:
        w = int.from_bytes(body[24:27], "little") + 1
        h = int.from_bytes(body[27:30], "little") + 1
        return w, h
    if chunk == b"VP8 " and len(body) >= 30:
        w, h = struct.unpack("<HH", body[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L" and len(body) >= 25:
        bits = int.from_bytes(body[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


SIZERS = {"png": _png, "ico": _ico, "gif": _gif, "jpg": _jpg, "webp": _webp}


def size_of(body: bytes, kind: str) -> tuple[int, int] | None:
    """(width, height) in pixels; for SVG the viewBox's or width/height's
    proportions (it scales); None when the bytes do not say."""
    if kind == "svg":
        try:
            return svg_size(_svg_root(body))
        except Refused:
            return None
    try:
        got = SIZERS[kind](body)
    except (struct.error, KeyError, IndexError):
        return None
    if not got or got[0] <= 0 or got[1] <= 0:
        return None
    return int(got[0]), int(got[1])


# -------------------------------------------------------------------- SVG

def _local(tag: str) -> tuple[str, str]:
    """(namespace, local name) of an ElementTree tag or attribute."""
    if tag.startswith("{"):
        ns, _, name = tag[1:].partition("}")
        return ns, name
    return "", tag


def _svg_root(body: bytes):
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("The SVG is not UTF-8 text.") from None
    low = text.lower()
    if "<!doctype" in low or "<!entity" in low:
        raise Refused("The SVG has a DOCTYPE or an entity; save it without one.")
    if re.search(r"<\?(?!xml\s)", text):
        raise Refused("The SVG has a processing instruction (a style sheet link).")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise Refused("The SVG cannot be read: it is not well-formed XML.") from None
    ns, name = _local(root.tag)
    if name != "svg" or ns not in ("", SVG_NS):
        raise Refused("The file is not an SVG image.")
    return root


def check_svg(body: bytes) -> None:
    """Raises Refused, with the reason, for anything that could run or load
    something; returns None for an SVG that only draws."""
    root = _svg_root(body)
    seen = 0
    inside_meta = set()
    for parent in root.iter():
        if _local(parent.tag)[1] == "metadata":
            inside_meta.update(id(x) for x in parent.iter() if x is not parent)
    for el in root.iter():
        seen += 1
        if seen > MAX_ELEMENTS:
            raise Refused(f"The SVG has more than {MAX_ELEMENTS} parts; simplify it.")
        if not isinstance(el.tag, str):
            continue
        ns, name = _local(el.tag)
        if ns not in ("", SVG_NS) and not (ns in EDITOR_NS or id(el) in inside_meta):
            raise Refused(f"The SVG has a part from another language ({name}).")
        if name.lower() in REFUSED_TAGS:
            raise Refused(f"The SVG has <{name}>, which can run or load something.")
        for attr, value in el.attrib.items():
            ans, aname = _local(attr)
            low = aname.lower()
            if low.startswith("on"):
                raise Refused(f"The SVG has an event handler ({aname}).")
            if low in LINK_ATTRS or (ans == XLINK_NS and low == "href"):
                if not str(value).strip().startswith("#"):
                    raise Refused("The SVG links to something outside itself.")
            if OUTSIDE.search(str(value)):
                raise Refused("The SVG points to something outside itself.")
        if name == "style" and OUTSIDE.search("".join(el.itertext())):
            raise Refused("The SVG's style points to something outside itself.")
    return None


def _length(raw) -> float | None:
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*(px)?\s*$", str(raw or ""))
    return float(m.group(1)) if m else None


def svg_size(root) -> tuple[int, int] | None:
    box = (root.attrib.get("viewBox") or "").replace(",", " ").split()
    if len(box) == 4:
        try:
            w, h = float(box[2]), float(box[3])
        except ValueError:
            w = h = 0
        if w > 0 and h > 0:
            return max(1, round(w)), max(1, round(h))
    w, h = _length(root.attrib.get("width")), _length(root.attrib.get("height"))
    if w and h:
        return max(1, round(w)), max(1, round(h))
    return None


# ----------------------------------------------------------------- checks

def check(body: bytes, kinds=tuple(CTYPES)) -> tuple[str, tuple[int, int] | None]:
    """(kind, size) of an image Skald will keep, or Refused. `kinds`: the
    types allowed here."""
    kind = kind_of(body)
    if kind is None or kind not in kinds:
        names = ", ".join(k.upper() for k in kinds)
        raise Refused(f"Not an image of a type Skald keeps here ({names}).")
    if kind == "svg":
        check_svg(body)
    size = size_of(body, kind)
    if size is None and kind != "svg":
        raise Refused("The image's size cannot be read; the file may be damaged.")
    return kind, size


def check_upload(body: bytes, limit: int) -> tuple[str, tuple[int, int] | None]:
    """An uploaded logo: PNG, ICO or a safe SVG, at most `limit` bytes,
    square (within 10%), at least 64 x 64 (SVG scales, so only square)."""
    if not body:
        raise Refused("The file is empty.")
    if len(body) > limit:
        raise Refused(f"The file is over {limit // 1024} KB.")
    kind, size = check(body, UPLOAD_KINDS)
    if size is not None:
        w, h = size
        if not SQUARE[0] <= w / h <= SQUARE[1]:
            raise Refused(f"The logo is {w} x {h}; it needs to be square.")
        if kind != "svg" and min(w, h) < UPLOAD_MIN:
            raise Refused(f"The logo is {w} x {h}; it needs at least "
                          f"{UPLOAD_MIN} x {UPLOAD_MIN}.")
    return kind, size
