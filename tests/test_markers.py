"""Deploy markers (markers.py): what goes into markers.json, and what never does."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import markers  # noqa: E402

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
NOW = datetime(2026, 10, 8, 16, 0, tzinfo=UTC)


class _Answer:
    def __init__(self, body: str) -> None:
        self.body = body.encode()

    def read(self, n=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _page(config, directory, now=NOW):
    return SimpleNamespace(config=config, live_dir=directory, now=now.astimezone(NY), tz=NY)


class TestMarkers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_then_build_newest_first_in_local_time(self):
        markers.append(self.dir, "skald_deploy", "release 1", at=NOW - timedelta(days=2))
        markers.append(self.dir, "backfill", "backfill --force 14 days", "old 10, new 9",
                       at=NOW - timedelta(hours=1))
        got = markers.build(_page({}, self.dir))
        self.assertEqual([m["kind"] for m in got["markers"]], ["backfill", "skald_deploy"])
        self.assertEqual(got["markers"][0]["at"], "2026-10-08T11:00:00-04:00")
        self.assertEqual(got["markers"][0]["detail"], "old 10, new 9")
        self.assertIsNone(got["website_version"])

    def test_older_than_180_days_and_garbage_lines_are_dropped(self):
        markers.append(self.dir, "skald_deploy", "ancient", at=NOW - timedelta(days=181))
        with open(self.dir / markers.LOG, "a") as handle:
            handle.write("not json\n{\"at\": \"x\"}\n{\"at\": \"2026-10-08T00:00:00+00:00\", "
                         "\"kind\": \"nonsense\", \"label\": \"x\"}\n")
        self.assertEqual(markers.build(_page({}, self.dir))["markers"], [])

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            markers.append(self.dir, "party", "x")

    def test_release_directories_are_dated_by_name_else_mtime(self):
        rel = self.dir / "releases"
        (rel / "20261007-151422").mkdir(parents=True)
        (rel / "hotfix").mkdir()
        os.utime(rel / "hotfix", (NOW.timestamp() - 3600, NOW.timestamp() - 3600))
        (rel / "notes.txt").write_text("a file, not a release")
        got = markers.build(_page({"markers": {"releases_dir": str(rel)}}, self.dir))["markers"]
        self.assertEqual([m["label"] for m in got],
                         ["website release hotfix", "website release 20261007-151422"])
        self.assertEqual(got[1]["at"], "2026-10-07T11:14:22-04:00")
        self.assertTrue(all(m["kind"] == "website_release" for m in got))

    def test_internal_address_changes_never_carry_the_address(self):
        log = self.dir / "ours-changes.log"
        log.write_text("2026-10-07T17:26:00+00:00\tadd\tOffice Mac\t192.0.2.10\tpage\n"
                       "2026-10-07T18:00:00+00:00\tremove\tOffice Mac\t192.0.2.10\tpage\n"
                       "broken line\n")
        got = markers.build(_page({"ours": {"change_log": str(log)}}, self.dir))
        labels = [m["label"] for m in got["markers"]]
        self.assertEqual(labels, ["internal address removed: Office Mac",
                                  "internal address added: Office Mac"])
        self.assertNotIn("192.0.2.10", json.dumps(got))

    def test_config_change_needs_a_previous_hash(self):
        cfg = self.dir / "config.yml"
        cfg.write_text("site:\n  name: example.com\n")
        self.assertIsNone(markers.note_config(cfg, self.dir, NOW))
        self.assertIsNone(markers.note_config(cfg, self.dir, NOW))
        cfg.write_text("site:\n  name: example.org\n")
        marker = markers.note_config(cfg, self.dir, NOW)
        self.assertEqual(marker["kind"], "config_change")
        self.assertIsNone(markers.note_config(cfg, self.dir, NOW))
        self.assertEqual(len(markers.build(_page({}, self.dir))["markers"]), 1)

    def test_missing_config_file_is_not_an_error(self):
        self.assertIsNone(markers.note_config(self.dir / "absent.yml", self.dir, NOW))

    def test_version_is_fetched_at_most_every_30_minutes(self):
        config = {"markers": {"version_url": "https://www.example.com/"}}
        page = "<footer>v1.4.0 · build 212</footer>"
        with mock.patch("urllib.request.urlopen", return_value=_Answer(page)) as fetch:
            self.assertEqual(markers.refresh_version(config, self.dir, NOW), "v1.4.0 · build 212")
            markers.refresh_version(config, self.dir, NOW + timedelta(minutes=10))
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(fetch.call_args.kwargs["timeout"], 5)
        self.assertEqual(markers.build(_page({}, self.dir))["website_version"],
                         "v1.4.0 · build 212")
        # The first version seen is not a release; a change is.
        self.assertEqual(markers.build(_page({}, self.dir))["markers"], [])
        with mock.patch("urllib.request.urlopen",
                        return_value=_Answer("v1.5.0 · build 230")) as fetch:
            markers.refresh_version(config, self.dir, NOW + timedelta(minutes=31))
            self.assertEqual(fetch.call_count, 1)
        got = markers.build(_page({}, self.dir, NOW + timedelta(hours=1)))["markers"]
        self.assertEqual([m["label"] for m in got], ["site now v1.5.0 · build 230"])

    def test_failed_fetch_keeps_the_last_good_version(self):
        config = {"markers": {"version_url": "https://www.example.com/"}}
        with mock.patch("urllib.request.urlopen", return_value=_Answer("v2.0 · build 1")):
            markers.refresh_version(config, self.dir, NOW)
        with mock.patch("urllib.request.urlopen", side_effect=OSError("timed out")):
            self.assertEqual(markers.refresh_version(config, self.dir, NOW, force=True),
                             "v2.0 · build 1")
        state = json.loads((self.dir / markers.VERSION_FILE).read_text())
        self.assertIn("timed out", state["error"])
        self.assertEqual(state["version"], "v2.0 · build 1")

    def test_react_comments_in_the_footer_are_read_through(self):
        config = {"markers": {"version_url": "https://www.example.com/"}}
        page = '<p>v<!-- -->1.4.0<!-- --> · build <!-- -->212<!-- --> · </p>'
        with mock.patch("urllib.request.urlopen", return_value=_Answer(page)) as fetch:
            self.assertEqual(markers.refresh_version(config, self.dir, NOW), "v1.4.0 · build 212")
        agent = fetch.call_args[0][0].get_header("User-agent")
        self.assertNotIn("skald", agent)     # never counted as the heartbeat

    def test_no_url_means_no_fetch(self):
        with mock.patch("urllib.request.urlopen") as fetch:
            self.assertIsNone(markers.refresh_version({}, self.dir, NOW))
            fetch.assert_not_called()

    def test_build_never_fetches(self):
        config = {"markers": {"version_url": "https://www.example.com/"}}
        with mock.patch("urllib.request.urlopen") as fetch:
            markers.build(_page(config, self.dir))
            fetch.assert_not_called()


class TestCommands(unittest.TestCase):
    def test_mark_deploy_and_list(self):
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            ap = argparse.ArgumentParser()
            sub = ap.add_subparsers(dest="command")
            markers.add_command(sub)
            lines = []
            ctx = SimpleNamespace(live_dir=Path(tmp), config={}, now=datetime.now(UTC), tz=NY,
                                  out=lines.append, err=lines.append)
            ctx.args = ap.parse_args(["mark-deploy", "--label", "release 2", "--detail", "abc123"])
            self.assertEqual(ctx.args.run(ctx), 0)
            ctx.args = ap.parse_args(["markers", "--json"])
            self.assertEqual(ctx.args.run(ctx), 0)
            got = json.loads(lines[-1])
            self.assertEqual(got["markers"][0]["kind"], "skald_deploy")
            self.assertEqual(got["markers"][0]["label"], "release 2")
            self.assertEqual(got["markers"][0]["detail"], "abc123")


if __name__ == "__main__":
    unittest.main()
