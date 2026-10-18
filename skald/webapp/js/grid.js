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
import { URL_SUFFIX, readGridParams, writeGridParams } from "../vendor/spcaeo-ui/data-grid/core/url-state.js";
import { h, n, ICON } from "./ui.js";
import { link } from "./drill.js";
import { shown, shownText } from "./labels.js";
import { REGISTRY, csv, download, alignOf } from "./table.js";
import { track } from "./mounts.js";

// ---- the hash's query, where every Skald key lives -----------------------------

function split() {
  const raw = location.hash.replace(/^#/, "");
  const at = raw.indexOf("?");
  return at < 0 ? [raw, ""] : [raw.slice(0, at), raw.slice(at + 1)];
}

// What upstream's `params` option asks for: read and write a URLSearchParams.
// Writing keeps the route and every other key; it never fires hashchange, so a grid
// change does not redraw the page (upstream's own rule: refine without re-rendering).
export const HASH = {
  read: () => new URLSearchParams(split()[1]),
  write(params, { push = false } = {}) {
    const qs = params.toString();
    const hash = `#${split()[0]}${qs ? `?${qs}` : ""}`;
    if (hash === location.hash) return;
    const url = `${location.pathname}${location.search}${hash}`;
    if (push) history.pushState(history.state, "", url);
    else history.replaceState(history.state, "", url);
  },
};

// A grid's key, for state.js hashFor to carry: S.set() rebuilds the hash from known keys.
export const GRID_KEY = new RegExp(`^[a-z][a-z0-9]*_(?:${Object.values(URL_SUFFIX).join("|")})$`);
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
  const cols = opts.columns.map((c) => (c.drill && !c.fmt ? { ...c, fmt: (v) => (v == null || v === "" ? "" : link(c.drill, v)), csv: c.csv || ((r) => r[c.key]) } : c));
  let rows = opts.rows || [];
  let texts = new WeakMap();  // each row's searchable text, built once per update()

  // A stored label the grid draws as plain text is said as shown ("Direct", not "Direct or unknown").
  const cell = (c, r) => { const v = r[c.key]; return c.fmt ? c.fmt(v, r) : c.num ? n(v) : typeof v === "string" ? shownText(v) : v; };
  const value = (c, r) => (c.sort ? c.sort(r) : r[c.key]);
  const fieldOf = (f) => f.value || ((r) => r[f.key]);
  const searchText = (r) => {
    let t = texts.get(r);
    if (t == null) { t = cols.map((c) => textOf(cell(c, r))).join("\u0001").toLowerCase(); texts.set(r, t); }
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
    const order = query.sort.length ? query.sort : sortKey ? [{ field: sortKey, direction: opts.dir || (cols.find((c) => c.key === sortKey)?.num ? "desc" : "asc") }] : [];
    if (order.length) {
      const keys = order.map((s) => [cols.find((c) => c.key === s.field), s.direction === "desc" ? -1 : 1]).filter(([c]) => c);
      out = out.slice().sort((a, b) => {
        for (const [c, dir] of keys) {
          const x = value(c, a), y = value(c, b);
          if (x == null && y == null) continue;
          if (x == null) return 1;  // not recorded: last, whichever way
          if (y == null) return -1;
          const d = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
          if (d) return d * dir;
        }
        return 0;
      });
    }
    return out;
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
  wrap.append(host);
  const dl = file ? h("button", { type: "button", class: "btn", html: ICON.download, "aria-label": `Download ${caption || "these rows"} as CSV` }, "CSV") : null;
  if (dl) {
    wrap.append(h("div", { class: "sk-grid-tools" }, dl));
    dl.addEventListener("click", () => download(file, csv(cols, filterAll(api.query))));
  }

  const segCounts = segments.map((s) => ({ id: s.id, label: s.label, count: s.test ? rows.filter(s.test).length : rows.length }));
  const api = createDataGrid(host, {
    namespace: ns,
    params: HASH,
    columns: cols.map((c) => ({ id: c.key, label: c.label, sortable: c.sortable !== false, align: alignOf(c), render: (r) => cell(c, r) })),
    filters: filters.map((f) => ({ id: f.key, label: f.label, type: "enum", options: optionsOf(f) })),
    segments: segCounts,
    getRowId: rowId || ((r) => rows.indexOf(r)),
    emptyMessage: opts.empty || "Nothing recorded.",
    searchPlaceholder: opts.placeholder || `Search ${caption ? caption.toLowerCase() : "rows"}`,
    async load(query) {
      const all = filterAll(query);
      onFiltered?.(all, query);
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
      if (e.key !== "Enter" || !e.target.matches?.("tbody tr")) return;
      const row = rowAt(e.target);
      if (row) { e.preventDefault(); onRow(row); }
    });
    const focusable = () => host.querySelectorAll(".dg-table tbody tr:not([tabindex])").forEach((tr) => { tr.tabIndex = 0; });
    const mo = new MutationObserver(focusable);
    mo.observe(host, { childList: true, subtree: true });
    focusable();
    wrap.addEventListener("sk-grid:gone", () => mo.disconnect());
  }

  REGISTRY.push({ caption, file, columns: cols, rows: () => filterAll(api.query) });

  wrap.api = api;
  wrap.filtered = () => filterAll(api.query);
  wrap.update = (next) => { rows = next || []; texts = new WeakMap(); api.refresh(); };
  wrap.destroy = track(wrap, () => { api.destroy(); wrap.dispatchEvent(new Event("sk-grid:gone")); });
  return wrap;
}
