"""/traffic/<site>/ for a known site with no dashboard page (setup_page.py).

Owner-reported (21 Oct 2026): a site added in the dashboard, its wizard at
step 3 of 5, kept its card in the site picker but its address answered
nginx's bare 404. Now every dashboard write puts a page in the folder of a
waiting or removed site that has none: what state it is in, the step, the
wizard's link (as the picker's badge has it) and the troubleshooting guide.
It never replaces a real page.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import SECRETS, Sandbox, day_lines  # noqa: E402

from skald import accounts, connections_api, setup_page  # noqa: E402
from skald.accounts import orgs, site_configs, site_setup  # noqa: E402

SHOP = "shop.example.com"
GONE = "gone.example.com"
MAIN = "example.com"


class SetupPages(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        env = mock.patch.dict("os.environ", SECRETS)
        env.start()
        self.addCleanup(env.stop)
        self.accounts = self.box.root / "accounts.sqlite"
        db = accounts.connect(self.accounts)
        try:
            org = accounts.create_org(db, "Org", "cli")
            self.org = org["id"]
            orgs.assign_site(db, MAIN, org["id"], "cli")
            site_configs.create(db, org["id"], SHOP, "cli")
            site_setup.save(db, org["id"], SHOP, "cli", step=3)
            site_configs.create(db, org["id"], GONE, "cli")
            site_setup.save(db, org["id"], GONE, "cli", step=3)
            site_configs.remove(db, org["id"], GONE, "cli")
        finally:
            db.close()
        self.box.log(day_lines(date(2026, 10, 5), 3) + day_lines(date(2026, 10, 6), 3))
        self.out = self.box.root / "www"
        self.config = {"history": {"db": str(self.box.db)}}

    def page(self, name: str) -> str:
        return (self.out / name / "index.html").read_text()

    def drawn(self, name: str) -> None:
        (self.out / name / "data").mkdir(parents=True, exist_ok=True)
        (self.out / name / "index.html").write_text("<!doctype html><p>the dashboard</p>")

    def write(self, sites=None) -> list:
        sites = sites if sites is not None else [{"name": MAIN, "waiting": False},
                                                 {"name": SHOP, "waiting": True}]
        return setup_page.write_missing(self.out, sites, self.config, self.box.config)

    def test_a_waiting_site_with_no_page_gets_one(self):
        self.drawn(MAIN)
        written = self.write()
        self.assertIn(self.out / SHOP / "index.html", written)
        got = self.page(SHOP)
        self.assertIn(f"{SHOP} is waiting for its first log lines", got)
        self.assertIn("step 3 of 5", got)
        self.assertIn(f'href="../{MAIN}/#settings/sitesadmin?setup={SHOP}">Continue setup</a>',
                      got)
        self.assertIn(f'href="../{MAIN}/#help?part=troubleshooting-connections"', got)
        self.assertIn('http-equiv="refresh"', got)
        self.assertIn(setup_page.MARK, got)
        self.assertNotIn("203.0.113", got)              # no address, no figure

    def test_the_link_matches_the_pickers_badge(self):
        self.drawn(MAIN)
        self.write()
        words, kind = connections_api.badges(self.config, self.box.root, self.box.config,
                                             [SHOP])[SHOP]
        self.assertEqual(kind, "setup")
        self.assertIn(f"#settings/sitesadmin?{kind}={SHOP}", self.page(SHOP))

    def test_a_finished_setup_offers_the_test(self):
        db = accounts.connect(self.accounts)
        try:
            site_setup.save(db, self.org, SHOP, "cli", step=5, done=True)
        finally:
            db.close()
        self.drawn(MAIN)
        self.write()
        got = self.page(SHOP)
        self.assertIn(f"#settings/sitesadmin?test={SHOP}\">Test the connection</a>", got)
        self.assertNotIn("Continue setup", got)

    def test_a_real_page_is_never_replaced(self):
        self.drawn(MAIN)
        self.drawn(SHOP)
        self.assertNotIn(self.out / SHOP / "index.html", self.write())
        self.assertIn("the dashboard", self.page(SHOP))
        # The first-page notice (first_page.py) is not this page either.
        (self.out / SHOP / "index.html").write_text("<title>getting ready</title>")
        self.write()
        self.assertEqual(self.page(SHOP), "<title>getting ready</title>")

    def test_its_own_page_is_kept_current_and_then_replaced(self):
        self.drawn(MAIN)
        self.write()
        db = accounts.connect(self.accounts)
        try:
            site_setup.save(db, self.org, SHOP, "cli", step=4)
        finally:
            db.close()
        self.write()
        self.assertIn("step 4 of 5", self.page(SHOP))
        self.assertEqual(self.write(), [], "unchanged: not written again")
        self.drawn(SHOP)                                 # its own run draws it
        self.write()
        self.assertIn("the dashboard", self.page(SHOP))

    def test_no_drawn_dashboard_no_wizard_link(self):
        got = (self.write(), self.page(SHOP))[1]
        self.assertNotIn("Continue setup", got)
        self.assertNotIn("#help", got)
        self.assertIn('<a href="../">All sites</a>', got)

    def test_a_removed_site_says_so_and_offers_no_setup(self):
        self.drawn(MAIN)
        self.write()
        got = self.page(GONE)
        self.assertIn(f"{GONE} was removed", got)
        self.assertIn("Its setup had reached step 3 of 5.", got)
        self.assertNotIn("waiting for its first log lines", got)
        self.assertNotIn("sitesadmin", got)
        self.assertNotIn('http-equiv="refresh"', got)

    def test_the_picker_offers_no_continue_for_a_removed_site(self):
        got = connections_api.badges(self.config, self.box.root, self.box.config, [SHOP, GONE])
        self.assertIn(SHOP, got)
        self.assertNotIn(GONE, got)

    def test_a_site_with_data_or_unknown_gets_nothing(self):
        self.write([{"name": MAIN, "waiting": False}])
        self.assertFalse((self.out / MAIN / "index.html").exists())
        self.assertFalse((self.out / SHOP / "index.html").exists())  # not listed as waiting

    def test_a_failure_never_breaks_the_dashboard(self):
        said = []
        with mock.patch.object(setup_page, "states", side_effect=RuntimeError("boom")):
            got = setup_page.write_missing(self.out, [], self.config, self.box.config,
                                           said.append)
        self.assertEqual(got, [])
        self.assertEqual(said, ["setup pages: RuntimeError: boom"])


class InTheRuns(unittest.TestCase):
    """End to end: a live run writes the removed site's page, and the waiting
    site's own run draws its dashboard over its page."""

    def test_live_run(self):
        box = Sandbox()
        self.addCleanup(box.close)
        env = mock.patch.dict("os.environ", SECRETS)
        env.start()
        self.addCleanup(env.stop)
        db = accounts.connect(box.root / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Org", "cli")
            orgs.assign_site(db, MAIN, org["id"], "cli")
            site_configs.create(db, org["id"], GONE, "cli")
            site_setup.save(db, org["id"], GONE, "cli", step=3)
            site_configs.remove(db, org["id"], GONE, "cli")
            site_configs.create(db, org["id"], SHOP, "cli")
            site_setup.save(db, org["id"], SHOP, "cli", step=3)
        finally:
            db.close()
        box.log(day_lines(date(2026, 10, 5), 3) + day_lines(date(2026, 10, 6), 3))
        code, out, err = box.run("--today", "2026-10-06", "live")
        self.assertEqual(code, 0, err)
        www = box.root / "www"
        gone = (www / GONE / "index.html").read_text()
        self.assertIn(f"{GONE} was removed", gone)
        shop = (www / SHOP / "index.html").read_text()
        self.assertNotIn(setup_page.MARK, shop, "its own run drew its dashboard")
        sites = json.loads((www / "sites.json").read_text())["sites"]
        self.assertNotIn(GONE, [s["name"] for s in sites])
        # The waiting site's folder lost (a container made again): the next
        # write by any site gives it the page, until its own run draws it.
        (www / SHOP / "index.html").unlink()
        code, out, err = box.run("--today", "2026-10-06", "--site", MAIN, "dashboard")
        self.assertEqual(code, 0, err)
        shop = (www / SHOP / "index.html").read_text()
        self.assertIn(f"{SHOP} is waiting for its first log lines", shop)
        self.assertIn(f"../{MAIN}/#settings/sitesadmin?setup={SHOP}", shop)


if __name__ == "__main__":
    unittest.main()
