"""Site › Data quality's scheduled jobs on a multi-site install (SKALD-26).

On a live install of eight sites, every site but the first said "History backup: never ran" in
red. The backup runs once for the whole install: it copies the one history file that holds
every site's figures, and records its run beside the history, in the first site's folder.
Each other site reads its jobs from its own folder (multisite.state_dir), where no backup is
ever recorded. Pinned here: the install's own jobs (runs.INSTALL_WIDE) are read beside the
history for every site; a site's own jobs stay its own.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import quality, runs  # noqa: E402

UTC = timezone.utc


class InstallWideJobs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.other = self.home / "sites" / "second.example"
        self.other.mkdir(parents=True)
        self.history = self.home / "history.sqlite"
        runs.record(self.home, "backup", 0, datetime(2026, 11, 17, 8, 30, tzinfo=UTC))
        runs.record(self.home, "live", 0, datetime(2026, 11, 17, 12, 0, tzinfo=UTC))
        runs.record(self.other, "live", 0, datetime(2026, 11, 17, 12, 2, tzinfo=UTC))
        runs.record(self.other, "verify-bots", 1, datetime(2026, 11, 17, 7, 20, tzinfo=UTC))

    def test_the_backup_is_read_beside_the_history_for_every_site(self):
        got = quality.job_state(self.other, self.history)
        self.assertEqual(got["backup"]["last_ok"], "2026-11-17T08:30:00+00:00")
        self.assertEqual(got["live"]["last_ok"], "2026-11-17T12:02:00+00:00", "a site's own job stays its own")
        self.assertEqual(got["verify-bots"]["last_exit"], 1)

    def test_the_first_site_reads_its_own_folder(self):
        got = quality.job_state(self.home, self.history)
        self.assertEqual(got["backup"]["last_ok"], "2026-11-17T08:30:00+00:00")
        self.assertEqual(got["live"]["last_ok"], "2026-11-17T12:00:00+00:00")

    def test_a_backup_that_never_ran_still_says_so(self):
        (self.home / runs.FILE).unlink()
        self.assertNotIn("backup", quality.job_state(self.other, self.history))

    def test_no_folder_or_no_history(self):
        self.assertEqual(quality.job_state(None, self.history), {})
        self.assertEqual(quality.job_state(self.other, None)["live"]["last_ok"], "2026-11-17T12:02:00+00:00")

    def test_a_newer_backup_in_the_sites_own_folder_wins(self):
        # `backup --site second.example` runs with that site's folder and records there.
        runs.record(self.other, "backup", 1, datetime(2026, 11, 18, 9, 0, tzinfo=UTC))
        got = quality.job_state(self.other, self.history)["backup"]
        self.assertEqual((got["last_fail"], got["last_exit"]), ("2026-11-18T09:00:00+00:00", 1))
        runs.record(self.home, "backup", 0, datetime(2026, 11, 19, 8, 30, tzinfo=UTC))
        got = quality.job_state(self.other, self.history)["backup"]
        self.assertEqual((got["last_ok"], got["last_exit"]), ("2026-11-19T08:30:00+00:00", 0))

    def test_the_page_reads_its_jobs_through_job_state(self):
        from types import SimpleNamespace
        from unittest import mock
        p = SimpleNamespace(live_dir=self.other, history=SimpleNamespace(path=self.history, db=mock.MagicMock()),
                            daily=[], snap=None, live_ok=False, config={}, key="second.example",
                            first=datetime(2026, 11, 1).date(), anchor=datetime(2026, 11, 17).date(), extras={})
        p.history.db.execute.return_value = []
        got = quality.build(p)
        self.assertEqual(got["runs"]["backup"]["last_ok"], "2026-11-17T08:30:00+00:00")
        self.assertEqual(got["runs"]["live"]["last_ok"], "2026-11-17T12:02:00+00:00")

    def test_only_the_backup_is_the_installs(self):
        self.assertEqual(runs.INSTALL_WIDE, ("backup",))


if __name__ == "__main__":
    unittest.main()
