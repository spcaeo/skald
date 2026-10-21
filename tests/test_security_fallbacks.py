"""2.21.1: two false "possible exposure" alarms found in real data, and the guard that no
alert or mail reads a day counted before the rule changed.

1. One host, the same page at two sizes: the bare IP's default page was learned at 404 bytes
   (134 paths), and 18 WordPress probes from one scanner that asked without gzip got the same
   page uncompressed, 626 bytes. Every size at least 3 probe paths share is a fallback size.
2. An injection in the query string of an ordinary page (/ answered with the home page,
   101,804 bytes): no file was asked for, so it is no exposure candidate; Attack attempts
   lists it with what was answered."""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import alerts_security, security, security_notify  # noqa: E402

from security_support import box, ln, put, stored  # noqa: E402

UTC = timezone.utc
T = datetime(2026, 10, 5, 5, 5, 7, tzinfo=UTC)
WP = ["//wp-includes/wlwmanifest.xml", "//blog/wp-includes/wlwmanifest.xml", "//xmlrpc.php",
      "//wordpress/wp-includes/wlwmanifest.xml", "//wp/wp-includes/wlwmanifest.xml",
      "//site/wp-includes/wlwmanifest.xml", "//cms/wp-includes/wlwmanifest.xml",
      "//wp1/wp-includes/wlwmanifest.xml", "//wp2/wp-includes/wlwmanifest.xml",
      "//test/wp-includes/wlwmanifest.xml", "//media/wp-includes/wlwmanifest.xml",
      "//news/wp-includes/wlwmanifest.xml", "//2018/wp-includes/wlwmanifest.xml",
      "//2019/wp-includes/wlwmanifest.xml", "//shop/wp-includes/wlwmanifest.xml",
      "//web/wp-includes/wlwmanifest.xml", "//website/wp-includes/wlwmanifest.xml",
      "//wp-admin/setup-config.php"]


def day() -> list[str]:
    out = []
    for i in range(134):                      # the IP's default page, gzipped: 404 bytes
        out.append(ln(T - timedelta(hours=2, seconds=-30 * i), f"203.0.113.{100 + i % 50}",
                      f"/.env.{i}" if i % 2 else f"/old-{i}.php", "Go-http-client/1.1", 200, 404,
                      host="192.0.2.10"))
    for i, path in enumerate(WP):             # the same page, uncompressed: 626 bytes
        out.append(ln(T + timedelta(seconds=i // 7), "198.51.100.14", path, "Mozilla/5.0 zgrab/0.x",
                      200, 626, host="192.0.2.10"))
    # a real leak on the same host: one path, its own size
    out.append(ln(T + timedelta(minutes=5), "198.51.100.15", "/.git/config", "curl/8.7.1", 200, 1873,
                  host="192.0.2.10"))
    # the home page answered to an injection in its query string: no file asked for
    out.append(ln(T + timedelta(hours=3), "198.51.100.16", "/?id=1%20union%20select%201,2",
                  "curl/8.7.1", 200, 101_804, host="example.com"))
    return sorted(out)


class Fallbacks(unittest.TestCase):
    def setUp(self):
        self.box = box(day())
        code, _, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_two_sizes_of_one_page_and_a_lone_leak(self):
        e = stored(self.box)["exposure"]
        ip = e["hosts"]["192.0.2.10"]
        self.assertEqual(ip["shell_sizes"], [404, 626], "the page gzipped and not")
        self.assertEqual((ip["shell_size"], ip["shell_paths"]), (404, 134))
        self.assertEqual((ip["shell"], ip["possible"]), (152, 1))
        self.assertEqual([(r["path"], r["size"]) for r in e["rows"]], [("/.git/config", 1873)],
                         "the 18 WordPress probes are harmless; the lone file is not")

    def test_a_query_only_probe_is_no_exposure_candidate(self):
        b = stored(self.box)
        e = b["exposure"]
        self.assertEqual(e["query_only"], 1)
        self.assertNotIn("example.com", e["hosts"])
        self.assertEqual(e["answered"] + e["query_only"], b["status"]["2xx"])
        inj = b["attacks"]["injection"]
        self.assertEqual((inj["requests"], inj["rows"][0]["status"]), (1, {"2xx": 1}),
                         "Attack attempts lists it, with what was answered")

    def test_both_roads_agree_and_the_rule_is_stamped(self):
        self.assertEqual(stored(self.box)["rules"]["exposure_rule"], 2)
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)
        b = stored(self.box)
        b["exposure"]["hosts"]["192.0.2.10"]["shell_sizes"] = [404]
        put(self.box, b)
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("shell_sizes", err)


class NoStaleAlerts(unittest.TestCase):
    """A day counted by 2.21.0 (no exposure_rule) is never alerted on or mailed, whatever it
    says, until it is recounted."""

    def test_an_old_day_is_skipped_by_the_site_alert_and_the_peoples_mail(self):
        row = {"host": "192.0.2.10", "path": "//xmlrpc.php", "at": "2026-10-17T05:05:08+00:00",
               "status": "200", "size": 626, "verdict": "possible", "category": "wordpress",
               "shell_size": 404}
        old = {"rules": {"tolerance": 16}, "exposure": {"rows": [row]}}
        new = {"rules": {"exposure_rule": 2}, "exposure": {"rows": [row]}}
        self.assertEqual(alerts_security.exposures([("2026-10-17", old)]), [])
        self.assertEqual(len(alerts_security.exposures([("2026-10-17", new)])), 1)
        self.assertEqual(security_notify.items({}, "example.com", [old], None), [])
        self.assertFalse(security.current(old))
        self.assertTrue(security.current(new))

    def test_a_stored_old_day_opens_no_alert(self):
        b = box(day())
        try:
            self.assertEqual(b.run("--today", "2026-10-06", "collect")[0], 0)
            blob = stored(b)
            blob["rules"].pop("exposure_rule")
            blob["exposure"]["rows"][0]["verdict"] = "possible"
            put(b, blob)
            from skald.store import History
            with History(b.db) as h:
                got = alerts_security.findings({}, {}, None, h, "example.com", date(2026, 10, 5))
            self.assertEqual([f for f in got if f["cause"] == "security_exposure"], [])
        finally:
            b.close()


if __name__ == "__main__":
    unittest.main()
