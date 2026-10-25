"""Crawler address checks on by default in Docker (F6, 2026-10-25).

render_config writes bots.ranges_dir unless SKALD_VERIFY_BOTS says off, the
container makes the folder, run-daily then runs verify-bots before counting,
a first fetch that fails keeps counting going, a second site's run the same
morning does not fetch the lists again, and doctor says when checks are off.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from support import CHROME, SECRETS, Sandbox, line  # noqa: E402
from skald import bot_verify, doctor  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


entrypoint = _load("skald_docker_entrypoint_f6", ROOT / "docker" / "entrypoint.py")
UTC = timezone.utc
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


class TheConfig(unittest.TestCase):
    def test_on_by_default_in_the_data_folder(self):
        cfg = entrypoint.render_config({})
        self.assertEqual(cfg["bots"], {"ranges_dir": str(entrypoint.DATA / "ranges")})

    def test_switched_off_by_the_environment(self):
        for off in ("off", "0", "false", "no", " OFF "):
            with self.subTest(off=off):
                self.assertNotIn("bots", entrypoint.render_config({"SKALD_VERIFY_BOTS": off}))
        for on in ("on", "1", "yes", ""):
            with self.subTest(on=on):
                self.assertIn("bots", entrypoint.render_config({"SKALD_VERIFY_BOTS": on}))

    def test_the_container_makes_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "data" / "ranges"
            entrypoint.ranges_folder({"bots": {"ranges_dir": str(folder)}})
            self.assertTrue(folder.is_dir())
            entrypoint.ranges_folder({})                 # off: nothing to make
            blocked = Path(tmp) / "file"
            blocked.write_text("x")
            with mock.patch.object(entrypoint, "log") as said:
                entrypoint.ranges_folder({"bots": {"ranges_dir": str(blocked / "ranges")}})
            self.assertIn("crawler checks wait", said.call_args[0][0])


def lists(folder: Path, fetched: datetime, error=None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in [*bot_verify.LISTS, "hosting"]:
        (folder / f"{name}.json").write_text(json.dumps(
            {"source": "test", "fetched": fetched.isoformat(), "networks": ["192.0.2.0/28"],
             "error": error}))


class TheDailyRun(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        env = mock.patch.dict(os.environ, SECRETS)
        env.start()
        self.addCleanup(env.stop)
        self.ranges = self.box.root / "ranges"
        self.box.config.write_text(self.box.config.read_text()
                                   + f"bots:\n  ranges_dir: {self.ranges}\n")
        t = datetime(2026, 10, 5, 15, tzinfo=UTC)
        self.box.log([line(t, "203.0.113.20", "/", CHROME)])

    def tearDown(self):
        self.box.close()

    def test_verify_bots_runs_first_and_a_failed_fetch_never_stops_counting(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("no network")), \
                mock.patch.object(bot_verify, "resolve", return_value={}):
            code, out, err = self.box.run("--today", "2026-10-06", "run-daily", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertLess(out.index("list google-common: failed"), out.index("audit ok"))
        stored = json.loads((self.ranges / "openai-gptbot.json").read_text())
        self.assertEqual(stored["networks"], [])
        self.assertIn("no network", stored["error"])

    def test_lists_fetched_this_morning_are_not_fetched_again(self):
        lists(self.ranges, datetime.now(UTC) - timedelta(hours=2))
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("fetched")), \
                mock.patch.object(bot_verify, "resolve", return_value={}):
            code, out, err = self.box.run("--today", "2026-10-06", "run-daily", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("lists: all fetched within 12 hours; kept", out)

    def test_which_lists_are_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertFalse(bot_verify.lists_current(folder, NOW))
            lists(folder, NOW - timedelta(hours=11))
            self.assertTrue(bot_verify.lists_current(folder, NOW))
            self.assertFalse(bot_verify.lists_current(folder, NOW + timedelta(hours=2)))
            lists(folder, NOW, error="URLError: timed out")
            self.assertFalse(bot_verify.lists_current(folder, NOW))


class TheDoctor(unittest.TestCase):
    def check(self, config, env=None):
        with mock.patch.dict(os.environ, env or {}, clear=False):
            if not env:
                os.environ.pop("SKALD_VERIFY_BOTS", None)
            return doctor.crawler_checks(config, NOW, "bin/skald")

    def test_off_needs_attention(self):
        got = self.check({})
        self.assertEqual(got["state"], doctor.ATTENTION)
        self.assertIn("crawler checks off", got["says"])
        self.assertIn("ranges_dir", got["fix"])

    def test_switched_off_on_purpose_is_off(self):
        got = self.check({}, {"SKALD_VERIFY_BOTS": "off"})
        self.assertEqual(got["state"], doctor.OFF)

    def test_on_before_the_first_fetch_fresh_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "ranges"
            config = {"bots": {"ranges_dir": str(folder)}}
            got = self.check(config)
            self.assertEqual(got["state"], doctor.OK)
            self.assertIn("not fetched yet", got["says"])
            lists(folder, NOW - timedelta(days=1))
            got = self.check(config)
            self.assertEqual(got["state"], doctor.OK)
            self.assertIn(f"{len(bot_verify.LISTS)} of {len(bot_verify.LISTS)}", got["says"])
            lists(folder, NOW - timedelta(days=9))
            got = self.check(config)
            self.assertEqual(got["state"], doctor.ATTENTION)
            self.assertIn("older than 7 days", got["says"])


if __name__ == "__main__":
    unittest.main()
