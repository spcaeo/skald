// Site › Data quality (js/tabs/quality.js), SKALD-25: "2,193 duplicate lines" on a live site
// left the reader asking whether they were counted. They are (COUNTING-TRAPS.md 7): the note
// says so, and how many lines that repeated a request ID were dropped.
//
//   node tests/js/quality-dups.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const { dupNote } = await import(new URL("../../skald/webapp/js/tabs/quality.js", import.meta.url));
assert.equal(dupNote({ duplicates: 2193 }), "the same line twice in one second: kept in the figures");
assert.equal(dupNote({ duplicates: 2193, duplicates_removed: 0 }), "the same line twice in one second: kept in the figures");
assert.equal(dupNote({ duplicates: 4, duplicates_removed: 1234 }),
  "the same line twice in one second: kept in the figures; 1,234 more repeated a request ID and were dropped");
assert.equal(dupNote(null), "the same line twice in one second: kept in the figures");
console.log("quality-dups: all passed");
