// #31: a lead's profile in its drawer (Leads & sales > Leads, owners and admins: who, every
// step with its time and value, newest first, their visits newest first (#55), proven or likely), and the Lead /
// Customer pill on Traffic > Visitors (the list and the visitor drawer; proven visits only).
// Shaped on freshlycited.com lead 1179. Addresses RFC 5737, emails at example.com.
//
//   node tests/js/lead-profile.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const PERSON = {
  ok: true, query: { kind: "lead", value: "u_1" }, kept: { identity: "full", keep_ips: true, ip_mode: "full", keep_days: 395 },
  visits: [], requests: [], leads: [], removed: [], journeys: [], candidates: [], withheld: {},
  keys: { ips: ["203.0.113.50"], emails: ["nate@example.com"], vids: [], leads: ["u_1"] },
  conversions: [
    { id: 8, tool: "lead", external_ref: "u_1", action: "signup", stage: "paid", at: "2026-11-11T16:50:14Z", value_minor: 4900, currency: "USD", email: "nate@example.com", name: "Nate Example", test: 0 },
    { id: 7, tool: "lead", external_ref: "u_1", action: "xray", stage: "completed", at: "2026-11-11T16:25:22Z", value_minor: null, currency: null, email: "nate@example.com", name: "Nate Example", test: 0 }],
  path: {
    visits: [
      { day: "2026-11-11", seq: 3, start: "2026-11-11T16:24:00Z", source: "Search engine", via: "bing.com", landing: "/bing-webmaster-tools/ai-performance-report",
        trail: [["/bing-webmaster-tools/ai-performance-report", "page", 0], ["/contact/", "app", 80]], link: "proven", why: "the only visit that sent a form at the lead's time",
        steps: [{ action: "xray", stage: "completed", at: "2026-11-11T16:25:22Z" }] },
      { day: "2026-11-11", seq: 9, start: "2026-11-11T17:02:00Z", source: "Direct or unknown", landing: "/app/", trail: [["/app/", "page", 0]], link: "likely", why: "the same address and browser as a proven visit", steps: [] }],
    unmatched: [{ action: "signup", stage: "paid", at: "2026-11-11T16:50:14Z", why: "no visit sent a form at its time" }],
    first: { start: "2026-11-11T16:24:00Z", source: "Search engine", via: "bing.com", landing: "/bing-webmaster-tools/ai-performance-report", link: "proven" } },
};
const asked = [];
globalThis.fetch = async (path) => {
  asked.push(String(path));
  if (String(path).startsWith("people?q=")) return { ok: true, status: 200, json: async () => structuredClone(PERSON) };
  return { ok: false, status: 404, json: async () => ({ ok: false, error: "not found" }) };
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const O = await import(new URL("overlays.js", JS));
const { ME } = await import(new URL("access.js", JS));
const L = await import(new URL("tabs/sa-leads.js", JS));
const V = await import(new URL("tabs/visitor.js", JS));
const VL = await import(new URL("tabs/visitlist.js", JS));
const P = await import(new URL("tabs/person.js", JS));

const top = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const fold = (d, title) => d.querySelectorAll("details.ui-fold").find((f) => f.querySelector("summary").textContent === title);
const J = { day: "2026-11-11", seq: 3, start: "2026-11-11T12:24:00-04:00", source: "Search", via: "bing.com", landing: "/bing-webmaster-tools/ai-performance-report",
  trail: [{ path: "/bing-webmaster-tools/ai-performance-report", page: true }], pages: 1, seconds: 80, country: "CA", device: "Desktop", browser: "Chrome", os: "Windows", flags: ["posted"], won: "customer" };
const J2 = { ...J, seq: 9, won: undefined, flags: [], landing: "/app/", trail: [{ path: "/app/", page: true }] };
const J3 = { ...J, seq: 12, won: "lead" };
const model = { site: "example.com", today: "2026-11-11", anchor: "2026-11-10", firstDay: "2026-08-01", byDay: new Map(), journeys: [J, J2, J3], journey_days: 7, x: {} };
S.on((next) => { O.sync(model, next); });
history.pushState(null, "", "#sales/leads?range=7d");
S.emit(true);
await tick(30);

// ---- the profile's parts, alone
const parts = P.profileParts(PERSON);
const words = parts.map((p) => p.textContent).join(" | ");
assert.match(words, /Who/);
assert.match(words, /Nate Example/);
assert.match(words, /nate@example\.com/);
assert.match(words, /Everything they did/);
assert.ok(words.indexOf("signup paid") < words.indexOf("xray completed"), "every step, newest first (#55)");
// #55: whatever order the steps come in, the newest is on top (the same time: the higher id).
const mixed = P.profileParts({ ...PERSON, conversions: [
  { id: 1, tool: "lead", external_ref: "u_1", action: "contact", stage: "started", at: "2026-11-01T09:00:00Z" },
  { id: 3, tool: "lead", external_ref: "u_1", action: "demo", stage: "completed", at: "2026-11-11T09:00:00Z" },
  { id: 2, tool: "lead", external_ref: "u_1", action: "contact", stage: "completed", at: "2026-11-01T09:00:00Z" }] });
const did = mixed[1].querySelectorAll("tbody tr").map((r) => r.textContent);
assert.ok(did[0].includes("demo completed") && did[1].includes("contact completed") && did[2].includes("contact started"), `newest on top: ${did}`);
assert.match(words, /\$49\.00 USD/, "a step's value");
assert.match(words, /First came from Search engine · bing\.com/);
assert.match(words, /Proven/);
assert.match(words, /Likely/);
const copies = parts.flatMap((p) => p.querySelectorAll("button.ua-copy")).map((b) => b.getAttribute("aria-label"));
assert.ok(copies.some((l) => /Nate Example/.test(l)), `a copy icon on the name: ${copies}`);
assert.ok(copies.some((l) => /nate@example\.com/.test(l)), "a copy icon on the email");
assert.ok(copies.some((l) => /u_1/.test(l)), "a copy icon on the reference");
// A site that keeps no names: said, none shown.
const anon = P.profileParts({ ...PERSON, kept: { identity: "anonymous" }, conversions: PERSON.conversions.map(({ email, name, ...r }) => r) });
assert.match(anon[0].textContent, /keeps no names or emails/);
// A site that keeps no visits with addresses: said, not hidden.
assert.match(P.profileParts({ ...PERSON, path: null })[2].textContent, /keeps no visits with their address/);

// ---- an owner opens a lead: the drawer, then the profile, asked by its reference
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const lead = { id: 1179, at: "2026-11-11T12:25:22-04:00", action: "signup", stage: "completed", now: "paid", tool: "lead", ref: "u_1", source: "Search engine",
  first_source: "Search engine", landing: "/bing-webmaster-tools/ai-performance-report", country: "CA", browser: false, steps: [], name: "Nate Example", email: "nate@example.com" };
await L.openLead(lead);
await tick(40);
let d = top();
assert.ok(asked.includes("people?q=u_1"), `asked by the reference: ${asked}`);
const prof = fold(d, "Their profile");
assert.ok(prof && (prof.open || prof.hasAttribute("open")), "the profile, open");
assert.match(prof.textContent, /Their visits, newest first/);
assert.match(prof.textContent, /\/bing-webmaster-tools\/ai-performance-report › \/contact\//, "the pages in order");
assert.match(prof.textContent, /audit log/);
const hash = decodeURIComponent(location.hash);
assert.match(hash, /lead=1179/, `the drawer is in the address by its row: ${hash}`);
assert.ok(!/u_1|nate|example\.com|203\.0\.113/.test(hash), `no reference, email or address in a link: ${hash}`);
// Show all, or any redraw, keeps it.
assert.equal(d.querySelectorAll("details.ui-fold").filter((f) => f.querySelector("summary").textContent === "Their profile").length, 1);
d.querySelector(".dw-x").click();
await tick(40);

// ---- a viewer: the drawer as before, nothing asked
Object.assign(ME, { role: "viewer" });
asked.length = 0;
await L.openLead({ ...lead, id: 1180, name: undefined, email: undefined });
await tick(40);
d = top();
assert.ok(!fold(d, "Their profile"), "no profile for a viewer");
assert.ok(!asked.some((p) => p.startsWith("people?q=")), "nothing asked");
d.querySelector(".dw-x").click();
await tick(40);

// ---- the pill, in the drawer's state card (proven only: a visit without `won` has none)
assert.deepEqual(V.statePills({ visits: [], leads: [], conversions: [], firstKnown: false, journey: J }).map(([k, w]) => [k, w]).pop(), ["good", "Customer"]);
assert.deepEqual(V.statePills({ visits: [], leads: [], conversions: [], firstKnown: false, journey: J3 }).map(([k, w]) => [k, w]).pop(), ["info", "Lead"]);
assert.ok(!V.statePills({ visits: [], leads: [], conversions: [], firstKnown: false, journey: J2 }).some(([, w]) => w === "Lead" || w === "Customer"));
await V.openVisitor(J);
await tick(40);
d = top();
assert.ok(d.querySelector(".vz-state").querySelectorAll(".ui-pill").some((p) => p.textContent.trim() === "Customer"), "Customer in the drawer");
d.querySelector(".dw-x").click();
await tick(40);

// ---- the pill, on the list
const r = { first: "2026-11-11", last: "2026-11-11", kind: "days", days: [{ day: "2026-11-11" }], length: 1 };
const list = VL.visitMatrix(model.journeys, model.journeys, r, 7);
document.body.append(list);
const pills = list.querySelectorAll(".ui-pill").map((p) => p.textContent.trim()).sort();
assert.deepEqual(pills, ["Customer", "Lead"], "one pill per proven visit, none on the likely one");
assert.equal(VL.wonWord(J), "Customer");
assert.equal(VL.wonWord(J2), "");
list.remove?.();

console.log("lead-profile: all passed");
process.exit(0);
