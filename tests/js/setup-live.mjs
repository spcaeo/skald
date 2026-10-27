// Add a site's live progress and its first two questions (2.43), against a fake helper:
//  - the words: how often the page asks (5 s, 30 s after 2 minutes), the checklist's lines with
//    their counts, the pill, the done words, and the address values (never an email);
//  - the live panel: asks while shown, not while the tab is hidden or once it left the page;
//    "Check now" says plainly what is missing; the done state (Receiving data, one primary
//    "Open the dashboard", Invite the people, Send the invites now);
//  - the wizard: a done set-up opened from its link shows the done state and Close, never
//    "Finish later"; the two questions keep org= and ppl= in the address (ids only) and send
//    the new organisation's name and the typed address in sites/add's body.
//
//   node tests/js/setup-live.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const STEPS_WAIT = [
  { id: "opened", words: "Your agent opened the line", done: true, at: "2026-10-27T13:20:00Z" },
  { id: "keys", words: "Keys made and taken", done: true, at: "2026-10-27T13:21:00Z" },
  { id: "road", words: "Data road set up: Vercel log drain", done: true, at: "2026-10-27T13:22:00Z" },
  { id: "data", words: "First data received", done: false },
  { id: "verified", words: "Domain verified", done: true },
  { id: "done", words: "Set-up done", done: false },
];
const WAITING = { state: "waiting", steps: STEPS_WAIT, recent: 0, people: 1 };
const DONE = { state: "done", recent: 1283, newest_at: "2026-10-27T13:28:00Z", people: 1, invites_at: null,
  steps: [...STEPS_WAIT.slice(0, 3), { id: "data", words: "First data received", done: true, at: "2026-10-27T13:27:00Z", recent: 1283, newest_at: "2026-10-27T13:28:00Z" },
    STEPS_WAIT[4], { id: "done", words: "Set-up done", done: true, at: "2026-10-27T13:28:00Z" }] };

let liveNow = WAITING;
const sites = { ok: true, can_add: true, ingest_url: "https://app.example.com/traffic-ingest", sites: [
  { name: "example.com", status: "active", source: "dashboard", setup: null },
  { name: "shop.example.org", status: "active", source: "dashboard", setup: { step: 5, method: "vercel", done: true } },
  { name: "half.example.org", status: "active", source: "dashboard", setup: { step: 4, method: "vercel", done: false } }] };
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "sites") return answer(sites);
  if (path === "sites/whoopts") return answer({ ok: true, org: { id: 1, name: "Alpha" }, may_make: true,
    orgs: [{ id: 7, name: "Beta", sites: 2 }], members: [{ id: 12, email: "ana@example.com", name: "Ana", role: "viewer" }] });
  if (path === "sites/detect") return answer({ ok: true, found: { site: body.address, reachable: true, server: "nginx", recommended_method: "server" } });
  if (path === "sites/add") return answer({ ok: true, site: body.host, verify: null, org: { id: 31, name: body.org_name || "Alpha", new: body.org === "new" }, people: (body.people || []).length });
  if (path === "sites/setup") return answer({ ok: true });
  if (path === "sites/live") return answer({ ok: true, live: liveNow });
  if (path === "sites/check") return answer({ ok: true, live: liveNow, check: { verdict: liveNow.state === "waiting" ? "wait" : "ok", head: "Checked." } });
  if (path.startsWith("sites/status")) return answer({ ok: true, last_batch: null, today: null });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const L = await import(new URL("tabs/setup-live-words.js", JS));
const { livePanel } = await import(new URL("tabs/setup-live.js", JS));
const { DETECT_WAIT_MS } = await import(new URL("tabs/conn-detect.js", JS));
const { openSiteKey } = await import(new URL("tabs/sitesadmin.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
const { primaries } = await import(new URL("ui/primary.js", JS));

// ---- the words
assert.equal(L.delay(0), 5000, "every 5 s at first");
assert.equal(L.delay(119000), 5000);
assert.equal(L.delay(121000), 30000, "every 30 s after 2 minutes");
const items = L.itemsOf(DONE);
assert.equal(items.find((x) => x.id === "data").more, "1,283 in the last 15 min, newest 13:28 UTC");
assert.deepEqual(L.pillOf(WAITING), ["warn", "Waiting for data"]);
assert.deepEqual(L.pillOf(DONE), ["good", "Receiving data"]);
assert.deepEqual(L.pillOf({ state: "done", recent: 0 }), ["good", "Set up"]);
assert.equal(L.pillOf({}), null, "no set-up: no pill");
assert.equal(L.doneWords(DONE, "shop.example.org").head, "shop.example.org is receiving data: 1,283 lines in the last 15 minutes.");
assert.equal(L.doneWords(DONE, "x").people, "1 person waits for an invite.");
assert.equal(L.doneWords({ ...DONE, invites_words: "Invites sent to 1 person." }, "x").people, "Invites sent to 1 person.");
assert.equal(L.orgFrom("ana@example.com"), "same", "never an email as the organisation");
assert.equal(L.orgFrom("7"), "7");
assert.equal(L.orgFrom("new"), "new");
assert.deepEqual(L.pplFrom("12.15.ana@example.com"), [12, 15], "ids only");
assert.equal(L.pplValue([12, "15", "ana@example.com", 12]), "12.15");
assert.deepEqual(L.addBody({ org: "same" }), {}, "this organisation, no one: nothing extra");
assert.deepEqual(L.addBody({ org: "new", name: " Acme ", privacy: "client", people: [{ email: "bo@example.com", role: "owner" }] }),
  { org: "new", org_name: "Acme", privacy_class: "client", people: [{ email: "bo@example.com", role: "owner" }] });
assert.equal(L.checkKind("ok"), "ok");
assert.equal(L.checkKind("wait"), "warn");

// ---- the live panel: asks while shown; not while hidden; not once it left the page
let asks = 0;
let answer = { ok: true, live: WAITING };
const check = { ok: true, check: { verdict: "wait", head: "No data yet.", says: "Skald has had no lines for shop.example.org.", fix: "Usually it starts within 2 minutes after the drain is saved.", tech: "last_batch: none" }, live: WAITING };
let done = 0;
const panel = livePanel("shop.example.org", { link: "0f3a9c2e7b1d4a58", onDone: () => done++,
  ask: { live: async () => { asks++; return answer; }, check: async () => check, send: async () => ({ ok: true, invites: { words: "Invites sent to 1 person." } }) } });
document.body.append(panel);
await tick(20);
assert.equal(asks, 1, "asked once at once");
assert.equal(panel.dataset.state, "waiting");
assert.equal(panel.querySelector(".sl-pill").textContent.trim(), "Waiting for data");
assert.equal(panel.querySelectorAll(".sl-list li").length, 6);
assert.equal(panel.querySelectorAll(".sl-list li.ok").length, 4);
assert.match(panel.querySelector('.sl-list li[data-id="road"]').textContent, /Vercel log drain/);
assert.ok(!/[\u2713\u2714\u2705]/.test(panel.textContent), "no tick glyphs: icons");
assert.match(panel.querySelector(".sl-people").textContent, /1 person waits for an invite: it is sent as soon as the first data arrives\./);
assert.ok(panel.querySelectorAll("button").find((b) => b.textContent === "Send the invites now"), "before the data too (the 24-hour mail)");
document.hidden = true;
await panel.refresh();
assert.equal(asks, 1, "not asked while the tab is hidden");
document.hidden = false;
await panel.refresh();
assert.equal(asks, 2, "asked again when shown");
// Check now, nothing yet: what is missing, plainly; the technical words folded.
panel.querySelectorAll("button").find((b) => b.textContent === "Check now").click();
await tick(10);
const out = panel.querySelector(".sl-check");
assert.match(out.textContent, /No data yet\./);
assert.match(out.textContent, /within 2 minutes after the drain is saved/);
assert.ok(out.querySelector("details"), "the technical part behind a fold");
// Done: the green answer, one primary, the people.
answer = { ok: true, live: DONE };
await panel.refresh();
assert.equal(done, 1, "onDone once");
await panel.refresh();
assert.equal(done, 1, "and only once");
const box = panel.querySelector(".sl-done");
assert.match(box.textContent, /Receiving data/);
assert.match(box.textContent, /1,283 lines in the last 15 minutes/);
assert.equal(primaries(panel), 1, "one primary button");
const open = panel.querySelectorAll("a").find((a) => a.textContent === "Open the dashboard");
assert.equal(open.getAttribute("href"), "/traffic/shop.example.org/#overview/summary");
assert.ok(panel.querySelectorAll("a").find((a) => a.textContent === "Invite the people who will use it"));
assert.ok(!panel.textContent.includes("Finish later"));
const sendNow = panel.querySelectorAll("button").find((b) => b.textContent === "Send the invites now");
assert.ok(sendNow, "people wait: send them now");
// Left the page: no more asking.
panel.remove?.() ?? document.body.removeChild(panel);
const before = asks;
await panel.refresh();
assert.equal(asks, before, "not asked once the panel left the page");

// ---- the wizard: a done set-up opened from its link
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const heading = () => dialog().querySelector("h3.cn-h").textContent;
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
async function next() { button(dialog(), "Next").click(); await tick(30); }
async function close() { dialog().querySelector(".dw-x").click(); await tick(400); }
history.replaceState(null, "", "#settings/org/sites");
liveNow = DONE;
await openSiteKey("shop.example.org", 1, {});
await tick(40);
assert.match(heading(), /Connect it$/, "done: opens on Connect it, whatever step the link named");
assert.ok(!button(dialog(), "Finish later"), "never Finish later when done");
assert.ok(button(dialog(), "Close"));
assert.match(dialog().querySelector(".sl-done").textContent, /Receiving data/);
assert.equal(primaries(dialog()), 1, "one primary: Open the dashboard");
await close();

// ---- one source of truth (2.43): on every path the live progress replaces the old waiting block
// and its Test connection; once it shows data, the old "nothing has arrived" words never show.
const RECEIVING = { state: "receiving", recent: 214, newest_at: "2026-10-27T13:29:00Z", people: 0,
  steps: DONE.steps.map((x) => (x.id === "done" ? { ...x, done: false, at: null } : x)) };
for (const by of ["me", "dev", "agent"]) {
  liveNow = WAITING;
  await openSiteKey("half.example.org", 4, { by, ...(by === "agent" ? { agent: "codex" } : {}) });
  await tick(40);
  let dd = dialog();
  assert.equal(dd.querySelectorAll(".sl").length, 1, `${by}: one live progress`);
  assert.ok(!button(dd, "Test connection"), `${by}: no second test button`);
  assert.ok(button(dd, "Check now"), `${by}: the one check`);
  assert.ok(!dd.textContent.includes("Skald waits for the first visits"), `${by}: no old waiting block`);
  liveNow = RECEIVING;
  button(dd, "Check now").click();
  await tick(40);
  dd = dialog();
  assert.match(dd.querySelector(".sl-pill").textContent, /Receiving data/, `${by}: data shown`);
  for (const old of ["Nothing has reached Skald yet", "Waiting for the first lines", "Skald waits for the first visits"]) {
    assert.ok(!dd.textContent.includes(old), `${by}: never "${old}" once the live progress shows data`);
  }
  assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.name === "half.example.org" && b.done === true), `${by}: the first data saves the set-up done`);
  await close();
}
// A refusal newer than the data: the plain reason, without a press.
{
  const seen = livePanel("x.example.org", { ask: { live: async () => ({ ok: true, live: { ...WAITING, refused: { words: "The sending token is not valid for x.example.org.", at: "2026-10-27T13:25:00Z" } } }) } });
  document.body.append(seen);
  await tick(20);
  assert.match(seen.querySelector(".sl-refused").textContent, /Skald refused what was sent\..*The sending token is not valid/);
  document.body.removeChild(seen);
}

// ---- the wizard: the two questions, in the address by id only
liveNow = WAITING;
await openSiteKey("new", 0, {});
await tick(30);
let d = dialog();
const radios = d.querySelectorAll('input[name="sw-org"]');
assert.deepEqual(radios.map((r) => r.getAttribute("value")), ["same", "other", "new"]);
assert.match(d.textContent, /This organisation \(Alpha\)/);
const inputOf = (name, v) => dialog().querySelectorAll(`input[name="${name}"]`).find((r) => r.getAttribute("value") === v);
const pick = (v) => { const r = inputOf("sw-org", v); r.checked = true; r.dispatchEvent(new Ev("change")); };
// Another of mine: its id, and the member ticked by id.
pick("other");
const sel = dialog().querySelectorAll("select").find((x) => x.getAttribute("aria-label") === "Which of your organisations");
sel.value = "7"; sel.dispatchEvent(new Ev("change"));
assert.equal(readState().org, "7");
const ana = dialog().querySelectorAll(".sw-people input")[0];
ana.checked = true; ana.dispatchEvent(new Ev("change"));
assert.equal(readState().ppl, "12", "the member by id");
// A new one: a name is needed; the email typed stays out of the address.
pick("new");
assert.equal(readState().org, "new");
assert.match(dialog().textContent, /A client: their own privacy settings apply/);
const addr = dialog().querySelector('input[name="site-address"]');
addr.value = "fieldcamp.example.net"; addr.dispatchEvent(new Ev("input"));
await tick(DETECT_WAIT_MS + 60);
await next();
assert.match(dialog().textContent, /Name the new organisation\./, "no name: Next refused");
assert.ok(!posted.some(([p]) => p === "sites/add"), "nothing made");
const nm = dialog().querySelector('input[name="org-name"]');
nm.value = "Fieldcamp"; nm.dispatchEvent(new Ev("input"));
const client = inputOf("sw-privacy", "client");
client.checked = true; client.dispatchEvent(new Ev("change"));
const em = dialog().querySelector('input[name="invite-email"]');
em.value = "Bo@Example.com";
button(dialog(), "Add").click(); await tick();
assert.match(dialog().textContent, /bo@example\.com/);
assert.ok(!location.hash.includes("@") && !location.hash.toLowerCase().includes("fieldcamp%20") && !/Fieldcamp\b/.test(location.hash), "never an email or a name in the address");
await next();
const add = posted.find(([p]) => p === "sites/add")[1];
assert.equal(add.host, "fieldcamp.example.net");
assert.equal(add.org, "new");
assert.equal(add.org_name, "Fieldcamp");
assert.equal(add.privacy_class, "client");
assert.deepEqual(add.people, [{ user: 12, role: "viewer", sees: "all" }, { email: "bo@example.com", role: "viewer", sees: "all" }],
  "a new organisation: every site by default");
assert.ok(!location.hash.includes("@"), "still no email in the address");
await close();
for (const k of ["org", "ppl", "sees"]) assert.equal(readState()[k], "", `closing takes ${k} away`);

// Settings › Organisations' Add a site: setup=new&org=<id>. One of mine: "Another of mine",
// chosen; then "Sees: this site only" by default, "every site" in the address once picked.
posted.length = 0;
await openSiteKey("new", 0, { org: "7" });
await tick(30);
const checkedOf = (name) => dialog().querySelectorAll(`input[name="${name}"]`).filter((r) => r.getAttribute("checked") != null).map((r) => r.getAttribute("value"));
assert.deepEqual(checkedOf("sw-org"), ["other"], "org=7 opens on Another of mine");
const beta = dialog().querySelectorAll("option").find((x) => x.getAttribute("value") === "7");
assert.ok(beta.getAttribute("selected") != null, "Beta chosen");
assert.equal(dialog().querySelector(".sw-sees"), null, "no one to invite yet: no Sees line");
const em2 = dialog().querySelector('input[name="invite-email"]');
em2.value = "cy@example.com";
button(dialog(), "Add").click(); await tick();
assert.match(dialog().querySelector(".sw-sees").textContent, /Sees: this site only every site/);
assert.deepEqual(checkedOf("sw-sees"), ["site"], "an existing organisation: this site only by default");
const every = inputOf("sw-sees", "all");
every.checked = true; every.dispatchEvent(new Ev("change"));
assert.equal(readState().sees, "all");
assert.equal(readState().org, "7");
const addr2 = dialog().querySelector('input[name="site-address"]');
addr2.value = "beta-shop.example.net"; addr2.dispatchEvent(new Ev("input"));
await tick(DETECT_WAIT_MS + 60);
await next();
const add2 = posted.find(([p]) => p === "sites/add")[1];
assert.equal(add2.org, "7");
assert.deepEqual(add2.people, [{ email: "cy@example.com", role: "viewer", sees: "all" }]);
await close();
for (const k of ["org", "ppl", "sees"]) assert.equal(readState()[k], "", `closing Add a site takes ${k} away`);
// This organisation's own id (or one not mine): "This organisation".
await openSiteKey("new", 0, { org: "1" });
await tick(30);
assert.deepEqual(checkedOf("sw-org"), ["same"]);
await close();

console.log("setup-live: all passed");
process.exit(0);
