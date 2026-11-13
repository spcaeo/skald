"""The second count of where each finished conversion happened (#52):
conversions.json's per-day `pages_at`, `paths_to`, `page_link` and
`page_form` (conversions_pages.py), counted again over conversions.sqlite opened
read-only, by this road's own SQL.

conversions_pages.py walks a visitor ID's page views back from the action
in Python and finds the form's visit by a bisect over every form time; here
a visitor ID's views are cut into visits forward, by SQL window functions
(LAG, then a running SUM of the gaps over VISIT_GAP), and the visit that
sent a form is found by a join of the finished rows with every form time
(json_each over `visits.posts`, each form's own page read from
`visits.posts_from` at the same place by json_extract, #57), its trail read
by json_each and json_extract, its steps rounded down by this module's own
table. When that form's page is kept, it is the page, and the path runs to
its last place in the trail up to the form's step (else the pages before
that step, then it); when not, the trail decides as before. It shares
only the name lists in conversions/__init__.py (the finished stages, the
labels for a page not known, the roads, the path's joiner and length,
VISIT_GAP) and the file's location. Called by audit_conversions.check_file;
a day it disagrees with is withheld.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from itertools import groupby
from pathlib import Path

from .audit_conversions_figures import _bounds, _fin, _open, once
from .conversions import (PAGE_NOT_KEPT, PAGE_ROADS, PAGE_UNKNOWN, PATH_JOIN, PATH_MORE,
                          PATH_PAGES, VISIT_GAP)

SECONDS = 10                # a form sent this close to the conversion's time
# (below, width): a trail offset under `below` seconds is kept to `width` (visits.py).
STEPS = ((60, 1), (600, 10), (3600, 60), (None, 600))

VID, FORM, NONE = PAGE_ROADS


def _step(seconds: int) -> tuple[int, int]:
    """(the offset rounded down, its step's width)."""
    s = seconds if seconds > 0 else 0
    for below, width in STEPS:
        if below is None or s < below:
            return s // width * width, width
    raise AssertionError


def _path(pages: list[str]) -> str:
    kept = [p for p, _ in groupby(pages)]
    head = [PATH_MORE] if len(kept) > PATH_PAGES else []
    return PATH_JOIN.join(head + kept[len(kept) - min(len(kept), PATH_PAGES):])


VISITS = ("WITH v AS (SELECT path, at, rowid AS r, CAST(strftime('%s', at) AS INTEGER) AS s "
          "FROM journeys WHERE site = ? AND vid = ? AND CAST(strftime('%s', at) AS INTEGER) "
          "<= ?), w AS (SELECT path, at, r, s, s - LAG(s) OVER (ORDER BY at, r) AS gap "
          "FROM v), x AS (SELECT path, at, r, s, SUM(CASE WHEN gap > ? THEN 1 ELSE 0 END) "
          "OVER (ORDER BY at, r) AS n FROM w) "
          "SELECT path, s FROM x WHERE n = (SELECT MAX(n) FROM x) ORDER BY at, r")
TRAIL = ("SELECT json_extract(t.value, '$[0]'), json_extract(t.value, '$[2]') FROM visits v, "
         "json_each(CASE WHEN json_valid(v.trail) THEN v.trail ELSE '[]' END) t "
         "WHERE v.site = ? AND v.day = ? AND v.seq = ? ORDER BY CAST(t.key AS INTEGER)")


def _by_vid(db, site: str, vid: str, at: int):
    rows = db.execute(VISITS, (site, vid, at, VISIT_GAP)).fetchall()
    if not rows or at - rows[-1][1] > VISIT_GAP:
        return None
    return rows[-1][0], _path([p for p, _ in rows])


def _from_page(db, site: str, visit: tuple, post: int, start: int | None, page: str):
    """#57: the form's own page; the path to its last place up to the form's step."""
    if start is None:
        return page, _path([page])
    sent, _ = _step(post - start)
    trail = db.execute(TRAIL, (site, *visit)).fetchall()
    stop = next((i for i, (_, o) in enumerate(trail) if not isinstance(o, int)), len(trail))
    timed = trail[:stop]
    upto = timed[:next((i for i, (_, o) in enumerate(timed) if o > sent), len(timed))]
    pages = [str(p) for p, _ in upto]
    if page in pages:
        return page, _path(pages[:len(pages) - pages[::-1].index(page)])
    before = timed[:next((i for i, (_, o) in enumerate(timed) if o >= sent), len(timed))]
    return page, _path([str(p) for p, _ in before] + [page])


def _from_trail(db, site: str, visit: tuple, post: int, start: int | None):
    if start is None:
        return PAGE_UNKNOWN, PAGE_UNKNOWN
    sent, width = _step(post - start)
    trail = db.execute(TRAIL, (site, *visit)).fetchall()
    # The pages up to the first one surely seen after the form.
    upto = next((i for i, (_, o) in enumerate(trail)
                 if isinstance(o, int) and o > sent), len(trail))
    seen = trail[:upto]
    if not seen or any(not isinstance(o, int) for _, o in seen):
        return PAGE_UNKNOWN, PAGE_UNKNOWN
    if width > 1 and any(o == sent for _, o in seen):
        return PAGE_UNKNOWN, PAGE_UNKNOWN          # the form's own step: before or after
    pages = [str(p) for p, _ in seen]
    return pages[-1], _path(pages)


def recount(path: Path, site: str, tz, first: date, last: date) -> dict[str, Counter]:
    """{day: Counter} keyed ("page", action, page), ("path", action, path)
    and ("link", action, road), for every finished row of [first, last], and
    ("form", action, "page_form") for each that took its form's own page."""
    head, args = _bounds(tz, first, last)
    lo, hi = (first - timedelta(days=1)).isoformat(), (last + timedelta(days=1)).isoformat()
    finished = (f"c AS (SELECT b.day AS day, c.id AS id, c.action AS action, c.vid AS vid, "
                f"CAST(strftime('%s', c.at) AS INTEGER) AS s, EXISTS (SELECT 1 FROM visit_days "
                f"d WHERE d.site = c.site AND d.day = b.day) AS kept FROM conversions c JOIN b "
                f"ON c.at >= b.lo AND c.at < b.hi WHERE c.site = ? AND c.test = 0 AND "
                f"c.stage IN {_fin()} AND {once()})")
    out: dict[str, Counter] = {}
    db = _open(path)
    try:
        rows = db.execute(head.rstrip() + ", " + finished +
                          " SELECT id, day, action, vid, s, kept FROM c", [*args, site]).fetchall()
        forms: dict[int, list] = {}
        for cid, vday, seq, ps, start, place, sent_from in db.execute(
                head.rstrip() + ", " + finished + ", p AS (SELECT v.day AS vday, v.seq AS seq, "
                "CAST(strftime('%s', v.start) AS INTEGER) AS start, CAST(strftime('%s', "
                "j.value) AS INTEGER) AS ps, CAST(j.key AS INTEGER) AS place, CASE WHEN "
                "json_valid(v.posts_from) AND json_type(v.posts_from) = 'array' AND "
                "json_array_length(v.posts_from) = json_array_length(v.posts) AND "
                "json_type(v.posts_from, '$[' || j.key || ']') = 'text' THEN "
                "json_extract(v.posts_from, '$[' || j.key || ']') END AS sent_from "
                "FROM visits v, json_each(CASE WHEN json_valid(v.posts) AND json_type(v.posts) "
                "= 'array' THEN v.posts ELSE '[]' END) j WHERE v.site = ? AND v.day "
                "BETWEEN ? AND ? AND j.type = 'text') SELECT c.id, p.vday, p.seq, p.ps, "
                "p.start, p.place, p.sent_from FROM c JOIN p ON p.ps IS NOT NULL AND p.ps "
                "BETWEEN c.s - ? AND c.s + ?",
                [*args, site, site, lo, hi, SECONDS, SECONDS]):
            forms.setdefault(cid, []).append(((vday, seq), ps, start, place, sent_from or ""))
        for cid, day, action, vid, at, kept in rows:
            got = _by_vid(db, site, vid, at) if vid else None
            road, own = VID, False
            if got is None:
                mine = forms.get(cid) or []
                if len({m[0] for m in mine}) == 1:
                    road = FORM
                    visit, post, start, _, page = min(
                        mine, key=lambda m: (abs(m[1] - at), m[1], m[3]))
                    own = page != ""
                    got = (_from_page(db, site, visit, post, start, page) if own
                           else _from_trail(db, site, visit, post, start))
                else:
                    road = NONE
                    label = PAGE_UNKNOWN if kept else PAGE_NOT_KEPT
                    got = (label, label)
            n = out.setdefault(day, Counter())
            n[("link", action, road)] += 1
            n[("page", action, got[0])] += 1
            n[("path", action, got[1])] += 1
            if own:
                n[("form", action, "page_form")] += 1
    finally:
        db.close()
    return out


def _flat(day: dict) -> Counter:
    out: Counter = Counter()
    for name, kind in (("pages_at", "page"), ("paths_to", "path"), ("page_link", "link")):
        for action, per in (day.get(name) or {}).items():
            for key, n in per.items():
                out[(kind, action, key)] += n
    for action, n in (day.get("page_form") or {}).items():
        out[("form", action, "page_form")] += n
    return +out


def check(path: Path, site: str, tz, first: date, last: date,
          days: list[dict]) -> dict[str, list[str]]:
    """{day: problems} for every shown day whose page, path or link counts
    the SQL recount disagrees with."""
    shown = [d for d in days if d.get("state") == "ok"]
    if not shown:
        return {}
    counted = recount(path, site, tz, first, last)
    out: dict[str, list[str]] = {}
    for d in shown:
        mine, theirs = _flat(d), +counted.get(d["day"], Counter())
        for key in sorted(set(mine) | set(theirs), key=str):
            if mine[key] != theirs[key]:
                out.setdefault(d["day"], []).append(
                    f"{d['day']} {' '.join(map(str, key))}: file {mine[key]}, "
                    f"SQL recount {theirs[key]}")
    return out
