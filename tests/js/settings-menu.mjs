// Settings' menu and frame (2.40, js/settings-menu.js, js/tabs/settings-frame.js,
// settings-pages.js): the groups by user flow, every page drawn, every page and tab with a
// Help guide that exists and a public Docs page with copy and open icons, the phone's
// "Settings page" select, each in-page tab its own address, and every old address opening
// its new home with its parameters.
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
["settings/org/users", "settings/org/billing"].forEach((k) => S.HIDDEN.add(k));
const { default: INDEX } = await import(new URL("help-index.js", JS));
const { SETTINGS_RENDER } = await import(new URL("tabs/settings-pages.js", JS));
const F = await import(new URL("tabs/settings-frame.js", JS));
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const guides = new Set(INDEX.map((g) => g.id));

// ---- the groups, by what a person comes to do
assert.deepEqual(M.SETTINGS_GROUPS.map((g) => g.name), ["This site", "AI & API", "Organisation", "You", "Help & docs"]);
const names = (k) => M.SETTINGS_GROUPS.find((g) => g.key === k).pages.map((p) => p.name);
assert.deepEqual(names("site"), ["Set-up checklist", "Collect data", "Site details", "Leads & integrations", "Internal traffic", "Privacy & retention", "Mail & reports", "AI answers"]);
assert.deepEqual(names("ai"), ["AI assistant (MCP)", "Read figures (API)", "Tokens & links"]);
assert.deepEqual(names("org"), ["Sites", "Team", "Users", "Sign-in rules", "Audit log", "Billing & usage"]);
assert.equal(M.SETTINGS_PAGES[0].route, "settings/home", "All settings first");
assert.deepEqual(S.SETTINGS_MENU.map(([g]) => g), ["", "This site", "AI & API", "Organisation", "You", "Help & docs"]);
assert.equal(S.read().tab === undefined, false);

// ---- every page: drawn, a line, a guide that exists, a docs path, a next page that exists
const routes = new Set(M.SETTINGS_PAGES.map((p) => p.route));
for (const p of M.SETTINGS_PAGES) {
  assert.ok(SETTINGS_RENDER[p.route], `${p.route} has a render`);
  assert.ok(TAB_RENDER[p.route], `${p.route} is a tab`);
  assert.ok(p.line && p.line.length > 20, `${p.route}: a line`);
  assert.ok(guides.has(p.help), `${p.route}: guide ${p.help}`);
  assert.match(M.docsPath(p.route), /^[a-z-]+\/([a-z-]+\/)?$/, p.route);
  if (p.next) assert.ok(routes.has(p.next[0]), `${p.route}: next ${p.next[0]}`);
  for (const [sub, , help] of p.tabs || []) {
    assert.equal(typeof SETTINGS_RENDER[p.route][sub], "function", `${p.route} ${sub}`);
    assert.ok(guides.has(M.helpOf(p.route, sub)), `${p.route} ${sub}: ${help}`);
  }
}
assert.equal(M.docsPath("settings/ai/mcp"), "integrations/mcp/");
assert.equal(M.docsPath("settings/site/collect", "script"), "docs/tracking-script/");
assert.equal(M.subOf("settings/site/mail", "nope"), "mail", "an unknown tab: the first");

// ---- the frame: Help and Docs under the title, the phone's select, Next step
const draw = (route, s = {}) => {
  const root = document.createElement("div");
  root.append(...TAB_RENDER[route]({ site: "example.com", x: { sites: { sites: [{ name: "example.com" }] } } }, { ...S.read(), tab: route, ...s }, {}).flat(9).filter(Boolean));
  return root;
};
// Internal traffic draws its figures (the site's days), so its frame is checked on its own.
const links = F.helpLinks("settings/site/internal");
assert.equal(links.querySelector("a.set-help").getAttribute("href"), "#help?part=internal-traffic");
assert.equal(links.querySelector("a.set-docs").getAttribute("href"), "https://skaldanalytics.com/docs/internal-traffic/");
for (const route of [...routes].filter((r) => r !== "settings/site/internal")) {
  const root = draw(route);
  await tick();
  const help = root.querySelector("a.set-help");
  assert.ok(help, `${route}: Help`);
  assert.equal(help.getAttribute("href"), `#help?part=${M.helpOf(route)}`);
  const docs = root.querySelector("a.set-docs");
  assert.equal(docs.getAttribute("href"), `https://skaldanalytics.com/${M.docsPath(route)}`, route);
  assert.equal(docs.getAttribute("target"), "_blank");
  const host = root.querySelector(".set-docs-w");
  assert.ok(host && host.querySelector(".ua-copy") && host.querySelector(".ua-open"), `${route}: copy and open icons on Docs`);
  const sel = root.querySelector(".set-jump select");
  assert.ok(sel && sel.getAttribute("aria-label") === "Settings page", route);
  assert.equal(root.querySelectorAll("h1").length, 1, `${route}: one title`);
  assert.equal(root.querySelector("h1").textContent, M.pageOf(route).name, `${route}: the menu's name is the title`);
}
// The select lists every page this reader may open, grouped, the page open selected.
const sel = draw("settings/ai/mcp").querySelector(".set-jump select");
assert.deepEqual(sel.querySelectorAll("optgroup").map((g) => g.getAttribute("label")), ["This site", "AI & API", "Organisation", "You", "Help & docs"]);
assert.ok(sel.querySelectorAll("option").some((o) => o.getAttribute("value") === "settings/ai/mcp" && o.getAttribute("selected") !== null));
assert.ok(!sel.querySelectorAll("option").some((o) => o.getAttribute("value") === "settings/org/users"), "hidden with accounts: not listed");
sel.value = "settings/org/team";
sel.dispatchEvent(new (globalThis.Event || class { constructor(t) { this.type = t; } })("change"));
// Next step at the foot.
const next = draw("settings/site/setup").querySelector("nav.set-next a");
assert.equal(next.getAttribute("href"), "#settings/site/collect");

// ---- in-page tabs: each its own address and its own guide
location.hash = "#settings/site/collect";
let root = draw("settings/site/collect", { sub: "script" });
const tabs = root.querySelectorAll(".set-tabs a, .set-tabs [role=tab]");
assert.ok(tabs.length >= 3, "the strip");
const hrefs = tabs.map((t) => t.getAttribute("href")).filter(Boolean);
assert.ok(hrefs.some((x) => x === "#settings/site/collect"), hrefs.join(" "));
assert.ok(hrefs.some((x) => x.startsWith("#settings/site/collect?") && x.includes("sub=script")), hrefs.join(" "));
assert.equal(root.querySelector("a.set-help").getAttribute("href"), "#help?part=tracking-script", "the tab's own guide");
assert.equal(root.querySelector("a.set-docs").getAttribute("href"), "https://skaldanalytics.com/docs/tracking-script/");
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
assert.equal(opens("#settings/api?conn=mcp&step=2")[0], "settings/ai/mcp");
assert.equal(opens("#settings/api?conn=api")[0], "settings/ai/api");
assert.equal(opens("#connections?conn=send")[0], "settings/site/collect");
assert.equal(opens("#settings/api")[0], "settings/site/setup");
assert.equal(opens("#settings")[0], "settings/home", "Settings opens All settings");
assert.equal(opens("#settings/help")[0], "settings/help");
assert.equal(opens("#guides")[0], "help");
console.log("settings-menu: all passed");
process.exit(0);
