"""One probe marks the whole visitor (CLASSIFICATION.md rule 6b, COUNTING-TRAPS.md trap 17).

Found on the live site (21 Oct 2026): "What visitors are doing now" showed a
person "from wp.<site>, now on /". In about two seconds the same address
and "Chrome" agent asked for six .env files (scanner probes, so bots) and for
/cdk.out, /outputs.tf, /variables.tf, /terraform.tfvars.json, /appspec.yml and
/main.tf (no probe shape then, so "people: client error"), with a forged
referrer of the site's own wp. subdomain.

Pinned here: those infrastructure files are probes now, and no page of the
made-up sitemap is; an address and agent that sent any probe on the day is
a scanner on every request of that day, before the probe and after it, so
none of its requests are people, page views or a live visitor; the same
address with another agent stays a person; the audit's own road agrees, and
catches a main road that only marks what comes after the probe.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, requests_feed  # noqa: E402
from skald import classify, tool_visits  # noqa: E402
from skald.classify import PROBE, SCANNER, SECRET_PROBE, Classifier  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald.store import History  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, GOOGLEBOT, Sandbox, line  # noqa: E402

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 21)
TODAY = "2026-10-22"
SAFARI = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
SCANNER_IP = "203.0.113.66"
FORGED = "https://wp.example.com/"

# The scanner's own requests, as the live log had them (path, status).
LIVE_PROBES = [("/.env.production.local", 404), ("/.env.development", 404),
               ("/.env.dev", 404), ("/.env.bak", 404), ("/.env.development.local", 404),
               ("/.env.prod.bak", 499), ("/cdk.out", 499), ("/outputs.tf", 499),
               ("/variables.tf", 499), ("/terraform.tfvars.json", 499),
               ("/appspec.yml", 499), ("/main.tf", 499)]
MORE_PROBES = ["/.terraform/terraform.tfstate", "/terraform.tfstate.backup",
               "/infra/prod.tfvars", "/api/main.tf.json", "/cdk.context.json", "/cdk.json",
               "/cdk.out/manifest.json", "/buildspec.yml", "/serverless.yaml",
               "/samconfig.toml", "/template.yaml", "/values.yaml", "/Chart.yaml",
               "/kubeconfig", "/.kube/config", "/.gitlab-ci.yml", "/.travis.yml",
               "/.circleci/config.yml", "/.github/workflows/deploy.yml", "/Jenkinsfile",
               "/Dockerfile", "/composer.json", "/composer.lock", "/package.json",
               "/package-lock.json", "/yarn.lock", "/app/yarn.lock", "/requirements.txt",
               "/bitbucket-pipelines.yml"]
# Probes a real reader may also send: they move only themselves.
SERVED = ["/wp-content/themes/a/style.css", "/wp-includes/js/jquery.js", "/wp-json/wp/v2/posts",
          "/wp-admin/admin-ajax.php", "/index.php", "/admin/", "/config.json",
          "/appsettings.json", "/env.js", "/firebase-config.json"]
# Real pages a site may have, with the same words: never probes.
PAGES = ["/terraform/", "/main-features/", "/blog/terraform-vs-pulumi/",
         "/services/kubernetes-consulting/", "/serverless-app-development/",
         "/jenkins-alternatives/", "/composer/", "/package/", "/packages/pricing/",
         "/values/", "/about/our-values/", "/templates/", "/templates/timesheet-template/",
         "/docs/template.yaml-guide/", "/blog/values.yaml/", "/guides/package.json-explained/",
         "/fonts/inter.ttf", "/models/chair.gltf", "/fonts/serif.otf", "/cdk/",
         "/cdk-tutorial/", "/blog/appspec-explained/", "/charts/", "/docker/",
         "/telemedicine-app-development/"]


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def asset(when, address, agent, page="/"):
    return line(when, address, "/_next/static/css/app.css", agent, f"https://example.com{page}")


def fixture() -> tuple[list[str], dict]:
    """The live scanner, a probe first, a probe last, and an honest visitor
    on the scanner's address with another agent. Returns (lines, expected)."""
    scanner = [line(at(10), SCANNER_IP, "/", CHROME, FORGED),
               asset(at(10), SCANNER_IP, CHROME)]               # it even "rendered"
    scanner += [line(at(10, 0, 1 + k // 6), SCANNER_IP, p, CHROME, FORGED, s)
                for k, (p, s) in enumerate(LIVE_PROBES)]
    scanner.append(line(at(10, 0, 3), SCANNER_IP, "/contact/", CHROME, FORGED))   # after
    first = [line(at(11), "203.0.113.67", "/.git/config", FIREFOX, status=404),
             line(at(11, 0, 5), "203.0.113.67", "/pricing/", FIREFOX),
             asset(at(11, 0, 5), "203.0.113.67", FIREFOX, "/pricing/")]
    last = [line(at(12), "203.0.113.68", "/", SAFARI),
            asset(at(12), "203.0.113.68", SAFARI),
            line(at(12, 5), "203.0.113.68", "/blog/", SAFARI),
            asset(at(12, 5), "203.0.113.68", SAFARI, "/blog/"),
            line(at(23, 50), "203.0.113.68", "/composer.json", SAFARI, status=404)]
    honest = [line(at(10, 1), SCANNER_IP, "/", SAFARI),
              asset(at(10, 1), SCANNER_IP, SAFARI),
              line(at(10, 3), SCANNER_IP, "/services/", SAFARI),
              asset(at(10, 3), SCANNER_IP, SAFARI, "/services/")]
    lines = sorted(scanner + first + last + honest)      # the timestamp leads each line
    probes = len(LIVE_PROBES) + 2
    return lines, {"people_hits": len(honest), "probes": probes,
                   "scanner": len(scanner) + len(first) + len(last) - probes}


class TestProbeShapes(unittest.TestCase):

    def test_the_live_scanners_paths_are_all_probes(self):
        for path, _ in LIVE_PROBES:
            with self.subTest(path=path):
                self.assertTrue(PROBE.search(path))

    def test_infrastructure_files_are_probes(self):
        for path in MORE_PROBES:
            with self.subTest(path=path):
                self.assertTrue(PROBE.search(path))

    def test_secret_and_infrastructure_files_mark_the_visitor(self):
        for path in [p for p, _ in LIVE_PROBES] + MORE_PROBES:
            with self.subTest(path=path):
                self.assertTrue(SECRET_PROBE.search(path))

    def test_paths_real_readers_ask_for_are_probes_that_mark_no_one(self):
        # A WordPress site's assets and API, a PHP page, the owner's /admin,
        # an app's settings file: each request is a probe, never a scanner.
        for path in SERVED:
            with self.subTest(path=path):
                self.assertTrue(PROBE.search(path))
                self.assertIsNone(SECRET_PROBE.search(path))

    def test_real_pages_with_the_same_words_are_not(self):
        for path in PAGES:
            with self.subTest(path=path):
                self.assertIsNone(PROBE.search(path))

    def test_the_made_up_sitemap_still_matches_nothing(self):
        text = (ROOT / "tests" / "fixtures" / "site_paths.txt").read_text()
        site = [p.strip() for p in text.splitlines() if p.startswith("/")]
        self.assertEqual(len(site), 475)
        self.assertEqual([p for p in site if PROBE.search(p)], [])


def count(lines, config=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        start, end = day_window(DAY, UTC)
        return analyse_window(config or {"site": {"hosts": ["example.com"]}}, start, end,
                              paths=[path])


class TestMainRoad(unittest.TestCase):

    def test_one_probe_moves_the_whole_visitor_and_the_groups_add_up(self):
        lines, want = fixture()
        totals = count(lines)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.hits, people.views, people.visits, people.readers),
                         (want["people_hits"], 2, 1, 1), "only the honest visitor")
        self.assertEqual(set(people.pages), {"/", "/services/"})
        bots = totals.groups[Group.BOTS]
        self.assertEqual(bots.probes, want["probes"])
        self.assertEqual(bots.agents[SCANNER], want["scanner"])
        self.assertEqual(sum(g.hits for g in totals.groups.values()), len(lines))

    def test_rule_off_without_a_probe(self):
        lines, _ = fixture()
        clean = [l for l in lines if not any(f" {p} " in l for p, _ in LIVE_PROBES)
                 and "/.git/" not in l and "/composer.json" not in l]
        totals = count(clean)
        self.assertNotIn(Group.BOTS, totals.groups)
        self.assertEqual(totals.groups[Group.PEOPLE].hits, len(clean))

    def test_a_legacy_path_marks_no_one(self):
        lines = [line(at(9), "203.0.113.70", "/wp-content/uploads/a.png", SAFARI,
                      "https://example.com/"),
                 line(at(9), "203.0.113.70", "/", SAFARI),
                 asset(at(9), "203.0.113.70", SAFARI)]
        totals = count(lines, {"site": {"hosts": ["example.com"],
                                        "legacy_paths": ["/wp-content/"]}})
        self.assertEqual(totals.groups[Group.PEOPLE].readers, 1)

    def test_a_reader_who_asks_for_served_probes_stays_a_person(self):
        # A WordPress reader and an app that loads its settings: the probe
        # rows are bots, the pages stay people.
        lines = [line(at(9), "203.0.113.71", "/", SAFARI),
                 line(at(9), "203.0.113.71", "/wp-content/themes/a/style.css", SAFARI,
                      "https://example.com/"),
                 line(at(9, 1), "203.0.113.71", "/wp-json/wp/v2/posts", SAFARI,
                      "https://example.com/"),
                 line(at(9, 2), "203.0.113.72", "/app/", FIREFOX),
                 asset(at(9, 2), "203.0.113.72", FIREFOX, "/app/"),
                 line(at(9, 2), "203.0.113.72", "/config.json", FIREFOX,
                      "https://example.com/app/")]
        totals = count(lines, {"site": {"hosts": ["example.com"],
                                        "asset_prefixes": ["/_next/static/", "/wp-content/"]}})
        self.assertEqual(totals.groups[Group.PEOPLE].readers, 2)
        self.assertEqual(totals.groups[Group.BOTS].probes, 3)
        self.assertNotIn(SCANNER, totals.groups[Group.BOTS].agents)

    def test_names_and_ours_come_first(self):
        c = Classifier(our_agents=["OfficeBrowser"])
        c.scanners = {("198.51.100.8", GOOGLEBOT), ("198.51.100.9", "OfficeBrowser/1.0"),
                      (SCANNER_IP, CHROME)}

        def hit(address, agent, path="/"):
            return Hit(at(9), address, "example.com", "GET", path, "200", "", agent)
        # A crawler name proves nothing on its own (rule 2b): unchecked, the
        # scanning "Googlebot" is a scanner; proven Google's, it is Googlebot.
        got = c(hit("198.51.100.8", GOOGLEBOT))
        self.assertEqual((got.group, got.engine), (Group.BOTS, SCANNER))

        class Proven:
            def status(self, name, address, agent=""):
                return "verified"

            def hosting(self, address):
                return False
        c.verifier = Proven()
        self.assertIs(c(hit("198.51.100.8", GOOGLEBOT)).group, Group.SEARCH_ENGINE)
        c.verifier = None
        self.assertIs(c(hit("198.51.100.9", "OfficeBrowser/1.0")).group, Group.OURS)
        got = c(hit(SCANNER_IP, CHROME))
        self.assertEqual((got.group, got.engine, got.probe), (Group.BOTS, SCANNER, False))
        self.assertEqual(requests_feed.rule_of(hit(SCANNER_IP, CHROME), got, "page"),
                         "bot: scanner (asked for secret or config files)")
        probe = c(hit(SCANNER_IP, CHROME, "/main.tf"))
        self.assertEqual(requests_feed.rule_of(hit(SCANNER_IP, CHROME, "/main.tf"), probe,
                                               "other"), "bot: scanner probe")
        self.assertIs(c(hit(SCANNER_IP, SAFARI)).group, Group.PEOPLE)


class Streaming(Classifier):
    """The mutation: marks a scanner only from its first probe on, as a
    one-pass reader would. Everything it asked for before stays people."""

    def __call__(self, hit):
        got = super().__call__(hit)
        if got.probe and got.group is Group.BOTS:
            self.scanners = self.scanners | {(hit.address, hit.user_agent)}
        return got


class TestBothRoads(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.log(fixture()[0])

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

    def test_the_audit_catches_a_pre_probe_page_kept_as_people(self):
        with mock.patch("skald.window.Classifier", Streaming), \
                mock.patch.object(classify.Scanners, "__call__", lambda self, hit: None), \
                mock.patch.object(tool_visits.ProbeSweep, "__call__", lambda self, hit: None):
            # (The live scanner's twelve missing probes would make it a probe
            # sweep too, rule 6c: that pass is off in the mutation as well.)
            code, out, err = self.collect_and_audit()
        # The live scanner's / and the probe-last visitor's two pages came
        # before their probes: the mutation kept both visits as people.
        self.assertEqual(self.people()[2], 3)
        self.assertEqual(code, 1, out)
        self.assertIn("people: visits: history has 3, the recount finds 1", err)


class TestIndependence(unittest.TestCase):

    def test_the_audit_shares_only_the_name_lists(self):
        from skald import audit
        tree = ast.parse(Path(audit.__file__).read_text())
        names = {a.name for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom) and n.module == "classify" for a in n.names}
        self.assertNotIn("Scanners", names)
        self.assertNotIn("Classifier", names)
        self.assertIn("PROBE", names)
        self.assertIn("SECRET_PROBE", names)


NOON = datetime(2026, 10, 21, 12, tzinfo=UTC)


class TestLiveDoing(unittest.TestCase):
    """(c) The live "doing" list never shows a visitor whose requests include
    a probe, even when its page came first; the audit's live road agrees."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        m = lambda minutes: NOON - timedelta(minutes=minutes)  # noqa: E731
        lines = [line(m(4), SCANNER_IP, "/", CHROME, FORGED, country="HK")]
        lines += [line(m(3.9), SCANNER_IP, p, CHROME, FORGED, s, country="HK")
                  for p, s in LIVE_PROBES]
        lines += [line(m(6), "203.0.113.67", "/pricing/", FIREFOX, country="CA"),
                  line(m(2), "203.0.113.67", "/.env", FIREFOX, status=404, country="CA"),
                  line(m(5), SCANNER_IP, "/services/", SAFARI, country="HK")]
        self.box.log(sorted(lines))
        stamp = NOON.timestamp() - 60
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))

    def test_only_the_honest_visitor_is_doing_anything(self):
        code, _, err = self.box.run("--today", DAY.isoformat(), "live")
        self.assertEqual(code, 0, err)
        rt = json.loads((self.box.root / "live-example.com.json").read_text())["realtime"]
        self.assertEqual(rt["visits_today"], 1)
        self.assertEqual([v["trail"] for v in rt["doing"]], [["/services/"]])
        self.assertEqual(rt["page_views"], 1)
        code, out, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)


if __name__ == "__main__":
    unittest.main()
