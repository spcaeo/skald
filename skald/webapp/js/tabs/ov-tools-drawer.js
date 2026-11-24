// "All figures from <tool>" (SKALD-55): one drawer with every figure a tool of your own gave
// Skald, opened from Overview's "From your tools" line (ov-tools.js), on Today and on a
// period. Its address: ytool=<id> (ytool=ga4), so a link, a reload and Back land on it.
//
//   the head      "Counted from: <tool>", its own days, its freshness, what it said about
//                 its answer (sampled, thresholded)
//   Totals        each total over the tool's own days, beside the days before ("previous")
//                 and the change, when the tool gave those
//   each table    channels, sources, landing pages, devices, countries, events (key events
//                 first), then any other report of another tool: the tool's own rows in its
//                 own order, each metric, and each row's share of the tool's own total
//
// Every figure is the tool's, as yourtools/api.py view gives it and yourtools/recount.py
// checks it; nothing here adds up anything but a row's share of the total the tool gave.
// GET integrations/yourtools/figures (any member).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { openDrawer } from "../drawer.js";
import { pill } from "../ui/pill.js";
import { FIGURES_PATH, said, change } from "./ov-tools.js";

// The tables first people ask about, then the rest in the tool's own order.
const ORDER = ["channels", "sources", "landing", "devices", "countries", "events"];
const NOT_HERE = "That tool is not connected on this site, or its figures are not kept.";

const totalsOf = (rep) => (rep?.figures || []).filter((f) => f.dim == null);

/* A report's rows: [{dim, figs: {name: figure}}] in the tool's own order, and its metrics. */
export function rowsOf(rep) {
  const rows = new Map(), metrics = [];
  for (const f of rep.figures || []) {
    if (!metrics.some((x) => x.name === f.name)) metrics.push({ name: f.name, label: f.label, unit: f.unit });
    if (f.dim == null) continue;
    if (!rows.has(f.dim)) rows.set(f.dim, { dim: f.dim, rank: f.rank ?? rows.size, figs: {} });
    rows.get(f.dim).figs[f.name] = f;
  }
  return { metrics, rows: [...rows.values()].sort((a, b) => a.rank - b.rank) };
}

const share = (v, total) => (v == null || !total ? "" : `${((v / total) * 100).toFixed(v / total < 0.1 ? 1 : 0)}%`);

function totalsTable(t) {
  const now = totalsOf(t.reports?.totals), before = Object.fromEntries(totalsOf(t.reports?.previous).map((f) => [f.name, f]));
  if (!now.length) return null;
  const has = !!t.reports?.previous;
  const span = (r) => (r?.start ? `${r.start} to ${r.end}` : "");
  return h("section", { class: "yt-sec", "data-report": "totals" }, h("h3", null, "Totals"),
    h("div", { class: "scroll" }, h("table", { class: "yt-tbl" },
      h("thead", null, h("tr", null, h("th", { scope: "col" }, "Figure"),
        h("th", { scope: "col", class: "num" }, span(t.reports.totals) || "Its own days"),
        has ? h("th", { scope: "col", class: "num" }, span(t.reports.previous) || "The days before") : null,
        has ? h("th", { scope: "col", class: "num" }, "Change") : null)),
      h("tbody", null, now.map((f) => {
        const was = before[f.name]?.value ?? null;
        const c = has ? change(f.value, was, f.unit) : null;
        return h("tr", null, h("th", { scope: "row" }, f.label), h("td", { class: "num" }, said(f.value, f.unit)),
          has ? h("td", { class: "num" }, said(was, f.unit)) : null,
          has ? h("td", { class: `num yt-chg ${c ? c.dir : ""}` }, c ? c.text : "-") : null);
      })))));
}

function reportTable(key, rep, name) {
  const { metrics, rows } = rowsOf(rep);
  if (!rows.length) return null;
  const totals = Object.fromEntries(totalsOf(rep).map((f) => [f.name, f.value]));
  const first = metrics[0];
  const flags = rep.flags || [];
  return h("section", { class: "yt-sec", "data-report": key }, h("h3", null, rep.title || key),
    h("div", { class: "scroll" }, h("table", { class: "yt-tbl" },
      h("thead", null, h("tr", null, h("th", { scope: "col" }, rep.title || key),
        ...metrics.map((mt) => h("th", { scope: "col", class: "num" }, mt.label)),
        totals[first.name] ? h("th", { scope: "col", class: "num", title: `Each row's ${first.label.toLowerCase()} out of the total ${name} gave` }, "Share") : null)),
      h("tbody", null, rows.map((r) => h("tr", null, h("th", { scope: "row", class: "yt-dim" }, r.dim),
        ...metrics.map((mt) => h("td", { class: "num" }, said(r.figs[mt.name]?.value ?? null, mt.unit))),
        totals[first.name] ? h("td", { class: "num yt-share" }, share(r.figs[first.name]?.value ?? null, totals[first.name])) : null))),
      Object.keys(totals).length ? h("tfoot", null, h("tr", null, h("th", { scope: "row" }, `Total, as ${name} gave it`),
        ...metrics.map((mt) => h("td", { class: "num" }, said(totals[mt.name] ?? null, mt.unit))),
        totals[first.name] ? h("td", { class: "num" }, "100%") : null)) : null)),
    h("p", { class: "note" }, `The top ${rows.length} rows, in the order ${name} gave them; the total is the one ${name} gave, so the rows may add up to less.`,
      flags.length ? ` As ${name} said: ${flags.join("; ")}.` : ""));
}

/* The drawer's body: the tool's head, its totals, then each table. */
export function toolFigures(t) {
  const period = t.period ? `Its own ${t.period.start} to ${t.period.end}${t.period.note ? ` (${t.period.note})` : ""}.` : "No answer kept yet.";
  if (t.withheld) return [h("p", { class: "msg err" }, t.withheld)];
  const keys = Object.keys(t.reports || {}).filter((k) => k !== "totals" && k !== "previous");
  keys.sort((a, b) => (ORDER.includes(a) ? ORDER.indexOf(a) : 99) - (ORDER.includes(b) ? ORDER.indexOf(b) : 99));
  return [
    h("div", { class: "yt-head" }, h("p", null, h("b", null, t.counted_from), ". ", period, " These are its counts, never Skald's, and never added to Skald's figures."),
      h("p", { class: "yt-meta" }, pill(t.pill, t.words), h("small", null, ` Last answer ${t.ago}.`))),
    totalsTable(t),
    ...keys.map((k) => reportTable(k, t.reports[k], t.name)),
  ].filter(Boolean);
}

/* Open it for a tool already fetched (a click on the card). */
export function openToolFigures(t) {
  return openDrawer({ title: `${t.name}: all its figures`, subtitle: t.counted_from, size: "lg", key: "ytool", className: "yt-figs-dw",
    body: h("div", { class: "yt-figs-b" }, ...toolFigures(t)), route: { key: "ytool", value: t.id } });
}

/* Open it from the address (overlays.js): the tool's figures fetched first. */
export async function openToolKey(v) {
  if (!/^[a-z0-9_-]{1,30}$/.test(v)) return NOT_HERE;
  const r = await call(FIGURES_PATH);
  const t = r.ok && (r.tools || []).find((x) => x.id === v);
  return t ? openToolFigures(t) : NOT_HERE;
}
