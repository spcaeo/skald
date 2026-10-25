"""Where visitors came from, all your sites (across_sites.py), under the site
picker: one row per site the viewer may see, Search, Social and its top
networks, AI and Direct, for today, 7, 30 or 90 days.

What is pinned:
- only verified days are summed; a withheld or missing day is counted and named;
- a figure no verified day recorded says "Not recorded", never 0; a network
  figure whose day does not add up says "Withheld";
- today is the live count, only while it is "ok";
- each figure links to that site's Sources with the range, the segment and
  the network in the address;
- the rights rule: the picker of one organisation never shows another's site,
  its row or its figures; the static picker shows every site of the install.
Hosts example.com and .example; no address.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, Server  # noqa: E402

from skald import across_sites, site_picker  # noqa: E402

ANCHOR = "2026-10-10"
BY = {"Search engine": 40, "Social media": 9, "AI assistant": 3, "Direct or unknown": 20,
      "Other website": 4}
NETS = {"visits": 76, "social": 9, "networks": {"x": 5, "linkedin": 3, "other": 1},
        "via": {"x": {"t.co": 5}, "linkedin": {"lnkd.in": 3}, "other": {"(utm_source)": 1}},
        "landings": {"x": {"/": 5}, "linkedin": {"/": 3}, "other": {"/": 1}}}


def write_site(out: Path, site: str, *, states=None, blob_days=None, live="ok", by=BY,
               nets=NETS):
    """Seven days ending ANCHOR: app.json and campaigns.json as the dashboard writes them."""
    data = out / site / "data"
    data.mkdir(parents=True, exist_ok=True)
    days = [f"2026-10-{d:02d}" for d in range(4, 11)]
    states = states or {}
    blob_days = set(days if blob_days is None else blob_days)
    app = {"anchor": ANCHOR, "today": "2026-10-11",
           "days": [{"day": d, "state": states.get(d, "ok"),
                     **({"by": {"source": dict(by)}} if states.get(d, "ok") == "ok" else {})}
                    for d in days],
           "live": {"day": "2026-10-11", "state": live,
                    "figures": {"by": {"source": {"Search engine": 2, "Social media": 1,
                                                  "Direct or unknown": 1}}}},
           "journeys": []}
    camp = {"schema_version": 1,
            "days": [{"day": d, "state": states.get(d, "ok"),
                      "social_networks": dict(nets) if d in blob_days else None} for d in days],
            "today": {"state": live, "social_networks": {
                "visits": 4, "social": 1, "networks": {"x": 1}, "via": {"x": {"t.co": 1}},
                "landings": {"x": {"/": 1}}}}}
    (data / "app.json").write_text(json.dumps(app))
    (data / "campaigns.json").write_text(json.dumps(camp))


class TestTheFigures(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        across_sites._CACHE.clear()

    def tearDown(self):
        self._tmp.cleanup()

    def test_seven_verified_days(self):
        write_site(self.out, "example.com")
        got = across_sites.figures(self.out, "example.com", "7d")
        self.assertEqual((got["days"], got["verified"], got["withheld"]), (7, 7, 0))
        self.assertEqual(got["sources"], {"search": 280, "social": 63, "ai": 21, "direct": 140})
        self.assertEqual(got["networks"]["x"], 35)
        self.assertEqual(got["networks"]["linkedin"], 21)
        self.assertEqual(got["networks"]["facebook"], 0, "recorded every day: none from it")

    def test_withheld_and_missing_days_are_left_out_and_named(self):
        write_site(self.out, "example.com", states={"2026-10-09": "withheld"})
        got = across_sites.figures(self.out, "example.com", "30d")
        self.assertEqual((got["days"], got["verified"], got["withheld"], got["missing"]),
                         (30, 6, 1, 23))
        self.assertEqual(got["sources"]["search"], 240)
        self.assertEqual(across_sites._covered(got), "6 of 30 days verified, 1 withheld")

    def test_not_recorded_is_never_zero(self):
        write_site(self.out, "example.com", blob_days=[])
        got = across_sites.figures(self.out, "example.com", "7d")
        self.assertIsNone(got["networks"]["x"])
        html = across_sites._table(self.out, [{"name": "example.com", "path": "example.com/"}], "7d")
        cells = re.findall(r"<td>(.*?)</td>", html)
        self.assertEqual(len(cells), 10)
        for c in cells[2:8]:                       # the six networks
            self.assertIn("Not recorded", c)
        self.assertNotIn(">0<", html)
        # A site with no figures written at all: every cell says so.
        none = across_sites.figures(self.out, "nothing.example", "7d")
        self.assertEqual(set(none["sources"].values()), {None})

    def test_networks_over_fewer_days_say_so(self):
        write_site(self.out, "example.com", blob_days=["2026-10-09", "2026-10-10"])
        got = across_sites.figures(self.out, "example.com", "7d")
        self.assertEqual(got["networks"]["x"], 10)
        self.assertEqual(across_sites._covered(got), "7 of 7 days verified, networks over 2")

    def test_a_day_that_does_not_add_up_withholds_the_networks(self):
        write_site(self.out, "example.com", nets=dict(NETS, social=8))
        got = across_sites.figures(self.out, "example.com", "7d")
        self.assertEqual(got["networks"]["x"], across_sites.WITHHELD)
        # Adds up on its own, but not to the Sources row (9 Social media readers).
        write_site(self.out, "two.example", nets=dict(NETS, social=8, networks={"x": 5, "linkedin": 3}))
        self.assertEqual(across_sites.figures(self.out, "two.example", "7d")["networks"]["x"],
                         across_sites.WITHHELD)
        html = across_sites._table(self.out, [{"name": "example.com"}], "7d")
        self.assertIn("Withheld", html)

    def test_today_is_the_live_count_while_ok(self):
        write_site(self.out, "example.com")
        got = across_sites.figures(self.out, "example.com", "today")
        self.assertEqual(got["sources"]["social"], 1)
        self.assertEqual(got["networks"]["x"], 1)
        write_site(self.out, "held.example", live="withheld")
        got = across_sites.figures(self.out, "held.example", "today")
        self.assertIsNone(got["sources"]["search"])
        self.assertEqual(got["missing"], 1)

    def test_each_figure_links_to_the_sites_sources(self):
        write_site(self.out, "example.com")
        html = across_sites.section(self.out, [{"name": "example.com", "path": "example.com/"}])
        self.assertIn('href="example.com/#traffic/sources?range=7d&amp;src_seg=social&amp;net=x"',
                      html)
        self.assertIn('href="example.com/#traffic/sources?src_seg=social&amp;net=linkedin"', html)
        self.assertIn('href="example.com/#traffic/sources?range=90d"', html)
        # One panel per range, each picked by the address; Today's last (shown by default).
        ids = re.findall(r'<section class="ax-r" id="([a-z0-9-]+)"', html)
        self.assertEqual(ids, ["sources-7d", "sources-30d", "sources-90d", "sources-today"])
        for k in ("today", "7d", "30d", "90d"):
            self.assertIn(f'href="#sources-{k}"', html)
        self.assertEqual(across_sites.section(self.out, []), "")

    def test_the_static_picker_shows_every_site(self):
        write_site(self.out, "one.example")
        write_site(self.out, "two.example")
        page = site_picker.static_page(["one.example", "two.example"],
                                       datetime(2026, 10, 11, 14, tzinfo=timezone.utc), self.out)
        self.assertIn("Where visitors came from, all your sites", page)
        for site in ("one.example", "two.example"):
            self.assertIn(f'<th scope="row"><a href="{site}/">{site}</a>', page)


class TestTheRightsRule(Server):

    def setUp(self):
        super().setUp()
        across_sites._CACHE.clear()
        listed = [{"name": s, "slug": s, "path": f"{s}/", "views": []} for s in (A, B)]
        (self.out / "sites.json").write_text(json.dumps({"schema_version": 1, "sites": listed,
                                                         "current": None}))
        write_site(self.out, A, by={**BY, "Search engine": 111})
        write_site(self.out, B, by={**BY, "Search engine": 222})

    def test_each_org_sees_only_its_own_sites_row(self):
        bob = self.login("bob@example.com").cookie
        page = self.call("GET", "/traffic/", cookie=bob).raw.decode()
        self.assertIn("Where visitors came from, all your sites", page)
        self.assertIn(f'<th scope="row"><a href="{B}/">{B}</a>', page)
        self.assertIn("1,554", page)            # 222 a day, seven days
        self.assertNotIn(A, page)
        self.assertNotIn("777", page)           # A's 111 a day
        alice = self.login().cookie
        page = self.call("GET", "/traffic/", cookie=alice).raw.decode()
        self.assertIn(f'<th scope="row"><a href="{A}/">{A}</a>', page)
        self.assertNotIn(B, page)

    def test_no_session_no_table(self):
        got = self.call("GET", "/traffic/")
        self.assertEqual(got.status, 401)
        self.assertNotIn(b"Where visitors came from", got.raw)


if __name__ == "__main__":
    unittest.main()
