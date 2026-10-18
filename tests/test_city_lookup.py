"""A visit's city from the city file (`logs.city_db`), on both roads.

What is pinned: the reader takes DB-IP's "IP to City Lite" record (city,
first subdivision, country, location) and tolerates anything else; the label
is "City, Region, CC"; a city in another country than the line's own is not
used; readers by city are stored (people_city_visits) and add up, the audit
recounts them by its own road and agrees, and a changed row is caught; a day
without a city file stores no city and journeys carry none; a period sums
cities only when each of its days has them; the live snapshot's real-time
cities (with their points) agree with the audit; the kept visit carries the
city; the container's SKALD_CITY_DB; DB-IP's credit for a city file.
Addresses are RFC 5737 documentation ranges.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_cities  # noqa: E402
from skald.conversions import geo  # noqa: E402

from conversions_support import city_record, mmdb  # noqa: E402
from support import GPTBOT, Sandbox, line  # noqa: E402

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
NOON = datetime(DAY.year, DAY.month, DAY.day, 12, tzinfo=UTC)
TORONTO = "Toronto, Ontario, CA"
NETS = {
    "203.0.113.0/26": city_record("Toronto", "Ontario", "CA", 43.6532, -79.3832),
    "203.0.113.64/26": city_record("Berlin", "Land Berlin", "DE", 52.52, 13.405),
    "203.0.113.128/26": city_record("Singapore", "Singapore", "SG", 1.2897, 103.8501),
    "198.51.100.0/24": "FR",                     # a country record: no city
}


def write_db(folder: Path, nets=NETS, kind: str = "DBIP-City-Lite") -> Path:
    path = folder / "city.mmdb"
    path.write_bytes(mmdb(nets, kind=kind))
    return path


class TestReader(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = write_db(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_dbip_city_record(self):
        self.assertEqual(geo.city(self.db, "203.0.113.7"),
                         {"city": "Toronto", "region": "Ontario", "country": "CA",
                          "lat": 43.653, "lon": -79.383})
        self.assertEqual(geo.city_label(geo.city(self.db, "203.0.113.7")), TORONTO)

    def test_no_city_no_answer(self):
        for ip in ("198.51.100.4", "192.0.2.1", "not an address", "", None):
            self.assertIsNone(geo.city(self.db, ip), ip)
        self.assertIsNone(geo.city(Path(self.tmp.name) / "missing.mmdb", "203.0.113.7"))
        self.assertIsNone(geo.city(None, "203.0.113.7"))
        junk = Path(self.tmp.name) / "junk.mmdb"
        junk.write_bytes(b"not a database")
        self.assertIsNone(geo.city(junk, "203.0.113.7"))

    def test_the_region_is_left_out_when_it_is_the_city(self):
        self.assertEqual(geo.city_label(geo.city(self.db, "203.0.113.130")), "Singapore, SG")

    def test_a_tolerant_reader(self):
        odd = {"192.0.2.0/28": {"city": {"names": {"de": "München"}},
                                "country": {"iso_code": "de"},
                                "location": {"latitude": "48", "longitude": 11.5}},
               "192.0.2.16/28": {"city": {"names": {"en": "  Dallas,  Fort   Worth "}},
                                 "subdivisions": "Texas", "country": "US",
                                 "location": {"latitude": 95.0, "longitude": -97.0}},
               "192.0.2.32/28": {"city": "Nowhere", "country": {"iso_code": "ZZ"}},
               "192.0.2.48/28": {"city": {"names": {"en": "Quebec"}},
                                 "subdivisions": [], "country": {"iso_code": "XX"}}}
        db = write_db(Path(self.tmp.name), odd)
        self.assertEqual(geo.city(db, "192.0.2.1"),
                         {"city": "München", "region": "", "country": "DE", "lat": None,
                          "lon": None})
        got = geo.city(db, "192.0.2.17")
        self.assertEqual((got["region"], got["country"], got["lat"]), ("", "", None))
        self.assertEqual(geo.city_label(got), "Dallas Fort Worth")
        self.assertIsNone(geo.city(db, "192.0.2.33"))
        self.assertEqual(geo.city_label(geo.city(db, "192.0.2.49")), "Quebec")

    def test_the_fill_caches_keeps_points_and_respects_the_line_s_country(self):
        fill = geo.Cities(self.db)
        self.assertEqual(fill("203.0.113.7"), TORONTO)
        self.assertEqual(fill("203.0.113.7", "ca"), TORONTO)
        self.assertEqual(fill("203.0.113.7", "US"), "", "a city of another country")
        self.assertEqual(fill("198.51.100.4", "FR"), "")
        self.assertEqual(fill.points, {TORONTO: (43.653, -79.383)})
        self.assertEqual(set(fill.seen), {"203.0.113.7", "198.51.100.4"})

    def test_the_audit_s_own_label_agrees(self):
        mine = audit_cities.fill({"logs": {"city_db": str(self.db)}})
        main = geo.Cities(self.db)
        for ip, cc in (("203.0.113.7", ""), ("203.0.113.70", "DE"), ("203.0.113.70", "PL"),
                       ("203.0.113.130", "SG"), ("198.51.100.4", "FR"), ("192.0.2.1", "")):
            self.assertEqual(mine(ip, cc), main(ip, cc), ip)
        self.assertIsNone(audit_cities.fill({}))

    def test_the_setting_and_the_credit(self):
        from skald.config import country_credit
        self.assertEqual(geo.city_database({"logs": {"city_db": "/g/c.mmdb"}}), "/g/c.mmdb")
        self.assertIsNone(geo.city_database({"logs": {"city_db": ""}}))
        self.assertIsNone(geo.cities({}))
        self.assertEqual(country_credit({"logs": {"city_db": str(self.db)}}),
                         ("IP Geolocation by DB-IP", "https://db-ip.com"))
        other = write_db(Path(self.tmp.name), kind="Test-City")
        self.assertIsNone(country_credit({"logs": {"city_db": str(other)}}))


class Case(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.city_db = write_db(self.box.root)

    def tearDown(self):
        self.box.close()

    def set_city_db(self):
        text = self.box.config.read_text()
        self.box.config.write_text(text.replace(
            "  format: auto\n", f"  format: auto\n  city_db: {self.city_db}\n", 1))

    def run_ok(self, *argv):
        code, out, err = self.box.run("--today", TODAY, *argv)
        self.assertEqual(code, 0, err + out)
        return out

    def stored(self, day: date = DAY) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return dict(db.execute(
                "SELECT name, n FROM counts WHERE site = 'example.com' AND day = ? "
                "AND kind = 'people_city_visits'", (day.isoformat(),)).fetchall())
        finally:
            db.close()

    def journeys(self) -> list[dict]:
        db = sqlite3.connect(str(self.box.db))
        try:
            return [json.loads(d) for (d,) in db.execute(
                "SELECT data FROM journeys WHERE site = 'example.com' AND day = ? ORDER BY seq",
                (DAY.isoformat(),))]
        finally:
            db.close()


def visitors(day: date = DAY) -> list[str]:
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    return [line(noon, "203.0.113.7", "/", country="CA"),
            line(noon + timedelta(minutes=1), "203.0.113.8", "/pricing", country="CA"),
            line(noon + timedelta(minutes=2), "203.0.113.70", "/", country="DE"),
            line(noon + timedelta(minutes=3), "203.0.113.71", "/", country="PL"),   # not Berlin
            line(noon + timedelta(minutes=4), "198.51.100.9", "/", country="FR"),   # no city
            line(noon + timedelta(minutes=5), "203.0.113.9", "/", GPTBOT, country="CA")]


class TestEndToEnd(Case):

    def test_cities_are_stored_add_up_and_the_audit_agrees(self):
        self.set_city_db()
        self.box.log(visitors())
        self.run_ok("collect")
        self.assertEqual(self.stored(), {TORONTO: 2, "Berlin, Land Berlin, DE": 1, "Unknown": 2})
        out = self.run_ok("audit")
        self.assertIn("all match", out)
        cities = [j.get("city") for j in self.journeys()]
        self.assertEqual(sorted(c for c in cities if c), ["Berlin, Land Berlin, DE",
                                                         TORONTO, TORONTO])
        self.assertEqual(len(cities), 5, "people only: the crawler is in no city")

    def test_a_changed_row_is_caught(self):
        self.set_city_db()
        self.box.log(visitors())
        self.run_ok("collect")
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE counts SET n = 1 WHERE kind = 'people_city_visits' AND name = ?",
                       (TORONTO,))
            db.execute("UPDATE counts SET n = 3 WHERE kind = 'people_city_visits' "
                       "AND name = 'Unknown'")
        db.close()
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertNotEqual(code, 0)
        self.assertIn(f"readers by city: {TORONTO}", out + err)

    def test_without_a_file_no_city(self):
        self.box.log(visitors())
        self.run_ok("collect")
        self.assertEqual(self.stored(), {})
        self.assertFalse(any("city" in j for j in self.journeys()))
        self.assertIn("all match", self.run_ok("audit"))

    def test_a_period_sums_cities_only_when_every_day_has_them(self):
        from skald.store import History
        before = DAY - timedelta(days=1)
        self.box.log(visitors(before) + visitors())
        self.run_ok("collect", "--day", before.isoformat())
        self.set_city_db()
        self.run_ok("collect")
        self.assertEqual(self.stored(before), {})
        with History(self.box.db) as h:
            one = h.period("example.com", DAY, DAY).totals.groups
            two = h.period("example.com", before, DAY).totals.groups
            days = h.periods("example.com", before, DAY)
        from skald.classify import Group
        self.assertEqual(one[Group.PEOPLE].by["city"][TORONTO], 2)
        self.assertNotIn("city", two[Group.PEOPLE].by)
        self.assertIn("city", days[DAY].totals.groups[Group.PEOPLE].by)
        self.assertNotIn("city", days[before].totals.groups[Group.PEOPLE].by)
        # The older day is audited without cities, the newer with them.
        self.assertIn("all match", self.run_ok("audit", "--day", before.isoformat()))
        self.assertIn("all match", self.run_ok("audit"))


LIVE_DAY = date(2026, 10, 7)
LIVE_NOON = datetime(2026, 10, 7, 12, tzinfo=UTC)


class TestLive(Case):

    def live(self, lines):
        self.box.log(lines)
        stamp = LIVE_NOON.timestamp() - 60
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        code, out, err = self.box.run("--today", LIVE_DAY.isoformat(), "live")
        self.assertEqual(code, 0, err)
        return json.loads((self.box.root / "live-example.com.json").read_text())

    def audit(self):
        return self.box.run("--today", LIVE_DAY.isoformat(), "audit", "--live")

    def morning(self):
        m = lambda minutes: LIVE_NOON - timedelta(minutes=minutes)  # noqa: E731
        return [line(m(180), "203.0.113.70", "/", country="DE"),             # not active
                line(m(25), "203.0.113.7", "/", country="CA"),
                line(m(3), "203.0.113.8", "/docs", country="CA"),
                line(m(2), "198.51.100.9", "/", country="FR"),                # no city
                line(m(1), "203.0.113.130", "/", country="SG")]

    def test_real_time_cities_with_their_points_and_the_audit_agrees(self):
        self.set_city_db()
        snap = self.live(self.morning())
        part = snap["realtime"]
        self.assertEqual(part["cities"][TORONTO],
                         {"visits": 2, "active": 2, "lat": 43.653, "lon": -79.383})
        self.assertEqual(part["cities"]["Berlin, Land Berlin, DE"]["active"], 0)
        self.assertEqual(part["cities"]["Singapore, SG"]["visits"], 1)
        self.assertEqual(len(part["cities"]), 3, "FR has no city")
        self.assertEqual(snap["breakdowns"]["by"]["city"]["Unknown"], 1)
        self.assertEqual({v["city"] for v in part["newest"]},
                         {TORONTO, "Berlin, Land Berlin, DE", "Singapore, SG", ""})
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("audit ok: live", out)

    def test_without_a_file_the_part_has_no_cities(self):
        snap = self.live(self.morning())
        self.assertNotIn("cities", snap["realtime"])
        self.assertNotIn("city", snap["breakdowns"]["by"])
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)

    def test_a_folded_tail(self):
        from skald import realtime
        cities = {f"Town {i}, CA": {"visits": 1, "active": 0} for i in range(70)}
        cities["Toronto, Ontario, CA"] = {"visits": 1, "active": 1}
        got = realtime.city_rows(cities, {TORONTO: (43.65, -79.38)})
        self.assertEqual(len(got), realtime.TOP_CITIES + 1)
        self.assertEqual(got[TORONTO], {"visits": 1, "active": 1, "lat": 43.65, "lon": -79.38})
        self.assertEqual(got["(all others)"], {"visits": 71 - realtime.TOP_CITIES, "active": 0})
        self.assertEqual(sum(r["visits"] for r in got.values()), 71)


class TestTheApp(Case):

    def test_app_json_carries_the_cities(self):
        self.set_city_db()
        text = self.box.config.read_text().replace("  app: false\n", "  app: true\n")
        self.box.config.write_text(text)
        self.box.log(visitors())
        self.run_ok("collect")
        self.run_ok("dashboard")
        app = json.loads((self.box.root / "www" / "example.com" / "data" / "app.json").read_text())
        self.assertIs(app["cities"], True)
        day = next(d for d in app["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["by"]["city"][TORONTO], 2)
        self.assertEqual(sum(day["by"]["city"].values()), day["readers"])
        self.assertIn(TORONTO, {j.get("city") for j in app["journeys"]})

    def test_the_words_on_screen(self):
        js = ROOT / "skald" / "webapp" / "js"
        self.assertIn('city: { name: "City"', (js / "drill.js").read_text())
        places = (js / "tabs" / "tr-places.js").read_text()
        for words in ("Visitors by city", "Search cities", "Cities are not recorded: no city file is set",
                      "counted before the city file was set"):
            self.assertIn(words, places)
        rt = (js / "tabs" / "realtime.js").read_text()
        self.assertIn('"By city"', rt)
        self.assertIn("city not recorded", rt)
        self.assertIn('["City", j.city', (js / "tabs" / "visitlist.js").read_text())
        # The visitor drawer (visitor.js; Find a person opens it too): the city in
        # its summary and under each visit's country.
        drawer = (js / "tabs" / "visitor.js").read_text()
        self.assertIn('cell("City", h("span", { class: "named", title: cityName(latest.city) }', drawer)
        self.assertIn("city(latest.city)", drawer)
        self.assertIn("cityPlace(v.city)", drawer)
        self.assertIn('city: raw.city || ""', drawer)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_map_places_a_city_with_the_shapes_projection(self):
        """rt-map.js project() is tools/world-map.py's Equal Earth: Singapore's
        extra point and the map's height land where the shapes file has them."""
        script = ('globalThis.addEventListener = () => {};'
                  'const m = await import(process.argv[1]);'
                  'const w = await import(process.argv[2]);'
                  'console.log(JSON.stringify({sg: m.project(103.82, 1.35), want: w.WORLD.points.SG,'
                  ' bottom: m.project(0, -58)[1], height: w.WORLD.height,'
                  ' placed: m.placed({"A, CA": {visits: 1, lat: 1, lon: 2}, "(all others)": {visits: 3},'
                  ' "B, CA": {visits: 1}}).map((x) => x[0])}));')
        done = subprocess.run(["node", "--input-type=module", "-e", script,
                               (ROOT / "skald/webapp/js/tabs/rt-map.js").as_uri(),
                               (ROOT / "skald/webapp/vendor/world-110m.js").as_uri()],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertAlmostEqual(got["sg"][0], got["want"][0], delta=0.1)
        self.assertAlmostEqual(got["sg"][1], got["want"][1], delta=0.1)
        self.assertAlmostEqual(got["bottom"], got["height"], delta=0.1)
        self.assertEqual(got["placed"], ["A, CA"])


class TestKeptVisit(unittest.TestCase):

    def test_the_kept_visit_holds_the_city(self):
        from skald.conversions import store
        from skald.people import visits
        j = {"source": "Direct or unknown", "country": "CA", "city": TORONTO, "pages": 2,
             "trail": [["/", "page"], ["/pricing", "page"]], "at": [0, 30], "seconds": 30}
        who = {"ip": "203.0.113.7", "user_agent": "test", "first": NOON, "last": NOON}
        db = store.connect(":memory:")
        try:
            self.assertEqual(visits.write(db, "example.com", DAY.isoformat(), [j, dict(j, city=None)],
                                          [who, who], "whole"), (2, 4))
            got = [r[0] for r in db.execute("SELECT city FROM visits ORDER BY seq")]
        finally:
            db.close()
        self.assertEqual(got, [TORONTO, None])


class TestContainer(unittest.TestCase):

    def test_skald_city_db(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docker"))
        import entrypoint
        self.assertNotIn("city_db", entrypoint.render_config({})["logs"])
        self.assertNotIn("city_db", entrypoint.render_config({"SKALD_CITY_DB": " "})["logs"])
        cfg = entrypoint.render_config({"SKALD_CITY_DB": " /geoip/dbip-city-lite.mmdb "})
        self.assertEqual(cfg["logs"]["city_db"], "/geoip/dbip-city-lite.mmdb")


if __name__ == "__main__":
    unittest.main()
