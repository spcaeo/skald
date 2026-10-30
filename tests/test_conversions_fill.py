"""2.45: a lead's touches filled from its visitor ID's page views
(conversions/fill.py) and checked by the second road (audit_filled.py); and
the ad click IDs kept on conversions while `conversions.click_ids` is on.
Hosts are example.com; addresses RFC 5737; the click IDs are made up."""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import VID  # noqa: E402
from test_conversions_beacon import ORIGIN, Server, body  # noqa: E402
from test_conversions_hooks import T, Base, lead  # noqa: E402

from skald import audit_conversions, audit_filled, beacon, settings_store  # noqa: E402
from skald.conversions import fill, from_beacon, outgoing, people_days, store  # noqa: E402
from skald.people import leadlist, lookup, notice  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 11)
OTHER = "skv_" + "Z" * 22
GCLID = "Cj0KCQjw-made_up-123"
EVERY = "source_type,first_source,campaign,landing,first_touch_at"


def stamp(text: str) -> str:
    return text if text.endswith("Z") else text + "Z"


class Touches(Base):
    """A lead hook with a visitor ID; the page views put straight in the store."""

    def views(self, *rows, vid=VID, campaign="(no campaign tag)", click=None):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            for at, path, source in rows:
                store.record_page_view(db, "example.com", vid, stamp(at), path, source, "",
                                       campaign, click)
        finally:
            db.close()

    def row(self, ref="L-1"):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return dict(db.execute("SELECT * FROM conversions WHERE external_ref = ?",
                                   (ref,)).fetchone())
        finally:
            db.close()

    def refresh(self, clicks=False, since=None):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return fill.refresh(db, "example.com", clicks, since)
        finally:
            db.close()

    def audit(self):
        return audit_filled.check(self.folder / "conversions.sqlite", "example.com", UTC,
                                  date(2026, 9, 1), date(2026, 10, 31))

    def two_visits(self):
        # A search eleven days before; today a LinkedIn post, two pages.
        self.views(("2026-09-30T10:00:00", "/blog/first/", "Search engine"))
        self.views(("2026-10-11T11:50:00", "/pricing/", "Social media"),
                   ("2026-10-11T11:55:00", "/contact/", "This site"),
                   campaign="linkedin / social / spring")

    def test_no_touches_filled_from_the_ids_page_views(self):
        self.two_visits()
        self.assertEqual(self.post("lead", lead(last_touch=None))[0], 200)
        got = self.row()
        self.assertEqual((got["source_type"], got["first_source"], got["campaign"],
                          got["landing"], got["first_touch_at"]),
                         ("Social media", "Search engine", "linkedin / social / spring",
                          "/blog/first/", "2026-09-30T10:00:00Z"))
        self.assertEqual(got["filled"], EVERY)
        self.assertEqual(self.audit(), {}, "the second road agrees")
        self.assertEqual(self.refresh(), 0, "a refresh finds nothing to change")

    def test_the_senders_touches_win(self):
        self.two_visits()
        self.post("lead", lead())          # its last touch: Google
        got = self.row()
        self.assertEqual((got["source_type"], got["first_source"], got["filled"]),
                         ("Search engine", None, None))
        self.assertEqual(got["landing"], "/pricing/", "the sender's own landing")
        self.refresh()
        self.assertEqual(self.row()["filled"], None, "never filled later either")
        self.assertEqual(self.audit(), {})

    def test_a_column_the_sender_gave_alone_stays(self):
        self.two_visits()
        self.post("lead", lead(last_touch=None, landing="/own-form/", campaign="partner"))
        got = self.row()
        self.assertEqual((got["landing"], got["campaign"], got["source_type"]),
                         ("/own-form/", "partner", "Social media"))
        self.assertEqual(got["filled"], "source_type,first_source,first_touch_at")
        self.assertEqual(self.audit(), {})

    def test_no_visitor_id_stays_unknown(self):
        self.two_visits()
        self.post("lead", lead(vid=None, last_touch=None))
        got = self.row()
        self.assertEqual((got["source_type"], got["first_source"], got["filled"]),
                         (None, None, None))

    def test_a_page_view_after_the_lead_is_never_used(self):
        self.views(("2026-10-11T12:30:00", "/thanks/", "Email"))
        self.post("lead", lead(last_touch=None))
        self.refresh()
        got = self.row()
        self.assertEqual((got["source_type"], got["filled"]), (None, None))
        # One before it: the later one still plays no part.
        self.views(("2026-10-11T11:00:00", "/", "AI assistant"))
        self.refresh()
        got = self.row()
        self.assertEqual((got["source_type"], got["first_source"], got["landing"]),
                         ("AI assistant", "AI assistant", "/"))

    def test_never_by_address(self):
        # A kept visit of the lead's own address, and another browser's page views: neither.
        db = store.connect(self.folder / "conversions.sqlite")
        db.execute("INSERT INTO visits (site, day, seq, ip, user_agent, start, end, source, "
                   "landing, pages, trail) VALUES ('example.com', '2026-10-11', 1, "
                   "'192.0.2.7', 'x', '2026-10-11T11:00:00Z', '2026-10-11T11:05:00Z', "
                   "'Search engine', '/', 1, '/')")
        db.close()
        self.views(("2026-10-11T11:00:00", "/", "Search engine"), vid=OTHER)
        self.post("lead", lead(vid=None, last_touch=None, ip="192.0.2.7"))
        self.refresh()
        got = self.row()
        self.assertEqual((got["source_type"], got["first_source"], got["country"]),
                         (None, None, "CA"))

    def test_page_views_that_arrive_later_fill_it_at_the_next_run(self):
        self.post("lead", lead(last_touch=None))
        self.assertEqual(self.row()["source_type"], None)
        self.views(("2026-10-11T11:58:00", "/pricing/", "Email"))
        self.assertEqual(self.refresh(since="2026-10-10T00:00:00Z"), 1)
        self.assertEqual(self.row()["source_type"], "Email")
        self.assertEqual(self.audit(), {})

    def test_page_views_taken_away_unfill_it(self):
        self.two_visits()
        self.post("lead", lead(last_touch=None))
        db = store.connect(self.folder / "conversions.sqlite")
        db.execute("DELETE FROM journeys WHERE at < '2026-10-01'")
        db.close()
        self.assertIn("2026-10-11", self.audit(), "until the refresh, the day is held")
        self.refresh()
        got = self.row()
        self.assertEqual((got["first_source"], got["landing"], got["source_type"]),
                         ("Social media", "/pricing/", "Social media"))
        self.assertEqual(self.audit(), {})

    def test_a_planted_mismatch_withholds_the_day(self):
        self.two_visits()
        self.post("lead", lead(last_touch=None))
        db = store.connect(self.folder / "conversions.sqlite")
        db.execute("UPDATE conversions SET source_type = 'Email'")
        db.close()
        got = self.audit()
        self.assertEqual(list(got), ["2026-10-11"])
        self.assertIn("source_type", got["2026-10-11"][0])
        self.assertNotIn(VID, json.dumps(got), "never the visitor ID")
        # And conversions.json withholds it (audit_conversions.check_file).
        from skald import conversions_data
        blob = conversions_data.blob(self.config, self.folder, "example.com", UTC,
                                     date(2026, 10, 12),
                                     datetime(2026, 10, 12, 12, 0, tzinfo=UTC))
        day = next(d for d in blob["days"] if d["day"] == "2026-10-11")
        self.assertEqual(day["state"], "withheld")
        # A column the mark names that its page views no longer fill is a mismatch too.
        db = store.connect(self.folder / "conversions.sqlite")
        db.execute("UPDATE conversions SET source_type = 'Social media'")
        db.execute("UPDATE journeys SET campaign = NULL")
        db.close()
        got = self.audit()["2026-10-11"]
        self.assertTrue(any("filled names" in p for p in got), got)

    def test_the_audit_walks_visits_its_own_way(self):
        views = [("2026-10-01T10:00:00Z", "/a/", "Email", None),
                 ("2026-10-11T10:00:00Z", "/b/", "Search engine", "x / y / z"),
                 ("2026-10-11T10:29:00Z", "/c/", "This site", None),
                 ("2026-10-11T10:58:00Z", "/d/", "This site", None),
                 ("2026-10-11T11:40:00Z", "/e/", "Social media", "s / - / -")]
        got = audit_filled.expected(views, "2026-10-11T11:45:00Z")
        self.assertEqual((got["source_type"], got["campaign"], got["first_source"],
                          got["landing"]), ("Social media", "s / - / -", "Email", "/a/"))
        got = audit_filled.expected(views, "2026-10-11T11:00:00Z")
        self.assertEqual(got["source_type"], "Search engine", "29 minutes apart: one visit")
        self.assertEqual(audit_filled.expected(views, "2026-09-01T00:00:00Z"),
                         dict.fromkeys(audit_filled.FIGURES))


class ClickIds(Touches):
    clicks = True

    def setUp(self):
        super().setUp()
        if self.clicks:
            self.config["conversions"]["click_ids"] = True
            from skald.conversions.hooks import Receiver
            self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)

    def test_off_by_default(self):
        key = settings_store.SCHEMA["conversions.click_ids"]
        self.assertEqual((key.kind, key.default), ("bool", False))
        self.assertFalse(fill.keep_clicks({}))
        self.assertTrue(fill.keep_clicks(self.config))

    def test_kept_from_the_senders_touch(self):
        self.post("lead", lead(last_touch={"referrer": "https://www.google.com/",
                                           "landing": f"/pricing/?gclid={GCLID}&x=1"}))
        got = self.row()
        self.assertEqual((got["click_kind"], got["click_id"], got["filled"]), ("gclid", GCLID,
                                                                             None))
        self.post("lead", lead(external_ref="L-2", last_touch={"msclkid": "4f2a9c0b"},
                               first_touch={"fbclid": "IwAR0made"}))
        got = self.row("L-2")
        self.assertEqual((got["click_kind"], got["click_id"]), ("msclkid", "4f2a9c0b"),
                         "the last touch's first")
        self.post("lead", lead(external_ref="L-3", last_touch={"landing": "/?gclid=<script>"}))
        self.assertEqual(self.row("L-3")["click_id"], None, "not an ID's shape")

    def test_filled_from_the_page_views(self):
        self.views(("2026-10-11T11:50:00", "/pricing/", "Search engine"),
                   campaign="google / cpc / (gclid)", click=("gclid", GCLID))
        self.post("lead", lead(last_touch=None))
        got = self.row()
        self.assertEqual((got["click_kind"], got["click_id"], got["filled"]),
                         ("gclid", GCLID, EVERY + ",click"))
        self.assertEqual(self.audit(), {})
        # Off: the next run clears every one, the figures' columns stay.
        self.assertEqual(self.refresh(clicks=False), 1)
        got = self.row()
        self.assertEqual((got["click_kind"], got["click_id"], got["filled"],
                          got["source_type"]), (None, None, EVERY, "Search engine"))
        db = store.connect(self.folder / "conversions.sqlite")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM journeys WHERE click_id IS NOT "
                                    "NULL").fetchone()[0], 0)
        db.close()
        self.assertEqual(self.audit(), {})

    def test_cleared_by_forget(self):
        self.views(("2026-10-11T11:50:00", "/", "Search engine"), click=("gclid", GCLID))
        self.post("lead", lead(last_touch=None))
        self.post("lead", lead(external_ref="L-2", vid=None,
                               last_touch={"landing": "/?gclid=OTHER-made-up"}))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.forget(db, "example.com", vid=VID)
            store.forget(db, "example.com", external_ref="L-2")
            dump = json.dumps([list(r) for t in ("conversions", "journeys", "removed")
                               for r in db.execute(f"SELECT * FROM {t}")])
        finally:
            db.close()
        self.assertNotIn(GCLID, dump)
        self.assertNotIn("OTHER-made-up", dump)

    def test_cleared_after_the_people_days(self):
        self.now = T - 100 * 86400
        self.post("lead", lead(external_ref="OLD", vid=None,
                               last_touch={"landing": f"/?gclid={GCLID}"},
                               at="2026-07-03T12:00:00Z"))
        self.now = T
        self.post("lead", lead(last_touch={"landing": "/?gclid=YOUNG-made-up"}))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            got = people_days.clear(db, DAY, lambda site: 30)
        finally:
            db.close()
        self.assertEqual(got["example.com"]["clicks"], 1)
        self.assertEqual(self.row("OLD")["click_id"], None)
        self.assertEqual(self.row("OLD")["action"], "demo", "the lead stays")
        self.assertEqual(self.row()["click_id"], "YOUNG-made-up")

    def test_shown_only_where_private_data_is(self):
        self.post("lead", lead(last_touch={"landing": f"/?gclid={GCLID}"}))
        folder, cfg = self.folder, self.config
        open_rows = leadlist.rows(cfg, folder, "example.com", DAY, DAY, False)
        self.assertEqual(open_rows["clicks"], False)
        self.assertNotIn("click_id", open_rows["rows"][0])
        self.assertEqual(open_rows["rows"][0]["filled"], [])
        shut = leadlist.rows(cfg, folder, "example.com", DAY, DAY, True, private=True)
        self.assertEqual(shut["rows"][0]["click_id"], GCLID)
        self.assertTrue(shut["clicks"], "so the view is written to the privacy log")
        # The test list: only for a caller who may see private data.
        db = store.connect(folder / "conversions.sqlite")
        store.mark_test(db, "example.com", [db.execute("SELECT id FROM conversions"
                                                       ).fetchone()[0]])
        row = dict(db.execute("SELECT * FROM conversions").fetchone())
        db.close()
        self.assertNotIn(GCLID, json.dumps(lookup.conversions_listing(cfg, folder, "example.com",
                                                                      "test", False)))
        self.assertIn(GCLID, json.dumps(lookup.conversions_listing(cfg, folder, "example.com",
                                                                   "test", True)))
        # The person lookup (admins, a read_private token) carries it.
        self.assertIn(GCLID, json.dumps(lookup.person(cfg, folder, "example.com", "L-1")))
        # Outgoing webhooks never.
        db = store.connect(folder / "conversions.sqlite")
        self.assertNotIn(GCLID, json.dumps(outgoing.body_for(db, row, "conversion")))
        db.close()

    def test_the_privacy_notice_says_so(self):
        text = notice.wording(self.config, self.folder)["text"]
        self.assertIn("click ID", text)
        self.config["conversions"]["click_ids"] = False
        self.assertNotIn("click ID", notice.wording(self.config, self.folder)["text"])


class NotKept(ClickIds):
    clicks = False

    def test_kept_from_the_senders_touch(self):
        self.post("lead", lead(last_touch={"landing": f"/pricing/?gclid={GCLID}"}))
        got = self.row()
        self.assertEqual((got["click_kind"], got["click_id"]), (None, None))
        self.assertEqual(got["source_type"], "Search engine", "the kind still names the source")

    test_off_by_default = test_filled_from_the_page_views = test_cleared_by_forget = None
    test_cleared_after_the_people_days = test_shown_only_where_private_data_is = None
    test_the_privacy_notice_says_so = None


class Beacon(Server):
    """Script-tag conversions: campaign, first source and first touch from the journeys."""

    def test_campaign_and_first_source_of_the_landing_visit(self):
        self.now = T - 3 * 86400
        self.post(body(e="page_view", p="/", id=None, r="", u="newsletter", m="email",
                       c="october"))
        self.now = T - 120
        self.post(body(e="page_view", p="/pricing/", id=None, r="linkedin.com", u="linkedin",
                       m="social", c="Spring Sale", k="gclid"))
        self.post(body(e="form_submit", p="/pricing/", id="contact", r="linkedin.com",
                       u="linkedin"), after=60)
        got = self.rows()[0]
        self.assertEqual((got["source_type"], got["campaign"], got["first_source"],
                          got["first_touch_at"], got["landing"]),
                         ("Social media", "linkedin / social / spring sale", "Email",
                          "2026-10-08T12:00:00Z", "/pricing/"))
        self.assertEqual(got["filled"], "first_source,campaign,first_touch_at")
        self.assertEqual(got["click_id"], None, "the site keeps no click IDs")
        self.assertNotIn('"k"', json.dumps(self.lines()), "the click never in the spool")
        self.assertEqual(audit_filled.check(self.db_path, "example.com", UTC, DAY, DAY), {})

    def test_a_click_kind_alone_names_the_campaign(self):
        self.post(body(e="page_view", p="/", id=None, k="msclkid"))
        pages = self.rows("SELECT campaign, click_kind, click_id FROM journeys")
        self.assertEqual(pages, [{"campaign": "bing / cpc / (msclkid)", "click_kind": None,
                                  "click_id": None}])

    def test_with_click_ids_on(self):
        self.config["conversions"]["click_ids"] = True
        self.sink.reconfigure(self.config)
        self.assertIn(b"CK=1", self.sink.snippet()[0])
        self.post(body(e="page_view", p="/", id=None, k=f"gclid:{GCLID}"))
        self.post(body(e="form_submit", p="/", id="contact"), after=30)
        got = self.rows()[0]
        self.assertEqual((got["click_kind"], got["click_id"]), ("gclid", GCLID))
        self.assertIn("click", got["filled"])
        self.assertNotIn(GCLID, json.dumps(self.lines()), "never in the spool")
        self.config["conversions"]["click_ids"] = False
        self.sink.reconfigure(self.config)
        self.assertIn(b"CK=0", self.sink.snippet()[0])

    def test_the_tags_shape(self):
        b = beacon.validate(body(e="page_view", p="/", id=None, m="\x07bad", c="x" * 61,
                                 k="gclid:<b>"), beacon.EVENTS + ("page_view",))
        self.assertFalse({"m", "c", "k"} & set(b))
        self.assertEqual(from_beacon.visit_campaign({}), "(no campaign tag)")


class AuditInCheckFile(unittest.TestCase):
    def test_check_file_runs_it(self):
        import inspect
        self.assertIn("audit_filled", inspect.getsource(audit_conversions.check_file))


if __name__ == "__main__":
    unittest.main()
