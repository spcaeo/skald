"""The welcome line (2.44.0): /me says `welcome: true` once, on a new person's
first load; accounts made before 2.44.0 never see it. And js/welcome.js's
welcomeNotice, run by node."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent

from auth_support import A, Server  # noqa: E402
from skald import accounts  # noqa: E402
from skald.accounts import users  # noqa: E402


class FirstLoad(Server):
    def me(self, cookie):
        return self.call("GET", f"/traffic/{A}/me", cookie=cookie).json

    def test_once_then_never(self):
        cookie = self.login().cookie
        self.assertTrue(self.me(cookie)["welcome"])
        self.assertFalse(self.me(cookie)["welcome"], "a reload: the tab keeps it, not /me")
        self.assertFalse(self.me(self.login().cookie)["welcome"], "a second sign-in")

    def test_an_account_from_before_has_no_welcome(self):
        db = self.db()
        try:
            uid = users.find_user(db, email="owner@example.com")["id"]
            db.execute("DELETE FROM settings WHERE scope = ? AND key = 'welcome'", (f"user:{uid}",))
            db.commit()
        finally:
            db.close()
        self.assertFalse(self.me(self.login().cookie)["welcome"])

    def test_each_person_their_own(self):
        self.assertTrue(self.me(self.login().cookie)["welcome"])
        self.assertTrue(self.me(self.login("viewer@example.com").cookie)["welcome"])

    def test_no_session_no_welcome(self):
        got = self.call("GET", f"/traffic/{A}/me")
        self.assertFalse((got.json or {}).get("welcome"))


class TakeOnce(unittest.TestCase):
    def test_take_welcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = accounts.connect(Path(tmp) / "accounts.sqlite")
            try:
                user = accounts.create_user(db, "new@example.com", "New Person")
                self.assertTrue(users.take_welcome(db, user["id"]))
                self.assertFalse(users.take_welcome(db, user["id"]))
                self.assertFalse(users.take_welcome(db, 999))
            finally:
                db.close()


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Words(unittest.TestCase):
    def run_js(self, cases: str) -> list:
        src = (ROOT / "skald" / "webapp" / "js" / "welcome.js").read_text()
        src = re.sub(r'^import .*$', "", src, flags=re.M)
        src = "const h = () => null, ICON = {}, ME = {};\n" + src + "\n" + cases
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "welcome.mjs"
            path.write_text(src)
            got = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(got.returncode, 0, got.stderr)
        return json.loads(got.stdout)

    def test_words(self):
        out = self.run_js("""
console.log(JSON.stringify([
  welcomeNotice({ welcome: true, name: "Sam Example", org: "Example Co" }, null),
  welcomeNotice({ welcome: true, name: "", org: null }, null),
  welcomeNotice({ welcome: false, name: "Sam" }, "1"),
  welcomeNotice({ welcome: false, name: "Sam" }, null),
]));""")
        self.assertEqual(out[0]["title"], "Welcome to Skald, Sam.")
        self.assertIn("Example Co's sites", out[0]["words"])
        self.assertEqual(out[1]["title"], "Welcome to Skald.")
        self.assertNotIn("sites", out[1]["words"])
        self.assertIsNotNone(out[2], "kept by the tab until closed")
        self.assertIsNone(out[3])


if __name__ == "__main__":
    unittest.main()
