// "Not set up", never 0 (skald/webapp/js/notset.js): an event the site never
// sent, a lead kind the lead store never recorded, a heartbeat that never ran, and how
// long a silence must be before Data quality calls a day worth a look.
//
//   node tests/js/notset.mjs        (tests/test_ui_honesty.py runs it)
//
// Example data only: example.com paths, no addresses.
import assert from "node:assert/strict";
import { everSent, howToSend, neverRecorded, heartbeatOn, quietLimit } from "../../skald/webapp/js/notset.js";

// ---- events: the file's `sent` list decides; an older file falls back on its rows and today
{
  const f = { sent: { signup_start: "2026-10-17", cta_click: "2026-10-01" }, rows: [], today: { events: {} } };
  assert.equal(everSent(f, "signup_start"), true);
  assert.equal(everSent(f, "signup_submit"), false, "never sent: not set up");
  assert.equal(everSent(null, "cta_click"), false);
  const old = { rows: [["2026-10-17", "cta_click", "hero", "/", "Direct", 3], ["2026-10-17", "scroll_75", "", "/", "Direct", 0]],
    today: { state: "ok", events: { signup_start: 2 } } };
  assert.equal(everSent(old, "cta_click"), true);
  assert.equal(everSent(old, "scroll_75"), false, "a zero row is not a sent event");
  assert.equal(everSent(old, "signup_start"), true, "today's spool counts");
  assert.match(howToSend("signup_submit"), /data-skald="signup"/);
  assert.match(howToSend("demo_booked"), /own code.*Help › The tracking script/);   // plain words: Help keeps the exact line
  assert.ok(howToSend("copy_text").length > 10);
}

// ---- leads: a kind never recorded on any day read (since, withheld days left out)
{
  const f = { types: ["signup", "contact", "waitlist", "demo_opened", "demo_booked"], since: "2026-10-01", days: [
    { day: "2026-09-30", leads: { demo_booked: 4 } },              // before the store was read: does not count
    { day: "2026-10-02", leads: { signup: 2, contact: 0 } },
    { day: "2026-10-03", state: "withheld", leads: { waitlist: 1 } }, // withheld: does not count
    { day: "2026-10-04", leads: { contact: 1 } },
  ] };
  assert.deepEqual([...neverRecorded(f)].sort(), ["demo_booked", "demo_opened", "waitlist"]);
  assert.deepEqual([...neverRecorded({ days: [] })].sort(), ["contact", "demo_booked", "demo_opened", "signup", "waitlist"]);
}

// ---- heartbeat: never seen is not set up; seen once and silent since stays an outage
{
  const none = { days: [{ day: "2026-10-16", heartbeat: { expected: 288, seen: 0, ok: 0, gaps: [{ from: "00:00", to: "00:00", minutes: 1440 }] } }], today: { heartbeat: { seen: 0 } } };
  assert.equal(heartbeatOn(none), false);
  const once = { days: [{ day: "2026-10-15", heartbeat: { seen: 12, ok: 12 } }, { day: "2026-10-16", heartbeat: { seen: 0 } }] };
  assert.equal(heartbeatOn(once), true);
  assert.equal(heartbeatOn({ days: [], today: { heartbeat: { seen: 3 } } }), true);
  assert.equal(heartbeatOn(null), false);
}

// ---- silence: an hour at least; longer on a quiet site
{
  assert.equal(quietLimit({ lines: 100000 }), 60, "a busy site: an hour");
  assert.equal(quietLimit({ lines: 500 }), 115, "500 lines a day: about two hours");
  assert.ok(quietLimit({ lines: 50 }) > 1000, "a very quiet site: most of a day");
  assert.ok(quietLimit({}) >= 60);
}

console.log("notset: ok");
