// SKALD-61: Yesterday next to Today, and what it says before and after the day is stored.
//
// Seen live on 26 Nov at 02:40 New York time: Yesterday said "0 whole days recorded, 1 not
// ... 1 was not collected" on every site (the day was stored only at 07:15), and Leads &
// sales said the same of a day its own 7 days called "whole, verified". Now close-day
// stores yesterday soon after midnight; until then the page says it is not counted yet;
// once stored, the period line says when ("counted 6 Oct 00:24 ..."); and a Leads & sales
// tab names its days from the lead store, as its 7 days do.
//
//   node tests/js/yesterday.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const C = await import(new URL("tabs/common.js", JS));
const { rangeOf } = await import(new URL("data.js", JS));
const { leadsPeriod } = await import(new URL("tabs/sa-options.js", JS));
const P = await import(new URL("tabs/sa-period.js", JS));

const TODAY = "2026-10-06", YDAY = "2026-10-05";
const iso = (k) => new Date(Date.UTC(2026, 8, 30) + k * 864e5).toISOString().slice(0, 10);   // iso(0) = 30 Sep
const model = (stored) => {
  const byDay = new Map();
  for (let i = 0; i < 5; i += 1) byDay.set(iso(i), { day: iso(i), state: "ok", readers: 3 });  // to 4 Oct
  if (stored) byDay.set(YDAY, { day: YDAY, state: "ok", readers: 4, counted_at: "2026-10-06T00:24-04:00" });
  // The lead store has every day to today, yesterday included, before the log's day is stored.
  const days = [];
  for (let i = 0; i <= 6; i += 1) days.push({ day: iso(i), state: "ok", stages: iso(i) === YDAY ? { contact: { completed: 1 } } : {}, abandoned: {}, labels: {}, labels_abandoned: {}, by: {}, visits_before: {}, time_to_convert: {}, assisted: null, likely_ai: {} });
  const f = { available: true, since: iso(0), finished: ["completed"], lead_actions: ["contact"], demo_actions: [], dims: [], days, timeline: [], today: { day: TODAY, state: "ok", total: 0, rows: [], periods: [] } };
  return { site: "example.com", today: TODAY, anchor: YDAY, firstDay: iso(0), byDay, views: [], journeys: [], options: {}, days: [...byDay.values()], live: { day: TODAY, state: "ok" }, x: { conversions: f } };
};
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);

// ---- 1. the bar: Yesterday is a button of the group, More keeps All time and Custom
{
  const main = readFileSync(new URL("main.js", JS), "utf8");
  assert.match(main, /const MAIN_RANGES = \["yesterday", "7d", "30d", "90d"\];/);
  assert.match(main, /title: "All time, or your own dates" \}/);
  const order = S.RANGES.map(([k]) => k);
  assert.deepEqual(order.slice(0, 5), ["today", "yesterday", "7d", "30d", "90d"], "Today, Yesterday, 7, 30, 90 in that order");
  assert.deepEqual(order.filter((k) => k !== "today" && !["yesterday", "7d", "30d", "90d"].includes(k)), ["all", "custom"], "More: All time and Custom");
}

// ---- 2. before close-day has stored it: "not counted yet", never "not collected"
{
  const m = model(false), s = { range: "yesterday", tab: "traffic/visitors" };
  C.setContext(m, s);
  const r = rangeOf(m, s);
  assert.deepEqual([r.first, r.days[0].state], [YDAY, "missing"]);
  const words = text(C.nothing(m, r, "visits"));
  assert.match(words, /^Yesterday, Mon 5 Oct 2026, is not counted yet\. It is stored when the day closes after midnight, or at the latest by the morning run, which counts it again\./);
  assert.match(words, /no visits are shown rather than zeros/);
  assert.match(words, /Show today so far/);
  assert.doesNotMatch(words, /not collected/);
  assert.equal(C.countedWords(r), "");
  // An older day the log never had keeps its own words.
  const old = rangeOf(m, { range: "custom", from: "2026-09-20", to: "2026-09-20" });
  assert.match(text(C.nothing(m, old, "visits")), /was not collected/);
}

// ---- 3. stored: the period line says when it was counted
{
  const m = model(true), s = { range: "yesterday", tab: "traffic/visitors" };
  C.setContext(m, s);
  const r = rangeOf(m, s);
  assert.match(C.countedWords(r), /^counted 6 Oct \d\d:\d\d/);
  const line = C.periodWords(r, { complete: true, ok: 1 });
  assert.match(line, /^Mon 5 Oct 2026 · every day whole and verified · counted 6 Oct \d\d:\d\d/);
  // A longer range does not say it: its days were counted at different times.
  assert.equal(C.countedWords(rangeOf(m, { range: "7d" })), "");
}

// ---- 4. Leads & sales names its days from the lead store, as its 7 days do
{
  const m = model(false);
  location.hash = "#sales/leads?range=yesterday";
  const s = S.read();
  C.setContext(m, s);
  const r = P.salesRange(m, s);
  assert.equal(leadsPeriod(m, s, r), "Mon 5 Oct 2026 · every day whole and verified",
    "the lead store has yesterday, whatever the log's day says");
  assert.equal(leadsPeriod(m, { ...s, tab: "traffic/visitors" }, r), undefined, "Leads & sales only");
  assert.equal(leadsPeriod(m, s, P.salesRange(m, { ...s, range: "7d" })), undefined, "a live period keeps its own words");
  // An older custom period of exactly 7 days is its dates, not "Last 7 days" (review, SKALD-61).
  const c = P.salesRange(m, { ...s, range: "custom", from: "2026-09-28", to: "2026-10-04" });
  assert.equal(c.length, 7);
  const words = leadsPeriod(m, { ...s, range: "custom" }, c);
  assert.doesNotMatch(words, /Last 7 days/);
  assert.match(words, /^\w{3} \d+ \w{3} to \w{3} \d+ \w{3}, 7 days · /);
}

console.log("yesterday: all passed");
