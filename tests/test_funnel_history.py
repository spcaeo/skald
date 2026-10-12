"""Phase 4, lane C: funnel history.

What is pinned:
- C1: every journey carries `at`, one bucketed offset per trail entry
  (seconds since the visit started, visits.seconds_bucket), and still no
  address, agent or exact clock time;
- C2: each saved funnel is counted over the day's journeys when the day is
  collected (day_extras kind `funnels`, keyed by a hash of its counted
  steps and source): visits per step, split by source type and device, the
  next pages after leaving each step and a time-to-complete histogram;
  verify holds its sums; a funnel saved after the day is not counted; the
  independent recount (audit_funnels.py) rebuilds trails from raw lines and
  matches, and catches a planted error; it imports only name lists;
- C3: funnels.json gives each saved funnel `history`: days from the day it
  was saved, only `ok` days carry figures, a day not recorded is null.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_funnels, funnel_days, funnels  # noqa: E402
from skald.store import History  # noqa: E402
from skald.visits import TRAIL_KEEP, seconds_bucket  # noqa: E402

from support import CHROME, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402
from test_visits import DAY, T, journey_day  # noqa: E402

SITE = "https://example.com"

# Any visit, then /features/ (in-app or loaded), then a page named pricing.
STEPS = [{"label": "Landed", "kind": "any"},
         {"label": "Features", "kind": "path", "match": "equals", "paths": ["/features"]},
         {"label": "Pricing", "kind": "path", "match": "segment", "paths": ["pricing"]},
         {"label": "Booked", "kind": "lead", "types": ["demo_booked"]}]


def saved(name="Features to pricing", steps=STEPS, source=None, at="2026-10-01T09:00:00+00:00"):
    return {"name": name, "source": source, "steps": steps, "saved_by": "admin", "saved_at": at}


def write_funnels(folder: Path, *items) -> None:
    (Path(folder) / "funnels.json").write_text(json.dumps(
        {"funnels": {f["name"]: f for f in items}}, indent=1))


def wanted(*items, day=DAY):
    """The funnels as collect hands them to funnel_days (from funnels.json)."""
    out = []
    for f in items:
        if funnel_days.saved_day(f, UTC) is None or funnel_days.saved_day(f, UTC) <= day:
            out.append(funnel_days.series(f))
    return out


def totals_with(lines, *items):
    from skald import aggregate
    real = aggregate.Tally.__init__

    def init(self, *a, **k):
        real(self, *a, **k)
        self.extras.funnels = wanted(*items)
    with mock.patch.object(aggregate.Tally, "__init__", init):
        return totals_for(lines)


# ------------------------------------------------------------------- C1

class TestTrailOffsets(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(day_lines(DAY, 3) + journey_day())

    def test_every_trail_entry_has_a_bucketed_offset(self):
        chat = next(j for j in self.totals.journeys if j["landing"] == "/compare/x/")
        self.assertEqual([p for p, _ in chat["trail"]], ["/compare/x/", "/features/", "/pricing/"])
        self.assertEqual(chat["at"], [0, 40, 100])
        for j in self.totals.journeys:
            self.assertEqual(len(j["at"]), len(j["trail"]))
            self.assertEqual(j["at"], sorted(j["at"]))
            self.assertTrue(all(a == seconds_bucket(a) for a in j["at"]))

    def test_offsets_are_bucketed_and_kept_as_long_as_the_trail(self):
        lines = [line(T + timedelta(seconds=67 * i), "203.0.113.90", f"/p{i}", CHROME)
                 for i in range(TRAIL_KEEP + 5)]
        j = totals_for(lines).journeys[0]
        self.assertEqual(len(j["trail"]), TRAIL_KEEP)
        self.assertEqual(len(j["at"]), TRAIL_KEEP)
        self.assertEqual(j["at"][1], 60)              # 67 s, to 10 s over a minute
        self.assertEqual(j["at"][9], 600)             # 603 s, to the minute over ten

    def test_still_nothing_identifying(self):
        text = json.dumps(self.totals.journeys)
        for secret in ("203.0.113.", "Mozilla", "https://", "15:00:40"):
            self.assertNotIn(secret, text)


# ------------------------------------------------------------- C2 count

def day_with_funnel_visits() -> list[str]:
    return day_lines(DAY, 3) + journey_day()


class TestCount(unittest.TestCase):

    def setUp(self):
        self.totals = totals_with(day_with_funnel_visits(), saved(),
                                  saved("From ChatGPT", source="ChatGPT"),
                                  saved("From google", source="google.com"))
        self.blob = self.totals.extras["funnels"]

    def series(self, name):
        return next(v for v in self.blob.values() if v["name"] == name)

    def test_steps_splits_next_pages_and_time(self):
        f = self.series("Features to pricing")
        self.assertEqual(f["visits"], 7)
        self.assertEqual(f["reached"], [7, 1, 1])
        self.assertEqual([s["label"] for s in f["steps"]], ["Landed", "Features", "Pricing"])
        self.assertEqual(f["by_source"]["AI assistant"], [2, 1, 1])
        self.assertEqual(sum(v[0] for v in f["by_source"].values()), 7)
        self.assertEqual(f["by_device"]["Mobile"], [1, 1, 1])
        self.assertEqual(f["next"][0], {"/": 3, "/guides/alpha": 2, "/guides/beta": 1})
        self.assertEqual(f["next"][1], {})
        self.assertEqual(f["next"][2], {funnel_days.LEFT: 1})
        self.assertEqual(f["complete"], {"1-3m": 1})

    def test_a_source_counts_only_its_visits(self):
        self.assertEqual(self.series("From ChatGPT")["visits"], 2)
        self.assertEqual(self.series("From ChatGPT")["reached"], [2, 1, 1])
        self.assertEqual(self.series("From google")["visits"], 1)
        self.assertEqual(self.series("From google")["reached"], [1, 0, 0])
        self.assertIsNone(self.series("From google")["complete"].get("1-3m"))

    def test_verify_holds_the_sums(self):
        from skald import check
        self.assertEqual(check(self.totals), [])
        f = self.series("Features to pricing")
        f["by_device"]["Mobile"][1] += 1
        whats = [p.what for p in check(self.totals)]
        self.assertTrue(any("funnel Features to pricing" in w for w in whats), whats)

    def test_the_key_follows_the_counted_steps_and_source_not_labels(self):
        base = funnel_days.series_key(saved())
        relabelled = [dict(s, label="x") for s in STEPS]
        self.assertEqual(funnel_days.series_key(saved(steps=relabelled)), base)
        other_lead = STEPS[:3] + [{"label": "Lead", "kind": "lead", "types": ["signup"]}]
        self.assertEqual(funnel_days.series_key(saved(steps=other_lead)), base)
        moved = STEPS[:2] + [{"label": "P", "kind": "path", "match": "segment",
                              "paths": ["prices"]}]
        self.assertNotEqual(funnel_days.series_key(saved(steps=moved)), base)
        self.assertNotEqual(funnel_days.series_key(saved(source="ChatGPT")), base)
        self.assertIn(base, self.blob)

    def test_no_saved_funnel_stores_nothing(self):
        totals = totals_for(day_with_funnel_visits())
        self.assertNotIn("funnels", totals.extras)

    def test_time_buckets(self):
        self.assertEqual([funnel_days.time_bucket(s) for s in (0, 9, 10, 59, 60, 179, 180,
                                                                 599, 600, 1799, 1800)],
                         ["under 10s", "under 10s", "10-30s", "30s-1m", "1-3m", "1-3m",
                          "3-10m", "3-10m", "10-30m", "10-30m", "30m or more"])


class TestWanted(unittest.TestCase):

    def test_only_funnels_saved_by_the_day_are_counted(self):
        box = Sandbox()
        try:
            write_funnels(box.root, saved(), saved("Later", at="2026-10-06T01:00:00+00:00"))
            config = {"_resolved": {"live_dir": str(box.root)}}
            got = funnel_days.wanted(config, DAY, UTC)
            self.assertEqual([f["name"] for f in got], ["Features to pricing"])
            self.assertEqual(len(funnel_days.wanted(config, date(2026, 10, 6), UTC)), 2)
            # Saved at 01:00 UTC on the 6th is still the 5th in New York.
            ny = ZoneInfo("America/New_York")
            self.assertEqual(len(funnel_days.wanted(config, DAY, ny)), 2)
            self.assertIsNone(funnel_days.wanted({}, DAY, UTC))
        finally:
            box.close()


# ------------------------------------------------------- C2 end to end

class TestCollectAndAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(day_with_funnel_visits())
        write_funnels(self.box.root, saved(), saved("From ChatGPT", source="ChatGPT"),
                      saved("Too new", at="2026-10-06T08:00:00+00:00",
                            steps=[STEPS[0], STEPS[2]]))
        code, _, err = self.box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def stored(self) -> dict:
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY, ("funnels",))[DAY.isoformat()]["funnels"]

    def test_collected_and_kept_only_for_funnels_saved_by_then(self):
        blob = self.stored()
        self.assertEqual(sorted(v["name"] for v in blob.values()),
                         ["Features to pricing", "From ChatGPT"])
        with History(self.box.db) as h:
            self.assertEqual(h.state("example.com", DAY), "ok")

    def test_the_recount_matches(self):
        code, out, err = self.box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)

    def plant(self, change) -> tuple[int, str]:
        db = sqlite3.connect(self.box.db)
        blob = json.loads(db.execute("SELECT data FROM day_extras WHERE kind = 'funnels'")
                          .fetchone()[0])
        change(blob)
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'funnels'",
                       (json.dumps(blob),))
        db.close()
        code, _, err = self.box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        return code, err

    def test_a_planted_step_count_is_caught(self):
        key = funnel_days.series_key(saved())
        code, err = self.plant(lambda b: b[key]["reached"].__setitem__(1, 2))
        self.assertEqual(code, 1)
        self.assertIn("funnel Features to pricing: step 2 reached", err)

    def test_a_planted_next_page_and_time_are_caught(self):
        key = funnel_days.series_key(saved())

        def change(b):
            b[key]["next"][0] = {"/": 4, "/guides/alpha": 1, "/guides/beta": 1}
            b[key]["complete"] = {"3-10m": 1}
        code, err = self.plant(change)
        self.assertEqual(code, 1)
        self.assertIn("next pages after step 1: /", err)
        self.assertIn("time to complete", err)

    def test_a_series_whose_steps_do_not_match_its_key_is_caught(self):
        key = funnel_days.series_key(saved())
        code, err = self.plant(lambda b: b[key]["steps"][1]["paths"].append("/x"))
        self.assertEqual(code, 1)
        self.assertIn("do not match its key", err)

    def test_a_deleted_funnels_stored_series_is_still_recounted(self):
        write_funnels(self.box.root)
        key = funnel_days.series_key(saved())
        code, err = self.plant(lambda b: b[key]["by_source"]["AI assistant"].__setitem__(0, 1))
        self.assertEqual(code, 1)
        self.assertIn("by source AI assistant", err)

    def test_the_live_snapshot_carries_and_recounts_them(self):
        live = Sandbox()
        try:
            live.log(day_with_funnel_visits())
            write_funnels(live.root, saved())
            now = datetime(2026, 10, 5, 20, tzinfo=UTC)
            with mock.patch("skald.cli._now", return_value=now):
                self.assertEqual(live.run("live")[0], 0)
                code, out, err = live.run("audit", "--live")
            self.assertEqual(code, 0, err)
            snap = json.loads((live.root / "live-example.com.json").read_text())
            self.assertEqual(snap["extras"]["funnels"][funnel_days.series_key(saved())]
                             ["reached"], [7, 1, 1])
        finally:
            live.close()


class TestRecountRules(unittest.TestCase):
    """The recount's own matching, read from the documented rules."""

    def test_matching(self):
        hit = audit_funnels._hit
        self.assertTrue(hit({"match": "equals", "paths": ["/pricing/"]}, "/pricing"))
        self.assertTrue(hit({"match": "equals", "paths": ["/"]}, "/"))
        self.assertFalse(hit({"match": "equals", "paths": ["/pricing"]}, "/pricing/x"))
        self.assertTrue(hit({"match": "starts_with", "paths": ["/blog/"]}, "/blog/a"))
        self.assertTrue(hit({"match": "segment", "paths": ["Pricing"]}, "/ca/fr/pricing/"))
        self.assertFalse(hit({"match": "segment", "paths": ["pricing"]}, "/pricing/plans"))
        self.assertTrue(hit({"match": "contains", "paths": ["demo"]}, "/book-demo/"))
        for step, path in ((STEPS[1], "/features/"), (STEPS[2], "/x/pricing"),
                           ({"match": "segment", "paths": ["/"]}, "/")):
            self.assertEqual(hit(step, path), funnels.matches(step, path))

    def test_the_key_is_computed_apart_and_agrees(self):
        for f in (saved(), saved(source="ChatGPT"), saved(steps=STEPS[:2])):
            self.assertEqual(audit_funnels.series_key(f["source"], f["steps"]),
                             funnel_days.series_key(f))


class TestIndependence(unittest.TestCase):

    def test_the_recount_imports_only_name_lists_and_the_audits_own_code(self):
        tree = ast.parse(Path(audit_funnels.__file__).read_text())
        froms = {node.module for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.level}
        self.assertLessEqual(froms, {"classify", "audit_labels", "audit_visits"})
        names = {a.name for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.module == "classify"
                 for a in node.names}
        self.assertTrue(all(n.isupper() for n in names), names)


# ------------------------------------------------------------------- C3

class TestFunnelsJson(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(day_lines(date(2026, 10, 3), 2) + day_lines(date(2026, 10, 4), 2)
                     + day_with_funnel_visits())
        # Saved on the 4th: the 3rd is before it; the 4th is made "not recorded"
        # below (as a day collected by an older version would be).
        write_funnels(self.box.root, saved(at="2026-10-04T10:00:00+00:00"))
        for day in ("2026-10-03", "2026-10-04", "2026-10-05"):
            code, _, err = self.box.run("--today", "2026-10-06", "collect", "--day", day)
            self.assertEqual(code, 0, err)
        db = sqlite3.connect(self.box.db)
        with db:
            db.execute("DELETE FROM day_extras WHERE kind = 'funnels' AND day = '2026-10-04'")
        db.close()

    def tearDown(self):
        self.box.close()

    def page(self, history):
        from skald.data_files import Page
        from skald.config import load_config
        config = load_config(self.box.config)
        config["_resolved"] = {"live_dir": str(self.box.root)}
        return Page(history, "example.com", "example.com", None, UTC,
                    datetime(2026, 10, 6, 12, tzinfo=UTC), None, config,
                    live_dir=self.box.root)

    def test_history_from_the_day_it_was_saved(self):
        with History(self.box.db) as h:
            body = funnels.build(self.page(h))
        mine = next(f for f in body["funnels"] if f["name"] == "Features to pricing")
        hist = mine["history"]
        self.assertEqual(hist["since"], "2026-10-04")
        self.assertEqual(hist["key"], funnel_days.series_key(saved()))
        self.assertEqual(hist["steps"], ["Landed", "Features", "Pricing"])
        days = {d["day"]: d for d in hist["days"]}
        self.assertEqual(sorted(days), ["2026-10-04", "2026-10-05"])
        self.assertIsNone(days["2026-10-04"]["reached"])          # not recorded, never 0
        self.assertEqual(days["2026-10-05"]["reached"], [7, 1, 1])
        self.assertEqual(days["2026-10-05"]["state"], "ok")
        default = next(f for f in body["funnels"] if f["saved_by"] == "default")
        self.assertIsNone(default["history"])

    def test_a_withheld_day_shows_no_figures(self):
        with History(self.box.db) as h:
            h.db.execute("UPDATE days SET verified = 0, problems = 'planted' WHERE day = ?",
                         ("2026-10-05",))
            h.db.commit()
            body = funnels.build(self.page(h))
        hist = next(f for f in body["funnels"] if f["saved_by"] != "default")["history"]
        day = next(d for d in hist["days"] if d["day"] == "2026-10-05")
        self.assertEqual(day["state"], "withheld")
        self.assertNotIn("reached", day)


if __name__ == "__main__":
    unittest.main()
