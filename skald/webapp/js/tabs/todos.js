// Overview > Insights (2.35; since #5, #6 the whole tab): only the open problems, worst
// leak first (todos.json, skald/todos.py). Nothing else: no figures on the cards.
//
//   To do this week     the open to-dos; every open leaving page in one card (todo=leave)
//   Fixes that failed   marked done or fixed, and the daily re-check of the log still finds
//                       the problem (todos.json status "failed", even after a live check passed)
//   N fixes being       one small link (show=checking): the fixes still being checked, the ones
//   checked             that worked, and the page changes marked on Traffic › Pages
//   Nothing to fix      one line when nothing is open
//   right now.
//
// Each card: three plain lines (what is wrong, why it matters, Do: what to do; all written in
// js/tabs/todo-words.js), its pill (Needs fixing, Failed, Checking, Passed) and two buttons:
//   Fix this    the one main button: "Who will do it?" (js/tabs/todo-fix.js, todo=<id>&fix=1&
//               by=agent|me|dev): My AI agent, Me (the lines to paste, Mark done), My developer
//   Open        the list behind it, in the address (todo=<id>): the to-do's own table (a failed
//               fix: the addresses still failing), "See it in <tab>", and the smaller actions:
//               Check again (2.44, js/tabs/todo-check.js), Mark done, Not now, Undo
//   the title   its copy icon copies the address of this card (green tick)
// "Not now" folds a to-do away at the bottom until someone puts it back.
//
// The marks are Skald's (js/tabs/todo-marks.js), never this browser's. The figures are
// the data layer's, checked by a second count; one it disagreed with is left out and named.

import { h, n, short, stateNote } from "../ui.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { copyText, TIMING, withCopy, withUrl } from "../urlactions.js";
import { MARKS, loadMarks, markItem, markOf, fixOf } from "./todo-marks.js";
import { agentNote } from "./todo-report.js";
import { checkButton, checkLine, checkAllBar, openAfter } from "./todo-check.js";
import { info } from "./tiles.js";
import { trackedList, merged as trackedChanges } from "./pagechange.js";
import { cardWords } from "./todo-words.js";

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

export function list(t) {
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

/* Where the to-do shows in its own tab: a quiet link, not a button. */
function openLink(t) {
  const go = { tab: t.open.tab, ...Object.fromEntries(Object.entries(t.open).filter(([k]) => !["tab", "name"].includes(k))) };
  return h("a", { class: "td-open", href: S.hashFor({ ...S.read(), ...go, todo: "", dd: "" }), onclick: (e) => { e.preventDefault(); S.set(go); } }, `See it in ${S.nameOf(t.open.tab)}`);
}

/* ---- #5, #6: what the card says ------------------------------------------------------------
   open      to do (not marked)
   failed    marked done or fixed, and the daily re-check of the log still finds the problem,
             even when the one live check passed (todos.py status_of)
   checking  marked, the re-check has no whole day yet (or a mark made since the data update)
   passed    the re-check finds nothing
   notnow    put off: folded at the bottom */
export function statusOf(t, mark) {
  if (!mark) return "open";
  if (mark.state === "notnow") return "notnow";
  const rc = t.recheck && t.marked?.day === mark.day ? t.recheck : null;
  if (!rc) return "checking";
  if (["failed", "passed", "checking"].includes(t.status)) return t.status;
  return { not_yet: "failed", fixed: "passed" }[rc.verdict] || "checking";
}

const PILL = {
  open: () => h("span", { class: "td-tag" }, "Needs fixing"),
  failed: () => h("span", { class: "td-verdict v-not_yet" }, "Failed"),
  checking: () => h("span", { class: "td-verdict v-waiting" }, "Checking"),
  passed: () => h("span", { class: "td-verdict v-fixed" }, "Passed"),
};
const TONE = { failed: "var(--bad)", checking: "var(--ink-3)", passed: "var(--good)" };
export const LEAVE = "leave";            // the card of every open leaving page together (todo=leave)

/* The title, with the copy icon for the link to this card. */
const titleOf = (id, words) => withCopy(h("h3", null, words), linkTo(id), { label: `the link to "${words}"`, cls: "td-title" });

/* A card: one to-do, or every open leaving page (item.list). */
function shownFor(item, s) {
  // A link to a check's answer (tdchk) opens its card too: the answer sits behind Open (#21).
  const on = (key) => Boolean(key) && (key === item.id || item.list.some((t) => t.id === key));
  return on(s.todo) || on(s.tdchk);
}

function card(item, s, redraw) {
  const { id, list: ts, status } = item;
  const t = ts[0];
  const w = cardWords(ts, status);
  const shown = shownFor(item, s);
  const fix = status === "open" || status === "failed";
  return h("article", { class: `td${shown ? " td-on" : ""}${status === "open" ? "" : ` td-${status}`}`, id: `td-${id}`,
    style: { "--tone": status === "open" ? TONES[t.tone] || "var(--ink-3)" : TONE[status] } },
    h("header", { class: "td-head" }, titleOf(id, w.title), PILL[status]()),
    h("p", { class: "td-why" }, w.why),
    h("p", null, h("b", null, "Do: "), w.act),
    ts.length === 1 && markOf(t.id, t.marked)?.withheld ? h("p", { class: "note", role: "note" }, `Shown as done, not fixed: the second count disagreed (${markOf(t.id, t.marked).withheld}).`) : null,
    h("div", { class: "td-acts" },
      fix ? h("button", { type: "button", class: "btn primary td-fix", onclick: () => S.set({ todo: id, fix: "1", by: "", fixby: "", link: "" }) }, "Fix this") : null,
      h("button", { type: "button", class: "btn", "aria-expanded": String(shown), onclick: () => S.set({ todo: shown ? "" : id, tdchk: "", tdhist: "", tdbots: "" }) }, shown ? "Close" : "Open")),
    shown ? openView(item, s, redraw) : null);
}

/* Open: the list behind the card (the to-do's own table), its quiet link to the tab that
   shows it, and the smaller actions: Check again, Mark done, Not now, Undo. */
function openView(item, s, redraw) {
  const { list: ts, status } = item;
  if (ts.length > 1 || (ts[0].kind === "leave" && status === "open")) return pagesList(ts);
  const t = ts[0];
  // A check made the "fixed" mark: no Undo, a new check undoes it (2.44).
  const fixedByCheck = markOf(t.id, t.marked)?.state === "fixed";
  const undo = fixedByCheck ? null : markButton("Undo", t.id, "open", redraw);
  if (status === "failed" && t.recheck?.still) return failedView(t, s, redraw, undo);
  const more = h("div", { class: "td-acts td-more" }, checkButton(t, openAfter(t, redraw)),
    status === "open" ? [markButton("Mark done", t.id, "done", redraw), markButton("Not now", t.id, "notnow", redraw)] : undo,
    openLink(t), historyLink(t, s));
  return h("div", { class: "td-view" }, fresh(t, s, redraw), more, history(t, s, redraw), list(t));
}

/* #23: a check just made (tdchk=<id>) shows its answer at once; the AI assistant's note and
   older checks sit behind History (tdhist=<id>), never in the way. */
const fresh = (t, s, redraw) => (s.tdchk === t.id ? checkLine(t, s, redraw) : null);
const hasHistory = (t) => Boolean(fixOf(t.id) || MARKS.checks?.[t.id]);

function historyLink(t, s) {
  if (!hasHistory(t)) return null;
  const on = s.tdhist === t.id;
  return h("a", { class: "td-open td-hist", href: S.hashFor({ ...S.read(), tdhist: on ? "" : t.id }), "aria-expanded": String(on),
    onclick: (e) => { e.preventDefault(); S.set({ tdhist: on ? "" : t.id }); } }, on ? "Hide history" : "History");
}

function history(t, s, redraw) {
  if (s.tdhist !== t.id || !hasHistory(t)) return null;
  return h("div", { class: "td-history" }, agentNote(fixOf(t.id)), s.tdchk === t.id ? null : checkLine(t, { ...s, tdchk: "" }, redraw));
}

/* A failed fix, opened (#23): the addresses still failing since the fix and, for old pages,
   where to send each; the ones only bots ask for folded into one quiet line (tdbots=<id>);
   Check again, Undo and History. */
function failedView(t, s, redraw, undo) {
  const r = t.recheck;
  const bots = new Set(r.bots_only || []);
  const to = new Map((t.rows || []).map((x) => [x.path, x.target]));
  const lost = t.kind === "lost";
  const rows = (r.still || []).filter(([path]) => !bots.has(path)).map(([path]) => ({ path, target: to.get(path) || "" }));
  const shown = (v) => (v ? withUrl(h("code", null, v), v) : h("span", { class: "muted" }, "no page like it"));
  const cols = [{ key: "path", label: lost ? "Old address" : "Address", path: true, fmt: shown }];
  if (lost) cols.push({ key: "target", label: "Send it to", path: true, fmt: shown, csv: (x) => x.target });
  const since = r.marked_day ? short(r.marked_day) : "";
  const head = t.kind === "errors" ? `Still failing since your fix${since ? ` on ${since}` : ""}`
    : `Still not found since your fix${since ? ` on ${since}` : ""}`;
  const more = (r.still_total ?? 0) - bots.size - rows.length;
  const open = s.tdbots === t.id;
  const quiet = bots.size ? h("p", { class: "note td-bots" },
    `${n(bots.size)} ${bots.size === 1 ? "address only bots ask for stays" : "addresses only bots ask for stay"} "not found". That is right for them. `,
    h("a", { href: S.hashFor({ ...S.read(), tdbots: open ? "" : t.id }), "aria-expanded": String(open),
      onclick: (e) => { e.preventDefault(); S.set({ tdbots: open ? "" : t.id }); } }, open ? "Hide" : "Show"),
    open ? h("span", { class: "td-bots-list" }, " ", ...[...bots].map((p, i) => [i ? ", " : "", withCopy(h("code", null, p), p)])) : null) : null;
  return h("div", { class: "td-view" }, fresh(t, s, redraw),
    h("h3", { class: "td-sub" }, head),
    rows.length ? h("div", { class: "td-list" }, table(cols, { caption: head, rows, ns: `tds${t.kind}`, limit: 25,
      sortKey: null, search: false, tools: false, count: false, empty: "No rows." })) : null,
    more > 0 ? h("p", { class: "note" }, `And ${n(more)} more, asked for less.`) : null,
    quiet,
    h("div", { class: "td-acts td-more" }, checkButton(t, openAfter(t, redraw)), undo, historyLink(t, s)),
    history(t, s, redraw));
}

/* Every open leaving page together: each page, its visits and how many left at once. */
function pagesList(ts) {
  const rows = ts.map((t) => ({ path: t.subject, visits: t.figures?.visits, one_page: t.figures?.one_page, __k: t.id }));
  const cols = [{ key: "path", label: "Page", path: true, fmt: (v) => withUrl(h("code", null, v), v) },
    { key: "visits", label: "Visits started here", num: true }, { key: "one_page", label: "Left after that page", num: true }];
  return h("div", { class: "td-list" }, table(cols, { caption: "Pages visitors leave", rows, file: "leaving-pages.csv", ns: "tdleave", limit: 25, sortKey: null, empty: "No rows." }),
    h("p", { class: "note" }, "Fix this: who will do it, with every page's list. Each page's figures: ", ...ts.map((t, i) => [i ? ", " : "", openLink(t)])));
}

function notNowItem(t, s, redraw) {
  return h("li", { class: "td-later" }, h("span", null, t.title), " ", h("span", { class: "muted" }, t.proof), " ",
    markButton("Put back", t.id, "open", redraw), " ", h("button", { type: "button", class: "btn", onclick: () => S.set({ todo: s.todo === t.id ? "" : t.id }) }, s.todo === t.id ? "Hide the list" : "Show the list"),
    s.todo === t.id ? list(t) : null);
}

const NEW_DAYS = 7;

/* The open to-dos that first qualified in the last NEW_DAYS days of the window (first_seen). */
export function newOnes(todos, w) {
  if (!w?.last) return [];
  const since = new Date(`${w.last}T00:00:00Z`);
  since.setUTCDate(since.getUTCDate() - (NEW_DAYS - 1));
  const from = since.toISOString().slice(0, 10);
  return todos.filter((t) => t.first_seen && t.first_seen >= from);
}

/* The cards, in the file's order (worst leak first): every open leaving page in one card,
   where the first of them ranks. */
export function cardsOf(all, statusOfT) {
  const out = [];
  let group = null;
  for (const t of all) {
    const status = statusOfT(t);
    if (t.kind === "leave" && status === "open") {
      if (!group) { group = { id: LEAVE, list: [], status }; out.push(group); }
      group.list.push(t);
    } else out.push({ id: t.id, list: [t], status });
  }
  return out;
}

/* The to-do section: drawn now from what is known, again once the marks have answered. */
export function todoSection(m, s) {
  const box = h("section", { class: "s td-box", "aria-label": "Insights" });
  const draw = () => box.replaceChildren(...body(m, S.read(), draw));
  box.replaceChildren(...body(m, s, draw));
  if (!MARKS.loaded) loadMarks().then(draw);
  if (s.todo) setTimeout(() => (document.getElementById(`td-${s.todo}`) || box.querySelector("article.td-on"))?.scrollIntoView?.({ block: "nearest" }), 0);
  return box;
}

const ABOUT = "Only what needs fixing on your site now, worst for people first, built only from your server log. "
  + "To do: problems over their threshold in the last whole days. Fixes that failed: you marked them fixed, and the log "
  + "still finds the problem on the whole days since. Open shows the list behind each one; Fix this asks who will do it.";

function body(m, s, redraw) {
  const about = () => info(ABOUT, "Insights");
  const top = (words) => h("div", { class: "td-top" }, h("h2", null, words), about());
  const file = m.x.todos;
  if (!file) return [top("To do this week"), stateNote("The to-do list comes with the next data update: the data layer has not written todos.json yet.")];
  const all = file.todos || [];
  const mark = (t) => markOf(t.id, t.marked);
  const cards = cardsOf(all.filter((t) => mark(t)?.state !== "notnow"), (t) => statusOf(t, mark(t)));
  const pick = (st) => cards.filter((c) => c.status === st);
  const grid = (list) => h("div", { class: "td-grid" }, list.map((c) => card(c, s, redraw)));
  const tracked = trackedChanges(m).length;
  const checking = pick("checking"), passed = pick("passed");
  const out = [];
  if (s.show === "checking") {
    out.push(top("Fixes being checked"));
    const again = checkAllBar(all.filter((t) => mark(t)?.state !== "notnow"), redraw);
    if (again) out.push(again);
    out.push(checking.length ? grid(checking) : tracked ? null : h("p", { class: "empty" }, "No fix is being checked now."));
    if (passed.length) out.push(h("h3", { class: "td-h3" }, "Fixes that worked"), grid(passed));
    out.push(...trackedList(m, s));          // the page changes marked on Traffic › Pages (pagechange.js)
    out.push(h("p", { class: "sub td-back" }, h("a", { class: "td-open", href: S.hashFor({ ...S.read(), show: "", todo: "" }), onclick: (e) => { e.preventDefault(); S.set({ show: "", todo: "" }); } }, "Back to the open problems")));
    return out;
  }
  const open = pick("open"), failed = pick("failed");
  if (open.length) out.push(top("To do this week"), grid(open));
  if (failed.length) out.push(...(open.length ? [h("h3", { class: "td-h3" }, "Fixes that failed")] : [top("Fixes that failed")]), grid(failed));
  if (!open.length && !failed.length) out.push(top("Insights"), h("p", { class: "empty td-none" }, "Nothing to fix right now."));
  if (s.todo && !cards.some((c) => shownFor(c, s)) && !all.some((t) => t.id === s.todo && mark(t)?.state === "notnow")) {
    out.push(stateNote("That to-do is not on the list now: it was fixed, it fell under its threshold, or it is not available to you."));
  }
  for (const x of file.withheld || []) out.push(h("p", { class: "note", role: "note" }, `"${x.title}" is left out: the second count disagreed. `, withCopy(x.why, x.why)));
  const c = checking.length + tracked;
  if (c || passed.length) {
    const words = c ? `${c} ${c === 1 ? "fix" : "fixes"} being checked` : `${passed.length} ${passed.length === 1 ? "fix" : "fixes"} passed`;
    out.push(h("p", { class: "sub td-checking" }, h("a", { class: "td-open", href: S.hashFor({ ...S.read(), show: "checking", todo: "" }),
      onclick: (e) => { e.preventDefault(); S.set({ show: "checking", todo: "" }); } }, words)));
  }
  const later = all.filter((t) => mark(t)?.state === "notnow");
  if (later.length) {
    const fold = h("details", { class: "fold td-fold" }, h("summary", null, `Not now (${later.length})`), h("ul", { class: "td-laters" }, later.map((t) => notNowItem(t, s, redraw))));
    if (later.some((t) => t.id === s.todo)) fold.open = true;
    out.push(fold);
  }
  return out;
}
