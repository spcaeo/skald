// Settings › Data › What counts › Not forms (js/tabs/prefs.js, set-parts.js; form_names.py): the
// POST paths a page's own script sends, not forms. The row says how many are suggested; the
// drawer lists each suggestion with its figures and Add, each saved path with Remove, a box to
// type one, and the list that is never a form. Nothing is saved until Save, and Save sends the
// list as it now stands. The request detail names a skipped POST (reqdetail.js).
//
//   node tests/js/not-forms.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
location.hash = "#settings/site/data?sub=counting";
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

const SETTING = { label: "Sent by the site's own pages, not forms", kind: "postpaths", value: ["/hooks/*", "/old/ping"], source: "site", editable: true,
  defaults: ["/api/events", "/ingest/*"],
  suggested: [{ path: "/api/beat", days: 5, visits: 29, of_posting: 29, of_all: 34, day: "2026-10-24" }] };
const ANSWER = { ok: true, role: "owner", site: "example.com", settings: { "site.script_posts": SETTING } };
const posted = [];
globalThis.fetch = async (path, opts) => {
  if (opts?.method === "POST" && String(path).endsWith("settings/save")) {
    const body = JSON.parse(opts.body);
    posted.push(body);
    return { ok: true, status: 200, json: async () => ({ ok: true, settings: { "site.script_posts": { ...SETTING, value: body["site.script_posts"], suggested: [] } } }) };
  }
  return { ok: true, status: 200, json: async () => ANSWER };
};
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com", install_admin: false });
const { sites } = await import(new URL("tabs/prefs.js", JS));
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
const button = (box, words) => box.querySelectorAll("button").filter((b) => b.textContent === words);

const root = document.createElement("div");
document.body.append(root);
root.append(...sites({ site: "example.com" }, "counting", { bare: true }).flat(Infinity).filter(Boolean));
await tick();

// The row: the saved list and how many are suggested.
const part = root.querySelector('[data-part="notforms"]');
assert.ok(part, "the Not forms card is on What counts");
assert.ok(part.textContent.includes("/hooks/*, /old/ping"), part.textContent);
assert.ok(part.textContent.includes("1 suggested"), part.textContent);

// The drawer: the suggestion with its figures and Add; the saved ones with Remove.
part.querySelector("button.set-row").click();
await tick();
const d = dialog();
assert.ok(d, "the drawer opened");
const text = d.textContent;
assert.ok(text.includes("Suggested from your log"));
assert.ok(text.includes("sent by 29 of the 29 visits that sent a POST, of 34 visits, on 2026-10-24; like that on 5 days"), text);
assert.ok(text.includes("If it is a real form, leave it."));
assert.ok(text.includes("Never forms on any site (2)"));
assert.ok(text.includes("A POST answered 204 with no body is never a form either."));
const save = button(d, "Save")[0];
assert.ok(save.disabled, "nothing changed yet: Save waits");

button(d, "Add")[0].click();                                   // the suggestion
await tick();
assert.ok(!dialog().textContent.includes("Suggested from your log"), "added: no longer suggested");
assert.equal(button(dialog(), "Remove").length, 3, "three saved now");
button(dialog(), "Remove")[1].click();                         // /old/ping
await tick();
assert.equal(posted.length, 0, "nothing saved before Save");
const form = dialog().querySelector("form");
assert.equal(button(dialog(), "Save")[0].disabled, false, "a change: Save is on");
form.dispatchEvent(new Event("submit"));
await tick();
assert.deepEqual(posted.pop(), { "site.script_posts": ["/hooks/*", "/api/beat"] });

// The request detail's words for a skipped POST.
const req = readFileSync(new URL("tabs/reqdetail.js", JS), "utf8");
assert.ok(req.includes(`page_script: "sent by the page's own script (not a form)"`));
console.log("not-forms: all passed");
process.exit(0);
