// The visitor drawer's outcome (js/tabs/visitor.js), 2.13: a person search that found a
// lead says so even when it shows no visit (an email or a lead search): never "No lead
// linked" above a Leads table with one in it. Spam, duplicate and test leads do not count.
//
//   node tests/js/visitor-drawer.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { outcome } = await import(new URL("tabs/visitor.js", JS));

const person = (leads, conversions = []) => ({ visits: [], conversions, person: { leads }, firstKnown: true });
assert.equal(outcome(person([{ id: 14, status: "won" }])).words, "Lead #14");
assert.equal(outcome(person([{ id: 14 }, { id: 20 }])).words, "Lead #14 and 1 more");
assert.equal(outcome(person([{ id: 9, left_out: true }])).words, "No lead linked");
assert.equal(outcome(person([], [{ action: "signup", stage: "completed" }])).words, "1 conversion");
assert.ok(outcome(person([{ id: 14 }])).lead);
// A visit's own end still wins; with nothing linked it says so.
assert.equal(outcome({ visits: [{ endNode: { kind: "booked" } }], conversions: [], firstKnown: true }).words, "Booked a demo");
assert.equal(outcome({ visits: [], conversions: [], firstKnown: true }).words, "No lead linked");
console.log("visitor-drawer: all passed");

// 2.26: a conversion opened on its own, with no visit, says the stage it reached, never "no lead".
assert.equal(outcome({ visits: [], conversion: { id: 1 }, conversions: [{ stage: "completed", at: "2026-10-21T10:12:00Z" }, { stage: "paid", at: "2026-10-21T10:31:00Z" }], firstKnown: true }).words, "Paid");
