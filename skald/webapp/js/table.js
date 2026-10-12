// Every table in the app: sort by any column, search its rows, download what
// it shows as CSV. The CSV holds the rows the filters and the search left,
// all of them, not only the ones on screen.

import { h, n, toast, reduced, ICON } from "./ui.js";
import { link } from "./drill.js";

/* Every table drawn in the current render, so "Export this view" and the
   report can take them all: {caption, file, columns, rows()}. main.js
   empties it before each render. */
export const REGISTRY = [];
// While a report is printed every row is shown, not only the first page of them.
let ALL_ROWS = false;
export function showAllRows(on) { ALL_ROWS = !!on; }

// A cell a spreadsheet would run as a formula is prefixed with an apostrophe,
// as export.py does for the server's files.
function cell(v) {
  let s = v == null ? "" : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function csv(columns, rows) {
  const head = columns.map((c) => cell(c.label)).join(",");
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

/* columns: [{key, label, num?, path?, cls?, title? (a hint on the header), fmt?(v,row), csv?(row), sort?(row), drill?: dimension}]
   opts: {caption, rows, file, limit=15, empty, sortKey, search=true, rowClass?(row), note, onRow?(row), placeholder,
          groups?: [[label, span]] - a header row above the columns that names groups of them}
   The returned element has update(rows): new rows, same sort and search. */
export function table(columns, opts) {
  const { caption, file, empty = "Nothing recorded.", search = true, rowClass, note, onRow } = opts;
  let rows = opts.rows;
  const limit = ALL_ROWS ? Infinity : opts.limit ?? 15;
  // A drillable column draws its value as a link to the value's detail, unless it formats it itself.
  columns = columns.map((c) => (c.drill && !c.fmt ? { ...c, fmt: (v) => (v == null || v === "" ? "" : link(c.drill, v)), csv: c.csv || ((r) => r[c.key]) } : c));
  let sortKey = opts.sortKey ?? columns.find((c) => c.num)?.key ?? null;
  let dir = opts.dir ?? (columns.find((c) => c.key === sortKey)?.num ? -1 : 1);
  let query = "", showAll = false;

  const wrap = h("div", { class: "tbl" });
  const count = h("span", { class: "tbl-count", "aria-live": "polite" });
  const input = search ? h("input", { type: "search", placeholder: opts.placeholder || "Search rows", "aria-label": `Search ${caption}` }) : null;
  const dl = file ? h("button", { type: "button", class: "btn", html: ICON.download }, "CSV") : null;
  if (dl) dl.setAttribute("aria-label", `Download ${caption} as CSV`);
  const thead = h("thead");
  const tbody = h("tbody");
  const tableEl = h("table", null, h("caption", { class: "vh" }, caption), thead, tbody);
  const more = h("button", { type: "button", class: "btn more-rows" });
  const tools = h("div", { class: "tbl-tools" }, input, h("span", { class: "grow" }), count, dl);
  wrap.append(tools, h("div", { class: "scroll" }, tableEl), more);
  if (note) wrap.append(h("p", { class: "note" }, note));

  const val = (c, r) => (c.sort ? c.sort(r) : r[c.key]);
  const filtered = () => {
    const q = query.trim().toLowerCase();
    const text = (c, r) => { const v = c.fmt ? c.fmt(r[c.key], r) : r[c.key] ?? ""; return v instanceof Node ? v.textContent : String(v); };
    let out = q ? rows.filter((r) => columns.some((c) => text(c, r).toLowerCase().includes(q))) : rows.slice();
    const c = columns.find((x) => x.key === sortKey);
    if (c) out.sort((a, b) => {
      const x = val(c, a), y = val(c, b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * dir;
    });
    return out;
  };

  function head() {
    const groups = opts.groups ? h("tr", { class: "grp-row" }, opts.groups.map(([l, span]) => h("th", { scope: l ? "colgroup" : null, colspan: span, class: l ? "colgrp" : null }, l || ""))) : null;
    thead.replaceChildren(...(groups ? [groups] : []), h("tr", null, columns.map((c) => {
      const sorted = c.key === sortKey;
      const th = h("th", { scope: "col", title: c.title || null, class: [c.num ? "n" : null, c.cls].filter(Boolean).join(" ") || null, "aria-sort": sorted ? (dir > 0 ? "ascending" : "descending") : null },
        h("button", { type: "button", onclick: () => { if (sorted) dir = -dir; else { sortKey = c.key; dir = c.num ? -1 : 1; } render(true); } },
          c.label, h("span", { class: "dir", "aria-hidden": "true" }, sorted && dir > 0 ? "▲" : "▼")));
      return th;
    })));
  }

  function render(animate = false) {
    const before = animate && !reduced() ? new Map([...tbody.children].map((tr) => [tr.dataset.k, tr.getBoundingClientRect().top])) : null;
    head();
    const all = filtered();
    const shown = showAll ? all : all.slice(0, limit);
    if (!rows.length) {
      tbody.replaceChildren(h("tr", null, h("td", { colspan: columns.length, class: "muted" }, empty)));
    } else if (!all.length) {
      tbody.replaceChildren(h("tr", null, h("td", { colspan: columns.length, class: "muted" }, "No row matches the search.")));
    } else {
      tbody.replaceChildren(...shown.map((r) => {
        const tr = h("tr", { class: rowClass ? rowClass(r) : null });
        if (onRow) {
          tr.tabIndex = 0;
          tr.addEventListener("click", (e) => { if (!e.target.closest("button,a")) onRow(r); });
          tr.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target === tr) { e.preventDefault(); onRow(r); } });
        }
        tr.dataset.k = r.__k ?? columns.map((c) => r[c.key]).join("|");
        for (const c of columns) {
          const v = r[c.key];
          const text = c.fmt ? c.fmt(v, r) : c.num ? n(v) : v ?? "";
          tr.append(h("td", { class: [c.num ? "n" : c.path ? "path" : null, c.cls].filter(Boolean).join(" ") || null }, text instanceof Node ? text : String(text)));
        }
        return tr;
      }));
    }
    count.textContent = rows.length ? (all.length === rows.length ? `${n(rows.length)} row${rows.length === 1 ? "" : "s"}` : `${n(all.length)} of ${n(rows.length)} rows`) : "";
    more.hidden = all.length <= limit;
    more.textContent = showAll ? "Show fewer" : `Show all ${n(all.length)}`;
    if (dl) dl.disabled = !all.length;
    if (before) [...tbody.children].forEach((tr) => {
      const was = before.get(tr.dataset.k);
      if (was == null) return;
      const dy = was - tr.getBoundingClientRect().top;
      if (!dy) return;
      tr.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 260, easing: "cubic-bezier(.2,.7,.2,1)" });
    });
  }

  input?.addEventListener("input", () => { query = input.value; render(); });
  more.addEventListener("click", () => { showAll = !showAll; render(); });
  dl?.addEventListener("click", () => download(file, csv(columns, filtered())));
  render();
  wrap.update = (next) => { rows = next; render(); };
  REGISTRY.push({ caption, file, columns, rows: filtered });
  return wrap;
}
