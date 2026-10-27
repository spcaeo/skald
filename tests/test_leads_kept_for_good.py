"""2.29: leads kept for good (the owner's choice, 2026-10-22: "never delete" a
lead's pages).

`conversions.retention_days` takes 0 (or the word `forever`): the conversions,
the rows a sync removed, the pages of an ID that converted, the identities they
point to and the hook spool's lines are never deleted by the nightly prune;
the delivery log keeps its own 90 days. `journeys.vid_days` (1 to 400) still
takes the pages of an ID with no conversion. Both are settings per site
(Settings > Privacy > Leads, `skald settings set`), each site pruned
by its own. The privacy-notice wording says "until you ask us to delete them",
and the second count still agrees over days older than any window.

Addresses are RFC 5737, hosts example.com / example.org.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, Server  # noqa: E402
from conversions_support import VID  # noqa: E402
from test_client_site_settings import MAIN, Cli  # noqa: E402
from test_conversions_hooks import Base, lead  # noqa: E402

from skald import audit_conversions, cli_conversions, settings_store  # noqa: E402
from skald.conversions import spool, store  # noqa: E402
from skald.people import notice  # noqa: E402

UTC = timezone.utc
SITE, OTHER = "example.com", "example.org"
VID2 = "skv_" + "R" * 22
VID3 = "skv_" + "S" * 22
TODAY = date(2026, 10, 11)
OLD = "2025-01-10T10:00:00Z"            # 639 days before TODAY: past 400 and past 30


def conv(**kw) -> dict:
    out = {"site": SITE, "tool": "lead", "action": "demo", "stage": "completed", "at": OLD,
           "external_ref": "L-1", "vid": VID}
    out.update(kw)
    return out


def count(db, table: str) -> int:
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ------------------------------------------------------------ the store's prune

class Prune(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = store.connect(Path(self.tmp.name) / "conversions.sqlite")
        self.addCleanup(self.db.close)
        # A lead with a name and email, the pages its ID read, and a removed row.
        store.record_conversion(self.db, conv(identity={"email": "a@example.com"}))
        store.record_page_view(self.db, SITE, VID, "2025-01-09T09:00:00Z", "/", "Search engine")
        store.record_page_view(self.db, SITE, VID, OLD, "/pricing/", None)
        store.record_conversion(self.db, conv(external_ref="L-2", vid=VID3, stage="started"))
        rid = self.db.execute("SELECT id FROM conversions WHERE external_ref = 'L-2'").fetchone()
        store.remove(self.db, rid[0], "a sync took it away")
        # An ID that never converted, a month and a half ago.
        store.record_page_view(self.db, SITE, VID2, "2026-08-25T10:00:00Z", "/blog/", None)
        store.log_delivery(self.db, SITE, "lead", "recorded", 200,
                           received_at="2025-01-10T10:00:01Z")

    def test_forever_keeps_every_lead_row_its_pages_and_identity(self):
        got = store.prune(self.db, TODAY, vid_days=30, retention_days=store.FOREVER)
        self.assertEqual(got["conversions"], 0)
        self.assertEqual(count(self.db, "conversions"), 1)
        self.assertEqual(count(self.db, "removed"), 1, "the removed row is kept")
        self.assertEqual(count(self.db, "identities"), 1, "the name and email are kept")
        self.assertEqual([r[0] for r in self.db.execute("SELECT DISTINCT vid FROM journeys")],
                         [VID], "the lead's pages stay; the unconverted ID's went")
        self.assertEqual(got["journeys"], 1)
        self.assertEqual(got["deliveries"], 1, "the delivery log keeps its own 90 days")
        # Years later, still kept.
        store.prune(self.db, date(2040, 1, 1), vid_days=30, retention_days=0)
        self.assertEqual((count(self.db, "conversions"), count(self.db, "journeys"),
                          count(self.db, "removed"), count(self.db, "identities")), (1, 2, 1, 1))

    def test_a_linked_journey_outlives_vid_days_and_an_unlinked_one_does_not(self):
        db = self.db
        store.record_page_view(db, SITE, VID3, "2026-09-01T10:00:00Z", "/", None)
        store.record_conversion(db, conv(external_ref="L-3", vid=VID3, at="2026-09-02T10:00:00Z"))
        store.prune(db, TODAY, vid_days=30, retention_days=400)
        left = {r[0] for r in db.execute("SELECT vid FROM journeys")}
        self.assertIn(VID3, left, "40 days old, but its ID converted")
        self.assertNotIn(VID2, left, "47 days old with no conversion: past 30")
        self.assertNotIn(VID, left, "639 days: past the 400 of the lead itself")

    def test_vid_days_reaches_400(self):
        store.prune(self.db, TODAY, vid_days=400, retention_days=0)
        self.assertIn(VID2, {r[0] for r in self.db.execute("SELECT vid FROM journeys")})

    def test_each_site_by_its_own_days(self):
        store.record_conversion(self.db, conv(site=OTHER, external_ref="O-1"))
        store.record_page_view(self.db, OTHER, VID2, "2026-09-25T10:00:00Z", "/", None)
        got = store.prune(self.db, TODAY, vid_days=30, retention_days=400,
                          own_vid={OTHER: 10}, own_keep={SITE: 0})
        self.assertEqual(got["conversions"], 1)
        self.assertEqual([r[0] for r in self.db.execute("SELECT site FROM conversions")], [SITE])
        self.assertEqual({r[0] for r in self.db.execute("SELECT site FROM journeys")}, {SITE},
                         "the other site's 16-day-old page went by its own 10 days")

    def test_forget_still_deletes_a_person_kept_for_good(self):
        store.prune(self.db, TODAY, vid_days=30, retention_days=0)
        got = store.forget(self.db, None, email="a@example.com")
        self.assertEqual(got["conversions"], 1)
        self.assertEqual((count(self.db, "conversions"), count(self.db, "identities")), (0, 0))
        self.assertFalse(self.db.execute("SELECT 1 FROM journeys WHERE vid = ?",
                                         (VID,)).fetchone())

    def test_the_preview_counts_what_a_shorter_window_removes(self):
        path = Path(self.tmp.name) / "conversions.sqlite"
        rows, days, first, last = store.prune_preview(path, SITE, "conversions.retention_days",
                                                      "2026-01-01")
        # 1 conversion + 1 removed row + 2 journeys of VID; the removed row was taken today.
        self.assertEqual((rows, first), (3, "2025-01-09"))
        rows, *_ = store.prune_preview(path, SITE, "journeys.vid_days", "2026-10-01")
        self.assertEqual(rows, 1, "only the page of the ID with no conversion")

    def test_the_days_read_from_a_config(self):
        self.assertEqual(store.keep_days({}), 400)
        for raw in (0, "0", "forever", "For good"):
            self.assertEqual(store.keep_days({"conversions": {"retention_days": raw}}), 0, raw)
        self.assertEqual(store.keep_days({"conversions": {"retention_days": "500"}}), 500)
        self.assertEqual(store.vid_days({}), 30)
        self.assertEqual(store.vid_days({"journeys": {"vid_days": 400}}), 400)


# ------------------------------------------------------------ the hook spool

class Spool(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.old, self.new = date(2025, 1, 10), date(2026, 10, 1)
        for day in (self.old, self.new):
            for site in (SITE, OTHER):
                spool.append(self.dir, day, json.dumps({"site": site, "tool": "lead",
                                                         "received_at": "x", "body": {}}))

    def sites(self, day: date) -> list:
        return [row["site"] for row in spool.read(self.dir, day)]

    def test_forever_keeps_every_file(self):
        self.assertEqual(spool.prune(self.dir, TODAY, 0), 0)
        self.assertEqual(spool.days(self.dir), [self.old, self.new])

    def test_a_site_kept_for_good_keeps_its_lines_and_the_others_go(self):
        self.assertEqual(spool.prune(self.dir, TODAY, 400, {SITE: 0}), 0)
        self.assertEqual(self.sites(self.old), [SITE], "the file written again, one line")
        self.assertEqual(self.sites(self.new), [SITE, OTHER])
        self.assertEqual(spool.prune(self.dir, TODAY, 0, {OTHER: 400}), 0)
        self.assertEqual(spool.prune(self.dir, TODAY, 400, {SITE: 5}), 1)
        self.assertEqual(spool.days(self.dir), [self.new], "nothing left in the old day")
        self.assertEqual(self.sites(self.new), [OTHER])

    def test_without_windows_per_site_a_whole_day_goes(self):
        self.assertEqual(spool.prune(self.dir, TODAY, 400), 1)
        self.assertEqual(spool.days(self.dir), [self.new])


# ------------------------------------------------- the nightly prune and the audit

class Audited(Base):
    """A lead 639 days old, through the real receiver: the audit agrees before
    and after the nightly prune, kept for good or not."""

    def setUp(self):
        super().setUp()
        quiet = redirect_stderr(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.now = int(datetime(2025, 1, 10, 12, 0, tzinfo=UTC).timestamp())
        status, answer = self.post("lead", lead(at=OLD))
        self.assertEqual((status, answer["recorded"]), (200, 1), answer)
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.record_page_view(db, SITE, VID, "2025-01-10T09:00:00Z", "/pricing/", None)
            store.record_page_view(db, SITE, VID2, "2025-01-10T09:00:00Z", "/blog/", None)
        finally:
            db.close()
        self.day = date(2025, 1, 10)

    def prune(self, config: dict) -> str:
        out: list[str] = []
        ctx = SimpleNamespace(config=config, db_path=self.folder / "history.sqlite",
                              now=datetime(2026, 10, 11, 7, 15, tzinfo=UTC), out=out.append)
        self.assertEqual(cli_conversions.cmd_prune(ctx), 0)
        return "\n".join(out)

    def findings(self, config: dict) -> dict:
        return audit_conversions.findings(config, self.folder, SITE, UTC, self.day, self.day,
                                          today=TODAY, refresh=False)

    def stored(self) -> dict:
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return store.day_counts(db, SITE, UTC, self.day, self.day)
        finally:
            db.close()

    def journeys(self) -> set:
        return {r[0] for r in self.rows("SELECT vid FROM journeys")}

    def test_kept_for_good_the_old_day_still_adds_up(self):
        config = {**self.config, "conversions": {**self.config["conversions"],
                                                 "retention_days": "forever"}}
        self.assertEqual(self.findings(config), {})
        said = self.prune(config)
        self.assertIn("0 conversion(s)", said)
        self.assertEqual(self.stored(), {"2025-01-10": {("demo", "completed"): 1}})
        self.assertEqual(spool.days(self.folder / "hooks"), [self.day], "the evidence stays")
        self.assertEqual(self.journeys(), {VID}, "the lead's pages stay, the other ID's go")
        self.assertEqual(self.findings(config), {}, "store and spool agree over the old day")

    def test_a_site_kept_for_good_in_settings_is_pruned_by_its_own_window(self):
        # Settings rows (settings_store.apply) put each site's days in _settings.
        config = {**self.config, "_settings": {"prune": {
            "conversions.retention_days": {"default": 400, "sites": {SITE: 0}},
            "journeys.vid_days": {"default": 30, "sites": {}}}}}
        self.prune(config)
        self.assertEqual(self.stored(), {"2025-01-10": {("demo", "completed"): 1}})
        self.assertEqual(self.journeys(), {VID})
        self.assertEqual(spool.days(self.folder / "hooks"), [self.day])

    def test_with_400_days_both_roads_go_and_still_agree(self):
        said = self.prune(self.config)
        self.assertIn("1 conversion(s)", said)
        self.assertEqual(self.stored(), {})
        self.assertEqual(spool.days(self.folder / "hooks"), [])
        self.assertEqual(self.journeys(), set())
        self.assertEqual(self.findings(self.config), {})

    def test_the_audit_sees_a_store_kept_without_its_spool(self):
        # Why the spool keeps the same days: kept rows with no evidence are withheld.
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.prune(db, TODAY, 30, 0)
        finally:
            db.close()
        spool.prune(self.folder / "hooks", TODAY, 400)
        self.assertIn("2025-01-10", self.findings(self.config))

    def test_the_beacon_day_cache_keeps_every_day_when_kept_for_good(self):
        days = {(date(2024, 1, 1) + timedelta(days=i)).isoformat(): [] for i in range(600)}
        audit_conversions._save_cache(self.folder, UTC, days, 0)
        self.assertEqual(len(audit_conversions._load_cache(self.folder, UTC)["days"]), 600)
        audit_conversions._save_cache(self.folder, UTC, days, 400)
        self.assertEqual(len(audit_conversions._load_cache(self.folder, UTC)["days"]), 400)


# ------------------------------------------------------------------ the settings

class Settings(unittest.TestCase):
    def test_retention_takes_forever_as_0(self):
        name = "conversions.retention_days"
        for raw in (0, "0", "forever", "Forever", "for good"):
            self.assertEqual(settings_store.validate(name, raw), 0, raw)
        self.assertEqual(settings_store.validate(name, 400), 400)
        self.assertEqual(settings_store.validate(name, "3650"), 3650)
        for bad in (-1, 3651, "always", True, 1.5):
            with self.assertRaises(settings_store.Invalid, msg=repr(bad)):
                settings_store.validate(name, bad)
        key = settings_store.SCHEMA[name]
        self.assertEqual((key.default, key.scopes[0], key.who, key.forever, key.shrink),
                         (400, "site", "admin", True, True))
        self.assertIn(name, settings_store.SHRINKING)

    def test_vid_days_is_1_to_400(self):
        name = "journeys.vid_days"
        self.assertEqual(settings_store.validate(name, 1), 1)
        self.assertEqual(settings_store.validate(name, "400"), 400)
        for bad in (0, "forever", 401):
            with self.assertRaises(settings_store.Invalid, msg=repr(bad)):
                settings_store.validate(name, bad)
        self.assertEqual(settings_store.SCHEMA[name].default, 30)

    def test_forever_keeps_the_most(self):
        less = settings_store.keeps_less
        self.assertFalse(less("conversions.retention_days", 400, 0))
        self.assertTrue(less("conversions.retention_days", 0, 3650))
        self.assertTrue(less("conversions.retention_days", 400, 30))
        self.assertTrue(less("journeys.vid_days", 30, 7))
        self.assertFalse(less("journeys.vid_days", 30, 400))

    def test_a_plan_cap_is_shorter_than_forever(self):
        name = "conversions.retention_days"
        self.assertEqual(settings_store.within(name, 0, 365), 365)
        self.assertEqual(settings_store.within(name, 100, 365), 100)
        with self.assertRaises(settings_store.Invalid):
            settings_store.validate(name, 0, cap=365)

    def test_the_config_word_reads_as_0_and_new_installs_keep_400_and_30(self):
        got = settings_store.explain({"conversions": {"retention_days": "forever"}})
        self.assertEqual((got["conversions.retention_days"]["value"],
                          got["conversions.retention_days"]["source"]), (0, "config"))
        got = settings_store.explain({})
        self.assertEqual((got["conversions.retention_days"]["value"],
                          got["journeys.vid_days"]["value"]), (400, 30))


class SettingsCli(Cli):
    def test_set_forever_and_400_days_per_site(self):
        code, out, err = self.run_ti("settings", "set", MAIN, "conversions.retention_days", "0")
        self.assertEqual(code, 0, err)
        self.assertIn("kept for good", out)
        self.assertEqual(settings_store.get(self.db, f"site:{MAIN}",
                                            "conversions.retention_days"), 0)
        code, out, err = self.run_ti("settings", "set", MAIN, "journeys.vid_days", "400")
        self.assertEqual(code, 0, err)
        config = {"site": {"name": MAIN}, "history": {"db": str(self.dir / "history.sqlite")}}
        got = settings_store.apply(config, MAIN, self.dir)
        self.assertEqual((got["conversions"]["retention_days"], got["journeys"]["vid_days"]),
                         (0, 400))
        self.assertEqual(settings_store.prune_plan(got, "conversions.retention_days", 400),
                         (400, {MAIN: 0}))
        self.assertEqual(settings_store.prune_plan(got, "journeys.vid_days", 30),
                         (30, {MAIN: 400}))
        # From for good back to days removes data: --yes, as the page asks for the name.
        code, _, err = self.run_ti("settings", "set", MAIN, "conversions.retention_days", "400")
        self.assertEqual(code, 2)
        self.assertIn("--yes", err)
        code, _, err = self.run_ti("settings", "set", MAIN, "conversions.retention_days",
                                   "forever")
        self.assertEqual(code, 0, err)
        code, _, err = self.run_ti("settings", "set", MAIN, "journeys.vid_days", "401")
        self.assertEqual(code, 1)


class SettingsPage(Server):
    def test_the_page_sends_forever_and_saves_it_without_a_confirm(self):
        cookie, csrf = self.session("owner@example.com")
        got = self.call("GET", f"/traffic/{A}/settings", cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        item = got.json["settings"]["conversions.retention_days"]
        self.assertEqual((item["value"], item["forever"], item["lo"], item["hi"]),
                         (400, True, 1, 3650))
        self.assertEqual(got.json["settings"]["journeys.vid_days"]["hi"], 400)
        saved = self.post(f"/traffic/{A}/settings/save", {"conversions.retention_days": 0},
                          cookie, csrf)
        self.assertEqual(saved.status, 200, saved.json)
        self.assertEqual(saved.json["settings"]["conversions.retention_days"]["value"], 0)
        self.assertIn("until you ask us to delete them", saved.json["notice"]["text"])
        # Back to days is keeping less: the site's name first.
        back = self.post(f"/traffic/{A}/settings/save", {"conversions.retention_days": 400},
                         cookie, csrf)
        self.assertEqual(back.status, 409, back.json)
        self.assertEqual(back.json["keys"], ["conversions.retention_days"])
        db = store.connect(self.live / "conversions.sqlite")
        try:
            store.record_conversion(db, conv(site=A, at="2020-01-01T10:00:00Z"))
            store.record_conversion(db, conv(site=A, external_ref="L-now",
                                             at=store.stamp(datetime.now(UTC))))
        finally:
            db.close()
        q = f"/traffic/{A}/settings/retention-preview?key=conversions.retention_days&value=400"
        got = self.call("GET", q, cookie=cookie)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual((got.json["shrinks"], got.json["rows"], got.json["first"]),
                         (True, 1, "2020-01-01"))
        q = f"/traffic/{A}/settings/retention-preview?key=conversions.retention_days&value=0"
        self.assertFalse(self.call("GET", q, cookie=cookie).json["shrinks"])


# --------------------------------------------------------------- the notice

class Notice(unittest.TestCase):
    def config(self, lead_days, vid_days=21, identity="full", ids=True) -> dict:
        return {"privacy": {"keep_ips": "off"}, "journeys": {"vid_days": vid_days},
                "conversions": {"identity": identity, "retention_days": lead_days},
                "beacon": {"enabled": True, "visitor_ids": ids}}

    def test_kept_for_good_says_until_you_ask(self):
        got = notice.wording(self.config(0))
        text = got["text"]
        self.assertIn("we keep your name and email with it, so we can see which visits led to "
                      "it. We keep them until you ask us to delete them.", text)
        self.assertIn("We keep the pages read with a visitor ID for 21 days. When you send us "
                      "a form or book a call, the pages read with that ID are kept with it, "
                      "until you ask us to delete them.", text)
        self.assertEqual((got["uses"]["lead_days"], got["uses"]["vid_days"]), (0, 21))

    def test_days_say_the_days(self):
        text = notice.wording(self.config("400", vid_days=1))["text"]
        self.assertIn("We keep them for 400 days.", text)
        self.assertIn("for 1 day. When you send us a form", text)
        self.assertIn("kept with it, for 400 days.", text)
        self.assertNotIn("until you ask us", text)

    def test_no_name_kept_and_no_ids_say_neither(self):
        text = notice.wording(self.config(0, identity="anonymous", ids=False))["text"]
        self.assertNotIn("until you ask us", text)
        self.assertNotIn("pages read with a visitor ID", text)


if __name__ == "__main__":
    unittest.main()
