"""Four leftovers from the browser check, pinned:

1. Settings > Mail: the sender address (`mail.from`) is a setting an install
   admin changes from the page; a test mail without one says so in a plain
   sentence, never with config key names.
2. A site added in Settings > Sites, or by sign-up, has a page at once (a
   "Getting ready" page, then its first build on a thread), never nginx's 404.
3. Internal addresses: with no `ours.file`, the list lives in ours.json beside
   the history; the classifier and the audit's own reading both find it.
4. Retention on a capped plan: the value shown and used is min(setting, cap),
   marked capped; the input's top follows the cap; pruning uses the cap.

Addresses are example.com, client addresses RFC 5737.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, SAME, Server  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald import accounts, audit_visits, auth_api, first_page, ours_store  # noqa: E402
from skald import settings_store as store  # noqa: E402
from skald.saas import plans  # noqa: E402

T = f"/traffic/{A}/"
PLANS = {"free": {"sites": 3, "members": 5, "retention_days_max": 90},
         "pro": {"sites": 5, "members": 10, "retention_days_max": 400, "trial_days": 14}}


def install_admin(case, email="owner@example.com"):
    db = case.db()
    try:
        accounts.set_install_admin(db, case.uids[email], True, "cli")
    finally:
        db.close()


# ------------------------------------------------------------ 1. the sender

class Sender(Server):
    def test_the_sender_is_checked_like_an_address(self):
        self.assertEqual(store.validate("mail.from", " Reports@Example.com "),
                         "reports@example.com")
        for bad in ("nope", "Skald <a@example.com>", "a@example.com\nBcc: b@example.com", 7):
            with self.subTest(bad=bad), self.assertRaises(store.Invalid):
                store.validate("mail.from", bad)
        self.assertEqual(store.SCHEMA["mail.from"].who, "install")
        self.assertEqual(store.SCHEMA["mail.from"].config, ("mail", "from"))

    def test_only_an_install_admin_sets_it_and_the_mail_uses_it(self):
        self.config["mail"] = {"host": "smtp.example.com"}
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "settings/save", {"mail.from": "skald@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 403)
        self.assertIn("install admin", got.json["error"])
        # Without a sender, the test mail says what to do, in words, not key names.
        got = self.post(T + "settings/test-mail", {"to": "admin@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertIn("Set the sender address first", got.json["error"])
        self.assertIn("An install admin sets it", got.json["error"])
        self.assertNotIn("mail.", got.json["error"])
        install_admin(self)
        cookie, csrf = self.session("owner@example.com")
        got = self.post(T + "settings/save", {"mail.from": "Skald@Example.com"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        entry = got.json["settings"]["mail.from"]
        self.assertEqual((entry["value"], entry["source"], entry["editable"]),
                         ("skald@example.com", "install", True))
        self.assertEqual(self.post(T + "settings/save", {"mail.from": "nope"}, cookie,
                                   csrf).status, 400)
        sent = []
        with mock.patch("skald.mailer.send", side_effect=lambda m, c: sent.append(m)):
            got = self.post(T + "settings/test-mail", {"to": "owner@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertIn("<skald@example.com>", sent[0]["From"])

    def test_no_server_says_so_too(self):
        self.config["mail"] = {"from": "skald@example.com"}
        install_admin(self)
        cookie, csrf = self.session("owner@example.com")
        got = self.post(T + "settings/test-mail", {"to": "owner@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertEqual(got.json["error"],
                         "Set the mail server first (Mail server (SMTP) > SMTP server).")


# -------------------------------------------------------- 2. the first page

class Placeholder(unittest.TestCase):
    def test_written_once_and_never_over_a_page(self):
        with tempfile.TemporaryDirectory() as d:
            page = first_page.placeholder(d, "shop.example.com")
            self.assertEqual(page, Path(d) / "shop.example.com" / "index.html")
            words = page.read_text()
            self.assertIn("Getting ready: shop.example.com", words)
            self.assertIn('http-equiv="refresh"', words)
            self.assertNotIn("<script", words)
            page.write_text("the real page")
            self.assertIsNone(first_page.placeholder(d, "shop.example.com"))
            self.assertEqual(page.read_text(), "the real page")
            self.assertIsNone(first_page.placeholder(None, "shop.example.com"))

    def test_the_build_is_the_runs_own_for_one_site(self):
        ran = []
        with mock.patch.object(first_page, "RUN",
                               side_effect=lambda cmd, **kw: ran.append(cmd) or
                               mock.Mock(returncode=0)):
            self.assertTrue(first_page.build("/etc/x/config.yml", "shop.example.com", "/srv/www"))
        self.assertEqual(ran[0][1:], [str(first_page.ROOT / "bin/skald"), "--config",
                                      "/etc/x/config.yml", "--site", "shop.example.com",
                                      "dashboard", "--out", "/srv/www"])
        with mock.patch.object(first_page, "RUN", side_effect=OSError("no")):
            self.assertFalse(first_page.build("/c.yml", "shop.example.com", "/srv/www"))


class NewSitePage(TenantServer):
    def test_a_site_added_in_settings_has_a_page_at_once_and_a_build(self):
        ran = []
        with mock.patch.object(first_page, "RUN", side_effect=lambda cmd, **kw: ran.append(cmd)
                               or mock.Mock(returncode=0)):
            cookie, csrf = self.session("admin@example.com")
            got = self.post(T + "sites/add", {"host": "shop.example.org"}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
            page = self.out / "shop.example.org" / "index.html"
            self.assertIn("Getting ready", page.read_text())
            auth_api.drain()
        self.assertEqual(len(ran), 1)
        self.assertEqual(ran[0][ran[0].index("--site") + 1], "shop.example.org")
        self.assertEqual(ran[0][ran[0].index("--out") + 1], str(self.out))
        self.assertEqual(ran[0][ran[0].index("--config") + 1], str(self.config_path))

    def test_the_real_build_draws_the_new_sites_page(self):
        cookie, csrf = self.session("admin@example.com")
        with mock.patch.object(first_page, "start"):           # the build below, not a thread
            got = self.post(T + "sites/add", {"host": "shop.example.org"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        first_page.placeholder(self.out, "shop.example.org")
        self.assertTrue(first_page.build(self.config_path, "shop.example.org", self.out))
        page = (self.out / "shop.example.org" / "index.html").read_text()
        self.assertNotIn("Getting ready", page)
        # The web app by default (2.2.2), with the site's plain page beside it.
        self.assertIn('id="app"', page)
        self.assertIn("shop.example.org", (self.out / "shop.example.org" / "classic.html").read_text())


class SignUpPage(Server):
    def test_the_sign_up_site_has_a_page_at_once(self):
        import re
        self.config["saas"] = {"enabled": True, "signup": True, "plans": PLANS,
                               "default_plan": "pro"}
        self.mail_on()
        self.call("POST", "/traffic-auth/signup", {"email": "carol@example.com"},
                  {**SAME, "X-Real-IP": "192.0.2.10"})
        auth_api.drain()
        token = re.search(r"signup-finish\?t=([A-Za-z0-9_-]+)",
                          self.sent[0][1].get_body(("plain",)).get_content()).group(1)
        got = self.call("POST", "/traffic-auth/signup-finish",
                        {"token": token, "name": "Carol", "password": "correct horse battery "
                         "staple", "org": "Carol Co", "host": "carol.example.com"}, SAME)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["next"], "/traffic/carol.example.com/")
        self.assertIn("Getting ready", (self.out / "carol.example.com" / "index.html").read_text())


# ------------------------------------------------------- 3. internal traffic

class OursBesideTheHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_the_default_file_and_both_roads_read_it(self):
        from skald.classify import Classifier
        config = {"_resolved": {"history_db": str(self.dir / "history.sqlite")}}
        self.assertEqual(ours_store.path_of(config), self.dir / "ours.json")
        self.assertEqual(ours_store.path_of({"history": {"db": str(self.dir / "h.sqlite")}}),
                         self.dir / "ours.json")
        self.assertIsNone(ours_store.path_of({"history": {"db": "history.sqlite"}}))
        self.assertIsNone(ours_store.path_of({}))
        # A file named in config.yml still wins.
        named = {**config, "ours": {"file": str(self.dir / "elsewhere.json")}}
        self.assertEqual(ours_store.path_of(named), self.dir / "elsewhere.json")
        when = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
        ours_store.add(config, "203.0.113.7", "Office", now=when)
        self.assertTrue((self.dir / "ours.json").is_file())
        self.assertEqual([e["ip"] for e in ours_store.listing(config)], ["203.0.113.7"])
        self.assertEqual(len(Classifier.from_config(config).ours_networks), 1)
        # The audit's second road reads the same file on its own terms.
        self.assertEqual(audit_visits.page_added(config), [("203.0.113.7", "Office", when)])

    def test_no_history_folder_known_refuses_in_plain_words(self):
        with self.assertRaises(ours_store.Invalid) as got:
            ours_store.add({}, "203.0.113.7", "Office")
        self.assertNotIn("ours.file is not set", str(got.exception))
        self.assertEqual(audit_visits.page_added({}), [])


class OursPage(Server):
    def test_the_list_says_whether_it_can_take_an_address(self):
        install_admin(self)
        cookie, csrf = self.session("owner@example.com")
        got = self.call("GET", T + "ours", headers=SAME, cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertTrue(got.json["can_add"])
        del self.config["ours"]["file"]                     # no file and no history known
        got = self.call("GET", T + "ours", headers=SAME, cookie=cookie)
        self.assertFalse(got.json["can_add"])
        self.config["_resolved"] = {"history_db": str(self.live / "history.sqlite")}
        got = self.call("GET", T + "ours", headers=SAME, cookie=cookie)
        self.assertTrue(got.json["can_add"])
        got = self.call("POST", T + "ours/add", {"ip": "203.0.113.9", "label": "Office"},
                        SAME, cookie=cookie, csrf=csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertTrue((self.live / "ours.json").is_file())


# ------------------------------------------------------ 4. the plan's cap

class CapShown(Server):
    def setUp(self):
        super().setUp()
        self.config["saas"] = {"enabled": True, "plans": PLANS, "default_plan": "pro"}
        db = self.db()
        try:
            plans.set_plan(db, self.alpha["id"], "free", "active", "cli")
            store.put(db, f"site:{A}", "report.retention_days", 400, "cli")
        finally:
            db.close()

    def test_the_value_is_the_cap_and_says_so(self):
        db = self.db()
        try:
            got = store.explain(self.config, A, db)
        finally:
            db.close()
        entry = got["report.retention_days"]
        self.assertEqual((entry["value"], entry["capped"], entry["set_value"]), (90, True, 400))
        # A value under the cap is not marked.
        self.assertNotIn("capped", got["report.journey_days"])
        cookie, _ = self.session("admin@example.com")
        s = self.call("GET", T + "settings", cookie=cookie).json["settings"]
        self.assertEqual((s["report.retention_days"]["value"], s["report.retention_days"]["hi"],
                          s["report.retention_days"]["capped"]), (90, 90, True))
        self.assertEqual(s["beacon.keep_days"]["value"], 90)            # default 400, capped
        # Another organisation, with no plan, keeps its own value.
        db = self.db()
        try:
            other = store.explain(self.config, "beta.example", db)
        finally:
            db.close()
        self.assertEqual(other["report.retention_days"]["value"], 400)

    def test_saving_under_the_cap_needs_the_typed_name_against_the_capped_value(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "settings/save", {"report.retention_days": 60}, cookie, csrf)
        self.assertEqual(got.status, 409)                   # 60 < 90: a shorter window
        got = self.post(T + "settings/save", {"report.retention_days": 90}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn("capped", got.json["settings"]["report.retention_days"])


SITE, OTHER = "alpha.example", "beta.example"


class CapPrunes(unittest.TestCase):
    TODAY = date(2026, 10, 11)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.config_path = self.dir / "config.yml"
        self.config_path.write_text(
            f"site:\n  name: {SITE}\nhistory:\n  db: {self.dir / 'history.sqlite'}\n"
            "report:\n  retention_days: 400\n  timezone: UTC\naccess:\n  mode: sessions\n"
            "saas:\n  enabled: true\n  default_plan: pro\n  plans:\n"
            "    - {name: free, sites: 3, members: 5, retention_days_max: 90}\n"
            "    - {name: pro, sites: 5, members: 10, retention_days_max: 400}\n")
        db = accounts.connect(self.dir / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Alpha", "cli")
            accounts.assign_site(db, SITE, org["id"], "cli")
            plans.set_plan(db, org["id"], "free", "active", "cli")
            store.put(db, f"site:{SITE}", "report.retention_days", 400, "cli")
            other = accounts.create_org(db, "Beta", "cli")
            accounts.assign_site(db, OTHER, other["id"], "cli")
            plans.set_plan(db, other["id"], "pro", "active", "cli")
        finally:
            db.close()

    def ctx(self):
        from skald.cli import Context
        args = argparse.Namespace(config=str(self.config_path), today=self.TODAY.isoformat(),
                                  dry_run=True, keep=None, weekly_keep=None)
        return Context(args)

    def test_pruning_uses_the_capped_value(self):
        from skald.cli import prune_kept
        from skald.store import History
        with History(self.dir / "history.sqlite") as h:
            for site in (SITE, OTHER):
                for ago in (10, 80, 100, 300):
                    h.db.execute("INSERT INTO day_extras (site, day, kind, data) VALUES "
                                 "(?, ?, 'pages', '{}')",
                                 (site, (self.TODAY - timedelta(days=ago)).isoformat()))
            h.db.commit()
        ctx = self.ctx()
        self.assertEqual(ctx.config["report"]["retention_days"], 90)
        self.assertEqual(store.prune_plan(ctx.config, "report.retention_days", 400)[1][SITE], 90)
        with ctx.history() as history:
            prune_kept(ctx, history)
        with History(self.dir / "history.sqlite") as h:
            kept = {(s, (self.TODAY - date.fromisoformat(d)).days)
                    for s, d in h.db.execute("SELECT site, day FROM day_extras")}
        # alpha's plan keeps 90 days although its row says 400; beta's plan allows 400.
        self.assertEqual(kept, {(SITE, 10), (SITE, 80), (OTHER, 10), (OTHER, 80), (OTHER, 100),
                                (OTHER, 300)})


if __name__ == "__main__":
    unittest.main()
