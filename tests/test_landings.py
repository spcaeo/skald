"""Visits by the page they started on (day kind `landings`, landings.py): the
counts per landing page, the sums verify holds, the fold, and the second
count (audit_landings.py) matching and catching a planted error."""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from support import Sandbox, line, totals_for  # noqa: E402

from skald import audit_landings, audit_more, day_more, extras, landings  # noqa: E402

NOON = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
DAY, TODAY = date(2026, 10, 5), "2026-10-06"
# (address, [(minute, path)], referrer of the first page)
VISITS = [
    ("203.0.113.20", [(0, "/pricing/")], "https://www.google.com/"),            # one page, search
    ("203.0.113.21", [(1, "/pricing/"), (2, "/signup/")], "https://www.google.com/"),
    ("203.0.113.22", [(3, "/pricing/")], "-"),                                  # one page, direct
    ("203.0.113.23", [(4, "/guides/alpha"), (5, "/pricing/"), (6, "/")], "https://chatgpt.com/"),
    ("203.0.113.24", [(7, "/guides/alpha")], "https://chatgpt.com/"),          # one page, AI
    ("203.0.113.25", [(8, "/")], "-"),
]


def lines() -> list[str]:
    out = []
    for address, steps, ref in VISITS:
        for i, (minute, path) in enumerate(steps):
            out.append(line(NOON + timedelta(minutes=minute), address, path,
                            referrer=ref if i == 0 else "https://example.com/"))
    return sorted(out)


class Kind(unittest.TestCase):
    def test_registered(self):
        self.assertIn("landings", day_more.modules())
        self.assertIn("landings", audit_more._modules(audit_more.RECOUNTS))

    def test_per_landing_page(self):
        totals = totals_for(lines())
        blob = totals.extras["landings"]
        self.assertEqual(blob["fields"], ["visits", "one_page", "views", "search", "ai"])
        self.assertEqual(blob["folded"], 0)
        self.assertEqual(blob["pages"], {"/pricing/": [3, 2, 4, 2, 0],
                                         "/guides/alpha": [2, 1, 4, 0, 2],
                                         "/": [1, 1, 1, 0, 0]})
        self.assertEqual(extras.check(totals), [])

    def test_check_catches_rows_that_do_not_add_up(self):
        totals = totals_for(lines())
        totals.extras["landings"]["pages"]["/pricing/"][1] = 3
        self.assertIn("landings: one-page visits does not sum", [p.what for p in extras.check(totals)])
        totals = totals_for(lines())
        totals.extras["landings"]["pages"]["/"] = [1, 2, 1, 0, 0]
        self.assertTrue(any(p.what == "landings: /" for p in extras.check(totals)))

    def test_the_fold_keeps_the_sums(self):
        rows = {f"/p{i:03d}": [i + 1, 1, i + 1, 0, 0] for i in range(landings.TOP + 5)}
        kept, folded = landings._fold(rows)
        self.assertEqual(folded, 5)
        self.assertEqual(len(kept), landings.TOP + 1)
        self.assertEqual(kept[landings.OTHER], [1 + 2 + 3 + 4 + 5, 5, 15, 0, 0])
        self.assertEqual(sum(r[0] for r in kept.values()), sum(r[0] for r in rows.values()))

    def test_the_recount_counts_by_its_own_rule(self):
        r = audit_landings.Recount({}, DAY, timezone.utc, {"example.com"})
        page = lambda _line: True  # noqa: E731
        r.visit([1, 2], page, {"landing": "/a/", "source": "Search engine"})
        r.visit([1], page, {"landing": "/a/", "source": "AI assistant"})
        r.visit([1], lambda _l: False, None)          # read no page: not a visit here
        self.assertEqual(r.rows, {"/a/": [2, 1, 3, 1, 1]})
        found = []
        r.compare({"landings": {"pages": {"/a/": [2, 1, 3, 1, 1]}, "folded": 0}},
                  lambda what, a, b: found.append(what) if a != b else None, [])
        self.assertEqual(found, [])
        r.compare({"landings": {"pages": {"/a/": [2, 2, 3, 1, 1]}, "folded": 0}},
                  lambda what, a, b: found.append(what) if a != b else None, [])
        self.assertEqual(found, ["landings on /a/: one_page"])

    def test_audit_matches_and_catches_a_planted_error(self):
        box = Sandbox()
        try:
            box.log(lines())
            self.assertEqual(box.run("--today", TODAY, "collect")[0], 0)
            code, _, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 0, err)
            db = sqlite3.connect(str(box.db))
            with db:
                got = json.loads(db.execute("SELECT data FROM day_extras WHERE "
                                            "kind = 'landings'").fetchone()[0])
                got["pages"]["/pricing/"][3] = 1
                db.execute("UPDATE day_extras SET data = ? WHERE kind = 'landings'",
                           (json.dumps(got),))
            db.close()
            code, _, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 1)
            self.assertIn("landings on /pricing/: search: history has 1, the recount finds 2", err)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
