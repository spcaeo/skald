#!/usr/bin/env python3
"""Build the dashboard's world map: skald/webapp/vendor/world-110m.js.

    python3 -I tools/world-map.py ne_110m_admin_0_countries.geojson

The input is Natural Earth's 1:110m "Admin 0 - Countries" (public domain,
naturalearthdata.com; the GeoJSON copy in github.com/nvkelso/natural-earth-vector,
geojson/ne_110m_admin_0_countries.geojson). It is downloaded once by hand and
never fetched by the dashboard: the output is a plain ES module with SVG path
data, so the page draws the map with no request and no third-party code.

What it does, standard library only:
  * keys each country by its ISO 3166-1 alpha-2 code (ISO_A2, else ISO_A2_EH:
    France and Norway carry -99 in ISO_A2); a shape with neither (Northern
    Cyprus, Somaliland) is left out, and so is Antarctica
  * projects longitude and latitude with the Equal Earth projection (Šavrič,
    Patterson, Jenny 2018), so areas are true and no country looks bigger
    than it is
  * simplifies each ring (Douglas-Peucker, TOLERANCE in map units) and drops
    rings smaller than MIN_AREA, then writes relative path commands
  * a point per country for the "active now" bubble: the area-weighted centre
    of its largest ring; countries too small for the 1:110m shapes (Singapore,
    Hong Kong, Malta...) get a point from EXTRA_POINTS and are drawn as a dot

Run it again only to change the projection or the detail; commit the output.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "skald" / "webapp" / "vendor" / "world-110m.js"
WIDTH = 1000.0
TOLERANCE = 0.55          # map units (the map is WIDTH wide)
MIN_AREA = 2.0            # square map units: smaller islands are dropped
SKIP = {"AQ"}             # Antarctica: no visitors, much height
# Small countries the 1:110m shapes do not hold: (latitude, longitude).
EXTRA_POINTS = {
    "SG": (1.35, 103.82), "HK": (22.32, 114.17), "MO": (22.19, 113.54), "MT": (35.9, 14.45),
    "BH": (26.07, 50.55), "MU": (-20.3, 57.58), "MV": (3.2, 73.22), "BB": (13.19, -59.54),
    "AD": (42.55, 1.6), "LI": (47.16, 9.55), "MC": (43.74, 7.42), "SM": (43.94, 12.46),
    "BM": (32.32, -64.76), "KY": (19.31, -81.25), "LU": (49.82, 6.13), "CV": (16.0, -24.0),
    "SC": (-4.68, 55.49), "TO": (-21.18, -175.2), "WS": (-13.76, -172.1), "AG": (17.06, -61.8),
    "LC": (13.91, -60.98), "GD": (12.12, -61.68), "KN": (17.36, -62.78), "VC": (13.25, -61.2),
    "DM": (15.41, -61.37), "AW": (12.52, -69.97), "CW": (12.17, -68.98), "GI": (36.14, -5.35),
    "JE": (49.21, -2.13), "GG": (49.45, -2.58), "IM": (54.24, -4.55), "FO": (62.0, -6.79),
    "PF": (-17.68, -149.4), "RE": (-21.12, 55.54), "GP": (16.25, -61.58), "MQ": (14.64, -61.02),
    "KI": (1.87, -157.36), "FM": (6.92, 158.16), "MH": (7.13, 171.18), "PW": (7.51, 134.58),
    "ST": (0.19, 6.61), "KM": (-11.88, 43.87),
}

# Equal Earth
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def equal_earth(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    t = math.asin(M * math.sin(phi))
    t2, t6 = t * t, t ** 6
    x = 2 * math.sqrt(3) * lam * math.cos(t) / (3 * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


X_MAX = equal_earth(180, 0)[0]
Y_TOP = equal_earth(0, 84)[1]          # the north edge kept (Greenland's tip)
Y_BOTTOM = equal_earth(0, -58)[1]      # the south edge kept (Tierra del Fuego)
SCALE = WIDTH / (2 * X_MAX)
HEIGHT = round((Y_TOP - Y_BOTTOM) * SCALE, 1)


def to_map(lon: float, lat: float) -> tuple[float, float]:
    x, y = equal_earth(lon, lat)
    return (x + X_MAX) * SCALE, (Y_TOP - y) * SCALE


def _dist(p, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - x1 - t * dx, y - y1 - t * dy)


def simplify(points: list, tol: float) -> list:
    """Douglas-Peucker, iterative (rings can be long)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        best, at = 0.0, -1
        for k in range(i + 1, j):
            d = _dist(points[k], points[i], points[j])
            if d > best:
                best, at = d, k
        if best > tol and at > 0:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, k in zip(points, keep) if k]


def area_centre(ring: list) -> tuple[float, float, float]:
    """(signed area, centre x, centre y) of a closed ring."""
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    if abs(a) < 1e-9:
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return a / 2, cx / (3 * a), cy / (3 * a)


def path_of(rings: list) -> str:
    """Relative SVG path commands, coordinates to one decimal."""
    out = []
    for ring in rings:
        pts = [(round(x * 10), round(y * 10)) for x, y in ring]
        dedup = [pts[0]] + [p for q, p in zip(pts, pts[1:]) if p != q]
        if len(dedup) < 3:
            continue
        x0, y0 = dedup[0]
        parts = [f"M{_n(x0)} {_n(y0)}"]
        steps = []
        for (ax, ay), (bx, by) in zip(dedup, dedup[1:]):
            steps.append(f"{_n(bx - ax)} {_n(by - ay)}")
        parts.append("l" + " ".join(steps) + "z")
        out.append("".join(parts))
    return "".join(out).replace(" -", "-")


def _n(v: int) -> str:
    """A tenth-unit integer as text: 125 -> 12.5, -3 -> -.3, 40 -> 4."""
    s = f"{v / 10:.1f}".rstrip("0").rstrip(".")
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return s or "0"


def code_of(props: dict) -> str | None:
    for key in ("ISO_A2", "ISO_A2_EH"):
        v = str(props.get(key) or "")
        if len(v) == 2 and v.isalpha():
            return v.upper()
    return None


def build(geo: dict) -> dict:
    paths, points = {}, {}
    for feature in geo["features"]:
        code = code_of(feature.get("properties") or {})
        if code is None or code in SKIP:
            continue
        g = feature["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings, best = [], (0.0, None)
        for poly in polys:
            for n, ring in enumerate(poly):
                pts = [to_map(lon, max(-58.0, min(84.0, lat))) for lon, lat in ring]
                a, cx, cy = area_centre(pts)
                if abs(a) < MIN_AREA:
                    continue
                if n == 0 and abs(a) > best[0]:
                    best = (abs(a), (round(cx, 1), round(cy, 1)))
                rings.append(simplify(pts, TOLERANCE)[:-1] or pts)
        if not rings:
            continue
        paths[code] = paths.get(code, "") + path_of(rings)
        if best[1] is not None and code not in points:
            points[code] = list(best[1])
    dots = {}
    for code, (lat, lon) in EXTRA_POINTS.items():
        if code not in paths:
            x, y = to_map(lon, lat)
            dots[code] = [round(x, 1), round(y, 1)]
    return {"width": WIDTH, "height": HEIGHT, "paths": dict(sorted(paths.items())),
            "points": dict(sorted({**points, **dots}.items())), "dots": sorted(dots)}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    geo = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    got = build(geo)
    text = ("// The world map: Natural Earth 1:110m countries (public domain, naturalearthdata.com),\n"
            "// Equal Earth projection, keyed by ISO 3166-1 alpha-2. Written by tools/world-map.py;\n"
            "// do not edit by hand. `dots`: countries too small for these shapes, drawn as a dot.\n"
            f"export const WORLD = {json.dumps(got, separators=(',', ':'))};\n")
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(got['paths'])} countries, {len(got['dots'])} dots, "
          f"{len(text.encode()) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
