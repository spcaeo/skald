// The first-run checklist's items (js/setup-items.js): each read from what the
// page has (the live count, the stored days) and the two answers it already
// uses (GET integrations: the doctor's lines and each hook's state; GET
// settings), each with a link to its fix; done when every item that is not
// optional is done.
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
  assert.equal(got.logs.fix[1], "#settings/sites");
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
  assert.match(got.assets.says, /no visit counted as people/);
  got = by(setupItems(model({ requests: 40, hits: { people: 12 }, by: { country: { Unknown: 12 } } })));
  assert.equal(got.assets.state, "done");
  assert.equal(got.countries.state, "todo");
  assert.equal(got.countries.fix[1], "#help?part=faq");
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
  assert.equal(got.logs.fix[0], "Set logs.dir");
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
  assert.equal(got.privacy.fix[1], "#settings/retention");
  got = by(setupItems(model(null), { status, tools: [], settings: { ...settings, "mail.daily": S(false) }, waiting: [] }));
  assert.match(got.mail.says, /both off/);
}
console.log("setup: all passed");
