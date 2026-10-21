"""The five sections' routes (2.7.0): every older address redirects, with its parameters.

js/routes.js holds the redirects; js/state.js applies them (read, set, emit) and keeps
each tab's own parameters (its `keep` list in js/tabs/s-*.js). These tests run both in
node, with the registry read from the s-*.js files, and check each row of the route
table in docs/plans/2026-10-12-ui-consolidation-map.md (section 5).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from urllib.parse import parse_qsl

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "skald" / "webapp" / "js"

# old address -> where it opens (route, parameters), as the map's table says.
TABLE = [
    ("overview", "overview/summary", {}),
    ("home", "overview/summary", {}),
    # Live and Compare are global modes (js/modes.js): Live is Today on Overview; the Compare
    # page opens the tab its table was on, A as the period, B as Compare's choice.
    # Today is the default period since 2.10.1, so the address no longer says it.
    ("live", "overview/summary", {}),
    ("live?range=7d&cmp=prev", "overview/summary", {}),
    ("insights?since=2026-10-01", "overview/insights", {"since": "2026-10-01"}),
    ("compare?ca=2026-09-01..2026-09-30&cb=2026-08-01..2026-08-31&cnorm=1&cgran=week&cm=views&cdim=pages",
     "traffic/pages", {"range": "custom", "from": "2026-09-01", "to": "2026-09-30", "cmp": "custom", "cb": "2026-08-01..2026-08-31",
                       "cnorm": "1", "cgran": "week", "cm": "views"}),
    ("compare", "overview/summary", {"cmp": "prev"}),
    ("compare?ca=2026-09-01..2026-09-30&cb=2026-08-02..2026-08-31&cdim=countries", "traffic/places",
     {"range": "custom", "from": "2026-09-01", "to": "2026-09-30", "cmp": "prev"}),
    ("compare?ca=2026-09-01..2026-09-30&cb=2025-09-02..2025-10-01&cdim=campaigns", "traffic/sources",
     {"range": "custom", "from": "2026-09-01", "to": "2026-09-30", "cmp": "year"}),
    ("compare?cdim=assistants", "traffic/sources", {"cmp": "prev"}),
    ("visitors", "traffic/visitors", {}),
    ("visits", "traffic/visitors", {}),
    ("sources", "traffic/sources", {}),
    ("pages?page=%2Fpricing%2F&pubfrom=2026-09-01&pubto=2026-09-30", "traffic/pages", {"page": "/pricing/", "pubfrom": "2026-09-01", "pubto": "2026-09-30"}),
    ("locations", "traffic/places", {}),
    ("audience", "traffic/places", {}),
    ("time", "traffic/time", {}),
    ("hours", "traffic/time", {}),
    ("leads", "sales/pipeline", {"lsrc": "db"}),
    ("conversions", "sales/pipeline", {"lsrc": "all"}),
    ("funnels?fn=%2F%3E%2Fpricing%2F&fsrc=Email&fstep=1&fmode=list", "sales/funnels", {"fn": "/>/pricing/", "fsrc": "Email", "fstep": "1", "fmode": "list"}),
    ("events", "sales/events", {}),
    ("bots", "ai/assistants", {}),
    ("crawlers", "ai/assistants", {}),
    ("settings/crawlers", "ai/rules", {}),
    ("health", "site/health", {}),
    ("health/alerts", "site/alerts", {}),
    ("alerts", "site/alerts", {}),
    ("requests?ip=203.0.113.9&rq=people", "site/requests", {"ip": "203.0.113.9", "rq": "people"}),
    ("health/broken", "site/notfound", {}),
    ("broken", "site/notfound", {}),
    ("health/speed?strat=desktop", "site/speed", {"strat": "desktop"}),
    ("speed", "site/speed", {}),
    ("health/quality", "site/quality", {}),
    ("quality", "site/quality", {}),
    # the old compare switch, on any route
    ("sources?cmp=1&range=7d", "traffic/sources", {"cmp": "prev", "range": "7d"}),
    ("overview/summary?cmp=1", "overview/summary", {"cmp": "prev"}),
    # the period, page group and filters ride along
    ("sources?range=custom&from=2026-09-01&to=2026-09-30&view=blog&country=CA&path=%2Fblog&pathmode=starts&tz=utc",
     "traffic/sources", {"range": "custom", "from": "2026-09-01", "to": "2026-09-30", "view": "blog", "country": "CA", "path": "/blog", "pathmode": "starts", "tz": "utc"}),
    ("requests?dd=country%3ACA", "site/requests", {"dd": "country:CA"}),
    # a bare section opens its first tab
    ("traffic", "traffic/visitors", {}),
    ("sales", "sales/pipeline", {}),
    ("ai", "ai/assistants", {}),
    ("site", "site/health", {}),
    # settings' short names, help's
    ("ours", "settings/internal", {}), ("internal", "settings/internal", {}), ("api", "settings/api", {}), ("tokens", "settings/api", {}),
    ("settings/tokens", "settings/api", {}), ("connections", "settings/api", {}), ("settings/connections", "settings/api", {}), ("team", "settings/team", {}), ("users", "settings/users", {}), ("account", "settings/account", {}),
    ("billing", "settings/billing", {}), ("security", "settings/security", {}), ("audit", "settings/audit", {}), ("mail", "settings/mail", {}), ("reports", "settings/reports", {}),
    ("retention", "settings/retention", {}), ("integrations", "settings/integrations", {}), ("sites", "settings/sites", {}),
    ("guides", "help", {}), ("docs", "help", {}), ("settings/help", "help", {}),
    # unchanged addresses stay as they are
    ("help?part=webhooks", "help", {"part": "webhooks"}),
    ("about?part=compare&note=x", "about", {"part": "compare", "note": "x"}),
    ("settings/internal", "settings/internal", {}),
    ("traffic/sources?range=7d", "traffic/sources", {"range": "7d"}),
]


def registry():
    """[{key, name, tabs: [{route, name, keep}]}] from js/sections.js and js/tabs/s-*.js."""
    sections = (JS / "sections.js").read_text(encoding="utf-8")
    files = dict(re.findall(r'import (\w+) from "\./tabs/(s-[a-z]+\.js)";', sections))
    out = []
    for key, name, var in re.findall(r'\{ key: "([a-z]+)", name: "([^"]+)",[^}]*?tabs: (\w+)', sections):
        text = (JS / "tabs" / files[var]).read_text(encoding="utf-8")
        tabs = []
        for line in re.findall(r'^  \["[a-z]+", .*$', text, re.M):
            tkey, tname = re.match(r'  \["([a-z]+)", "([^"]+)"', line).groups()
            keep = re.search(r"keep: \[([^\]]*)\]", line)
            tabs.append({"route": f"{key}/{tkey}", "name": tname, "keep": re.findall(r'"(\w+)"', keep.group(1)) if keep else []})
        out.append({"key": key, "name": name, "tabs": tabs})
    return out


def node_routes(table):
    """Each address through state.js: where it lands, what the address bar says after."""
    script = """
const reg = JSON.parse(process.argv[1]), table = JSON.parse(process.argv[2]);
const loc = { hash: "" };
globalThis.location = loc;
globalThis.history = { replaceState: (_, __, h) => { loc.hash = h; }, pushState: (_, __, h) => { loc.hash = h; } };
globalThis.addEventListener = () => {};
globalThis.localStorage = { getItem: () => null };
const S = await import(process.argv[3]);
S.addSections(reg);
let seen = null;
S.on((s) => { seen = s; });
const out = [];
for (const asked of table) {
  loc.hash = `#${asked}`;
  S.emit(true);
  out.push([loc.hash, seen.tab]);
}
// set() takes old routes and bare sections too
loc.hash = "#site/health?range=7d";
S.set({ tab: "conversions" });
out.push([loc.hash, null]);
S.set({ tab: "ai" });
out.push([loc.hash, null]);
console.log(JSON.stringify(out));
"""
    done = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(registry()), json.dumps(table), (JS / "state.js").as_uri()],
                          capture_output=True, text=True, timeout=60, cwd=JS)
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def split(h):
    route, _, q = h.lstrip("#").partition("?")
    return route, dict(parse_qsl(q))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Redirects(unittest.TestCase):
    def test_the_registry_is_read(self):
        reg = registry()
        self.assertEqual([s["key"] for s in reg], ["overview", "traffic", "sales", "ai", "site"])
        routes = {t["route"] for s in reg for t in s["tabs"]}
        for r in ("overview/summary", "overview/insights", "traffic/visitors", "traffic/sources", "traffic/pages", "traffic/places", "traffic/time",
                  "sales/pipeline", "sales/bookings", "sales/funnels", "sales/events", "sales/people",
                  "ai/assistants", "ai/crawlers", "ai/rules", "ai/llms",
                  "site/health", "site/alerts", "site/requests", "site/notfound", "site/speed", "site/quality"):
            self.assertIn(r, routes)

    def test_every_old_address_opens_its_new_tab_with_its_parameters(self):
        got = node_routes([asked for asked, _, _ in TABLE])
        for (asked, route, params), (hash_, tab) in zip(TABLE, got):
            with self.subTest(asked=asked):
                self.assertEqual(tab, route)
                self.assertEqual(split(hash_), (route, params))
        self.assertEqual(split(got[-2][0]), ("sales/pipeline", {"range": "7d", "lsrc": "all"}))
        self.assertEqual(split(got[-1][0]), ("ai/assistants", {"range": "7d"}))

    def test_compare_keys_ride_along_only_while_compare_is_on(self):
        """cb (a custom B), cnorm ("Per day") stay on every tab while Compare is on; a custom B
        without its dates is the previous period."""
        script = """
const loc = { hash: "" };
globalThis.location = loc;
globalThis.history = { replaceState: (_, __, h) => { loc.hash = h; }, pushState: (_, __, h) => { loc.hash = h; } };
globalThis.addEventListener = () => {};
globalThis.localStorage = { getItem: () => null };
const S = await import(process.argv[2]);
S.addSections(JSON.parse(process.argv[1]));
const out = [];
for (const h of ["#traffic/sources?cmp=year&cb=2026-08-01..2026-08-31&cnorm=1", "#traffic/sources?cmp=custom",
                 "#traffic/sources?cmp=custom&cb=2026-08-01..2026-08-31&cnorm=1", "#traffic/sources?cnorm=1&cb=2026-08-01..2026-08-31"]) {
  loc.hash = h;
  const s = S.read();
  out.push([s.cmp, S.hashFor(s), S.hashFor({ ...s, tab: "site/health" })]);
}
console.log(JSON.stringify(out));
"""
        done = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(registry()), (JS / "state.js").as_uri()],
                              capture_output=True, text=True, timeout=60, cwd=JS)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual(got[0], ["year", "#traffic/sources?cmp=year&cnorm=1", "#site/health?cmp=year&cnorm=1"])
        self.assertEqual(got[1][0:2], ["prev", "#traffic/sources?cmp=prev"])
        self.assertEqual(got[2][2], "#site/health?cmp=custom&cb=2026-08-01..2026-08-31&cnorm=1")
        self.assertEqual(got[3][1:], ["#traffic/sources", "#site/health"])

    def test_every_redirect_row_is_tested_and_lands_on_a_route(self):
        text = (JS / "routes.js").read_text(encoding="utf-8")
        body = text.split("export const REDIRECTS = {", 1)[1].split("\n};", 1)[0]
        rows = dict(re.findall(r'"?([a-z/]+)"?: \["([a-z/]+)"', body))
        self.assertGreaterEqual(len(rows), 48)
        asked = {a.split("?")[0] for a, _, _ in TABLE}
        self.assertEqual(sorted(set(rows) - asked), [], "a redirect without a test row")
        routes = {t["route"] for s in registry() for t in s["tabs"]}
        routes |= set(re.findall(r'\["([a-z/]+)", "[^"]+"\]', (JS / "state.js").read_text(encoding="utf-8")))
        for old, new in rows.items():
            self.assertIn(new, routes, f"{old} -> {new}")


if __name__ == "__main__":
    unittest.main()
