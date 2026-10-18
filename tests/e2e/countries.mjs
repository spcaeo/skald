// Countries are shown as the flag and the ISO alpha-3 code ("🇨🇦 CAN", owner
// 2026-10-18), everywhere: the full name only in a tooltip, an aria-label, the
// text a screen reader reads (.vh) and the CSV. In a real browser, on pages with a
// country drill-down, a country filter and the drawers, no full country name is
// drawn as visible text. A tooltip or the palette may say both ("CAN · Canada").
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/countries.mjs https://host/traffic/<site>/ [user:password]
//
// Works on the demo too: python3 tools/demo.py OUT, serve OUT, pass .../traffic/example.com/

const args = process.argv.slice(2);
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node countries.mjs <page url> [user:password]"); process.exit(2); }

// The names a demo or a real site shows most; each must never be visible text.
const NAMES = ["Canada", "United States", "United Kingdom", "Germany", "Netherlands", "France", "Australia", "India", "Brazil", "Spain", "Sweden", "Ireland", "Singapore"];
const PAGES = [];
for (const cc of ["CA", "US"]) {
  PAGES.push(`overview/summary?range=7d&dd=country:${cc}`, `overview/summary?dd=country:${cc}`, `traffic/places?range=30d&dd=country:${cc}`,
    `traffic/visitors?range=7d&country=${cc}`, `traffic/sources?range=30d&country=${cc}`, `overview/summary?range=30d&country=${cc}`,
    `overview/insights?country=${cc}`, `traffic/places?range=30d&dd=city:${cc === "CA" ? "Toronto%2C%20Ontario%2C%20CA" : "New%20York%2C%20New%20York%2C%20US"}`);
}
PAGES.push("overview/summary?dd=country%3ACA", "overview/realtime", "traffic/places?range=30d", "traffic/visitors?range=7d", "overview/insights", "sales/pipeline?range=30d&lsrc=db");

const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };
const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
let where = "";
p.on("pageerror", (e) => fail(`${where}: ${e.message}`));

// Visible text only: no .vh (screen reader), no hidden element, no <title>/<option> tooltips.
const visible = (names) => {
  const bad = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    const el = t.parentElement;
    if (!el || el.closest(".vh, script, style, template, option, [hidden], [aria-hidden='true'] .vh")) continue;
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || !el.getClientRects().length) continue;
    // Help and About pages quote names in prose; the mail preview frame is the mail's own.
    if (el.closest(".help, .about, .mdview, .prose")) continue;
    // A region or city that shares a country's name is not the country: "Paris, Île-de-France, FRA",
    // "Singapore, SGP" (a city, then its country's code).
    for (const nm of names) if (new RegExp(`(?<![-\\w])${nm}(?![-\\w])(?!, [A-Z]{3}\\b)`).test(t.data)) bad.push(`"${nm}" in "${t.data.trim().slice(0, 70)}" (${el.tagName.toLowerCase()}.${[...el.classList].join(".")})`);
  }
  // SVG text (charts, the map, the flow) is visible text too.
  return [...new Set(bad)];
};

// The check itself: a full name drawn on screen is found, one in a tooltip or for a screen reader is not.
where = "self-check";
await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
const self = await p.evaluate((names) => {
  const box = document.createElement("div");
  box.innerHTML = '<p>Visitors from Canada</p><p title="Canada">CAN</p><span class="vh">Canada</span><p>Toronto, Ontario, CAN</p>';
  box.id = "cc-self";
  document.body.prepend(box);
  return names;
}, NAMES);
const caught = await p.evaluate(visible, self);
if (caught.length !== 1) fail(`${where}: expected 1 name on screen, found ${caught.length} (${caught.join("; ")})`);
await p.evaluate(() => document.getElementById("cc-self").remove());

let n = 0;
for (const page of PAGES) {
  where = page;
  await p.goto(`${base}#${page}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(900);
  n++;
  for (const x of await p.evaluate(visible, NAMES)) fail(`${where}: ${x}`);
}

// The visitor drawer, from the first visit of the grid.
where = "visitor drawer";
await p.goto(`${base}#traffic/visitors?range=7d`, { waitUntil: "networkidle" });
await p.waitForTimeout(800);
const row = p.locator(".v-row").first();
if (await row.count()) {
  await row.click(); await p.waitForTimeout(1500); n++;
  for (const x of await p.evaluate(visible, NAMES)) fail(`${where}: ${x}`);
} else fail(`${where}: no visit row to open`);

// The palette: a country found by its name, shown by its code.
where = "palette";
await p.goto(`${base}#overview/summary?range=30d`, { waitUntil: "networkidle" });
await p.waitForTimeout(600);
await p.keyboard.press("Control+k"); await p.waitForTimeout(400);
await p.keyboard.type("canada"); await p.waitForTimeout(500);
const first = await p.locator(".pal-list li").first().textContent().catch(() => "");
if (!/CAN/.test(first)) fail(`${where}: "canada" does not find CAN first ("${first.trim().slice(0, 60)}")`);
n++;

await b.close();
console.log(fails.length ? `${fails.length} problems on ${n} pages` : `countries: ${n} pages, all passed`);
process.exit(fails.length ? 1 : 0);
