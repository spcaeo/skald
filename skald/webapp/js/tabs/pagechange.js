// "Did my change work?" (Traffic › Pages › a page, and Overview › Insights' "Done, and did
// it work?"). Someone marks "I changed this page on <day>" with what changed and a short
// note; Skald then puts the same number of whole days before and after it side by side:
// visits that started on the page, leads and conversions that landed on it, visits from
// search engines and from AI assistants, AI reads (live fetches) and the share that left at
// once, with the change and a verdict, "too early to tell" until 14 whole days have passed.
//
//   the figures   page_changes.json (skald/page_changes.py), checked by a second
//                 count (audit_page_changes.py); a change it disagreed with is left out, named
//   the marks     Skald's own (accounts.sqlite, the helper's settings/todos: todo-marks.js),
//                 never this browser's: a mark shows at once, its figures on the next update
//   the address   pchg=<id>: the change open (an opaque id: c and 8 hex); pcm=new: the Mark a
//                 change dialog, with pcd (its day) and pck (what changed) inside it; the note
//                 typed never goes in the address
//   the chart     the page's days around the change; the change is a marker on every chart
//                 (markers.json's page_change)
//   the hint      the website's or the sitemap's change date (page_index.json, page_trends.json)
//                 suggests "this page changed on 21 Oct: track it?"

import { h, n, short, long, addDays, dayDiff } from "../ui.js";
import * as S from "../state.js";
import { lines, legend } from "../charts.js";
import { table } from "../table.js";
import { openDrawer } from "../drawer.js";
import { opened, stepped } from "../overlays.js";
import { withCopy, withUrl } from "../urlactions.js";
import { call } from "./ipmanager.js";
import { MARKS, loadMarks } from "./todo-marks.js";
import { copyButton } from "./todos.js";

export const KINDS = [["content", "Content update"], ["title", "New title"], ["backlink", "New backlink"], ["redirect", "Redirect"], ["other", "Other"]];
export const kindWords = (k) => (KINDS.find(([x]) => x === k) || [null, "Changed"])[1];
export const VERDICTS = { up: "Up", down: "Down", no_clear_change: "No clear change", too_early: "Too early to tell", not_recorded: "Not recorded",
  not_enough_days: "Not enough days", too_few: "Too few to tell" };
const LABELS = { visits: "Visits that started here", leads: "Leads and conversions that landed here", search: "Visits from search engines",
  ai: "Visits from AI assistants", reads: "AI reads (live fetches)", left: "Left at once" };
const COLORS = { visits: "var(--g-people)", search: "var(--g-search_engines)", ai: "var(--g-answer_engines)", reads: "var(--ink-3)", leads: "var(--leads)" };
const DAY_RE = /^\d{4}-\d\d-\d\d$/;
const pageKey = (p) => { const x = String(p || "").split(/[?#]/)[0]; return x.endsWith("/") ? x : `${x}/`; };

// ------------------------------------------------------------------ what is tracked
/* The changes: the file's figures, for the marks Skald holds now. A mark made since the last
   data update has no figures yet ({pending: true}); one stopped since is left out. */
export function merged(m) {
  const file = m?.x?.page_changes;
  const counted = new Map((file?.changes || []).map((c) => [c.id, c]));
  if (!MARKS.ok) return [...counted.values()];
  return (MARKS.changes || []).map((c) => (counted.has(c.id) ? { ...counted.get(c.id), kind: c.kind, note: c.note } : { ...c, pending: true }));
}
export const changesOf = (m, path) => merged(m).filter((c) => pageKey(c.path) === pageKey(path));

/* The website's or the sitemap's change date for the page, when no tracked change has that day. */
export function suggestion(m, path, tracked) {
  const k = pageKey(path);
  const fromIndex = (m?.x?.page_index?.pages || []).find((p) => pageKey(p.path) === k && p.updated);
  const fromTrends = (m?.x?.page_trends?.changed?.pages || []).find((p) => pageKey(p.path) === k && p.changed);
  const day = fromIndex?.updated || fromTrends?.changed;
  const source = fromIndex ? fromIndex.updated_source : fromTrends?.source;
  if (!day || !DAY_RE.test(day) || day > m.today || tracked.some((c) => c.day === day)) return null;
  return { day, source: source === "sitemap" ? "sitemap" : "website" };
}

// ------------------------------------------------------------------ words for a figure
const per = (x) => (x == null ? "" : x >= 10 ? n(x) : x.toFixed(1).replace(/\.0$/, ""));
export function sideWords(f, side) {
  const s = f[side];
  if (!s || !s.days) return "not recorded";
  if (f.key === "left") return s.share == null ? "no visit" : `${(s.share * 100).toFixed(1)}%${s.at_least ? "+" : ""}`;
  return `${per(s.per_day)}${s.at_least ? "+" : ""}`;
}
export function sideDetail(f, side) {
  const s = f[side];
  if (!s || !s.days) return "";
  if (f.key === "left") return `${n(s.one_page)} of ${n(s.visits)} visits, ${n(s.days)} day${s.days === 1 ? "" : "s"}`;
  return `${n(s.total)} in ${n(s.days)} day${s.days === 1 ? "" : "s"}`;
}
export function changeWords(f) {
  const c = f.change;
  if (!c) return "";
  if (f.key === "left") return c.points === 0 ? "same" : `${c.points > 0 ? "+" : "−"}${Math.abs(c.points).toFixed(1)} points`;
  if (c.pct == null) return c.per_day > 0 ? "new" : "same";
  return c.pct === 0 ? "same" : `${c.pct > 0 ? "+" : "−"}${Math.abs(c.pct)}%`;
}
/* better, worse or neutral: up is better for counts, down for "left at once". */
export const tone = (f) => (f.verdict === "up" || f.verdict === "down" ? ((f.verdict === "up") === (f.better === "up") ? "better" : "worse") : "neutral");

export function statusWords(c) {
  if (c.pending) return `Marked. Skald counts it on the next data update, then on every whole day after ${short(c.day)}.`;
  if (c.status === "waiting") return `Counting starts with the first whole day after the change, ${short(addDays(c.day, 1))}.`;
  if (c.status === "too_early") return `Too early to tell: ${c.days_after} of ${c.min_days || 14} whole days so far. The verdict comes on ${short(c.verdict_on)}.`;
  const b = c.before, a = c.after;
  return `${n(a.days)} whole day${a.days === 1 ? "" : "s"} after the change (${short(a.first)} to ${short(a.last)}) against the ${n(b.days)} before it (${short(b.first)} to ${short(b.last)})${c.complete ? "" : `; it grows to ${c.max_days || 28} days on each side`}.`;
}
/* Coverage: the days a side has with each figure, said when the two sides differ. */
export function coverageNotes(c) {
  const out = [];
  const odd = (c.figures || []).filter((f) => f.unequal && f.before.days && f.after.days);
  if (odd.length) out.push(`Compared per day: ${odd.map((f) => `${LABELS[f.key].toLowerCase()} on ${f.before.days} days before, ${f.after.days} after`).join("; ")}. A day not whole or not recorded is in neither.`);
  if ((c.figures || []).some((f) => f.before?.at_least || f.after?.at_least)) out.push("+ is a floor: on some days the page was not among the 200 landing pages a day keeps.");
  if (c.leads_why) out.push(`Leads: not recorded (${c.leads_why}).`);
  return out;
}

// ------------------------------------------------------------------ the address
export function linkTo(c) {
  const here = typeof location !== "undefined" ? location.href.split("#")[0] : "";
  return `${here}${S.hashFor({ ...S.read(), tab: "traffic/pages", page: c.path, pchg: c.id, pcm: "", pcd: "", pck: "", dd: "" })}`;
}
const goTo = (c) => S.set({ tab: "traffic/pages", page: c.path, pchg: c.id });

// ------------------------------------------------------------------ one change
function figureTable(c) {
  return h("div", { class: "pc-tbl", role: "table", "aria-label": `Before and after the change on ${short(c.day)}` },
    h("div", { class: "pc-tr pc-th", role: "row" }, ["Measure", "Before (a day)", "After (a day)", "Change", "What it says"].map((x) => h("span", { role: "columnheader" }, x))),
    (c.figures || []).map((f) => h("div", { class: `pc-tr pc-${tone(f)}`, role: "row" },
      h("span", { role: "cell", class: "pc-m" }, LABELS[f.key] || f.key),
      h("span", { role: "cell", class: "num" }, sideWords(f, "before"), h("small", null, sideDetail(f, "before"))),
      h("span", { role: "cell", class: "num" }, sideWords(f, "after"), h("small", null, sideDetail(f, "after"))),
      h("span", { role: "cell", class: "num" }, changeWords(f)),
      h("span", { role: "cell" }, h("span", { class: `pc-v v-${f.verdict}` }, VERDICTS[f.verdict] || f.verdict)))));
}

function chart(c) {
  const days = c.days || [];
  const series = ["visits", "search", "ai", "reads", "leads"].filter((k) => days.some((d) => d.state === "ok" && d[k])).map((k) => ({ name: LABELS[k], color: COLORS[k], get: (d) => d[k] }));
  if (!series.length || days.filter((d) => d.state === "ok").length < 2) return null;
  return h("div", { class: "sheet pc-chart" }, legend(series.map((x) => [x.name, x.color]), true),
    lines(days, series, { label: `${c.path}, ${days.length} days around the change on ${short(c.day)}`, H: 190 }));
}

function card(m, c, s, redraw) {
  const on = s.pchg === c.id;
  const can = MARKS.ok && MARKS.can_mark;
  const stop = h("button", { type: "button", class: "btn", disabled: can ? null : true, title: can ? null : MARKS.why || null }, "Stop tracking");
  stop.addEventListener("click", async () => {
    stop.disabled = true;
    const r = await stopChange(c);
    if (!r.ok) { stop.disabled = false; stop.textContent = "Stop tracking: not saved"; stop.title = r.error || ""; return; }
    redraw();
  });
  return h("article", { class: `pc-card${on ? " pc-on" : ""}`, id: `pc-${c.id}` },
    h("header", { class: "pc-head" }, h("h3", null, `Changed ${short(c.day)}: ${kindWords(c.kind)}`),
      h("span", { class: `pc-st st-${c.pending ? "pending" : c.status}` }, c.pending ? "Waiting for the next update" : { ready: "Compared", too_early: "Too early to tell", waiting: "Counting starts tomorrow" }[c.status] || c.status)),
    c.note ? h("p", { class: "pc-note" }, withCopy(h("span", null, c.note), c.note, { label: "the note" })) : null,
    h("p", { class: "sub" }, statusWords({ ...c, min_days: m.x.page_changes?.min_days, max_days: m.x.page_changes?.max_days })),
    c.pending ? null : [chart(c), figureTable(c), coverageNotes(c).map((x) => h("p", { class: "note" }, x))],
    h("div", { class: "td-acts" }, copyButton("Copy link", () => linkTo(c), `Copy the link to the change on ${short(c.day)}`), stop));
}

/* The page's tracker: drawn now from what is known, again once the marks have answered. */
export function changeTracker(m, s) {
  const box = h("section", { class: "s pc-box", "aria-label": "Did my change work?" });
  const draw = () => { if (box.isConnected || !box.childNodes.length) box.replaceChildren(...body(m, S.read(), draw)); };
  box.replaceChildren(...body(m, s, draw));
  if (!MARKS.loaded) loadMarks().then(draw);
  if (s.pchg) setTimeout(() => document.getElementById(`pc-${s.pchg}`)?.scrollIntoView?.({ block: "nearest" }), 0);
  return box;
}

function markButton(words, patch) {
  const can = MARKS.ok && MARKS.can_mark;
  return h("button", { type: "button", class: "btn primary", "aria-haspopup": "dialog", disabled: MARKS.loaded && !can ? true : null, title: MARKS.loaded && !can ? MARKS.why : null,
    onclick: () => S.set({ pcm: "new", pcd: patch.pcd || "", pck: patch.pck || "" }, { mark: { ov: "pcm" } }) }, words);
}

function body(m, s, redraw) {
  const file = m.x.page_changes;
  const path = s.page;
  const head = h("div", { class: "pc-top" }, h("div", null, h("h2", null, "Did my change work?"),
    h("p", { class: "sub" }, "Mark the day you changed this page. Skald puts the same number of whole days before and after it side by side, and says when it is too early to tell.")),
  markButton("+ Mark a change", {}));
  if (file?.whole_site_only) return [head, h("p", { class: "note" }, "Tracked changes are the whole site's: open All pages to see them.")];
  const list = changesOf(m, path).sort((a, b) => (a.day < b.day ? 1 : -1));
  const out = [head];
  const hint = suggestion(m, path, list);
  if (hint) out.push(h("p", { class: "pc-hint" }, `${hint.source === "sitemap" ? "Your sitemap says" : "The website says"} this page changed on ${long(hint.day)}. `,
    h("button", { type: "button", class: "linkish", onclick: () => S.set({ pcm: "new", pcd: hint.day, pck: "content" }, { mark: { ov: "pcm" } }) }, "Track that change?")));
  if (s.pchg && !list.some((c) => c.id === s.pchg)) out.push(h("p", { class: "note", role: "status" }, "That change is not tracked now: it was stopped, or it is on another page."));
  for (const x of (file?.withheld || []).filter((w) => pageKey(w.path) === pageKey(path))) out.push(h("p", { class: "note", role: "note" }, `The change on ${short(x.day)} is left out: the second count disagreed. `, withCopy(x.why.join ? x.why.join("; ") : String(x.why), x.why.join ? x.why.join("; ") : String(x.why))));
  if (!file && !list.length) out.push(h("p", { class: "empty" }, "The figures come with the next data update: the data layer has not written page_changes.json yet."));
  else if (!list.length) out.push(h("p", { class: "empty" }, "No change marked on this page yet."));
  else out.push(h("div", { class: "pc-list" }, list.map((c) => card(m, c, s, redraw))));
  if (MARKS.loaded && MARKS.why) out.push(h("p", { class: "note" }, MARKS.why));
  else if (file && file.marks === false && !MARKS.ok) out.push(h("p", { class: "note" }, "Marking needs accounts (signing in): this Skald runs without them."));
  return out;
}

// ------------------------------------------------------------------ the marks
export async function markChange(path, day, kind, note) {
  const r = await call("settings/todos", { item: `page:${path}`, state: "changed", day, kind, note });
  if (r.ok && r.changes) MARKS.changes = r.changes;
  return r;
}
export async function stopChange(c) {
  const r = await call("settings/todos", { item: `page:${c.path}`, state: "open", day: c.day });
  if (r.ok && r.changes) MARKS.changes = r.changes;
  return r;
}

// ------------------------------------------------------------------ the dialog
/* The address named the Mark a change dialog (pcm=new): the dialog, or the plain line why not. */
export async function openMarkKey(v, m, s) {
  if (v !== "new") return "That dialog is not in this version of the page.";
  if (!s.page || s.tab !== "traffic/pages") return "Open a page in Traffic › Pages first, then mark its change.";
  await loadMarks();
  if (!MARKS.ok || !MARKS.can_mark) return `Mark a change is not offered here: ${MARKS.why || "only an owner or an admin can mark one."}`;
  return markDialog(m, s);
}

export function markDialog(m, s) {
  const today = m.today;
  const day = DAY_RE.test(s.pcd || "") && s.pcd <= today ? s.pcd : today;
  let kind = KINDS.some(([k]) => k === s.pck) ? s.pck : "content";
  const date = h("input", { type: "date", value: day, max: today, min: addDays(today, -365), "aria-label": "When it changed" });
  const note = h("input", { type: "text", maxlength: "200", placeholder: "e.g. added a pricing table", "aria-label": "Note (optional)" });
  const chips = h("div", { class: "r2-chips", role: "radiogroup", "aria-label": "What changed" });
  const drawChips = () => chips.replaceChildren(...KINDS.map(([k, w]) => h("button", { type: "button", role: "radio", class: `r2-chip${k === kind ? " on" : ""}`, "aria-checked": String(k === kind),
    onclick: () => { kind = k; drawChips(); stepped("pcm", "new", { pck: k }); } }, w)));
  drawChips();
  date.addEventListener("change", () => stepped("pcm", "new", { pcd: date.value }));
  const said = h("p", { class: "td-said", role: "status", "aria-live": "polite" });
  const save = h("button", { type: "button", class: "btn primary" }, "Save change");
  const cancel = h("button", { type: "button", class: "btn" }, "Cancel");
  const ago = dayDiff(date.value || day, today);
  const body = h("div", { class: "pc-form" },
    h("div", { class: "td-field" }, h("span", null, "Page"), withUrl(h("code", null, s.page), s.page)),
    h("div", { class: "td-field" }, h("span", null, "What changed"), chips),
    h("label", { class: "td-field" }, h("span", null, "When"), date),
    h("label", { class: "td-field" }, h("span", null, "Note (optional, up to 200 characters)"), note),
    h("p", { class: "note" }, `Skald compares the same number of whole days before and after that day, up to 28, and says "too early to tell" until 14 have passed${ago >= 15 ? "; this one can be told at once" : ""}. Everyone on the team sees it; it stays until someone stops tracking it.`),
    said);
  const d = openDrawer({ title: "Mark a change", subtitle: s.page, size: "md", key: "page-change", scope: "page", body, footer: [cancel, save], focus: date,
    route: { key: "pcm", value: "new" } });
  cancel.addEventListener("click", () => d.close());
  save.addEventListener("click", async () => {
    if (!DAY_RE.test(date.value) || date.value > today) { said.textContent = "Pick the day it changed: today or before."; return; }
    save.disabled = true;
    said.textContent = "Saving…";
    const r = await markChange(s.page, date.value, kind, note.value);
    save.disabled = false;
    if (!r.ok) { said.replaceChildren(withCopy(r.error || "Not saved.", r.error || "Not saved.")); said.classList.add("bad"); return; }
    d.close();
    S.set({ pchg: r.id, pcm: "", pcd: "", pck: "" }, { replace: true });
  });
  return d;
}

// ------------------------------------------------------------------ Insights' list
/* Every tracked change, for Insights' "Done, and did it work?": one row each, its page opens it. */
export function trackedList(m, s) {
  const list = merged(m);
  if (!list.length) return [];
  const visits = (c) => (c.figures || []).find((f) => f.key === "visits");
  const cols = [
    { key: "path", label: "Page", path: true },
    { key: "day", label: "Changed", type: "date", fmt: (v) => short(v) },
    { key: "kind", label: "What changed", fmt: (v, c) => h("span", null, kindWords(v), c.note ? h("small", { class: "ps-t" }, c.note) : null), csv: (c) => `${kindWords(c.kind)}${c.note ? `: ${c.note}` : ""}` },
    { key: "vb", label: "Visits a day, before", num: true, sort: (c) => visits(c)?.before?.per_day ?? -1, fmt: (_, c) => (visits(c) ? sideWords(visits(c), "before") : "counting"), csv: (c) => visits(c)?.before?.per_day ?? "" },
    { key: "va", label: "After", num: true, sort: (c) => visits(c)?.after?.per_day ?? -1, fmt: (_, c) => (visits(c) ? sideWords(visits(c), "after") : "counting"), csv: (c) => visits(c)?.after?.per_day ?? "" },
    { key: "verdict", label: "What it says", sort: (c) => (c.pending ? "pending" : visits(c)?.verdict || ""),
      fmt: (_, c) => (c.pending ? "Waiting for the next update" : c.status === "ready" ? VERDICTS[visits(c)?.verdict] || "" : c.status === "too_early" ? `Too early: verdict on ${short(c.verdict_on)}` : "Counting starts tomorrow"),
      csv: (c) => (c.pending ? "pending" : visits(c)?.verdict || c.status) },
  ];
  return [h("h3", { class: "td-h3" }, "Pages you changed: did it work?"),
    h("p", { class: "sub" }, "Each change marked on a page, its visits a day on the whole days before and after it. Open one for every figure: leads, search, AI and those who left at once."),
    table(cols, { caption: "Pages you changed", rows: list.map((c) => ({ ...c, __k: c.id })), file: "page-changes.csv", sortKey: "day", dir: -1, limit: 10,
      rowClass: (c) => (c.id === s.pchg ? "go on" : "go"), onRow: goTo, empty: "No change tracked." })];
}
