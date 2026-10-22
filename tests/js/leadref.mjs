// A lead's own reference, its steps and Mark as test (2.25, js/tabs/leadref.js): the line
// with its copy icon and the tool's name, every step, the button for owners and admins only
// (never a viewer or an editor), its confirm step, the POST it sends, the toast, and the same
// part in every drawer that shows a lead or a conversion: Leads' lead drawer, the visitor
// drawer's "Leads and conversions", Find a person, the Conversions lists and Calendar
// bookings' rows.
//
//   node tests/js/leadref.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal ||= function () { this.setAttribute("open", ""); };
Element.prototype.close ||= function () { this.removeAttribute("open"); };
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "sales", name: "Leads & sales", tabs: [{ route: "sales/leads", name: "Leads", keep: ["lact", "llabel", "lnow", "lby", "lshow", "lview"] }] }]);
const { ME } = await import(new URL("access.js", JS));
const U = await import(new URL("urlactions.js", JS));
const R = await import(new URL("tabs/leadref.js", JS));
const L = await import(new URL("tabs/sa-leads.js", JS));
const V = await import(new URL("tabs/visitor.js", JS));
const P = await import(new URL("tabs/person.js", JS));
const B = await import(new URL("tabs/sa-bookings.js", JS));
const LI = await import(new URL("tabs/sa-lists.js", JS));
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const tick = () => new Promise((r) => setTimeout(r, 5));
const copied = [];
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async (t) => { copied.push(t); } } });

// The helper, as the page asks it: POST people/mark-test, and the Conversions lists.
const posts = [];
let answer = { ok: true, test: true, changed: 3, ids: [12, 13, 14] };
const LIST = { ok: true, kind: "test", private: true, rows: [{ id: 21, at: "2026-10-20T10:00:00-04:00", action: "signup", stage: "completed", tool: "lead", external_ref: "u-555", test: 1, journey: [] }] };
globalThis.fetch = async (url, opts = {}) => {
  if (opts.method === "POST") { posts.push({ url, body: JSON.parse(opts.body) }); return { ok: answer.ok, status: answer.ok ? 200 : 403, json: async () => answer }; }
  if (String(url).startsWith("people/conversions")) return { ok: true, status: 200, json: async () => LIST };
  return { ok: false, status: 404, json: async () => ({ ok: false, error: "not here" }) };
};
U.setSiteBase("shop.example");

const LEAD = { id: 12, ref: "u-1001", tool: "lead", test: false,
  steps: [{ at: "2026-10-22T09:00:00-04:00", action: "signup", stage: "completed", tool: "lead" }, { at: "2026-10-22T08:58:00-04:00", action: "signup", stage: "started", tool: "lead" }] };

// ---- the line: the reference, its copy icon, where it came from
{
  const line = R.refLine("u-1001", "lead");
  assert.equal(text(line), "Reference: u-1001 (from shop.example's server)");
  const copy = line.querySelector("button.ua-copy");
  assert.equal(copy.getAttribute("aria-label"), "Copy reference u-1001");
  assert.equal(line.querySelector("a.ua-open"), null, "an ID has nothing to open");
  copy.click();
  await tick();
  assert.deepEqual(copied, ["u-1001"], "the copy writes the whole reference");
  assert.match(text(R.refLine("abc", "calendly")), /\(from Calendly\)$/);
  assert.equal(R.refCell(null), "-");
}

// ---- who sees the button: owners and admins, never a viewer or an editor
{
  for (const role of ["viewer", "editor", null]) {
    ME.role = role;
    assert.equal(R.markButton(LEAD), null, `no button for ${role}`);
    assert.equal(R.refBlock(LEAD).querySelector("[data-mark]"), null, `the block has none for ${role}`);
    assert.match(text(R.refBlock(LEAD)), /Reference: u-1001/, `${role} still sees the reference`);
  }
  for (const role of ["owner", "admin"]) {
    ME.role = role;
    assert.equal(text(R.markButton(LEAD)), "Mark as test", role);
    assert.equal(text(R.markButton({ ...LEAD, test: true })), "Not a test", `${role}: a test lead is unmarked`);
  }
  assert.equal(R.markButton({ ...LEAD, id: "lead-4" }), null, "a lead database's left-out lead has no conversion to mark");
  // The page script's reference holds the visitor ID: not sent to every member, still markable.
  assert.equal(text(R.markButton({ ...LEAD, ref: null })), "Mark as test");
  assert.equal(R.question(null, true), "Mark this conversion as test? It stays listed under Show left out and leaves every count.");
  assert.match(text(R.refBlock({ ...LEAD, ref: null })), /not shown here/);
  ME.role = "viewer";
  assert.equal(R.refBlock({ ...LEAD, ref: null }), null, "a viewer: nothing to show or do");
}

// ---- the block: every step, oldest first; the confirm step; the POST; the toast
{
  ME.role = "admin";
  const heard = [];
  const off = R.afterMark((got) => heard.push(got));
  const x = { ...LEAD, steps: [...LEAD.steps] };
  const block = R.refBlock(x);
  document.body.append(block);
  assert.deepEqual(block.querySelectorAll(".lr-steps li").map((li) => li.querySelector("b").textContent), ["started", "completed"], "oldest first");
  block.querySelector("[data-mark]").click();
  assert.equal(text(block.querySelector(".lr-confirm span")), "Mark u-1001 as test? It stays listed under Show left out and leaves every count.");
  assert.equal(posts.length, 0, "nothing is sent before the yes");
  [...block.querySelectorAll(".lr-confirm button")].find((b) => text(b) === "Cancel").click();
  assert.equal(text(block.querySelector("[data-mark]")), "Mark as test", "Cancel goes back");
  block.querySelector("[data-mark]").click();
  block.querySelector("[data-yes]").click();
  await tick();
  assert.deepEqual(posts.at(-1), { url: "people/mark-test", body: { id: 12, test: true } });
  assert.match(document.getElementById("toast").textContent, /u-1001 marked as test: 3 steps left out of every count/);
  assert.equal(text(block.querySelector("[data-mark]")), "Not a test", "the button turns");
  assert.match(text(block.querySelector(".lr-state")), /Marked test/);
  assert.equal(heard.length, 1, "the page is told: it reads its files again");
  // Unmark works the same way.
  answer = { ok: true, test: false, changed: 3, ids: [12, 13, 14] };
  block.querySelector("[data-mark]").click();
  assert.match(text(block.querySelector(".lr-confirm span")), /^Count u-1001 again\?/);
  block.querySelector("[data-yes]").click();
  await tick();
  assert.deepEqual(posts.at(-1).body, { id: 12, test: false });
  assert.equal(text(block.querySelector("[data-mark]")), "Mark as test");
  // A refusal says why and changes nothing.
  answer = { ok: false, error: "admins only" };
  block.querySelector("[data-mark]").click();
  block.querySelector("[data-yes]").click();
  await tick();
  assert.match(document.getElementById("toast").textContent, /admins only/);
  assert.equal(text(block.querySelector("[data-mark]")), "Mark as test");
  assert.equal(heard.length, 2);
  off();
  block.remove();
  answer = { ok: true, test: true, changed: 1, ids: [21] };
}

// ---- conversion rows as one entry per reference
{
  const got = R.byRef([{ id: 9, external_ref: "a", tool: "lead", action: "signup", stage: "completed", at: "2026-10-02", test: 1 },
    { id: 8, external_ref: "a", tool: "lead", action: "signup", stage: "started", at: "2026-10-01", test: 1 },
    { id: 7, external_ref: "b", tool: "calendly", action: "demo", stage: "completed", at: "2026-10-03", test: 0 },
    { id: 6, external_ref: null, tool: "beacon", action: "contact", stage: "completed", at: "2026-10-04" }]);
  assert.deepEqual(got.map((x) => [x.ref, x.id, x.test, x.steps.length]), [["b", 7, false, 1], ["a", 8, true, 2]]);
}

// ---- every drawer that shows a lead or a conversion renders the part
const drawers = {
  async "Leads: the lead's drawer"() {
    return L.openLead({ id: 12, ref: "u-1001", at: "2026-10-22T09:00:00-04:00", action: "signup", now: "completed", tool: "lead", left_out: null, journey: [], steps: LEAD.steps });
  },
  async "the visitor drawer's Leads and conversions"() {
    return V.leadsAndConversions({ leads: [], conversions: [{ id: 12, external_ref: "u-1001", tool: "lead", action: "signup", stage: "completed", at: "2026-10-22T09:00:00-04:00" }], firstKnown: true });
  },
  async "Find a person"() {
    return { el: { textContent: "", querySelector: () => null }, parts: P.personParts({ query: { kind: "email", value: "x@example.com" }, keys: {}, kept: {}, visits: [], requests: [], leads: [], candidates: [], removed: [], journeys: [],
      conversions: [{ id: 12, external_ref: "u-1001", tool: "lead", action: "signup", stage: "completed", at: "2026-10-22T09:00:00-04:00", test: 0 }] }) };
  },
  async "the Conversions lists drawer"() { return P.openConversionList("test"); },
  async "a Conversions list's row"() { return LI.openConvKey(`test.${(await import(new URL("routekeys.js", JS))).codeOf(["test", LIST.rows[0].at, "signup", "completed", "lead", "u-555"].join("|"))}`); },
  async "Calendar bookings' row"() {
    const rows = [{ id: 31, ref: "inv-1", at: "2026-10-22T09:00:00-04:00", action: "demo", stage: "completed", tool: "calendly", test: false },
      { id: 30, ref: "inv-1", at: "2026-10-22T08:00:00-04:00", action: "demo", stage: "started", tool: "calendly", test: false }];
    return B.openStep(rows[0], rows);
  },
};
const holder = (got) => {
  if (got?.parts) { const box = document.createElement("div"); box.append(...got.parts); return box; }
  return got?.el || got?.body || got;
};
for (const role of ["admin", "owner", "viewer"]) {
  ME.role = role;
  for (const [name, open] of Object.entries(drawers)) {
    const got = await open();
    await tick();
    const el = holder(got);
    assert.ok(el && typeof el.querySelector === "function", `${name}: opened`);
    const lr = el.querySelector(".lr") || el.querySelector(".lr-line") || el.querySelector(".lr-id");
    assert.ok(lr, `${name}: shows the reference (${role})`);
    assert.ok(el.querySelector("button.ua-copy"), `${name}: with its copy icon (${role})`);
    const btn = el.querySelector("[data-mark]");
    if (role === "viewer") assert.equal(btn, null, `${name}: no Mark as test for a viewer`);
    else assert.ok(btn, `${name}: Mark as test for ${role}`);
    got?.close?.();
  }
}
console.log("leadref: all passed");
