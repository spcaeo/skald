// Settings v2: Your account, Audit log and Tokens & links as rows with pills and one primary
// (js/tabs/account.js, auditlog.js, tokens.js, conn-share.js). Each row's form opens in a
// drawer whose part is in the address (edit=<id>, js/tabs/set-edit.js), so a link opens it too.
//
//   node tests/js/set-account.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const ACCOUNT = { ok: true, name: "Ann Example", email: "ann@example.com", totp_on: false,
  sessions: [{ current: true, agent: UA, created_at: "2099-01-01T10:00:00Z", last_seen: "2099-01-02T10:00:00Z" },
    { current: false, agent: UA, created_at: "2099-01-01T09:00:00Z", last_seen: "2099-01-01T09:30:00Z" }] };
const AUDIT = { ok: true, actions: ["setting.change", "token.create"], entries: [
  { at: "2099-01-02T10:00:00Z", actor_email: "ann@example.com", action: "setting.change", target: "privacy.keep_days", detail: "395 -> 200" },
  { at: "2099-01-01T10:00:00Z", actor_email: "ann@example.com", action: "token.create", target: "Weekly sheet", detail: "" }] };
const TOKENS = { ok: true, tokens: [
  { id: "ab12cd34", name: "Sending logs: example.com", scopes: ["ingest"], sites: ["example.com"], created_at: "2099-01-01T10:00:00Z", last_used: "2099-01-02T10:00:00Z" },
  { id: "ef56ab78", name: "Weekly sheet", scopes: ["read"], sites: ["example.com"], created_at: "2099-01-01T10:00:00Z", last_used: null },
  { id: "aa00bb11", name: "Old one", scopes: ["read"], sites: ["example.com"], created_at: "2099-01-01T10:00:00Z", revoked_at: "2099-01-01T11:00:00Z" }] };
const SHARES = { ok: true, shares: [{ ref: "cd34ef56", task: "send", method: "server", site: "example.com", state: "open", expires_at: "2099-01-08T10:00:00Z", views: 0 }] };
const posted = [];
globalThis.fetch = async (path, init = {}) => {
  const p = String(path).split("?")[0];
  if (init.body) posted.push([p, JSON.parse(init.body)]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (/(^|\/)account$/.test(p)) return answer(ACCOUNT);
  if (/settings\/audit$/.test(p)) return answer(AUDIT);
  if (/(^|\/)tokens$/.test(p)) return answer(TOKENS);
  if (/sites\/shares$/.test(p)) return answer(SHARES);
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "ann@example.com" });
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const E = await import(new URL("tabs/set-edit.js", JS));
const m = { site: "example.com", x: { sites: { sites: [{ name: "example.com" }] } } };
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const q = () => new URLSearchParams(location.hash.split("?")[1]);
async function page(route, sub = "") {
  location.hash = `#${route}${sub ? `?sub=${sub}` : ""}`;
  const root = document.createElement("div");
  document.body.append(root);
  root.append(...TAB_RENDER[route](m, { ...S.read(), tab: route, sub }, {}).flat(9).filter(Boolean));
  await tick(60);
  return root;
}

// ---- Your account: one card of rows, the primary only while two-step sign-in is off
let root = await page("settings/you/account");
const rows = root.querySelectorAll(".acct-rows .set-row");
assert.equal(rows.length, 5, "name, email, password, two-step sign-in, where you are signed in");
for (const t of ["Name", "Email", "Password", "Two-step sign-in", "Where you are signed in"]) assert.ok(root.textContent.includes(t), t);
assert.ok(root.textContent.includes("Ann Example") && root.textContent.includes("2 browsers"));
const two = rows.find((r) => r.textContent.includes("Two-step sign-in"));
assert.equal(two.querySelector(".ui-pill.warn").textContent, "Off");
assert.ok(rows.find((r) => r.textContent.includes("Email")).querySelector("button.ua-copy"), "the email has its copy icon");
let prim = root.querySelectorAll(".set-primary");
assert.equal(prim.length, 1, "one primary");
assert.equal(prim[0].textContent, "Turn on two-step sign-in");
assert.equal(root.querySelectorAll("form").length, 0, "no form on the page: each is in its drawer");
// a row opens its form in a drawer, its part in the address
two.click();
await tick(60);
assert.equal(q().get("edit"), "totp", location.hash);
assert.equal(dialog().querySelector(".dw-title").textContent, "Two-step sign-in");
assert.ok(dialog().textContent.includes("Your password, to turn it on"));
dialog().querySelector(".dw-x").click();
await tick(30);
assert.equal(q().get("edit"), null, "closing takes it away");
rows.find((r) => r.textContent.includes("Where you are signed in")).click();
await tick(60);
assert.equal(q().get("edit"), "sessions");
assert.equal(dialog().querySelectorAll(".set-row").length, 2, "one row per browser");
assert.ok(dialog().querySelector(".ui-pill.good").textContent === "This browser");
for (const t of ["Sign out everywhere else", "Sign out of this browser"]) assert.ok(dialog().querySelectorAll("button").some((b) => b.textContent === t), t);
dialog().querySelector(".dw-x").click();
await tick(30);
// a link opens a part on its own; an unknown part says so
await E.openEditKey("password", m, {});
await tick(30);
assert.ok(dialog().textContent.includes("New password again"));
dialog().querySelector(".dw-x").click();
await tick(30);
assert.equal(await E.openEditKey("nosuch", m, {}), "That part is not on this page.");
assert.equal(await E.openEditKey("../x", m, {}), "That part is not on this page.");
// two-step on: no primary, the pill says On
ACCOUNT.totp_on = true;
root = await page("settings/you/account");
assert.equal(root.querySelectorAll(".set-primary").length, 0, "nothing to press when it is on");
assert.equal(root.querySelector(".acct-rows .ui-pill.good").textContent, "On");

// ---- Audit log: one row per change, the action a pill, Download CSV the one primary
root = await page("settings/org/audit");
prim = root.querySelectorAll(".set-primary");
assert.equal(prim.length, 1);
assert.equal(prim[0].textContent, "Download CSV");
const ar = root.querySelectorAll(".aud-rows .set-row");
assert.equal(ar.length, 2);
assert.equal(ar[0].querySelector(".ui-pill.info").textContent, "setting.change");
assert.ok(ar[0].textContent.includes("privacy.keep_days") && ar[0].textContent.includes("395 -> 200"));
assert.ok(ar[0].querySelectorAll("button.ua-copy").length >= 2, "who, what and the detail copy");
assert.ok(root.textContent.includes("2 rows, newest first"));
assert.equal(root.querySelectorAll("table").length, 0, "no table");

// ---- Tokens & links: tokens and links as rows, Revoke on each, New token the one primary
root = await page("settings/ai/assistants", "tokens");
prim = root.querySelectorAll(".set-primary");
assert.equal(prim.length, 1);
assert.equal(prim[0].textContent, "New token");
const tr = root.querySelectorAll(".tok-rows .set-row");
assert.equal(tr.length, 3, "two tokens (the revoked one left out) and one link");
assert.equal(tr[0].querySelector(".ui-pill.good").textContent, "In use");
assert.equal(tr[1].querySelector(".ui-pill.off").textContent, "Never used");
assert.equal(tr[0].querySelector(".cn-purpose").textContent, "Sending logs");
assert.ok(tr[2].textContent.includes("Sending this site's visits (server)") && tr[2].querySelector(".ui-pill.off").textContent === "Not opened");
assert.ok(tr.every((r) => r.querySelector("button.btn.danger").textContent === "Revoke"), "Revoke on each row");
tr[1].querySelector("button.btn.danger").click();
assert.ok(tr[1].textContent.includes("Whatever uses it stops at once."), "Revoke asks first");
prim[0].click();
await tick(60);
assert.equal(q().get("edit"), "token-new", location.hash);
assert.equal(dialog().querySelector(".dw-title").textContent, "New token");
assert.ok(dialog().querySelectorAll("input").some((i) => i.getAttribute("name") === "token-name") && dialog().textContent.includes("What it may do"));
dialog().querySelector(".dw-x").click();
await tick(30);

// ---- a viewer: no tokens drawer from a link
Object.assign(ME, { role: "viewer" });
assert.match(await E.openEditKey("token-new", m, {}), /Tokens are for admins\./);

console.log("set-account: all passed");
