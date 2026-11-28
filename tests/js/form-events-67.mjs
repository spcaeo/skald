// SKALD-67 on Traffic › Events (tabs/events.js formNotes): under Form started → Form sent, one line
// saying Form sent counts presses of the send button, the forms Leads & sales received on the same
// verified days from the site's server or form tools (leadfigs.js formsOn: its checked by.tool, never
// the tag's own "beacon" rows, no demos), and what the tag counted before the version that tells a
// real form from a pop-up's close button. Hosts are example.com only.
//
//   node tests/js/form-events-67.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const EV = await import(new URL("tabs/events.js", JS));
const { setContext } = await import(new URL("tabs/common.js", JS));
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const find = (out, sel) => flat(out).flatMap((el) => (el.querySelectorAll ? [...(el.matches?.(sel) ? [el] : []), ...el.querySelectorAll(sel)] : []));
const go = (hash) => { location.hash = hash; return S.read(); };

const DAYS = ["2026-11-19", "2026-11-20", "2026-11-21"];
const rows = [
  ["2026-11-19", "form_start", "contact", "/contact/", "Search engine", 10], ["2026-11-19", "form_submit", "contact", "/contact/", "Search engine", 6],
  ["2026-11-20", "form_start", "contact", "/contact/", "Direct", 4], ["2026-11-20", "form_submit", "contact", "/contact/", "Direct", 2],
  ["2026-11-21", "scroll_75", "", "/", "Direct", 9],
];
const events = { events: [{ name: "form_start", label: "Form started" }, { name: "form_submit", label: "Form sent" }, { name: "scroll_75", label: "Read three quarters" }],
  sent: { form_start: 1, form_submit: 1, scroll_75: 1 }, first_day: "2026-11-01", rows,
  // 21 Nov did not pass the beacon's checks: its leads are not put beside it either.
  days: [{ day: "2026-11-19", state: "ok" }, { day: "2026-11-20", state: "ok" }, { day: "2026-11-21", state: "withheld" }] };
// Leads & sales' own checked days, by tool (finished rows only): 19 Nov 1 contact form from the
// lead hook, 4 "contact completed" from the tag itself (visitor IDs on: the Form sent presses
// again) and 1 demo; 20 Nov 1 sign-up from the lead hook; 21 Nov 5 (left out above).
const conversions = { schema_version: 1, available: true, lead_actions: ["contact", "signup", "waitlist", "trial", "demo"], demo_actions: ["demo"],
  set_up: { beacon: true, visitor_ids: true, hooks: ["lead", "calendly"], leads_db: false, store: true },
  days: [{ day: "2026-11-19", state: "ok", stages: { contact: { started: 9, completed: 5 }, demo: { completed: 1 } }, by: { tool: { contact: { lead: 1, beacon: 4 }, demo: { calendly: 1 } } } },
    { day: "2026-11-20", state: "ok", stages: { signup: { completed: 1 } }, by: { tool: { signup: { lead: 1 } } } },
    { day: "2026-11-21", state: "ok", stages: { contact: { completed: 5 } }, by: { tool: { contact: { lead: 5 } } } }] };
const model = (x) => ({ site: "example.com", today: "2026-11-22", anchor: "2026-11-21", firstDay: "2026-11-01", journeys: [],
  byDay: new Map(DAYS.map((d) => [d, { day: d, state: "ok", readers: 100 }])), x });
const render = (x, hash) => { const m = model(x); setContext(m, go(hash)); return flat(EV.default(m, S.read())); };
// One day for a whole page (the fake DOM draws no chart, and one day has none); formNotes itself for more.
const RANGE = "#traffic/events?range=custom&from=2026-11-19&to=2026-11-19";
const notes = (x, days, hash = "#traffic/events") => { const m = model(x); setContext(m, go(hash)); return flat(EV.formNotes(m, S.read(), days)); };
const say = (out, cls) => find(out, `.${cls}`).map((p) => p.textContent);

// 1. With a lead store: what Form sent counts, the leads of the same verified days, and the version note.
{
  const out = render({ events, conversions }, RANGE);
  const step = find(out, ".ev-step")[0];
  assert.match(step.textContent, /Form started10.*Form sent6/);
  const [sentNote] = say(out, "ev-sent");
  assert.match(sentNote, /Form sent counts presses of a form's send button, not forms received/);
  const [leads] = say(out, "ev-leads");
  assert.match(leads, /^Forms received: 1\. Forms your site's server or form tools reported/, "19 Nov: the hook's 1 contact form; not the tag's 4, not the demo, not the 9 started");
  // The tab passes the events' verified days only: 19 and 20 Nov, never 21 Nov (withheld) and its 5.
  const ok = [...EV.eventRows(events, { kind: "custom", first: "2026-11-19", last: "2026-11-21" }).ok].sort();
  assert.deepEqual(ok, ["2026-11-19", "2026-11-20"]);
  assert.match(say(notes({ events, conversions }, ok), "ev-leads")[0], /^Forms received: 2\./);
  assert.equal(find(out, ".ev-leads a")[0].getAttribute("href").split("?")[0], "#sales/summary");
  const [before] = say(out, "ev-before");
  assert.ok(before.includes(`Before Skald ${EV.FORMS_SINCE}, Form started and Form sent also counted a pop-up's close button, pickers and quizzes`));
  assert.match(EV.FORMS_SINCE, /^\d+\.\d+\.\d+$/);
  const tile = find(out, ".ev-did .ev-t").find((t) => t.querySelector(".ev-l").textContent === "Form sent");
  assert.match(tile.textContent, /Times a form's send button was pressed \(not forms received\)\./);
  const read = find(out, ".ev-did .ev-t").find((t) => t.querySelector(".ev-l").textContent === "Read three quarters");
  assert.match(read.textContent, /a page that fits on the screen never counts/);
}

// 2. A day the events passed but Leads & sales has not checked: said, never counted as 0.
{
  const conv = { ...conversions, days: [conversions.days[0], { day: "2026-11-20", state: "withheld" }, conversions.days[2]] };
  const [leads] = say(notes({ events, conversions: conv }, ["2026-11-19", "2026-11-20"]), "ev-leads");
  assert.match(leads, /^Forms received: 1 \(on 1 of the 2 days counted above: 20 Nov did not pass Leads & sales' checks\)\./);
  // A day Leads & sales has no row for (before its first day): named as not recorded, never 0.
  const late = { ...conversions, days: [conversions.days[1]] };
  const [two] = say(notes({ events, conversions: late }, ["2026-11-19", "2026-11-20"]), "ev-leads");
  assert.match(two, /^Forms received: 1 \(on 1 of the 2 days counted above: 19 Nov not recorded there\)\./);
}

// 3. No lead store, none of the days checked, or no hook that reports forms (visitor IDs on, so the
//    store holds only the tag's own rows; or a booking hook only): no line at all (unknown is not 0).
{
  assert.deepEqual(say(render({ events }, RANGE), "ev-leads"), []);
  const none = { ...conversions, days: [] };
  assert.deepEqual(say(render({ events, conversions: none }, RANGE), "ev-leads"), []);
  for (const hooks of [[], ["calendly"], ["stripe"]]) {
    const tagOnly = { ...conversions, set_up: { ...conversions.set_up, hooks } };
    assert.deepEqual(say(render({ events, conversions: tagOnly }, RANGE), "ev-leads"), [], `hooks ${hooks}`);
  }
  const db = { ...conversions, set_up: { ...conversions.set_up, hooks: [], leads_db: true } };
  assert.match(say(render({ events, conversions: db }, RANGE), "ev-leads")[0], /^Forms received: 1\./, "a lead database reports forms too");
  // A checked day with no by-tool breakdown (an older file): not counted, named as not recorded.
  const old = { ...conversions, days: [{ ...conversions.days[0], by: undefined }] };
  assert.deepEqual(say(notes({ events, conversions: old }, ["2026-11-19"]), "ev-leads"), [], "no checked breakdown: no figure");
  assert.equal(say(render({ events }, RANGE), "ev-sent").length, 1, "the send-button line stays");
}

// 4. A page or source filter: leads are for the whole site, so no figure, a line saying why.
{
  const [byPage] = say(render({ events, conversions }, `${RANGE}&path=%2Fcontact%2F`), "ev-leads");
  assert.match(byPage, /^Forms received is for the whole site/);
  assert.ok(!/Forms received: \d/.test(byPage));
  const [bySource] = say(render({ events, conversions }, `${RANGE}&source=Search%20engine`), "ev-leads");
  assert.match(bySource, /for the whole site/);
}

// 5. Today: the spool is not checked yet, so no leads line; the two other lines stay.
{
  const today = { ...events, today: { state: "ok", rows: [["form_start", "contact", "/contact/", "Direct", 2], ["form_submit", "contact", "/contact/", "Direct", 1]] } };
  const out = render({ events: today, conversions }, "#traffic/events?range=today");
  assert.equal(say(out, "ev-leads").length, 0);
  assert.equal(say(out, "ev-sent").length, 1);
  assert.equal(say(out, "ev-before").length, 1);
}

// 6. A site that never sent the form events: none of the three lines.
{
  const only = { ...events, sent: { scroll_75: 1 }, rows: rows.filter((x) => x[1] === "scroll_75"), events: events.events.filter((e) => e.name === "scroll_75") };
  const out = render({ events: only, conversions }, RANGE);
  assert.equal(find(out, ".ev-sent, .ev-leads, .ev-before").length, 0);
}

console.log("form-events-67: all passed");
