"""Update notices (updates.py): versions, the release answer, the daily
cache, silence when offline, the mail card, the banner's /me field and
`skald updates`. No test touches the network: the fetcher is passed in."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import mailer, updates  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.store import History  # noqa: E402

from support import SECRETS, UTC, Sandbox, day_lines, totals_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "github_release_latest.json"
T0 = datetime(2026, 10, 21, 6, 0, tzinfo=timezone.utc)


def release(**over) -> dict:
    data = json.loads(FIXTURE.read_text())
    data.update(over)
    return data


class Fetcher:
    """The network, as the tests want it: an answer or an error, and a log of calls."""

    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.calls = answer or release(), error, []

    def __call__(self, url, agent):
        self.calls.append((url, agent))
        if self.error is not None:
            raise self.error
        return json.dumps(self.answer).encode()


class Versions(unittest.TestCase):
    def test_semver_order_including_pre_releases(self):
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                   "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1",
                   "1.9.0", "1.10.0", "2.0.0", "v2.1.0", "2.10.3"]
        for older, newer in zip(ordered, ordered[1:]):
            self.assertEqual(updates.compare(older, newer), -1, (older, newer))
            self.assertEqual(updates.compare(newer, older), 1, (older, newer))
        self.assertEqual(updates.compare("v2.1.0", "2.1.0"), 0)
        self.assertEqual(updates.compare("2.1.0+build.5", "2.1.0"), 0)

    def test_not_a_version(self):
        four_parts = ".".join("2104")      # written so, or the public sweep reads it as an address
        for bad in ("", "2.1", "v2", four_parts, "02.1.0", "latest", None):
            self.assertIsNone(updates.parse_version(bad), bad)
        with self.assertRaises(ValueError):
            updates.compare("2.1", "2.1.0")

    def test_levels(self):
        self.assertEqual(updates.level("2.1.0", "2.1.1"), "patch")
        self.assertEqual(updates.level("2.1.0", "2.2.0"), "minor")
        self.assertEqual(updates.level("2.1.9", "2.2.0"), "minor")
        self.assertEqual(updates.level("2.1.0", "3.0.0"), "major")
        self.assertEqual(updates.level("2.1.0", "2.1.0"), "same")
        self.assertEqual(updates.level("2.1.0", "2.0.9"), "older")
        self.assertEqual(updates.level("2.1.0", "2.1.1-rc.1"), "patch")

    def test_settings(self):
        self.assertEqual(updates.settings({}), {"check": True, "repo": "spcaeo/skald", "auto": "off"})
        got = updates.settings({"updates": {"check": False, "repo": "example/fork", "auto": "minor"}})
        self.assertEqual(got, {"check": False, "repo": "example/fork", "auto": "minor"})
        # YAML reads a bare `off` as false; a nonsense level or repo falls back.
        self.assertEqual(updates.settings({"updates": {"auto": False}})["auto"], "off")
        self.assertEqual(updates.settings({"updates": {"auto": "major"}})["auto"], "off")
        self.assertEqual(updates.settings({"updates": {"repo": "../../evil"}})["repo"], "spcaeo/skald")
        self.assertFalse(updates.settings({"updates": {"check": "false"}})["check"])


class Releases(unittest.TestCase):
    def test_the_fixture(self):
        got = updates.parse_release(release())
        self.assertEqual(got["version"], "2.2.0")
        self.assertEqual(got["tag"], "v2.2.0")
        self.assertEqual(got["url"], "https://github.com/spcaeo/skald/releases/tag/v2.2.0")
        self.assertFalse(got["security"])
        self.assertEqual(got["published_at"], "2026-10-20T09:12:31Z")
        # The first lines, without the heading, the bullets, bold, code or link marks.
        self.assertEqual(got["notes"], [
            "Update notices in the daily mail and on the dashboard (#8).",
            "skald upgrade: safe upgrades with a backup and a rollback.",
            "Explicit database migrations.", "Optional automatic upgrades."])

    def test_security_marks(self):
        self.assertTrue(updates.parse_release(release(name="v2.2.1 [security]"))["security"])
        self.assertTrue(updates.parse_release(release(body="Fixes.\nLabels: bug, security\n"))["security"])
        self.assertTrue(updates.parse_release(release(body="[SECURITY] a session fix"))["security"])
        self.assertFalse(updates.parse_release(release(body="Read SECURITY.md for reports."))["security"])
        notes = updates.parse_release(release(body="Labels: security\nA session fix.\n"))["notes"]
        self.assertEqual(notes, ["A session fix."])

    def test_refused_answers(self):
        for bad in (release(tag_name="nightly"), release(draft=True), release(prerelease=True), []):
            with self.assertRaises(ValueError):
                updates.parse_release(bad)

    def test_a_link_elsewhere_is_replaced_by_the_release_page(self):
        got = updates.parse_release(release(html_url="https://evil.example.com/x"))
        self.assertEqual(got["url"], "https://github.com/spcaeo/skald/releases/tag/v2.2.0")


class Cache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, fetch, now=T0, config=None, **kw):
        return updates.check(config or {}, now, folder=self.folder, fetch=fetch,
                             current="2.1.0", log=self.logged.append, **kw)

    logged: list = []

    def test_once_a_day_and_only_the_user_agent(self):
        self.logged = []
        fetch = Fetcher()
        state = self.check(fetch)
        self.assertEqual(fetch.calls, [("https://api.github.com/repos/spcaeo/skald/releases/latest",
                                        "Skald/2.1.0")])
        self.assertTrue(state["ok"])
        self.assertEqual(state["latest"]["version"], "2.2.0")
        saved = json.loads((self.folder / "updates.json").read_text())
        self.assertEqual(saved["checked_at"], "2026-10-21T06:00:00+00:00")
        self.check(fetch, T0 + timedelta(hours=23))
        self.assertEqual(len(fetch.calls), 1, "asked again within a day")
        self.check(fetch, T0 + timedelta(hours=24, minutes=1))
        self.assertEqual(len(fetch.calls), 2)
        self.check(fetch, T0 + timedelta(hours=25), force=True)
        self.assertEqual(len(fetch.calls), 3, "--check-now asks whatever the time")

    def test_a_changed_repo_is_asked_at_once(self):
        self.logged = []
        fetch = Fetcher()
        self.check(fetch)
        self.check(fetch, T0 + timedelta(hours=1), config={"updates": {"repo": "example/fork"}})
        self.assertEqual(fetch.calls[-1][0], "https://api.github.com/repos/example/fork/releases/latest")

    def test_offline_is_silent_and_said_once(self):
        self.logged = []
        down = Fetcher(error=urllib.error.URLError("no route to host"))
        state = self.check(down)
        self.assertFalse(state["ok"])
        self.assertIn("URLError", state["error"])
        self.check(down, T0 + timedelta(days=1, minutes=1))
        self.check(down, T0 + timedelta(days=2, minutes=2))
        self.assertEqual(len(down.calls), 3)
        self.assertEqual(len(self.logged), 1, self.logged)
        # It works again: the earlier answer is kept meanwhile, the next failure is said again.
        self.check(Fetcher(), T0 + timedelta(days=3, minutes=3))
        self.check(down, T0 + timedelta(days=4, minutes=4))
        self.assertEqual(len(self.logged), 2)
        self.assertEqual(updates.read(self.folder)["latest"]["version"], "2.2.0")

    def test_a_bad_answer_is_a_failure_too(self):
        self.logged = []
        fetch = Fetcher()
        fetch.answer = {"message": "API rate limit exceeded"}
        state = self.check(fetch)
        self.assertFalse(state["ok"])
        self.assertIsNone(state.get("latest"))

    def test_checks_off_never_ask(self):
        self.logged = []
        fetch = Fetcher()
        state = self.check(fetch, config={"updates": {"check": False}}, force=True)
        self.assertEqual(fetch.calls, [])
        self.assertTrue(state["off"])

    def test_notice(self):
        self.logged = []
        self.check(Fetcher())
        n = updates.notice({}, self.folder, "2.1.0")
        self.assertEqual((n["current"], n["latest"], n["level"]), ("2.1.0", "2.2.0", "minor"))
        self.assertIsNone(updates.notice({}, self.folder, "2.2.0"))
        self.assertIsNone(updates.notice({}, self.folder, "2.3.0"))
        self.assertIsNone(updates.notice({"updates": {"check": False}}, self.folder, "2.1.0"))
        self.assertIsNone(updates.notice({}, self.folder / "nowhere", "2.1.0"))


def cached(folder: Path, **over) -> None:
    latest = updates.parse_release(release(**over))
    (folder / "updates.json").write_text(json.dumps(
        {"checked_at": "2026-10-21T06:00:00+00:00", "ok": True, "repo": "spcaeo/skald",
         "latest": latest}))


class Showing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.config = {"_resolved": {"history_db": str(self.folder / "history.sqlite")}}
        self.patch = mock.patch("skald.updates.current_version", return_value="2.1.0")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_mail_card(self):
        self.assertEqual(updates.mail_notice(self.config), ("", ""))
        cached(self.folder)
        text, html = updates.mail_notice(self.config)
        self.assertIn("Skald 2.2.0 is available (you run 2.1.0).", text)
        self.assertIn("What's new: https://github.com/spcaeo/skald/releases/tag/v2.2.0", text)
        self.assertIn("Update available", html)
        self.assertIn('href="https://github.com/spcaeo/skald/releases/tag/v2.2.0"', html)
        self.assertIn("What's new &rarr;", html)
        self.assertNotIn("Security", html)

    def test_security_card_and_escaping(self):
        cached(self.folder, name="v2.2.0 [security]", body="<script>x</script> fix")
        text, html = updates.mail_notice(self.config)
        self.assertIn("a security release", text)
        self.assertIn("Security update available", html)
        self.assertNotIn("<script>", html)

    def test_banner_data_for_owners_and_admins_only(self):
        cached(self.folder)
        for role in ("owner", "admin"):
            body = updates.for_me({"ok": True, "role": role}, self.config, self.folder)
            self.assertEqual(body["update"]["latest"], "2.2.0")
            self.assertEqual(body["update"]["url"],
                             "https://github.com/spcaeo/skald/releases/tag/v2.2.0")
        for role in ("viewer", "", None):
            self.assertNotIn("update", updates.for_me({"ok": True, "role": role}, self.config,
                                                      self.folder))
        (self.folder / "updates.json").write_text("{broken")
        self.assertNotIn("update", updates.for_me({"role": "owner"}, self.config, self.folder))


class MailBuilt(unittest.TestCase):
    """The card inside the real daily mail, read from updates.json only."""

    def test_daily_mail_carries_the_card(self):
        box = Sandbox()
        try:
            history = History(box.db)
            day = date(2026, 10, 5)
            history.record("example.com", day, totals_for(day_lines(day, 3)), "UTC", [])
            config = load_config(box.config)
            config["_resolved"] = {"history_db": str(box.db)}
            cached(box.root)
            brand = {"name": "Skald", "version": "2.1.0", "tagline": "", "release": 1,
                     "commit": "abc", "deployed_at": None}
            with mock.patch.dict(os.environ, SECRETS), \
                    mock.patch("skald.brand.load", return_value=brand):
                msg = mailer.build("daily", config, history, UTC,
                                   datetime(2026, 10, 6, 9, tzinfo=UTC))
            history.close()
            text = msg.get_body(("plain",)).get_content()
            html = msg.get_body(("html",)).get_content()
            self.assertIn("Skald 2.2.0 is available (you run 2.1.0)", text)
            self.assertIn("Update available", html)
        finally:
            box.close()


class Command(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)

    def tearDown(self):
        self.box.close()

    def test_prints_the_state_without_asking(self):
        with mock.patch("skald.updates._get") as net, \
                mock.patch("skald.updates.current_version", return_value="2.1.0"):
            code, out, _ = self.box.run("updates")
            self.assertEqual(code, 0)
            self.assertIn("not asked yet", out)
            cached(self.box.root, name="v2.2.0 [security]")
            code, out, _ = self.box.run("updates")
            net.assert_not_called()
        self.assertIn("Skald 2.2.0 is available (you run 2.1.0): a security release, a minor release", out)
        self.assertIn("what's new: https://github.com/spcaeo/skald/releases/tag/v2.2.0", out)

    def test_check_now_asks_once(self):
        with mock.patch("skald.updates._get",
                        side_effect=lambda url, agent: json.dumps(release()).encode()) as net, \
                mock.patch("skald.updates.current_version", return_value="2.2.0"):
            code, out, _ = self.box.run("updates", "--check-now")
            self.assertEqual(net.call_count, 1)
            self.assertEqual(net.call_args[0][1], "Skald/2.2.0")
        self.assertEqual(code, 0)
        self.assertIn("up to date (latest release 2.2.0)", out)

    def test_run_daily_step_asks_only_from_an_installed_copy(self):
        ctx = mock.Mock(config={}, db_path=self.box.db)
        with mock.patch("skald.updates.check") as check:
            with mock.patch("skald.updates.deployed", return_value=False):
                self.assertEqual(updates.daily(ctx), 0)
            check.assert_not_called()
            with mock.patch("skald.updates.deployed", return_value=True):
                self.assertEqual(updates.daily(ctx), 0)
            check.assert_called_once()
            check.side_effect = RuntimeError("boom")
            with mock.patch("skald.updates.deployed", return_value=True):
                self.assertEqual(updates.daily(ctx), 0, "never fails the run")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Banner(unittest.TestCase):
    """js/updates.js's updateNotice, run by node with its two imports stubbed."""

    def run_js(self, cases: str) -> list:
        src = (ROOT / "skald" / "webapp" / "js" / "updates.js").read_text()
        src = re.sub(r'^import .*$', "", src, flags=re.M)
        src = "const h = () => null, ICON = {}, ME = {};\n" + src + "\n" + cases
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "updates.mjs"
            path.write_text(src)
            got = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(got.returncode, 0, got.stderr)
        return json.loads(got.stdout)

    def test_who_sees_it_and_dismissal_per_version(self):
        out = self.run_js("""
const u = { product: "Skald", current: "2.1.0", latest: "2.2.0", security: false,
  url: "https://github.com/spcaeo/skald/releases/tag/v2.2.0", notes: ["One.", "Two.", "Three."] };
console.log(JSON.stringify([
  updateNotice({ role: "owner", update: u }, null),
  updateNotice({ role: "admin", update: u }, "2.1.5"),
  updateNotice({ role: "viewer", update: u }, null),
  updateNotice({ role: "owner", update: null }, null),
  updateNotice({ role: "owner", update: u }, "2.2.0"),
  updateNotice({ role: "owner", update: { ...u, security: true, url: "javascript:alert(1)" } }, null),
]));""")
        owner, admin, viewer, none, dismissed, security = out
        self.assertEqual(owner["title"], "Skald 2.2.0 is available")
        self.assertEqual(owner["notes"], ["One.", "Two."])
        self.assertFalse(owner["security"])
        self.assertIsNotNone(admin, "dismissing an older version does not hide a newer one")
        self.assertIsNone(viewer)
        self.assertIsNone(none)
        self.assertIsNone(dismissed)
        self.assertTrue(security["security"])
        self.assertIn("security release", security["words"])
        self.assertIsNone(security["url"], "only a GitHub link is drawn")

    def test_wired_into_the_page(self):
        main = (ROOT / "skald" / "webapp" / "js" / "main.js").read_text()
        access = (ROOT / "skald" / "webapp" / "js" / "access.js").read_text()
        self.assertIn('import { updateBanner } from "./updates.js";', main)
        self.assertIn("updateBanner()", main)
        self.assertIn("ME.update = r.update || null;", access)


class Workflow(unittest.TestCase):
    def test_docker_tags_major_minor_patch_and_latest(self):
        path = ROOT / "public" / ".github" / "workflows" / "docker.yml"
        if not path.exists():                      # the public copy: the overlay is at the root
            path = ROOT / ".github" / "workflows" / "docker.yml"
        text = path.read_text()
        for tag in ("type=semver,pattern={{version}}", "type=semver,pattern={{major}}.{{minor}}",
                    "type=semver,pattern={{major}}\n",
                    "type=raw,value=latest,enable=${{ startsWith(github.ref, 'refs/tags/v') }}"):
            self.assertIn(tag, text)
        self.assertRegex(text, r"docker/metadata-action@[0-9a-f]{40} # v\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
