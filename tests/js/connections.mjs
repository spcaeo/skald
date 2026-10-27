// The connection pages (v2: Data › Send logs, AI assistants' MCP, API and Tokens & links
// tabs; js/tabs/set-site.js, set-ai.js, connections.js and conn-*.js) and the "Add a
// site" wizard (site-wizard.js, sitesadmin.js), drawn from real helper answers
// (tests/test_connections_page.py writes GET sites, tokens and sites/status to
// CONN_JSON): each tab's state and one button, Your tokens with each token's purpose, the send
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
let shareInfo = given.share_info;
// sites/link (2.30), as the contract says: the token, and a one-time command that holds it.
let links = 0;
const LINK_TOKEN = "skald_cd34ef56_" + "u".repeat(43);
const linkAnswer = (site) => ({ ok: true, url: `https://www.example.com/traffic-kit/${"k".repeat(21)}${++links}`,
  command: `curl -fsSL https://www.example.com/traffic-kit/${"k".repeat(21)}${links} | sudo bash`, expires_at: "2099-01-02T12:00:00Z",
  token: LINK_TOKEN, token_id: "cd34ef56", site });
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, blob: async () => new Blob(["file"]), headers: { get: () => null } });
  if (path === "sites/link") return answer(linkAnswer(body.site));
  if (path === "sites/kit" || path === "sites/pack" || path.endsWith("/kit")) return answer(null);
  if (path === "sites/packmail") return answer({ ok: true, sent_to: body.to });
  if (path === "sites") return answer(sites);
  if (path === "tokens") return answer(given.tokens);
  if (path.startsWith("sites/status")) return answer(given.status);
  if (path === "api/v1/") return answer({ ok: true, files: ["overview.json", "pages.json"] });
  if (path === "tokens/create") return answer({ ok: true, token: "skald_ab12cd34_" + "t".repeat(43), id: "ab12cd34", scopes: body.scopes, sites: body.sites });
  if (path === "sites/share") return answer({ ok: true, link: "https://www.example.com/traffic-auth/setup/" + "x".repeat(22), ref: "ab12cd34", expires_at: "2099-01-08T12:00:00Z" });
  if (path.startsWith("/traffic-auth/setup/")) {
    if (path.endsWith("/info")) return answer(shareInfo);
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
const { dataLogs } = await import(new URL("tabs/set-site.js", JS));
const { mcpTab, apiTab, tokensTab } = await import(new URL("tabs/set-ai.js", JS));
const { connOpener } = await import(new URL("tabs/connections.js", JS));
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
assert.equal(words.purposeOf(["mcp", "setup"]), "AI assistant (MCP), Making set-up lines for an AI agent");

// The tabs (v2): Send logs, its state and one button (Who will do it?, setup-finish.js), the
// rest under More options; Tokens & links with the real tokens and their purposes; MCP and
// API, each one button, how it works behind the "?".
const M = { site: SITE, x: { sites: { sites: [{ name: SITE }] } } };
const root = document.createElement("div");
document.body.append(root);
root.append(...[dataLogs(M)].flat(9).filter(Boolean));
const toks = document.createElement("div");
toks.append(...[tokensTab(M)].flat(9).filter(Boolean));
const mcpRoot = document.createElement("div");
mcpRoot.append(...mcpTab(M).flat(9).filter(Boolean));
const apiRoot = document.createElement("div");
apiRoot.append(...apiTab(M).flat(9).filter(Boolean));
await tick();
assert.ok(root.textContent.includes("Your server's log"));
assert.equal(root.querySelectorAll("button.set-go").length, 1, "one button");
assert.ok(root.querySelector("details.set-more"), "the rest under More options");
// v2: one row per token, with what it is for; New token is the tab's one primary (its form in a drawer, edit=token-new).
for (const t of ["Your tokens", "New token"]) assert.ok(toks.textContent.includes(t), t);
assert.equal(toks.querySelectorAll("button.set-primary").length, 1, "one primary: New token");
assert.ok(toks.querySelectorAll(".tok-rows .set-row").length >= 2, "the tokens as rows");
assert.ok(!toks.textContent.includes("cards above"), "no card above any more");
const purposes = toks.querySelectorAll(".set-row .cn-purpose").map((td) => td.textContent);
assert.ok(purposes.includes("Sending logs"), purposes.join("|"));
assert.ok(purposes.includes("Reading figures"), purposes.join("|"));
// The MCP tab: Connect an assistant (one button), the address, then the assistants' tokens
// only (none here).
const mtext = mcpRoot.textContent;
assert.equal(mcpRoot.querySelectorAll("button.set-go").length, 1, "one button");
assert.ok(mtext.indexOf("Connect an assistant") < mtext.indexOf("Assistants connected"), "the tokens after the button");
assert.ok(!mtext.includes("How it works"), "how it works is behind the ?");
assert.ok(mtext.includes("https://www.example.com/traffic-mcp"), "the MCP address");
assert.ok(mtext.includes("No token for an assistant yet"), "only mcp tokens: none of the two here");
assert.equal(mcpRoot.querySelectorAll(".cn-purpose").length, 0);
assert.ok(button(apiRoot, "Set up the API") && !apiRoot.textContent.includes("How it works"));
assert.ok(apiRoot.textContent.includes(`https://www.example.com/traffic-api/v1/${SITE}/`));

// The card's lines, from the helper's answer for a new site.
const lines = detect.foundLines(given.detect_new.found);
assert.deepEqual(lines.map((x) => [x.name, x.known]), [["Server", true], ["Platform", true], ["Built with", true], ["Host names", true]]);
assert.equal(lines[0].value, "nginx, on Ubuntu");
assert.equal(lines[2].value, "Next.js");
assert.equal(lines[3].value, "www.example.org and example.org");
assert.deepEqual(detect.foundLines({ reachable: true, server: "unknown", hosts: [] }).map((x) => x.value), ["could not tell", "could not tell", "could not tell", "could not tell"]);
assert.equal(detect.recommendFor({ found: given.detect_new.found, useFound: false }), null);

// The ways (2.30): one for a server, with or without Docker; the older ids map to it.
assert.deepEqual(words.METHODS.map((x) => x.id), ["server", "cloudflare", "vercel", "script"]);
assert.equal(words.METHODS[0].title, "My own server (nginx or Apache)");
assert.ok(words.METHODS[0].best);
assert.equal(words.wayId("docker"), "server");
assert.equal(words.wayId("systemd"), "server");
assert.equal(words.wayId("cloudflare"), "cloudflare");
assert.equal(words.methodOf("docker").id, "server", "an old link's way still has its words");
assert.equal(detect.recommendFor({ found: { ...given.detect_new.found, recommended_method: "systemd" } }).id, "server");
assert.deepEqual(send.stepsAfter({ method: "docker" }).map((s) => s.name), ["Run one command", "Test"]);
assert.deepEqual(send.stepsAfter({ method: "vercel" }).map((s) => s.name), ["Sending token", "Install", "Test"]);
assert.deepEqual(send.stepsAfter({ method: "script" }).map((s) => s.name), ["Install", "Test"]);

// The send dialog: what Skald found for this site, where it runs, then that way's steps.
// The page's own address first, so the dialog's keys are written beside it (state.js hashFor).
const { read: readState } = await import(new URL("state.js", JS));
history.replaceState(null, "", `#${readState().tab}`);
await connOpener("send", SITE)();
await tick();
let d = dialog();
const bar = () => d.querySelectorAll(".cn-bar li").map((li) => li.querySelector(".cn-t").textContent);
assert.ok(d, "the dialog opened");
assert.ok(d.textContent.includes("What Skald found"), "the card");
assert.ok(d.textContent.includes("Cloudflare (proxied)"), d.querySelector(".cn-found").textContent);
assert.deepEqual(posted.find(([p]) => p === "sites/detect")[1], { address: SITE, name: SITE });
assert.ok(radio(d, "cloudflare").checked, "the found way is chosen");
assert.ok(!radio(d, "docker") && !radio(d, "systemd"), "no older ways to choose");
assert.ok(d.textContent.includes(`Recommended for ${SITE}`));
assert.deepEqual(bar(), ["Where it runs", "Sending token", "Install", "Test"], "Cloudflare needs a token step");
// Cloudflare's token is made when its step is shown, with no press.
await next();
assert.ok(d.textContent.includes("Step 2 of 4: Sending token"));
await tick();
const made = posted.find(([p]) => p === "tokens/create")[1];
assert.deepEqual(made.scopes, ["ingest"]);
assert.deepEqual(made.sites, [SITE]);
assert.ok(made.name.startsWith(`Sending logs: ${SITE}, `), made.name);
assert.ok(d.textContent.includes("shown only this once") && d.textContent.includes("skald_ab12cd34_"));
button(d, "Back").click(); await tick();
await next();
assert.equal(posted.filter(([p]) => p === "tokens/create").length, 1, "drawn again: no second token");
button(d, "Back").click(); await tick();
const use = d.querySelector('input[name="use-found"]');
use.checked = false;
use.dispatchEvent(new Ev("change"));
assert.ok(!radio(d, "cloudflare").checked, "Use these off: the found way is dropped");
assert.ok(!d.textContent.includes(`Recommended for ${SITE}`));
assert.deepEqual(bar(), ["Where it runs", "Run one command", "Test"], "nothing chosen: the server way's steps");
await next();
assert.ok(d.textContent.includes("Choose how the visits get to Skald."), "Next needs a choice");
const server = radio(d, "server");
server.checked = true;
server.dispatchEvent(new Ev("change"));
assert.match(d.querySelector("h3.cn-h").textContent, /^Step 1 of 3/);
await next();
await tick();
// Run one command: sites/link asked once; the command shown with Copy; never in the address.
assert.ok(d.textContent.includes("Step 2 of 3: Run one command"), d.querySelector("h3.cn-h").textContent);
assert.deepEqual(posted.filter(([p]) => p === "sites/link").map(([, b]) => b), [{ site: SITE }]);
const cmd = d.querySelector(".cn-run .cn-code").textContent;
assert.ok(cmd.startsWith("curl -fsSL https://www.example.com/traffic-kit/") && cmd.includes("| sudo bash"), cmd);
assert.ok(d.textContent.includes(`Paste it on the web server of ${SITE}. It works once, for 24 hours.`));
assert.ok(!location.hash.includes("traffic-kit") && !location.hash.includes("skald_"), location.hash);
assert.equal(send.freshFor(SITE).token, LINK_TOKEN, "the link's token is the page's token now");
button(d, "Back").click(); await tick();
await next(); await tick();
assert.equal(posted.filter(([p]) => p === "sites/link").length, 1, "drawn again: the same command");
// One file, with the same token in it.
button(d, "Download as one file").click();
await tick();
assert.deepEqual(posted.filter(([p]) => p === "sites/kit").pop()[1], { site: SITE, method: "server", include_token: true, token: LINK_TOKEN });
// Email it to your server admin: the set-up pack, with the page's token; pack=1, never the address.
button(d, "Email it to your server admin").click();
assert.equal(readState().pack, "1", location.hash);
const to = d.querySelector('input[name="pack-to-1"]');
to.value = "admin@example.com";
button(d, "Send by email").click();
await tick();
assert.deepEqual(posted.filter(([p]) => p === "sites/packmail").pop()[1], { site: SITE, to: ["admin@example.com"], include_secrets: true, token: LINK_TOKEN });
assert.ok(d.textContent.includes("Sent to admin@example.com."));
assert.ok(!location.hash.includes("@") && !location.hash.includes("admin"), location.hash);
button(d, "Email it to your server admin").click();
assert.equal(readState().pack, "", "closed again: the key goes");
button(d, "Make a new command").click();
await tick();
assert.equal(posted.filter(([p]) => p === "sites/link").length, 2, "a new command on request");
assert.ok(d.querySelector(".cn-run .cn-code pre").textContent.endsWith("kkkkkkkkkkkkkkkkkkkkk2 | sudo bash"));
const shownSteps = d.textContent;
assert.ok(shownSteps.includes("Other ways: by hand with Docker / without Docker"));
assert.ok(shownSteps.includes(`https://www.example.com/traffic-ingest/${SITE}`), "the send address, by hand");
assert.ok(shownSteps.includes("Download the install kit (.zip)"));
assert.ok(shownSteps.includes("skald_cd34ef56_"), "the link's token is filled in by hand too");
// The kit's token choice: ticked by default; unticked, token=0 in the address (never the
// token), the token shown to copy, and the zip asked for without it. Back and Next redraw
// the step from the address; closing the dialog takes the key away.
const { KIT_WORDS } = await import(new URL("tabs/conn-install.js", JS));
const kitTick = () => d.querySelector('input[name="kit-token"]');
const kitText = () => d.querySelector(".cn-kit").textContent;
const kitAsked = async () => { button(d, "Download the install kit (.zip)").click(); await tick(); return posted.filter(([p]) => p === "sites/kit").pop()[1]; };
assert.ok(shownSteps.includes(KIT_WORDS.label) && KIT_WORDS.label === "Include the access token in the zip");
assert.equal(kitTick().checked, true, "ticked by default");
assert.ok(kitText().includes(KIT_WORDS.on), kitText());
assert.equal(d.querySelectorAll(".cn-kit .cn-code").length, 0, "ticked: no token block in the kit box");
assert.equal(readState().conn, "send");
assert.equal(readState().token, "", "ticked is the default: no key");
let asked = await kitAsked();
assert.equal(asked.include_token, true);
assert.ok(asked.token.startsWith("skald_cd34ef56_"));
kitTick().checked = false;
kitTick().dispatchEvent(new Ev("change"));
assert.equal(readState().token, "0", location.hash);
assert.ok(!location.hash.includes("skald_"), "the token itself never goes in the address");
assert.ok(kitText().includes(KIT_WORDS.off), kitText());
assert.ok(d.querySelector(".cn-kit .cn-code").textContent.includes("skald_cd34ef56_"), "the token to copy and send apart");
asked = await kitAsked();
assert.equal(asked.include_token, false);
assert.ok(!("token" in asked), "the token is not even sent for a zip without it");
button(d, "Back").click(); await tick();
await next();
assert.equal(kitTick().checked, false, "redrawn from the address (token=0): still unticked");
kitTick().checked = true;
kitTick().dispatchEvent(new Ev("change"));
assert.equal(readState().token, "", "ticked again: the key goes");
kitTick().checked = false;
kitTick().dispatchEvent(new Ev("change"));
button(d, "Share with your developer").click();
await tick();
button(d, "Make the link").click();
await tick();
assert.deepEqual(posted.find(([p]) => p === "sites/share")[1], { site: SITE, task: "send", method: "server", days: 7 });
assert.ok(d.textContent.includes("/traffic-auth/setup/"), "the link is shown");
await next();
await tick(); // the Test starts by itself when shown
await tick();
assert.ok(d.textContent.includes("Connected: 4 lines received today"), d.querySelector(".cn-test-out").textContent);
assert.equal(readState().token, "0", "the choice stays while the dialog is open");
d.querySelector(".dw-x").click();
await tick();
assert.equal(readState().conn, "", "closed");
assert.equal(readState().token, "", "closing the dialog takes the kit's key away");

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
button(mcpRoot, "Connect an assistant").click();
await tick();
assert.ok(dialog().textContent.includes("Connect an AI assistant (MCP)"));
// 2.39: the guide at the top, then Who will do it? (ui/who.js: Me or My AI agent). 2.40: Me,
// one step that holds the choice, the token and the command, in that order; then Test.
assert.equal(dialog().querySelector(".cn-guide a").textContent, "Read the MCP guide");
assert.match(dialog().querySelector("h3.cn-h").textContent, /^Step 1 of \d+: Who will do it\?/);
dialog().querySelector('.ui-who-c[data-who="me"]').click();
await tick(30);
assert.equal(readState().by, "me", location.hash);
assert.match(dialog().querySelector("h3.cn-h").textContent, /^Step 2 of 3: Connect your assistant/);
{
  const t = dialog().textContent;
  assert.ok(t.indexOf("Choose your assistant") < t.indexOf("Make a token for it") && t.indexOf("Make a token for it") < t.indexOf("claude mcp add"), "choose, token, command");
  assert.ok(t.includes("claude mcp add --transport http skald") && t.includes("<token>"), "the command, the token's place marked");
  const made = posted.filter(([p]) => p === "tokens/create").length;
  button(dialog(), "Make the token").click();
  await tick();
  assert.equal(posted.filter(([p]) => p === "tokens/create").length, made + 1);
  assert.deepEqual(posted.filter(([p]) => p === "tokens/create").pop()[1].scopes, ["mcp"]);
  const cmdNow = dialog().querySelectorAll(".cn-code").map((c) => c.textContent).find((x) => x.includes("claude mcp add"));
  assert.ok(cmdNow.includes("skald_ab12cd34_"), "made: the command holds the token");
  assert.ok(!location.hash.includes("skald_"), "never in the address");
  button(dialog(), "Claude Desktop").click();
  await tick();
  assert.equal(readState().asst, "claude-desktop", location.hash);
  assert.ok(dialog().textContent.includes("claude_desktop_config.json") && dialog().textContent.includes("mcp-remote"));
  await next();
  assert.match(dialog().querySelector("h3.cn-h").textContent, /^Step 3 of 3: Test/);
  dialog().querySelector(".dw-x").click();
  await tick();
  assert.equal(readState().asst, "", "closed: the assistant's key goes");
}

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
// 2.42: two steps. Step 1: the address, what Skald found in one line, the time zone, who connects it.
assert.ok(d.textContent.includes("Step 1 of 2: Your site"), d.textContent.slice(0, 200));
const addr = d.querySelector('input[name="site-address"]');
addr.value = "https://WWW.Example.org/x";
addr.dispatchEvent(new Ev("input"));
assert.ok(d.querySelector(".sw-found").textContent.includes("Looking at www.example.org..."));
await tick(detect.DETECT_WAIT_MS + 100);             // the check waits for the typing to stop
assert.match(d.querySelector(".sw-found").textContent, /^foundRuns on nginx.* · suggested: one command on the server$/);
assert.match(d.querySelector(".sw-zone").textContent, /^Time zone: \S+ Change$/, "one line, Change to type another");
d.querySelector("details.ui-fold").fill();          // What Skald found: the details behind the fold
const card = d.querySelector(".cn-found").textContent;
for (const t of ["What Skald found", "Server: nginx, on Ubuntu", "Built with: Next.js", "Host names: www.example.org and example.org", "Page assets: /_next/static/", "Use these", "Check again"]) assert.ok(card.includes(t), `${t} in ${card}`);
assert.ok(card.includes("www.example.org runs on its own nginx server (Ubuntu), so one command on that server sends its log."), card);
assert.equal(posted.filter(([p]) => p === "sites/detect").pop()[1].address, "www.example.org");
assert.match(d.textContent, /Who will connect it\?/);
assert.deepEqual(d.querySelectorAll(".ui-who-c").map((b) => b.dataset.who), ["me", "dev", "agent"]);
d.querySelector('.ui-who-c[data-who="me"]').click();
await tick();
assert.equal(readState().by, "me", location.hash);
await next();
const added = posted.find(([p]) => p === "sites/add")[1];
assert.equal(added.host, "www.example.org");
assert.equal(added.token, false);
assert.deepEqual(added.hosts, ["www.example.org", "example.org"]);
assert.deepEqual(added.asset_prefixes, ["/_next/static/"]);
const kept = posted.find(([p, b]) => p === "sites/setup" && b.step === 3)[1];
assert.equal(kept.found.recommended_method, "docker");
assert.equal(kept.found.use, true);
assert.equal(kept.method, "server", "the found way, saved with the progress");
assert.equal(readState().setup, "www.example.org", "the site made: the address names it, so a reload finds it");
assert.ok(!d.textContent.includes("No proof needed"), "no proof step when none is needed");
// Step 2, Me: the way Skald found (docker is the server way), its one command, then the wait.
assert.ok(d.textContent.includes("Step 2 of 2: Connect it"), d.querySelector("h3.cn-h").textContent);
assert.equal(readState().step, "2");
await tick();
assert.match(d.querySelector(".sw-way").textContent, /^My own server \(nginx or Apache\) found Another way$/);
assert.deepEqual(posted.filter(([p]) => p === "sites/link").pop()[1], { site: "www.example.org" });
assert.ok(d.querySelector(".cn-run .cn-code").textContent.includes("| sudo bash"));
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.token_id === "cd34ef56" && b.step === 4), "the token's id, never the token");
assert.ok(!posted.some(([p, b]) => p === "sites/setup" && JSON.stringify(b).includes("skald_")));
assert.equal(d.querySelector('input[name="kit-token"]').checked, true, "the by-hand kit's box: ticked by default");
assert.ok(d.querySelector(".cn-kit").textContent.includes(KIT_WORDS.on));
assert.ok(d.querySelector(".cn-test-out"), "Skald waits for the first lines on the same step");
// Another way: the choices, the found one marked; the script tag for the new site.
button(d, "Another way").click(); await tick();
assert.ok(radio(d, "server").checked, "the found way chosen");
assert.ok(d.textContent.includes("Recommended for www.example.org"));
assert.equal(d.querySelectorAll("em.cn-rec").length, 1);
const script = radio(d, "script");
script.checked = true;
script.dispatchEvent(new Ev("change"));
await tick();
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.method === "script" && b.step === 3));
assert.ok(d.textContent.includes('data-site="www.example.org"'), "the tag for the new site");
assert.ok(button(d, "Finish later"));
// Back to step 1 and My developer: a private link with the steps, and the same wait.
button(d, "Change").click(); await tick();
assert.ok(d.textContent.includes("Step 1 of 2: Your site"));
d.querySelector('.ui-who-c[data-who="dev"]').click();
await tick();
await next(); await tick(30);
assert.equal(readState().by, "dev");
assert.ok(button(d, "Share with your developer"), "the private link's button");
assert.ok(d.querySelector(".cn-test-out"));
dialog().querySelector(".dw-x").click();
await tick(400);
assert.equal(readState().by, "", "closing takes by away");

// Resumed: a site at step 3 shows "Finish setting up", and the badge reopens the wizard.
const halfFound = { site: "half.example.com", reachable: true, use: true, server: "unknown", platform: "vercel", platform_label: "Vercel", hosts: ["half.example.com"], recommended_method: "vercel", reason: "half.example.com runs on Vercel, so its log drain sends each request to Skald." };
sites = { ...given.sites, sites: [...given.sites.sites, { name: "half.example.com", status: "active", source: "dashboard", setup: { step: 3, method: "", done: false, found: halfFound }, quiet: false }] };
const again = document.createElement("div");
again.append(...sitesadmin({ site: SITE }, {}));
await tick();
const badge = button(again, "Finish setting up");
assert.ok(badge, "the badge");
badge.click();
await tick();
assert.ok(dialog().textContent.includes("Step 1 of 2: Your site"), "nothing chosen yet: who connects it first");
assert.match(dialog().querySelector(".sw-found").textContent, /Vercel · suggested: a log drain from Vercel or Netlify/, "the kept facts, in one line");
dialog().querySelector('.ui-who-c[data-who="me"]').click();
await next();
assert.ok(dialog().textContent.includes("Step 2 of 2: Connect it"));
assert.ok(!/\bnull\b|\bundefined\b/.test(dialog().textContent), "no stray null or undefined");
assert.match(dialog().querySelector(".sw-way").textContent, /^Vercel or Netlify found/, "resumed: the kept facts choose the way");
button(dialog(), "Another way").click(); await tick();
assert.ok(radio(dialog(), "vercel").checked);
assert.ok(dialog().textContent.includes("Recommended for half.example.com"));
assert.ok(dialog().textContent.includes("its log drain sends each request"));
// The site picker's link names no step (#settings/sitesadmin?setup=<site>): the saved way opens Connect it.
dialog().querySelector(".dw-x").click();
await tick(400);
sites.sites.at(-1).setup.method = "vercel";
await openSiteKey("half.example.com", 0);
await tick();
assert.ok(dialog().textContent.includes("Step 2 of 2: Connect it"), dialog().querySelector("h3.cn-h")?.textContent);
assert.equal(readState().by, "me", "a saved way is Me");
// An older link at step 5: Connect it.
dialog().querySelector(".dw-x").click();
await tick(400);
await openSiteKey("half.example.com", 5);
await tick();
assert.ok(dialog().textContent.includes("Step 2 of 2: Connect it"));
dialog().querySelector(".dw-x").click();
await tick(400);
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
// A link made for the server way (2.30): one file and its two commands, no one-time command
// (the page has no session for sites/link); the file asked for from the link's own address.
shareInfo = { ...given.share_info, method: "server", kit: { ...given.share_info.kit, server: true } };
const page2 = document.createElement("main");
await drawShare(page2, "y".repeat(22));
assert.ok(page2.textContent.includes(`sudo bash skald-install-${SITE}.sh`), page2.textContent.slice(0, 400));
assert.ok(!page2.textContent.includes("curl -fsSL"));
assert.ok(page2.textContent.includes("Other ways: by hand with Docker / without Docker"));
button(page2, "Show the secret").click();
await tick();
button(page2, "Download as one file").click();
await tick();
const shareKit = posted.filter(([p]) => p.endsWith("/kit")).pop();
assert.equal(shareKit[0], `/traffic-auth/setup/${"y".repeat(22)}/kit`);
assert.deepEqual(shareKit[1], { site: SITE, method: "server", include_token: true, token: "skald_ee12ff34_" + "s".repeat(43) });
// A used or expired one-time command is not shown again (HEAD answers 410; never uses it up).
{
  const cmd = "curl -fsSL https://stats.example.com/traffic-kit/" + "c".repeat(43) + " | sudo bash";
  const seen = [];
  const head = (status) => async (url) => { seen.push(url); return { status }; };
  assert.equal(await send.stillGood({ command: cmd }, head(410)), false);
  assert.equal(seen[0], "https://stats.example.com/traffic-kit/" + "c".repeat(43));
  assert.equal(await send.stillGood({ command: cmd }, head(200)), true);
  assert.equal(await send.stillGood({ command: cmd }, async () => { throw new Error("offline"); }), true);
  assert.equal(await send.stillGood({ command: cmd, expires_at: "2020-01-01T00:00:00Z" }, head(200)), false);
}
console.log("connections: all passed");
process.exit(0);
