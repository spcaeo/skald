// Settings v2: the pages that were forms, as rows (js/tabs/set-parts.js, prefs.js,
// set-internal.js, reports.js, ai-answers-settings.js). A row shows the value in words and a
// pill; the form opens in a drawer whose part is in the address (edit=<id>, set-edit.js),
// so a link opens it too; an internal address goes in the address as a code, never itself.
//
//   node tests/js/set-parts.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

const set = (label, kind, value, more = {}) => ({ label, kind, value, source: "default", editable: true, ...more });
const SETTINGS = { ok: true, role: "owner", site: "example.com", settings: {
  "mail.daily": set("Daily mail", "bool", true), "mail.weekly": set("Weekly mail", "bool", false),
  "mail.to": set("Recipients", "emails", ["ann@example.com"], { source: "site" }), "mail.from_name": set("From name", "text", ""),
  "mail.from": set("Sender address", "email", "", { editable: false, reason: "Set by whoever runs this install." }),
  "mail.smtp.host": set("SMTP server", "text", null, { hidden: true, editable: false, reason: "Shown to install admins only." }),
  "mail.smtp.password": set("SMTP password", "secret", null, { set: false, editable: false, reason: "Set by whoever runs this install." }),
  "pagespeed.api_key": set("PageSpeed key", "secret", null, { set: true }),
  "privacy.keep_ips": set("Keep visitors' IP addresses", "ipmode", "short", { source: "site" }),
  "privacy.keep_days": set("Visits with addresses", "int", 395, { lo: 1, hi: 3650 }),
  "conversions.retention_days": set("Leads and the pages they read", "int", 0, { forever: true, lo: 1, hi: 3650 }),
} };
const OURS = { ok: true, limit: 50, entries: [
  { ip: "203.0.113.7", label: "Office Mac", active: true, added_at: "2026-10-01T10:00:00Z" },
  { ip: "198.51.100.0/24", label: "Test lab", active: false, paused_since: "2026-10-20T10:00:00Z", added_at: "2026-10-02T10:00:00Z" },
  { ip: "192.0.2.10", label: "Uptime check", source: "config", editable: false }] };
const REPORTS = { ok: true, mail_ready: false, timezone: "UTC", org: "Example Org", periods: { last_month: "Last month" }, sections: ["summary"], section_words: { summary: "Summary" },
  branding: { agency_name: "Example Agency", color: "#0f766e", logo: false },
  reports: [{ id: 12, spec: { name: "Monthly for the client", recipients: ["client@example.com"], schedule: { kind: "monthly", day: 1, at: "08:00" }, period: "last_month", sections: ["summary"], paused: false },
    confirmed: [], waiting: ["client@example.com"], next: "2026-11-01T08:00:00Z", next_first: "2026-10-01", next_last: "2026-10-31", last_send: null }] };
const AIA = { ok: true, editable: true, providers: [{ id: "openai", name: "OpenAI", key: false }],
  lists: { questions: ["Which analytics tool reads server logs?"], brands: ["Example Analytics"], competitors: [], keep_days: 400 },
  profiles: [{ id: "p1", name: "Toronto, English", frequency: "weekly", repeats: 1, asks_questions: 1, cap: 2, paused: [], providers: ["openai"],
    estimate: { answers: 1, questions: 1, tries: 1, assistants: 1, per_run: 0.01, per_month: 0.05, cap: 2, fits: true, days: 7 } }] };
const posted = [];
globalThis.fetch = async (path, init = {}) => {
  const p = String(path).split("?")[0];
  if (init.body) posted.push([p, JSON.parse(init.body)]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (p === "settings") return answer(SETTINGS);
  if (p === "settings/save") return answer({ ok: true, settings: { ...SETTINGS.settings, "mail.weekly": { ...SETTINGS.settings["mail.weekly"], value: true, source: "site" } } });
  if (p === "ours") return answer(OURS);
  if (p === "ours/pause") return answer({ ok: true, entries: OURS.entries });
  if (p === "settings/reports") return answer(REPORTS);
  if (p === "ai-answers") return answer(AIA);
  if (p === "logo/state") return answer({ ok: true, source: "auto", editable: true });
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "ann@example.com", install_admin: true });
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const E = await import(new URL("tabs/set-edit.js", JS));
const P = await import(new URL("tabs/set-parts.js", JS));
const I = await import(new URL("tabs/set-internal.js", JS));
const m = { site: "example.com", x: { sites: { sites: [{ name: "example.com" }] }, ours: { api: { list: "ours" } } } };
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const q = () => new URLSearchParams(location.hash.split("?")[1]);
const closeAll = () => document.body.querySelectorAll("dialog").filter((d) => d.open).forEach((d) => d.querySelector(".dw-x")?.click());
async function page(route, sub = "") {
  closeAll();
  location.hash = `#${route}${sub ? `?sub=${sub}` : ""}`;
  const root = document.createElement("div");
  document.body.append(root);
  root.append(...TAB_RENDER[route](m, { ...S.read(), tab: route, sub }, {}).flat(9).filter(Boolean));
  await tick(60);
  return root;
}
const primaries = (root) => root.querySelectorAll(".set-primary, .ui-primary").filter((b, i, all) => all.indexOf(b) === i);

// ---- A setting's value in words; a pill only for on/off and set/not set.
assert.deepEqual(P.valueOf("mail.daily", SETTINGS.settings["mail.daily"]), { text: "", kind: "good", word: "On" });
assert.equal(P.valueOf("privacy.keep_ips", SETTINGS.settings["privacy.keep_ips"]).text, "Shortened (last part removed)");
assert.equal(P.valueOf("privacy.keep_days", SETTINGS.settings["privacy.keep_days"]).text, "395 days");
assert.equal(P.valueOf("conversions.retention_days", SETTINGS.settings["conversions.retention_days"]).text, "Kept for good");
assert.equal(P.valueOf("pagespeed.api_key", SETTINGS.settings["pagespeed.api_key"]).word, "Set");
assert.equal(P.valueOf("mail.smtp.host", SETTINGS.settings["mail.smtp.host"]).text, "Shown to install admins only");

// ---- Mail: rows, one primary (Send a test mail), no form on the page; the mail server's
// settings, none of which this reader may change, are one read-only line.
{
  const root = await page("settings/site/mail");
  assert.equal(root.querySelector("form"), null, "no form on the page");
  const mail = root.querySelector('[data-part="mail"]');
  assert.ok(mail.textContent.includes("Daily mail") && mail.querySelector(".ui-pill.good"), "a row each, On as a pill");
  assert.ok(mail.textContent.includes("ann@example.com"), "the recipients in words");
  assert.ok(mail.textContent.includes("Preview the mail"), "the preview is a row of the same card");
  const smtp = root.querySelector('[data-part="smtp"]');
  assert.equal(smtp.querySelectorAll(".set-row").length, 1, "read-only: one line, not a row each");
  assert.ok(smtp.querySelector(".ui-pill.off").textContent.includes("Read-only"));
  assert.equal(primaries(root).length, 1, "one primary");
  assert.ok(primaries(root)[0].textContent.includes("Send a test mail"));
  // A row opens the card's form in a drawer, its part in the address; Save waits for a change.
  mail.querySelector("button.set-row").click();
  await tick();
  assert.equal(q().get("edit"), "mail", location.hash);
  const d = dialog();
  assert.ok(d.querySelector("form") && d.textContent.includes("Weekly mail"));
  const save = d.querySelectorAll("button").find((b) => b.textContent === "Save");
  assert.ok(save.disabled, "Save waits for a change");
  const weekly = d.querySelectorAll("input").find((i) => i.id === "set-mail-weekly");
  weekly.checked = true;
  d.querySelector("form").dispatchEvent(new Event("change"));
  assert.ok(!save.disabled, "a change wakes Save");
  for (const el of d.querySelectorAll("input")) el.value ??= el.getAttribute("value") ?? "";
  for (const el of d.querySelectorAll("textarea")) el.value ??= el.textContent;
  d.querySelector("form").dispatchEvent(new Event("submit"));
  await tick(60);
  assert.deepEqual(posted.filter(([p]) => p === "settings/save").pop()[1], { "mail.weekly": true });
  assert.ok(d.textContent.includes("Saved. It applies from the next run."), "the drawer says so");
  assert.ok(root.querySelector('[data-part="mail"]').querySelectorAll(".ui-pill.good").length === 2, "the page's rows follow");
  closeAll();
  await tick();
  assert.equal(q().get("edit"), null, "closing takes the key away");
  root.remove();
}

// ---- A link opens the part on its own; a part the page does not have says so.
{
  const d = await E.openEditKey("people", m, {});
  assert.ok(d && dialog().textContent.includes("Keep visitors' IP addresses"));
  closeAll();
  assert.equal(typeof (await E.openEditKey("nothing-here", m, {})), "string");
  assert.equal(typeof (await E.openEditKey("../x", m, {})), "string");
}

// ---- Internal traffic: rows with pills, the address with a copy icon, one primary; a row's
// drawer is keyed by a code of the address, never the address.
{
  const root = await page("settings/site/details", "internal");
  const rows = root.querySelectorAll(".set-row");
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map((r) => r.querySelector(".ui-pill").textContent), ["Active", "Paused", "Always on"]);
  assert.ok(rows[0].textContent.includes("203.0.113.7") && rows[0].querySelector("button[aria-label]"), "the address, with its icons");
  assert.equal(primaries(root).length, 1);
  assert.ok(primaries(root)[0].textContent.includes("Add an address"));
  assert.ok(root.querySelector("details.ui-fold").textContent.includes("Our own traffic, in figures"), "the figures behind a fold");
  rows[0].querySelector("button.set-chg").click();
  await tick();
  const key = q().get("edit");
  assert.equal(key, `ip-${I.ipCode("203.0.113.7")}`);
  assert.ok(!key.includes("203") && !key.includes("."), "never the address");
  dialog().querySelectorAll("button").find((b) => b.textContent === "Pause it").click();
  await tick();
  assert.deepEqual(posted.filter(([p]) => p === "ours/pause").pop()[1], { ip: "203.0.113.7" });
  assert.equal(q().get("edit"), null, "done: the drawer closes");
  // The config line: locked, said in its drawer.
  rows[2].querySelector("button.set-chg").click();
  await tick();
  assert.ok(dialog().textContent.includes("Set in the config file"));
  assert.ok(!dialog().querySelectorAll("button").some((b) => b.textContent === "Delete"));
  closeAll();
  root.remove();
}

// ---- Client reports: a row each with its pill, New report the one primary, branding as rows.
{
  const root = await page("settings/site/mail", "reports");
  assert.ok(root.querySelector(".set-strip.s-warn").textContent.includes("No mail server"));
  const row = root.querySelectorAll("button.set-row").find((b) => b.textContent.includes("Monthly for the client"));
  assert.ok(row.querySelector(".ui-pill.warn").textContent.includes("No one confirmed yet"));
  assert.ok(root.textContent.includes("Example Agency") && root.textContent.includes("#0f766e"));
  assert.equal(primaries(root).length, 1);
  assert.ok(primaries(root)[0].textContent.includes("New report"));
  row.click();
  await tick();
  assert.equal(q().get("edit"), "report-12");
  assert.ok(["Preview", "Download PDF", "Send now", "History", "Edit", "Delete"].every((w) => dialog().querySelectorAll("button").some((b) => b.textContent === w)));
  dialog().querySelectorAll("button").find((b) => b.textContent === "Edit").click();
  await tick();
  assert.equal(q().get("edit"), "reportedit-12", "the report's form has its own address");
  assert.ok(dialog().querySelector("form.rp-form"));
  closeAll();
  root.remove();
}

// ---- AI answers: the lists and the profiles as rows, New profile the one primary.
{
  const root = await page("settings/ai/answers");
  assert.ok(root.querySelector(".set-strip.s-warn").textContent.includes("No API key"));
  assert.ok(root.textContent.includes("Questions buyers ask (1)") && root.textContent.includes("Which analytics tool reads server logs?"));
  const prof = root.querySelectorAll("button.set-row").find((b) => b.textContent.includes("Toronto, English"));
  assert.equal(prof.querySelector(".ui-pill.good").textContent, "Active");
  assert.equal(primaries(root).length, 1);
  prof.click();
  await tick();
  assert.equal(q().get("edit"), "profile-p1");
  assert.ok(["Duplicate", "Pause", "Run now", "Delete"].every((w) => dialog().querySelectorAll("button").some((b) => b.textContent === w)));
  closeAll();
  root.remove();
}
console.log("set-parts: all passed");
