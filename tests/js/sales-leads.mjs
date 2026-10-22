// Leads & sales > Leads (2.20, js/tabs/sa-leads.js): the list of the period's leads, one
// row per lead. Names and emails are columns only when the helper's answer holds them (an
// owner or admin, on a site that keeps them); a viewer's table has no such columns at all.
// The count is the Leads figure, never a count of the rows; left-out rows only when asked;
// a row opens the visitor drawer with the lead's facts. dom-lite throws on a null child, so
// every view must append nothing for a missing value.
//
//   node tests/js/sales-leads.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "sales", name: "Leads & sales", tabs: [
  { route: "sales/leads", name: "Leads", keep: ["lact", "llabel", "lnow", "lby", "lshow", "lview", "lsplit"] },
  { route: "sales/summary", name: "Summary", keep: ["lsrc", "lact", "llabel", "lstage"] }] }]);
const { ME } = await import(new URL("access.js", JS));
const L = await import(new URL("tabs/sa-leads.js", JS));
const { viewSwitch } = await import(new URL("viewswitch.js", JS));
const sales = (await import(new URL("tabs/s-sales.js", JS))).default;
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const tick = () => new Promise((r) => setTimeout(r, 5));

// ---- the tab's name and the section's order
assert.deepEqual(sales.map((t) => t[1]), ["Leads", "Summary", "Sources", "Calendar bookings", "Funnels", "Events", "Find a person"]);
assert.equal(sales.find((t) => t[0] === "bookings")[1], "Calendar bookings", "the route stays sales/bookings");

// ---- the rows the options keep
const R = { kind: "history", first: "2026-10-19", last: "2026-10-20", length: 2, days: [] };
const rows = [
  { id: 1, at: "2026-10-20T10:00:00-04:00", action: "demo", now: "won", tool: "calendly", source: "Direct", left_out: null, name: "Avery Lane", email: "lead1@example.com" },
  { id: 2, at: "2026-10-19T09:00:00-04:00", action: "signup", now: "completed", tool: "site", source: "Search engine", left_out: null, label: "sales" },
  { id: 3, at: "2026-10-19T08:00:00-04:00", action: "contact", now: "spam", tool: "site", source: null, left_out: "spam" },
  { id: 4, at: "2026-10-12T08:00:00-04:00", action: "signup", now: "completed", tool: "site", source: "Direct", left_out: null },
];
assert.deepEqual(L.keepRows(rows, {}, R).map((x) => x.id), [1, 2], "the period's rows; left out hidden");
assert.deepEqual(L.keepRows(rows, { lshow: "out" }, R).map((x) => x.id), [1, 2, 3], "Show left out adds them");
assert.deepEqual(L.keepRows(rows, { lnow: "won" }, R).map((x) => x.id), [1]);
assert.deepEqual(L.keepRows(rows, { lby: "Search engine" }, R).map((x) => x.id), [2]);
assert.deepEqual(L.keepRows(rows, { llabel: "sales" }, R).map((x) => x.id), [2]);
assert.deepEqual(L.keepRows(rows, { lnow: "out", lshow: "out" }, R).map((x) => x.id), [3]);

// ---- the columns: Name and Email for an answer with names, none for one without
const labels = (cols) => cols.map((c) => c.label);
assert.deepEqual(labels(L.columnsFor(true)).slice(0, 3), ["When", "Name", "Email"]);
assert.ok(!labels(L.columnsFor(false)).includes("Name") && !labels(L.columnsFor(false)).includes("Email"), "no name or email column at all");
assert.deepEqual(labels(L.columnsFor(false)), ["When", "What", "Stage now", "From", "Reference", "Source", "First touch", "Landing page", "Country"]);
{
  // 2.25: the sender's own reference, hidden until Columns shows it, always in the CSV.
  const ref = L.columnsFor(false).find((c) => c.key === "ref");
  assert.equal(ref.hide, true, "hidden by default");
  assert.equal(ref.csvAlways, true, "in the CSV even while hidden");
  assert.equal(ref.csv({ ref: "u-119797" }), "u-119797");
  assert.equal(ref.csv({ ref: null }), "");
  assert.equal(text(ref.fmt(null, {})), "-");
}
{
  // A left-out row says so in its stage; a row without a label appends nothing (no "null").
  const stage = L.columnsFor(false).find((c) => c.key === "now");
  assert.match(text(stage.fmt(null, rows[2])), /Spam \(left out\)/);
  const what = L.columnsFor(false).find((c) => c.key === "action");
  assert.equal(text(what.fmt("signup", { action: "signup", label: null })), "Sign-up");
  assert.equal(text(what.fmt("signup", rows[1])), "Sign-upsales");
}

// ---- the tab: who asks for names, what the answer draws, the count beside it
const f = { available: true, finished: ["completed", "paid"], lead_actions: ["contact", "signup", "demo"], demo_actions: ["demo"], min_rate: 10,
  days: [{ day: "2026-10-19", state: "ok", stages: { signup: { completed: 1 } }, by: { source_type: { signup: { "Search engine": 1 } }, country: {} } },
    { day: "2026-10-20", state: "ok", stages: { demo: { completed: 1, won: 1 } }, by: { source_type: { demo: { Direct: 1 } }, country: {} } }] };
const m = { today: "2026-10-21", anchor: "2026-10-20", byDay: new Map(), x: { conversions: f }, days: [] };
const s = { tab: "sales/leads", range: "custom", from: "2026-10-19", to: "2026-10-20" };
const asked = [];
const answer = (names) => ({ ok: true, names, why: null, rows: rows.map((r) => (names ? r : { ...r, name: undefined, email: undefined })) });
globalThis.fetch = async (url) => { asked.push(String(url)); return { ok: true, status: 200, json: async () => answer(/names=1/.test(url)) }; };
async function draw(role) {
  ME.role = role;
  document.body.replaceChildren();
  const out = flat(L.default(m, s));
  document.body.append(...out);
  for (let i = 0; i < 10; i++) await tick();
  return out;
}
{
  const out = await draw("admin");
  assert.match(asked.at(-1), /people\/leads\?first=2026-10-19&last=2026-10-20&names=1/, "an admin asks for names");
  const line = out.find((el) => (el.className || "").includes("sa-figure"));
  assert.match(text(line), /^2 leads/, "the count is the Leads figure of the period");
  const view = out.find((el) => (el.className || "").includes("sa-view"));
  assert.ok(view.querySelector(".sk-grid"), "the list is a grid");
  assert.doesNotMatch(text(view), /names and emails show to admins/i);
}
{
  await draw("viewer");
  assert.match(asked.at(-1), /people\/leads\?first=2026-10-19&last=2026-10-20$/, "a viewer never asks for names");
  const view = document.body.querySelector(".sa-view");
  assert.match(text(view), /Names and emails show to admins and owners/);
}
{
  // The board: the same rows, in the column of their stage now, read-only.
  s.lview = "board";
  await draw("admin");
  const cols = document.body.querySelectorAll(".bd-col");
  assert.deepEqual(cols.map((c) => c.querySelector(".bd-h").textContent), ["New or open", "Won", "Lost", "Cancelled or no-show"]);
  assert.match(text(cols[1]), /Avery Lane/, "a won lead in Won, by name for an admin");
  assert.match(text(cols[0]), /Sign-up/);
  delete s.lview;
}

// ---- a lead opens the visitor drawer, with its facts
{
  // dom-lite has no dialog: a drawer opens as an element with "open".
  Element.prototype.showModal ||= function () { this.setAttribute("open", ""); };
  Element.prototype.close ||= function () { this.removeAttribute("open"); };
  const { openLead } = L;
  const d = await openLead({ ...rows[0], steps: [{ at: rows[0].at, action: "demo", stage: "completed", tool: "calendly" }], journey: [] });
  const shown = text(d?.el || document.body);
  assert.match(shown, /Avery Lane/);
  assert.match(shown, /lead1@example\.com/);
  assert.match(shown, /Won/);
}

// ---- the view switcher: one pressed, the address keeps the choice
{
  let picked = null;
  const sw = viewSwitch("Show leads as", "board", L.VIEWS, (k) => { picked = k; });
  const btns = sw.querySelectorAll("button");
  assert.equal(btns.length, 4);
  assert.deepEqual(btns.map((b) => b.getAttribute("aria-pressed")), ["false", "true", "false", "false"]);
  btns[2].click();
  assert.equal(picked, "timeline");
}
console.log("sales-leads: all passed");
