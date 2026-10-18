// "Vs yesterday at this hour" as the page reads it (skald/webapp/js/by-now.js):
// a figure not recorded is never a fall to zero; a series is drawn only when its
// hours add up to the figure beside it.
//
//   node tests/js/by-now.mjs
import assert from "node:assert/strict";
import { comparisons, delta, running, arrived } from "../../skald/webapp/js/by-now.js";

const z = () => Array(24).fill(0);
const hours = (pairs) => { const a = z(); for (const [k, v] of pairs) a[k] = v; return a; };

const live = {
  state: "ok",
  by_now: {
    state: "ok", day: "2026-10-17", until: "2026-10-17T14:33:00-04:00", visitors: 31, pages: 65, ai_visitors: 4,
    hours: { visitors: hours([[9, 11], [14, 20]]), pages: hours([[9, 30], [14, 35]]), ai_visitors: hours([[10, 4]]) },
    today_hours: { visitors: hours([[9, 20], [14, 29]]), pages: hours([[10, 101]]), ai_visitors: hours([[11, 4]]) },
  },
};
const conv = { today: { state: "ok", by_now: { state: "ok", until: "2026-10-17T14:33:10-04:00", leads: 2, hours: hours([[8, 1], [10, 1]]), today_hours: hours([[3, 2], [12, 2]]) } } };

// ---- the four, with today's figures as the tiles show them
{
  const cs = comparisons(live, conv, { visitors: 49, pages: 101, leads: 4, ai: 5 });
  const by = Object.fromEntries(cs.map((c) => [c.key, c]));
  assert.deepEqual(cs.map((c) => c.key), ["visitors", "pages", "leads", "ai"]);
  assert.equal(by.visitors.yesterday, 31);
  assert.equal(by.visitors.at, "14:33");
  assert.equal(by.leads.yesterday, 2);
  assert.ok(by.visitors.hoursToday && by.visitors.hoursYesterday, "both series add up");
  assert.equal(by.ai.hoursToday, null, "today's AI hours sum to 4, the tile says 5: not drawn");
  assert.ok(by.ai.hoursYesterday, "yesterday's still adds up");
  assert.equal(by.ai.yesterday, 4);
}

// ---- yesterday not recorded: never zero
for (const state of ["withheld", "partial", "empty"]) {
  const L = { state: "ok", by_now: { state, until: "2026-10-17T14:33:00-04:00", visitors: null, pages: null, ai_visitors: null, hours: null, today_hours: null } };
  const [v] = comparisons(L, null, { visitors: 49 });
  assert.equal(v.yesterday, null, state);
  assert.ok(v.why.length > 0, state);
  assert.equal(delta(v.today, v.yesterday), null, "no change is said");
}
{
  const [, , leads] = comparisons(live, { today: { state: "ok", by_now: { state: "not_recorded", until: "2026-10-17T14:33:00-04:00", leads: null } } }, { leads: 4 });
  assert.equal(leads.yesterday, null);
  assert.match(leads.why, /not recorded/);
  const [v] = comparisons({ state: "withheld" }, null, { visitors: null });
  assert.equal(v.yesterday, null, "today withheld: nothing compared");
  const page = comparisons({ state: "ok" }, null, { visitors: 3 })[0];
  assert.match(page.why, /not counted for this page/, "a page group's page has no by_now");
}

// ---- the change in words
assert.deepEqual(delta(214, 182), { dir: "up", text: "+18%" });
assert.deepEqual(delta(80, 100), { dir: "down", text: "−20%" });
assert.deepEqual(delta(5, 3), { dir: "up", text: "+2" }, "under 10 yesterday: a count");
assert.deepEqual(delta(3, 3), { dir: "same", text: "same" });
assert.deepEqual(delta(1, 0), { dir: "up", text: "+1" });
assert.deepEqual(delta(1001, 1000), { dir: "same", text: "about the same" });
assert.equal(delta(null, 3), null);

// ---- the running total: from midnight to the time itself, ending at the figure
{
  const pts = running(hours([[9, 11], [14, 20]]), "14:33");
  assert.deepEqual(pts[0], [0, 0]);
  assert.deepEqual(pts[pts.length - 1], [14 + 33 / 60, 31]);
  assert.deepEqual(pts[10], [10, 11]);
  assert.equal(pts.length, 16);
  assert.equal(running(hours([[15, 1]]), "14:33"), null, "a count after the time itself: not drawn");
  assert.equal(running(null, "14:33"), null);
  assert.equal(running(z(), "bad"), null);
}

// ---- arrivals in the last minutes
assert.equal(arrived([{ started: 1 }, { started: 2 }, { started: 0 }, { started: 1 }, { started: 1 }, { started: 3 }]), 7);
assert.equal(arrived([]), 0);

console.log("by-now ok");
