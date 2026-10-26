"""The web app's files: what install() writes, and what the app may not do.

The app runs behind a Content-Security-Policy that allows script, styles and
fetches from the same origin only. These tests keep it that way: no inline
script, no address outside the page's own folder, no font, and nothing in
the app that could carry a visitor's address or user agent.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import webapp  # noqa: E402
from support import Sandbox  # noqa: E402
from test_views import KEYS, VIEWS, mixed_day  # noqa: E402

APP = Path(webapp.__file__).resolve().parent


def sources():
    return [p for p in APP.rglob("*") if p.suffix in (".js", ".css", ".html")]


class Install(unittest.TestCase):
    def test_shared_files_and_one_shell_per_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            written = webapp.install(out, ["example.com", "other site"])
            self.assertTrue((out / "_app" / "app.css").is_file())
            self.assertTrue((out / "_app" / "js" / "main.js").is_file())
            self.assertTrue((out / "_app" / "js" / "tabs" / "overview.js").is_file())
            for name in ("example.com", "other-site"):
                shell = (out / name / "index.html").read_text()
                self.assertIn('src="../_app/js/main.js?v=', shell)
            self.assertFalse(any(p.suffix == ".py" for p in written))

    def test_the_shell_asks_for_this_release_s_assets(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(webapp, "_version", return_value="abc1234"):
            out = Path(tmp)
            webapp.install(out, ["example.com"])
            shell = (out / "example.com" / "index.html").read_text()
            for asset in ("app.css", "features.css", "js/main.js"):
                self.assertIn(f"../_app/{asset}?v=abc1234", shell)

    def test_a_file_left_by_an_older_version_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            stale = out / "_app" / "js" / "gone.js"
            stale.parent.mkdir(parents=True)
            stale.write_text("old")
            webapp.install(out, ["example.com"])
            self.assertFalse(stale.exists())

    def test_vendored_components_ship_with_every_file_they_import(self):
        # spcaeo/ui (vendor/spcaeo-ui/VERSION.md): upstream's core files were .mjs, which
        # install() would not copy; every import in the installed app must find its file.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            webapp.install(out, ["example.com"])
            app = out / "_app"
            for rel in ("vendor/spcaeo-ui/folder-tabs/vanilla/folder-tabs.js", "vendor/spcaeo-ui/data-grid/vanilla/data-grid.js",
                        "vendor/spcaeo-ui/data-grid/core/url-state.js", "vendor/spcaeo-ui/spcaeo-ui-skald.css", "js/grid.js", "js/foldertabs.js"):
                self.assertTrue((app / rel).is_file(), rel)
            shell = (out / "example.com" / "index.html").read_text()
            for css in ("folder-tabs/folder-tabs.css", "data-grid/data-grid.css", "spcaeo-ui-skald.css"):
                self.assertIn(f'href="../_app/vendor/spcaeo-ui/{css}?v=', shell)
            for js in app.rglob("*.js"):
                # Static imports (a statement's line starts with import, export or the "}" of a long list) and import("…").
                code = js.read_text()
                specs = re.findall(r"""^\s*(?:import|export|\})[^\n;]*?\bfrom\s*["'](\.{1,2}/[^"']+)["']""", code, re.M)
                specs += re.findall(r"""^\s*import\s*["'](\.{1,2}/[^"']+)["']""", code, re.M)
                specs += re.findall(r"""\bimport\(\s*["'](\.{1,2}/[^"']+)["']\s*\)""", code)
                for spec in specs:
                    self.assertTrue((js.parent / spec.split("?", 1)[0]).resolve().is_file(), f"{js.relative_to(app)} imports {spec}, which is not installed")
            self.assertFalse(list(app.rglob("*.mjs")))

    def test_every_import_carries_the_version(self):
        # The code is kept a year by the browser (DEPLOY.md): an import without the
        # version would be a second copy of the module, or an old one after a release.
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(webapp, "_version", return_value="abc1234"):
            out = Path(tmp)
            webapp.install(out, ["example.com"])
            seen = 0
            for js in (out / "_app").rglob("*.js"):
                code = js.read_text()
                specs = re.findall(r"""^\s*(?:import|export|\})[^\n;]*?\bfrom\s*["'](\.{1,2}/[^"']+)["']""", code, re.M)
                specs += re.findall(r"""^\s*import\s*["'](\.{1,2}/[^"']+)["']""", code, re.M)
                specs += re.findall(r"""\bimport\(\s*["'](\.{1,2}/[^"']+)["']\s*\)""", code)
                for spec in specs:
                    seen += 1
                    self.assertTrue(spec.endswith(".js?v=abc1234"), f"{js.name} imports {spec}")
            self.assertGreater(seen, 500)
            # The sources themselves stay plain: node and the JS tests import them as they are.
            self.assertNotIn("?v=", (APP / "js" / "main.js").read_text())

    def test_the_version_follows_the_code(self):
        webapp._version.cache_clear()
        try:
            first = webapp._version()
            self.assertRegex(first, r"^[0-9a-f]{12}$")
            from unittest import mock
            real = Path.read_bytes
            changed = lambda p: real(p) + (b"//x" if p.name == "main.js" else b"")  # noqa: E731
            webapp._version.cache_clear()
            with mock.patch.object(Path, "read_bytes", changed):
                self.assertNotEqual(webapp._version(), first)
        finally:
            webapp._version.cache_clear()

    def test_the_shell_preloads_main_js_whole_graph(self):
        # One round of requests for the code instead of one per level of imports (seven).
        from unittest import mock
        graph = webapp.static_graph()
        self.assertGreater(len(graph), 150)
        self.assertIn("js/data.js", graph)
        self.assertIn("js/lazy.js", graph)
        self.assertNotIn("js/main.js", graph)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(webapp, "_version", return_value="abc1234"):
            out = Path(tmp)
            webapp.install(out, ["example.com"])
            shell = (out / "example.com" / "index.html").read_text()
            links = re.findall(r'<link rel="modulepreload" href="\.\./_app/([^"?]+)\?v=abc1234">', shell)
            self.assertEqual(links, list(graph))
            self.assertLess(shell.index("modulepreload"), shell.index('<script type="module"'))
            # Closed: every static import of a preloaded module is preloaded too.
            have = set(links) | {"js/main.js"}
            for rel in have:
                code = (out / "_app" / rel).read_text()
                for spec in re.findall(r"""^\s*(?:import|export|\})[^\n;]*?\bfrom\s*["'](\.{1,2}/[^"'?]+)""", code, re.M):
                    dep = os.path.normpath(os.path.join(os.path.dirname(rel), spec))
                    self.assertIn(dep, have, f"{rel} imports {spec}, not preloaded")

    def test_an_unchanged_file_is_not_written_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            webapp.install(out, ["example.com"])
            main = out / "_app" / "js" / "main.js"
            self.assertTrue((out / "_app" / "js" / "main.js.gz").is_file())
            inode = main.stat().st_ino
            webapp.install(out, ["example.com"])
            self.assertEqual(main.stat().st_ino, inode, "rewritten though nothing changed")
            self.assertTrue((out / "_app" / "js" / "main.js.gz").is_file(), "the copy was removed")

    def test_without_script_the_shell_sends_the_reader_to_the_static_page(self):
        shell = (APP / "index.html").read_text()
        self.assertRegex(shell, r'<noscript><meta http-equiv="refresh" content="0;url=classic.html"></noscript>')


class SameOriginOnly(unittest.TestCase):
    def test_no_inline_script_and_no_outside_address(self):
        for path in sources():
            text = path.read_text()
            if path.suffix == ".html":
                for tag in re.findall(r"<script[^>]*>", text):
                    self.assertIn("src=", tag, f"inline script in {path.name}")
                self.assertNotRegex(text, r"(?:src|href)=\"https?://", path.name)
            self.assertNotRegex(text, r"@import|url\(\s*['\"]?https?:", path.name)
            self.assertNotIn("fonts.googleapis", text, path.name)

    def test_fetches_stay_beside_the_page(self):
        for path in APP.rglob("*.js"):
            for call in re.findall(r"fetch\(([^,)]+)", path.read_text()):
                self.assertNotRegex(call, r"https?:|//", f"{path.name}: {call}")

    def test_robots_and_referrer_metas(self):
        shell = (APP / "index.html").read_text()
        self.assertIn('content="noindex, nofollow, noarchive"', shell)
        self.assertIn('name="referrer" content="no-referrer"', shell)


class Rendered(unittest.TestCase):
    """`dashboard.app: true`: the shell at the site's address, the static
    page beside it, and the figures as data/app.json for the site and each view."""

    def setUp(self):
        self.box = Sandbox(views=VIEWS)
        text = self.box.config.read_text().replace("  app: false\n", "  app: true\n")
        self.box.config.write_text(text)
        self.box.log(mixed_day())
        code, _, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertEqual(code, 0, err)
        code, _, err = self.box.run("--today", "2026-10-07", "dashboard")
        self.assertEqual(code, 0, err)
        self.site = self.box.root / "www" / "example.com"

    def tearDown(self):
        self.box.close()

    def data(self, *view):
        return json.loads(self.site.joinpath(*view, "data", "app.json").read_text())

    def test_shell_static_page_and_shared_files(self):
        self.assertIn("../_app/js/main.js", (self.site / "index.html").read_text())
        self.assertIn("<h1>", (self.site / "classic.html").read_text())
        self.assertTrue((self.site.parent / "_app" / "js" / "main.js").is_file())

    def test_a_verified_day_carries_its_figures(self):
        day = next(d for d in self.data()["days"] if d["day"] == "2026-10-06")
        self.assertEqual(day["state"], "ok")
        self.assertEqual(sum(day["hits"].values()), day["requests"])
        self.assertEqual(day["readers"], sum(day["by"]["country"].values()))
        for key in KEYS:
            self.assertEqual(self.data(key)["site"], "example.com")

    def test_each_journey_step_carries_its_offset(self):
        # `at` comes from the journey store (visits.py): seconds since the
        # visit's first request, bucketed, one per trail step.
        journeys = self.data()["journeys"]
        self.assertTrue(journeys)
        for j in journeys:
            at = [step["at"] for step in j["trail"]]
            self.assertTrue(all(isinstance(a, int) for a in at), j)
            self.assertEqual(at[0], 0, j)
            self.assertEqual(at, sorted(at), j)
            self.assertLessEqual(at[-1], j["seconds"], j)  # buckets round down

    def test_no_address_or_user_agent_in_the_data(self):
        for view in ((), *[(k,) for k in KEYS]):
            text = self.site.joinpath(*view, "data", "app.json").read_text()
            self.assertNotRegex(text, r"203\.0\.113|198\.51\.100|Mozilla|curl/")



class AppByDefault(unittest.TestCase):
    """A config without dashboard.app gets the web app (2.2.2): installs made
    from an older config.example.yml have no such key."""

    def test_no_key_means_the_app(self):
        box = Sandbox()
        try:
            box.config.write_text(box.config.read_text().replace("  app: false\n", ""))
            box.log(mixed_day())
            self.assertEqual(box.run("--today", "2026-10-07", "collect")[0], 0)
            code, _, err = box.run("--today", "2026-10-07", "dashboard")
            self.assertEqual(code, 0, err)
            site = box.root / "www" / "example.com"
            self.assertTrue((site / "classic.html").exists(), "the plain page moves beside the app")
            self.assertTrue((site / "data" / "app.json").exists())
        finally:
            box.close()

if __name__ == "__main__":
    unittest.main()
