// The period's dates (release 2: skald/webapp/js/period-dates.js, data.js withToday,
// mode-compare.js): Include today on Summary and Pages, the two windows of a period and
// their words, the "On 15 Jan" examples, "before: not measured" when the earlier period was
// not counted (never 0, never a rise), "≈ about the same" for 3 or fewer, and inc / psort in
// the address with Back and Forward.
//
//   node tests/js/period.mjs        (tests/test_navigate_js.py runs it)
//
// Example data only: made-up days and figures.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
const H = { stack: [{ state: null, hash: "" }], at: 0 };
globalThis.history = {
  get state() { return H.stack[H.at].state; },
  pushState(state, _, hash) { H.stack.splice(H.at + 1); H.stack.push({ state, hash }); H.at += 1; location.hash = hash; },
  replaceState(state, _, hash) { H.stack[H.at] = { state, hash }; location.hash = hash; },
  // The state is read from the address (state.js read), so stepping is setting it back.
  back() { if (H.at > 0) { H.at -= 1; location.hash = H.stack[H.at].hash; } },
  forward() { if (H.at < H.stack.length - 1) { H.at += 1; location.hash = H.stack[H.at].hash; } },
  go() {},
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const P = await import(new URL("period-dates.js", JS));
const D = await import(new URL("data.js", JS));
const C = await import(new URL("mode-compare.js", JS));
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));

// ---- the brief's examples: on 15 Jan ------------------------------------------------
{
  const inc = P.windows("2027-01-15", 7, true);
  assert.deepEqual(inc, { a: { first: "2027-01-09", last: "2027-01-15" }, b: { first: "2027-01-02", last: "2027-01-08" } });
  assert.equal(`${P.span(inc.a.first, inc.a.last)} against ${P.span(inc.b.first, inc.b.last)}`, "9–15 Jan against 2–8 Jan");
  const whole = P.windows("2027-01-15", 7, false);
  assert.deepEqual(whole, { a: { first: "2027-01-08", last: "2027-01-14" }, b: { first: "2027-01-01", last: "2027-01-07" } });
  assert.equal(`${P.span(whole.a.first, whole.a.last)} against ${P.span(whole.b.first, whole.b.last)}`, "8–14 Jan against 1–7 Jan");
  // 30 days across a month and a year
  const w30 = P.windows("2027-01-15", 30, false);
  assert.equal(P.span(w30.a.first, w30.a.last), "16 Dec 2026–14 Jan 2027");
  assert.equal(P.span(w30.b.first, w30.b.last), "16 Nov–15 Dec");
  assert.equal(P.span("2026-10-29", "2026-11-04"), "29 Oct–4 Nov");
  assert.equal(P.span("2026-10-24", "2026-10-24"), "24 Oct");
}

// ---- the first full comparison: measured from 22 Oct (first whole day) ----------------
{
  const f = P.firstFull("2026-10-22", 7, false);
  assert.equal(f.on, "2026-11-05");
  assert.equal(`${P.span(f.a.first, f.a.last)} against ${P.span(f.b.first, f.b.last)}`, "29 Oct–4 Nov against 22–28 Oct");
  assert.equal(P.firstFull("2026-10-22", 7, true).on, "2026-11-04");
}

// ---- the change in words -------------------------------------------------------------
{
  assert.deepEqual(P.changeWords(75, 125), { text: "▼ 40%", dir: "down" });
  assert.deepEqual(P.changeWords(6, 2), { text: "▲ 200%", dir: "up" });
  assert.deepEqual(P.changeWords(28, 25), { text: "≈ about the same", dir: "same" });   // 3: about the same
  assert.deepEqual(P.changeWords(29, 25), { text: "▲ 16%", dir: "up" });
  assert.deepEqual(P.changeWords(5, 0), { text: "▲ new", dir: "up" });
  // Not measured: never a 0 and never a rise.
  const nm = P.changeWords(426, null);
  assert.equal(nm.text, "before: not measured");
  assert.equal(nm.dir, "none");
  assert.doesNotMatch(nm.text, /0|▲/);
  assert.equal(P.changeWords(10, 12, { state: "not_whole" }).text, "before: not complete");
}

// ---- a model: history from 21 Oct (a part day), today 25 Oct --------------------------
const day = (d, readers, state = "ok") => ({ day: d, state, readers, views: readers * 2, visits: readers, by: { source: { "Search engine": 2 } } });
const days = [day("2026-10-21", 40, "partial"), day("2026-10-22", 120), day("2026-10-23", 125), day("2026-10-24", 75)];
const m = { today: "2026-10-25", anchor: "2026-10-24", firstDay: "2026-10-21", byDay: new Map(days.map((d) => [d.day, d])), site: "example.com",
  live: { state: "ok", day: "2026-10-25", generated_at: "2026-10-25T10:54:00-04:00", from: "2026-10-25T00:00:00-04:00", figures: { readers: 28, views: 40, visits: 28 } }, x: {} };
const st = (o) => ({ tab: "overview/summary", range: "7d", inc: "", cmp: "", ...o });

{
  // Whole days: 18–24 Oct; Include today: 19–25 Oct, with today as one more day.
  const whole = D.rangeOf(m, st({}));
  assert.equal(`${whole.first}..${whole.last}`, "2026-10-18..2026-10-24");
  assert.ok(!whole.inc);
  const inc = D.rangeOf(m, st({ inc: "1" }));
  assert.equal(`${inc.first}..${inc.last}`, "2026-10-19..2026-10-25");
  assert.equal(inc.days.length, 7);
  const today = inc.days[6];
  assert.equal(today.live, true);
  assert.equal(today.state, "ok");
  assert.equal(D.total(inc.days).readers, 120 + 125 + 75 + 28);       // only whole days and today; 21 Oct is partial
  // The chart leaves today out.
  assert.ok(!D.chartDays(inc).some((d) => d.live));
  // Only Summary and Pages honour it; Yesterday and Custom ignore it.
  assert.ok(!D.rangeOf(m, st({ inc: "1", tab: "traffic/sources" })).inc);
  assert.ok(!D.rangeOf(m, st({ inc: "1", range: "yesterday" })).inc);
  assert.ok(D.rangeOf(m, st({ inc: "1", tab: "traffic/pages" })).inc);
  assert.ok(!D.rangeOf(m, st({ inc: "1", tab: "traffic/pages", page: "/a/" })).inc);
  // Today not whole: the day is left out and named, never zero.
  const held = D.rangeOf({ ...m, live: { ...m.live, state: "withheld" } }, st({ inc: "1" }));
  assert.equal(held.days[6].state, "withheld");
  assert.equal(D.total(held.days).readers, 320);
  // The words.
  const w = P.lineWords(inc, st({ inc: "1" }), { today: m.today, b: D.previousOf(m, inc) });
  assert.equal(w.now, "Last 7 days including today: 19–25 Oct");
  assert.equal(w.prev, "12–18 Oct");
  assert.match(w.how, /On 15 Jan that is 9–15 Jan against 2–8 Jan/);
  const ww = P.lineWords(whole, st({}), { today: m.today, b: D.previousOf(m, whole) });
  assert.equal(ww.now, "Last 7 whole days: 18–24 Oct");
  assert.equal(ww.prev, "11–17 Oct");
  assert.match(ww.how, /On 15 Jan that is 8–14 Jan against 1–7 Jan/);
  const y = D.rangeOf(m, st({ range: "yesterday" }));
  assert.equal(P.lineWords(y, st({ range: "yesterday" }), { b: D.previousOf(m, y) }).now, "Yesterday, Sat 24 Oct");
  assert.equal(P.lineWords(y, st({ range: "yesterday" }), { b: D.previousOf(m, y) }).prev, "Fri 23 Oct");
  const t = P.lineWords({ kind: "today" }, st({ range: "today" }), { live: m.live });
  assert.equal(`${t.now} compared with ${t.prev}`, "Today until 10:54 compared with yesterday until 10:54");
}

{
  // Compare: Yesterday against the day before compares (both whole).
  const cy = C.compareOf(m, st({ range: "yesterday", cmp: "prev" }));
  assert.equal(cy.ok, true);
  assert.equal(cy.bT.readers, 125);
  assert.equal(P.changeWords(75, cy.bT.readers).text, "▼ 40%");
  // 7 whole days against the 7 before: before history, so not measured, never 0.
  const c7 = C.compareOf(m, st({ cmp: "prev" }));
  assert.equal(c7.ok, false);
  assert.equal(P.beforeState(c7.b), "not_measured");
  const words = P.notMeasuredWords(D.rangeOf(m, st({})), st({}), { firstWhole: P.firstWholeDay(m.byDay, m.firstDay), site: "example.com", firstDay: m.firstDay });
  assert.match(words, /^Before: not measured\. 11–17 Oct was before example.com was measured \(measured from 21 Oct\)/);
  assert.match(words, /The first full 7 days against the 7 before is on 5 Nov \(29 Oct–4 Nov against 22–28 Oct\)\./);
  assert.doesNotMatch(words, /\b0\b|▲/);
  // Include today with Compare: never compared, and it says why.
  const ci = C.compareOf(m, st({ inc: "1", cmp: "prev" }));
  assert.equal(ci.ok, false);
  assert.equal(ci.inc, true);
  assert.match(ci.why, /Not compared while today is included/);
  assert.equal(`${ci.b.first}..${ci.b.last}`, "2026-10-12..2026-10-18");
}

// ---- the address: inc and psort, Back and Forward ----------------------------------------
{
  const keys = new Set(K.ROUTE_KEYS.map((k) => k.key));
  assert.ok(keys.has("inc") && keys.has("psort"));
  assert.equal(K.KEYS.get("inc").kind, "global");
  assert.equal(K.KEYS.get("psort").kind, "tab");
  for (const k of S.KNOWN()) assert.ok(keys.has(k), `${k} is listed in routekeys.js`);
  location.hash = "#overview/summary?range=7d";
  S.set({ inc: "1" });
  assert.match(location.hash, /[?&]inc=1/);
  assert.equal(S.read().inc, "1");
  S.set({ tab: "traffic/pages" });
  assert.match(location.hash, /^#traffic\/pages\?.*inc=1/);          // carried to Pages
  S.set({ psort: "rising" });
  assert.match(location.hash, /psort=rising/);
  S.set({ tab: "traffic/sources" });
  assert.doesNotMatch(location.hash, /psort/);                         // a Pages key stays on Pages
  history.back();
  assert.match(location.hash, /^#traffic\/pages\?.*psort=rising/);
  assert.equal(S.read().psort, "rising");
  history.back();
  assert.doesNotMatch(location.hash, /psort/);
  history.forward();
  assert.equal(S.read().psort, "rising");
  location.hash = "#overview/summary?range=7d&inc=yes";
  assert.equal(S.read().inc, "");                                     // only "1" counts
}

console.log("period: all passed");
