"""Phase 4 lane A: leads.json's attribution rows, time to convert, and a
second count (audit_leads.py) that covers every figure the file shows. A
block the recount disagrees with is withheld in the written file.

The CMS file is a temporary SQLite database with the website's
`submissions` schema; addresses are example.com and made up.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import NY, Sandbox, day_lines  # noqa: E402
from test_leads import JOURNEYS, ROWS, SCHEMA, TODAY, make_db, touch  # noqa: E402

from skald import audit_leads, leads  # noqa: E402

MADE = "2026-10-07T14:00:00.000Z"       # 10:00 on the 7th in New York


def at(**back) -> str:
    when = datetime(2026, 10, 7, 14, tzinfo=timezone.utc) - timedelta(**back)
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# (type, status, first_touch, last_touch, visits)
CONVERT = [
    ("signup", "new", touch(at=at(minutes=30)), None, 1),                    # <1h
    ("signup", "new", touch(at=at(hours=5)), None, 2),                       # <1d
    ("contact", "won", touch(at=at(days=3)), None, 4),                       # 1-7d
    ("contact", "new", touch(at=at(days=7, hours=23, minutes=59, seconds=59)), None, 12),
    ("waitlist", "new", touch(at=at(days=8)), None, None),                   # 8-30d
    ("signup", "lost", touch(at=at(days=31)), None, 0),                      # 31-90d
    ("signup", "new", touch(at=at(days=101)), None, 2.5),                    # >90d
    ("signup", "new", touch(at=at(hours=-1)), None, 1),                      # clock error
    ("signup", "new", None, None, 1),                                        # unknown
    ("signup", "new", touch(at="yesterday"), None, 1),                       # unknown
    ("signup", "new", json.dumps({"at": 12345}), None, 1),                   # unknown
    ("signup", "spam", touch(at=at(hours=2)), None, 1),                      # left out
    ("demo_booked", "qualified",
     touch(gclid="abc", referrerHost="", utmSource="google", utmMedium="CPC"),
     touch(fbclid="xyz"), 3),
]


def convert_db(path: Path, rows=CONVERT, made=MADE) -> Path:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for i, (kind, status, first, last, visits) in enumerate(rows, 1):
        db.execute(
            "INSERT INTO submissions (id, type, email, fields, locale, updated_at, created_at, "
            "status, page, first_touch, last_touch, visits) "
            "VALUES (?, ?, ?, '{}', 'en-us', ?, ?, ?, '/signup/', ?, ?, ?)",
            (i, kind, f"person{i}@example.com", made, made, status, first, last, visits))
    db.commit()
    db.close()
    return path


class Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = make_db(self.dir / "payload.db")
        self.config = {"leads": {"db": str(self.path)}}

    def tearDown(self):
        self._tmp.cleanup()

    def raw(self, config=None, today=TODAY):
        return leads.blob(config or self.config, NY, today, JOURNEYS, date(2026, 9, 30),
                          audited=False)

    def recount(self, config=None, today=TODAY):
        config = config or self.config
        return audit_leads.audit_leads(leads.db_path(config), NY,
                                       today - timedelta(days=leads.DAYS - 1), today,
                                       journeys=JOURNEYS, config=config)


# ------------------------------------------------------------------- A1

class TestRecountCoversEveryFigure(Base):

    def test_the_recount_agrees_with_every_block(self):
        self.assertEqual(audit_leads.compare(self.raw(), self.recount()), [])

    def test_the_old_call_still_works(self):
        got = self.raw()
        old = audit_leads.audit_leads(self.path, NY, date(2026, 9, 7), TODAY)
        self.assertEqual(audit_leads.compare(got, old), [])

    def plant(self, change) -> dict:
        got = self.raw()
        change(got)
        return audit_leads.findings(got, self.recount())

    def test_each_block_is_checked(self):
        cases = {
            "period": lambda b: b["period"]["first_touch"]["source"].update({"AI assistant": 9}),
            "period ": lambda b: b["period"]["last_touch"]["source"].update({"Search engine": 2}),
            "period  ": lambda b: b["period"]["last_touch"]["landing"].update({"/x/": 1}),
            "period   ": lambda b: b["period"]["status"].update({"won": 5}),
            "period    ": lambda b: b["period"]["leads"].update({"signup": 7}),
            "by_source_type": lambda b: b["by_source_type"]["last_touch"].update(
                {"Email": {"signup": 1}}),
            "by_source_type ": lambda b: b["by_source_type"]["first_touch"].update(
                {"Email": {"signup": 1}}),
            "funnel": lambda b: b["funnel"]["by_source"][0].update(
                {"demo_booked": b["funnel"]["by_source"][0]["demo_booked"] + 1}),
            "funnel ": lambda b: b["funnel"]["by_source"][0].update(
                {"readers": b["funnel"]["by_source"][0]["readers"] + 1}),
            "funnel  ": lambda b: b["funnel"]["total"].update({"pricing": 99}),
            "attribution_rows": lambda b: b["attribution_rows"][0].__setitem__(-1, 5),
            "time_to_convert": lambda b: b["time_to_convert"]["rows"][0].__setitem__(-1, 5),
            "days/2026-10-06": lambda b: b["days"][-2]["leads"].update({"signup": 4}),
        }
        for block, change in cases.items():
            with self.subTest(block=block):
                got = self.plant(change)
                self.assertIn(block.strip(), got, got)
                self.assertEqual(len(got), 1, got)

    def test_a_wrong_figure_is_withheld_in_the_file_with_the_reason(self):
        with mock.patch("skald.audit_leads.findings",
                        return_value={"period": ["first_touch.source differs"],
                                      "days/2026-10-06": ["leads differ"]}):
            got = leads.blob(self.config, NY, TODAY, JOURNEYS, date(2026, 9, 30))
        self.assertTrue(got["available"])
        self.assertEqual(got["period"]["state"], "withheld")
        self.assertIn("first_touch.source differs", got["period"]["why"])
        day = {d["day"]: d for d in got["days"]}["2026-10-06"]
        self.assertEqual(day["state"], "withheld")
        self.assertNotIn("leads", day)
        self.assertIn("leads differ", day["why"])
        self.assertIsInstance(got["funnel"], dict)
        self.assertNotIn("state", got["funnel"])
        self.assertEqual(set(got["withheld"]), {"period", "days/2026-10-06"})

    def test_all_agree_nothing_withheld(self):
        got = leads.blob(self.config, NY, TODAY, JOURNEYS, date(2026, 9, 30))
        self.assertEqual(got["withheld"], {})
        self.assertIsInstance(got["attribution_rows"], list)

    def test_a_recount_that_cannot_run_withholds_everything(self):
        with mock.patch("skald.audit_leads.audit_leads", side_effect=RuntimeError("x")):
            got = leads.blob(self.config, NY, TODAY, JOURNEYS, date(2026, 9, 30))
        for block in ("period", "by_source_type", "funnel", "attribution_rows",
                      "time_to_convert"):
            self.assertEqual(got[block]["state"], "withheld", block)
        self.assertTrue(all(d["state"] == "withheld" for d in got["days"]))

    def test_the_written_file_withholds_a_block_the_recount_disagrees_with(self):
        box = Sandbox(tz="America/New_York", mail=False)
        try:
            make_db(box.root / "payload.db")
            with open(box.config, "a") as handle:
                handle.write(f"leads:\n  db: {box.root / 'payload.db'}\n")
            box.log(day_lines(date(2026, 10, 6), 3, NY))
            code, _, err = box.run("--today", "2026-10-07", "collect", "--day", "2026-10-06")
            self.assertEqual(code, 0, err)
            real = audit_leads.findings

            def planted(built, audit):
                out = real(built, audit)
                out["attribution_rows"] = ["planted"]
                return out
            with mock.patch("skald.audit_leads.findings", side_effect=planted):
                code, _, err = box.run("--today", "2026-10-07", "dashboard")
            self.assertEqual(code, 0, err)
            got = json.loads((box.root / "www" / "example.com" / "data" / "leads.json")
                             .read_text())
            self.assertEqual(got["attribution_rows"], {"state": "withheld", "why": got[
                "attribution_rows"]["why"]})
            self.assertIn("planted", got["attribution_rows"]["why"])
            self.assertIsInstance(got["time_to_convert"], dict)
            self.assertNotIn("state", got["time_to_convert"])
        finally:
            box.close()


class TestDailyStep(Base):

    def test_daily_compares_every_block(self):
        ctx = mock.Mock(config=self.config, tz=NY,
                        now=datetime(2026, 10, 7, 12, tzinfo=NY))
        with mock.patch("skald.leads.site_journeys",
                        return_value=(JOURNEYS, date(2026, 9, 30))):
            self.assertEqual(audit_leads.daily(ctx, TODAY), [])
            # Every row still adds up (check passes); one label is wrong.
            wrong = [[*r[:4], "Email", *r[5:]] for r in leads.attribution(
                leads.read_rows(leads.connect(self.path)), NY,
                TODAY - timedelta(days=leads.DAYS - 1), TODAY)]
            with mock.patch("skald.leads.attribution", return_value=wrong):
                got = audit_leads.daily(ctx, TODAY)
        self.assertTrue(any("attribution_rows" in p for p in got), got)


# ------------------------------------------------------------------- A2

class TestAttributionRows(Base):

    def test_the_columns_and_a_row(self):
        got = self.raw()
        self.assertEqual(got["attribution_columns"], leads.ATTRIBUTION_COLUMNS)
        rows = got["attribution_rows"]
        first = [r for r in rows if r[0] == "2026-10-06" and r[1] == "waitlist"]
        self.assertIn(["2026-10-06", "waitlist", "qualified", "first", "Social media", "(none)",
                       "launch", "linkedin", "social", "/ca/fr/", False, 1], first)
        self.assertIn(["2026-10-06", "waitlist", "qualified", "last", "Search engine", "(none)",
                       "(none)", "(none)", "(none)", "/", False, 1], first)

    def test_rows_add_up_to_every_lead_of_each_day_once_per_touch(self):
        got = self.raw()
        for d in got["days"]:
            for t in ("first", "last"):
                n = sum(r[-1] for r in got["attribution_rows"] if r[0] == d["day"] and r[3] == t)
                self.assertEqual(n, sum(d["status"].values()), (d["day"], t))

    def test_check_catches_rows_that_do_not_add_up(self):
        got = self.raw()
        got["attribution_rows"][0][-1] += 1
        self.assertTrue(any("attribution_rows" in p for p in leads.check(got)))

    def test_paid_is_an_ad_click_id_or_a_paid_medium_never_fbclid(self):
        path = convert_db(self.dir / "convert.db")
        got = leads.blob({"leads": {"db": str(path)}}, NY, TODAY, [], TODAY, audited=False)
        booked = [r for r in got["attribution_rows"] if r[1] == "demo_booked"]
        first = next(r for r in booked if r[3] == "first")
        last = next(r for r in booked if r[3] == "last")
        self.assertEqual((first[4], first[7], first[8], first[10]),
                         ("Search engine", "google", "cpc", True))
        self.assertEqual((last[4], last[10]), ("Social media", False))
        self.assertEqual(audit_leads.compare(got, audit_leads.audit_leads(
            path, NY, TODAY - timedelta(days=leads.DAYS - 1), TODAY)), [])

    def test_only_the_180_days(self):
        got = self.raw(today=date(2027, 4, 10))
        self.assertEqual(got["attribution_rows"], [])
        got = self.raw(today=date(2027, 4, 3))     # the 6th is the oldest day kept
        self.assertTrue(got["attribution_rows"])
        self.assertEqual(min(r[0] for r in got["attribution_rows"]), "2026-10-06")


# ------------------------------------------------------------------- A3

class TestTimeToConvert(Base):

    def setUp(self):
        super().setUp()
        self.cpath = convert_db(self.dir / "convert.db")
        self.cconfig = {"leads": {"db": str(self.cpath)}}

    def ttc(self, config=None):
        return leads.blob(config or self.cconfig, NY, TODAY, [], TODAY,
                          audited=False)["time_to_convert"]

    def test_buckets_in_elapsed_hours(self):
        t = self.ttc()
        self.assertEqual(t["buckets"], leads.CONVERT_BUCKETS)
        got = {}
        for day, kind, bucket, n in t["rows"]:
            self.assertEqual(day, "2026-10-07")
            got[bucket] = got.get(bucket, 0) + n
        # The booked demo's first touch is the fixture's 1 October: 1-7 days too.
        self.assertEqual(got, {"<1h": 1, "<1d": 1, "1-7d": 3, "8-30d": 1, "31-90d": 1,
                               ">90d": 1, "clock_error": 1, "unknown": 3})
        self.assertEqual(t["known"], 8)          # the spam lead is left out
        self.assertIsNone(t["median_hours"])     # under 10 known

    def test_visits_before_the_lead(self):
        t = self.ttc()
        got = {}
        for _, _, bucket, n in t["visits_rows"]:
            got[bucket] = got.get(bucket, 0) + n
        self.assertEqual(got, {"1": 5, "2": 1, "3-5": 2, "11+": 1, "0": 1, "unknown": 2})

    def test_no_visits_column_no_visits_figures(self):
        t = self.ttc(self.config)                # the fixture without visits values
        self.assertIsNotNone(t["visits_rows"])   # the column exists, values unknown
        old = self.dir / "old.db"
        db = sqlite3.connect(old)
        db.execute("CREATE TABLE submissions (id integer, type text, created_at text, "
                   "status text, first_touch text)")
        db.execute("INSERT INTO submissions VALUES (1, 'signup', ?, 'new', ?)",
                   (MADE, touch(at=at(hours=3))))
        db.commit()
        db.close()
        got = leads.blob({"leads": {"db": str(old)}}, NY, TODAY, [], TODAY)
        self.assertIsNone(got["time_to_convert"]["visits_rows"])
        self.assertEqual(got["withheld"], {})

    def test_median_only_with_ten_known(self):
        rows = [("signup", "new", touch(at=at(hours=h)), None, 1) for h in range(1, 12)]
        path = convert_db(self.dir / "eleven.db", rows)
        t = self.ttc({"leads": {"db": str(path)}})
        self.assertEqual(t["known"], 11)
        self.assertEqual(t["median_hours"], 6.0)
        path = convert_db(self.dir / "ten.db", rows[:10])
        t = self.ttc({"leads": {"db": str(path)}})
        self.assertEqual(t["median_hours"], 5.5)

    def test_the_sql_recount_agrees_and_sees_a_change(self):
        got = leads.blob(self.cconfig, NY, TODAY, [], TODAY, audited=False)
        recount = audit_leads.audit_leads(self.cpath, NY, TODAY - timedelta(days=leads.DAYS - 1),
                                          TODAY)
        self.assertEqual(audit_leads.compare(got, recount), [])
        got["time_to_convert"]["median_hours"] = 1.0
        self.assertIn("time_to_convert", audit_leads.findings(got, recount))

    def test_check_catches_buckets_that_do_not_add_up(self):
        got = leads.blob(self.cconfig, NY, TODAY, [], TODAY, audited=False)
        got["time_to_convert"]["rows"][0][-1] += 1
        self.assertTrue(any("time_to_convert" in p for p in leads.check(got)))


class TestUnchanged(Base):

    def test_the_fixture_still_reconciles(self):
        got = leads.blob(self.config, NY, TODAY, JOURNEYS, date(2026, 9, 30))
        self.assertTrue(got["available"], got.get("error"))
        self.assertEqual(len(ROWS), 8)


class TestIndependence(unittest.TestCase):
    """The recount shares name lists only through classify.py: from leads.py it
    takes the read-only connection, the column check, the "(none)" label and
    the builder its daily step calls - never a name list or counting code."""

    def imports(self, module):
        import ast
        tree = ast.parse(Path(module.__file__).read_text())
        return {(n.module, a.name) for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.level for a in n.names}

    def test_the_recount_takes_its_name_lists_from_classify(self):
        got = self.imports(audit_leads)
        from_leads = {name for module, name in got if module == "leads"}
        self.assertLessEqual(from_leads, {"NONE", "_columns", "connect", "DAYS", "blob",
                                          "db_path", "site_journeys"})
        for name in ("PAID_CLICK_IDS", "PAID_MEDIUMS", "PRICING_PAGES", "FORM_PAGES"):
            self.assertIn(("classify", name), got)

    def test_leads_takes_the_same_lists_from_classify(self):
        from skald import classify
        got = self.imports(leads)
        for name in ("PAID_CLICK_IDS", "PAID_MEDIUMS", "PRICING_PAGES", "FORM_PAGES"):
            self.assertIn(("classify", name), got)
            self.assertIs(getattr(leads, name), getattr(classify, name))


if __name__ == "__main__":
    unittest.main()
