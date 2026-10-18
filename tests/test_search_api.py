"""Settings > Integrations > Search over real HTTP (search/api.py, sessions
mode), against the fake Google and Bing of search_support.py: keys only an
install admin may set, never echoed; the wizard's properties, test, connect,
sync now (rate-limited) and disconnect; a property of another site refused."""
from __future__ import annotations

import dataclasses
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search_support as ss  # noqa: E402
from auth_support import A, Server  # noqa: E402

from skald import accounts, settings_store  # noqa: E402
from skald.accounts import auditlog  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.search import api, bing, google, state  # noqa: E402

T = f"/traffic/{A}/"


class Base(Server):
    def setUp(self):
        super().setUp()
        self.config["site"] = {"name": A, "hosts": [A, f"www.{A}"]}
        self.engines = ss.Engines()
        self.addCleanup(self.engines.stop)
        self.engines.data = ss.records(date(2026, 9, 1), date(2026, 10, 9))
        self.spawned = []
        made = api._job

        def job(c, site):
            return dataclasses.replace(made(c, site), api=self.engines.api())

        for patch in (mock.patch.object(api, "_job", job),
                      mock.patch.object(api, "spawn",
                                        lambda c, site, args: self.spawned.append((site, args)))):
            patch.start()
            self.addCleanup(patch.stop)

    def admin(self, on=True, email="owner@example.com"):
        db = self.db()
        try:
            accounts.set_install_admin(db, self.uids[email], on, "cli")
        finally:
            db.close()

    def get(self, email="owner@example.com"):
        cookie, _ = self.session(email)
        return self.call("GET", T + "integrations/search", cookie=cookie)

    def do(self, act, body, email="owner@example.com"):
        cookie, csrf = self.session(email)
        return self.post(T + "integrations/search/" + act, body, cookie, csrf)


class Keys(Base):
    def test_only_an_install_admin_sets_keys_and_they_never_come_back(self):
        self.assertEqual(self.do("googlekey", {"key": ss.service_key()}).status, 403)
        self.admin()
        got = self.do("googlekey", {"key": ss.service_key()})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["client_email"], ss.EMAIL)
        kept = secrets_store.load(self.live / "secrets.json")
        self.assertEqual(google.check_key(kept[google.SECRET])["client_email"], ss.EMAIL)
        page = self.get().json
        self.assertEqual(page["keys"]["google"]["client_email"], ss.EMAIL)
        self.assertEqual(page["google_steps"]["email"], ss.EMAIL)
        self.assertIn(ss.EMAIL, page["google_steps"]["send_text"])
        body = json.dumps(page) + json.dumps(got.json) + json.dumps(self.audit())
        self.assertNotIn(ss.VECTOR["pkcs8_der_base64"][:30], body)
        self.assertNotIn("private_key", body)
        self.assertEqual(self.do("googleremove", {}).json["removed"], True)
        self.assertNotIn(google.SECRET, secrets_store.load(self.live / "secrets.json"))

    def test_a_bad_key_in_plain_words(self):
        self.admin()
        got = self.do("googlekey", {"key": json.dumps({"type": "authorized_user"})})
        self.assertEqual(got.status, 400)
        self.assertIn("not a service-account key", got.json["error"])

    def test_bing_key(self):
        self.admin()
        self.assertEqual(self.do("bingkey", {"key": "short"}).status, 400)
        got = self.do("bingkey", {"key": ss.BING_KEY})
        self.assertEqual((got.status, got.json["hint"]), (200, "…" + ss.BING_KEY[-4:]))
        page = json.dumps(self.get().json)
        self.assertNotIn(ss.BING_KEY, page)
        self.assertIn(ss.BING_KEY[-4:], page)
        self.assertNotIn(ss.BING_KEY, json.dumps(self.audit()))
        self.do("bingremove", {})
        self.assertNotIn(bing.ENV, secrets_store.load(self.live / "secrets.json"))

    def audit(self):
        db = self.db()
        try:
            return auditlog.recent(db, None)
        finally:
            db.close()


class Wizard(Base):
    def setUp(self):
        super().setUp()
        # The install admin sets the keys; the owner (a site admin) does the rest.
        self.admin(email="admin@example.com")
        self.do("googlekey", {"key": ss.service_key()}, "admin@example.com")
        self.do("bingkey", {"key": ss.BING_KEY}, "admin@example.com")

    def test_viewers_cannot(self):
        self.assertEqual(self.get("viewer@example.com").status, 403)
        self.assertEqual(self.do("properties", {"engine": "google"}, "viewer@example.com").status,
                         403)

    def test_find_test_connect_sync_disconnect(self):
        got = self.do("properties", {"engine": "google"})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual([p["siteUrl"] for p in got.json["properties"]], [f"sc-domain:{A}"])
        self.assertEqual(got.json["seen"], 2)
        tested = self.do("test", {"engine": "google", "source": f"sc-domain:{A}"})
        self.assertEqual(tested.status, 200, tested.json)
        self.assertTrue(tested.json["ok"])
        self.assertGreater(tested.json["clicks"], 0)
        refused = self.do("connect", {"engine": "google", "source": "https://www.beta.example/"})
        self.assertEqual(refused.status, 403)
        self.assertIn("does not cover", refused.json["error"])
        done = self.do("connect", {"engine": "google", "source": f"sc-domain:{A}",
                                   "backfill_months": 16})
        self.assertEqual(done.status, 200, done.json)
        self.assertEqual(self.spawned[-1], (A, ["search-console", "sync",
                                                "--backfill-months", "16"]))
        db = self.db()
        try:
            got = settings_store.explain(self.config, A, db)["search.google_property"]
        finally:
            db.close()
        self.assertEqual(got["value"], f"sc-domain:{A}")
        page = self.get().json
        self.assertEqual(page["engines"]["google"]["connected"], f"sc-domain:{A}")
        self.assertEqual(page["engines"]["google"]["status"]["backfill"]["state"], "queued")
        first = self.do("sync", {})
        self.assertEqual(first.status, 200, first.json)
        self.assertEqual(self.spawned[-1], (A, ["search", "sync"]))
        again = self.do("sync", {})
        self.assertEqual(again.status, 429)
        self.assertIn("try again in", again.json["error"])
        with state.lock(self.live, A):
            self.tick(api.SYNC_MINUTES * 60 + 1)
            self.assertEqual(self.do("sync", {}).status, 409)
        off = self.do("disconnect", {"engine": "google"})
        self.assertEqual((off.status, off.json["kept"]), (200, True))
        self.assertIsNone(self.get().json["engines"]["google"]["connected"])

    def test_bing(self):
        got = self.do("properties", {"engine": "bing"})
        self.assertEqual([p["siteUrl"] for p in got.json["properties"]], [f"https://www.{A}/"])
        tested = self.do("test", {"engine": "bing", "source": f"https://www.{A}/"})
        self.assertEqual(tested.status, 200, tested.json)
        self.assertEqual(self.do("connect", {"engine": "bing", "source": f"https://www.{A}/",
                                             "backfill_months": 3}).status, 400)
        self.assertEqual(self.do("connect", {"engine": "bing",
                                             "source": f"https://www.{A}/"}).status, 200)
        self.assertEqual(self.spawned[-1], (A, ["bing", "sync"]))

    def test_nothing_connected_cannot_sync(self):
        self.assertEqual(self.do("sync", {}).status, 409)

    def test_no_hosts(self):
        self.config["site"] = {"name": A}
        got = self.do("properties", {"engine": "google"})
        self.assertEqual(got.status, 409)


if __name__ == "__main__":
    unittest.main()
