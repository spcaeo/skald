// Lines for your sites (2.40: js/tabs/agent-many.js, agent-many-words.js), against a fake
// server shaped as docs/plans/2026-10-26-agent-everywhere.md says (GET sites/agentleft, POST
// sites/agentlink per site, tokens/create with mcp and setup, sites/add):
//  - the address: lines=all | site.<site> | mcp.<site> | add, parsed and written back the
//    same (a round trip), never a line, a code or a token;
//  - "Make a line for each site" makes one separate line per site that has jobs left (not
//    the one waiting for its domain), each with only that site's jobs;
//  - a site's line, its watch and its two lines (an MCP token with mcp and setup for that one
//    site, line 1 for Claude Code and Codex, line 2 "Set up Skald for this site");
//  - the box that adds several sites: one sites/add per name, token false, names cleaned;
//  - closing takes the key away; a link opens the same view again.
//
//   node tests/js/agent-many.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const PAGE = "a.example.com";
Object.assign(globalThis.location, { origin: "https://stats.example.com", pathname: `/traffic/${PAGE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const TOKEN = "skald_ab12cd34_" + "Zx9Yw8Vu7Ts6Rq5Po4Nm3Lk2Jh1Gf0Ed9Cb8Aa7Bb6";
const row = (site, jobs, more = {}) => ({ site, status: "active", pending: false, done: false, jobs,
  left: jobs.map((j) => ({ id: j, title: `Line ${j}`, state: "todo", says: "", optional: j === "script", job: j })), line: null, ...more });
let sites = [row("a.example.com", ["logs", "script"]), row("b.example.org", ["script"]), row("c.example.net", ["logs"], { pending: true }),
  row("d.example.com", [], { done: true, left: [] })];
let made = 0;
const newest = {};   // the server's newest line per site (agent.latest), as sites/agentleft answers it
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "sites/agentleft") return answer({ ok: true, sites: sites.map((r) => ({ ...r, line: newest[r.site] || null })), mcp: { url: "https://stats.example.com/traffic-mcp", on: true } });
  if (path === "sites/agentlink") {
    made += 1;
    const code = `Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4zAb7dEf0hIj${made}`;
    newest[body.site] = { link_id: `1f3a9c2e7b1d4a5${made}`, state: "waiting", expires_at: "2099-01-02T12:00:00Z", opened_at: null, keys_at: null, reported_at: null };
    return answer({ ok: true, line: `finish setting up Skald for ${body.site} (x) — read https://stats.example.com/traffic-kit/llms.txt and use code ${code} (works once, 24 hours)`,
      llms_url: "https://stats.example.com/traffic-kit/llms.txt", steps_url: `https://stats.example.com/traffic-kit/${code}/steps`,
      expires_at: "2099-01-02T12:00:00Z", token_id: null, link_id: `1f3a9c2e7b1d4a5${made}`, cancelled: 0, jobs: body.jobs });
  }
  if (path === "sites/agentstatus") return answer({ ok: true, state: "waiting", opened_at: null, keys_at: null, reported_at: null, expires_at: "2099-01-02T12:00:00Z", report: null });
  if (path === "tokens/create") return answer({ ok: true, token: TOKEN, id: "ab12cd34", scopes: body.scopes, sites: body.sites });
  if (path === "sites/add") {
    if (body.host === "full.example.com") return answer({ ok: false, error: "Your plan does not allow another site." }, 403);
    sites = [...sites, row(body.host, ["logs", "script"])];
    return answer({ ok: true, site: body.host, token: null, verify: null });
  }
  if (path.startsWith("sites/status")) return answer({ ok: true, last_batch: null, today: null });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", org: "Example" });
const { WATCH } = await import(new URL("tabs/agent-watch.js", JS));
Object.assign(WATCH, { every: 20, slowAfter: 60000, slow: 20, late: 20, lateFor: 120 });
const W = await import(new URL("tabs/agent-many-words.js", JS));
const { openLines, openLinesKey } = await import(new URL("tabs/agent-many.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
const { KEYS, OPENERS } = await import(new URL("routekeys.js", JS));
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const calls = (p) => posted.filter(([x]) => x === p);
const card = (site) => dialog().querySelector(`section[data-site="${site}"]`);
async function close() { dialog().querySelector(".dw-x").click(); await tick(400); }
history.replaceState(null, "", "#settings/org/sites");

// ---- the address: one key, a round trip
assert.ok(KEYS.get("lines") && OPENERS.includes("lines"), "lines is an overlay that opens the view");
for (const v of ["all", "add", "site.a.example.com", "mcp.b.example.org"]) assert.equal(W.linesValue(W.parseLines(v)), v, v);
for (const bad of ["", "site.", "mcp.<x>", "site.A.EXAMPLE", "keys.a.example.com", "site.a.example.com/x", "203.0.113.7x"]) assert.equal(W.parseLines(bad), null, bad);
assert.equal(W.linesValue({ view: "site", site: "../x" }), "all", "a bad site is never written");
assert.deepEqual(W.siteNames("https://Shop.Example.com/x?y=1\nblog.example.org, blog.example.org; nope localhost:8080 www.example.net."),
  { names: ["shop.example.com", "blog.example.org", "www.example.net"], bad: ["nope", "localhost:8080"], more: 0 });
assert.equal(W.siteNames(Array.from({ length: 30 }, (_, i) => `s${i}.example.com`).join("\n")).names.length, W.MOST_NEW);
assert.equal(W.siteNames(Array.from({ length: 30 }, (_, i) => `s${i}.example.com`).join("\n")).more, 5);
assert.deepEqual(W.lineSites(sites), ["a.example.com", "b.example.org"], "pending and finished sites get no line");
const two = W.twoLines("b.example.org", "https://stats.example.com/traffic-mcp", TOKEN);
assert.equal(two.claude, `claude mcp add --transport http skald https://stats.example.com/traffic-mcp --header "Authorization: Bearer ${TOKEN}"`);
assert.ok(two.codex.includes("[mcp_servers.skald-b-example-org]") && two.codex.endsWith(">> ~/.codex/config.toml"));
assert.equal(two.two, "Set up Skald for this site");
assert.equal(W.lineWords(null), "No line yet.");
assert.equal(W.lineWords({ state: "keys_taken", reported_at: "x" }), "The agent sent its report");

// ---- the view: every site, its own line each
const d = openLines();
await tick(50);
assert.equal(readState().lines, "all");
assert.ok(card("a.example.com") && card("b.example.org") && card("c.example.net") && card("d.example.com"));
assert.ok(card("c.example.net").textContent.includes("verified"), "pending: verify first");
assert.ok(!button(card("c.example.net"), "Make its line"), "no line before the domain is verified");
assert.ok(card("d.example.com").textContent.includes("Everything is set up."));
button(dialog(), "Make a line for each site").click();
await tick(80);
assert.deepEqual(calls("sites/agentlink").map(([, b]) => b), [{ site: "a.example.com", jobs: ["logs", "script"] }, { site: "b.example.org", jobs: ["script"] }],
  "one line per site, each with its own jobs");
assert.ok(dialog().textContent.includes("2 of 2 lines made, one per site."));
assert.ok(card("a.example.com").querySelector(".am-state").textContent.startsWith("Line sent"), "the card says its line is out at once");
assert.ok(!location.hash.includes("use code") && !location.hash.includes("Ab3dEf"), "never a line or a code in the address");
// A second press makes nothing new: each site already has its line.
button(dialog(), "Make a line for each site").click();
await tick(80);
assert.equal(calls("sites/agentlink").length, 2);

// One site's line and its watch: lines=site.<site>
button(card("b.example.org"), "Show its line").click();
await tick(40);
assert.equal(readState().lines, "site.b.example.org");
assert.ok(card("b.example.org").textContent.includes("Paste this into the AI agent working on b.example.org"));
assert.ok(card("b.example.org").querySelector(".ag-line"), "the line, its code hidden");
assert.ok(!card("b.example.org").querySelector(".ag-line").textContent.includes("Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4zAb7dEf0hIj2"), "code hidden until Show code");
assert.ok(card("b.example.org").textContent.includes("Watch its agent work"));
assert.ok(!card("a.example.com").querySelector(".ag-line"), "only the open site's line shows");

// The two lines: lines=mcp.<site>, a token for that one site with mcp and setup
button(card("a.example.com"), "Two lines (MCP)").click();
await tick(40);
assert.equal(readState().lines, "mcp.a.example.com");
button(card("a.example.com"), "Make the token for a.example.com").click();
await tick(40);
assert.deepEqual(calls("tokens/create").pop()[1], { name: "AI agent (MCP + set-up): a.example.com", sites: ["a.example.com"], scopes: ["mcp", "setup"] });
const blocks = card("a.example.com").querySelectorAll(".cn-code").map((b) => b.textContent);
assert.ok(blocks.some((t) => t.includes(`claude mcp add --transport http skald https://stats.example.com/traffic-mcp --header "Authorization: Bearer ${TOKEN}"`)));
assert.ok(blocks.some((t) => t.includes("Set up Skald for this site")));
assert.ok(card("a.example.com").textContent.includes("Never paste the token into a chat message"));
assert.ok(!location.hash.includes(TOKEN.slice(0, 20)), "never the token in the address");

// Several sites at once: one sites/add each, token false, the plan's refusal stops the rest
button(dialog(), "Add several sites").click();
await tick(30);
assert.equal(readState().lines, "add");
dialog().querySelector(".am-add textarea").value = "new1.example.com\nhttps://New2.example.com/\nfull.example.com\nafter.example.com\nnope";
button(dialog(), "Add these sites").click();
await tick(120);
assert.deepEqual(calls("sites/add").map(([, b]) => b), [{ host: "new1.example.com", token: false }, { host: "new2.example.com", token: false }, { host: "full.example.com", token: false }],
  "each added as Add a site adds it; a 403 (the plan, the role) stops the rest");
assert.ok(dialog().textContent.includes("Your plan does not allow another site."));
assert.ok(dialog().textContent.includes("Not site names, left out: nope."));
assert.ok(card("new1.example.com") && card("new2.example.com"), "each new site with its own line to make");
await close();
assert.equal(readState().lines, "", "closing takes the key away");

// ---- a link opens the same view
const r = await openLinesKey("site.b.example.org");
assert.equal(typeof r, "object");
await tick(50);
assert.equal(readState().lines, "site.b.example.org");
assert.ok(card("b.example.org").classList.contains("open"));
await close();
assert.equal(await openLinesKey("keys.x"), "That view is not one this page offers.");
Object.assign(ME, { role: "viewer" });
assert.equal(await openLinesKey("all"), "Not available to your role.");
void d;
console.log("agent-many: all passed");
