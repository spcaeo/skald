// "Check again" (2.44) on Overview › Insights' to-dos. The owner (27 Oct): "I have made
// fixes; there is no way to re-run the check. Can that be built for each case?"
//
//   Check again       on each to-do's card and in Fix this (the drawer): Skald runs that
//                     to-do's own check now (POST settings/todo-check, skald/todo_check.py)
//                     and the answer shows in place: a pill (Fixed, Partly fixed, Not fixed,
//                     Checking, Can't check yet, Could not check) and one line of words
//   the details       the addresses still failing, each with what it answered, and the log
//                     line since the fix; open in the address (tdchk=<id>), so the link opens it
//   Check the next 50 a to-do with more addresses than one check asks continues where it stopped
//   Check all again   above the list: every to-do Skald can ask, one after the other, with its
//                     progress in place (the server's limits apply: one start a minute a to-do,
//                     30 checks an hour a site)
//
// A check that finds every address fixed marks the to-do Fixed (Skald's mark, never a
// person's). Owners and admins press it; a viewer sees the answer, not the button. In the
// demo it reads a sample answer (tools/demo_todocheck.py) and says so.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { pill } from "../ui/pill.js";
import { time } from "../tz.js";
import { withUrl, withCopy } from "../urlactions.js";
import { DEMO } from "../demo.js";
import { MARKS, checkTodo, checkOf } from "./todo-marks.js";

export const LIVE = ["lost", "markdown", "sitemap", "errors"];
export const CAP = 50;
export const VERDICT = {
  fixed: ["good", "Fixed"], partly: ["warn", "Partly fixed"], not_fixed: ["bad", "Not fixed"],
  more: ["info", "Checking"], waiting: ["off", "Can't check yet"], error: ["bad", "Could not check"],
};
export const DEMO_WORDS = "Sample answer: the demo has no server to ask.";

// What this page knows beyond the helper's answer: a refusal per to-do, and the demo's samples.
const SAID = new Map();
const SAMPLES = new Map();
export const forgetChecks = () => { SAID.clear(); SAMPLES.clear(); ALL.text = ""; ALL.running = false; };

/* Owners and admins press it; the demo reads its sample. */
export const canCheck = () => DEMO.on || (MARKS.ok && MARKS.can_mark);

export const resultOf = (id) => SAMPLES.get(id) || checkOf(id);

async function demoCheck(id) {
  const file = DEMO.api.todocheck?.[id];
  if (!file) return { ok: false, error: "In the demo, this to-do has no sample answer." };
  try {
    const got = await (await fetch(file, { cache: "no-store" })).json();
    if (got?.check) { SAMPLES.set(id, { ...got.check, demo: true }); return { ok: true, check: got.check }; }
  } catch { /* said below */ }
  return { ok: false, error: "The demo's sample answer could not be read." };
}

/* Run one check (or the next page of one): {ok, check} or {ok: false, error}. */
export async function runCheck(t, start = 0) {
  const r = DEMO.on ? await demoCheck(t.id) : await checkTodo(t.id, start);
  if (r.ok) SAID.delete(t.id); else SAID.set(t.id, r.error || "Not checked.");
  return r;
}

/* The button. `after` draws the answer (a card: open it in the address). */
export function checkButton(t, after, { words = "Check again", start = 0 } = {}) {
  if (!canCheck()) return null;
  const b = h("button", { type: "button", class: "btn td-chk", "aria-label": `${words}: ${t.title}` }, words);
  b.addEventListener("click", async () => {
    b.disabled = true;
    b.setAttribute("aria-busy", "true");
    b.textContent = "Checking…";
    const r = await runCheck(t, start);
    b.disabled = false;
    b.removeAttribute("aria-busy");
    b.textContent = words;
    after(r);
  });
  return b;
}

/* "Checked at 14:32 by owner@example.com" */
function whenWho(c) {
  const at = c.at ? `Checked ${time(c.at, { label: false, date: true })}` : "Checked";
  return c.demo ? `${at}. ${DEMO_WORDS}` : `${at}${c.by ? ` by ${c.by}` : ""}.`;
}

function badTable(c) {
  const rows = c.bad || [];
  if (!rows.length) return null;
  return h("div", { class: "td-chk-rows" },
    h("table", { class: "td-chk-tbl" }, h("caption", { class: "vh" }, "Addresses not fixed yet"),
      h("thead", null, h("tr", null, h("th", null, "Address"), h("th", null, "What it answers now"))),
      h("tbody", null, rows.map((r) => h("tr", null,
        h("td", null, withUrl(h("code", null, r.path), r.path)),
        h("td", null, r.location ? [withCopy(r.why, r.why), " to ", withUrl(h("code", null, r.location), r.location)] : withCopy(r.why, r.why)))))),
    c.bad_total > rows.length ? h("p", { class: "note" }, `The first ${n(rows.length)} of ${n(c.bad_total)}.`) : null);
}

/* The answer in place: one line, and its details when open (tdchk=<id>). */
export function checkLine(t, s, redraw, { inline = false } = {}) {
  const c = resultOf(t.id);
  const said = SAID.get(t.id);
  if (!c && !said) return null;
  const box = h("div", { class: "td-chk-box", role: "status", "aria-live": "polite", id: `tdchk-${t.id}` });
  if (said) box.append(h("p", { class: "td-chk-said" }, pill("bad", "Not checked"), " ", withCopy(said, said)));
  if (!c) return box;
  const [kind, word] = VERDICT[c.verdict] || ["off", c.verdict];
  const open = inline || s.tdchk === t.id;
  const hasMore = !!(c.bad?.length);
  const toggle = inline || !hasMore ? null : h("a", { href: S.hashFor({ ...S.read(), tdchk: open ? "" : t.id }), class: "td-chk-open",
    "aria-expanded": String(open), onclick: (e) => { e.preventDefault(); S.set({ tdchk: open ? "" : t.id }); } },
  open ? "Hide the addresses" : `Show the ${n(c.bad_total)} not fixed`);
  const nxt = c.next != null && canCheck() && !c.demo ? checkButton(t, () => redraw(), { words: `Check the next ${n(Math.min(CAP, c.total - c.next))}`, start: c.next }) : null;
  box.append(...[h("p", { class: "td-chk-says" }, pill(kind, word), " ", c.words),
    h("p", { class: "td-chk-meta muted" }, whenWho(c), toggle ? " " : null, toggle),
    nxt ? h("div", { class: "td-acts" }, nxt) : null,
    open && hasMore ? badTable(c) : null].filter(Boolean));
  return box;
}

/* Next to an AI agent's report: Skald's own check, when it ran after that report. */
export function checkNote(t, fix) {
  const c = resultOf(t.id);
  if (!c || !fix || (fix.at && c.at < fix.at)) return null;
  const [kind, word] = VERDICT[c.verdict] || ["off", c.verdict];
  return h("p", { class: "td-chk-says fx-chk-note" }, h("b", null, "Skald checked: "), pill(kind, word), " ", c.words);
}

/* After a press on a card: the answer open in the address, and the list drawn again. */
export const openAfter = (t, redraw) => () => {
  if (S.read().tdchk !== t.id) S.set({ tdchk: t.id });
  redraw();
};

/* ---- Check all again -------------------------------------------------------------------- */

const ALL = { running: false, text: "", el: null };

export function checkAllBar(list, redraw) {
  const live = list.filter((t) => LIVE.includes(t.kind));
  if (!canCheck() || !live.length) return null;
  const said = h("span", { class: "td-chkall-said", role: "status", "aria-live": "polite" }, ALL.text);
  ALL.el = said;
  const b = h("button", { type: "button", class: "btn td-chkall", disabled: ALL.running ? true : null }, `Check all again (${live.length})`);
  const say = (text) => { ALL.text = text; if (ALL.el) ALL.el.textContent = text; };
  b.addEventListener("click", async () => {
    ALL.running = true;
    b.disabled = true;
    const tally = { fixed: 0, partly: 0, not_fixed: 0, more: 0, error: 0, skipped: 0 };
    let stopped = "";
    for (const [i, t] of live.entries()) {
      say(`Checking ${i + 1} of ${live.length}: ${t.title}…`);
      const r = await runCheck(t, 0);
      if (!r.ok) {
        tally.skipped += 1;
        if (r.status === 429 && /an hour/.test(r.error || "")) { stopped = ` Stopped: ${r.error}`; break; }
        continue;
      }
      const v = r.check?.verdict;
      tally[v in tally ? v : "error"] += 1;
    }
    const parts = [["fixed", "fixed"], ["partly", "partly fixed"], ["not_fixed", "not fixed"], ["more", "with more to check"],
      ["error", "could not be checked"], ["skipped", "not checked now"]].filter(([k]) => tally[k]).map(([k, w]) => `${tally[k]} ${w}`);
    ALL.running = false;
    say(`Checked again: ${parts.join(", ") || "nothing"}.${stopped}`);
    redraw();
  });
  return h("div", { class: "td-chkall" }, b, " ", said);
}
