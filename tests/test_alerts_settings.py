"""Alert switches on Site > Alerts (settings_store keys alerts.*, 2.13.0): each
key resolves as every setting does (the site's row, then config.yml's `alerts`
section under the same name, then the default), a key config.yml locks ignores
the row, `apply` lays a saved switch over the config so alerts.py, alerts_ai.py
and alerts_history.py read it, and only an admin of the site may save one, for
that site only."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from test_settings_api import Base, T  # noqa: E402

from skald import alerts, alerts_ai, alerts_history, settings_store as store  # noqa: E402


class Resolution(unittest.TestCase):
    def test_every_rule_has_a_key_by_its_config_name(self):
        for cause, name in alerts.SETTING.items():
            key = store.SCHEMA[name]
            self.assertEqual((key.kind, key.who, key.scopes), ("bool", "admin", ("site",)), cause)
            self.assertEqual(key.config, ("alerts", name.split(".", 1)[1]))
        self.assertEqual(set(alerts.SETTING), set(alerts.CAUSES) | set(alerts_ai.CAUSES)
                         | set(alerts_history.CAUSES))

    def test_config_words_and_defaults(self):
        got = store.explain({"alerts": {"enabled": "yes", "server_errors": "off",
                                        "ai": {"stopped_reading": False}}})
        self.assertEqual((got["alerts.enabled"]["value"], got["alerts.enabled"]["source"]),
                         (True, "config"))
        self.assertIs(got["alerts.server_errors"]["value"], False)
        self.assertIs(got["alerts.ai_stopped_reading"]["value"], False)    # nested alerts.ai
        self.assertEqual((got["alerts.site_down"]["value"], got["alerts.site_down"]["source"]),
                         (True, "default"))
        self.assertIs(store.explain({})["alerts.enabled"]["value"], False)


class Switches(Base):
    def read(self, email="owner@example.com"):
        cookie, _ = self.session(email)
        return self.call("GET", T + "settings", cookie=cookie).json["settings"]

    def test_an_admin_switches_alerts_on_for_this_site_only(self):
        got = self.save({"alerts.enabled": True, "alerts.site_down": False,
                         "alerts.ai_started_reading": False}, "admin@example.com")
        self.assertEqual(got.status, 200, got.json)
        s = got.json["settings"]
        self.assertEqual((s["alerts.enabled"]["value"], s["alerts.enabled"]["source"]),
                         (True, "site"))
        db = self.db()
        try:
            self.assertIs(store.get(db, f"site:{A}", "alerts.enabled"), True)
            self.assertIsNone(store.get(db, "install", "alerts.enabled"))
            self.assertIs(store.explain(self.config, B, db)["alerts.enabled"]["value"], False)
        finally:
            db.close()
        # The run reads the merged config: the rules see the switches.
        merged = store.apply(self.config, A, self.live)
        cfg = alerts.settings(merged)
        self.assertEqual((cfg["enabled"], cfg["site_down"], cfg["server_errors"]),
                         (True, False, True))
        self.assertIs(alerts_ai.settings(merged)["started_reading"], False)
        self.assertIs(alerts_history.settings(store.apply(self.config, A, self.live))
                      ["crawler_silent"], True)
        self.assertIs(alerts.settings(store.apply(self.config, B, self.live))["enabled"], False)

    def test_a_viewer_reads_the_switches_and_may_not_save(self):
        s = self.read("viewer@example.com")
        self.assertFalse(s["alerts.enabled"]["editable"])
        self.assertIn("admin", s["alerts.enabled"]["reason"])
        got = self.save({"alerts.enabled": True}, "viewer@example.com")
        self.assertEqual(got.status, 403)

    def test_a_locked_switch_stays_the_configs(self):
        self.config["alerts"] = {"enabled": True}
        self.config["settings"] = {"locked": ["alerts.enabled"]}
        s = self.read()
        self.assertEqual((s["alerts.enabled"]["locked"], s["alerts.enabled"]["editable"],
                          s["alerts.enabled"]["value"]), (True, False, True))
        got = self.save({"alerts.enabled": False})
        self.assertEqual(got.status, 403)
        self.assertIn("Locked", got.json["error"])
        self.assertTrue(alerts.settings(store.apply(self.config, A, self.live))["enabled"])

    def test_only_on_or_off(self):
        got = self.save({"alerts.site_down": "sometimes"})
        self.assertEqual(got.status, 400)


class Build(unittest.TestCase):
    def test_each_rule_names_its_switch(self):
        class P:
            config, live_dir = {"alerts": {"enabled": True}}, None
        got = alerts.build(P)
        self.assertTrue(got["rules"])
        self.assertTrue(all(r["setting"] in store.SCHEMA for r in got["rules"]))


if __name__ == "__main__":
    unittest.main()
