"""The independent audit of visits and of our own traffic by label.

What is pinned: a collected day's visit figures and today's live snapshot
recount exactly by the audit's own road; a stored visit figure nudged by one
is caught and, with --withhold, keeps the day off the page; and the audit's
visits module imports nothing from the package.
"""
from __future__ import annotations

import ast
import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_extras, audit_visits  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, UTC, Sandbox, day_lines, line  # noqa: E402
from test_visits import DAY, OFFICE, T, journey_day  # noqa: E402


class AuditVisits(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.config.write_text(self.box.config.read_text().replace(
            "ours:\n  user_agents: [MyCompanyCrawler]\n",
            "ours:\n  user_agents:\n    - {agent: MyCompanyCrawler, label: crawler}\n"
            f"  addresses: [{OFFICE}]\n"))
        self.box.log(day_lines(DAY, 3) + journey_day() + [
            line(T, OFFICE, "/", CHROME),
            line(T, "198.51.100.3", "/", "MyCompanyCrawler/2"),
        ])
        code, _, err = self.box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_a_stored_day_recounts_exactly(self):
        code, out, err = self.box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)
        with History(self.box.db) as h:
            labels = dict(h.db.execute("SELECT name, n FROM counts WHERE kind = 'ours_label'"))
        # An unlabelled address is named by its place in the list, never itself.
        self.assertEqual(labels, {"Listed address 1": 1, "crawler": 1})

    def test_a_nudged_visit_figure_is_caught_and_withheld(self):
        db = sqlite3.connect(self.box.db)
        db.execute("UPDATE counts SET n = n + 1 WHERE kind = 'visit_step' AND site = "
                   "'example.com' AND name LIKE '/compare/x/%'")
        db.commit()
        db.close()
        code, out, err = self.box.run("--today", "2026-10-06", "audit", "--day",
                                      "2026-10-05", "--withhold")
        self.assertEqual(code, 1)
        self.assertIn("visits by steps: /compare/x/ → /features/", err)
        self.assertNotIn("203.0.113.", err)
        with History(self.box.db) as h:
            self.assertEqual(h.state("example.com", DAY), "withheld")

    def test_a_nudged_label_count_is_caught(self):
        db = sqlite3.connect(self.box.db)
        db.execute("UPDATE counts SET n = n + 1 WHERE kind = 'ours_label' AND name = 'crawler'")
        db.commit()
        db.close()
        code, _, err = self.box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 1)
        self.assertIn("our own traffic: crawler", err)

    def test_live_recounts_exactly(self):
        now = datetime(2026, 10, 5, 20, tzinfo=UTC)
        with mock.patch("skald.cli._now", return_value=now):
            self.assertEqual(self.box.run("live")[0], 0)
            code, out, err = self.box.run("audit", "--live")
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)


class TestIndependence(unittest.TestCase):

    def test_the_visits_recount_imports_nothing_from_the_package(self):
        source = Path(audit_visits.__file__).read_text() + Path(audit_extras.__file__).read_text()
        relative = [node for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.ImportFrom) and node.level]
        self.assertEqual(relative, [])


if __name__ == "__main__":
    unittest.main()
