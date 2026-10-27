// Overview > Insights' to-do list (2.35), above the "what changed" cards: what to do
// this week, worst leak first. Each to-do is a problem the site has now (todos.json,
// skald/todos.py), with its proof (a figure and its window), what to do, how
// Skald will know it worked, and the list behind it.
//
//   Fix this        2.41, the one main button: "Who will do it?" (js/tabs/todo-fix.js,
//                   todo=<id>&fix=1&by=agent|me|dev; older links said fixby=): My AI agent (one line; the
//                   agent fetches every row and reports back), Me (the lines to paste and
//                   the CSV), Someone else (Send to team, the link). "Fix all (N)" above
//                   the list asks the same for every open to-do (fix=all)
//   Show the list   the rows, as a table; the address keeps it open (todo=<id>), so
//                   the link and the mail's link open the same to-do with its list
//   the title       its copy icon copies the address of this to-do (green tick)
//   See it in <tab> a quiet link to the tab that shows it, with its filter
//   Mark done       moves it to "Done, and did it work?", re-checked on every whole day
//                   after the mark with the measure that raised it; "Not now" folds it away
//   the agent's     what the person's AI agent reported (todo-report.js): its change,
//   report          the rows it left and why; on a done to-do, beside "Working" / "Not yet"
//
// New to-dos (first_seen in the window's last 7 days) that an agent can fix get one line
// at the top with "Fix them with my AI agent" (2.41).
//
// The marks are Skald's (js/tabs/todo-marks.js), never this browser's. The figures are
// the data layer's, checked by a second count; one it disagreed with is left out and named.

import { h, n, short, stateNote } from "../ui.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { copyText, TIMING, withCopy, withUrl } from "../urlactions.js";
import { MARKS, loadMarks, markItem, markOf, fixOf } from "./todo-marks.js";
import { agentNote } from "./todo-report.js";
import { info } from "./tiles.js";
import { trackedList } from "./pagechange.js";

export const MATCH_WORDS = { exact: "Same page", likely: "Same topic", guess: "Loose", none: "No good match" };
const TONES = { bad: "var(--bad)", warn: "var(--warn)", info: "var(--g-search_engines)" };
const TICK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 8.4 6.5 11.6 12.8 4.6"/></svg>';

/* A to-do's columns as table() and csv() take them: paths get copy and open, words copy. */
export function columnsOf(t) {
  return (t.columns || []).map((c) => {
    if (c.key === "match") return { ...c, type: "badge", fmt: (v) => h("span", { class: `lp-m lp-${v || "none"}` }, MATCH_WORDS[v || "none"]), csv: (r) => MATCH_WORDS[r.match || "none"] };
    if (c.path) return { ...c, fmt: (v) => (v ? v : h("span", { class: "muted td-none" }, "none close")), csv: (r) => r[c.key] ?? "" };
    if (!c.num) return { ...c, fmt: (v) => (v == null || v === "" ? "" : withCopy(String(v), v)) };
    return c;
  });
}

/* The address of one to-do, with its list open: what "Copy link" copies. */
export function linkTo(id) {
  const here = typeof location !== "undefined" ? location.href.split("#")[0] : "";
  return `${here}${S.hashFor({ ...S.read(), tab: "overview/insights", todo: id, tdsend: "" })}`;
}

/* A button that copies, then shows a green tick for TIMING.tick ms. */
export function copyButton(words, text, label) {
  const b = h("button", { type: "button", class: "btn td-copy", "aria-label": label }, words);
  b.addEventListener("click", async () => {
    const ok = await copyText(typeof text === "function" ? text() : text);
    b.classList.toggle("ok", ok);
    b.replaceChildren(...(ok ? [h("span", { class: "td-tick", html: TICK }), " Copied"] : ["Copy failed: select and copy"]));
    setTimeout(() => { b.classList.remove("ok"); b.textContent = words; }, ok ? TIMING.tick : TIMING.failed);
  });
  return b;
}

function rowsNote(t) {
  const total = t.rows_total ?? (t.rows || []).length;
  return total > (t.rows || []).length ? `The list and the CSV have the first ${n(t.rows.length)} of ${n(total)} rows.` : null;
}

function list(t) {
  return h("div", { class: "td-list" },
    table(columnsOf(t), { caption: t.title, rows: t.rows || [], file: t.file, ns: `td${t.kind}`, limit: 25, sortKey: null, empty: "No rows." }),
    rowsNote(t) ? h("p", { class: "note" }, rowsNote(t)) : null);
}

function markButton(words, item, state, redraw) {
  const why = MARKS.ok && MARKS.can_mark ? "" : MARKS.why;
  const b = h("button", { type: "button", class: "btn", disabled: why ? true : null, title: why || null }, words);
  b.addEventListener("click", async () => {
    b.disabled = true;
    const r = await markItem(item, state);
    if (!r.ok) { b.disabled = false; b.title = r.error || "Not saved."; b.textContent = `${words}: not saved`; return; }
    redraw();
  });
  return b;
}

/* 2.41, the owner's one-button rule: "Fix this" asks who will do it (js/tabs/todo-fix.js);
   Download CSV and Send to team moved into it, Copy link is the icon beside the title. */
function acts(t, s, redraw, { done = false } = {}) {
  const shown = s.todo === t.id;
  return h("div", { class: "td-acts" },
    done ? null : h("button", { type: "button", class: "btn primary td-fix", onclick: () => S.set({ todo: t.id, fix: "1", by: "", fixby: "", link: "" }) }, "Fix this"),
    h("button", { type: "button", class: "btn", "aria-expanded": String(shown), onclick: () => S.set({ todo: shown ? "" : t.id }) },
      shown ? "Hide the list" : `Show the list (${n(t.rows_total ?? t.rows.length)})`),
    done ? markButton("Undo", t.id, "open", redraw) : [markButton("Mark done", t.id, "done", redraw), markButton("Not now", t.id, "notnow", redraw)]);
}

/* Where the to-do shows in its own tab: a quiet link, not a button. */
function openLink(t) {
  const go = { tab: t.open.tab, ...Object.fromEntries(Object.entries(t.open).filter(([k]) => !["tab", "name"].includes(k))) };
  return h("a", { class: "td-open", href: S.hashFor({ ...S.read(), ...go, todo: "", dd: "" }), onclick: (e) => { e.preventDefault(); S.set(go); } }, `See it in ${S.nameOf(t.open.tab)}`);
}

/* The title, with the copy icon for the link to this to-do. */
const titleOf = (t) => withCopy(h("h3", null, t.title), linkTo(t.id), { label: `the link to "${t.title}"`, cls: "td-title" });

function card(t, i, s, redraw) {
  const shown = s.todo === t.id;
  return h("article", { class: `td${shown ? " td-on" : ""}`, id: `td-${t.id}`, style: { "--tone": TONES[t.tone] || "var(--ink-3)" } },
    h("header", { class: "td-head" }, h("span", { class: "td-n" }, String(i + 1)), titleOf(t), h("span", { class: "td-tag" }, t.tag)),
    t.subject ? h("p", { class: "td-sub" }, "Page: ", withUrl(h("code", null, t.subject), t.subject)) : null,
    h("p", null, h("b", null, "Proof: "), t.proof, " ", openLink(t)),
    h("p", null, h("b", null, "Do: "), t.todo),
    h("p", { class: "td-check" }, `Skald will check: ${t.check}.`),
    agentNote(fixOf(t.id)),
    acts(t, s, redraw),
    shown ? list(t) : null);
}

function doneItem(t, s, mark, redraw) {
  const shown = s.todo === t.id;
  // The re-check is the last data update's; a mark made since waits for the next one.
  const rc = t.recheck && t.marked?.day === mark.day ? t.recheck : null;
  const verdict = rc ? rc.verdict : "waiting";
  const words = rc ? rc.words : `Marked done ${short(mark.day)}. Skald re-checks it on the next data update, then on every whole day after.`;
  return h("article", { class: `td td-done${shown ? " td-on" : ""}`, id: `td-${t.id}` },
    h("header", { class: "td-head" }, titleOf(t), h("span", { class: `td-verdict v-${verdict}` }, { fixed: "Fixed", not_yet: "Not yet", waiting: "Waiting" }[verdict] || "Waiting")),
    h("p", null, words),
    h("p", { class: "td-check" }, `Measured as: ${t.check}. Marking it done changed no figure; Undo puts it back on the list.`),
    agentNote(fixOf(t.id)),
    acts(t, s, redraw, { done: true }),
    shown ? list(t) : null);
}

function notNowItem(t, s, redraw) {
  return h("li", { class: "td-later" }, h("span", null, t.title), " ", h("span", { class: "muted" }, t.proof), " ",
    markButton("Put back", t.id, "open", redraw), " ", h("button", { type: "button", class: "btn", onclick: () => S.set({ todo: s.todo === t.id ? "" : t.id }) }, s.todo === t.id ? "Hide the list" : "Show the list"),
    s.todo === t.id ? list(t) : null);
}

const AGENT_KINDS = ["lost", "errors", "markdown", "sitemap", "leave"];
const NEW_DAYS = 7;

/* The open to-dos that first qualified in the last NEW_DAYS days of the window (first_seen). */
export function newOnes(todos, w) {
  if (!w?.last) return [];
  const since = new Date(`${w.last}T00:00:00Z`);
  since.setUTCDate(since.getUTCDate() - (NEW_DAYS - 1));
  const from = since.toISOString().slice(0, 10);
  return todos.filter((t) => t.first_seen && t.first_seen >= from);
}

/* The to-do section: drawn now from what is known, again once the marks have answered. */
export function todoSection(m, s) {
  const box = h("section", { class: "s td-box", "aria-label": "To do now" });
  const draw = () => box.replaceChildren(...body(m, S.read(), draw));
  box.replaceChildren(...body(m, s, draw));
  if (!MARKS.loaded) loadMarks().then(draw);
  if (s.todo) setTimeout(() => document.getElementById(`td-${s.todo}`)?.scrollIntoView?.({ block: "nearest" }), 0);
  return box;
}

function body(m, s, redraw) {
  const file = m.x.todos;
  const head = h("div", { class: "td-top" }, h("h2", null, "To do now"),
    info("Problems the site has now, worst leak first, each with its proof and the full list behind it. Built only from what Skald counts, over the last whole days; a to-do shows once its figure passes a threshold. Mark one done and Skald re-checks it, with the same measure, on every whole day after.", "To do now"));
  if (!file) return [head, stateNote("The to-do list comes with the next data update: the data layer has not written todos.json yet.")];
  const w = file.window || {};
  const all = file.todos || [];
  const state = (t) => markOf(t.id, t.marked);
  const open = all.filter((t) => !state(t));
  // 2.41: one "Fix all (N)" for every open to-do an AI agent can fix, and the new ones said.
  const doable = open.filter((t) => t.agent ?? AGENT_KINDS.includes(t.kind));
  if (doable.length > 1) head.append(h("button", { type: "button", class: "btn primary td-fixall", onclick: () => S.set({ fix: "all", todo: "", by: "", fixby: "", link: "" }) }, `Fix all (${doable.length})`));
  const out = [head, h("p", { class: "sub" }, `Each one shows its proof and the full list behind it. Press Fix this: your AI agent, you, or a teammate. Built from ${w.first ? `${short(w.first)} to ${short(w.last)}` : "no whole day yet"}${w.days ? ` (${w.days} whole day${w.days === 1 ? "" : "s"})` : ""}.`)];
  const fresh = newOnes(doable, w);
  if (fresh.length) {
    // One quiet link, not another button (the owner: one main button a to-do).
    const go = fresh.length === 1 ? { todo: fresh[0].id, fix: "1", by: "agent", fixby: "", link: "" } : { fix: "all", todo: "", by: "agent", fixby: "", link: "" };
    const words = fresh.length === 1 ? "Fix it with my AI agent" : fresh.length === doable.length ? "Fix them with my AI agent" : `Fix all ${doable.length} with my AI agent`;
    out.push(h("p", { class: "note td-new", role: "status" },
      h("strong", null, `${fresh.length} new to-do${fresh.length === 1 ? "" : "s"} your AI agent can fix. `),
      "One line for your agent: it fetches every row from Skald, fixes what is missing, and reports back here. ",
      h("a", { class: "td-go", href: S.hashFor({ ...S.read(), ...go }), onclick: (e) => { e.preventDefault(); S.set(go); } }, `${words} →`)));
  }
  if (S.activeFilters(s).length) out.push(h("p", { class: "note" }, "The to-dos cover the whole site: the filters above apply to the cards below, not to these."));
  const done = all.filter((t) => state(t)?.state === "done");
  const later = all.filter((t) => state(t)?.state === "notnow");
  if (s.todo && !all.some((t) => t.id === s.todo)) out.push(stateNote("That to-do is not on the list now: it was fixed, it fell under its threshold, or it is not available to you."));
  out.push(open.length ? h("div", { class: "td-grid" }, open.map((t, i) => card(t, i, s, redraw)))
    : h("p", { class: "empty" }, all.length ? "Nothing left to do now." : "Nothing to do now: no problem passes its threshold in these days."));
  for (const x of file.withheld || []) out.push(h("p", { class: "note", role: "note" }, `"${x.title}" is left out: the second count disagreed. `, withCopy(x.why, x.why)));
  if (MARKS.loaded && MARKS.why) out.push(h("p", { class: "note" }, MARKS.why));
  if (done.length || open.length) {
    out.push(h("h3", { class: "td-h3" }, "Done, and did it work?"),
      h("p", { class: "sub" }, "Each item marked done is re-checked on every whole day after the mark, with the same measure that raised it."),
      done.length ? h("div", { class: "td-grid" }, done.map((t) => doneItem(t, s, state(t), redraw))) : h("p", { class: "empty" }, "Nothing marked done yet."));
  }
  out.push(...trackedList(m, s));          // the page changes marked on Traffic › Pages (pagechange.js)
  if (later.length) {
    const fold = h("details", { class: "fold td-fold" }, h("summary", null, `Not now (${later.length})`), h("ul", { class: "td-laters" }, later.map((t) => notNowItem(t, s, redraw))));
    if (later.some((t) => t.id === s.todo)) fold.open = true;
    out.push(fold);
  }
  return out;
}
