// Settings › Organisation › Organisations (js/tabs/orgs.js, org-drawer.js, org-members.js,
// org-words.js, org-line.js): the cards, the search and order in the address, a card's drawer
// (org=<id>) and its tabs (otab=), a link to an organisation not yours, New organisation
// (org=new, an install admin's), Archive asking first, a member's sites, and the
// "Organisation: <name> · Switch" line. Every answer is mocked (tests/test_orgs_api.py and
// tests/test_site_access.py check the server's). Ids only in the address, never an email.
//
//   node tests/js/orgs.mjs
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
  pushState(state, _, hash) { H.stack.splice(H.at + 1); H.stack.push({ state, hash }); H.at += 1; location.hash = hash.slice(hash.indexOf("#")); },
  replaceState(state, _, hash) { H.stack[H.at] = { state, hash }; location.hash = hash.slice(hash.indexOf("#")); },
  back() { if (H.at > 0) { H.at -= 1; location.hash = H.stack[H.at].hash; } },
  go() {},
};

const card = (id, name, more = {}) => ({ id, name, slug: name.toLowerCase().replace(/\W+/g, "-"), sites: [], members: 1, plan: null,
  privacy_class: "internal", state: "active", created_at: "2026-09-01T10:00:00Z", archived_at: null, role: "owner", path: null, ...more });
const CARDS = [
  card(1, "Alpha", { sites: ["alpha.example", "gamma.example"], members: 3, path: "alpha.example/", created_at: "2026-06-01T10:00:00Z" }),
  card(2, "Beta Client", { sites: ["beta.example"], members: 5, privacy_class: "client", role: "admin", path: "beta.example/", created_at: "2026-10-01T10:00:00Z" }),
  card(3, "Old Agency", { sites: ["old.example.net"], state: "archived", archived_at: "2026-10-15T10:00:00Z", role: null }),
];
const MEMBERS = [
  { id: 11, email: "owner@example.com", name: "Sam", role: "owner", sites: null, last_seen: null, totp_on: true, disabled_at: null, me: true },
  { id: 12, email: "admin@example.com", name: "Alex", role: "admin", sites: null, last_seen: null, totp_on: false, disabled_at: null, me: false },
  { id: 13, email: "viewer@example.com", name: "", role: "viewer", sites: ["alpha.example"], last_seen: null, totp_on: null, disabled_at: null, me: false },
];
const MAY = { rename: true, privacy: true, archive: true, members: true, owners: true, sites_access: true, settings_totp: true,
  settings_mail: true, keys: true, audit: true, move: true, add_site: true, leave: true, transfer: true };
const show = (c, more = {}) => ({ org: c, role: c.role, acts: "owner", may: MAY,
  overview: { sites: c.sites.length, members: c.members, requests_7d: null, last_day: null, withheld: null },
  sites: c.sites.map((s) => ({ name: s, path: `${s}/`, state: "active" })), members: MEMBERS,
  invites: [{ email: "new@example.com", role: "viewer", invited_by: 12, expires_at: "2026-11-01T00:00:00Z", sites: ["gamma.example"], expired: false }],
  settings: { require_totp: false, session_days: null, mail_daily: true },
  keys: [{ id: "7", name: "Weekly sheet", scopes: ["read"], sites: null, created_by: "11", last_used: null, revoked_at: null }],
  movable: [], install_keeps: true, ...more });

const posted = [];
let canCreate = true;
let answers = {};
globalThis.fetch = async (path, opts) => {
  const body = opts?.method === "POST" ? JSON.parse(opts.body) : null;
  const ok = (x) => ({ ok: true, status: 200, json: async () => ({ ok: true, ...x }) });
  const no = (status, error) => ({ ok: false, status, json: async () => ({ ok: false, error }) });
  if (body) { posted.push([path, body]); return answers[path] ? ok(answers[path]) : ok({}); }
  if (path === "orgs") return ok({ orgs: CARDS, install_admin: canCreate, current: 1, can_create: canCreate });
  const m = /^orgs\/show\?org=(\d+)$/.exec(path);
  if (m) { const c = CARDS.find((x) => x.id === Number(m[1])); return c ? ok(show(c)) : no(404, "There is no such organisation, or it is not yours."); }
  if (path.startsWith("orgs/auditlog?org=1")) return ok({ entries: [{ id: 1, at: "2026-10-20T10:00:00Z", actor: "11", actor_email: "owner@example.com", action: "member.sites", target: "13", detail: "every site -> alpha.example" }] });
  return no(404, "not here");
};
const tick = (ms = 25) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
const { ME } = await import(new URL("access.js", JS));
const K = await import(new URL("routekeys.js", JS));
const W = await import(new URL("tabs/org-words.js", JS));
const M = await import(new URL("settings-menu.js", JS));

// ---- the words and the pure parts
assert.equal(W.parseKey("3"), 3);
assert.equal(W.parseKey("new"), "new");
for (const bad of ["", "0", "-1", "3x", "owner@example.com", "Alpha"]) assert.equal(W.parseKey(bad), null, bad);
assert.deepEqual(W.filterSort(CARDS, "gamma").map((c) => c.id), [1], "the search reads the sites too");
assert.deepEqual(W.filterSort(CARDS, "", "members:desc").map((c) => c.id), [2, 1, 3], "archived ones last");
assert.deepEqual(W.filterSort(CARDS, "", "created:desc").map((c) => c.id), [2, 1, 3]);
assert.equal(W.sortOf("drop table"), "name:asc");
// The plan is a hosted install's only: never "Plan: Internal" beside a Client pill.
assert.equal(W.cardLine(CARDS[0]), "2 sites · 3 members", "no plan where the install sells none");
assert.equal(W.cardLine(CARDS[1], false), "1 site · 5 members");
assert.equal(W.planWord(CARDS[1]), null);
assert.equal(W.cardLine(CARDS[0], true), "2 sites · 3 members · Plan: none", "hosted, no plan: none");
assert.equal(W.cardLine({ ...CARDS[0], plan: "pro" }, true), "2 sites · 3 members · Plan: Pro");
for (const c of CARDS) assert.ok(!W.cardLine(c).includes("Internal") && !W.cardLine(c, true).includes("Internal"), c.name);
assert.equal(W.accessWords(null, "viewer"), "Every site");
assert.equal(W.accessWords(["a.example"], "owner"), "Every site", "an owner always sees every site");
assert.equal(W.figure(null), "Not recorded", "a figure not kept is never 0");
assert.deepEqual(W.tabsFor({}).map(([k]) => k), ["overview", "sites", "members", "settings"], "a viewer's tabs");
assert.equal(W.tabOf("keys", {}), "overview", "a tab not theirs opens Overview");
assert.ok(W.ARCHIVE.what.includes("Nothing is deleted"));

// ---- the address: registered keys, the menu, the drawer's tab inside it
assert.equal(K.KEYS.get("org").kind, "overlay");
assert.ok(K.INSIDE.includes("otab") && !K.OPENERS.includes("otab"), "otab is inside the drawer");
assert.ok(K.OPENERS.includes("org"));
assert.ok(M.SETTINGS_PAGES.some((p) => p.route === "settings/org/orgs" && p.name === "Organisations"));
assert.equal(M.SETTINGS_GROUPS.find((g) => g.key === "org").pages.at(-1).route, "settings/org/orgs");
assert.ok(S.HIDDEN.has("settings/org/orgs"), "hidden on a server without accounts");

// ---- the page
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", org: "Alpha", install_admin: true });
const O = await import(new URL("overlays.js", JS));
S.on((next) => { O.sync(null, next); });
const { default: orgs } = await import(new URL("tabs/orgs.js", JS));
history.pushState(null, "", "#settings/org/orgs?orgs_q=beta");
const root = document.createElement("div");
document.body.append(root);
root.append(...orgs({}, S.read()));
await tick();
let cards = root.querySelectorAll("button").filter((b) => b.className.includes("org-card"));
assert.equal(cards.length, 1, "the search from the address is applied");
assert.ok(cards[0].textContent.includes("Beta Client") && cards[0].textContent.includes("Client"));
const search = root.querySelectorAll("input").find((i) => i.getAttribute("name") === "orgs_q");
assert.equal(search.value, "beta");
search.value = "";
search.dispatchEvent(new Ev("input"));
cards = root.querySelectorAll("button").filter((b) => b.className.includes("org-card"));
assert.equal(cards.length, 3);
assert.ok(!location.hash.includes("orgs_q"), "an empty search leaves the address");
assert.ok(cards[2].textContent.includes("Archived"), "the archived one is last, and says so");
for (const c of cards) assert.ok(!c.textContent.includes("Plan:"), "no plan on a card where nothing is sold");
const client = cards.find((b) => b.getAttribute("data-org") === "2");
assert.ok(client.textContent.includes("Client") && !client.textContent.includes("Internal"), "the pill says it once");
const order = root.querySelectorAll("select").find((s) => s.getAttribute("name") === "orgs_sort");
order.value = "sites:desc";
order.dispatchEvent(new Ev("change"));
assert.ok(location.hash.includes("orgs_sort=sites%3Adesc") || location.hash.includes("orgs_sort=sites:desc"), location.hash);
assert.ok(root.textContent.includes("New organisation"), "an install admin's one primary button");

const openDialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const button = (d, words) => d.querySelectorAll("button").find((b) => b.textContent === words);

// A card opens its drawer: org=<id>, never its name.
cards = root.querySelectorAll("button").filter((b) => b.className.includes("org-card"));
cards.find((b) => b.getAttribute("data-org") === "1").dispatchEvent(new Ev("click"));
await tick();
let d = openDialog();
assert.ok(d, "the drawer opened");
assert.ok(location.hash.includes("org=1") && !location.hash.includes("Alpha"), location.hash);
assert.ok(d.textContent.includes("Requests, last 7 days") && d.textContent.includes("Not recorded"));
assert.ok(d.textContent.includes("Privacy class") && !d.textContent.includes("Plan"), "no Plan row where nothing is sold");
// A tab writes otab= in place.
const tab = (words) => d.querySelectorAll("a").find((a) => a.getAttribute("role") === "tab" && a.textContent.startsWith(words));
tab("Members").dispatchEvent(new Ev("click"));
await tick();
assert.ok(location.hash.includes("otab=members"), location.hash);
assert.ok(!/@/.test(decodeURIComponent(location.hash)), "no email in the address");
assert.ok(d.textContent.includes("viewer@example.com") && d.textContent.includes("alpha.example"));
// A member's sites: Change, tick, Save posts the member's id and the list.
answers["orgs/member/sites"] = { sites: ["gamma.example"] };
const change = d.querySelectorAll("button").find((b) => b.getAttribute("aria-label") === "Change the sites viewer@example.com sees");
change.dispatchEvent(new Ev("click"));
const ticks = d.querySelectorAll("input").filter((i) => i.getAttribute("name") === "site");
ticks.find((i) => i.getAttribute("value") === "alpha.example").checked = false;
ticks.find((i) => i.getAttribute("value") === "gamma.example").checked = true;
button(d, "Save").dispatchEvent(new Ev("click"));
await tick();
assert.deepEqual(posted.pop(), ["orgs/member/sites", { org: 1, user: 13, sites: ["gamma.example"] }]);
assert.ok(d.textContent.includes("now sees gamma.example"));
// No Change for an owner (every site) or for yourself.
assert.ok(!d.querySelectorAll("button").some((b) => /Change the sites (owner|admin)@/.test(b.getAttribute("aria-label") || "") && /owner@/.test(b.getAttribute("aria-label"))));

// Archive asks first, and says nothing is deleted.
button(d, "Archive").dispatchEvent(new Ev("click"));
assert.equal(posted.length, 0, "nothing posted before the answer");
assert.ok(d.textContent.includes("Nothing is deleted"));
button(d, "Yes, archive").dispatchEvent(new Ev("click"));
await tick();
assert.deepEqual(posted.pop(), ["orgs/archive", { org: 1 }]);

// The Audit tab reads its own rows.
tab("Audit").dispatchEvent(new Ev("click"));
await tick();
assert.ok(location.hash.includes("otab=audit"));
assert.ok(d.textContent.includes("member.sites"));

// ---- a link: org=1&otab=keys opens the drawer on Keys; org=9 is not yours; a bad value
const { openOrgKey } = await import(new URL("tabs/orgs.js", JS));
const got = await openOrgKey("1", null, { tab: "settings/org/orgs", otab: "keys" });
assert.ok(got && got.el, "a drawer");
assert.ok(openDialog().textContent.includes("Weekly sheet"));
assert.equal(await openOrgKey("9", null, { tab: "settings/org/orgs" }), "That organisation is not available to you.");
assert.match(await openOrgKey("Alpha", null, {}), /not one Skald keeps/);
// org=new: an install admin's; anyone else gets one plain line.
const made = await openOrgKey("new", null, { tab: "settings/org/orgs" });
assert.ok(made && made.el && openDialog().textContent.includes("Privacy class"));
answers["orgs/create"] = { org: card(4, "Delta") , link: "https://www.example.com/traffic/invite?t=demo-not-a-token", mailed: false };
const nd = openDialog();
const nameIn = nd.querySelectorAll("input").find((i) => i.getAttribute("name") === "name");
nameIn.value = "Delta";
const other = nd.querySelectorAll("input").find((i) => i.getAttribute("name") === "owner" && i.getAttribute("value") === "other");
nd.querySelectorAll("input").find((i) => i.getAttribute("name") === "owner" && i.getAttribute("value") === "me").checked = false;
other.checked = true;
nd.querySelectorAll("input").find((i) => i.getAttribute("name") === "owner_email").value = "first@example.com";
nd.querySelector("form").dispatchEvent(new Ev("submit"));
await tick();
assert.deepEqual(posted.pop(), ["orgs/create", { name: "Delta", privacy_class: "internal", owner: "first@example.com", sites: [] }]);
assert.ok(nd.textContent.includes("Delta is made") && nd.textContent.includes("pass this link"));
canCreate = false;
const L = await import(new URL("tabs/orgs.js", JS));
await L.loadOrgs();
assert.match(await openOrgKey("new", null, { tab: "settings/org/orgs" }), /Not available to your role/);

// Elsewhere (Add a site's setup=new&org=<id>), org= is left alone: no drawer.
const R = await O.sync(null, { ...S.read(), tab: "settings/org/sites", org: "1" });
assert.equal(R, undefined);

// ---- "Organisation: <name> · Switch": two or more organisations
const LINE = await import(new URL("tabs/org-line.js", JS));
const shown = LINE.lineOf({ orgs: CARDS, current: 1 });
assert.equal(shown.name, "Alpha");
assert.deepEqual(shown.others.map((o) => o.name), ["Beta Client"], "an archived one, or one with no site, is not offered");
assert.equal(LINE.lineOf({ orgs: [CARDS[0]], current: 1 }), null, "one organisation: no line");
LINE.forget();
const line = LINE.orgLine("settings/org/people");
await tick();
assert.ok(!line.hidden && line.textContent.includes("Organisation: Alpha"));

console.log("orgs: all passed");
