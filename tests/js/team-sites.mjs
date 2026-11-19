// SKALD-42: Settings › Organisation › People (js/tabs/team.js) shows the sites each member sees,
// with Change for an admin (POST team/access, by email as the page's other routes), as the
// Organisations drawer does; and an invite that replaced an open one says its earlier link no
// longer works. Every answer is mocked (tests/test_invites_add_sites.py checks the server's).
//
//   node tests/js/team-sites.mjs
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: "/traffic/alpha.example/" });

const MEMBERS = [
  { email: "admin@example.com", name: "Alex", role: "admin", sites: null, last_seen: null, totp_on: false },
  { email: "owner@example.com", name: "Sam", role: "owner", sites: null, last_seen: null, totp_on: true },
  { email: "viewer@example.com", name: "Vi", role: "viewer", sites: ["alpha.example"], last_seen: null, totp_on: null },
];
const SITES = ["alpha.example", "gamma.example"];
const MAY = { sites: true };
const posted = [];
const gets = {};
const answers = {};
globalThis.fetch = async (path, opts) => {
  const ok = (x) => ({ ok: true, status: 200, json: async () => ({ ok: true, ...x }) });
  if (opts?.method === "POST") { posted.push([path, JSON.parse(opts.body)]); return ok(answers[path] || {}); }
  if (path === "team") gets.team = (gets.team || 0) + 1;
  if (path === "team") return ok({ org: "Alpha", role: "admin", members: MEMBERS, invites: [], sites: SITES, others: [], may_sites: MAY.sites });
  return { ok: false, status: 404, json: async () => ({ ok: false, error: "not here" }) };
};
const tick = (ms = 25) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
const team = (await import(new URL("tabs/team.js", JS))).default;
Object.assign(ME, { user: "admin@example.com", role: "admin", org: "Alpha", mode: "sessions" });

// ---- the words: a reader on some sites only is told "and others", never their names
const W = await import(new URL("tabs/org-words.js", JS));
assert.equal(W.seenWords({ role: "viewer", sites: [], more: true }), "Other sites only");
assert.equal(W.seenWords({ role: "viewer", sites: ["a.example"], more: true }), "a.example, and others");
assert.equal(W.seenWords({ role: "viewer", sites: ["a.example"] }), "a.example");
assert.equal(W.seenWords({ role: "owner", sites: null }), "Every site");

const draw = async () => { const d = document.createElement("div"); d.append(...team().flat().filter(Boolean)); await tick(); return d; };
const buttons = (d) => d.querySelectorAll("button");
const labelled = (d, label) => buttons(d).find((b) => b.getAttribute("aria-label") === label);

// ---- the Sites column
let d = await draw();
const heads = d.querySelectorAll("th").map((t) => t.textContent);
assert.ok(heads.includes("Sites"), `a Sites column: ${heads}`);
const rowOf = (email) => d.querySelectorAll("tr").find((r) => r.textContent.includes(email));
assert.ok(rowOf("viewer@example.com").textContent.includes("alpha.example"));
assert.ok(rowOf("owner@example.com").textContent.includes("Every site"));
assert.ok(rowOf("admin@example.com").textContent.includes("Every site"));

// ---- Change: only for someone else who is not an owner
assert.ok(labelled(d, "Change the sites viewer@example.com sees"));
assert.ok(!labelled(d, "Change the sites owner@example.com sees"), "an owner sees every site");
assert.ok(!labelled(d, "Change the sites admin@example.com sees"), "never your own");
answers["team/access"] = { email: "viewer@example.com", sites: ["alpha.example", "gamma.example"] };
labelled(d, "Change the sites viewer@example.com sees").dispatchEvent(new Ev("click"));
const ticks = d.querySelectorAll("input").filter((i) => i.getAttribute("name") === "site");
ticks.find((i) => i.getAttribute("value") === "gamma.example").checked = true;
buttons(d).find((b) => b.textContent === "Save").dispatchEvent(new Ev("click"));
await tick();
assert.deepEqual(posted.pop(), ["team/access", { email: "viewer@example.com", sites: ["alpha.example", "gamma.example"] }]);
assert.ok(d.textContent.includes("viewer@example.com now sees alpha.example, gamma.example."), d.textContent);
assert.ok(rowOf("viewer@example.com").textContent.includes("gamma.example"));

// ---- a role change draws the team again (an owner's sites go; the Sites cell follows)
const before = gets.team;
const roleSel = d.querySelectorAll("select").find((x) => x.getAttribute("aria-label") === "Role of viewer@example.com");
roleSel.value = "admin"; roleSel.dispatchEvent(new Ev("change"));
await tick();
assert.equal(posted.pop()[0], "team/role");
assert.equal(gets.team, before + 1, "the team is asked again after a role change");
d = await draw();

// ---- nothing ticked is refused on the page
labelled(d, "Change the sites viewer@example.com sees").dispatchEvent(new Ev("click"));
d.querySelectorAll("input").filter((i) => i.getAttribute("name") === "site").forEach((i) => { i.checked = false; });
buttons(d).find((b) => b.textContent === "Save").dispatchEvent(new Ev("click"));
await tick();
assert.equal(posted.length, 0, "nothing posted");
assert.ok(d.textContent.includes("Tick at least one site, or Every site."));

// ---- one site only: nothing to choose, no Change
SITES.splice(1);
d = await draw();
assert.ok(!labelled(d, "Change the sites viewer@example.com sees"), "one site: nothing to change");
SITES.push("gamma.example");

// ---- a viewer reads the column, changes nothing
Object.assign(ME, { role: "viewer", user: "viewer@example.com" });
d = await draw();
assert.ok(d.querySelectorAll("th").some((t) => t.textContent === "Sites"));
assert.ok(!buttons(d).some((b) => /^Change the sites/.test(b.getAttribute("aria-label") || "")));
Object.assign(ME, { role: "admin", user: "admin@example.com" });

// ---- a reader on some sites only: no Change, and other sites are not named, only counted
MAY.sites = false;
MEMBERS.push({ email: "far@example.com", name: "Far", role: "viewer", sites: [], more: true, last_seen: null, totp_on: null },
  { email: "near@example.com", name: "Near", role: "viewer", sites: ["alpha.example"], more: true, last_seen: null, totp_on: null });
d = await draw();
assert.ok(!buttons(d).some((b) => /^Change the sites/.test(b.getAttribute("aria-label") || "")), "may_sites false: no Change");
assert.ok(rowOf("far@example.com").textContent.includes("Other sites only"));
assert.ok(rowOf("near@example.com").textContent.includes("alpha.example, and others"));
MEMBERS.splice(-2);
MAY.sites = true;

// ---- an invite that replaced an open one says so
d = await draw();
answers["team/invite"] = { mailed: true, replaced: true };
const emailBox = () => d.querySelectorAll("input").find((i) => i.getAttribute("name") === "email");
emailBox().value = "new@example.com";
d.querySelectorAll("form")[0].dispatchEvent(new Ev("submit"));
await tick();
assert.deepEqual(posted.pop()[0], "team/invite");
assert.ok(d.textContent.includes("Invite sent to new@example.com. It replaces the invite sent before: that link no longer works."), d.textContent);
answers["team/invite"] = { mailed: true };
emailBox().value = "other@example.com";   // the form was drawn again after the first
d.querySelectorAll("form")[0].dispatchEvent(new Ev("submit"));
await tick();
assert.ok(d.textContent.includes("Invite sent to other@example.com.") && !d.textContent.includes("other@example.com. It replaces"));

console.log("team-sites: ok");
