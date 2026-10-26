"""The performance work changes no figure (docs/PERFORMANCE.md).

One fixture - six collected days of synthetic traffic (tools/bench_data.py,
documentation addresses and example.com only), three views, returning
visitors, today's live snapshot - is drawn twice: with the code as it is,
and with the slower code it replaced put back (kept below as references).
Every data file must come out the same, byte for byte once the build time
is set aside; so must compare and every page's story. And the schema
upgrades (history 12, accounts 5, conversions 3) only add indexes.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))

import bench_data  # noqa: E402
from support import Sandbox  # noqa: E402
from skald import (ai_likely, compare, data_files, data_reports,  # noqa: E402
                          lifecycle, store)
from skald.config import load_config  # noqa: E402
from skald.store import History  # noqa: E402

TODAY = date(2026, 10, 12)
TZ = ZoneInfo("America/New_York")
PATHS = bench_data.pages(30)
VIEWS = ["{name: Canada, path_prefix: /ca/}", "{name: Guides, path_prefix: /guides/}"]
KEY = {"SKALD_VISITOR_KEY": "test-only-dummy-key"}
BOX = None


def setUpModule():
    global BOX
    with mock.patch.dict(os.environ, KEY):
        BOX = Sandbox(mail=False, tz="America/New_York", views=VIEWS)
        BOX.config.write_text(BOX.config.read_text().replace(
            "  app: false\n", "  app: true\n"))
        today = ("--today", TODAY.isoformat())
        for i in range(6, 0, -1):
            day = TODAY - timedelta(days=i)
            log = BOX.root / f"day-{day}.log"
            log.write_text("".join(bench_data.day_lines(day, TZ, 1500, PATHS, seed=i,
                                                        people=0.08)))
            code, _, err = BOX.run(*today, "collect", "--day", day.isoformat(), "--log", str(log))
            assert code == 0, err
        midnight = datetime.combine(TODAY, time(0), tzinfo=TZ)
        BOX.log(bench_data.day_lines(TODAY, TZ, 1500, PATHS, seed=99, people=0.08,
                                     until=midnight + timedelta(hours=12)))
        code, _, err = BOX.run(*today, "live")
        assert code in (0, 1), err


def tearDownModule():
    BOX.close()


def draw(out: Path) -> dict[str, object]:
    """Every file `skald dashboard` writes, JSON without its build time."""
    with mock.patch.dict(os.environ, KEY):
        code, _, err = BOX.run("--today", TODAY.isoformat(), "dashboard", "--out", str(out))
    assert code == 0, err
    got = {}
    for path in sorted(out.rglob("*")):
        if not path.is_file() or "_app" in path.parts:
            continue
        raw = path.read_bytes()
        if path.name.endswith(".json.gz"):          # a data file's gzip copy (files.write_atomic)
            raw = gzip.decompress(raw)
            assert raw == path.with_suffix("").read_bytes(), f"{path.name} is not its file"
            raw = _timeless(json.loads(raw))
        elif path.suffix == ".json":
            raw = _timeless(json.loads(raw))
        got[str(path.relative_to(out))] = raw
    return got


def _timeless(x):
    if isinstance(x, dict):
        return {k: _timeless(v) for k, v in x.items() if k != "generated_at"}
    if isinstance(x, list):
        return [_timeless(v) for v in x]
    return x


# ------------------------------------------------- the code it replaced

def old_periods(self, site, first, last, include_partial=False):
    return {d: self.period(site, d, d, include_partial=include_partial)
            for d in store._days(first, last)}


def old_page_extras(history, key, first, last):
    return history.extras(key, first, last)


def old_visitor_days(p):
    site = p.key.split("::", 1)[0]
    rows = p.history.db.execute(
        "SELECT day, visitor, kind FROM visitor_days WHERE site = ? ORDER BY day",
        (site,)).fetchall()
    seen: dict[tuple, list[str]] = {}
    for d, v, kind in rows:
        seen.setdefault((v, kind), []).append(d)
    out: dict[str, dict] = {}
    for (v, kind), days in seen.items():
        for i, d in enumerate(days):
            slot = out.setdefault(d, {}).setdefault(kind, {"visitors": 0, "repeat_visitors": 0})
            slot["visitors"] += 1
            earlier = [x for x in days[:i]
                       if date.fromisoformat(x) >= date.fromisoformat(d) - timedelta(days=29)]
            slot["repeat_visitors"] += 1 if earlier else 0
    return out


def old_minute(at):
    from datetime import timezone
    return ai_likely.minute(datetime.strptime(at, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc))


def old_story(history, site, path, config, tz, today):
    L = lifecycle
    path = L._norm(path)
    meta, _ = L.load_meta(config)
    seen = L._first_seen(history, site)
    if path not in meta and path not in seen:
        return {"ok": False, "error": "no such page in the website's list, its sitemap or "
                                      "the logs"}
    published, updated, source = L._published(path, meta, seen)
    marks = (L.milestones(history, site, None, tz).get(path)
             or {k: None for k in L.SINGLE} | {k: [] for k in L.MULTI})
    landed, sent = L._leads(config, tz)
    start = date.fromisoformat(published or seen.get(path) or today.isoformat())
    last = today - timedelta(days=1)
    start = max(start, last - timedelta(days=L.MAX_DAYS - 1))
    days = []
    if start <= last:
        blobs = history.extras(site, start, last, ("pages",))
        for e in history.daily(site, start, last):
            d = e["day"].isoformat()
            row = {"day": d, "state": e["state"],
                   "days_since_publish": (e["day"] - date.fromisoformat(published)).days
                   if published else None}
            pages = (blobs.get(d) or {}).get("pages")
            if e["state"] in ("ok", "partial") and pages is not None:
                got = Counter()
                parts = {"sources": Counter(), "assistants": Counter(), "countries": Counter()}
                for p, v in pages.items():
                    if L._norm(p) != path:
                        continue
                    for k in ("readers", "views", "ai_asked", "ai_training", "search"):
                        got[k] += int(v.get(k, 0))
                    for k in parts:
                        parts[k].update({a: int(b) for a, b in (v.get(k) or {}).items()})
                row.update({k: got[k] for k in ("readers", "views", "ai_asked", "ai_training",
                                                 "search")},
                           **{k: dict(c) for k, c in parts.items()})
            else:
                row.update({k: None for k in ("readers", "views", "ai_asked", "ai_training",
                                              "search", "sources", "assistants", "countries")})
            days.append(row)
    entry = meta.get(path) or {}
    return {"ok": True, "path": path, "title": entry.get("title"), "locale": entry.get("locale"),
            # the sitemap's change dates (added later): none in this sandbox
            "published": published, "updated": updated, "date_source": source,
            "updated_source": "website" if updated else None, "lastmod": None,
            "lastmod_seen": [],
            "first_seen": seen.get(path),
            "days_since_publish": (today - date.fromisoformat(published)).days
            if published else None,
            "milestones": {**marks,
                           "lead_landed": {"at": landed[path]} if path in landed else None,
                           "lead_sent": {"at": sent[path]} if path in sent else None},
            "days": days}


def the_old_code():
    """Patches that put the replaced code back."""
    return [mock.patch.object(History, "periods", old_periods),
            mock.patch.object(data_files, "page_extras", old_page_extras),
            mock.patch.object(data_reports, "_visitor_days", old_visitor_days),
            mock.patch.object(ai_likely, "_stored_minute", old_minute),
            mock.patch.object(lifecycle, "build", lambda p: lifecycle._build(
                p, p.key.split("::", 1)[0])),
            mock.patch.object(lifecycle, "story", old_story)]


class SameFigures(unittest.TestCase):
    def test_every_data_file_is_the_same_as_the_old_code_made_it(self):
        now = draw(BOX.root / "new")
        patches = the_old_code()
        for p in patches:
            p.start()
        try:
            before = draw(BOX.root / "old")
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(sorted(now), sorted(before))
        for name in ("example.com/data/overview.json", "example.com/data/app.json",
                     "example.com/data/page_index.json", "example.com/data/ai_activity.json",
                     "example.com/data/visits.json", "example.com/canada/data/overview.json"):
            self.assertIn(name, now)
        for name in now:
            self.assertEqual(now[name], before[name], name)

    def test_every_page_story_and_compare_is_the_same(self):
        config = load_config(BOX.config)
        with History.reader(BOX.db) as h:
            for path in PATHS + ["/pricing", "/no-such/", "/ca/fr/"]:
                self.assertEqual(lifecycle.story(h, "example.com", path, config, TZ, TODAY),
                                 old_story(h, "example.com", path, config, TZ, TODAY), path)
            a = f"{TODAY - timedelta(days=3)}..{TODAY - timedelta(days=1)}"
            b = f"{TODAY - timedelta(days=6)}..{TODAY - timedelta(days=4)}"
            got = compare.compare(h, "example.com", None, a, b, {}, config, TZ)
            rows = {m["key"]: m for m in got["metrics"]}
            self.assertTrue(rows["visitors"]["a"])
            self.assertTrue(rows["ai_training"]["a"])         # the rewritten query's figure

    def test_the_compare_metrics_query_reads_the_same_rows(self):
        with History.reader(BOX.db) as h:
            days = [r[0] for r in h.db.execute("SELECT day FROM days WHERE site = 'example.com'")]
            marks = ",".join("?" * len(days))
            old = h.db.execute(
                f"SELECT kind, name, SUM(n) FROM counts WHERE site = ? AND day IN ({marks}) AND "
                f"((kind = 'engine_tier') OR (kind = 'status_people' AND name = '404')) "
                f"GROUP BY kind, name", ("example.com", *days)).fetchall()
            new = h.db.execute(
                f"SELECT kind, name, SUM(n) FROM counts WHERE site = ? AND day IN ({marks}) AND "
                f"kind IN ('engine_tier', 'status_people') AND "
                f"(kind = 'engine_tier' OR name = '404') "
                f"GROUP BY kind, name", ("example.com", *days)).fetchall()
        self.assertTrue(old)
        self.assertEqual(new, old)

    def test_periods_is_period_day_by_day(self):
        with History.reader(BOX.db) as h:
            for key in ("example.com", "example.com::canada", "example.com::guides"):
                for partial in (False, True):
                    first, last = TODAY - timedelta(days=10), TODAY - timedelta(days=1)
                    got = h.periods(key, first, last, include_partial=partial)
                    self.assertEqual(list(got), list(store._days(first, last)))
                    for d, period in got.items():
                        want = h.period(key, d, d, include_partial=partial)
                        self.assertEqual(repr(period), repr(want), (key, d))
                        if period.recorded:
                            self.assertEqual(list(period.totals.groups),
                                             list(want.totals.groups))
                            for g, s in period.totals.groups.items():
                                self.assertEqual(list(s.pages.items()),
                                                 list(want.totals.groups[g].pages.items()))

    def test_a_page_never_reads_a_kind_it_did_not_load(self):
        with History.reader(BOX.db) as h:
            got = data_files.page_extras(h, "example.com", TODAY - timedelta(days=6),
                                         TODAY - timedelta(days=1))
        day = next(iter(got.values()))
        self.assertIsNotNone(day.get("pages"))
        for kind in data_files.OWN_READERS:
            with self.assertRaises(KeyError):
                day.get(kind)


class Upgrades(unittest.TestCase):
    def test_history_11_gets_its_indexes_and_its_figures_stay(self):
        copy = BOX.root / "v11" / "history.sqlite"
        copy.parent.mkdir(exist_ok=True)
        shutil.copy(BOX.db, copy)
        db = sqlite3.connect(str(copy))
        for _, name, _ in store.ADDED_INDEXES:
            db.execute(f"DROP INDEX {name}")
        db.execute("UPDATE meta SET value = '11' WHERE key = 'schema_version'")
        db.commit()
        db.close()
        with History.reader(copy) as h:
            before = h.periods("example.com", TODAY - timedelta(days=6), TODAY)
        with History(copy) as h:
            self.assertEqual(h.migrated_from, 11)
            self.assertEqual(h.schema_version, store.SCHEMA_VERSION)
            names = {r[0] for r in h.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'")}
            after = h.periods("example.com", TODAY - timedelta(days=6), TODAY)
        self.assertLessEqual({n for _, n, _ in store.ADDED_INDEXES}, names)
        self.assertEqual(repr(after), repr(before))
        # an index changes no row: no copy is kept for it
        self.assertEqual([p.name for p in copy.parent.iterdir()], ["history.sqlite"])
        with History(copy) as h:                 # and once is enough
            self.assertIsNone(h.migrated_from)

    def test_the_prune_reads_the_day_index(self):
        with History.reader(BOX.db) as h:
            plan = " ".join(r[3] for r in h.db.execute(
                "EXPLAIN QUERY PLAN DELETE FROM day_extras WHERE day < ? AND kind IN (?, ?)",
                ("2026-01-01", "pages", "cube")))
        self.assertIn("day_extras_day", plan)

    def test_accounts_4_gets_its_indexes_and_skips_the_script_after(self):
        from skald.accounts import db as base
        path = BOX.root / "accounts-v4.sqlite"
        db = base.connect(path)
        for sql in base.INDEXES_V5:
            db.execute(f"DROP INDEX {sql.split()[5]}")
        db.execute("UPDATE meta SET value = '4' WHERE key = 'schema_version'")
        db.close()
        db = base.connect(path)
        try:
            self.assertEqual(base.schema_version(db), 5)
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
            self.assertLessEqual({"sites_org", "settings_key", "tokens_org", "invites_org"}, names)
            plan = " ".join(r[3] for r in db.execute(
                "EXPLAIN QUERY PLAN SELECT name FROM sites WHERE org_id = ? ORDER BY name", (1,)))
            self.assertIn("sites_org", plan)
        finally:
            db.close()
        ran = []
        real = sqlite3.connect

        def traced(*args, **kw):
            got = real(*args, **kw)
            got.set_trace_callback(ran.append)
            return got
        with mock.patch.object(base.sqlite3, "connect", traced):
            base.connect(path).close()                       # set up: no script
            self.assertFalse([s for s in ran if "CREATE TABLE" in s])
            with mock.patch.object(base, "SCHEMA_STAMP", "changed"):
                base.connect(path).close()                   # a changed SCHEMA runs it once
            self.assertTrue([s for s in ran if "CREATE TABLE" in s])

    def test_conversions_2_gets_the_journeys_index(self):
        from skald.conversions import store as cstore
        path = BOX.root / "conversions-v2.sqlite"
        db = cstore.connect(path)
        db.execute("DROP INDEX journeys_site_at")
        db.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")
        db.close()
        db = cstore.connect(path)
        try:
            self.assertEqual(cstore.schema_version(db), cstore.SCHEMA_VERSION)
            plan = " ".join(r[3] for r in db.execute(
                "EXPLAIN QUERY PLAN SELECT vid, path FROM journeys WHERE site = ? AND at >= ? "
                "AND at < ?", ("example.com", "a", "b")))
            self.assertIn("journeys_site_at", plan)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
