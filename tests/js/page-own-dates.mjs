// A page's own dates in words and marks (SKALD-64, js/page-dates.js): where each date
// comes from, the sitemap's dates when Skald does not read the page, a mark per update
// day in its chart slot, and the line for a page Skald could not read.
//
//   node tests/js/page-own-dates.mjs      (tests/test_page_dates_js.py runs it)
//
// Example data only: made-up paths and dates.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const tz = await import(new URL("tz.js", JS));
tz.setZone("site", "America/New_York");
const D = await import(new URL("page-dates.js", JS));

const page = {
  path: "/guide/", published: "2024-11-05", date_source: "page", published_at: "2024-11-05T06:42:00Z", published_from: "jsonld",
  updated: "2026-11-26", updated_source: "page", updated_at: "2026-11-26T05:42:14Z",
  changes: [{ day: "2026-11-20", at: "2026-11-20", sources: ["sitemap"] }, { day: "2026-11-26", at: "2026-11-26T05:42:14Z", sources: ["jsonld", "sitemap"] }],
  check: { at: "2026-11-26T06:00:00Z", outcome: "dated", status: 200, error: null },
};

// ---- the dates line says where each date comes from
const line = D.datesLine(page);
assert.match(line, /^Published .*2024.* \(from the page's structured data\) · Last updated .* \(from the page\)$/);
assert.equal(D.datesLine({ published: "2026-10-29", date_source: "first seen", updated: "2026-11-25", updated_source: "sitemap" }),
  "First seen 29 Oct (no publish date known) · Last changed 25 Nov (from your sitemap)");
assert.equal(D.datesLine(null), "");

// ---- a value as the page gave it
assert.match(D.whenWords("2026-11-26T07:30:00"), /, 07:30 \(as the page wrote it\)$/);
assert.equal(D.whenWords("2024-11-05", (d) => `day ${d}`), "day 2024-11-05");

// ---- marks: the page's own and the sitemap's, else the sitemap's dates
assert.deepEqual(D.updateMarks(page).map((c) => c.day), ["2026-11-20", "2026-11-26"]);
assert.deepEqual(D.updateMarks({ lastmod_seen: [["2026-11-01", "2026-11-02"]] }), [{ day: "2026-11-01", at: "2026-11-01", sources: ["sitemap"] }]);
assert.deepEqual(D.updateMarks(null), []);

// ---- one mark per slot that holds an update: a day, or a stretch of days
const days = [{ day: "2026-11-19" }, { day: "2026-11-20" }, { day: "2026-11-21" }];
const svg = D.markerSvg(D.updateMarks(page), days, (i) => 10 + i * 10, 0, 100);
assert.equal((svg.match(/class="upd-mark"/g) || []).length, 1);
assert.match(svg, /x1="20\.0"/);
assert.match(svg, /<title>Updated (?:Fri )?20 Nov 2026 \(from your sitemap\)<\/title>/);
const buckets = [{ first: "2026-11-15", last: "2026-11-21" }, { first: "2026-11-22", last: "2026-11-28" }];
assert.equal((D.markerSvg(D.updateMarks(page), buckets, (i) => i, 0, 1).match(/upd-mark/g) || []).length, 2);
assert.equal(D.markerSvg([], days, (i) => i, 0, 1), "");

// ---- a page Skald could not read, and one that gives no date
assert.match(D.checkWords({ check: { at: "2026-11-26T06:00:00Z", outcome: "blocked", status: 403 } }), /a bot check stopped Skald's request/);
assert.match(D.checkWords({ check: { at: "2026-11-26T06:00:00Z", outcome: "not_given", status: 200 } }), /^The page gives no published or updated date/);
assert.equal(D.checkWords(page), "");

console.log("page-dates: all passed");
