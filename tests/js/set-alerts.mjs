// Settings › This site › Alerts (v2, js/tabs/set-alerts.js): one state line that never counts
// rules as on while alerts are off; "Turn alerts on" as the page's one primary only while they
// are off (and only for who may); All alerts and Mail alerts on top; the rules in folds by area,
// each "N of M on", a rule one line (name, "?" with its threshold, the switch); no
// "not watched" on every row; the sale minimum in a drawer (edit=alertmin).
//
//   node tests/js/set-alerts.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

const sw = (value, more = {}) => ({ kind: "bool", value, source: "default", editable: true, ...more });
let SETTINGS = {};
const reset = (enabled) => {
  SETTINGS = { "alerts.enabled": sw(enabled), "alerts.mail": sw(true), "alerts.site_down": sw(true), "alerts.server_errors": sw(true),
    "alerts.crawler_burst": sw(false), "alerts.scan_wave": sw(true, { editable: false, locked: true, reason: "Locked in config.yml." }),
    "alerts.sale": sw(true), "alerts.sale_minimum": { kind: "text", value: "USD 100", source: "site", editable: true } };
};
reset(false);
const posted = [];
globalThis.fetch = async (path, init = {}) => {
  const p = String(path).split("?")[0];
  if (init.body) {
    const body = JSON.parse(init.body);
    posted.push([p, body]);
    for (const [k, v] of Object.entries(body)) SETTINGS[k] = { ...SETTINGS[k], value: v };
  }
  return { ok: true, status: 200, json: async () => ({ ok: true, role: "owner", settings: SETTINGS }) };
};
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
ME.mode = "sessions";
ME.user = "owner@example.com";
ME.role = "owner";
const A = await import(new URL("tabs/set-alerts.js", JS));

const rules = [["site_down", "2 heartbeats missed"], ["server_errors", "10+ 5xx in 10 minutes"], ["crawler_burst", "one crawler 50%+"],
  ["scan_wave", "probes 3x the median"], ["sale", "a sale comes in"]].map(([cause, threshold]) => ({ cause, threshold, on: true, setting: `alerts.${cause}` }));
const m = { site: "example.com", x: { alerts: { open: [], closed: [], rules, enabled: false, mail: true, checked_at: "2026-10-26T21:12:00+00:00" } } };
const page = () => document.body.querySelector(".set-alerts");
// dom-lite: h() writes disabled as an attribute; a later .disabled = x is a property.
const dis = (b) => b.disabled ?? b.hasAttribute("disabled");
const text = (el) => el.textContent.replace(/\s+/g, " ").trim();

// ---- the areas
assert.equal(A.areaOf("site_down"), "Site health");
assert.equal(A.areaOf("traffic_drop"), "Traffic");
assert.equal(A.areaOf("ai_started_reading"), "Crawlers & AI");
assert.equal(A.areaOf("ai_something_new"), "Crawlers & AI", "an AI rule not named yet");
assert.equal(A.areaOf("stack_advisory"), "Security");
assert.equal(A.areaOf("sale_refunded"), "Sales");
assert.equal(A.areaOf("odd_one"), "Other");

// ---- off: nothing is checked, and no "on" count that is not true
document.body.replaceChildren(A.alertsSettings(m));
await tick();
let p = page();
const state = () => text(p.querySelector(".set-strip .ui-grow"));
const word = () => text(p.querySelector(".set-strip .ui-pill"));
assert.equal(word(), "Off");
assert.equal(state(), "Alerts are off, so nothing is checked. 4 rules will run when you turn them on.");
assert.ok(!/ on\b/.test(state().replace("turn them on", "")), "no on count while off");
const prim = () => [...document.body.querySelectorAll(".set-primary")];
assert.equal(prim().length, 1, "one primary");
assert.equal(text(prim()[0]), "Turn alerts on");
assert.ok(!p.querySelector(".state.bad"), "no banner plus button");
const pills = () => [...p.querySelectorAll(".al-fold summary .ui-pill")].map(text);
assert.deepEqual([...p.querySelectorAll(".al-fold summary b")].map(text), ["Site health", "Crawlers & AI", "Security", "Sales"]);
assert.deepEqual(pills(), ["2 of 2 will run", "0 of 1 will run", "1 of 1 will run", "1 of 1 will run"]);
assert.ok(!p.textContent.includes("not watched"), "never on every row");
// The two switches on top; a rule is one line: name, "?" (its threshold), switch.
assert.deepEqual([...p.querySelectorAll(".set-rows")[0].querySelectorAll(".al-row b")].map(text), ["All alerts", "Mail alerts"]);
const health = p.querySelector(".al-fold");
assert.ok(!health.hasAttribute("open"), "folded");
health.setAttribute("open", "");
health.dispatchEvent(new Event("toggle"));
const row = health.querySelector(".al-row");
assert.equal(text(row.querySelector(".al-name b")), "Site down");
assert.ok(row.querySelector(".ui-help-pop").textContent.includes("2 heartbeats missed"), "the threshold behind the ?");
assert.ok(!row.querySelector("small"), "one line");
assert.equal(row.querySelector('[role="switch"]').getAttribute("aria-checked"), "true");

// ---- a locked rule says so; a viewer-free page lets the owner switch
p.querySelectorAll(".al-fold")[2].setAttribute("open", "");
p.querySelectorAll(".al-fold")[2].dispatchEvent(new Event("toggle"));
const scan = p.querySelectorAll(".al-fold")[2].querySelector(".al-row");
assert.ok(dis(scan.querySelector('[role="switch"]')));
assert.ok(scan.textContent.includes("Locked in the server's config file"));

// ---- Turn alerts on: saved, the state line counts, the primary goes
prim()[0].click();
await tick();
p = page();
assert.deepEqual(posted.at(-1), ["settings/save", { "alerts.enabled": true }]);
assert.equal(word(), "On");
assert.equal(state(), "4 of 5 rules are checked with every live run, and mailed to the site's confirmed recipients.");
assert.equal(prim().length, 0, "no primary while alerts are on");
assert.deepEqual(pills(), ["2 of 2 on", "0 of 1 on", "1 of 1 on", "1 of 1 on"]);
assert.ok(p.querySelector(".al-fold").hasAttribute("open"), "an open fold stays open after a save");
// Mail off: said once, on the state line.
p.querySelectorAll(".set-rows")[0].querySelectorAll('[role="switch"]')[1].click();
await tick();
p = page();
assert.ok(state().endsWith("and shown on Site › Alerts, not mailed."), state());

// ---- the sale minimum: a row under Sales, its form in a drawer (edit=alertmin)
const sales = p.querySelectorAll(".al-fold")[3];
sales.setAttribute("open", "");
sales.dispatchEvent(new Event("toggle"));
const minRow = [...sales.querySelectorAll(".set-row")].find((r) => r.textContent.includes("Sale alert minimum"));
assert.ok(minRow.textContent.includes("USD 100"));
location.hash = "#settings/site/alerts";
minRow.click();
for (let i = 0; i < 50 && !document.body.querySelector(".set-edit"); i += 1) await tick(10);
const dw = document.body.querySelector(".set-edit");
assert.ok(dw, "the drawer");
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("edit"), "alertmin");
const save = [...dw.querySelectorAll("button")].find((b) => text(b) === "Save");
assert.ok(dis(save), "Save waits for a change");
const input = dw.querySelector("input.al-least");
input.value = "EUR 50";
input.dispatchEvent(new Event("input"));
assert.ok(!dis(save));
save.click();
await tick(60);
assert.ok(posted.some(([, b]) => b["alerts.sale_minimum"] === "EUR 50"));

// ---- no alerts file yet: one quiet line
document.body.replaceChildren(...[A.alertsSettings({ x: {} })].flat());
assert.ok(document.body.textContent.includes("No alerts file yet"));

// ---- off and locked: no primary, and it says who can switch them on
reset(false);
SETTINGS["alerts.enabled"] = sw(false, { editable: false, locked: true, reason: "Locked in config.yml." });
document.body.replaceChildren(A.alertsSettings(m));
await tick();
p = page();
assert.equal(prim().length, 0, "no primary for who may not");
assert.ok(state().includes("will run when they are turned on"));
assert.ok(state().includes("your server admin can switch them on"));

console.log("set-alerts: all passed");
