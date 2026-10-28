// Settings › This site › Leads & tools (2.43, "connect the dots", js/tabs/set-leads.js): on top,
// "Next step for <site>" with what Skald found on the site and the one most useful thing to
// connect as the page's one primary, and "Connect everything left with your AI agent"
// (setup=finish-tools, by=agent); then one card per goal (Leads from your forms, Bookings,
// Payments, Search, Your own tools, Recorded journeys, Send each lead out), each row with its
// pill (Connected, Waiting, Failing, Not connected), when it last sent and one action; a
// connected row links to the page with its data; rows that do not fit the site fold under
// "More you can connect"; lt=<group> marks a group. tool=<id> drawers stay as they were.
//
//   node tests/js/set-leads.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
Element.prototype.scrollIntoView = function scrollIntoView() {};
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

// GET integrations, as integrations_api.py answers, with `found` (the site check): a Next.js
// site on Vercel with Calendly and the GA4 tag on its home page and two forms.
const FOUND = { server: "vercel", server_label: "Vercel", platform: "vercel", platform_label: "Vercel", framework: "nextjs", framework_label: "Next.js",
  hosted_builder: false, tags: { ga4: ["G-ABC123"], calendly: ["calendly.com/example/demo"] }, forms: 2, checked_at: "2099-01-01T00:00:00Z" };
const INTEG = {
  ok: true, site: "example.com", sites: ["example.com"], found: FOUND,
  tools: [
    { tool: "lead", name: "Your site's server (lead)", set: true, state: "received", last_at: "2099-01-01T10:00:00Z", deliveries: [] },
    { tool: "json", name: "Zapier, Make, n8n (json)", set: false, state: "needs_secret", deliveries: [] },
    { tool: "calendly", name: "Calendly", set: false, state: "needs_secret", deliveries: [] },
    { tool: "calcom", name: "Cal.com", set: false, state: "needs_secret", deliveries: [] },
    { tool: "stripe", name: "Stripe", set: true, state: "missing", problem: "the signing secret does not match", words: "a lead was refused", deliveries: [] },
    { tool: "hubspot", name: "HubSpot", set: false, state: "needs_secret", deliveries: [] },
    { tool: "typeform", name: "Typeform", set: false, state: "needs_secret", deliveries: [] },
  ],
  status: [
    { part: "Lead hook", state: "NEEDS ATTENTION", says: "the hook answered 403", fix: "Allow POST on `/traffic-hooks/` in nginx" },
    { part: "Log", state: "OK", says: "lines arrive" },
    { id: "script", part: "Script tag", state: "OK", says: "on your pages; the last event came 5 min ago" },
  ],
  webhooks: [{ id: "w1", url: "https://crm.example.com/in/skald" }],
};
const YOURS = {
  ok: true, site: "example.com", connected: 1, sync_minutes: 10,
  tools: [
    { id: "ga4", name: "Google Analytics", state: "answering", pill: "good", words: "Answering", ago: "2 h ago", counted_from: "Counted from: Google Analytics",
      key: { set: true, where: "file", who: "robot@project.example.com", problem: null }, in_env: false, options: { property: "123456789" },
      option_specs: { property: { label: "Property ID", words: "Its digits.", required: true, example: "123456789" } },
      key_words: "a Google service-account key file", permission: "Viewer on the property", make_key: "Google Cloud > IAM > Service accounts > Keys", suggest: {}, shares_key: "search",
      reports: {}, headline: [{ name: "sessions", label: "Sessions", value: 1200 }] },
    { id: "calendlyapi", name: "Calendly API", state: "off", pill: "off", words: "Not connected", ago: "never", counted_from: "Counted from: Calendly API",
      key: { set: false }, options: {}, option_specs: {}, reports: {}, headline: [] },
  ],
};
let integ = INTEG;
const posted = [];
globalThis.fetch = async (path, opts) => {
  if (opts?.body) posted.push([String(path), JSON.parse(opts.body)]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (String(path).includes("integrations/yourtools/")) return answer({ ok: true });
  if (String(path).includes("integrations/yourtools")) return answer(YOURS);
  if (String(path).includes("integrations")) return answer(integ);
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const L = await import(new URL("tabs/set-leads.js", JS));
const { forgetSources } = await import(new URL("ui/connect.js", JS));
const { toolKind } = await import(new URL("tabs/integrations.js", JS));
const keyOf = (k) => new URLSearchParams(location.hash.split("?")[1] || "").get(k);

// ---- the drawers' pills are unchanged (integrations.js)
assert.deepEqual(toolKind(INTEG.tools[0]), ["good", "Working"]);
assert.deepEqual(toolKind({ state: "needs_secret" }), ["off", "Not set up"]);

// ---- the page
const m = { site: "example.com", x: { sites: { sites: [{ name: "example.com" }] } } };
async function page(hash = "#settings/site/leads") {
  location.hash = hash;
  forgetSources();
  const root = document.createElement("div");
  document.body.replaceChildren(root);
  root.append(...TAB_RENDER["settings/site/leads"](m, { ...S.read(), tab: "settings/site/leads" }, {}).flat(9).filter(Boolean));
  await tick(80);
  return root;
}
let root = await page();
assert.equal(root.querySelectorAll("h1").length, 1, "one title");
assert.equal(root.querySelector("h1").textContent, "Leads & tools");
assert.equal(root.querySelectorAll(".stabs, [role=tablist]").length, 0, "no tabs");

// Next step: Stripe is failing, so fixing it comes first; what Skald found, as chips.
const next = root.querySelector(".lt-next");
assert.ok(next, "the Next step card");
assert.equal(next.querySelector("h2").textContent, "Next step for example.com");
assert.ok(next.textContent.includes("Stripe is not working"), next.textContent);
assert.equal(next.querySelector(".lt-next-go").textContent, "Fix it");
const chips = next.querySelectorAll(".ui-chip").map((c) => c.textContent);
assert.ok(chips.includes("Next.js") && chips.includes("Vercel") && chips.includes("2 forms on the home page"), chips.join(" | "));
assert.ok(chips.some((c) => c.startsWith("Google Analytics: G-ABC123")), "the GA4 tag, with its ID");
assert.ok(next.querySelector(".ua-copy"), "a copy icon on a found value");
assert.equal(root.querySelectorAll(".ui-primary").length, 1, "one primary on the page: the next step's");
assert.equal(root.querySelectorAll(".set-primary").length, 0, "no Connect a tool by the title while a next step exists");
assert.ok(next.querySelector(".lt-agent").textContent.includes("Connect everything left with your AI agent"));

// the red line: the check that needs attention; a hook's or the script tag's own check is its row's pill
const strips = root.querySelectorAll(".set-strip.s-bad");
assert.equal(strips.length, 1, strips.map((x) => x.textContent).join(" | "));
assert.ok(strips[0].textContent.includes("Lead hook") && strips[0].textContent.includes("the hook answered 403"));
strips[0].querySelector(".set-fix").click();
await tick();
assert.ok(strips[0].querySelector(".set-fixtext code"), "the fix, with its code");

// the groups, in order, each with its one-line why
const groups = root.querySelectorAll(".lt-group").map((g) => g.getAttribute("data-group"));
assert.deepEqual(groups, ["leads", "bookings", "payments", "search", "tools", "journeys", "out"]);
const group = (id) => root.querySelector(`.lt-group[data-group="${id}"]`);
assert.equal(group("leads").querySelector("h2").textContent, "Leads from your forms");
assert.ok(group("leads").querySelector(".ui-meta").textContent.length > 10, "its why");
const row = (id) => root.querySelector(`[data-row="${id}"]`);
const pillOf = (id) => row(id).querySelector(".ui-pill");
// Connected: the lead hook, with when it last sent and the way to its data
assert.equal(pillOf("lead").textContent, "Connected");
assert.ok(pillOf("lead").className.includes("good"));
assert.ok(row("lead").textContent.includes("Last received"), row("lead").textContent);
assert.equal(row("lead").querySelector(".lt-see").textContent, "See leads");
assert.equal(row("lead").querySelector(".lt-see").getAttribute("href").split("?")[0], "#sales/leads");
// Failing: Stripe, no See link while it fails
assert.equal(pillOf("stripe").textContent, "Failing");
assert.equal(row("stripe").querySelector(".lt-see"), null);
// Not connected and fits (Calendly is on the home page): in Bookings, with Connect
assert.equal(pillOf("calendly").textContent, "Not connected");
assert.ok(group("bookings").contains(row("calendly")));
assert.equal(row("calendly").querySelector(".lt-go").textContent, "Connect");
// Script tag (connected), in Leads; Your own tools: Google Analytics, connected, See on Overview
assert.equal(pillOf("script").textContent, "Connected");
assert.equal(pillOf("your-ga4").textContent, "Connected");
assert.equal(row("your-ga4").querySelector(".lt-see").textContent, "See on Overview");
assert.ok(row("your-ga4").textContent.includes("Last answer 2 h ago"));
// Recorded journeys fit a Next.js site; Send each lead out lists its address
assert.ok(group("journeys").contains(row("journeys")));
assert.ok(row("webhooks").textContent.includes("crm.example.com"));
// Search: not connected, fits every site
assert.equal(pillOf("search").textContent, "Not connected");

// More you can connect: rows that do not fit this site, folded
const more = root.querySelector(".lt-more");
assert.ok(more && more.tagName === "DETAILS", "a fold");
assert.match(more.querySelector("summary").textContent, /^More you can connect \(\d+\)$/);
more.open = true; more.dispatchEvent(new Event("toggle"));
await tick();
for (const id of ["json", "calcom", "hubspot", "typeform", "your-calendlyapi"]) assert.ok(more.contains(row(id)), `${id} under More`);
for (const id of ["lead", "calendly", "stripe"]) assert.ok(!more.contains(row(id)), `${id} not under More`);

// no glyph in a label (audit rule 19)
assert.ok(!/[✓✗◐▲▼⋯→›]/.test(root.textContent.replace(/Settings › [A-Za-z &]+/g, "")), `no glyphs: ${root.textContent.match(/[✓✗◐▲▼⋯→›]/)}`);

// ---- one action per row: Connect writes the dialog's key, Fix it opens Stripe's drawer
row("calendly").querySelector(".lt-go").click();
await tick(40);
assert.equal(keyOf("setup"), "lead", location.hash);
assert.equal(keyOf("way"), "calendly", location.hash);
root = await page();
row("search").querySelector(".lt-go").click();
await tick(40);
assert.equal(keyOf("setup"), "search");
root = await page();
root.querySelector(".lt-agent").click();
await tick(40);
assert.equal(keyOf("setup"), "finish-tools");
assert.equal(keyOf("by"), "agent");
root = await page();
root.querySelector(".lt-next-go").click();
await tick(60);
assert.equal(keyOf("tool"), "stripe", location.hash);

// ---- a connected row opens its drawer, its id in the address (as before)
root = await page();
row("lead").querySelector(".lt-open").click();
await tick(60);
assert.equal(keyOf("tool"), "lead", location.hash);
root = await page();
row("your-ga4").querySelector(".lt-open").click();
await tick(60);
const yd = document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
assert.equal(yd.querySelector(".dw-title").textContent, "Google Analytics");
assert.equal(keyOf("tool"), "your-ga4");
assert.ok(yd.textContent.includes("robot@project.example.com"), "whose key it is, to copy");
assert.equal(await L.openTool("your-nope", m), "That tool is not one Skald knows.");
assert.equal(await L.openTool("../x", m), "That tool is not one Skald knows.");

// ---- lt=<group> (a data page's Sources link): that group is marked
root = await page("#settings/site/leads?lt=bookings");
assert.ok(group("bookings").classList.contains("lt-hl"), "the group is marked");
assert.ok(!group("leads").classList.contains("lt-hl"));
// a group only under More opens the fold
root = await page("#settings/site/leads?lt=out");
assert.ok(group("out").classList.contains("lt-hl"));

// ---- nothing failing, a lead source on, Calendly found: the next step is Calendly
integ = { ...INTEG, tools: INTEG.tools.filter((t) => t.tool !== "stripe") };
root = await page();
assert.ok(root.querySelector(".lt-next").textContent.includes("Calendly is on your home page"), root.querySelector(".lt-next").textContent);
assert.equal(root.querySelector(".lt-next-go").textContent, "Connect");
root.querySelector(".lt-next-go").click();
await tick(40);
assert.equal(keyOf("setup"), "lead");
assert.equal(keyOf("way"), "calendly");

// ---- everything that fits connected: "All connected", Connect a tool by the title
integ = { ...INTEG, found: { ...FOUND, tags: {} }, tools: INTEG.tools.filter((t) => t.tool !== "stripe"),
  status: INTEG.status.filter((c) => c.state !== "NEEDS ATTENTION") };   // nothing to fix
const allOn = { ...integ };
// Search Console connected (the page's own search.json)
const m2 = { ...m, x: { ...m.x, search: { engines: { google: { connected: true } } } } };
location.hash = "#settings/site/leads";
forgetSources();
integ = allOn;
const r2 = document.createElement("div");
document.body.replaceChildren(r2);
r2.append(...TAB_RENDER["settings/site/leads"](m2, { ...S.read(), tab: "settings/site/leads" }, {}).flat(9).filter(Boolean));
await tick(80);
assert.ok(r2.querySelector(".lt-next.good"), "the card says all is connected");
assert.equal(r2.querySelector(".lt-next .ui-pill").textContent, "All connected");
assert.equal(r2.querySelector(".lt-next-go"), null);
assert.equal(r2.querySelectorAll(".set-primary").length, 1, "Connect a tool, the one primary, by the title");
assert.equal(r2.querySelector(".set-primary").textContent, "Connect a tool");

// ---- all connected, but a check needs a fix: never "All connected" over a red line (2.44)
integ = { ...allOn, status: [...allOn.status, { id: "place:lead", part: "Lead countries: Your site's server", state: "NEEDS ATTENTION", says: "Your last 3 leads came without the visitor's address", fix: "" }] };
forgetSources();
const r3 = document.createElement("div");
document.body.replaceChildren(r3);
r3.append(...TAB_RENDER["settings/site/leads"](m2, { ...S.read(), tab: "settings/site/leads" }, {}).flat(9).filter(Boolean));
await tick(80);
assert.equal(r3.querySelector(".lt-next.good"), null, "not green while something needs a fix");
assert.equal(r3.querySelector(".lt-next .ui-pill").textContent, "1 to fix");
assert.ok(r3.querySelector(".lt-next-w").textContent.includes("one thing needs a fix"));
assert.ok(r3.textContent.includes("Needs a fix"), "the red line's word");
integ = allOn;

// ---- a viewer sees why, not the tools
Object.assign(ME, { role: "viewer" });
const v = [L.leadsPage(m)].flat().filter(Boolean);
assert.ok(v[0].textContent.includes("Tools are for admins."));
assert.equal(await L.openTool("calendly", m), "Not available to your role.");

console.log("set-leads: all passed");
