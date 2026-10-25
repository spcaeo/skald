"""Tools in a browser's clothes (CLASSIFICATION.md rules 6c and 8b, COUNTING-TRAPS.md trap 18).

Found on live sites, 21 to 24 Oct 2026, all counted as people:

  * an attack whose traversal was encoded twice (templates%252f%252e%252e...),
    sent with five browser agents, with "/" pages and font fetches between
    the attempts and a POST / every few seconds (1,260 page views a day);
  * a scanner with a Chrome agent that asked for /index.php, /info.php,
    /phpinfo.php, /login.php, /admin/, /wp-login.php ... on a site that runs
    none of them (all 404), and read "/" between them;
  * a link checker with a Chrome agent: GET a page, load its assets, HEAD
    every link on it - 560 page views in one visit.

Pinned here: each is bots on both roads, the groups still add up, and the
readers next to them (a WordPress reader, a person with a few 404s, a page
whose script sends one HEAD) stay people. Addresses are RFC 5737's.
"""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, tool_visits  # noqa: E402
from skald.classify import (LINK_CHECKER, PROBE_QUERY, SCANNER, SWEEP,  # noqa: E402
                                   Classifier)
from skald.parse import Hit  # noqa: E402
from skald.store import History  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, Sandbox, line  # noqa: E402

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 23)
TODAY = "2026-10-24"
SAFARI = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
HOSTS = {"site": {"hosts": ["example.com"]}}
# The live attack's query, as the log had it.
ATTACK = ("/?page_id=1&pagename=templates%252f%252e%252e%252f%252e%252e%252f%252e%252e"
          "%252fusr%252flib%252fphp%252f20230831%252fpearcmd")
SWEEP_PATHS = ["/index.php", "/info.php", "/phpinfo.php", "/login.php", "/admin/",
               "/admin/index.php", "/wp-login.php", "/wp-admin/", "/dashboard.php"]


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def method(text: str, verb: str) -> str:
    return text.replace('"GET ', f'"{verb} ', 1)


def asset(when, address, agent, page="/", path="/_next/static/css/app.css"):
    return line(when, address, path, agent, f"https://example.com{page}")


def reader(when, address, agent, page="/"):
    """A person: a page and its stylesheet."""
    return [line(when, address, page, agent), asset(when, address, agent, page)]


def count(lines, config=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(sorted(lines)))
        start, end = day_window(DAY, UTC)
        return analyse_window(config or HOSTS, start, end, paths=[path])


def attack_fixture():
    """The twice-encoded attack from two addresses and three agents, with
    pages, fonts and POSTs between, and an honest reader."""
    out = []
    for k, (address, agent) in enumerate([("203.0.113.80", CHROME), ("203.0.113.80", SAFARI),
                                          ("203.0.113.81", FIREFOX)]):
        base = at(17, 10 + k)
        out += reader(base, address, agent)
        out.append(asset(base, address, agent, path="/_next/static/media/font.woff2"))
        out.append(line(base, address, ATTACK, agent))
        out.append(method(line(at(17, 10 + k, 5), address, "/", agent), "POST"))
        out += [line(at(17, 10 + k, 9), address, "/", agent)]
    honest = reader(at(9), "198.51.100.20", SAFARI) + reader(at(9, 5), "198.51.100.20", SAFARI,
                                                              "/pricing/")
    return out, honest


def sweep_fixture():
    scanner = reader(at(10), "203.0.113.90", CHROME)
    scanner += [line(at(10, 0, 7 + k), "203.0.113.90", p, CHROME, status=404)
                for k, p in enumerate(SWEEP_PATHS)]
    scanner += reader(at(10, 2), "203.0.113.90", CHROME)
    return scanner


def checker_fixture():
    tool = reader(at(14), "203.0.113.95", CHROME, "/about/")
    tool += [method(line(at(14, 0, 1), "203.0.113.95", p, CHROME), "HEAD")
             for p in ("/", "/services/", "/contact/")]
    tool += reader(at(14, 0, 6), "203.0.113.95", CHROME, "/case-studies/")
    return tool


class TestTheAttackString(unittest.TestCase):

    def test_twice_and_thrice_encoded_traversal_is_an_attack(self):
        for url in (ATTACK, "/?f=%2e%2e%2fetc", "/?f=%25252e%25252e%25252f", "/?f=.%2e/x",
                    "/?f=%2e.%5cwin", "/?f=%252fetc%252fpasswd", "/?f=..%2f"):
            with self.subTest(url=url):
                self.assertTrue(PROBE_QUERY.search(url))

    def test_ordinary_queries_and_pages_are_not(self):
        for url in ("/?page=2", "/search?q=v1..v2", "/?utm_source=a.b", "/x?v=1.5.0",
                    "/blog/how-to-read-etc-passwd/", "/?page_id=1&pagename=templates",
                    "/pricing/?plan=pro%2Fyear"):
            with self.subTest(url=url):
                self.assertIsNone(PROBE_QUERY.search(url))

    def test_the_made_up_sitemap_matches_nothing(self):
        text = (ROOT / "tests" / "fixtures" / "site_paths.txt").read_text()
        site = [p.strip() for p in text.splitlines() if p.startswith("/")]
        self.assertEqual([p for p in site if PROBE_QUERY.search(p)], [])

    def test_the_attacker_is_bots_with_its_pages_and_posts(self):
        attack, honest = attack_fixture()
        totals = count(attack + honest)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.hits, people.views, people.readers), (len(honest), 2, 1))
        self.assertEqual(people.posts, 0, "its POST / is no form a person sent")
        bots = totals.groups[Group.BOTS]
        self.assertEqual(bots.probes, 3)
        self.assertEqual(bots.agents[SCANNER], len(attack) - 3)
        self.assertEqual(sum(g.hits for g in totals.groups.values()), len(attack + honest))


class TestProbeSweep(unittest.TestCase):

    def test_a_sweep_moves_the_whole_visitor(self):
        honest = reader(at(10, 1), "203.0.113.90", SAFARI)      # same address, another browser
        totals = count(sweep_fixture() + honest)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.hits, people.readers), (len(honest), 1))
        bots = totals.groups[Group.BOTS]
        self.assertEqual(bots.probes, len(SWEEP_PATHS))
        self.assertEqual(bots.agents[SWEEP], 4, "its four page and asset requests")
        self.assertEqual(sum(g.hits for g in totals.groups.values()), 9 + 4 + 2)

    def test_four_missing_probes_are_not_enough(self):
        lines = reader(at(10), "203.0.113.91", CHROME)
        lines += [line(at(10, 0, 3 + k), "203.0.113.91", p, CHROME, status=404)
                  for k, p in enumerate(SWEEP_PATHS[:4])]
        self.assertEqual(count(lines).groups[Group.PEOPLE].readers, 1)

    def test_served_redirected_old_and_asset_probes_do_not_count(self):
        # A WordPress reader (200s), an admin at work (302s), a page that
        # still embeds the old site's images (404 assets), and old URLs
        # under site.legacy_paths: none of them is a sweep.
        lines = reader(at(11), "203.0.113.92", SAFARI)
        lines += [line(at(11, 0, 5 * k + 5), "203.0.113.92", p, SAFARI, "https://example.com/")
                  for k, p in enumerate(("/wp-json/wp/v2/posts", "/wp-json/wp/v2/pages",
                                         "/xmlrpc.php", "/wp-includes/blocks/",
                                         "/wp-content/plugins/a/"))]
        lines += reader(at(11, 5), "203.0.113.93", FIREFOX)
        lines += [line(at(11, 5, 1), "203.0.113.93", p, FIREFOX, status=302)
                  for p in ("/wp-admin/post.php", "/wp-admin/options.php", "/wp-login.php",
                            "/wp-admin/admin-post.php", "/wp-admin/edit.php")]
        lines += reader(at(11, 9), "203.0.113.94", CHROME)
        lines += [line(at(11, 9, 1), "203.0.113.94", f"/wp-content/uploads/2024/0{k}/a.png",
                       CHROME, "https://example.com/", 404) for k in range(1, 7)]
        lines += reader(at(12), "203.0.113.96", CHROME)
        lines += [line(at(12, 0, 1), "203.0.113.96", f"/old/page{k}.php", CHROME, status=404)
                  for k in range(6)]
        config = {"site": {"hosts": ["example.com"], "legacy_paths": ["/old/"]}}
        totals = count(lines, config)
        self.assertEqual(totals.groups[Group.PEOPLE].readers, 4)
        self.assertNotIn(SWEEP, totals.groups[Group.BOTS].agents)

    def test_names_come_first(self):
        c = Classifier()
        c.sweepers = {("198.51.100.8", "Mozilla/5.0 (compatible; Googlebot/2.1)"),
                      ("203.0.113.90", CHROME)}
        hit = Hit(at(9), "203.0.113.90", "example.com", "GET", "/", "200", "", CHROME)
        self.assertEqual(c(hit).engine, SWEEP)
        bot = Hit(at(9), "198.51.100.8", "example.com", "GET", "/", "200", "",
                  "Mozilla/5.0 (compatible; Googlebot/2.1)")
        self.assertIs(c(bot).group, Group.SEARCH_ENGINE)


class TestLinkChecker(unittest.TestCase):

    def test_head_for_pages_moves_the_whole_visit(self):
        honest = reader(at(15), "203.0.113.95", SAFARI)
        totals = count(checker_fixture() + honest)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.hits, people.readers), (2, 1))
        self.assertEqual(totals.groups[Group.BOTS].agents[LINK_CHECKER], 7)

    def test_only_the_visit_that_sent_head(self):
        later = reader(at(18), "203.0.113.95", CHROME, "/blog/")   # hours later: a new visit
        totals = count(checker_fixture() + later)
        self.assertEqual(totals.groups[Group.PEOPLE].hits, 2)
        self.assertEqual(totals.groups[Group.BOTS].agents[LINK_CHECKER], 7)

    def test_one_head_or_head_for_assets_stays_a_person(self):
        lines = reader(at(16), "203.0.113.97", CHROME)
        lines.append(method(line(at(16, 0, 2), "203.0.113.97", "/status/", CHROME,
                                 "https://example.com/"), "HEAD"))
        lines += [method(asset(at(16, 0, 3), "203.0.113.97", CHROME, path=p), "HEAD")
                  for p in ("/_next/static/a.js", "/logo.png", "/api/health")]
        totals = count(lines)
        self.assertEqual(totals.groups[Group.PEOPLE].hits, len(lines))
        self.assertNotIn(Group.BOTS, totals.groups)

    def test_a_tool_that_says_so_is_a_bot_anyway(self):
        lines = [method(line(at(16), "203.0.113.98", p, "curl/8.7.1"), "HEAD")
                 for p in ("/", "/a/")]
        totals = count(lines)
        self.assertNotIn(LINK_CHECKER, totals.groups[Group.BOTS].agents)


class TestBothRoads(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        attack, honest = attack_fixture()
        self.box.log(sorted(attack + honest + sweep_fixture() + checker_fixture()))

    def collect_and_audit(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def people(self):
        with History(self.box.db) as h:
            return h.db.execute("SELECT hits, views, visits, readers FROM groups WHERE "
                                "site = ? AND day = ? AND grp = 'people'",
                                ("example.com", DAY.isoformat())).fetchone()

    def test_the_audit_agrees(self):
        code, out, err = self.collect_and_audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        self.assertEqual(self.people(), (4, 2, 1, 1))

    def test_the_audit_catches_a_main_road_without_the_sweep(self):
        with mock.patch.object(tool_visits.ProbeSweep, "__call__", lambda self, hit: None):
            code, out, err = self.collect_and_audit()
        self.assertEqual(code, 1, out)
        self.assertIn("people", err)

    def test_the_audit_catches_a_main_road_without_the_link_checker(self):
        with mock.patch.object(tool_visits.HeadChecks, "spans", lambda self: {}):
            code, out, err = self.collect_and_audit()
        self.assertEqual(code, 1, out)
        self.assertIn("people", err)


class TestIndependence(unittest.TestCase):

    def test_the_audit_shares_only_the_name_lists(self):
        from skald import audit_tools
        tree = ast.parse(Path(audit_tools.__file__).read_text())
        got = {(n.module, a.name) for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(got, {("classify", "OTHER_BOT"), ("classify", "PROBE")})


if __name__ == "__main__":
    unittest.main()
