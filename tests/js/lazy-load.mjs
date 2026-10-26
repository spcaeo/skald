// The big files load when first needed (2.41: skald/webapp/js/data.js LAZY, lazy.js):
//   * a site opens without not_found, pages, page_index or page_trends
//   * need() fetches each once, however many ask at the same time, and puts it in the model
//   * a tab names the files it is drawn with (sections.js tabFiles); the Overview none
//   * an Overview panel shows its title and "Loading", then is drawn when its file comes
//   * the two-minute refresh reads again only the big files this page already has
//
//   node tests/js/lazy-load.mjs <a site's folder from a dashboard run>
//   (tests/test_lazy_load.py makes the folder and runs it)
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { install } from "./dom-lite.mjs";

const SITE = process.argv[2];
install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, hash) { location.hash = hash; }, replaceState(_, __, hash) { location.hash = hash; }, back() {}, go() {} };
location.hash = "#overview/summary?range=7d";

const asked = [];
globalThis.fetch = async (url) => {
  asked.push(url);
  const path = join(SITE, url.split("?")[0]);
  if (!existsSync(path)) return { ok: false, status: 404, body: { cancel() {} } };
  const text = readFileSync(path, "utf8");
  return { ok: true, status: 200, json: async () => JSON.parse(text), body: { cancel() {} } };
};
const names = () => asked.map((u) => u.replace(/^data\//, "").replace(/^slim\//, "").replace(/\.json$/, ""));
const file = (rel) => JSON.parse(readFileSync(join(SITE, "data", rel), "utf8"));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const D = await import(new URL("data.js", JS));
const { tabFiles } = await import(new URL("sections.js", JS));
const { later } = await import(new URL("lazy.js", JS));
const { h } = await import(new URL("ui.js", JS));

assert.deepEqual(D.LAZY, ["not_found", "pages", "page_index", "page_trends"]);

// ---- a site opens without them
const s = { view: "all", tab: "overview/summary", range: "7d" };
const m = await D.load(s);
assert.ok(names().includes("app"), "app.json first");
assert.ok(names().includes("overview"));
for (const n of D.LAZY) {
  assert.ok(!names().includes(n), `${n}.json fetched with the page`);
  assert.equal(m.x[n], null);
  assert.equal(D.has(m, [n]), false);
}
for (const n of D.LAZY) assert.ok(m.files.includes(n), `the run did not write ${n}.json`);
assert.equal(D.has(m, ["overview", "leads"]), true, "a core file is always there");

// ---- what each tab is drawn with
assert.deepEqual(tabFiles("overview/summary", s), []);
assert.deepEqual(tabFiles("overview/summary", s, { panels: true }).sort(), ["page_index", "page_trends"]);
assert.deepEqual(tabFiles("traffic/pages", s).sort(), ["page_index", "page_trends", "pages"]);
assert.deepEqual(tabFiles("site/notfound", s), ["not_found"]);
assert.deepEqual(tabFiles("ai/assistants", s), ["page_trends"]);
assert.deepEqual(tabFiles("sales/funnels", s), ["pages"]);
assert.deepEqual(tabFiles("traffic/sources", s), []);
assert.deepEqual(tabFiles("settings", s), []);

// ---- need(): once each, into the model
asked.length = 0;
await Promise.all([D.need(m, ["pages", "page_trends"]), D.need(m, ["pages"]), D.need(m, ["page_trends", "overview"])]);
assert.deepEqual(names().sort(), ["page_trends", "pages"]);
// The slim copy, when app.json lists it (slim.py): every page, without the parts never drawn.
assert.ok(m.slim.includes("pages"), "the run wrote no slim copy of pages.json");
assert.ok(asked.includes("data/slim/pages.json"));
assert.deepEqual(m.x.pages, file("slim/pages.json"));
assert.equal(m.x.pages.pages.length, file("pages.json").pages.length);
assert.equal(m.x.pages.pages[0].daily, undefined);
assert.equal(D.has(m, ["pages", "page_trends"]), true);
assert.equal(D.has(m, ["pages", "not_found"]), false);
asked.length = 0;
await D.need(m, ["pages"]);
assert.deepEqual(asked, [], "fetched again");

// ---- a builder that failed: "could not be built", as before
const real = globalThis.fetch;
globalThis.fetch = async (url) => (/not_found/.test(url)
  ? { ok: true, status: 200, json: async () => ({ schema_version: 1, state: "error", error: "a test failure" }), body: { cancel() {} } }
  : real(url));
await D.need(m, ["not_found"]);
assert.equal(m.failed.not_found, "a test failure");
assert.equal(m.x.not_found, null);
globalThis.fetch = real;

// ---- a slim copy listed but gone (a run between): the file itself
const gone404 = globalThis.fetch;
globalThis.fetch = async (url) => (/slim\/page_index/.test(url) ? (asked.push(url), { ok: false, status: 404, body: { cancel() {} } }) : gone404(url));
asked.length = 0;
const mm = await D.load(s);
await D.need(mm, ["page_index"]);
assert.deepEqual(asked.slice(-2), ["data/slim/page_index.json", "data/page_index.json"]);
assert.deepEqual(mm.x.page_index, file("page_index.json"));
globalThis.fetch = gone404;

// ---- the refresh reads again only those this page has
asked.length = 0;
const next = await D.load(s, { fresh: true, previous: m });
assert.ok(names().includes("pages") && names().includes("page_trends") && names().includes("not_found"));
assert.ok(!names().includes("page_index"), "the refresh fetched a big file nobody opened");
assert.equal(D.has(next, ["pages", "page_trends", "not_found"]), true);
assert.ok(next.x.pages && next.x.page_trends);
assert.equal(next.failed.not_found, undefined, "the file is whole again");

// ---- a panel waits on its own
const fresh = await D.load(s);
let built = 0;
const box = later(fresh, ["page_index"], () => { built += 1; return h("section", { class: "s done" }, "drawn"); }, "New and updated pages");
document.body.append(box);
assert.equal(built, 0);
assert.equal(box.getAttribute("aria-busy"), "true");
assert.match(box.textContent, /New and updated pages/);
assert.match(box.textContent, /Loading/);
await D.need(fresh, ["page_index"]);
await new Promise((r) => setTimeout(r, 0));
assert.equal(built, 1);
assert.equal(box.isConnected, false, "the placeholder stayed");
assert.match(document.body.textContent, /drawn/);
// Once there, drawn at once.
const at = later(fresh, ["page_index"], () => h("p", null, "now"), "x");
assert.equal(at.textContent, "now");
// A page drawn again meanwhile: the old panel is left be.
const gone = later(await D.load(s), ["page_trends"], () => { built += 1; return h("p", null, "late"); }, "x");
await new Promise((r) => setTimeout(r, 20));
assert.equal(built, 1, "drew a panel no longer on the page");
assert.equal(gone.isConnected, false);

console.log("lazy-load: all passed");
