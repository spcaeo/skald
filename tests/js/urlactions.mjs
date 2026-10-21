// Copy and open in a new tab on every URL and site path (2.21, js/urlactions.js): both
// buttons with their labels, the copy writes the full URL (a path joined with the site's
// own address), the tick shows and clears, a failed copy says so, open has the right href
// and rel, neither click reaches the row; every table and grid column of site paths or
// URLs draws them, and no page column in the code is left without the flag.
//
//   node tests/js/urlactions.mjs
import assert from "node:assert/strict";
import { mock } from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { install, Ev } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const U = await import(new URL("urlactions.js", JS));
const { table } = await import(new URL("table.js", JS));
const copied = [];
let refuse = false;
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true,
  value: { writeText: async (t) => { if (refuse) throw new Error("denied"); copied.push(t); } } });
const tick = () => new Promise((r) => setImmediate(r));

// ---- the full URL
U.setSiteBase("example.com");
assert.equal(U.fullUrl("/pricing/"), "https://example.com/pricing/");
assert.equal(U.fullUrl("https://news.example.org/a?b=1"), "https://news.example.org/a?b=1");
for (const no of ["", "(all others)", "(none)", "//evil.example", "pricing", "/a b", null]) assert.equal(U.fullUrl(no), null, String(no));
U.setSiteBase("https://www.example.com/");
assert.equal(U.fullUrl("/x/"), "https://www.example.com/x/", "the site's name, without its scheme or slash");
U.setSiteBase("example.com");

// ---- the two buttons, their labels, href and rel
const cell = U.withUrl(document.createTextNode("/pricing/"), "/pricing/");
assert.ok(cell.classList.contains("ua-host"));
const copy = cell.querySelector("button.ua-copy");
const openA = cell.querySelector("a.ua-open");
assert.equal(copy.getAttribute("aria-label"), "Copy link to /pricing/");
assert.equal(openA.getAttribute("aria-label"), "Open /pricing/ in a new tab");
assert.equal(openA.getAttribute("href"), "https://example.com/pricing/");
assert.equal(openA.getAttribute("target"), "_blank");
assert.equal(openA.getAttribute("rel"), "noopener noreferrer");
assert.equal(copy.getAttribute("type"), "button", "a real button: Tab reaches it, Enter and Space press it");
assert.equal(U.withUrl("x", "(none)"), "x", "no URL: the content alone");

// ---- copy: the full URL, a green tick for 1.5 s, then hidden; the row under it never hears the click
const row = document.createElement("tr");
let rowClicks = 0;
row.addEventListener("click", () => { rowClicks += 1; });
row.append(cell);
document.body.append(row);
mock.timers.enable({ apis: ["setTimeout"] });
copy.click();
await tick();
assert.deepEqual(copied, ["https://example.com/pricing/"]);
const ua = cell.querySelector(".ua");
assert.ok(ua.classList.contains("ua-ok"), "the tick");
assert.equal(copy.getAttribute("aria-label"), "Copied the link to /pricing/");
assert.equal(cell.querySelector(".ua-msg").textContent, "Copied");
mock.timers.tick(U.TIMING.tick - 1);
assert.ok(ua.classList.contains("ua-ok"), "still the tick before 1.5 s");
mock.timers.tick(1);
assert.ok(!ua.classList.contains("ua-ok"), "the tick clears");
assert.ok(ua.classList.contains("ua-gone"), "and the icons hide");
assert.equal(copy.getAttribute("aria-label"), "Copy link to /pricing/");
assert.equal(rowClicks, 0, "the row's own click did not run");
// Back when the reader leaves the cell and comes again.
cell.dispatchEvent(new Ev("mouseleave"));
assert.ok(!ua.classList.contains("ua-gone"));

// ---- a copy that fails says so instead of a tick
refuse = true;
copy.click();
await tick();
assert.ok(ua.classList.contains("ua-bad") && !ua.classList.contains("ua-ok"));
assert.equal(cell.querySelector(".ua-msg").textContent, "Copy failed: select and copy");
mock.timers.tick(U.TIMING.failed);
assert.ok(!ua.classList.contains("ua-bad"));
refuse = false;

// ---- open: hides the icons; Space on the link opens it too
let opened = 0;
openA.addEventListener("click", () => { opened += 1; });
openA.click();
assert.equal(opened, 1);
assert.ok(ua.classList.contains("ua-gone"), "hidden after open");
const space = new Ev("keydown", { key: " " });
openA.dispatchEvent(space);
assert.equal(opened, 2, "Space opens");
assert.ok(space.defaultPrevented);
assert.equal(rowClicks, 0, "the row's own click never ran");
mock.timers.reset();

// ---- every table column of site paths or URLs draws them (the shared table's column kinds)
const kinds = [{ path: true }, { url: true }, { drill: "path" }, { drill: "landing" }];
for (const kind of kinds) {
  const t = table([{ key: "p", label: "Page", ...kind }, { key: "v", label: "Views", num: true }], { caption: "T", rows: [{ p: "/a/", v: 1 }, { p: "/b/", v: 2 }], ns: false });
  const btns = t.querySelectorAll("button.ua-copy");
  assert.equal(btns.length, 2, `${JSON.stringify(kind)}: each row`);
  assert.equal(t.querySelectorAll("a.ua-open")[0].getAttribute("href"), "https://example.com/b/");
  assert.ok(U.isUrlColumn(kind));
}
const plain = table([{ key: "p", label: "Country" }], { caption: "T2", rows: [{ p: "CA" }], ns: false });
assert.equal(plain.querySelectorAll(".ua").length, 0, "other columns do not");
// href(row): the URL when the cell shows something else.
const hrefT = table([{ key: "label", label: "Page", url: true, href: (r) => r.k }], { caption: "T3", rows: [{ label: "Pricing", k: "/pricing/" }], ns: false });
assert.equal(hrefT.querySelector("a.ua-open").getAttribute("href"), "https://example.com/pricing/");

// ---- the code: a column of pages or URLs always says so (path, url, or drilled by page)
const files = [...readdirSync(new URL("tabs/", JS)).map((f) => `tabs/${f}`), ...readdirSync(JS).filter((f) => f.endsWith(".js"))].filter((f) => f.endsWith(".js") && f !== "rules.js");   // rules.js: the filters' dimensions, not columns
const PAGEISH = /\{ key: "[a-z_]+", label: "(Page|Pages read|Landing|Landing page|Path|URL|Request|Referring site)"[^}]*\}/g;
let seen = 0;
for (const f of files) {
  const src = readFileSync(new URL(f, JS), "utf8");
  for (const m of (src.match(PAGEISH) || []).filter((x) => !/num: true|type: "num"/.test(x))) {
    seen += 1;
    assert.ok(/path: (true|kind)|url: true|drill: "(path|landing)"/.test(m), `${f}: a page column without path: true or url: true: ${m.slice(0, 120)}`);
  }
}
assert.ok(seen >= 20, `${seen} page columns checked`);
// The shared builders: table.js and grid.js wrap such cells; the counts' and bars' helpers too.
for (const f of ["table.js", "grid.js", "tabs/common.js", "tabs/tr-grid.js", "journeymap.js"]) {
  assert.ok(/withUrl|url: true/.test(readFileSync(new URL(f, JS), "utf8")), `${f} uses the component`);
}
console.log("urlactions: all passed");
