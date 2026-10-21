"""Security > Your stack (stack.py, advisories.py, audit_stack.py): what serves a site, read
from outside through the safe fetcher (here a fake one: no network in tests), the advisories
shipped with Skald matched against it, kept per day, and read again by the second count."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import advisories, audit_stack, site_fetch, stack  # noqa: E402

NOW = datetime(2026, 10, 21, 11, tzinfo=timezone.utc)
DOC = advisories.load()
PHP, NODE = DOC["advisories"]
HOME_WP = (b'<html><head><meta name="generator" content="WordPress 6.4.2"><title>Home</title>'
           b'</head><body><img src="https://media.example.com/wp-content/uploads/a.png"></body></html>')
HOME_NEXT = b'<html><body><div id="__next"></div><script src="/_next/static/a.js"></script></body></html>'


def answer(status=200, headers=None, body=b"", url=""):
    return site_fetch.Answer(status=status, headers={k.lower(): [v] for k, v in (headers or {}).items()},
                             body=body, url=url)


def fake(pages: dict, asked: list | None = None):
    def fetch(url, method):
        if asked is not None:
            asked.append((method, url))
        got = pages.get((method, url)) or pages.get(url)
        if got is None:
            raise site_fetch.Unreachable("it did not answer in time")
        return got
    return fetch


SITE = {
    "https://example.com/": answer(200, {"Server": "nginx", "X-Powered-By": "PHP/8.1.2"}, HOME_WP),
    ("HEAD", "https://example.com/wp-login.php"): answer(403),
    "https://app.example.com/": answer(200, {"Server": "nginx/1.24.0", "X-Powered-By": "Next.js"}, HOME_NEXT),
    "https://media.example.com/": answer(200, {"Server": "Apache/2.4.58 (Ubuntu)", "X-Powered-By": "PHP/8.3.10"}, b""),
    ("HEAD", "https://media.example.com/wp-login.php"): answer(200),
}
HOSTS = ["example.com", "www.example.com", "app.example.com"]


class Reading(unittest.TestCase):
    def test_products_and_hidden_versions(self):
        got = stack.products("example.com", {"server": "nginx/1.24.0", "powered_by": "PHP/8.1.2",
                                             "generator": "WordPress 6.4.2", "markers": ["wp-content"]})
        self.assertEqual({(p["product"], p["version"]) for p in got},
                         {("nginx", "1.24.0"), ("php", "8.1.2"), ("wordpress", "6.4.2")})
        got = stack.products("example.com", {"server": "nginx", "powered_by": "", "generator": "",
                                             "markers": ["wp-content"]})
        self.assertEqual({(p["product"], p["version"]) for p in got},
                         {("nginx", None), ("wordpress", None), ("php", None)},
                         "a version the server does not show is None, never guessed")
        got = stack.products("app.example.com", {"server": "", "powered_by": "Next.js", "generator": "",
                                                 "markers": ["_next"]})
        self.assertEqual({(p["product"], p["version"]) for p in got}, {("nextjs", None), ("nodejs", None)})
        self.assertEqual(stack.origins(HOME_WP.decode(), "example.com"), ["media.example.com"])
        self.assertEqual(stack.site_hosts(HOSTS), ["example.com", "app.example.com"])
        # documentation and test names are never fetched for real (tests, the sample install)
        self.assertTrue(all(stack.reserved(h) for h in ("example.com", "app.example.org", "site.test")))
        self.assertFalse(stack.reserved("shop.example.co.uk"))

    def test_the_states(self):
        self.assertEqual([advisories.judge(PHP, v) for v in ("8.3.10", "8.3.36", "8.4.30", "8.1.2", "7.4.33", None, "8")],
                         ["update_needed", "fixed", "fixed", "no_fix", "no_fix", "check_version", "check_version"])
        self.assertEqual([advisories.judge(NODE, v) for v in ("22.1.0", "24.22.1", "23.11.0", "20.18.0", "27.0.0")],
                         ["update_needed", "fixed", "no_fix", "no_fix", "not_listed"])
        for a, v in ((PHP, "8.3.10"), (PHP, "8.1.2"), (NODE, "23.1.0"), (NODE, None), (NODE, "27.1.0")):
            self.assertEqual(audit_stack.state(a, v), advisories.judge(a, v), (a["id"], v))

    def test_the_shipped_list_is_valid_and_dated(self):
        self.assertTrue(advisories.valid(DOC))
        self.assertEqual(DOC["updated"], "2026-10-21")
        self.assertEqual(PHP["fixed"], {"8.5": "8.5.12", "8.4": "8.4.27", "8.3": "8.3.36", "8.2": "8.2.35"})
        self.assertEqual(NODE["fixed"], {"22": "22.23.4", "24": "24.22.1", "26": "26.12.1"})
        self.assertTrue(all(u.startswith("https://") for a in DOC["advisories"] for u in a["sources"]))


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.said = []
        self.ctx = SimpleNamespace(config={"site": {"hosts": HOSTS}}, live_dir=self.dir, site="example.com",
                                   now=NOW, tz=ZoneInfo("UTC"), out=self.said.append, err=self.said.append)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_check_kept_with_its_matches_and_audited(self):
        asked = []
        self.assertEqual(stack.daily(self.ctx, fake(SITE, asked)), 0)
        self.assertIn(("HEAD", "https://media.example.com/wp-login.php"), asked)
        self.assertNotIn(("GET", "https://www.example.com/"), asked, "www. is the same site")
        day, blob = stack.latest(self.dir, "example.com")
        self.assertEqual(day, "2026-10-21")
        self.assertEqual(blob["checked_at"], "2026-10-21T11:00:00+00:00")
        r = blob["read"]
        states = {(m["host"], m["product"]): m["state"] for m in r["matches"]}
        self.assertEqual(states, {("example.com", "php"): "no_fix", ("media.example.com", "php"): "update_needed",
                                  ("app.example.com", "nodejs"): "check_version"})
        self.assertEqual({x["host"]: x["open"] for x in r["logins"]},
                         {"example.com": False, "media.example.com": True})
        self.assertEqual(audit_stack.daily(self.ctx, None), [])
        # the site's alert (dashboard, its mail, Slack): one per match that needs something done
        from skald import alerts_security
        got = alerts_security.advisory_findings("example.com", self.dir)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(f["cause"] == "stack_advisory" and f["subject"].startswith("a") for f in got))
        self.assertIn("Update needed", " ".join(f["title"] for f in got))
        # a planted change: the kept state no longer what the evidence says
        r["matches"][0]["state"] = "fixed"
        kept = stack.stored(self.dir, "example.com")
        kept["days"][day] = blob
        stack.path_for({}, self.dir, "example.com").write_text(json.dumps(kept))
        self.assertTrue(audit_stack.daily(self.ctx, None))

    def test_a_failure_never_stops_the_run_and_the_switch(self):
        self.assertEqual(stack.daily(self.ctx, fake({})), 0)
        _, blob = stack.latest(self.dir, "example.com")
        self.assertEqual(blob["read"]["products"], [])
        self.assertTrue(blob["hosts"][0]["error"])
        self.ctx.config["security"] = {"stack_check": False}
        (self.dir / "stack-example.com.json").unlink()
        self.assertEqual(stack.daily(self.ctx, fake(SITE)), 0)
        self.assertIsNone(stack.latest(self.dir, "example.com"))
        self.assertIsNone(audit_stack.daily(self.ctx, None))

    def test_no_phoning_home_unless_asked(self):
        self.assertEqual(advisories.refresh({}, self.dir, fetch=lambda u: 1 / 0), "off")
        newer = dict(DOC, updated="2026-11-01")
        on = {"security": {"advisories_fetch": True}}
        got = advisories.refresh(on, self.dir, fetch=lambda u: answer(200, body=json.dumps(newer).encode()))
        self.assertIn("2026-11-01", got)
        self.assertEqual(advisories.load(self.dir)["updated"], "2026-11-01")
        bad = advisories.refresh(on, self.dir, fetch=lambda u: answer(200, body=b'{"schema": 2}'))
        self.assertIn("not valid", bad)
        self.assertEqual(advisories.load()["updated"], "2026-10-21", "the shipped list is untouched")

    def test_the_data_file_carries_the_stack_and_its_cards(self):
        from skald import security_page
        stack.daily(self.ctx, fake(SITE))
        p = SimpleNamespace(live_dir=self.dir, site="example.com", key="example.com", config={}, view=None)
        p.history = SimpleNamespace(extras=lambda *a, **k: {})
        p.daily, p.first, p.anchor = [], NOW.date(), NOW.date()
        p.today_block = lambda: None
        p.live_ok = False
        got = security_page.build(p)["stack"]
        self.assertEqual(got["day"], "2026-10-21")
        self.assertEqual({a["id"] for a in got["advisories"]}, {"php-2026-10-21", "nodejs-2026-10"})
        self.assertEqual(got["commands"]["php"], "php -v")



class StackCommand(unittest.TestCase):
    def test_the_stack_command_runs_the_daily_check(self):
        from skald import cli, stack
        args = cli.parser().parse_args(["stack"])
        self.assertIs(args.run, stack.daily)


if __name__ == "__main__":
    unittest.main()
