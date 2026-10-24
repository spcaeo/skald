"""Phase 4, lane D: goals from beacon events, campaign tag hygiene, exit rate.

What is pinned:
- the spool recount also counts events by source, with its own pattern; a
  mismatch withholds the by-source block (rows lose their source, goals
  leave the day out) and not the day's totals;
- `beacon.goals`: events per 100 visits by source, from days whose events,
  by-source recount and log figures are all whole and verified;
- utm_hygiene (day kind) and its independent recount audit_utm (parse_qsl,
  its own rules): a planted error is caught by the audit;
- pages.json's exit rate: exits / visits, null under MIN_RATE.

Addresses are RFC 5737; the host is example.com.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import (audit_more, audit_utm, beacon, campaigns, classify,  # noqa: E402
                          data_reports, day_more, events, utm_hygiene)
from skald.store import History  # noqa: E402

from support import Sandbox, day_lines, line, totals_for  # noqa: E402

NY = ZoneInfo("America/New_York")
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"


def spool_line(event="cta_click", path="/pricing/", group="people", source="Direct or unknown",
               at="2026-10-05T12:00:00+00:00", label="signup_hero"):
    row = {"at": at, "e": event, "p": path, "g": group, "s": source, "id": label,
           "r": "", "u": "", "vw": "lg", "t": 3}
    return json.dumps(row, separators=(",", ":"), sort_keys=True)


# ------------------------------------------------------------ D1: by source

class EventsBySource(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.spool = self.box.root / "beacon"
        self.spool.mkdir()
        self.config = {"beacon": {"enabled": True, "goals": ["demo_booked", "signup_submit",
                                                             "purchase", "demo_booked"]}}

    def tearDown(self):
        self.box.close()

    def write(self, lines):
        beacon.day_file(self.spool, DAY).write_text("\n".join(lines) + "\n")

    def test_the_recount_counts_by_event_and_source(self):
        self.write([spool_line(), spool_line(source="Search engine"),
                    spool_line(event="demo_booked", source="Search engine"),
                    spool_line(group="ours"),
                    '{"at":"2026-10-05T12:00:00+00:00","e":"scroll_75","g":"people","p":"/"}'])
        people, ours, _times, by_source = events.recount_spool(beacon.day_file(self.spool, DAY))
        self.assertEqual(people, Counter({"cta_click": 2, "demo_booked": 1, "scroll_75": 1}))
        self.assertEqual(ours, Counter({"cta_click": 1}))
        self.assertEqual(by_source, Counter({("cta_click", "Direct or unknown"): 1,
                                             ("cta_click", "Search engine"): 1,
                                             ("demo_booked", "Search engine"): 1,
                                             ("scroll_75", "Direct or unknown"): 1}))

    def test_goal_names_keep_known_events_once(self):
        self.assertEqual(events.goal_names(self.config), ["demo_booked", "signup_submit"])
        self.assertEqual(events.goal_names({}), [])
        self.assertEqual(events.goal_names({"beacon": {"goals": "demo_booked"}}),
                         ["demo_booked"])

    def collected(self):
        with History(self.box.db) as history:
            events.collect(history, self.config, "example.com", self.spool, DAY)
            return events.audit(history, self.config, "example.com", self.spool, DAY,
                                timezone.utc)

    def test_a_matching_day_is_ok_by_source(self):
        self.write([spool_line(), spool_line(source="Search engine")])
        got = self.collected()
        self.assertEqual((got["state"], got["by_source"]), ("ok", "ok"))

    def test_a_source_mismatch_withholds_only_the_by_source_block(self):
        self.write([spool_line(), spool_line(source="Search engine")])
        with History(self.box.db) as history:
            events.collect(history, self.config, "example.com", self.spool, DAY)
            with history.db:               # a source filed wrong; the totals still add up
                history.db.execute("UPDATE event_counts SET source = 'Email' "
                                   "WHERE source = 'Search engine'")
            got = events.audit(history, self.config, "example.com", self.spool, DAY,
                               timezone.utc)
            self.assertEqual((got["state"], got["by_source"]), ("ok", "mismatch"))
            self.assertTrue(any("Email" in p for p in got["by_source_problems"]))
            state = history.db.execute("SELECT state FROM event_days").fetchone()[0]
            self.assertEqual(state, "ok")
            page = SimpleNamespace(key="example.com", view=None, config=self.config,
                                   anchor=DAY, today=DAY + timedelta(days=1), history=history,
                                   live_dir=self.box.root, snap=None)
            built = events.build(page)
        last = built["days"][-1]
        self.assertEqual((last["state"], last["by_source"]), ("ok", "withheld"))
        self.assertEqual(last["events"], {"cta_click": 2})
        self.assertEqual({r[4] for r in built["rows"]}, {None})
        goal_day = [d for d in built["goals"]["days"] if d["day"] == DAY.isoformat()][0]
        self.assertEqual(goal_day["state"], "left_out")


# ------------------------------------------------------------- D2: goals

class Goals(unittest.TestCase):

    def test_goals_per_day_from_whole_verified_days(self):
        box = Sandbox()
        try:
            box.log(day_lines(DAY, 4))
            self.assertEqual(box.run("--today", TODAY, "collect")[0], 0)
            spool = box.root / "beacon"
            spool.mkdir()
            beacon.day_file(spool, DAY).write_text("\n".join([
                spool_line(event="demo_booked", source="AI assistant"),
                spool_line(event="demo_booked"), spool_line(event="cta_click"),
                spool_line(event="signup_submit", path="/signup/")]) + "\n")
            config = {"beacon": {"enabled": True, "goals": ["demo_booked", "signup_submit"]}}
            with History(box.db) as history:
                events.collect(history, config, "example.com", spool, DAY)
                events.audit(history, config, "example.com", spool, DAY, timezone.utc)
                page = SimpleNamespace(key="example.com", view=None, config=config,
                                       anchor=DAY, today=DAY + timedelta(days=1),
                                       history=history, live_dir=box.root, snap=None)
                goals = events.build(page)["goals"]
        finally:
            box.close()
        self.assertEqual(goals["names"], ["demo_booked", "signup_submit"])
        self.assertEqual(goals["min_rate"], 10)
        day = goals["days"][-1]
        self.assertEqual((day["day"], day["state"]), (DAY.isoformat(), "ok"))
        self.assertEqual(day["events"], {"demo_booked": {"AI assistant": 1,
                                                         "Direct or unknown": 1},
                                         "signup_submit": {"Direct or unknown": 1}})
        # day_lines: 4 readers, the first cited by an assistant.
        self.assertEqual(day["visits"], {"AI assistant": 1, "Direct or unknown": 3})

    def test_no_goals_configured(self):
        self.assertIsNone(events.goals_block(SimpleNamespace(config={}), None, {}, [], DAY,
                                             DAY))


# ------------------------------------------------------- D3: tag hygiene

NOON = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
TAGGED = [
    ("/pricing/?utm_source=news", "-"),                                  # no medium
    ("/?utm_source=x&utm_medium=Weird+Medium", "-"),                     # unknown medium
    ("/?gclid=abc123", "-"),                                             # click id, no tags
    ("/guides/alpha?utm_source=site&utm_medium=email&email=a@example.com",
     "https://example.com/blog/"),                                       # an internal link
    ("/?utm_source=google&utm_medium=cpc", "-"),                         # fine
    ("/", "-"),                                                          # untagged
]


def tagged_lines() -> list[str]:
    return [line(NOON + timedelta(minutes=i), f"203.0.113.{20 + i}", path, referrer=ref)
            for i, (path, ref) in enumerate(TAGGED)]


class TagHygiene(unittest.TestCase):

    def test_registered(self):
        self.assertIn("utm_hygiene", day_more.modules())
        self.assertIn("utm_hygiene", audit_more._modules(audit_more.RECOUNTS))

    def test_the_click_id_lists_agree(self):
        self.assertEqual(set(classify.CLICK_ID_PARAMS), set(campaigns.CLICK_IDS))

    def test_counts_paths_and_examples(self):
        totals = totals_for(tagged_lines())
        blob = totals.extras["utm_hygiene"]
        self.assertEqual(blob["visits"], 6)
        self.assertEqual(blob["counts"], {"source_no_medium": 1, "unknown_medium": 1,
                                          "click_id_no_tags": 1, "internal_tags": 1})
        self.assertEqual(blob["paths"]["internal_tags"], {"/guides/alpha": 1})
        example = blob["examples"]["internal_tags"][0]
        self.assertEqual(example, {"path": "/guides/alpha",
                                   "tags": "utm_source=site&utm_medium=email", "click_id": ""})
        self.assertEqual(blob["examples"]["click_id_no_tags"][0],
                         {"path": "/", "tags": "", "click_id": "Google Ads"})
        self.assertNotIn("a@example.com", json.dumps(blob))
        from skald import extras
        self.assertEqual(extras.check(totals), [])

    def test_check_catches_paths_that_do_not_add_up(self):
        totals = totals_for(tagged_lines())
        totals.extras["utm_hygiene"]["paths"]["unknown_medium"]["/x"] = 1
        from skald import extras
        self.assertIn("utm_hygiene: unknown_medium by landing page does not sum",
                      [p.what for p in extras.check(totals)])

    def test_a_day_with_no_people(self):
        noon = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
        totals = totals_for([line(noon, "198.51.100.40", "/", "curl/8.7.1")])
        blob = totals.extras.get("utm_hygiene")
        self.assertEqual(blob["visits"], 0)
        self.assertEqual(sum(blob["counts"].values()), 0)

    def test_the_recount_reads_the_raw_line(self):
        from skald.audit import line_hit
        r = audit_utm.Recount({}, DAY, timezone.utc, {"example.com"})
        for raw in tagged_lines():
            got = line_hit(raw)
            r.visit([got], lambda _l: True, {"landing": got.path[:70], "source": "x"})
        r.visit([], lambda _l: True, None)             # read no page: not a visit
        self.assertEqual(r.visits, 6)
        self.assertEqual(r.counts, Counter({"source_no_medium": 1, "unknown_medium": 1,
                                            "click_id_no_tags": 1, "internal_tags": 1}))

    def test_audit_matches_and_catches_a_planted_error(self):
        box = Sandbox()
        try:
            box.log(tagged_lines())
            self.assertEqual(box.run("--today", TODAY, "collect")[0], 0)
            code, out, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 0, err)
            db = sqlite3.connect(str(box.db))
            with db:
                data = json.loads(db.execute("SELECT data FROM day_extras WHERE "
                                             "kind = 'utm_hygiene'").fetchone()[0])
                data["counts"]["internal_tags"] = 2
                db.execute("UPDATE day_extras SET data = ? WHERE kind = 'utm_hygiene'",
                           (json.dumps(data),))
            db.close()
            code, _, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 1)
            self.assertIn("utm_hygiene: internal_tags: history has 2, the recount finds 1", err)
        finally:
            box.close()

    def test_campaigns_json_carries_it(self):
        blob = {"visits": 1, "counts": {}, "paths": {}, "examples": {}}
        p = SimpleNamespace(extras={"2026-10-05": {"campaigns": {"rows": {}, "tagged": 0},
                                                   "utm_hygiene": blob}},
                            per_day=lambda f: [{"day": "2026-10-05", "state": "ok",
                                                **f("2026-10-05", {})}],
                            today_block=lambda: None, live_ok=False, snap=None,
                            anchor=DAY, config=None)
        got = data_reports.campaigns(p)
        self.assertEqual(got["days"][0]["utm_hygiene"], blob)


# ------------------------------------------------------------ D4: exit rate

class ExitRate(unittest.TestCase):

    def figures(self, visits, exits):
        v = {k: 0 for k in data_reports.PAGE_SUMS}
        v.update(visits=visits, exits=exits, time=Counter(), sources=Counter(),
                 assistants=Counter(), countries=Counter())
        return data_reports._figures(v)

    def test_exits_over_visits(self):
        self.assertEqual(self.figures(12, 3)["exit_rate"], 0.25)

    def test_none_under_min_rate(self):
        self.assertIsNone(self.figures(9, 3)["exit_rate"])
        self.assertIsNone(self.figures(0, 0)["exit_rate"])


if __name__ == "__main__":
    unittest.main()
