"""A site's logo asked for the moment the site is added (2.25): site_logos.fetch_now on
first_page's thread (Settings > Sites and the Add a site wizard, sign-up), inline for
`skald site add`; sites.json rewritten so the switcher shows it at once; a failure noted,
never failing the add; and the site picker's retry for a site still showing its letter,
at most once a day. The site is a local test server; names are example.org / .example."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_site_logos as logos_t  # noqa: E402
import test_sites_admin as admin_t  # noqa: E402

from skald import first_page, site_logos, site_picker  # noqa: E402

SITE = "shop.example.org"
UTC = timezone.utc


class FetchNow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "live"
        self.out = Path(self.tmp.name) / "www"
        logos_t.FakeSite.routes = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), logos_t.FakeSite)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]
        self.config = {"site": {"name": SITE}}
        listed = [{"name": "main.example.org", "logo": {"url": None, "letter": "M"}},
                  {"name": SITE, "logo": {"url": None, "letter": "S"}}]
        for path in (self.out / "sites.json", self.out / SITE / "data" / "sites.json"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"schema_version": 1, "sites": listed, "current": None}))

    def fetcher(self):
        return site_logos.Fetcher(["127.0.0.1"], scheme="http", port=self.port, allow_private=True)

    def logos(self, path):
        return {s["name"]: s["logo"] for s in json.loads(path.read_text())["sites"]}

    def test_a_new_site_gets_its_logo_and_the_switcher_shows_it(self):
        logos_t.FakeSite.routes["/favicon.ico"] = (200, {"Content-Type": "image/x-icon"}, logos_t.ico(32))
        got = site_logos.fetch_now(self.config, SITE, self.base, self.out, fetcher=self.fetcher())
        self.assertTrue(got["ok"], got)
        for path in (self.out / "sites.json", self.out / SITE / "data" / "sites.json"):
            logos = self.logos(path)
            self.assertTrue(logos[SITE]["url"].startswith(f"{SITE}/logo?v="), path)
            self.assertEqual(logos["main.example.org"]["url"], None, "another site is untouched")
        self.assertIsNotNone(site_logos.chosen(self.config, SITE, self.base))

    def test_a_site_with_no_icon_keeps_its_letter_and_never_raises(self):
        got = site_logos.fetch_now(self.config, SITE, self.base, self.out, fetcher=self.fetcher())
        self.assertFalse(got["ok"])
        self.assertTrue(got["error"])
        self.assertIsNone(self.logos(self.out / "sites.json")[SITE]["url"])
        state = site_logos.load_state(site_logos.folder(self.base, SITE))
        self.assertTrue(state["checked_at"], "the try is kept: the picker waits a day")
        with mock.patch.object(site_logos, "check", side_effect=RuntimeError("boom")):
            self.assertEqual(site_logos.fetch_now(self.config, SITE, self.base, self.out),
                             {"ok": False, "error": "RuntimeError"})

    def test_a_letter_or_an_upload_is_never_asked(self):
        for source in ("letter", "upload"):
            cfg = {"site": {"name": SITE, "logo_source": source}}
            with mock.patch.object(site_logos, "check") as check:
                self.assertEqual(site_logos.fetch_now(cfg, SITE, self.base, self.out), {})
            check.assert_not_called()
        self.assertEqual(site_logos.fetch_now(self.config, SITE, None, self.out), {})


class Picker(unittest.TestCase):
    """retry_missing: a site still showing its letter, asked again at most once a day."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}}
        self.started = []
        site_logos._ASKING.clear()          # a test's spawned check never ran: none in flight
        # example.org is never asked (RFC 2606): here it stands for a real host name.
        real = site_logos.hosts_of
        hosts = mock.patch.object(site_logos, "hosts_of", side_effect=lambda c, s: [s] if s == SITE else real(c, s))
        hosts.start()
        self.addCleanup(hosts.stop)

    def spawn(self, fn):
        self.started.append(fn)

    def failed(self, hours_ago):
        at = datetime.now(UTC) - timedelta(hours=hours_ago)
        site_logos.save_state(site_logos.folder(self.base, SITE),
                              {"checked_at": at.isoformat(timespec="seconds"), "ok": False, "error": "none"})

    def retry(self, config=None):
        return site_logos.retry_missing(config or self.config, SITE, self.base, None, spawn=self.spawn)

    def test_never_asked_is_asked(self):
        self.assertTrue(self.retry())
        self.assertEqual(len(self.started), 1)

    def test_at_most_once_a_day(self):
        self.failed(2)
        self.assertFalse(self.retry(), "failed 2 hours ago: not again yet")
        self.failed(25)
        self.assertTrue(self.retry(), "failed a day ago: asked again")

    def test_one_check_at_a_time_and_then_free_again(self):
        self.assertTrue(self.retry())
        self.assertFalse(self.retry(), "the first is still running")
        with mock.patch.object(site_logos, "fetch_now", return_value={}) as fetch:
            self.started[0]()
        fetch.assert_called_once()
        self.assertTrue(self.retry(), "done: the next picker load may ask (still never checked)")

    def test_a_site_with_a_logo_a_letter_or_no_host_is_left_alone(self):
        self.assertFalse(self.retry({"site": {"name": SITE, "logo_source": "letter"}}))
        self.assertFalse(site_logos.retry_missing({"site": {"name": "shop.example"}}, "shop.example",
                                                  self.base, None, spawn=self.spawn),
                         "a reserved name: nothing to ask")
        site_logos.store_upload(self.base, SITE, logos_t.png(64, 64), "pat")
        self.assertFalse(self.retry({"site": {"name": SITE, "logo_source": "upload"}}))
        self.assertEqual(self.started, [])

    def test_the_picker_asks_for_each_site_without_a_logo(self):
        seen = []
        with mock.patch.object(site_logos, "retry_missing", side_effect=lambda c, n, b, o: seen.append(n)):
            got = site_picker.enrich([{"name": SITE}, {"name": "b.example.org"}], None, self.config, self.base)
        self.assertEqual(seen, [SITE, "b.example.org"])
        self.assertEqual([s["logo"]["url"] for s in got], [None, None], "this answer shows what is there now")


class FirstPage(unittest.TestCase):
    """first_page.start runs `before` (the logo) on its thread, then the build."""

    def test_before_runs_first_and_a_failure_never_stops_the_build(self):
        order = []
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        with mock.patch.object(first_page, "build", side_effect=lambda *a: order.append("build") or True):
            err = io.StringIO()
            with redirect_stderr(err):
                first_page.start(out, SITE, out / "config.yml", before=lambda: order.append("logo") or {"ok": True}).join(5)
                first_page.start(out, SITE, out / "config.yml", before=lambda: 1 / 0).join(5)
                first_page.start(out, SITE, out / "config.yml", before=lambda: {"ok": False, "error": "x"}).join(5)
        self.assertEqual(order[:2], ["logo", "build"])
        self.assertEqual(order.count("build"), 3, "the build runs every time")
        self.assertIn("a new site's logo: ZeroDivisionError", err.getvalue())
        self.assertIn("a new site's logo: none found yet", err.getvalue())
        self.assertNotIn("http", err.getvalue(), "never an address in the journal")
        self.assertIsNone(first_page.start(None, SITE, None), "nothing to do, nothing started")
        t = first_page.start(None, SITE, None, before=lambda: order.append("only the logo"))
        t.join(5)
        self.assertIn("only the logo", order)


class AddedInSettings(admin_t.Api):
    """Settings > Sites > Add (sites_api.add): the logo is asked on the new site's thread."""

    def test_add_asks_the_new_site_for_its_logo(self):
        seen = []
        with mock.patch.object(site_logos, "fetch_now", side_effect=lambda c, n, b, o: seen.append((n, b, o)) or {}):
            cookie, csrf = self.session("admin@example.com")
            got = self.post(admin_t.T + "sites/add", {"host": "Shop.Example.org"}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
            from skald.auth_api import drain
            drain(30)
        self.assertEqual([n for n, _, _ in seen], [SITE])
        self.assertEqual(seen[0][1], self.live, "into the logos folder beside the history")


for _name in [n for n in dir(admin_t.Api) if n.startswith("test_")]:
    setattr(AddedInSettings, _name, None)       # Api's own tests run in their own module


class AddedOnTheServer(admin_t.Cli):
    """`skald site add`: the logo is asked at once; a failure is said, never an error."""

    def test_site_add_asks_for_the_logo(self):
        code, out, err = self.run_ti("site", "add", "shop.example.com", "--org", self.org["slug"])
        self.assertEqual(code, 0, err)
        self.assertIn("logo: none yet", out, "a reserved name has no host to ask: said, not failed")
        state = site_logos.load_state(site_logos.folder(self.dir, "shop.example.com"))
        self.assertTrue(state.get("checked_at"))


for _name in [n for n in dir(admin_t.Cli) if n.startswith("test_")]:
    setattr(AddedOnTheServer, _name, None)


if __name__ == "__main__":
    unittest.main()
