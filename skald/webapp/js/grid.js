// Long listings as a spcaeo/ui Data Grid (vendor/spcaeo-ui, MIT): search, filters,
// segments, sort and paging, each kept in the address beside the route's own keys,
// so a link or a reload brings back the same view:
//
//   #traffic/pages?range=7d&pg_q=pricing&pg_sort=views:desc&pg_page=2
//
// Keys are <ns>_<q|seg|fx|sort|page|size|view|sel>; Skald's own keys have no "_",
// so the two never meet. Reset clears only this grid's keys.
//
// Skald's listings are already in memory, so this file filters, sorts and pages them
// itself. Totals and shares are the caller's, over every filtered row (onFiltered),
// never the page; the CSV, ZIP and JSON exports (table.js REGISTRY) hold every filtered
// row, and while printing every filtered row is shown.
//
//   const g = grid({
//     ns: "pg", caption: "Pages read", file: "pages.csv",
//     columns: [{ key: "path", label: "Page", drill: "path" }, { key: "views", label: "Views", num: true }],
//     rows,                                             // the whole list
//     filters: [{ key: "kind", label: "Kind" }],        // options found in the rows unless given
//     segments: [{ id: "all", label: "All" }, { id: "blog", label: "Blog", test: (r) => r.path.startsWith("/blog/") }],
//     sortKey: "views",                                 // the order when the link names none
//     onFiltered: (all) => { … totals over all … },
//     onRow: (row) => openDrawer(row),                  // optional: rows open on click and Enter
//   });
//   card.append(g);   // g.update(rows), g.filtered(), g.destroy(), g.api (upstream's)
//
// Columns take table.js's shape: {key, label, num?, type?, fmt?(v,row), csv?(row), sort?(row), drill?, sortable?};
// type lines a column up as in table.js (alignOf): numbers right, tags and yes/no centred.

import { createDataGrid } from "../vendor/spcaeo-ui/data-grid/vanilla/data-grid.js";
import { readGridParams, writeGridParams } from "../vendor/spcaeo-ui/data-grid/core/url-state.js";
import { h, n } from "./ui.js";
import { link, drillRow } from "./drill.js";
import { shown, shownText } from "./labels.js";
import { REGISTRY, csv, csvWidth, download, alignOf } from "./table.js";
import { track } from "./mounts.js";
import { HASH, TABLE_KEY, writeKeys, sortRows, nextSort, readFilters, writeFilters, readHidden, testFilter, filterKind, parseAmount, visibleColumns } from "./tablestate.js";
import { chooser, exportButton, filterToggle, filterCell } from "./tabletools.js";

// ---- the hash's query, where every Skald key lives -----------------------------
// What upstream's `params` option asks for (tablestate.js HASH): read and write a
// URLSearchParams. Writing keeps the route and every other key; it never fires
// hashchange, so a grid change does not redraw the page (upstream's own rule).
export { HASH };

// A grid's key, for state.js hashFor to carry: S.set() rebuilds the hash from known keys.
// Its own suffixes plus the column filters and the column chooser's (tablestate.js).
export const GRID_KEY = TABLE_KEY;
export function carryGridKeys(into, from = HASH.read()) {
  for (const [k, v] of from) if (GRID_KEY.test(k)) into.set(k, v);
  return into;
}

// ---- printing shows every filtered row -----------------------------------------
// main.js redraws on beforeprint; this module is evaluated before main.js's body, so
// its listener runs first and the redraw sees the flag.
let printing = false;
addEventListener("beforeprint", () => { printing = true; });
addEventListener("afterprint", () => { printing = false; });
const everyRow = () => printing || !!document.body?.classList.contains("reporting");

// ---- the grid ------------------------------------------------------------------

const textOf = (node) => (node instanceof Node ? node.textContent : node == null ? "" : String(node));

export function grid(opts) {
  const { ns, caption, file, filters = [], segments = [], rowId, sortKey, onFiltered, onRow } = opts;
  if (!/^[a-z][a-z0-9]*$/.test(ns || "")) throw new Error(`grid: namespace "${ns}" must be lower-case letters and digits`);
  // A drillable column draws its value as a link to the value's detail, as in table.js.
  const cols = opts.columns.map((c) => (c.drill && !c.fmt ? { ...c, fmt: (v) => (v == null || v === "" ? "" : link(c.drill, v)), csv: c.csv || ((r) => r[c.key]) } : c))
    .map((c) => (c.drill === "country" && !c.country ? { ...c, country: (r) => (c.key === "label" ? r.k : r[c.key]) } : c));  // CSV: name and code (table.js)
  let rows = opts.rows || [];
  let texts = new WeakMap();  // each row's searchable text, built once per update()
  // The column filters and the hidden columns, from the address (tablestate.js).
  const kept = HASH.read();
  let cfs = readFilters(kept.get(`${ns}_cf`), cols.map((c) => c.key));
  let hidden = readHidden(kept.get(`${ns}_hide`), cols.slice(1).map((c) => c.key));
  let frowOpen = cfs.length > 0;

  // A stored label the grid draws as plain text is said as shown ("Direct", not "Direct or unknown").
  // The vendor grid draws a string as text (not through h()), so a formatted string is mapped here too.
  const cell = (c, r) => { const v = r[c.key]; const out = c.fmt ? c.fmt(v, r) : c.num ? n(v) : v; return typeof out === "string" ? shownText(out) : out; };
  const value = (c, r) => (c.sort ? c.sort(r) : r[c.key]);
  // What a cell says, worked out once per row and column (the search and the column filters read it).
  let said = new WeakMap();
  const cellText = (c, r) => {
    let m = said.get(r);
    if (!m) { m = new Map(); said.set(r, m); }
    if (!m.has(c.key)) m.set(c.key, textOf(cell(c, r)));
    return m.get(c.key);
  };
  const fieldOf = (f) => f.value || ((r) => r[f.key]);
  const searchText = (r) => {
    let t = texts.get(r);
    if (t == null) { t = cols.map((c) => cellText(c, r)).join("\u0001").toLowerCase(); texts.set(r, t); }
    return t;
  };
  const optionsOf = (f) => {
    if (f.options) return f.options.map((o) => (Array.isArray(o) ? { value: String(o[0]), label: o[1] } : { value: String(o), label: shown(String(o)) }));
    const seen = new Set();
    for (const r of rows) { const v = fieldOf(f)(r); if (v != null && v !== "") seen.add(String(v)); }
    // The value stays the stored name (the filter compares it); the label is its shown words.
    return [...seen].sort((a, b) => a.localeCompare(b)).slice(0, 100).map((v) => ({ value: v, label: shown(v) }));
  };
  const segTest = (id) => segments.find((s) => s.id === id)?.test;

  // Every row the query keeps, in its order: the grid shows a page of these.
  function filterAll(query) {
    let out = rows;
    const test = segTest(query.segment ?? segments[0]?.id);
    if (test) out = out.filter(test);
    for (const cond of query.filter.conditions) {
      const f = filters.find((x) => x.key === cond.field);
      if (!f) continue;
      const get = fieldOf(f);
      const has = (r) => { const v = get(r); return v != null && v !== ""; };
      const set = new Set(cond.values.map(String));
      if (cond.operator === "in") out = out.filter((r) => set.has(String(get(r))));
      else if (cond.operator === "not_in") out = out.filter((r) => !set.has(String(get(r))));
      else if (cond.operator === "is_set") out = out.filter(has);
      else if (cond.operator === "is_not_set") out = out.filter((r) => !has(r));
    }
    const q = query.q.trim().toLowerCase();
    if (q) out = out.filter((r) => searchText(r).includes(q));
    // The column filters (tablestate.js): what a cell shows, or the number it holds.
    for (const f of cfs) {
      const c = cols.find((x) => x.key === f.key);
      if (c) out = out.filter((r) => testFilter(f, { num: typeof r[c.key] === "number" ? r[c.key] : parseAmount(cellText(c, r)) ?? value(c, r), text: cellText(c, r).trim() }));
    }
    const order = shownSort(query);
    if (order.length) {
      // Not recorded last, whichever way; numbers by size, dates by time (tablestate.js sortRows).
      const keys = order.map((s) => [cols.find((c) => c.key === s.field), s.direction === "desc" ? -1 : 1]).filter(([c]) => c)
        .map(([c, dir]) => ({ get: (r) => value(c, r), type: c.type, dir }));
      out = sortRows(out, keys);
    }
    return out;
  }

  // The order on screen: the address's, else the grid's own (sortKey).
  function shownSort(query) {
    return query.sort.length ? query.sort : sortKey ? [{ field: sortKey, direction: opts.dir || (cols.find((c) => c.key === sortKey)?.num ? "desc" : "asc") }] : [];
  }
  // A header click: one way, the other, then the grid's own order (tablestate.js nextSort).
  function cycle(field, query) {
    const c = cols.find((x) => x.key === field);
    const cur = query.sort[0] ? { key: query.sort[0].field, dir: query.sort[0].direction === "asc" ? 1 : -1 } : null;
    const d = shownSort({ sort: [] })[0];
    const next = nextSort(cur, c, d ? { key: d.field, dir: d.direction === "asc" ? 1 : -1 } : null);
    return next ? [{ field: next.key, direction: next.dir > 0 ? "asc" : "desc" }] : [];
  }

  const config = {
    sortableFields: new Set(cols.filter((c) => c.sortable !== false).map((c) => c.key)),
    filterFields: new Map(filters.map((f) => [f.key, "enum"])),
    segmentIds: segments.map((s) => s.id),
  };
  // A link from before the rows shrank may ask for a page past the last: show the last.
  {
    const { query } = readGridParams(ns, HASH.read(), config);
    const pages = Math.max(1, Math.ceil(filterAll(query).length / query.pageSize));
    if (query.page > pages) HASH.write(writeGridParams(ns, { ...query, page: pages }, HASH.read()));
  }

  let onPage = [];  // the rows on screen (not labels.js shown)
  const wrap = h("div", { class: "sk-grid" });
  const host = h("div", { class: "sk-grid-host", "aria-label": caption || null, role: caption ? "region" : null });
  // The columns the grid draws: the same array, changed in place when the chooser hides one.
  const every = cols.map((c) => ({ id: c.key, label: c.label, sortable: c.sortable !== false, align: alignOf(c), render: (r) => cell(c, r) }));
  const drawn = every.filter((c) => !hidden.includes(c.id));
  const shownCols = () => visibleColumns(cols, hidden);
  const dl = file ? exportButton(() => download(file, csv(shownCols(), filterAll(api.query)))) : null;
  const ftog = rows.length < 2 && !cfs.length ? null : filterToggle((on) => { frowOpen = on; frowFor = null; api.refresh(); if (on) setTimeout(() => frow.querySelector("input,button")?.focus(), 0); });
  const pick = cols.length >= 4 ? chooser(cols, hidden, (next) => {
    hidden = next; frowFor = null;
    drawn.splice(0, drawn.length, ...every.filter((c) => !hidden.includes(c.id)));
    writeKeys({ [`${ns}_hide`]: hidden.join(",") });
    api.refresh();
  }, caption) : null;
  wrap.append(h("div", { class: "sk-grid-tools" }, ftog, pick, dl), host);

  // The filter row under the headers: built once for the columns shown, then moved into each
  // header the grid draws; the cell being typed in keeps its focus and caret.
  const frow = h("tr", { class: "tt-frow" });
  let frowFor = null;
  const setFilter = (k, f) => {
    cfs = [...cfs.filter((x) => x.key !== k), ...(f ? [f] : [])];
    writeKeys({ [`${ns}_cf`]: writeFilters(cfs) });
    api.change({}, "filter");  // page 1 again
  };
  const valuesOf = (c) => () => {
    const seen = new Map();
    for (const r of rows) { const t = cellText(c, r).trim(); seen.set(t, (seen.get(t) || 0) + 1); }
    return [...seen].sort((a, b) => b[1] - a[1]).slice(0, 40);
  };
  const kinds = new Map(cols.map((c) => [c.key, filterKind(c, new Set(rows.slice(0, 400).map((r) => cellText(c, r).trim())).size)]));
  function headExtra() {
    if (!frowOpen) return null;
    if (frowFor !== hidden.join()) {
      frow.replaceChildren(...shownCols().map((c) => h("td", { class: { right: "dg-num", center: "dg-center" }[alignOf(c)] || null },
        kinds.get(c.key) ? filterCell(c, kinds.get(c.key), cfs.find((f) => f.key === c.key), valuesOf(c), (f) => setFilter(c.key, f)) : null)));
      frowFor = hidden.join();
    }
    const a = document.activeElement;
    if (a && frow.contains(a)) {
      const caret = a.type === "text" || a.type === "search" ? [a.selectionStart, a.selectionEnd] : null;
      queueMicrotask(() => { if (a.isConnected) { a.focus({ preventScroll: true }); if (caret) a.setSelectionRange(...caret); } });
    }
    return frow;
  }
  const sayTools = (count) => { dl?.say(count, csvWidth(shownCols()), caption); ftog?.say(frowOpen, cfs.length); };

  const segCounts = segments.map((s) => ({ id: s.id, label: s.label, count: s.test ? rows.filter(s.test).length : rows.length }));
  const api = createDataGrid(host, {
    namespace: ns,
    params: HASH,
    columns: drawn,
    shownSort,
    nextSort: cycle,
    headExtra,
    filters: filters.map((f) => ({ id: f.key, label: f.label, type: "enum", options: optionsOf(f) })),
    segments: segCounts,
    getRowId: rowId || ((r) => rows.indexOf(r)),
    emptyMessage: opts.empty || "Nothing recorded.",
    searchPlaceholder: opts.placeholder || `Search ${caption ? caption.toLowerCase() : "rows"}`,
    async load(query) {
      const all = filterAll(query);
      onFiltered?.(all, query);
      sayTools(all.length);
      // One page of rows: no Previous, Next or "Page 1 of 1" (the count and the page size stay).
      wrap.classList.toggle("sk-one-page", query.page <= 1 && all.length <= query.pageSize);
      const start = (query.page - 1) * query.pageSize;
      onPage = everyRow() ? all : all.slice(start, start + query.pageSize);
      return { rows: onPage, total: all.length };
    },
  });

  // Rows that open something: a click, or Enter on the focused row, as in table.js.
  if (onRow) {
    host.classList.add("sk-grid-rows");
    const rowAt = (tr) => (tr?.parentElement?.closest(".dg-table") && !tr.classList.contains("dg-skeleton-row") ? onPage[[...tr.parentElement.children].indexOf(tr)] : null);
    host.addEventListener("click", (e) => {
      if (e.target.closest("button,a,input,label,select")) return;
      const row = rowAt(e.target.closest("tbody tr"));
      if (row) onRow(row);
    });
    host.addEventListener("keydown", (e) => {
      if ((e.key !== "Enter" && e.key !== " ") || !e.target.matches?.("tbody tr")) return;
      const row = rowAt(e.target);
      if (row) { e.preventDefault(); onRow(row); }
    });
    const focusable = () => host.querySelectorAll(".dg-table tbody tr:not([tabindex])").forEach((tr) => { tr.tabIndex = 0; });
    const mo = new MutationObserver(focusable);
    mo.observe(host, { childList: true, subtree: true });
    focusable();
    wrap.addEventListener("sk-grid:gone", () => mo.disconnect());
  }

  // No onRow: a row about a value opens it, the whole row (drill.js drillRow), as in table.js.
  else if (opts.rowDrill !== false) {
    const rowsOpen = () => host.querySelectorAll(".dg-table tbody tr:not([data-drow])").forEach((tr) => { if (!tr.classList.contains("dg-skeleton-row")) drillRow(tr); });
    const mo = new MutationObserver(rowsOpen);
    mo.observe(host, { childList: true, subtree: true });
    rowsOpen();
    wrap.addEventListener("sk-grid:gone", () => mo.disconnect());
  }

  REGISTRY.push({ caption, file, ns, columns: cols, rows: () => filterAll(api.query) });

  wrap.api = api;
  wrap.filtered = () => filterAll(api.query);
  wrap.update = (next) => { rows = next || []; texts = new WeakMap(); said = new WeakMap(); api.refresh(); };
  wrap.destroy = track(wrap, () => { api.destroy(); wrap.dispatchEvent(new Event("sk-grid:gone")); });
  return wrap;
}
