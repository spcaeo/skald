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

TOKEN = object()   # stands for "~" and 10 letters or digits: an address made opaque (2.21)

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
    # Compare is on by default for a period of whole days (2.42, state.js defaultCmp): the
    # previous period is that default, so the address leaves it out.
    ("compare?ca=2026-09-01..2026-09-30&cb=2026-08-02..2026-08-31&cdim=countries", "traffic/places",
     {"range": "custom", "from": "2026-09-01", "to": "2026-09-30"}),
    ("compare?ca=2026-09-01..2026-09-30&cb=2025-09-02..2025-10-01&cdim=campaigns", "traffic/sources",
     {"range": "custom", "from": "2026-09-01", "to": "2026-09-30", "cmp": "year"}),
    ("compare?cdim=assistants", "traffic/sources", {"cmp": "prev"}),
    ("visitors", "traffic/visitors", {}),
    ("visits", "traffic/visitors", {}),
    ("sources", "traffic/sources", {}),
    ("pages?page=%2Fpricing%2F&pubfrom=2026-09-01&pubto=2026-09-30", "traffic/pages", {"page": "/pricing/", "pubfrom": "2026-09-01", "pubto": "2026-09-30"}),
    ("traffic/pages?chgfrom=2026-10-13", "traffic/pages", {"chgfrom": "2026-10-13"}),
    ("locations", "traffic/places", {}),
    ("audience", "traffic/places", {}),
    ("time", "traffic/time", {}),
    ("hours", "traffic/time", {}),
    ("leads", "sales/summary", {"lsrc": "db"}),
    ("conversions", "sales/summary", {"lsrc": "all"}),
    # 2.20: Pipeline is Summary now (Leads lists the leads); its options ride along
    ("sales/pipeline", "sales/summary", {}),
    ("sales/pipeline?lsrc=all&lact=demo&llabel=sales", "sales/summary", {"lsrc": "all", "lact": "demo", "llabel": "sales"}),
    ("sales/bookings?bact=demo", "sales/bookings", {"bact": "demo"}),
    ("funnels?fn=%2F%3E%2Fpricing%2F&fsrc=Email&fstep=1&fmode=list", "sales/funnels", {"fn": "/>/pricing/", "fsrc": "Email", "fstep": "1", "fmode": "list"}),
    ("events", "sales/events", {}),
    ("bots", "ai/assistants", {}),
    ("crawlers", "ai/assistants", {}),
    ("settings/crawlers", "ai/rules", {}),
    ("health", "site/health", {}),
    ("health/alerts", "site/alerts", {}),
    ("alerts", "site/alerts", {}),
    # An address never stays in the address: the new one holds a token (js/routemask.js).
    ("requests?ip=203.0.113.9&rq=people", "site/requests", {"ip": TOKEN, "rq": "people"}),
    ("health/broken", "site/notfound", {}),
    ("broken", "site/notfound", {}),
    ("health/speed?strat=desktop", "site/speed", {"strat": "desktop"}),
    ("speed", "site/speed", {}),
    ("health/quality", "site/quality", {}),
    ("quality", "site/quality", {}),
    # the old compare switch, on any route
    ("sources?cmp=1&range=7d", "traffic/sources", {"range": "7d"}),
    ("overview/summary?cmp=1", "overview/summary", {"cmp": "prev"}),
    # the period, page group and filters ride along
    ("sources?range=custom&from=2026-09-01&to=2026-09-30&view=blog&country=CA&path=%2Fblog&pathmode=starts&tz=utc",
     "traffic/sources", {"range": "custom", "from": "2026-09-01", "to": "2026-09-30", "view": "blog", "country": "CA", "path": "/blog", "pathmode": "starts", "tz": "utc"}),
    ("requests?dd=country%3ACA", "site/requests", {"dd": "country:CA"}),
    # a bare section opens its first tab
    ("traffic", "traffic/visitors", {}),
    ("sales", "sales/leads", {}),
    ("ai", "ai/assistants", {}),
    ("site", "site/health", {}),
    # settings' pages before v2 and their short names (js/settings-menu.js OLD_SETTINGS), help's
    ("ours", "settings/site/details", {"sub": "internal"}), ("internal", "settings/site/details", {"sub": "internal"}),
    ("settings/internal", "settings/site/details", {"sub": "internal"}),
    ("tokens", "settings/ai/assistants", {"sub": "tokens"}), ("settings/tokens", "settings/ai/assistants", {"sub": "tokens"}),
    ("mcp", "settings/ai/assistants", {}), ("settings/mcp", "settings/ai/assistants", {}),
    ("team", "settings/org/people", {}), ("settings/team", "settings/org/people", {}),
    ("users", "settings/org/people", {}), ("settings/users", "settings/org/people", {}),
    ("account", "settings/you/account", {}), ("settings/account", "settings/you/account", {}),
    ("billing", "settings/org/billing", {}), ("settings/billing", "settings/org/billing", {}),
    ("security", "settings/org/people", {"sub": "security"}), ("settings/security", "settings/org/people", {"sub": "security"}),
    ("audit", "settings/org/audit", {}), ("settings/audit", "settings/org/audit", {}),
    ("mail", "settings/site/mail", {}), ("settings/mail", "settings/site/mail", {}),
    ("reports", "settings/site/mail", {"sub": "reports"}), ("settings/reports", "settings/site/mail", {"sub": "reports"}),
    ("retention", "settings/site/privacy", {}), ("settings/retention", "settings/site/privacy", {}), ("settings/privacy", "settings/site/privacy", {}),
    ("integrations", "settings/site/leads", {}), ("settings/integrations", "settings/site/leads", {}),
    ("sites", "settings/site/details", {}), ("settings/sites", "settings/site/details", {}),
    ("settings/aianswers", "settings/ai/answers", {}),
    ("settings/sitesadmin?setup=new&step=2", "settings/org/sites", {"setup": "new", "step": "2"}),
    # 2.40's pages (the card page, the checklist page, the split AI and people pages), with their parameters
    ("settings/home", "settings/todo", {}), ("settings/site/setup?setup=finish&by=agent", "settings/todo", {"setup": "finish", "by": "agent"}),
    ("settings/site/collect?sub=script", "settings/site/data", {"sub": "script"}),
    ("settings/site/internal", "settings/site/details", {"sub": "internal"}),
    ("settings/site/aianswers?sub=keys", "settings/ai/answers", {"sub": "keys"}),
    ("settings/ai/mcp?conn=mcp&step=2", "settings/ai/assistants", {"conn": "mcp", "step": "2"}),
    ("settings/ai/api", "settings/ai/assistants", {"sub": "api"}), ("settings/ai/tokens", "settings/ai/assistants", {"sub": "tokens"}),
    ("settings/org/team", "settings/org/people", {}), ("settings/org/users", "settings/org/people", {}),
    ("settings/org/security", "settings/org/people", {"sub": "security"}),
    ("settings/help", "help", {}),
    # Leads & tools had tabs until v2: Search Console and the outgoing webhooks open in their drawer
    ("settings/site/leads?sub=search", "settings/site/leads", {"tool": "search"}),
    ("settings/site/leads?sub=webhooks", "settings/site/leads", {"tool": "webhooks"}),
    ("settings/site/leads?sub=hooks", "settings/site/leads", {}),
    ("settings/site/leads?tool=calendly", "settings/site/leads", {"tool": "calendly"}),
    # the old Connections page opens where its dialog lives now, the dialog's keys kept
    ("api", "settings/todo", {}), ("connections", "settings/todo", {}), ("settings/connections", "settings/todo", {}),
    ("settings/api", "settings/todo", {}),
    ("settings/api?conn=mcp&step=2&agent=hand", "settings/ai/assistants", {"conn": "mcp", "step": "2", "agent": "hand"}),
    ("settings/api?conn=api&step=2", "settings/ai/assistants", {"conn": "api", "step": "2", "sub": "api"}),
    ("settings/api?conn=send&step=3", "settings/site/data", {"conn": "send", "step": "3"}),
    ("settings/api?setup=example.com&step=3&agent=codex", "settings/todo", {"setup": "example.com", "step": "3", "agent": "codex"}),
    ("guides", "help", {}), ("docs", "help", {}),
    # unchanged addresses stay as they are
    ("help?part=webhooks", "help", {"part": "webhooks"}),
    ("about?part=compare&note=x", "about", {"part": "compare", "note": "x"}),
    ("settings/todo?setup=finish-logs&by=me", "settings/todo", {"setup": "finish-logs", "by": "me"}),
    ("settings/site/data?sub=sample", "settings/site/data", {"sub": "sample"}),
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
        self.assertEqual([s["key"] for s in reg], ["overview", "traffic", "sales", "ai", "threats", "site"])
        routes = {t["route"] for s in reg for t in s["tabs"]}
        for r in ("overview/summary", "overview/insights", "traffic/visitors", "traffic/sources", "traffic/pages", "traffic/places", "traffic/time",
                  "sales/leads", "sales/summary", "sales/sources", "sales/bookings", "sales/funnels", "sales/events", "sales/people",
                  "ai/assistants", "ai/crawlers", "ai/rules", "ai/llms",
                  "site/health", "site/alerts", "site/requests", "site/notfound", "site/speed", "site/quality"):
            self.assertIn(r, routes)

    def test_every_old_address_opens_its_new_tab_with_its_parameters(self):
        got = node_routes([asked for asked, _, _ in TABLE])
        for (asked, route, params), (hash_, tab) in zip(TABLE, got):
            with self.subTest(asked=asked):
                self.assertEqual(tab, route)
                got_route, got_params = split(hash_)
                if params.get("ip") is TOKEN:
                    self.assertRegex(got_params.pop("ip", ""), r"^~[a-z0-9]{10}$", "an address is a token")
                    params = {k: v for k, v in params.items() if k != "ip"}
                self.assertEqual((got_route, got_params), (route, params))
        self.assertEqual(split(got[-2][0]), ("sales/summary", {"range": "7d", "lsrc": "all"}))
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

    def test_compare_is_on_by_default_for_whole_days(self):
        """2.42 (the UX audit's task 5): a period of whole days is compared with the one before
        unless the address says otherwise; that default is never written; cmp=off turns it off
        and stays; Today, All time and Include today are never compared by default."""
        script = """
const loc = { hash: "" };
globalThis.location = loc;
globalThis.history = { replaceState: (_, __, h) => { loc.hash = h; }, pushState: (_, __, h) => { loc.hash = h; } };
globalThis.addEventListener = () => {};
globalThis.localStorage = { getItem: () => null };
const S = await import(process.argv[2]);
S.addSections(JSON.parse(process.argv[1]));
const out = {};
const at = (h) => { loc.hash = h; return S.read(); };
for (const h of ["#traffic/sources?range=7d", "#traffic/sources?range=7d&cmp=off", "#traffic/sources?range=7d&cmp=year",
                 "#traffic/sources", "#traffic/sources?range=all", "#overview/summary?range=7d&inc=1"]) {
  const s = at(h);
  out[h] = [s.cmp, S.hashFor(s)];
}
// Turned off on 7 days, then a move to 30 days keeps it off; Today and back brings the default.
at("#traffic/sources?range=7d");
S.set({ cmp: "" });
out.off = loc.hash;
S.set({ range: "30d" });
out.off30 = [S.read().cmp, loc.hash];
at("#traffic/sources?range=7d");
S.set({ range: "today", cmp: "" });
out.today = [S.read().cmp, loc.hash];
S.set({ range: "7d" });
out.back = [S.read().cmp, loc.hash];
console.log(JSON.stringify(out));
"""
        done = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(registry()), (JS / "state.js").as_uri()],
                              capture_output=True, text=True, timeout=60, cwd=JS)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual(got["#traffic/sources?range=7d"], ["prev", "#traffic/sources?range=7d"])
        self.assertEqual(got["#traffic/sources?range=7d&cmp=off"], ["", "#traffic/sources?range=7d&cmp=off"])
        self.assertEqual(got["#traffic/sources?range=7d&cmp=year"], ["year", "#traffic/sources?range=7d&cmp=year"])
        self.assertEqual(got["#traffic/sources"], ["", "#traffic/sources"])
        self.assertEqual(got["#traffic/sources?range=all"], ["", "#traffic/sources?range=all"])
        self.assertEqual(got["#overview/summary?range=7d&inc=1"], ["", "#overview/summary?range=7d&inc=1"])
        self.assertEqual(got["off"], "#traffic/sources?range=7d&cmp=off")
        self.assertEqual(got["off30"], ["", "#traffic/sources?range=30d&cmp=off"])
        self.assertEqual(got["today"], ["", "#traffic/sources"])
        self.assertEqual(got["back"], ["prev", "#traffic/sources?range=7d"])

    def test_every_redirect_row_is_tested_and_lands_on_a_route(self):
        text = (JS / "routes.js").read_text(encoding="utf-8")
        body = text.split("export const REDIRECTS = {", 1)[1].split("\n};", 1)[0]
        menu = (JS / "settings-menu.js").read_text(encoding="utf-8")
        body += menu.split("export const OLD_SETTINGS = {", 1)[1].split("\n};", 1)[0]
        rows = dict(re.findall(r'"?([a-z/]+)"?: \["([a-z/]+)"', body))
        self.assertGreaterEqual(len(rows), 48)
        asked = {a.split("?")[0] for a, _, _ in TABLE}
        self.assertEqual(sorted(set(rows) - asked), [], "a redirect without a test row")
        routes = {t["route"] for s in registry() for t in s["tabs"]}
        routes |= set(re.findall(r'\["([a-z/]+)", "[^"]+"\]', (JS / "state.js").read_text(encoding="utf-8")))
        routes |= set(re.findall(r'route: "(settings/[a-z/]+)"', menu)) | {"help"}
        for old, new in rows.items():
            self.assertIn(new, routes, f"{old} -> {new}")


if __name__ == "__main__":
    unittest.main()
