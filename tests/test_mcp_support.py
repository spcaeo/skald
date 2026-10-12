"""Fixtures for the MCP tests (no tests here).

`Fixture()` writes a real dashboard output folder with the same commands
the server runs (backfill, then live), from logs made with tests/support.py:
example.com, 2026-10-01 to 2026-10-08 with 3 to 10 readers a day, the
day 2026-10-04 stored as withheld, and today (2026-10-09) so far with two
readers and two AI fetches. A copy of the site's folder is a second site,
shop.example.com, for the isolation tests. Addresses are RFC 5737.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, GPTBOT, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402

FIRST = date(2026, 10, 1)
DAYS = 8
WITHHELD = date(2026, 10, 4)
TODAY = date(2026, 10, 9)
SITE, OTHER = "example.com", "shop.example.com"


def readers_on(day: date) -> int:
    """Readers day_lines makes on a fixture day."""
    return 3 + (day - FIRST).days


class Fixture:
    def __init__(self) -> None:
        from skald.store import History
        from skald.verify import Problem
        self.box = Sandbox(mail=False)
        lines = []
        for i in range(DAYS):
            lines += day_lines(FIRST + timedelta(days=i), readers_on(FIRST + timedelta(days=i)))
        t0 = datetime(TODAY.year, TODAY.month, TODAY.day, 9, tzinfo=UTC)
        lines += [line(t0, "203.0.113.50", "/", referrer="https://chatgpt.com/"),
                  line(t0 + timedelta(minutes=1), "203.0.113.51", "/pricing/"),
                  line(t0 + timedelta(minutes=2), "198.51.100.40", "/guides/alpha", GPTBOT),
                  line(t0 + timedelta(minutes=3), "198.51.100.41", "/", ASKED)]
        self.box.log(lines)
        today = ("--today", TODAY.isoformat())
        code, _, err = self.box.run(*today, "backfill", "--days", str(DAYS))
        assert code == 0, err
        with History(self.box.db) as h:
            h.record(SITE, WITHHELD, totals_for(day_lines(WITHHELD, readers_on(WITHHELD))),
                     "UTC", [Problem("groups do not sum", "test")])
        code, _, err = self.box.run(*today, "live")
        assert code in (0, 1), err
        self.out = self.box.root / "www"
        shutil.copytree(self.out / SITE, self.out / OTHER)
        sites = json.loads((self.out / "sites.json").read_text())
        sites["sites"].append({**sites["sites"][0], "name": OTHER, "slug": OTHER,
                               "path": f"{OTHER}/"})
        (self.out / "sites.json").write_text(json.dumps(sites))

    @property
    def root(self) -> Path:
        return self.box.root

    @property
    def config(self) -> Path:
        return self.box.config

    def context(self, sites=(SITE, OTHER), private=False, **kw):
        from skald.mcp.data import Context
        allowed = set(sites)
        return Context(self.out, history_path=self.box.db,
                       checker=lambda s: (s in allowed, "" if s in allowed
                                          else "this token is not for that site", private),
                       **kw)

    def close(self) -> None:
        self.box.close()
