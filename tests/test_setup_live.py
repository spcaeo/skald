"""Add a site's live progress, Check now, and its first two questions (2.43:
setup_live.py, setup_people.py, sites_api.py's sites/add and the named-site
switch, ingest_status.recent, the kit's last words).

  - the organisation: same, another of mine (an owner or admin only), or new
    (made with the site; its maker its owner, so its keys stay valid); people:
    members by id or new addresses, viewer or admin, owner only for a new one;
  - sites/live ticks the checklist; the invites go only once data arrived and
    the domain is verified, never before, once; the maker gets one mail;
  - sites/sendinvites sends them before the data, by hand; the late mail after
    a day, once; a set-up from before 2.43 gets no mail;
  - Check now says plainly what is missing.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import ingest_status, setup_live, setup_people  # noqa: E402
from skald.accounts import apitokens, auditlog, orgs, site_setup  # noqa: E402

T = f"/traffic/{A}/"
NEW = "shop.example.org"


class Recent(unittest.TestCase):
    def test_counts_the_last_fifteen_minutes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            now = 1_800_000_000.0
            ingest_status.accepted(tmp, NEW, 10, 0, "vercel", now=now - 20 * 60)
            ingest_status.accepted(tmp, NEW, 7, 0, "vercel", now=now - 60)
            ingest_status.accepted(tmp, NEW, 5, 0, "vercel", now=now)
            got = ingest_status.recent(tmp, NEW, now)
            self.assertEqual(got["lines"], 12, "the batch 20 minutes ago is not counted")
            self.assertEqual(got["shipper"], "vercel")
            self.assertEqual(got["first_at"], ingest_status._stamp(now - 20 * 60))
            kept = ingest_status.read(tmp, NEW)["minutes"]
            self.assertLessEqual(len(kept), 16, "only the last minutes are kept")


class Verdict(unittest.TestCase):
    F = {"lines": 0, "recent": 0, "newest_at": None, "first_at": None, "shipper": None,
         "events": 0, "arrived": False}

    def test_the_refusal_shown_without_a_press(self):
        """The live view carries the plain reason a newer refusal gave (the old Test
        connection's words), and drops it once newer data was kept."""
        ref = {"at": "2026-10-27T13:25:00Z", "code": 401, "reason": "token", "words": "The sending token is not valid."}
        self.assertEqual(setup_live.refused(ref, self.F), {"words": "The sending token is not valid.", "at": ref["at"]})
        self.assertIsNone(setup_live.refused(ref, {**self.F, "newest_at": "2026-10-27T13:26:00Z"}))
        self.assertIsNone(setup_live.refused(None, self.F))

    def test_no_data_names_the_way(self):
        got = setup_live.verdict({"method": "vercel"}, None, None, self.F, None, NEW)
        self.assertEqual(got["verdict"], "wait")
        self.assertEqual(got["head"], "No data yet.")
        self.assertIn("Usually it starts within 2 minutes after the drain is saved", got["says"])
        self.assertIn(f"/traffic-ingest/{NEW}?format=vercel", got["says"])
        line = {"state": "waiting"}
        self.assertIn("has not opened its line", setup_live.verdict(
            {}, None, line, self.F, None, NEW)["says"])
        report = {"state": "keys_taken", "keys_at": "x", "report": {"hosting": "Netlify"}}
        self.assertIn("Netlify", setup_live.verdict({}, None, report, self.F, None, NEW)["says"])

    def test_receiving_refused_and_unverified(self):
        f = {**self.F, "lines": 40, "recent": 12, "newest_at": "2026-10-27T13:28:00Z",
             "arrived": True}
        got = setup_live.verdict({}, None, None, f, None, NEW)
        self.assertEqual((got["verdict"], got["head"]), ("ok", "Receiving data."))
        self.assertIn("12 lines in the last 15 minutes, the newest at 13:28 UTC", got["says"])
        refused = {"at": "2026-10-27T13:30:00Z", "words": "The token is wrong or was revoked."}
        self.assertEqual(setup_live.verdict({}, None, None, f, refused, NEW)["verdict"], "bad")
        got = setup_live.verdict({}, {"state": "pending"}, None, f, None, NEW)
        self.assertEqual(got["head"], "The domain is not verified yet.")

    def test_steps_in_order(self):
        line = {"state": "keys_taken", "opened_at": "a", "keys_at": "b", "reported_at": "c",
                "report": {"jobs": {"logs": "done"}, "hosting": "Vercel"}}
        f = {**self.F, "lines": 5, "recent": 5, "arrived": True, "shipper": "vercel",
             "first_at": "d"}
        got = setup_live.steps({"done": True, "done_at": "e", "people": [{"email": "x"}]},
                               None, line, f)
        self.assertEqual([s["id"] for s in got],
                         ["opened", "keys", "road", "data", "verified", "done", "invites"])
        self.assertEqual(got[2]["words"], "Data road set up: Vercel log drain")
        self.assertTrue(all(s["done"] for s in got[:6]))
        self.assertFalse(got[6]["done"], "the invite waits")
        self.assertEqual(setup_live.state_of({"done": False}, f), "receiving")


class Wizard(TenantServer):
    def setUp(self):
        super().setUp()
        self.mail_on()
        self.cookie, self.csrf = self.session("owner@example.com")

    def post_(self, act, body):
        return self.post(T + act, body, self.cookie, self.csrf)

    def add(self, **more):
        return self.post_("sites/add", {"host": NEW, "token": False, **more})

    def audit(self, org_id):
        db = self.accounts_db()
        try:
            return [e["action"] for e in auditlog.recent(db, org_id, 100)]
        finally:
            db.close()

    def row(self):
        db = self.accounts_db()
        try:
            return site_setup.get(db, NEW)
        finally:
            db.close()

    def test_a_new_organisation_is_made_with_the_site(self):
        got = self.add(org="new", org_name="Fieldcamp", privacy_class="client",
                       people=[{"email": "ana@example.com", "role": "owner"},
                               {"user": self.uids["viewer@example.com"], "role": "viewer"}])
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["org"]["name"], "Fieldcamp")
        self.assertTrue(got.json["org"]["new"])
        db = self.accounts_db()
        try:
            org = orgs.org_of_site(db, NEW)
            self.assertEqual(org["name"], "Fieldcamp", "there from the start: nothing moves")
            from skald.accounts import users
            self.assertEqual(users.role_in(db, self.uids["owner@example.com"], org["id"]), "owner")
            self.assertTrue(apitokens.creator_ok(db, org["id"], self.uids["owner@example.com"]))
            self.assertEqual(orgs.privacy_class(db, org["id"]), "client")
        finally:
            db.close()
        row = self.row()
        self.assertEqual(row["privacy_class"], "client")
        self.assertEqual(row["made_by"], str(self.uids["owner@example.com"]))
        self.assertEqual(len(row["people"]), 2)
        self.assertIn("org.create", self.audit(org["id"]))
        self.assertIn("org.privacy", self.audit(org["id"]))
        self.assertEqual(self.sent, [], "nothing is sent when the site is added")
        # The wizard goes on from the page of a site of the old organisation.
        got = self.post_("sites/setup", {"name": NEW, "step": 3, "method": "vercel"})
        self.assertEqual(got.status, 200, got.json)
        got = self.call("GET", T + f"sites?site={NEW}", cookie=self.cookie)
        self.assertEqual([s["name"] for s in got.json["sites"]], [NEW])
        self.assertEqual(got.json["org"], "Fieldcamp")

    def test_refusals(self):
        beta = self.beta["id"]
        got = self.add(org=str(beta))
        self.assertEqual(got.status, 400)
        self.assertIn("not an owner or admin", got.json["error"])
        got = self.add(people=[{"email": "ana@example.com", "role": "owner"}])
        self.assertEqual(got.status, 400, "an owner only for a new organisation")
        got = self.add(people=[{"user": self.uids["bob@example.com"], "role": "viewer"}])
        self.assertEqual(got.status, 400, "Bob is Beta's, not this organisation's")
        got = self.add(org="new", org_name="", privacy_class="internal")
        self.assertEqual(got.status, 400)
        db = self.accounts_db()
        try:
            self.assertIsNone(orgs.org_of_site(db, NEW), "a refusal makes nothing")
            self.assertEqual(len(orgs.list_orgs(db)), 2, "no organisation half made")
        finally:
            db.close()
        viewer = self.session("viewer@example.com")
        got = self.post(T + "sites/live", {"site": A}, *viewer)
        self.assertEqual(got.status, 403, "an owner or admin only")

    def test_invites_go_once_data_arrives(self):
        self.assertEqual(self.add(people=[{"email": "ana@example.com", "role": "viewer"}]).status,
                         200)
        got = self.post_("sites/live", {"site": NEW})
        self.assertEqual(got.status, 200, got.json)
        live = got.json["live"]
        self.assertEqual(live["state"], "waiting")
        ids = [s["id"] for s in live["steps"]]
        self.assertEqual(ids, ["road", "data", "verified", "done", "invites"])
        self.assertEqual(self.sent, [], "never before the data")
        check = self.post_("sites/check", {"site": NEW}).json["check"]
        self.assertEqual((check["verdict"], check["head"]), ("wait", "No data yet."))
        token = self.token(self.alpha, sites=[NEW])
        self.assertEqual(self.ship(NEW, token, lines(30)).status, 200)
        live = self.post_("sites/live", {"site": NEW}).json["live"]
        self.assertEqual(live["state"], "done")
        self.assertEqual(live["recent"], 30)
        got = {s["id"]: s for s in live["steps"]}
        self.assertTrue(got["data"]["done"] and got["done"]["done"] and got["invites"]["done"])
        self.assertEqual(live["invites_words"], "Invites sent to 1 person.")
        to = sorted(t for t, _ in self.sent)
        self.assertEqual(to, ["ana@example.com", "owner@example.com"])
        invite = next(m for t, m in self.sent if t == "ana@example.com")
        self.assertIn(f"{NEW} is live, 30 requests so far.", str(invite.get_body(("plain",))))
        maker = next(m for t, m in self.sent if t == "owner@example.com")
        self.assertTrue(maker["Subject"].endswith(f"{NEW} is live. Invites sent to 1 person."))
        self.post_("sites/live", {"site": NEW})
        self.assertEqual(len(self.sent), 2, "once")
        self.assertIn("setup.invites", self.audit(self.alpha["id"]))
        self.assertEqual(self.post_("sites/check", {"site": NEW}).json["check"]["verdict"], "ok")
        every = self.post_("sites/live", {"all": True}).json["sites"]
        self.assertEqual(every[NEW]["state"], "done")

    def test_invites_see_this_site_only_or_every_site(self):
        """Master's site access (invites.sites): in an existing organisation the people see
        this site only unless "every site" was chosen; an owner always sees every site."""
        got = self.add(people=[{"email": "ana@example.com", "role": "viewer"},
                               {"email": "cy@example.com", "role": "admin", "sees": "all"}])
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual([p["sees"] for p in self.row()["people"]], ["site", "all"])
        got = self.post_("sites/whofor", {"site": NEW, "people": [
            {"email": "dee@example.com", "role": "viewer", "sees": "some"}]})
        self.assertEqual(got.status, 400, "sees is site or all")
        token = self.token(self.alpha, sites=[NEW])
        self.assertEqual(self.ship(NEW, token, lines(5)).status, 200)
        self.assertEqual(self.post_("sites/live", {"site": NEW}).json["live"]["state"], "done")
        from skald.accounts import invites
        db = self.accounts_db()
        try:
            waiting = {i["email"]: i["sites"] for i in invites.pending(db, self.alpha["id"])}
        finally:
            db.close()
        self.assertEqual(waiting, {"ana@example.com": [NEW], "cy@example.com": None})
        ana = next(m for t, m in self.sent if t == "ana@example.com")
        self.assertIn(f"as viewer of {NEW} only", str(ana.get_body(("plain",))))
        cy = next(m for t, m in self.sent if t == "cy@example.com")
        self.assertIn("as admin. ", str(cy.get_body(("plain",))))

    def test_a_new_organisation_sees_every_site(self):
        got = self.add(org="new", org_name="Fieldcamp", privacy_class="internal",
                       people=[{"email": "ana@example.com", "role": "viewer"},
                               {"email": "bo@example.com", "role": "owner", "sees": "site"},
                               {"email": "cy@example.com", "role": "admin", "sees": "site"}])
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual([p["sees"] for p in self.row()["people"]], ["all", "all", "site"],
                         "every site by default in a new organisation; an owner always")

    def test_send_by_hand_and_the_late_mail(self):
        self.add(people=[{"email": "ana@example.com", "role": "admin"}])
        db = self.accounts_db()
        try:
            started = site_setup.get(db, NEW)["started_at"]
            from skald.accounts import db as base
            later = base.parse(started).timestamp() + 25 * 3600
            heard = lambda: (0, False)   # noqa: E731
            self.assertEqual(setup_people.tick(db, self.config, NEW, "https://x.example", heard,
                                               lambda: "No data yet.", now=later), "late")
            self.assertIsNone(setup_people.tick(db, self.config, NEW, "https://x.example", heard,
                                                lambda: "", now=later), "one late mail")
        finally:
            db.close()
        self.assertEqual([t for t, _ in self.sent], ["owner@example.com"])
        self.assertIn("is not set up yet", self.sent[0][1]["Subject"])
        got = self.post_("sites/sendinvites", {"site": NEW})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["invites"]["sent"], 1)
        self.assertIn("ana@example.com", [t for t, _ in self.sent])

    def test_a_setup_from_before_gets_no_mail(self):
        db = self.accounts_db()
        try:
            site_setup.save(db, self.alpha["id"], A, "cli", step=5, done=True)
            self.assertIsNone(setup_people.tick(db, self.config, A, None, lambda: (9, True)))
        finally:
            db.close()
        self.assertEqual(self.sent, [])

    def test_who_will_use_it(self):
        got = self.call("GET", T + "sites/whoopts", cookie=self.cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["org"]["name"], "Alpha")
        self.assertEqual(got.json["orgs"], [], "the owner is in no other organisation as admin")
        self.assertEqual(sorted(m["email"] for m in got.json["members"]),
                         ["admin@example.com", "owner@example.com", "viewer@example.com"])
        self.add()
        got = self.post_("sites/whofor", {"site": NEW, "people": [
            {"email": "Ana@Example.com", "role": "viewer"}]})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["setup"]["people"], [{"email": "ana@example.com",
                                                         "role": "viewer", "sees": "site"}])

    def test_the_agent_says_who_gets_an_invite(self):
        self.add(people=[{"email": "ana@example.com", "role": "viewer"}])
        got = self.post_("sites/agentlink", {"site": NEW})
        self.assertEqual(got.status, 200, got.json)
        code = re.search(r"use code ([A-Za-z0-9_-]{43}) ", got.json["line"]).group(1)
        from skald.kit import agent
        entry = agent.find(self.live, code)
        text = agent.steps(entry, code, "https://www.example.com")
        self.assertIn('"Done. ana@example.com will get an invite as soon as the first data '
                      'arrives."', text)


class NginxRoutes(unittest.TestCase):
    def test_the_new_routes_reach_the_helper(self):
        text = (Path(__file__).resolve().parent.parent / "DEPLOY.md").read_text()
        rule = re.search(r"\|sites\(\?:/\[a-z\]\+\)\?\|", text)
        self.assertIsNotNone(rule, "DEPLOY.md's sessions block passes sites/<letters>")
        for act in setup_live.ROUTES:
            self.assertRegex(act, r"^sites/[a-z]+$")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Page(unittest.TestCase):
    """tests/js/setup-live.mjs: the polling, the done state, Check now, the two questions and
    the address (ids only, never an email)."""

    def test_live_panel_and_questions(self):
        root = Path(__file__).resolve().parent.parent
        done = subprocess.run(["node", str(root / "tests" / "js" / "setup-live.mjs")], capture_output=True,
                              text=True, timeout=120, cwd=root)
        self.assertEqual(done.returncode, 0, done.stderr[-4000:])
        self.assertIn("setup-live: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
