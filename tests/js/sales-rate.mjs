// #32, item 4: the completion rate, one rule on every Leads & sales tab (js/tabs/sa-rate.js).
// A rate is completions over starts, and only the page's script sees a start: so a rate is
// shown only where every completion came from the script too. Otherwise it says "not
// comparable", with one line why. 2.46.3 did this on Summary's table; #33 brings the old
// Calendar bookings onto Leads (What: Demos, its steps: sa-steps.js), whose "booked of opened"
// follows the same rule. Funnels never puts a lead or an event step over visits.
//
//   node tests/js/sales-rate.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { setContext } = await import(new URL("tabs/common.js", JS));
const R = await import(new URL("tabs/sa-rate.js", JS));
const ST = await import(new URL("tabs/sa-steps.js", JS));
const P = await import(new URL("tabs/sa-period.js", JS));
const PL = await import(new URL("tabs/sa-pipeline.js", JS));
const L = await import(new URL("tabs/sa-leads.js", JS));
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const flat = (out) => [out].flat(Infinity).filter(Boolean);

// ---- 1. the rule itself
assert.deepEqual(R.rateOf({ started: 20, done: 15, tools: { beacon: 15 } }), { rate: 0.75, words: "75%", why: "" }, "the script saw both: a rate");
assert.equal(R.rateOf({ started: 20, done: 30, tools: ["beacon"] }).words, "100%", "never over 100%");
const mixed = R.rateOf({ started: 25, done: 84, tools: { lead: 70, beacon: 14 } });
assert.deepEqual([mixed.rate, mixed.words], [null, R.NOT_COMPARABLE], "84 sign-ups from the server against 25 starts: not comparable");
assert.match(mixed.why, /^Starts are seen only by the page's script/, "with one line why");
assert.equal(R.rateOf({ started: 25, done: 3, tools: { calendly: 3 } }).words, R.NOT_COMPARABLE, "a booking tool's bookings too");
assert.equal(R.rateOf({ started: 25, done: 3, tools: { site: 3 } }).words, R.NOT_COMPARABLE, "the lead database's rows too");
assert.equal(R.rateOf({ started: 0, done: 3, tools: { beacon: 3 } }).words, "no starts seen");
assert.equal(R.rateOf({ started: 4, done: 3, tools: { beacon: 3 } }).words, "too few to say (4)");
assert.equal(R.rateOf({ started: 400, done: 1, tools: { beacon: 1 } }).words, "<1%");
assert.equal(R.mixedTools({ beacon: 3, lead: 0 }), false, "a tool with no completion does not count");

// ---- the fixture: one day, 22 Oct (today)
const TODAY = "2026-10-22";
const day = (stages, tool) => ({ day: TODAY, state: "ok", stages, abandoned: {}, labels: {}, labels_abandoned: {},
  by: { source_type: Object.fromEntries(Object.keys(stages).map((a) => [a, { Direct: stages[a].completed || 0 }])), tool }, visits_before: {}, time_to_convert: {}, assisted: null, likely_ai: {} });
const fileOf = (d) => ({ available: true, since: "2026-10-01", finished: ["completed", "paid"], lead_actions: ["contact", "signup", "demo"], demo_actions: ["demo"], min_rate: 10, abandon_hours: 24,
  dims: ["source_type", "tool"], days: [d], timeline: [], pages_before: null, period: { first: "2026-10-01", last: TODAY } });
const model = (f) => ({ site: "example.com", today: TODAY, anchor: "2026-10-21", firstDay: "2026-10-01", byDay: new Map(), views: [], journeys: [], options: {}, days: [], x: { conversions: f, events: null } });
const go = (hash) => { location.hash = hash; return S.read(); };

// ---- 2. Summary's table: the same rule, row by row
{
  const f = fileOf(day({ signup: { started: 25, completed: 84 }, contact: { started: 20, completed: 15 } }, { signup: { lead: 70, beacon: 14 }, contact: { beacon: 15 } }));
  const m = model(f);
  const s = go("#sales/summary?range=today");
  setContext(m, s);
  const out = flat(PL.summary(m, s, {}));
  const box = out.find((el) => el.querySelector?.("h2") && text(el.querySelector("h2")).startsWith("Each kind of lead"));
  const rows = box.querySelectorAll("tr").map(text);
  assert.match(rows.find((t) => t.startsWith("Sign-ups")), /not comparable/);
  assert.match(rows.find((t) => t.startsWith("Contact")), /75%/);
  const cell = box.querySelectorAll("span.few").find((x) => text(x) === R.NOT_COMPARABLE);
  assert.equal(cell.getAttribute("title"), R.WHY_NOT, "the cell says why on hover and to a screen reader");
  // #33: an old Sources link (lpart=sources) opens with where they came from first, fold open.
  const order = (st) => flat(PL.summary(m, st, {})).map((el) => text(el.querySelector?.("h2"))).filter((t) => /^(Each kind of lead|Where they came from)/.test(t)).map((t) => t.split(" ")[0]);
  assert.deepEqual(order(s), ["Each", "Where"], "the table first");
  const src = go("#sales/summary?range=today&lpart=sources");
  assert.deepEqual(order(src), ["Where", "Each"], "Sources' link: where they came from first");
  const fold = flat(PL.summary(m, src, {})).flatMap((el) => el.querySelectorAll?.("details") || []).find((d) => d.id === "sa-sources");
  assert.ok(fold && (fold.open || fold.hasAttribute("open")), "its fold open");
}

// ---- 3. Leads › What: Demos (the old Calendar bookings): the steps, booked of opened
{
  // Booked through Calendly: the page's script saw the starts, Calendly the bookings.
  const f = fileOf(day({ demo: { started: 30, completed: 6, cancelled: 1 }, signup: { completed: 2 } }, { demo: { calendly: 6 }, signup: { lead: 2 } }));
  const m = model(f);
  assert.equal(ST.isBooking(f, "demo"), true);
  assert.equal(ST.isBooking(f, "signup"), false, "a sign-up is not a booking: no steps strip");
  const r = P.salesRange(m, { range: "7d" });
  const got = ST.stepsOf(f, "demo", P.periodDays(m, r));
  assert.deepEqual(got.steps.map(([k, , v]) => [k, v]), [["started", 30], ["booked", 6], ["cancelled", 1]], "only the steps this site sends");
  const s = go("#sales/leads?lact=demo");
  setContext(m, s);
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true, names: false, rows: [] }) });
  const out = flat(L.default(m, s));
  const strip = out.find((el) => el.matches?.(".sa-steps"));
  assert.ok(strip, "What: Demos shows each step above the list");
  assert.match(text(strip), /Opened the booking30Booked6not comparableCancelled1/);
  assert.match(text(strip.querySelector(".note")), /Reported by Calendly\. .*Booked of opened: not comparable\. Starts are seen only by the page's script/);
  // The same strip from the page's script alone: its rate.
  const g = fileOf(day({ demo: { started: 30, completed: 6 } }, { demo: { beacon: 6 } }));
  const strip2 = flat(L.default(model(g), s)).find((el) => el.matches?.(".sa-steps"));
  assert.match(text(strip2), /Booked620% of opened/);
  // Another kind: no strip.
  assert.ok(!flat(L.default(m, go("#sales/leads?lact=signup"))).some((el) => el.matches?.(".sa-steps")));
  // Calendar bookings' Show left out (the tools' cancelled, removed and test conversions) is
  // Leads' Show left out now, of the kind chosen: never lost with the tab.
  const heads = (out) => flat(out).flatMap((el) => el.querySelectorAll?.("h2") || []).map(text);
  assert.ok(!heads(L.default(m, s)).some((t) => t.startsWith("Cancelled, removed and test")), "only when asked for");
  assert.ok(heads(L.default(m, go("#sales/leads?lact=demo&lshow=out"))).includes("Cancelled, removed and test: demos"));
  assert.ok(heads(L.default(m, go("#sales/leads?lshow=out"))).includes("Cancelled, removed and test conversions"));
}

// ---- 4. Funnels: lead and event steps are on their own scale, never a share of visits
{
  const src = (await import("node:fs")).readFileSync(new URL("tabs/funnels.js", JS), "utf8");
  assert.match(src, /Lead steps, on their own scale/);
  assert.match(src, /not a share of the visits above, never joined to them/);
  assert.match(src, /Beacon steps, on their own scale/);
}

console.log("sales-rate: all passed");
