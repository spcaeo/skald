"""A small PDF writer, standard library only: text, rules, filled shapes and
raster logos on A4 pages (the client reports, client_report_pdf.py).

Why not print the HTML to PDF: that needs a browser, and the Docker image
has none (docker/Dockerfile). A report is text, tables and bars, all of which
PDF draws natively as vectors, so a few hundred lines are enough:

  * fonts: the two built-in Helvetica faces (every PDF reader has them, so
    nothing is embedded), WinAnsi encoded; the widths below are Adobe's
    metrics, so text can be measured, cut with "..." and wrapped. A character
    WinAnsi cannot show is written "?" (an accent is kept when it can be).
  * shapes: rectangles (optionally rounded at the top, for bars), lines
  * images: PNG (8-bit, or a palette at any depth; transparency kept as a
    soft mask), baseline JPEG, and an ICO holding a PNG. Anything else
    (SVG, a bitmap ICO, 16-bit PNG) is refused with None: the caller draws
    the letter instead.

Coordinates are points (1/72 inch) from the page's top left corner; `y` of
text is its baseline. The file is PDF 1.4: one cross-reference table with
every object's byte offset, which `tests/test_pdf_writer.py` reads back.
"""
from __future__ import annotations

import struct
import unicodedata
import zlib
from datetime import datetime, timezone

A4 = (595.28, 841.89)
K = 0.5523                              # a quarter circle as one Bezier curve

# Adobe's Helvetica and Helvetica-Bold widths (1/1000 em) for ASCII 32..126.
_REG = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
        556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
        1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
        333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
        556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
         556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
         975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
         333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
         611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]
# A few WinAnsi characters past ASCII, by their code: same width in both faces.
_HIGH = {0x80: 556, 0x85: 1000, 0x91: 222, 0x92: 222, 0x93: 333, 0x94: 333, 0x95: 350,
         0x96: 556, 0x97: 1000, 0xA0: 278, 0xA9: 737, 0xB0: 400, 0xB7: 278, 0xD7: 584}


class ImageError(ValueError):
    """Bytes that are not an image this writer can place."""


# ------------------------------------------------------------- the text

def encode(text: str) -> bytes:
    """`text` in WinAnsi (cp1252): an accent the encoding lacks is dropped
    from its letter; anything else becomes "?"."""
    out = bytearray()
    for ch in str(text):
        try:
            out += ch.encode("cp1252")
            continue
        except UnicodeEncodeError:
            pass
        base = "".join(c for c in unicodedata.normalize("NFKD", ch)
                       if not unicodedata.combining(c))
        try:
            out += base.encode("cp1252") if base else b"?"
        except UnicodeEncodeError:
            out += b"?"
    return bytes(out)


def _width_of(code: int, bold: bool) -> int:
    if 32 <= code <= 126:
        return (_BOLD if bold else _REG)[code - 32]
    if code in _HIGH:
        return _HIGH[code]
    if code >= 0xC0:                    # an accented letter: its base letter's width
        base = unicodedata.normalize("NFKD", bytes([code]).decode("cp1252"))[:1]
        if base and 32 <= ord(base) <= 126:
            return (_BOLD if bold else _REG)[ord(base) - 32]
    return 556


def text_width(text: str, size: float, bold: bool = False) -> float:
    return sum(_width_of(c, bold) for c in encode(text)) * size / 1000


def fit(text: str, size: float, width: float, bold: bool = False) -> str:
    """`text`, cut with "..." when it is wider than `width`."""
    text = str(text)
    if text_width(text, size, bold) <= width:
        return text
    dots = text_width("...", size, bold)
    lo, hi = 0, len(text)
    while lo < hi:                       # the longest prefix that fits with the dots
        mid = (lo + hi + 1) // 2
        if text_width(text[:mid], size, bold) + dots <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "..."


def wrap(text: str, size: float, width: float, bold: bool = False) -> list[str]:
    """`text` broken into lines no wider than `width` (a word wider than a
    line is cut); a newline in it starts a new line."""
    lines: list[str] = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split():
            trial = f"{line} {word}" if line else word
            if text_width(trial, size, bold) <= width:
                line = trial
                continue
            if line:
                lines.append(line)
            line = word if text_width(word, size, bold) <= width else fit(word, size, width, bold)
        lines.append(line)
    return lines


def _literal(data: bytes) -> str:
    """A PDF string literal, ASCII only."""
    out = []
    for b in data:
        if b in (0x28, 0x29, 0x5C):
            out.append("\\" + chr(b))
        elif 32 <= b <= 126:
            out.append(chr(b))
        else:
            out.append(f"\\{b:03o}")
    return "(" + "".join(out) + ")"


def _rgb(color: str) -> tuple[float, float, float]:
    c = str(color).lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    if len(c) != 6:
        raise ValueError(f"not a colour: {color!r}")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _n(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))


# ------------------------------------------------------------- the images

def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _unfilter(raw: bytes, width: int, height: int, bpp: int, row_bytes: int) -> bytes:
    out = bytearray()
    prev = bytearray(row_bytes)
    pos = 0
    for _ in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + row_bytes])
        pos += 1 + row_bytes
        if len(line) != row_bytes:
            raise ImageError("PNG data is short")
        if kind == 1:
            for i in range(bpp, row_bytes):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif kind == 2:
            for i in range(row_bytes):
                line[i] = (line[i] + prev[i]) & 255
        elif kind == 3:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif kind == 4:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 255
        elif kind != 0:
            raise ImageError("unknown PNG filter")
        out += line
        prev = line
    return bytes(out)


def decode_png(data: bytes) -> tuple[int, int, bytes, bytes | None]:
    """(width, height, RGB bytes, alpha bytes or None)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ImageError("not a PNG")
    pos, idat, palette, trns, head = 8, bytearray(), b"", b"", None
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if head is None:
        raise ImageError("PNG without a header")
    width, height, depth, ctype, _, _, interlace = head
    if interlace or not (0 < width <= 4096 and 0 < height <= 4096):
        raise ImageError("interlaced or too large")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if channels is None or (ctype != 3 and depth != 8) or depth not in (1, 2, 4, 8):
        raise ImageError("a PNG kind this writer does not read (16-bit?)")
    row_bytes = (width * channels * depth + 7) // 8
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as why:
        raise ImageError("broken PNG data") from why
    pixels = _unfilter(raw, width, height, max(1, channels * depth // 8), row_bytes)
    rgb, alpha = bytearray(), bytearray()
    if ctype == 3:
        if not palette:
            raise ImageError("palette PNG without a palette")
        per = 8 // depth
        mask = (1 << depth) - 1
        for y in range(height):
            row = pixels[y * row_bytes:(y + 1) * row_bytes]
            for x in range(width):
                i = (row[x // per] >> ((per - 1 - x % per) * depth)) & mask
                rgb += palette[i * 3:i * 3 + 3] or b"\0\0\0"
                alpha.append(trns[i] if i < len(trns) else 255)
        return width, height, bytes(rgb), bytes(alpha) if trns else None
    if ctype == 2:
        return width, height, pixels, None
    if ctype == 0:
        return width, height, bytes(b for g in pixels for b in (g, g, g)), None
    step = channels
    for i in range(0, len(pixels), step):
        if ctype == 4:
            rgb += bytes((pixels[i],) * 3)
        else:
            rgb += pixels[i:i + 3]
        alpha.append(pixels[i + step - 1])
    return width, height, bytes(rgb), bytes(alpha)


def jpeg_size(data: bytes) -> tuple[int, int, int]:
    """(width, height, components) from a JPEG's frame header."""
    if data[:2] != b"\xff\xd8":
        raise ImageError("not a JPEG")
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ImageError("broken JPEG")
        marker = data[pos + 1]
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return width, height, data[pos + 9]
        pos += 2 + length
    raise ImageError("JPEG without a frame header")


def png_in_ico(data: bytes) -> bytes | None:
    """The largest PNG an ICO file holds, or None (a bitmap-only icon)."""
    if data[:4] != b"\0\0\1\0" or len(data) < 6:
        return None
    best, size = None, -1
    for i in range(struct.unpack("<H", data[4:6])[0]):
        entry = data[6 + i * 16:22 + i * 16]
        if len(entry) < 16:
            break
        w, length, offset = entry[0] or 256, *struct.unpack("<II", entry[8:16])
        body = data[offset:offset + length]
        if body[:8] == b"\x89PNG\r\n\x1a\n" and w > size:
            best, size = body, w
    return best


class Image:
    def __init__(self, ref: int, width: int, height: int):
        self.ref, self.width, self.height = ref, width, height


# ------------------------------------------------------------- the pages

class Page:
    def __init__(self, doc: "Document"):
        self.doc, self.ops, self.images = doc, [], {}
        self.width, self.height = doc.size

    def _y(self, y: float) -> float:
        return self.height - y

    def text(self, x: float, y: float, text: str, size: float = 10, bold: bool = False,
             color: str = "#000000", align: str = "left") -> float:
        """Write `text` with its baseline at `y`; returns its width."""
        w = text_width(text, size, bold)
        if align == "right":
            x -= w
        elif align == "center":
            x -= w / 2
        r, g, b = _rgb(color)
        self.ops.append(f"BT /F{2 if bold else 1} {_n(size)} Tf {r:.3f} {g:.3f} {b:.3f} rg "
                        f"{_n(x)} {_n(self._y(y))} Td {_literal(encode(text))} Tj ET")
        return w

    def rect(self, x: float, y: float, w: float, h: float, fill: str | None = None,
             stroke: str | None = None, width: float = 0.5, radius: float = 0,
             top_only: bool = False) -> None:
        """A rectangle; `radius` rounds its corners (only the top two with `top_only`)."""
        if w <= 0 or h <= 0:
            return
        ops = []
        if fill:
            ops.append("{:.3f} {:.3f} {:.3f} rg".format(*_rgb(fill)))
        if stroke:
            ops.append("{:.3f} {:.3f} {:.3f} RG {} w".format(*_rgb(stroke), _n(width)))
        x0, y0, x1, y1 = x, self._y(y + h), x + w, self._y(y)
        r = min(radius, w / 2, h / 2)
        if r <= 0:
            ops.append(f"{_n(x0)} {_n(y0)} {_n(w)} {_n(h)} re")
        else:
            c = r * K
            rb = 0 if top_only else r
            cb = rb * K
            ops.append(
                f"{_n(x0 + rb)} {_n(y0)} m {_n(x1 - rb)} {_n(y0)} l "
                + (f"{_n(x1 - rb + cb)} {_n(y0)} {_n(x1)} {_n(y0 + rb - cb)} {_n(x1)} {_n(y0 + rb)} c "
                   if rb else "")
                + f"{_n(x1)} {_n(y1 - r)} l {_n(x1)} {_n(y1 - r + c)} {_n(x1 - r + c)} {_n(y1)} "
                f"{_n(x1 - r)} {_n(y1)} c {_n(x0 + r)} {_n(y1)} l {_n(x0 + r - c)} {_n(y1)} "
                f"{_n(x0)} {_n(y1 - r + c)} {_n(x0)} {_n(y1 - r)} c {_n(x0)} {_n(y0 + rb)} l "
                + (f"{_n(x0)} {_n(y0 + rb - cb)} {_n(x0 + rb - cb)} {_n(y0)} {_n(x0 + rb)} {_n(y0)} c "
                   if rb else "") + "h")
        ops.append("B" if fill and stroke else "f" if fill else "S")
        self.ops.append(" ".join(ops))

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = "#000000",
             width: float = 0.5, dash: tuple | None = None) -> None:
        d = f"[{' '.join(_n(v) for v in dash)}] 0 d " if dash else ""
        self.ops.append("q {:.3f} {:.3f} {:.3f} RG {} w {}{} {} m {} {} l S Q".format(
            *_rgb(color), _n(width), d, _n(x1), _n(self._y(y1)), _n(x2), _n(self._y(y2))))

    def image(self, img: Image, x: float, y: float, w: float, h: float) -> None:
        """Draw `img` (Document.image) into the box, keeping its shape, centred."""
        scale = min(w / img.width, h / img.height)
        dw, dh = img.width * scale, img.height * scale
        name = f"Im{img.ref}"
        self.images[name] = img.ref
        self.ops.append(f"q {_n(dw)} 0 0 {_n(dh)} {_n(x + (w - dw) / 2)} "
                        f"{_n(self._y(y + (h - dh) / 2 + dh))} cm /{name} Do Q")


class Document:
    def __init__(self, title: str = "", author: str = "", size=A4):
        self.title, self.author, self.size = title, author, size
        self.pages: list[Page] = []
        self.objects: list[bytes | None] = [None, None, None, None]   # 1 catalog, 2 pages, 3-4 fonts

    def add_page(self) -> Page:
        page = Page(self)
        self.pages.append(page)
        return page

    def _add(self, body: bytes) -> int:
        self.objects.append(body)
        return len(self.objects)

    def _stream(self, head: str, data: bytes) -> int:
        return self._add(f"<< {head} /Length {len(data)} >>\nstream\n".encode("ascii")
                         + data + b"\nendstream")

    def image(self, data: bytes) -> Image | None:
        """Register a PNG, JPEG or ICO-with-PNG; None for anything else."""
        try:
            if data[:4] == b"\0\0\1\0":
                data = png_in_ico(data) or b""
            if data[:2] == b"\xff\xd8":
                w, h, comps = jpeg_size(data)
                space = {1: "/DeviceGray", 3: "/DeviceRGB"}.get(comps)
                if space is None:
                    return None
                ref = self._stream(f"/Type /XObject /Subtype /Image /Width {w} /Height {h} "
                                   f"/ColorSpace {space} /BitsPerComponent 8 /Filter /DCTDecode",
                                   data)
                return Image(ref, w, h)
            w, h, rgb, alpha = decode_png(data)
        except (ImageError, struct.error, IndexError, ValueError):
            return None
        mask = ""
        if alpha is not None and any(a != 255 for a in alpha):
            sref = self._stream(f"/Type /XObject /Subtype /Image /Width {w} /Height {h} "
                                "/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode",
                                zlib.compress(alpha, 9))
            mask = f" /SMask {sref} 0 R"
        ref = self._stream(f"/Type /XObject /Subtype /Image /Width {w} /Height {h} "
                           f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode{mask}",
                           zlib.compress(rgb, 9))
        return Image(ref, w, h)

    def to_bytes(self, now: datetime | None = None) -> bytes:
        if not self.pages:
            self.add_page()
        saved = list(self.objects)       # to_bytes may be called again: it adds nothing
        objects = self.objects
        font = "<< /Type /Font /Subtype /Type1 /BaseFont /{} /Encoding /WinAnsiEncoding >>"
        objects[2] = font.format("Helvetica").encode()
        objects[3] = font.format("Helvetica-Bold").encode()
        kids = []
        for page in self.pages:
            content = self._stream("/Filter /FlateDecode",
                                   zlib.compress("\n".join(page.ops).encode("ascii"), 9))
            xobj = " ".join(f"/{k} {v} 0 R" for k, v in sorted(page.images.items()))
            kids.append(self._add((
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_n(page.width)} {_n(page.height)}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >>"
                + (f" /XObject << {xobj} >>" if xobj else "") +
                f" >> /Contents {content} 0 R >>").encode("ascii")))
        objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objects[1] = (f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] "
                      f"/Count {len(kids)} >>").encode("ascii")
        when = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        info = self._add(("<< /Title " + _literal(encode(self.title)) + " /Author "
                          + _literal(encode(self.author)) + " /Producer (Skald) /CreationDate "
                          + f"(D:{when:%Y%m%d%H%M%S}Z) >>").encode("ascii"))
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(self.objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objects) + 1}\n0000000000 65535 f \n".encode("ascii")
        out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode("ascii")
        out += (f"trailer\n<< /Size {len(self.objects) + 1} /Root 1 0 R /Info {info} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n").encode("ascii")
        self.objects = saved
        return bytes(out)
