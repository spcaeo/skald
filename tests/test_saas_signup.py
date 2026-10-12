"""Phase 5a sign-up over real HTTP (saas/signup_api.py, saas/signups.py):
/traffic-auth/signup mails a link (24 h, used once), the same answer whether
or not the address has an account, limits per address and per email,
saas.allowed_domains, and signup-finish making the user, the organisation
(owner), its first site and the trial plan, then signing in.

With saas off, every new route answers 404 and nothing is written.
Addresses are example.com, client addresses RFC 5737.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import ORIGIN, PW, SAME, Server  # noqa: E402

from skald import accounts, auth_api  # noqa: E402
from skald.saas import plans, signups  # noqa: E402

PLANS = {"free": {"sites": 1, "members": 3, "retention_days_max": 90},
         "pro": {"sites": 5, "members": 10, "retention_days_max": 400, "trial_days": 14,
                 "price_id": "price_pro_test"}}
NEW = "carol@example.com"


class Case(Server):
    def setUp(self):
        super().setUp()
        self.config["saas"] = {"enabled": True, "signup": True, "plans": PLANS,
                               "default_plan": "pro"}
        self.mail_on()

    def signup(self, email=NEW, ip="192.0.2.10"):
        return self.call("POST", "/traffic-auth/signup", {"email": email},
                         {**SAME, "X-Real-IP": ip})

    def mailed_token(self, to=NEW) -> str | None:
        auth_api.drain()
        for got_to, msg in self.sent:
            if got_to == to:
                found = re.search(r"/traffic-auth/signup-finish\?t=([A-Za-z0-9_-]+)",
                                  msg.get_body(("plain",)).get_content())
                if found:
                    return found.group(1)
        return None

    def finish(self, token, **extra):
        body = {"token": token, "name": "Carol", "password": PW, "org": "Carol Co",
                "host": "carol.example.com", **extra}
        return self.call("POST", "/traffic-auth/signup-finish", body, SAME)


class Flow(Case):
    def test_sign_up_verify_and_finish(self):
        got = self.signup()
        self.assertEqual(got.status, 200, got.json)
        token = self.mailed_token()
        self.assertTrue(token)
        self.assertTrue(str(self.sent[0][1]["Subject"]).endswith("Finish signing up"))
        self.assertIn(ORIGIN, self.sent[0][1].get_body(("plain",)).get_content())
        info = self.call("GET", f"/traffic-auth/signup-info?t={token}")
        self.assertEqual((info.status, info.json["email"]), (200, NEW))
        done = self.finish(token, host="https://Carol.Example.com/pricing")
        self.assertEqual(done.status, 200, done.json)
        self.assertEqual(done.json["next"], "/traffic/carol.example.com/")
        self.assertTrue(done.cookie)
        db = self.db()
        try:
            user = accounts.find_user(db, email=NEW)
            self.assertFalse(user["install_admin"])
            org = accounts.org_of_site(db, "carol.example.com")
            self.assertEqual(org["name"], "Carol Co")
            self.assertEqual(accounts.role_in(db, user["id"], org["id"]), "owner")
            state = plans.org_state(db, org["id"])
            self.assertEqual((state["plan"], state["plan_status"], state["created_via"]),
                             ("pro", "trialing", "signup"))
            self.assertEqual(state["trial_ends_at"], "2026-10-25T14:00:00Z")
            self.assertIsNotNone(accounts.sessions.resolve(db, done.cookie))
            actions = [e["action"] for e in accounts.auditlog.recent(db, None)]
            self.assertIn("signup.finish", actions)
        finally:
            db.close()
        # The new owner's session works on the new site's pages.
        me = self.call("GET", "/traffic/carol.example.com/me", cookie=done.cookie)
        self.assertEqual((me.json["user"], me.json["role"]), (NEW, "owner"))
        self.assertEqual(me.json["plan"]["name"], "pro")

    def test_the_new_site_is_a_dashboard_site_with_its_log_folder(self):
        # Found by the browser check: the site was only assigned to the organisation, so
        # no run read it, Settings called it a config-file site, and its page never came.
        from skald import ingest_log
        from skald.accounts import site_configs
        self.signup()
        self.assertEqual(self.finish(self.mailed_token()).status, 200)
        db = self.db()
        try:
            row = site_configs.get(db, "carol.example.com")
            org = accounts.org_of_site(db, "carol.example.com")
        finally:
            db.close()
        self.assertIsNotNone(row)
        self.assertEqual((row["org_id"], row["active"]), (org["id"], True))
        folder = Path(row["log_dir"])
        self.assertEqual(folder.name, ingest_log.slug("carol.example.com"))
        self.assertEqual(folder.parent.name, "ingest")
        self.assertTrue(folder.is_dir())

    def test_the_trial_plans_retention_cap_is_written_for_the_new_org(self):
        self.config["saas"]["default_plan"] = "free"
        self.signup()
        self.assertEqual(self.finish(self.mailed_token()).status, 200)
        db = self.db()
        try:
            from skald import settings_store
            got = settings_store.explain(self.config, "carol.example.com", db)
            self.assertEqual(got["report.retention_days"]["value"], 90)
            self.assertEqual(got["report.retention_days"]["source"], "org")
        finally:
            db.close()

    def test_a_link_works_once(self):
        self.signup()
        token = self.mailed_token()
        self.assertEqual(self.finish(token).status, 200)
        again = self.finish(token, host="other.example.com")
        self.assertEqual(again.status, 400)
        self.assertEqual(self.call("GET", f"/traffic-auth/signup-info?t={token}").status, 400)

    def test_a_link_expires_after_24_hours(self):
        self.signup()
        token = self.mailed_token()
        self.tick(24 * 3600 + 1)
        got = self.finish(token)
        self.assertEqual(got.status, 400)
        self.assertIn("expired", got.json["error"])
        db = self.db()
        try:
            self.assertIsNone(accounts.find_user(db, email=NEW))
        finally:
            db.close()

    def test_bad_input_is_refused_and_keeps_the_link(self):
        self.signup()
        token = self.mailed_token()
        for extra, words in (({"password": "short"}, "12 characters"),
                             ({"host": "not a host"}, "host name"),
                             ({"host": "index.html"}, "host name"),
                             ({"host": "alpha.example"}, "already"),
                             ({"org": ""}, "organisation a name"),
                             ({"name": ""}, "name")):
            got = self.finish(token, **extra)
            self.assertEqual(got.status, 400, extra)
            self.assertIn(words, got.json["error"], extra)
        self.assertEqual(self.finish(token).status, 200)

    def test_a_site_over_the_plans_limit_is_never_the_first(self):
        self.config["saas"]["plans"] = {"none": {"sites": 0}}
        self.config["saas"]["default_plan"] = "none"
        self.signup()
        got = self.finish(self.mailed_token())
        self.assertEqual(got.status, 400)
        self.assertIn("allows 0 sites", got.json["error"])


class Enumeration(Case):
    def test_the_same_answer_for_a_known_and_an_unknown_address(self):
        known = self.signup("owner@example.com", ip="192.0.2.11")
        fresh = self.signup(NEW, ip="192.0.2.12")
        self.assertEqual((known.status, known.json), (fresh.status, fresh.json))
        auth_api.drain()
        # The owner gets "you have an account", never a sign-up link.
        self.assertIsNone(self.mailed_token("owner@example.com"))
        mails = [m for to, m in self.sent if to == "owner@example.com"]
        self.assertEqual(len(mails), 1)
        self.assertIn("/traffic-auth/forgot", mails[0].get_body(("plain",)).get_content())

    def test_a_bad_address_says_so(self):
        got = self.signup("not-an-address")
        self.assertEqual(got.status, 400)


class Limits(Case):
    def test_three_links_an_hour_per_email_then_silence(self):
        for n in range(5):
            self.assertEqual(self.signup(ip=f"192.0.2.{20 + n}").status, 200)
        auth_api.drain()
        self.assertEqual(len([1 for to, _ in self.sent if to == NEW]), signups.PER_EMAIL)
        self.tick(3601)
        self.signup(ip="192.0.2.30")
        auth_api.drain()
        self.assertEqual(len([1 for to, _ in self.sent if to == NEW]), signups.PER_EMAIL + 1)

    def test_ten_an_hour_per_address_then_429(self):
        for n in range(signups.PER_IP):
            self.assertEqual(self.signup(f"p{n}@example.com").status, 200)
        got = self.signup("late@example.com")
        self.assertEqual(got.status, 429)
        self.assertTrue(got.header("Retry-After"))
        self.assertEqual(self.signup("late@example.com", ip="192.0.2.99").status, 200)

    def test_allowed_domains(self):
        self.config["saas"]["allowed_domains"] = ["example.com"]
        self.assertEqual(self.signup("ann@sub.example.com").status, 200)
        got = self.signup("ann@example.org")
        self.assertEqual(got.status, 400)
        self.assertIn("cannot sign up", got.json["error"])
        auth_api.drain()
        self.assertFalse([1 for to, _ in self.sent if to == "ann@example.org"])

    def test_same_origin_only(self):
        got = self.call("POST", "/traffic-auth/signup", {"email": NEW},
                        {"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(got.status, 403)


class Pages(Case):
    def test_the_pages_are_served_with_the_csp(self):
        for name in ("signup", "signup-finish"):
            got = self.call("GET", f"/traffic-auth/{name}")
            self.assertEqual(got.status, 200, name)
            self.assertIn("script-src 'self'", got.header("Content-Security-Policy"))
            self.assertIn(f'data-page="{name}"'.encode(), got.raw)


class Off(Server):
    ROUTES = (("GET", "/traffic-auth/signup"), ("GET", "/traffic-auth/signup-finish"),
              ("GET", "/traffic-auth/signup-info?t=x"), ("POST", "/traffic-auth/signup"),
              ("POST", "/traffic-auth/signup-finish"))

    def check_all_404(self):
        for method, path in self.ROUTES:
            got = self.call(method, path, {"email": NEW} if method == "POST" else None, SAME)
            self.assertEqual(got.status, 404, (method, path))

    def test_saas_off_every_route_is_404_and_nothing_is_written(self):
        self.check_all_404()
        self.config["saas"] = {"enabled": True, "signup": False}
        self.check_all_404()
        self.config["saas"] = {"enabled": False, "signup": True}
        self.check_all_404()
        db = self.db()
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM signups").fetchone()[0], 0)
            self.assertIsNone(accounts.find_user(db, email=NEW))
        finally:
            db.close()

    def test_the_me_answer_has_no_plan_with_saas_off(self):
        cookie = self.login().cookie
        me = self.call("GET", "/traffic/alpha.example/me", cookie=cookie).json
        self.assertNotIn("plan", me)
        self.assertNotIn("saas", me)


if __name__ == "__main__":
    unittest.main()
