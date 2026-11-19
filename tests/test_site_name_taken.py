"""SKALD-38: Add a site says why a name is taken, and what to do, at the first step.

Reported on 18 Nov 2026: adding a site whose name was removed in another
organisation failed at the last step with only "<name> is already a site of
this install." Now every case has its own words (site_configs.why_taken and
taken_words), create() refuses with them (so POST sites/add and the MCP's
add_site do too), and POST sites/name gives them while the address is typed:

  * a config-file site: set up in the server's config;
  * one of your organisations' sites, active: pick it in the site menu;
  * one of yours, removed: removed on <date>, data kept; an owner of its
    organisation may restore it, anyone else asks an owner;
  * another organisation's site (active or removed): in use on this install,
    never naming that organisation; who can move or free it;
  * a name held after a purge: until <date>, and who can allow reuse.

Names are example.com/.org.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402

from skald import accounts, site_verify  # noqa: E402
from skald.accounts import orgs, site_configs, users  # noqa: E402

MINE, THEIRS = "mine.example.org", "theirs.example.org"


class Base(AccountsCase):
    def setUp(self):
        super().setUp()
        self.at("2026-10-21T13:49:00Z")
        self.own = accounts.create_org(self.db, "Ours Ltd", "cli")
        self.other = accounts.create_org(self.db, "Secret Client Co", "cli")
        self.boss = users.create_user(self.db, "boss@example.com", "Boss")["id"]
        self.helper = users.create_user(self.db, "helper@example.com", "Helper")["id"]
        users.add_member(self.db, self.own["id"], self.boss, "owner", "cli")
        users.add_member(self.db, self.own["id"], self.helper, "admin", "cli")
        site_configs.create(self.db, self.own["id"], MINE, "cli")
        site_configs.create(self.db, self.other["id"], THEIRS, "cli")

    def mine(self, uid):
        return [o["id"] for o in orgs.list_orgs(self.db, uid)]


class WhyTaken(Base):
    def test_a_free_name_is_none(self):
        self.assertIsNone(site_configs.why_taken(self.db, "new.example.org", self.mine(self.boss)))

    def test_a_config_file_site(self):
        got = site_configs.why_taken(self.db, "main.example", [], taken=["main.example"])
        self.assertEqual(got["kind"], "config")
        self.assertEqual(site_configs.taken_words("main.example", got),
                         "main.example is set up in the server's config; it can't be added "
                         "from the dashboard.")

    def test_one_of_yours_active(self):
        got = site_configs.why_taken(self.db, MINE, self.mine(self.helper))
        self.assertEqual((got["kind"], got["removed_at"], got["org_id"]),
                         ("yours", None, self.own["id"]))
        self.assertEqual(site_configs.taken_words(MINE, got),
                         f"{MINE} is already one of your sites: pick it in the site menu.")

    def test_one_of_yours_removed_says_when_and_who_restores(self):
        self.at("2026-10-21T14:24:00Z")
        site_configs.remove(self.db, self.own["id"], MINE, "cli")
        got = site_configs.why_taken(self.db, MINE, self.mine(self.helper))
        self.assertEqual((got["kind"], got["removed_at"][:10]), ("yours", "2026-10-21"))
        said = f"{MINE} was removed on 21 Oct 2026; its data is kept."
        self.assertEqual(site_configs.taken_words(MINE, got, owner=True),
                         f"{said} Restore it to collect again.")
        self.assertEqual(site_configs.taken_words(MINE, got),
                         f"{said} Ask an owner to restore it in Settings › Organisation › "
                         "Sites, under Removed sites.")

    def test_another_organisations_site_never_names_it(self):
        for removed in (False, True):
            with self.subTest(removed=removed):
                if removed:
                    site_configs.remove(self.db, self.other["id"], THEIRS, "cli")
                got = site_configs.why_taken(self.db, THEIRS, self.mine(self.boss))
                self.assertEqual(got["kind"], "elsewhere")
                self.assertNotIn("org_id", got, "the other organisation is not handed out")
                words = site_configs.taken_words(THEIRS, got, owner=True)
                self.assertEqual(
                    words, f"{THEIRS} is already in use on this install. Someone who is an "
                    "admin of both organisations can move it to yours (Settings › "
                    "Organisation › Organisations, Move a site here), or the install's "
                    "admin can free it.")
                self.assertNotIn("Secret Client", words)

    def test_a_name_held_after_a_purge(self):
        site_verify.reserve(self.db, "gone.example.org", "cli")
        got = site_configs.why_taken(self.db, "gone.example.org", self.mine(self.boss))
        self.assertEqual(got["kind"], "held")
        self.assertEqual(site_configs.taken_words("gone.example.org", got),
                         site_verify.RESERVED_WORDS.format(name="gone.example.org",
                                                           until=got["until"][:10]))


class CreateRefuses(Base):
    """create() refuses with the case's words (sites/add and the MCP's add_site)."""

    def refused(self, org_id, name, mine=()):
        with self.assertRaises(ValueError) as caught:
            site_configs.create(self.db, org_id, name, "cli", mine=mine)
        return str(caught.exception)

    def test_removed_in_your_own_organisation(self):
        site_configs.remove(self.db, self.own["id"], MINE, "cli")
        self.assertIn("was removed on 21 Oct 2026; its data is kept.",
                      self.refused(self.own["id"], MINE))

    def test_another_organisations_site(self):
        words = self.refused(self.own["id"], THEIRS, mine=self.mine(self.boss))
        self.assertIn("already in use on this install", words)
        self.assertNotIn("Secret Client", words)

    def test_yours_in_another_of_your_organisations(self):
        second = accounts.create_org(self.db, "Second", "cli")
        users.add_member(self.db, second["id"], self.boss, "owner", "cli")
        self.assertIn("already one of your sites",
                      self.refused(second["id"], MINE, mine=self.mine(self.boss)))

    def test_the_held_name_keeps_its_own_words_and_allow_reuse(self):
        site_verify.reserve(self.db, "gone.example.org", "cli")
        self.assertIn("its name is held until", self.refused(self.own["id"], "gone.example.org"))
        site_configs.create(self.db, self.own["id"], "gone.example.org", "cli", allow_reuse=True)


class NameRoute(Base):
    """POST sites/name {host}: the first step's check, before anything is made."""

    def ask(self, uid, host, role="owner"):
        from skald import sites_api
        test, org = self, self.own

        class Ctx:
            db, config, config_path, session = test.db, {}, None, {}

            def __init__(self):
                self.uid, self.org, self.role = uid, org, role

            def ok(self, **body):
                return 200, body

            def no(self, code, error, **extra):
                return code, {"error": error, **extra}

        return sites_api.name_check(Ctx(), {"host": host})

    def test_a_free_name(self):
        self.assertEqual(self.ask(self.boss, "https://New.Example.org/x"),
                         (200, {"site": "new.example.org", "free": True}))

    def test_removed_here_an_owner_may_restore(self):
        site_configs.remove(self.db, self.own["id"], MINE, "cli")
        code, body = self.ask(self.boss, MINE)
        self.assertEqual((code, body["free"], body["kind"], body["restore"]),
                         (200, False, "yours", MINE))
        self.assertIn("Restore it to collect again.", body["words"])
        code, body = self.ask(self.helper, MINE, role="admin")
        self.assertNotIn("restore", body, "only an owner of its organisation restores")
        self.assertIn("Ask an owner to restore it", body["words"])

    def test_removed_in_another_of_your_organisations_names_it(self):
        second = accounts.create_org(self.db, "Second", "cli")
        users.add_member(self.db, second["id"], self.boss, "owner", "cli")
        site_configs.create(self.db, second["id"], "two.example.org", "cli")
        site_configs.remove(self.db, second["id"], "two.example.org", "cli")
        code, body = self.ask(self.boss, "two.example.org")
        self.assertNotIn("restore", body, "Restore acts on the organisation open now")
        self.assertTrue(body["words"].endswith(
            "its data is kept. Switch to Second, then restore it in Settings › Organisation › "
            "Sites, under Removed sites."), body["words"])

    def test_another_organisations_site(self):
        code, body = self.ask(self.boss, THEIRS)
        self.assertEqual((code, body["free"], body["kind"]), (200, False, "elsewhere"))
        self.assertNotIn("restore", body)
        self.assertNotIn("Secret Client", str(body))

    def test_the_router_serves_it_as_a_post(self):
        from skald import sites_api
        m = sites_api.PATH.match("/traffic/example.com/sites/name")
        self.assertEqual(m.group("act"), "sites/name")
        self.assertNotIn("sites/name", sites_api.GETS, "a POST, so same-origin and CSRF apply")
        self.assertIs(sites_api.ROUTES["sites/name"], sites_api.name_check)

    def test_a_bad_address(self):
        code, body = self.ask(self.boss, "not a site")
        self.assertEqual(code, 400)
        self.assertTrue(body["error"])


if __name__ == "__main__":
    unittest.main()
