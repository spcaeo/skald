// Overview's "Set up this site" (js/tabs/checklist.js, js/setup-items.js) and its
// Set up dialogs (js/tabs/setup-*.js), drawn from real helper answers
// (tests/test_setup_checklist.py writes them to SETUP_JSON): plain lines with no
// server words outside "For your server admin", a Set up button on each open
// line (none for a reader who may not manage), and each dialog - logs, script
// tag, lead hook, mail, privacy, page assets, countries, Next.js pages - opened and walked;
// the mails to the developer hold the snippet or the steps and never the secret.
//
//   SETUP_JSON=answers.json node tests/js/setup-checklist.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install, Ev } from "./dom-lite.mjs";

install();
const given = JSON.parse(readFileSync(process.env.SETUP_JSON, "utf8"));
const SITE = given.site;
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; this.dispatchEvent?.(new Ev("close")); };
// Reduced motion: a drawer closes at once, with no animation to wait for.
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
const copied = [];
Object.defineProperty(globalThis.navigator, "clipboard", { value: { writeText: async (t) => { copied.push(t); } }, configurable: true });

const posted = [];
let hooked = false;     // after the test: the lead hook is ready, then a real one arrives
let rscState = "";      // "", "missing" (payloads without the field) or "fixed"
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => structuredClone(data) });
  if (path === "settings") return answer(given.settings);
  if (path.startsWith("integrations?site=")) {
    if (rscState) return answer(rscState === "fixed" ? given.integ_rsc_ok : given.integ_rsc);
    if (!hooked) return answer(given.integ);
    const after = structuredClone(given.integ_after);
    const lead = after.tools.find((t) => t.tool === "lead");
    Object.assign(lead, { state: "received", words: "last received just now (kept)" });
    return answer(after);
  }
  if (path === "sites") return answer(given.sites);
  if (path.startsWith("sites/status")) return answer(given.status_after);
  if (path === "integrations/secret") return answer(given.secret);
  if (path === "integrations/test") { hooked = true; return answer(given.hooktest); }
  if (path === "settings/save") {
    if ("privacy.keep_ips" in body) return answer(given.saved_privacy);
    if (Object.keys(body).some((k) => k.startsWith("mail."))) return answer(given.saved_mail);
    return answer({ ok: true, saved: Object.keys(body), settings: given.settings.settings, notice: given.settings.notice });
  }
  if (path === "sites/share") return answer({ ok: true, link: "https://www.example.com/traffic-auth/setup/xxxxxxxxxxxxxxxxxxxxxx", ref: "ab12cd34", expires_at: "2026-10-28T12:00:00Z" });
  if (path === "settings/test-mail") return answer({ ok: true, sent: true, to: body.to });
  if (path === "tokens/create") return answer({ ok: true, token: "skald_ab12cd34_" + "t".repeat(43), id: "ab12cd34", scopes: body.scopes, sites: body.sites });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { setupChecklist, row } = await import(new URL("tabs/checklist.js", JS));
const { verdict } = await import(new URL("tabs/conn-send.js", JS));
const { openSetup } = await import(new URL("tabs/setup-dialogs.js", JS));

const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
async function next() { button(dialog(), "Next").click(); await tick(); }
const stepName = () => dialog().querySelector("h3.cn-h").textContent;
function pick(root, value) {
  const radio = root.querySelectorAll("input").find((i) => i.getAttribute("value") === value);
  assert.ok(radio, `the choice ${value}`);
  radio.checked = true;
  radio.dispatchEvent(new Ev("change"));
}
// The text a site owner reads: everything but the folded server admin's words.
const plain = (n) => (n instanceof Element && n.tagName === "DETAILS" && n.classList.contains("fold") ? "" : n.childNodes ? (n instanceof Element ? n.childNodes.map(plain).join("") : n.textContent) : n.textContent);
const mailBody = (a) => decodeURIComponent(/[?&]body=([^&]*)/.exec(a.getAttribute("href"))?.[1] || "");
const mailOf = (d) => d.querySelector("a.su-mail");
async function closeDialog() { dialog().querySelector(".dw-x").click(); await tick(); }

// ---- the checklist: plain lines, a Set up button on each open line
const m = { site: SITE, today: new Date().toISOString().slice(0, 10), live: null, byDay: new Map() };
const box = setupChecklist(m);
assert.ok(box, "an owner sees the checklist");
document.body.append(box);
await tick();
assert.ok(!box.hidden, "something is left, so the list shows");
const items = box.querySelectorAll("li.su-i");
assert.deepEqual(items.map((li) => li.getAttribute("data-item")), ["logs", "assets", "countries", "script", "lead", "mail", "privacy"]);
const said = plain(box);
for (const word of ["--origin", "helper", "nginx", "beacon.origins", "logs.dir"]) assert.ok(!said.includes(word), `no "${word}" for the site owner: ${said}`);
const folds = box.querySelectorAll("details.fold").map((d) => d.textContent).join(" ");
assert.ok(folds.includes("For your server admin"));
assert.ok(folds.includes("nginx"), "the doctor's words stay, folded, for the server admin");
const byId = (id) => items.find((li) => li.getAttribute("data-item") === id);
for (const li of items) {
  const open = li.classList.contains("su-todo");
  assert.equal(Boolean(button(li, "Set up")), open && ["logs", "assets", "countries", "script", "lead", "mail", "privacy"].includes(li.getAttribute("data-item")), li.textContent);
}
for (const id of ["logs", "script", "lead", "mail", "privacy"]) assert.ok(button(byId(id), "Set up"), `${id} has Set up`);
assert.ok(byId("script").textContent.includes("optional") && byId("lead").textContent.includes("optional"));
assert.ok(!byId("mail").textContent.includes("optional"));
// A reader who may not manage gets the plain line and no button.
const viewerRow = row({ id: "mail", title: "Mail recipient confirmed", state: "todo", says: "Nobody gets the daily mail yet.", tech: "x", act: "mail" });
assert.ok(!button(viewerRow, "Set up") && !viewerRow.querySelector("details"));

// ---- Logs arriving: Settings > Connections' send dialog
button(byId("logs"), "Set up").click();
await tick(30);
let d = dialog();
assert.ok(d.textContent.includes("Send this site's visits to Skald"));
assert.equal(d.querySelectorAll(".cn-bar li").length, 4);
pick(d, "docker");
await next();
assert.match(stepName(), /Step 2 of 4: Sending token/);
await closeDialog();
assert.ok(!dialog(), "closed");

// ---- Script tag: what it adds, the tag, the mail, the Test
button(box.querySelectorAll("li.su-i").find((li) => li.getAttribute("data-item") === "script"), "Set up").click();
await tick(30);
d = dialog();
assert.match(stepName(), /Step 1 of 4: What it adds/);
assert.ok(d.textContent.includes("what a server log cannot see"));
for (const word of ["--origin", "helper", "nginx"]) assert.ok(!plain(d).includes(word), word);
await next();
const tag = given.integ.script.tag;
assert.ok(d.querySelector(".cn-code").textContent.includes(tag), "the exact tag for this site");
assert.ok(tag.includes(`data-site="${SITE}"`));
for (const words of ["WordPress", "Next.js", "root layout", "header.php", "<head>"]) assert.ok(d.textContent.includes(words), words);
assert.ok(d.querySelector("details.fold").textContent.includes("/traffic-beacon"), "the server part is folded");
await next();
const tagMail = mailBody(mailOf(d));
assert.ok(tagMail.includes(tag), "the mail holds the tag");
assert.ok(tagMail.includes("WordPress") && tagMail.includes("no password and no token"));
assert.match(mailOf(d).getAttribute("href"), /^mailto:\?subject=Add%20the%20Skald%20script%20tag/);
// "Share with your developer": a private page for the script task.
button(d, "Share with your developer").click();
button(d, "Make the link").click();
await tick();
assert.deepEqual(posted.filter(([p]) => p === "sites/share").pop()[1], { site: SITE, task: "script", days: 7 });
assert.ok(d.textContent.includes("https://www.example.com/traffic-auth/setup/"));
await next();
assert.match(stepName(), /Step 4 of 4: Test/);
assert.equal(verdict(given.status_before, "script").kind, "wait", "before: waiting for the first event");
button(d, "Test connection").click();
await tick(30);
assert.ok(d.querySelector(".cn-answer").textContent.includes("Connected: a page opened with the tag"), d.querySelector(".cn-answer").textContent);
button(d, "Done").click();
await tick();
assert.ok(!dialog());

// ---- Lead hook: the tool, the secret, the steps, the mail without the secret, the test
const secret = given.secret.secret;
button(box.querySelectorAll("li.su-i").find((li) => li.getAttribute("data-item") === "lead"), "Set up").click();
await tick(30);
d = dialog();
for (const words of ["Your site's own form or backend", "Zapier, Make or n8n", "Calendly", "Cal.com", "Stripe", "HubSpot"]) assert.ok(d.textContent.includes(words), words);
pick(d, "lead");
await next();
assert.match(stepName(), /The secret/);
await next();
assert.ok(d.textContent.includes("Make the secret first."), "Next waits for the secret");
button(d, "Make the secret").click();
await tick();
assert.ok(d.querySelector(".cn-code").textContent.includes(secret), "shown once");
await next();
assert.match(stepName(), /Set it up/);
assert.ok(d.textContent.includes(given.secret.url) && d.textContent.includes(secret), "the address and the secret filled in");
const hookMail = mailBody(mailOf(d));
assert.ok(hookMail.includes(given.secret.url) && hookMail.includes("X-Skald-Signature"), "the mail holds the steps");
assert.ok(!hookMail.includes(secret) && !mailOf(d).getAttribute("href").includes(encodeURIComponent(secret)), "never the secret");
assert.ok(hookMail.includes("The secret is not in this mail"));
button(d, "Copy the steps").click();
await tick();
assert.ok(copied.pop().includes(secret), "the copied steps hold the secret, for the reader");
assert.ok(button(d, "Share with your developer"), "a private page for the hook task");
// The guide's body and examples, with this hook's address.
await tick(50);
const ex = d.querySelectorAll("details.fold").find((x) => x.textContent.includes("examples in curl, Node, Python and PHP"));
assert.ok(ex && ex.textContent.includes(given.secret.url), "the guide's examples carry the real address");
assert.ok(!ex.textContent.includes("stats.example.com/traffic-hooks"));
button(d, "Share with your developer").click();
button(d, "Make the link").click();
await tick();
assert.deepEqual(posted.filter(([p]) => p === "sites/share").pop()[1], { site: SITE, task: "hook", method: "lead", days: 7 });
await next();
button(d, "Send a test lead").click();
await tick();
assert.ok(d.querySelector(".cn-answer").textContent.includes("The test was signed, received and read"));
button(d, "Wait for a real one").click();
await tick();
assert.ok(d.querySelector(".cn-answer").textContent.includes("Connected: Your site's server (lead), last received just now"));
assert.deepEqual(posted.filter(([p]) => p.startsWith("integrations/")).map(([p, b]) => [p, b.tool]), [["integrations/secret", "lead"], ["integrations/test", "lead"]]);
assert.ok(!posted.some(([p, b]) => p === "sites/share" && JSON.stringify(b).includes(secret)), "the share asks for no secret");
await closeDialog();

// ---- Mail: turn on, who gets it, confirm and test
button(box.querySelectorAll("li.su-i").find((li) => li.getAttribute("data-item") === "mail"), "Set up").click();
await tick(30);
d = dialog();
assert.ok(d.textContent.includes("Daily mail") && d.textContent.includes("Weekly mail"));
await next();
assert.match(stepName(), /Who gets it/);
d.querySelector("textarea").value = "owner@example.com";
d.querySelector("textarea").dispatchEvent(new Ev("input"));
await next();
assert.match(stepName(), /Confirm and test/);
assert.ok(posted.some(([p, b]) => p === "settings/save" && b["mail.to"]?.[0] === "owner@example.com"));
assert.ok(d.querySelector(".cn-answer"), "who still has to confirm, or that all did");
button(d, "Send a test mail").click();
await tick();
assert.ok(d.textContent.includes("Sent to owner@example.com"));
await closeDialog();

// ---- Privacy: the three IP choices, names and emails, the notice with Copy
button(box.querySelectorAll("li.su-i").find((li) => li.getAttribute("data-item") === "privacy"), "Set up").click();
await tick(30);
d = dialog();
for (const words of ["Full address", "Shortened (last part removed)", "Don't keep", "203.0.113.57 is kept as 203.0.113.0"]) assert.ok(d.textContent.includes(words), words);
pick(d, "short");
await next();
assert.match(stepName(), /Names and emails/);
await next();
const save = posted.filter(([p]) => p === "settings/save").pop()[1];
assert.equal(save["privacy.keep_ips"], "short");
const card = d.querySelector("section.notice-card");
assert.ok(card, "the wording for the privacy notice");
for (const line of given.saved_privacy.notice.items) assert.ok(card.textContent.includes(line), line);
button(card, "Copy").click();
await tick();
assert.equal(copied.pop(), given.saved_privacy.notice.text);
button(d, "Done").click();
await tick();

// ---- Page assets and countries (open when the log shows visits that are not people, or no country)
await openSetup("assets", SITE, { item: { tech: "Page assets: no request for /_next/static/ in the log's last lines" } });
await tick(30);
d = dialog();
await next();
assert.ok(d.textContent.includes("Choose what the site is built with."));
pick(d, "wordpress");
await next();
assert.deepEqual(posted.filter(([p]) => p === "settings/save").pop()[1], { "site.asset_prefixes": ["/wp-content/", "/wp-includes/"] });
assert.ok(d.textContent.includes("Saved."));
for (const word of ["helper", "nginx", "backfill"]) assert.ok(!plain(d).includes(word), word);
await closeDialog();
await openSetup("countries", SITE, {});
d = dialog();
assert.ok(d.textContent.includes("Skald never guesses"));
await next();
const geo = mailBody(mailOf(d));
assert.ok(geo.includes("SKALD_COUNTRY_DB") && geo.includes(SITE));
await closeDialog();

// ---- Next.js pages: only on a log whose payloads lack the prefetch field
rscState = "missing";
const nbox = setupChecklist(m);
document.body.append(nbox);
await nbox.refresh();
await tick();
const nrow = nbox.querySelectorAll("li.su-i").find((li) => li.getAttribute("data-item") === "rsc");
assert.ok(nrow, "the Next.js line shows");
assert.ok(nrow.textContent.includes("Pages opened inside the site are not counted yet"));
for (const word of ["rsc_prefetch", "nginx", "_rsc"]) assert.ok(!plain(nrow).includes(word), word);
assert.ok(nrow.querySelector("details.fold").textContent.includes("rsc_prefetch=$http_next_router_prefetch"));
button(nrow, "Set up").click();
await tick(30);
d = dialog();
assert.match(stepName(), /Step 1 of 4: What is missing/);
assert.ok(d.textContent.includes("prefetch") && d.textContent.includes("Nothing is guessed"));
await next();
const codes = d.querySelectorAll(".cn-code").map((c) => c.textContent);
assert.ok(codes.some((c) => c.includes(" rsc_prefetch=$http_next_router_prefetch")), "the nginx line");
assert.ok(codes.some((c) => c.includes("log_format") && c.includes("rsc_prefetch=$http_next_router_prefetch';")), "a whole log_format, the field last");
assert.ok(codes.some((c) => c.includes("rsc_prefetch=%{Next-Router-Prefetch}i")), "the Apache line");
for (const words of ["sudo nginx -t", "sudo systemctl reload nginx"]) assert.ok(d.textContent.includes(words), words);
button(d, "Copy").click();
await tick();
assert.equal(copied.pop(), " rsc_prefetch=$http_next_router_prefetch");
await next();
const nmail = mailBody(mailOf(d));
for (const words of ["rsc_prefetch=$http_next_router_prefetch", "rsc_prefetch=%{Next-Router-Prefetch}i", "nginx -t", SITE]) assert.ok(nmail.includes(words), words);
assert.ok(button(d, "Share with your developer"), "a private page for the developer");
button(d, "Share with your developer").click();
await tick();
button(d, "Make the link").click();
await tick(30);
assert.equal(posted.filter(([p]) => p === "sites/share").pop()[1].task, "nextjs");
await next();
assert.match(stepName(), /Step 4 of 4: Test/);
rscState = "fixed";
button(d, "Test").click();
await tick(30);
assert.ok(d.textContent.includes("It works: the log records the header"), d.textContent);
await closeDialog();
await nbox.refresh();
await tick();
assert.ok(!nbox.querySelectorAll("li.su-i").some((li) => li.getAttribute("data-item") === "rsc"), "fixed: the line goes away");
nbox.remove();
rscState = "";
await box.refresh();

// ---- 2.21: the list names its site
assert.equal(box.querySelector(".su-head h2").textContent, `Set up ${SITE}`);
assert.equal(box.getAttribute("aria-label"), `Set up ${SITE}`);

// ---- 2.21: each Set up dialog is in the address, setup=<item>&step=<n>; closing takes it away
location.hash = "#overview/summary";
button(box.querySelectorAll("li.su-i").find((li) => li.getAttribute("data-item") === "mail"), "Set up").click();
await tick(30);
let q = new URLSearchParams(location.hash.split("?")[1]);
assert.equal(q.get("setup"), "mail", location.hash);
assert.equal(q.get("step"), "1");
await next();
q = new URLSearchParams(location.hash.split("?")[1]);
assert.equal(q.get("step"), "2", "a step replaces the entry in place");
await closeDialog();
await tick(5);
q = new URLSearchParams(location.hash.split("?")[1] || "");
assert.ok(!q.get("setup") && !q.get("step"), `closing takes the keys away: ${location.hash}`);
// A link at a step: the dialog opens there (the mail dialog's first step has no choice to wait for).
const { openSetupKey } = await import(new URL("tabs/setup-dialogs.js", JS));
location.hash = "#overview/summary?setup=mail&step=2";
await openSetupKey("mail", m, 2);
await tick(30);
assert.match(stepName(), /Step 2 of 3: Who gets it/);
await closeDialog();
// A step that needs an earlier choice waits for it: assets at step 2 opens at step 1.
location.hash = "#overview/summary?setup=assets&step=2";
await openSetupKey("assets", m, 2);
await tick(30);
assert.match(stepName(), /Step 1 of 2/, "the choice first");
await closeDialog();
// Not for a viewer, and nothing for an unknown item.
ME.role = "viewer";
assert.equal(await openSetupKey("mail", m, 1), "Not available to your role.");
ME.role = "owner";
assert.match(await openSetupKey("nope", m, 1), /not in this version/);

// ---- 2.21: Settings › Connections shows the same list, always, all ticks and "All set" once done
const doneAnswers = { status: [{ id: "logs", state: "OK", says: "readable" }, { id: "assets", state: "OK", says: "ok" }, { id: "script", state: "OK", says: "the last event came 2 minutes ago" }],
  tools: [], settings: { "mail.to": { value: ["owner@example.com"], source: "site" }, "mail.daily": { value: true, source: "site" }, "privacy.keep_ips": { value: "full", source: "site" } }, waiting: [] };
const { setupItems: items2, setupDone: done2 } = await import(new URL("setup-items.js", JS));
const live = { ...m, live: { state: "ok", day: m.today, figures: { requests: 9, readers: 3, hits: { people: 3 }, by: { country: { CA: 3 } } } } };
assert.ok(done2(items2(live, doneAnswers)), "a finished site");
const conn = setupChecklist(live, { where: "connections" });
assert.ok(conn && !conn.hidden, "always drawn on Connections");
assert.ok(!button(conn, "Hide on Overview"), "no Hide on Connections");
assert.equal(conn.querySelector(".su-head h2").textContent, `Set up ${SITE}`);

// ---- Hide on Overview: hidden on Overview only, with the note that it stays on Connections
assert.ok(box.textContent.includes("Always in Settings › Connections"));
button(box, "Hide on Overview").click();
assert.ok(!box.parentNode, "hidden for this site");
assert.equal(setupChecklist(m), null, "not on Overview");
assert.ok(setupChecklist(m, { where: "connections" }), "still on Settings › Connections");
console.log("setup-checklist: all passed");
