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
root.querySelectorAll(".cn-card button")[0].click();
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
assert.ok(card.includes("www.example.org runs on its own nginx server (Ubuntu), so one command on that server sends its log."), card);
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
assert.ok(radio(d, "server").checked, "step 3 chooses the found way (docker, from the check, is the server way)");
assert.ok(d.textContent.includes("Recommended for www.example.org"));
assert.equal(d.querySelectorAll("em.cn-rec").length, 1);
// Step 4, the server way: the one command for the new site; its token id kept with the progress.
await next();
await tick();
assert.ok(d.textContent.includes("Step 4 of 5: Install"));
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.method === "server" && b.step === 4));
assert.deepEqual(posted.filter(([p]) => p === "sites/link").pop()[1], { site: "www.example.org" });
assert.ok(d.querySelector(".cn-run .cn-code").textContent.includes("| sudo bash"));
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.token_id === "cd34ef56"), "the token's id, never the token");
assert.ok(!posted.some(([p, b]) => p === "sites/setup" && JSON.stringify(b).includes("skald_")));
assert.equal(d.querySelector('input[name="kit-token"]').checked, true, "the by-hand kit's box: ticked by default");
assert.ok(d.querySelector(".cn-kit").textContent.includes(KIT_WORDS.on));
button(d, "Back").click(); await tick();
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
