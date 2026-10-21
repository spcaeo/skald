"""The "Add a site" wizard's progress (accounts/site_setup.py, POST
<page>/sites/setup, connections_api.py): kept per site on the server, the
step to resume at, the badge in Settings > Add or remove sites and on the
site picker, never a token's value, every change in the audit log.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald.accounts import auditlog, site_configs, site_setup  # noqa: E402

NEW = "shop.example.com"


class Progress(TenantServer):
    def add(self, cookie, csrf, host="https://Shop.Example.com/pricing"):
        got = self.post(f"/traffic/{A}/sites/add", {"host": host, "format": "auto", "token": False},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        return got.json

    def listing(self, cookie):
        got = self.call("GET", f"/traffic/{A}/sites", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        return {s["name"]: s for s in got.json["sites"]}

    def test_the_wizard_adds_a_site_without_a_token_and_resumes_where_it_stopped(self):
        cookie, csrf = self.session("admin@example.com")
        made = self.add(cookie, csrf)
        self.assertEqual(made["site"], NEW)                    # a whole link becomes the host
        self.assertIsNone(made["token"])                       # the wizard makes a named one later
        for body in ({"step": 2}, {"step": 3}, {"step": 4, "method": "docker"}):
            got = self.post(f"/traffic/{A}/sites/setup", {"name": NEW, **body}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
        token = self.post(f"/traffic/{A}/tokens/create", {"name": f"Sending logs: {NEW}", "sites": [NEW],
                                                          "scopes": ["ingest"]}, cookie, csrf).json
        got = self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "token_id": token["token"]}, cookie, csrf)
        self.assertEqual(got.json["setup"]["token_id"], token["id"])   # only the id is kept
        row = self.listing(cookie)[NEW]
        self.assertEqual(row["setup"]["step"], 4)
        self.assertEqual(row["setup"]["method"], "docker")
        self.assertFalse(row["setup"]["done"])
        self.assertFalse(row["quiet"])
        self.assertTrue(row["setup"]["verified"])               # no check on this install
        db = self.accounts_db()
        try:
            raw = json.dumps([dict(r) for r in db.execute("SELECT * FROM site_setup")])
            self.assertNotIn(token["token"], raw)
            words = [e["detail"] for e in auditlog.recent(db, self.alpha["id"], action="site.setup")]
        finally:
            db.close()
        self.assertIn("step 4 of 5; docker", words)
        self.assertIn("step 2 of 5", words)

    def test_done_and_then_quiet_for_a_day(self):
        cookie, csrf = self.session("owner@example.com")
        self.add(cookie, csrf, NEW)
        got = self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "step": 5, "done": True}, cookie, csrf)
        self.assertTrue(got.json["setup"]["done"])
        self.assertTrue(self.listing(cookie)[NEW]["quiet"])     # finished, nothing received
        token = self.token(self.alpha, sites=[NEW])
        self.assertEqual(self.ship(NEW, token, lines(3)).status, 200)
        self.assertFalse(self.listing(cookie)[NEW]["quiet"])

    def test_cloudflare_sets_edge_json_only_while_nothing_arrived(self):
        cookie, csrf = self.session("owner@example.com")
        self.add(cookie, csrf, NEW)
        self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "step": 4, "method": "cloudflare"}, cookie, csrf)
        db = self.accounts_db()
        try:
            self.assertEqual(site_configs.get(db, NEW)["format"], "edge_json")
        finally:
            db.close()
        self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "method": "docker"}, cookie, csrf)
        db = self.accounts_db()
        try:
            self.assertEqual(site_configs.get(db, NEW)["format"], "auto")
        finally:
            db.close()

    def test_refusals(self):
        cookie, csrf = self.session("owner@example.com")
        self.add(cookie, csrf, NEW)
        for body, code in (({"name": NEW, "step": 9}, 400), ({"name": NEW, "method": "fax"}, 400),
                           ({"name": B, "step": 2}, 404)):
            self.assertEqual(self.post(f"/traffic/{A}/sites/setup", body, cookie, csrf).status, code, body)
        self.assertEqual(self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "step": 2}, cookie, None).status, 403)
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "step": 2}, cookie, csrf).status, 403)
        self.assertNotIn("setup", self.listing(cookie).get(NEW, {}))   # a viewer sees no progress

    def test_the_site_picker_offers_to_continue(self):
        cookie, csrf = self.session("owner@example.com")
        self.add(cookie, csrf, NEW)
        self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "step": 3}, cookie, csrf)
        listed = [{"name": s, "slug": s, "path": f"{s}/", "views": []} for s in (A, NEW)]
        (self.out / "sites.json").write_text(json.dumps({"schema_version": 1, "sites": listed}))
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertIn("Setup: step 3 of 5, continue", page)
        self.assertIn(f"#settings/sitesadmin?setup={NEW}", page)
        self.assertIn("#settings/sitesadmin?setup=new", page)   # + Add a site opens the wizard
        self.post(f"/traffic/{A}/sites/setup", {"name": NEW, "step": 5, "done": True}, cookie, csrf)
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertIn("No visits yet: test the connection", page)
        self.assertIn(f"?test={NEW}", page)
        cookie, _ = self.session("viewer@example.com")
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertNotIn("test the connection", page)

    def test_the_store_itself(self):
        db = self.accounts_db()
        try:
            self.assertIsNone(site_setup.get(db, A))
            got = site_setup.save(db, self.alpha["id"], A, "cli", step=3, method="script")
            self.assertEqual((got["step"], got["method"], got["done"]), (3, "script", False))
            got = site_setup.save(db, self.alpha["id"], A, "cli", step=5, done=True)
            self.assertEqual((got["step"], got["method"], got["done"]), (5, "script", True))
            with self.assertRaises(ValueError):
                site_setup.save(db, self.beta["id"], A, "cli", step=2)
            self.assertEqual(list(site_setup.for_org(db, self.alpha["id"])), [A])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
