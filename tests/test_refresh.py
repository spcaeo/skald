"""The dashboard's Refresh now button and its local helper."""
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import cli, dashboard  # noqa: E402
from skald.refresh_server import (  # noqa: E402
    Runner, allowed_origins, back_to, install_sites, make_handler, same_origin)

from support import Sandbox  # noqa: E402


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


WHOLE = ["py", "bin/skald", "--config", "c.yml", "live"]
TWO = {"a.example": "a.example", "b.example": "b.example"}


class Recorder:
    """A fake subprocess.run that keeps every command it was given."""

    def __init__(self, code=0):
        self.commands, self.code = [], code

    def __call__(self, command, **k):
        self.commands.append(list(command))
        return subprocess.CompletedProcess(command, self.code)


class OneSitePerPress(unittest.TestCase):
    """A multi-site install counts the pressed page's site only."""

    def test_known_site_runs_alone(self):
        run = Recorder()
        r = Runner(WHOLE, ".", run=run, sites=lambda: TWO)
        self.assertEqual(r.refresh(site="b.example"), "ran")
        self.assertEqual(run.commands,
                         [["py", "bin/skald", "--config", "c.yml", "--site", "b.example", "live"]])

    def test_unknown_site_never_runs(self):
        run = Recorder()
        r = Runner(WHOLE, ".", run=run, sites=lambda: TWO)
        for bad in ("zz.example", "", "b.example --all"):
            self.assertEqual(r.refresh(site=bad), "unknown", bad)
            self.assertEqual(r.refresh(force=True, site=bad), "unknown", bad)
        self.assertEqual(run.commands, [])

    def test_folder_maps_to_the_site_name(self):
        run = Recorder()
        r = Runner(WHOLE, ".", run=run, sites=lambda: {"shop-example": "Shop Example"})
        self.assertEqual(r.refresh(site="shop-example"), "ran")
        self.assertEqual(run.commands[0][4:6], ["--site", "Shop Example"])

    def test_one_site_install_keeps_the_whole_command(self):
        for sites in (None, lambda: {}):
            run = Recorder()
            r = Runner(WHOLE, ".", run=run, sites=sites)
            self.assertEqual(r.refresh(site="anything.example"), "ran")
            self.assertEqual(run.commands, [WHOLE])

    def test_gap_is_per_site(self):
        t = [100.0]
        run = Recorder()
        r = Runner(WHOLE, ".", gap=15, clock=lambda: t[0], run=run, sites=lambda: TWO)
        self.assertEqual(r.refresh(site="a.example"), "ran")
        t[0] += 5
        self.assertEqual(r.refresh(site="a.example"), "recent")
        self.assertEqual(r.refresh(site="b.example"), "ran", "A's press must not hold B back")
        self.assertEqual(r.refresh(force=True, site="a.example"), "ran", "a change still runs")
        t[0] += 16
        self.assertEqual(r.refresh(site="b.example"), "ran")
        self.assertEqual([c[5] for c in run.commands],
                         ["a.example", "b.example", "a.example", "b.example"])

    def test_never_two_runs_at_once(self):
        run = Recorder()
        r = Runner(WHOLE, ".", run=run, sites=lambda: TWO)
        r.lock.acquire()                         # a run for a.example is going
        try:
            self.assertEqual(r.refresh(site="b.example"), "busy")
        finally:
            r.lock.release()
        self.assertEqual(run.commands, [])

    def test_the_list_is_read_on_every_press(self):
        listed = dict(TWO)
        r = Runner(WHOLE, ".", run=Recorder(), sites=lambda: listed)
        self.assertEqual(r.refresh(site="c.example"), "unknown")
        listed["c.example"] = "c.example"        # added in Settings > Sites
        self.assertEqual(r.refresh(site="c.example"), "ran")


class InstallSites(unittest.TestCase):
    """install_sites() on real config files, and the per-site command they
    give accepted by skald itself."""

    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def config(self):
        return cli.load_config(self.box.config)

    def test_one_site_config_is_empty(self):
        self.assertEqual(install_sites(self.config(), self.box.config), {})
        self.assertEqual(install_sites({}, None), {})

    def test_two_sites_and_a_broken_list(self):
        (self.box.root / "shop.yml").write_text(
            "site:\n  name: shop.example\n  hosts: [shop.example]\n")
        self.box.config.write_text(self.box.config.read_text() + "sites:\n  - shop.yml\n")
        self.assertEqual(install_sites(self.config(), self.box.config),
                         {"example.com": "example.com", "shop.example": "shop.example"})
        (self.box.root / "shop.yml").unlink()   # a missing file: the old whole run
        self.assertEqual(install_sites(self.config(), self.box.config), {})

    def test_the_site_command_runs_that_site_only(self):
        (self.box.root / "shop.yml").write_text(
            "site:\n  name: shop.example\n  hosts: [shop.example]\n"
            "logs:\n  base: shop.log\n")
        self.box.config.write_text(self.box.config.read_text() + "sites:\n  - shop.yml\n")
        self.box.log([])
        self.box.log([], "shop.log")
        outputs = []

        def in_process(command, **k):            # skald's own main, no new process
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(command[2:])
            outputs.append(out.getvalue() + err.getvalue())
            return subprocess.CompletedProcess(command, code)

        r = Runner(["py", "bin/skald", "--config", str(self.box.config), "live"], self.box.root,
                   run=in_process, sites=lambda: install_sites(self.config(), self.box.config))
        self.assertEqual(r.refresh(site="shop.example"), "ran", outputs)
        self.assertIn("shop.example", outputs[0])
        self.assertNotIn("www/example.com/", outputs[0])


class Route(unittest.TestCase):
    """POST <page>/refresh: JSON for the web app's fetch, 303 for a form."""

    SAME = {"Sec-Fetch-Site": "same-origin"}
    JSON = {"Sec-Fetch-Site": "same-origin", "Accept": "application/json"}

    def post(self, path, headers, code=0, sites=lambda: TWO):
        run = Recorder(code)
        handler = make_handler(Runner(WHOLE, ".", run=run, sites=sites), set(), {})
        raw = (f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n"
               + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
               + "\r\n").encode()
        out = io.BytesIO()

        class Socket:
            def makefile(self, mode, *a, **k):
                return io.BytesIO(raw)

            def sendall(self, data):
                out.write(data)

        handler(Socket(), ("127.0.0.1", 5555), None)
        head, _, data = out.getvalue().partition(b"\r\n\r\n")
        status = int(head.split()[1])
        location = next((h.split(b": ", 1)[1].decode() for h in head.split(b"\r\n")
                         if h.lower().startswith(b"location:")), None)
        return status, (json.loads(data) if data.startswith(b"{") else None), location, run

    def test_json_answer(self):
        status, body, _, run = self.post("/traffic/b.example/refresh",
                                         {**self.JSON, "Accept": "application/json, */*"})
        self.assertEqual((status, body), (200, {"ok": True, "result": "ran",
                                                "site": "b.example"}))
        self.assertEqual(run.commands[0][4:6], ["--site", "b.example"])
        status, body, _, _ = self.post("/traffic/b.example/us-english/refresh", self.JSON)
        self.assertEqual(body["site"], "b.example")

    def test_json_failed_run(self):
        status, body, _, _ = self.post("/traffic/a.example/refresh", self.JSON, code=2)
        self.assertEqual((status, body), (200, {"ok": False, "result": "failed",
                                                "site": "a.example"}))

    def test_unknown_site_is_404_and_runs_nothing(self):
        status, body, _, run = self.post("/traffic/zz.example/refresh", self.JSON)
        self.assertEqual((status, body["ok"], body["result"]), (404, False, "unknown"))
        status, body, _, run2 = self.post("/traffic/zz.example/refresh", self.SAME)
        self.assertEqual((status, body), (404, None))
        self.assertEqual(run.commands + run2.commands, [])

    def test_form_post_still_goes_back_to_the_page(self):
        status, body, location, run = self.post("/traffic/a.example/us-english/refresh",
                                                self.SAME)
        self.assertEqual((status, body, location), (303, None, "/traffic/a.example/us-english/"))
        self.assertEqual(len(run.commands), 1)

    def test_other_origin_refused_either_way(self):
        for extra in ({}, {"Accept": "application/json"}):
            status, body, _, run = self.post("/traffic/a.example/refresh",
                                             {"Sec-Fetch-Site": "cross-site", **extra})
            self.assertEqual(status, 403)
            self.assertEqual(run.commands, [])
            self.assertEqual(body is not None, bool(extra))


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
