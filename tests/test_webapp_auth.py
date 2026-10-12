"""The sign-in pages (webapp/auth/) and the accounts pages in Settings.

The sign-in pages are served by the helper under /traffic-auth/ with the
dashboard's Content-Security-Policy (script and styles from the same origin
only), so: no inline script or handler, nothing fetched from elsewhere, and a
password only ever in a POST body. Team and Your account are Settings pages,
shown only when /me says the server runs with accounts.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import webapp  # noqa: E402

APP = Path(webapp.__file__).resolve().parent
AUTH = APP / "auth"
PAGES = ("login", "forgot", "reset", "invite")


class SignInPages(unittest.TestCase):
    def test_the_four_pages_and_their_shared_files_exist(self):
        for name in PAGES:
            self.assertTrue((AUTH / f"{name}.html").is_file(), name)
        self.assertTrue((AUTH / "auth.js").is_file())
        self.assertTrue((AUTH / "auth.css").is_file())

    def test_no_inline_script_no_handler_and_no_outside_address(self):
        for name in PAGES:
            text = (AUTH / f"{name}.html").read_text(encoding="utf-8")
            for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", text, re.S):
                self.assertIn("src=", attrs, f"inline script in {name}.html")
                self.assertEqual(body.strip(), "", f"script body in {name}.html")
            self.assertNotRegex(text, r"\son[a-z]+\s*=", f"inline handler in {name}.html")
            self.assertNotRegex(text, r"javascript:", name)
            for url in re.findall(r"(?:src|href|action)=\"([^\"]*)\"", text):
                self.assertFalse(re.match(r"(?:https?:)?//", url), f"{name}.html: {url}")
            self.assertIn('src="/traffic-auth/auth.js"', text)
            self.assertIn('href="/traffic-auth/auth.css"', text)
            self.assertIn(f'data-page="{name}"', text)
            self.assertIn('name="robots" content="noindex, nofollow, noarchive"', text)
            self.assertIn('name="referrer" content="no-referrer"', text)
        css = (AUTH / "auth.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"@import|url\(\s*['\"]?(?:https?:)?//")

    def test_a_password_form_never_falls_back_to_a_get(self):
        # Without script a form would submit itself; as a GET the password would land in the address.
        for name in PAGES:
            text = (AUTH / f"{name}.html").read_text(encoding="utf-8")
            for form in re.findall(r"<form[^>]*>", text):
                self.assertIn('method="post"', form, name)

    def test_the_script_keeps_passwords_out_of_storage_and_addresses(self):
        js = (AUTH / "auth.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"(?:localStorage|sessionStorage)\.setItem|indexedDB|document\.cookie")
        for call in re.findall(r"fetch\(([^,)]+)", js):
            self.assertNotRegex(call, r"https?:|//", call)
            self.assertNotIn("password", call)
        self.assertIn('"/traffic/"', js)

    def test_next_is_checked_before_the_browser_goes_there(self):
        js = (AUTH / "auth.js").read_text(encoding="utf-8")
        self.assertRegex(js, r"function safeNext")
        self.assertIn('startsWith("//")', js)
        self.assertIn('pathname.startsWith("/traffic/")', js)
        self.assertNotRegex(js, r"location\.(?:replace|assign|href\s*=)\((?!safeNext)", "every redirect goes through safeNext")


class SettingsPages(unittest.TestCase):
    def test_team_and_account_are_settings_tabs_with_a_render(self):
        state = (APP / "js" / "state.js").read_text(encoding="utf-8")
        self.assertIn('["settings/team", "Team"]', state)
        self.assertIn('["settings/account", "Your account"]', state)
        index = (APP / "js" / "tabs" / "index.js").read_text(encoding="utf-8")
        self.assertIn('"settings/team": team', index)
        self.assertIn('"settings/account": account', index)

    def test_every_post_can_carry_the_csrf_value(self):
        ipm = (APP / "js" / "tabs" / "ipmanager.js").read_text(encoding="utf-8")
        self.assertIn('"X-Skald-CSRF"', ipm)
        access = (APP / "js" / "access.js").read_text(encoding="utf-8")
        self.assertIn("setCsrf(r.csrf)", access)


class Sizes(unittest.TestCase):
    def test_every_app_file_stays_under_1000_lines(self):
        for path in APP.rglob("*"):
            if path.suffix in (".js", ".css", ".html"):
                lines = path.read_text(encoding="utf-8").count("\n")
                self.assertLess(lines, 1000, path.name)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Parses(unittest.TestCase):
    def test_every_js_file_parses(self):
        # As .mjs, so any node version reads them as the ES modules they are.
        with tempfile.TemporaryDirectory() as tmp:
            for path in sorted(APP.rglob("*.js")):
                copy = Path(tmp) / (str(path.relative_to(APP)).replace("/", "__") + ".mjs")
                shutil.copyfile(path, copy)
                got = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
                self.assertEqual(got.returncode, 0, f"{path.relative_to(APP)}: {got.stderr}")


if __name__ == "__main__":
    unittest.main()
