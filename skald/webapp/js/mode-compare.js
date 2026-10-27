// Compare mode (2.7.0): "Compare with…" in the top bar (js/modes.js) sets
// `cmp` in the address: prev (the previous period), year (the same period 52
// weeks earlier, so weekdays match) or custom (the period in `cb`,
// "2026-08-01..2026-08-31"). A is always the global period; B is the chosen one.
// Live (Today) is never compared.
//
// ---------------------------------------------------- for section builders
// A tab says it follows Compare with `compare: true` in its registry entry
// (js/tabs/s-*.js). The shell then puts one line at the top of the tab: what A
// and B are, or why they are not compared (js/modes.js modeBanner). A tab
// without `compare: true` gets a quiet "No compare on this tab" instead.
// Inside a tab that compares:
//
//   import { compareOf, cmpTable, compareFor, versus, noCompare } from "../mode-compare.js";
//   const c = compareOf(m, s);
//
//   c.on      Compare is switched on (whatever happens next)
//   c.ok      A and B can be compared; when false, c.why says why (the banner
//             already shows it: a panel need not repeat it)
//   c.a, c.b  the two periods, as data.js rangeOf gives them ({first, last, length, days})
//   c.bT      B's totals, summed exactly as data.js total() sums A's: the same
//             sum over B's whole, verified days. Build B's rows from it the way
//             the plain table builds A's from its totals.
//   c.perDay  "Per day" is on (custom B of another length): cmpTable divides
//   c.used    {a, b}: the whole days each side counts (per-day divisor)
//
// A table, A · B · ± (grouped headers; full width, the label column stays put
// while the figures scroll, as the 2.5.1 lead tables):
//
//   const cols = [{ key: "k", label: "Source", ... }, { key: "v", label: "Visitors", num: true }];
//   const A = ranked(t.by.source).map(([k, v]) => ({ k, v }));
//   if (!c.ok) return table(cols, { caption, rows: A, file });       // compare off or not possible
//   const B = ranked(c.bT.by?.source).map(([k, v]) => ({ k, v }));
//   return cmpTable(cols, A, B, { key: "k", measures: ["v"], caption, file }, c);
//
//   key       the field naming a row in both lists (default "k")
//   measures  the number columns that become A · B · ±; default every `num` column.
//             Leave shares and rates out (they keep their minimums only as A's), or
//             drop such columns before calling. A column not in `measures` stays as
//             it is and reads as A's (blank on a row only B has).
//   ratios    measures not divided in "Per day" (pages per visit, a rate)
//   better    {key: "down"} where more is worse (pages not found); default "up"
//   min       below this count in both periods the ± shows no percentage (default 10)
//   Any other table option (limit, search, rowClass, note, empty...) passes through.
//   A row only one period has counts 0 in the other; a figure that is null stays null.
//
// A chart: compareFor(m, s).prev is the day function charts.js columns()/lines()
// take as `prev` (a dashed line of B, day 1 of A over day 1 of B); .legend is its
// legend entry. A tile or a single figure: versus(a, b, opts) draws "B 1,234 ▲ +12 +1.0%".
// A panel that does not compare (its own period, a list, a check):
// noCompare(s, "why") draws one quiet line when Compare is on, else nothing.
//
// Rules kept from 2.5: previous period and last year are strict (both periods whole
// and verified, else not compared); a custom B follows the Compare page's rule (whole
// days only, every day left out named, "Per day" when the lengths differ).

import { h, n, short, addDays, dayDiff } from "./ui.js";
import { rangeOf, previousOf, daysBetween, coverage, total } from "./data.js";
import { table } from "./table.js";
import { cmpOf, spanOf } from "./routes.js";

export const YEAR = 364;          // "last year": 52 weeks back, the same weekdays (the Compare page's rule)
export const MAX_DAYS = 366;
export const KINDS = [
  ["prev", "Previous period", "the same number of days just before"],
  ["year", "Same period last year", "the same dates 52 weeks earlier, so weekdays match"],
  ["custom", "Custom period", "any whole days, up to 12 months"],
];
const NAME = Object.fromEntries(KINDS.map(([k, w]) => [k, w]));

export const compareOn = (s) => !!cmpOf(s.cmp);
export const spanWords = (x) => (x.first === x.last ? `${short(x.first)} ${x.first.slice(0, 4)}`
  : `${short(x.first)} to ${short(x.last)} ${x.last.slice(0, 4)}`);

// B for a kind, as a range: {first, last, length, days}. Null when a custom B has no dates.
export function rangeB(m, s, a, kind = cmpOf(s.cmp)) {
  if (!a || a.kind !== "history") return null;
  if (kind === "prev") return previousOf(m, a);
  let x = kind === "year" ? { first: addDays(a.first, -YEAR), last: addDays(a.last, -YEAR) } : kind === "custom" ? spanOf(s.cb) : null;
  if (!x) return null;
  if (x.last > m.anchor) x = { first: x.first > m.anchor ? m.anchor : x.first, last: m.anchor };
  if (dayDiff(x.first, x.last) + 1 > MAX_DAYS) x = { first: addDays(x.last, -(MAX_DAYS - 1)), last: x.last };
  return { kind: "history", first: x.first, last: x.last, length: dayDiff(x.first, x.last) + 1, days: daysBetween(m, x.first, x.last) };
}

// The days a period leaves out, named: "6 Oct partial; 1 to 5 Oct not collected".
const STATE = { partial: "partial", withheld: "withheld (did not pass the checks)", missing: "not collected", before: "before history begins" };
export function leftOut(r) {
  const groups = {};
  for (const d of r.days) if (d.state !== "ok") (groups[d.state] ||= []).push(d.day);
  return Object.entries(groups).map(([st, list]) => {
    const runs = [];
    for (const day of list.sort()) { const last = runs[runs.length - 1]; if (last && addDays(last[1], 1) === day) last[1] = day; else runs.push([day, day]); }
    return `${runs.map(([x, y]) => (x === y ? short(x) : `${short(x)} to ${short(y)}`)).join(", ")} ${STATE[st] || st}`;
  }).join("; ");
}

/* A and B for this state, or why not. See the top of the file. */
export function compareOf(m, s) {
  const kind = cmpOf(s.cmp);
  if (!kind) return { on: false, ok: false };
  const a = rangeOf(m, s);
  const base = { on: true, ok: false, kind, name: NAME[kind], a };
  if (a.kind === "today") return { ...base, why: "Today is live and partial, so it is never compared. Pick Yesterday or longer to compare." };
  // Include today (period-dates.js): today is not over, and no earlier day is kept cut at the
  // same hour, so a period that ends today is never set against whole days.
  if (a.inc) {
    const whole = rangeOf(m, { ...s, inc: "" });
    return { ...base, inc: true, b: previousOf(m, a), why: `Not compared while today is included: today is not over, so its figures would always look lower than a whole day's. Turn Include today off to compare ${spanWords(whole)} with the ${whole.length} days before.` };
  }
  const b = rangeB(m, s, a, kind);
  if (!b) return { ...base, why: "Not compared: choose the custom period's dates under Compare with…" };
  const ca = coverage(a), cb = coverage(b);
  const out = { ...base, b, name: kind === "custom" ? `B, ${spanWords(b)}` : NAME[kind] };
  if (kind !== "custom") {
    if (!ca.complete) return { ...out, why: `Not compared: only ${ca.ok} of this period's ${a.length} days are whole and verified.` };
    if (!cb.complete) {
      const held = cb.ok ? `only ${cb.ok} of its ${b.length} days are whole and verified` : "history does not reach back that far yet";
      const which = kind === "year" ? "The same days a year earlier" : `The ${a.length} day${a.length === 1 ? "" : "s"} before`;
      return { ...out, why: `Not compared: ${which.toLowerCase()} (${short(b.first)} to ${short(b.last)}) ${b.length === 1 ? "is" : "are"} not complete; ${held}.` };
    }
  } else {
    const first = m.firstDay ? short(m.firstDay) : "the first day";
    if (!ca.ok) return { ...out, why: "Not compared: this period has no whole, verified day." };
    if (!cb.ok) return { ...out, why: `Not compared: B (${spanWords(b)}) has no whole, verified day. History begins ${first}.` };
  }
  const differ = a.length !== b.length || ca.ok !== cb.ok;
  const gaps = kind === "custom" ? [["A", a, ca], ["B", b, cb]].filter(([, r]) => r.days.some((d) => d.state !== "ok"))
    .map(([nm, r, cv]) => `${nm}: left out ${leftOut(r)}; ${cv.ok} whole day${cv.ok === 1 ? "" : "s"} counted.`) : [];
  return { ...out, ok: true, bT: total(b.days), shift: dayDiff(b.first, a.first), used: { a: ca.ok, b: cb.ok },
    differ, perDay: kind === "custom" && differ && s.cnorm === "1", gaps };
}

/* For charts and older callers (tabs/common.js compareFor re-exports this):
   prev - the day of B at the same place as a day of A, for charts.js `prev`, or null;
          it carries .label, the words charts use for the dashed line
   legend - the dashed line's legend entry; note - null (the tab's banner says why not). */
export function compareFor(m, s) {
  const c = compareOf(m, s);
  if (!c.ok) return { ...c, prev: null, note: null, legend: [] };
  const words = c.kind === "custom" ? `B (${spanWords(c.b)})` : c.name;
  const prev = (d) => {
    const day = addDays(d.day, -c.shift);
    if (day < c.b.first || day > c.b.last) return null;
    const e = m.byDay.get(day);
    return e && e.state === "ok" ? e : null;
  };
  prev.label = words.charAt(0).toLowerCase() + words.slice(1);
  return { ...c, prev, note: null, legend: [[words, "var(--ink-3)", "ghost"]] };
}

// ----------------------------------------------------------------- figures
const num1 = (v) => (v == null ? "-" : Math.abs(v) < 100 && !Number.isInteger(v) ? v.toFixed(1) : n(v));
const pctWords = (p) => `${p > 0 ? "+" : "−"}${Math.abs(p) < 10 ? Math.abs(p).toFixed(1) : Math.round(Math.abs(p))}%`;

/* The change, A against B: "+12" with "+1.0%" under it in a table (or beside it).
   better: "up" (more is good, green), "down" (more is bad), "none" (no colour).
   min: below this in both periods, no percentage (a handful says little). */
export function change(a, b, { better = "up", min = 10, fmt = num1, inline = false } = {}) {
  if (a == null || b == null) return h("span", { class: "vs-d none" }, "-");
  const d = a - b;
  const flat = Number(String(fmt(Math.abs(d))).replace(/[^\d.]/g, "")) === 0;
  const tone = flat || better === "none" ? "" : (d > 0) === (better !== "down") ? " good" : " bad";
  const dir = flat ? "flat" : d > 0 ? "up" : "down";
  const pct = flat ? null : !b ? (a ? "new" : null) : Math.max(a, b) < min ? null : pctWords((d / b) * 100);
  return h("span", { class: `vs-d ${dir}${tone}` },
    flat ? "0" : `${d > 0 ? "+" : "−"}${fmt(Math.abs(d))}`,
    pct ? h("span", { class: inline ? "d-pct in" : "d-pct" }, pct) : null,
    h("span", { class: "vh" }, dir === "up" ? " (up)" : dir === "down" ? " (down)" : ""));
}

// One figure against B, for a tile: "vs 1,234 ▲ +12 +1.0%".
export function versus(a, b, opts = {}) {
  const fmt = opts.fmt || num1;
  return h("span", { class: "cmp-vs" }, h("i", { class: "sb", "aria-hidden": "true" }), h("span", { class: "vh" }, "B: "), "vs ", fmt(b), " ", change(a, b, { ...opts, inline: true }));
}

// A panel that does not compare: one quiet line while Compare is on.
export function noCompare(s, why = "") {
  if (!compareOn(s)) return null;
  return h("p", { class: "cmp-none" }, `No compare here${why ? `: ${why}` : ""}.`);
}

// ------------------------------------------------------------------ tables
const D = (k) => `${k}__d`, B = (k) => `${k}__b`;

// One list of rows from A's and B's, by `key`: A's figures, B's beside them, and the change.
export function joinRows(rowsA, rowsB, { key = "k", measures, ratios = new Set(), numeric = [] }, c) {
  const scaleA = c.perDay ? Math.max(1, c.used.a) : 1, scaleB = c.perDay ? Math.max(1, c.used.b) : 1;
  const per = (v, sc, k) => (v == null || ratios.has(k) ? v : v / sc);
  const bBy = new Map(rowsB.map((r) => [r[key], r]));
  const seen = new Set();
  const out = [];
  const one = (ra, rb) => {
    const row = { ...(ra || rb) };
    // A figure only B has is blank, never B's (a share of B read as A's).
    if (!ra) for (const k of numeric) if (!measures.includes(k)) row[k] = null;
    for (const k of measures) {
      const va = ra ? per(ra[k], scaleA, k) : 0, vb = rb ? per(rb[k], scaleB, k) : 0;
      row[k] = va;
      row[B(k)] = vb;
      row[D(k)] = va == null || vb == null ? null : va - vb;
    }
    return row;
  };
  for (const ra of rowsA) { seen.add(ra[key]); out.push(one(ra, bBy.get(ra[key]))); }
  for (const rb of rowsB) if (!seen.has(rb[key])) out.push(one(null, rb));
  return out;
}

// The columns and the header groups: each measure becomes A · B · ± under its own name.
export function cmpCols(columns, measures, { better = {}, min = 10 } = {}, c) {
  const cols = [], groups = [];
  const plain = () => { const g = groups[groups.length - 1]; if (g && g[0] === "") g[1] += 1; else groups.push(["", 1]); };
  const fmtOf = (col) => (c.perDay && !col.ratio ? num1 : col.fmt ? (v, row) => col.fmt(v, row) : (v) => n(v));
  // "Per day" figures are small: the percentage's minimum shrinks with them.
  if (c.perDay) min /= Math.max(1, c.used.a, c.used.b);
  for (const col of columns) {
    if (!measures.includes(col.key)) { cols.push(col); plain(); continue; }
    const k = col.key, f = fmtOf(col), name = String(col.label);
    cols.push({ ...col, label: "A", csvLabel: `${name}, A`, cls: [col.cls, "g-start"].filter(Boolean).join(" "), title: `${name} in A (${spanWords(c.a)})`, fmt: f });
    cols.push({ key: B(k), label: "B", csvLabel: `${name}, B`, num: true, title: `${name} in B (${spanWords(c.b)})`, fmt: f, csv: (r) => r[B(k)] });
    cols.push({ key: D(k), label: "±", csvLabel: `${name}, change`, num: true, title: `${name}: A against B`, sort: (r) => r[D(k)],
      fmt: (_, r) => change(r[k], r[B(k)], { better: better[k] || "up", min, fmt: c.perDay || col.ratio ? num1 : (v) => n(v) }), csv: (r) => r[D(k)] });
    groups.push([name, 3]);
  }
  return { cols, groups };
}

/* A table with A · B · ± columns. See the top of the file. */
export function cmpTable(columns, rowsA, rowsB, opts, c) {
  const measures = opts.measures || columns.filter((x) => x.num).map((x) => x.key);
  const ratios = new Set(opts.ratios || []);
  const cols0 = columns.map((x) => (ratios.has(x.key) ? { ...x, ratio: true } : x));
  const rows = joinRows(rowsA, rowsB, { key: opts.key || "k", measures, ratios, numeric: columns.filter((x) => x.num).map((x) => x.key) }, c);
  const { cols, groups } = cmpCols(cols0, measures, { better: opts.better, min: opts.min ?? 10 }, c);
  const file = opts.file ? opts.file.replace(/\.csv$/, `-vs-${c.b.first}-to-${c.b.last}.csv`) : opts.file;
  const t = table(cols, { ...opts, rows, groups, file, caption: `${opts.caption}, A against B`,
    sortKey: opts.sortKey && measures.includes(opts.sortKey) ? opts.sortKey : opts.sortKey ?? measures[0],
    note: c.perDay ? [opts.note, "Per day: each figure is a typical day of its period."].filter(Boolean).join(" ") : opts.note });
  t.classList.add("cmp-tbl");
  return t;
}
