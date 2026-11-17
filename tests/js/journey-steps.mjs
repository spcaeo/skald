// The visitor drawer's journey (js/journeymap.js), 2.20.1: a step seen only in the
// browser is the same small chip as a page loaded from the server, only its border
// dashed. It used to carry the bare class "app", which is the page shell's class
// (app.css: a grid with a min-height of the whole window), so the live drawer drew a
// screen-tall dashed box with the path at its bottom (seen on a live site, 2026-10-21).
//
//   node tests/js/journey-steps.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
const WEB = new URL("../../skald/webapp/", import.meta.url);
const { journeyMap } = await import(new URL("js/journeymap.js", WEB));

// One visit: a page loaded from the server, then one seen only in the browser.
const visit = {
  start: "2026-10-21T10:02:11-04:00", stop: "2026-10-21T10:02:53-04:00", source: "Search", via: "google.com",
  pages: 1, seconds: 42, this: true,
  trail: [{ path: "/insights/", page: true, at: 0 }, { path: "/telemedicine-app-development/", page: false, at: 42 }],
  endNode: { kind: "left", words: "left" },
};
const { el } = journeyMap([visit]);
const chips = el.querySelectorAll(".jm-n.pg");
assert.equal(chips.length, 2, "two page steps");
const [loaded, seen] = chips;
const classes = (e) => e.getAttribute("class").split(/\s+/);

assert.ok(loaded.textContent.includes("/insights/"));
assert.ok(!classes(loaded).includes("jm-app"), "a loaded page is not dashed");

assert.ok(seen.textContent.includes("/telemedicine-app-development/"));
assert.ok(classes(seen).includes("jm-n") && classes(seen).includes("pg"), "the browser-seen step is the same chip");
assert.ok(classes(seen).includes("jm-app"), "marked as seen in the browser");
// Never a class the page shell styles: "app" made the chip a full-window grid.
for (const c of classes(seen)) assert.ok(!["app", "shell", "main"].includes(c), `shell class "${c}" on a chip`);
// No inline size on either chip.
for (const chip of [loaded, seen]) {
  assert.equal(chip.getAttribute("style"), null, "no inline style");
  assert.equal(chip.style.height, undefined, "no inline height");
  assert.equal(chip.style.minHeight, undefined, "no inline min-height");
}

// The stylesheet marks it by its border only, and nothing in it sizes the chip.
const css = readFileSync(new URL("css/visitor.css", WEB), "utf8");
const rule = css.match(/\.jm-n\.pg\.jm-app\s*\{([^}]*)\}/);
assert.ok(rule, "visitor.css styles .jm-n.pg.jm-app");
assert.equal(rule[1].trim(), "border-style: dashed;");
assert.ok(!/\.jm-n\.pg\.app\b/.test(css), "the old .app selector is gone");
// And the shell's own `.app` rule is still what it was: a full-window grid, so it must never reach a chip.
const shell = readFileSync(new URL("app.css", WEB), "utf8");
assert.ok(/\.app\s*\{[^}]*min-height:\s*100vh/.test(shell));

// #62: the time between two steps, as honestly as the log knows it. `at` is rounded
// past the first minute (10 s, then a minute), so 0 there is "under 10 s", never "under 1 s".
const { gapWords } = await import(new URL("js/journeymap.js", WEB));
const pg = (at) => ({ page: true, at }), seenAt = (at) => ({ page: false, at });
assert.equal(gapWords(pg(0), pg(90)), "about 1 min 30 s", "past a minute the gap is rounded");
assert.equal(gapWords(pg(3), pg(20)), "17 s", "under a minute it is exact");
assert.equal(gapWords(pg(12), pg(12)), "opened together", "two pages in the same second");
assert.equal(gapWords(pg(90), pg(90)), "under 10 s", "the same 10 s step");
assert.equal(gapWords(pg(900), pg(900)), "under 1 min", "the same minute step");
assert.equal(gapWords(pg(20), seenAt(60)), "within 40 s", "a browser step happened within the gap");
assert.equal(gapWords(pg(20), seenAt(20)), "time not known");
assert.equal(gapWords(seenAt(60), pg(60)), "time not known", "leaving a browser step: its own time is not in the log");
assert.equal(gapWords(pg(0), { page: true }), "", "no time kept: no words");
for (const [a, b] of [[pg(0), pg(0)], [pg(90), pg(90)], [seenAt(60), pg(60)], [pg(20), seenAt(20)]])
  assert.notEqual(gapWords(a, b), "under 1 s");

// In the drawer: the live visit's shape, three pages, the last two the same 10 s step.
const live = { ...visit, pages: 3, seconds: 247,
  trail: [{ path: "/pricing-plans/", page: true, at: 0 }, { path: "/consulting/", page: true, at: 90 }, { path: "/implementation/", page: true, at: 90 }] };
const words = [...journeyMap([live]).el.querySelectorAll(".jm-t")].map((e) => e.textContent);
assert.deepEqual(words, ["about 1 min 30 s", "under 10 s"]);
console.log("journey-steps: all passed");
