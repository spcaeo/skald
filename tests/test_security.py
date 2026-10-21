"""Security (security.py, security_names.py, audit_security.py): scanner probes, what the
server answered them, attack attempts and fake browsers, counted in the tally pass as a view
across the groups, stored as the day kind `security`, held by verify's sums and recounted by
the audit's own road, which catches a planted change."""
from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import security, security_names as N  # noqa: E402
from skald.classify import Group, Verdict  # noqa: E402
from skald.parse import Hit  # noqa: E402

from security_support import CHROME, DAY, T, box, ln, put, stored  # noqa: E402


def hit(path, status="200", size=512, host="example.com", address="198.51.100.7",
        agent="curl/8.7.1", when=T, method="GET", referrer=""):
    return Hit(when=when, address=address, host=host, method=method, url=path, status=status,
               referrer=referrer, user_agent=agent, size=size)


BOT = Verdict(Group.BOTS, probe=True)


class Names(unittest.TestCase):
    def test_each_probe_gets_one_category_in_order(self):
        cases = {"/.env": "secrets", "/.git/config": "secrets", "/id_rsa": "secrets",
                 "/serverless.yml": "cloud", "/appspec.yml": "cloud", "/main.tf": "cloud",
                 "/terraform.tfstate": "cloud", "/docker-compose.yml": "cloud",
                 "/wp-login.php": "wordpress", "/xmlrpc.php": "wordpress",
                 "/backup.sql": "dumps", "/db.zip": "dumps",
                 "/phpmyadmin/index.php": "admin", "/owa/auth/logon.aspx": "admin",
                 "/phpinfo.php": "php", "/vendor/phpunit/x/eval-stdin.php": "php",
                 "/x/y": "other"}
        for path, want in cases.items():
            self.assertEqual(security.category(path, path), want, path)
        self.assertEqual(security.category("/search", "/search?q=../../etc/passwd"), "injection")
        self.assertEqual(security.injection_kind("/?x=${jndi:ldap://x}"), "log4shell")
        self.assertEqual(security.injection_kind("/?id=1 union select 1"), "sql")
        self.assertEqual(security.injection_kind("/?q=<script>"), "xss")

    def test_bare_ip_and_the_sites_own_referrers(self):
        for host in ("192.0.2.10", "192.0.2.10:443", "[2001:db8::1]", "2001:db8::1"):
            self.assertTrue(N.bare_ip(host), host)
        for host in ("example.com", "", "app.example.com:8080"):
            self.assertFalse(N.bare_ip(host), host)
        own = {"www.example.com"}
        self.assertTrue(N.own_like("wp.example.com", own))
        self.assertTrue(N.own_like("example.com", own))
        self.assertFalse(N.own_like("example.org", own))
        self.assertFalse(N.own_like("notexample.com", own))

    def test_login_paths(self):
        for p in ("/login", "/wp-login.php", "/api/auth/callback", "/contact/", "/xmlrpc.php"):
            self.assertTrue(N.LOGIN_PATH.search(p), p)
        for p in ("/pricing/", "/blog/post"):
            self.assertFalse(N.LOGIN_PATH.search(p), p)

    def test_settings_are_bounded(self):
        got = N.settings({"security": {"login_posts": "1", "burst_seconds": "x"}})
        self.assertEqual(got["login_posts"], 3)
        self.assertEqual(got["burst_seconds"], 60)


class Exposure(unittest.TestCase):
    """The rule, on the collector alone: shell, empty, possible, can't tell."""

    def collect(self, hits) -> dict:
        c = security.Collector()
        for h in hits:
            (c.other_host if N.bare_ip(h.host) else lambda x: c.add(x, BOT))(h)
        return c.finish()["exposure"]

    def test_a_spa_shell_and_a_default_page_are_harmless_each_on_its_own_host(self):
        hits = [hit(p, size=392, host="app.example.com", when=T + timedelta(seconds=i))
                for i, p in enumerate(["/.env", "/phpinfo.php", "/config/auth.php"])]
        hits += [hit(p, size=404, host="192.0.2.10", address="203.0.113.200",
                     when=T + timedelta(minutes=1, seconds=i))
                 for i, p in enumerate(["/.env", "/wp-login.php", "/.aws/credentials"])]
        e = self.collect(hits)
        self.assertEqual((e["answered"], e["shell"], e["possible"]), (6, 6, 0))
        self.assertEqual(e["hosts"]["app.example.com"]["shell_size"], 392)
        self.assertEqual(e["hosts"]["192.0.2.10"]["shell_size"], 404)
        self.assertTrue(e["hosts"]["192.0.2.10"]["bare_ip"])
        # the same page, 392 bytes through the name and 404 through the IP: one size per
        # site would have called one of them a leak
        self.assertEqual(e["rows"], [])

    def test_a_leak_unlike_the_shell_is_possible_and_says_the_shell(self):
        hits = [hit(p, size=392, host="app.example.com", when=T + timedelta(seconds=i))
                for i, p in enumerate(["/.env", "/phpinfo.php", "/admin", "/config/auth.php"])]
        hits.append(hit("/.git/config", size=1873, host="app.example.com", when=T + timedelta(minutes=1)))
        e = self.collect(hits)
        self.assertEqual((e["shell"], e["possible"]), (4, 1))
        row = e["rows"][0]
        self.assertEqual((row["path"], row["size"], row["verdict"], row["shell_size"], row["category"]),
                         ("/.git/config", 1873, "possible", 392, "secrets"))

    def test_within_the_tolerance_is_the_shell(self):
        hits = [hit(p, size=s, host="app.example.com", when=T + timedelta(seconds=i))
                for i, (p, s) in enumerate([("/a.php", 390), ("/b.php", 400), ("/c.php", 395),
                                            ("/.env", 405)])]
        e = self.collect(hits)
        self.assertEqual(e["possible"], 0)
        self.assertEqual(e["hosts"]["app.example.com"]["shell_size"], 390, "the smallest of a tie")

    def test_too_few_paths_make_no_shell_and_one_path_many_times_is_no_shell(self):
        e = self.collect([hit("/.env", size=900), hit("/.env.local", size=900, when=T + timedelta(seconds=1))])
        self.assertEqual(e["possible"], 2, "two paths are not enough to call a size the shell")
        e = self.collect([hit("/.env", size=1873, when=T + timedelta(seconds=i)) for i in range(5)])
        self.assertEqual((e["possible"], e["hosts"]["example.com"]["shell_size"]), (5, None),
                         "one file asked five times is still a file")

    def test_no_size_is_cant_tell_never_safe_and_empty_is_empty(self):
        e = self.collect([hit("/.env", size=None), hit("/.git/HEAD", size=0, when=T + timedelta(seconds=1))])
        self.assertEqual((e["unknown"], e["empty"], e["shell"], e["possible"]), (1, 1, 0, 0))
        self.assertEqual(e["rows"][0]["verdict"], "unknown")
        self.assertIsNone(e["rows"][0]["size"])

    def test_only_2xx_answers_are_judged(self):
        e = self.collect([hit("/.env", status="404", size=1873), hit("/.env", status="301", size=0)])
        self.assertEqual(e["answered"], 0)


class Episodes(unittest.TestCase):
    def posts(self, n, step):
        c = security.Collector()
        for i in range(n):
            c.add(hit("/login", status="401", method="POST", address="198.51.100.10",
                      agent="python-requests/2.31", when=T + timedelta(seconds=step * i)),
                  Verdict(Group.BOTS))
        return c.finish()["attacks"]["login"]

    def test_the_login_threshold(self):
        self.assertEqual(self.posts(19, 1)["episodes"], 0, "19 POSTs in 5 minutes: not enough")
        got = self.posts(20, 1)
        self.assertEqual((got["episodes"], got["posts"]), (1, 20))
        self.assertEqual(got["rows"][0]["status"], {"4xx": 20})
        self.assertEqual(self.posts(30, 20)["episodes"], 0, "30 POSTs over 10 minutes: never 20 in 5")
        got = self.posts(40, 14)                # 20 in 266 s, spread over 9 minutes
        self.assertEqual(got["episodes"], 1)
        self.assertEqual(got["posts"], 40)

    def test_a_burst_and_crawlers_are_left_out(self):
        c = security.Collector()
        for i in range(300):
            c.add(hit("/x", address="198.51.100.11", agent="Scrapy", when=T + timedelta(milliseconds=150 * i)),
                  Verdict(Group.BOTS))
            c.add(hit("/x", address="198.51.100.50", agent="Googlebot", when=T + timedelta(milliseconds=150 * i)),
                  Verdict(Group.SEARCH_ENGINE, engine="Googlebot"))
        got = c.finish()
        self.assertEqual((got["attacks"]["bursts"]["episodes"], got["attacks"]["bursts"]["requests"]), (1, 300))
        self.assertEqual(got["who"][0]["burst"], 300)


class Day(unittest.TestCase):
    """The whole road: collect, verify, store, audit."""

    def setUp(self):
        self.box = box()
        code, _, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_counted_stored_and_audited(self):
        b = stored(self.box)
        self.assertEqual((b["probes"], b["probes_other"], b["scanners"], b["bare_ip"]), (12, 3, 4, 3))
        self.assertEqual(sum(b["categories"].values()), b["probes"])
        self.assertEqual(b["exposure"]["possible"], 1)
        self.assertEqual(b["exposure"]["rows"][0]["path"], "/.env.production")
        self.assertEqual(b["attacks"]["login"]["posts"], 25)
        self.assertEqual(b["attacks"]["bursts"]["requests"], 320)
        self.assertEqual(b["attacks"]["injection"]["kinds"], {"log4shell": 1, "traversal": 1})
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)

    def test_scanners_grouped_with_their_categories_and_signs(self):
        b = stored(self.box)
        rows = {(r["country"], r["probes"]): r for r in b["who"]}
        spa = rows[("SG", 5)]
        self.assertEqual(spa["categories"], {"admin": 1, "php": 3, "secrets": 1})
        self.assertEqual(spa["probe_status"], {"2xx": 5})
        self.assertFalse(spa["forged"])
        leak = rows[("HK", 2)]
        self.assertTrue(leak["forged"], "a referrer of the site's wp. subdomain, and nothing rendered")
        self.assertEqual(leak["categories"], {"cloud": 1, "secrets": 1})
        bare = rows[("NL", 3)]
        self.assertEqual(bare["bare_ip"], 3)
        self.assertEqual(b["forged"], 1)
        kinds = {r["seq"]: r["kinds"] for r in b["who"]}
        self.assertTrue(any(k == ["attack"] for k in kinds.values()), "the hammering address is a suspect")
        self.assertFalse(any(r["country"] == "US" and r["requests"] == 2 for r in b["who"]),
                         "the person who rendered the page is no suspect")

    def test_no_address_or_agent_in_history(self):
        import sqlite3
        with sqlite3.connect(self.box.db) as db:
            data = " ".join(d for (d,) in db.execute(
                "SELECT data FROM day_extras WHERE kind = 'security'"))
        for word in ("198.51.100.", "203.0.113.", "curl/", "Mozilla", "python-requests"):
            self.assertNotIn(word, data)
        self.assertIn("192.0.2.10", data, "the server's own address as a host is not a person's")

    def test_the_groups_are_unchanged(self):
        """Security is a view: the five groups still add up to the site's requests."""
        import sqlite3
        with sqlite3.connect(self.box.db) as db:
            hits = db.execute("SELECT hits FROM days WHERE day = ?", (DAY,)).fetchone()[0]
            groups = db.execute("SELECT SUM(hits) FROM groups WHERE day = ?", (DAY,)).fetchone()[0]
        self.assertEqual(hits, groups)
        self.assertEqual(hits, 356, "the 3 bare-IP lines stay another host's")

    def test_the_audit_catches_a_change_anywhere(self):
        b = stored(self.box)
        b["exposure"]["possible"] = 0
        b["exposure"]["shell"] += 1
        b["exposure"]["rows"] = []
        put(self.box, b)
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("security.exposure.possible", err)
        self.assertNotIn("198.51.100.", err, "no address in a problem")

    def test_the_audit_catches_a_moved_category_and_a_dropped_row(self):
        b = stored(self.box)
        b["who"][0]["categories"]["php"] -= 1
        b["who"][0]["categories"]["other"] = 1
        del b["who"][-1]
        put(self.box, b)
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("security.who", err)

    def test_verify_holds_the_sums(self):
        import tempfile
        from skald.aggregate import summarise_views
        from skald import Classifier, read
        from skald.verify import check
        from security_support import day_lines
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(day_lines()))
            totals = summarise_views(read([path]), Classifier([]), 30,
                                     hosts=["example.com", "app.example.com"])[0]
        self.assertEqual(check(totals), [])
        blob = totals.extras["security"]
        blob["categories"]["secrets"] += 1
        self.assertTrue(any(p.what == "security: probes by categories" or "categories" in str(p)
                            for p in check(totals)))
        blob["categories"]["secrets"] -= 1
        blob["exposure"]["shell"] += 1
        self.assertTrue(check(totals))

    def test_a_view_has_none(self):
        import tempfile
        from skald.aggregate import summarise_views
        from skald import Classifier, read
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text(ln(T, "198.51.100.7", "/blog/.env", "curl/8.7.1", 404, 0))
            whole, views = summarise_views(read([path]), Classifier([]), 30,
                                           hosts=["example.com"],
                                           views={"blog": lambda h: h.path.startswith("/blog")})
        self.assertEqual(whole.extras["security"]["probes"], 1)
        self.assertNotIn("security", views["blog"].extras)

    def test_the_live_run_counts_today_and_its_audit_compares_it(self):
        import json
        import os
        from datetime import datetime, timezone
        stamp = datetime(2026, 10, 5, 23, tzinfo=timezone.utc).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", "2026-10-05", "live")[0], 0)
        code, _, err = self.box.run("--today", "2026-10-05", "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["extras"]["security"]["exposure"]["possible"], 1)


class Legacy(unittest.TestCase):
    def test_an_old_path_of_the_site_is_no_probe(self):
        b = box([ln(T, "198.51.100.7", "/wp-content/old.jpg", "curl/8.7.1", 200, 900),
                 ln(T + timedelta(seconds=1), "198.51.100.7", "/.env", "curl/8.7.1", 404, 0)],
                "")
        text = b.config.read_text().replace("require_rendering: false",
                                            "require_rendering: false\n  legacy_paths: [/wp-content/]")
        b.config.write_text(text)
        try:
            self.assertEqual(b.run("--today", "2026-10-06", "collect")[0], 0)
            self.assertEqual(stored(b)["probes"], 1)
            self.assertEqual(b.run("--today", "2026-10-06", "audit")[0], 0)
        finally:
            b.close()


class NoSizes(unittest.TestCase):
    def test_a_log_without_bytes_cannot_tell(self):
        lines = [ln(T + timedelta(seconds=i), "198.51.100.7", p, "curl/8.7.1", 200, None)
                 for i, p in enumerate(["/.env", "/phpinfo.php", "/admin"])]
        b = box(lines)
        try:
            self.assertEqual(b.run("--today", "2026-10-06", "collect")[0], 0)
            e = stored(b)["exposure"]
            self.assertEqual((e["unknown"], e["shell"], e["possible"]), (3, 0, 0))
            self.assertEqual(b.run("--today", "2026-10-06", "audit")[0], 0)
        finally:
            b.close()


if __name__ == "__main__":
    unittest.main()
