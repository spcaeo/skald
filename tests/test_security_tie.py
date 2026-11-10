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


# #1 (2.45.8): exposure rows tie on (verdict, second, host, path) when two addresses ask for
# the same path in the same second; one site's 4 Nov was withheld for rows 13 and 14
# ("history has 110, the recount finds 63", then the other way round).
RULES = {"tolerance": 16, "shell_paths": 3}


def answered(order):
    return [("example.com", "/.env", T, 200, size, "secrets", key) for key, size in order]


def main_exposure(order, seq):
    c = security.Collector.__new__(security.Collector)
    c.rules, c.sizes, c.query_only = RULES, {}, 0
    c.answered = answered(order)
    return c._exposure(seq)["rows"]


def audit_exposure(order, seq):
    r = Recount.__new__(Recount)
    r.rules = RULES
    return r._exposure(answered(order), {}, seq)["rows"]


class TiedExposureRows(unittest.TestCase):
    def test_one_order_whatever_the_order_seen(self):
        seq = {A: 110, B: 63}
        for size_a, size_b in ((512, 512), (None, None), (512, 700)):
            one, other = [(A, size_a), (B, size_b)], [(B, size_b), (A, size_a)]
            with self.subTest(sizes=(size_a, size_b)):
                self.assertEqual(main_exposure(one, seq), main_exposure(other, seq))
                self.assertEqual(audit_exposure(one, seq), audit_exposure(other, seq))
                self.assertEqual(main_exposure(one, seq), audit_exposure(other, seq))
        same = main_exposure([(A, 512), (B, 512)], seq)
        self.assertEqual([r["who"] for r in same], [63, 110])   # the address number settles it


if __name__ == "__main__":
    unittest.main()
