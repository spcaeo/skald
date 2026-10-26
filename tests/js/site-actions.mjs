// Settings > Add or remove sites, a site's ⋯ menu (js/tabs/site-actions.js and
// site-act-words.js): which actions each role sees, the dialog's words (what happens,
// what stays, how to undo), the dialog in the address (sact=<act>.<site>), and the
// typed name and the tick before a danger action posts. Every answer is mocked
// (tests/test_site_lifecycle.py checks the server's).
//
//   node tests/js/site-actions.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; this.dispatchEvent?.(new Ev("close")); };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: "/traffic/main.example/" });
const H = { stack: [{ state: null, hash: "" }], at: 0 };
globalThis.history = {
  get state() { return H.stack[H.at].state; },
  pushState(state, _, hash) { H.stack.splice(H.at + 1); H.stack.push({ state, hash }); H.at += 1; location.hash = hash; },
  replaceState(state, _, hash) { H.stack[H.at] = { state, hash }; location.hash = hash; },
  back() { if (H.at > 0) { H.at -= 1; location.hash = H.stack[H.at].hash; } },
  go() {},
};

const MAIN = { name: "main.example", source: "config", status: "active", main: true };
const SHOP = { name: "shop.example.com", source: "dashboard", status: "active", main: false, format: "auto" };
const OLD = { name: "old.example.org", source: "config", status: "removed", main: false, removed_at: "2026-10-20T09:00:00Z" };
const posted = [];
let answer = {};
globalThis.fetch = async (path, opts) => {
  const body = opts?.method === "POST" ? JSON.parse(opts.body) : null;
  if (body) posted.push([path, body]);
  const ok = (x) => ({ ok: true, status: 200, json: async () => ({ ok: true, ...x }) });
  if (path === "sites") return ok({ org: "Org", role: "owner", sites: [MAIN, SHOP, OLD], can_add: false, add_refused: "No." });
  if (body) return ok(answer[path] || { site: body.name });
  return { ok: false, status: 404, json: async () => ({ ok: false, error: "not here" }) };
};
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
const { ME } = await import(new URL("access.js", JS));
const W = await import(new URL("tabs/site-act-words.js", JS));
const K = await import(new URL("routekeys.js", JS));

// ---- which actions each role sees
assert.deepEqual(W.menuFor(SHOP, "owner"), ["pause", "remove", "clear", "delete"]);
assert.deepEqual(W.menuFor({ ...SHOP, status: "paused" }, "owner"), ["resume", "remove", "clear", "delete"]);
assert.deepEqual(W.menuFor(SHOP, "admin"), ["pause"], "an admin pauses and resumes only");
assert.deepEqual(W.menuFor(SHOP, "viewer"), []);
assert.deepEqual(W.menuFor(MAIN, "owner"), ["pause"], "the main site is only paused");
assert.deepEqual(W.menuFor(OLD, "owner"), ["restore", "clear", "delete"]);
assert.equal(W.menuFor(SHOP, "owner")[0], "pause", "Pause is the first, recommended option");

// ---- the address: <act>.<site>, a key of the registry
assert.deepEqual(W.parseRoute("delete.shop.example.com"), { act: "delete", site: "shop.example.com" });
assert.equal(W.parseRoute("drop.shop.example.com"), null);
assert.equal(W.parseRoute("pause.nodot"), null);
assert.equal(K.KEYS.get("sact").kind, "overlay");

// ---- every dialog says what happens, what stays or goes, and how to undo
for (const act of W.ACTS) {
  const t = W.words(act, act === "restore" ? OLD : SHOP);
  const heads = t.parts.map(([head]) => head);
  assert.ok(heads.includes("How to undo"), `${act}: how to undo`);
  assert.ok(heads.some((x) => /What (happens|is deleted)/.test(x)), `${act}: what happens`);
  assert.ok(t.button && t.done, act);
}
assert.ok(W.words("delete", SHOP).parts[0][1].includes("tokens"), "Delete all data names the tokens");
assert.ok(W.words("delete", { ...SHOP, source: "config" }).parts[1][1].includes("becomes Removed"));
assert.ok(W.words("clear", SHOP).parts.find(([x]) => x === "Afterwards")[1].includes("Not recorded, never 0"));
assert.ok(W.words("pause", SHOP).parts.find(([x]) => x === "The days while paused")[1].includes("Not recorded, never 0"));
assert.equal(W.stateWords({ status: "paused", paused_at: "2026-10-20T08:00:00Z" }), "Paused since 2026-10-20");
assert.equal(W.stateWords(OLD), "Removed on 2026-10-20");

// ---- the page: the menu, a dialog in the address, the typed name and the tick
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", org: "Org" });
const O = await import(new URL("overlays.js", JS));
S.on((next) => { O.sync(null, next); });
const { default: sitesadmin } = await import(new URL("tabs/sitesadmin.js", JS));
history.pushState(null, "", "#settings/sitesadmin");
const root = document.createElement("div");
document.body.append(root);
root.append(...sitesadmin({}, {}));
await tick();
const text = root.textContent;
assert.ok(text.includes("Removed sites"), "removed sites are listed apart");
assert.ok(text.includes("Removed on 2026-10-20"));
const menus = root.querySelectorAll("button").filter((b) => b.getAttribute("aria-haspopup") === "menu");
assert.equal(menus.length, 3, "a ⋯ menu on every row");
const shopMenu = menus.find((b) => b.getAttribute("aria-label") === "Actions for shop.example.com");
shopMenu.dispatchEvent(new Ev("click"));
const items = shopMenu.parentNode.querySelectorAll("button").filter((b) => b.getAttribute("role") === "menuitem");
assert.deepEqual(items.map((b) => b.textContent), ["Pause", "Remove", "Clear data", "Delete all data"]);
assert.ok(items.slice(1).every((b) => b.className.includes("danger")), "danger actions are red");
assert.ok(!items[0].className.includes("danger"));

const openDialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const button = (d, words) => d.querySelectorAll("button").find((b) => b.textContent === words);

// Pause: no typing; the address names it while it is open.
items[0].dispatchEvent(new Ev("click"));
await tick();
let d = openDialog();
assert.ok(d.textContent.includes("What stays"));
assert.ok(location.hash.includes("sact=pause.shop.example.com"), location.hash);
button(d, "Pause the site").dispatchEvent(new Ev("click"));
await tick();
assert.deepEqual(posted.pop(), ["sites/pause", { name: "shop.example.com" }]);
assert.ok(d.textContent.includes("is paused"));
button(d, "Close").dispatchEvent(new Ev("click"));
await tick();

// Delete all data: the name typed exactly and the box ticked, or nothing is posted.
answer = { "sites/purge": { site: "shop.example.com", status: "deleted", archive: "/var/lib/skald/backups/site-shop.example.com-purge-20261026T100000Z.tar.gz" } };
shopMenu.dispatchEvent(new Ev("click"));
items[3].dispatchEvent(new Ev("click"));
await tick();
d = openDialog();
assert.ok(location.hash.includes("sact=delete.shop.example.com"));
assert.ok(d.textContent.includes("Pause instead"), "Pause is offered before a danger action");
const typed = d.querySelectorAll("input").find((i) => i.getAttribute("name") === "confirm");
const box = d.querySelectorAll("input").find((i) => i.getAttribute("name") === "understood");
const go = button(d, "Delete all data");
assert.ok(go.className.includes("danger"));
typed.value = "shop";
go.dispatchEvent(new Ev("click"));
await tick();
assert.equal(posted.length, 0, "a wrong name posts nothing");
assert.ok(d.textContent.includes("Type shop.example.com exactly"));
typed.value = "shop.example.com";
go.dispatchEvent(new Ev("click"));
await tick();
assert.equal(posted.length, 0, "an unticked box posts nothing");
box.checked = true;
go.dispatchEvent(new Ev("click"));
await tick();
assert.deepEqual(posted.pop(), ["sites/purge", { name: "shop.example.com", confirm: "shop.example.com", understood: true }]);
assert.ok(d.textContent.includes("site-shop.example.com-purge-20261026T100000Z.tar.gz"), "the archive's path is shown");

// A link to an action this role may not take says so in one line.
ME.role = "admin";
const { openSiteActKey } = await import(new URL("tabs/site-actions.js", JS));
assert.match(await openSiteActKey("delete.shop.example.com"), /Not available to your role/);
assert.match(await openSiteActKey("nothing"), /not one this page offers/);

console.log("site-actions: all passed");
