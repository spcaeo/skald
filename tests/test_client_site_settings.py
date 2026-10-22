"""Adding a client's site to a multi-site install (deployments runbook gaps):

1. Per-site page assets: `site.asset_prefixes` and `site.require_rendering`
   are settings rows a site's admin saves; `apply` writes them into
   config["site"], where the first pass (rendering.py), its recount
   (audit_rendered.py) and the doctor read them, so both roads agree.
2. `skald settings list-keys | get | set`: the same checks and audit rows
   as the page, actor "cli"; secrets and locked keys refused.
3. `skald site hosts | remove`, and `site purge` deleting the logo folder.
4. The Add-a-site panel's tag loads /traffic-js/skald.js.
5. `token --help` names the ingest scope.
6. Settings > Integrations reads the merged beacon.visitor_ids.

Addresses are RFC 5737, names example.com/.org.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402
from support import Sandbox, line  # noqa: E402
from test_integrations_api import Base as IntegrationsBase  # noqa: E402
from test_rendering import DAY, TODAY, at  # noqa: E402

from skald import accounts, audit_rendered, rendering, settings_store as store  # noqa: E402
from skald.accounts import auditlog, site_configs  # noqa: E402
from skald.store import History  # noqa: E402

SHOP, MAIN = "shop.example.com", "main.example"


# ------------------------------------------------------- 1. page assets

class AssetKeys(unittest.TestCase):
    def check(self, value):
        return store.validate("site.asset_prefixes", value)

    def test_the_check(self):
        self.assertEqual(self.check(["/wp-content/", "/wp-includes/", "/wp-content/"]),
                         ["/wp-content/", "/wp-includes/"])
        self.assertEqual(self.check("/assets/, /static/"), ["/assets/", "/static/"])
        for bad in (["wp-content/"], ["/"], [], ["/a b/"], ["/../x/"],
                    [f"/p{i}/" for i in range(11)], [3], 7):
            with self.assertRaises(store.Invalid, msg=repr(bad)):
                self.check(bad)
        self.assertIsNone(self.check(None))
        self.assertIs(store.validate("site.require_rendering", "false"), False)

    def test_saved_for_the_site_by_an_admin(self):
        for name in ("site.asset_prefixes", "site.require_rendering"):
            key = store.SCHEMA[name]
            self.assertEqual((key.scopes, key.who), (("site",), "admin"), name)
        self.assertEqual(store.SCHEMA["site.asset_prefixes"].default,
                         list(rendering.ASSET_PREFIXES))


class AssetRows(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")
        accounts.assign_site(self.db, SHOP, self.org["id"], "cli")
        self.history = self.dir / "history.sqlite"
        self.config = {"site": {"name": SHOP, "hosts": [SHOP]},
                       "history": {"db": str(self.history)}}

    def applied(self):
        return store.apply(self.config, SHOP, self.dir)

    def test_no_row_keeps_the_config_and_the_default(self):
        got = self.applied()
        self.assertNotIn("asset_prefixes", got["site"])
        self.assertEqual(rendering.asset_prefixes(got), rendering.ASSET_PREFIXES)
        self.assertEqual(audit_rendered.prefixes(got), rendering.ASSET_PREFIXES)
        self.assertTrue(rendering.required(got) and audit_rendered.switched_on(got))

    def test_a_row_reaches_both_roads_the_same(self):
        store.put(self.db, f"site:{SHOP}", "site.asset_prefixes",
                  ["/wp-content/", "/wp-includes/"], "cli")
        got = self.applied()
        self.assertEqual(rendering.asset_prefixes(got), ("/wp-content/", "/wp-includes/"))
        self.assertEqual(audit_rendered.prefixes(got), rendering.asset_prefixes(got))
        store.put(self.db, f"site:{SHOP}", "site.require_rendering", False, "cli")
        got = self.applied()
        self.assertFalse(rendering.required(got))
        self.assertFalse(audit_rendered.switched_on(got))
        # The config itself is not changed; the install's other site is not either.
        self.assertNotIn("asset_prefixes", self.config["site"])
        self.assertEqual(store.effective(self.config, "other.example.org", self.db)
                         ["site.asset_prefixes"], ["/_next/static/"])


class AssetRowsCount(unittest.TestCase):
    """A WordPress site: a reader counts once its row names /wp-content/,
    and the audit's recount agrees."""

    def setUp(self):
        self.box = Sandbox()
        text = self.box.config.read_text().replace("  require_rendering: false\n", "")
        self.box.config.write_text(text)
        self.box.log([line(at(10), "203.0.113.30", "/"),
                      line(at(10, 0, 1), "203.0.113.30", "/wp-content/themes/a/style.css"),
                      line(at(11), "203.0.113.31", "/pricing/")])

    def tearDown(self):
        self.box.close()

    def run_day(self):
        for cmd in ("collect", "audit"):
            code, out, err = self.box.run("--today", TODAY, cmd, "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        with History(self.box.db) as h:
            row = h.db.execute("SELECT readers FROM groups WHERE site = 'example.com' AND "
                               "day = ? AND grp = 'people'", (DAY.isoformat(),)).fetchone()
        return row[0] if row else 0

    def test_the_row_counts_the_wordpress_reader_and_the_audit_agrees(self):
        self.assertEqual(self.run_day(), 0)
        db = accounts.connect(self.box.root / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Org", "cli")
            accounts.assign_site(db, "example.com", org["id"], "cli")
            store.put(db, "site:example.com", "site.asset_prefixes", ["/wp-content/"], "cli")
        finally:
            db.close()
        self.assertEqual(self.run_day(), 1)


# -------------------------------------------- 2, 3. settings and site CLI

class Cli(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")
        accounts.assign_site(self.db, MAIN, self.org["id"], "cli")
        self.cfg_path = self.dir / "config.yml"
        self.cfg_path.write_text(json.dumps({
            "site": {"name": MAIN}, "history": {"db": str(self.dir / "history.sqlite")},
            "dashboard": {"out": str(self.dir / "www")}, "access": {"mode": "sessions"},
            "settings": {"locked": ["mail.from_name"]}}))

    def run_ti(self, *argv):
        from skald import cli
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--config", str(self.cfg_path), *argv])
        return code, out.getvalue(), err.getvalue()

    def actions(self):
        return [(e["actor"], e["action"], e["target"], e["detail"])
                for e in auditlog.recent(self.db, None)
                if e["action"] not in ("org.create", "site.assign", "site.add")]


class SettingsCli(Cli):
    def test_list_keys(self):
        code, out, _ = self.run_ti("settings", "list-keys")
        self.assertEqual(code, 0)
        for name in ("site.asset_prefixes", "site.require_rendering", "beacon.visitor_ids",
                     "privacy.keep_ips", "mail.smtp.password"):
            self.assertIn(name, out)

    def test_set_and_get_a_site_key_audited_as_cli(self):
        code, out, err = self.run_ti("settings", "set", MAIN, "beacon.visitor_ids", "true")
        self.assertEqual(code, 0, err)
        self.assertIn("false -> true", out.replace("(not set)", "false"))
        self.assertIs(store.get(self.db, f"site:{MAIN}", "beacon.visitor_ids"), True)
        code, out, _ = self.run_ti("settings", "get", MAIN, "beacon.visitor_ids")
        self.assertEqual((code, out.split()), (0, ["beacon.visitor_ids", "true", "(site)"]))
        code, out, err = self.run_ti("settings", "set", MAIN, "site.asset_prefixes",
                                     '["/wp-content/", "/wp-includes/"]')
        self.assertEqual(code, 0, err)
        self.assertIn("backfill", out)
        code, out, err = self.run_ti("settings", "set", MAIN, "conversions.identity",
                                     "anonymous")
        self.assertEqual(code, 0, err)
        rows = self.actions()
        self.assertTrue(all(r[0] == "cli" and r[1] == "setting.change" for r in rows))
        self.assertEqual({r[2] for r in rows},
                         {"beacon.visitor_ids", "site.asset_prefixes", "conversions.identity"})
        code, out, _ = self.run_ti("settings", "get", MAIN)
        self.assertIn('"/wp-content/"', out)
        self.assertIn("mail.smtp.password", out)          # only "set" or "not set"
        # null clears the row: the default again.
        code, out, err = self.run_ti("settings", "set", MAIN, "beacon.visitor_ids", "null")
        self.assertEqual(code, 0, err)
        self.assertIn("now false (default)", out)

    def test_refusals(self):
        cases = [(("settings", "set", "nowhere.example", "beacon.visitor_ids", "true"), 2),
                 (("settings", "set", MAIN, "no.such.key", "1"), 2),
                 (("settings", "set", MAIN, "mail.smtp.password", "x"), 2),
                 (("settings", "set", MAIN, "mail.from_name", '"Shop"'), 1),
                 (("settings", "set", MAIN, "site.asset_prefixes", '["/"]'), 1),
                 (("settings", "set", MAIN, "privacy.keep_days", "99999"), 1),
                 (("settings", "get", MAIN, "no.such.key"), 2)]
        for argv, want in cases:
            code, _, err = self.run_ti(*argv)
            self.assertEqual(code, want, (argv, err))
        self.assertEqual(self.actions(), [])
        self.assertIsNone(store.get(self.db, f"site:{MAIN}", "site.asset_prefixes"))

    def test_a_smaller_window_needs_yes(self):
        code, _, err = self.run_ti("settings", "set", MAIN, "privacy.keep_days", "30")
        self.assertEqual(code, 2)
        self.assertIn("--yes", err)
        self.assertIsNone(store.get(self.db, f"site:{MAIN}", "privacy.keep_days"))
        code, _, err = self.run_ti("settings", "set", MAIN, "privacy.keep_days", "30", "--yes")
        self.assertEqual(code, 0, err)
        self.assertEqual(store.get(self.db, f"site:{MAIN}", "privacy.keep_days"), 30)


class SiteCli(Cli):
    def add_shop(self):
        code, _, err = self.run_ti("site", "add", SHOP, "--org", self.org["slug"])
        self.assertEqual(code, 0, err)

    def test_hosts(self):
        self.add_shop()
        code, out, err = self.run_ti("site", "hosts", SHOP, SHOP, "WWW." + SHOP)
        self.assertEqual(code, 0, err)
        self.assertEqual(site_configs.get(self.db, SHOP)["hosts"], [SHOP, "www." + SHOP])
        self.assertIn(("cli", "site.hosts", SHOP, f"{SHOP} -> {SHOP} www.{SHOP}"),
                      self.actions())
        # A Host names row saved in Settings is kept the same.
        store.put(self.db, f"site:{SHOP}", "sites.hosts", [SHOP], "cli")
        code, out, err = self.run_ti("site", "hosts", SHOP, SHOP, "shop.example.org")
        self.assertEqual(code, 0, err)
        self.assertEqual(store.get(self.db, f"site:{SHOP}", "sites.hosts"),
                         [SHOP, "shop.example.org"])
        self.assertIn("same list", out)
        for argv in (("site", "hosts", SHOP, "not a host"), ("site", "hosts", MAIN, MAIN)):
            code, _, _ = self.run_ti(*argv)
            self.assertEqual(code, 1, argv)
        self.assertEqual(site_configs.get(self.db, SHOP)["hosts"], [SHOP, "shop.example.org"])

    def test_remove_then_purge_deletes_the_logo_folder(self):
        from skald.site_logos import folder
        self.add_shop()
        logos = folder(self.dir, SHOP)
        # 2.25: `site add` asked for the logo already (its state.json is there).
        self.assertTrue((logos / "state.json").is_file())
        (logos / "state.json").write_text("{}")
        code, _, err = self.run_ti("site", "remove", SHOP)
        self.assertEqual(code, 2)
        self.assertTrue(site_configs.get(self.db, SHOP)["active"])
        code, out, err = self.run_ti("site", "remove", SHOP, "--yes")
        self.assertEqual(code, 0, err)
        self.assertFalse(site_configs.get(self.db, SHOP)["active"])
        self.assertEqual(self.run_ti("site", "remove", SHOP, "--yes")[0], 1)
        self.assertEqual(self.run_ti("site", "remove", MAIN, "--yes")[0], 1)
        code, out, err = self.run_ti("site", "purge", SHOP, "--yes")
        self.assertEqual(code, 0, err)
        self.assertFalse(logos.exists())
        self.assertIn(f"deleted {logos}", out)


# ------------------------------------------------ 4, 5. tag and token help

class TagAndHelp(unittest.TestCase):
    def test_the_add_a_site_tag_loads_the_served_path(self):
        from skald import beacon_server, sites_api
        self.assertEqual(sites_api.tag(SHOP), f'<script src="{beacon_server.SNIPPET_PATH}" '
                                              f'data-site="{SHOP}" defer></script>')
        self.assertIn('src="/traffic-js/skald.js"', sites_api.tag(SHOP))

    def test_token_help_names_the_ingest_scope(self):
        from skald import cli
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            cli.parser().parse_args(["token", "create", "--help"])
        self.assertIn("ingest", out.getvalue())


# ------------------------------------------- 6. Integrations: visitor IDs

class IntegrationsVisitorIds(IntegrationsBase):
    def test_the_note_reads_the_sites_settings_row(self):
        from auth_support import A
        self.assertFalse(self.get().json["script"]["visitor_ids"])
        db = self.db()
        try:
            store.put(db, f"site:{A}", "beacon.visitor_ids", True, "cli")
        finally:
            db.close()
        self.assertTrue(self.get().json["script"]["visitor_ids"])


if __name__ == "__main__":
    unittest.main()
