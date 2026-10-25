"""2.35.1: attack rows that tie on everything but their answers keep one order on both roads.
Two traversal tries in the same second from addresses without a number, one answered 3xx and
one 4xx, were stored in one order and recounted in the other; the audit withheld the day."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import security  # noqa: E402
from skald.audit_security import Recount  # noqa: E402

T = datetime(2026, 10, 24, 19, 37, 14, tzinfo=timezone.utc)
A, B = ("192.0.2.1", "UA"), ("192.0.2.2", "UA")


def main_rows(order):
    c = security.Collector.__new__(security.Collector)
    c.inj = {}
    for key, status in order:
        c.inj[(key, "traversal")] = [1, T, T, Counter({status: 1})]
    return c._injection({})["rows"]


def audit_rows(order):
    inj = {(key, "traversal"): [1, [T], Counter({status: 1})] for key, status in order}
    return Recount._inj(inj, {})["rows"]


class TiedRows(unittest.TestCase):
    def test_one_order_whatever_the_order_seen(self):
        one, other = [(A, "3xx"), (B, "4xx")], [(B, "4xx"), (A, "3xx")]
        self.assertEqual(main_rows(one), main_rows(other))
        self.assertEqual(audit_rows(one), audit_rows(other))
        self.assertEqual(main_rows(one), audit_rows(other))
        self.assertEqual([r["status"] for r in main_rows(other)], [{"3xx": 1}, {"4xx": 1}])


if __name__ == "__main__":
    unittest.main()
