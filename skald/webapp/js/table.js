// Every table in the app: sort by any column, filter each column, choose the
// columns, search its rows, download what it shows as CSV. The CSV holds the rows
// the filters and the search left, all of them, not only the ones on screen, with
// the columns shown, in their order.

import { h, n, toast, reduced, ICON } from "./ui.js";
import { link, drillRow } from "./drill.js";
import { shownText } from "./labels.js";
import { code3, countryName } from "./countries.js";
import { HASH, writeKeys, nsOf, compare, sortRows, nextSort, sortParam, readSort, readFilters, writeFilters, readHidden, testFilter, filterKind, parseAmount, visibleColumns } from "./tablestate.js";
import { chooser, exportButton, filterToggle, filterCell, filterChips } from "./tabletools.js";
import { withUrl, isUrlColumn, copyCell } from "./urlactions.js";

/* Every table drawn in the current render, so "Export this view" and the
   report can take them all: {caption, file, columns, rows()}. main.js
   empties it before each render. */
export const REGISTRY = [];
// While a report is printed every row is shown, not only the first page of them.
let ALL_ROWS = false;
export function showAllRows(on) { ALL_ROWS = !!on; }

// A cell a spreadsheet would run as a formula is prefixed with an apostrophe,
// as export.py does for the server's files. A stored label is written in its shown words.
function cell(v) {
  let s = v == null ? "" : shownText(String(v));
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/* A country column (country: row -> its stored two-letter code; a column drilled by
   country gets one) is written as two: the full name under the column's own header,
   and its ISO alpha-3 code under "Code"; a column that also shows a city (city: row -> its
   words) adds a "City" column. The screen shows the flag and the code. */
const COUNTRY_CSV = (columns) => columns.flatMap((c) => (c.country
  ? [{ ...c, csv: (r) => countryName(c.country(r)) }, { label: "Code", csv: (r) => { const k = c.country(r); return /^[A-Za-z]{2}$/.test(k || "") ? code3(k) : ""; } },
    ...(c.city ? [{ label: "City", csv: c.city }] : [])]
  : [c]));

/* A drawn cell's words: shown (its text without the .vh or [hidden] parts a reader does
   not see, joined as drawn) and all (shown, then each hidden part apart, for the search box). */
export function cellWords(node) {
  let shown = "";
  const hidden = [];
  const walk = (x, off) => {
    if (x.nodeType === 8) return;
    const el = typeof x.tagName === "string";
    if (!el && !x.childNodes?.length) { const t = x.textContent || ""; if (off) hidden.push(t.trim()); else shown += t; return; }
    const out = off || (el && (x.classList?.contains("vh") || x.hasAttribute?.("hidden")));
    for (const k of x.childNodes) walk(k, out);
  };
  walk(node, false);
  shown = shown.trim();
  return { shown, all: [shown, ...hidden.filter(Boolean)].join(" ") };
}

/* How many columns csv() writes for these: a country column is two (or three with a city),
   so "Export what you see" says the CSV's own width. */
export const csvWidth = (columns) => COUNTRY_CSV(columns).length;

export function csv(columns, rows) {
  columns = COUNTRY_CSV(columns);
  // csvLabel: a header that needs its group to be read alone ("Visitors, B": js/mode-compare.js).
  const head = columns.map((c) => cell(c.csvLabel ?? c.label)).join(",");
  const body = rows.map((r) => columns.map((c) => cell(c.csv ? c.csv(r) : r[c.key])).join(","));
  return [head, ...body].join("\r\n") + "\r\n";
}

export function download(name, text, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(text instanceof Blob ? text : new Blob([text], { type }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  toast(`Downloaded ${name}`);
}

/* How a column lines up, the same in every table and grid (js/grid.js): every cell sits at
   the top of its row (app.css); words left; numbers right (counts, shares, durations,
   money, times and dates written as numbers); a yes/no or a small tag ("New", "Blocked")
   centred. The header follows its column.
     type: "num"  (or num: true)  right; num: true also formats a bare number and sorts biggest first
     type: "date"                 right, sorted like words (an ISO day sorts as itself)
     type: "badge" | "bool"       centred, before num (an HTTP status is a number drawn as a tag)
     type: "text" (the default)   left */
export function alignOf(c) {
  if (c.type === "badge" || c.type === "bool") return "center";
  if (c.num || c.type === "num" || c.type === "date") return "right";
  return null;
}
const ALIGN_CLS = { right: "n", center: "c" };

/* columns: [{key, label, num?, type?, path?, url?, href?(row), cls?, title? (a hint on the header), fmt?(v,row), csv?(row), sort?(row), drill?: dimension,
             filter?: "text"|"num"|"enum"|false (the column filter; tablestate.js filterKind decides when not given),
             hide?: true - a secondary column, left out until "Columns" shows it (only with the tools; never the first)}]
   A column of site paths (path: true, or drilled by page or landing page) or of URLs (url: true)
   draws copy and open-in-a-new-tab at each cell's end (urlactions.js); href(row): the URL when
   the cell's value is not it.
   opts: {caption, rows, file, limit=15, empty, sortKey, dir, search=true, rowClass?(row), note, onRow?(row), placeholder, rowDrill?: false,
          groups?: [[label, span]] - a header row above the columns that names groups of them,
          ns?: the table's name in the address (default: its caption made short); ns: false keeps nothing there,
          tools?: false - no filter row, column chooser or export (a table inside a small card)}
   Every table: a header click sorts (A to Z or biggest first, the other way, then the
   table's own order again), "Filter columns" opens a row of filters under the headers
   (words: contains; numbers: lowest and highest; a few values: pick some), "Columns"
   chooses which show, and "Export what you see" downloads the rows that match, in their
   order, with the columns shown. Sort, filters, hidden columns and search stay in the
   address (tablestate.js), so a link or a reload brings the same table back.
   Without onRow, a row whose cells hold a value's link opens that value, the whole row
   (drill.js drillRow); rowDrill: false keeps only the link.
   The returned element has update(rows): new rows, same sort, filters and search. */
export function table(columns, opts) {
  const { caption, file, empty = "Nothing recorded.", search = true, rowClass, note, onRow } = opts;
  let rows = opts.rows;
  const limit = ALL_ROWS ? Infinity : opts.limit ?? 15;
  // A drillable column draws its value as a link to the value's detail, unless it formats it itself.
  columns = columns.map((c) => (c.drill && !c.fmt ? { ...c, fmt: (v) => (v == null || v === "" ? "" : link(c.drill, v)), csv: c.csv || ((r) => r[c.key]) } : c))
    .map((c) => (c.drill === "country" && !c.country ? { ...c, country: (r) => (c.key === "label" ? r.k : r[c.key]) } : c));
  const keys = columns.map((c) => c.key);
  const ns = opts.ns === false ? null : opts.ns || nsOf(caption, REGISTRY.map((x) => x.ns).filter(Boolean));
  const key = (suffix) => `${ns}_${suffix}`;
  const kept = ns ? HASH.read() : new URLSearchParams();
  const tools = opts.tools !== false;

  const def = (() => {
    const k = opts.sortKey ?? columns.find((c) => c.num)?.key ?? null;
    return k == null ? null : { key: k, dir: opts.dir ?? (columns.find((c) => c.key === k)?.num ? -1 : 1) };
  })();
  let sort = readSort(kept.get(key("sort")), keys);
  let filters = tools ? readFilters(kept.get(key("cf")), keys) : [];
  // A column marked hide starts hidden; once the reader chooses, the address keeps the choice
  // ("-": every column shown), and choosing the defaults again leaves the address clean.
  const defHidden = tools ? columns.slice(1).filter((c) => c.hide).map((c) => c.key) : [];
  const isDefault = (x) => x.length === defHidden.length && defHidden.every((k) => x.includes(k));
  let hidden = tools ? (kept.has(key("hide")) ? readHidden(kept.get(key("hide")), keys.slice(1)) : defHidden) : [];
  let query = search ? kept.get(key("q")) || "" : "", showAll = false;
  let frowOpen = filters.length > 0;
  const save = () => { if (ns) writeKeys({ [key("sort")]: sortParam(sort), [key("cf")]: writeFilters(filters), [key("hide")]: isDefault(hidden) ? "" : hidden.join(",") || "-", [key("q")]: query.trim() }); };

  // A table without a search box (most cards): its tools sit beside the card's title (css/tables.css).
  const wrap = h("div", { class: search ? "tbl" : "tbl tbl-quiet" });
  const count = h("span", { class: "tbl-count", "aria-live": "polite" });
  const input = search ? h("input", { type: "search", value: query, placeholder: opts.placeholder || "Search rows", "aria-label": `Search ${caption}` }) : null;
  const shownCols = () => visibleColumns(columns, hidden);
  const dl = file && tools ? exportButton(() => download(file, csv(shownCols(), filtered()))) : null;
  const plainDl = file && !tools ? h("button", { type: "button", class: "btn", html: ICON.download, "aria-label": `Download ${caption} as CSV`, onclick: () => download(file, csv(columns, filtered())) }, "CSV") : null;
  const ftog = tools && rows.length > 1 ? filterToggle((on) => { frowOpen = on; render(); if (on) frow.querySelector("input,button")?.focus(); }) : null;
  const pick = tools && columns.length >= 4 ? chooser(columns, hidden, (next) => { hidden = next; save(); render(); }, caption) : null;
  const thead = h("thead");
  const tbody = h("tbody");
  const tableEl = h("table", null, h("caption", { class: "vh" }, caption), thead, tbody);
  const more = h("button", { type: "button", class: "btn more-rows" });
  // One toolbar row: the search on the left, the tools on the right; the filters that are on
  // as chips under it; the row count and "Show all" directly under the table, at its edges.
  const bar = h("div", { class: "tbl-tools" }, input, h("span", { class: "grow" }), ftog, pick, dl || plainDl);
  const chips = tools ? filterChips((k) => { filters = k == null ? [] : filters.filter((f) => f.key !== k); frowFor = null; save(); render(); }) : null;
  const scroll = h("div", { class: "scroll" }, tableEl);
  const foot = h("div", { class: "tbl-foot" }, count, more);
  wrap.append(...[input || ftog || pick || dl || plainDl ? bar : null, chips, scroll, foot].filter(Boolean));
  if (note) wrap.append(h("p", { class: "note" }, note));

  // What a cell shows (its visible words: a column filter and the value lists match these,
  // so "USA" never matches AUS through a screen reader's hidden "Australia"), and what the
  // search box also finds (the hidden words too, apart: "Canada" finds CAN). Once per row.
  let texts = new WeakMap();
  const cellOf = (c, r) => {
    let m = texts.get(r);
    if (!m) { m = new Map(); texts.set(r, m); }
    if (!m.has(c.key)) { const v = c.fmt ? c.fmt(r[c.key], r) : r[c.key] ?? ""; m.set(c.key, v instanceof Node ? cellWords(v) : { shown: String(v).trim(), all: String(v).trim() }); }
    return m.get(c.key);
  };
  const textOf = (c, r) => cellOf(c, r).shown;
  const val = (c, r) => (c.sort ? c.sort(r) : r[c.key]);
  const kinds = new Map(columns.map((c) => [c.key, filterKind(c, new Set(rows.slice(0, 400).map((r) => textOf(c, r))).size)]));
  const filtered = () => {
    const q = query.trim().toLowerCase();
    let out = q ? rows.filter((r) => columns.some((c) => cellOf(c, r).all.toLowerCase().includes(q))) : rows.slice();
    for (const f of filters) {
      const c = columns.find((x) => x.key === f.key);
      // The number a range compares: the row's own, else the one the cell shows ("12%", "3 min"), else what it sorts by.
      if (c) out = out.filter((r) => testFilter(f, { num: typeof r[c.key] === "number" ? r[c.key] : parseAmount(textOf(c, r)) ?? val(c, r), text: textOf(c, r) }));
    }
    const s = sort || def;
    const c = s && columns.find((x) => x.key === s.key);
    return c ? sortRows(out, [{ get: (r) => val(c, r), type: c.type, dir: s.dir }]) : out;
  };

  // The filter row: one cell per column shown, built once per render of the header.
  const frow = h("tr", { class: "tt-frow" });
  let frowFor = null;  // the columns the filter row was built for
  const setFilter = (k, f) => { filters = [...filters.filter((x) => x.key !== k), ...(f ? [f] : [])]; save(); render(); };
  const optionsOf = (c) => () => {
    const seen = new Map();
    for (const r of rows) { const t = textOf(c, r); seen.set(t, (seen.get(t) || 0) + 1); }
    return [...seen].sort((a, b) => b[1] - a[1] || compare(a[0], b[0])).slice(0, 40);
  };
  function filterRow() {
    frow.replaceChildren(...shownCols().map((c) => h("td", { class: ALIGN_CLS[alignOf(c)] || null },
      kinds.get(c.key) ? filterCell(c, kinds.get(c.key), filters.find((f) => f.key === c.key), optionsOf(c), (f) => setFilter(c.key, f)) : null)));
  }

  function head() {
    const cols = shownCols();
    const s = sort || def;
    const groups = opts.groups && !hidden.length ? h("tr", { class: "grp-row" }, opts.groups.map(([l, span]) => h("th", { scope: l ? "colgroup" : null, colspan: span, class: l ? "colgrp" : null }, l || ""))) : null;
    const row = h("tr", null, cols.map((c) => {
      const sorted = s && c.key === s.key;
      const th = h("th", { scope: "col", title: c.title || null, class: [ALIGN_CLS[alignOf(c)], c.cls].filter(Boolean).join(" ") || null, "aria-sort": sorted ? (s.dir > 0 ? "ascending" : "descending") : "none" },
        h("button", { type: "button", "aria-label": `${c.label}: sort ${sortWords(c, sort, def)}`, onclick: () => { sort = nextSort(sort, c, def); save(); render(true); } },
          c.label, h("span", { class: "dir", "aria-hidden": "true" }, sorted ? (s.dir > 0 ? "▲" : "▼") : "↕")));
      return th;
    }));
    // The filter row is built once for the columns shown and then left in place, so a
    // cell keeps its focus and an open list of values stays open while the rows change.
    const lead = [groups, row].filter(Boolean);
    if (!frowOpen) { frowFor = null; thead.replaceChildren(...lead); return; }
    if (frowFor !== hidden.join()) { filterRow(); frowFor = hidden.join(); }
    for (const el of [...thead.children]) if (el !== frow) el.remove();
    if (frow.parentNode === thead) for (const el of lead) thead.insertBefore(el, frow);
    else thead.append(...lead, frow);
  }

  function render(animate = false) {
    const before = animate && !reduced() ? new Map([...tbody.children].map((tr) => [tr.dataset.k, tr.getBoundingClientRect().top])) : null;
    head();
    const cols = shownCols();
    const all = filtered();
    const shown = showAll ? all : all.slice(0, limit);
    if (!rows.length) {
      tbody.replaceChildren(h("tr", null, h("td", { colspan: cols.length, class: "muted" }, empty)));
    } else if (!all.length) {
      tbody.replaceChildren(h("tr", null, h("td", { colspan: cols.length, class: "muted" }, filters.length ? "No row matches these filters." : "No row matches the search.")));
    } else {
      tbody.replaceChildren(...shown.map((r) => {
        const tr = h("tr", { class: rowClass ? rowClass(r) : null });
        if (onRow) {
          tr.tabIndex = 0;
          tr.addEventListener("click", (e) => { if (!e.target.closest("button,a")) onRow(r); });
          tr.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === tr) { e.preventDefault(); onRow(r); } });
        }
        tr.dataset.k = r.__k ?? columns.map((c) => r[c.key]).join("|");
        for (const c of cols) {
          const v = r[c.key];
          const text = c.fmt ? c.fmt(v, r) : c.num ? n(v) : v ?? "";
          const shown = text instanceof Node ? text : String(text);
          // A page or a URL: copy and open in a new tab at the cell's end (urlactions.js).
          const cellEl = isUrlColumn(c) ? withUrl(shown, c.href ? c.href(r) : v) : copyCell(c, r, shown);
          tr.append(h("td", { class: [ALIGN_CLS[alignOf(c)] || (c.path ? "path" : null), c.cls].filter(Boolean).join(" ") || null }, cellEl));
        }
        // A row about a value opens it, the whole row (drill.js drillRow); onRow wins.
        if (!onRow && opts.rowDrill !== false) drillRow(tr);
        return tr;
      }));
    }
    count.textContent = rows.length ? (all.length === rows.length ? `${n(rows.length)} row${rows.length === 1 ? "" : "s"}` : `${n(all.length)} of ${n(rows.length)} rows`) : "";
    more.hidden = all.length <= limit;
    more.textContent = showAll ? "Show fewer" : `Show all ${n(all.length)}`;
    // A table of one row says nothing under it; otherwise the count, and Show all when there is more.
    if (rows.length < 2 && all.length === rows.length) count.textContent = "";
    foot.hidden = !count.textContent && more.hidden;
    // Every row on screen: the header stays in view while the box scrolls.
    wrap.classList.toggle("tall", showAll && all.length > 25);
    dl?.say(all.length, csvWidth(cols), caption);
    if (plainDl) plainDl.disabled = !all.length;
    ftog?.say(frowOpen, filters.length);
    chips?.say(columns, filters);
    if (before) [...tbody.children].forEach((tr) => {
      const was = before.get(tr.dataset.k);
      if (was == null) return;
      const dy = was - tr.getBoundingClientRect().top;
      if (!dy) return;
      tr.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 260, easing: "cubic-bezier(.2,.7,.2,1)" });
    });
  }

  let qTimer = 0;
  input?.addEventListener("input", () => { query = input.value; render(); clearTimeout(qTimer); qTimer = setTimeout(save, 300); });
  more.addEventListener("click", () => { showAll = !showAll; render(); });
  render();
  wrap.update = (next) => { rows = next; texts = new WeakMap(); render(); };
  REGISTRY.push({ caption, file, ns, columns, rows: filtered });
  return wrap;
}

// What the next header click does, for a screen reader: "ascending", "descending", "back to the table's order".
function sortWords(c, sort, def) {
  const next = nextSort(sort, c, def);
  if (!next) return "back to the table's own order";
  return next.dir > 0 ? (c.num || c.type === "num" ? "smallest first" : c.type === "date" ? "oldest first" : "A to Z")
    : (c.num || c.type === "num" ? "biggest first" : c.type === "date" ? "newest first" : "Z to A");
}
