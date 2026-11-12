// A lead's own visits in the person drawer (#30, 2.46.5): where they first came from, each
// visit in order with its pages, what it sent, and whether it is proven or likely; a step
// no visit is proven for is said, never hidden. Shaped on freshlycited.com lead 1179.
//
//   node tests/js/person-path.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { pathPart } = await import(new URL("tabs/person.js", JS));
const text = (el) => (el == null ? "" : el.textContent);

assert.equal(pathPart(null), null);
assert.equal(pathPart({ visits: [], unmatched: [] }), null);
const v1 = { start: "2026-11-11T16:24:00Z", source: "Search engine", via: "bing.com", landing: "/bing-webmaster-tools/ai-performance-report",
  trail: [["/bing-webmaster-tools/ai-performance-report", "page", 0], ["/contact/", "app", 80]], link: "proven", why: "the only visit that sent a form at the lead's time",
  steps: [{ action: "xray", stage: "completed", at: "2026-11-11T16:25:22Z" }] };
const v2 = { start: "2026-11-11T17:02:00Z", source: "Direct or unknown", via: null, landing: "/app/", trail: [["/app/", "page", 0]], link: "likely", why: "the same address and browser as a proven visit", steps: [] };
const sec = pathPart({ visits: [v1, v2], unmatched: [{ action: "signup", stage: "paid", at: "2026-11-11T16:50:14Z", why: "no visit sent a form at its time" }],
  first: { start: v1.start, source: v1.source, via: v1.via, landing: v1.landing, link: "proven" } });
const words = text(sec);
assert.match(words, /Their visits, in order/);
assert.match(words, /First came from Search engine · bing\.com/);
assert.match(words, /\/bing-webmaster-tools\/ai-performance-report › \/contact\//, "the pages in order");
assert.match(words, /xray completed/);
assert.match(words, /Proven/);
assert.match(words, /Likely/);
assert.match(words, /Not matched to a visit: signup paid/);
assert.match(words, /Never counted in any figure/);
console.log("person-path: all passed");
