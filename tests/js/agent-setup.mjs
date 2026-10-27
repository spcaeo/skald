// "Set up with your AI agent" (2.31): the Add a site wizard's Connect it on the agent's
// way (2.42: one step, the line and the watch under it; js/tabs/agent-setup.js, agent-watch.js,
// agent-words.js, site-wizard.js), against
// answers shaped as the contract says (sites/agentlink, sites/agentstatus):
//  - the words: the code found and hidden, the time left, the report in plain words, the
//    checklist, the asset paths offered only when they differ;
//  - step 3's tiles, Next refused with nothing chosen, an agent chosen writes agent=<id>;
//  - step 4: one sites/agentlink per site, the line shown with its code hidden, Copy writes
//    the whole line and shows a green tick for TIMING.tick, Show code, Make a new line; the
//    address holds link=<link id> and never the code; the progress saves method "agent";
//  - step 5: agentstatus polled with the link id until everything ticks, the report, Use
//    these, the tag check and the test lead; polling stops when the dialog closes and when
//    the line runs out; done saves done: true;
//  - a chat-only agent gets the one command; a reload at steps 4 and 5 comes back from the
//    address; Connections' Set up with your AI agent opens step 3 whatever way was saved.
//
//   node tests/js/agent-setup.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const SITE = "www.example.org";
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
let copied = null;
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async (t) => { copied = t; } } });

const CODE = "Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4zAb7dEf0hIj3";
let made = 0;
const lineAnswer = () => {
  made += 1;
  const code = made === 1 ? CODE : CODE.replace(/^Ab/, `N${made}`);
  return { ok: true, line: `set up Skald for ${SITE} — read https://www.example.com/traffic-kit/llms.txt and use code ${code} (works once, 24 hours)`,
    llms_url: "https://www.example.com/traffic-kit/llms.txt", steps_url: `https://www.example.com/traffic-kit/${code}/steps`,
    expires_at: "2099-01-02T12:00:00Z", token_id: `ab12cd3${made}`, link_id: `0f3a9c2e7b1d4a5${made}`, cancelled: made > 1 ? 1 : 0 };
};
const REPORT = { hosting: "A VPS", server: "nginx 1.24", log_path: "/var/log/nginx/access.log", framework: "Next.js",
  asset_paths: ["/_next/static/"], script_tag: "app/layout.tsx", leads: [{ tool: "lead", file: "app/api/contact/route.ts" }],
  privacy: { keep_ips: false, days: 30, notice_url: "https://www.example.org/privacy" }, nextjs_log_field: true,
  changed_files: ["app/layout.tsx"], left_for_user: ["Restart the site's app after the deploy"], notes: "All went well." };
const STATUSES = [
  { ok: true, state: "waiting", opened_at: null, keys_at: null, reported_at: null, report: null },
  { ok: true, state: "opened", opened_at: "2099-01-01T12:01:00Z", keys_at: null, reported_at: null, report: null },
  { ok: true, state: "keys_taken", opened_at: "2099-01-01T12:01:00Z", keys_at: "2099-01-01T12:02:00Z", reported_at: null, report: null },
  { ok: true, state: "keys_taken", opened_at: "2099-01-01T12:01:00Z", keys_at: "2099-01-01T12:02:00Z", reported_at: "2099-01-01T12:05:00Z", report: REPORT },
];
let statuses = STATUSES;
let statusCode = 200;
let asked = 0;
let lines = false;
const posted = [];
const got = [];
let sites = { ok: true, can_add: true, ingest_url: "https://www.example.com/traffic-ingest", sites: [
  { name: SITE, status: "active", source: "dashboard", setup: { step: 3, method: "", done: false }, verify: null },
  { name: "old.example.org", status: "active", source: "dashboard", setup: { step: 4, method: "server", done: false }, verify: null }] };
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]); else got.push(path);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (path === "sites") return answer(sites);
  if (path === "sites/agentlink") return answer(lineAnswer());
  if (path === "sites/agentstatus") return answer(statusCode === 200 ? statuses[Math.min(asked++, statuses.length - 1)] : { ok: false, error: "Sign in first." }, statusCode);
  if (path === "sites/link") return answer({ ok: true, command: "curl -fsSL https://www.example.com/traffic-kit/" + "k".repeat(43) + " | sudo bash", url: "x", expires_at: "2099-01-02T12:00:00Z", token: "skald_cd34ef56_" + "u".repeat(43), token_id: "cd34ef56" });
  if (path === "sites/setup") return answer({ ok: true });
  if (path === "sites/agentcancel") return answer({ ok: true, state: "cancelled" });
  if (path === "sites/tagcheck") return answer({ ok: true, check: { state: "ok", words: "The tag is on the home page." } });
  if (path.startsWith("sites/status")) return answer(lines ? { ok: true, today: { lines: 12 }, last_batch: { at: "2099-01-01T12:06:00Z", lines: 12 } } : { ok: true, last_batch: null, today: null });
  if (path === `/traffic/${SITE}/settings`) return answer({ ok: true, settings: { "site.asset_prefixes": { value: ["/assets/"], editable: true } } });
  if (path === `/traffic/${SITE}/settings/save`) return answer({ ok: true });
  if (path.startsWith(`/traffic/${SITE}/integrations`)) return answer({ ok: true, tools: [{ tool: "lead", state: "ready", words: "ready: a test passed just now; nothing real yet", attention: false }] });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const W = await import(new URL("tabs/agent-words.js", JS));
const U = await import(new URL("urlactions.js", JS));
const { WATCH } = await import(new URL("tabs/agent-watch.js", JS));
const { forgetLine } = await import(new URL("tabs/agent-setup.js", JS));
const { openSiteKey } = await import(new URL("tabs/sitesadmin.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
Object.assign(WATCH, { every: 20, slowAfter: 60000, slow: 20, late: 20, lateFor: 120 });
U.TIMING.tick = 60;

const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const heading = () => dialog().querySelector("h3.cn-h").textContent;
async function next() { button(dialog(), "Next").click(); await tick(); }
const calls = (p) => posted.filter(([x]) => x === p);

// ---- the words
const first = lineAnswer();
made = 0;
assert.equal(W.codeOf(first), CODE);
assert.equal(W.codeOf({ line: first.line }), CODE, "from the line when steps_url is missing");
assert.equal(W.codeOf({ line: "no code here" }), "");
assert.ok(!W.masked(first.line, CODE).includes(CODE));
assert.ok(W.masked(first.line, CODE).includes(W.HIDDEN));
assert.equal(W.timeLeft("2099-01-01T12:40:00Z", Date.parse("2099-01-01T12:00:00Z")), "for 40 more minutes");
assert.equal(W.timeLeft("2099-01-02T11:00:00Z", Date.parse("2099-01-01T12:00:00Z")), "for 23 more hours");
assert.equal(W.timeLeft("2020-01-01T00:00:00Z"), "");
assert.ok(W.expired("2020-01-01T00:00:00Z") && !W.expired("2099-01-01T00:00:00Z"));
assert.equal(W.agentKey("codex"), "codex");
assert.equal(W.agentKey("hand"), "hand");
assert.equal(W.agentKey("<script>"), "", "only known ids from the address");
assert.ok(W.isLinkId("0f3a9c2e7b1d4a58") && !W.isLinkId(CODE));
const rep = W.reportLines(REPORT);
assert.deepEqual(rep.map((x) => x.name), ["Hosting", "Web server", "Access log", "Built with", "Page assets", "Script tag", "Leads", "Privacy", "Privacy notice", "Next.js", "Files changed", "Left for you", "Notes"]);
assert.deepEqual(rep.find((x) => x.name === "Privacy").value, ["Keep no IP addresses", "Apply it below, or set it in Settings > Privacy."]);
assert.equal(rep.find((x) => x.name === "Privacy").kind, "noted");
assert.equal(W.reportLines({ privacy: { keep_ips: true, days: 30 } })[0].value[0], "Keep IP addresses for 30 days");
assert.equal(W.reportLines({ privacy: { keep_ips: true } })[0].value[0], "Keep IP addresses with no end date");
assert.equal(rep.find((x) => x.name === "Script tag").value, "added in app/layout.tsx");
assert.deepEqual(rep.find((x) => x.name === "Leads").value, ["lead in app/api/contact/route.ts"]);
assert.equal(rep.find((x) => x.name === "Left for you").kind, "warn");
assert.deepEqual(W.reportLines({ privacy: { notice_url: "javascript:alert(1)" } }), [], "only a web address is a link");
assert.deepEqual(W.reportLines(null), []);
assert.deepEqual(W.newAssets(REPORT, ["/assets/"]), ["/_next/static/"]);
assert.deepEqual(W.newAssets(REPORT, ["/_next/static/"]), [], "the same: nothing to offer");
assert.deepEqual(W.watchItems(null).map((x) => [x.id, x.done]), [["opened", false], ["keys", false], ["report", false], ["lines", false]]);
assert.deepEqual(W.watchItems(STATUSES[3], { lines: true, tag: true }).map((x) => [x.id, x.done]),
  [["opened", true], ["keys", true], ["report", true], ["lines", true], ["tag", true], ["lead", false]]);
assert.equal(W.watchItems(STATUSES[3], { tag: null }).find((x) => x.id === "tag").words, "Skald could not look for the script tag just now");
assert.ok(W.stopWords({ state: "expired" }).startsWith("The line ran out before your agent took the keys"));
assert.equal(W.stopWords({ state: "expired", keys_at: "x", reported_at: "y" }), "");
assert.ok(W.stopWords({ state: "unknown" }));
assert.ok(W.stopWords({ state: "cancelled", keys_at: "x" }).startsWith("This line was ended"));

// ---- resumed at step 3 with nothing chosen: who connects it, first (2.42)
history.replaceState(null, "", "#settings/sitesadmin");
await openSiteKey(SITE, 3);
await tick();
let d = dialog();
assert.equal(heading(), "Step 1 of 2: Your site");
d.querySelector(".dw-x").click();
await tick(400);
// ---- the tiles: Connections' "Set up with your AI agent" (pick) opens Connect it on My AI agent
await openSiteKey(SITE, 3, { pick: true });
await tick();
d = dialog();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(readState().by, "agent");
assert.equal(d.querySelectorAll("li").find((li) => li.getAttribute("aria-current") === "step").querySelector(".cn-t").textContent, "Connect it", "the short name in the step bar");
const tiles = d.querySelectorAll("button.ag-tile");
assert.deepEqual(tiles.map((b) => b.querySelector("b").textContent), ["Claude Code", "Codex", "Cursor", "Claude.ai or ChatGPT", "Another agent"]);
assert.ok(tiles.every((b) => b.getAttribute("aria-pressed") === "false" && b.getAttribute("aria-label")), "keyboard buttons with names");
assert.ok(!d.querySelector("button.ag-hand"), "who connects it is asked once, in step 1: no Me among the agents");

// ---- step 4: the line
tiles[0].click();
await tick();
assert.equal(readState().agent, "claude-code", location.hash);
assert.equal(heading(), "Step 2 of 2: Connect it", "the line on the same step");
assert.ok(calls("sites/setup").some(([, b]) => b.step === 4 && b.method === "agent"), JSON.stringify(calls("sites/setup")));
assert.deepEqual(calls("sites/agentlink").map(([, b]) => b), [{ site: SITE, leads: true }]);
await tick();
const shown = () => d.querySelector(".ag-line pre").textContent;
assert.ok(shown().startsWith(`set up Skald for ${SITE}`), shown());
assert.ok(!shown().includes(CODE) && shown().includes(W.HIDDEN), "the code hidden by default");
assert.ok(!d.textContent.includes(CODE), "nowhere on the page");
assert.ok(d.textContent.includes("Paste it into Claude Code, in a terminal in the site's project folder"));
assert.ok(d.textContent.includes("It works once, until"));
// Is it safe to paste this into a chat? The owner's words, open on a wide screen; folded on a phone.
const safe = d.querySelector("details.ag-safe");
assert.equal(safe.querySelector("summary").textContent, "Is it safe to paste this into a chat?");
assert.ok(safe.hasAttribute("open"), "open on a wide screen");
assert.equal(safe.querySelectorAll("li").length, 7);
assert.ok(safe.textContent.includes("Yes. The line holds a one-time code, not a password or a key."));
assert.ok(safe.textContent.includes("Settings > AI assistants > Tokens & links"), "where the tokens really are");
const { SAFE } = await import(new URL("tabs/agent-words.js", JS));
assert.deepEqual(safe.querySelectorAll("li").map((li) => li.textContent), SAFE, "the seven lines, in order");
assert.equal(SAFE[2], "Your agent is told to save the keys straight into a locked file and never show them in the chat. Skald gives them only to a command-line download such as curl, and turns away web readers and fetch tools, which could pass them into a chat.");
assert.equal(SAFE[6], "If your site already has a lead secret, the agent gets that same one (unless your Skald keeps it in the server's settings; then the keys hold none). After the set-up you can remove the agent's sending key (\"AI agent set-up\") in Settings > AI assistants > Tokens & links, and make a new lead secret in Settings > Leads & tools.");
{
  const was = globalThis.matchMedia;
  globalThis.matchMedia = (q) => ({ matches: q.includes("max-width"), addEventListener() {} });
  const { safetyBox } = await import(new URL("tabs/agent-setup.js", JS));
  const folded = safetyBox();
  assert.ok(!folded.hasAttribute("open"), "folded on a phone");
  assert.equal(folded.querySelector("summary").textContent, "Is it safe to paste this into a chat?", "the title still in view");
  globalThis.matchMedia = was;
}
assert.equal(readState().link, "0f3a9c2e7b1d4a51", "the link id in the address");
assert.ok(!location.hash.includes(CODE) && !location.hash.includes("traffic-kit"), location.hash);
assert.ok(calls("sites/setup").some(([, b]) => b.token_id === "ab12cd31"), "the token's id kept, never a token");
assert.ok(!JSON.stringify(calls("sites/setup")).includes(CODE));
assert.ok(d.querySelector(".ua-host")?.textContent.includes("/traffic-kit/llms.txt"), "the public guide's address with copy and open icons");
// Copy: the whole line, a green tick, then back.
const copy = d.querySelector("button.ag-copy");
copy.click();
await tick();
assert.equal(copied, `set up Skald for ${SITE} — read https://www.example.com/traffic-kit/llms.txt and use code ${CODE} (works once, 24 hours)`);
assert.ok(copy.classList.contains("ok") && copy.textContent.includes("Copied"));
await tick(U.TIMING.tick + 30);
assert.ok(!copy.classList.contains("ok") && copy.textContent === "Copy", "the tick goes after TIMING.tick");
// Show code, and hide it again.
button(d, "Show code").click();
assert.ok(shown().includes(CODE));
assert.equal(button(d, "Hide code").getAttribute("aria-pressed"), "true");
button(d, "Hide code").click();
assert.ok(!shown().includes(CODE));
assert.ok(d.querySelector(".ag-watch"), "the watch under the line, from the start");
assert.equal(d.querySelectorAll("button").filter((b) => b.textContent === "Cancel this line").length, 1, "one Cancel: the line's");
// Another agent, then the same one again: the same line, asked once.
button(d, "Another agent").click(); await tick();
assert.equal(d.querySelectorAll("button.ag-tile").length, 5);
d.querySelector('button.ag-tile[data-agent="claude-code"]').click(); await tick(); await tick();
assert.equal(calls("sites/agentlink").length, 1, "drawn again: no second line");
assert.equal(readState().link, "0f3a9c2e7b1d4a51", "the line made here is the one watched");
// Make a new line: a new code, a new link id in the address.
button(d, "Make a new line").click();
await tick(); await tick();
assert.equal(calls("sites/agentlink").length, 2);
assert.equal(readState().link, "0f3a9c2e7b1d4a52");
assert.ok(!shown().includes("N2") && shown().includes(W.HIDDEN));
assert.ok(d.textContent.includes("The old line was cancelled."));
d.querySelector("button.ag-copy").click();
await tick();
assert.ok(copied.includes("use code N2") && !copied.includes(CODE), "the new line is the one copied");
// Cancel this line: sites/agentcancel with the link id, then the words and Make a new line.
button(d, "Cancel this line").click();
await tick();
assert.deepEqual(calls("sites/agentcancel").pop()[1], { site: SITE, link_id: "0f3a9c2e7b1d4a52" });
assert.ok(d.textContent.includes("Cancelled. This line no longer works."), d.querySelector(".cn-step").textContent.slice(0, 300));
assert.ok(!d.querySelector(".ag-line"), "the cancelled line is not shown");
button(d, "Make a new line").click();
await tick(); await tick();
assert.equal(readState().link, "0f3a9c2e7b1d4a53", "a new line after the cancel");
assert.ok(d.querySelector(".ag-line"));

// ---- the watch, under the line: Skald ticks each step by itself
asked = 0;
await tick(150);
const asks = calls("sites/agentstatus").filter(([, b]) => b.link_id === "0f3a9c2e7b1d4a53");
assert.ok(asks.length >= 4, `polled ${asks.length} times`);
assert.deepEqual(asks[0][1], { site: SITE, link_id: "0f3a9c2e7b1d4a53" });
const items = () => d.querySelectorAll(".ag-watch li").map((li) => [li.className, li.textContent]);
assert.ok(items().slice(0, 3).every(([c]) => c === "ok"), JSON.stringify(items()));
// The keys taken: when, used up, and what to do if it was not your agent.
assert.match(d.textContent, /Your agent took the keys at \d\d:\d\d\. The code is used up: it cannot give the keys again\./);
assert.ok(d.textContent.includes("Didn't your agent do this? Cancel the line, remove the key in Settings > AI assistants > Tokens & links, and make a new line."));
assert.ok(d.textContent.includes("What your agent did") && d.textContent.includes("/var/log/nginx/access.log") && d.textContent.includes("Restart the site's app"));
assert.ok(d.querySelector(".ag-report .ua-host")?.textContent.includes("https://www.example.org/privacy"), "the privacy notice with its icons");
assert.ok(items().some(([c, t]) => c === "ok" && t.includes("The script tag is on the home page")), "the tag seen");
assert.ok(items().some(([c, t]) => c === "ok" && t.includes("A test lead arrived")), "the test lead seen");
assert.ok(items().some(([c, t]) => c === "wait" && t.includes("Waiting for the first log lines")));
assert.ok(got.includes(`/traffic/${SITE}/settings`), "the new site's own settings, not the page's");
// 2.39: the page assets are a recommendation with Apply (agent-recs.js); nothing saved before the press.
assert.equal(calls(`/traffic/${SITE}/settings/save`).length, 0, "nothing applied by itself");
d.querySelector('.ag-rec[data-rec="assets"] .acts button').click();
await tick();
assert.deepEqual(calls(`/traffic/${SITE}/settings/save`).pop()[1], { "site.asset_prefixes": ["/_next/static/"] });
// The first log lines: done, saved; then the watch stops by itself.
lines = true;
button(d, "Test connection").click();
await tick(60);
assert.ok(d.textContent.includes(`Done: ${SITE} is receiving visits.`));
assert.ok(calls("sites/setup").some(([, b]) => b.done === true && b.step === 5));
assert.ok(items().every(([c]) => c === "ok"), JSON.stringify(items()));
await tick(60);
const stopped = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, stopped, "all ticked: no more asking");
d.querySelector(".dw-x").click();
await tick();
assert.equal(readState().setup, "", "closed");
assert.equal(readState().agent, "", "closing takes the agent key away");
assert.equal(readState().link, "", "and the link id");

// ---- a reload at step 5 (link from the address); closing the dialog stops the polling
forgetLine(SITE);
asked = 0;
statuses = [STATUSES[0]];
lines = false;
await openSiteKey(SITE, 5, { agent: "codex", link: "0f3a9c2e7b1d4a58" });   // one this page never cancelled
await tick(80);
d = dialog();
assert.equal(heading(), "Step 2 of 2: Connect it", "back at the step from the address");
assert.ok(d.textContent.includes("The line was made before this page was reloaded, so it is not shown again."));
assert.equal(calls("sites/agentstatus").pop()[1].link_id, "0f3a9c2e7b1d4a58");
d.querySelector(".dw-x").click();
await tick(400);      // the drawer slides out (320 ms), then leaves the page
const closedAt = calls("sites/agentstatus").length;
await tick(120);
assert.equal(calls("sites/agentstatus").length, closedAt, "the dialog closed: polling stopped");
// ... and at an older step 4: the line is not shown again, the watch goes on.
await openSiteKey(SITE, 4, { agent: "codex", link: "0f3a9c2e7b1d4a55" });   // one this page never cancelled
await tick(40);
d = dialog();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.ok(d.textContent.includes("The line was made before this page was reloaded, so it is not shown again."));
assert.equal(calls("sites/agentlink").length, 3, "no new line made by itself (two made, one after the cancel)");
assert.equal(d.querySelector(".sw-way b").textContent, "Codex");
button(d, "Cancel this line").click();
await tick();
assert.deepEqual(calls("sites/agentcancel").pop()[1], { site: SITE, link_id: "0f3a9c2e7b1d4a55" }, "a line from before the reload can be cancelled");
assert.ok(d.textContent.includes("Cancelled. This line no longer works."));
assert.ok(button(d, "Make a new line"));
d.querySelector(".dw-x").click();
await tick();

// ---- after the keys: Cancel this line there; the cancelled state stops the polling
statuses = [STATUSES[2], { ...STATUSES[2], state: "cancelled", cancelled_at: "2099-01-01T12:03:00Z" }];
asked = 0;
await openSiteKey(SITE, 5, { agent: "codex", link: "0f3a9c2e7b1d4a54" });
await tick(80);
d = dialog();
assert.ok(d.textContent.includes("Your agent took the keys at"));
button(d, "Cancel this line").click();
await tick(80);
assert.deepEqual(calls("sites/agentcancel").pop()[1], { site: SITE, link_id: "0f3a9c2e7b1d4a54" });
assert.ok(d.textContent.includes("This line was ended"), "the next answer says cancelled");
const cancelledAt = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, cancelledAt, "cancelled: polling stopped");
assert.equal(d.querySelectorAll("button").filter((b) => b.textContent === "Cancel this line").length, 0, "no second cancel");
d.querySelector(".dw-x").click();
await tick();

// ---- before the keys (waiting, opened): Cancel this line is there too
statuses = [STATUSES[1]];
asked = 0;
await openSiteKey(SITE, 5, { agent: "codex", link: "0f3a9c2e7b1d4a56" });
await tick(80);
d = dialog();
assert.ok(d.textContent.includes("Sent it to the wrong place, or changed your mind?"));
assert.equal(d.querySelectorAll("button").filter((b) => b.textContent === "Cancel this line").length, 1);
statuses = [{ ...STATUSES[1], state: "cancelled", cancelled_at: "2099-01-01T12:03:00Z" }];
asked = 0;
button(d, "Cancel this line").click();
await tick(80);
assert.deepEqual(calls("sites/agentcancel").pop()[1], { site: SITE, link_id: "0f3a9c2e7b1d4a56" });
assert.ok(d.textContent.includes("Cancelled. This line no longer works.") && d.textContent.includes("Go Back to make a new line."));
assert.ok(!button(d, "Cancel this line"), "the button goes once it is cancelled");
const waitCancelledAt = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, waitCancelledAt, "cancelled: polling stopped");
d.querySelector(".dw-x").click();
await tick();

// ---- the line runs out: the watch says so and stops
statuses = [{ ok: true, state: "expired", opened_at: null, keys_at: null, reported_at: null, report: null }];
asked = 0;
await openSiteKey(SITE, 5, { agent: "cursor", link: "0f3a9c2e7b1d4a59" });
await tick(80);
d = dialog();
assert.ok(d.textContent.includes("The line ran out before your agent took the keys."));
const ranOut = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, ranOut, "expired: polling stopped");
d.querySelector(".dw-x").click();
await tick();

// ---- a newer report replaces the first; every URL in it has its icons; at most 10 page assets
const MANY = Array.from({ length: 12 }, (_, i) => `/a${i}/`);
statuses = [STATUSES[3], { ...STATUSES[3], reported_at: "2099-01-01T12:09:00Z",
  report: { ...REPORT, asset_paths: MANY, left_for_user: ["Read https://www.example.org/help/setup, then restart."], notes: "Second try." } }];
asked = 0;
lines = false;
await openSiteKey(SITE, 5, { agent: "codex", link: "0f3a9c2e7b1d4a57" });
await tick(150);
d = dialog();
assert.ok(d.textContent.includes("Second try.") && !d.textContent.includes("All went well."), "the newer report is shown");
assert.ok(d.textContent.includes("Sent by your agent. Check it before you use it."));
const hosts = d.querySelectorAll(".ag-report .ua-host").map((x) => x.textContent);
assert.ok(hosts.some((t) => t.includes("https://www.example.org/help/setup")), "a URL inside the words has its icons");
assert.ok(hosts.some((t) => t.includes("https://www.example.org/privacy")), "the privacy notice too");
assert.ok(d.textContent.includes("Skald keeps at most 10: these are the first 10."));
d.querySelector('.ag-rec[data-rec="assets"] .acts button').click();
await tick();
assert.deepEqual(calls(`/traffic/${SITE}/settings/save`).pop()[1], { "site.asset_prefixes": MANY.slice(0, 10) });
d.querySelector(".dw-x").click();
await tick(400);

// ---- signed out (401): said once, and the watch stops
statusCode = 401;
await openSiteKey(SITE, 5, { agent: "codex", link: "0f3a9c2e7b1d4a57" });
await tick(80);
d = dialog();
assert.ok(d.textContent.includes("Sign in again, then reload this page."));
const signedOut = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, signedOut, "401: polling stopped");
statusCode = 200;
d.querySelector(".dw-x").click();
await tick(400);

// ---- past the expiry with the keys taken: slower, then Check again; with the log lines in, it stops
statuses = [{ ...STATUSES[2], expires_at: "2020-01-01T00:00:00Z" }];
asked = 0;
lines = false;
await openSiteKey(SITE, 5, { agent: "codex", link: "0f3a9c2e7b1d4a57" });
await tick(250);
d = dialog();
assert.ok(d.textContent.includes("Still waiting? Press Check again."), "after lateFor: Check again");
const late = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, late, "it waits for Check again");
lines = true;
button(d, "Check again").click();
await tick(150);
assert.ok(d.textContent.includes(`Done: ${SITE} is receiving visits.`));
const linesIn = calls("sites/agentstatus").length;
assert.ok(linesIn > late, "Check again asked");
await tick(100);
assert.equal(calls("sites/agentstatus").length, linesIn, "past the expiry with the log lines in: stopped");
d.querySelector(".dw-x").click();
await tick(400);
lines = false;

// ---- from an address with no link: no line by itself, "Make the line" on request
forgetLine(SITE);
const madeBefore = calls("sites/agentlink").length;
await openSiteKey(SITE, 4, { agent: "codex" });
await tick();
d = dialog();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(calls("sites/agentlink").length, madeBefore, "no sites/agentlink from an address");
assert.ok(!d.querySelector(".ag-line"));
button(d, "Make the line").click();
await tick(); await tick();
assert.equal(calls("sites/agentlink").length, madeBefore + 1);
assert.ok(d.querySelector(".ag-line"), "the line after Make the line");
d.querySelector(".dw-x").click();
await tick(400);

// ---- a chat-only agent: the one command, with one line why; the progress says "server"
await openSiteKey(SITE, 3, { pick: true });
await tick();
d = dialog();
d.querySelector('button.ag-tile[data-agent="chat"]').click();
await tick(); await tick();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.ok(d.textContent.includes("A chat in the browser cannot run commands on your server."));
assert.ok(d.querySelector(".cn-run .cn-code").textContent.includes("| sudo bash"));
assert.ok(calls("sites/setup").some(([, b]) => b.step === 4 && b.method === "server"));
assert.equal(readState().agent, "chat");
assert.ok(!d.querySelector(".ag-watch"), "no agent checklist for a chat");
assert.ok(d.textContent.includes("sudo skald-ship-check"), "the server way's test words");
d.querySelector(".dw-x").click();
await tick();

// ---- by hand from an older address (agent=hand is Me), and back to the agents
await openSiteKey(SITE, 4, { agent: "hand" });
await tick();
d = dialog();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(readState().by, "me", "agent=hand is read as by=me");
assert.ok(d.textContent.includes("Where does the site run?"), "nothing chosen by hand yet: the ways first");
button(d, "Change").click();
await tick();
assert.equal(heading(), "Step 1 of 2: Your site");
d.querySelector('.ui-who-c[data-who="agent"]').click();
await next(); await tick();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.equal(readState().by, "agent");
assert.equal(d.querySelectorAll("button.ag-tile").length, 5, "the agents");
d.querySelector(".dw-x").click();
await tick();
// A site saved by hand reopens by hand. v2: Data › Send logs has one button, and it asks who will do it.
await openSiteKey("old.example.org", 4);
await tick();
assert.equal(heading(), "Step 2 of 2: Connect it");
assert.match(dialog().querySelector(".sw-way").textContent, /^My own server/, "its saved way");
dialog().querySelector(".dw-x").click();
await tick();
const { dataLogs } = await import(new URL("tabs/set-site.js", JS));
const root = document.createElement("div");
document.body.append(root);
root.append(...[dataLogs({ site: "old.example.org", x: { sites: { sites: [{ name: "old.example.org" }] } } })].flat(9).filter(Boolean));
await tick(30);
assert.equal(root.querySelectorAll("button.set-go").length, 1, "one button");
root.querySelector("button.set-go").click();
await tick(30);
assert.equal(readState().setup, "finish-logs", "Who will do it? for this line");
assert.ok(dialog().textContent.includes("Who will do it?"));
dialog().querySelector('.ui-who-c[data-who="agent"]').click();
await tick(50);
dialog().querySelector('button.ag-tile[data-agent="codex"]').click();
await tick(50);
assert.equal(readState().setup, "finish-logs", "the agent's line is made in this dialog");
assert.equal(readState().by, "agent");
assert.equal(readState().agent, "codex");
console.log("agent-setup: all passed");
process.exit(0);
