// Every state in the address (2.21, js/routekeys.js, js/overlays.js): each drawer and
// dialog that shows a record writes its key when it opens, a link with the key opens it
// again, Back closes it, closing takes the key away, a link to something not kept opens
// the page with one plain line; and no value in the address is ever an address (IPv4 or
// IPv6) or holds an "@". Every key state.js reads is in the registry.
//
//   node tests/js/routes.mjs
import assert from "node:assert/strict";
import { isIP } from "node:net";
import { install, Ev } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; this.dispatchEvent?.(new Ev("close")); };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });   // reduced motion: drawers close at once
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: "/traffic/example.com/" });

// A history that keeps its entries, so Back is Back; every address written is kept for the privacy check.
const written = [];
const H = { stack: [{ state: null, hash: "" }], at: 0 };
globalThis.history = {
  get state() { return H.stack[H.at].state; },
  pushState(state, _, hash) { H.stack.splice(H.at + 1); H.stack.push({ state, hash }); H.at += 1; location.hash = hash; written.push(hash); },
  replaceState(state, _, hash) { H.stack[H.at] = { state, hash }; location.hash = hash; written.push(hash); },
  back() { if (H.at > 0) { H.at -= 1; location.hash = H.stack[H.at].hash; backed += 1; } },
  go() {},
};
let backed = 0;
const answers = new Map();   // fetch path -> answer
globalThis.fetch = async (path) => {
  const key = [...answers.keys()].find((k) => String(path).startsWith(k));
  const data = key ? answers.get(key) : { ok: false, error: "not found" };
  return { ok: data.ok !== false, status: data.ok === false ? 404 : 200, json: async () => structuredClone(data) };
};
const tick = (ms = 10) => new Promise((r) => setTimeout(r, ms));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const O = await import(new URL("overlays.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { openVisitor } = await import(new URL("tabs/visitor.js", JS));
const { openLead } = await import(new URL("tabs/sa-leads.js", JS));

const qOf = () => new URLSearchParams(location.hash.split("?")[1] || "");
const open = () => document.body.querySelectorAll("dialog").filter((d) => d.open);
const top = () => open().pop();
const panel = document.getElementById("panel");
// main.js's listener: a change of what is open only is not a redraw; overlays.js opens or closes it.
let model = null;
S.on((next) => { O.sync(model, next); });
// Back, as the browser does it: the entry before, then popstate.
async function back() { history.back(); S.emit(); await tick(); }
async function load(hash) { history.pushState(null, "", hash); panel.replaceChildren(); S.emit(true); await tick(30); }

// ---- the registry covers every key the address can hold
for (const k of S.KNOWN()) assert.ok(K.KEYS.has(k), `${k} is listed in js/routekeys.js`);
for (const sec of S.SECTIONS) for (const [route] of sec.tabs) assert.ok(S.TABS.some(([r]) => r === route));
for (const k of K.OVERLAY) assert.ok(S.KNOWN().includes(k), `${k} is read by state.js`);
for (const k of K.ROUTE_KEYS) assert.ok(k.owner && k.means && ["global", "tab", "overlay"].includes(k.kind), k.key);

// ---- the visitor drawer: vis=<day>.<seq>
const today = "2026-10-20";
const J = { day: today, seq: 14, start: `${today}T10:00:00-04:00`, end: `${today}T10:04:00-04:00`, source: "Search", via: "google.com", landing: "/pricing/",
  trail: [["/pricing/", "page", 0], ["/signup/", "page", 30]], pages: 2, seconds: 240, country: "CA", device: "Desktop", browser: "Chrome", os: "macOS" };
model = { site: "example.com", today, anchor: "2026-10-19", firstDay: "2026-08-01", byDay: new Map(), journeys: [J], journey_days: 7, x: {} };
await load("#traffic/visitors?range=7d");
const before = location.hash;
ME.role = "viewer";   // a viewer opens the anonymous drawer; no person search is asked for
await openVisitor(J);
assert.equal(qOf().get("vis"), `${today}.14`, `opening writes the key: ${location.hash}`);
assert.equal(qOf().get("range"), "7d", "the rest of the address stays");
assert.ok(top()?.className.includes("vz-dw"), "the drawer is open");
await back();
assert.equal(location.hash, before, "Back leaves the drawer's entry");
assert.equal(open().length, 0, "Back closes the drawer");
await load(`#traffic/visitors?range=7d&vis=${today}.14`);
assert.ok(top()?.className.includes("vz-dw"), "the link opens the drawer again");
assert.ok(!S.hashFor({ ...S.read(), tab: "traffic/pages" }).includes("vis="), "a link to another tab never carries the drawer");
assert.ok(S.hashFor(S.read()).includes(`vis=${today}.14`), "this tab's own link does");
top().querySelector(".dw-x").click();
await tick();
assert.ok(!qOf().get("vis"), `closing takes the key away: ${location.hash}`);
// A visitor no longer kept: the page and one plain line.
await load("#traffic/visitors?vis=2020-01-01.3");
assert.equal(open().length, 0);
assert.match(panel.textContent, /That visitor is no longer kept \(journeys are kept 7 days\)\./);
assert.ok(!/unknown|error/i.test(panel.textContent), "never an error, never unknown");
assert.ok(!qOf().get("vis"), "the key is taken away");
ME.role = "owner";

// ---- a lead's row: lead=<id>
const LEAD = { id: 1287, at: `${today}T11:00:00-04:00`, action: "demo", now: "completed", tool: "calendly", source: "Search", landing: "/pricing/", country: "CA", steps: [], journey: [] };
answers.set("people/leads", { ok: true, rows: [LEAD] });
await load("#sales/leads?range=7d");
await openLead(LEAD);
assert.equal(qOf().get("lead"), "1287");
await back();
assert.equal(open().length, 0, "Back closes the lead");
await load("#sales/leads?range=7d&lead=1287");
assert.ok(top(), "the link reopens the lead");
top().querySelector(".dw-x").click();
await tick();
await load("#sales/leads?range=7d&lead=999");
assert.match(panel.textContent, /That lead is not in the period on screen/);

// ---- a cancelled, removed or test conversion: conv=<list>.<code>
const CONV = { at: `${today}T09:00:00-04:00`, action: "demo", stage: "completed", tool: "calendly", external_ref: "https://calendly.example.com/x/1", journey: [] };
answers.set("people/conversions?kind=test", { ok: true, rows: [CONV] });
const { openConvKey } = await import(new URL("tabs/sa-lists.js", JS));
await load("#sales/leads");
const { convRow } = await import(new URL("tabs/sa-lists.js", JS));
const code = `test.${K.codeOf(["test", CONV.at, CONV.action, CONV.stage, CONV.tool, CONV.external_ref].join("|"))}`;
assert.ok(convRow("test", CONV));
await load(`#sales/leads?conv=${code}`);
assert.ok(top(), "the conversion's drawer opens from its code");
top().querySelector(".dw-x").click();
await tick();
assert.equal(await openConvKey("test.rnothere"), "That conversion is no longer in its list.");

// ---- a request's detail: req=<code>, never its address
const ROW = { at: `${today}T10:00:00-04:00`, ip: "203.0.113.9", method: "GET", path: "/pricing/", status: 200, group: "people", rule: "browser", host: "example.com", kind: "page" };
answers.set("data/requests.json", { schema_version: 1, rows: [ROW], window_hours: 6, total: 1, from: ROW.at, until: ROW.at });
const RQ = await import(new URL("tabs/si-requests.js", JS));
const rcode = K.codeOf(`${ROW.at}|${ROW.ip}|${ROW.method}|${ROW.path}|${ROW.status}`);
await load(`#site/requests?req=${rcode}`);
assert.ok(top()?.className.includes("rq-dw"), "the request's detail opens from its code");
assert.ok(!location.hash.includes("203.0.113"), "the code, not the address");
// "Show every request from" the address: a token in the address, the address on screen.
top().querySelectorAll("button").find((b) => b.textContent.startsWith("Show every request from")).click();
await tick();
assert.ok(qOf().get("ip")?.startsWith("~"), `the address is a token: ${location.hash}`);
assert.equal(S.read().ip, "203.0.113.9", "and reads back in this browser");
assert.equal(await RQ.openRequestKey(model, S.read(), "rgone"), "That request is no longer in the recent log (it keeps the last 6 hours).");
// A token another browser made: the plain line, and the filter taken away.
await load("#site/requests?ip=~zzzzzzzzzz");
assert.match(panel.textContent, /made in another browser/);
assert.ok(!qOf().get("ip"));

// ---- the person search: who=<token>, never the search itself
answers.set("people?q=", { ok: true, query: { kind: "email", value: "person@example.com" }, visits: [], leads: [], conversions: [], requests: [], journeys: [], candidates: [], removed: [], kept: {} });
await load("#overview/summary");
await openVisitor({ q: "person@example.com" });
await tick();
assert.ok(qOf().get("who")?.startsWith("~"), `a token: ${location.hash}`);
assert.ok(!location.hash.includes("example.com?") && !decodeURIComponent(location.hash).includes("@"), "never the email");
const whoHash = location.hash;
await back();
assert.equal(open().length, 0, "Back closes the search");
await load(whoHash);
assert.ok(top(), "this browser opens it again");
top().querySelector(".dw-x").click();
await tick();
await load("#overview/summary?who=~qqqqqqqqqq");
assert.match(panel.textContent, /That search was made in another browser/);
ME.role = "viewer";
await load("#overview/summary?who=~qqqqqqqqqq");
assert.match(panel.textContent, /Not available to your role\./);
ME.role = "owner";

// ---- the lists of what the figures leave out: list=leftout | conv-<kind>
answers.set("people/left-out", { ok: true, leads: [], conversions: [] });
await load("#sales/leads?list=leftout");
assert.ok(top()?.textContent.includes("Left out of the figures"));
top().querySelector(".dw-x").click();
await tick();
assert.ok(!qOf().get("list"));

// ---- Retention: cohort=<first day>.<step>
answers.set("people/cohort", { ok: true, found: true, rows: [], listed: 0 });
model.x.retention = { identity: { by: "address", lookback: 90, reach: 90 }, offsets: { week: 8 },
  grains: { week: { cohorts: [{ start: "2026-10-05", end: "2026-10-11", state: "ok", size: 10, cells: { 1: [3, 1] }, status: { 1: "ok" } }] } } };
await load("#traffic/retention?cohort=2026-10-05.1");
assert.ok(top()?.textContent.includes("Came back"), "the cell's visitors open from the link");
assert.equal(qOf().get("cohort"), "2026-10-05.1");
top().querySelector(".dw-x").click();
await tick();
await load("#traffic/retention?cohort=2025-01-06.1");
assert.match(panel.textContent, /That group of visitors is no longer in the figures/);

// ---- Search: sq=<kind>.<engine>:<key>
model.x.search = { engines: { google: { connected: "sc-domain:example.com", summary: { days: 28 }, periods: { 28: { first: "2026-09-22", last: today, query: { rows: [["skald analytics", 3, 40, 0.075, 4.2]] } } } } } };
await load("#traffic/search?sq=query.google:skald%20analytics");
assert.ok(top()?.textContent.includes("skald analytics"), "the query's drawer opens");
top().querySelector(".dw-x").click();
await tick();
await load("#traffic/search?sq=query.google:nothing");
assert.match(panel.textContent, /That search row is not in the 28 days on screen/);

// ---- Connections: conn=send|api|mcp&step=<n>
answers.set("sites", { ok: true, sites: [{ name: "example.com", status: "active" }], tokens: [] });
answers.set("tokens", { ok: true, tokens: [] });
await load("#settings/api?conn=api&step=1");
assert.ok(top()?.textContent.includes("Read your figures (API)"), "the API dialog opens from the link");
assert.equal(qOf().get("step"), "1");
top().querySelector(".dw-x").click();
await tick();
assert.ok(!qOf().get("conn") && !qOf().get("step"), `closing takes both keys away: ${location.hash}`);
ME.role = "viewer";
await load("#settings/api?conn=send");
assert.match(panel.textContent, /Not available to your role\./);
ME.role = "owner";

// ---- the app's dialogs: dlg=keys | new | views | find
await load("#overview/summary?dlg=keys");
assert.ok(top()?.textContent.includes("keyboard shortcuts"));
assert.equal(qOf().get("dlg"), "keys");
await load("#overview/summary");
assert.equal(open().length, 0, "the key gone (Back): closed");
const { help } = await import(new URL("keys.js", JS));
help();
assert.equal(qOf().get("dlg"), "keys", "opening writes it");
await back();
assert.equal(open().length, 0, "Back closes it");
await load("#overview/summary?dlg=nope");
assert.match(panel.textContent, /That dialog is not in this version of the page\./);

// ---- Add a site: setup=new&step=<n> on Settings › Add or remove sites
answers.set("sites", { ok: true, can_add: true, sites: [], tokens: [] });
await load("#settings/sitesadmin?setup=new&step=1");
assert.ok(top()?.textContent.includes("Add a site"), "the wizard opens from the link");
top().querySelector(".dw-x").click();
await tick();
assert.ok(!qOf().get("setup"));
await load("#settings/sitesadmin?setup=other.example.com");
assert.match(panel.textContent, /That site is not one of this organisation's sites\./);

// ---- a sub-tab's choice stays in the address: <ns>_view
const { subView } = await import(new URL("tablestate.js", JS));
location.hash = "#site/alerts";
subView("alerts").set("ai", "all");
assert.equal(qOf().get("alerts_view"), "ai");
assert.equal(subView("alerts").get(), "ai");
subView("alerts").set("all", "all");
assert.ok(!qOf().get("alerts_view"), "the default leaves the address clean");

// ---- privacy: no value is ever an address or holds an "@"
// The drill-down by an address, a table's search box with an email, an old link with the address.
const { open: drill } = await import(new URL("drill.js", JS));
const { writeKeys, HASH } = await import(new URL("tablestate.js", JS));
await load("#site/requests");
drill("ip", "2001:db8::7");
assert.equal(S.read().dd, "ip:2001:db8::7", "the address reads back in this browser");
writeKeys({ req_q: "person@example.com" });
assert.equal(HASH.read().get("req_q"), "person@example.com");
S.set({ rules: "all~referrer:is:mail.example.com|path:has:/@team/" });
location.hash = "#site/requests?ip=198.51.100.7";
S.emit();   // an older link with the address in it: rewritten with a token
assert.ok(!location.hash.includes("198.51.100.7"), `rewritten: ${location.hash}`);
const values = [];
for (const hsh of [...written, location.hash]) for (const [k, v] of new URLSearchParams(String(hsh).split("?")[1] || "")) values.push([k, v]);
assert.ok(values.length > 40, `${values.length} values checked`);
for (const [k, v] of values) {
  assert.ok(!v.includes("@"), `${k}=${v} holds an @`);
  assert.equal(isIP(v), 0, `${k}=${v} is an address`);
  for (const part of v.split(/[|,;]/)) {
    const bare = part.replace(/^[a-z_]+:/, "");
    assert.equal(isIP(part), 0, `${k}: ${part} is an address`);
    assert.equal(isIP(bare), 0, `${k}: ${bare} is an address`);
  }
  assert.ok(!K.isPersonal(v), `${k}=${v} holds an address or an email`);
}
assert.ok(backed > 0, "Back was used to close what an opening pushed");
console.log("routes: all passed");
