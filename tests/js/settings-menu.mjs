// Settings' menu and frame (v2, js/settings-menu.js, js/tabs/settings-frame.js,
// settings-pages.js): To do first, then four short groups; every page drawn with one title
// and its "?" (what it is for, a Help guide that exists and a public Docs page with copy and
// open icons); no card catalogue, no Next step, no Help & docs page; the phone's "Settings
// page" select; each in-page tab its own address; a tab the reader may not open left out;
// every old address (2.40's and before) opening its new home with its parameters.
//
//   node tests/js/settings-menu.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({ ok: false, error: "not found" }), headers: { get: () => null } });
const tick = (ms = 10) => new Promise((r) => setTimeout(r, ms));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const M = await import(new URL("settings-menu.js", JS));
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
// What access.js loadMe leaves hidden for an owner with accounts, not on the paid service.
S.HIDDEN.clear();
S.HIDDEN.add("settings/org/billing");
const { default: INDEX } = await import(new URL("help-index.js", JS));
const { SETTINGS_RENDER } = await import(new URL("tabs/settings-pages.js", JS));
const F = await import(new URL("tabs/settings-frame.js", JS));
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const guides = new Set(INDEX.map((g) => g.id));

// ---- the menu: To do, then This site, AI, Organisation, You (Help is in the sidebar's foot)
assert.deepEqual(M.SETTINGS_GROUPS.map((g) => g.name), ["This site", "AI", "Organisation", "You"]);
const names = (k) => M.SETTINGS_GROUPS.find((g) => g.key === k).pages.map((p) => p.name);
assert.deepEqual(names("site"), ["Data", "Leads & tools", "Site", "Privacy", "Mail & reports", "Alerts"]);
assert.deepEqual(names("ai"), ["AI assistants", "AI answers"]);
assert.deepEqual(names("org"), ["Sites", "People", "Billing", "Audit log"]);
assert.deepEqual(names("you"), ["Your account"]);
assert.equal(M.SETTINGS_PAGES[0].route, "settings/todo", "To do first");
assert.equal(M.SETTINGS_PAGES.length, 14, "about ten pages, not twenty");
assert.deepEqual(S.SETTINGS_MENU.map(([g]) => g), ["", "This site", "AI", "Organisation", "You"]);
assert.ok(!M.SETTINGS_PAGES.some((p) => /home|help/.test(p.route)), "no card page, no Help & docs page");
assert.deepEqual(M.pageOf("settings/ai/assistants").tabs.map(([k]) => k), ["mcp", "api", "tokens"], "MCP, API and tokens on one page");
assert.deepEqual(M.pageOf("settings/org/people").tabs.map(([k]) => k), ["team", "security"]);
assert.deepEqual(M.pageOf("settings/site/data").tabs.map(([k]) => k), ["logs", "script", "counting", "sample"]);

// ---- every page: drawn, one short line, a "?" note, a guide that exists, a docs path
for (const p of M.SETTINGS_PAGES) {
  assert.ok(SETTINGS_RENDER[p.route], `${p.route} has a render`);
  assert.ok(TAB_RENDER[p.route], `${p.route} is a tab`);
  assert.ok(p.line && p.line.split(/[.!?] /).length === 1, `${p.route}: one sentence at most`);
  assert.ok(M.aboutOf(p.route), `${p.route}: its "?" says what it is for`);
  assert.ok(guides.has(p.help), `${p.route}: guide ${p.help}`);
  assert.match(M.docsPath(p.route), /^[a-z-]+\/([a-z-]+\/)?$/, p.route);
  for (const [sub, , help] of p.tabs || []) {
    assert.equal(typeof SETTINGS_RENDER[p.route][sub], "function", `${p.route} ${sub}`);
    assert.ok(guides.has(M.helpOf(p.route, sub)), `${p.route} ${sub}: ${help}`);
  }
}
assert.equal(M.docsPath("settings/ai/assistants"), "integrations/mcp/");
assert.equal(M.docsPath("settings/site/data", "script"), "docs/tracking-script/");
assert.equal(M.subOf("settings/site/mail", "nope"), "mail", "an unknown tab: the first");
assert.equal(M.subOf("settings/org/people", "security", (k) => k !== "settings/org/people#security"), "team", "a tab the reader may not open: the first they may");

// ---- the frame: one title and its "?", Help and Docs inside the "?", the phone's select
const draw = (route, s = {}) => {
  const root = document.createElement("div");
  root.append(...TAB_RENDER[route]({ site: "example.com", x: { sites: { sites: [{ name: "example.com" }] } } }, { ...S.read(), tab: route, ...s }, {}).flat(9).filter(Boolean));
  return root;
};
for (const route of M.SETTINGS_PAGES.map((p) => p.route)) {
  const root = draw(route);
  await tick();
  assert.equal(root.querySelectorAll("h1").length, 1, `${route}: one title`);
  assert.equal(root.querySelector("h1").textContent, M.pageOf(route).name, `${route}: the menu's name is the title`);
  const q = root.querySelector(".set-head .ui-head .ui-help");
  assert.ok(q && q.getAttribute("aria-expanded") === "false", `${route}: the "?" by the title (ui/help.js), closed`);
  const box = root.querySelector(".set-head .ui-help-pop");
  assert.ok(box.hidden, `${route}: the note waits for the "?"`);
  q.dispatchEvent(new Event("click"));
  assert.ok(!box.hidden && q.getAttribute("aria-expanded") === "true", `${route}: the "?" opens it`);
  q.dispatchEvent(new Event("click"));
  const help = box.querySelector("a.set-help");
  assert.equal(help.getAttribute("href"), `#help?part=${M.helpOf(route)}`, route);
  const docs = box.querySelector("a.set-docs");
  assert.equal(docs.getAttribute("href"), `https://skaldanalytics.com/${M.docsPath(route)}`, route);
  assert.equal(docs.getAttribute("target"), "_blank");
  const host = box.querySelector(".set-docs-w");
  assert.ok(host && host.querySelector(".ua-copy") && host.querySelector(".ua-open"), `${route}: copy and open icons on Docs`);
  assert.equal(root.querySelector(".set-head .lede"), null, `${route}: no intro paragraph on the page`);
  assert.equal(root.querySelector("nav.set-next"), null, `${route}: no Next step`);
  const sel = root.querySelector(".set-jump select");
  assert.ok(sel && sel.getAttribute("aria-label") === "Settings page", route);
}
// A card's explaining line goes behind a "?" by its title.
const card = document.createElement("div");
card.append(Object.assign(document.createElement("section"), {}));
const sec = card.firstChild;
const h2 = document.createElement("h2"); h2.textContent = "Reports";
const sub = document.createElement("p"); sub.className = "sub"; sub.textContent = "The daily mail goes after each morning's run.";
sec.append(h2, sub);
F.tipify(card);
assert.ok(h2.querySelector(".ui-help"), "the card's ? (ui/help.js)");
assert.ok(card.querySelector(".ui-help-pop").hidden, "its line is behind it");
assert.ok(card.querySelector(".ui-help-pop").textContent.includes("each morning's run"));
assert.equal(card.querySelector("p.sub"), null, "not on the page");
// The page's one primary sits beside its title (audit rule 1), wherever the page drew it.
const sample = draw("settings/site/data", { sub: "sample" });
assert.equal(sample.querySelector(".set-head .set-act .set-primary").textContent, "Paste a sample");
assert.equal(sample.querySelectorAll(".set-primary").length, 1, "one primary");
assert.equal(sample.querySelector(".set-body .set-primary"), null, "not left in the body");
// The select lists every page this reader may open, grouped, the page open selected.
const sel = draw("settings/ai/assistants").querySelector(".set-jump select");
assert.deepEqual(sel.querySelectorAll("optgroup").map((g) => g.getAttribute("label")), ["This site", "AI", "Organisation", "You"]);
assert.ok(sel.querySelectorAll("option").some((o) => o.getAttribute("value") === "settings/ai/assistants" && o.getAttribute("selected") !== null));
assert.ok(!sel.querySelectorAll("option").some((o) => o.getAttribute("value") === "settings/org/billing"), "hidden: not listed");

// ---- in-page tabs: each its own address and its own guide; a hidden tab left out
location.hash = "#settings/site/data";
let root = draw("settings/site/data", { sub: "script" });
const tabs = root.querySelectorAll(".set-tabs a, .set-tabs [role=tab]");
assert.equal(tabs.length, 4, "the strip");
const hrefs = tabs.map((t) => t.getAttribute("href")).filter(Boolean);
assert.ok(hrefs.some((x) => x === "#settings/site/data"), hrefs.join(" "));
assert.ok(hrefs.some((x) => x.startsWith("#settings/site/data?") && x.includes("sub=script")), hrefs.join(" "));
assert.equal(root.querySelector("a.set-help").getAttribute("href"), "#help?part=tracking-script", "the tab's own guide");
S.HIDDEN.add("settings/org/people#security");
root = draw("settings/org/people", { sub: "security" });
assert.equal(root.querySelector(".set-tabs"), null, "one tab left: no strip");
S.HIDDEN.delete("settings/org/people#security");
assert.equal(draw("settings/org/people").querySelectorAll(".set-tabs a").length, 2);
location.hash = "#settings/site/mail?sub=reports";
assert.equal(S.read().sub, "reports", "sub is read from the address");
assert.equal(S.read().tab, "settings/site/mail");

// ---- old addresses: their new home, their parameters kept
const opens = (hash) => { location.hash = hash; const s = S.read(); return [s.tab, s]; };
for (const [old, [to, patch]] of Object.entries(M.OLD_SETTINGS)) {
  const [tab, s] = opens(`#${old}`);
  assert.equal(tab, to, old);
  if (patch?.sub) assert.equal(s.sub, patch.sub, old);
}
assert.equal(opens("#settings/api?conn=mcp&step=2")[0], "settings/ai/assistants");
assert.deepEqual(opens("#settings/api?conn=api").map((x, i) => (i ? x.sub : x)), ["settings/ai/assistants", "api"]);
assert.equal(opens("#connections?conn=send")[0], "settings/site/data");
assert.equal(opens("#settings/api")[0], "settings/todo");
assert.equal(opens("#settings")[0], "settings/todo", "Settings opens To do");
assert.equal(opens("#settings/home")[0], "settings/todo", "2.40's card page: To do");
assert.equal(opens("#settings/help")[0], "help", "2.40's Help & docs: Help");
assert.deepEqual(opens("#settings/site/setup?setup=finish&by=agent").map((x, i) => (i ? `${x.setup}|${x.by}` : x)), ["settings/todo", "finish|agent"]);
assert.deepEqual(opens("#settings/ai/tokens").map((x, i) => (i ? x.sub : x)), ["settings/ai/assistants", "tokens"]);
assert.deepEqual(opens("#settings/org/security").map((x, i) => (i ? x.sub : x)), ["settings/org/people", "security"]);
assert.deepEqual(opens("#settings/site/collect?sub=counting").map((x, i) => (i ? x.sub : x)), ["settings/site/data", "counting"]);
assert.equal(opens("#guides")[0], "help");
console.log("settings-menu: all passed");
process.exit(0);
