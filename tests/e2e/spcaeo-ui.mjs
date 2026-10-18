// The vendored spcaeo/ui components through Skald's adapters (js/foldertabs.js, js/grid.js),
// on a demo page served here with the dashboard's Content-Security-Policy:
//  - both mount; Folder Tabs move with arrows, Home and End (skipping a disabled tab),
//    keep focus across the redraw, and a keyboard move does not stack history;
//  - the Data Grid's search, sort (biggest first, smallest, its own order) and filter round-trip through the hash beside the route
//    and the page's own keys, survive a reload, and Reset clears only the grid's keys;
//  - paging pushes history and Back returns; totals and exports hold every filtered row;
//  - redraws do not pile up instances or window listeners; no CSP refusal, no error.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs node tests/e2e/spcaeo-ui.mjs

import http from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
const ROOT = resolve(fileURLToPath(import.meta.url), "../../..");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };
// The dashboard's policy (deployments/…/nginx), so an inline script or eval would be refused here too.
const CSP = "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'";

const server = http.createServer(async (req, res) => {
  const file = resolve(ROOT, `.${decodeURIComponent(new URL(req.url, "http://localhost").pathname)}`);
  if (!file.startsWith(ROOT + sep) || !TYPES[extname(file)]) return res.writeHead(404).end();
  try {
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": TYPES[extname(file)], "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store" });
    res.end(body);
  } catch { res.writeHead(404).end(); }
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const BASE = `http://127.0.0.1:${server.address().port}/tests/e2e/spcaeo-ui/demo.html`;

const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };
const check = (ok, what) => { if (!ok) fail(what); };

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
const p = await ctx.newPage();
p.on("pageerror", (e) => fail(`page error: ${e.message}`));
p.on("console", (m) => { if (m.type() === "error") fail(`console error: ${m.text()}`); });

const hash = () => p.evaluate(() => location.hash);
const params = async () => new URLSearchParams((await hash()).split("?")[1] || "");
const routeOf = async () => (await hash()).replace(/^#/, "").split("?")[0];
const frame = () => p.waitForTimeout(80);
const rowCount = () => p.locator(".dg-table tbody tr").count();
const total = async () => Number(((await p.locator(".dg-count").textContent()) || "").replace(/.* of /, "").replace(/\D/g, ""));
const activeKey = () => p.evaluate(() => document.activeElement?.dataset?.key || document.activeElement?.tagName);

await p.goto(`${BASE}#demo/one?range=7d`, { waitUntil: "networkidle" });
await frame();

// ---- mount
check(await p.locator("[data-folder-tabs] .fldr-tab").count() === 5, "five tabs drawn");
check(await p.locator('.fldr-tab[data-state="active"]').getAttribute("data-key") === "demo/one", "the route's tab is active");
check(await p.locator(".fldr-panel").getAttribute("aria-labelledby") === "ft-demo-demo-one", "the panel is labelled by the active tab");
check(await rowCount() === 25, `a page of 25 rows (got ${await rowCount()})`);
check(await total() === 60, "the count says of 60");

// ---- keyboard on the tabs: arrows (skipping the disabled tab), Home, End; focus survives the redraw
const before = await p.evaluate(() => history.length);
await p.focus('.fldr-tab[data-state="active"]');
const press = async (key, want) => {
  const drawn = await p.evaluate(() => demo.renders());
  await p.keyboard.press(key);
  // After the redraw: the old strip's tab holds focus until then, the new one's after.
  await p.waitForFunction(([w, n]) => demo.renders() > n && location.hash.split("?")[0] === `#${w}`
    && document.activeElement?.dataset?.key === w && document.activeElement.isConnected, [want, drawn], { timeout: 2000 }).catch(() => {});
  check(await routeOf() === want, `${key} goes to ${want} (at ${await routeOf()})`);
  check(await activeKey() === want, `${key}: focus on the new strip's ${want} tab (on ${await activeKey()})`);
  check((await params()).get("range") === "7d", `${key}: the period stays in the address`);
};
await press("ArrowRight", "demo/two");
await press("ArrowRight", "demo/three");  // past the disabled tab
await press("End", "demo/four");
await press("Home", "demo/one");
await press("ArrowLeft", "demo/four");  // wraps
await press("ArrowLeft", "demo/three");
await press("ArrowLeft", "demo/two");   // past the disabled tab again
await press("Home", "demo/one");
check(await p.evaluate(() => history.length) === before, "keyboard moves replace the address, not stack history");
check(await p.locator('.fldr-tab[data-key="demo/locked"]').getAttribute("href") === null, "a disabled tab has no link");

// A plain click follows the link (one history entry); Ctrl/Cmd-click is left to the browser.
await p.click('.fldr-tab[data-key="demo/two"]');
await p.waitForFunction(() => location.hash.startsWith("#demo/two"));
check(await p.evaluate(() => history.length) === before + 1, "a click pushes one entry");
const popup = ctx.waitForEvent("page", { timeout: 2000 }).catch(() => null);
await p.click('.fldr-tab[data-key="demo/three"]', { modifiers: ["ControlOrMeta"] });
const opened = await popup;
await frame();
check(await routeOf() === "demo/two", "a modifier click leaves this page's tab alone");
check(await p.locator('.fldr-tab[data-state="active"]').getAttribute("data-key") === "demo/two", "and its strip");
if (opened) await opened.close();
await p.click('.fldr-tab[data-key="demo/one"]');
await p.waitForFunction(() => location.hash.startsWith("#demo/one") && document.querySelector(".dg-table"));

// ---- grid search: typing keeps going across the debounce; the key joins the hash beside the route
const box = p.locator('.dg-search input[type="search"]');
await box.click();
await p.keyboard.type("be");
await p.waitForTimeout(400);
await p.keyboard.type("ta");
await p.waitForTimeout(400);
check(await box.inputValue() === "beta", `search box holds what was typed (got "${await box.inputValue()}")`);
check(await p.evaluate(() => document.activeElement?.type === "search"), "focus stays in the search box");
let q = await params();
check(q.get("pg_q") === "beta" && q.get("range") === "7d" && (await routeOf()) === "demo/one", `search in the hash beside route and range (${await hash()})`);
check(await total() === 12 && (await rowCount()) === 12, `12 rows have "beta" (got ${await total()})`);

// ---- sort (2.13, js/tablestate.js nextSort): a number biggest first, then smallest, then the grid's own order
const viewsHead = p.locator(".dg-table thead th", { hasText: "Views" });
await viewsHead.locator("button").click();
check((await params()).get("pg_sort") === "views:desc", "sort descending in the hash");
await viewsHead.locator("button").click();
check((await params()).get("pg_sort") === "views:asc", "sort ascending in the hash");
check(await viewsHead.getAttribute("aria-sort") === "ascending", "header says ascending");
await viewsHead.locator("button").click();
check(!(await params()).get("pg_sort"), "a third click: the grid's own order, nothing in the hash");
await viewsHead.locator("button").click();
check((await params()).get("pg_sort") === "views:desc", "sort descending in the hash again");
// The marks are the shared tables' (patch 7): ▼ on the column sorted biggest first, a ↕ on the others.
const marks = await p.locator(".dg-table thead th .dg-sort .dir").allTextContents();
check(marks.filter((x) => x === "▼").length === 1 && marks.filter((x) => x === "▲").length === 0 && marks.filter((x) => x === "↕").length === marks.length - 1,
  `one ▼ on the sorted column, ↕ on the rest (got ${marks.join(" ")})`);
check(await viewsHead.locator(".dir").textContent() === "▼", "Views, sorted biggest first, shows ▼");
const firstViews = async () => Number(await p.locator(".dg-table tbody tr").first().locator("td").nth(3).textContent());
check(await firstViews() === 100, `largest views first (got ${await firstViews()})`);

// ---- filter: Kind = blog
await p.locator(".dg-toolbar .dg-btn", { hasText: "Kind" }).click();
await p.locator(".dg-pop:popover-open label", { hasText: "blog" }).locator("input").check();
await p.locator(".dg-pop:popover-open .dg-btn-primary").click();
await frame();
q = await params();
check(!!q.get("pg_fx"), "the filter is in the hash");
check(q.get("pg_q") === "beta" && q.get("pg_sort") === "views:desc" && q.get("range") === "7d", "and the other keys stay");
const kinds = await p.locator(".dg-table tbody tr td:nth-child(3)").allTextContents();
check(kinds.length === 4 && kinds.every((k) => k === "blog"), `only blog rows (got ${kinds.join(",")})`);
check(await p.locator(".dg-chip").count() === 1, "one filter chip");
check((await p.locator("#totals").textContent()).startsWith("Filtered: 4"), "totals over the filtered rows");

// ---- reload: the same view comes back from the address alone
const shown = await p.locator(".dg-table tbody").textContent();
await p.reload({ waitUntil: "networkidle" });
await frame();
check(await p.locator('.dg-search input[type="search"]').inputValue() === "beta", "reload: search kept");
check(await p.locator(".dg-table thead th", { hasText: "Views" }).getAttribute("aria-sort") === "descending", "reload: sort kept");
check(await p.locator(".dg-chip").count() === 1, "reload: filter kept");
check(await p.locator(".dg-table tbody").textContent() === shown, "reload: the same rows");

// ---- Reset clears only the grid's keys
await p.locator(".dg-toolbar .dg-btn", { hasText: "Reset" }).click();
q = await params();
check(![...q.keys()].some((k) => k.startsWith("pg_")), `Reset drops the grid's keys (${await hash()})`);
check(q.get("range") === "7d" && (await routeOf()) === "demo/one", "Reset keeps the route and the period");
check(await total() === 60, "Reset shows every row");

// ---- exports and totals hold every filtered row, not the page
check((await p.evaluate(() => demo.registry())).join() === "60", "the export registry holds all 60 rows, not the page of 25");

// ---- paging pushes; Back returns
const len = await p.evaluate(() => history.length);
await p.locator(".dg-pagination .dg-btn", { hasText: "Next" }).click();
check((await params()).get("pg_page") === "2", "Next writes page 2");
check(await p.evaluate(() => history.length) === len + 1, "a page is a history entry");
const page2 = await p.locator(".dg-table tbody tr").first().textContent();
await p.goBack();
await frame();
check(!(await params()).get("pg_page"), "Back drops the page key");
check(await p.locator(".dg-table tbody tr").first().textContent() !== page2, "Back shows page 1 again");
check(await routeOf() === "demo/one" && (await params()).get("range") === "7d", "Back keeps route and period");

// ---- a row opens on click and on Enter
await p.locator(".dg-table tbody tr").nth(2).click();
const clicked = await p.evaluate(() => demo.opened());
await p.locator(".dg-table tbody tr").nth(3).focus();
await p.keyboard.press("Enter");
const entered = await p.evaluate(() => demo.opened());
check(!!clicked && !!entered && clicked !== entered, `rows open on click and Enter (${clicked}, ${entered})`);

// ---- redraws: no pile-up of instances or window listeners
const counts = () => p.evaluate(() => ({ live: demo.liveCount(), pop: __listeners("popstate"), resize: __listeners("resize") }));
const base = await counts();
for (let i = 0; i < 6; i++) { await p.evaluate(() => demo.redraw()); await frame(); }
await p.evaluate(() => { location.hash = "#demo/one?range=30d"; });
await frame();
await p.evaluate(() => demo.sweep());
const after = await counts();
check(JSON.stringify(after) === JSON.stringify(base), `redraws leave the same listeners (${JSON.stringify(base)} then ${JSON.stringify(after)})`);
check(base.live === 2, `two live components (tabs and grid), got ${base.live}`);

// ---- Skald's colours, light and dark: the active tab is the panel's own fill
for (const theme of ["light", "dark"]) {
  await p.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
  await p.waitForTimeout(400);  // the tabs' colour transition
  const got = await p.evaluate(() => {
    const css = (sel, prop) => getComputedStyle(document.querySelector(sel))[prop];
    const root = getComputedStyle(document.documentElement);
    const probe = document.createElement("i");
    document.body.append(probe);
    const rgb = (v) => { probe.style.color = v; return getComputedStyle(probe).color; };
    const out = {
      tab: css('.fldr-tab[data-state="active"]', "backgroundColor"), panel: css(".fldr-panel", "backgroundColor"),
      surface: rgb(root.getPropertyValue("--surface").trim()), rail: css(".fldr-rail", "backgroundColor"),
      grid: rgb(getComputedStyle(document.querySelector(".dg")).getPropertyValue("--dg-bg").trim()),
    };
    probe.remove();
    return out;
  });
  check(got.tab === got.panel && got.panel === got.surface, `${theme}: active tab = panel = Skald's surface (${got.tab}, ${got.panel}, ${got.surface})`);
  check(got.rail !== got.panel, `${theme}: the rail differs from the panel`);
  check(got.grid === got.surface, `${theme}: the grid sits on Skald's surface`);
}

check((await p.evaluate(() => __csp)).length === 0, `no CSP refusal (${await p.evaluate(() => __csp.join("; "))})`);

await b.close();
server.close();
console.log(fails.length ? `${fails.length} failed` : "spcaeo-ui: all passed");
process.exit(fails.length ? 1 : 0);
