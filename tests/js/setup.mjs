// The first-run checklist's items (js/setup-items.js): each read from what the
// page has (the live count, the stored days) and the two answers it already
// uses (GET integrations: the doctor's lines and each hook's state; GET
// settings), each with one plain line, the Set up dialog that fixes it (act)
// and the doctor's own words for the server admin (tech); done when every item
// that is not optional is done.
//
//   node tests/js/setup.mjs
import assert from "node:assert/strict";
import { setupItems, setupDone } from "../../skald/webapp/js/setup-items.js";

const model = (live, days = []) => ({ today: "2026-10-18", live: live ? { state: "ok", day: "2026-10-18", figures: live } : null,
  byDay: new Map(days.map((d) => [d.day, d])) });
const by = (items) => Object.fromEntries(items.map((i) => [i.id, i]));
const S = (value, source = "default") => ({ value, source });

// ---- a brand-new site: nothing read yet
{
  const got = by(setupItems(model(null)));
  assert.deepEqual(Object.keys(got), ["logs", "assets", "countries", "script", "lead", "mail", "privacy"]);
  assert.equal(got.logs.state, "todo");
  assert.equal(got.logs.act, "logs");
  assert.equal(got.assets.state, "wait");
  assert.equal(got.countries.state, "wait");
  assert.equal(got.script.state, "unknown", "without the integrations answer it is not guessed");
  assert.equal(got.mail.state, "unknown");
  assert.ok(got.script.optional && got.lead.optional && !got.mail.optional);
  assert.ok(!setupDone(Object.values(got)));
}

// ---- requests but no people: the page assets are wrong; people with no country: GeoIP
{
  let got = by(setupItems(model({ requests: 40, hits: { people: 0 }, by: { country: {} } })));
  assert.equal(got.logs.state, "done");
  assert.equal(got.assets.state, "todo");
  assert.match(got.assets.says, /none counts as a person yet/);
  assert.equal(got.assets.act, "assets");
  got = by(setupItems(model({ requests: 40, hits: { people: 12 }, by: { country: { Unknown: 12 } } })));
  assert.equal(got.assets.state, "done");
  assert.equal(got.countries.state, "todo");
  assert.equal(got.countries.act, "countries");
  assert.match(got.countries.tech, /GeoIP/);
  assert.doesNotMatch(got.countries.says, /GeoIP/);
  // No live count today: the last whole day stands in.
  got = by(setupItems(model(null, [{ day: "2026-10-17", state: "ok", requests: 9, readers: 3, by: { country: { CA: 3 } } }])));
  assert.equal(got.countries.state, "done");
  assert.equal(got.assets.state, "done");
}

// ---- the doctor's lines win over the page's own reading; hooks and settings
{
  const status = [{ id: "logs", state: "NEEDS ATTENTION", says: "the folder /logs is not there", fix: "Set logs.dir" },
    { id: "assets", state: "OFF", says: "not needed (site.require_rendering: false)" }, { id: "script", state: "OK", says: "the last event came 2 minutes ago" }];
  const tools = [{ tool: "lead", state: "ready", words: "ready: a test passed 1 minute ago; nothing real yet" }];
  const settings = { "mail.to": S(["owner@example.com"], "site"), "mail.daily": S(true), "mail.weekly": S(false), "privacy.keep_ips": S(true, "site"), "privacy.keep_days": S(30, "site") };
  let got = by(setupItems(model({ requests: 9, hits: { people: 3 }, by: { country: { US: 3 } } }), { status, tools, settings, waiting: [] }));
  assert.equal(got.logs.state, "todo", "the doctor says the log is not there");
  assert.match(got.logs.tech, /Fix: Set logs.dir/);
  assert.doesNotMatch(got.logs.says, /logs\.dir|\/logs/, "the plain line has no config words");
  assert.equal(got.assets.state, "done", "a rule turned off is not a problem");
  assert.equal(got.script.state, "done");
  assert.equal(got.lead.state, "done");
  assert.equal(got.mail.state, "done");
  assert.match(got.mail.says, /daily mail goes to 1 confirmed recipient/);
  assert.equal(got.privacy.state, "done");
  assert.match(got.privacy.says, /kept with each visit for 30 days/);
  assert.ok(!setupDone(Object.values(got)), "the log still needs its fix");
  status[0] = { id: "logs", state: "OK", says: "readable" };
  got = setupItems(model({ requests: 9, hits: { people: 3 }, by: { country: { US: 3 } } }), { status, tools: [], settings, waiting: [] });
  assert.equal(by(got).lead.state, "todo", "no lead hook: to do, but optional");
  assert.ok(setupDone(got), "optional items do not hold the list open");
  // A recipient waiting for the confirm link; privacy left at the default.
  got = by(setupItems(model(null), { status, tools: [], settings: { ...settings, "privacy.keep_ips": S(false) }, waiting: ["second@example.com"] }));
  assert.equal(got.mail.state, "todo");
  assert.match(got.mail.says, /1 recipient has not confirmed/);
  assert.equal(got.privacy.state, "todo");
  assert.equal(got.privacy.act, "privacy");
  got = by(setupItems(model(null), { status, tools: [], settings: { ...settings, "mail.daily": S(false) }, waiting: [] }));
  assert.match(got.mail.says, /both off/);
}

// ---- the script tag's doctor line in plain words; its server words only in tech
{
  const status = [{ id: "logs", state: "OK", says: "readable" },
    { id: "script", part: "Script tag", state: "NEEDS ATTENTION", says: "origins the helper's --origin; no event has arrived yet",
      fix: "Put the tag on every page, from one of these origins. nginx must send /traffic-beacon and /traffic-js/ to the helper (docs/INTEGRATIONS.md)." }];
  let got = by(setupItems(model(null), { status, tools: [], settings: null }));
  assert.equal(got.script.state, "todo");
  assert.equal(got.script.act, "script");
  for (const word of ["--origin", "helper", "nginx", "origins"]) assert.ok(!got.script.says.includes(word), word);
  assert.match(got.script.tech, /--origin/);
  assert.match(got.script.tech, /nginx must send/);
  status[1] = { id: "script", state: "OK", says: "origins the helper's --origin; the last event came 2 minutes ago" };
  got = by(setupItems(model(null), { status, tools: [], settings: null }));
  assert.equal(got.script.says, "The tag works: the last event came 2 minutes ago.");
  assert.equal(got.script.act, null);
  status[1] = { id: "script", state: "OFF", says: "not set up (no beacon.origins); hooks work without it" };
  got = by(setupItems(model(null), { status, tools: [], settings: null }));
  assert.ok(got.script.optional && got.script.act === "script" && !got.script.tech);
  assert.doesNotMatch(got.script.says, /beacon/);
  // Any hook tool that passed a test ticks the lead line, not only the lead hook.
  got = by(setupItems(model(null), { status, tools: [{ tool: "lead", name: "Your site's server (lead)", state: "needs_secret", words: "needs a secret" },
    { tool: "calcom", name: "Cal.com", state: "ready", words: "ready: a test passed 1 minute ago; nothing real yet" }], settings: null }));
  assert.equal(got.lead.state, "done");
  assert.match(got.lead.says, /^Cal.com: ready/);
}
// ---- Next.js pages: only while the doctor's rsc line needs attention, never otherwise
{
  const base = [{ id: "logs", state: "OK", says: "readable" }];
  const rsc = (state) => ({ id: "rsc", part: "Next.js pages", state, says: "the log has Next.js page requests (?_rsc=) but not the header",
    fix: "Append ` rsc_prefetch=$http_next_router_prefetch` at the end of the site's nginx log_format" });
  const live = model({ requests: 9, hits: { people: 3 }, by: { country: { US: 3 } } });
  let items = setupItems(live, { status: [...base, rsc("NEEDS ATTENTION")], tools: [], settings: null });
  const got = by(items);
  assert.deepEqual(items.map((i) => i.id).slice(0, 3), ["logs", "assets", "rsc"]);
  assert.equal(got.rsc.state, "todo");
  assert.equal(got.rsc.act, "rsc");
  assert.ok(!got.rsc.optional, "a page not counted holds the list open");
  assert.equal(got.rsc.title, "Pages opened inside the site are not counted yet");
  assert.match(got.rsc.says, /Next\.js/);
  for (const word of ["rsc_prefetch", "nginx", "_rsc", "log_format"]) assert.ok(!got.rsc.says.includes(word), word);
  assert.match(got.rsc.tech, /rsc_prefetch=\$http_next_router_prefetch/);
  assert.ok(!setupDone(items));
  for (const state of ["OK", "OFF"]) {
    items = setupItems(live, { status: [...base, rsc(state)], tools: [], settings: null });
    assert.ok(!items.some((i) => i.id === "rsc"), state);
  }
  assert.ok(!setupItems(live, { status: base, tools: [], settings: null }).some((i) => i.id === "rsc"), "no line: not Next.js");
  assert.ok(!setupItems(live, { status: null, tools: [], settings: null }).some((i) => i.id === "rsc"), "not loaded: not guessed");
}
console.log("setup: all passed");
