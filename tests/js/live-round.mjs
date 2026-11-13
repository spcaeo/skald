// The footer's "next" follows the measured gap between live counts (#54): data.js nextWords.
// A round of many sites takes minutes, so "any moment" only once that time has passed.
//
//   node tests/js/live-round.mjs        (tests/test_live_round.py runs it)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { nextWords } = await import(new URL("data.js", JS));

const at = "2026-11-12T17:24:00-05:00", t = Date.parse(at);
const L = { generated_at: at, every_s: 360 };
assert.equal(nextWords(L, t), "next in about 6 min", "a 6-minute round");
assert.equal(nextWords(L, t + 4 * 60000), "next in about 2 min", "4 minutes in: not yet any moment");
assert.equal(nextWords(L, t + 5.9 * 60000), "next in about 1 min", "never less than 1 min while waiting");
assert.equal(nextWords(L, t + 6 * 60000 + 1000), "next any moment", "only once the round has passed");
// Unknown: the plan, 2 minutes.
assert.equal(nextWords({ generated_at: at }, t), "next in about 2 min");
assert.equal(nextWords({ generated_at: at, every_s: null }, t + 2 * 60000 + 1000), "next any moment");
assert.equal(nextWords({ generated_at: at, every_s: 0 }, t + 60000), "next in about 1 min", "zero is unknown");
// The footer says it, never the old fixed two minutes.
const main = readFileSync(new URL("main.js", JS), "utf8");
assert.ok(main.includes("nextWords(L)"), "the footer uses nextWords");
assert.ok(!main.includes("+ 120000"), "no fixed two-minute countdown");
console.log("live round: ok");
