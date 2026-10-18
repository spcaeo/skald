"""2.12.0: first touch - where each visit's visitor first came from - its
links (visitor ID, then kept address and browser, then the 30-day code), the
privacy settings it obeys, its figures, their audit, and the visitor timeline.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import firsttouch  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.conversions import store  # noqa: E402
from skald.people import api, timeline  # noqa: E402

from support import UTC, Sandbox, line  # noqa: E402

D1, D2 = date(2026, 10, 5), date(2026, 10, 6)
A, B, C = "203.0.113.20", "203.0.113.21", "203.0.113.22"
KEY = {"SKALD_VISITOR_KEY": "cd" * 32}


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def lines(same_day: bool = False) -> list[str]:
    """A from Google and B from ChatGPT on D1; on D2 both come back Direct and
    C comes for the first time. same_day: A also came from Google on D2's
    morning, before its Direct visit."""
    out = [line(at(D1, 9), A, "/guides/alpha", referrer="https://www.google.com/search?q=x"),
           line(at(D1, 9, 1), A, "/pricing/", referrer="https://example.com/guides/alpha"),
           line(at(D1, 10), B, "/", referrer="https://chatgpt.com/")]
    if same_day:
        out.append(line(at(D2, 8), A, "/blog/", referrer="https://www.bing.com/"))
    out += [line(at(D2, 14), A, "/"), line(at(D2, 14, 2), A, "/pricing/",
                                           referrer="https://example.com/"),
            line(at(D2, 15), B, "/"), line(at(D2, 16), C, "/")]
    return out


class Base(unittest.TestCase):
    extra = ""

    def setUp(self):
        self.box = Sandbox(mail=False)
        if self.extra:
            self.box.config.write_text(self.box.config.read_text() + self.extra)

    def tearDown(self):
        self.box.close()

    def collect(self, *days: date):
        for d in days:
            code, _, err = self.box.run("--today", (d + timedelta(days=1)).isoformat(), "collect")
            self.assertEqual(code, 0, err)

    def audit(self, d: date) -> tuple[int, str]:
        code, out, err = self.box.run("--today", (d + timedelta(days=1)).isoformat(), "audit",
                                      "--day", d.isoformat())
        return code, out + err

    def journeys(self, d: date) -> list[dict]:
        db = sqlite3.connect(self.box.db)
        try:
            return [json.loads(x) for (x,) in db.execute(
                "SELECT data FROM journeys WHERE day = ? ORDER BY seq", (d.isoformat(),))]
        finally:
            db.close()

    def blob(self, d: date) -> dict | None:
        db = sqlite3.connect(self.box.db)
        try:
            row = db.execute("SELECT data FROM day_extras WHERE site = 'example.com' AND day = ? "
                             "AND kind = 'first_touch'", (d.isoformat(),)).fetchone()
        finally:
            db.close()
        return json.loads(row[0]) if row else None


class ByAddress(Base):
    def test_a_direct_visit_knows_its_first_visit(self):
        self.box.log(lines())
        self.collect(D1, D2)
        a, b, c = self.journeys(D2)
        self.assertEqual(a["source"], "Direct or unknown")
        self.assertEqual(a["first_touch"]["by"], "address")
        self.assertEqual(a["first_touch"]["source"], "Search engine")
        self.assertEqual(a["first_touch"]["referrer"], "google.com")
        self.assertEqual(a["first_touch"]["day"], "2026-10-05")
        self.assertEqual(a["first_touch"]["landing"], "/guides/alpha")
        self.assertEqual(b["first_touch"]["source"], "AI assistant")
        self.assertEqual(c["first_touch"], {"by": "none"})
        self.assertEqual([j["seq"] for j in (a, b, c)], [0, 1, 2])
        got = self.blob(D2)
        self.assertEqual(got["direct"]["visits"], 3)
        self.assertEqual((got["direct"]["known"], got["direct"]["none"], got["direct"]["off"]),
                         (2, 1, 0))
        self.assertEqual(got["direct"]["first"], {"Search engine": 1, "AI assistant": 1})
        self.assertEqual(got["direct"]["referrer"], {"google.com": 1, "chatgpt.com": 1})
        self.assertEqual(got["by"]["address"], 2)
        self.assertEqual(sum(got["by"].values()), got["visits"])
        # the journeys hold labels only: no address
        self.assertNotIn("203.0.113", json.dumps(self.journeys(D2)))

    def test_the_first_day_is_the_first_visit_we_know_of(self):
        self.box.log(lines())
        self.collect(D1)
        self.assertEqual({j["first_touch"]["by"] for j in self.journeys(D1)}, {"none"})

    def test_an_earlier_visit_the_same_day_counts(self):
        self.box.log(lines(same_day=True))
        self.collect(D2)
        a = [j for j in self.journeys(D2) if j["landing"] == "/" and j["start"].endswith("14:00")][0]
        self.assertEqual(a["first_touch"]["source"], "Search engine")
        self.assertEqual(a["first_touch"]["referrer"], "bing.com")
        self.assertEqual(a["first_touch"]["day"], "2026-10-06")

    def test_the_audit_agrees_then_catches_a_changed_kept_visit(self):
        self.box.log(lines())
        self.collect(D1, D2)
        code, out = self.audit(D2)
        self.assertEqual(code, 0, out)
        db = sqlite3.connect(self.box.root / "conversions.sqlite")
        db.execute("UPDATE visits SET source = 'Social media' WHERE day = '2026-10-05' AND seq = 0")
        db.commit()
        db.close()
        code, out = self.audit(D2)
        self.assertEqual(code, 1)
        self.assertIn("first touch: direct visits first from", out)
        self.assertNotIn("203.0.113", out, "no address in a problem")

    def test_the_audit_catches_a_changed_figure(self):
        self.box.log(lines())
        self.collect(D1, D2)
        db = sqlite3.connect(self.box.db)
        blob = self.blob(D2)
        blob["direct"]["none"] += 1
        db.execute("UPDATE day_extras SET data = ? WHERE kind = 'first_touch' AND day = ?",
                   (json.dumps(blob), D2.isoformat()))
        db.commit()
        db.close()
        code, out = self.audit(D2)
        self.assertEqual(code, 1)
        self.assertIn("first touch: direct visits, none", out)


class AddressesOff(Base):
    extra = "privacy:\n  keep_ips: false\n"

    def test_no_link_at_all_without_a_key(self):
        self.box.log(lines())
        self.collect(D1, D2)
        self.assertIsNone(self.blob(D2))
        self.assertTrue(all("first_touch" not in j for j in self.journeys(D2)))

    def test_the_30_day_code_links_without_an_address(self):
        with mock.patch.dict(os.environ, KEY):
            self.box.log(lines())
            self.collect(D1, D2)
            a = self.journeys(D2)[0]
            self.assertEqual(a["first_touch"]["by"], "hash")
            self.assertEqual(a["first_touch"]["source"], "Search engine")
            self.assertEqual(a["first_touch"]["referrer"], "(not kept)")
            self.assertIsNone(a["first_touch"]["start"])
            self.assertEqual(self.blob(D2)["roads"]["address"], 0)
            self.assertFalse((self.box.root / "conversions.sqlite").exists()
                             and _rows(self.box.root / "conversions.sqlite", "visits"))
            code, out = self.audit(D2)
            self.assertEqual(code, 0, out)

    def test_no_timeline_without_kept_addresses(self):
        cfg = load_config(self.box.config)
        got = timeline.visitor(cfg, self.box.root, "example.com", "2026-10-06", 0)
        self.assertFalse(got["found"])
        self.assertIn("keeps no IP addresses", got["why"])


def _rows(path: Path, table: str) -> int:
    db = sqlite3.connect(path)
    try:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        db.close()


class ByVisitorID(Base):
    extra = "beacon:\n  enabled: true\n  visitor_ids: true\n"

    def page_views(self, rows):
        db = store.connect(self.box.root / "conversions.sqlite")
        with store.tx(db):
            for vid, when, path, source, via in rows:
                store.record_page_view(db, "example.com", vid, store.stamp(when), path, source, via)
        db.close()

    def test_the_visitor_id_comes_before_the_address(self):
        vid = "skv_" + "A" * 22
        # The ID was seen a week before, from LinkedIn (another address: the
        # log has no line of it), and on A's Direct visit's landing page.
        self.page_views([(vid, at(D1, 7), "/blog/", "Social media", "linkedin.com"),
                         (vid, at(D2, 14) + timedelta(seconds=1), "/", "Direct or unknown", "")])
        self.box.log(lines())
        self.collect(D1, D2)
        a, b, _ = self.journeys(D2)
        self.assertEqual(a["first_touch"]["by"], "vid")
        self.assertEqual(a["first_touch"]["source"], "Social media")
        self.assertEqual(a["first_touch"]["referrer"], "linkedin.com")
        self.assertEqual(b["first_touch"]["by"], "address")          # no ID: the address
        code, out = self.audit(D2)
        self.assertEqual(code, 0, out)

    def test_two_ids_on_the_same_page_match_neither(self):
        self.page_views([("skv_" + "B" * 22, at(D1, 7), "/x", "Email", ""),
                         ("skv_" + "B" * 22, at(D2, 14) + timedelta(seconds=1), "/", None, ""),
                         ("skv_" + "C" * 22, at(D2, 14) + timedelta(seconds=3), "/", None, "")])
        self.box.log(lines())
        self.collect(D1, D2)
        self.assertEqual(self.journeys(D2)[0]["first_touch"]["by"], "address")

    def test_matching_is_one_to_one(self):
        views = [("v", at(D2, 14) + timedelta(seconds=1), "/")]
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE journeys (vid, site, at, path, source_type, via)")
        db.executemany("INSERT INTO journeys VALUES (?, 'example.com', ?, ?, NULL, NULL)",
                       [(v, store.stamp(w), p) for v, w, p in views])
        got = firsttouch.match_vids(db, "example.com", [(0, at(D2, 14), "/"), (1, at(D2, 14, 0), "/")],
                                    at(D2, 23))
        self.assertEqual(got, {}, "one ID on two visits matches neither")
        got = firsttouch.match_vids(db, "example.com", [(0, at(D2, 14), "/")], at(D2, 23))
        self.assertEqual(got, {0: "v"})
        got = firsttouch.match_vids(db, "example.com", [(0, at(D2, 14), "/")], at(D2, 14))
        self.assertEqual(got, {}, "a page view after the window's end is not read")


class Timeline(Base):
    def test_every_visit_of_the_visitor_newest_first(self):
        self.box.log(lines())
        self.collect(D1, D2)
        cfg = load_config(self.box.config)
        got = timeline.visitor(cfg, self.box.root, "example.com", "2026-10-06", 0)
        self.assertTrue(got["found"])
        self.assertEqual([v["start"] for v in got["visits"]],
                         ["2026-10-06T14:00:00Z", "2026-10-05T09:00:00Z"])
        self.assertTrue(got["visits"][-1].get("first"))
        self.assertEqual(got["visits"][0]["linked"], "this")
        self.assertEqual({v["city"] for v in got["visits"]}, {None}, "no city file: no city, never a guess")
        self.assertNotIn("203.0.113", json.dumps(got), "no address in the answer")

    def test_only_admins_and_owners(self):
        self.box.log(lines())
        self.collect(D1, D2)
        cfg = load_config(self.box.config)
        sent = []

        class H:
            def _json(self, code, body):
                sent.append((code, body))

        api._visitor(H(), {"day": "2026-10-06", "seq": "0"}, cfg, self.box.root, "example.com",
                     False, cfg, None, None, "viewer@example.com")
        self.assertEqual(sent[-1][0], 403)
        api._visitor(H(), {"day": "6 Oct", "seq": "0"}, cfg, self.box.root, "example.com",
                     True, cfg, None, None, "owner@example.com")
        self.assertEqual(sent[-1][0], 400)
        api._visitor(H(), {"day": "2026-10-06", "seq": "0"}, cfg, self.box.root, "example.com",
                     True, cfg, self.box.root, None, "owner@example.com")
        self.assertEqual(sent[-1][0], 200)
        log = (self.box.root / "privacy.log").read_text()
        self.assertIn("people.visitor", log)
        self.assertNotIn("203.0.113", log)


class DrawerOutcome(unittest.TestCase):
    def test_a_person_search_with_a_lead_says_so(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node not installed")
        js = Path(__file__).resolve().parent / "js" / "visitor-drawer.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("visitor-drawer: all passed", done.stdout)


class Words(unittest.TestCase):
    def test_no_unknown_in_the_new_pages(self):
        app = Path(firsttouch.__file__).resolve().parent / "webapp" / "js"
        for name in ("tabs/visitor.js", "journeymap.js", "tabs/tr-firsttouch.js"):
            # the stored name it compares against ("Unknown") is not a word shown
            text = (app / name).read_text().lower().replace('=== "unknown"', "")
            self.assertNotRegex(text, r"unknown", f"{name} says unknown")


if __name__ == "__main__":
    unittest.main()
