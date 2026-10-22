"""Sharing the visitor ID across subdomains, switched on in Skald per site
(`beacon.share_subdomains`), with the script tag unchanged:

1. the setting: a site's, for admins, off by default; `settings set` works;
2. the beacon's answer to a page_view from the site's own Origin carries
   X-Skald-Sh: 1 (on) or 0 (off), exposed to the page by CORS; status and
   body stay what they were (204 counted, 202 not, no body), so nginx's
   count and older scripts are untouched; never for another Origin, never on
   any other event's answer;
3. Settings > Integrations and the privacy notice treat the setting as the
   tag's data-share-subdomains="true".

skald.js's side (the ask, the day's flag, the cookie) is in
tests/js/skald-snippet.mjs. Addresses are RFC 5737; hosts example.com/.net.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_beacon_sites as beacon_sites  # noqa: E402  (not its classes: no second run)
from test_beacon_sites import FIRST, SECOND, body  # noqa: E402
from test_client_site_settings import MAIN, Cli  # noqa: E402
from test_integrations_api import Base as IntegrationsBase  # noqa: E402
from test_privacy_notice import config as notice_config  # noqa: E402

from skald import beacon, settings_store as store  # noqa: E402
from skald.people import notice  # noqa: E402

KEY = "beacon.share_subdomains"


class Setting(unittest.TestCase):
    def test_a_site_s_admin_setting_off_by_default(self):
        key = store.SCHEMA[KEY]
        self.assertEqual((key.kind, key.who, key.scopes, key.default),
                         ("bool", "admin", ("site",), False))
        self.assertIs(store.validate(KEY, "true"), True)
        self.assertIs(beacon.share_subdomains({}), False)
        self.assertIs(beacon.share_subdomains({"beacon": {"share_subdomains": True}}), True)
        self.assertIs(beacon.share_subdomains({"beacon": {"share_subdomains": "true"}}), True)


class SettingCli(Cli):
    def test_set_and_get(self):
        code, out, err = self.run_ti("settings", "set", MAIN, KEY, "true")
        self.assertEqual(code, 0, err)
        self.assertIs(store.get(self.db, f"site:{MAIN}", KEY), True)
        code, out, _ = self.run_ti("settings", "get", MAIN, KEY)
        self.assertEqual((code, out.split()), (0, [KEY, "true", "(site)"]))


class Answer(unittest.TestCase):
    """FIRST has the setting off; SECOND (visitor IDs on) has it on. The
    helper as test_beacon_sites.TwoSites builds it (not inherited: its tests
    would run twice)."""

    tearDown, call = beacon_sites.TwoSites.tearDown, beacon_sites.TwoSites.call

    def setUp(self):
        beacon_sites.TwoSites.setUp(self)
        self.second.config["beacon"]["share_subdomains"] = True
        self.second.reconfigure(self.second.config)

    def direct(self, origin, raw):
        h = {"Content-Type": "text/plain", "Sec-Fetch-Site": "cross-site"}
        if origin:
            h["Origin"] = origin
        return self.call("POST", "/traffic-beacon", raw, **h)

    def test_on_and_off(self):
        status, h, raw = self.direct(SECOND, body(e="page_view", v="skv_" + "a" * 22))
        self.assertEqual((status, raw, h.get("Content-Length")), (204, b"", "0"))
        self.assertEqual(h.get("X-Skald-Sh"), "1")
        self.assertEqual(h.get("Access-Control-Expose-Headers"), "X-Skald-Sh")
        self.assertEqual(h.get("Access-Control-Allow-Origin"), SECOND)
        self.assertNotIn("Access-Control-Allow-Credentials", h)
        # Off: 0, and the answer is otherwise the one it always was (202, page views not counted).
        status, h, raw = self.direct(FIRST, body(e="page_view"))
        self.assertEqual((status, raw, h.get("X-Skald-Sh")), (202, b"", "0"))
        self.assertEqual(h.get("Access-Control-Allow-Origin"), FIRST)

    def test_switched_off_the_next_answer_says_0(self):
        self.second.config["beacon"]["share_subdomains"] = False
        self.second.reconfigure(self.second.config)
        _, h, _ = self.direct(SECOND, body(e="page_view"))
        self.assertEqual(h.get("X-Skald-Sh"), "0")

    def test_never_for_an_origin_that_is_not_the_site_s(self):
        for origin in ("https://elsewhere.example.org", "http://second.example.net",
                       "https://second.example.net.example.org", "null", None):
            status, h, _ = self.direct(origin, body(e="page_view"))
            self.assertEqual(status, 403, origin)
            self.assertNotIn("X-Skald-Sh", h)
            self.assertNotIn("Access-Control-Expose-Headers", h)

    def test_other_answers_unchanged(self):
        """Not a page_view, a refusal, the probe: as before, no X-Skald-Sh."""
        status, h, raw = self.direct(SECOND, body())                      # cta_click
        self.assertEqual((status, raw), (204, b""))
        self.assertNotIn("X-Skald-Sh", h)
        status, h, _ = self.direct(SECOND, b"x" * 2000)
        self.assertEqual(status, 413)
        self.assertNotIn("X-Skald-Sh", h)
        status, h, _ = self.direct(SECOND, body(e="nope"))
        self.assertEqual(status, 400)
        self.assertNotIn("X-Skald-Sh", h)
        status, h, _ = self.call("POST", "/traffic-beacon", b"", **{"X-Skald-Probe": "1"})
        self.assertEqual(status, 200)
        self.assertNotIn("X-Skald-Sh", h)
        status, h, _ = self.call("GET", "/traffic-js/skald.js", Referer=SECOND + "/")
        self.assertEqual(status, 200)
        self.assertNotIn("X-Skald-Sh", h)

    def test_the_count_is_unchanged(self):
        """nginx counts 204s per site: a page_view with the answer is still one."""
        self.direct(SECOND, body(e="page_view", v="skv_" + "b" * 22))
        today = self.second.now().date()
        self.assertEqual([r["e"] for r in beacon.read_day(self.second.spool, today)],
                         ["page_view"])


class IntegrationsShared(IntegrationsBase):
    def test_the_script_box_reads_the_setting(self):
        from auth_support import A
        sc = self.get().json["script"]
        self.assertFalse(sc["share_subdomains"])
        db = self.db()
        try:
            store.put(db, f"site:{A}", KEY, True, "cli")
        finally:
            db.close()
        sc = self.get().json["script"]
        self.assertTrue(sc["share_subdomains"])
        self.assertIn('data-site="alpha.example"', sc["tag"])
        self.assertNotIn("share-subdomains", sc["tag"], "the tag stays as it is")
        what = next(o["what"] for o in sc["options"] if o["attr"] == "data-share-subdomains")
        self.assertIn("already on for this site in Skald", what)


class Notice(unittest.TestCase):
    def test_the_shared_line_is_plain_when_skald_shares(self):
        c = notice_config("full", "full", "ids")
        got = notice.wording(c)
        self.assertIn(notice.SHARED_MARK, got["text"])
        self.assertIn(notice.SHARED_MARK, got["placeholders"])
        self.assertFalse(got["uses"]["share_subdomains"])
        c["beacon"]["share_subdomains"] = True
        got = notice.wording(c)
        self.assertNotIn(notice.SHARED_MARK, got["text"])
        self.assertNotIn(notice.SHARED_MARK, got["placeholders"])
        self.assertIn(notice.SHARED_LINE, got["items"])
        self.assertTrue(got["uses"]["share_subdomains"])
        # No visitor IDs: no ID to share, so no cookie line either way.
        c = notice_config("full", "full", "tag")
        c["beacon"]["share_subdomains"] = True
        got = notice.wording(c)
        self.assertNotIn("skald_vid", got["text"])
        self.assertFalse(got["uses"]["share_subdomains"])


if __name__ == "__main__":
    unittest.main()
