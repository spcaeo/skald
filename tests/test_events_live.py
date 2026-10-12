"""events.json's today block reads the live snapshot's people page views
(snapshot "people" -> "views"; "groups" holds plain request counts). It used
to read groups["people"] as a mapping and crashed the dashboard redraw as
soon as the day's first event arrived."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import events  # noqa: E402


class TestTodayWithEvents(unittest.TestCase):
    def test_a_real_snapshot_shape_with_events_draws(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp)
            (spool / "2026-10-08.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
                {"at": "2026-10-08T08:01:43-04:00", "e": "cta_click", "g": "people",
                 "id": "signup_hero", "p": "/", "r": "", "s": "Direct or unknown", "t": 0,
                 "u": "", "vw": "xl"}]))
            snap = {"state": "ok", "groups": {"people": 900, "bots": 50},
                    "people": {"views": 120, "readers": 40}}
            page = SimpleNamespace(snap=snap, today=date(2026, 10, 8), view=None)
            got = events._today(page, spool, None)
        self.assertEqual(got["state"], "ok")
        self.assertEqual(got["events"], {"cta_click": 1})


if __name__ == "__main__":
    unittest.main()
