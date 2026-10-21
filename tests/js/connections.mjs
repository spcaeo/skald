// Settings > Connections (js/tabs/connections.js and conn-*.js) and the "Add a
// site" wizard (site-wizard.js, sitesadmin.js), drawn from real helper answers
// (tests/test_connections_page.py writes GET sites, tokens and sites/status to
// CONN_JSON): the three cards, Your tokens with each token's purpose, the send
// dialog walked step by step to a Test that reads the real status, the API and
// MCP tests, and the wizard from an address to its last step, then resumed.
// The site check (sites/detect) answers as the helper answered for a new site
// (nginx with Next.js) and for this one (behind Cloudflare's proxy): the "What
// Skald found" card, and the way it suggests chosen in the chooser.
//
//   CONN_JSON=answers.json node tests/js/connections.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install, Ev } from "./dom-lite.mjs";

install();
const given = JSON.parse(readFileSync(process.env.CONN_JSON, "utf8"));
const SITE = given.site;
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };

const posted = [];
let sites = given.sites;
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data });
  if (path === "sites") return answer(sites);
  if (path === "tokens") return answer(given.tokens);
  if (path.startsWith("sites/status")) return answer(given.status);
  if (path === "api/v1/") return answer({ ok: true, files: ["overview.json", "pages.json"] });
  if (path === "tokens/create") return answer({ ok: true, token: "skald_ab12cd34_" + "t".repeat(43), id: "ab12cd34", scopes: body.scopes, sites: body.sites });
  if (path === "sites/share") return answer({ ok: true, link: "https://www.example.com/traffic-auth/setup/" + "x".repeat(22), ref: "ab12cd34", expires_at: "2099-01-08T12:00:00Z" });
  if (path.startsWith("/traffic-auth/setup/")) {
    if (path.endsWith("/info")) return answer(given.share_info);
    if (path.endsWith("/reveal")) return answer({ ok: true, kind: "sending token", secret: "skald_ee12ff34_" + "s".repeat(43) });
    if (path.endsWith("/status")) return answer(given.status);
  }
  if (path === "sites/add") return answer({ ok: true, site: "www.example.org", token: null, verify: null });
  if (path === "sites/setup") return answer({ ok: true, setup: { name: body.name, step: body.step || 1 } });
  if (path === "sites/detect") return answer(body.address === SITE ? given.detect_here : given.detect_new);
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const words = await import(new URL("tabs/conn-words.js", JS));
const send = await import(new URL("tabs/conn-send.js", JS));
const read = await import(new URL("tabs/conn-read.js", JS));
const { default: connections } = await import(new URL("tabs/connections.js", JS));
const { default: sitesadmin } = await import(new URL("tabs/sitesadmin.js", JS));
const { siteFrom } = await import(new URL("tabs/site-wizard.js", JS));
const detect = await import(new URL("tabs/conn-detect.js", JS));
const radio = (root, id) => root.querySelectorAll("input").find((i) => i.getAttribute("value") === id);

const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
async function next() { button(dialog(), "Next").click(); await tick(); }

// The purpose words.
assert.equal(words.purposeOf(["ingest"]), "Sending logs");
assert.equal(words.purposeOf(["read"]), "Reading figures");
assert.equal(words.purposeOf(["read", "read_private"]), "Reading figures and addresses");
assert.equal(words.purposeOf("mcp"), "AI assistant (MCP)");
assert.equal(words.purposeOf(["read", "mcp"]), "Reading figures, AI assistant (MCP)");

// The page: three cards, then Your tokens with the real tokens and their purposes.
const root = document.createElement("div");
document.body.append(root);
root.append(...connections({ site: SITE, x: { sites: { sites: [{ name: SITE }] } } }));
await tick();
const text = root.textContent;
for (const t of ["Connections", "Send this site's visits to Skald", "Read your figures (API)", "Connect an AI assistant (MCP)", "Your tokens", "What it is for", "Make a token by hand"]) assert.ok(text.includes(t), t);
const purposes = root.querySelectorAll("td.cn-purpose").map((td) => td.textContent);
assert.ok(purposes.includes("Sending logs"), purposes.join("|"));
assert.ok(purposes.includes("Reading figures"), purposes.join("|"));
assert.equal(root.querySelectorAll(".cn-card").length, 3);

// The card's lines, from the helper's answer for a new site.
const lines = detect.foundLines(given.detect_new.found);
assert.deepEqual(lines.map((x) => [x.name, x.known]), [["Server", true], ["Platform", true], ["Built with", true], ["Host names", true]]);
assert.equal(lines[0].value, "nginx, on Ubuntu");
assert.equal(lines[2].value, "Next.js");
assert.equal(lines[3].value, "www.example.org and example.org");
assert.deepEqual(detect.foundLines({ reachable: true, server: "unknown", hosts: [] }).map((x) => x.value), ["could not tell", "could not tell", "could not tell", "could not tell"]);
assert.equal(detect.recommendFor({ found: given.detect_new.found, useFound: false }), null);

// The send dialog: what Skald found for this site, choose, token, install, test.
root.querySelectorAll(".cn-card button")[0].click();
await tick();
let d = dialog();
assert.ok(d, "the dialog opened");
assert.equal(d.querySelectorAll(".cn-bar li").length, 4);
assert.ok(d.textContent.includes("What Skald found"), "the card");
assert.ok(d.textContent.includes("Cloudflare (proxied)"), d.querySelector(".cn-found").textContent);
assert.deepEqual(posted.find(([p]) => p === "sites/detect")[1], { address: SITE, name: SITE });
assert.ok(radio(d, "cloudflare").checked, "the found way is chosen");
assert.ok(d.textContent.includes(`Recommended for ${SITE}`));
const use = d.querySelector('input[name="use-found"]');
use.checked = false;
use.dispatchEvent(new Ev("change"));
assert.ok(!radio(d, "cloudflare").checked, "Use these off: the found way is dropped");
assert.ok(!d.textContent.includes(`Recommended for ${SITE}`));
await next();
assert.ok(d.textContent.includes("Choose how the visits get to Skald."), "Next needs a choice");
const docker = radio(d, "docker");
docker.checked = true;
docker.dispatchEvent(new Ev("change"));
await next();
assert.ok(d.textContent.includes("Step 2 of 4: Sending token"));
const tokenName = d.querySelector('input[name="token-name"]');
assert.equal(tokenName.value.startsWith(`Sending logs: ${SITE}, `), true);
button(d, "Make a sending token").click();
await tick();
const made = posted.find(([p]) => p === "tokens/create")[1];
assert.deepEqual(made.scopes, ["ingest"]);
assert.deepEqual(made.sites, [SITE]);
assert.ok(d.textContent.includes("shown only this once"));
await next();
const shownSteps = d.textContent;
assert.ok(shownSteps.includes(`https://www.example.com/traffic-ingest/${SITE}`), "the send address");
assert.ok(shownSteps.includes("Download the install kit (.zip)"));
assert.ok(shownSteps.includes("Put the token in the zip (only if you will send the zip privately)"));
assert.ok(shownSteps.includes("skald_ab12cd34_"), "the fresh token is filled in");
button(d, "Share with your developer").click();
await tick();
button(d, "Make the link").click();
await tick();
assert.deepEqual(posted.find(([p]) => p === "sites/share")[1], { site: SITE, task: "send", method: "docker", days: 7 });
assert.ok(d.textContent.includes("/traffic-auth/setup/"), "the link is shown");
await next();
button(d, "Test connection").click();
await tick();
assert.ok(d.textContent.includes("Connected: 4 lines received today"), d.querySelector(".cn-test-out").textContent);

// Refusals and waiting, in words.
const refused = { ...given.status, last_refusal: { at: "2099-01-01T10:41:00Z", code: 403, reason: "wrong_site", words: "The token is not for this site." } };
const v = send.verdict(refused, "docker");
assert.equal(v.kind, "bad");
assert.match(v.head, /^Refused at \d\d:\d\d: the token is not for this site\.$/);
assert.ok(v.fix.includes("sending token for this site"));
assert.equal(send.verdict({ ok: true, last_batch: null, today: null }, "docker").head, "Waiting for the first lines. Nothing has reached Skald yet.");
assert.equal(send.verdict({ ok: true, beacon: null }, "script").kind, "bad");
assert.equal(send.verdict({ ok: true, beacon: { events: 0 } }, "script").kind, "wait");

// API and MCP tests, against answers shaped like the server's.
const okApi = await read.testApi("https://www.example.com", SITE, "skald_x", async () => ({ status: 200, json: async () => ({ schema_version: 1, site: SITE, days: [] }) }));
assert.equal(okApi.head, "200: it works. The answer starts with: schema_version, site, days.");
assert.match((await read.testApi("https://www.example.com", SITE, "bad", async () => ({ status: 401 }))).head, /^401: the token is wrong/);
let rpc = 0;
const mcp = await read.testMcp("https://www.example.com/traffic-mcp", "skald_x", async (url, opts) => {
  rpc += 1;
  assert.equal(opts.headers.Authorization, "Bearer skald_x");
  const m = JSON.parse(opts.body).method;
  return { status: 200, json: async () => (m === "initialize" ? { jsonrpc: "2.0", id: 1, result: { serverInfo: { name: "skald" } } } : { jsonrpc: "2.0", id: 2, result: { tools: [{}, {}, {}] } }) };
});
assert.equal(mcp.head, "Connected: 3 tools.");
assert.equal(rpc, 2);
root.querySelectorAll(".cn-card button")[2].click();
await tick();
assert.ok(dialog().textContent.includes("Connect an AI assistant (MCP)"));
await next();
assert.ok(dialog().textContent.includes("claude mcp add --transport http skald"));

// The wizard: an address becomes the site; steps to the end; the progress is saved.
assert.deepEqual(siteFrom("https://WWW.Example.org/pricing"), { name: "www.example.org" });
assert.ok(siteFrom("not a site").error);
assert.ok(siteFrom("203.0.113.5").error);
const admin = document.createElement("div");
admin.append(...sitesadmin({ site: SITE }, {}));
await tick();
// #settings/sitesadmin?setup=new: the router opens the wizard (js/overlays.js -> openSiteKey).
const { openSiteKey } = await import(new URL("tabs/sitesadmin.js", JS));
await openSiteKey("new", 1);
await tick();
d = dialog();
assert.ok(d.textContent.includes("Step 1 of 5: Your site"), d.textContent.slice(0, 200));
const addr = d.querySelector('input[name="site-address"]');
addr.value = "https://WWW.Example.org/x";
addr.dispatchEvent(new Ev("input"));
assert.ok(d.textContent.includes("The site will be www.example.org"));
await tick(detect.DETECT_WAIT_MS + 100);             // the check waits for the typing to stop
const card = d.querySelector(".cn-found").textContent;
for (const t of ["What Skald found", "Server: nginx, on Ubuntu", "Built with: Next.js", "Host names: www.example.org and example.org", "Page assets: /_next/static/", "Use these", "Check again"]) assert.ok(card.includes(t), `${t} in ${card}`);
assert.ok(card.includes("www.example.org runs on its own nginx server (Ubuntu), so the log shipper kit is the way."), card);
assert.equal(posted.filter(([p]) => p === "sites/detect").pop()[1].address, "www.example.org");
await next();
const added = posted.find(([p]) => p === "sites/add")[1];
assert.equal(added.host, "www.example.org");
assert.equal(added.token, false);
assert.deepEqual(added.hosts, ["www.example.org", "example.org"]);
assert.deepEqual(added.asset_prefixes, ["/_next/static/"]);
const kept = posted.find(([p, b]) => p === "sites/setup" && b.step === 2)[1];
assert.equal(kept.found.recommended_method, "docker");
assert.equal(kept.found.use, true);
assert.ok(d.textContent.includes("Step 2 of 5") && d.textContent.includes("No proof needed"));
await next();
assert.ok(radio(d, "docker").checked, "step 3 chooses the found way");
assert.ok(d.textContent.includes("Recommended for www.example.org"));
assert.equal(d.querySelectorAll("em.cn-rec").length, 1);
const script = radio(d, "script");
script.checked = true;
script.dispatchEvent(new Ev("change"));
await next();
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.method === "script" && b.step === 4));
assert.ok(d.textContent.includes('data-site="www.example.org"'), "the tag for the new site");
await next();
assert.ok(d.textContent.includes("Step 5 of 5: Test and finish"));
assert.ok(button(d, "Finish later"));

// Resumed: a site at step 3 shows its badge, and the badge reopens the wizard there.
const halfFound = { site: "half.example.com", reachable: true, use: true, server: "unknown", platform: "vercel", platform_label: "Vercel", hosts: ["half.example.com"], recommended_method: "vercel", reason: "half.example.com runs on Vercel, so its log drain sends each request to Skald." };
sites = { ...given.sites, sites: [...given.sites.sites, { name: "half.example.com", status: "active", source: "dashboard", setup: { step: 3, method: "", done: false, found: halfFound }, quiet: false }] };
const again = document.createElement("div");
again.append(...sitesadmin({ site: SITE }, {}));
await tick();
const badge = button(again, "Setup: step 3 of 5, continue");
assert.ok(badge, "the badge");
badge.click();
await tick();
assert.ok(dialog().textContent.includes("Step 3 of 5: How visits reach Skald"));
assert.ok(!/\bnull\b|\bundefined\b/.test(dialog().textContent), "no stray null or undefined on step 3");
assert.ok(radio(dialog(), "vercel").checked, "resumed: the kept facts choose the way");
assert.ok(dialog().textContent.includes("Recommended for half.example.com"));
assert.ok(dialog().textContent.includes("its log drain sends each request"));
// The shared link's page: the steps, the secret shown once, the Test.
const { draw: drawShare } = await import(new URL("tabs/share-page.js", JS));
const page = document.createElement("main");
await drawShare(page, "x".repeat(22));
assert.ok(page.textContent.includes(`Send this site's visits to Skald: ${SITE}`));
assert.ok(page.textContent.includes(`https://www.example.com/traffic-ingest/${SITE}`));
assert.ok(!page.textContent.includes("skald_ee12ff34_"), "no secret before Show");
button(page, "Show the secret").click();
await tick();
assert.ok(page.textContent.includes("this page does not show it again"));
assert.ok(page.textContent.includes("skald_ee12ff34_"), "the steps now carry the token");
button(page, "Test connection").click();
await tick();
assert.ok(page.textContent.includes("Connected: 4 lines received today"));
console.log("connections: all passed");
process.exit(0);
