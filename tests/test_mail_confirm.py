"""Shared SMTP abuse (security review 2, finding 9): recipients added from
the page get nothing but one confirm mail (at most one a day) until they
confirm; the From name and organisation names in subjects are cut to
letters, digits, spaces and . - '; the test mail goes only to the caller or a
confirmed recipient."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, Server  # noqa: E402

from skald import accounts, auth_api, mail_confirm, mailer  # noqa: E402
from skald import settings_store as store  # noqa: E402
from skald.accounts import mails  # noqa: E402

T = f"/traffic/{A}/"
SAME = {"Origin": "https://www.example.com"}


class Names(unittest.TestCase):
    def test_from_name_is_refused_on_save_unless_plain(self):
        self.assertEqual(store.validate("mail.from_name", "Acme Co. O'Neil-Smith"),
                         "Acme Co. O'Neil-Smith")
        for bad in ("PayPal <security@example.com>", "x" * 41, "Bank: verify now!",
                    "a/b", "line\nbreak"):
            with self.subTest(bad), self.assertRaises(store.Invalid):
                store.validate("mail.from_name", bad)

    def test_from_name_is_cut_on_send_too(self):
        got = mailer._sender("skald@example.com", "Evil <x@example.net>: " + "y" * 60)
        name = got.rsplit("<", 1)[0].strip().strip('"')
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9 .'-]{1,40}", name), got)
        self.assertNotIn("@example.net", got)

    def test_org_names_in_invite_subjects_are_cut(self):
        with mock.patch.object(mails, "mail_settings",
                               return_value={"prefix": "[Skald]", "from": "s@example.com",
                                             "to": ["a@example.com"]}):
            msg = mails.invite_mail({}, "a@example.com", "https://www.example.com/x",
                                    "Win <a href=x> $$$ prize: claim at evil.example/now", "viewer")
        subject = msg["Subject"].replace("[Skald] ", "")
        self.assertTrue(re.fullmatch(r"You are invited to [A-Za-z0-9 .'-]{1,40}", subject),
                        subject)


class Store(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.db = accounts.connect(self.dir / "accounts.sqlite")
        self.addCleanup(self.db.close)
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        accounts.assign_site(self.db, A, self.org["id"], "cli")
        self.config = {"site": {"name": A}, "history": {"db": str(self.dir / "history.sqlite")},
                       "mail": {"host": "smtp.example.com", "from": "skald@example.com",
                                "to": ["ops@example.com"]}}

    def test_one_confirm_mail_a_day_and_the_token_confirms(self):
        first = mail_confirm.request(self.db, self.org["id"], "new@example.com")
        self.assertTrue(first)
        self.assertIsNone(mail_confirm.request(self.db, self.org["id"], "new@example.com"))
        # Another organisation cannot mail the same address again that day.
        other = accounts.create_org(self.db, "Beta", "cli")
        self.assertIsNone(mail_confirm.request(self.db, other["id"], "new@example.com"))
        self.assertFalse(mail_confirm.is_confirmed(self.db, self.org["id"], "new@example.com"))
        self.assertIsNotNone(mail_confirm.confirm(self.db, first))
        self.assertTrue(mail_confirm.is_confirmed(self.db, self.org["id"], "new@example.com"))
        self.assertFalse(mail_confirm.is_confirmed(self.db, other["id"], "new@example.com"))
        self.assertIsNone(mail_confirm.confirm(self.db, first))        # used once
        self.assertIsNone(mail_confirm.confirm(self.db, "not-a-token"))
        rows = self.db.execute("SELECT * FROM mail_confirms").fetchall()
        self.assertNotIn("new@example.com", repr([tuple(r) for r in rows]))

    def test_the_daily_run_mails_only_confirmed_page_recipients(self):
        store.put(self.db, f"site:{A}", "mail.to",
                  ["ops@example.com", "new@example.com", "victim@example.org"], "1")
        got = store.apply(self.config, A, self.dir)
        self.assertEqual(got["mail"]["to"], ["ops@example.com"])      # config's own: kept
        mail_confirm.mark_confirmed(self.db, self.org["id"], "new@example.com")
        got = store.apply(self.config, A, self.dir)
        self.assertEqual(got["mail"]["to"], ["ops@example.com", "new@example.com"])

    def test_nobody_confirmed_is_withheld_not_sent(self):
        store.put(self.db, f"site:{A}", "mail.to", ["victim@example.org"], "1")
        got = store.apply(self.config, A, self.dir)
        self.assertEqual(got["mail"]["to"], [])
        with self.assertRaises(mailer.Withheld):
            mailer.settings(got)


class Page(Server):
    def save(self, body, email="owner@example.com"):
        cookie, csrf = self.session(email)
        return self.post(T + "settings/save", body, cookie, csrf)

    def test_saving_recipients_mails_one_confirm_link_each(self):
        self.mail_on()
        got = self.save({"mail.to": ["new@example.com", "other@example.com"]})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(sorted(got.json["mail_waiting"]),
                         ["new@example.com", "other@example.com"])
        auth_api.drain()
        self.assertEqual(sorted(to for to, _ in self.sent),
                         ["new@example.com", "other@example.com"])
        self.save({"mail.to": ["new@example.com"]})
        auth_api.drain()
        self.assertEqual(len(self.sent), 2)                 # not again the same day
        msg = dict(self.sent)["new@example.com"]
        link = re.search(r"https://\S+mail-confirm\?t=\S+", msg.get_body(("plain",))
                         .get_content()).group(0)
        path = link.split("example.com", 1)[1]
        page = self.call("GET", path)
        self.assertEqual(page.status, 200)
        db = self.db()
        try:
            self.assertFalse(mail_confirm.is_confirmed(db, self.alpha["id"], "new@example.com"))
        finally:
            db.close()
        token = path.split("t=", 1)[1]
        done = self.call("POST", "/traffic-auth/mail-confirm", headers={
            **SAME, "Content-Type": "application/x-www-form-urlencoded"},
            raw=f"t={token}".encode())
        self.assertEqual(done.status, 200)
        db = self.db()
        try:
            self.assertTrue(mail_confirm.is_confirmed(db, self.alpha["id"], "new@example.com"))
        finally:
            db.close()

    def test_no_mail_server_is_said_at_once_and_no_link_is_used_up(self):
        # 2.42 (the UX audit): with no mail server the dialog waited for good for a confirm
        # mail that could not go. The answer says what is missing, and no day's link is used.
        got = self.save({"mail.to": ["new@example.com"]})
        self.assertEqual(got.status, 200, got.json)
        self.assertFalse(got.json["mail_server"]["ready"])
        self.assertIn("Set the sender address first", got.json["mail_server"]["missing"])
        self.assertEqual(got.json["mail_waiting"], ["new@example.com"])
        auth_api.drain()
        self.assertEqual(self.sent, [])
        db = self.db()
        try:
            self.assertIsNotNone(mail_confirm.request(db, self.alpha["id"], "new@example.com"),
                                 "no link was made, so the first real one goes at once")
        finally:
            db.close()
        self.mail_on()
        cookie, csrf = self.session("owner@example.com")
        again = self.call("GET", T + "settings", cookie=cookie)
        self.assertTrue(again.json["mail_server"]["ready"])
        self.assertIsNone(again.json["mail_server"]["missing"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_mail_page_says_no_mail_server_above_the_recipients(self):
        # 2.42: Settings > Mail said "A confirm link was mailed to ..." with no mail server.
        # The page, drawn in node from these real answers (tests/js/prefs-mail.mjs).
        cookie, csrf = self.session("owner@example.com")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            def keep(name, got):
                self.assertEqual(got.status, 200, got.json)
                (out / name).write_text(json.dumps(got.json))
            keep("off-get.json", self.call("GET", T + "settings", cookie=cookie))
            keep("off-save.json", self.post(T + "settings/save", {"mail.to": ["new@example.com"]}, cookie, csrf))
            self.mail_on()
            cookie, csrf = self.session("owner@example.com")      # the config is read at sign-in
            keep("on-get.json", self.call("GET", T + "settings", cookie=cookie))
            keep("on-save.json", self.post(T + "settings/save", {"mail.to": ["new@example.com", "other@example.com"]}, cookie, csrf))
            js = Path(__file__).resolve().parent / "js" / "prefs-mail.mjs"
            done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=120,
                                  env={**os.environ, "PREFS_MAIL_DIR": tmp})
        self.assertEqual(done.returncode, 0, done.stderr[-4000:])
        self.assertIn("prefs-mail: all passed", done.stdout)

    def test_the_signed_in_persons_own_address_is_not_asked(self):
        self.mail_on()
        got = self.save({"mail.to": ["owner@example.com", "new@example.com"]})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["mail_waiting"], ["new@example.com"], "only the other one waits")
        auth_api.drain()
        self.assertEqual([to for to, _ in self.sent], ["new@example.com"])
        db = self.db()
        try:
            self.assertTrue(mail_confirm.is_confirmed(db, self.alpha["id"], "owner@example.com"),
                            "so the daily mail reaches it")
        finally:
            db.close()

    def test_the_test_mail_goes_only_to_the_caller_or_a_confirmed_recipient(self):
        self.mail_on()
        sent = []
        with mock.patch("skald.mailer.send", side_effect=lambda m, c: sent.append(c)):
            cookie, csrf = self.session("admin@example.com")
            got = self.post(T + "settings/test-mail", {"to": "victim@example.org"}, cookie, csrf)
            self.assertEqual(got.status, 403, got.json)
            got = self.post(T + "settings/test-mail", {"to": "admin@example.com"}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
            db = self.db()
            try:
                mail_confirm.mark_confirmed(db, self.alpha["id"], "team@example.com")
            finally:
                db.close()
            got = self.post(T + "settings/test-mail", {"to": "team@example.com"}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
        self.assertEqual([c["to"] for c in sent], [["admin@example.com"], ["team@example.com"]])


if __name__ == "__main__":
    unittest.main()
