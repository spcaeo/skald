// Connect the dots (2.43): the plan (js/connect-plan.js: rows, states, what fits the site, the
// way Skald recommends, the next step, partly connected) and the shared "not connected yet"
// card (js/ui/connect.js) on each page whose source is missing: what it needs, what Skald
// found, Connect writing the dialog's own address key (setup=lead&way=<tool>, setup=search...),
// a viewer's "Ask an admin to connect it" with the dialog's link, AI answers' plain state,
// the partly-connected line, the way back to Leads & tools (lt=<group>) and alerts that need
// a source. Sample data only (example.com).
//
//   node tests/js/connect.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

const NEXT_VERCEL = { server: "vercel", server_label: "Vercel", platform: "vercel", platform_label: "Vercel", framework: "nextjs", framework_label: "Next.js",
  hosted_builder: false, tags: { ga4: ["G-ABC123"] }, forms: 1, checked_at: "2099-01-01T00:00:00Z" };
let integ = { ok: true, site: "example.com", sites: ["example.com"], found: NEXT_VERCEL,
  tools: [{ tool: "lead", name: "Your site's server (lead)", state: "needs_secret" }, { tool: "calendly", name: "Calendly", state: "needs_secret" }],
  status: [], webhooks: [] };
const asked = [];
globalThis.fetch = async (path) => {
  asked.push(String(path));
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (String(path).includes("integrations/yourtools")) return answer({ ok: true, tools: [] });
  if (String(path).includes("integrations")) return answer(integ);
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
const P = await import(new URL("connect-plan.js", JS));
const C = await import(new URL("ui/connect.js", JS));
const K = await import(new URL("routekeys.js", JS));
const leads = (await import(new URL("tabs/sa-leads.js", JS))).default;
const bookings = (await import(new URL("tabs/sa-bookings.js", JS))).default;
const revenue = (await import(new URL("tabs/sa-revenue.js", JS))).default;
const search = (await import(new URL("tabs/tr-search.js", JS))).default;
const events = (await import(new URL("tabs/events.js", JS))).default;
const { needsSource } = await import(new URL("tabs/si-alerts.js", JS));
const { neverSentAny } = await import(new URL("notset.js", JS));
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const text = (out) => flat(out).map((el) => (typeof el === "string" ? el : el.textContent)).join(" ");
const find = (out, sel) => flat(out).flatMap((el) => (el.querySelectorAll ? [...(el.matches?.(sel) ? [el] : []), ...el.querySelectorAll(sel)] : []));
const keyOf = (k) => new URLSearchParams(location.hash.split("?")[1] || "").get(k);
const owner = () => Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", install_admin: false });
const viewer = () => Object.assign(ME, { mode: "sessions", role: "viewer", user: "viewer@example.com", install_admin: false });

// ================================================================ the plan
// ---- states: hooks, your tools, the doctor's lines
assert.equal(P.hookState({ state: "received" }), "connected");
assert.equal(P.hookState({ state: "received", attention: true }), "failing");
assert.equal(P.hookState({ state: "missing" }), "failing");
assert.equal(P.hookState({ state: "never" }), "waiting");
assert.equal(P.hookState({ state: "needs_secret" }), "off");
assert.equal(P.yourState({ state: "answering" }), "connected");
assert.equal(P.yourState({ state: "no_key" }), "waiting");
assert.equal(P.yourState({ state: "stopped" }), "failing");
assert.equal(P.lineState({ state: "OK" }), "connected");
assert.equal(P.lineState({ state: "OFF", says: "waits for the first event" }), "waiting");
assert.equal(P.lineState(null), "off");
assert.deepEqual(P.stateWords("failing"), ["bad", "Failing"]);
assert.deepEqual(P.stateWords("nonsense"), ["off", "Not connected"]);

// ---- rows: every source, its group, its Connect address
const rows = P.rowsOf({ integ: { ...integ, tools: [...integ.tools, { tool: "stripe", name: "Stripe", state: "received", last_at: "2099-01-01T00:00:00Z" }],
  webhooks: [{ url: "https://crm.example.com/in" }] }, yours: { ok: true, tools: [{ id: "ga4", name: "Google Analytics", state: "off" }] } });
const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
assert.deepEqual(Object.keys(byId).sort(), ["calendly", "journeys", "lead", "script", "search", "stripe", "webhooks", "your-ga4"].sort());
assert.equal(byId.calendly.group, "bookings");
assert.deepEqual(byId.calendly.act, { setup: "lead", way: "calendly" });
assert.equal(byId.stripe.group, "payments");
assert.equal(byId.stripe.state, "connected");
assert.deepEqual(byId["your-ga4"].act, { setup: "tool-ga4" });
assert.deepEqual(byId.search.act, { setup: "search" });
assert.deepEqual(byId.journeys.act, { rjc: "connect" });
assert.equal(byId.webhooks.state, "connected");
assert.equal(byId.webhooks.line, "crm.example.com");
// every act names an address key the router knows (docs/ROUTES.md)
const known = new Set(K.ROUTE_KEYS.map((k) => k.key));
for (const r of rows) for (const k of Object.keys(r.act)) assert.ok(known.has(k), `${r.id}: ${k} is a routed key`);
assert.ok(known.has("lt") && known.has("way"), "lt and way are routed keys");

// ---- what fits the site: Stripe only where Stripe was found, journeys on Next.js, GA4 by its tag
assert.equal(P.fits(byId.calendly, NEXT_VERCEL), false, "no Calendly link on the home page");
assert.equal(P.fits(byId.calendly, { tags: { calendly: ["calendly.com/x"] } }), true);
assert.equal(P.fits(byId.journeys, NEXT_VERCEL), true);
assert.equal(P.fits(byId.journeys, { framework: "wordpress" }), false);
assert.equal(P.fits(byId["your-ga4"], NEXT_VERCEL), true);
assert.equal(P.fits(byId.stripe, null), true, "a connected row always fits");
assert.equal(P.fits(byId.lead, { hosted_builder: true }), false, "a hosted builder has no server of its own");

// ---- the way Skald recommends: the owner's kiwiform.com case, Next.js on Vercel
assert.deepEqual(P.recommend("leads", NEXT_VERCEL), { words: "Your site is Next.js on Vercel: send leads from your form's server action with the signed lead hook.", act: { setup: "lead", way: "lead" } });
assert.equal(P.recommend("leads", { framework: "wordpress", framework_label: "WordPress" }).act.way, "wordpress");
assert.equal(P.recommend("leads", { hosted_builder: true, platform: "wix", platform_label: "Wix" }).act.way, "json");
assert.equal(P.recommend("leads", { tags: { hubspot: ["js.hs-scripts.com"] } }).act.way, "hubspot");
assert.equal(P.recommend("bookings", { tags: { calcom: ["cal.com/example"] } }).act.way, "calcom");
assert.equal(P.recommend("payments", { tags: { stripe: ["js.stripe.com"] } }).act.way, "stripe");
assert.deepEqual(P.recommend("tools", NEXT_VERCEL).act, { setup: "tool-ga4" });
assert.deepEqual(P.recommend("tools", { platform: "vercel" }).act, { setup: "tool-vercel" });
assert.deepEqual(P.recommend("search", null).act, { setup: "search" });
assert.ok(P.otherWays("leads", NEXT_VERCEL).every(([, act]) => act.way !== "lead"), "Other ways leave the recommended one out");

// ---- the next step: a failing row first; else what helps most and fits
assert.equal(P.nextStep([{ ...byId.stripe, state: "failing" }, byId.lead], NEXT_VERCEL).button, "Fix it");
const n1 = P.nextStep(P.rowsOf({ integ }), NEXT_VERCEL);
assert.equal(n1.need, "leads");
assert.deepEqual(n1.act, { setup: "lead", way: "lead" });
const leadOn = P.rowsOf({ integ: { ...integ, tools: [{ tool: "lead", name: "Lead", state: "received" }, { tool: "calendly", name: "Calendly", state: "needs_secret" }] }, searchOn: true });
assert.equal(P.nextStep(leadOn, NEXT_VERCEL).need, "tools", "the GA4 tag was found");
assert.equal(P.nextStep(leadOn, { tags: {} }).need, "script");

// ---- facts as chips; the alerts' sources
assert.deepEqual(P.factsOf(NEXT_VERCEL).map((f) => f.label), ["Next.js", "Vercel", "1 form on the home page", "Google Analytics"]);
assert.equal(P.factsOf(NEXT_VERCEL)[3].value, "G-ABC123");
assert.deepEqual(P.factsOf(null), []);
assert.equal(P.groupOf("sale"), "payments");
assert.equal(P.groupOf("bookings_drop"), "bookings");
assert.equal(P.groupOf("crawler_spike"), "");

// ---- partly connected: what arrives, what is still missing
const cal = P.rowsOf({ integ: { ...integ, tools: [{ tool: "lead", name: "Lead", state: "needs_secret" }, { tool: "calendly", name: "Calendly", state: "received" }] } });
assert.equal(P.partly("leads", cal, null), "Leads arrive from Calendly; your forms are not connected.");
assert.equal(P.partly("leads", leadOn, { tags: { calendly: ["calendly.com/x"] } }), "Leads arrive from your server; bookings are not connected.");
assert.equal(P.partly("leads", leadOn, { tags: {} }), "", "nothing missing that fits");
assert.equal(P.partly("leads", P.rowsOf({ integ }), null), "", "nothing arrives: the card says it, not a line");

// ---- the script tag never sent anything
assert.equal(neverSentAny(null), true);
assert.equal(neverSentAny({ sent: {} }), true);
assert.equal(neverSentAny({ sent: { page_view: "2026-10-01" } }), false);
assert.equal(neverSentAny({ rows: [["2026-10-01", "cta_click", 0, "/", "", 3]] }), false);

// ================================================================ the card, on each page
location.hash = "#sales/leads";
owner();
const m = { site: "example.com", today: "2026-10-27", anchor: "2026-10-26", days: [], byDay: new Map(), journeys: [], x: {} };
const s = () => S.read();

// ---- Leads, nothing connected: what it needs, what Skald found, the recommended way, Connect
let out = flat(leads(m, s()));
let card = find(out, '.ui-conn[data-need="leads"]')[0];
assert.ok(card, "the leads card");
assert.match(card.textContent, /No lead source connected yet/);
assert.equal(find(out, ".ui-primary").length, 1, "one primary: Connect");
await tick(60);
assert.ok(card.textContent.includes("Skald found on example.com"), card.textContent);
assert.ok(card.textContent.includes("Next.js") && card.textContent.includes("Google Analytics"));
assert.ok(card.textContent.includes("Your site is Next.js on Vercel: send leads from your form's server action with the signed lead hook."));
assert.ok(card.querySelector(".ui-conn-other"), "Other ways, folded");
card.querySelector(".ui-conn-go").click();
await tick();
assert.equal(keyOf("setup"), "lead", location.hash);
assert.equal(keyOf("way"), "lead");
assert.equal(location.hash.split("?")[0], "#sales/leads", "the dialog opens over the page");
assert.ok(K.INSIDE.includes("way"), "way leaves with the dialog");
// its way back to Leads & tools
const src = find(out, ".ui-conn-src")[0];
assert.ok(src, "Sources: Leads & tools in the head");
assert.equal(src.getAttribute("href"), "#settings/site/leads?lt=leads");

// ---- Leads, partly connected: Calendly arrives, the forms do not
location.hash = "#sales/leads";
C.forgetSources();
integ = { ...integ, found: null, tools: [{ tool: "lead", name: "Lead", state: "needs_secret" }, { tool: "calendly", name: "Calendly", state: "received" }] };
const line = C.partlyLine(m, "leads");
assert.ok(line.hidden, "hidden until the answer comes");
await tick(60);
assert.equal(line.hidden, false);
assert.ok(line.textContent.includes("Partly connected"));
assert.ok(line.textContent.includes("Leads arrive from Calendly; your forms are not connected."), line.textContent);
line.querySelector("button").click();
await tick();
assert.equal(keyOf("setup"), "lead");

// ---- Bookings, Revenue, Search, Events: each its need
location.hash = "#sales/bookings";
C.forgetSources();
integ = { ...integ, found: { tags: { calendly: ["calendly.com/example/demo"] } } };
out = flat(bookings(m, s(), {}));
card = find(out, '.ui-conn[data-need="bookings"]')[0];
assert.ok(card, "the bookings card");
await tick(60);
assert.ok(card.textContent.includes("Calendly is on your home page (calendly.com/example/demo)"), card.textContent);
card.querySelector(".ui-conn-go").click();
await tick();
assert.equal(keyOf("way"), "calendly");
assert.equal(find(out, ".ui-conn-src")[0].getAttribute("href"), "#settings/site/leads?lt=bookings");

location.hash = "#sales/revenue";
out = flat(revenue(m, s()));
assert.equal(find(out, '.ui-conn[data-need="payments"]').length, 1, "the payments card");
assert.equal(find(out, ".ui-conn-src")[0].getAttribute("href"), "#settings/site/leads?lt=payments");

location.hash = "#traffic/search";
const sm = { ...m, x: { search: { engines: { google: {}, bing: {} } } } };
out = flat(search(sm, s()));
await tick();
card = find(out, '.ui-conn[data-need="search"]')[0];
assert.ok(card, "the search card");
assert.match(card.textContent, /Search Console is not connected yet/);
card.querySelector(".ui-conn-go").click();
await tick();
assert.equal(keyOf("setup"), "search");
assert.equal(location.hash.split("?")[0], "#traffic/search");
assert.equal(find(out, ".ui-conn-src")[0].getAttribute("href"), "#settings/site/leads?lt=search");

location.hash = "#sales/events";
out = flat(events(m, s()));
card = find(out, '.ui-conn[data-need="script"]')[0];
assert.ok(card, "the script tag card");
card.querySelector(".ui-conn-go").click();
await tick();
assert.equal(keyOf("setup"), "script");

// ---- one quiet line (a part of a page): Connect, never the page's primary
const ln = C.connectCard(m, "journeys", { mode: "line" });
assert.ok(ln.classList.contains("ui-conn-line"));
assert.equal(ln.querySelectorAll(".ui-primary").length, 0);
ln.querySelector("button.btn").click();
await tick();
assert.equal(keyOf("rjc"), "connect");

// ---- AI answers: their plain state, no push (the owner's rule)
const ai = C.connectCard(m, "ai", { mode: "plain" });
assert.ok(ai.textContent.includes("AI answers are off"));
assert.equal(ai.querySelector(".ui-pill.off").textContent, "Off");
assert.equal(ai.querySelectorAll("button.btn, .ui-primary").length, 0, "no Connect");

// ---- alerts that need a source
const alertM = { ...m, x: { conversions: { days: [{ day: "2026-10-26", state: "ok", by: { tool: { contact: { lead: 2 } } } }] } } };
const need = needsSource(alertM, [{ cause: "sale", on: true }, { cause: "bookings_drop", on: true }, { cause: "leads_drop", on: true }, { cause: "crawler_spike", on: true }]);
assert.ok(need, "a line");
assert.ok(need.textContent.includes("payments not connected") && need.textContent.includes("bookings not connected"), need.textContent);
assert.ok(!need.textContent.includes("leads from your forms not connected"), "leads arrive");
assert.deepEqual(need.querySelectorAll(".ui-conn-src").map((a) => a.getAttribute("href")), ["#settings/site/leads?lt=payments", "#settings/site/leads?lt=bookings"]);
assert.equal(needsSource(alertM, [{ cause: "sale", on: false }]), null, "a rule switched off needs nothing");

// ================================================================ a viewer
viewer();
location.hash = "#sales/leads";
const before = asked.length;
out = flat(leads(m, s()));
card = find(out, '.ui-conn[data-need="leads"]')[0];
assert.ok(card.classList.contains("quiet"));
assert.ok(card.textContent.includes("Ask an admin to connect it."), card.textContent);
assert.equal(find(out, ".ui-primary").length, 0, "no Connect for a viewer");
assert.ok(card.querySelector(".ui-conn-link").textContent.startsWith("https://app.example.com/traffic/example.com/#sales/leads?"), card.querySelector(".ui-conn-link").textContent);
assert.ok(card.querySelector(".ui-conn-link").textContent.includes("setup=lead"), "the link opens the set-up");
assert.ok(card.querySelector(".ua-copy"), "a copy icon on the link");
assert.equal(find(out, ".ui-conn-src").length, 0, "no Sources link for a viewer");
assert.equal(C.partlyLine(m, "leads"), null, "no partly line for a viewer");
await tick(60);
assert.equal(asked.length, before, "a viewer never asks GET integrations (it answers 403)");
const vline = C.connectCard(m, "tools", { mode: "line" });
assert.ok(vline.textContent.includes("Ask an admin to connect it"));
assert.equal(vline.querySelectorAll("button.btn").length, 0);

console.log("connect: all passed");
