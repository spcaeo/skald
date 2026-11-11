// Leads & sales › Summary shows a payment (#26, 2.46.3): a Sales tile and, in "What people
// did", each action's Sales and Value from the day's revenue.by.action; the columns and
// tiles of stages a site never sends (starts, won, lost, cancelled, demos) are left off,
// and "Count from" is gone where there is no lead database. Shaped on freshlycited.com,
// 11 Nov 2026: 2 X-ray runs, 1 sign-up that paid $25.00 on its own reference, 1 activated.
//
//   node tests/js/summary-sales.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const P = await import(new URL("tabs/sa-pipeline.js", JS));
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const flat = (out) => [out].flat(Infinity).filter(Boolean);
function walk(el, pred) {
  if (!el || typeof el !== "object") return null;
  if (pred(el)) return el;
  for (const k of el.childNodes || []) { const got = walk(k, pred); if (got) return got; }
  return null;
}
const find = (nodes, pred) => { for (const el of nodes) { const got = walk(el, pred); if (got) return got; } return null; };
const all = (nodes, pred, out = []) => { const go = (el) => { if (!el || typeof el !== "object") return; if (pred(el)) out.push(el); for (const k of el.childNodes || []) go(k); }; nodes.forEach(go); return out; };

const usd = (net, sales, action) => ({ gross_minor: net, refunded_minor: 0, net_minor: net, sales, refunds: 0, new_customers: sales, renewals: 0,
  by: { source: { "Direct or unknown": { net_minor: net, sales } }, action: { [action]: { net_minor: net, sales } } } });
const today = { day: "2026-11-11", state: "ok", stages: { xray: { completed: 2 }, signup: { completed: 1 }, activated: { completed: 1 } }, abandoned: {}, labels: {}, labels_abandoned: {},
  by: { source_type: { xray: { "Direct or unknown": 2 }, signup: { "Direct or unknown": 1 }, activated: { Unknown: 1 } } },
  visits_before: {}, time_to_convert: {}, assisted: null, likely_ai: {}, revenue: { USD: usd(2500, 1, "signup") } };
const f = { available: true, finished: ["completed", "paid"], min_rate: 10, abandon_hours: 24, dims: ["source_type"], since: "2026-10-17",
  lead_actions: ["contact", "signup", "waitlist", "trial", "demo"], set_up: { hooks: ["lead"] }, currencies: { USD: 2 }, revenue_since: "2026-11-11",
  period: { first: "2026-10-17", last: "2026-11-11" }, timeline: [], pages_before: null, days: [today] };
const m = { today: "2026-11-12", anchor: "2026-11-11", byDay: new Map(), x: { conversions: f, events: null, leads: { available: false, error: "leads.db not set" } }, options: {}, days: [] };
const s = { tab: "sales/summary", lsrc: "", lact: "", llabel: "", range: "custom", from: "2026-11-11", to: "2026-11-11" };

{
  const out = flat(P.summary(m, s, {}));
  const words = out.map(text).join(" ");
  // The tiles: Leads and Sales; never Demos booked, Won or Lost on a site that sends none.
  const labels = all(out, (el) => (el.className || "") === "t-l").map(text);
  assert.deepEqual(labels, ["Leads", "Sales"], `tiles: ${labels}`);
  const sales = find(out, (el) => (el.className || "") === "tile" && text(el).startsWith("Sales"));
  assert.match(text(sales), /\$25\.00/, "the sale's value under its count");
  // The table: Action, Completed, Sales, Value; the sign-up carries its $25.00.
  const h2 = find(out, (el) => (el.tagName || "").toLowerCase() === "h2" && text(el).startsWith("What people did"));
  assert.ok(h2, "the actions table under its plain heading");
  const heads = all([h2.parentNode], (el) => (el.tagName || "").toLowerCase() === "th").map((el) => text(el).replace(/[↕▼▲]/g, "").trim());
  assert.deepEqual(heads, ["Action", "Completed", "Sales", "Value"], `columns: ${heads}`);
  const signup = all([h2.parentNode], (el) => (el.tagName || "").toLowerCase() === "tr").map(text).find((t) => t.startsWith("Sign-ups"));
  assert.match(signup, /^Sign-ups11\$25\.00$/, `the sign-up row: ${signup}`);
  assert.doesNotMatch(words, /Count from/, "no lead database: no Count from");
  assert.doesNotMatch(words, /not seen|no starts seen/, "no Started column on a site whose script records no starts");
}
{
  // Narrowed to X-ray: no sale of its own, so the sign-up's sale is not shown under it.
  const out = flat(P.summary(m, { ...s, lact: "xray" }, {}));
  const sales = find(out, (el) => (el.className || "") === "tile" && text(el).startsWith("Sales"));
  assert.match(text(sales), /^Sales.*0/, "X-ray made no sale");
  assert.doesNotMatch(text(sales), /\$25/);
}
{
  // A site that does send starts, won and a demo keeps those columns and tiles.
  const busy = { ...today, stages: { contact: { started: 12, completed: 10, won: 2 }, demo: { completed: 1 } }, revenue: undefined };
  const g = { ...f, days: [busy], set_up: { hooks: ["lead", "calendly"] } };
  const out = flat(P.summary({ ...m, x: { ...m.x, conversions: g } }, s, {}));
  const labels = all(out, (el) => (el.className || "") === "t-l").map(text);
  assert.deepEqual(labels, ["Leads", "Demos booked", "Won"], `tiles: ${labels}`);
  const h2 = find(out, (el) => (el.tagName || "").toLowerCase() === "h2" && text(el).startsWith("What people did"));
  const heads = all([h2.parentNode], (el) => (el.tagName || "").toLowerCase() === "th").map((el) => text(el).replace(/[↕▼▲]/g, "").trim());
  assert.deepEqual(heads, ["Action", "Started", "Completed", "Abandoned", "Completion rate", "Won"], `columns: ${heads}`);
}
{
  // Freshlycited's 30 days: 25 starts from the page's script, 84 sign-ups mostly from the
  // server: the clamped rate read 100%. A rate mixing the two roads is not given.
  const mixed = { ...today, stages: { signup: { started: 25, completed: 84 } }, abandoned: { signup: 9 },
    by: { source_type: {}, tool: { signup: { lead: 70, beacon: 14 } } }, revenue: undefined };
  const own = { ...today, day: "2026-11-10", stages: { contact: { started: 20, completed: 15 } }, abandoned: {},
    by: { source_type: {}, tool: { contact: { beacon: 15 } } }, revenue: undefined };
  const g = { ...f, days: [own, mixed] };
  const out = flat(P.summary({ ...m, x: { ...m.x, conversions: g } }, { ...s, from: "2026-11-10" }, {}));
  const h2 = find(out, (el) => (el.tagName || "").toLowerCase() === "h2" && text(el).startsWith("What people did"));
  const rows = all([h2.parentNode], (el) => (el.tagName || "").toLowerCase() === "tr").map(text);
  const signup = rows.find((t) => t.startsWith("Sign-ups")), contact = rows.find((t) => t.startsWith("Contact"));
  assert.match(signup, /not comparable/, `mixed roads: no rate (${signup})`);
  assert.doesNotMatch(signup, /100/, "never the clamped 100%");
  assert.match(contact, /75(\.0)?%/, `script-only: its rate (${contact})`);
}
{
  // Calendar bookings on a day with five other conversions and no booking (#27): it says
  // "No booking", never "No conversion".
  const B = await import(new URL("tabs/sa-bookings.js", JS));
  const words = flat(B.default(m, { ...s, tab: "sales/bookings" }, {})).map(text).join(" ");
  assert.match(words, /No booking in this range\./, "no booking said plainly");
  assert.doesNotMatch(words, /No conversion in this range/);
  // The sign-up's sale is not a booking's: never shown on Calendar bookings.
  assert.doesNotMatch(words, /\$25|Sign-ups/, "another action's sale is not a booking's");
  assert.match(words, /Every stage/, "the stage table keeps its section");
}
console.log("summary-sales: all passed");
