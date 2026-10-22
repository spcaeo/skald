// Settings > Data retention (js/tabs/prefs.js), 2.15.0: "Keep visitors' IP
// addresses" as a choice of three, each with its line, and the card "Wording for
// your privacy notice" with its note and a Copy button. Drawn from a real GET
// settings answer (tests/test_privacy_notice.py writes it to SETTINGS_JSON); a
// change saves the word, and the answer's notice is drawn again.
//
//   SETTINGS_JSON=answer.json node tests/js/settings-privacy.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
const answer = JSON.parse(readFileSync(process.env.SETTINGS_JSON, "utf8"));
const posted = [];
globalThis.fetch = async (path, opts) => {
  if (opts?.method === "POST") {
    const body = JSON.parse(opts.body);
    posted.push(body);
    const settings = { ...answer.settings, "privacy.keep_ips": { ...answer.settings["privacy.keep_ips"], value: body["privacy.keep_ips"], source: "site" } };
    const notice = { ...answer.notice, items: ["Changed wording."], text: "Changed wording." };
    return { ok: true, status: 200, json: async () => ({ ok: true, saved: Object.keys(body), settings, notice }) };
  }
  return { ok: true, status: 200, json: async () => answer };
};
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const { retention } = await import(new URL("tabs/prefs.js", JS));

const root = document.createElement("div");
root.append(...retention({ site: "example.com" }));
await new Promise((r) => setTimeout(r, 20));
const text = root.textContent;

// The three choices, each with its line, and what switching does.
const set = root.querySelectorAll("fieldset").find((f) => f.id === "set-privacy-keep_ips");
assert.ok(set, "the IP choice is a fieldset");
const radios = set.querySelectorAll("input");
assert.deepEqual(radios.map((i) => i.getAttribute("value")), ["full", "short", "off"]);
assert.deepEqual(radios.map((i) => i.getAttribute("type")), ["radio", "radio", "radio"]);
for (const words of ["Full address", "Shortened (last part removed)", "Don't keep", "203.0.113.57 is kept as 203.0.113.0",
  "From full to shortened, the addresses already kept are shortened at the next nightly run"]) assert.ok(text.includes(words), words);
assert.ok(radios[0].hasAttribute("checked"), "full is the value of a new install");

// The notice card: its title, the note, the server's lines and a Copy button.
const card = root.querySelector("section.notice-card");
assert.ok(card, "the notice card is drawn");
const words = card.textContent;
assert.ok(words.includes("Wording for your privacy notice"));
assert.ok(words.includes("A starting point, not legal advice. Your notice must match your own situation."));
for (const line of answer.notice.items) assert.ok(words.includes(line), line);
assert.ok(card.querySelectorAll("button").some((b) => b.textContent === "Copy"));

// Choose "Shortened" and save: the word is sent, and the new notice is drawn.
radios.forEach((i) => { i.checked = i.getAttribute("value") === "short"; });
const form = set.closest("form");
// dom-lite has no form values: give each field the value a browser would.
for (const el of form.querySelectorAll("input")) el.value ??= el.getAttribute("value") ?? "";
for (const el of form.querySelectorAll("select")) el.value ??= el.querySelectorAll("option").find((o) => o.hasAttribute("selected"))?.getAttribute("value") ?? "";
form.dispatchEvent(new Event("submit"));
await new Promise((r) => setTimeout(r, 20));
assert.deepEqual(posted, [{ "privacy.keep_ips": "short" }]);
assert.ok(root.querySelector("section.notice-card").textContent.includes("Changed wording."));

// 2.29, the Leads card: "Kept for good" or N days, and the days before a sign-up.
const leads = root.querySelectorAll("section").find((s) => s.querySelector("h2")?.textContent === "Leads");
assert.ok(leads, "the Leads card is drawn");
const lt = leads.textContent;
for (const words of ["Leads and the pages they read", "Kept for good", "Skald never deletes them", "days (1 to 3650)",
  "Pages of visitors who have not signed up yet", "Once they sign up, their pages are kept with the lead", "1 to 400"]) assert.ok(lt.includes(words), words);
const keep = leads.querySelectorAll("fieldset").find((f) => f.id === "set-conversions-retention_days");
const picks = keep.querySelectorAll('input[type="radio"]');
assert.deepEqual(picks.map((i) => i.getAttribute("value")), ["forever", "days"]);
assert.ok(picks[1].hasAttribute("checked"), "a new install keeps 400 days");
picks.forEach((i) => { i.checked = i.getAttribute("value") === "forever"; });
const lform = keep.closest("form");
for (const el of lform.querySelectorAll("input")) el.value ??= el.getAttribute("value") ?? "";
lform.dispatchEvent(new Event("submit"));
await new Promise((r) => setTimeout(r, 20));
assert.deepEqual(posted[1], { "conversions.retention_days": 0 }, "kept for good is saved as 0");
console.log("settings-privacy: all passed");
