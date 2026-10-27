// Settings > Mail (js/tabs/prefs.js), 2.42: with no mail server the page says so at once,
// above the recipients, with "Who will set it up?" (mail-ready.js's card); a saved recipient
// is never told "A confirm link was mailed" when no mail can go. With a mail server, no card,
// and the line says the link was mailed. Drawn from real answers that
// tests/test_mail_confirm.py writes to PREFS_MAIL_DIR: off-get.json, off-save.json (no mail
// server), on-get.json, on-save.json (a mail server).
//
//   PREFS_MAIL_DIR=<folder> node tests/js/prefs-mail.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
location.hash = "#settings/site/mail";
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const DIR = process.env.PREFS_MAIL_DIR;
const read = (name) => JSON.parse(readFileSync(join(DIR, name), "utf8"));
let answers = { get: read("off-get.json"), save: read("off-save.json") };
const posted = [];
globalThis.fetch = async (path, opts) => {
  if (opts?.method === "POST" && String(path).endsWith("settings/save")) {
    posted.push(JSON.parse(opts.body));
    return { ok: true, status: 200, json: async () => answers.save };
  }
  return { ok: true, status: 200, json: async () => answers.get };
};
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", install_admin: true });
const { mail } = await import(new URL("tabs/prefs.js", JS));
const M = { site: "www.example.com" };
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();

async function draw() {
  const root = document.createElement("div");
  document.body.append(root);
  root.append(...mail(M).filter(Boolean));
  await tick();
  return root;
}

// Save the recipients in the Mail card's drawer; the line the drawer says after it.
async function saveRecipients(root, to) {
  root.querySelector('[data-part="mail"] button.set-row').click();
  await tick();
  const d = dialog();
  const box = d.querySelectorAll("textarea").find((t) => t.id === "set-mail-to");
  assert.ok(box, "the recipients box");
  const form = box.closest("form");
  for (const el of form.querySelectorAll("input")) el.value ??= el.getAttribute("value") ?? "";
  for (const el of form.querySelectorAll("select")) el.value ??= el.querySelectorAll("option").find((o) => o.hasAttribute("selected"))?.getAttribute("value") ?? "";
  box.value = to;
  form.dispatchEvent(new Event("input"));
  form.dispatchEvent(new Event("submit"));
  await tick();
  const said = dialog().querySelector("p.msg").textContent;
  dialog().close();
  return said;
}

// 1. No mail server: the card first, above the recipients, with who will set it up.
assert.equal(answers.get.mail_server.ready, false, "the answer says no mail server");
let root = await draw();
const note = root.querySelector("section.mr-note");
assert.ok(note, "the no-mail-server card");
assert.ok(note.textContent.includes("Skald cannot send mail yet"));
assert.ok(note.textContent.includes("No mail server is set, so the daily and weekly mail cannot go."));
assert.ok(note.textContent.includes(answers.get.mail_server.missing), "what is missing, in the server's words");
assert.ok(note.querySelector(".ui-who"), "Who will set it up?");
assert.ok(note.querySelectorAll("a").some((a) => a.getAttribute("href") === "#settings/site/mail?edit=smtp" && a.textContent === "Set the mail server"), "Me: the SMTP drawer");
assert.equal(note.querySelectorAll(".ui-who-c").length, 2, "Me and My developer");
const order = root.querySelectorAll("section.mr-note, [data-part]");
assert.equal(order[0], note, "above the recipients");
assert.equal(order[1].getAttribute("data-part"), "mail");
// Saved: never "mailed", the link waits for the mail server.
let said = await saveRecipients(root, "new@example.com");
assert.deepEqual(posted.pop(), { "mail.to": ["new@example.com"] });
assert.ok(said.includes("new@example.com will get a link to confirm once the mail server is set. Until then no mail can go."), said);
assert.ok(!/mailed/.test(said), said);
root.remove();

// 2. A mail server: no card, and the line says the link was mailed.
answers = { get: read("on-get.json"), save: read("on-save.json") };
assert.equal(answers.get.mail_server.ready, true);
root = await draw();
assert.equal(root.querySelector("section.mr-note"), null, "mail works: no card");
said = await saveRecipients(root, "new@example.com\nother@example.com");   // new@ has not confirmed either
assert.ok(said.includes("A link to confirm was mailed to new@example.com and other@example.com. They get no reports until they press it."), said);
console.log("prefs-mail: all passed");
process.exit(0);
