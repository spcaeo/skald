// The shared UI pieces (2.41, docs/UI-RULES.md; js/ui/*.js): the status pills, the "?"
// popover (opens, closes on Escape and on its x, focus back, one open at a time, the
// guide's words and link), the folds, the one primary button, and "Who will do it?":
// the choice kept in the address and remembered per person, and each path calling the
// flow Skald already has (the agent line, the developer's link, the steps by hand).
//
//   node tests/js/ui.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  posted.push([path, body]);
  if (path === "sites/agentlink") return { ok: true, status: 200, json: async () => ({ ok: true, line: "Set up Skald: curl https://app.example.com/k/abc123 | read the steps", link_id: "0f3a9c2e7b1d4a58", expires_at: "2099-01-01T00:00:00Z", token_id: "t1" }) };
  if (path === "sites/share") return { ok: true, status: 200, json: async () => ({ ok: true, link: "https://app.example.com/traffic-share/abc", expires_at: "2099-01-01T00:00:00Z" }) };
  return { ok: true, status: 200, json: async () => ({ ok: true, state: "waiting", steps: [] }) };
};
const tick = (ms = 5) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const { ME } = await import(new URL("access.js", JS));
const { setSiteBase } = await import(new URL("urlactions.js", JS));
const P = await import(new URL("ui/pill.js", JS));
const HELP = await import(new URL("ui/help.js", JS));
const F = await import(new URL("ui/fold.js", JS));
const PR = await import(new URL("ui/primary.js", JS));
const W = await import(new URL("ui/who.js", JS));
setSiteBase("example.com");
const go = (hash) => { history.replaceState(null, "", hash); };
const key = (type, k) => { const e = new Event(type); e.key = k; return e; };

// ---- pills: five kinds, the state words Skald uses, and anything else is "off"
assert.deepEqual(P.KINDS, ["good", "warn", "bad", "off", "info"]);
for (const [state, kind] of [["done", "good"], ["Working", "good"], ["waiting", "warn"], ["medium", "warn"], ["high", "bad"], ["broken", "bad"],
  ["paused", "off"], ["Not set up", "off"], ["low", "info"], ["new", "info"], ["something else", "off"], [null, "off"]]) {
  assert.equal(P.kindOf(state), kind, `${state} is ${kind}`);
}
const p1 = P.pill("bad", "Urgent");
assert.equal(p1.className, "ui-pill bad");
assert.equal(p1.textContent, "Urgent");
assert.equal(P.pill("waiting", "Waiting for logs").className, "ui-pill warn", "a state word picks its kind");

// ---- the "?": closed at first, a press opens it, Escape and the x close it, focus goes back
const h1 = HELP.help("Alerts", { text: ["What the alerts watch for.", "They close by themselves."], guide: "what-to-fix" });
document.body.append(h1);
const btn = h1.querySelector(".ui-help");
const pop = h1.querySelector(".ui-help-pop");
assert.equal(btn.getAttribute("aria-label"), "Help: Alerts");
assert.equal(btn.getAttribute("aria-controls"), pop.getAttribute("id"));
assert.equal(pop.getAttribute("role"), "dialog");
assert.ok(pop.hidden, "closed at first");
assert.equal(btn.getAttribute("aria-expanded"), "false");
btn.click();
assert.ok(!pop.hidden, "a press opens it (a phone has no hover)");
assert.equal(btn.getAttribute("aria-expanded"), "true");
assert.equal(document.activeElement, pop.querySelector("a"), "the focus moves into it");
assert.equal(pop.querySelector("a").getAttribute("href"), "#help?part=what-to-fix", "Read the guide opens the guide");
assert.deepEqual(pop.querySelectorAll("p").map((x) => x.textContent), ["What the alerts watch for.", "They close by themselves."]);
h1.dispatchEvent(key("keydown", "Escape"));
assert.ok(pop.hidden, "Escape closes it");
assert.equal(document.activeElement, btn, "and the focus goes back to the ?");
btn.click();
pop.querySelector(".ui-help-x").click();
assert.ok(pop.hidden, "the x closes it");
assert.equal(document.activeElement, btn);
btn.click();
btn.click();
assert.ok(pop.hidden, "a second press closes it");
// One open at a time.
const h2 = HELP.help("Visitors", { guide: "where-visitors-come-from" });
document.body.append(h2);
btn.click();
h2.querySelector(".ui-help").click();
assert.ok(pop.hidden && !h2.querySelector(".ui-help-pop").hidden, "opening one closes the other");
assert.ok(h2.querySelector("p").textContent.startsWith("Most visits say Direct"), "no text: the guide's own summary");
const h3 = HELP.help("Odd", { text: "Short words.", guide: "no-such-guide" });
assert.equal(h3.querySelector("a"), null, "a guide that does not exist gets no link");
assert.equal(HELP.guideOf("security").title.startsWith("Security"), true);

// ---- folds: nothing for nothing; the body drawn the first time it opens
assert.equal(F.doneFold([], () => null), null);
let drawn = 0;
const df = F.doneFold(["a", "b", "c"], (x) => { drawn += 1; const li = document.createElement("p"); li.textContent = x; return li; });
assert.ok(df.querySelector("summary").textContent.includes("3 done"));
assert.equal(df.querySelector("summary").textContent.includes("✓"), false, "the tick is an icon, never a glyph");
assert.equal(drawn, 0, "not drawn while folded");
df.setAttribute("open", "");
df.dispatchEvent(new Event("toggle"));
assert.equal(drawn, 3);
df.dispatchEvent(new Event("toggle"));
assert.equal(drawn, 3, "drawn once");
const f2 = F.fold("2 closed", [document.createElement("p")], { open: true });
assert.equal(f2.querySelector(".ui-fold-b").childNodes.length, 1, "open: drawn at once");

// ---- the one primary
const head = PR.screenHead("Alerts", { action: PR.primary("Fix", null), help: HELP.help("Alerts", { text: "x" }) });
assert.equal(PR.primaries(head), 1);
assert.equal(head.querySelector(".ui-primary").textContent, "Fix");
assert.ok(head.querySelector(".ui-act .ui-primary"), "at the top right of the head");

// ---- Who will do it: the address keys
assert.equal(K.KEYS.get("by").kind, "overlay");
assert.equal(K.KEYS.get("by").owner, "ui/who.js");
assert.ok(K.INSIDE.includes("by"), "it leaves with the dialog");
assert.equal(K.KEYS.get("who").owner, "tabs/visitor.js", "who stays Find a person's");
assert.equal(K.KEYS.get("rby").owner, "tabs/sa-revenue.js", "Revenue's breakdown moved to rby");
// An old Revenue link (by=campaign) keeps its breakdown, as rby; by=me there is Who will do it.
go("#sales/revenue?cur=EUR&by=campaign");
assert.equal(S.read().rby, "campaign");
assert.equal(S.read().by, "");
assert.equal(S.read().cur, "EUR");
assert.deepEqual(W.WHO, ["me", "dev", "agent"], "the approved order");
assert.deepEqual(W.WHO.map((k) => W.WORDS[k].title), ["Me", "My developer", "My AI agent"]);

// Only the paths given are offered.
ME.user = "owner@example.com";
const only = W.whoStep({ paths: { me: () => "steps", dev: () => "message" } });
assert.deepEqual(only.el.querySelectorAll(".ui-who-c").map((b) => b.dataset.who), ["me", "dev"]);
assert.equal(only.el.querySelector('[role="radiogroup"]').getAttribute("aria-label"), "Who will do it?");
assert.equal(only.choice(), "", "nothing remembered, no fallback: nothing chosen");

// The address round trip, inside an open dialog (setup=logs is one).
go("#overview/summary?setup=logs&step=1&by=dev");
const route = { key: "setup", value: "logs" };
const meNodes = () => { const p = document.createElement("p"); p.textContent = "The steps by hand"; return p; };
let w1 = W.whoStep({ route, paths: { me: W.mePath(meNodes), dev: () => "dev words", agent: () => "agent words" } });
assert.equal(w1.choice(), "dev", "the address opens on its choice");
await w1.ready;
assert.equal(w1.el.querySelector('[aria-checked="true"]').dataset.who, "dev");
await w1.pick("me");
assert.equal(S.read().by, "me", "a pick is written to the address");
assert.ok(location.hash.includes("by=me") && location.hash.includes("setup=logs"));
assert.equal(w1.el.querySelector(".ui-who-path").textContent, "The steps by hand", "Me: the steps by hand");
go("#overview/summary?setup=logs&step=1&by=someone");
assert.equal(W.whoStep({ route, paths: { me: () => "", dev: () => "" } }).choice(), "dev", "Insights' someone (its first Fix this links) is read as dev");
go("#overview/summary?setup=logs&step=1&by=nonsense");
assert.equal(W.whoStep({ route, paths: { me: () => "", dev: () => "" } }).choice(), "me", "a word it does not know: the remembered choice");

// Remembered per person: the next dialog opens on the last choice; another person does not.
go("#overview/summary");
assert.equal(W.remembered(), "me");
assert.equal(W.whoStep({ paths: { me: () => "", dev: () => "", agent: () => "" } }).choice(), "me");
for (const v of Object.keys(localStorage)) assert.ok(!String(v).includes("@"), "the person's address is never stored as is");
ME.user = "dev@example.com";
assert.equal(W.remembered(), "", "another person starts fresh");
assert.equal(W.whoStep({ paths: { me: () => "", dev: () => "" }, fallback: "dev" }).choice(), "dev", "then the caller's fallback");
assert.equal(W.whoStep({ paths: { me: () => "" }, fallback: "agent" }).choice(), "", "a fallback that is not offered is not used");
ME.user = "owner@example.com";
// The address beats the remembered choice; a remembered choice not offered here is not used.
W.remember("agent");
go("#overview/summary?setup=logs&step=1&by=me");
assert.equal(W.whoStep({ route, paths: { me: () => "", agent: () => "" } }).choice(), "me");
go("#overview/summary");
assert.equal(W.whoStep({ paths: { me: () => "", dev: () => "" } }).choice(), "", "agent is remembered but not offered here");
assert.equal(W.remember("nobody"), false);

// Arrow keys move the choice, as a radio group does.
const ar = W.whoStep({ paths: { me: () => "", dev: () => "", agent: () => "" } });
ar.el.querySelector('[data-who="me"]').dispatchEvent(key("keydown", "ArrowDown"));
assert.equal(ar.choice(), "dev");
ar.el.querySelector('[data-who="dev"]').dispatchEvent(key("keydown", "ArrowDown"));
assert.equal(ar.choice(), "agent");
ar.el.querySelector('[data-who="agent"]').dispatchEvent(key("keydown", "ArrowDown"));
assert.equal(ar.choice(), "me", "and wraps");

// ---- each path calls the flow Skald already has
// My AI agent: the agent line for these jobs (sites/agentlink), never made by itself from a link.
go("#overview/summary?setup=logs&step=1&by=agent&agent=claude-code");
posted.length = 0;
const wa = W.whoStep({ route, paths: { me: () => "", agent: W.agentPath({ site: "example.com", jobs: ["logs"], route }) } });
document.body.append(wa.el);
await wa.ready;
await tick();
assert.equal(wa.choice(), "agent");
assert.equal(posted.filter(([p]) => p === "sites/agentlink").length, 0, "opened from a link: no line made by itself");
const make = wa.el.querySelectorAll("button").find((b) => b.textContent === "Make the line");
assert.ok(make, "the agent line's own Make the line");
make.click();
await tick(20);
const ask = posted.find(([p]) => p === "sites/agentlink");
assert.deepEqual(ask[1], { site: "example.com", jobs: ["logs"] }, "the existing line, with the job kit/agent_jobs.py knows");
assert.equal(S.read().link, "0f3a9c2e7b1d4a58", "the line watched is in the address by its id");
assert.ok(!location.hash.includes("abc123"), "never the line or its code");
assert.ok(wa.el.querySelector(".ag-line"), "the line in its box (agent-setup.js lineBox)");
assert.ok(wa.el.textContent.includes("Watch your agent work"));
// No agent chosen yet: the agent tiles first (agent-setup.js agentChooser), the choice kept in the address.
go("#overview/summary?setup=logs&step=1&by=agent");
const wb = W.whoStep({ route, paths: { agent: W.agentPath({ site: "example.com", jobs: ["logs"], route }) } });
await wb.ready;
const tile = wb.el.querySelectorAll(".ag-tile").find((b) => b.dataset.agent === "codex");
assert.ok(tile, "the agent tiles");
assert.equal(wb.el.querySelectorAll(".ag-tile").some((b) => b.dataset.agent === "chat"), false, "only agents that run commands");
tile.click();
await tick(20);
assert.equal(S.read().agent, "codex");

// My developer or host: the private link (conn-share.js shareBox, sites/share) when the job has one.
go("#overview/summary?setup=logs&step=1&by=dev");
posted.length = 0;
const wd = W.whoStep({ route, paths: { dev: W.devPath({ site: "example.com", task: "send", method: "server" }) } });
await wd.ready;
const share = wd.el.querySelectorAll("button").find((b) => b.textContent === "Share with your developer");
assert.ok(share, "the existing Share with your developer");
share.click();
assert.equal(S.read().share, "1", "its form open is in the address");
const mk = wd.el.querySelectorAll("button").find((b) => b.textContent === "Make the link");
mk.click();
await tick(20);
const sh = posted.find(([p]) => p === "sites/share");
assert.equal(sh[1].site, "example.com");
assert.equal(sh[1].task, "send");
// With no link for the job: the message to send, with its copy icon, and the link to this place.
const wm = W.whoStep({ paths: { dev: W.devPath({ site: "example.com", message: "Update PHP on media.example.com.", link: "https://app.example.com/traffic/example.com/#site/alerts" }) }, fallback: "dev" });
await wm.ready;
assert.ok(wm.el.querySelector(".ui-msg").textContent.includes("Update PHP"));
assert.ok(wm.el.querySelectorAll(".ua-copy").length >= 2, "copy on the message and on the link");
assert.ok(wm.el.querySelector(".ua-open"), "open on the link");

// A path that fails to draw says so, in words.
const wf = W.whoStep({ paths: { me: () => Promise.reject(new Error("no data")) }, fallback: "me" });
await wf.ready.catch(() => {});
await tick();
assert.ok(wf.el.textContent.includes("This part could not be drawn: no data"));

// whoDialog: the drawer, with the question inside and Close.
go("#overview/summary");
const d = await W.whoDialog({ title: "Fix it", paths: { me: () => "steps" }, fallback: "me" });
assert.ok(d.el.textContent.includes("Who will do it?"));
assert.ok(d.el.querySelectorAll("button").some((b) => b.textContent === "Close"));
d.close({ instant: true });

console.log("ui: all passed");
process.exit(0);
