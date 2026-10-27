// Add a site in two steps (2.42, js/tabs/site-wizard.js), against a fake helper:
//  - who connects it, from the address and the saved progress (byFrom), and what Skald found in
//    one line (foundWords);
//  - a new site: the address, "Who will connect it?" (Me, My developer, My AI agent), Next makes
//    the site and opens Connect it with only that path; every answer in the address (setup=<site>,
//    step, by), and closing takes them away;
//  - the proof step only when the server asks for it;
//  - older links: step=3, 4 or 5 is Connect it; agent=hand is by=me; agent=<id> is by=agent.
//
//   node tests/js/add-site.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const FOUND = { site: "blog.example.org", reachable: true, server: "nginx", server_label: "nginx", hosts: ["blog.example.org"], recommended_method: "server", reason: "It answers from its own nginx." };
let verify = null;
let sites = { ok: true, can_add: true, ingest_url: "https://app.example.com/traffic-ingest", sites: [
  { name: "example.com", status: "active", source: "dashboard", setup: null },
  { name: "half.example.org", status: "active", source: "dashboard", setup: { step: 4, method: "", done: false } },
  { name: "proof.example.org", status: "active", source: "dashboard", setup: { step: 2, method: "server", done: false }, verify: { state: "pending", txt: "skald-verify=abc", meta: '<meta name="skald-verify" content="abc">' } }] };
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "sites") return answer(sites);
  if (path === "sites/detect") return answer({ ok: true, found: { ...FOUND, site: body.address } });
  if (path === "sites/add") return answer({ ok: true, site: body.host, verify });
  if (path === "sites/setup") return answer({ ok: true });
  if (path === "sites/link") return answer({ ok: true, command: "curl -fsSL https://app.example.com/traffic-kit/" + "k".repeat(43) + " | sudo bash", url: "x", expires_at: "2099-01-02T12:00:00Z", token_id: "cd34ef56" });
  if (path.startsWith("sites/status")) return answer({ ok: true, last_batch: null, today: null });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const SW = await import(new URL("tabs/site-wizard.js", JS));
const { DETECT_WAIT_MS } = await import(new URL("tabs/conn-detect.js", JS));
const { openSiteKey } = await import(new URL("tabs/sitesadmin.js", JS));
const { read: readState } = await import(new URL("state.js", JS));

const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const heading = () => dialog().querySelector("h3.cn-h").textContent;
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
async function next() { button(dialog(), "Next").click(); await tick(30); }
async function close() { dialog().querySelector(".dw-x").click(); await tick(400); }
const who = (k) => dialog().querySelector(`.ui-who-c[data-who="${k}"]`);
history.replaceState(null, "", "#settings/org/sites");

// ---- the words
assert.equal(SW.byFrom({ by: "dev" }), "dev");
assert.equal(SW.byFrom({ by: "nope", agent: "hand" }), "me", "agent=hand is Me");
assert.equal(SW.byFrom({ agent: "codex" }), "agent");
assert.equal(SW.byFrom({ method: "agent" }), "agent");
assert.equal(SW.byFrom({ method: "vercel" }), "me", "a saved way is Me");
assert.equal(SW.byFrom({}), "", "nothing saved: the question");
assert.equal(SW.foundWords(FOUND), "Runs on nginx · suggested: one command on the server");
assert.equal(SW.foundWords({ ...FOUND, server: "unknown", platform_label: "Vercel", recommended_method: "vercel" }), "Server not told behind Vercel · suggested: a log drain from Vercel or Netlify");
assert.match(SW.foundWords({ site: "x.example.org", reachable: false }), /could not reach x\.example\.org/);
assert.equal(SW.STEPS, 5, "the server's scale is kept");

// ---- a new site, Me: two presses after the address (Next, and the command is there)
await openSiteKey("new", 0, {});
await tick();
let d = dialog();
assert.equal(heading(), "Step 1 of 2: Your site");
assert.match(d.querySelector(".dw-head, header")?.textContent || d.textContent, /Two short steps/);
assert.deepEqual(d.querySelectorAll(".ui-who-c").map((b) => b.dataset.who), ["me", "dev", "agent"]);
assert.equal(d.querySelector('.ui-who-c[aria-checked="true"]').dataset.who, "me", "Me unless you chose before");
assert.equal(readState().by, "me", "the answer shown is in the address");
await next();
assert.equal(heading(), "Step 1 of 2: Your site", "no address: Next refused");
assert.match(d.textContent, /Type the site's address/);
const addr = d.querySelector('input[name="site-address"]');
addr.value = "https://Blog.Example.org/hello";
addr.dispatchEvent(new Ev("input"));
await tick(DETECT_WAIT_MS + 60);
assert.equal(d.querySelector(".sw-found").textContent, "foundRuns on nginx · suggested: one command on the server");
assert.ok(!posted.some(([p]) => p === "sites/add"), "nothing made while typing");
await next();
assert.deepEqual(posted.find(([p]) => p === "sites/add")[1].host, "blog.example.org");
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(readState().setup, "blog.example.org");
assert.equal(readState().step, "2");
assert.equal(readState().by, "me");
await tick(30);
assert.match(d.querySelector(".sw-who").textContent, /^Who connects it: Me Change$/);
assert.ok(d.querySelector(".cn-run .cn-code")?.textContent.includes("| sudo bash"), "the command, made at once");
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.step === 3 && b.method === "server"));
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.step === 4 && b.token_id === "cd34ef56"));
assert.ok(!d.querySelector(".ag-tile"), "only the path chosen");
// My developer: the private link, and the wait.
button(d, "Change").click(); await tick();
who("dev").click(); await tick();
assert.equal(readState().by, "dev");
await next(); await tick(30);
assert.ok(button(d, "Share with your developer"));
assert.ok(!d.querySelector(".cn-run") && !d.querySelector(".ag-tile"));
// My AI agent: which agent.
button(d, "Change").click(); await tick();
who("agent").click(); await tick();
await next();
assert.equal(readState().by, "agent");
assert.equal(d.querySelectorAll("button.ag-tile").length, 5);
await close();
for (const k of ["setup", "step", "by", "agent", "link"]) assert.equal(readState()[k], "", `closing takes ${k} away`);

// ---- a link back: the address's answer wins
history.replaceState(null, "", "#settings/org/sites?setup=blog.example.org&step=2&by=dev");
sites.sites.push({ name: "blog.example.org", status: "active", source: "dashboard", setup: { step: 3, method: "server", done: false } });
await openSiteKey("blog.example.org", 2, readState());
await tick(30);
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.ok(button(dialog(), "Share with your developer"), "by=dev from the link");
await close();

// ---- older links: step 3, 4 or 5 is Connect it; agent=hand is Me; agent=<id> is My AI agent
await openSiteKey("half.example.org", 5, { agent: "hand" });
await tick();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(readState().by, "me");
await close();
await openSiteKey("half.example.org", 4, { agent: "codex" });
await tick();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(readState().by, "agent");
assert.equal(dialog().querySelector(".sw-way b").textContent, "Codex");
await close();
await openSiteKey("half.example.org", 4, {});
await tick();
assert.equal(heading(), "Step 1 of 2: Your site", "nothing saved, nothing in the link: who connects it, first");
await close();

// ---- the proof only when the server asks: three steps, then Connect it
await openSiteKey("proof.example.org", 0, {});
await tick();
assert.equal(heading(), "Step 2 of 3: Prove it's yours", "the saved step");
assert.ok(dialog().textContent.includes("skald-verify=abc"));
await next();
assert.equal(heading(), "Step 3 of 3: Connect it");
await close();
verify = { state: "pending", txt: "skald-verify=new", meta: "<meta>" };
await openSiteKey("new", 0, {});
await tick();
dialog().querySelector('input[name="site-address"]').value = "shop.example.org";
dialog().querySelector('input[name="site-address"]').dispatchEvent(new Ev("input"));
await next();
assert.equal(heading(), "Step 2 of 3: Prove it's yours");
assert.ok(posted.some(([p, b]) => p === "sites/setup" && b.name === "shop.example.org" && b.step === 2));
await close();

console.log("add-site: all passed");
process.exit(0);
