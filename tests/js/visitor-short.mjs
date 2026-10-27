// The visitor drawer, state first (2.42, js/tabs/visitor.js): one card with the state in pills,
// one sentence and one line of facts (each with its copy icon); the newest two visits, then
// "Show all (N)" (vall=1 in the address, gone when the drawer closes, and a link with it opens
// every visit); the rest behind folds; how the visits are linked behind "?".
//
//   node tests/js/visitor-short.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const day = (d) => `2026-10-${String(d).padStart(2, "0")}`;
const T = (d, hm) => `${day(d)}T${hm}:00-04:00`;
const J = { day: day(20), seq: 14, start: T(20, "10:00"), end: T(20, "10:04"), source: "Search", via: "google.com", landing: "/pricing/",
  trail: [["/pricing/", "page", 0], ["/signup/", "page", 30]], pages: 2, seconds: 240, country: "CA", city: "CA|Quebec|Montreal", device: "Mobile", browser: "Safari", os: "iOS",
  first_touch: { by: "address", day: day(8), source: "Social", via: "reddit.com", landing: "/blog/" } };
const kept = (d, extra = {}) => ({ day: day(d), seq: d, start: T(d, "09:00"), end: T(d, "09:03"), source: "Direct", landing: "/", trail: [["/", "page", 0]], pages: 1, seconds: 20, country: "CA", device: "Mobile", browser: "Safari", os: "iOS", ...extra });
const VISITS = { ok: true, found: true, visits: [{ ...J, first_touch: undefined }, kept(16), kept(12), kept(8, { source: "Social", via: "reddit.com", landing: "/blog/" })], leads: [], conversions: [] };
let asks = 0;
globalThis.fetch = async (path) => {
  if (String(path).startsWith("people/visitor")) { asks++; return { ok: true, status: 200, json: async () => structuredClone(VISITS) }; }
  return { ok: false, status: 404, json: async () => ({ ok: false, error: "not found" }) };
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const O = await import(new URL("overlays.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const V = await import(new URL("tabs/visitor.js", JS));
const K = await import(new URL("routekeys.js", JS));

const top = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const qOf = () => new URLSearchParams(location.hash.split("?")[1] || "");
const button = (root, re) => root.querySelectorAll("button").find((b) => re.test(b.textContent.trim()));
const model = { site: "example.com", today: day(20), anchor: day(19), firstDay: "2026-08-01", byDay: new Map(), journeys: [J], journey_days: 7, x: {} };
S.on((next) => { O.sync(model, next); });
async function load(hash) { history.pushState(null, "", hash); S.emit(true); await tick(40); }

// ---- the key is known, and leaves with the drawer
assert.ok(K.KEYS.has("vall") && K.INSIDE.includes("vall"), "vall is an inside key");
assert.equal(V.SHORT, 2);

// ---- the words
const two = { visits: [{ kind: "kept", start: T(20, "10:00"), endNode: { kind: "left" } }, { kind: "kept", start: T(8, "09:00"), source: "Social", via: "reddit.com" }], leads: [], conversions: [], firstKnown: true,
  firstTouch: { by: "address", day: day(8), via: "reddit.com", source: "Social" } };
assert.deepEqual(V.statePills(two).map(([k, w]) => [k, w]), [["info", "Returning"], ["off", "No lead linked"]]);
assert.match(V.stateLine(two), /^2 visits over 13 days\. First came from reddit\.com, /);
const booked = { visits: [{ kind: "kept", start: T(20, "10:00"), active: true, endNode: { kind: "booked", words: "booked a demo" } }], leads: [], conversions: [], firstKnown: true };
assert.deepEqual(V.statePills(booked).map(([k, w]) => [k, w]), [["good", "Here now"], ["good", "Booked a demo"]]);
assert.match(V.stateLine(booked), /^1 visit, on one day\./);

// ---- open from a visit: state first, two visits, Show all (4)
await load("#traffic/visitors?range=7d");
await V.openVisitor(J);
await tick(40);
let d = top();
assert.equal(qOf().get("vis"), `${day(20)}.14`);
const body = d.querySelector(".dw-body");
assert.ok(body.children[0].className.includes("vz-state"), "the state comes first");
const state = d.querySelector(".vz-state");
assert.deepEqual(state.querySelectorAll(".ui-pill").map((p) => p.textContent.trim()), ["Returning", "No lead linked"]);
assert.match(state.querySelector(".vz-line").textContent, /^4 visits over 13 days\. First came from reddit\.com, /);
const facts = state.querySelector(".vz-facts");
assert.match(facts.textContent, /Montreal/);
assert.match(facts.textContent, /Mobile, Safari on iOS/);
assert.match(facts.textContent, /First seen /);
assert.ok(facts.querySelectorAll("button").filter((b) => /^Copy /.test(b.getAttribute("aria-label") || "")).length >= 2, "copy icons on the place and the device");
assert.ok(state.querySelectorAll("button.ui-help").some((b) => b.getAttribute("aria-label") === "Help: How these visits are linked"), "how they are linked: behind ?");
assert.ok(!body.querySelector(":scope > p.note"), "no paragraph of notes on the screen");
assert.equal(d.querySelector(".dw-sub").textContent, "", "the header keeps only the title");
assert.equal(d.querySelector(".vz-journey").querySelectorAll(".jm-v").length, 2, "two visits drawn");
const all = button(d, /^Show all \(4\)$/);
assert.ok(all, "Show all (4)");
assert.deepEqual(d.querySelectorAll("details.ui-fold").map((f) => f.querySelector("summary").textContent), ["This visit: every detail", "Every visit as a table (4)"]);
assert.ok(d.querySelectorAll("details.ui-fold").every((f) => !f.open && !f.hasAttribute("open")), "the details are folded");
all.click();
await tick();
assert.equal(qOf().get("vall"), "1", `Show all is in the address: ${location.hash}`);
assert.ok(!button(top(), /^Show all/), "every visit drawn");
assert.equal(top().querySelector(".vz-journey").querySelectorAll(".jm-v").length, 4);
top().querySelector(".dw-x").click();
await tick(40);
assert.ok(!qOf().get("vis") && !qOf().get("vall"), `closing takes both keys away: ${location.hash}`);

// ---- a link with vall=1 opens every visit
await load(`#traffic/visitors?range=7d&vis=${day(20)}.14&vall=1`);
await tick(40);
d = top();
assert.ok(d?.className.includes("vz-dw"), "the link opens the drawer");
assert.ok(!button(d, /^Show all/), "vall=1: every visit");
assert.equal(d.querySelector(".vz-journey").querySelectorAll(".jm-v").length, 4);
d.querySelector(".dw-x").click();
await tick(40);

// ---- a lead linked: its fold is open, counted
VISITS.leads = [{ lead: 31, type: "demo", created_at: T(16, "09:02"), visit_start: T(16, "09:00") }];
const J2 = { ...J, seq: 15 };
model.journeys.push(J2);
await V.openVisitor(J2);
await tick(40);
d = top();
assert.deepEqual(d.querySelector(".vz-state").querySelectorAll(".ui-pill").map((p) => p.textContent.trim()), ["Returning", "Lead #31"]);
const lc = d.querySelectorAll("details.ui-fold").find((f) => f.querySelector("summary").textContent === "Leads and conversions (1)");
assert.ok(lc && (lc.open || lc.hasAttribute("open")) && lc.textContent.includes("Lead #31"), "the leads fold, open");
assert.ok(asks >= 2);

console.log("visitor-short: all passed");
process.exit(0);
