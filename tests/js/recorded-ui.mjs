// Recorded journeys on the dashboard (2.43, js/tabs/recorded.js), against answers shaped as
// journeys_api.py gives them:
//  - Traffic › Visitors' card: not drawn for a site that never connected and sent nothing;
//    its own figures (never the log's), the ten newest sessions and a fold for the rest;
//    "Figures withheld" and no figure when the recount did not match;
//  - a session's drawer (rj=<ref>): pages, actions, and the log's own visit for owners and
//    admins only; the address holds the opaque ref, never an address or an email;
//  - the visitor drawer's fold: the linked sessions and how each is linked; none for a viewer;
//  - Settings › Leads & tools' row: Not set up (Connect), Waiting, Working, Stopped;
//  - Connect (rjc=connect): Me / My developer / My AI agent; Me makes the secret and shows it
//    once with a copy icon; the developer's message never holds a secret; My AI agent makes a
//    line with the job connect-journeys.
//
//   node tests/js/recorded-ui.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const SITE = "www.example.org";
const BASE = "https://www.example.com";
Object.assign(globalThis.location, { origin: BASE, pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const SECRET = "journey-ui-test-secret-not-real-0000000000";
const IP = "203.0.113.7";
const session = (i, more = {}) => ({ ref: `s${String(i).padStart(12, "0")}`, start: `2026-10-20T1${i % 10}:00:00Z`, end: `2026-10-20T1${i % 10}:04:00Z`,
  seconds: 240, landing: "/pricing", pages: 3, events: 5, returning: i === 1, ended: i === 1 ? "booking_made" : "",
  trail: [["/pricing", 0], ["/features", 40], ["/book", 200]], actions: i === 1 ? [{ event: "booking_made", path: "/book", label: "Demo", at: 230 }] : [],
  touch: { source: "newsletter", medium: "email" }, script_id: i === 1, ...more });
let listing = null;
let visitAnswer = null;
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path.startsWith("recorded?")) return answer(listing);
  if (path.startsWith("recorded/session?")) {
    const admin = ["owner", "admin"].includes(ME.role);
    const x = { ...session(1), visitor_sessions: 2, ...(admin ? { ip: IP, email: "person@example.com" } : {}) };
    return answer({ ok: true, label: "Recorded by your site", private: admin, session: x,
      visits: admin ? [{ day: "2026-10-20", seq: 4, start: "2026-10-20T11:00:00Z", end: "2026-10-20T11:05:00Z", source: "Email", landing: "/pricing", pages: 3, linked_by: "address" }] : [] });
  }
  if (path.startsWith("recorded/visit?")) return answer(visitAnswer);
  if (path === "recorded/status") return answer({ ok: true, label: "Recorded by your site", site: SITE, connected: false, where: "",
    url: `${BASE}/traffic-hooks/${SITE}/journey`, withdraw_url: `${BASE}/traffic-hooks/${SITE}/journey/withdraw`,
    helper: `${BASE}/traffic-js/journeys.js`, last_received: null, counts: {}, events_30d: 0 });
  if (path === "recorded/connect") return answer({ ok: true, site: SITE, secret: SECRET, rotated: false,
    url: `${BASE}/traffic-hooks/${SITE}/journey`, withdraw_url: `${BASE}/traffic-hooks/${SITE}/journey/withdraw`, helper: `${BASE}/traffic-js/journeys.js` });
  if (path === "sites/agentlink") return answer({ ok: true, line: `finish setting up Skald for ${SITE} (connect recorded journeys) — read ${BASE}/traffic-kit/llms.txt and use code Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4zAb7dEf0hIj1 (works once, 24 hours)`,
    llms_url: `${BASE}/traffic-kit/llms.txt`, steps_url: `${BASE}/traffic-kit/x/steps`, expires_at: "2099-01-02T12:00:00Z", token_id: null, link_id: "1f3a9c2e7b1d4a51", cancelled: 0, jobs: body.jobs });
  if (path === "sites/agentstatus") return answer({ ok: true, state: "waiting", expires_at: "2099-01-02T12:00:00Z" });
  if (path.startsWith("sites/status")) return answer({ ok: true, last_batch: null, today: null });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const R = await import(new URL("tabs/recorded.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
const { ROUTE_KEYS } = await import(new URL("routekeys.js", JS));
const { setupItems } = await import(new URL("setup-items.js", JS));
const W = await import(new URL("tabs/agent-words.js", JS));
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const noPerson = () => assert.ok(!location.hash.includes(IP) && !location.hash.includes("@") && !location.hash.includes(SECRET), `nothing personal in ${location.hash}`);
history.replaceState(null, "", "#overview/summary");
const m = { site: SITE, today: "2026-10-21", journeys: [{ day: "2026-10-20", seq: 4, path: ["/pricing"] }], journey_days: 7 };
const r = { kind: "history", first: "2026-10-15", last: "2026-10-21", length: 7 };

// ---- the address keys are listed, kind overlay
for (const key of ["rj", "rjc"]) assert.equal(ROUTE_KEYS.find((k) => k.key === key)?.kind, "overlay", key);
// ---- the agent job's words
assert.equal(W.jobOf("connect-journeys").title, "Connect recorded journeys");

// ---- the card: nothing for a site that never connected
listing = { ok: true, label: "Recorded by your site", connected: false, state: "ok", figures: { sessions: 0, visitors: 0, page_views: 0, actions: 0 }, sessions: [] };
let card = R.recordedCard(m, {}, r);
document.body.append(card);
await tick();
assert.ok(!card.isConnected, "no card for a site that never connected");

// ---- its own figures, ten rows and a fold for the rest
const many = Array.from({ length: 13 }, (_, i) => session(i + 1));
listing = { ok: true, label: "Recorded by your site", connected: true, state: "ok", figures: { sessions: 13, visitors: 12, page_views: 39, actions: 1, by_event: {} }, sessions: many, private: true };
card = R.recordedCard(m, {}, r);
document.body.append(card);
await tick();
assert.ok(card.isConnected);
assert.match(card.querySelector("h3").textContent, /Recorded by your site/);
assert.ok(card.textContent.includes("From your site"), "labelled by where it came from");
const kpis = card.querySelectorAll(".kpi").map((k) => [k.querySelector(".k-l").textContent, k.querySelector(".k-v").textContent]);
assert.deepEqual(kpis, [["Sessions", "13"], ["Visitors", "12"], ["Pages read", "39"], ["Actions", "1"]]);
assert.equal(card.querySelector(".rj-list").childNodes.length, 10);
assert.ok(card.textContent.includes("Show the other 3"));
assert.ok(card.textContent.includes("newsletter / email"), "where it came from, as the site said");
assert.ok(card.textContent.includes("Booked"), "how it ended");
card.remove();

// ---- withheld: no figure
listing = { ...listing, state: "withheld", figures: null, why: "The figures did not match their recount from the raw events." };
card = R.recordedCard(m, {}, r);
document.body.append(card);
await tick();
assert.equal(card.querySelectorAll(".kpi").length, 0, "no figure when the recount does not match");
assert.ok(card.textContent.includes("Figures withheld."));
assert.equal(card.querySelectorAll(".rj-row").length, 10, "the sessions stay");

// ---- a session's drawer, as an owner
card.querySelector(".rj-row").click();
await tick(40);
let d = dialog();
assert.equal(readState().rj, "s000000000001");
assert.match(d.textContent, /Pages read \(3\)/);
assert.match(d.textContent, /Actions \(1\)/);
assert.ok(d.textContent.includes(IP), "the kept address, for an owner");
assert.ok(d.querySelector(".rj-facts .ua-host"), "a copy icon on the address");
assert.ok(d.textContent.includes("same address"), "the log's own visit, and how it is linked");
noPerson();
d.querySelector(".dw-x").click();
await tick(40);
assert.equal(readState().rj || "", "");
card.remove();

// ---- as a viewer: no address, no log visit
ME.role = "viewer";
assert.equal(typeof await R.openSession("not-a-ref", m), "string", "a bad ref says so");
await R.openSession("s000000000001", m);
await tick(40);
d = dialog();
assert.ok(!d.textContent.includes(IP), "no address for a viewer");
assert.ok(d.textContent.includes("Admins and owners see the server log's own visit here."));
d.querySelector(".dw-x").click();
await tick(40);

// ---- the visitor drawer's fold: owners and admins only
const fake = () => ({ el: { isConnected: true }, body: document.createElement("div") });
visitAnswer = { ok: true, label: "Recorded by your site", connected: true, sessions: [{ ...session(1), linked_by: "visitor_id" }] };
assert.equal(await R.visitRecorded(fake(), { day: "2026-10-20", seq: 4 }, m), null, "none for a viewer");
ME.role = "admin";
const vd = fake();
const sec = await R.visitRecorded(vd, { day: "2026-10-20", seq: 4 }, m);
assert.ok(sec && vd.recorded === sec, "kept on the drawer for a redraw");
assert.match(sec.textContent, /Recorded by your site \(1\)/);
assert.ok(sec.textContent.includes("linked by the script tag's visitor ID"));
visitAnswer = { ok: true, connected: false, sessions: [] };
assert.equal(await R.visitRecorded(fake(), { day: "2026-10-20", seq: 4 }, m), null, "nothing when the site never connected");

// ---- Settings › Leads & tools: one row from the doctor's line
const row = (status) => R.journeysRow(m, status);
let x = row([]);
assert.ok(x.textContent.includes("Not set up") && button(x, "Connect"), "Not set up, with Connect");
x = row([{ id: "journeys", state: "OFF", says: "connected; waiting for the first event from the site" }]);
assert.ok(x.textContent.includes("Waiting"));
x = row([{ id: "journeys", state: "OK", says: "the last event came 3 minutes ago" }]);
assert.ok(x.textContent.includes("Working") && x.textContent.includes("Last event 3 minutes ago"));
x = row([{ id: "journeys", state: "NEEDS ATTENTION", says: "no event since 9 days ago" }]);
assert.ok(x.textContent.includes("Stopped") && x.textContent.includes("No event since 9 days ago"));

// ---- the checklist line: only once connected
assert.equal(setupItems({}, { status: [], tools: [], settings: {} }).find((i) => i.id === "journeys"), undefined);
assert.equal(setupItems({}, { status: [{ id: "journeys", state: "OFF", says: "connected" }], tools: [], settings: {} }).find((i) => i.id === "journeys").act, "journeys");

// ---- Connect: Who will do it?
await R.openConnect(SITE);
await tick(40);
d = dialog();
assert.equal(readState().rjc, "connect");
assert.deepEqual(d.querySelectorAll(".ui-who-c").map((b) => b.getAttribute("data-who")), ["me", "dev", "agent"]);
d.querySelector('.ui-who-c[data-who="me"]').click();
await tick(40);
assert.equal(readState().by, "me");
button(d, "Make the secret").click();
await tick(40);
assert.deepEqual(posted.filter(([p]) => p === "recorded/connect").length, 1);
assert.ok(d.textContent.includes(SECRET) && d.textContent.includes("Shown once."), "the secret, once");
assert.ok(d.querySelector(".rj-made .ua-host"), "with a copy icon");
const top = d.querySelector(".rj-top").textContent;
assert.ok(top.includes("Waiting") && !top.includes("Not set up"), "the status follows the new secret");
assert.ok(d.textContent.includes("traffic-js/journeys.js"), "the page helper's line");
noPerson();
d.querySelector('.ui-who-c[data-who="dev"]').click();
await tick(40);
assert.ok(d.textContent.includes("SKALD_JOURNEY_SECRET") && !d.querySelector(".ui-who-path").textContent.includes(SECRET), "the message never holds the secret");
d.querySelector('.ui-who-c[data-who="agent"]').click();
await tick(40);
d.querySelector('button.ag-tile[data-agent="claude-code"]').click();
await tick(60);
assert.deepEqual(posted.filter(([p]) => p === "sites/agentlink").pop()[1], { site: SITE, jobs: ["connect-journeys"] });
noPerson();
d.querySelector(".dw-x").click();
await tick(40);
assert.equal(readState().rjc || "", "");
assert.equal(readState().by || "", "", "by leaves with the dialog");

// ---- the demo (tools/demo_recorded.py): the card and a session read from the demo's files, as a
//      viewer sees them; a period it has no answer for draws no card; Connect still says why not
const { setDemo, DEMO } = await import(new URL("demo.js", JS));
const asked = [];
const real = globalThis.fetch;
globalThis.fetch = async (path, opts) => { asked.push(path); return real(path.startsWith("data/demo/rl") ? "recorded?x" : "recorded/session?ref=s000000000001", opts); };
listing = { ok: true, label: "Recorded by your site", connected: true, state: "ok", figures: { sessions: 1, visitors: 1, page_views: 3, actions: 1, by_event: {} }, sessions: [session(1)], private: false };
Object.assign(ME, { mode: "basic", role: null });
setDemo({ api: { recorded: { [`recorded?first=${r.first}&last=${r.last}`]: "data/demo/rl.json", "recorded/session?ref=s000000000001": "data/demo/rs.json" } } });
assert.ok(DEMO.on);
card = R.recordedCard(m, {}, r);
document.body.append(card);
await tick(40);
assert.ok(card.isConnected && card.textContent.includes("Recorded by your site"), "the demo shows its sample sessions");
assert.deepEqual(asked, ["data/demo/rl.json"], "read from the demo's file, never the helper");
const other = R.recordedCard(m, {}, { ...r, first: "2026-01-01" });
document.body.append(other);
await tick(40);
assert.ok(!other.isConnected, "a period the demo has no answer for: no card");
const sd = await R.openSession("s000000000001", m);
await tick(40);
assert.ok(sd.body.textContent.includes("Pages read (3)"), "a session's drawer from its file");
assert.deepEqual(asked.slice(-1), ["data/demo/rs.json"]);
sd.close?.();
assert.match(await R.openConnect(SITE), /In the demo/);
card.remove();

console.log("recorded-ui: all passed");
process.exit(0);
