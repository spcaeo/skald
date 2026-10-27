// Settings › This site › Leads & tools (v2, js/tabs/set-leads.js, the UX audit's mockup
// v-settings-after): one primary beside the title (Connect a tool); each connected tool a row
// with its status pill, the whole row opening its details in a drawer (tool=<id> in the
// address); a red line with Fix only for what is broken; the tools not connected in one quiet
// line; Send each lead out and Search Console as two small rows; no tabs, no glyphs.
//
//   node tests/js/set-leads.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

// GET integrations, as integrations_api.py answers: two tools connected (one working, one not),
// three not connected, one check that needs attention, one outgoing webhook.
const INTEG = {
  ok: true, site: "example.com", sites: ["example.com"],
  tools: [
    { tool: "calendly", name: "Calendly", set: true, state: "received", words: "last lead today", url: "https://app.example.com/traffic-hooks/x/calendly", deliveries: [{ received_at: "2099-01-01T10:00:00Z", http_status: 200, outcome: "lead" }] },
    { tool: "stripe", name: "Stripe", set: true, state: "missing", problem: "the signing secret does not match", words: "a lead was refused", deliveries: [] },
    { tool: "hubspot", name: "HubSpot", set: false, state: "needs_secret", deliveries: [] },
    { tool: "typeform", name: "Typeform", set: false, state: "needs_secret", deliveries: [] },
    { tool: "zapier", name: "Zapier", set: false, state: "needs_secret", deliveries: [] },
  ],
  status: [
    { part: "Lead hook", state: "NEEDS ATTENTION", says: "the hook answered 403", fix: "Allow POST on `/traffic-hooks/` in nginx" },
    { part: "Log", state: "OK", says: "lines arrive" },
    { part: "Hook Calendly", state: "NEEDS ATTENTION", says: "secret set, but nothing has arrived" },
  ],
  webhooks: [{ id: "w1", url: "https://crm.example.com/in/skald" }],
};
const asked = [];
globalThis.fetch = async (path) => {
  asked.push(path);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (String(path).includes("integrations")) return answer(INTEG);
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const L = await import(new URL("tabs/set-leads.js", JS));
const { toolKind } = await import(new URL("tabs/integrations.js", JS));

// ---- the pills: what each tool state reads as
assert.deepEqual(toolKind(INTEG.tools[0]), ["good", "Working"]);
assert.deepEqual(toolKind(INTEG.tools[1]), ["bad", "Not working"]);
assert.deepEqual(toolKind({ state: "never" }), ["warn", "Nothing yet"]);
assert.deepEqual(toolKind({ state: "ready" }), ["good", "Ready"]);
assert.deepEqual(toolKind({ state: "needs_secret" }), ["off", "Not set up"]);

// ---- the page
location.hash = "#settings/site/leads";
const root = document.createElement("div");
const m = { site: "example.com", x: { sites: { sites: [{ name: "example.com" }] } } };
root.append(...TAB_RENDER["settings/site/leads"](m, { ...S.read(), tab: "settings/site/leads" }, {}).flat(9).filter(Boolean));
await tick(60);
assert.equal(root.querySelectorAll("h1").length, 1, "one title");
assert.equal(root.querySelector("h1").textContent, "Leads & tools");
assert.equal(root.querySelectorAll(".stabs, [role=tablist]").length, 0, "no tabs");
const prim = root.querySelectorAll(".set-primary");
assert.equal(prim.length, 1, "one primary");
assert.equal(prim[0].textContent, "Connect a tool");
assert.ok(root.querySelector(".set-head .set-act .set-primary"), "beside the title");

// the red lines: the check that needs attention, and the tool that is not working
const strips = root.querySelectorAll(".set-strip.s-bad");
assert.equal(strips.length, 2, "one red line per broken thing; a tool's own check is its row's pill");
assert.ok(strips[0].textContent.includes("Lead hook") && strips[0].textContent.includes("the hook answered 403"));
assert.ok(strips[1].textContent.includes("Stripe"));
// Fix on a check shows the fix, its code as code
strips[0].querySelector(".set-fix").click();
await tick();
assert.ok(strips[0].querySelector(".set-fixtext code"), "the fix, with its code");
assert.equal(strips[0].querySelector(".set-fix"), null, "Fix pressed once");

// the connected tools: rows with a pill, the whole row a button
const rows = root.querySelectorAll(".set-rows button.set-row");
assert.equal(rows.length, 2, "Calendly and Stripe");
assert.ok(root.querySelector(".set-rows h2").textContent.includes("Connected (2)"));
assert.equal(rows[0].querySelector(".ui-pill.good").textContent, "Working");
assert.equal(rows[1].querySelector(".ui-pill.bad").textContent, "Not working");
assert.ok(/<svg class="ic"/.test(rows[0].querySelector(".sr-more").innerHTML), "the details icon is an icon, not a glyph");

// not connected: one quiet line, names only
const quiet = [...root.querySelectorAll(".set-quiet")].find((x) => x.textContent.includes("Not connected"));
assert.ok(quiet && quiet.textContent.includes("HubSpot") && quiet.textContent.includes("Zapier"));

// Send each lead out (on, one address) and Search Console (not set up)
const pair = root.querySelector(".set-pair");
assert.ok(pair.textContent.includes("Send each lead out") && pair.textContent.includes("crm.example.com"));
assert.ok(pair.querySelector(".ui-pill.good") && pair.querySelector(".ui-pill.off"));
assert.ok(pair.textContent.includes("Search Console & Bing"));
assert.ok(root.textContent.includes("Every check (3)"));

// no glyph in a label (audit rule 19)
assert.ok(!/[✓✗◐▲▼⋯→›]/.test(root.textContent), `no glyphs: ${root.textContent.match(/[✓✗◐▲▼⋯→›]/)}`);

// ---- a row opens its tool's drawer, its id in the address
rows[0].click();
await tick(60);
const dw = document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
assert.ok(dw && dw.className.includes("set-dw"), "the drawer is open");
assert.equal(dw.querySelector(".dw-title").textContent, "Calendly");
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("tool"), "calendly", location.hash);

// ---- an address that names a tool Skald does not know says so, and opens nothing
assert.equal(await L.openTool("../x", m), "That tool is not one Skald knows.");
assert.equal(await L.openTool("nosuch", m), "That tool is not one Skald knows.");

// ---- a viewer sees why, not the tools
Object.assign(ME, { role: "viewer" });
const v = [L.leadsPage(m)].flat().filter(Boolean);
assert.ok(v[0].textContent.includes("Tools are for admins."));
assert.equal(await L.openTool("calendly", m), "Not available to your role.");

console.log("set-leads: all passed");
