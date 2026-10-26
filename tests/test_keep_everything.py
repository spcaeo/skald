"""Keep everything (keep_everything.py): on an internal or enterprise site
Skald deletes and clears nothing by itself. Every automatic prune runs on a
keep-everything site and the stored rows and files stay the same, byte for
byte; the same site with the rule off is pruned as before; hosted, only a
customer plan's sites are pruned. Hosts are example.com names, emails made up."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, Server  # noqa: E402

from skald import accounts, alerts, backup, events, keep_everything  # noqa: E402
from skald.answers import run as answers_run  # noqa: E402
from skald.answers import store as answers_store  # noqa: E402
from skald.conversions import outgoing, spool  # noqa: E402
from skald.conversions import store as cstore  # noqa: E402
from skald.saas import plans  # noqa: E402

UTC = timezone.utc
TODAY = date(2026, 10, 11)
OLD = date(2026, 1, 2)                       # past every window below
OLD_AT = "2026-01-02T10:00:00Z"
SITE = "alpha.example.com"
ENTERPRISE, CUSTOMER = "beta.example.com", "gamma.example.com"
SITES = (SITE, ENTERPRISE, CUSTOMER)
COLLECTED = repr((TODAY - timedelta(days=1)).isoformat())


def put(db, table: str, **values) -> None:
    """One row, every NOT NULL column without a default filled in (a
    composite key's parts made unique)."""
    cols = list(db.execute(f"PRAGMA table_info({table})"))
    keys = sum(1 for c in cols if c[5])
    for _, name, kind, notnull, default, pk in cols:
        if name in values or default is not None:
            continue
        if pk and keys == 1 and "INT" in (kind or "").upper():
            continue                                    # the rowid
        if not notnull and not pk:
            continue
        put.n += 1
        values[name] = put.n if "INT" in (kind or "").upper() else f"x{put.n}"
    names = ", ".join(values)
    db.execute(f"INSERT INTO {table} ({names}) VALUES ({', '.join('?' * len(values))})",
               tuple(values.values()))


put.n = 0


def tables(path: Path) -> dict:
    db = sqlite3.connect(path)
    try:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                          "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: sorted(map(repr, db.execute(f"SELECT * FROM {n}"))) for n in names}
    finally:
        db.close()


def snapshot(folder: Path) -> dict:
    """Every table's rows of every .sqlite file, and every other file's bytes."""
    out = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.endswith(("-wal", "-shm", "-journal", ".lock")):
            continue
        rel = str(path.relative_to(folder))
        if path.suffix == ".sqlite":
            out[rel] = tables(path)
        else:
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def count(path: Path, table: str, site: str | None = None) -> int:
    db = sqlite3.connect(path)
    try:
        if site is None:
            return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return db.execute(f"SELECT COUNT(*) FROM {table} WHERE site = ?", (site,)).fetchone()[0]
    finally:
        db.close()


def old_rows(path: Path, table: str, site: str, day: str = OLD.isoformat()) -> int:
    db = sqlite3.connect(path)
    try:
        return db.execute(f"SELECT COUNT(*) FROM {table} WHERE site = ? AND day = ?",
                          (site, day)).fetchone()[0]
    finally:
        db.close()


class Install(unittest.TestCase):
    """An install whose sites keep everything, from config.yml (Docker:
    SKALD_KEEP_EVERYTHING), against the same install without it."""

    keep = True
    extra = ""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.write_config()
        self.seed()

    def write_config(self):
        keep = "retention:\n  keep_everything: true\n" if self.keep else ""
        (self.dir / "config.yml").write_text(
            f"site:\n  name: {SITE}\nhistory:\n  db: {self.dir / 'history.sqlite'}\n"
            "report:\n  retention_days: 30\n  journey_days: 7\n  timezone: UTC\n"
            "visitors:\n  repeat_days: 7\n"
            "privacy:\n  keep_ips: true\n  keep_days: 30\n"
            "conversions:\n  identity: full\n  retention_days: 60\n"
            "journeys:\n  vid_days: 7\n"
            "beacon:\n  enabled: true\n  keep_days: 7\n" + keep + self.extra)

    def ctx(self, **more):
        from skald.cli import Context
        given = {"config": str(self.dir / "config.yml"), "today": TODAY.isoformat(),
                 "dry_run": True, "keep": None, "weekly_keep": None, "pull": False,
                 "verify": False, "dir": None}
        args = argparse.Namespace(**{**given, **more})
        ctx = Context(args)
        ctx.out = ctx.err = lambda *a, **k: None
        return ctx

    # ------------------------------------------------------------- the data

    def seed(self):
        from skald.store import History
        days = [OLD.isoformat(), (TODAY - timedelta(days=2)).isoformat()]
        with History(self.dir / "history.sqlite") as h:
            events.ensure(h.db)
            for site in self.sites():
                for day in days:
                    put(h.db, "journeys", site=site, day=day)
                    put(h.db, "visitor_days", site=site, day=day, visitor=f"v-{site}-{day}")
                    put(h.db, "day_extras", site=site, day=day, kind="pages", data="{}")
                    put(h.db, "day_extras", site=site, day=day, kind="ai_fetches", data="{}")
                    put(h.db, "event_counts", site=site, day=day, event="click", label="",
                        path="/", source="", n=1)
                    put(h.db, "event_days", site=site, day=day, state="whole", events=1)
            h.db.commit()
        db = cstore.connect(self.dir / "conversions.sqlite")
        try:
            for site in self.sites():
                for n, at in enumerate((OLD_AT, "2026-10-09T10:00:00Z")):
                    cstore.record_conversion(db, {
                        "site": site, "action": "demo", "stage": "completed", "at": at,
                        "external_ref": f"L-{n}", "tool": "lead", "vid": f"skv_{n}{site[:4]}",
                        "identity": {"email": f"person{n}@example.com", "name": f"Person {n}"}})
                with db:
                    put(db, "journeys", site=site, vid=f"skv_x{site[:4]}", at=OLD_AT)
                    put(db, "deliveries", site=site, received_at=OLD_AT)
                    put(db, "hook_replays", site=site, received_at=OLD_AT)
                    put(db, "pay_links", site=site, received_at=OLD_AT)
                    put(db, "visits", site=site, day=OLD.isoformat())
                    put(db, "visit_days", site=site, day=OLD.isoformat(), state="whole")
                    put(db, "security_rows", site=site, day=OLD.isoformat())
                    put(db, "security_days", site=site, day=OLD.isoformat(), state="whole")
        finally:
            db.close()
        hooks = spool.spool_dir({}, self.dir)
        for day in (OLD, TODAY - timedelta(days=1)):
            for site in self.sites():
                spool.append(hooks, day, json.dumps({"received_at": OLD_AT, "site": site,
                                                     "tool": "lead", "body": {}}))
        beacon_dir = self.dir / "beacon"
        beacon_dir.mkdir()
        for day in (OLD, TODAY - timedelta(days=1)):
            (beacon_dir / f"{day.isoformat()}.jsonl").write_text('{"e":"click"}\n')

    def sites(self):
        return (SITE,)

    def prune_everything(self):
        """Every automatic delete of the daily and live runs. events.daily also
        counts yesterday (COLLECTED): its new rows are not a change to the old."""
        from skald.prune import prune_kept
        ctx = self.ctx()
        with ctx.history() as history:
            prune_kept(ctx, history)                      # history, people, conversions
        events.daily(ctx, TODAY - timedelta(days=1))      # event counts, beacon spool
        return ctx

    # ------------------------------------------------------------- the tests

    def test_every_prune_leaves_every_row_and_file_as_it_was(self):
        if not self.keep:
            self.skipTest("the rule is off")
        before = snapshot(self.dir)
        self.prune_everything()
        after = snapshot(self.dir)
        for table in ("event_counts", "event_days"):
            got = after["history.sqlite"][table]
            after["history.sqlite"][table] = [r for r in got if COLLECTED not in r]
        for name in sorted(set(before) | set(after)):
            if name.endswith(".log") or name.startswith("runs") or name.endswith(".json"):
                continue                                   # run records, not data
            with self.subTest(file=name):
                self.assertEqual(before.get(name), after.get(name))

    def test_the_keeper_and_its_reason(self):
        ctx = self.ctx()
        keeper = keep_everything.of(ctx)
        self.assertEqual(keeper(SITE), self.keep)
        self.assertEqual(keeper.why(SITE), "install" if self.keep else None)
        self.assertEqual(keep_everything.describe(ctx.config, SITE)["words"],
                         keep_everything.WORDS if self.keep else None)


class InstallRuleOff(Install):
    """The same install without the rule: every prune removes what it did."""

    keep = False

    def test_the_same_prunes_clear(self):
        self.prune_everything()
        history, conv = self.dir / "history.sqlite", self.dir / "conversions.sqlite"
        for table in ("journeys", "visitor_days", "event_counts", "event_days"):
            with self.subTest(table=table):
                self.assertEqual(old_rows(history, table, SITE), 0)
                self.assertEqual(old_rows(history, table, SITE, "2026-10-09"), 1)
        self.assertEqual(count(history, "day_extras", SITE), 2)
        self.assertEqual(count(conv, "conversions", SITE), 1)
        for table in ("journeys", "deliveries", "hook_replays", "pay_links", "visits",
                      "visit_days", "security_rows", "security_days"):
            with self.subTest(table=table):
                self.assertEqual(count(conv, table, SITE), 0)
        self.assertEqual(count(conv, "identities", SITE), 1)
        self.assertFalse(spool.day_file(self.dir / "hooks", OLD).exists())
        self.assertFalse((self.dir / "beacon" / f"{OLD.isoformat()}.jsonl").exists())


class Pieces(Install):
    """The deletes outside the daily prune: AI answers, the outgoing outbox,
    closed alerts, the conversions file's backups, the People-days sweep."""

    def outbox(self, keeper):
        db = cstore.connect(self.dir / "conversions.sqlite")
        try:
            with db:
                put(db, "webhooks", site=SITE, url="https://example.com/hook", events="[]",
                    created_at=OLD_AT)
                hook = db.execute("SELECT MAX(id) FROM webhooks").fetchone()[0]
                put(db, "outbox", site=SITE, webhook_id=hook, created_at=OLD_AT)
            outgoing.prune(db, datetime(2026, 10, 11, tzinfo=UTC), spare=keeper)
            return db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        finally:
            db.close()

    def test_outbox(self):
        self.assertEqual(self.outbox(keep_everything.of(self.ctx())), 1 if self.keep else 0)

    def test_closed_alerts(self):
        state = {"alerts": [{"cause": "x", "subject": "s", "closed_at": "2026-01-02T00:00:00Z"}]}
        alerts.apply(state, [], datetime(2026, 10, 11, tzinfo=UTC), alerts.settings({}),
                     keep=keep_everything.of(self.ctx())(SITE))
        self.assertEqual(len(state["alerts"]), 1 if self.keep else 0)

    def test_ai_answers(self):
        db = answers_store.connect(answers_store.path_for(self.dir))
        try:
            with db:
                put(db, "runs", site=SITE, day="2025-01-02", state="done")   # past 400 days
        finally:
            db.close()
        ctx = self.ctx()
        answers_run.run_site(self.dir, SITE, ctx.config, UTC, datetime(2026, 10, 11, 9, tzinfo=UTC),
                             live_dir=self.dir, out=lambda *a: None, err=lambda *a: None)
        self.assertEqual(count(answers_store.path_for(self.dir), "runs", SITE),
                         1 if self.keep else 0)

    def test_conversions_backups(self):
        folder = self.dir / "backups"
        folder.mkdir()
        for n in range(3):
            day = OLD + timedelta(days=n)
            (folder / f"conversions-{day.isoformat()}.sqlite").write_bytes(b"old copy")
        backup.cmd_backup(self.ctx(keep=1, weekly_keep=1))
        old = [p for p in folder.glob("conversions-2026-01-*.sqlite")]
        self.assertEqual(len(old), 3 if self.keep else 0)

    def test_people_days_sweep(self):
        from skald.conversions import people_days
        before = tables(self.dir / "conversions.sqlite")["identities"]
        people_days.run(self.ctx())
        after = tables(self.dir / "conversions.sqlite")["identities"]
        self.assertEqual(before == after, self.keep)


class PiecesRuleOff(Pieces):
    keep = False


class Hosted(Install):
    """saas on: an organisation with no plan (the install's own) and one on
    an Enterprise plan with keep_everything keep everything; a customer
    plan's site is pruned."""

    keep = False
    extra = ("access:\n  mode: sessions\n"
             "saas:\n  enabled: true\n  default_plan: pro\n"
             # The list form: read the same with or without PyYAML (SAAS.md).
             "  plans: [{name: pro, sites: 5, label: Pro},"
             " {name: enterprise, keep_everything: true, label: Enterprise}]\n")

    def sites(self):
        return SITES

    def setUp(self):
        super().setUp()
        db = accounts.connect(self.dir / "accounts.sqlite")
        try:
            for site, plan in ((SITE, None), (ENTERPRISE, "enterprise"), (CUSTOMER, "pro")):
                org = accounts.create_org(db, f"Org {site[:5]}", "cli")
                accounts.assign_site(db, site, org["id"], "cli")
                if plan:
                    plans.set_plan(db, org["id"], plan, "active", "cli")
        finally:
            db.close()

    def test_every_prune_leaves_every_row_and_file_as_it_was(self):
        self.skipTest("hosted: per site below")

    def test_the_keeper_and_its_reason(self):
        keeper = keep_everything.of(self.ctx())
        self.assertEqual(keeper.why(SITE), "no plan")
        self.assertEqual(keeper.why(ENTERPRISE), "plan enterprise")
        self.assertIsNone(keeper.why(CUSTOMER))
        self.assertEqual(keeper.why("unheld.example.com"), "no plan")
        self.assertTrue(keeper.any())

    def test_only_the_customer_plan_is_pruned(self):
        def rows(site):
            return {name: [r for r in got if repr(site) in r
                           and not (name.startswith("event_") and COLLECTED in r)]
                    for path in (self.dir / "history.sqlite", self.dir / "conversions.sqlite")
                    for name, got in tables(path).items()}
        before = {site: rows(site) for site in SITES}
        self.prune_everything()
        for site in (SITE, ENTERPRISE):
            with self.subTest(site=site):
                self.assertEqual(rows(site), before[site])
        history, conv = self.dir / "history.sqlite", self.dir / "conversions.sqlite"
        self.assertEqual(count(history, "journeys", CUSTOMER), 1)
        self.assertEqual(count(history, "day_extras", CUSTOMER), 2)
        self.assertEqual(count(conv, "conversions", CUSTOMER), 1)
        self.assertEqual(count(conv, "deliveries", CUSTOMER), 0)
        self.assertEqual(count(conv, "visits", CUSTOMER), 0)
        # The hook spool keeps the kept sites' lines and drops the customer's.
        lines = spool.read(self.dir / "hooks", OLD)
        self.assertEqual(sorted(r["site"] for r in lines), [SITE, ENTERPRISE])
        # The beacon spool holds every site's lines: kept while any site keeps.
        self.assertTrue((self.dir / "beacon" / f"{OLD.isoformat()}.jsonl").exists())


class Notice(unittest.TestCase):
    def test_the_notice_says_until_you_ask(self):
        from skald.people.notice import wording
        base = {"site": {"name": SITE}, "privacy": {"keep_ips": True, "keep_days": 30},
                "conversions": {"identity": "full", "retention_days": 60},
                "beacon": {"enabled": True, "visitor_ids": True}}
        kept = wording({**base, "retention": {"keep_everything": True}})
        text = kept["text"]
        for days in ("30 days", "60 days", "14 days"):
            self.assertNotIn(days, text)
        self.assertIn("until you ask us to delete it", text)
        self.assertIn("We keep them until you ask us to delete them.", text)
        self.assertTrue(kept["uses"]["keep_everything"])
        plain = wording(base)
        self.assertIn("for 30 days", plain["text"])
        self.assertFalse(plain["uses"]["keep_everything"])

    def test_the_env_var_writes_the_config(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docker"))
        import entrypoint
        got = entrypoint.render_config({"SKALD_SITE": "example.com",
                                        "SKALD_KEEP_EVERYTHING": "1"})
        self.assertIs(got["retention"]["keep_everything"], True)
        self.assertNotIn("retention", entrypoint.render_config({"SKALD_SITE": "example.com"}))
        self.assertTrue(keep_everything.install_on(got))

    def test_the_doctor_says_it_once(self):
        from skald import doctor
        got = doctor.keep_everything({"retention": {"keep_everything": "true"}}, SITE, None)
        self.assertEqual((got["part"], got["state"]), ("Keep everything", doctor.OK))
        self.assertTrue(got["says"].startswith("on: nothing on this site is deleted"))
        self.assertIsNone(doctor.keep_everything({}, SITE, None))

    def test_a_plan_says_keep_everything(self):
        table = plans.plans({"saas": {"plans": {"pro": {"sites": 5},
                                                "enterprise": {"keep_everything": "true"}}}})
        self.assertFalse(table["pro"]["keep_everything"])
        self.assertTrue(table["enterprise"]["keep_everything"])


class InThePage(Server):
    """GET settings says it; a shorter window's preview removes nothing."""

    def ask(self):
        cookie, _ = self.session("owner@example.com")
        page = self.call("GET", f"/traffic/{A}/settings", cookie=cookie)
        shorter = self.call("GET", f"/traffic/{A}/settings/retention-preview"
                            "?key=report.retention_days&value=30", cookie=cookie)
        self.assertEqual((page.status, shorter.status), (200, 200), (page.json, shorter.json))
        return page.json, shorter.json

    def test_kept(self):
        self.config["retention"] = {"keep_everything": True}
        page, shorter = self.ask()
        self.assertEqual(page["keep_everything"],
                         {"on": True, "why": "install", "words": keep_everything.WORDS})
        self.assertIn("until you ask us to delete it", page["notice"]["text"])
        self.assertEqual((shorter["kept"], shorter["shrinks"]), (True, False))
        self.assertEqual(shorter["words"], keep_everything.WORDS)

    def test_not_kept(self):
        page, shorter = self.ask()
        self.assertFalse(page["keep_everything"]["on"])
        self.assertTrue(shorter["shrinks"])
        self.assertNotIn("kept", shorter)


if __name__ == "__main__":
    unittest.main()
