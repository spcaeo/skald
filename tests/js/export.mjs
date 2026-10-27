// Export (2.42, js/export-dialog.js): one button asks "What do you need?", then only that path.
//  - the choices: a PDF of this page, the tables as CSV, a report by mail (owners and admins
//    with accounts only) and Everything for my own tools; one primary on each path;
//  - the address: dlg=export, kind=<pdf|csv|monthly|tools>, xch=1 while Change is open; a
//    link opens the same path; closing takes every key away; Back closes it;
//  - the old links: dlg=report (the report builder) opens kind=pdf with Change open, and
//    kind=client is read as monthly;
//  - the report by mail: who gets it (the last report's address), how often, this page's
//    part; Start sending posts settings/report-save; no mail server: the card, "Who will set
//    it up?" in the address as by=, and the PDF now as the one primary.
//
//   node tests/js/export.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; this.dispatchEvent?.(new Ev("close")); };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const H = { stack: [{ state: null, hash: "" }], at: 0 };
const written = [];
globalThis.history = {
  get state() { return H.stack[H.at].state; },
  pushState(state, _, hash) { H.stack.splice(H.at + 1); H.stack.push({ state, hash }); H.at += 1; location.hash = hash; written.push(hash); },
  replaceState(state, _, hash) { H.stack[H.at] = { state, hash }; location.hash = hash; written.push(hash); },
  back() { if (H.at > 0) { H.at -= 1; location.hash = H.stack[H.at].hash; } },
  go() {},
};
let mailReady = true;
const posted = [];
const REPORTS = () => ({ ok: true, periods: { last_week: "Last week", last_month: "Last month", month_to_date: "Month to date" },
  sections: ["summary", "sources", "pages", "places", "ai", "leads", "search_console", "notes"],
  section_words: { summary: "Summary", sources: "Where visitors came from", pages: "Top pages", places: "Countries", ai: "AI answers", leads: "Leads", search_console: "Search", notes: "Notes" },
  timezone: "America/New_York", reports: [{ id: 3, spec: { name: "Monthly", recipients: ["client@example.com"] } }], mail_ready: mailReady, search_console: false });
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "settings/reports") return answer(REPORTS());
  if (path === "settings/report-save") return answer({ ok: true, report: { id: 4, spec: body }, confirm: "asked" });
  if (path === "settings/report-preview") return answer({ ok: true, subject: "Monthly report", html: "<p>x</p>", coverage: [] });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const O = await import(new URL("overlays.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const X = await import(new URL("export-dialog.js", JS));
const { REGISTRY } = await import(new URL("table.js", JS));
const { primaries } = await import(new URL("ui/primary.js", JS));

const today = "2026-10-20";
const day = (d) => ({ day: d, state: "ok", requests: 10, readers: 4 });
const model = { site: "example.com", today, anchor: "2026-10-19", firstDay: "2026-10-01", tz: "America/New_York",
  byDay: new Map(["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19"].map((d) => [d, day(d)])), x: {}, views: [] };
const loadView = async () => model;
// main.js's restorers and its listener.
O.addRestorer("dlg:export", () => { const s = S.read(); return X.openExport(model, s, loadView, { kind: s.kind, change: s.xch === "1" }); });
O.addRestorer("dlg:report", () => X.openExport(model, S.read(), loadView, { kind: "pdf", change: true }));
S.on((next) => { O.sync(model, next); });
const qOf = () => new URLSearchParams(location.hash.split("?")[1] || "");
const open = () => document.body.querySelectorAll("dialog").filter((d) => d.open);
const top = () => open().pop();
const panel = document.getElementById("panel");
async function load(hash) { history.pushState(null, "", hash); panel.replaceChildren(); S.emit(true); await tick(40); }
async function back() { history.back(); S.emit(); await tick(); }
const kinds = (d) => d.querySelectorAll(".ui-who-c").map((b) => b.dataset.kind);
const checked = (d) => d.querySelector('.ui-who-c[aria-checked="true"]')?.dataset.kind || "";
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const tile = (d, k) => d.querySelector(`.ui-who-c[data-kind="${k}"]`);

// ---- the keys are registered, inside the dialog
assert.ok(K.KEYS.has("kind") && K.KEYS.has("xch"));
assert.ok(K.INSIDE.includes("kind") && K.INSIDE.includes("xch"), "they leave with the dialog");
assert.deepEqual(X.KINDS, ["pdf", "csv", "monthly", "tools"]);
assert.equal(X.kindOf("client"), "monthly");
assert.equal(X.kindOf("nope"), "");

// ---- opened from More: the question, nothing chosen, nothing drawn, no primary yet
await load("#overview/summary?range=7d");
REGISTRY.length = 0;
REGISTRY.push({ caption: "Top pages", file: "pages.csv", columns: [{ key: "path", label: "Page" }, { key: "views", label: "Views" }], rows: () => [{ path: "/", views: 3 }, { path: "/pricing/", views: 2 }] });
const startAt = H.at;
let d = X.openExport(model, S.read(), loadView).el;
await tick();
assert.equal(qOf().get("dlg"), "export");
assert.equal(qOf().get("kind"), null, "nothing chosen yet");
assert.match(d.textContent, /What do you need\?/);
assert.deepEqual(kinds(d), ["pdf", "csv", "monthly", "tools"]);
assert.match(tile(d, "pdf").textContent, /A PDF of this page.*Overview › Summary, .*as on screen/);
assert.match(tile(d, "csv").textContent, /The table on this page, or all in a ZIP/);
assert.equal(primaries(d), 0, "no primary before a choice");

// ---- each path: one primary, written in the address
tile(d, "pdf").click();
await tick();
assert.equal(qOf().get("kind"), "pdf");
assert.equal(primaries(d), 1);
assert.ok(button(d, "Print or save as PDF") && button(d, "Preview"));
assert.match(d.querySelector(".ex-what").textContent, /What is in it: this page \(Overview › Summary\)/);
assert.ok(d.querySelector(".ex-change").hidden, "the sections are behind Change");
button(d, "Change").click();
await tick();
assert.equal(qOf().get("xch"), "1", "Change is in the address");
assert.ok(!d.querySelector(".ex-change").hidden);
const boxes = d.querySelectorAll('.ex-change input[type="checkbox"]');
assert.ok(boxes.length > 10, "every section with figures");
const src = boxes.find((b) => b.getAttribute("value") === "traffic/sources");
src.checked = true;
src.dispatchEvent(new Event("change"));
await tick();
assert.match(d.querySelector(".ex-what").textContent, /2 sections/);

tile(d, "csv").click();
await tick();
assert.equal(qOf().get("kind"), "csv");
assert.equal(qOf().get("xch"), null, "another path closes Change");
assert.equal(primaries(d), 1);
assert.ok(button(d, "Download all (ZIP)"));
const rows = d.querySelectorAll(".ex-t");
assert.equal(rows.length, 1);
assert.match(rows[0].textContent, /Top pages.*2 rows/);
assert.equal(rows[0].querySelector("button").getAttribute("aria-label"), "Download Top pages as CSV");

tile(d, "tools").click();
await tick();
assert.equal(qOf().get("kind"), "tools");
assert.equal(primaries(d), 1);
assert.ok(button(d, "Download JSON"));
assert.ok(d.querySelector('a[href="#settings/ai/assistants?sub=api"]') && d.querySelector('a[href="#settings/ai/assistants?sub=mcp"]'));

tile(d, "monthly").click();
await tick(40);
assert.equal(qOf().get("kind"), "monthly");
assert.equal(primaries(d), 1);
assert.equal(d.querySelector('input[type="email"]').value, "client@example.com", "the last report's address");
assert.match(d.querySelector(".ex-what").textContent, /this page \(Overview › Summary\)/);
button(d, "Start sending").click();
await tick(40);
const [, saved] = posted.find(([p]) => p === "settings/report-save");
assert.deepEqual(saved.recipients, ["client@example.com"]);
assert.deepEqual(saved.schedule, { kind: "monthly", day: 1, at: "08:00" });
assert.equal(saved.period, "last_month");
assert.deepEqual(saved.sections, ["summary"], "this page's part");
assert.match(d.textContent, /Done\. The report is on its way\./);
assert.match(d.textContent, /client@example.com gets it every month, on the 1st\. Each new address gets a link to confirm first\./);
assert.ok(d.querySelector('a[href="#settings/site/mail?sub=reports"]'));
d.querySelector(".dw-x").click();
await tick(40);
for (const k of ["dlg", "kind", "xch", "by"]) assert.equal(qOf().get(k), null, `closing takes ${k} away: ${location.hash}`);
assert.equal(H.at, startAt, "Back over the entry the opening made");

// ---- a link with kind opens that path; Back closes it
await load("#traffic/sources?range=7d&dlg=export&kind=csv");
d = top();
assert.ok(d?.className.includes("ex-dw"), "the link opens Export");
assert.equal(checked(d), "csv");
assert.ok(button(d, "Download all (ZIP)"));
await back();
assert.equal(open().length, 0, "Back closes it");

// ---- the old report builder's link: the PDF path, Change open, the address rewritten
await load("#overview/summary?range=7d&dlg=report");
d = top();
assert.ok(d?.className.includes("ex-dw"));
assert.equal(checked(d), "pdf");
assert.ok(!d.querySelector(".ex-change").hidden, "its sections open");
assert.equal(qOf().get("dlg"), "export");
assert.equal(qOf().get("kind"), "pdf");
assert.equal(qOf().get("xch"), "1");
d.querySelector(".dw-x").click();
await tick(40);

// ---- kind=client (an older word) is read as monthly; no mail server: the card and by=
mailReady = false;
ME.install_admin = true;
await load("#overview/summary?range=7d&dlg=export&kind=client");
d = top();
await tick(40);
assert.equal(checked(d), "monthly");
assert.ok(d.querySelector(".mr-note"), "the no mail server card");
assert.equal(primaries(d), 1);
assert.ok(button(d, "Download the PDF now"), "the PDF now is the one primary");
assert.ok(!button(d, "Start sending"));
d.querySelector('.mr-note .ui-who-c[data-who="dev"]').click();
await tick(40);
assert.equal(qOf().get("by"), "dev", "who sets it up is in the address");
assert.equal(qOf().get("kind"), "monthly", "and the path stays");
d.querySelector(".dw-x").click();
await tick(40);
assert.equal(qOf().get("by"), null);

// ---- a viewer, or a basic install: no report by mail
ME.role = "viewer";
ME.install_admin = false;
await load("#overview/summary?range=7d&dlg=export&kind=monthly");
d = top();
assert.deepEqual(kinds(d), ["pdf", "csv", "tools"]);
assert.equal(checked(d), "", "a path not offered opens on the question");
d.querySelector(".dw-x").click();
await tick(40);
ME.role = "owner";

// ---- no page with figures (Help): the PDF asks for the sections
await load("#help?dlg=export&kind=pdf");
d = top();
assert.match(tile(d, "pdf").textContent, /Choose the sections/);
assert.ok(!d.querySelector(".ex-change").hidden);
d.querySelector(".dw-x").click();
await tick(40);

// ---- opened again from More: on the last choice, so a PDF again is More, Export, Print
await load("#traffic/pages?range=7d");
d = X.openExport(model, S.read(), loadView).el;
await tick(40);
assert.equal(X.lastKind(), "monthly", "the last press");
assert.equal(checked(d), "monthly");
assert.equal(qOf().get("kind"), "monthly", "written in the address");
tile(d, "pdf").click();
await tick();
d.querySelector(".dw-x").click();
await tick(40);
d = X.openExport(model, S.read(), loadView).el;
await tick(40);
assert.equal(checked(d), "pdf");
assert.equal(primaries(d), 1);
d.querySelector(".dw-x").click();
await tick(40);

// ---- the address never held an address or an email
for (const hash of written) assert.ok(!/@|%40/.test(hash), `no email in ${hash}`);

console.log("export: all passed");
