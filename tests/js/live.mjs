// Live status and the Test button (2.44: js/live-words.js, js/ui/live.js), against a fake
// helper:
//  - the words: how often a page asks (5 s, 30 s after 3 minutes), Search's live state in plain
//    words ("Connected. Getting Google's history: 36 of 70 weeks."), when the live answer is
//    ahead of the built file, when a viewer's file is still busy;
//  - poll: asks while shown, not while the tab is hidden, stops once it left the page, on a 403,
//    or once until() says done;
//  - redraw: reads the files again at most once in REDRAW_GAP;
//  - testButton and arrivedBox: "Checking...", the plain answer with "Last checked", the agent's
//    steps, the technical words behind Details, onDone once; a 429 says to wait;
//  - Traffic › Search: the built file says not connected, the live answer says connected and
//    syncing: the page says so, with no Connect card and no reload, and reads its file again.
//
//   node tests/js/live.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const W = await import(new URL("live-words.js", JS));
const L = await import(new URL("ui/live.js", JS));

// ---- the words
assert.equal(W.delay(0), 5000, "every 5 s at first");
assert.equal(W.delay(179000), 5000);
assert.equal(W.delay(181000), 30000, "every 30 s after 3 minutes");
const SYNCING = { connected: "sc-domain:docs.example", status: { backfill: { state: "running", done: 36, of: 70 } }, summary: { days: 0 } };
let st = W.searchState(SYNCING, "google");
assert.equal(st.state, "syncing");
assert.equal(st.words, "Connected. Getting Google's history: 36 of 70 weeks. The figures appear as each week arrives.");
assert.deepEqual(st.pill, ["info", "Syncing"]);
assert.equal(st.busy, true);
assert.equal(W.searchState(null).state, "off");
assert.equal(W.searchState({ connected: "x", status: { error: "HTTP 403" }, summary: { days: 4 } }).state, "failing");
assert.ok(!W.searchState({ connected: "x", status: { error: "HTTP 403" }, summary: { days: 4 } }).words.includes("403"), "the code is not on the first line");
st = W.searchState({ connected: "x", status: { last_sync: "2026-10-27T21:50:00Z" }, summary: { days: 480, last: "2026-10-25" } });
assert.equal(st.words, "Connected. 480 days of Search Console's figures are here, the newest 2026-10-25.");
assert.equal(W.searchAhead({ connected: null }, SYNCING), true, "live connected, file not: ahead");
assert.equal(W.searchAhead({ connected: "x", status: { backfill: { state: "running", done: 11, of: 70 } } }, SYNCING), true, "more weeks live");
assert.equal(W.searchAhead(SYNCING, SYNCING), false, "the same: not ahead");
assert.equal(W.searchAhead({ connected: null }, { connected: null }), false);
assert.equal(W.searchBusy({ engines: { google: SYNCING } }), true);
assert.equal(W.searchBusy({ engines: { google: { connected: "x", status: { last_sync: "t" }, summary: { days: 3 } } } }), false);
assert.deepEqual(W.pillOf("ok"), ["good", "Working"]);
assert.deepEqual(W.pillOf("wait"), ["warn", "Waiting"]);
assert.equal(W.kindOf("bad"), "bad");
assert.equal(W.hookWords({ state: "never" }, "Calendly").words, "Waiting for Calendly: nothing has arrived yet.");
assert.equal(W.hookWords({ state: "received", last_at: "2026-10-27T10:42:00Z" }, "Stripe").verdict, "ok");

// ---- poll: asks while shown, not hidden, stops when gone, on 403, or when done
let asks = 0;
let reply = { ok: true, n: 0 };
const el = document.createElement("div");
document.body.append(el);
const p = L.poll(el, async () => { asks++; return reply; }, { until: (r) => r.done === true });
await tick(20);
assert.equal(asks, 1, "asked at once");
document.hidden = true;
await p.now();
assert.equal(asks, 1, "not while hidden");
document.hidden = false;
await p.now();
assert.equal(asks, 2, "asked again when shown");
reply = { ok: true, done: true };
await p.now();
assert.equal(asks, 3);
await p.now();
assert.equal(asks, 3, "stopped once done");
let asks2 = 0;
const el2 = document.createElement("div");
document.body.append(el2);
const p2 = L.poll(el2, async () => { asks2++; return { ok: false, status: 403 }; });
await tick(20);
await p2.now();
assert.equal(asks2, 1, "stopped on 403");
let asks3 = 0;
const el3 = document.createElement("div");
document.body.append(el3);
const p3 = L.poll(el3, async () => { asks3++; return { ok: true }; });
await tick(20);
document.body.removeChild(el3);
await p3.now();
assert.equal(asks3, 1, "stopped once it left the page");

// ---- redraw: at most once in the gap
let redraws = 0;
L.setRedraw(async (names) => { redraws++; assert.deepEqual(names, ["search"]); return true; });
L.resetRedraw();
assert.equal(await L.redraw("search"), true);
assert.equal(await L.redraw(["search"]), false, "not again within the gap");
assert.equal(redraws, 1);
L.resetRedraw();

// ---- testButton: Checking, the plain answer, Last checked, the steps, Details
const T1 = { verdict: "wait", head: "Waiting for your agent: it has not opened the line yet.", says: "Nothing has happened on this line so far.",
  fix: "Paste the line into Claude Code or Codex, opened in the site's own folder or on its server.",
  steps: [{ id: "opened", words: "Your agent opened the line", done: false }, { id: "keys", words: "Your agent took its keys", done: false }],
  tech: "state: waiting", at: "2026-10-27T10:42:00Z" };
let answer = { ok: true, test: T1 };
const tb = L.testButton({ ask: async () => answer });
document.body.append(tb);
const btn = tb.querySelector("button");
assert.equal(btn.textContent, "Test");
await tb.press();
const out = tb.querySelector(".lv-out");
assert.match(out.textContent, /Waiting for your agent: it has not opened the line yet\./);
assert.match(out.textContent, /Next: Paste the line into Claude Code/);
assert.match(out.textContent, /Last checked 10:42/);
assert.equal(out.querySelectorAll(".lv-steps li").length, 2);
assert.ok(out.querySelector("details"), "the technical words behind Details");
assert.ok(!/[✓✔✅]/.test(out.textContent), "icons, not tick glyphs");
answer = { ok: false, status: 429, error: "Too many checks. Try again in a few minutes." };
await tb.press();
assert.match(out.textContent, /Too many checks/);
assert.match(out.textContent, /Wait a few minutes/);

// ---- arrivedBox: the pill and sentence update by themselves; onDone once; then it stops
let live = { ok: true, test: { verdict: "wait", head: "Waiting for Calendly: nothing real has arrived yet.", at: "2026-10-27T10:42:00Z" } };
let polled = 0;
let done = 0;
const box = L.arrivedBox("example.com", "hook:calendly", { onDone: () => done++,
  ask: { live: async () => { polled++; return live; }, press: async () => live } });
document.body.append(box);
await tick(20);
assert.equal(polled, 1);
assert.equal(box.dataset.verdict, "wait");
assert.match(box.querySelector(".lv-line").textContent, /Waiting/);
assert.match(box.querySelector(".lv-line").textContent, /Waiting for Calendly: nothing real has arrived yet\. Last checked 10:42\./);
assert.equal(box.querySelectorAll("button").find((b) => b.textContent === "Test") ? 1 : 0, 1, "a Test button beside it");
live = { ok: true, test: { verdict: "ok", head: "Connected. The last delivery from Calendly came at 10:44 UTC on 2026-10-27.", at: "2026-10-27T10:44:00Z" } };
await box.querySelector("button").click();
await tick(10);
assert.equal(box.dataset.verdict, "ok", "a press updates the line too");
assert.match(box.querySelector(".lv-line").textContent, /Working/);
assert.equal(done, 1, "onDone once");
box.show(live.test);
assert.equal(done, 1, "and only once");

// ---- Traffic › Search: built file not connected, live answer connected and syncing
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
let liveSearch = { ok: true, engines: { google: SYNCING, bing: { connected: null, status: {}, summary: {} } } };
const fetched = [];
globalThis.fetch = async (path, opts = {}) => {
  fetched.push(path);
  const ans = (data, code = 200) => ({ ok: code < 300, status: code, json: async () => structuredClone(data), headers: { get: () => null } });
  if (String(path).startsWith("integrations/search")) return ans(liveSearch);
  if (String(path).startsWith("integrations")) return ans({ ok: true, found: null, tools: [] });
  return ans({ ok: false, error: "not found" }, 404);
};
const S = await import(new URL("state.js", JS));
const search = (await import(new URL("tabs/tr-search.js", JS))).default;
const m = { site: "docs.example", x: { search: { schema_version: 1, engines: { google: { connected: null, status: {}, summary: {} }, bing: { connected: null, status: {}, summary: {} } } } },
  byDay: new Map(), anchor: "2026-10-27", today: "2026-10-27", live: null };
let asked = [];
L.setRedraw(async (names) => { asked.push(names); return false; });
L.resetRedraw();
const page = document.createElement("div");
document.body.append(page);
page.append(...[search(m, S.read())].flat().filter(Boolean));
assert.match(page.textContent, /Search Console is not connected yet/, "first the file's answer");
await tick(30);
assert.ok(fetched.some((x) => x.startsWith("integrations/search?site=docs.example")), "asked the helper");
assert.ok(!/is not connected yet/.test(page.textContent), "no stale 'not connected' once the live answer came");
assert.match(page.textContent, /Connected\. Getting Google's history: 36 of 70 weeks\./);
assert.match(page.textContent, /no need to reload/);
assert.ok(!page.querySelector(".ui-conn"), "no Connect card");
assert.deepEqual(asked, [["search"]], "the file is read again once");

// ---- Search asked to connect, Google does not show the robot yet (27 Oct): said, with
// Check now; never "not connected yet" with a Connect card.
liveSearch = { ok: true, engines: { google: { connected: null, status: {}, summary: {} }, bing: { connected: null, status: {}, summary: {} } },
  auto: { state: "waiting", words: "Waiting for Google: Skald's robot address is not on a shop.example property yet. Google can take a few minutes." } };
globalThis.fetch = async (path, opts = {}) => {
  const ans = (data, code = 200) => ({ ok: code < 300, status: code, json: async () => structuredClone(data), headers: { get: () => null } });
  if (String(path).startsWith("integrations/search")) return ans(liveSearch);
  if (path === "sites/arrived") return ans({ ok: true, test: { verdict: "wait", head: liveSearch.auto.words, at: "2026-10-27T17:56:00Z" } });
  if (String(path).startsWith("integrations")) return ans({ ok: true, found: null, tools: [] });
  return ans({ ok: false }, 404);
};
const page2 = document.createElement("div");
document.body.append(page2);
page2.append(...[search({ ...m, site: "shop.example" }, S.read())].flat().filter(Boolean));
await tick(40);
assert.match(page2.textContent, /Waiting for Google: Skald's robot address is not on a shop\.example property yet\./);
assert.match(page2.textContent, /Last checked 17:56/);
assert.ok(page2.querySelectorAll("button").find((b) => b.textContent === "Check now"), "Check now beside it");
assert.ok(!/is not connected yet/.test(page2.textContent));
assert.match(page2.textContent, /Nothing to press: Skald connects by itself/);

// ---- the agent watch's one line on top (agent-words.js headWords)
const AW = await import(new URL("tabs/agent-words.js", JS));
assert.deepEqual(AW.headWords(null), ["info", "Checking", "Checking what your agent has done..."]);
assert.equal(AW.headWords({ state: "waiting" })[2], "Waiting for your agent to open the line.");
assert.match(AW.headWords({ state: "keys_taken", opened_at: "t", keys_at: "2026-10-27T21:40:00Z" }, {}, ["search"])[2], /^Your agent is working: it took its keys at 21:40\./);
const left = AW.headWords({ state: "keys_taken", opened_at: "t", keys_at: "t", reported_at: "t", report: { left_for_user: ["Add the robot address in Search Console", "Bing key"] } }, {}, ["search"]);
assert.deepEqual(left.slice(0, 2), ["warn", "Left for you"]);
assert.equal(left[2], "Your agent finished. Left for you: Add the robot address in Search Console (and 1 more, in Details)");
assert.deepEqual(AW.headWords({ state: "keys_taken", opened_at: "t", keys_at: "t", reported_at: "t", report: {} }, {}, ["search"]).slice(0, 2), ["good", "Done"]);
assert.equal(AW.headWords({ state: "keys_taken", opened_at: "t", keys_at: "t", reported_at: "t", report: {} }, {}, ["logs"])[1], "Waiting for visits");
// The agent is done but Google does not show the robot yet (27 Oct): never "Done".
const rep = { state: "keys_taken", opened_at: "t", keys_at: "t", reported_at: "t", report: {} };
assert.deepEqual(AW.headWords(rep, { search: { verdict: "wait" } }, ["search"]).slice(0, 2), ["warn", "Waiting for Google"]);
assert.match(AW.headWords(rep, { search: { verdict: "wait" } }, ["search"])[2], /nothing to press/);
assert.equal(AW.headWords(rep, { search: { verdict: "ok" } }, ["search"])[2], "Done: your agent finished, and Search Console is connected.");

console.log("live: all passed");
process.exit(0);
