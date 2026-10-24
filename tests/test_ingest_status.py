"""What the log endpoint last did for a site (ingest_status.py), as the Test
button in Settings > Connections reads it (GET <page>/sites/status,
connections_api.py): accepted batches and today's lines, refusals with their
reason, never an address or a token; a sending token made from the page.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import ingest, ingest_status  # noqa: E402


class Words(unittest.TestCase):
    def test_reasons(self):
        cases = [(401, "a bearer token is needed", "no_token"), (401, "unrecognised or revoked token", "bad_token"),
                 (403, "this token is not for that site", "wrong_site"), (403, "this token has no ingest scope", "not_sending"),
                 (403, "This site is waiting for its domain to be verified (Settings > Sites); x", "not_verified"),
                 (429, "too many batches for this site; slow down", "rate_limited"),
                 (429, ingest.DAY_WORDS.format(mb=200), "day_full"), (429, ingest.QUOTA_WORDS, "plan_limit"),
                 (410, "this site was removed", "removed"), (404, "this install does not process that site", "not_here"),
                 (404, "not found", "off"), (507, ingest.DISK_WORDS, "disk"), (402, "unpaid", "read_only"),
                 (400, "this site's log format is x", "bad_format"), (400, "X-Skald-Batch: ...", "bad_batch")]
        for code, error, want in cases:
            with self.subTest(code=code, error=error):
                self.assertEqual(ingest_status.reason(code, error), want)
                self.assertIn(want, ingest_status.REASONS)

    def test_file_shape_and_the_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = time.time()
            ingest_status.accepted(tmp, "example.com", 5, 1, "s1", now=day - 86400)
            ingest_status.accepted(tmp, "example.com", 3, 0, "s1", now=day)
            got = ingest_status.read(tmp, "example.com")
            self.assertEqual(got["today"]["lines"], 3)          # a new UTC day starts at 0
            self.assertEqual(got["last_batch"]["lines"], 3)
            ingest_status.accepted(tmp, "example.com", 0, 0, "vercel", now=day + 1)
            self.assertEqual(ingest_status.read(tmp, "example.com")["last_batch"]["lines"], 3)
            ingest_status._LAST_REFUSAL.clear()
            ingest_status.refused(tmp, "example.com", 401, "unrecognised or revoked token", now=day + 2)
            ingest_status.refused(tmp, "example.com", 403, "this token is not for that site", now=day + 2.5)
            self.assertEqual(ingest_status.read(tmp, "example.com")["last_refusal"]["reason"], "bad_token")
            self.assertEqual(sorted(p.name for p in Path(tmp, "ingest-status").iterdir()), ["example.com.json"])


class Recorded(TenantServer):
    def setUp(self):
        super().setUp()
        ingest_status._LAST_REFUSAL.clear()

    def status(self, site=A, who="owner@example.com"):
        cookie, _ = self.session(who)
        return self.call("GET", f"/traffic/{A}/sites/status?site={site}", cookie=cookie)

    def raw_file(self, site) -> str:
        path = ingest_status.path_for(self.live, site)
        return path.read_text() if path.exists() else ""

    def test_nothing_yet_then_a_batch(self):
        got = self.status()
        self.assertEqual(got.status, 200, got.json)
        self.assertIsNone(got.json["last_batch"])
        self.assertIsNone(got.json["last_refusal"])
        self.assertTrue(got.json["ingest_enabled"])
        self.assertEqual(got.json["send_url"], f"https://www.example.com/traffic-ingest/{A}")
        token = self.token(self.alpha, sites=[A])
        self.assertEqual(self.ship(A, token, lines(4), batch="box-1:1").status, 200)
        got = self.status().json
        self.assertEqual(got["last_batch"]["lines"], 4)
        self.assertEqual(got["last_batch"]["shipper"], "box-1")
        self.assertEqual(got["today"]["lines"], 4)
        self.assertEqual(got["received"]["accepted"], 4)
        self.assertTrue(got["folder"])
        # Never an address, a user agent or the token.
        raw = self.raw_file(A)
        for word in ("192.0.2.", "Mozilla", token, "skald_"):
            self.assertNotIn(word, raw)

    def test_refusals_are_recorded_with_their_reason(self):
        token = self.token(self.alpha, sites=[A])
        self.ship(A, token, lines(2), batch="s:1")              # the site is known now
        self.assertEqual(self.ship(A, "skald_00000000_" + "z" * 43, lines(1), batch="s:2").status, 401)
        got = self.status().json["last_refusal"]
        self.assertEqual((got["code"], got["reason"]), (401, "bad_token"))
        self.assertEqual(got["words"], "The token is wrong or was revoked.")
        ingest_status._LAST_REFUSAL.clear()
        other = self.token(self.beta, sites=[B])
        self.assertEqual(self.ship(A, other, lines(1), batch="s:3").status, 403)
        self.assertEqual(self.status().json["last_refusal"]["reason"], "wrong_site")
        ingest_status._LAST_REFUSAL.clear()
        reader = self.token(self.alpha, scopes=("read",), sites=[A])
        self.assertEqual(self.ship(A, reader, lines(1), batch="s:4").status, 403)
        self.assertEqual(self.status().json["last_refusal"]["reason"], "not_sending")
        ingest_status._LAST_REFUSAL.clear()
        self.config["ingest"].update({"per_minute": 1, "burst": 1})
        ingest._BUCKETS.clear()
        self.ship(A, token, lines(1), batch="s:5")
        self.assertEqual(self.ship(A, token, lines(1), batch="s:6").status, 429)
        self.assertEqual(self.status().json["last_refusal"]["reason"], "rate_limited")
        for word in (token, other, reader, "192.0.2."):
            self.assertNotIn(word, self.raw_file(A))

    def test_the_checks_probe_is_not_a_refusal(self):
        """skald-ship-check posts with no token and X-Skald-Check: 1 (check.sh),
        expecting the 401: that is not written as a refusal."""
        token = self.token(self.alpha, sites=[A])
        self.ship(A, token, lines(2), batch="s:1")              # the site is known now
        probe = {"Content-Type": "text/plain", "X-Skald-Check": "1"}
        got = self.call("POST", f"/traffic-ingest/{A}", headers=probe, raw=b"")
        self.assertEqual(got.status, 401)
        self.assertIsNone(self.status().json["last_refusal"])
        got = self.call("POST", f"/traffic-ingest/{A}", raw=b"",
                        headers={"Content-Type": "text/plain"})
        self.assertEqual(got.status, 401)
        self.assertEqual(self.status().json["last_refusal"]["reason"], "no_token",
                         "without the marker a tokenless post is a refusal, as before")
        ingest_status._LAST_REFUSAL.clear()
        self.assertEqual(self.ship(A, "skald_00000000_" + "z" * 43, lines(1), batch="s:2",
                                   headers={"X-Skald-Check": "1"}).status, 401)
        self.assertEqual(self.status().json["last_refusal"]["reason"], "bad_token",
                         "the marker never hides a refused token")
        check = (Path(__file__).resolve().parent.parent / "skald" / "kit"
                 / "check.sh").read_text()
        self.assertEqual(check.count("X-Skald-Check"), 2, "curl and python3 both send it")
        # The marker skips only the 401 the probe expects: any other refusal is kept.
        ingest_status._LAST_REFUSAL.clear()
        h = type("H", (), {"headers": {"X-Skald-Check": "1"},
                           "_skald_ingest": {"base": self.live, "site": A}})()
        ingest_status.note(h, 403, {"error": "this site is paused"})
        self.assertEqual(self.status().json["last_refusal"]["code"], 403)

    def test_a_site_this_install_does_not_know_leaves_no_file(self):
        self.assertEqual(self.ship("unknown.example", "skald_00000000_" + "z" * 43, lines(1)).status, 401)
        self.assertFalse(ingest_status.path_for(self.live, "unknown.example").exists())

    def test_a_drain_is_recorded_by_its_name(self):
        token = self.token(self.beta, sites=[B])
        body = json.dumps([{"timestamp": 1760187600000, "proxy": {"clientIp": "192.0.2.9", "method": "GET",
                            "host": B, "path": "/", "statusCode": 200, "userAgent": ["Mozilla/5.0"]}}]).encode()
        got = self.call("POST", f"/traffic-ingest/{B}?format=vercel", raw=body,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        self.assertIn(got.status, (200, 400), got.json)        # B's format is nginx_combined: 400
        last = ingest_status.read(self.live, B)
        if got.status == 200:
            self.assertEqual(last["last_contact"][:4], "20")
        else:
            self.assertEqual(last["last_refusal"]["reason"], "bad_format")

    def test_who_may_read_it(self):
        self.assertEqual(self.status(who="viewer@example.com").status, 403)
        self.assertEqual(self.status(site=B).status, 404)       # another organisation's site
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/status", {}, cookie, csrf)
        self.assertEqual(got.status, 405)

    def test_a_sending_token_made_from_the_page_ships(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(f"/traffic/{A}/tokens/create", {"name": f"Sending logs: {A}, 2026-10-11",
                                                        "sites": [A], "scopes": ["ingest"]}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["scopes"], ["ingest"])
        self.assertEqual(got.json["sites"], [A])
        self.assertEqual(self.ship(A, got.json["token"], lines(2)).status, 200)
        listed = self.call("GET", f"/traffic/{A}/tokens", cookie=cookie).json["tokens"]
        self.assertIn("ingest", [s for t in listed for s in t["scopes"]])
        # A viewer cannot make one.
        cookie, csrf = self.session("viewer@example.com")
        got = self.post(f"/traffic/{A}/tokens/create", {"name": "x", "sites": [A], "scopes": ["ingest"]},
                        cookie, csrf)
        self.assertEqual(got.status, 403)


if __name__ == "__main__":
    unittest.main()
