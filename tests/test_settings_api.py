"""Settings in the dashboard over real HTTP (settings_api.py, sessions mode):
reading every setting with who may change it, saving with CSRF and roles,
locks, the typed site name for a smaller window, the retention preview,
secrets that never come back, the test mail and its limit, the audit log
with CSV, the organisation's security settings at the nginx check, and 404
in basic mode."""
from __future__ import annotations

import json
import os
import stat
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, PW, SAME, Server  # noqa: E402

from skald import accounts, settings_store as store  # noqa: E402
from skald.accounts import auditlog, totp  # noqa: E402

T = f"/traffic/{A}/"
SECRET = "pw-that-must-never-come-back"


class Base(Server):
    def install_admin(self, email="owner@example.com"):
        db = self.db()
        try:
            accounts.set_install_admin(db, self.uids[email], True, "cli")
        finally:
            db.close()

    def save(self, body, email="owner@example.com"):
        cookie, csrf = self.session(email)
        return self.post(T + "settings/save", body, cookie, csrf)


class Reading(Base):
    def test_a_viewer_reads_every_setting_and_may_change_none(self):
        cookie, _ = self.session("viewer@example.com")
        got = self.call("GET", T + "settings", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        s = got.json["settings"]
        self.assertEqual(set(s), set(store.SCHEMA))
        self.assertEqual(s["report.retention_days"]["value"], 400)
        self.assertEqual(s["report.retention_days"]["source"], "default")
        self.assertFalse(any(v["editable"] for v in s.values()))
        self.assertIn("admin", s["report.retention_days"]["reason"])
        self.assertIn("install admin", s["mail.smtp.host"]["reason"])
        self.assertTrue(s["mail.smtp.host"]["hidden"])
        self.assertEqual(set(s["mail.smtp.password"]) & {"value"}, set())
        self.assertIs(s["mail.smtp.password"]["set"], False)

    def test_an_admin_may_change_site_keys_but_not_install_or_owner_keys(self):
        cookie, _ = self.session("admin@example.com")
        s = self.call("GET", T + "settings", cookie=cookie).json["settings"]
        self.assertTrue(s["report.retention_days"]["editable"])
        self.assertTrue(s["mail.to"]["editable"])
        self.assertFalse(s["backup.daily"]["editable"])
        self.assertFalse(s["mail.smtp.password"]["editable"])
        self.assertFalse(s["security.require_totp"]["editable"])

    def test_other_orgs_site_and_no_session(self):
        cookie, _ = self.session()
        self.assertEqual(self.call("GET", f"/traffic/{B}/settings", cookie=cookie).status, 403)
        self.assertEqual(self.call("GET", T + "settings").status, 401)

    def test_a_locked_key_reads_locked_and_refuses(self):
        self.config["settings"] = {"locked": ["report.journey_days"]}
        cookie, csrf = self.session()
        s = self.call("GET", T + "settings", cookie=cookie).json["settings"]
        self.assertEqual((s["report.journey_days"]["locked"], s["report.journey_days"]
                          ["editable"]), (True, False))
        got = self.post(T + "settings/save", {"report.journey_days": 14}, cookie, csrf)
        self.assertEqual(got.status, 403)
        self.assertIn("Locked", got.json["error"])


class Saving(Base):
    def test_csrf_same_origin_and_roles(self):
        cookie, csrf = self.session()
        body = {"report.journey_days": 14}
        for bad in (None, "wrong"):
            self.assertEqual(self.post(T + "settings/save", body, cookie, bad).status, 403)
        got = self.call("POST", T + "settings/save", body, {"Sec-Fetch-Site": "cross-site"},
                        cookie=cookie, csrf=csrf)
        self.assertEqual(got.status, 403)
        self.assertEqual(self.save(body, "viewer@example.com").status, 403)
        self.assertEqual(self.call("GET", T + "settings/save", cookie=cookie).status, 405)
        got = self.save(body, "admin@example.com")
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["saved"], ["report.journey_days"])
        self.assertEqual(got.json["settings"]["report.journey_days"]["value"], 14)
        self.assertEqual(got.json["settings"]["report.journey_days"]["source"], "site")
        db = self.db()
        try:
            self.assertEqual(store.get(db, f"site:{A}", "report.journey_days"), 14)
            rows = auditlog.recent(db, self.alpha["id"], action="setting.change")
            self.assertEqual(rows[0]["detail"], f"site:{A}: (not set) -> 14")
            self.assertEqual(rows[0]["actor"], str(self.uids["admin@example.com"]))
        finally:
            db.close()

    def test_bad_values_unknown_keys_and_install_keys(self):
        self.assertEqual(self.save({"report.journey_days": 0}).status, 400)
        self.assertEqual(self.save({"report.nope": 1}).status, 400)
        self.assertEqual(self.save({}).status, 400)
        got = self.save({"mail.smtp.host": "smtp.mail.test"}, "admin@example.com")
        self.assertEqual(got.status, 403)
        self.assertIn("install admin", got.json["error"])
        # All or nothing: one refused key saves none of the others.
        self.save({"report.journey_days": 9, "backup.daily": 3}, "admin@example.com")
        db = self.db()
        try:
            self.assertIsNone(store.get(db, f"site:{A}", "report.journey_days"))
        finally:
            db.close()
        self.install_admin()
        got = self.save({"mail.smtp.host": "smtp.mail.test", "backup.daily": 20})
        self.assertEqual(got.status, 200, got.json)

    def test_a_smaller_window_needs_the_site_name(self):
        got = self.save({"report.retention_days": 90})
        self.assertEqual(got.status, 409)
        self.assertTrue(got.json["needs_confirm"])
        self.assertEqual(got.json["keys"], ["report.retention_days"])
        self.assertEqual(self.save({"report.retention_days": 90, "confirm": "wrong"}).status, 409)
        self.assertEqual(self.save({"report.retention_days": 90, "confirm": A}).status, 200)
        # Longer again needs no name.
        self.assertEqual(self.save({"report.retention_days": 800}).status, 200)

    def test_owner_security_needs_their_own_two_step(self):
        got = self.save({"security.require_totp": True})
        self.assertEqual(got.status, 400)
        self.assertIn("two-step", got.json["error"])
        self.assertEqual(self.save({"security.session_days": 7},
                                   "admin@example.com").status, 403)
        self.assertEqual(self.save({"security.session_days": 7}).status, 200)


class Goals(Base):
    def seed_events(self):
        from skald import events
        from skald.store import History
        with History(self.live / "history.sqlite") as h:
            events.ensure(h.db)
            for site, event in ((A, "signup_submit"), (A, "cta_click"), (B, "copy_text")):
                h.db.execute("INSERT INTO event_counts (site, day, event, label, path, source, "
                             "n) VALUES (?, '2026-10-01', ?, '', '/', 'direct', 2)",
                             (site, event))
            h.db.commit()

    def test_goals_are_chosen_from_the_events_seen_and_saved_by_admins(self):
        self.seed_events()
        cookie, _ = self.session("admin@example.com")
        s = self.call("GET", T + "settings", cookie=cookie).json["settings"]["beacon.goals"]
        self.assertEqual((s["kind"], s["value"], s["editable"]), ("events", [], True))
        seen = {e["name"] for e in s["events"] if e["seen"]}
        self.assertEqual(seen, {"signup_submit", "cta_click"})        # not the other site's
        labels = {e["name"]: e["label"] for e in s["events"]}
        self.assertEqual(labels["signup_submit"], "Sign-up sent")
        got = self.save({"beacon.goals": ["signup_submit"]}, "admin@example.com")
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["settings"]["beacon.goals"]["value"], ["signup_submit"])
        self.assertEqual(got.json["settings"]["beacon.goals"]["source"], "site")
        self.assertEqual(self.save({"beacon.goals": ["nope"]}, "admin@example.com").status, 400)
        self.assertEqual(self.save({"beacon.goals": ["cta_click"]}, "viewer@example.com").status,
                         403)


class Secrets(Base):
    def test_a_secret_is_written_once_and_only_ever_said_set(self):
        self.install_admin()
        with mock.patch.dict(os.environ, {"SKALD_SMTP_PASSWORD": ""}):
            got = self.save({"mail.smtp.password": SECRET})
            self.assertEqual(got.status, 200, got.json)
            self.assertNotIn(SECRET.encode(), got.raw)
            cookie, _ = self.session()
            read = self.call("GET", T + "settings", cookie=cookie)
            self.assertNotIn(SECRET.encode(), read.raw)
            self.assertEqual(read.json["settings"]["mail.smtp.password"]["set"], True)
            audit = self.call("GET", T + "settings/audit", cookie=cookie)
            self.assertNotIn(SECRET.encode(), audit.raw)
        path = self.live / "secrets.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(path.read_text())["SKALD_SMTP_PASSWORD"], SECRET)
        db = self.db()
        try:
            dump = "\n".join(str(tuple(r)) for t in ("settings", "audit")
                             for r in db.execute(f"SELECT * FROM {t}"))
        finally:
            db.close()
        self.assertNotIn(SECRET, dump)
        self.assertEqual(self.save({"mail.smtp.password": SECRET},
                                   "admin@example.com").status, 403)


class Preview(Base):
    def seed_history(self):
        from skald.store import History
        today = date.today()
        with History(self.live / "history.sqlite") as h:
            for site in (A, B):
                for ago in (2, 20, 50):
                    day = (today - timedelta(days=ago)).isoformat()
                    h.db.execute("INSERT INTO journeys (site, day, seq, data) VALUES "
                                 "(?, ?, 1, '{}')", (site, day))
                    h.db.execute("INSERT INTO journeys (site, day, seq, data) VALUES "
                                 "(?, ?, 2, '{}')", (site, day))
            h.db.commit()

    def test_how_much_a_smaller_window_removes(self):
        self.seed_history()
        cookie, _ = self.session("admin@example.com")
        got = self.call("GET", T + "settings/retention-preview?key=report.journey_days&value=10",
                        cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        # Journeys are kept 7 days now (the default); 10 is longer: nothing goes.
        self.assertEqual((got.json["shrinks"], got.json["rows"]), (False, 0))
        self.save({"report.journey_days": 60})
        got = self.call("GET", T + "settings/retention-preview?key=report.journey_days&value=10",
                        cookie=cookie)
        self.assertEqual((got.json["shrinks"], got.json["rows"], got.json["days"]), (True, 4, 2))
        self.assertEqual(self.call("GET", T + "settings/retention-preview?key=mail.to&value=1",
                                   cookie=cookie).status, 400)
        vcookie, _ = self.session("viewer@example.com")
        self.assertEqual(self.call("GET", T + "settings/retention-preview?key=report."
                                   "journey_days&value=3", cookie=vcookie).status, 403)


class TestMail(Base):
    def test_admins_send_three_in_ten_minutes(self):
        self.mail_on()
        sent = []
        with mock.patch("skald.mailer.send", side_effect=lambda m, c: sent.append((m, c))):
            cookie, csrf = self.session("admin@example.com")
            for _ in range(3):
                got = self.post(T + "settings/test-mail", {"to": "admin@example.com"}, cookie,
                                csrf)
                self.assertEqual(got.status, 200, got.json)
            got = self.post(T + "settings/test-mail", {"to": "admin@example.com"}, cookie, csrf)
            self.assertEqual(got.status, 429)
            self.tick(601)
            self.assertEqual(self.post(T + "settings/test-mail", {"to": "admin@example.com"},
                                       cookie, csrf).status, 200)
        self.assertEqual(len(sent), 4)
        self.assertEqual(sent[0][1]["to"], ["admin@example.com"])
        self.assertIn("Test mail", sent[0][0]["Subject"])

    def test_viewers_bad_addresses_and_no_mail_setup(self):
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(T + "settings/test-mail", {"to": "x@example.com"}, cookie,
                                   csrf).status, 403)
        cookie, csrf = self.session("admin@example.com")
        self.assertEqual(self.post(T + "settings/test-mail", {"to": "nope"}, cookie,
                                   csrf).status, 400)
        got = self.post(T + "settings/test-mail", {"to": "admin@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 400)
        # A plain sentence, not config key names (test_browser_leftovers.py).
        self.assertIn("Set the sender address first", got.json["error"])


class Audit(Base):
    def test_the_log_with_a_filter_and_csv(self):
        self.save({"report.journey_days": 14})
        cookie, _ = self.session()
        got = self.call("GET", T + "settings/audit?action=setting.change", cookie=cookie)
        self.assertEqual(got.status, 200)
        self.assertEqual({e["action"] for e in got.json["entries"]}, {"setting.change"})
        self.assertIn("setting.change", got.json["actions"])
        csv = self.call("GET", T + "settings/audit?format=csv", cookie=cookie)
        self.assertEqual(csv.status, 200)
        self.assertTrue(csv.header("Content-Type").startswith("text/csv"))
        self.assertIn("attachment", csv.header("Content-Disposition"))
        self.assertTrue(csv.raw.decode().startswith("at,actor,action,target,detail"))
        self.assertIn("owner@example.com", csv.raw.decode())
        vcookie, _ = self.session("viewer@example.com")
        self.assertEqual(self.call("GET", T + "settings/audit", cookie=vcookie).status, 403)

    def test_a_formula_in_a_cell_is_not_run(self):
        from skald.settings_api import _cell
        self.assertEqual(_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(_cell("plain"), "plain")


class Security(Base):
    def set_org(self, name, value):
        db = self.db()
        try:
            store.put(db, f"org:{self.alpha['id']}", name, value, "cli")
        finally:
            db.close()

    def test_session_length_ends_older_sessions(self):
        cookie = self.login().cookie
        self.assertEqual(self.check(T + "overview", cookie).status, 200)
        self.set_org("security.session_days", 1)
        self.tick(86400 + 60)
        self.assertEqual(self.check(T + "overview", cookie).status, 401)

    def test_required_two_step_is_set_up_at_sign_in(self):
        cookie = self.login("viewer@example.com").cookie
        self.set_org("security.require_totp", True)
        self.assertEqual(self.check(T + "overview", cookie).status, 401)
        got = self.login("viewer@example.com")
        self.assertTrue(got.json.get("needs_setup"), got.json)
        self.assertIsNone(got.cookie)
        code = totp.code_at(got.json["secret"], int(self._now.timestamp()))
        bad = self.login("viewer@example.com", setup_code="000000" if code != "000000"
                         else "111111")
        self.assertEqual(bad.status, 400)
        got = self.login("viewer@example.com", setup_code=code)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(len(got.json["recovery_codes"]), 10)
        self.assertEqual(self.check(T + "overview", got.cookie).status, 200)
        # Bob's organisation does not require it.
        self.assertIsNotNone(self.login("bob@example.com").cookie)


class Routes(Base):
    def test_settings_audit_is_not_the_team_routes_audit(self):
        cookie, _ = self.session()
        got = self.call("GET", T + "settings/audit", cookie=cookie)
        self.assertIn("actions", got.json)


class BasicMode(Server):
    MODE = "basic"

    def test_every_route_is_404(self):
        for method, path in (("GET", "settings"), ("POST", "settings/save"),
                             ("GET", "settings/retention-preview?key=report.journey_days&value=3"),
                             ("POST", "settings/test-mail"), ("GET", "settings/audit")):
            got = self.call(method, T + path, {} if method == "POST" else None, SAME)
            self.assertEqual(got.status, 404, path)


if __name__ == "__main__":
    unittest.main()


class WebPages(unittest.TestCase):
    """The pages are registered, hidden in basic mode, and never put a server
    value in as markup."""
    JS = Path(__file__).resolve().parent.parent / "skald" / "webapp" / "js"

    def test_registered_and_hidden_without_accounts(self):
        state = (self.JS / "state.js").read_text()
        index = (self.JS / "tabs" / "index.js").read_text()
        access = (self.JS / "access.js").read_text()
        for key, name in (("retention", "Data retention"), ("mail", "Mail"), ("sites", "Sites"),
                          ("security", "Security"), ("audit", "Audit log")):
            self.assertIn(f'["settings/{key}", "{name}"]', state)
            self.assertIn(f'"settings/{key}":', index)
            self.assertIn(f'"settings/{key}"', state.split("ACCOUNT_TABS =")[1].split("\n")[0])
        self.assertIn("ACCOUNT_TABS.forEach((k) => HIDDEN.add(k))", access)

    def test_no_markup_from_the_server(self):
        for name in ("prefs.js", "auditlog.js"):
            js = (self.JS / "tabs" / name).read_text()
            self.assertNotIn("innerHTML", js, name)
            self.assertNotIn("html:", js, name)
