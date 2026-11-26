"""Traffic's shared filter (SKALD-62): one Country / Source / Device bar for Visitors, Sources,
Pages and Places & devices. The browser side runs in node (tests/js/shared-filter.mjs); the
server's landing-page split it reads is pinned in tests/test_compare.py."""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from skald import audit_visit_combos  # noqa: E402

JS = Path(__file__).resolve().parent / "js"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class SharedFilter(unittest.TestCase):
    def test_the_shared_filter_counts_only_the_matching_visits_and_says_what_it_cannot_split(self):
        done = subprocess.run(["node", str(JS / "shared-filter.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("shared-filter: all passed", done.stdout)


class Combinations(unittest.TestCase):
    """audit_visit_combos: one figure for the whole set, then at most SHOWN combinations by
    name and the rest as a count, so one wrong field never floods the withheld day's reason."""

    def recount(self, n):
        r = audit_visit_combos.Recount({}, None, None, set())
        for i in range(n):
            r.visit([], None, {"country": f"C{i:02d}", "landing": "/", "source": "Direct", "device": "Desktop",
                               "browser": "Chrome", "os": "Windows", "campaign": "(no campaign tag)"})
        return r

    def test_one_figure_when_all_match_and_a_capped_list_when_not(self):
        rows = [[f"C{i:02d}", "/", "Direct", "", "Desktop", "Chrome", "Windows", "(no campaign tag)", 1] for i in range(30)]
        calls, problems = [], []
        self.recount(30).compare({"visit_cube": {"rows": rows}}, lambda *a: calls.append(a), problems)
        self.assertEqual(calls, [("visit records: combinations that match", 30, 30)])
        self.assertEqual(problems, [])
        calls.clear()
        moved = [[*r[:4], "Mobile", *r[5:]] for r in rows]          # every visit's device differs
        self.recount(30).compare({"visit_cube": {"rows": moved}}, lambda *a: calls.append(a), problems)
        self.assertEqual(calls[0], ("visit records: combinations that match", 60, 0))
        self.assertEqual(len(calls), 1 + audit_visit_combos.SHOWN)
        self.assertEqual(problems, [f"visit records: {60 - audit_visit_combos.SHOWN} more combinations differ"])
        calls.clear()
        self.recount(3).compare({"visit_cube": {"rows": rows[:3], "folded": True}}, lambda *a: calls.append(a), [])
        self.assertEqual(calls, [], "a folded blob is not checked")


if __name__ == "__main__":
    unittest.main()
