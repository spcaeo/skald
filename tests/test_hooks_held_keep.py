"""Held refused deliveries on a site that keeps everything (owner's rule: internal and
enterprise sites delete nothing by themselves): never purged by age or by the cap; past
KEEP_ALL_CAP a hook holds no more, and no old one is deleted to make room."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skald.conversions import held

SITE, TOOL = "example.com", "calendly"
HEADERS = {"calendly-webhook-signature": "t=1,v1=00", "content-type": "application/json"}
DAY = 24 * 3600


class KeepEverything(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def hold(self, at, keeps):
        return held.keep(self.folder, SITE, TOOL, HEADERS, b'{"n": 1}', at, "bad_signature", keeps=keeps)

    def test_kept_past_a_day_when_the_site_keeps_everything(self):
        self.hold(1_000_000.0, keeps=True)
        later = 1_000_000.0 + 3 * DAY
        self.assertEqual(held.purge(self.folder, later, SITE, TOOL, keeps=True), 0)
        self.assertEqual(held.count(self.folder, SITE, TOOL, later, keeps=True), 1)
        self.assertEqual(len(held.entries(self.folder, SITE, TOOL, later, keeps=True)), 1)
        self.assertEqual(held.purge(self.folder, later, keeps=lambda site: site == SITE), 0, "the daily run, per site")

    def test_a_client_site_still_loses_them_after_a_day(self):
        self.hold(1_000_000.0, keeps=False)
        later = 1_000_000.0 + 2 * DAY
        self.assertEqual(held.count(self.folder, SITE, TOOL, later), 0)
        self.assertEqual(held.purge(self.folder, later, SITE, TOOL), 1)

    def test_past_the_cap_new_ones_are_not_held_and_none_deleted(self):
        with mock.patch.object(held, "KEEP_ALL_CAP", 3), mock.patch.object(held, "CAP", 2):
            for n in range(3):
                self.assertIsNotNone(self.hold(1_000_000.0 + n, keeps=True))
            self.assertIsNone(self.hold(1_000_010.0, keeps=True))
            self.assertEqual(held.count(self.folder, SITE, TOOL, 1_000_020.0, keeps=True), 3)

    def test_the_rule(self):
        with mock.patch("skald.keep_everything.Keeper") as K:
            K.return_value.why.return_value = "install"
            self.assertTrue(held.keeps({}, self.folder, SITE))
            K.return_value.why.return_value = None
            self.assertFalse(held.keeps({}, self.folder, SITE))
            K.return_value.why.side_effect = OSError("unreadable")
            self.assertTrue(held.keeps({}, self.folder, SITE), "an unreadable rule keeps")


if __name__ == "__main__":
    unittest.main()
