"""tools/demo.py: the public demo dashboard (sample data, static files, no helper).

The traffic is seeded and fictional (RFC 5737 addresses, example.com); it goes
through the real pipeline; the output works from any path with no helper, and
the web app's demo mode never asks a helper address.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
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
            self.assertEqual(line.split()[2], "example.com")
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


class Build(unittest.TestCase):
    """One small build (4 days) through the real pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="skald-demo-test-")
        cls.out = Path(cls.tmp) / "site"
        demo.build(cls.out, NOW, days=4, say=lambda *_: None)
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
        self.assertEqual(set(d), {"people/left-out", "people/conversions?kind=cancelled",
                                  "people/conversions?kind=removed", "people/conversions?kind=test"})
        left = json.loads((self.site / d["people/left-out"]).read_text())
        self.assertTrue(left["ok"])
        self.assertIn("test", {r["why"] for r in left["leads"]})            # the team's own test lead
        for name in d.values():
            text = (self.site / name).read_text()
            self.assertFalse(json.loads(text)["private"], name)
            self.assertNotIn("@example.com", text, name)
            self.assertNotIn('"vid":"', text, name)

    def test_no_request_log_names_a_helper_to_poll(self):
        for path in self.out.rglob("data/requests.json"):
            self.assertNotIn("api", json.loads(path.read_text()))

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
