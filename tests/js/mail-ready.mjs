// "Get the daily mail" with no mail server (2.42, js/mail-ready.js, tabs/setup-mail.js):
//  - the helper reads both answers' shapes (settings: mail_server; reports: mail_ready) and
//    says nothing when the answer does not say;
//  - no mail server: one card on every step of the dialog, what is missing in plain words,
//    "Who will set it up?" with Me (install admins only) and My developer (a message with no
//    secret in it), the answer kept in the address as by=;
//  - step 3 never says "Waiting for ... to press the link" and offers no test mail; with a
//    mail server it waits as before, with Check again;
//  - not an install admin: no question of one answer, the message at once.
//
//   node tests/js/mail-ready.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const SITE = "www.example.org";
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });

const NO_SERVER = { ready: false, missing: "Set the sender address first (Mail server (SMTP) > Sender address)." };
let server = NO_SERVER;
const SETTINGS = { "mail.to": { value: ["owner@example.com", "new@example.com"], source: "site", editable: true },
  "mail.daily": { value: true, source: "site", editable: true }, "mail.weekly": { value: false, source: "default", editable: true } };
const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "settings") return answer({ ok: true, settings: SETTINGS, mail_waiting: ["new@example.com"], mail_server: server });
  if (path === "settings/save") return answer({ ok: true, saved: Object.keys(body), settings: SETTINGS, mail_waiting: ["new@example.com"], mail_server: server });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", install_admin: true });
const MR = await import(new URL("mail-ready.js", JS));
const { openSetup } = await import(new URL("tabs/setup-dialogs.js", JS));
const { read: readState } = await import(new URL("state.js", JS));

const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
async function close() { dialog().querySelector(".dw-x").click(); await tick(400); }
history.replaceState(null, "", "#overview/summary");

// ---- the helper
assert.equal(MR.mailReady(null), null);
assert.equal(MR.mailReady({ ok: false }), null, "a failed answer says nothing");
assert.equal(MR.mailReady({ ok: true }), null, "an older helper says nothing");
assert.equal(MR.mailReady({ ok: true, mail_server: { ready: true } }), true);
assert.equal(MR.mailReady({ ok: true, mail_server: NO_SERVER }), false);
assert.equal(MR.mailReady({ ok: true, mail_ready: false }), false, "GET settings/reports' shape");
assert.equal(MR.mailMissing({ ok: true, mail_server: { ready: true } }), "");
assert.match(MR.mailMissing({ ok: true, mail_ready: false }), /SMTP server and a sender address/);
assert.equal(MR.mailServerNote({ ok: true, mail_server: { ready: true } }), null, "mail works: no card");
assert.equal(MR.waitingWords({ ok: true }, []), "");
assert.match(MR.waitingWords({ ok: true, mail_server: { ready: true } }, ["a@example.com", "b@example.com"]), /^A link to confirm was mailed to a@example.com and b@example.com\./);
const off = MR.waitingWords({ ok: true, mail_server: NO_SERVER }, ["a@example.com"]);
assert.match(off, /once the mail server is set/);
assert.doesNotMatch(off, /was mailed|Waiting/i, "never says a mail went when none can");
const msg = MR.devMessage("https://app.example.com");
assert.match(msg, /SMTP server and a sender address/);
assert.match(msg, /SKALD_SMTP_HOST/);
assert.doesNotMatch(msg, /password\s*[:=]/i, "names where a secret goes, never a value");

// ---- the dialog, no mail server, an install admin: the card on step 1, Me and My developer
await openSetup("mail", SITE, {});
await tick(40);
let d = dialog();
let card = d.querySelector(".mr-note");
assert.ok(card, "the card is on the first step");
assert.equal(card.querySelector("h3").textContent, "Skald cannot send mail yet");
assert.match(card.textContent, /Set the sender address first/);
assert.equal(card.querySelector(".ui-pill").textContent, "Not set up");
assert.deepEqual(card.querySelectorAll(".ui-who-c").map((b) => b.dataset.who), ["me", "dev"]);
assert.equal(card.querySelector('[aria-checked="true"]').dataset.who, "me");
assert.ok(card.querySelector('a[href="#settings/site/mail?edit=smtp"]'), "Me: the page to fill");
card.querySelectorAll(".ui-who-c").find((b) => b.dataset.who === "dev").click();
await tick(40);
assert.equal(readState().by, "dev", "the answer is in the address");
assert.equal(readState().setup, "mail");
assert.match(card.textContent, /Please set up the mail server of our Skald/);
// Next twice: the card stays, and step 3 neither waits nor offers a test mail.
button(d, "Next").click();
await tick(60);
assert.ok(dialog().querySelector(".mr-note"), "the card on step 2");
button(dialog(), "Next").click();
await tick(80);
d = dialog();
assert.equal(String(readState().step), "3");
assert.ok(d.querySelector(".mr-note"), "the card on step 3");
assert.doesNotMatch(d.textContent, /Waiting for/, "no endless wait");
assert.ok(!button(d, "Check again"), "nothing to check");
assert.ok(!button(d, "Send a test mail"), "no test mail without a server");
assert.match(d.textContent, /new@example.com will get a link to confirm once the mail server is set/);
await close();
assert.equal(readState().by, "", "closing clears the inside keys");

// ---- a reload at step 3 with by=dev: the same card, the developer's message open
history.replaceState(null, "", "#overview/summary?setup=mail&step=3&by=dev");
await openSetup("mail", SITE, { start: 2 });
await tick(60);
d = dialog();
assert.equal(d.querySelector(".mr-note [aria-checked=\"true\"]").dataset.who, "dev");
await close();

// ---- not an install admin: no question with one answer, the message at once
ME.install_admin = false;
history.replaceState(null, "", "#overview/summary");
await openSetup("mail", SITE, {});
await tick(60);
card = dialog().querySelector(".mr-note");
assert.equal(card.querySelectorAll(".ui-who-c").length, 0);
assert.match(card.textContent, /Whoever runs this Skald server sets it/);
assert.match(card.textContent, /Please set up the mail server/);
await close();

// ---- with a mail server: no card, and step 3 waits as before
server = { ready: true, missing: null };
ME.install_admin = true;
await openSetup("mail", SITE, { start: 2 });
await tick(60);
d = dialog();
assert.ok(!d.querySelector(".mr-note"));
assert.match(d.textContent, /A link to confirm was mailed to new@example.com/);
assert.ok(button(d, "Check again"));
await close();

console.log("mail-ready: all passed");
