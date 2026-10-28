// From your tools in the page (js/tabs/ov-tools.js, yourtools.js, setup-finish.js), against
// answers shaped as yourtools/api.py gives them (no network):
//  - Overview's card: one line per tool, each figure labelled "Counted from: <tool>", a figure
//    the tool did not give says "Not given" (never 0), what the tool said about its answer,
//    its freshness pill; withheld: no figure; none connected: one quiet line with Connect
//  - Connect a tool (setup=finish-tools): Who will do it? offers Me, My developer and My AI
//    agent; Me lists the lead hook and each tool; a tool opens setup=tool-<id>, whose steps
//    paste the key with POST integrations/yourtools/key
//  - My developer's message names the key and its permission, never a key
//
//   node tests/js/your-tools.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
const SITE = "example.com";
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async (t) => { copied.push(t); } } });
const copied = [];
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

const GA = { id: "ga4", name: "Google Analytics", state: "answering", pill: "good", words: "Answering", ago: "2 h ago", counted_from: "Counted from: Google Analytics",
  period: { start: "2026-09-29", end: "2026-10-26", note: "its own days, America/New_York" },
  headline: [{ name: "sessions", label: "Sessions", value: 1234 }, { name: "totalUsers", label: "Users", value: 980 }, { name: "keyEvents", label: "Key events", value: null }],
  reports: { totals: { flags: ["Google Analytics hid small numbers (thresholding)"], figures: [] } } };
let figures = { ok: true, site: SITE, tools: [GA], connected: 1 };
const ADMIN = { ok: true, site: SITE, sync_minutes: 10, tools: [{ ...GA, state: "off", pill: "off", words: "Not connected", key: { set: false }, options: {},
  option_specs: { property: { label: "Property ID", words: "Its digits, from Admin > Property details.", required: true, example: "123456789" } },
  key_words: "a Google service-account key file (JSON)", permission: "Viewer on the Google Analytics property", make_key: "Google Cloud > IAM > Service accounts > Keys > Add key > JSON",
  suggest: { property: "" }, shares_key: "search" }] };
const ITEMS_INTEG = { ok: true, status: [], tools: [{ tool: "lead", name: "Your site's server", state: "needs_secret", set: false, words: "no secret yet" }],
  yourtools: [{ tool: "ga4", name: "Google Analytics", state: "off", words: "Not connected" }] };
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (body) posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "integrations/yourtools/figures") return answer(figures);
  if (path === "integrations/yourtools/key") return answer({ ok: true, tool: "ga4", who: "robot@project.example.com", replaced: false });
  if (path === "integrations/yourtools") return answer(ADMIN);
  if (path.startsWith("integrations")) return answer(ITEMS_INTEG);
  if (path === "settings") return answer({ ok: true, settings: {}, mail_waiting: [] });
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const T = await import(new URL("tabs/ov-tools.js", JS));
const Y = await import(new URL("tabs/yourtools.js", JS));
const { finishDialog } = await import(new URL("tabs/setup-finish.js", JS));
const { openSetupKey } = await import(new URL("tabs/setup-dialogs.js", JS));
const { setupItems } = await import(new URL("setup-items.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
history.replaceState(null, "", "#overview/summary");

// ---- the card: labelled figures, Not given for a figure the tool did not give
let card = T.toolsCard();
await tick(40);
assert.equal(card.querySelector("h2").textContent, "From your tools");
const line = card.querySelector(".yt-line");
assert.ok(line.textContent.includes("Counted from: Google Analytics"), "every line names its tool");
assert.deepEqual(line.querySelectorAll(".yt-fig b").map((b) => b.textContent), ["1,234", "980", "Not given"]);
assert.ok(!line.textContent.includes(" 0"), "never 0 for nothing");
assert.ok(line.textContent.includes("thresholding"), "what the tool said about its answer");
assert.ok(line.textContent.includes("2026-09-29 to 2026-10-26"), "the tool's own period");
assert.equal(line.querySelector(".ui-pill.good").textContent, "Answering");
assert.ok(line.querySelector(".ua-copy"), "a copy icon on a figure");

// withheld: its words, no figure
figures = { ok: true, site: SITE, tools: [{ ...GA, state: "withheld", pill: "bad", words: "Withheld", withheld: "Withheld: Skald's recheck did not match.", headline: [] }] };
card = T.toolsCard();
await tick(40);
assert.equal(card.querySelectorAll(".yt-fig").length, 0);
assert.ok(card.textContent.includes("Withheld: Skald's recheck did not match."));

// none connected: one quiet line with Connect (2.43, js/ui/connect.js, need tools)
figures = { ok: true, site: SITE, tools: [], connected: 0 };
card = T.toolsCard({ site: SITE, x: {} });
await tick(40);
const none = card.querySelector('.ui-conn-line[data-need="tools"]');
assert.ok(none, "one quiet line");
assert.ok(none.textContent.includes("From your tools: none connected"));
assert.equal(card.querySelectorAll(".ui-primary").length, 0, "a quiet line, never the page's primary");

// ---- the set-up lines: the lead hook and one line per tool
const items = setupItems({}, { status: [], tools: ITEMS_INTEG.tools, settings: {}, yourtools: ITEMS_INTEG.yourtools });
const ga = items.find((i) => i.id === "tool-ga4");
assert.equal(ga.act, "connect-tools");

// ---- Connect a tool: Who will do it? Me, My developer, My AI agent
const d = await finishDialog(SITE, items, { only: "tools" });
await tick(30);
assert.equal(readState().setup, "finish-tools");
assert.equal(dialog().querySelector(".dw-title").textContent, "Connect a tool");
assert.deepEqual(dialog().querySelectorAll(".ui-who-c").map((b) => b.getAttribute("data-who")), ["me", "dev", "agent"]);
dialog().querySelector('.ui-who-c[data-who="dev"]').click();
await tick(40);
const mail = button(dialog(), "Copy the message");
assert.ok(mail, "My developer: a message to copy");
mail.click();
await tick(20);
assert.ok(copied.at(-1).includes("Viewer on the Google Analytics property"), "the permission it needs");
assert.ok(copied.at(-1).includes("Please never send a key by mail or chat."));
dialog().querySelector('.ui-who-c[data-who="me"]').click();
await tick(40);
const lines = dialog().querySelectorAll("button.fin-line").map((b) => b.getAttribute("data-act"));
assert.deepEqual(lines, ["lead", "connect-tools"], "the lead hook and Google Analytics");
dialog().querySelectorAll("button.fin-line")[1].click();
await tick(60);
assert.equal(readState().setup, "tool-ga4", "the tool in the address");
assert.ok(dialog().textContent.includes("Viewer on the Google Analytics property"), dialog().textContent.slice(0, 300));
button(dialog(), "Next").click();
await tick(40);
assert.ok(dialog().textContent.includes("Paste the key"));
const area = dialog().querySelector("textarea");
area.value = '{"type": "service_account"}';
area.dispatchEvent(new Event("input"));
const prop = dialog().querySelectorAll("input").find((i) => i.getAttribute("type") === "text");
prop.value = "123456789";
prop.dispatchEvent(new Event("input"));
button(dialog(), "Next").click();
await tick(60);
assert.deepEqual(posted.find(([p]) => p === "integrations/yourtools/key"), ["integrations/yourtools/key", { site: SITE, tool: "ga4", key: '{"type": "service_account"}', options: { property: "123456789" } }]);
// 2.44: "Key saved.", and whether the tool answered yet follows by itself (sites/arrived tool:ga4).
assert.ok(dialog().textContent.includes("Key saved."));
assert.ok(posted.some(([p, b]) => p === "sites/arrived" && b.what === "tool:ga4"));
assert.ok(dialog().textContent.includes("robot@project.example.com"));
d?.close?.({ instant: true, silent: true });

// ---- the address alone opens the same dialog
assert.equal(typeof (await openSetupKey("tool-ga4", { site: SITE }, 1, false, { by: "me" })), "object");
assert.equal(await openSetupKey("tool-../x", { site: SITE }, 1), "That set-up step is not in this version of the page.");

// ---- the developer message never holds a key
assert.ok(!Y.toolsMail(SITE, ADMIN.tools).includes("service_account"));

// ---- a tool's drawer: its notes, the lines Skald worked out, the people as kept, each with copy
const CAL = { ...ADMIN.tools[0], id: "calendly", name: "Calendly", state: "answering", pill: "good", words: "Answering", counted_from: "Counted from: Calendly",
  key: { set: true, where: "file", who: "a Calendly token ending ...abcd" }, option_specs: {}, shares_key: null,
  notes: ["Calendly's own history and figures."],
  more: { lines: ["Of these 5 bookings, 2 reached Skald by the webhook too (matched on the meeting's address); 3 did not."],
    people: [{ when: "2026-10-26T20:00:00Z", what: "Demo", state: "active", name: "Eve Example", email: "eve@example.com" },
      { when: "2026-10-01T09:00:00Z", what: "Intro call", state: "no-show", name: null, email: null }] } };
const dw = Y.toolDrawer(CAL, SITE);
assert.deepEqual(dw.querySelectorAll(".yt-note").map((p) => p.textContent), [CAL.notes[0], CAL.more.lines[0]]);
const people = dw.querySelectorAll(".yt-person");
assert.equal(people.length, 2);
assert.ok(people[0].textContent.includes("Eve Example") && people[0].textContent.includes("eve@example.com"));
assert.equal(people[0].querySelectorAll(".ua-copy").length, 2, "a copy icon on the name and the email");
assert.equal(people[1].querySelector(".ui-pill.warn").textContent, "no-show");
assert.ok(!people[1].textContent.includes("null"), "no name kept: nothing shown");
assert.equal(Y.toolDrawer({ ...CAL, more: {} }, SITE).querySelectorAll(".yt-person").length, 0);

// ---- the shared drawer's buttons (UI-RULES rules 1 and 12): one primary, Pause and Remove quieter
const { primaries } = await import(new URL("ui/primary.js", JS));
const btn = (root, words) => root.querySelectorAll("button").find((b) => b.textContent === words);
const isMain = (b) => b.className.includes("ui-primary");
const GAON = { ...ADMIN.tools[0], state: "answering", pill: "good", words: "Answering", options: { property: "123456789" }, suggest: {},
  key: { set: true, where: "file", who: "a service account ending ...@example.com" } };
const g = Y.toolDrawer(GAON, SITE);
assert.equal(primaries(g), 1, "one primary in the drawer");
assert.ok(isMain(btn(g, "Sync now")), "nothing changed: Sync now is the primary");
assert.ok(btn(g, "Save").disabled && !isMain(btn(g, "Save")), "Save waits for a change");
assert.ok(btn(g, "Replace the key").disabled, "Replace the key waits for a pasted key");
const quiet = g.querySelector(".yt-quiet");
assert.ok(quiet, "a quieter row");
assert.deepEqual(quiet.querySelectorAll("button").map((b) => b.textContent), ["Pause", "Remove the key"]);
assert.ok(quiet.querySelectorAll("button").every((b) => !isMain(b)));
assert.ok(!g.querySelector(".yt-main").textContent.includes("Pause"), "Pause is not beside Sync now");
const propIn = g.querySelectorAll("input").find((i) => i.getAttribute("placeholder") === "123456789");
propIn.value = "987654321";
propIn.dispatchEvent(new Ev("input"));
assert.ok(isMain(btn(g, "Save")) && !btn(g, "Save").disabled, "an option changed: Save is the primary");
assert.equal(primaries(g), 1);
propIn.value = "123456789";
propIn.dispatchEvent(new Ev("input"));
assert.ok(isMain(btn(g, "Sync now")) && btn(g, "Save").disabled, "changed back: Sync now again");
const keyArea = g.querySelector("textarea");
keyArea.value = "{\"type\": \"service_account\"}";
keyArea.dispatchEvent(new Ev("input"));
assert.ok(isMain(btn(g, "Replace the key")) && !btn(g, "Replace the key").disabled, "a key pasted: Replace the key");
assert.equal(primaries(g), 1);
// Not connected yet: keeping the key is the one thing to do; no Sync now, no Pause.
const off = Y.toolDrawer({ ...ADMIN.tools[0], suggest: {} }, SITE);
assert.ok(isMain(btn(off, "Keep the key")) && !btn(off, "Sync now") && !btn(off, "Pause"));
assert.equal(primaries(off), 1);
// A key in the server's environment: nothing to edit, Sync now is the primary; no Remove.
const env = Y.toolDrawer({ ...GAON, in_env: true, key: { set: true, where: "env GA_KEY" } }, SITE);
assert.ok(isMain(btn(env, "Sync now")) && !btn(env, "Save") && !btn(env, "Remove the key"));
assert.deepEqual(env.querySelector(".yt-quiet").querySelectorAll("button").map((b) => b.textContent), ["Pause"]);
// The same for every tool: Calendly's drawer (no options) has its one primary too.
assert.equal(primaries(dw), 1);
assert.ok(isMain(btn(dw, "Sync now")));

console.log("your-tools: all passed");
