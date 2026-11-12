// The page takes a refreshed count only when it is later (#50): data.js newerStamp.
// An overlapping run could write a file drawn from an older count; the open page
// must keep the newer one it already shows.
//
//   node tests/js/live-newer.mjs        (tests/test_live_newest.py runs it)
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { newerStamp } = await import(new URL("data.js", JS));

assert.equal(newerStamp("2026-11-12T17:24:02-05:00", "2026-11-12T17:19:47-05:00"), true);
assert.equal(newerStamp("2026-11-12T17:19:47-05:00", "2026-11-12T17:24:02-05:00"), false, "older count");
assert.equal(newerStamp("2026-11-12T22:19:47+00:00", "2026-11-12T17:24:02-05:00"), false, "older, other zone");
assert.equal(newerStamp("2026-11-12T17:24:02-05:00", "2026-11-12T17:24:02-05:00"), false, "same count");
assert.equal(newerStamp("", "2026-11-12T17:24:02-05:00"), false, "no count");
assert.equal(newerStamp("2026-11-12T17:24:02-05:00", ""), true, "first count");
console.log("live newer: ok");
