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
import { compareFor, fileName } from "./common.js";

/* One figure card, as bots.js drew them. v null: not recorded, shown as "-", never 0. */
export function kpi(first, label, v, note, group, unit = "pages fetched") {
  return h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note),
    h("div", { class: "k-v" }, v == null ? "-" : first ? counter(v) : n(v)),
    h("div", { class: "k-c" }, h("span", { class: "sw", style: { background: color(group) } }), unit));
}

/* AI pages fetched per day for one tier (days `tiers`), with the compare ghost. */
export function tierChart(m, s, r, { title, name, tier, group, label, get, unit = "fetches" }) {
  if (r.kind !== "history" || r.length < 2) return null;
  const series = [{ name, color: color(group), get: get || ((d) => d.tiers?.[tier] || 0) }];
  const cmp = compareFor(m, s);
  return h("section", { class: "s" }, h("h2", null, title), cmp.note,
    h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"], ...cmp.legend]),
      columns(chartDays(r), series, { label, unit, H: 220, prev: cmp.prev })));
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

// What AI fetches asked for (app.json `ai_formats`, ai_formats.py), in this order.
const FORMATS = ["Page", "llms.txt", "Markdown", "Text", "robots.txt", "Sitemap", "Other file"];

/* "What they fetch": one tier's fetches by what the path names (a page, llms.txt, Markdown,
   ...), then by name. A range with a day counted before this existed shows no table: a sum
   of some of the days would not add up to the fetches above it. */
export function formatsSection(t, r, tier, { who, file }) {
  const title = h("h2", null, "What they fetch");
  const sub = h("p", { class: "sub" }, "Each fetch by what its address names: a page, llms.txt, a Markdown or text file, robots.txt, a sitemap, or another file (images, scripts, feeds, PDFs). The address decides, not what the server answered.");
  const missing = r.kind === "history" ? t.unmeasured?.ai_formats || 0 : 0;
  const got = t.ai_formats?.[tier];
  if (!got || missing) {
    const why = missing && missing < (t.days || 0) ? `${missing} of these ${t.days} days were collected before this was counted, so it is not shown for this range.` : "Not recorded for this range.";
    return h("section", { class: "s" }, title, sub, h("p", { class: "note" }, why));
  }
  const formats = got.formats || {};
  const sum = Object.values(formats).reduce((a, v) => a + v, 0);
  const rows = FORMATS.filter((k) => formats[k]).map((k) => ({ k, v: formats[k], __k: k }));
  const byFormat = table([
    { key: "k", label: "What", sortable: false },
    { key: "v", label: "Fetches", num: true },
    { key: "share", label: "Share", num: true, sort: (x) => x.v, fmt: (_, x) => share(x.v, sum), csv: (x) => (share(x.v, sum) ? (x.v / sum).toFixed(4) : "") },
  ], { caption: `What ${who} fetched`, rows, file: fileName(`${file}-by-format`, r), sortKey: "v", search: false, empty: `No ${who} fetches in this range.` });
  const shown = rows.map((x) => x.k);
  const named = Object.entries(got.by_name || {}).map(([name, c]) => ({ name, __k: name, ...Object.fromEntries(shown.map((k) => [k, c[k] || 0])), total: shown.reduce((a, k) => a + (c[k] || 0), 0) }));
  const byName = named.length ? table([
    { key: "name", label: who === "assistants" ? "Assistant" : "Crawler" },
    ...shown.map((k) => ({ key: k, label: k, num: true })),
    { key: "total", label: "Fetches", num: true },
  ], { caption: `What ${who} fetched, by name`, rows: named, file: fileName(`${file}-by-name`, r), sortKey: "total", search: false }) : null;
  // The second table has its own heading and room above it, not glued under the first.
  const nameHead = byName ? h("h3", { class: "ai-sub-h" }, who === "assistants" ? "By assistant" : "By crawler") : null;
  return h("section", { class: "s" }, title, sub, byFormat, nameHead, byName,
    named.some((x) => x.name === "(all others)") ? h("p", { class: "note" }, "Each day keeps the 20 names with the most fetches; the rest are summed in (all others), so the totals still add up.") : null);
}
