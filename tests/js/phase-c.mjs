// The UX build, part 3 (2.42): the pieces AI & bots, Traffic, Leads & sales and Security share.
//   * ui/showall.js: a long list opens on its first rows, "Show all (N)" shows the rest
//   * ui/fold.js urlFold: a fold whose open state is in the address (<ns>_view=open)
//   * tabs/fixit.js causesOf: the pages AI can't read well, by what to do
//
//   node tests/js/phase-c.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { h } = await import(new URL("ui.js", JS));
const { showAll } = await import(new URL("ui/showall.js", JS));
const { urlFold } = await import(new URL("ui/fold.js", JS));
const F = await import(new URL("tabs/fixit.js", JS));
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();

// ---- Show all (N)
const rows = Array.from({ length: 8 }, (_, i) => `row ${i + 1}`);
const box = showAll((k) => h("ul", null, rows.slice(0, k).map((r) => h("li", null, r))), rows.length, { first: 5 });
assert.equal(box.querySelectorAll("li").length, 5, "the first five");
const more = box.querySelector("button.ui-more");
assert.equal(text(more), "Show all (8)");
more.click();
assert.equal(box.querySelectorAll("li").length, 8, "all of them after the press");
assert.equal(text(box.querySelector("button.ui-more")), "Show fewer");
const short = showAll((k) => h("ul", null, rows.slice(0, 3).slice(0, k).map((r) => h("li", null, r))), 3, { first: 5 });
assert.equal(short.querySelector("button.ui-more"), null, "no button when all fit");

// ---- a fold kept in the address
location.hash = "#ai/assistants?range=7d";
let drawn = 0;
const d = urlFold("ai", "Open the details", () => { drawn++; return h("p", null, "inside"); });
assert.equal(drawn, 0, "drawn only when it opens");
d.setAttribute("open", "");
d.open = true;
d.dispatchEvent(new Event("toggle"));
assert.equal(drawn, 1);
assert.match(location.hash, /ai_view=open/, "open: in the address");
const again = urlFold("ai", "Open the details", () => h("p", null, "inside"));
assert.ok(again.open || again.hasAttribute("open"), "a link with ai_view=open opens it");
d.open = false;
d.removeAttribute("open");
d.dispatchEvent(new Event("toggle"));
assert.doesNotMatch(location.hash, /ai_view=/, "closed: out of the address");

// ---- the pages AI can't read well, by what to do
const f = { attention: { total: 4, rows: [
  { path: "/a.md", copy_errors: 2, copy_404: 2, not_found: 0, server_errors: 0, blocked: 0, robots: [], slow: 0 },
  { path: "/b/", copy_errors: 0, not_found: 3, server_errors: 0, blocked: 0, robots: ["GPTBot"], slow: 0 },
  { path: "/c/", copy_errors: 0, not_found: 0, server_errors: 1, blocked: 1, robots: [], slow: 0 },
  { path: "/d/", copy_errors: 0, not_found: 0, server_errors: 0, blocked: 0, robots: [], slow: 2 },
] } };
const got = F.causesOf(f);
assert.deepEqual(got.map((c) => [c[0], c[3]]), [["copy", ["/a.md"]], ["404", ["/b/"]], ["errors", ["/c/"]], ["robots", ["/b/"]], ["slow", ["/d/"]]]);
assert.ok(got.every((c) => c[4]), "each kind has its short words for the card");
assert.deepEqual(F.causesOf({ attention: { rows: [] } }), [], "nothing to fix: no kinds");
assert.equal(await F.openFixit("nothing", {}), "That Fix is not one Skald has.");
assert.equal(F.KEY, "fixit");

// ---- Retention: the tile's weeks against the period chip's 12 (tabs/tr-retention.js seenIn)
const { seenIn } = await import(new URL("tabs/tr-retention.js", JS));
const weeks = ["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07"].map((start) => ({ start }));
const file = { begun: "2026-08-25", grains: { week: { cohorts: weeks } } };
const shown = weeks.filter((c) => c.start >= file.begun);
assert.equal(seenIn(file, "week", shown, shown.slice(0, 1)), "first seen in 1 of the 6 weeks: 4 before what is kept begins (Tue 25 Aug 2026), 1 not counted yet");
assert.equal(seenIn({ grains: { week: { cohorts: weeks } } }, "week", weeks, weeks), "first seen in the 6 weeks", "all counted: the plain words");

console.log("phase-c: all passed");
process.exit(0);
