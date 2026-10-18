// What every table and grid shares that is not drawing: the order rows sort in,
// the per-column filters, and how both are kept in the address. Pure, so node runs
// it (tests/js/tables.mjs); table.js and grid.js draw with it.
//
// In the hash, beside the route's own keys, each table keeps its state under its
// namespace (a grid's ns, a table's caption made short):
//   eachvisit_sort=pages:desc       the column and direction (none: the table's default)
//   eachvisit_cf=pages:ge:3;src:has:google;device:in:Mobile|Tablet
//   eachvisit_hide=browser,path     columns taken away with the column chooser
//   eachvisit_q=pricing             the search box
// state.js carries these keys while the tab stays (TABLE_KEY), as it does a grid's.

import { URL_SUFFIX } from "../vendor/spcaeo-ui/data-grid/core/url-state.js";

// A table's own keys: the data grid's suffixes, plus the column filters and the chooser's.
export const EXTRA_SUFFIX = ["cf", "hide"];
export const TABLE_KEY = new RegExp(`^[a-z][a-z0-9]*_(?:${[...Object.values(URL_SUFFIX), ...EXTRA_SUFFIX].join("|")})$`);

// ---- reading and writing the hash's query, where every Skald key lives ------------
function split() {
  const raw = location.hash.replace(/^#/, "");
  const at = raw.indexOf("?");
  return at < 0 ? [raw, ""] : [raw.slice(0, at), raw.slice(at + 1)];
}
// Writing keeps the route and every other key and never fires hashchange, so a
// table's change does not redraw the page.
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
// Set (or, for "" and null, remove) some keys in the hash at once.
export function writeKeys(patch) {
  const p = HASH.read();
  for (const [k, v] of Object.entries(patch)) { if (v == null || v === "") p.delete(k); else p.set(k, v); }
  HASH.write(p);
}

// A namespace from a caption: "Each visit" -> "eachvisit". Lower-case letters and digits,
// a letter first, at most 14; `taken` (the namespaces drawn so far) makes it unique.
export function nsOf(caption, taken = []) {
  let base = String(caption || "").toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 14);
  if (!/^[a-z]/.test(base)) base = `t${base}`.slice(0, 14);
  let ns = base, i = 2;
  while (taken.includes(ns)) ns = `${base}${i++}`;
  return ns;
}

// ---- order ------------------------------------------------------------------------
/* A value nobody recorded sorts last, whichever way: null, "", "-", "Not recorded",
   "Unknown", "(none)". Numbers by size, dates by time (an ISO date or time sorts as
   itself; other dates through Date.parse), words in natural order ("page 2" before "page 10"). */
const NONE = new Set(["", "-", "—", "not recorded", "unknown", "(none)", "(not set)"]);
export const unrecorded = (v) => v == null || (typeof v === "number" && Number.isNaN(v)) || (typeof v === "string" && NONE.has(v.trim().toLowerCase()));

const collator = typeof Intl !== "undefined" ? new Intl.Collator("en", { numeric: true, sensitivity: "base" }) : null;
const ISOISH = /^\d{4}-\d\d-\d\d/;
export function timeOf(v) {
  if (typeof v === "number") return v;
  if (v instanceof Date) return v.getTime();
  const s = String(v);
  if (ISOISH.test(s)) return s;  // ISO strings sort as themselves (local times have no zone to parse)
  const t = Date.parse(s);
  return Number.isNaN(t) ? s : t;
}

// -1, 0 or 1 for two values, ascending; "date" compares as times.
export function compare(x, y, type) {
  const nx = unrecorded(x), ny = unrecorded(y);
  if (nx || ny) return nx && ny ? 0 : nx ? 1 : -1;
  if (type === "date") { x = timeOf(x); y = timeOf(y); }
  if (typeof x === "number" && typeof y === "number") return x === y ? 0 : x < y ? -1 : 1;
  if (typeof x === "boolean" && typeof y === "boolean") return x === y ? 0 : x ? -1 : 1;
  const a = String(x), b = String(y);
  return collator ? collator.compare(a, b) : a.localeCompare(b);
}

/* Rows in order: keys [{get(row), type, dir: 1|-1}]. Unrecorded values last in either
   direction; ties keep the rows' own order (a stable sort). */
export function sortRows(rows, keys) {
  if (!keys.length) return rows.slice();
  return rows.map((r, i) => [r, i]).sort((a, b) => {
    for (const k of keys) {
      const x = k.get(a[0]), y = k.get(b[0]);
      const nx = unrecorded(x), ny = unrecorded(y);
      if (nx || ny) { if (nx && ny) continue; return nx ? 1 : -1; }
      const d = compare(x, y, k.type);
      if (d) return d * k.dir;
    }
    return a[1] - b[1];
  }).map(([r]) => r);
}

// A column's first direction: numbers and dates biggest or newest first, words A to Z.
export const firstDir = (c) => (c.num || c.type === "num" || c.type === "date" ? -1 : 1);

/* A header click: asc, desc, then the table's default order again.
   sort: {key, dir} chosen, or null (the default); def: the default {key, dir} or null. */
export function nextSort(sort, c, def) {
  const first = firstDir(c);
  if (!sort) return def && def.key === c.key && def.dir === first ? { key: c.key, dir: -first } : { key: c.key, dir: first };
  if (sort.key !== c.key) return { key: c.key, dir: first };
  if (sort.dir === first && !(def && def.key === c.key && def.dir === -first)) return { key: c.key, dir: -first };
  return null;
}
export const sortParam = (sort) => (sort ? `${sort.key}:${sort.dir > 0 ? "asc" : "desc"}` : "");
export function readSort(v, keys) {
  const m = /^([^:]+):(asc|desc)$/.exec(v || "");
  return m && keys.includes(m[1]) ? { key: m[1], dir: m[2] === "asc" ? 1 : -1 } : null;
}

// ---- per-column filters -------------------------------------------------------------
/* What a column's filter is: "num" (a lowest and a highest value), "enum" (pick some of
   its values), "text" (contains), or null (none). A column says it with `filter`; else
   numbers are "num", tags and yes/no "enum", a column with few distinct values "enum". */
export function filterKind(c, distinct = Infinity) {
  if (c.filter === false) return null;
  if (c.filter) return c.filter;
  if (c.num || c.type === "num") return "num";
  if (c.type === "badge" || c.type === "bool") return "enum";
  if (c.type === "date") return "text";
  return distinct <= 8 ? "enum" : "text";
}

// The words "1 min", "90 s", "2:30", "1h 5m" in seconds; a bare number as it is.
export function parseAmount(s) {
  const t = String(s ?? "").trim().toLowerCase().replace(/,/g, "");
  if (!t) return null;
  if (/^-?\d+(\.\d+)?%?$/.test(t)) return Number(t.replace("%", ""));
  const mmss = /^(\d+):(\d\d)$/.exec(t);
  if (mmss) return Number(mmss[1]) * 60 + Number(mmss[2]);
  const re = /(\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|m|min|mins|minutes?|s|sec|secs|seconds?)\b/g;
  let total = 0, any = false, m;
  while ((m = re.exec(t))) { any = true; const u = m[2][0]; total += Number(m[1]) * (u === "h" ? 3600 : u === "m" ? 60 : 1); }
  return any ? total : null;
}

/* A filter: {key, op: "has"|"in"|"range", value: text | [values] | [lo, hi]}.
   test(f, cell): cell = {num, text} - num the column's number, text what the cell shows. */
export function testFilter(f, cell) {
  if (f.op === "has") return String(cell.text || "").toLowerCase().includes(String(f.value).toLowerCase());
  if (f.op === "in") return f.value.includes(String(cell.text ?? "").trim());
  if (f.op === "range") {
    const [lo, hi] = f.value;
    if (unrecorded(cell.num) || typeof cell.num !== "number") return false;  // not recorded: never in a range
    return (lo == null || cell.num >= lo) && (hi == null || cell.num <= hi);
  }
  return true;
}
export const filterOn = (f) => (f.op === "has" ? String(f.value).trim() !== "" : f.op === "in" ? f.value.length > 0 : f.op === "range" ? f.value.some((x) => x != null) : false);

const esc = (s) => encodeURIComponent(String(s));
export function writeFilters(list) {
  return list.filter(filterOn).map((f) => {
    if (f.op === "has") return `${f.key}:has:${esc(f.value)}`;
    if (f.op === "in") return `${f.key}:in:${f.value.map(esc).join("|")}`;
    return `${f.key}:range:${f.value.map((x) => (x == null ? "" : x)).join("..")}`;
  }).join(";");
}
export function readFilters(v, keys) {
  const out = [];
  for (const part of String(v || "").split(";")) {
    const m = /^([^:]+):(has|in|range):(.*)$/.exec(part);
    if (!m || !keys.includes(m[1])) continue;
    try {
      if (m[2] === "has") out.push({ key: m[1], op: "has", value: decodeURIComponent(m[3]) });
      else if (m[2] === "in") out.push({ key: m[1], op: "in", value: m[3].split("|").map(decodeURIComponent).filter((x) => x !== "") });
      else {
        const [lo, hi] = m[3].split("..").map((x) => (x === "" || x == null || Number.isNaN(Number(x)) ? null : Number(x)));
        out.push({ key: m[1], op: "range", value: [lo ?? null, hi ?? null] });
      }
    } catch { /* a garbled value: left out */ }
  }
  return out.filter(filterOn);
}
export const readHidden = (v, keys) => String(v || "").split(",").filter((k) => keys.includes(k));

// ---- the CSV of what is on screen -----------------------------------------------------
// Columns as shown, rows as filtered and sorted: the caller passes both already in order.
export function visibleColumns(columns, hidden) {
  const set = new Set(hidden);
  return columns.filter((c) => !set.has(c.key));
}
