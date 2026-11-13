"""Where each finished conversion happened (#52): the page it was made on and
the pages read before it in the same visit. conversions.json, per day:

    pages_at    {action: {page: n}}   the page last seen at or before the action
    paths_to    {action: {path: n}}   that visit's pages up to it, in order
    page_link   {action: {road: n}}   how each was tied to its visit (PAGE_ROADS)
    page_form   {action: n}           of the server_log ones, how many took the
                                      page the form was sent from (#57)

A conversion is tied to its visit by a proven link only, never a likely one
(people/lead_visits' "same address and browser" is not used):

    visitor_id  the row's visitor ID has a page view (the beacon's journeys) at
                or before its time and no more than VISIT_GAP before it. The
                visit is the views back from there no more than VISIT_GAP
                apart (as the beacon's landing is); its page, the last one.
    server_log  else, the only kept server-log visit (visits) that sent a form
                within FORM_SECONDS of the row's time (lead_visits' proven
                rule), at its own form time nearest the row's (the first of
                them in the visit's list on a tie). Its page:
                - the page that form was sent from, when kept (#57, schema 11:
                  `visits.posts_from`, the form's same-site referrer, aligned
                  with `posts`). Its path: the trail's pages up to that page's
                  last appearance at or before the form's step; when the trail
                  does not hold it there, the pages strictly before the form's
                  step, then that page. Counted in `page_form`.
                - else (a row kept before schema 11, NULL; a form sent with no
                  referrer from this site, "") the last trail page seen at or
                  before the form was sent. The trail's times are offsets from
                  the visit's start rounded down (visits.seconds_bucket): to the
                  second under a minute, so a page seen in the form's own second
                  counts as before; past a minute a page in the form's own step
                  (10 s, a minute, 10 minutes) cannot be told before or after,
                  and the page is PAGE_UNKNOWN.
    none        neither: PAGE_NOT_KEPT when the server-log visits of the row's
                local day are not kept (visit_days has no row: the site keeps
                no addresses, or the day is past privacy.keep_days), else
                PAGE_UNKNOWN. Never dropped.

A path is the visit's pages in order, a page seen twice in a row once, joined
by PATH_JOIN; only the last PATH_PAGES are written (an older start is
PATH_MORE). Every finished row counts once in pages_at, paths_to and
page_link, so each adds up to the day's finished rows; page_form is a part
of page_link's server_log. Counted here in Python; the second road is
audit_conversions_page.py, by SQL (window functions and json_each).
"""
from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

from .conversions import (PAGE_NOT_KEPT, PAGE_UNKNOWN, PATH_JOIN, PATH_MORE, PATH_PAGES,
                          VISIT_GAP, store)
from .visits import seconds_bucket

FORM_SECONDS = 10           # people/lead_visits.PROVEN_SECONDS
EXACT = 60                  # under this, a trail offset is kept to the second


def path_text(pages: list[str]) -> str:
    """The pages in order, a repeat in a row once, the last PATH_PAGES."""
    out = [p for i, p in enumerate(pages) if i == 0 or p != pages[i - 1]]
    return PATH_JOIN.join(([PATH_MORE] if len(out) > PATH_PAGES else []) + out[-PATH_PAGES:])


class Finder:
    """Ties finished conversions of [first, last] (local days) to their visit."""

    def __init__(self, db, site: str, tz, first: date, last: date):
        self.db, self.site, self.tz = db, site, tz
        lo, hi = (first - timedelta(days=1)).isoformat(), (last + timedelta(days=1)).isoformat()
        self.kept = {d for (d,) in db.execute(
            "SELECT day FROM visit_days WHERE site = ? AND day BETWEEN ? AND ?", (site, lo, hi))}
        self.visits: dict[tuple, tuple] = {}
        # (form time, visit, its place in the visit's list, the page it was sent from)
        posts: list[tuple[str, tuple, int, str | None]] = []
        for day, seq, start, trail, raw, sent_from in db.execute(
                "SELECT day, seq, start, trail, posts, posts_from FROM visits WHERE site = ? "
                "AND day BETWEEN ? AND ? AND posts IS NOT NULL AND posts <> '[]'",
                (site, lo, hi)):
            try:
                stamps = json.loads(raw or "[]")
            except ValueError:
                continue
            if not isinstance(stamps, list):
                continue
            froms = _froms(sent_from, len(stamps))
            key = (day, seq)
            self.visits[key] = (start, trail)
            for i, t in enumerate(stamps):
                if isinstance(t, str) and _ok(t):
                    posts.append((t, key, i, froms[i]))
        posts.sort(key=lambda p: p[:3])
        self.posts = posts
        self.times = [p[0] for p in posts]

    def where(self, row) -> tuple[str, str, str, bool]:
        """(road, page, path, from the form) of one finished row (see the
        module): the last True when the page is the one its form was sent from."""
        if row["vid"]:
            got = self._by_vid(row["vid"], row["at"])
            if got is not None:
                return ("visitor_id", *got, False)
        found = self._by_form(row["at"])
        if found is not None:
            key, post, page = found
            if page:
                return ("server_log", *self._from_page(key, post, page), True)
            return ("server_log", *self._from_trail(key, post), False)
        day = store.parse(row["at"]).astimezone(self.tz).date().isoformat()
        label = PAGE_UNKNOWN if day in self.kept else PAGE_NOT_KEPT
        return "none", label, label, False

    def _by_vid(self, vid: str, at: str):
        pages, before = [], store.parse(at)
        for when, path in self.db.execute(
                "SELECT at, path FROM journeys WHERE site = ? AND vid = ? AND at <= ? "
                "ORDER BY at DESC, rowid DESC", (self.site, vid, at)):
            moment = store.parse(when)
            if (before - moment).total_seconds() > VISIT_GAP:
                break
            pages.append(path)
            before = moment
        if not pages:
            return None
        pages.reverse()
        return pages[-1], path_text(pages)

    def _by_form(self, at: str):
        when = store.parse(at)
        a = store.stamp(when - timedelta(seconds=FORM_SECONDS))
        b = store.stamp(when + timedelta(seconds=FORM_SECONDS))
        near = self.posts[bisect_left(self.times, a):bisect_right(self.times, b)]
        if len({p[1] for p in near}) != 1:
            return None
        t, key, _, page = min(near, key=lambda p: (
            abs((store.parse(p[0]) - when).total_seconds()), p[0], p[2]))
        return key, t, page

    def _step(self, key: tuple, post: str):
        """(the visit's trail, the form's rounded step), or (None, None)."""
        start, raw = self.visits[key]
        try:
            trail = json.loads(raw or "[]")
            sent = seconds_bucket(int((store.parse(post) - store.parse(start)).total_seconds()))
        except (TypeError, ValueError):
            return None, None
        return (trail if isinstance(trail, list) else []), sent

    def _from_page(self, key: tuple, post: str, page: str) -> tuple[str, str]:
        """#57: the page the form was sent from, and the trail's pages up to it."""
        trail, sent = self._step(key, post)
        timed = []                          # the trail's pages while their offsets are known
        for item in trail or ():
            offset = item[2] if isinstance(item, list) and len(item) > 2 else None
            if not isinstance(offset, int):
                break
            timed.append((str(item[0]), offset))
        upto = list(_while(timed, lambda o: o <= sent))
        last = max((i for i, (p, _) in enumerate(upto) if p == page), default=None)
        if last is not None:
            return page, path_text([p for p, _ in upto[:last + 1]])
        return page, path_text([p for p, _ in _while(timed, lambda o: o < sent)] + [page])

    def _from_trail(self, key: tuple, post: str) -> tuple[str, str]:
        trail, sent = self._step(key, post)
        if trail is None:
            return PAGE_UNKNOWN, PAGE_UNKNOWN
        before = []
        for item in trail:
            offset = item[2] if isinstance(item, list) and len(item) > 2 else None
            if not isinstance(offset, int):
                return PAGE_UNKNOWN, PAGE_UNKNOWN
            if offset > sent:
                break
            if offset == sent and sent >= EXACT:
                return PAGE_UNKNOWN, PAGE_UNKNOWN       # in the form's own step
            before.append(str(item[0]))
        if not before:
            return PAGE_UNKNOWN, PAGE_UNKNOWN
        return before[-1], path_text(before)


def _while(timed: list, keep) -> list:
    """The leading (page, offset) pairs whose offset `keep` holds."""
    out = []
    for page, offset in timed:
        if not keep(offset):
            break
        out.append((page, offset))
    return out


def _froms(raw, n: int) -> list:
    """The page each of a visit's `n` forms was sent from (#57): a page, or
    None (not kept: NULL, unreadable, not aligned with `posts`, or "")."""
    try:
        got = json.loads(raw) if raw is not None else None
    except ValueError:
        got = None
    if not isinstance(got, list) or len(got) != n:
        return [None] * n
    return [p if isinstance(p, str) and p else None for p in got]


def _ok(text: str) -> bool:
    try:
        store.parse(text)
    except ValueError:
        return False
    return True
