"""The MCP tools that add a site and watch its set-up (2.44,
skald/mcp/tools_addsite.py), the token scope `add_sites`
(accounts/apitokens.py) and the one code path they share with POST sites/add
(site_add.py), on a real helper with two organisations (alpha.example,
beta.example; ingest_support.TenantServer).

Pinned: the scope is for the whole organisation, owner/admin-made, with mcp;
add_site adds into the token's own organisation through site_add.add and is
refused by exactly what refuses the dashboard (the plan's sites and members, a
read-only organisation), with no limit for an organisation without a plan;
wrong scope, a revoked token, a demoted or limited maker are refused; a token
of one organisation cannot touch another's site; site_progress and check_site
answer as sites/live and sites/check do; Check now's limit is counted per
token; add_site and send_invites write audit rows with no code, token or
address. RFC 5737 addresses, example.com mail."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_support import A, B, ORIGIN  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import kit_api, setup_live, site_add  # noqa: E402
from skald.accounts import apitokens, orgs, site_setup  # noqa: E402
from skald.mcp import tools  # noqa: E402
from skald.mcp.data import Context  # noqa: E402
from skald.saas import plans  # noqa: E402

NEW = "shop.example.org"
LINE = ("finish setting up Skald for shop.example.org (Logs, Script tag) - read "
        "https://www.example.com/traffic-kit/llms.txt and use code k1w1-c0de (works once, "
        "24 hours)")
PLANS = {"tiny": {"sites": 1, "members": 3}, "team": {"sites": 5, "members": 4}}


def rpc(name, args):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": args}}


class AddSite(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["mcp"] = {"enabled": True}
        self.config.setdefault("hooks", {})["test_url"] = "http://127.0.0.1:9"
        self.mail_on()
        self.owner = self.uids["owner@example.com"]
        self.lines_made = []
        fake = mock.patch.object(kit_api, "make_agent_line", self._line)
        fake.start()
        self.addCleanup(fake.stop)

    def _line(self, db, config, org, site, jobs, actor, **kw):
        self.lines_made.append({"org": org["id"], "site": site, "jobs": jobs, "actor": actor})
        return {"line": LINE, "llms_url": f"{ORIGIN}/traffic-kit/llms.txt",
                "steps_url": f"{ORIGIN}/traffic-kit/k1w1-c0de/steps",
                "expires_at": "2026-10-12T14:00:00Z", "token_id": "0a1b2c3d",
                "link_id": "0123456789abcdef", "cancelled": 0, "jobs": jobs}

    # ------------------------------------------------------------ helpers

    def make(self, scopes=("mcp", "add_sites"), sites=None, actor=None, org=None):
        db = self.db()
        try:
            return apitokens.create(db, (org or self.alpha)["id"], "agent", sites=sites,
                                    scopes=scopes, actor=self.owner if actor is None else actor)
        finally:
            db.close()

    def mcp(self, token, name, args):
        return self.call("POST", "/traffic-mcp", body=rpc(name, args),
                         headers={"Authorization": f"Bearer {token}"})

    def result(self, token, name, args) -> dict:
        got = self.mcp(token, name, args)
        self.assertEqual(got.status, 200, got.json)
        return got.json["result"]

    def ok(self, token, name, args) -> dict:
        got = self.result(token, name, args)
        self.assertFalse(got.get("isError"), got)
        return got

    def refused(self, token, name, args, words):
        got = self.result(token, name, args)
        self.assertTrue(got.get("isError"), got)
        self.assertIn(words, got["content"][0]["text"])
        return got["content"][0]["text"]

    def audit(self, action):
        db = self.db()
        try:
            return [dict(r) for r in db.execute(
                "SELECT actor, target, detail FROM audit WHERE action = ?", (action,))]
        finally:
            db.close()

    def org_of(self, site):
        db = self.db()
        try:
            got = orgs.org_of_site(db, site)
            return got["id"] if got else None
        finally:
            db.close()

    def saas(self, plan=None, status="active", org=None):
        self.config["saas"] = {"enabled": True, "plans": PLANS, "default_plan": "team"}
        if plan:
            db = self.db()
            try:
                plans.set_plan(db, (org or self.alpha)["id"], plan, status, "cli")
            finally:
                db.close()

    # ------------------------------------------------------------ the scope

    def test_the_scope_is_for_the_whole_organisation_owner_or_admin_made_with_mcp(self):
        db = self.db()
        try:
            for kw, words in (({"sites": [A]}, "leave the sites out"),
                              ({"scopes": ("add_sites",)}, "give it the mcp scope too"),
                              ({"actor": self.uids["viewer@example.com"]}, "owner or admin")):
                args = {"sites": None, "scopes": ("mcp", "add_sites"), "actor": self.owner, **kw}
                with self.assertRaises(ValueError) as no:
                    apitokens.create(db, self.alpha["id"], "agent", **args)
                self.assertIn(words, str(no.exception))
            db.execute("UPDATE members SET sites = ? WHERE user_id = ?",
                       (json.dumps([A]), self.uids["admin@example.com"]))
            with self.assertRaises(ValueError) as no:
                apitokens.create(db, self.alpha["id"], "agent", scopes=("mcp", "add_sites"),
                                 actor=self.uids["admin@example.com"])
            self.assertIn("who sees every site", str(no.exception))
            token = apitokens.create(db, self.alpha["id"], "agent", scopes=("mcp", "add_sites"),
                                     actor=self.owner)
            entry = apitokens.listing(db, self.alpha["id"])[0]
            self.assertEqual((entry["sites"], entry["scopes"]), (None, ["mcp", "add_sites"]))
            ok, _, got = apitokens.check_org(db, f"Bearer {token}")
            self.assertTrue(ok)
            self.assertEqual(got["org_id"], self.alpha["id"])
        finally:
            db.close()

    # ------------------------------------------------------------ add_site

    def test_add_site_adds_into_the_tokens_organisation_with_its_people(self):
        token = self.make()
        got = self.ok(token, "add_site", {"host": NEW, "people": [
            {"email": "ana@example.com", "role": "viewer"},
            {"email": "ben@example.com", "role": "admin", "sees": "all"}]})
        data = got["structuredContent"]
        self.assertEqual(data["site"], NEW)
        self.assertEqual(data["dashboard"], f"{ORIGIN}/traffic/{NEW}/")
        self.assertEqual((data["state"], data["people"], data["line"]), ("waiting", 2, LINE))
        self.assertEqual(data["jobs"], ["logs", "script", "lead"])
        self.assertEqual(self.org_of(NEW), self.alpha["id"])
        self.assertEqual(self.lines_made, [{"org": self.alpha["id"], "site": NEW,
                                            "jobs": ["logs", "script", "lead"],
                                            "actor": self.owner}])
        db = self.db()
        try:
            row = site_setup.get(db, NEW)
            self.assertEqual(row["made_by"], str(self.owner))
            self.assertEqual([(p["email"], p["role"], p["sees"]) for p in row["people"]],
                             [("ana@example.com", "viewer", "site"),
                              ("ben@example.com", "admin", "all")])
            self.assertEqual([t for t in apitokens.listing(db, self.alpha["id"])
                              if "ingest" in t["scopes"]], [], "no ingest token over MCP")
        finally:
            db.close()
        self.assertIn(LINE, got["content"][0]["text"])
        self.assertIn("2 people get an invite mail once the first data arrives",
                      got["content"][0]["text"])
        self.assertEqual(self.sent, [], "nothing is mailed when the site is added")
        rows = self.audit("mcp.add_site")
        self.assertEqual(len(rows), 1)
        tid = token.split("_", 2)[1]
        self.assertEqual((rows[0]["actor"], rows[0]["target"]), (str(self.owner), NEW))
        self.assertIn(f"token {tid}; 2 people; jobs logs,script,lead; link 0123456789abcdef",
                      rows[0]["detail"])
        dump = json.dumps(rows)
        for secret in (token, "k1w1", "ana@example.com"):
            self.assertNotIn(secret, dump)
        # A name already taken is refused as the dashboard refuses it.
        self.refused(token, "add_site", {"host": NEW}, "already a site of this install")

    def test_the_dashboard_and_the_tool_share_one_code_path(self):
        cookie, csrf = self.session("owner@example.com")
        with mock.patch.object(site_add, "add", side_effect=site_add.Refused(403, "One door.")):
            got = self.post(f"/traffic/{A}/sites/add", {"host": NEW}, cookie, csrf)
            self.assertEqual((got.status, got.json["error"]), (403, "One door."))
            self.refused(self.make(), "add_site", {"host": NEW}, "One door.")

    def test_a_beta_token_adds_into_beta_only(self):
        token = self.make(org=self.beta, actor=self.uids["bob@example.com"])
        self.ok(token, "add_site", {"host": NEW, "jobs": ["logs"]})
        self.assertEqual(self.org_of(NEW), self.beta["id"])
        self.assertEqual(self.lines_made[0]["jobs"], ["logs"])
        # Alpha's member is not Beta's to name.
        self.refused(token, "add_site", {"host": "two.example.org",
                                         "people": [{"user": self.uids["viewer@example.com"]}]},
                     "not one of your organisation's")

    def test_bad_people_and_jobs_are_refused_and_nothing_is_made(self):
        token = self.make()
        self.refused(token, "add_site", {"host": NEW, "people": [{"email": "x@example.com",
                                                                  "role": "owner"}]},
                     "An owner can only be named for a new organisation")
        self.refused(token, "add_site", {"host": NEW, "people": [{"email": "a@example.com"}] * 21},
                     "At most 20 people")
        self.refused(token, "add_site", {"host": NEW, "jobs": ["countries"]},
                     "Not a job an AI agent can do")
        self.refused(token, "add_site", {"host": "not a host"}, "")
        self.assertIsNone(self.org_of(NEW))
        self.assertEqual(self.audit("mcp.add_site"), [])
        self.assertEqual(self.lines_made, [])

    # ------------------------------------------------------------ the plan

    def test_the_plans_sites_limit_refuses_as_the_dashboard_does(self):
        self.saas("tiny")
        words = self.refused(self.make(), "add_site", {"host": NEW}, "The tiny plan allows 1 site")
        self.assertIn("Settings > Billing", words)
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/add", {"host": NEW, "token": False}, cookie, csrf)
        self.assertEqual((got.status, got.json["error"]), (403, words))
        self.assertIsNone(self.org_of(NEW))

    def test_the_plans_members_limit_counts_new_people(self):
        self.saas("team")        # 4 members; alpha has owner, admin and viewer
        token = self.make()
        words = self.refused(token, "add_site", {"host": NEW, "people": [
            {"email": "ana@example.com"}, {"email": "ben@example.com"}]},
            "The team plan allows 4 members")
        self.assertIn("this organisation has 3 and the site names 2 new", words)
        self.assertIsNone(self.org_of(NEW), "nothing is made")
        # The dashboard refuses the same.
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/add", {"host": NEW, "token": False, "people": [
            {"email": "ana@example.com"}, {"email": "ben@example.com"}]}, cookie, csrf)
        self.assertEqual((got.status, got.json["error"]), (400, words))
        # A member already in it is no new seat; one new person fits.
        got = self.ok(token, "add_site", {"host": NEW, "people": [
            {"email": "viewer@example.com"}, {"email": "ana@example.com"}]})
        self.assertEqual(got["structuredContent"]["state"], "pending")

    def test_a_read_only_organisation_is_refused(self):
        self.saas("team", status="canceled")
        token = self.make()
        self.refused(token, "add_site", {"host": NEW}, "read-only")
        self.refused(token, "site_progress", {"site": A}, "read-only")
        self.refused(token, "check_site", {"site": A}, "read-only")
        self.assertIsNone(self.org_of(NEW))

    def test_an_organisation_with_no_plan_has_no_limit(self):
        self.saas()              # saas on, alpha without a plan (a family project)
        token = self.make()
        for n in range(4):
            got = self.ok(token, "add_site", {"host": f"s{n}.example.org", "people": [
                {"email": f"p{n}@example.com"}, {"email": f"q{n}@example.com"}]})
            data = got["structuredContent"]
            self.assertEqual(data["state"], "pending", "saas: the domain is verified first")
            self.assertTrue(data["verify"]["txt"])
            self.assertIn("Nothing is collected until the domain is verified",
                          got["content"][0]["text"])

    # ------------------------------------------------------------ who may

    def test_wrong_scope_revoked_and_demoted_tokens_are_refused(self):
        self.refused(self.make(("mcp",), sites=[A]), "add_site", {"host": NEW},
                     "needs a token with the add_sites scope")
        self.refused(self.make(("mcp", "setup"), sites=[A]), "add_site", {"host": NEW},
                     "this token has no add_sites scope")
        self.assertEqual(self.mcp(self.make(("read",)), "add_site", {"host": NEW}).status, 401)
        token = self.make()
        db = self.db()
        try:
            apitokens.revoke(db, self.alpha["id"], token, "cli")
        finally:
            db.close()
        self.assertEqual(self.mcp(token, "add_site", {"host": NEW}).status, 401)
        admin = self.make(actor=self.uids["admin@example.com"])
        db = self.db()
        try:
            db.execute("UPDATE members SET sites = ? WHERE user_id = ?",
                       (json.dumps([A]), self.uids["admin@example.com"]))
        finally:
            db.close()
        self.refused(admin, "add_site", {"host": NEW}, "for the whole organisation")
        db = self.db()
        try:
            db.execute("UPDATE members SET sites = NULL, role = 'viewer' WHERE user_id = ?",
                       (self.uids["admin@example.com"],))
        finally:
            db.close()
        self.assertEqual(self.mcp(admin, "add_site", {"host": NEW}).status, 401)
        self.assertIsNone(self.org_of(NEW))
        got = tools.call(Context(None), "add_site", {"host": NEW})
        self.assertIn("This connection has no token", got["content"][0]["text"])

    def test_a_token_of_one_organisation_cannot_touch_anothers_site(self):
        token = self.make()
        for name in ("site_progress", "check_site", "send_invites"):
            with self.subTest(tool=name):
                self.refused(token, name, {"site": B}, f"Watching {B}'s set-up needs")
                self.refused(token, name, {"site": "nowhere.example.org"},
                             "Watching nowhere.example.org's set-up needs")
        # A setup token for its one site may watch it, not another.
        setup = self.make(("mcp", "setup"), sites=[A])
        self.ok(setup, "site_progress", {"site": A})
        self.refused(self.make(("mcp",), sites=[A]), "site_progress", {"site": A},
                     "Watching")

    # ------------------------------------------------------------ watching

    def test_progress_and_check_answer_as_sites_live_and_sites_check(self):
        token = self.make()
        self.ok(token, "add_site", {"host": NEW, "people": [{"email": "ana@example.com"}]})
        cookie, csrf = self.session("owner@example.com")
        page = self.post(f"/traffic/{A}/sites/live", {"site": NEW}, cookie, csrf).json["live"]
        got = self.ok(token, "site_progress", {"site": NEW})
        live = got["structuredContent"]
        self.assertEqual(sorted(live), sorted(page))
        self.assertEqual({k: v for k, v in live.items() if k != "now"},
                         {k: v for k, v in page.items() if k != "now"})
        self.assertEqual(live["state"], "waiting")
        self.assertIn(f"{NEW}: waiting for its first data.", got["content"][0]["text"])
        self.assertIn("- First data received: not yet.", got["content"][0]["text"])
        check = self.ok(token, "check_site", {"site": NEW})["structuredContent"]
        page = self.post(f"/traffic/{A}/sites/check", {"site": NEW}, cookie, csrf).json
        self.assertEqual(check["check"], page["check"])
        self.assertEqual((check["check"]["verdict"], check["check"]["head"]),
                         ("wait", "No data yet."))
        # Data arrives: done, and the invites go (once) with the live run's words.
        shipper = self.token(self.alpha, sites=[NEW])
        self.assertEqual(self.ship(NEW, shipper, lines(30)).status, 200)
        got = self.ok(token, "site_progress", {"site": NEW})
        self.assertEqual(got["structuredContent"]["state"], "done")
        self.assertIn("30 lines kept so far", got["content"][0]["text"])
        self.assertEqual(sorted(t for t, _ in self.sent), ["ana@example.com", "owner@example.com"])
        check = self.ok(token, "check_site", {"site": NEW})["structuredContent"]["check"]
        self.assertEqual((check["verdict"], check["head"]), ("ok", "Receiving data."))

    def test_check_now_is_limited_per_token(self):
        one, two = self.make(), self.make()
        with mock.patch.object(setup_live, "CHECK_PER_HOUR", 2):
            self.ok(one, "check_site", {"site": A})
            self.ok(one, "check_site", {"site": A})
            self.refused(one, "check_site", {"site": A}, "Too many checks with this token (2 an hour)")
            self.ok(two, "check_site", {"site": A})

    def test_send_invites_mails_now_once_and_is_audited(self):
        token = self.make()
        self.ok(token, "add_site", {"host": NEW, "people": [{"email": "ana@example.com"}]})
        got = self.ok(token, "send_invites", {"site": NEW})
        self.assertEqual(got["structuredContent"]["invites"]["sent"], 1)
        self.assertIn("Invites sent to 1 person.", got["content"][0]["text"])
        self.assertIn("ana@example.com", [t for t, _ in self.sent])
        again = self.ok(token, "send_invites", {"site": NEW})
        self.assertIn("went already", again["content"][0]["text"])
        rows = self.audit("mcp.send_invites")
        tid = token.split("_", 2)[1]
        self.assertEqual([r["detail"] for r in rows],
                         [f"token {tid}; 1 invited, 0 added, 0 skipped, 0 not mailed",
                          f"token {tid}; already sent"])
        self.assertNotIn("ana@example.com", json.dumps(rows))


if __name__ == "__main__":
    unittest.main()
