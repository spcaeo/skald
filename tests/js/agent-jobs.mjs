// Your AI agent, in every set-up job (2.39: js/tabs/agent-first.js, agent-recs.js, the
// checklist's "Set up everything left with your AI agent"), against answers shaped as
// docs/plans/2026-10-26-agent-everywhere.md says (a fake server: sites/agentlink with jobs,
// sites/agentstatus with the report's jobs and tools):
//  - each set-up dialog with an agent job (logs, script, lead, rsc, assets, privacy, and the
//    MCP dialog) opens on "Your AI agent, or by hand?": the tiles without the chat-only one,
//    and By hand; countries and mail stay by hand;
//  - a tile makes the line with POST sites/agentlink {site, jobs: [<job>]} (mcp for the MCP
//    dialog), the address holds agent and link, never the line;
//  - the checklist's button shows with two or more agent jobs left and makes one line for all
//    of them, in the contract's order (setup=all&jobs=...);
//  - the watch: no log lines for a line without logs, done on the report; the report's jobs
//    and tools as a short list; page assets and privacy as recommendations whose Apply makes
//    the by-hand dialogs' saves, and nothing saved without the press;
//  - the address round trip: a reload at the watch, at the line, by hand, and setup=all;
//  - the MCP dialog's "Read the MCP guide" button at the top.
//
//   node tests/js/agent-jobs.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const SITE = "www.example.org";
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

let made = 0;
const lineAnswer = (body) => {
  made += 1;
  const code = `Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4zAb7dEf0hIj${made}`;
  return { ok: true, line: `finish setting up Skald for ${SITE} (${body.jobs.join(", ")}) — read https://www.example.com/traffic-kit/llms.txt and use code ${code} (works once, 24 hours)`,
    llms_url: "https://www.example.com/traffic-kit/llms.txt", steps_url: `https://www.example.com/traffic-kit/${code}/steps`,
    expires_at: "2099-01-02T12:00:00Z", token_id: body.jobs.includes("logs") ? `ab12cd3${made}` : null,
    ...(body.jobs.includes("mcp") ? { mcp_token_id: `cd34ef5${made}` } : {}), link_id: `1f3a9c2e7b1d4a5${made}`, cancelled: 0, jobs: body.jobs };
};
// As the server builds it: bad ids, an empty list or not a list are a 400.
const JOB_IDS = ["logs", "script", "lead", "rsc", "assets", "privacy", "search", "mcp"];
const badJobs = (jobs) => jobs !== undefined && (!Array.isArray(jobs) || !jobs.length || jobs.some((j) => !JOB_IDS.includes(j)));
const REPORT = { framework: "Next.js", asset_paths: ["/_next/static/"], privacy: { keep_ips: false },
  jobs: { script: "already", lead: "done", assets: "done", privacy: "left" }, tools: [{ tool: "calendly", hook: "set" }, { tool: "stripe", hook: "left" }] };
const STATUS = { ok: true, state: "reported", opened_at: "2099-01-01T12:01:00Z", keys_at: "2099-01-01T12:02:00Z", reported_at: "2099-01-01T12:05:00Z",
  expires_at: "2099-01-02T12:00:00Z", report: REPORT, jobs: REPORT.jobs, tools: REPORT.tools, line_jobs: ["assets"] };
let status = STATUS;
const SETTINGS = { "mail.to": { value: [], source: "default", editable: true }, "mail.daily": { value: false, source: "default", editable: true },
  "privacy.keep_ips": { value: "full", source: "default", editable: true }, "privacy.keep_days": { value: 395, source: "default", editable: true },
  "conversions.identity": { value: "full", source: "default", editable: true },
  "search.google_property": { value: "sc-domain:www.example.org", source: "site", editable: true },
  "site.asset_prefixes": { value: ["/assets/"], source: "site", editable: true }, "site.require_rendering": { value: false, source: "site", editable: true } };
// The checklist's answers: logs, assets, rsc, script, lead and privacy open; countries and mail by hand.
let doctor = [{ id: "logs", state: "NEEDS ATTENTION", says: "no line yet" }, { id: "assets", state: "NEEDS ATTENTION", says: "no asset seen" },
  { id: "rsc", state: "NEEDS ATTENTION", says: "payloads without the field" }, { id: "script", state: "OFF", says: "off" }];
let settings = SETTINGS;
const INTEG = () => ({ ok: true, status: doctor, tools: [{ tool: "lead", name: "Your site's server", state: "needs_secret", set: false, rotatable: true, words: "no secret yet", url: "https://www.example.com/traffic-hooks/x/lead" }],
  script: { tag: `<script src="https://www.example.com/traffic-js/skald.js" data-site="${SITE}" defer></script>`, src: "https://www.example.com/traffic-js/skald.js" } });
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "sites") return answer({ ok: true, ingest_url: "https://www.example.com/traffic-ingest", sites: [{ name: SITE, status: "active" }] });
  if (path === "sites/agentlink") {
    if (badJobs(body.jobs)) return answer({ ok: false, error: "jobs is a list of known job ids." }, 400);
    return answer(lineAnswer({ ...body, jobs: body.jobs || (body.leads === false ? ["logs", "script"] : ["logs", "script", "lead"]) }));
  }
  if (path === "sites/agentstatus") return answer(status);
  if (path === "sites/tagcheck") return answer({ ok: true, check: { state: "ok", words: "The tag is on the home page." } });
  if (path.startsWith("sites/status")) return answer({ ok: true, last_batch: null, today: null });
  if (path === "settings") return answer({ ok: true, settings, mail_waiting: [], notice: { intro: "We keep:", items: ["Visits."], text: "We keep: visits." } });
  if (path === "settings/save") return answer({ ok: true, saved: Object.keys(body), settings, notice: { intro: "We keep:", items: ["No IP address."], text: "We keep: no IP address." } });
  if (path.startsWith("integrations")) return answer(INTEG());
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { WATCH } = await import(new URL("tabs/agent-watch.js", JS));
const { openSetup, openSetupKey } = await import(new URL("tabs/setup-dialogs.js", JS));
const { openConnKey } = await import(new URL("tabs/connections.js", JS));
const { setupChecklist } = await import(new URL("tabs/checklist.js", JS));
const { agentJobsLeft, AGENT_JOBS, setupItems } = await import(new URL("setup-items.js", JS));
const W = await import(new URL("tabs/agent-words.js", JS));
const R = await import(new URL("tabs/agent-recs.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
Object.assign(WATCH, { every: 20, slowAfter: 60000, slow: 20, late: 20, lateFor: 120 });

const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const heading = () => dialog().querySelector("h3.cn-h").textContent;
const calls = (p) => posted.filter(([x]) => x === p);
async function close() { dialog().querySelector(".dw-x").click(); await tick(400); }
const m = { site: SITE, today: new Date().toISOString().slice(0, 10), live: null, byDay: new Map() };
history.replaceState(null, "", "#overview/summary");

// ---- the words: jobs in the contract's order, from the address, in a list
assert.deepEqual(W.JOBS.map((j) => j.id), ["logs", "script", "lead", "rsc", "assets", "privacy", "search", "mcp"]);
assert.deepEqual(W.jobsInOrder(["privacy", "logs", "nope", "logs", "lead"]), ["logs", "lead", "privacy"]);
assert.deepEqual(W.jobsFrom("assets.logs.<script>"), ["logs", "assets"], "only known ids from the address");
assert.equal(W.jobsWords(["logs", "script", "lead"]), "the server's log, the script tag and your leads");
assert.deepEqual(AGENT_JOBS, ["logs", "script", "lead", "rsc", "assets", "privacy", "search"]);
const rep = W.reportLines(REPORT);
assert.deepEqual(rep.find((x) => x.name === "Each job").value,
  ["Add the script tag: already there", "Connect your leads: done", "Find the page assets: done", "Read the privacy notice: left for you"]);
assert.deepEqual(rep.find((x) => x.name === "Lead tools").value, ["Calendly: hook set", "Stripe: left for you"]);
assert.deepEqual(W.reportLines({ jobs: { logs: "sure" }, tools: [{ tool: "x", hook: "maybe" }] }), [], "unknown results are left out");
assert.deepEqual(W.watchItems(null, {}, ["script"]).map((x) => x.id), ["opened", "keys", "report"], "no log lines without the logs job");
assert.deepEqual(W.watchItems(null, {}, ["logs", "script"]).map((x) => x.id), ["opened", "keys", "report", "lines"]);
// The saves Apply makes: the by-hand dialogs' (assets: require_rendering back on; privacy: the IP choice).
assert.deepEqual(R.assetsSave(REPORT, SETTINGS), { "site.asset_prefixes": ["/_next/static/"], "site.require_rendering": true });
assert.equal(R.assetsSave(REPORT, { ...SETTINGS, "site.asset_prefixes": { value: ["/_next/static/"], editable: true } }), null, "the same: nothing to apply");
assert.equal(R.assetsSave(REPORT, { ...SETTINGS, "site.asset_prefixes": { value: [], editable: false } }), null, "not editable here");
assert.deepEqual(R.privacySave({ keep_ips: false }, SETTINGS), { "privacy.keep_ips": "off" });
assert.deepEqual(R.privacySave({ keep_ips: true, days: 30 }, SETTINGS), { "privacy.keep_ips": "full", "privacy.keep_days": 30 }, "the default: recorded as chosen");
assert.deepEqual(R.privacySave({ keep_ips: true }, { ...SETTINGS, "privacy.keep_ips": { value: "short", source: "site", editable: true } }), null, "kept shortened already: kept");
assert.equal(R.privacySave({ keep_ips: "yes" }, SETTINGS), null);
assert.equal(R.privacySave({ keep_ips: false }, { ...SETTINGS, "privacy.keep_ips": { value: "full", editable: false } }), null, "locked: nothing offered");

// ---- each dialog's first choice, and the line for its job
for (const act of AGENT_JOBS) {
  const before = calls("sites/agentlink").length;
  await openSetup(act, SITE, {});
  await tick(30);
  const d = dialog();
  assert.equal(heading(), "Step 1 of 3: Your AI agent, or by hand?", act);
  assert.equal(readState().setup, act);
  const tiles = d.querySelectorAll("button.ag-tile").map((b) => b.getAttribute("data-agent"));
  assert.deepEqual(tiles, ["claude-code", "codex", "cursor", "other"], `${act}: no chat-only tile`);
  assert.ok(button(d, "By hand"), `${act}: By hand`);
  button(d, "Next").click();
  await tick();
  assert.ok(d.textContent.includes("Choose your AI agent, or By hand."), "Next refused with nothing chosen");
  d.querySelector('button.ag-tile[data-agent="codex"]').click();
  await tick(30);
  assert.equal(heading(), "Step 2 of 3: Send this line", act);
  assert.equal(calls("sites/agentlink").length, before + 1, `${act}: one line`);
  assert.deepEqual(calls("sites/agentlink").pop()[1], { site: SITE, jobs: [act] }, `${act}: the job in the body`);
  assert.equal(readState().agent, "codex");
  assert.match(readState().link, /^1f3a9c2e7b1d4a5\d$/);
  assert.ok(!location.hash.includes("traffic-kit") && !location.hash.includes("Ab3dEf"), "never the line or its code");
  assert.ok(d.querySelector(".ag-line pre").textContent.includes(`(${act})`));
  await close();
}
// countries and mail stay by hand.
for (const act of ["countries", "mail"]) {
  await openSetup(act, SITE, {});
  await tick(30);
  assert.ok(!dialog().querySelector("button.ag-tile"), `${act}: no agent`);
  assert.doesNotMatch(heading(), /Your AI agent/);
  await close();
}

// ---- the MCP dialog: the guide at the top, the same choice, job mcp
await openConnKey("mcp", m, 1);
await tick(30);
let d = dialog();
const guide = d.querySelector(".cn-guide a.btn");
assert.equal(guide.textContent, "Read the MCP guide");
assert.ok(guide.getAttribute("href").endsWith("#help?part=mcp"), guide.getAttribute("href"));
assert.equal(guide.getAttribute("target"), "_blank");
assert.ok(d.querySelectorAll(".cn-guide, .cn-bar").map((x) => x.className)[0] === "cn-guide", "above the step bar");
assert.equal(heading(), "Step 1 of 3: Your AI agent, or by hand?");
assert.equal(readState().conn, "mcp");
d.querySelector('button.ag-tile[data-agent="claude-code"]').click();
await tick(30);
assert.deepEqual(calls("sites/agentlink").pop()[1], { site: SITE, jobs: ["mcp"] });
assert.equal(readState().agent, "claude-code");
assert.ok(d.querySelector(".cn-guide a.btn"), "the guide stays on every step");
await close();
// By hand (2.40): one step holds the choice, the token and the command; then Test.
await openConnKey("mcp", m, 2, false, { agent: "hand" });
await tick(30);
assert.match(heading(), /^Step 2 of 3: Connect your assistant/);
assert.ok(dialog().textContent.includes("claude mcp add --transport http skald"));
await close();

// ---- the watch for one job: no log lines, done on the report, the jobs and tools, Apply
status = STATUS;
await openSetupKey("assets", m, 3, false, { agent: "codex", link: "1f3a9c2e7b1d4a59" });
await tick(150);
d = dialog();
assert.equal(heading(), "Step 3 of 3: Watch your agent work", "back at the watch from the address");
assert.deepEqual(calls("sites/agentstatus").pop()[1], { site: SITE, link_id: "1f3a9c2e7b1d4a59" });
const items = d.querySelectorAll(".ag-watch li").map((li) => li.textContent);
assert.ok(!items.some((t) => t.includes("log lines")), JSON.stringify(items));
assert.ok(!button(d, "Test connection"), "no log test for a line without logs");
assert.ok(d.textContent.includes("Done: your agent sent its report."));
assert.ok(d.textContent.includes("Add the script tag: already there") && d.textContent.includes("Calendly: hook set") && d.textContent.includes("Stripe: left for you"));
assert.ok(d.textContent.includes("What your agent recommends") && d.textContent.includes("Skald changes nothing until you press Apply."));
await tick(100);
assert.equal(calls("settings/save").length, 0, "nothing applied without the press");
const recs = d.querySelectorAll(".ag-rec").map((x) => x.getAttribute("data-rec"));
assert.deepEqual(recs, ["assets", "privacy"]);
assert.ok(d.querySelector('.ag-rec[data-rec="assets"] .ua-host'), "the folder has its copy icon");
assert.ok(d.querySelector('.ag-rec[data-rec="privacy"]').textContent.includes("Keep no IP addresses"));
d.querySelector('.ag-rec[data-rec="privacy"] .acts button').click();
await tick();
assert.deepEqual(calls("settings/save").map(([, b]) => b), [{ "privacy.keep_ips": "off" }], "the privacy dialog's save, alone");
assert.ok(d.querySelector('.ag-rec[data-rec="privacy"]').textContent.includes("Saved. Copy this wording into your privacy notice."));
assert.ok(d.querySelector('.ag-rec[data-rec="privacy"] section.notice-card'), "the wording for the notice");
d.querySelector('.ag-rec[data-rec="assets"] .acts button').click();
await tick();
assert.deepEqual(calls("settings/save").pop()[1], { "site.asset_prefixes": ["/_next/static/"], "site.require_rendering": true }, "the assets dialog's save");
assert.equal(calls("settings/save").length, 2);
const polled = calls("sites/agentstatus").length;
await tick(100);
assert.equal(calls("sites/agentstatus").length, polled, "the report came: the watch stops");
await close();

// ---- the server's answer as built: jobs and tools at the top level only still show
status = { ...STATUS, reported_at: "2099-01-01T12:07:00Z", report: { framework: "Next.js" }, jobs: { rsc: "left" }, tools: [{ tool: "hubspot", hook: "set" }], line_jobs: ["rsc"] };
await openSetupKey("rsc", m, 3, false, { agent: "codex", link: "1f3a9c2e7b1d4a57" });
await tick(80);
d = dialog();
assert.ok(d.textContent.includes("Count pages opened inside the site: left for you") && d.textContent.includes("HubSpot: hook set"), "top-level jobs and tools");
await close();
status = STATUS;
// A bad job id: the server's words, and Try again.
const { makeLine } = await import(new URL("tabs/agent-setup.js", JS));
const refused = await makeLine(SITE, ["nope"]);
assert.equal(refused.status, 400);
assert.ok(calls("sites/agentlink").pop()[1].jobs[0] === "nope");

// ---- a reload at the line: no line by itself; Back returns to the choice, the tile shown
const madeBefore = calls("sites/agentlink").length;
await openSetupKey("privacy", m, 2, false, { agent: "cursor" });
await tick(30);
d = dialog();
assert.equal(heading(), "Step 2 of 3: Send this line");
assert.equal(calls("sites/agentlink").length, madeBefore, "an address never makes a line by itself");
assert.ok(button(d, "Make the line"));
button(d, "Back").click();
await tick();
assert.equal(heading(), "Step 1 of 3: Your AI agent, or by hand?");
assert.equal(d.querySelector('button.ag-tile[data-agent="cursor"]').getAttribute("aria-pressed"), "true");
// By hand, then Back: the address follows.
button(d, "By hand").click();
await tick(30);
assert.equal(readState().agent, "hand");
assert.equal(readState().step, "2");
assert.equal(heading(), "Step 2 of 4: IP addresses");
await close();
assert.equal(readState().setup, "", "closed");
assert.equal(readState().agent, "", "closing takes the agent away");
// A chat agent from an old address is not offered here: the choice again.
await openSetupKey("script", m, 2, false, { agent: "chat" });
await tick(30);
assert.equal(heading(), "Step 1 of 3: Your AI agent, or by hand?");
await close();

// ---- the checklist: one line for every open agent job, in the contract's order
const got = { settings, status: doctor, tools: INTEG().tools, waiting: [] };
assert.deepEqual(agentJobsLeft(setupItems(m, got)), ["logs", "script", "lead", "rsc", "assets", "privacy"]);
const box = setupChecklist(m, { where: "connections" });
document.body.append(box);
await tick(50);
const go = button(box, "Set up everything left with your AI agent");
assert.ok(go && !box.querySelector(".su-agent").hidden, "six left: the button");
assert.ok(box.querySelector(".su-agent").textContent.includes("Logs arriving"));
go.click();
await tick(50);
d = dialog();
assert.equal(readState().setup, "all");
assert.equal(readState().jobs, "logs.script.lead.rsc.assets.privacy", location.hash);
assert.equal(heading(), "Step 1 of 3: Which AI agent are you using?");
assert.ok(!button(d, "By hand"), "no By hand for everything at once");
assert.ok(d.textContent.includes("the server's log, the script tag, your leads, pages opened inside the site, the page assets and the privacy choice"));
d.querySelector('button.ag-tile[data-agent="claude-code"]').click();
await tick(30);
assert.deepEqual(calls("sites/agentlink").pop()[1], { site: SITE, jobs: ["logs", "script", "lead", "rsc", "assets", "privacy"] });
await close();
// A reload at its watch: the jobs from the address; the log lines are on the list.
status = { ...STATUS, report: null, reported_at: null };
await openSetupKey("all", m, 3, false, { agent: "claude-code", link: "1f3a9c2e7b1d4a58", jobs: "logs.script" });
await tick(80);
d = dialog();
assert.equal(heading(), "Step 3 of 3: Watch your agent work");
assert.equal(readState().jobs, "logs.script");
assert.ok(d.querySelectorAll(".ag-watch li").some((li) => li.textContent.includes("Waiting for the first log lines")), "logs: the log lines");
assert.ok(button(d, "Test connection"), "logs: the log test");
await close();
// One agent job left: no button. None: the link says so.
doctor = [{ id: "logs", state: "OK", says: "readable" }, { id: "assets", state: "OK", says: "ok" }, { id: "script", state: "OK", says: "the last event came 2 minutes ago" }];
settings = { ...SETTINGS, "privacy.keep_ips": { value: "full", source: "site", editable: true } };
await box.refresh();
await tick(30);
assert.deepEqual(agentJobsLeft(setupItems(m, { settings, status: doctor, tools: INTEG().tools })), ["lead"]);
assert.ok(box.querySelector(".su-agent").hidden, "one left: no button");
const { refreshChecklists } = await import(new URL("tabs/checklist.js", JS));
refreshChecklists();
console.log("agent-jobs: all passed");
process.exit(0);
