"""2.38.0: a person in two or more organisations sees their sites grouped by
organisation, in the sidebar's switcher (sites.json names each site's org)
and on the All sites page; a person in one sees the plain list as before.
Hosts are example.com/.example."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald import accounts, site_picker  # noqa: E402
from skald.helper_sessions import org_names  # noqa: E402

ALPHA, BETA = "owner@example.com", "bob@example.com"


class Grouped(TenantServer):
    def setUp(self):
        super().setUp()
        listed = {"schema_version": 1, "sites": [{"name": A, "slug": A, "path": f"{A}/"},
                                                 {"name": B, "slug": B, "path": f"{B}/"}],
                  "current": None}
        (self.out / "sites.json").write_text(json.dumps(listed))
        for s in (A, B):
            (self.out / s / "data" / "sites.json").write_text(json.dumps({**listed,
                                                                           "current": s}))

    def join_beta(self):
        db = self.db()
        try:
            accounts.add_member(db, self.beta["id"], self.uids[ALPHA], "viewer", "cli")
        finally:
            db.close()

    def test_one_organisation_gets_the_plain_list(self):
        cookie, _ = self.session(ALPHA)
        for path in ("/traffic/sites.json", f"/traffic/{A}/data/sites.json"):
            got = self.call("GET", path, cookie=cookie).json["sites"]
            self.assertEqual([(s["name"], s.get("org")) for s in got], [(A, None)], path)
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertNotIn('class="pk-org"', page)

    def test_two_organisations_are_named_on_each_site(self):
        self.join_beta()
        cookie, _ = self.session(ALPHA)
        for path in ("/traffic/sites.json", f"/traffic/{A}/data/sites.json"):
            got = self.call("GET", path, cookie=cookie).json["sites"]
            self.assertEqual([(s["name"], s["org"]) for s in got],
                             [(A, "Alpha"), (B, "Beta")], path)
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertEqual(page.count('class="pk-org"'), 2)
        self.assertLess(page.index("Alpha <small>1 site</small>"),
                        page.index("Beta <small>1 site</small>"))
        # Beta's own owner is in one organisation: no names, and nothing of Alpha.
        cookie, _ = self.session(BETA)
        got = self.call("GET", "/traffic/sites.json", cookie=cookie).json["sites"]
        self.assertEqual([(s["name"], s.get("org")) for s in got], [(B, None)])
        self.assertNotIn("Alpha", self.call("GET", "/traffic/", cookie=cookie).raw.decode())


class Groups(unittest.TestCase):
    def test_org_names_only_for_two_or_more_with_sites(self):
        self.assertEqual(org_names({"orgs": [{"name": "Alpha", "sites": [A]}]}), {})
        self.assertEqual(org_names({"orgs": [{"name": "Alpha", "sites": [A]},
                                             {"name": "Empty", "sites": []}]}), {})
        self.assertEqual(org_names({"orgs": [{"name": "Alpha", "sites": [A]},
                                             {"name": "Beta", "sites": [B]}]}),
                         {A: "Alpha", B: "Beta"})
        self.assertEqual(org_names({}), {})

    def test_render_groups_in_the_sites_order_with_other_sites_last(self):
        sites = [{"name": n, "path": f"{n}/"} for n in ("c.example", A, B)]
        page = site_picker.render(sites, datetime(2026, 10, 26, tzinfo=timezone.utc),
                                  orgs={A: "Alpha", B: "Alpha"}, add_href="a/#settings")
        self.assertLess(page.index("Alpha <small>2 sites</small>"),
                        page.index("Other sites <small>1 site</small>"))
        self.assertIn("Add a site", page)
        plain = site_picker.render(sites, datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertNotIn('class="pk-org"', plain)


if __name__ == "__main__":
    unittest.main()
