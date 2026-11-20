"""SKALD-22: "Who is scanning us?" on a site whose log holds a CDN's addresses.

Behind a CDN that the site's server does not see through, every scanner arrives as the
edge's address, with the edge's data-centre country, and one edge carries many scanners
(one row per address and user agent). The security blob now says so on both roads: a row
from a CDN edge carries `cdn` (the CDN's name; "" for any other address; absent when no
CDN list is kept) and no country, the scanner countries count its probes as not known,
and the `cdn` total says how many probes came through a CDN. A day stored before these
rules is recounted as it was, so it is never withheld for them.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import UTC, Sandbox, line  # noqa: E402
from test_cdn_addresses import EDGE, lists  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
SCANNER = "203.0.113.66"
CURL, PY = "curl/8.4.0", "python-requests/2.31.0"


class Scanners(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        folder = lists(self.box.root / "ranges")
        self.box.config.write_text(self.box.config.read_text()
                                   + f"bots:\n  ranges_dir: {folder}\n")
        at = datetime(DAY.year, DAY.month, DAY.day, 3, tzinfo=UTC)
        self.box.log([line(at + timedelta(seconds=i), EDGE, "/.env", CURL, country="FR") for i in range(4)]
                     + [line(at + timedelta(minutes=1, seconds=i), EDGE, "/wp-config.php.bak", PY,
                             country="FR") for i in range(3)]
                     + [line(at + timedelta(minutes=2, seconds=i), SCANNER, "/.git/config", CURL,
                             country="NL") for i in range(2)])

    def tearDown(self):
        self.box.close()

    def blob(self) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return json.loads(db.execute(
                "SELECT data FROM day_extras WHERE kind = 'security' AND day = ?",
                (DAY.isoformat(),)).fetchone()[0])
        finally:
            db.close()

    def collect_and_audit(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def test_cdn_edges_are_said_and_their_country_is_not_known_and_the_audit_agrees(self):
        code, out, err = self.collect_and_audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        blob = self.blob()
        self.assertEqual(blob["cdn"], 7, "probes through the CDN edge")
        self.assertEqual(blob["countries"].get("NL"), 2)
        self.assertNotIn("FR", blob["countries"], "the data centre's country is not the scanners'")
        rows = sorted((r["probes"], r.get("cdn"), r["country"]) for r in blob["who"])
        self.assertEqual(rows, [(2, "", "NL"), (3, "Cloudflare", None), (4, "Cloudflare", None)])

    def test_the_block_lists_addresses_mark_a_cdn_edge_on_any_day(self):
        # people/security marks each kept address by today's list, so the block list leaves
        # out a CDN edge even on a day stored before the rows carried a flag (SKALD-20).
        from skald import security_kept
        from skald.config import load_config
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        got = security_kept.listing(load_config(self.box.config), self.box.root, "example.com", DAY, DAY)
        marks = {r["ip"]: r.get("cdn") for r in got["rows"]}
        self.assertEqual(marks, {EDGE: "Cloudflare", SCANNER: None})

    def test_a_day_counted_without_the_list_is_audited_without_it(self):
        # Collected with no CDN list (the day before this release, or a failed fetch); the
        # list arrives later: an audit of that day recounts it as it was, never withholding it.
        (self.box.root / "ranges" / "cdn-cloudflare.json").unlink()
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        from test_cdn_addresses import lists as with_list
        with_list(self.box.root / "ranges")
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_a_day_stored_before_the_rules_is_recounted_as_it_was(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        blob = self.blob()
        # As 2.55 stored it: no cdn total, no row flag, the edge's country kept.
        blob.pop("cdn")
        blob["countries"] = {"FR": 7, "NL": 2}
        for r in blob["who"]:
            if r.pop("cdn"):
                r["country"] = "FR"
        db = sqlite3.connect(str(self.box.db))
        try:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'security' AND day = ?",
                       (json.dumps(blob), DAY.isoformat()))
            db.commit()
        finally:
            db.close()
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)


if __name__ == "__main__":
    unittest.main()
