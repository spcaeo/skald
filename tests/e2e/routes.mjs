// Every older address (bookmarks, saved views, links in help, mails and
// insights) opens its new section and tab, with its parameters (2.7.0, the
// five sections; js/routes.js). For each one, in a real browser:
//   * the address bar ends on the new route, with the old one's parameters
//   * the menu marks the section and the strip selects the tab
//   * no console error, and Back does not land on the old address and loop
// Also: a bare section opens its first tab, and the strip's keyboard works
// (arrows and Home/End move the focus, Enter opens).
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/routes.mjs https://host/traffic/<site>/ [user:password]
//
// Works on the demo too: python3 tools/demo.py OUT, serve OUT, pass .../traffic/example.com/

const args = process.argv.slice(2);
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node routes.mjs <page url> [user:password]"); process.exit(2); }

// old address -> [new route, its parameters, section in the menu, tab selected]
const TABLE = [
  ["overview", "overview/summary", {}, "Overview", "Summary"],
  ["home", "overview/summary", {}, "Overview", "Summary"],
  // Live and Compare are global modes (js/modes.js): Live is Today on Overview, Compare opens its table's tab.
  // Today is the default period (2.10.1), so the address leaves range=today out.
  ["live", "overview/summary", {}, "Overview", "Summary"],
  ["insights?since=7d", "overview/insights", { since: "7d" }, "Overview", "Insights"],
  ["compare?cdim=pages&cgran=week", "traffic/pages", { cmp: "prev", cgran: "week" }, "Traffic", "Pages"],
  ["compare?ca=2026-09-01..2026-09-30&cb=2026-08-01..2026-08-31&cdim=countries", "traffic/places",
    { range: "custom", from: "2026-09-01", to: "2026-09-30", cmp: "custom", cb: "2026-08-01..2026-08-31" }, "Traffic", "Places & devices"],
  ["compare", "overview/summary", { cmp: "prev" }, "Overview", "Summary"],
  ["visitors", "traffic/visitors", {}, "Traffic", "Visitors"],
  ["visits", "traffic/visitors", {}, "Traffic", "Visitors"],
  ["sources?range=7d&country=US", "traffic/sources", { range: "7d", country: "US" }, "Traffic", "Sources"],
  ["pages?page=%2Fpricing%2F", "traffic/pages", { page: "/pricing/" }, "Traffic", "Pages"],
  ["locations", "traffic/places", {}, "Traffic", "Places & devices"],
  ["audience", "traffic/places", {}, "Traffic", "Places & devices"],
  ["time", "traffic/time", {}, "Traffic", "Time"],
  ["hours", "traffic/time", {}, "Traffic", "Time"],
  ["leads", "sales/pipeline", { lsrc: "db" }, "Leads & sales", "Pipeline"],
  ["conversions", "sales/pipeline", { lsrc: "all" }, "Leads & sales", "Pipeline"],
  ["funnels?fn=%2F%20%3E%20%2Fpricing%2F", "sales/funnels", { fn: "/ > /pricing/" }, "Leads & sales", "Funnels"],
  ["events", "sales/events", {}, "Leads & sales", "Events"],
  ["bots", "ai/assistants", {}, "AI & bots", "Assistants"],
  ["crawlers", "ai/assistants", {}, "AI & bots", "Assistants"],
  ["settings/crawlers", "ai/rules", {}, "AI & bots", "Crawler rules"],
  ["health", "site/health", {}, "Site", "Health"],
  ["health/alerts", "site/alerts", {}, "Site", "Alerts"],
  ["alerts", "site/alerts", {}, "Site", "Alerts"],
  ["requests?rq=people", "site/requests", { rq: "people" }, "Site", "Requests"],
  ["health/broken", "site/notfound", {}, "Site", "Not found"],
  ["broken", "site/notfound", {}, "Site", "Not found"],
  ["health/speed?strat=desktop", "site/speed", { strat: "desktop" }, "Site", "Speed"],
  ["speed", "site/speed", {}, "Site", "Speed"],
  ["health/quality", "site/quality", {}, "Site", "Data quality"],
  ["quality", "site/quality", {}, "Site", "Data quality"],
  ["sources?cmp=1", "traffic/sources", { cmp: "prev" }, "Traffic", "Sources"],
  ["traffic", "traffic/visitors", {}, "Traffic", "Visitors"],
  ["sales", "sales/pipeline", {}, "Leads & sales", "Pipeline"],
  ["ai", "ai/assistants", {}, "AI & bots", "Assistants"],
  ["site", "site/health", {}, "Site", "Health"],
  ["ours", "settings/internal", {}, null, null],
  ["guides", "help", {}, null, null],
];

const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };
const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
let where = "";
p.on("console", (m) => { if (m.type() === "error") fail(`${where}: console error ${m.text()}`); });
p.on("pageerror", (e) => fail(`${where}: ${e.message}`));
const state = () => p.evaluate(() => ({
  hash: location.hash,
  section: document.querySelector('.nav .tab[aria-current="page"] .tab-name')?.textContent.trim() || null,
  tab: document.querySelector('.stabs-list [role="tab"][aria-selected="true"] .stab-name')?.textContent.trim() || null,
}));
const split = (hash) => { const [route, q = ""] = hash.replace(/^#/, "").split("?"); return [route, Object.fromEntries(new URLSearchParams(q))]; };
const same = (a, b) => JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

let n = 0;
for (const [old, route, params, section, tab] of TABLE) {
  where = `#${old}`;
  // From a page of the app, as a click on an old link would: the old address is pushed, then replaced.
  await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
  await p.evaluate((h) => { location.hash = h; }, `#${old}`);
  await p.waitForTimeout(400);
  const got = await state();
  const [r, q] = split(got.hash);
  n++;
  if (r !== route || !same(q, params)) fail(`${where}: opened ${got.hash}, not #${route} ${JSON.stringify(params)}`);
  if (section && got.section !== section) fail(`${where}: the menu marks "${got.section}", not "${section}"`);
  if (tab && got.tab !== tab) fail(`${where}: the strip selects "${got.tab}", not "${tab}"`);
  // Back: to the page before, never to the old address (which would redirect again: a loop).
  await p.goBack();
  await p.waitForTimeout(300);
  const back = await state();
  if (!back.hash.startsWith("#overview/summary")) fail(`${where}: Back went to ${back.hash}, not to the page before`);
}

// A fresh load of an old bookmark: lands, and Back leaves the app's history (no loop).
where = "bookmark #sources";
const load = async (hash) => {
  const fresh = await ctx.newPage();
  fresh.on("pageerror", (e) => fail(`${where}: ${e.message}`));
  await fresh.goto(`${base}${hash}`, { waitUntil: "networkidle" });
  await fresh.waitForTimeout(300);
  const got = await fresh.evaluate(() => [location.hash, history.length]);
  await fresh.close();
  return got;
};
const [, plain] = await load("#traffic/sources?range=7d");
const [landed, entries] = await load("#sources?range=7d");
if (landed !== "#traffic/sources?range=7d") fail(`${where}: opened ${landed}`);
if (entries !== plain) fail(`${where}: ${entries} entries in a new tab's history, not ${plain} as for the new address`);

// The strip's keyboard: one tab stop; arrows, Home and End move; Enter opens and keeps the focus.
where = "tab strip keyboard";
await p.goto(`${base}#traffic/visitors`, { waitUntil: "networkidle" });
await p.focus('.stabs-list [role="tab"][aria-selected="true"]');
const focus = () => p.evaluate(() => [document.activeElement.textContent.trim(), location.hash.split("?")[0]]);
await p.keyboard.press("ArrowRight");
let f = await focus();
if (f[0] !== "Sources" || f[1] !== "#traffic/visitors") fail(`${where}: ArrowRight gave ${f}`);
await p.keyboard.press("End");
if ((await focus())[0] !== "Time") fail(`${where}: End did not reach the last tab`);
await p.keyboard.press("ArrowRight");
if ((await focus())[0] !== "Visitors") fail(`${where}: ArrowRight on the last tab did not wrap`);
await p.keyboard.press("ArrowRight");
await p.keyboard.press("Enter");
await p.waitForTimeout(400);
f = await focus();
if (f[0] !== "Sources" || f[1] !== "#traffic/sources") fail(`${where}: Enter gave ${f}`);
const stops = await p.evaluate(() => [...document.querySelectorAll('.stabs-list [role="tab"]')].filter((t) => t.tabIndex === 0).length);
if (stops !== 1) fail(`${where}: ${stops} tab stops in the strip, not one`);
const panel = await p.evaluate(() => { const t = document.querySelector('.stabs [aria-selected="true"]'); const pn = document.getElementById(t.getAttribute("aria-controls")); return pn?.getAttribute("role") === "tabpanel" && pn.getAttribute("aria-labelledby") === t.id; });
if (!panel) fail(`${where}: the tab panel is not labelled by the chosen tab`);

await b.close();
console.log(`${n} old addresses checked; ${fails.length ? `${fails.length} failed` : "all passed"}`);
process.exit(fails.length ? 1 : 0);
