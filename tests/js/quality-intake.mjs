// SKALD-34: Data quality says when the log endpoint refused posts on a day (quality.json
// `intake_refused`: {reason: count}; null when not recorded). Only a Worker's refused posts
// ("edge_limited") make a day worth a look: those records are lost, it never sends them
// again. Other refusals (a shipper that waits, a stranger's post with no token) show in the
// column and its hover only.
//
//   node tests/js/quality-intake.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const Q = await import(new URL("tabs/quality.js", JS));

const good = { day: "2026-11-18", state: "ok", verify: "ok", lines: 1000, unparsed: 0, audit: { state: "match" } };

// Counted, none refused; or not recorded: nothing to say.
assert.deepEqual(Q.grade({ ...good, intake_refused: {} }), ["green", []]);
assert.deepEqual(Q.grade({ ...good, intake_refused: null }), ["green", []]);

// A Worker's burst: lost, and said so.
let [g, why] = Q.grade({ ...good, intake_refused: { edge_limited: 1157 } });
assert.equal(g, "amber");
assert.deepEqual(why, ["1,157 edge posts refused at the log endpoint: those records are lost"]);
[, why] = Q.grade({ ...good, intake_refused: { edge_limited: 1 } });
assert.deepEqual(why, ["1 edge post refused at the log endpoint: those records are lost"]);

// Refusals that lose nothing (a shipper waits and sends again) or are noise (no token) do not grade.
assert.deepEqual(Q.grade({ ...good, intake_refused: { rate_limited: 3, no_token: 40 } }), ["green", []]);
[g, why] = Q.grade({ ...good, intake_refused: { rate_limited: 3, bad_token: 1, edge_limited: 2 } });
assert.equal(g, "amber");
assert.deepEqual(why, ["2 edge posts refused at the log endpoint: those records are lost"]);

// A day with no figures at all, whose every Worker post was refused: still said.
[g, why] = Q.grade({ day: "2026-11-19", state: "missing", intake_refused: { edge_limited: 90 } });
assert.equal(g, "amber");
assert.match(why[0], /^90 edge posts refused/);
assert.deepEqual(Q.grade({ day: "2026-11-19", state: "missing" }), ["none", []]);

// The column's words: a count, "0" for none, "not recorded" when not recorded.
assert.equal(Q.intakeWords({ edge_limited: 2, rate_limited: 1 }), "3");
assert.equal(Q.intakeWords({}), "0");
assert.equal(Q.intakeWords(null), "not recorded");

console.log("quality-intake: all passed");
process.exit(0);
