"""Sites made from the dashboard: the site_config rows, multisite loading
them, Settings > Sites (sites_api.py) and `skald site list|add|purge`."""
from __future__ import annotations

import io
import json
import sys
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402
from auth_support import A, B, SAME  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import accounts, multisite  # noqa: E402
from skald.accounts import apitokens, auditlog, site_configs  # noqa: E402
from skald.config import site_name  # noqa: E402

T = f"/traffic/{A}/"


class Rows(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")

    def test_create_validates_and_owns(self):
        got = site_configs.create(self.db, self.org["id"], "Shop.Example.COM", "7",
                                  timezone="Europe/London", fmt="caddy_json")
        self.assertEqual(got["name"], "shop.example.com")
        self.assertEqual(got["hosts"], ["shop.example.com"])
        self.assertEqual(accounts.org_of_site(self.db, "shop.example.com")["id"], self.org["id"])
        self.assertIn("site.add", self.audit_actions(self.org["id"]))
        for bad in ("", "nodot", "a b.example", "../x.example", "x.example:8080", "data"):
            with self.subTest(bad), self.assertRaises(ValueError):
                site_configs.create(self.db, self.org["id"], bad, "cli")
        with self.assertRaises(ValueError):
            site_configs.create(self.db, self.org["id"], "shop.example.com", "cli")
        with self.assertRaises(ValueError):
            site_configs.create(self.db, self.org["id"], "taken.example", "cli",
                                taken=["taken.example"])
        with self.assertRaises(ValueError):
            site_configs.create(self.db, self.org["id"], "f.example", "cli", fmt="weird")
        with self.assertRaises(ValueError):
            site_configs.create(self.db, self.org["id"], "z.example", "cli", timezone="Mars/X")

    def test_remove_then_purge(self):
        site_configs.create(self.db, self.org["id"], "shop.example.com", "cli")
        token = apitokens.create(self.db, self.org["id"], "ship", sites=["shop.example.com"],
                                 scopes=("ingest",))
        with self.assertRaises(ValueError):
            site_configs.purge(self.db, "shop.example.com", "cli")      # still active
        other = accounts.create_org(self.db, "Other", "cli")
        with self.assertRaises(ValueError):
            site_configs.remove(self.db, other["id"], "shop.example.com", "cli")
        site_configs.remove(self.db, self.org["id"], "shop.example.com", "cli")
        self.assertEqual(site_configs.active(self.db), [])
        self.assertIsNotNone(accounts.org_of_site(self.db, "shop.example.com"))   # data kept
        got = site_configs.purge(self.db, "shop.example.com", "cli")
        self.assertEqual(got["tokens_revoked"], 1)
        self.assertIsNone(accounts.org_of_site(self.db, "shop.example.com"))
        ok, _, _ = apitokens.check(self.db, f"Bearer {token}", "shop.example.com", "ingest")
        self.assertFalse(ok)

    def test_as_config(self):
        entry = site_configs.create(self.db, self.org["id"], "shop.example.com", "cli",
                                    timezone="UTC", views=[{"name": "Blog",
                                                            "path_prefix": "/blog/"}])
        over = site_configs.as_config(entry, "/srv/ingest/shop.example.com")
        self.assertEqual(over["logs"], {"dir": "/srv/ingest/shop.example.com",
                                        "base": "access.log", "format": "auto"})
        self.assertEqual(over["report"], {"timezone": "UTC"})
        self.assertEqual(over["dashboard"]["views"][0]["name"], "Blog")


class Loading(AccountsCase):
    """multisite.site_configs adds the active dashboard sites."""

    def config(self, **extra):
        cfg = {"site": {"name": "main.example", "hosts": ["main.example"]},
               "history": {"db": str(self.dir / "history.sqlite")},
               "mail": {"host": "smtp.example.com", "from": "a@example.com",
                        "to": ["owner@example.com"]},
               "leads": {"forms": ["/contact"]}, "pagespeed": {"urls": ["/"]},
               "beacon": {"enabled": True, "origins": ["https://main.example"]}, **extra}
        path = self.dir / "config.yml"
        path.write_text(json.dumps(cfg))
        return cfg, path

    def test_no_accounts_file_means_nothing_changes(self):
        self.db.close()
        (self.dir / "accounts.sqlite").unlink()
        cfg, path = self.config()
        self.assertEqual(multisite.site_configs(cfg, path), [])
        self.assertFalse((self.dir / "accounts.sqlite").exists())
        self.db = accounts.connect(self.path)

    def test_dashboard_sites_are_loaded_without_the_first_sites_people(self):
        org = accounts.create_org(self.db, "Org", "cli")
        site_configs.create(self.db, org["id"], "shop.example.com", "cli", fmt="caddy_json")
        site_configs.create(self.db, org["id"], "gone.example.com", "cli")
        site_configs.remove(self.db, org["id"], "gone.example.com", "cli")
        cfg, path = self.config()
        got = multisite.site_configs(cfg, path)
        self.assertEqual([site_name(c) for c in got], ["shop.example.com"])
        shop = got[0]
        self.assertEqual(shop["logs"]["format"], "caddy_json")
        self.assertEqual(shop["logs"]["dir"], str(self.dir / "ingest" / "shop.example.com"))
        self.assertEqual(shop["mail"]["to"], [])
        self.assertIs(shop["mail"]["daily"], False)
        self.assertEqual(shop["mail"]["host"], "smtp.example.com")   # the install's server
        for gone in ("leads", "pagespeed"):
            self.assertNotIn(gone, shop)
        self.assertNotIn("origins", shop["beacon"])
        self.assertIs(shop["alerts"]["mail"], False)

    def test_a_config_file_site_wins_on_a_name_clash(self):
        org = accounts.create_org(self.db, "Org", "cli")
        site_configs.create(self.db, org["id"], "shop.example.com", "cli")
        (self.dir / "shop.yml").write_text(json.dumps(
            {"site": {"name": "shop.example.com"}, "logs": {"dir": "/var/log/shop"}}))
        cfg, path = self.config(sites=["shop.yml"])
        err = io.StringIO()
        with redirect_stderr(err):
            got = multisite.site_configs(cfg, path)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["logs"]["dir"], "/var/log/shop")
        self.assertIn("skipped", err.getvalue())

    def test_run_daily_contexts_include_dashboard_sites(self):
        from skald import cli
        org = accounts.create_org(self.db, "Org", "cli")
        site_configs.create(self.db, org["id"], "shop.example.com", "cli")
        _, path = self.config()
        seen = []
        with mock.patch.object(cli, "cmd_check", side_effect=lambda ctx: seen.append(
                (ctx.site, str(ctx.live_dir))) or 0):
            args = cli.parser().parse_args(["--config", str(path), "check"])
            args.run = cli.cmd_check
            with mock.patch.object(cli, "parser") as p:
                p.return_value.parse_args.return_value = args
                cli.main([])
        self.assertEqual([s for s, _ in seen], ["main.example", "shop.example.com"])
        self.assertTrue(seen[1][1].endswith("sites/shop.example.com"))


class Api(TenantServer):
    def owner_of_alpha(self):
        return self.session("owner@example.com")

    def test_the_list_shows_only_the_organisations_sites(self):
        cookie, _ = self.owner_of_alpha()
        got = self.call("GET", T + "sites", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual([s["name"] for s in got.json["sites"]], [A])
        self.assertEqual(got.json["sites"][0]["source"], "config")
        self.assertTrue(got.json["can_add"])
        cookie, _ = self.session("bob@example.com")
        got = self.call("GET", f"/traffic/{B}/sites", cookie=cookie)
        self.assertEqual([(s["name"], s["source"]) for s in got.json["sites"]],
                         [(B, "dashboard")])

    def test_add_makes_the_site_a_token_and_the_instructions(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "sites/add", {"host": "Shop.Example.org",
                                          "format": "nginx_combined"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        body = got.json
        self.assertEqual(body["site"], "shop.example.org")
        self.assertTrue(body["token"].startswith("skald_"))
        self.assertIn("/traffic-ingest/shop.example.org", body["ship_command"])
        self.assertIn('data-site="shop.example.org"', body["tag"])
        self.assertEqual(body["log_dir"], str(self.ingest_root / "shop.example.org"))
        db = self.db()
        try:
            self.assertEqual(accounts.org_of_site(db, "shop.example.org")["id"],
                             self.alpha["id"])
            tokens = apitokens.listing(db, self.alpha["id"])
            self.assertEqual(tokens[0]["scopes"], ["ingest"])
            self.assertEqual(tokens[0]["sites"], ["shop.example.org"])
        finally:
            db.close()
        # The token works at once, and multisite now processes the site.
        shipped = self.ship("shop.example.org", body["token"], lines(2))
        self.assertEqual(shipped.status, 200, shipped.json)
        names = [site_name(c) for c in multisite.site_configs(self.config, self.config_path)]
        self.assertIn("shop.example.org", names)
        # The token is shown once: the listing has no secret.
        listed = self.call("GET", T + "sites", cookie=cookie)
        self.assertNotIn(body["token"], listed.raw.decode())

    def test_add_refusals(self):
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(T + "sites/add", {"host": "v.example"}, cookie, csrf).status,
                         403)
        cookie, csrf = self.session("admin@example.com")
        for host, code in ((B, 400), (A, 400), ("bad host", 400)):
            with self.subTest(host):
                self.assertEqual(self.post(T + "sites/add", {"host": host}, cookie,
                                           csrf).status, code)
        self.assertEqual(self.call("POST", T + "sites/add", {"host": "x.example"}, SAME,
                                   cookie=cookie).status, 403)       # no CSRF
        self.assertEqual(self.call("POST", T + "sites/add", {"host": "x.example"},
                                   cookie=cookie, csrf=csrf).status, 403)  # not same-origin
        self.config["ingest"]["enabled"] = False
        got = self.post(T + "sites/add", {"host": "x.example"}, cookie, csrf)
        self.assertEqual(got.status, 403)
        self.assertIn("ingest", got.json["error"])

    def test_the_plan_limit_when_saas_limits_exists(self):
        fake = types.ModuleType("skald.saas.limits")
        fake.can_add_site = lambda db, org_id: (False, "Your plan has room for 1 site.")
        pkg = types.ModuleType("skald.saas")
        pkg.limits = fake
        cookie, csrf = self.session("admin@example.com")
        with mock.patch.dict(sys.modules, {"skald.saas": pkg,
                                           "skald.saas.limits": fake}):
            got = self.post(T + "sites/add", {"host": "x.example"}, cookie, csrf)
            listed = self.call("GET", T + "sites", cookie=cookie)
        self.assertEqual((got.status, got.json["error"]), (403, "Your plan has room for 1 site."))
        self.assertFalse(listed.json["can_add"])

    def test_a_read_only_plan_refuses_every_change_with_402(self):
        fake = types.ModuleType("skald.saas.limits")
        fake.read_only = lambda db, org_id, config: "The plan was cancelled."
        fake.can_add_site = lambda db, org_id, config: (True, "")
        pkg = types.ModuleType("skald.saas")
        pkg.limits = fake
        cookie, csrf = self.session("owner@example.com")
        with mock.patch.dict(sys.modules, {"skald.saas": pkg,
                                           "skald.saas.limits": fake}):
            for route, body in (("sites/add", {"host": "x.example"}),
                                ("sites/token", {"name": A})):
                got = self.post(T + route, body, cookie, csrf)
                self.assertEqual((got.status, got.json["error"]),
                                 (402, "The plan was cancelled."), route)
            self.assertEqual(self.call("GET", T + "sites", cookie=cookie).status, 200)

    def test_remove_is_for_owners_with_the_typed_name(self):
        cookie, csrf = self.session("bob@example.com")
        page = f"/traffic/{B}/"
        self.assertEqual(self.post(page + "sites/remove", {"name": B}, cookie, csrf).status, 400)
        self.assertEqual(self.post(page + "sites/remove", {"name": B, "confirm": "b"}, cookie,
                                   csrf).status, 400)
        got = self.post(page + "sites/remove", {"name": B, "confirm": B}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        names = [site_name(c) for c in multisite.site_configs(self.config, self.config_path)]
        self.assertNotIn(B, names)
        listed = self.call("GET", page + "sites", cookie=cookie)
        self.assertEqual(listed.json["sites"][0]["status"], "removed")
        db = self.db()
        try:
            self.assertIn("site.remove", [e["action"] for e in auditlog.recent(db,
                                                                               self.beta["id"])])
        finally:
            db.close()

    def test_an_admin_may_not_remove_and_config_sites_stay(self):
        cookie, csrf = self.session("admin@example.com")
        self.assertEqual(self.post(T + "sites/remove", {"name": A, "confirm": A}, cookie,
                                   csrf).status, 403)
        cookie, csrf = self.session("owner@example.com")
        got = self.post(T + "sites/remove", {"name": A, "confirm": A}, cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertIn("config", got.json["error"])

    def test_a_new_token_for_a_site(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "sites/token", {"name": A}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.ship(A, got.json["token"], lines(1)).status, 200)
        self.assertEqual(self.post(T + "sites/token", {"name": B}, cookie, csrf).status, 404)

    def test_basic_mode_answers_404(self):
        self.config["access"]["mode"] = "basic"
        self.assertEqual(self.call("GET", T + "sites").status, 404)


class Cli(AccountsCase):
    def run_ti(self, *argv):
        from skald import cli
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--config", str(self.cfg_path), *argv])
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")
        self.cfg_path = self.dir / "config.yml"
        self.cfg_path.write_text(json.dumps({
            "site": {"name": "main.example"}, "history": {"db": str(self.dir / "history.sqlite")},
            "dashboard": {"out": str(self.dir / "www")}, "access": {"mode": "sessions"}}))

    def test_add_list_and_purge(self):
        code, out, err = self.run_ti("site", "add", "shop.example.com", "--org", self.org["slug"])
        self.assertEqual(code, 0, err)
        self.assertTrue((self.dir / "ingest" / "shop.example.com").is_dir())
        code, out, _ = self.run_ti("site", "list")
        self.assertIn("shop.example.com", out)
        self.assertIn("dashboard", out)
        code, _, err = self.run_ti("site", "purge", "shop.example.com", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("still active", err)
        site_configs.remove(self.db, self.org["id"], "shop.example.com", "cli")
        from skald.store import History
        h = History(self.dir / "history.sqlite")
        h.db.execute("INSERT INTO counts (site, day, kind, name, n) VALUES (?,?,?,?,?)",
                     ("shop.example.com", "2026-10-10", "path", "/", 3))
        h.db.execute("INSERT INTO counts (site, day, kind, name, n) VALUES (?,?,?,?,?)",
                     ("main.example", "2026-10-10", "path", "/", 5))
        h.db.commit()
        h.db.close()
        (self.dir / "www" / "shop.example.com" / "data").mkdir(parents=True)
        code, _, err = self.run_ti("site", "purge", "shop.example.com")
        self.assertEqual(code, 2)                                 # no --yes
        code, out, err = self.run_ti("site", "purge", "shop.example.com", "--yes")
        self.assertEqual(code, 0, err)
        h = History(self.dir / "history.sqlite")
        try:
            sites = [r[0] for r in h.db.execute("SELECT site FROM counts")]
        finally:
            h.db.close()
        self.assertEqual(sites, ["main.example"])
        self.assertFalse((self.dir / "www" / "shop.example.com").exists())
        self.assertFalse((self.dir / "ingest" / "shop.example.com").exists())
        self.assertIsNone(site_configs.get(self.db, "shop.example.com"))

    def test_a_config_site_cannot_be_purged(self):
        code, _, err = self.run_ti("site", "purge", "main.example", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("not a dashboard site", err)


if __name__ == "__main__":
    unittest.main()
