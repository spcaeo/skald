// A funnel's lead steps on a site without a lead database (#25, 2.46.4): counted from the
// leads the site's server sent (conversions.json's checked day counts), each lead once,
// on the funnel's visit days; a day not checked is left out; with a starting source the
// step is not split. Shaped on freshlycited.com, 4-11 Nov 2026.
//
//   node tests/js/funnel-leads.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const L = await import(new URL("tabs/funnel-leads.js", JS));
const F = await import(new URL("tabs/funnels.js", JS));

const day = (d, stages, state = "ok") => ({ day: d, state, stages });
const f = { available: true, days: [
  day("2026-11-10", { xray: { completed: 3 }, signup: { started: 2, completed: 1 } }),
  // The sign-up that paid: one lead (the repeat finish is out of the day counts).
  day("2026-11-11", { xray: { completed: 2 }, signup: { completed: 1 }, activated: { completed: 1 } }),
  day("2026-11-09", { signup: { completed: 9 } }, "withheld"),
] };
const days = ["2026-11-09", "2026-11-10", "2026-11-11"];

assert.deepEqual(L.toolLeads(f, ["signup", "contact", "waitlist"], days, ""), { n: 2, days: 2, of: 3 }, "a withheld day is left out");
assert.deepEqual(L.toolLeads(f, ["xray"], days, ""), { n: 5, days: 2, of: 3 }, "any action the site sent");
assert.equal(L.toolLeads(f, ["signup"], days, "Search engine"), null, "not split by a visit's source");
assert.equal(L.toolLeads({ available: false }, ["signup"], days, ""), null);
assert.equal(L.toolLeads(f, ["signup"], ["2026-11-01"], ""), null, "no checked day: nothing to add up");
assert.equal(L.neverSent(f, ["demo_booked"]), true);
assert.equal(L.neverSent(f, ["signup"]), false);
assert.deepEqual(L.sentActions(f).map(([a]) => a), ["xray", "signup", "activated"]);
assert.equal(L.leadName("xray"), "Xray");
assert.equal(L.leadName("demo_booked"), "Demo booked");

// The link keeps an action as a lead step; a malformed one is dropped.
assert.deepEqual(F.parse("* > lead:xray,signup > lead:Bad!")[1], { kind: "lead", types: ["xray", "signup"] });
assert.equal(F.parse("* > lead:Bad!").length, 1);
assert.equal(F.glob(F.parse("* > ~sign-up > lead:signup")), "* > ~sign-up > lead:signup");

// No lead database: a step the site never sent says so, never 0.
const m = { x: { leads: { available: false, error: "leads.db not set" }, conversions: f, events: null } };
assert.match(F.unsentStep(m, { kind: "lead", types: ["demo_booked"] }), /never sent demo booked/);
assert.equal(F.unsentStep(m, { kind: "lead", types: ["signup"] }), null);
console.log("funnel-leads: all passed");

// The whole page: freshlycited's default funnel on 10-11 Nov, no lead database. Its lead
// step reads the two sign-ups the site sent, "leads your site sent", never "not recorded".
{
  const steps = [
    { label: "Landed", kind: "path", match: "starts_with", paths: ["/"] },
    { label: "Sign-up, contact or early-access page", kind: "path", match: "segment", paths: ["signup", "sign-up"] },
    { label: "Lead: sign-up, contact or early access", kind: "lead", types: ["signup", "contact", "waitlist"] }];
  const result = { first: "2026-11-10", last: "2026-11-11", visits: 2, steps: [{ n: 2 }, { n: 1 }, { n: null }] };
  const j = (d, pages) => ({ day: d, source: "Direct or unknown", landing: pages[0], trail: pages.map((p) => ({ path: p })) });
  const page = { ...m, today: "2026-11-11", anchor: "2026-11-10", journey_days: 7, byDay: new Map(), options: {}, days: [],
    journeys: [j("2026-11-10", ["/", "/sign-up"]), j("2026-11-11", ["/pricing-guide"])],
    x: { ...m.x, funnels: { funnels: [{ name: "Landing to lead", saved_by: "default", source: null, steps, result, long: null, history: null }] } } };
  const out = [F.default(page, { tab: "sales/funnels", range: "7d" })].flat(Infinity).filter(Boolean);
  const words = out.map((el) => (typeof el === "string" ? el : el.textContent)).join(" ");
  assert.match(words, /leads your site sent/, "the step says where its count comes from");
  assert.match(words, /count the leads your site sent on the same days, each lead once/);
  assert.doesNotMatch(words, /counted once saved/);
  console.log("funnel-leads: page passed");
}
