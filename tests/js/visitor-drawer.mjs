// The visitor drawer's outcome (js/tabs/visitor.js), 2.13: a person search that found a
// lead says so even when it shows no visit (an email or a lead search): never "No lead
// linked" above a Leads table with one in it. Spam, duplicate and test leads do not count.
//
//   node tests/js/visitor-drawer.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { outcome, linkedCount } = await import(new URL("tabs/visitor.js", JS));

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

// #27: one lead with a sign-up and a payment on its reference is one, not three.
const steps = [{ tool: "lead", external_ref: "u_1", action: "signup", stage: "completed" }, { tool: "lead", external_ref: "u_1", action: "signup", stage: "paid" }];
assert.equal(linkedCount({ leads: [], conversions: steps }), 1);
assert.equal(linkedCount({ leads: [], conversions: steps, ref: { ref: "u_1", tool: "lead", steps } }), 1);
assert.equal(linkedCount({ leads: [{ lead: 4 }], conversions: [...steps, { tool: "beacon", action: "contact", stage: "completed" }] }), 3);
console.log("visitor-drawer: linked count passed");

// #66: a visit the end of the day cut in two is drawn as one, its parts' figures left alone.
const { joinMidnight } = await import(new URL("tabs/visitor.js", JS));
const { journeyMap } = await import(new URL("journeymap.js", JS));
const part = (day, seq, start, stop, paths, extra = {}) => ({
  kind: "kept", day, seq, start, stop, source: extra.source || "Direct or unknown", via: "",
  trail: paths.map(([path, at, page = true]) => ({ path, page, at, times: 1 })), pages: paths.filter((p) => p[2] !== false).length,
  seconds: Math.round((Date.parse(stop) - Date.parse(start)) / 1000), posted: !!extra.posted, nf: false, active: false,
  raw: { start, pages: paths.length, trail: paths.map(([p, at, page = true]) => [p, page ? "page" : "app", at]), continues: extra.continues },
});
// 23:50 New York on 15 Nov (04:50 UTC), then 00:00 and 00:10 on 16 Nov; and a visit on 14 Nov.
const before = part("2026-11-15", 7, "2026-11-16T04:50:00Z", "2026-11-16T04:50:01Z", [["/", 0]]);
const after = part("2026-11-16", 0, "2026-11-16T05:00:00Z", "2026-11-16T05:10:00Z", [["/features/", 0], ["/pricing/", 600]],
  { source: "This site", continues: ["2026-11-15", 7], posted: true });
const older = part("2026-11-14", 2, "2026-11-14T15:00:00Z", "2026-11-14T15:05:00Z", [["/blog/", 0], ["/contact/", 300]]);
const joined = joinMidnight([after, before, older]);
assert.equal(joined.length, 2, "three kept rows, two visits: the midnight pair is one");
const one = joined.find((v) => v.midnight);
assert.equal(one.start, before.start, "starts when the visit started, before midnight");
assert.equal(one.stop, after.stop, "ends when its part after midnight ended");
assert.equal(one.source, "Direct or unknown", "its source is the visit's own, not \"This site\"");
assert.deepEqual(one.trail.map((p) => [p.path, p.at, !!p.midnight]),
  [["/", 0, false], ["/features/", 600, true], ["/pricing/", 1200, false]],
  "one trail, its offsets from the first part's start, the step after midnight marked");
assert.equal(one.pages, 3);
assert.equal(one.seconds, 1200);
assert.ok(one.posted, "a form sent after midnight belongs to the visit");
assert.deepEqual(one.parts.map((r) => r.start), [before.start, after.start], "both parts kept, for their leads");
assert.equal(one.raw.trail.length, 3, "the header's page count reads both parts");
assert.ok(!joined.find((v) => v.day === "2026-11-14").midnight, "a visit on another day stays as it is");
// Without the mark, nothing is joined: two visits, as counted.
assert.equal(joinMidnight([{ ...after, raw: { ...after.raw, continues: undefined } }, { ...before }]).length, 2);
// Three days: a visit that went on past two midnights is one.
const third = part("2026-11-17", 0, "2026-11-17T05:00:00Z", "2026-11-17T05:01:00Z", [["/docs/", 0]], { source: "This site", continues: ["2026-11-16", 0] });
const chain = joinMidnight([part("2026-11-15", 7, before.start, before.stop, [["/", 0]]), { ...after, raw: { ...after.raw } }, third]);
assert.equal(chain.length, 1);
assert.deepEqual(chain[0].trail.map((p) => p.path), ["/", "/features/", "/pricing/", "/docs/"]);
// Drawn: one card, tagged, the line where the day changed says so.
const el = journeyMap([{ ...one, endNode: { kind: "form", words: "sent a form" } }]).el;
assert.ok(el.textContent.includes("continued past midnight"), "the card is tagged");
const lines = [...el.querySelectorAll(".jm-t")].map((e) => e.textContent);
// #62: past a visit's first minute times are kept to 10 s, so a gap reads "about".
assert.deepEqual(lines, ["about 10 min · past midnight", "about 10 min"]);
console.log("visitor-drawer: midnight passed");

// SKALD-18: "First seen 16 Nov" beside "First came from Direct, 26 days ago". The visits shown
// are those linked here and still kept; the first touch is kept longer and may be a visit from
// another address. First seen is the older of the two, and the sentence says that visit is not
// among those shown. Times are whole UTC instants, so the drawer's zone does not move the day.
const { firstSeen, stateLine } = await import(new URL("tabs/visitor.js", JS));
const kept = (start) => ({ kind: "kept", start, source: "Direct or unknown", via: "", trail: [], raw: {} });
const shownVisits = [kept("2026-11-17T15:00:00Z"), kept("2026-11-16T15:03:00Z"), kept("2026-11-16T18:00:00Z")];
const touched = { visits: shownVisits, firstKnown: true, leads: [], conversions: [],
  firstTouch: { by: "vid", day: "2026-10-22", start: "2026-10-22T14:00:00Z", source: "Direct or unknown", via: "" } };
const fs = firstSeen(touched);
assert.equal(fs.day, "2026-10-22", "the first touch is older than every visit shown");
assert.ok(fs.touch);
assert.match(fs.words, /^22 Oct/);
assert.match(stateLine(touched), /^3 visits over 2 days\. First came from Direct, \d+ days ago \(that visit is not shown here\)\.$/);
// By the 30-day hash: a day, no time.
const byHash = { ...touched, firstTouch: { by: "hash", day: "2026-10-22", start: null, source: "Search", via: "" } };
assert.equal(firstSeen(byHash).words, "22 Oct");
// The first touch is the oldest visit shown (the usual case): nothing added.
const same = { ...touched, firstTouch: { by: "vid", day: "2026-11-16", start: "2026-11-16T15:03:00Z", source: "Direct or unknown", via: "" } };
assert.equal(firstSeen(same).touch, false);
assert.equal(firstSeen(same).day, "2026-11-16");
assert.ok(!stateLine(same).includes("not shown"));
// No first touch linked ("none", "off"), or none at all: the oldest visit shown.
for (const ft of [{ by: "none" }, { by: "off" }, undefined]) {
  const m = { ...touched, firstTouch: ft };
  assert.equal(firstSeen(m).day, "2026-11-16");
  assert.ok(!stateLine(m).includes("not shown"));
}
assert.equal(firstSeen({ visits: [], firstTouch: undefined }), null);
// The reader's zone is not the site's (the review of SKALD-18). A first touch's `day` is the
// site's day and its `start` the site's wall time: compared as instants, or as site days.
const { setZone } = await import(new URL("tz.js", JS));
setZone("utc", "America/New_York");
// One visit at 21:00 New York on 16 Nov (02:00 UTC on the 17th), and it is the first touch.
const ny = { visits: [kept("2026-11-17T02:00:00Z")], firstKnown: true, leads: [], conversions: [],
  firstTouch: { by: "vid", day: "2026-11-16", start: "2026-11-16T21:00", source: "Direct or unknown", via: "" } };
assert.equal(firstSeen(ny).touch, false, "the same visit: shown, so never 'not shown here'");
assert.ok(!stateLine(ny).includes("not shown"));
assert.equal(firstSeen({ ...ny, firstTouch: { ...ny.firstTouch, by: "hash", start: null } }).touch, false, "by its site day too");
// A first touch's start is kept to the minute: the visit that started at 21:00:40 is the one
// whose first touch says 21:00 (found in the demo build: "not shown here" beside that very visit).
const secs = { ...ny, visits: [kept("2026-11-17T02:00:40Z")] };
assert.equal(firstSeen(secs).touch, false, "the same minute is the same visit");
assert.equal(firstSeen({ ...secs, firstTouch: { ...ny.firstTouch, start: "2026-11-16T20:59" } }).touch, true, "a minute before is older");
// A first touch an hour earlier the same evening: older, by its time.
assert.equal(firstSeen({ ...ny, firstTouch: { ...ny.firstTouch, start: "2026-11-16T20:00" } }).touch, true);
// A site ahead of UTC: the visit at 20:00 UTC on 16 Nov is 01:30 on the 17th in Kolkata, so a
// first touch on the site's 16 Nov is older.
setZone("utc", "Asia/Kolkata");
const ahead = { ...ny, visits: [kept("2026-11-16T20:00:00Z")], firstTouch: { by: "hash", day: "2026-11-16", start: null, source: "Search", via: "" } };
assert.equal(firstSeen(ahead).touch, true, "the site's day before the visit's site day");
assert.equal(firstSeen({ ...ahead, firstTouch: { ...ahead.firstTouch, day: "2026-11-17" } }).touch, false);
setZone("site", "UTC");
console.log("visitor-drawer: first seen passed");
