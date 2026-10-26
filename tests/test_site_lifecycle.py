"""A site's lifecycle from Settings > Sites and `skald site`: Pause/Resume,
Remove/Restore, Clear data and Delete all data (site_lifecycle.py, site_data.py,
site_actions_api.py, sites_cli.py).

Alpha's alpha.example is the config file's own (main) site, Beta's beta.example
a site made from the dashboard (ingest_support.TenantServer); some tests add a
second config-file site, shop.example.com, to Alpha. Addresses are RFC 5737,
names example.com/.org/.example.
"""
from __future__ import annotations

import io
import json
import sys
import tarfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402
from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402
from support import day_lines, totals_for  # noqa: E402

from skald import accounts, multisite, site_data, site_lifecycle  # noqa: E402
from skald.accounts import apitokens, auditlog, site_configs, site_state  # noqa: E402
from skald.conversions import secrets_store, spool, store  # noqa: E402
from skald.store import History  # noqa: E402

SHOP = "shop.example.com"
AT = "2026-10-10T10:00:00Z"


class Seeded(TenantServer):
    """The helper, with something of `site` in every store Skald keeps."""

    def setUp(self):
        super().setUp()
        self.built = []
        run = mock.patch("skald.first_page.RUN",
                         side_effect=lambda cmd, **kw: self.built.append(cmd) or
                         mock.Mock(returncode=0))
        run.start()
        self.addCleanup(run.stop)

    def add_shop(self):
        """A second config-file site of Alpha's."""
        (self.root / "shop.yml").write_text(json.dumps(
            {"site": {"name": SHOP, "hosts": [SHOP]},
             "logs": {"dir": str(self.root / "shop-logs"), "format": "nginx_combined"}}))
        self.config["sites"] = ["shop.yml"]
        self.config_path.write_text(json.dumps(self.config))
        db = self.db()
        try:
            accounts.assign_site(db, SHOP, self.alpha["id"], "cli")
        finally:
            db.close()

    def seed_site(self, site: str) -> None:
        live = self.live
        with History(live / "history.sqlite") as h:
            h.record(site, date(2026, 10, 8), totals_for(day_lines(date(2026, 10, 8), 3)),
                     "UTC", [])
            h.record(f"{site}::blog", date(2026, 10, 8),
                     totals_for(day_lines(date(2026, 10, 8), 1)), "UTC", [])
        db = store.connect(live / "conversions.sqlite")
        try:
            db.execute("INSERT INTO conversions (site, action, stage, at, external_ref, tool, "
                       "received_at) VALUES (?, 'demo', 'completed', ?, ?, 'calendly', ?)",
                       (site, AT, f"ref-{site}", AT))
            db.execute("INSERT INTO webhooks (site, url, events, created_at) VALUES "
                       "(?, 'https://example.com/h', 'conversion.completed', ?)", (site, AT))
            db.execute("INSERT INTO meta (key, value) VALUES (?, '1')", (f"outbox_cursor:{site}",))
            db.commit()
        finally:
            db.close()
        from skald.answers import store as answers
        db = answers.connect(answers.path_for(live))
        try:
            db.execute("INSERT INTO lists (site) VALUES (?)", (site,))
            pid = db.execute("INSERT INTO profiles (site, version, body, created_at, "
                             "updated_at) VALUES (?, 1, '{}', ?, ?)", (site, AT, AT)).lastrowid
            db.execute("INSERT INTO profile_versions (profile_id, version, body, saved_at) "
                       "VALUES (?, 1, '{}', ?)", (pid, AT))
            self.pids = {**getattr(self, "pids", {}), site: pid}
            db.execute("INSERT INTO runs (site, profile_id, version, day, started_at, why, plan, "
                       "planned, state) VALUES (?, ?, 1, '2026-10-08', ?, 'daily', '[]', 0, "
                       "'done')", (site, pid, AT))
            db.commit()
        finally:
            db.close()
        db = self.db()
        try:
            from skald import security_notify
            db.execute(security_notify.ITEMS)
            cols = [c[1] for c in db.execute("PRAGMA table_info(security_items)")]
            db.execute(f"INSERT INTO security_items ({', '.join(cols)}) VALUES "
                       f"({', '.join('?' * len(cols))})",
                       [site if c == "site" else "x1" if c == "item" else AT for c in cols])
            db.execute("INSERT INTO settings (scope, key, value) VALUES (?, 'site.asset_prefixes',"
                       " '[\"/assets/\"]')", (f"site:{site}",))
        finally:
            db.close()
        state = live / "sites" / site
        state.mkdir(parents=True, exist_ok=True)
        (state / f"live-{site}.json").write_text("{}")
        (state / "funnels.json").write_text('{"funnels": []}')
        ingest = self.ingest_root / site
        ingest.mkdir(parents=True, exist_ok=True)
        (ingest / "access.log").write_bytes(lines(2))
        (live / "ingest-status").mkdir(exist_ok=True)
        (live / "ingest-status" / f"{site}.json").write_text("{}")
        (live / "logos" / site).mkdir(parents=True, exist_ok=True)
        (live / "logos" / site / "logo.png").write_bytes(b"\x89PNG")
        (live / "search").mkdir(exist_ok=True)
        (live / "search" / f"{site}.json").write_text("{}")
        (self.out / site / "data").mkdir(parents=True, exist_ok=True)
        spool.append(live / "hooks", date(2026, 10, 10),
                     spool.line_for(AT, site, "calendly", {"a": 1}, False))
        secrets_store.put(live / "secrets.json", f"hooks/{site}/calendly", f"skh_{site}")
        links = live / "kit-links.json"
        got = json.loads(links.read_text()) if links.exists() else {"links": {}}
        got["links"][f"h-{site}"] = {"site": site, "made_at": 1, "expires_at": 4102444800}
        links.write_text(json.dumps(got))

    # ---- what is left of a site, store by store
    def rows(self, site: str) -> dict:
        out = {}
        h = History(self.live / "history.sqlite")
        try:
            out["history"] = h.db.execute("SELECT COUNT(*) FROM days WHERE site = ? OR site = ?",
                                          (site, f"{site}::blog")).fetchone()[0]
        finally:
            h.db.close()
        db = store.connect(self.live / "conversions.sqlite")
        try:
            for t in ("conversions", "webhooks"):
                out[t] = db.execute(f"SELECT COUNT(*) FROM {t} WHERE site = ?",
                                    (site,)).fetchone()[0]
            out["meta"] = db.execute("SELECT COUNT(*) FROM meta WHERE key = ?",
                                     (f"outbox_cursor:{site}",)).fetchone()[0]
        finally:
            db.close()
        from skald.answers import store as answers
        db = answers.connect(answers.path_for(self.live))
        try:
            for t in ("lists", "profiles", "runs"):
                out[t] = db.execute(f"SELECT COUNT(*) FROM {t} WHERE site = ?",
                                    (site,)).fetchone()[0]
            out["profile_versions"] = db.execute(
                "SELECT COUNT(*) FROM profile_versions WHERE profile_id = ?",
                (self.pids.get(site),)).fetchone()[0]
        finally:
            db.close()
        db = self.db()
        try:
            out["security_items"] = db.execute("SELECT COUNT(*) FROM security_items WHERE "
                                               "site = ?", (site,)).fetchone()[0]
            out["settings"] = db.execute("SELECT COUNT(*) FROM settings WHERE scope = ?",
                                         (f"site:{site}",)).fetchone()[0]
        finally:
            db.close()
        live = self.live
        out["files"] = sorted(str(p.relative_to(self.root)) for p in (
            live / "sites" / site / f"live-{site}.json", live / "sites" / site / "funnels.json",
            self.ingest_root / site / "access.log", live / "ingest-status" / f"{site}.json",
            live / "logos" / site, live / "search" / f"{site}.json", self.out / site)
            if p.exists())
        out["spool"] = len([r for r in spool.read(live / "hooks", date(2026, 10, 10))
                            if r["site"] == site])
        out["secrets"] = len([k for k in secrets_store.load(live / "secrets.json")
                              if k.split("/")[1] == site])
        out["links"] = len([v for v in json.loads((live / "kit-links.json").read_text())
                            ["links"].values() if v["site"] == site])
        return out

    def audit(self, org) -> list[dict]:
        db = self.db()
        try:
            return auditlog.recent(db, org["id"])
        finally:
            db.close()


# --------------------------------------------------------------- pause/resume

class Pause(Seeded):
    def run_check(self) -> list[str]:
        """The sites `skald check` (a collecting command) runs for."""
        from skald import cli
        seen = []
        out = io.StringIO()
        with mock.patch.object(cli, "cmd_check", side_effect=lambda ctx: seen.append(ctx.site)
                               or 0), redirect_stdout(out):
            args = cli.parser().parse_args(["--config", str(self.config_path), "check"])
            args.run = cli.cmd_check
            with mock.patch.object(cli, "parser") as p:
                p.return_value.parse_args.return_value = args
                cli.main([])
        return seen

    def test_pause_stops_ingest_and_the_runs_and_resume_starts_them(self):
        cookie, csrf = self.session("bob@example.com")
        token = self.token(self.beta, sites=[B])
        self.assertEqual(self.ship(B, token, lines(1)).status, 200)
        self.assertEqual(self.run_check(), [A, B])
        got = self.post(f"/traffic/{B}/sites/pause", {"name": B}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        shipped = self.ship(B, token, lines(1, 5), batch="s1:2")
        self.assertEqual(shipped.status, 503)               # the shipper keeps the lines
        self.assertEqual(shipped.header("Retry-After"), "3600")
        self.assertIn("paused", shipped.json["error"])
        self.assertEqual(self.run_check(), [A])
        listed = self.call("GET", f"/traffic/{B}/sites", cookie=cookie).json["sites"][0]
        self.assertEqual((listed["status"], listed["paused_at"]), ("paused", "2026-10-11T14:00:00Z"))
        self.assertEqual(self.post(f"/traffic/{B}/sites/pause", {"name": B}, cookie,
                                   csrf).status, 400)        # already paused
        got = self.post(f"/traffic/{B}/sites/resume", {"name": B}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertIn("Not recorded", got.json["words"])
        self.assertEqual(self.ship(B, token, lines(1, 5), batch="s1:2").status, 200)
        self.assertEqual(self.run_check(), [A, B])
        acts = [e["action"] for e in self.audit(self.beta)]
        self.assertIn("site.pause", acts)
        self.assertIn("site.resume", acts)

    def test_the_main_config_site_can_be_paused_by_an_admin(self):
        cookie, csrf = self.session("admin@example.com")
        self.assertEqual(self.post(f"/traffic/{A}/sites/pause", {"name": A}, cookie,
                                   csrf).status, 200)
        token = self.token(self.alpha, sites=[A])
        self.assertEqual(self.ship(A, token, lines(1)).status, 503)
        self.assertEqual(self.run_check(), [B])
        got = self.post(f"/traffic/{A}/sites/resume", {"name": A}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.run_check(), [A, B])

    def test_a_viewer_may_not_pause(self):
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(f"/traffic/{A}/sites/pause", {"name": A}, cookie,
                                   csrf).status, 403)

    def test_the_paused_days_read_not_recorded_never_0(self):
        with History(self.live / "history.sqlite") as h:
            for d in (date(2026, 10, 1), date(2026, 10, 6)):
                h.record(B, d, totals_for(day_lines(d, 2)), "UTC", [])
            got = {e["day"].isoformat(): e for e in
                   h.daily(B, date(2026, 10, 1), date(2026, 10, 6))}
        for d in ("2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"):
            self.assertEqual(got[d]["state"], "missing")
            self.assertNotIn("groups", got[d])               # no figure, so never a 0
        self.assertEqual(got["2026-10-01"]["state"], "ok")

    def test_resume_says_whether_the_log_can_fill_the_days(self):
        now = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
        same = site_lifecycle.resume_words({}, "2026-10-15T08:00:00Z", now)
        self.assertEqual(same["days"], 0)
        shipper = site_lifecycle.resume_words({"_dashboard_site": True, "site": {"name": B},
                                               "logs": {"format": "auto"}},
                                              "2026-10-11T14:00:00Z", now)
        self.assertEqual((shipper["days"], shipper["first"], shipper["last"]),
                         (4, "2026-10-11", "2026-10-14"))
        self.assertIn("shipper kept its lines", shipper["words"])
        self.assertIn(f"skald --site {B} backfill --days 4", shipper["words"])
        drain = site_lifecycle.resume_words({"_dashboard_site": True,
                                             "logs": {"format": "vercel_json"}},
                                            "2026-10-11T14:00:00Z", now)
        self.assertIn("stay Not recorded", drain["words"])
        gone = site_lifecycle.resume_words({"logs": {"dir": str(self.root / "none")}},
                                           "2026-10-11T14:00:00Z", now)
        self.assertIn("no longer holds them", gone["words"])


# ------------------------------------------------------------ remove/restore

class RemoveRestore(Seeded):
    def test_remove_and_restore_a_dashboard_site(self):
        cookie, csrf = self.session("bob@example.com")
        page = f"/traffic/{B}/"
        got = self.post(page + "sites/remove", {"name": B, "confirm": B}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn(B, [c["site"]["name"] for c in
                             multisite.site_configs(self.config, self.config_path)])
        token = self.token(self.beta, sites=[B])
        self.assertEqual(self.ship(B, token, lines(1)).status, 410)
        got = self.post(page + "sites/restore", {"name": B}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertIn(B, [c["site"]["name"] for c in
                          multisite.site_configs(self.config, self.config_path)])
        self.assertEqual(self.ship(B, token, lines(1)).status, 200)
        acts = [e["action"] for e in self.audit(self.beta)]
        self.assertLess(acts.index("site.restore"), acts.index("site.remove"))   # newest first

    def test_remove_and_restore_a_config_file_site(self):
        self.add_shop()
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/remove", {"name": SHOP, "confirm": SHOP}, cookie,
                        csrf)
        self.assertEqual(got.status, 200, got.json)
        token = self.token(self.alpha, sites=[SHOP])
        self.assertEqual(self.ship(SHOP, token, lines(1)).status, 410)
        listed = {s["name"]: s for s in
                  self.call("GET", f"/traffic/{A}/sites", cookie=cookie).json["sites"]}
        self.assertEqual((listed[SHOP]["source"], listed[SHOP]["status"]), ("config", "removed"))
        got = self.post(f"/traffic/{A}/sites/restore", {"name": SHOP}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.ship(SHOP, token, lines(1)).status, 200)

    def test_owner_only_typed_name_and_never_the_main_site(self):
        cookie, csrf = self.session("admin@example.com")
        for act in ("remove", "restore", "clear", "purge"):
            got = self.post(f"/traffic/{A}/sites/{act}", {"name": A, "confirm": A,
                                                          "understood": True}, cookie, csrf)
            self.assertEqual(got.status, 403, act)
            self.assertIn("Only an owner", got.json["error"])
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/remove", {"name": A, "confirm": A}, cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertIn("main site", got.json["error"])
        self.assertEqual(self.post(f"/traffic/{A}/sites/remove", {"name": B, "confirm": B},
                                   cookie, csrf).status, 404)        # another organisation's


# ------------------------------------------------------------- delete, clear

def archive_names(path: str) -> list[str]:
    with tarfile.open(path) as tar:
        return tar.getnames()


def archived_rows(path: str, store_name: str, table: str) -> int:
    import sqlite3
    import tempfile
    with tarfile.open(path) as tar, tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "copy.sqlite"
        copy.write_bytes(tar.extractfile(f"{store_name}.sqlite").read())
        db = sqlite3.connect(copy)
        try:
            return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            db.close()


class Wipe(Seeded):
    def setUp(self):
        super().setUp()
        self.seed_site(B)
        self.seed_site(A)

    def test_delete_all_data_archives_then_removes_every_store(self):
        before = self.rows(B)
        self.assertTrue(all(before.values()), before)
        token = self.token(self.beta, sites=[B])
        cookie, csrf = self.session("bob@example.com")
        page = f"/traffic/{B}/"
        self.assertEqual(self.post(page + "sites/purge", {"name": B, "confirm": B}, cookie,
                                   csrf).status, 400)                # the box not ticked
        self.assertEqual(self.post(page + "sites/purge", {"name": B, "confirm": "beta",
                                                          "understood": True}, cookie,
                                   csrf).status, 400)                # the name not typed
        got = self.post(page + "sites/purge", {"name": B, "confirm": B, "understood": True},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        body = got.json
        self.assertEqual(body["status"], "deleted")
        path = Path(body["archive"])
        self.assertEqual(path.parent, self.live / "backups")
        self.assertRegex(path.name, r"^site-beta\.example-purge-\d{8}T\d{6}Z\.tar\.gz$")
        names = archive_names(str(path))
        for part in ("manifest.json", "history.sqlite", "conversions.sqlite",
                     "answers.sqlite", "accounts.sqlite", "hooks-spool.jsonl",
                     "setup-links.json", f"files/dashboard/{B}"):
            self.assertIn(part, names)
        self.assertIn(f"files/history-folder/ingest/{B}/access.log", names)
        self.assertEqual(archived_rows(str(path), "history", "days"), 2)   # the site and its view
        self.assertEqual(archived_rows(str(path), "conversions", "webhooks"), 1)
        self.assertEqual(archived_rows(str(path), "answers", "profile_versions"), 1)
        with tarfile.open(path) as tar:
            manifest = json.load(tar.extractfile("manifest.json"))
            self.assertNotIn(f"skh_{B}", tar.extractfile("manifest.json").read().decode())
        self.assertEqual(manifest["secrets_deleted_not_archived"], [f"hooks/{B}/calendly"])
        after = self.rows(B)
        self.assertFalse(any(after.values()), after)
        kept = self.rows(A)
        self.assertTrue(all(kept.values()), kept)                    # the other site untouched
        ok, _, _ = self.call_token(token)
        self.assertFalse(ok)
        db = self.db()
        try:
            self.assertIsNone(site_configs.get(db, B))
        finally:
            db.close()
        row = self.audit(self.beta)[0]
        self.assertEqual((row["action"], row["target"]), ("site.purge", B))
        self.assertIn(path.name, row["detail"])
        self.assertNotIn("@", row["detail"])

    def call_token(self, token):
        db = self.db()
        try:
            return apitokens.check(db, f"Bearer {token}", B, "ingest")
        finally:
            db.close()

    def test_clear_keeps_settings_and_tokens(self):
        token = self.token(self.beta, sites=[B])
        cookie, csrf = self.session("bob@example.com")
        got = self.post(f"/traffic/{B}/sites/clear", {"name": B, "confirm": B,
                                                      "understood": True}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertRegex(Path(got.json["archive"]).name, r"^site-beta\.example-clear-")
        left = self.rows(B)
        for gone in ("history", "conversions", "meta", "runs", "security_items", "spool"):
            self.assertEqual(left[gone], 0, gone)
        for kept in ("webhooks", "lists", "profiles", "settings", "secrets", "links"):
            self.assertEqual(left[kept], 1, kept)
        self.assertIn(f"lib/sites/{B}/funnels.json", left["files"])
        self.assertNotIn(f"lib/sites/{B}/live-{B}.json", left["files"])
        self.assertIn(f"lib/logos/{B}", left["files"])
        self.assertTrue((self.ingest_root / B).is_dir())             # the shipper's folder
        self.assertEqual(self.ship(B, token, lines(1)).status, 200)  # the token still works
        db = self.db()
        try:
            self.assertTrue(site_configs.get(db, B)["active"])
            self.assertIsNotNone(site_state.get(db, B)["cleared_at"])
        finally:
            db.close()
        self.assertTrue(self.built)                                  # its pages drawn again
        row = self.audit(self.beta)[0]
        self.assertEqual(row["action"], "site.clear")
        self.assertIn(Path(got.json["archive"]).name, row["detail"])
        # Days before the clear are never collected again: they read Not recorded.
        cfg = {**self.config, "_resolved": {"history_db": str(self.live / "history.sqlite")}}
        self.assertTrue(site_lifecycle.before_clear(cfg, self.live, B, date(2026, 10, 10)))
        self.assertFalse(site_lifecycle.before_clear(cfg, self.live, B, date(2026, 10, 11)))
        with History(self.live / "history.sqlite") as h:
            days = h.daily(B, date(2026, 10, 5), date(2026, 10, 10))
        self.assertTrue(all(e["state"] in ("missing", "before") and "groups" not in e
                            for e in days), days)

    def test_a_config_file_site_keeps_its_entry_and_becomes_removed(self):
        self.add_shop()
        self.seed_site(SHOP)
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/purge", {"name": SHOP, "confirm": SHOP,
                                                      "understood": True}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["status"], "removed")
        left = self.rows(SHOP)
        self.assertFalse(any(left.values()), left)
        self.assertIn(SHOP, site_lifecycle.config_names(self.config, self.config_path))
        listed = {s["name"]: s for s in
                  self.call("GET", f"/traffic/{A}/sites", cookie=cookie).json["sites"]}
        self.assertEqual(listed[SHOP]["status"], "removed")
        self.assertTrue(self.rows(A)["history"])
        # A clear or a purge refuses the main site.
        for act in ("clear", "purge"):
            got = self.post(f"/traffic/{A}/sites/{act}", {"name": A, "confirm": A,
                                                          "understood": True}, cookie, csrf)
            self.assertEqual(got.status, 400, act)
            self.assertIn("main site", got.json["error"])

    def test_wipes_are_rate_limited(self):
        cookie, csrf = self.session("bob@example.com")
        page = f"/traffic/{B}/"
        for _ in range(3):
            self.assertEqual(self.post(page + "sites/clear", {"name": B, "confirm": B,
                                                              "understood": True}, cookie,
                                       csrf).status, 200)
        got = self.post(page + "sites/clear", {"name": B, "confirm": B, "understood": True},
                        cookie, csrf)
        self.assertEqual(got.status, 429)


class Archives(unittest.TestCase):
    def test_archives_older_than_30_days_are_pruned(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            now = time.time()
            old = datetime.fromtimestamp(now - 31 * 86400, timezone.utc)
            new = datetime.fromtimestamp(now - 29 * 86400, timezone.utc)
            for when in (old, new):
                (folder / f"site-x.example-clear-{when:%Y%m%dT%H%M%SZ}.tar.gz").write_bytes(b"")
            (folder / "history-2026-01-01.sqlite").write_bytes(b"")
            gone = site_data.prune(folder, now=now)
            self.assertEqual([p.name for p in gone],
                             [f"site-x.example-clear-{old:%Y%m%dT%H%M%SZ}.tar.gz"])
            self.assertEqual(len(list(folder.iterdir())), 2)

    def test_an_install_that_keeps_everything_keeps_every_archive(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            old = datetime.fromtimestamp(time.time() - 400 * 86400, timezone.utc)
            name = f"site-x.example-purge-{old:%Y%m%dT%H%M%SZ}.tar.gz"
            (folder / name).write_bytes(b"")
            self.assertEqual(site_data.prune(folder, config={"retention": {"keep_everything": True}}), [])
            self.assertTrue((folder / name).exists())


# --------------------------------------------------------------------- CLI

class Cli(AccountsCase):
    def run_ti(self, *argv):
        from skald import cli
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), \
                mock.patch("skald.first_page.RUN",
                           return_value=mock.Mock(returncode=0)):
            code = cli.main(["--config", str(self.cfg_path), *argv])
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")
        self.cfg_path = self.dir / "config.yml"
        self.cfg_path.write_text(json.dumps({
            "site": {"name": "main.example"}, "history": {"db": str(self.dir / "history.sqlite")},
            "dashboard": {"out": str(self.dir / "www")}, "access": {"mode": "sessions"}}))
        code, _, err = self.run_ti("site", "add", SHOP, "--org", self.org["slug"])
        self.assertEqual(code, 0, err)

    def test_pause_resume_restore_clear_and_purge(self):
        code, out, err = self.run_ti("site", "pause", SHOP)
        self.assertEqual(code, 0, err)
        code, out, _ = self.run_ti("site", "list")
        self.assertIn("paused", out)
        code, out, err = self.run_ti("site", "resume", SHOP)
        self.assertEqual(code, 0, err)
        self.assertIn("resumed", out)
        self.assertEqual(self.run_ti("site", "remove", SHOP)[0], 2)        # no --yes
        self.assertEqual(self.run_ti("site", "remove", SHOP, "--yes")[0], 0)
        code, out, err = self.run_ti("site", "restore", SHOP)
        self.assertEqual(code, 0, err)
        with History(self.dir / "history.sqlite") as h:
            h.record(SHOP, date(2026, 10, 8), totals_for(day_lines(date(2026, 10, 8), 2)),
                     "UTC", [])
        self.assertEqual(self.run_ti("site", "clear", SHOP)[0], 2)          # no --yes
        code, out, err = self.run_ti("site", "clear", SHOP, "--yes")
        self.assertEqual(code, 0, err)
        self.assertIn("archive written to", out)
        self.assertEqual(len(list((self.dir / "backups").glob("site-*-clear-*.tar.gz"))), 1)
        with History(self.dir / "history.sqlite") as h:
            self.assertIsNone(h.first_day(SHOP))
        self.assertIsNotNone(site_configs.get(self.db, SHOP))                # the site stays
        self.assertEqual(self.run_ti("site", "purge", SHOP)[0], 2)          # no --yes
        code, out, err = self.run_ti("site", "purge", SHOP, "--yes")
        self.assertEqual(code, 0, err)
        self.assertIn("held until", out)
        self.assertIsNone(site_configs.get(self.db, SHOP))
        acts = [e["action"] for e in auditlog.recent(self.db, self.org["id"])]
        for act in ("site.pause", "site.resume", "site.remove", "site.restore", "site.clear",
                    "site.purge"):
            self.assertIn(act, acts)

    def test_the_main_site_is_only_paused(self):
        for act in ("remove", "clear", "purge"):
            code, _, err = self.run_ti("site", act, "main.example", "--yes")
            self.assertEqual(code, 1, act)
            self.assertIn("main site", err)
        self.assertEqual(self.run_ti("site", "pause", "main.example")[0], 0)
        code, out, _ = self.run_ti("check")
        self.assertIn("main.example: paused since", out)

    def test_a_day_before_the_clear_is_never_collected_again(self):
        from skald import cli
        self.assertEqual(self.run_ti("site", "clear", SHOP, "--yes")[0], 0)
        args = cli.parser().parse_args(["--config", str(self.cfg_path), "--site", SHOP, "check"])
        _, contexts, _ = multisite.contexts(cli.Context(args), args, cli.Context)
        ctx = contexts[0]
        ctx.err = lambda *a: None
        yesterday = self._now.date() - timedelta(days=1)          # the clear was "now"
        with History(self.dir / "history.sqlite") as h:
            self.assertEqual(cli.collect_day(ctx, h, yesterday,
                                             logs=[str(self.dir / "none.log")]), "empty")
            self.assertIsNone(h.state(SHOP, yesterday))


class Page(unittest.TestCase):
    def test_the_row_menu_and_its_dialogs(self):
        import os
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node not installed")
        js = Path(__file__).resolve().parent / "js" / "site-actions.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ))
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertIn("site-actions: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
