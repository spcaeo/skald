"""SKALD-58: the doctor's lines on Settings › Leads & tools, Settings › To do and the
Overview set-up bar read the site's saved settings (settings rows, Settings › Data ›
What counts), as the CLI's doctor and run-daily do (settings_store.apply).

Before, GET integrations built the site's config without the rows, so a site whose
asset prefixes were saved on the page was checked against the default
/_next/static/ and its "Visits count as people" step stayed To do, though its
visits were counted with the saved paths. Hosts are example.com."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_integrations_api import A, Base  # noqa: E402

from skald import settings_store, setup_items  # noqa: E402
from skald.conversions import roads  # noqa: E402

DOWN = {"up": False, "script": None, "error": "ConnectionRefusedError: refused"}
# A WordPress page and its files, as nginx's combined format logs them.
LINES = "".join(
    f'203.0.113.7 - - [11/Oct/2026:13:5{i}:00 +0000] "GET {path} HTTP/1.1" 200 512 '
    f'"https://{A}/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    f'(KHTML, like Gecko) Chrome/130.0 Safari/537.36"\n'
    for i, path in enumerate(["/", "/wp-content/themes/a/style.css",
                              "/wp-includes/js/jquery.min.js", "/about/"]))


class SavedSettings(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(roads, "helper", return_value=DOWN)
        patcher.start()
        self.addCleanup(patcher.stop)
        logs = self.live.parent / "logs"
        logs.mkdir()
        (logs / "access.log").write_text(LINES)
        self.config["logs"] = {"dir": str(logs)}

    def save(self, name, value):
        db = self.db()
        try:
            settings_store.put(db, f"site:{A}", name, value, "owner@example.com")
        finally:
            db.close()

    def assets(self):
        got = self.get()
        self.assertEqual(got.status, 200, got.json)
        return next(s for s in got.json["status"] if s["id"] == "assets")

    def test_without_a_row_the_default_prefix_is_checked(self):
        line = self.assets()
        self.assertEqual(line["state"], "NEEDS ATTENTION")
        self.assertIn("/_next/static/", line["says"])

    def test_saved_asset_prefixes_are_what_the_page_checks(self):
        self.save("site.asset_prefixes", ["/wp-content/", "/wp-includes/"])
        line = self.assets()
        self.assertEqual(line["state"], "OK", line)
        self.assertIn("/wp-content/", line["says"])

    def test_saved_rendering_off_says_not_needed(self):
        self.save("site.require_rendering", False)
        line = self.assets()
        self.assertEqual(line["state"], "OFF", line)
        self.assertIn("not needed", line["says"])

    def test_the_mcp_setup_list_reads_the_rows_too(self):
        self.save("site.asset_prefixes", ["/wp-content/"])
        got = setup_items.answers(self.config, A, live_dir=self.live)
        line = next(s for s in got["status"] if s["id"] == "assets")
        self.assertEqual(line["state"], "OK", line)

    def test_a_broken_accounts_file_still_answers_with_the_file_config(self):
        self.save("site.asset_prefixes", ["/wp-content/"])
        with mock.patch.object(settings_store, "apply", side_effect=RuntimeError("made up")), \
                mock.patch("sys.stderr"):
            line = self.assets()
        self.assertEqual(line["state"], "NEEDS ATTENTION", "the config file's view, not a 500")


class DashboardSite(unittest.TestCase):
    """The ticket's own case: a site added from the dashboard (multisite's tenant_base,
    which takes nothing of the first site's `site:` section), its paths saved on the page."""

    def setUp(self):
        import json
        import tempfile
        from skald.accounts import db as base, site_configs
        from skald.accounts.orgs import create_org
        patcher = mock.patch.object(roads, "helper", return_value=DOWN)
        patcher.start()
        self.addCleanup(patcher.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        logs = self.root / "logs-b"
        logs.mkdir()
        (logs / "access.log").write_text(LINES)
        self.config = {"site": {"name": A, "asset_prefixes": ["/first-site-only/"]},
                       "history": {"db": str(self.root / "history.sqlite")}}
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config))
        db = base.connect(base.path_for(self.config, self.root))
        try:
            org = create_org(db, "Beta", "cli")["id"]
            site_configs.create(db, org, "b.example.com", "cli", hosts=["b.example.com"],
                                log_dir=str(logs))
            settings_store.put(db, "site:b.example.com", "site.asset_prefixes",
                               ["/wp-content/", "/wp-includes/"], "owner@example.com")
        finally:
            db.close()

    def lines(self):
        got = setup_items.answers(self.config, "b.example.com", live_dir=self.root,
                                  config_path=self.config_path)
        return {s["id"]: s for s in got["status"]}

    def test_its_saved_prefixes_are_checked_and_nothing_else_moves(self):
        from skald import doctor
        after = self.lines()
        self.assertEqual(after["assets"]["state"], "OK", after["assets"])
        self.assertIn("/wp-content/", after["assets"]["says"])
        with mock.patch.object(doctor, "with_saved_settings", lambda c, s, f: c):
            before = self.lines()
        self.assertEqual(before["assets"]["state"], "NEEDS ATTENTION", "the old behaviour")
        self.assertIn("/_next/static/", before["assets"]["says"])
        self.assertEqual({k: v for k, v in before.items() if k != "assets"},
                         {k: v for k, v in after.items() if k != "assets"},
                         "only the Page assets line reads the row here")


if __name__ == "__main__":
    unittest.main()
