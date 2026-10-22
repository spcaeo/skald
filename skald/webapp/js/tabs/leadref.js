// A lead's or a conversion's own reference, its steps and "Mark as test" (2.25): one part,
// the same in every drawer that shows a lead or a conversion (Leads' lead drawer, the
// visitor drawer's "Leads and conversions", Find a person, the Conversions lists, Calendar
// bookings' rows), so they all behave the same.
//
//   refBlock({id, ref, tool, test, steps})   the section: "Reference: u-1001 (from
//                                            shop.example's server)" with a copy icon, every
//                                            step of that reference (stage, what, time), and
//                                            for owners and admins Mark as test / Not a test
//   refLine(ref, tool)                       the line alone
//   refCell(ref, words)                      a grid's or a table's cell: the ID and its copy icon
//   markButton(x)                            the button alone (a list's row), or null
//   afterMark(fn)                            run after every mark (a tab drops its kept answers;
//                                            main.js reads the page's files again)
//
// The reference is the sender's own record ID (an account ID, a booking's address), not a
// name or an email: shown to everyone who can see the lead, as the Conversions lists always
// have; but the page script's own reference is made from the visitor ID, so the helper sends
// that one to owners and admins only (people/policy.py shown_ref). Marking is for owners and admins: POST people/mark-test (people/marktest.py), the
// same mark as the CLI's `conversions mark-test` and the site's signed leads/test, on every
// stage of that (tool, reference), written to the audit log with who did it. A confirm step
// first; then a toast, and the page's lists and counts are read again.

import { h, toast } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { ME } from "../access.js";
import { DEMO } from "../demo.js";
import { siteBase, withCopy } from "../urlactions.js";
import { call } from "./ipmanager.js";
import { toolName, oneAction, STAGE } from "./leadfigs.js";

const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
// In the demo every reader sees the button, as owners and admins do (the demo's server says no).
export const mayMark = () => DEMO.on || ["owner", "admin"].includes(ME.role);
const markable = (x) => Number.isInteger(x?.id) && x.id > 0;
const named = (x) => x.ref || "this conversion";

// Where a reference came from, in words: the site's own server by its name ("shop.example's
// server"), else the tool ("Calendly", "Lead database").
export function fromWords(tool) {
  if (tool === "lead") {
    const site = siteBase().replace(/^https?:\/\//, "");
    return site ? `${site}'s server` : toolName(tool);
  }
  return toolName(tool || "") || "-";
}

/* "u-1001" with its copy icon; "-" without one. words: what the cell shows (a long
   booking address is shortened by its caller), the copy is always the whole reference. */
export function refCell(ref, words = ref) {
  if (ref == null || ref === "") return "-";
  return withCopy(h("span", { class: "mono lr-id", title: String(ref) }, words), ref, { label: `reference ${ref}`, cls: "ua-after" });
}

/* "Reference: u-1001 (from shop.example's server)", the ID with its copy icon. */
export function refLine(ref, tool) {
  return h("p", { class: "lr-line" }, h("span", null, "Reference: "), refCell(ref), h("span", { class: "lr-from" }, ` (from ${fromWords(tool)})`));
}

// ------------------------------------------------------------------ after a mark
const listeners = new Set();
export function afterMark(fn) { listeners.add(fn); return () => listeners.delete(fn); }
function marked(answer) { for (const fn of listeners) { try { fn(answer); } catch { /* one listener never stops the others */ } } }

/* POST people/mark-test: {ok, test, changed, ids} or {ok: false, error}. */
export async function mark(id, on) {
  return call("people/mark-test", { id, test: !!on });
}

/* The question the confirm step asks, in plain words. */
export function question(ref, on) {
  const it = ref || "this conversion";
  return on ? `Mark ${it} as test? It stays listed under Show left out and leaves every count.`
    : `Count ${it} again? It leaves Show left out and is counted in every figure.`;
}

/* Mark as test / Not a test, with its confirm step, for one reference; null for a reader
   who may not mark, or a row with no conversion behind it (a lead database's left-out
   lead, a removed row). x: {id, ref, tool, test}; ref may be null (the page script's).
   onDone(answer) after a mark that worked. */
export function markButton(x, { onDone = null, compact = false } = {}) {
  if (!mayMark() || !markable(x)) return null;
  const slot = h("span", { class: "lr-mark" });
  const draw = () => {
    const on = !x.test;
    const b = h("button", { type: "button", class: `btn${compact ? " sm" : ""}${on ? "" : " primary"}`, "data-mark": on ? "test" : "untest",
      title: on ? "Leave every stage of this reference out of every count; it stays listed" : "Count every stage of this reference again" }, on ? "Mark as test" : "Not a test");
    b.addEventListener("click", (e) => { e.stopPropagation(); ask(on); });
    slot.replaceChildren(b);
  };
  const ask = (on) => {
    const yes = h("button", { type: "button", class: `btn${on ? " danger" : " primary"}`, "data-yes": "1" }, on ? "Mark as test" : "Not a test");
    const no = h("button", { type: "button", class: "btn" }, "Cancel");
    for (const el of [yes, no]) el.addEventListener("pointerdown", (e) => e.stopPropagation());
    slot.replaceChildren(h("span", { class: "confirm lr-confirm", role: "group", "aria-label": "Confirm" }, h("span", null, question(x.ref, on)), yes, no));
    no.focus?.();
    no.addEventListener("click", (e) => { e.stopPropagation(); draw(); });
    yes.addEventListener("click", async (e) => {
      e.stopPropagation();
      yes.disabled = true; no.disabled = true;
      const got = await mark(x.id, on);
      if (!got?.ok) { toast(got?.error || "That did not work. Try again in a minute."); draw(); return; }
      x.test = on;
      const n = got.changed || 0;
      const it = named(x).replace(/^this/, "This");
      toast(on ? `${it} marked as test: ${n} step${n === 1 ? "" : "s"} left out of every count.`
        : `${it} counts again: ${n} step${n === 1 ? "" : "s"} back in the figures.`);
      draw();
      onDone?.(got);
      marked({ ...got, ref: x.ref });
    });
  };
  draw();
  return slot;
}

/* The section: the reference, every step of it (stage, what, when), and the button.
   x: {id, ref, tool, test, steps: [{at, action, stage, tool, test}]}. */
export function refBlock(x, { title = "Reference", onDone = null } = {}) {
  // No reference to show (the page script's, made from the visitor ID, outside an owner's
  // answer): the steps and the button still, for a row that can be marked.
  if (!x?.ref && !(markable(x) && mayMark())) return null;
  const steps = [...(x.steps || [])].sort((a, b) => String(a.at || "").localeCompare(String(b.at || "")));
  const state = h("p", { class: "note lr-state" });
  const say = () => { state.textContent = x.test ? "Marked test: listed under Show left out, never counted." : ""; state.hidden = !x.test; };
  say();
  const list = steps.length
    ? h("ol", { class: "lr-steps" }, steps.map((s) => h("li", null, h("b", null, STAGE[s.stage] || s.stage || "-"), ` ${oneAction(s.action || "").toLowerCase()}, ${at(s.at)}`,
      s.tool && s.tool !== x.tool ? h("small", { class: "v-ft" }, ` reported by ${toolName(s.tool)}`) : null)))
    : h("p", { class: "empty" }, "No step of this reference is kept.");
  const btn = markButton(x, { onDone: (got) => { say(); onDone?.(got); } });
  const line = x.ref ? refLine(x.ref, x.tool) : h("p", { class: "lr-line" }, `Reference: not shown here (the page's script tag makes it from the visitor ID; owners and admins see it in Find a person)`);
  return h("section", { class: "dw-sec lr", "data-ref": String(x.ref || "") }, h("h3", null, title), line,
    h("p", { class: "sub lr-sub" }, `Every step of this reference (${steps.length}), oldest first`), list, state, btn ? h("div", { class: "acts lr-acts" }, btn) : null);
}

/* Conversion rows ({id, external_ref, tool, test, action, stage, at}) as one entry per
   reference: [{id, ref, tool, test, steps}], newest first. Rows without a reference are left
   out (the caller lists them as before). test: every row of it is test. */
export function byRef(rows) {
  const out = new Map();
  for (const r of rows || []) {
    const ref = r.external_ref ?? r.ref;
    if (ref == null || ref === "") continue;
    const k = `${r.tool}\u0001${ref}`;
    const e = out.get(k) || { id: null, ref: String(ref), tool: r.tool, test: true, steps: [] };
    if (Number.isInteger(r.id) && (e.id == null || r.id < e.id)) e.id = r.id;
    e.test = e.test && !!r.test;
    e.steps.push({ at: r.at, action: r.action, stage: r.stage, tool: r.tool, test: !!r.test });
    out.set(k, e);
  }
  const last = (e) => e.steps.reduce((m, s) => (String(s.at || "") > m ? String(s.at || "") : m), "");
  return [...out.values()].sort((a, b) => last(b).localeCompare(last(a)));
}
