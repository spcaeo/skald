"""Tenant isolation: organisation Alpha can neither read nor change anything
of organisation Beta, through every route the helper answers.

Alpha owns alpha.example, the config file's own site; Beta owns beta.example,
a site made from the dashboard (ingest_support.TenantServer). Each has its
own people. Every check below is made as Alpha's owner (an admin with every
right in Alpha) against Beta, and most also the other way round, so a rule
that only happens to hold for one kind of site is caught. Addresses are
RFC 5737; hosts example.com/.example.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, SAME  # noqa: E402
from conversions_support import FakeHandler  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import accounts  # noqa: E402
from skald.accounts import apitokens, auditlog, site_configs  # noqa: E402

ALPHA, BETA = "owner@example.com", "bob@example.com"
SECRET_A, SECRET_B = "alpha-hook-secret-not-real", "beta-hook-secret-not-real"


class Isolation(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["mcp"] = {"enabled": True}
        listed = {"schema_version": 1, "sites": [{"name": A, "slug": A, "path": f"{A}/"},
                                                 {"name": B, "slug": B, "path": f"{B}/"}],
                  "current": None}
        (self.out / "sites.json").write_text(json.dumps(listed))
        for s in (A, B):
            (self.out / s / "data" / "sites.json").write_text(json.dumps({**listed,
                                                                           "current": s}))
        self.a = self.session(ALPHA)
        self.b = self.session(BETA)

    def other(self, me):
        """(my site, their site, my cookie+csrf, their org) for a direction."""
        return (A, B, self.a, self.beta) if me == "alpha" else (B, A, self.b, self.alpha)

    def directions(self):
        return ("alpha", "beta")

    # ------------------------------------------------- static files (nginx)

    def test_the_session_check_refuses_the_other_organisations_files(self):
        for me in self.directions():
            mine, theirs, (cookie, _), _ = self.other(me)
            with self.subTest(me):
                self.assertEqual(self.check(f"/traffic/{mine}/data/overview.json",
                                            cookie).status, 200)
                tricky = [
                    (f"/traffic/{theirs}/", None),
                    (f"/traffic/{theirs}/data/overview.json", None),
                    (f"/traffic/{theirs}/data/requests.json", None),
                    (f"/traffic/{theirs.upper()}/data/overview.json", None),
                    (f"/traffic/_app/%2e%2e/{theirs}/data/overview.json",
                     f"/traffic/{theirs}/data/overview.json"),
                    (f"/traffic/{mine}/../{theirs}/data/overview.json",
                     f"/traffic/{theirs}/data/overview.json"),
                    (f"/traffic/{mine}/%2e%2e/{theirs}/", f"/traffic/{theirs}/"),
                    (f"/traffic//{theirs}/data/overview.json",
                     f"/traffic/{theirs}/data/overview.json"),
                    (f"/traffic/{mine}/data/overview.json",
                     f"/traffic/{theirs}/data/overview.json"),      # the two forms differ
                    (f"/traffic/sites.json/../{theirs}/", f"/traffic/{theirs}/"),
                    (f"/traffic/{theirs}\\data/overview.json", None),
                ]
                for uri, normalised in tricky:
                    got = self.check(uri, cookie, normalised)
                    self.assertIn(got.status, (401, 403), uri)
                    self.assertIsNone(got.header("X-Skald-User"), uri)

    # ------------------------------------------- the helper's /traffic/ routes

    def test_every_read_route_of_the_other_site_is_refused(self):
        reads = ["me", "team", "account", "tokens", "audit", "settings",
                 "settings/audit", "settings/retention-preview?key=report.retention_days&"
                 "value=30", "sites", "api/v1/", "api/v1/overview", "api/v1/requests",
                 "api/compare?a=2026-10-01..2026-10-07&b=2026-10-08..2026-10-10",
                 "api/page?path=/", "funnels", "ours", "bot-policy", "data/sites.json"]
        for me in self.directions():
            _, theirs, (cookie, _), _ = self.other(me)
            for route in reads:
                with self.subTest(me=me, route=route):
                    got = self.call("GET", f"/traffic/{theirs}/{route}", cookie=cookie)
                    self.assertIn(got.status, (403, 404), got.raw[:200])
                    self.assertNotIn(theirs.encode(), got.raw.replace(
                        b"You are not a member here.", b""))

    def test_every_write_route_of_the_other_site_is_refused(self):
        writes = {
            "refresh": {}, "ours/add": {"ip": "192.0.2.1", "label": "x"},
            "ours/remove": {"ip": "192.0.2.1"}, "funnels/save": {"name": "x", "steps": []},
            "funnels/delete": {"name": "x"}, "bot-policy": {},
            "team/invite": {"email": "mallory@example.com", "role": "owner"},
            "team/role": {"email": BETA, "role": "viewer"}, "team/remove": {"email": BETA},
            "tokens/create": {"name": "steal", "scopes": ["read"]},
            "tokens/revoke": {"id": "x"},
            "settings/save": {"report.retention_days": 30},
            "settings/test-mail": {"to": "mallory@example.com"},
            "sites/add": {"host": "evil.example"}, "sites/token": {"name": B},
            "sites/remove": {"name": B, "confirm": B},
        }
        for me in self.directions():
            _, theirs, (cookie, csrf), _ = self.other(me)
            for route, body in writes.items():
                with self.subTest(me=me, route=route):
                    got = self.post(f"/traffic/{theirs}/{route}", body, cookie, csrf)
                    self.assertIn(got.status, (403, 404, 405), (route, got.raw[:200]))
        db = self.db()
        try:
            self.assertEqual(apitokens.listing(db, self.beta["id"]), [])
            self.assertEqual(apitokens.listing(db, self.alpha["id"]), [])
            self.assertEqual(accounts.role_in(db, self.uids[BETA], self.beta["id"]), "owner")
            self.assertTrue(site_configs.get(db, B)["active"])
            self.assertIsNone(site_configs.get(db, "evil.example"))
        finally:
            db.close()
        self.assertEqual(self.runner.calls, [])

    def test_own_routes_cannot_reach_into_the_other_organisation(self):
        cookie, csrf = self.a
        t = f"/traffic/{A}/"
        # A token for Beta's site, made from Alpha's page.
        got = self.post(t + "tokens/create", {"name": "x", "sites": [B], "scopes": ["read"]},
                        cookie, csrf)
        self.assertEqual(got.status, 400)
        # Revoking Beta's token from Alpha's page.
        b_token = self.token(self.beta, scopes=("read",), sites=[B])
        tid = b_token.split("_")[1]
        got = self.post(t + "tokens/revoke", {"id": tid}, cookie, csrf)
        self.assertIn(got.status, (400, 404))
        self.assertEqual(self.call("GET", f"/traffic-api/v1/{B}/overview",
                                   headers={"Authorization": f"Bearer {b_token}"}).status, 200)
        # Beta's member through Alpha's team page.
        for route, body in (("team/role", {"email": BETA, "role": "viewer"}),
                            ("team/remove", {"email": BETA})):
            self.assertEqual(self.post(t + route, body, cookie, csrf).status, 404)
        # Beta's site through Alpha's Sites page.
        for route, body in (("sites/remove", {"name": B, "confirm": B}),
                            ("sites/token", {"name": B})):
            self.assertEqual(self.post(t + route, body, cookie, csrf).status, 404)
        got = self.post(t + "sites/add", {"host": B}, cookie, csrf)
        self.assertEqual(got.status, 400)
        db = self.db()
        try:
            self.assertEqual(accounts.org_of_site(db, B)["id"], self.beta["id"])
        finally:
            db.close()

    def test_lists_show_only_the_callers_own(self):
        cookie, csrf = self.a
        t = f"/traffic/{A}/"
        self.post(f"/traffic/{B}/settings/save", {"report.retention_days": 40}, *self.b)
        got = self.call("GET", t + "team", cookie=cookie)
        self.assertNotIn(BETA, got.raw.decode())
        got = self.call("GET", t + "audit", cookie=cookie)
        self.assertEqual({e["org_id"] for e in got.json["entries"]} - {self.alpha["id"], None},
                         set())
        got = self.call("GET", t + "settings/audit", cookie=cookie)
        self.assertNotIn(B, json.dumps(got.json))
        got = self.call("GET", t + "sites", cookie=cookie)
        self.assertEqual([s["name"] for s in got.json["sites"]], [A])
        got = self.call("GET", t + "tokens", cookie=cookie)
        self.assertEqual(got.json["tokens"], [])
        for path in ("/traffic/sites.json", f"/traffic/{A}/data/sites.json"):
            got = self.call("GET", path, cookie=cookie)
            self.assertEqual([s["name"] for s in got.json["sites"]], [A], path)
        got = self.call("GET", "/traffic/", cookie=cookie)
        self.assertNotIn(B, got.raw.decode())
        got = self.call("GET", "/traffic/sites.json", cookie=self.b[0])
        self.assertEqual([s["name"] for s in got.json["sites"]], [B])

    # ----------------------------------------------------------- tokens

    def test_a_token_reads_and_ships_only_its_own_organisations_sites(self):
        for me in self.directions():
            mine, theirs, _, _ = self.other(me)
            org = self.alpha if me == "alpha" else self.beta
            with self.subTest(me):
                read = self.token(org, scopes=("read", "read_private"))
                auth = {"Authorization": f"Bearer {read}"}
                self.assertEqual(self.call("GET", f"/traffic-api/v1/{mine}/overview",
                                           headers=auth).status, 200)
                for name in ("overview", "requests"):
                    got = self.call("GET", f"/traffic-api/v1/{theirs}/{name}", headers=auth)
                    self.assertEqual(got.status, 401)
                    self.assertNotIn(b'"site"', got.raw)
                ship = self.token(org)
                self.assertEqual(self.ship(theirs, ship, lines(2)).status, 403)
                self.assertEqual(self.ship(mine, ship, lines(2), batch=f"{me}:1").status, 200)
                # A read token cannot ship, an ingest token cannot read.
                self.assertEqual(self.ship(mine, read, lines(1), batch=f"{me}:2").status, 403)
                self.assertEqual(self.call("GET", f"/traffic-api/v1/{mine}/overview",
                                           headers={"Authorization": f"Bearer {ship}"}).status,
                                 401)
        self.assertEqual(self.stored(A).count(b"\n"), 2)
        self.assertEqual(self.stored(B).count(b"\n"), 2)

    def test_mcp_tools_read_only_the_tokens_organisation(self):
        token = self.token(self.alpha, scopes=("mcp",))

        def tool(name, **args):
            body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": name, "arguments": args}}
            got = self.call("POST", "/traffic-mcp", body,
                            {"Authorization": f"Bearer {token}"})
            self.assertEqual(got.status, 200, got.raw[:300])
            return got.json["result"]
        listed = tool("list_sites")
        self.assertNotIn(B, json.dumps(listed))
        for name in ("overview", "top_pages", "ai_activity", "leads", "breakdown",
                     "live_today", "data_quality", "site_health"):
            with self.subTest(name):
                got = tool(name, site=B, **({"dimension": "country"}
                                            if name == "breakdown" else {}))
                self.assertIs(got["isError"], True)
                self.assertIn("may not read", got["content"][0]["text"])

    # -------------------------------------------------------- tool hooks

    def test_a_hook_signed_for_one_site_is_refused_for_the_other(self):
        from skald.conversions import secrets_store
        from skald.conversions.adapters import adapter
        from skald.conversions.hooks import Receiver
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            gamma = folder / "gamma.yml"
            gamma.write_text(json.dumps({"site": {"name": "gamma.example"}}))
            config = {**self.config, "sites": [str(gamma)],
                      "history": {"db": str(self.live / "history.sqlite")},
                      "hooks": {"per_minute": 600, "burst": 100}}
            path = secrets_store.path_for(config, self.live)
            secrets_store.put(path, secrets_store.key(A, "lead"), SECRET_A)
            secrets_store.put(path, secrets_store.key(B, "lead"), SECRET_B)
            now = 1791720000                       # 2026-10-11 12:00 UTC
            rx = Receiver(config, self.live, config_path=self.config_path, clock=lambda: now)

            def post(site, secret):
                body = json.dumps({"external_ref": "L-1", "action": "demo"}).encode()
                p = f"/traffic-hooks/{site}/lead"
                headers = {"Host": "www.example.com", "X-Forwarded-Proto": "https",
                           **adapter("lead").sign(body, secret, now, "POST",
                                                  "https://www.example.com" + p)}
                return rx.http(FakeHandler(p, body, headers))[0]
            self.assertEqual(post(A, SECRET_A), 200)       # the right secret works
            self.assertEqual(post(B, SECRET_A), 401)
            self.assertEqual(post(A, SECRET_B), 401)
            self.assertEqual(post("other.example", SECRET_A), 404)

    # ------------------------------------------------------------ the record

    def test_the_audit_log_files_each_change_under_its_own_organisation(self):
        cookie, csrf = self.a
        self.post(f"/traffic/{A}/sites/add", {"host": "shop.example.org"}, cookie, csrf)
        db = self.db()
        try:
            beta_rows = auditlog.recent(db, self.beta["id"])
        finally:
            db.close()
        self.assertNotIn("shop.example.org", json.dumps(beta_rows))

    def test_without_a_session_nothing_is_answered(self):
        for path in (f"/traffic/{B}/sites", f"/traffic/{B}/me", f"/traffic/{B}/api/v1/overview",
                     "/traffic/sites.json"):
            self.assertEqual(self.call("GET", path).status, 401, path)
        got = self.call("POST", f"/traffic/{B}/sites/add", {"host": "x.example"}, SAME)
        self.assertEqual(got.status, 401)


if __name__ == "__main__":
    unittest.main()
