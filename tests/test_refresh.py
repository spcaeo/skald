"""The dashboard's Refresh now button and its local helper."""
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import dashboard  # noqa: E402
from skald.refresh_server import (  # noqa: E402
    Runner, allowed_origins, back_to, same_origin)


class BackTo(unittest.TestCase):
    def test_site_and_view_pages(self):
        self.assertEqual(back_to("/traffic/example.com/refresh"), "/traffic/example.com/")
        self.assertEqual(back_to("/traffic/example.com/us-english/refresh"),
                         "/traffic/example.com/us-english/")

    def test_rejects_other_paths(self):
        for bad in ["/refresh", "/traffic/refresh", "/traffic/example.com/a/b/refresh",
                    "/traffic/../etc/refresh", "/traffic/example.com/refresh/x",
                    "/traffic/Example.com/refresh", "//evil.com/refresh"]:
            self.assertIsNone(back_to(bad), bad)


class SameOrigin(unittest.TestCase):
    ALLOWED = {"https://www.example.com"}

    def test_fetch_metadata_wins(self):
        self.assertTrue(same_origin({"Sec-Fetch-Site": "same-origin"}, self.ALLOWED))
        self.assertFalse(same_origin({"Sec-Fetch-Site": "cross-site",
                                      "Origin": "https://www.example.com"}, self.ALLOWED))

    def test_origin_fallback(self):
        self.assertTrue(same_origin({"Origin": "https://www.example.com"}, self.ALLOWED))
        self.assertFalse(same_origin({"Origin": "https://evil.example"}, self.ALLOWED))
        self.assertFalse(same_origin({}, self.ALLOWED))


class AllowedOrigins(unittest.TestCase):
    """--origin has no built-in default: no domain is trusted unless named."""

    def test_none_given_trusts_nothing(self):
        self.assertEqual(allowed_origins([]), set())
        self.assertEqual(allowed_origins(None), set())
        # Browsers that send Sec-Fetch-Site still get in; Origin-only ones do not.
        self.assertTrue(same_origin({"Sec-Fetch-Site": "same-origin"}, allowed_origins([])))
        self.assertFalse(same_origin({"Origin": "https://www.example.com"},
                                     allowed_origins([])))

    def test_named_origins_kept(self):
        got = allowed_origins(["https://www.example.com/", " https://example.com "])
        self.assertEqual(got, {"https://www.example.com", "https://example.com"})
        self.assertTrue(same_origin({"Origin": "https://www.example.com"}, got))

    def test_generic_unit_names_no_real_domain(self):
        unit = (Path(__file__).resolve().parent.parent / "systemd"
                / "skald-refresh.service").read_text()
        self.assertIn("--origin https://www.example.com", unit)
        self.assertNotIn("acme", unit.lower())


class FakeRun:
    def __init__(self, code=0):
        self.calls, self.code = 0, code

    def __call__(self, *a, **k):
        self.calls += 1
        return subprocess.CompletedProcess(a, self.code)


class RunnerGap(unittest.TestCase):
    def test_runs_then_waits_for_the_gap(self):
        t = [100.0]
        run = FakeRun()
        r = Runner(["x"], ".", gap=15, clock=lambda: t[0], run=run)
        self.assertEqual(r.refresh(), "ran")
        t[0] += 5
        self.assertEqual(r.refresh(), "recent")
        t[0] += 11
        self.assertEqual(r.refresh(), "ran")
        self.assertEqual(run.calls, 2)

    def test_withheld_counts_as_ran_and_errors_as_failed(self):
        self.assertEqual(Runner(["x"], ".", run=FakeRun(1)).refresh(), "ran")
        self.assertEqual(Runner(["x"], ".", run=FakeRun(2)).refresh(), "failed")

    def test_busy_while_running(self):
        r = Runner(["x"], ".", run=FakeRun())
        r.lock.acquire()
        try:
            self.assertEqual(r.refresh(), "busy")
        finally:
            r.lock.release()


class Button(unittest.TestCase):
    def snap(self, now):
        return {"day": now.date().isoformat(), "state": "empty",
                "generated_at": now.isoformat(), "from": now.isoformat()}

    def test_button_only_when_switched_on(self):
        tz = ZoneInfo("America/New_York")
        now = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc).astimezone(tz)
        off = dashboard.live_panel(self.snap(now), tz, now)
        on = dashboard.live_panel(self.snap(now), tz, now, refresh=True)
        self.assertNotIn("Refresh now", off)
        self.assertIn('method="post" action="refresh"', on)
        self.assertIn("Refresh now", on)


if __name__ == "__main__":
    unittest.main()
