"""Security alerts to the people on a site (security_notify.py, security_api.py): who gets
one (owners and admins by default, a viewer who opts in, never an unconfirmed or disabled
account), once per item and a reminder while it stays open, the daily-mail digest, the test
send, the link straight to the item, and every send in the audit log without its content."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import accounts, security_api, security_notify as sn  # noqa: E402
from skald.accounts import orgs, sessions, users  # noqa: E402

SITE = "example.com"
NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
CONFIG = {"dashboard": {"url": "https://stats.example.com/traffic/example.com/"},
          "mail": {"host": "smtp.example.com", "port": 587, "from": "skald@example.com",
                   "to": ["owner@example.com"]},
          "access": {"mode": "sessions"}}
EXPOSURE = {"rules": {"exposure_rule": 2}, "exposure": {"rows": [{"host": "example.com", "path": "/.env.production", "status": "200",
                                   "size": 1873, "verdict": "possible", "category": "secrets"}]}}
STACK = {"matches": [{"advisory": "php-2026-10-21", "product": "php", "host": "media.example.com",
                      "version": "8.3.10", "state": "update_needed"},
                     {"advisory": "php-2026-10-21", "product": "php", "host": "example.com",
                      "version": "8.4.30", "state": "fixed"}]}


class Mailbox:
    def __init__(self):
        self.sent = []

    def __call__(self, msg, cfg):
        self.sent.append((cfg["to"][0], msg["Subject"], msg.get_body(("plain",)).get_content()))


class Team(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = accounts.connect(Path(self.tmp.name) / "accounts.sqlite")
        org = orgs.create_org(self.db, "Example", "test")
        self.org = org["id"]
        orgs.assign_site(self.db, SITE, self.org, "test")
        self.ids = {}
        for email, role, pw, off in (("owner@example.com", "owner", "Long-test-pass-41", False),
                                     ("admin@example.com", "admin", "Long-test-pass-42", False),
                                     ("viewer@example.com", "viewer", "Long-test-pass-43", False),
                                     ("invited@example.com", "admin", None, False),
                                     ("gone@example.com", "admin", "Long-test-pass-44", True)):
            u = users.create_user(self.db, email, email.split("@")[0], password=pw, actor="test")
            users.add_member(self.db, self.org, u["id"], role, "test")
            if off:
                users.disable_user(self.db, u["id"], "test")
            self.ids[email] = u["id"]
        self.found = sn.items(CONFIG, SITE, [EXPOSURE], STACK)
        self.box = Mailbox()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def who(self):
        return sorted(r["email"] for r in sn.recipients(self.db, SITE))

    def test_who_gets_them(self):
        self.assertEqual(self.who(), ["admin@example.com", "owner@example.com"],
                         "owners and admins by default; never unconfirmed or disabled")
        sn.set_prefs(self.db, self.ids["viewer@example.com"], SITE, True, "daily")
        sn.set_prefs(self.db, self.ids["admin@example.com"], SITE, False, "now")
        self.assertEqual(self.who(), ["owner@example.com", "viewer@example.com"], "a viewer opts in")
        sn.set_prefs(self.db, self.ids["invited@example.com"], SITE, True, "now")
        self.assertNotIn("invited@example.com", self.who(), "an account never confirmed gets none")
        self.assertEqual(sn.recipients(self.db, "other.example.com"), [])

    def test_the_items_and_their_links(self):
        kinds = [(i["kind"], i["item"][:1]) for i in self.found]
        self.assertEqual(kinds, [("exposure", "x"), ("advisory", "a")], "a fixed version is no item")
        it = self.found[0]
        self.assertRegex(it["item"], r"^x[0-9a-f]{12}$")
        self.assertEqual(sn.link(CONFIG, "exposure", it["item"]),
                         f"https://stats.example.com/traffic/example.com/#threats/exposed?item={it['item']}")
        self.assertEqual(sn.link(CONFIG, "advisory", "a1"), "https://stats.example.com/traffic/example.com/#threats/stack?item=a1")
        self.assertEqual(sn.item_id("exposure", SITE, "example.com", "/.env.production"), it["item"],
                         "the same id every run")
        self.assertNotIn("example.com", it["item"])

    def test_once_per_item_then_a_reminder(self):
        cfg = {**CONFIG, "mail": {**CONFIG["mail"], "to": []}}
        got = sn.run(self.db, cfg, SITE, self.found, NOW, "now", self.box)
        self.assertEqual(sorted((e, h) for e, _, h in got),
                         [("admin@example.com", "first")] * 2 + [("owner@example.com", "first")] * 2)
        self.assertEqual(len(self.box.sent), 4, "right away: one mail per item")
        to, subject, text = self.box.sent[0]
        self.assertIn("What to do:", text)
        self.assertIn("#threats/", text)
        self.assertIn(SITE, subject)
        self.assertEqual(sn.run(self.db, cfg, SITE, self.found, NOW + timedelta(hours=5), "now", self.box), [],
                         "once per item")
        later = sn.run(self.db, cfg, SITE, self.found, NOW + timedelta(days=3), "now", self.box)
        self.assertEqual({h for _, _, h in later}, {"reminder"}, "still open after 3 days")
        self.assertIn("Reminder:", self.box.sent[-1][2])
        self.assertEqual(sn.run(self.db, cfg, SITE, [], NOW + timedelta(days=9), "now", self.box), [],
                         "a closed item is never mailed")
        audit = self.db.execute("SELECT actor, action, target, detail FROM audit WHERE action = "
                                "'security.alert.sent'").fetchall()
        self.assertEqual(len(audit), 8, "4 first sends, 4 reminders")
        self.assertTrue(all(r[0] == "skald" and "@example.com" in r[2] for r in audit))
        self.assertFalse(any(".env" in r[3] or "8.3.10" in r[3] for r in audit), "never the content")

    def test_the_site_alert_mail_is_not_doubled(self):
        cfg = {**CONFIG, "alerts": {"enabled": True, "mail": True}}
        got = sn.run(self.db, cfg, SITE, self.found, NOW, "now", self.box)
        owner = [(i, h) for e, i, h in got if e == "owner@example.com"]
        self.assertEqual([i[:1] for i, _ in owner], ["a"], "the owner gets the exposure in the site's alert mail")

    def test_the_daily_mail(self):
        cfg = {**CONFIG, "mail": {**CONFIG["mail"], "to": []}}
        sn.set_prefs(self.db, self.ids["owner@example.com"], SITE, True, "daily")
        now = sn.run(self.db, cfg, SITE, self.found, NOW, "now", self.box)
        self.assertNotIn("owner@example.com", {e for e, _, _ in now})
        before = len(self.box.sent)
        daily = sn.run(self.db, cfg, SITE, self.found, NOW, "daily", self.box)
        self.assertEqual(sorted(h for e, _, h in daily if e == "owner@example.com"), ["daily", "daily"])
        self.assertEqual(len(self.box.sent), before + 1, "one mail with both items")
        self.assertIn("2 items", self.box.sent[-1][1])
        self.assertEqual(sn.run(self.db, cfg, SITE, self.found, NOW + timedelta(hours=1), "daily", self.box), [])

    def test_the_test_send(self):
        user = {"user_id": self.ids["admin@example.com"], "email": "admin@example.com"}
        self.assertIsNone(sn.test_send(self.db, CONFIG, SITE, user, self.org, NOW, self.box))
        self.assertEqual(self.box.sent[-1][0], "admin@example.com")
        self.assertIn("test", self.box.sent[-1][1])
        self.assertIn("#threats/exposed?item=x", self.box.sent[-1][2])
        row = self.db.execute("SELECT target, detail FROM audit WHERE action = 'security.alert.sent' "
                              "ORDER BY id DESC").fetchone()
        self.assertEqual(row[0], "admin@example.com")
        self.assertTrue(row[1].endswith("test test"))
        cfg = {**CONFIG, "mail": {}}
        self.assertIsNotNone(sn.test_send(self.db, cfg, SITE, user, self.org, NOW, self.box), "no mail server: said")


class Fake:
    def __init__(self, path, cookie, csrf="", body=None):
        raw = json.dumps(body).encode() if body is not None else b""
        self.path = path
        self.headers = {"Cookie": f"{sessions.COOKIE}={cookie}", "X-Skald-CSRF": csrf,
                        "Content-Type": "application/json", "Content-Length": str(len(raw))}
        self.rfile = io.BytesIO(raw)
        self.sent = None

    def send_response(self, code):
        self.code = code

    def send_header(self, *a):
        pass

    def end_headers(self):
        pass

    @property
    def wfile(self):
        return self

    def write(self, data):
        self.sent = (self.code, json.loads(data))


class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = accounts.connect(self.dir / "accounts.sqlite")
        org = orgs.create_org(self.db, "Example", "test")
        orgs.assign_site(self.db, SITE, org["id"], "test")
        self.cookies = {}
        for email, role in (("admin@example.com", "admin"), ("viewer@example.com", "viewer")):
            u = users.create_user(self.db, email, "x", password="pw-long-enough-1", actor="test")
            users.add_member(self.db, org["id"], u["id"], role, "test")
            self.cookies[role] = sessions.start(self.db, u["id"], "", "test")
        self.db.close()
        self.box = Mailbox()

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, act, role, body=None):
        cookie, csrf = self.cookies[role]
        h = Fake(f"/traffic/{SITE}/settings/{act}", cookie, csrf, body)
        security_api.handle(h, body is not None, CONFIG, self.dir, [], lambda *_: True, send=self.box)
        return h.sent

    def test_prefs_and_test_by_role(self):
        self.assertTrue(security_api.is_security(f"/traffic/{SITE}/settings/security-prefs"))
        code, got = self.ask("security-prefs", "viewer")
        self.assertEqual((code, got["alerts"], got["default"]), (200, False, True))
        code, got = self.ask("security-prefs", "viewer", {"alerts": True, "mode": "daily"})
        self.assertEqual((code, got["alerts"], got["mode"]), (200, True, "daily"))
        code, got = self.ask("security-test", "viewer", {})
        self.assertEqual(code, 403)
        code, got = self.ask("security-test", "admin", {})
        self.assertEqual((code, got["sent_to"]), (200, "admin@example.com"))
        for _ in range(2):
            self.ask("security-test", "admin", {})
        code, _ = self.ask("security-test", "admin", {})
        self.assertEqual(code, 429, "at most 3 test alerts in 10 minutes")


if __name__ == "__main__":
    unittest.main()
