"""Settings in the dashboard (settings_store.py): the merged view and its
order (site > org > install > config.yml > default), locks, the checks on
every key, who may change what, the audit rows, secrets that never come
back, and the daily run reading the merged view (pruning, mail, backups)."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402

from skald import accounts, settings_store as store  # noqa: E402
from skald.accounts import auditlog  # noqa: E402

SITE, OTHER = "alpha.example", "beta.example"


class Seeded(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        self.org2 = accounts.create_org(self.db, "Beta", "cli")
        accounts.assign_site(self.db, SITE, self.org["id"], "cli")
        accounts.assign_site(self.db, OTHER, self.org2["id"], "cli")
        self.config = {"site": {"name": SITE}, "report": {"retention_days": "200"}}

    def value(self, name, site=SITE, config=None):
        return store.effective(config or self.config, site, self.db)[name]


class Precedence(Seeded):
    def test_default_then_config_then_install_org_site(self):
        self.assertEqual(self.value("report.journey_days"), 7)               # default
        self.assertEqual(self.value("report.retention_days"), 200)           # config.yml
        store.put(self.db, "install", "report.retention_days", 300, "cli")
        self.assertEqual(self.value("report.retention_days"), 300)
        store.put(self.db, f"org:{self.org['id']}", "report.retention_days", 500, "cli")
        self.assertEqual(self.value("report.retention_days"), 500)
        store.put(self.db, f"site:{SITE}", "report.retention_days", 600, "cli")
        got = store.explain(self.config, SITE, self.db)["report.retention_days"]
        self.assertEqual((got["value"], got["source"]), (600, "site"))
        # The other organisation's site sees only the install's row.
        self.assertEqual(self.value("report.retention_days", OTHER), 300)
        # Clearing the site's row falls back to the org's.
        store.put(self.db, f"site:{SITE}", "report.retention_days", None, "cli")
        self.assertEqual(self.value("report.retention_days"), 500)

    def test_a_locked_key_ignores_every_row(self):
        store.put(self.db, f"site:{SITE}", "report.retention_days", 600, "cli")
        config = {**self.config, "settings": {"locked": ["report.retention_days"]}}
        got = store.explain(config, SITE, self.db)["report.retention_days"]
        self.assertEqual((got["value"], got["source"], got["locked"]), (200, "config", True))
        self.assertEqual(store.may_edit("report.retention_days", "owner", True, config),
                         (False, store.LOCK_WORDS))

    def test_tiny_yaml_reads_the_lock_list(self):
        from skald.config import tiny_yaml
        got = tiny_yaml("settings:\n  locked: [report.retention_days, mail.to]\n")
        self.assertEqual(store.locked(got), frozenset({"report.retention_days", "mail.to"}))

    def test_a_key_saved_only_where_its_scope_allows(self):
        with self.assertRaises(store.Invalid):
            store.put(self.db, f"site:{SITE}", "mail.smtp.host", "smtp.mail.test", "cli")
        with self.assertRaises(store.Invalid):
            store.put(self.db, "install", "security.require_totp", True, "cli")
        with self.assertRaises(store.Invalid):
            store.put(self.db, "nowhere", "report.journey_days", 3, "cli")


class Goals(Seeded):
    """beacon.goals from the dashboard: a site's own list of event names,
    checked against the events the beacon takes, merged like every key."""

    def test_the_check(self):
        v = lambda value: store.validate("beacon.goals", value)  # noqa: E731
        self.assertEqual(v(["demo_booked", "signup_submit", "demo_booked"]),
                         ["demo_booked", "signup_submit"])
        self.assertEqual(v("signup_submit, cta_click"), ["signup_submit", "cta_click"])
        self.assertEqual(v([]), [])
        self.assertIsNone(v(None))
        self.assertEqual(v(["page_view"]), ["page_view"])
        for bad in (["nope"], [3], ["signup_submit", {"x": 1}], 7,
                    ["<script>"], list(store.GOAL_EVENTS[:11])):
            with self.assertRaises(store.Invalid, msg=repr(bad)):
                v(bad)

    def test_config_then_the_sites_row(self):
        config = {**self.config, "beacon": {"goals": ["cta_click"]}}
        got = store.explain(config, SITE, self.db)["beacon.goals"]
        self.assertEqual((got["value"], got["source"]), (["cta_click"], "config"))
        self.assertEqual(self.value("beacon.goals"), [])                     # the default
        store.put(self.db, f"site:{SITE}", "beacon.goals", ["demo_booked"], "cli")
        self.assertEqual(self.value("beacon.goals", config=config), ["demo_booked"])
        self.assertEqual(self.value("beacon.goals", OTHER, config), ["cta_click"])
        store.put(self.db, f"site:{SITE}", "beacon.goals", [], "cli")      # none, on purpose
        self.assertEqual(self.value("beacon.goals", config=config), [])
        with self.assertRaises(store.Invalid):
            store.put(self.db, f"org:{self.org['id']}", "beacon.goals", ["cta_click"], "cli")
        self.assertTrue(store.may_edit("beacon.goals", "admin", False, {})[0])
        self.assertFalse(store.may_edit("beacon.goals", "viewer", False, {})[0])
        rows = auditlog.recent(self.db, self.org["id"], action="setting.change")
        self.assertIn('["demo_booked"] -> []', rows[0]["detail"])


class Validation(unittest.TestCase):
    def bad(self, name, value):
        with self.assertRaises(store.Invalid, msg=(name, value)):
            store.validate(name, value)

    def test_ranges(self):
        for name, lo, hi in (("report.retention_days", 30, 3650), ("report.journey_days", 1, 90),
                             ("visitors.repeat_days", 1, 90), ("beacon.keep_days", 30, 3650),
                             ("backup.daily", 1, 60), ("backup.weekly", 0, 52),
                             ("security.session_days", 1, 90)):
            self.assertEqual(store.validate(name, lo), lo)
            self.assertEqual(store.validate(name, str(hi)), hi)
            self.bad(name, lo - 1)
            self.bad(name, hi + 1)
            self.bad(name, True)
            self.bad(name, "ten")

    def test_other_kinds(self):
        self.assertIs(store.validate("mail.daily", False), False)
        self.bad("mail.daily", "maybe")
        self.assertEqual(store.validate("mail.to", ["A@Example.com", "a@example.com",
                                                     "b@example.com"]),
                         ["a@example.com", "b@example.com"])
        self.bad("mail.to", [])
        self.bad("mail.to", ["not an address"])
        self.assertEqual(store.validate("mail.from_name", "  Traffic  report "), "Traffic report")
        self.bad("mail.from_name", "x" * 61)
        self.bad("mail.from_name", "line\nbreak")
        self.assertEqual(store.validate("mail.smtp.security", "ssl"), "ssl")
        self.bad("mail.smtp.security", "tls")
        self.bad("mail.smtp.host", "smtp example")
        self.assertEqual(store.validate("sites.hosts", "Example.com, www.example.com"),
                         ["example.com", "www.example.com"])
        self.bad("sites.hosts", [])
        self.assertEqual(store.validate("sites.timezone", "Europe/London"), "Europe/London")
        self.bad("sites.timezone", "Mars/Olympus")
        self.bad("sites.timezone", "../etc/passwd")
        self.assertEqual(store.validate("sites.log_dir", "/var/log/nginx/"), "/var/log/nginx")
        self.bad("sites.log_dir", "relative/logs")
        self.bad("sites.log_dir", "/var/../etc")
        self.bad("sites.log_base", "../access.log")
        self.bad("mail.smtp.password", "two\nlines")
        self.bad("no.such.key", 1)

    def test_views(self):
        got = store.validate("sites.views", [{"name": "Canada", "path_prefix": "/ca/",
                                              "exclude_prefix": "/ca/fr/  /ca/x/"}])
        self.assertEqual(got, [{"name": "Canada", "path_prefix": "/ca/",
                                "exclude_prefix": "/ca/fr/ /ca/x/"}])
        self.bad("sites.views", [{"name": "A"}, {"name": "a"}])          # same slug
        self.bad("sites.views", [{"name": "Data"}])                        # reserved
        self.bad("sites.views", [{"name": "X", "path_prefix": "ca"}])
        self.bad("sites.views", [{"path_prefix": "/x/"}])


class Permissions(unittest.TestCase):
    def test_who_may_change_what(self):
        cases = {"report.retention_days": "admin", "mail.to": "admin", "sites.hosts": "admin",
                 "backup.daily": "install", "mail.smtp.host": "install",
                 "mail.smtp.password": "install", "pagespeed.api_key": "install",
                 "sites.log_dir": "install", "security.require_totp": "owner",
                 "security.session_days": "owner"}
        for name, who in cases.items():
            for role in ("viewer", "admin", "owner"):
                for install in (False, True):
                    may, why = store.may_edit(name, role, install, {})
                    want = {"admin": role in ("admin", "owner"), "install": install,
                            "owner": role == "owner"}[who]
                    self.assertEqual(may, want, (name, role, install))
                    self.assertEqual(bool(why), not want)


class AuditAndSecrets(Seeded):
    def test_every_change_is_audited_old_to_new(self):
        store.put(self.db, f"site:{SITE}", "report.journey_days", 14, 7)
        store.put(self.db, f"site:{SITE}", "report.journey_days", 14, 7)      # no change
        store.put(self.db, f"site:{SITE}", "report.journey_days", None, 7)
        rows = [e for e in auditlog.recent(self.db, self.org["id"])
                if e["action"] == "setting.change"]
        self.assertEqual([(e["target"], e["detail"]) for e in reversed(rows)],
                         [("report.journey_days", f"site:{SITE}: (not set) -> 14"),
                          ("report.journey_days", f"site:{SITE}: 14 -> (not set)")])
        self.assertEqual(rows[0]["actor"], "7")

    def test_a_secret_goes_to_the_file_never_the_table_or_the_log(self):
        path = self.dir / "secrets.json"
        name = store.secret_name({}, "mail.smtp.password")
        self.assertEqual(name, "SKALD_SMTP_PASSWORD")
        store.put(self.db, "install", "mail.smtp.password", "s3cret-value", "cli", (path, name))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(path.read_text())[name], "s3cret-value")
        dump = "\n".join(str(tuple(r)) for t in ("settings", "audit")
                         for r in self.db.execute(f"SELECT * FROM {t}"))
        self.assertNotIn("s3cret-value", dump)
        self.assertIn("install: set", dump)
        cfg = {"_resolved": {"history_db": str(self.dir / "history.sqlite")}}
        with mock.patch.dict(os.environ, {name: ""}):
            self.assertEqual(store.secret_state(cfg, "mail.smtp.password"),
                             {"set": True, "env": False})
            self.assertEqual(store.secret_value(cfg, "mail.smtp.password"), "s3cret-value")
        with mock.patch.dict(os.environ, {name: "from-env"}):          # the environment wins
            self.assertEqual(store.secret_value(cfg, "mail.smtp.password"), "from-env")
        store.put(self.db, "install", "mail.smtp.password", None, "cli", (path, name))
        with mock.patch.dict(os.environ, {name: ""}):
            self.assertEqual(store.secret_state(cfg, "mail.smtp.password")["set"], False)
        self.assertIn("install: cleared", [e["detail"] for e in auditlog.recent(self.db, None)])

    def test_the_password_keeps_the_name_config_gives_it(self):
        self.assertEqual(store.secret_name({"mail": {"password_env": "MY_SMTP"}},
                                           "mail.smtp.password"), "MY_SMTP")
        self.assertEqual(store.secret_name({}, "pagespeed.api_key"), "PSI_API_KEY")

    def test_the_mailer_reads_a_typed_login(self):
        from skald import mailer
        path = self.dir / "secrets.json"
        store.put(self.db, "install", "mail.smtp.password", "pw-typed", "cli",
                  (path, "SKALD_SMTP_PASSWORD"))
        cfg = {"_resolved": {"history_db": str(self.dir / "history.sqlite")},
               "mail": {"host": "smtp.mail.test", "from": "skald@example.com",
                        "to": ["a@example.com"], "user": "robot"}}
        with mock.patch.dict(os.environ, {"SKALD_SMTP_PASSWORD": ""}):
            got = mailer.settings(cfg)
        self.assertEqual((got["user"], got["password"]), ("robot", "pw-typed"))


# ------------------------------------------------- the daily run reads it

def _write_config(folder: Path, extra: str = "") -> Path:
    path = folder / "config.yml"
    path.write_text(f"site:\n  name: {SITE}\nhistory:\n  db: {folder / 'history.sqlite'}\n"
                    f"report:\n  retention_days: 400\n  timezone: UTC\n{extra}")
    return path


class DailyRun(unittest.TestCase):
    TODAY = date(2026, 10, 11)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.config_path = _write_config(self.dir)

    def ctx(self):
        from skald.cli import Context
        args = argparse.Namespace(config=str(self.config_path), today=self.TODAY.isoformat(),
                                  dry_run=True, keep=None, weekly_keep=None)
        return Context(args)

    def accounts_db(self):
        db = accounts.connect(self.dir / "accounts.sqlite")
        if not accounts.org_of_site(db, SITE):
            org = accounts.create_org(db, "Alpha", "cli")
            accounts.assign_site(db, SITE, org["id"], "cli")
        return db

    def seed_extras(self):
        from skald.store import History
        with History(self.dir / "history.sqlite") as h:
            for site in (SITE, OTHER, f"{SITE}::canada"):
                for ago in (10, 40, 100):
                    day = (self.TODAY - timedelta(days=ago)).isoformat()
                    h.db.execute("INSERT INTO day_extras (site, day, kind, data) "
                                 "VALUES (?, ?, 'pages', '{}')", (site, day))
            h.db.commit()

    def kept(self):
        from skald.store import History
        with History(self.dir / "history.sqlite") as h:
            return sorted((s, d) for s, d in h.db.execute("SELECT site, day FROM day_extras"))

    def prune(self):
        from skald.cli import prune_kept
        ctx = self.ctx()
        with ctx.history() as history:
            prune_kept(ctx, history)

    def test_no_accounts_file_changes_nothing(self):
        ctx = self.ctx()
        self.assertNotIn("_settings", ctx.config)
        self.assertEqual(str(ctx.config["report"]["retention_days"]), "400")
        self.seed_extras()
        self.prune()
        self.assertEqual(len(self.kept()), 9)

    def test_a_retention_row_changes_pruning_for_that_site_only(self):
        self.seed_extras()
        db = self.accounts_db()
        try:
            store.put(db, f"site:{SITE}", "report.retention_days", 30, "cli")
        finally:
            db.close()
        self.assertEqual(self.ctx().config["report"]["retention_days"], 30)
        self.prune()
        days = {(s, (self.TODAY - date.fromisoformat(d)).days) for s, d in self.kept()}
        # alpha (and its view) keep 30 days; beta keeps config.yml's 400.
        self.assertEqual(days, {(SITE, 10), (f"{SITE}::canada", 10),
                                (OTHER, 10), (OTHER, 40), (OTHER, 100)})

    def test_another_sites_longer_window_is_kept_when_this_site_prunes(self):
        self.seed_extras()
        self.config_path.write_text(self.config_path.read_text().replace(
            "retention_days: 400", "retention_days: 35"))
        db = self.accounts_db()
        try:
            org = accounts.create_org(db, "Beta", "cli")
            accounts.assign_site(db, OTHER, org["id"], "cli")
            store.put(db, f"org:{org['id']}", "report.retention_days", 365, "cli")
        finally:
            db.close()
        self.prune()
        days = {(s, (self.TODAY - date.fromisoformat(d)).days) for s, d in self.kept()}
        self.assertIn((OTHER, 100), days)
        self.assertNotIn((SITE, 40), days)

    def test_the_mail_switches_and_the_mail_list(self):
        from skald.cli import daily_steps
        db = self.accounts_db()
        try:
            store.put(db, f"site:{SITE}", "mail.daily", False, "cli")
            store.put(db, f"site:{SITE}", "mail.to", ["x@example.com"], "cli")
            # A page-set recipient is mailed once confirmed (mail_confirm.py).
            from skald import mail_confirm
            mail_confirm.mark_confirmed(db, accounts.org_of_site(db, SITE)["id"],
                                        "x@example.com")
        finally:
            db.close()
        ctx = self.ctx()
        self.assertEqual(ctx.config["mail"]["to"], ["x@example.com"])
        self.assertNotIn("daily mail", [n for n, _ in daily_steps(ctx)])

    def test_backups_and_the_visitor_window(self):
        from skald import backup, visitors
        self.assertEqual(backup.kept(self.ctx().config), (14, 8))
        db = self.accounts_db()
        try:
            store.put(db, "install", "backup.daily", 5, "cli")
            store.put(db, "install", "backup.weekly", 0, "cli")
            store.put(db, f"site:{SITE}", "visitors.repeat_days", 60, "cli")
        finally:
            db.close()
        ctx = self.ctx()
        self.assertEqual(backup.kept(ctx.config), (5, 0))
        self.assertEqual(backup.kept(ctx.config, 9, 2), (9, 2))       # flags win
        self.assertEqual(visitors.repeat_days(ctx.config), 60)
        self.assertEqual(store.prune_plan(ctx.config, "visitors.repeat_days", 30),
                         (30, {SITE: 60}))

    def test_the_beacon_window(self):
        from skald import events
        db = self.accounts_db()
        try:
            store.put(db, f"site:{SITE}", "beacon.keep_days", 90, "cli")
        finally:
            db.close()
        self.assertEqual(events.keep_days(self.ctx().config), 90)


    def test_goals_set_in_the_dashboard_reach_the_events_file(self):
        from skald import events
        db = self.accounts_db()
        try:
            store.put(db, f"site:{SITE}", "beacon.goals", ["signup_submit", "cta_click"], "cli")
        finally:
            db.close()
        ctx = self.ctx()
        self.assertEqual(ctx.config["beacon"]["goals"], ["signup_submit", "cta_click"])
        self.assertEqual(events.goal_names(ctx.config), ["signup_submit", "cta_click"])


class SecretsFileGuard(unittest.TestCase):
    def test_a_file_others_can_read_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "secrets.json"
            path.write_text('{"PSI_API_KEY": "k"}')
            os.chmod(path, 0o644)
            cfg = {"_resolved": {"history_db": str(Path(d) / "history.sqlite")}}
            with mock.patch.dict(os.environ, {"PSI_API_KEY": ""}):
                with self.assertRaises(PermissionError):
                    store.secret_value(cfg, "pagespeed.api_key")
                self.assertEqual(store.secret_state(cfg, "pagespeed.api_key")["set"], False)


if __name__ == "__main__":
    unittest.main()
