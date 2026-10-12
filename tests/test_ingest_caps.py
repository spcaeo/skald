"""The ingest's guards against filling the disk (security review 2, finding 7):
a per-organisation daily byte cap counted as lines are accepted, a free-disk
guard (507), and a read-only organisation refused (402)."""
from __future__ import annotations

import sys
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import B  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import ingest, ingest_log  # noqa: E402

Usage = namedtuple("Usage", "total used free")
GB = 1024 ** 3


class DailyCap(TenantServer):
    def test_bytes_over_the_orgs_day_are_refused_and_the_count_survives(self):
        one = len(lines(5))
        self.config["ingest"]["org_daily_mb"] = (one * 1.5) / (1024 * 1024)
        token = self.token(self.beta)
        self.assertEqual(self.ship(B, token, lines(5), batch="s:1").status, 200)
        got = self.ship(B, token, lines(5), batch="s:2")
        self.assertEqual(got.status, 429, got.json)
        self.assertIn("a day", got.json["error"])
        self.assertTrue(int(got.header("Retry-After")) >= 60)
        self.assertEqual(self.stored(B).count(b"\n"), 5)
        # Counted on disk as accepted, not in memory: a new count still refuses.
        used = ingest_log.org_bytes(self.ingest_root, self.beta["id"])
        self.assertEqual(used, one)
        self.assertEqual(self.ship(B, token, lines(5), batch="s:3").status, 429)

    def test_a_refused_or_repeated_batch_is_not_counted(self):
        token = self.token(self.beta)
        self.assertEqual(self.ship(B, token, lines(2), batch="s:1").status, 200)
        self.assertEqual(self.ship(B, token, lines(2), batch="s:1").status, 200)   # repeat
        self.assertEqual(ingest_log.org_bytes(self.ingest_root, self.beta["id"]),
                         len(lines(2)))

    def test_the_plan_may_set_its_own_daily_size(self):
        self.config["ingest"]["org_daily_mb"] = 1000
        small = (len(lines(5)) * 1.5) / (1024 * 1024)
        with mock.patch("skald.saas.limits.limits_for",
                        return_value={"plan": "tiny", "sites": None, "members": None,
                                      "requests_month": None}), \
                mock.patch("skald.saas.plans.plans",
                           return_value={"tiny": {"name": "tiny", "ingest_daily_mb": small}}):
            token = self.token(self.beta)
            self.assertEqual(self.ship(B, token, lines(5), batch="s:1").status, 200)
            self.assertEqual(self.ship(B, token, lines(5), batch="s:2").status, 429)


class DiskAndPlan(TenantServer):
    def test_short_of_disk_is_507_and_nothing_is_written(self):
        token = self.token(self.beta)
        self.config["ingest"].pop("min_free_gb")            # unset: the default floor, 5 GB
        with mock.patch.object(ingest, "disk_usage",
                               return_value=Usage(100 * GB, 99 * GB, 1 * GB)):
            got = self.ship(B, token, lines(2))
        self.assertEqual(got.status, 507, got.json)
        self.assertEqual(self.stored(B), b"")
        self.config["ingest"]["min_free_gb"] = 0.5
        with mock.patch.object(ingest, "disk_usage",
                               return_value=Usage(100 * GB, 99 * GB, 1 * GB)):
            self.assertEqual(self.ship(B, token, lines(2), batch="s:2").status, 200)

    def test_a_read_only_organisation_is_402(self):
        token = self.token(self.beta)
        with mock.patch("skald.saas.limits.read_only",
                        return_value="The last payment failed."):
            got = self.ship(B, token, lines(2))
        self.assertEqual(got.status, 402, got.json)
        self.assertIn("payment", got.json["error"])
        self.assertEqual(self.stored(B), b"")


if __name__ == "__main__":
    unittest.main()
