"""SKALD-42: one person named on several sites' set-ups gets every one of them.

Reported on 19 Nov 2026: three sites added the same morning each named the
same person, "this site only". Each invite deleted the one before (one open
invite per address and organisation), so only the last site's link worked and
the person joined seeing one site of three. Now:

  * an invite from Add a site (setup_people.send, `add=True`) adds its site to
    the open invite: every open link of that address gets the same sites (the
    union; every site when one of them said so) and the strongest role, and
    stays valid; accepting one uses them all up;
  * an invite typed by an admin (Settings, the CLI) still replaces the open one,
    as before, and the answer says so (`replaced`): its sites are the ones
    chosen, and the earlier link no longer works;
  * someone already in the organisation but limited to some sites gets the new
    site added (members.sites) instead of being skipped;
  * Settings › Organisation › People shows each member's sites, and an admin
    changes them there (POST team/access).

Names are example.com/.org.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import GOOD_PW, AccountsCase  # noqa: E402
from auth_support import A, Server  # noqa: E402

from skald import accounts, setup_people  # noqa: E402
from skald.accounts import invites, site_configs, site_setup, users  # noqa: E402

ONE, TWO, THREE = "one.example.org", "two.example.org", "three.example.org"
NEW = "new@example.com"
T = f"/traffic/{A}/"


class Base(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Ours", "cli")
        self.boss = users.create_user(self.db, "boss@example.com", "Boss")
        users.add_member(self.db, self.org["id"], self.boss["id"], "owner", "cli")
        for name in (ONE, TWO, THREE):
            site_configs.create(self.db, self.org["id"], name, "cli")

    def sites_of(self, email):
        user = users.find_user(self.db, email=email)
        return users.site_access(self.db, self.org["id"], user["id"])

    def open_rows(self, email=NEW):
        return self.db.execute("SELECT role, sites FROM invites WHERE email = ? AND "
                               "used_at IS NULL ORDER BY created_at", (email,)).fetchall()


class AddingInvites(Base):
    def invite(self, sites, role="viewer", add=True):
        return invites.invite(self.db, self.org["id"], NEW, role, self.boss["id"],
                              sites=sites, add=add)

    def test_three_sites_one_person_every_link_works_and_gives_all_three(self):
        links = [self.invite([s]) for s in (ONE, TWO, THREE)]
        for link in links:
            self.assertIsNotNone(invites.invite_info(self.db, link), "every link still works")
        waiting = invites.pending(self.db, self.org["id"])
        self.assertEqual([(p["email"], p["sites"]) for p in waiting],
                         [(NEW, sorted([ONE, TWO, THREE]))], "listed once, with all three")
        got = invites.accept(self.db, links[0], "New", GOOD_PW)
        self.assertEqual(self.sites_of(NEW), sorted([ONE, TWO, THREE]))
        self.assertEqual(got["role"], "viewer")
        for link in links[1:]:
            with self.assertRaisesRegex(ValueError, "already used"):
                invites.accept(self.db, link, "New", GOOD_PW)
        self.assertEqual(invites.pending(self.db, self.org["id"]), [])

    def test_the_last_link_works_as_well_as_the_first(self):
        links = [self.invite([s]) for s in (ONE, TWO)]
        invites.accept(self.db, links[-1], "New", GOOD_PW)
        self.assertEqual(self.sites_of(NEW), sorted([ONE, TWO]))

    def test_every_site_wins(self):
        self.invite([ONE])
        self.invite(None)
        link = self.invite([TWO])
        invites.accept(self.db, link, "New", GOOD_PW)
        self.assertIsNone(self.sites_of(NEW), "one set-up said every site")

    def test_the_strongest_role_wins(self):
        self.invite([ONE], role="admin")
        link = self.invite([TWO], role="viewer")
        self.assertEqual([r[0] for r in self.open_rows()], ["admin", "admin"])
        got = invites.accept(self.db, link, "New", GOOD_PW)
        self.assertEqual(got["role"], "admin")

    def test_the_audit_says_the_sites_added_up(self):
        self.invite([ONE])
        self.invite([TWO])
        got = self.db.execute("SELECT detail FROM audit WHERE action = 'invite.send' "
                              "ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertEqual(got, f"viewer; only {ONE}, {TWO}; added to the open invite")

    def test_an_expired_invite_is_not_added_to(self):
        self.invite([ONE])
        self.tick(invites.INVITE_DAYS * 86400 + 1)
        link = self.invite([TWO])
        invites.accept(self.db, link, "New", GOOD_PW)
        self.assertEqual(self.sites_of(NEW), [TWO])

    def test_a_typed_invite_still_replaces_the_open_one(self):
        first = self.invite([ONE, TWO])
        self.assertEqual(invites.open_invite(self.db, self.org["id"], NEW)["sites"],
                         sorted([ONE, TWO]))
        second = self.invite([THREE], add=False)
        self.assertIsNone(invites.invite_info(self.db, first), "the earlier link is gone")
        invites.accept(self.db, second, "New", GOOD_PW)
        self.assertEqual(self.sites_of(NEW), [THREE], "an admin may narrow it")
        self.assertIsNone(invites.open_invite(self.db, self.org["id"], NEW))


class SetupSends(Base):
    def setup_for(self, site, people):
        site_setup.save(self.db, self.org["id"], site, self.boss["id"])
        site_setup.note(self.db, site, people=people, made_by=str(self.boss["id"]))

    def send(self, site):
        real, self.links = invites.invite, getattr(self, "links", [])

        def keep(*args, **kw):
            self.links.append(real(*args, **kw))
            return self.links[-1]
        with mock.patch.object(invites, "invite", keep):
            return setup_people.send(self.db, {}, site, "https://www.example.com", "skald")

    def limited_maker(self, site):
        """A set-up made by an admin who sees only ONE."""
        maker = users.create_user(self.db, "lim@example.com", "Lim")
        users.add_member(self.db, self.org["id"], maker["id"], "admin", "cli", sites=[ONE])
        site_setup.save(self.db, self.org["id"], site, maker["id"])
        return maker

    def test_the_maker_never_widens_themselves(self):
        maker = self.limited_maker(TWO)
        site_setup.note(self.db, TWO, made_by=str(maker["id"]), people=[
            {"user": maker["id"], "role": "admin", "sees": "all"},
            {"email": "lim@example.com", "role": "admin", "sees": "all"}])
        got = self.send(TWO)
        self.assertEqual((got["added"], got["skipped"]), (0, 2))
        self.assertEqual(self.sites_of("lim@example.com"), [ONE])

    def test_a_maker_on_some_sites_gives_this_site_never_every_site(self):
        maker = self.limited_maker(TWO)
        ana = users.create_user(self.db, "ana@example.com", "Ana")
        users.add_member(self.db, self.org["id"], ana["id"], "viewer", "cli", sites=[THREE])
        site_setup.note(self.db, TWO, made_by=str(maker["id"]),
                        people=[{"user": ana["id"], "role": "viewer", "sees": "all"}])
        self.send(TWO)
        self.assertEqual(self.sites_of("ana@example.com"), sorted([TWO, THREE]))

    def test_three_set_ups_name_the_same_address(self):
        for site in (ONE, TWO, THREE):
            self.setup_for(site, [{"email": NEW, "role": "viewer", "sees": "site"}])
            self.send(site)
        rows = self.open_rows()
        self.assertEqual(len(rows), 3, "no link was deleted")
        self.assertEqual(len(self.links), 3)
        invites.accept(self.db, self.links[0], "New", GOOD_PW)      # the first mail's link
        self.assertEqual(self.sites_of(NEW), sorted([ONE, TWO, THREE]))

    def test_a_member_limited_to_one_site_gets_the_new_one(self):
        ana = users.create_user(self.db, "ana@example.com", "Ana")
        users.add_member(self.db, self.org["id"], ana["id"], "viewer", "cli", sites=[ONE])
        self.setup_for(TWO, [{"user": ana["id"], "role": "viewer", "sees": "site"}])
        got = self.send(TWO)
        self.assertEqual((got["added"], got["skipped"]), (1, 0))
        self.assertEqual(self.sites_of("ana@example.com"), sorted([ONE, TWO]))
        self.assertEqual(users.role_in(self.db, ana["id"],
                                       self.org["id"]), "viewer", "the role is not changed")
        self.assertIn("member.sites", self.audit_actions(self.org["id"]))

    def test_named_by_address_too(self):
        ana = users.create_user(self.db, "ana@example.com", "Ana")
        users.add_member(self.db, self.org["id"], ana["id"], "admin", "cli", sites=[ONE])
        self.setup_for(THREE, [{"email": "ana@example.com", "role": "viewer", "sees": "all"}])
        got = self.send(THREE)
        self.assertEqual(got["added"], 1)
        self.assertIsNone(self.sites_of("ana@example.com"), "the set-up said every site")
        self.assertEqual(users.role_in(self.db, ana["id"], self.org["id"]), "admin")

    def test_one_who_sees_every_site_already_is_skipped(self):
        ana = users.create_user(self.db, "ana@example.com", "Ana")
        users.add_member(self.db, self.org["id"], ana["id"], "viewer", "cli")
        self.setup_for(TWO, [{"user": ana["id"], "role": "viewer", "sees": "site"}])
        got = self.send(TWO)
        self.assertEqual((got["added"], got["skipped"]), (0, 1))
        self.assertIsNone(self.sites_of("ana@example.com"), "never narrowed by a set-up")


class TeamPage(Server):
    """Settings › Organisation › People: each member's sites, and Change."""

    def limited_viewer(self, sites):
        db = self.db()
        try:
            users.set_site_access(db, self.alpha["id"], self.uids["viewer@example.com"], sites,
                                  "cli")
        finally:
            db.close()

    def add_site(self, name):
        db = self.db()
        try:
            accounts.assign_site(db, name, self.alpha["id"], "cli")
        finally:
            db.close()

    def test_the_team_lists_each_members_sites(self):
        self.add_site("more.example")
        self.limited_viewer([A])
        cookie, _ = self.session()
        got = {m["email"]: m["sites"] for m in self.call("GET", T + "team",
                                                          cookie=cookie).json["members"]}
        self.assertEqual(got, {"owner@example.com": None, "admin@example.com": None,
                               "viewer@example.com": [A]})

    def test_an_admin_changes_them(self):
        self.add_site("more.example")
        self.limited_viewer([A])
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "team/access", {"email": "viewer@example.com",
                                           "sites": [A, "more.example"]}, cookie, csrf)
        self.assertEqual((got.status, got.json.get("sites")), (200, [A, "more.example"]),
                         got.json)
        got = self.post(T + "team/access", {"email": "viewer@example.com", "sites": None},
                        cookie, csrf)
        self.assertEqual((got.status, got.json["sites"]), (200, None))

    def test_refusals(self):
        self.add_site("more.example")
        cookie, csrf = self.session("viewer@example.com")
        got = self.post(T + "team/access", {"email": "admin@example.com", "sites": [A]},
                        cookie, csrf)
        self.assertEqual(got.status, 403, "a viewer changes nothing")
        cookie, csrf = self.session("admin@example.com")
        for body, code in (({"email": "admin@example.com", "sites": [A]}, 400),
                           ({"email": "owner@example.com", "sites": [A]}, 400),
                           ({"email": "viewer@example.com", "sites": ["beta.example"]}, 400),
                           ({"email": "viewer@example.com", "sites": []}, 400),
                           ({"email": "nobody@example.com", "sites": [A]}, 404)):
            with self.subTest(body=body):
                self.assertEqual(self.post(T + "team/access", body, cookie, csrf).status, code)

    def test_a_reader_on_some_sites_sees_only_those_names_and_changes_none(self):
        """A limited admin is shown other members' sites cut to their own, and may
        not change them: a Save from their shorter list would drop the rest."""
        self.add_site("more.example")
        db = self.db()
        try:
            users.set_site_access(db, self.alpha["id"], self.uids["admin@example.com"], [A], "cli")
            users.set_site_access(db, self.alpha["id"], self.uids["viewer@example.com"],
                                  ["more.example"], "cli")
        finally:
            db.close()
        cookie, csrf = self.session("admin@example.com")
        got = self.call("GET", T + "team", cookie=cookie).json
        viewer = next(m for m in got["members"] if m["email"] == "viewer@example.com")
        self.assertEqual((viewer["sites"], viewer["more"]), ([], True),
                         "more.example is not named to them, only that there is more")
        self.assertNotIn("more.example", str(got))
        self.assertIs(got["may_sites"], False)
        got = self.post(T + "team/access", {"email": "viewer@example.com", "sites": [A]},
                        cookie, csrf)
        self.assertEqual(got.status, 403)
        owner, _ = self.session()
        self.assertIs(self.call("GET", T + "team", cookie=owner).json["may_sites"], True)

    def limit(self, email, sites):
        db = self.db()
        try:
            users.set_site_access(db, self.alpha["id"], self.uids[email], sites, "cli")
        finally:
            db.close()

    def test_pending_invites_name_only_the_readers_sites(self):
        self.add_site("more.example")
        db = self.db()
        try:
            invites.invite(db, self.alpha["id"], NEW, "viewer", "cli", sites=[A])
            invites.invite(db, self.alpha["id"], NEW, "viewer", "cli", sites=["more.example"],
                           add=True)
        finally:
            db.close()
        self.limit("admin@example.com", [A])
        cookie, _ = self.session("admin@example.com")
        got = self.call("GET", T + "team", cookie=cookie).json
        self.assertEqual([(i["sites"], i.get("more")) for i in got["invites"]], [([A], True)])
        self.assertNotIn("more.example", str(got))

    def test_the_organisations_drawer_hides_them_too(self):
        self.add_site("more.example")
        self.limit("viewer@example.com", ["more.example"])
        self.limit("admin@example.com", [A])
        db = self.db()
        try:
            invites.invite(db, self.alpha["id"], NEW, "viewer", "cli", sites=["more.example"])
        finally:
            db.close()
        for who, page in (("admin@example.com", T), ("viewer@example.com",
                                                     "/traffic/more.example/")):
            with self.subTest(who=who):
                cookie = self.login(who).cookie
                got = self.call("GET", page + f"orgs/show?org={self.alpha['id']}", cookie=cookie)
                self.assertEqual(got.status, 200, got.json)
                hidden = "more.example" if who == "admin@example.com" else A
                self.assertNotIn(hidden, str(got.json["members"]) + str(got.json["invites"]))
        cookie, csrf = self.session("admin@example.com")
        got = self.call("GET", T + f"orgs/show?org={self.alpha['id']}", cookie=cookie).json
        self.assertIs(got["may"]["sites_access"], False, "a limited admin changes no access")
        got = self.post(T + "orgs/member/sites", {"org": self.alpha["id"],
                                                  "user": self.uids["viewer@example.com"],
                                                  "sites": [A]}, cookie, csrf)
        self.assertEqual(got.status, 403)

    def test_a_resend_in_the_drawer_is_not_called_a_replacement(self):
        cookie, csrf = self.session()
        self.post(T + "orgs/member/invite", {"org": self.alpha["id"], "email": NEW,
                                             "role": "viewer"}, cookie, csrf)
        got = self.post(T + "orgs/invite/resend", {"org": self.alpha["id"], "email": NEW},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertNotIn("replaced", got.json)

    def test_a_typed_invite_says_it_replaced_the_open_one(self):
        cookie, csrf = self.session("admin@example.com")
        body = {"email": NEW, "role": "viewer"}
        first = self.post(T + "team/invite", body, cookie, csrf).json
        self.assertNotIn("replaced", first)
        again = self.post(T + "team/invite", body, cookie, csrf).json
        self.assertIs(again["replaced"], True)

    def test_the_organisations_drawer_says_so_too(self):
        cookie, csrf = self.session("admin@example.com")
        body = {"org": self.alpha["id"], "email": NEW, "role": "viewer", "sites": [A]}
        first = self.post(T + "orgs/member/invite", body, cookie, csrf)
        self.assertEqual(first.status, 200, first.json)
        self.assertNotIn("replaced", first.json)
        again = self.post(T + "orgs/member/invite", body, cookie, csrf).json
        self.assertIs(again["replaced"], True)


class PeoplePage(unittest.TestCase):
    """The page itself (tests/js/team-sites.mjs): the Sites column, Change, and the
    words of an invite that replaced an open one."""

    def test_the_sites_column_and_change(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        js = Path(__file__).resolve().parent / "js" / "team-sites.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ))
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertIn("team-sites: ok", done.stdout)


if __name__ == "__main__":
    unittest.main()
