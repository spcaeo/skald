"""Shared fixtures for the accounts tests. Not a test module itself.

Each test gets a fresh accounts file in a temporary folder and a clock it
can move: `self.at("2026-10-11T14:00:00Z")`, `self.tick(seconds)`.
Addresses are RFC 5737 documentation ranges, mail goes to example.com.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.accounts import db as base  # noqa: E402

START = "2026-10-11T14:00:00Z"
GOOD_PW = "correct horse battery staple"
OTHER_PW = "a different long passphrase"


class AccountsCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "accounts.sqlite"
        self._now = datetime.strptime(START, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        patcher = mock.patch.object(base, "now", self._stamp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = base.connect(self.path)
        self.addCleanup(self._close)

    def _close(self) -> None:
        self.db.close()
        self._tmp.cleanup()

    def _stamp(self) -> str:
        return self._now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def at(self, stamp: str) -> None:
        self._now = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    def tick(self, seconds: float = 0, **kw) -> None:
        self._now += timedelta(seconds=seconds, **kw)

    def audit_actions(self, org_id=None) -> list[str]:
        from skald.accounts import auditlog
        return [e["action"] for e in auditlog.recent(self.db, org_id)]
