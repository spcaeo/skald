"""The hook receiver: refusals, the spool, the store, privacy, and the
dispatch from the beacon helper. Addresses are RFC 5737; hosts example.com."""
from __future__ import annotations

import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID, FakeHandler, mmdb  # noqa: E402

from skald.conversions import secrets_store, spool, store  # noqa: E402
from skald.conversions.adapters import adapter  # noqa: E402
from skald.conversions.hooks import Receiver  # noqa: E402

T = 1791720000          # 2026-10-11 12:00 UTC
CHROME_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def lead(**kw) -> dict:
    out = {"external_ref": "L-1", "action": "demo", "vid": VID,
           "last_touch": {"referrer": "https://www.google.com/", "landing": "/pricing/?x=1"},
           "email": "person@example.com", "name": "A Person"}
    out.update(kw)
    return out


class Base(unittest.TestCase):
    identity = ""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        (self.folder / "country.mmdb").write_bytes(mmdb({"192.0.2.0/24": "CA"}))
        self.config = {"site": {"name": "example.com", "hosts": ["example.com"]},
                       "history": {"db": str(self.folder / "history.sqlite")},
                       "conversions": {"country_db": str(self.folder / "country.mmdb")},
                       "hooks": {"per_minute": 600, "burst": 100}}
        if self.identity:
            self.config["conversions"]["identity"] = self.identity
        path = secrets_store.path_for(self.config, self.folder)
        for tool in ("lead", "calendly", "stripe", "hubspot", "typeform", "calcom", "json"):
            secrets_store.put(path, secrets_store.key("example.com", tool), SECRET)
        self.now = T
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, tool: str, payload, site: str = "example.com", secret: str = SECRET,
             extra: dict | None = None, raw: bytes | None = None):
        body = raw if raw is not None else json.dumps(payload).encode()
        path = f"/traffic-hooks/{site}/{tool}"
        uri = "https://www.example.com" + path
        headers = {"Host": "www.example.com", "X-Forwarded-Proto": "https",
                   **adapter(tool).sign(body, secret, self.now, "POST", uri), **(extra or {})}
        return self.rx.http(FakeHandler(path, body, headers))

    def rows(self, sql: str) -> list:
        db = sqlite3.connect(self.folder / "conversions.sqlite")
        try:
            return db.execute(sql).fetchall()
        finally:
            db.close()

    def spooled(self) -> str:
        day = datetime.fromtimestamp(self.now, tz=timezone.utc).date()
        path = spool.day_file(self.folder / "hooks", day)
        return path.read_text() if path.exists() else ""


class Refusals(Base):
    def test_unknown_site_tool_or_no_secret_is_404(self):
        self.assertEqual(self.post("lead", lead(), site="other.example.com")[0], 404)
        got = self.rx.http(FakeHandler("/traffic-hooks/example.com/zapier", b"{}"))
        self.assertEqual(got[0], 404)
        self.assertEqual(self.rx.http(FakeHandler("/traffic-hooks/example.com", b"{}"))[0], 404)
        path = secrets_store.path_for(self.config, self.folder)
        data = json.loads(path.read_text())
        del data["hooks/example.com/stripe"]
        path.write_text(json.dumps(data))
        self.assertEqual(self.post("stripe", {})[0], 404, "no secret: not set up")
        self.assertFalse((self.folder / "conversions.sqlite").exists(), "nothing logged")

    def test_get_is_405(self):
        got = self.rx.http(FakeHandler("/traffic-hooks/example.com/lead", command="GET"))
        self.assertEqual(got[0], 405)

    def test_bad_signature_is_401_and_logged(self):
        self.assertEqual(self.post("lead", lead(), secret="wrong")[0], 401)
        self.now = T + 400
        body = json.dumps(lead()).encode()
        headers = adapter("lead").sign(body, SECRET, T, "POST", "")   # signed 400 s ago
        got = self.rx.http(FakeHandler("/traffic-hooks/example.com/lead", body, headers))
        self.assertEqual(got[0], 401, "a replay outside 5 minutes")
        self.assertEqual(self.rows("SELECT outcome, http_status FROM deliveries"),
                         [("bad_signature", 401)] * 2)
        self.assertEqual(self.spooled(), "", "nothing spooled before the signature holds")

    def test_too_large_is_413_and_not_read(self):
        handler = FakeHandler("/traffic-hooks/example.com/lead", b"",
                              {"Content-Length": str(64 * 1024 + 1)})
        self.assertEqual(self.rx.http(handler)[0], 413)
        handler = FakeHandler("/traffic-hooks/example.com/lead", b"", {"Content-Length": "x"})
        self.assertEqual(self.rx.http(handler)[0], 411)

    def test_rate_limit_is_429_logged_once_a_minute(self):
        self.config["hooks"] = {"per_minute": 1, "burst": 2}
        rx = Receiver(self.config, self.folder, clock=lambda: self.now)
        self.rx = rx
        codes = [self.post("lead", lead(external_ref=f"R{i}"))[0] for i in range(5)]
        self.assertEqual(codes[:2], [200, 200])
        self.assertEqual(set(codes[2:]), {429})
        self.assertEqual(self.rows("SELECT COUNT(*) FROM deliveries WHERE outcome = "
                                   "'rate_limited'")[0][0], 1)

    def test_not_json_is_400(self):
        self.assertEqual(self.post("lead", None, raw=b"not json")[0], 400)

    def test_invalid_lead_is_400_after_spooling(self):
        status, answer = self.post("lead", lead(action="Book a demo!"))
        self.assertEqual(status, 400)
        self.assertIn("action", answer["error"])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 0)
        self.assertEqual(len(self.spooled().splitlines()), 1)

    def test_exposed_secrets_file_is_500(self):
        secrets_store.path_for(self.config, self.folder).chmod(0o644)
        self.assertEqual(self.post("lead", lead())[0], 500)


class Kept(Base):
    def test_a_lead_is_spooled_and_kept_once(self):
        status, answer = self.post("lead", lead())
        self.assertEqual((status, answer["recorded"]), (200, 1))
        status, answer = self.post("lead", lead())
        self.assertEqual((status, answer["duplicates"]), (200, 1))
        got = self.rows("SELECT site, tool, action, stage, at, vid, source_type, landing, "
                        "identity_id FROM conversions")
        self.assertEqual(got, [("example.com", "lead", "demo", "completed",
                                "2026-10-11T12:00:00Z", VID, "Search engine", "/pricing/",
                                None)])
        self.assertEqual([r[0] for r in self.rows("SELECT outcome FROM deliveries ORDER BY id")],
                         ["recorded", "duplicate"])
        self.assertEqual(len(self.spooled().splitlines()), 2)

    def test_anonymous_by_default(self):
        self.post("lead", lead(ip="192.0.2.44", user_agent=CHROME_MOBILE))
        self.assertEqual(self.rows("SELECT country, device FROM conversions"), [("CA", "Mobile")])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM identities")[0][0], 0)
        text = self.spooled()
        for personal in ("person@example.com", "A Person", "192.0.2.44", "iPhone"):
            self.assertNotIn(personal, text)
        dump = "\n".join(sqlite3.connect(self.folder / "conversions.sqlite").iterdump())
        for personal in ("person@example.com", "A Person", "192.0.2.44", "iPhone"):
            self.assertNotIn(personal, dump)

    def test_unknown_stays_null(self):
        self.post("lead", {"external_ref": "L-5", "action": "trial"})
        got = self.rows("SELECT vid, source_type, campaign, landing, country, device, "
                        "visits_before FROM conversions")
        self.assertEqual(got, [(None,) * 7])

    def test_country_given_wins_over_lookup(self):
        self.post("lead", lead(country="fr", ip="192.0.2.1", device="tablet"))
        self.assertEqual(self.rows("SELECT country, device FROM conversions"), [("FR", "Tablet")])

    def test_event_far_ahead_is_refused(self):
        self.assertEqual(self.post("lead", lead(at=T + 2 * 86400))[0], 400)

    def test_tool_events(self):
        uri = "https://api.calendly.com/scheduled_events/E/invitees/I"
        base = {"created_at": "2026-10-11T11:59:00Z",
                "payload": {"uri": uri, "email": "p@example.com",
                            "tracking": {"utm_content": VID, "utm_source": "linkedin"}}}
        self.assertEqual(self.post("calendly", {**base, "event": "invitee.created"})[0], 200)
        self.assertEqual(self.post("calendly", {**base, "event": "invitee.canceled"})[0], 200)
        self.assertEqual(self.post("calendly", {**base, "event": "routing_form.x"})[1]["recorded"], 0)
        got = self.rows("SELECT action, stage, external_ref, source_type FROM conversions "
                        "ORDER BY id")
        self.assertEqual(got, [("demo", "completed", uri, "Social media"),
                               ("demo", "cancelled", uri, "Social media")])
        self.assertEqual(self.rows("SELECT outcome FROM deliveries ORDER BY id")[-1][0], "ignored")

    def test_hubspot_signs_the_public_url(self):
        status, _ = self.post("hubspot", [{"subscriptionType": "contact.creation",
                                           "objectId": 3, "occurredAt": T * 1000}])
        self.assertEqual(status, 200)

    def test_test_delivery_is_read_not_kept(self):
        status, answer = self.post("stripe", adapter("stripe").sample("example.com", T),
                                   extra={"X-Skald-Test": "1"})
        self.assertEqual((status, answer["test"], answer["records"]), (200, True, 1))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 0)
        self.assertEqual(self.spooled(), "")
        self.assertEqual(self.rows("SELECT outcome FROM deliveries"), [("test",)])


class FullIdentity(Base):
    identity = "full"

    def test_name_and_email_kept_never_address(self):
        self.post("lead", lead(ip="192.0.2.44"))
        self.assertEqual(self.rows("SELECT email, name FROM identities"),
                         [("person@example.com", "A Person")])
        text = self.spooled()
        self.assertIn("person@example.com", text)
        self.assertNotIn("192.0.2.44", text)


class ThroughTheBeaconHelper(Base):
    def test_dispatch(self):
        from skald.beacon_server import Limiter, Sink, make_handler
        config_path = self.folder / "config.yml"
        config_path.write_text("")
        sink = Sink(self.config, self.folder / "beacon")
        sink.config_path = config_path
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     make_handler(sink, Limiter(), {"https://www.example.com"}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.now = time.time()
            body = json.dumps(lead()).encode()
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            conn.request("POST", "/traffic-hooks/example.com/lead", body,
                         adapter("lead").sign(body, SECRET, time.time()))
            answer = conn.getresponse()
            self.assertEqual(answer.status, 200)
            self.assertEqual(json.loads(answer.read())["recorded"], 1)
            conn.request("POST", "/traffic-hooks/example.com/lead", body,
                         {"X-Skald-Signature": "t=1,v1=00"})
            answer = conn.getresponse()
            answer.read()
            self.assertEqual(answer.status, 401)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 1)
        self.assertEqual(store.path_for(self.config, self.folder),
                         self.folder / "conversions.sqlite")


class DashboardSites(Base):
    """A site made from the dashboard (accounts.sqlite) receives hooks even
    when config.yml has no `sites:` list: the same loading as multisite."""

    def setUp(self):
        super().setUp()
        from skald import accounts
        from skald.accounts import site_configs
        db = accounts.connect(self.folder / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Org", "cli")
            site_configs.create(db, org["id"], "shop.example.com", "cli")
        finally:
            db.close()
        self.config_path = self.folder / "config.yml"
        self.config_path.write_text(json.dumps(self.config))

    def test_a_dashboard_site_is_known_without_a_sites_list(self):
        self.assertNotIn("sites", self.config)
        path = secrets_store.path_for(self.config, self.folder)
        secrets_store.put(path, secrets_store.key("shop.example.com", "lead"), SECRET)
        self.rx = Receiver(self.config, self.folder, self.config_path, clock=lambda: self.now)
        self.assertIn("shop.example.com", self.rx.sites)
        status, answer = self.post("lead", lead(), site="shop.example.com")
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.rows("SELECT site FROM conversions"), [("shop.example.com",)])
        # Without a secret for it, still 404 like any site.
        self.assertEqual(self.post("stripe", {}, site="shop.example.com")[0], 404)

    def test_the_installs_secrets_file_is_where_its_secret_is_read(self):
        moved = self.folder / "elsewhere" / "hook-secrets.json"
        self.config["hooks"]["secrets"] = str(moved)
        self.config_path.write_text(json.dumps(self.config))
        secrets_store.put(moved, secrets_store.key("shop.example.com", "lead"), SECRET)
        self.rx = Receiver(self.config, self.folder, self.config_path, clock=lambda: self.now)
        self.assertEqual(self.post("lead", lead(), site="shop.example.com")[0], 200)

    def test_a_site_added_after_the_helper_started(self):
        from unittest import mock
        from skald import accounts
        from skald.accounts import site_configs
        from skald.conversions import hooks
        self.rx = Receiver(self.config, self.folder, self.config_path, clock=lambda: self.now)
        db = accounts.connect(self.folder / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Later", "cli")
            site_configs.create(db, org["id"], "late.example.com", "cli")
        finally:
            db.close()
        path = secrets_store.path_for(self.config, self.folder)
        secrets_store.put(path, secrets_store.key("late.example.com", "lead"), SECRET)
        self.assertEqual(self.post("lead", lead(), site="late.example.com")[0], 404,
                         "inside the gap: the sites are not read again")
        with mock.patch.object(hooks, "SITES_EVERY", 0):
            self.assertEqual(self.post("lead", lead(), site="late.example.com")[0], 200)

    def test_without_accounts_nothing_changes(self):
        (self.folder / "accounts.sqlite").unlink()
        self.rx = Receiver(self.config, self.folder, self.config_path, clock=lambda: self.now)
        self.assertEqual(list(self.rx.sites), ["example.com"])


if __name__ == "__main__":
    unittest.main()
