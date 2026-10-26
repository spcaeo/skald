"""tools/demo.py: the public demo dashboard (sample data, static files, no helper).

The traffic is seeded and fictional (RFC 5737 addresses, example.com); it goes
through the real pipeline; the output works from any path with no helper, and
the web app's demo mode never asks a helper address.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
APP_JS = ROOT / "skald" / "webapp" / "js"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


demo = load("demo")
dt = sys.modules["demo_traffic"]
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
DOCS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


class Traffic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = dt.generate(NOW, 12)

    def test_seeded_the_same_clock_gives_the_same_traffic(self):
        again = dt.generate(NOW, 12)
        self.assertEqual(self.t.lines, again.lines)
        self.assertEqual(self.t.beacon, again.beacon)
        self.assertEqual(self.t.hooks, again.hooks)
        self.assertEqual(self.t.leads, again.leads)
        self.assertNotEqual(self.t.lines, dt.generate(NOW, 12, seed=1).lines)

    def test_documentation_addresses_and_example_hosts_only(self):
        for line in self.t.lines:
            address = ipaddress.ip_address(line.split()[1])
            self.assertTrue(any(address in n for n in DOCS), line)
            self.assertIn(line.split()[2], ("example.com", "app.example.com", "192.0.2.10"))
        for _, address, _, _ in self.t.beacon:
            self.assertTrue(any(ipaddress.ip_address(address) in n for n in DOCS))
        mails = {m.lower() for line in self.t.lines for m in re.findall(r"[\w.-]+@[\w.-]+\.\w+", line)}
        self.assertLessEqual(mails, {"claude-user@anthropic.com", "spider-feedback@bytedance.com"})

    def test_nothing_after_the_clock_and_every_day_has_traffic(self):
        self.assertTrue(all(line.split()[0] <= NOW.isoformat() for line in self.t.lines))
        days = {datetime.fromisoformat(line.split()[0]).astimezone(dt.ZoneInfo(dt.TZ_NAME)).date() for line in self.t.lines}
        self.assertEqual(days, {self.t.first + timedelta(days=i) for i in range(13)})

    def test_every_kind_of_visitor_is_there(self):
        text = "".join(self.t.lines)
        for token in ("GPTBot", "ChatGPT-User", "ClaudeBot", "Perplexity-User", "Googlebot", "bingbot",
                      "/.env", '"https://chatgpt.com/"', "utm_campaign=fall-launch", f" {dt.OFFICE} "):
            self.assertIn(token, text, token)
        self.assertTrue(self.t.leads and self.t.hooks and self.t.beacon)

    def test_a_user_fetch_then_a_direct_visit_to_that_page(self):
        """The road the "likely sent by an AI assistant" figure stands on."""
        rows = [line.split('"') for line in self.t.lines]
        fetches = [(datetime.fromisoformat(r[0].split()[0]), r[1].split()[1]) for r in rows if "-User/1.0" in r[5]]
        visits = [(datetime.fromisoformat(r[0].split()[0]), r[1].split()[1]) for r in rows
                  if r[3] == "-" and r[5].startswith("Mozilla/5.0 (") and "bot" not in r[5].lower()]
        followed = [f for f in fetches if any(p == f[1] and timedelta(0) < t - f[0] <= timedelta(minutes=15)
                                              for t, p in visits)]
        self.assertGreaterEqual(len(followed), 5)

    def test_the_html_sitemap_page_is_walked_by_crawlers_and_test_browsers(self):
        """2.36: /sitemap/ is not a page; the demo has it so Data quality's "Not counted as
        pages" shows it. Its own generator: the other lines are the same as without it."""
        rows = [line.split('"') for line in self.t.lines if '"GET /sitemap/ ' in line]
        agents = {r[5] for r in rows}
        self.assertTrue(any("Googlebot" in a for a in agents) and any("bingbot" in a for a in agents))
        self.assertTrue(any(a in dt.HUMAN for a in agents))
        self.assertTrue({line.split()[1] for line in self.t.lines if line.split()[1] in dt.TEST_BROWSERS})
        rest = [line for line in self.t.lines if line.split()[1] not in dt.TEST_BROWSERS + ("198.51.100.245",)
                and '"GET /sitemap/ ' not in line]
        bare = dt.html_sitemap
        try:
            dt.html_sitemap = lambda *a, **k: None
            self.assertEqual(rest, dt.generate(NOW, 12).lines)
        finally:
            dt.html_sitemap = bare


class Build(unittest.TestCase):
    """One small build (4 days) through the real pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="skald-demo-test-")
        cls.out = Path(cls.tmp) / "site"
        cls.keep = Path(cls.tmp) / "install"
        demo.build(cls.out, NOW, days=4, keep=cls.keep, say=lambda *_: None)
        cls.site = cls.out / "traffic" / "example.com"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_static_folder_that_works_from_any_path(self):
        index = (self.out / "index.html").read_text()
        self.assertIn('content="0;url=traffic/example.com/"', index)
        self.assertNotRegex(index, r'(?:href|src|url)=["/]*/')            # relative only
        shell = (self.site / "index.html").read_text()
        self.assertIn('src="../_app/js/main.js', shell)
        self.assertTrue((self.out / "traffic" / "_app" / "js" / "demo.js").is_file())
        self.assertTrue((self.out / ".nojekyll").is_file())
        build = json.loads((self.out / "traffic" / "build.json").read_text())
        self.assertEqual(build["name"], (ROOT / "NAME").read_text().strip())
        self.assertEqual(build["version"], (ROOT / "VERSION").read_text().strip())

    def test_the_html_sitemap_page_is_counted_in_data_quality_not_in_pages(self):
        quality = json.loads((self.site / "data" / "quality.json").read_text())
        found = [d["not_pages"]["sitemap_page"] for d in quality["days"] if (d.get("not_pages") or {}).get("sitemap_page")]
        self.assertTrue(found)
        self.assertNotIn('"/sitemap/"', (self.site / "data" / "pages.json").read_text())

    def test_ai_answers_made_up_and_recounted_and_no_key_kept(self):
        # demo_answers.py: runs through answers/run.py with a stand-in for the providers,
        # every run recounted by the second road; the made-up keys never leave the build.
        got = json.loads((self.site / "data" / "ai_answers.json").read_text())
        self.assertEqual(got["state"], "ok")
        self.assertEqual([p["name"] for p in got["profiles"]], ["New York", "London", "Montréal"])
        self.assertTrue(got["trend"])
        self.assertFalse(any(t["withheld"] for t in got["trend"]))
        self.assertTrue(got["last"])
        self.assertTrue(all(p["key"] for p in got["providers"]))
        for var in sys.modules["demo_answers"].KEYS:
            self.assertNotEqual(os.environ.get(var), "demo-made-up-key")
        leaked = [p for p in self.out.rglob("*") if p.is_file() and b"demo-made-up-key" in p.read_bytes()]
        self.assertEqual(leaked, [])
        text = json.dumps(got)
        self.assertNotRegex(text, r"https?://(?!(?:[a-z0-9-]+\.)*example\.(?:com|org|net)/)[^\s\"]+")

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_visitor_flow_reconciles_with_the_visit_tables(self):
        """js/flow.js on the built page: its columns are Where visits started, Common
        next steps (less reloads) and Where visits ended, and every drawn flow adds up."""
        done = subprocess.run(["node", str(ROOT / "tests" / "js" / "flow.mjs"), str(self.site / "data" / "app.json")],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("reconcile with the tables", done.stdout)
        self.assertIn("flow: all passed", done.stdout)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_new_and_returning_and_engagement_reconcile(self):
        """Traffic > Visitors' cards (js/visitorfigs.js) on the built page: every
        verified day's new and returning visits and both histograms add up to its
        readers, today's live figures too."""
        done = subprocess.run(["node", str(ROOT / "tests" / "js" / "visitorfigs.mjs"), str(self.site / "data" / "app.json"),
                               str(self.site / "data" / "overview.json")], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("visitorfigs: all passed", done.stdout)
        live = json.loads((self.site / "data" / "app.json").read_text())["live"]["figures"]
        self.assertEqual(live["returning"]["readers"], live["readers"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_palette_finds_every_page_and_insights_lose_nothing(self):
        """js/finder.js finds every page the demo's last 30 days list ("pricing" finds
        /pricing/); js/insight-rank.js folds the demo's insights one card per subject
        and shows every finding (2.13)."""
        for script, data, says in (("finder.mjs", "app.json", "finder: all passed"),
                                   ("insights.mjs", "insights.json", "insights: all passed")):
            done = subprocess.run(["node", str(ROOT / "tests" / "js" / script), str(self.site / "data" / data)],
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn(says, done.stdout)

    def test_every_app_json_says_demo_with_its_answers(self):
        apps = sorted(self.out.rglob("data/app.json"))
        self.assertEqual(len(apps), 2)                                     # the site and its Blog view
        for path in apps:
            app = json.loads(path.read_text())
            self.assertTrue(app["canRefresh"])
            d = app["demo"]
            self.assertTrue(d["links"] and all(link["url"].startswith("https://") for link in d["links"]))
            self.assertIn("#quick-start-in-60-seconds", d["links"][0]["url"])
        d = json.loads((self.site / "data" / "app.json").read_text())["demo"]
        anchor = date.fromisoformat(json.loads((self.site / "data" / "app.json").read_text())["anchor"])
        default = f"{anchor - timedelta(days=29)}..{anchor}|{anchor - timedelta(days=59)}..{anchor - timedelta(days=30)}"
        self.assertIn(default, d["api"]["compare"])                      # what Compare opens on
        for name in [*d["api"]["compare"].values(), *d["api"]["page"].values()]:
            self.assertTrue(json.loads((self.site / name).read_text())["ok"], name)
        index = json.loads((self.site / "data" / "page_index.json").read_text())
        self.assertEqual(set(d["api"]["page"]), {p["path"] for p in index["pages"]})

    def test_the_left_out_lists_are_files_without_emails_or_visitor_ids(self):
        d = json.loads((self.site / "data" / "app.json").read_text())["demo"]["api"]["people"]
        timelines = {k: v for k, v in d.items() if k.startswith("people/visitor?")}
        d = {k: v for k, v in d.items() if k not in timelines}
        self.assertEqual(set(d), {"people/left-out", "people/conversions?kind=cancelled",
                                  "people/conversions?kind=removed", "people/conversions?kind=test",
                                  "people/leads", "people/security"})
        # Security's addresses (2.21): documentation addresses only, as an owner sees them.
        sec = json.loads((self.site / d.pop("people/security")).read_text())
        self.assertTrue(sec["ok"] and sec["rows"])
        self.assertEqual(sec["mode"], "full")
        for row in sec["rows"]:
            self.assertTrue(any(ipaddress.ip_address(row["ip"]) in n for n in DOCS), row["ip"])
        leads = json.loads((self.site / d.pop("people/leads")).read_text())
        self.assertTrue(leads["ok"] and leads["rows"])
        self.assertFalse(leads["names"], "the demo shows the leads as a viewer sees them")
        self.assertNotIn("@", json.dumps(leads))
        # 2.12.0: the visitor drawer's timelines, labels and times only
        self.assertTrue(timelines)
        for name in timelines.values():
            text = (self.site / name).read_text()
            self.assertTrue(json.loads(text)["found"], name)
            for word in ("192.0.2.", "198.51.100.", "203.0.113.", "@", '"vid":"', "skv_"):
                self.assertNotIn(word, text, name)
        left = json.loads((self.site / d["people/left-out"]).read_text())
        self.assertTrue(left["ok"])
        self.assertIn("test", {r["why"] for r in left["leads"]})            # the team's own test lead
        for name in d.values():
            text = (self.site / name).read_text()
            self.assertFalse(json.loads(text)["private"], name)
            self.assertNotIn("@example.com", text, name)
            self.assertNotIn('"vid":"', text, name)

    def test_the_kept_install_audits_every_day_with_its_own_visitor_key(self):
        """--keep DIR: `skald --config DIR/config.yml audit --day D` recounts each
        stored day, the visitor hashes too: the install names its demo key in
        report.env_file, as a real install's helper finds its key."""
        from unittest import mock
        from skald.config import load_config
        from skald.visitors import load_key
        cfgp = self.keep / "config.yml"
        today = NOW.astimezone(dt.ZoneInfo(dt.TZ_NAME)).date()
        with mock.patch.dict("os.environ"):
            os.environ.pop(demo.KEY_VAR, None)
            self.assertEqual(load_key(load_config(cfgp)), demo.DEMO_KEY.encode())
            for k in range(1, 5):
                day = (today - timedelta(days=k)).isoformat()
                code, err = demo.run(cfgp, "--today", today.isoformat(), "audit", "--day", day)
                self.assertEqual(code, 0, f"{day}: {err}")

    def test_no_request_log_names_a_helper_to_poll(self):
        for path in self.out.rglob("data/requests.json"):
            self.assertNotIn("api", json.loads(path.read_text()))

    def test_connections_and_the_setup_list_come_from_files(self):
        """Settings > Connections in the demo: the set-up list's two answers and made-up tokens,
        worked out from the demo's install, naming no folder of the machine that built it."""
        setup = json.loads((self.site / "data" / "app.json").read_text())["demo"]["api"]["setup"]
        self.assertEqual(set(setup), {"settings", "integrations", "tokens"})
        got = {k: json.loads((self.site / v).read_text()) for k, v in setup.items()}
        self.assertTrue(all(g["ok"] for g in got.values()))
        self.assertEqual(got["settings"]["settings"]["privacy.keep_ips"]["source"], "config")
        ids = {s["id"] for s in got["integrations"]["status"]}
        self.assertTrue({"logs", "receiver", "script", "leads"} <= ids, ids)
        text = json.dumps(got)
        self.assertNotIn(str(self.keep), text)
        self.assertNotIn(self.tmp, text)
        self.assertTrue(all("token" not in t or not t["token"] for t in got["tokens"]["tokens"]))

    def test_search_console_and_bing_are_synced_by_the_real_sync(self):
        """Traffic > Search in the demo: both engines connected, days stored by the sync
        (folded, written and read back), the newest one provisional."""
        search = json.loads((self.site / "data" / "search.json").read_text())
        for engine in ("google", "bing"):
            part = search["engines"][engine]
            self.assertTrue(part["connected"], engine)
            self.assertTrue(part["days"], engine)
        days = search["engines"]["google"]["days"]
        self.assertFalse(days[-1]["final"])
        self.assertTrue(all(d["final"] for d in days[:-1]))

    def test_only_documentation_addresses_reach_the_page(self):
        for path in self.out.rglob("*.json"):
            for found in re.findall(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", path.read_text()):
                try:
                    address = ipaddress.ip_address(found)
                except ValueError:
                    continue
                self.assertTrue(any(address in n for n in DOCS), f"{path.name}: {found}")

    def test_a_folder_it_did_not_write_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "keep.txt").write_text("mine")
            with self.assertRaises(SystemExit):
                demo.prepare(Path(tmp))
            self.assertTrue((Path(tmp) / "keep.txt").exists())
        with self.assertRaises(SystemExit):
            demo.prepare(ROOT)


class ComparePresets(unittest.TestCase):
    def test_the_app_s_presets_and_their_b_periods(self):
        got = demo.compare_ranges(date(2026, 10, 11))
        a_list = [a for a, _ in got]
        for a in [(date(2026, 10, 5), date(2026, 10, 11)), (date(2026, 9, 12), date(2026, 10, 11)),
                  (date(2026, 7, 14), date(2026, 10, 11)), (date(2026, 10, 1), date(2026, 10, 11)),
                  (date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 7, 1), date(2026, 9, 30)),
                  (date(2026, 4, 12), date(2026, 10, 11))]:
            self.assertIn(a, a_list)
        self.assertIn(((date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 8, 2), date(2026, 8, 31))), got)
        self.assertIn(((date(2026, 9, 12), date(2026, 10, 11)), (date(2025, 9, 13), date(2025, 10, 12))), got)
        self.assertEqual(len(got), len(set(got)))
        jan = demo.compare_ranges(date(2027, 1, 15))
        self.assertIn(((date(2026, 12, 1), date(2026, 12, 31)), (date(2026, 10, 31), date(2026, 11, 30))), jan)
        self.assertIn((date(2026, 10, 1), date(2026, 12, 31)), [a for a, _ in jan])     # last quarter


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class DemoMode(unittest.TestCase):
    """webapp/js/demo.js: the map from a helper address to the demo's file."""

    def node(self, script: str) -> str:
        done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                              timeout=60, cwd=APP_JS)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def test_answers_come_from_files_or_not_at_all(self):
        url = (APP_JS / "demo.js").as_uri()
        out = self.node(f"""
const d = await import({json.dumps(url)});
const before = [d.DEMO.on, d.demoFile("api/page?path=%2F")];
d.setDemo({{links: [{{text: "Q", url: "https://example.com/q"}}, {{text: "x", url: "javascript:void 0"}}],
  api: {{compare: {{"2026-09-12..2026-10-11|2026-08-13..2026-09-11": "data/demo/c.json"}}, page: {{"/pricing/": "data/demo/p.json"}}}}}});
console.log(JSON.stringify([...before, d.DEMO.on, d.DEMO.links.length,
  d.demoFile("api/compare?a=2026-09-12..2026-10-11&b=2026-08-13..2026-09-11"),
  d.demoFile("api/compare?a=2026-09-12..2026-10-11&b=2026-08-13..2026-09-11&country=US"),
  d.demoFile("api/page?path=%2Fpricing%2F"), d.demoFile("api/page?path=%2Fnope%2F"), d.demoFile("me")]));
""")
        self.assertEqual(json.loads(out), [False, None, True, 1, "data/demo/c.json", None, "data/demo/p.json", None, None])

    def test_a_left_out_list_is_read_from_its_file_and_nothing_is_posted(self):
        url = (APP_JS / "demo.js").as_uri()
        out = self.node(f"""
const d = await import({json.dumps(url)});
const asked = [];
globalThis.fetch = async (f) => {{ asked.push(f); return {{ json: async () => ({{ ok: true, leads: [] }}) }}; }};
d.setDemo({{api: {{people: {{"people/left-out": "data/demo/left-out.json"}}}}}});
const got = await d.demoAnswer("people/left-out");
const post = await d.demoAnswer("people/left-out", {{x: 1}});
const other = await d.demoAnswer("people?q=203.0.113.9");
console.log(JSON.stringify([got.ok, post.ok, post.demo, other.ok, asked]));
""")
        self.assertEqual(json.loads(out), [True, False, True, False, ["data/demo/left-out.json"]])

    def test_the_helper_is_never_asked_in_the_demo(self):
        """call() (every save and helper read) and getJSON's api/ addresses stop before fetch."""
        call = (APP_JS / "tabs" / "ipmanager.js").read_text()
        body = call.split("export async function call(path, body) {", 1)[1]
        self.assertLess(body.index("if (DEMO.on) return"), body.index("fetch("))
        data = (APP_JS / "data.js").read_text()
        get = data.split("export async function getJSON(url, fresh) {", 1)[1]
        self.assertLess(get.index("DEMO.on"), get.index("fetch("))
        ref = data.split("export async function refresh(m) {", 1)[1]
        self.assertLess(ref.index("if (DEMO.on) return"), ref.index("fetch("))
        self.assertIn("DEMO.on && S.inSettings(s.tab) ? demoState(name)", (APP_JS / "main.js").read_text())


if __name__ == "__main__":
    unittest.main()
