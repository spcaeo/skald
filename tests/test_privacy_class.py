"""The organisation rule (accounts schema 6, accounts/orgs.py privacy_class):
"internal" (the default) changes nothing; "client" makes an organisation's
sites follow their own retention settings even on an install that keeps
everything. Every deletion path of keep_everything.py's list asks it: the
whole daily prune and each piece outside it run against a client's site and
clear exactly what an install without the rule clears (test_keep_everything's
own fixture and expectations). Hosts are example.com names, emails made up."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_keep_everything as tke  # noqa: E402

from skald import accounts, doctor, keep_everything  # noqa: E402
from skald.accounts import orgs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SITE = tke.SITE


def org_for(folder: Path, cls: str | None) -> None:
    """An accounts file beside the history whose organisation holds SITE, made
    `cls` (None: left at its default)."""
    db = accounts.connect(folder / "accounts.sqlite")
    try:
        org = accounts.create_org(db, "Client Co", "cli")
        accounts.assign_site(db, SITE, org["id"], "cli")
        if cls is not None:
            orgs.set_privacy_class(db, org["id"], cls, "cli")
    finally:
        db.close()


class InternalByDefault:
    """The install keeps everything; the site's organisation was made with the
    default class: every expectation of the install's rule holds as before."""

    def setUp(self):
        super().setUp()
        org_for(self.dir, None)


class DefaultInstall(InternalByDefault, tke.Install):
    pass


class DefaultPieces(InternalByDefault, tke.Pieces):
    pass


class DefaultRuleOff(InternalByDefault, tke.InstallRuleOff):
    pass


class ClientOrg:
    """The install keeps everything, but the site's organisation is a client:
    every path clears what it clears on an install without the rule (keep is
    False for the expectations; the config still says keep_everything)."""

    keep = False

    def write_config(self):
        super().write_config()
        path = self.dir / "config.yml"
        path.write_text(path.read_text() + "retention:\n  keep_everything: true\n")

    def setUp(self):
        super().setUp()
        org_for(self.dir, "client")

    def test_the_install_still_says_keep_everything(self):
        ctx = self.ctx()
        keeper = keep_everything.of(ctx)
        self.assertTrue(keeper.install)
        self.assertFalse(keeper.all)                     # a client's site is pruned
        self.assertIsNone(keeper.why(SITE))
        self.assertTrue(keeper("other.example.com"))   # a site no client holds: kept
        rule = keep_everything.describe(ctx.config, SITE)["rule"]
        self.assertEqual((rule["class"], rule["org"]), ("client", "Client Co"))
        self.assertIn("follows its own retention settings, even though the install keeps "
                      "everything", rule["words"])


class ClientInstall(ClientOrg, tke.InstallRuleOff):
    pass


class ClientPieces(ClientOrg, tke.Pieces):
    pass


# ------------------------------------------------------------- the keeper

class Keeper(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def config(self, keep=True, **more):
        cfg = {"history": {"db": str(self.dir / "history.sqlite")}, **more}
        if keep:
            cfg["retention"] = {"keep_everything": True}
        return cfg

    def test_no_accounts_file_changes_nothing(self):
        for keep in (True, False):
            k = keep_everything.Keeper(self.config(keep))
            self.assertEqual(k.why(SITE), "install" if keep else None)
            self.assertEqual(k.rule(SITE)["class"], "internal")
            self.assertEqual(k.any([SITE]), keep)

    def test_an_unreadable_file_keeps_everything(self):
        (self.dir / "accounts.sqlite").write_bytes(b"not a database at all" * 100)
        k = keep_everything.Keeper(self.config())
        self.assertEqual(k.why(SITE), "install")

    def test_any_is_no_only_when_every_site_is_a_clients(self):
        org_for(self.dir, "client")
        k = keep_everything.Keeper(self.config())
        self.assertFalse(k.any([SITE]))
        self.assertTrue(keep_everything.Keeper(self.config()).any([SITE, "other.example.com"]))

    def test_hosted_a_client_on_a_plan_that_keeps_is_kept(self):
        org_for(self.dir, "client")
        db = accounts.connect(self.dir / "accounts.sqlite")
        try:
            org = accounts.org_of_site(db, SITE)
            db.execute("UPDATE orgs SET plan = 'enterprise', plan_status = 'active' WHERE id = ?",
                       (org["id"],))
        finally:
            db.close()
        saas = {"saas": {"enabled": True, "default_plan": "pro",
                         "plans": [{"name": "pro", "sites": 5},
                                   {"name": "enterprise", "keep_everything": True}]},
                "access": {"mode": "sessions"}}
        k = keep_everything.Keeper(self.config(True, **saas))
        self.assertEqual(k.why(SITE), "plan enterprise")

    def test_the_doctor_says_which_rule(self):
        org_for(self.dir, "client")
        line = doctor.keep_everything(self.config(), SITE, self.dir)
        self.assertIn("off: Client Co is a client organisation", line["says"])
        db = accounts.connect(self.dir / "accounts.sqlite")
        try:
            orgs.set_privacy_class(db, accounts.org_of_site(db, SITE)["id"], "internal", "cli")
        finally:
            db.close()
        line = doctor.keep_everything(self.config(), SITE, self.dir)
        self.assertIn("on: nothing on this site is deleted", line["says"])
        self.assertIn("Client Co is an internal organisation", line["says"])
        self.assertIsNone(doctor.keep_everything(self.config(False), SITE, self.dir))

    def test_the_class_is_checked_and_audited(self):
        org_for(self.dir, None)
        db = accounts.connect(self.dir / "accounts.sqlite")
        try:
            oid = accounts.org_of_site(db, SITE)["id"]
            self.assertEqual(orgs.privacy_class(db, oid), "internal")
            with self.assertRaises(ValueError):
                orgs.set_privacy_class(db, oid, "public", "cli")
            orgs.set_privacy_class(db, oid, "client", "cli")
            orgs.set_privacy_class(db, oid, "client", "cli")        # no second row
            rows = [e for e in accounts.auditlog.recent(db, oid) if e["action"] == "org.privacy"]
            self.assertEqual([r["detail"] for r in rows], ["internal -> client"])
        finally:
            db.close()


# ------------------------------------------------- every path asks the keeper

class EveryPathAsks(unittest.TestCase):
    """Each module keep_everything.py's list names decides through Keeper or
    of() (which ask the organisation rule), never through install_on alone."""

    PATHS = ("prune.py", "store_visits.py", "people/visits.py", "security_kept.py",
             "conversions/store.py", "conversions/spool.py", "conversions/people_days.py",
             "conversions/outgoing.py", "events.py", "beacon.py", "answers/run.py", "alerts.py",
             "backup.py", "ingest.py", "ingest_drain.py", "site_data.py",
             "yourtools/people_days.py")
    # Where the decision for a module is made by its caller, which passes the keeper in.
    DECIDED_BY = {"store_visits.py": "prune.py", "conversions/store.py": "prune.py",
                  "conversions/spool.py": "cli_conversions.py", "beacon.py": "events.py",
                  "security_kept.py": "security_kept.py", "people/visits.py": "people/visits.py"}

    def test_each_decides_through_the_keeper(self):
        pkg = ROOT / "skald"
        for path in self.PATHS:
            decider = pkg / self.DECIDED_BY.get(path, path)
            with self.subTest(path=path):
                text = decider.read_text()
                self.assertRegex(text, r"keep_everything(?: import (?:of|Keeper)|\.of\()")

    def test_install_on_alone_decides_nothing_that_deletes(self):
        allowed = {"keep_everything.py", "orgs_api.py", "cli_orgs.py"}   # the last two: words
        for path in (ROOT / "skald").rglob("*.py"):
            if path.name in allowed:
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(re.search(r"\binstall_on\(", path.read_text()))


if __name__ == "__main__":
    unittest.main()
