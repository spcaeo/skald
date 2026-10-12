"""The accounts commands (cli_accounts.py): `accounts init|status`, `org`,
`member`, `account`, `site assign`, and `token` in sessions mode.

Run through skald's own parser and Context (support.Sandbox). Addresses
are example.com; no real secret anywhere.
"""
from __future__ import annotations

import json
import re
import unittest
from unittest import mock

from support import Sandbox

from skald import accounts, cli_accounts
from skald import tokens as old_tokens
from skald.accounts import apitokens, auditlog

BASE = "https://stats.example.com"
OWNER = "owner@example.com"
GOOD_PW = "correct horse battery staple"


class Case(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.addCleanup(self.box.close)
        quiet = mock.patch.object(cli_accounts, "_interactive", return_value=False)
        quiet.start()                                     # never wait on a terminal
        self.addCleanup(quiet.stop)
        (self.box.root / "shop.yml").write_text(
            "site:\n  name: shop.example\n  hosts: [shop.example]\n"
            "logs:\n  base: shop.log\n")
        self.box.config.write_text(self.box.config.read_text() + "sites:\n  - shop.yml\n")
        self.users_json({"morgan": "admin", "sam": "viewer", "bob": "viewer"})
        self.path = self.box.root / "accounts.sqlite"

    def users_json(self, roles: dict) -> None:
        (self.box.root / "users.json").write_text(json.dumps(
            {"users": {n: {"role": r} for n, r in roles.items()}}))

    def run_ti(self, *argv):
        return self.box.run(*argv)

    def init(self, *extra):
        return self.run_ti("accounts", "init", "--org", "Example Co", "--owner-email", OWNER,
                           "--base-url", BASE, "--map", "morgan=morgan@example.com",
                           "--map", "sam=sam@example.com", *extra)

    def db(self):
        db = accounts.connect(self.path)
        self.addCleanup(db.close)
        return db

    def link(self, out: str, kind: str) -> list[str]:
        return re.findall(re.escape(BASE) + rf"/traffic-auth/{kind}\?t=([A-Za-z0-9_-]+)", out)


class TestInit(Case):
    def test_happy_path(self):
        path = old_tokens.path_for({}, self.box.root)
        plain = old_tokens.create(path, "a script")
        shop = old_tokens.create(path, "shop only", sites=["shop.example"], private=True)
        code, out, err = self.init()
        self.assertEqual(code, 0, err)
        db = self.db()
        org = accounts.list_orgs(db)[0]
        self.assertEqual((org["name"], org["slug"]), ("Example Co", "example-co"))
        self.assertEqual(accounts.sites_of_org(db, org["id"]), ["example.com", "shop.example"])
        owner = accounts.find_user(db, email=OWNER)
        self.assertTrue(owner["install_admin"])
        self.assertEqual(accounts.role_in(db, owner["id"], org["id"]), "owner")
        invites = {i["email"]: i["role"] for i in accounts.pending(db, org["id"])}
        self.assertEqual(invites, {"morgan@example.com": "admin", "sam@example.com": "viewer"})
        self.assertIn("bob", out)                         # skipped, and said so
        self.assertIn("no email", out)
        # Tokens: imported with their hashes, still valid, sites honoured.
        ok, why, _ = apitokens.check(db, f"Bearer {plain}", "example.com", name="overview")
        self.assertTrue(ok, why)
        self.assertTrue(apitokens.check(db, f"Bearer {shop}", "shop.example",
                                        name="requests")[0])
        self.assertFalse(apitokens.check(db, f"Bearer {shop}", "example.com")[0])
        # Links: one set-your-password link that works, one invite link each.
        resets = self.link(out, "reset")
        self.assertEqual(len(resets), 1)
        accounts.use_reset(db, resets[0], GOOD_PW)
        self.assertIsNotNone(accounts.authenticate(db, OWNER, GOOD_PW))
        tokens = self.link(out, "invite")
        self.assertEqual(len(tokens), 2)
        info = accounts.invite_info(db, tokens[0])
        self.assertIn(info["email"], invites)
        # Audited, by the CLI.
        actors = {e["actor"] for e in auditlog.recent(db, None)
                  if e["action"] in ("org.create", "site.assign", "invite.send", "token.import")}
        self.assertEqual(actors, {"cli"})

    def test_twice_is_refused_and_force_only_adds(self):
        self.assertEqual(self.init()[0], 0)
        code, out, err = self.init()
        self.assertEqual(code, 1)
        self.assertIn("already", err)
        db = self.db()
        before = len(accounts.pending(db, 1))
        self.users_json({"morgan": "admin", "sam": "viewer", "bob": "viewer"})
        code, out, err = self.init("--force", "--map", "bob=bob@example.com")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(accounts.list_orgs(db)), 1)
        emails = sorted(i["email"] for i in accounts.pending(db, 1))
        self.assertEqual(len(emails), before + 1)
        self.assertIn("bob@example.com", emails)
        self.assertEqual(len(self.link(out, "invite")), 1)    # only the new one

    def test_map_is_needed_without_a_terminal(self):
        code, out, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email", OWNER,
                                     "--base-url", BASE)
        self.assertEqual(code, 0, err)
        self.assertEqual(accounts.pending(self.db(), 1), [])
        for name in ("morgan", "sam", "bob"):
            self.assertIn(name, out)

    def test_asks_for_each_email_on_a_terminal(self):
        answers = iter(["", "morgan@example.com", "sam@example.com"])   # bob, morgan, sam
        with mock.patch.object(cli_accounts, "_interactive", return_value=True), \
                mock.patch("builtins.input", side_effect=lambda _: next(answers)):
            code, out, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email",
                                         OWNER, "--base-url", BASE)
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(i["email"] for i in accounts.pending(self.db(), 1)),
                         ["morgan@example.com", "sam@example.com"])

    def test_bad_map_and_missing_base_url(self):
        code, _, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email", OWNER,
                                   "--base-url", BASE, "--map", "morgan")
        self.assertEqual(code, 2)
        self.assertFalse(self.path.exists())
        # No access.base_url, dashboard.base_url or dashboard.url: no address for links.
        import re
        self.box.config.write_text(re.sub(r"\n  url: [^\n]*", "", self.box.config.read_text()))
        code, _, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email", OWNER)
        self.assertEqual(code, 2)
        self.assertIn("base", err)
        self.assertFalse(self.path.exists())

    def test_dashboard_url_gives_its_scheme_and_host(self):
        code, out, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email", OWNER)
        self.assertEqual(code, 0, err)
        self.assertIn("https://stats.example.com/traffic-auth/reset?t=", out)

    def test_base_url_from_the_config(self):
        self.box.config.write_text(self.box.config.read_text().replace(
            "dashboard:\n", "dashboard:\n  base_url: https://dash.example.com/\n"))
        code, out, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email", OWNER)
        self.assertEqual(code, 0, err)
        self.assertIn("https://dash.example.com/traffic-auth/reset?t=", out)

    def test_access_base_url_comes_first_and_the_flag_overrides_it(self):
        # The same address the helper's mails use (accounts/links.py).
        self.box.config.write_text(self.box.config.read_text().replace(
            "dashboard:\n", "access:\n  base_url: https://auth.example.com/x/\n"
            "dashboard:\n  base_url: https://dash.example.com/\n"))
        code, out, err = self.run_ti("accounts", "init", "--org", "X", "--owner-email", OWNER)
        self.assertEqual(code, 0, err)
        self.assertIn("https://auth.example.com/traffic-auth/reset?t=", out)
        code, out, err = self.run_ti("account", "reset-link", OWNER, "--base-url", BASE)
        self.assertEqual(code, 0, err)
        self.assertIn(f"{BASE}/traffic-auth/reset?t=", out)

    def test_status(self):
        code, out, _ = self.run_ti("accounts", "status")
        self.assertEqual(code, 0)
        self.assertIn("not set up", out)
        self.assertFalse(self.path.exists())              # status never creates the file
        self.init()
        code, out, _ = self.run_ti("accounts", "status")
        self.assertEqual(code, 0)
        self.assertIn("mode: basic", out)
        self.assertIn("Example Co (example-co)", out)
        self.assertIn("1 member", out)
        self.assertIn("2 pending invites", out)
        self.assertIn(f"schema version: {accounts.SCHEMA_VERSION}", out)
        self.assertIn("install admins: 1", out)
        self.assertIn("owners 1", out)
        self.assertIn("sessions: 0", out)


class Ready(Case):
    def setUp(self):
        super().setUp()
        code, self.init_out, err = self.init()
        self.assertEqual(code, 0, err)


class TestOrgAndSite(Ready):
    def test_org_list_create_rename(self):
        self.assertEqual(self.run_ti("org", "create", "Second Org")[0], 0)
        code, out, _ = self.run_ti("org", "rename", "second-org", "Renamed")
        self.assertEqual(code, 0)
        code, out, _ = self.run_ti("org", "list")
        self.assertIn("example-co", out)
        self.assertIn("Renamed", out)
        self.assertEqual(self.run_ti("org", "rename", "nope", "X")[0], 1)

    def test_site_assign(self):
        self.run_ti("org", "create", "Shop Co")
        code, out, err = self.run_ti("site", "assign", "shop.example", "--org", "shop-co")
        self.assertEqual(code, 0, err)
        db = self.db()
        self.assertEqual(accounts.org_of_site(db, "shop.example")["slug"], "shop-co")
        self.assertEqual(self.run_ti("site", "assign", "other.example", "--org", "shop-co")[0], 2)
        self.assertEqual(self.run_ti("site", "assign", "shop.example", "--org", "nope")[0], 1)
        self.assertIn("site.assign", [e["action"] for e in auditlog.recent(db, None)])

    def test_commands_need_init(self):
        self.path.unlink()
        for suffix in ("-wal", "-shm"):
            (self.box.root / f"accounts.sqlite{suffix}").unlink(missing_ok=True)
        code, _, err = self.run_ti("org", "list")
        self.assertEqual(code, 1)
        self.assertIn("accounts init", err)
        self.assertFalse(self.path.exists())


class TestMember(Ready):
    def test_invite_role_remove(self):
        code, out, err = self.run_ti("member", "invite", "new@example.com", "--role", "viewer",
                                     "--base-url", BASE)
        self.assertEqual(code, 0, err)
        token = self.link(out, "invite")[0]
        db = self.db()
        accounts.accept(db, token, "New", GOOD_PW)
        code, out, _ = self.run_ti("member", "list")
        self.assertIn("new@example.com", out)
        self.assertIn("viewer", out)
        self.assertEqual(self.run_ti("member", "role", "new@example.com", "admin")[0], 0)
        user = accounts.find_user(db, email="new@example.com")
        self.assertEqual(accounts.role_in(db, user["id"], 1), "admin")
        self.assertEqual(self.run_ti("member", "remove", "new@example.com")[0], 0)
        self.assertIsNone(accounts.role_in(db, user["id"], 1))
        actions = [e["action"] for e in auditlog.recent(db, 1)]
        for action in ("invite.send", "member.role", "member.remove"):
            self.assertIn(action, actions)

    def test_last_owner_is_kept(self):
        code, _, err = self.run_ti("member", "remove", OWNER)
        self.assertEqual(code, 1)
        self.assertIn("only owner", err)
        code, _, err = self.run_ti("member", "role", OWNER, "viewer")
        self.assertEqual(code, 1)

    def test_remove_cancels_a_pending_invite(self):
        code, out, _ = self.run_ti("member", "remove", "sam@example.com")
        self.assertEqual(code, 0)
        self.assertIn("cancel", out)
        self.assertNotIn("sam@example.com", [i["email"] for i in accounts.pending(self.db(), 1)])

    def test_bad_role_and_unknown_org(self):
        self.assertEqual(self.run_ti("member", "invite", "x@example.com", "--role", "god")[0], 2)
        self.assertEqual(self.run_ti("member", "list", "--org", "nope")[0], 1)
        self.run_ti("org", "create", "Second")
        code, _, err = self.run_ti("member", "list")
        self.assertEqual(code, 2)                         # two orgs: name one
        self.assertIn("--org", err)

    def test_mail_is_sent_when_the_hook_says_so(self):
        sent = []
        with mock.patch.object(cli_accounts, "_mail_invite",
                               side_effect=lambda *a: sent.append(a) or "mail sent"):
            code, out, _ = self.run_ti("member", "invite", "m@example.com", "--role", "viewer",
                                         "--base-url", BASE)
        self.assertEqual(code, 0)
        self.assertEqual(len(sent), 1)
        self.assertIn("mail sent", out)
        self.assertEqual(len(self.link(out, "invite")), 1)    # the link is printed anyway

    def test_invite_mail_goes_through_accounts_mails(self):
        from skald.accounts import mails
        self.box.config.write_text(self.box.config.read_text() + (
            "mail:\n  host: smtp.example.com\n  from: traffic@example.com\n"))
        sent = []
        with mock.patch.object(mails, "deliver", side_effect=lambda m, c, to: sent.append(
                (m["To"], m["Subject"], to))):
            code, out, err = self.run_ti("member", "invite", "m@example.com", "--role",
                                         "admin", "--base-url", BASE)
        self.assertEqual(code, 0, err)
        self.assertEqual(sent, [("m@example.com", "[Skald] You are invited to Example Co",
                                 "m@example.com")])
        self.assertIn("invite mail sent", out)
        with mock.patch.object(mails, "deliver", side_effect=OSError("refused")):
            code, out, _ = self.run_ti("member", "invite", "n@example.com", "--role",
                                       "viewer", "--base-url", BASE)
        self.assertEqual(code, 0)
        self.assertIn("not sent", out)
        self.assertEqual(len(self.link(out, "invite")), 1)


class TestAccount(Ready):
    def test_reset_link_disable_enable_totp_off(self):
        code, out, err = self.run_ti("account", "reset-link", OWNER, "--base-url", BASE)
        self.assertEqual(code, 0, err)
        db = self.db()
        accounts.use_reset(db, self.link(out, "reset")[0], GOOD_PW)
        code, _, err = self.run_ti("account", "disable", OWNER)
        self.assertEqual(code, 1)                         # the only owner stays enabled
        self.assertIn("only owner", err)
        second = accounts.create_user(db, "second@example.com", "Second", GOOD_PW)
        accounts.add_member(db, 1, second["id"], "owner", "cli")
        self.assertEqual(self.run_ti("account", "disable", OWNER)[0], 0)
        self.assertIsNone(accounts.authenticate(db, OWNER, GOOD_PW))
        self.assertEqual(self.run_ti("account", "enable", OWNER)[0], 0)
        self.assertIsNotNone(accounts.authenticate(db, OWNER, GOOD_PW))
        self.assertEqual(self.run_ti("account", "totp-off", OWNER)[0], 0)
        self.assertEqual(self.run_ti("account", "reset-link", "nobody@example.com")[0], 1)
        actions = [(e["action"], e["actor"]) for e in auditlog.recent(db, None)]
        for action in ("user.disable", "user.enable", "totp.off", "reset.issue"):
            self.assertIn((action, "cli"), actions)

    def test_the_old_user_command_still_works(self):
        code, out, _ = self.run_ti("user", "list")
        self.assertEqual(code, 0)
        self.assertIn("morgan", out)


class TestTokenInSessionsMode(Ready):
    def sessions(self):
        self.box.config.write_text(self.box.config.read_text() + "access:\n  mode: sessions\n")

    def test_create_list_revoke_in_the_accounts_file(self):
        self.sessions()
        code, out, err = self.run_ti("token", "create", "a script", "--site", "shop.example")
        self.assertEqual(code, 0, err)
        token = re.search(r"skald_[0-9a-f]{8}_[A-Za-z0-9_-]+", out).group(0)
        db = self.db()
        self.assertTrue(apitokens.check(db, f"Bearer {token}", "shop.example")[0])
        self.assertEqual(old_tokens.load(old_tokens.path_for({}, self.box.root)), {})
        code, out, _ = self.run_ti("token", "list")
        self.assertIn("a script", out)
        self.assertIn("example-co", out)
        tid = token.split("_")[1]
        self.assertEqual(self.run_ti("token", "revoke", tid)[0], 0)
        self.assertFalse(apitokens.check(db, f"Bearer {token}", "shop.example")[0])
        self.assertEqual(self.run_ti("token", "revoke", "deadbeef")[0], 1)

    def test_basic_mode_keeps_tokens_json(self):
        code, out, _ = self.run_ti("token", "create", "plain")
        self.assertEqual(code, 0)
        self.assertEqual(len(old_tokens.load(old_tokens.path_for({}, self.box.root))), 1)



class TestReviewGaps(Ready):
    """The security review's CLI gaps: reset links on demand, install admins,
    token scopes, counts in status, handed invite links."""

    def test_reset_link_is_not_limited_to_three_an_hour(self):
        for _ in range(5):
            code, out, err = self.run_ti("account", "reset-link", OWNER, "--base-url", BASE)
            self.assertEqual(code, 0, err)
            self.assertEqual(len(self.link(out, "reset")), 1)
        actions = [(e["action"], e["actor"]) for e in auditlog.recent(self.db(), None)]
        self.assertGreaterEqual(actions.count(("reset.issue", "cli")), 5)

    def test_install_admin_on_and_off(self):
        db = self.db()
        other = accounts.create_user(db, "other@example.com", "Other", GOOD_PW)
        self.assertEqual(self.run_ti("account", "install-admin", "other@example.com", "on")[0],
                         0)
        self.assertTrue(accounts.find_user(db, user_id=other["id"])["install_admin"])
        self.assertEqual(self.run_ti("account", "install-admin", OWNER, "off")[0], 0)
        code, _, err = self.run_ti("account", "install-admin", "other@example.com", "off")
        self.assertEqual(code, 1)
        self.assertIn("last install admin", err)
        self.assertEqual(self.run_ti("account", "install-admin", "x@example.com", "on")[0], 1)
        code, out, _ = self.run_ti("accounts", "status")
        self.assertIn("install admins: 1", out)

    def test_token_scopes_in_sessions_mode(self):
        self.box.config.write_text(self.box.config.read_text() + "access:\n  mode: sessions\n")
        code, out, err = self.run_ti("token", "create", "agent", "--scope", "mcp",
                                     "--scope", "read")
        self.assertEqual(code, 0, err)
        tid = re.search(r"skald_([0-9a-f]{8})_", out).group(1)
        entry = [t for t in apitokens.listing(self.db(), 1) if t["id"] == tid][0]
        self.assertEqual(entry["scopes"], ["read", "mcp"])
        code, out, _ = self.run_ti("token", "list")
        self.assertIn("read,mcp", out)
        code, out, err = self.run_ti("token", "create", "x", "--scope", "write")
        self.assertEqual(code, 2)

    def test_scopes_other_than_read_need_sessions_mode(self):
        code, _, err = self.run_ti("token", "create", "agent", "--scope", "mcp")
        self.assertEqual(code, 2)
        self.assertIn("sessions", err)

    def test_an_invite_link_printed_without_mail_is_handed(self):
        code, out, err = self.run_ti("member", "invite", "new@example.com", "--role", "viewer",
                                     "--base-url", BASE)
        self.assertEqual(code, 0, err)
        user = accounts.accept(self.db(), self.link(out, "invite")[0], "New", GOOD_PW)
        self.assertTrue(user["must_reset"])

    def test_a_mailed_invite_is_not_handed(self):
        with mock.patch.object(cli_accounts, "_mail_invite", return_value="invite mail sent"):
            code, out, err = self.run_ti("member", "invite", "new@example.com", "--role",
                                         "viewer", "--base-url", BASE)
        user = accounts.accept(self.db(), self.link(out, "invite")[0], "New", GOOD_PW)
        self.assertFalse(user["must_reset"])


if __name__ == "__main__":
    unittest.main()
