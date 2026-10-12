// Pieces the AI & bots tabs share (2.7.0): a figure card, the per-day chart of one
// tier of AI fetches, a ranked list as a Data Grid, and a link to another tab of
// the section. Every figure comes from the same field as on the AI & crawlers page
// before 2.7.0 (bots.js); only where it shows changed.

import { h, n, counter, share } from "../ui.js";
import { color, ranked, chartDays } from "../data.js";
import { columns, legend } from "../charts.js";
import * as S from "../state.js";
import { grid } from "../grid.js";
import { table } from "../table.js";
import { compareFor } from "./common.js";

/* One figure card, as bots.js drew them. v null: not recorded, shown as "-", never 0. */
export function kpi(first, label, v, note, group, unit = "pages fetched") {
  return h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note),
    h("div", { class: "k-v" }, v == null ? "-" : first ? counter(v) : n(v)),
    h("div", { class: "k-c" }, h("span", { class: "sw", style: { background: color(group) } }), unit));
}

/* AI pages fetched per day for one tier (days `tiers`), with the compare ghost. */
export function tierChart(m, s, r, { title, name, tier, group, label }) {
  if (r.kind !== "history" || r.length < 2) return null;
  const series = [{ name, color: color(group), get: (d) => d.tiers?.[tier] || 0 }];
  const cmp = compareFor(m, s);
  return h("section", { class: "s" }, h("h2", null, title), cmp.note,
    h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"], ...cmp.legend]),
      columns(chartDays(r), series, { label, unit: "fetches", H: 220, prev: cmp.prev })));
}

// A list longer than this is a Data Grid; a shorter one stays a plain table (no search or pages to page).
export const LONG = 12;

/* A {label: n} breakdown: label, any extra columns, the count and its share of the
   rows the filter keeps (as common.js countTable). A long one is a Data Grid, its
   search, sort and page in the address under `ns`; a short one a plain table. */
export function countGrid(ns, obj, { caption, file, key, value, keep, drill, empty, extra = [] }) {
  const rows = ranked(obj, keep).map(([k, v]) => ({ k, v, __k: k }));
  const sum = rows.reduce((a, x) => a + x.v, 0);
  const columns = [
    { key: "k", label: key, ...(drill ? { drill } : {}) },
    ...extra,
    { key: "v", label: value, num: true },
    { key: "share", label: "Share", num: true, sort: (x) => x.v, fmt: (_, x) => share(x.v, sum), csv: (x) => (share(x.v, sum) ? (x.v / sum).toFixed(4) : "") },
  ];
  if (rows.length <= LONG) return table(columns, { caption, rows, file, sortKey: "v", search: false, empty });
  return h("div", { class: "ai-g" }, grid({ ns, caption, file, rows, columns, sortKey: "v", empty, rowId: (x) => x.k }));
}

/* A link to another tab of AI & bots, keeping the period and page group. */
export function tabLink(s, tab, words) {
  return h("a", { href: S.hashFor({ ...s, tab: `ai/${tab}` }) }, words);
}
