// The page takes a refreshed count only when it is later (#50): data.js newerStamp.
// An overlapping run could write a file drawn from an older count; the open page
// must keep the newer one it already shows.
//
//   node tests/js/live-newer.mjs        (tests/test_live_newest.py runs it)
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { newerStamp, latestFirst } = await import(new URL("data.js", JS));

assert.equal(newerStamp("2026-11-12T17:24:02-05:00", "2026-11-12T17:19:47-05:00"), true);
assert.equal(newerStamp("2026-11-12T17:19:47-05:00", "2026-11-12T17:24:02-05:00"), false, "older count");
assert.equal(newerStamp("2026-11-12T22:19:47+00:00", "2026-11-12T17:24:02-05:00"), false, "older, other zone");
assert.equal(newerStamp("2026-11-12T17:24:02-05:00", "2026-11-12T17:24:02-05:00"), false, "same count");
assert.equal(newerStamp("", "2026-11-12T17:24:02-05:00"), false, "no count");
assert.equal(newerStamp("2026-11-12T17:24:02-05:00", ""), true, "first count");
// Latest visits: newest start first; the same minute by seq, the later one on top (#53).
const visits = [{ start: "2026-11-12T17:19", seq: 80 }, { start: "2026-11-12T17:22", seq: 86 },
  { start: "2026-11-12T17:22", seq: 87 }, { start: "2026-11-12T16:59", seq: 83 }];
assert.deepEqual(visits.slice().sort(latestFirst).map((v) => v.seq), [87, 86, 80, 83]);
// A drill-down's visits today say how old the count is (#53).
const { asOfWords } = await import(new URL("drillview.js", JS));
assert.match(asOfWords({ live: { generated_at: "2026-11-12T17:24:02-05:00" } }, { kind: "today" }), /^, as of \S+/);
assert.equal(asOfWords({ live: { generated_at: "2026-11-12T17:24:02-05:00" } }, { kind: "range" }), "", "whole days need none");
assert.equal(asOfWords({}, { kind: "today" }), "", "no count yet");
console.log("live newer: ok");
