// Leads & sales > Leads: the other shapes of the same leads (2.20), beside the List
// (sa-leads.js). Each uses the same options (What, Label, Source) and never a count of its
// own: the board shows the rows the list holds; the timeline and the map draw the Leads
// figure itself, from conversions.json's checked days (the same sums as Summary and
// Overview), so the views never disagree with the figure.
//
//   board(rows, names, open)   the period's leads in columns by stage now, one card each;
//                              read-only: stages come from the site's tools, never from Skald
//   timeline(m, s, r)          leads per day, stacked by what they did or by source (lsplit);
//                              a day's bar opens the List on that day
//   map(m, s, r)               leads by country, with the same figures in a table beside it

import { h, n, short } from "../ui.js";
import * as S from "../state.js";
import { chartDays } from "../data.js";
import { columns, legend } from "../charts.js";
import { table } from "../table.js";
import { time as tzTime } from "../tz.js";
import { info } from "./tiles.js";
import { actionName, oneAction, toolName, labelTag, convFile } from "./leadfigs.js";
import { worldMap } from "./rt-map.js";
import { countryWords } from "./readers.js";
import { choice } from "./sa-options.js";

const GROUPS = [["open", "New or open"], ["won", "Won"], ["lost", "Lost"], ["cancelled", "Cancelled or no-show"]];
const groupOf = (now) => (now === "won" ? "won" : now === "lost" ? "lost" : now === "cancelled" || now === "no_show" ? "cancelled" : "open");
const TONES = ["var(--g-people)", "var(--g-search_engines)", "var(--g-answer_engines)", "var(--g-bots)", "var(--leads)", "var(--g-ours)", "var(--ink-3)"];
const when = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");

// ------------------------------------------------------------------- board

export function board(rows, names, open) {
  const cols = GROUPS.map(([k, words]) => {
    const mine = rows.filter((x) => !x.left_out && groupOf(x.now) === k);
    return h("section", { class: "bd-col", "aria-label": words }, h("h3", { class: "bd-h" }, words),
      mine.length ? h("ul", { class: "bd-cards" }, mine.map((x) => h("li", null, h("button", { type: "button", class: "bd-card", onclick: () => open(x) },
        names && (x.name || x.email) ? h("b", { class: "bd-who" }, x.name || x.email) : null,
        names && x.name && x.email ? h("span", { class: "bd-mail" }, x.email) : null,
        h("span", { class: "bd-what" }, oneAction(x.action || ""), labelTag(x.label)),
        h("span", { class: "bd-meta" }, [x.source || "Source not recorded", toolName(x.tool || ""), when(x.at)].join(" · ")))))) : h("p", { class: "empty" }, "None."));
  });
  const out = rows.filter((x) => x.left_out);
  return [h("div", { class: "bd-top" }, h("span", { class: "note" }, "Each lead in the column of its stage now."),
    info("Read-only: a lead's stage comes from the site's tools (its lead database, the booking tool, its CRM). Skald shows it and never changes it.", "The board")),
  h("div", { class: "bd" }, cols),
  out.length ? h("p", { class: "note" }, `${n(out.length)} left out (test, spam or duplicate) are in the List, marked.`) : null];
}

// ---------------------------------------------------------------- timeline

// The figure's days for the period, in the shape charts.js columns() draws.
function chartOf(f, r) {
  const at = new Map((f.days || []).map((d) => [d.day, d]));
  return chartDays(r).map((d) => {
    const e = at.get(d.day);
    if (e?.state === "ok") return { ...e, state: "ok" };
    if (e?.state === "withheld") return { day: d.day, state: "withheld" };
    return { day: d.day, state: !e || e.state === "before" ? "before" : "missing" };
  });
}

/* m: the model with the Leads figure's file for the filters on (sa-filters.js figureFile:
   What, Label and at most one breakdown already applied); fig.dim: the breakdown applied. */
export function timeline(m, s, r, fig = {}) {
  const f = convFile(m);
  const split = s.lsplit === "source" ? "source" : "what";
  const switcher = choice("Split by", split, [["what", "What they did"], ["source", "Source"]], (k) => S.set({ lsplit: k === "what" ? "" : k }));
  if (!f) return null;
  if (r.kind === "today" || r.length < 2) {
    return [h("div", { class: "sa-viewbar" }, switcher), h("div", { class: "sa-empty" }, h("p", null, "The timeline needs a period of two days or more."),
      h("button", { type: "button", class: "btn primary", onclick: () => S.set({ range: "30d" }) }, "Show the last 30 days"))];
  }
  // By source needs the sources: a label or another breakdown leaves none to split by (2.23:
  // before, the chart came out empty, as if there were no lead).
  if (split === "source" && (s.llabel || (fig.dim && fig.dim !== "source_type"))) {
    return [h("div", { class: "sa-viewbar" }, switcher), h("p", { class: "empty" },
      `Leads per day by source cannot be shown with ${s.llabel ? "a label" : "this filter"} on: the figure keeps each breakdown on its own. Split by what they did, or remove the filter.`)];
  }
  const fin = new Set(f.finished || ["completed", "paid"]), lead = (f.lead_actions || []);
  const days = chartOf(f, r);
  let series;
  if (split === "what") {
    // Each action's completed leads that day: the figure's file is already narrowed to the
    // filters on (a source, a country, a device or a campaign: by[dim], sa-filters.js).
    series = lead.map((a, i) => ({ name: actionName(a), color: TONES[i % TONES.length],
      get: (d) => Object.entries(d.stages?.[a] || {}).reduce((x, [st, v]) => x + (fin.has(st) ? v : 0), 0) }));
  } else {
    const total = {};
    for (const d of days) if (d.state === "ok") for (const a of lead) for (const [k, v] of Object.entries(d.by?.source_type?.[a] || {})) total[k] = (total[k] || 0) + v;
    const top = Object.keys(total).filter((k) => total[k] && (!s.lby || k === s.lby)).sort((a, b) => total[b] - total[a]);
    const shown = top.slice(0, 6), rest = top.slice(6);
    const sum = (d, keys) => lead.reduce((x, a) => x + keys.reduce((y, k) => y + (d.by?.source_type?.[a]?.[k] || 0), 0), 0);
    series = [...shown.map((k, i) => ({ name: k === "Unknown" ? "Not recorded" : k, color: TONES[i % TONES.length], get: (d) => sum(d, [k]) })),
      ...(rest.length ? [{ name: "Other sources", color: "var(--ink-3)", get: (d) => sum(d, rest) }] : [])];
  }
  series = series.filter((x) => days.some((d) => d.state === "ok" && x.get(d)));
  return [h("div", { class: "sa-viewbar" }, switcher),
    h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not recorded", "", "hatch"]]),
      columns(days, series, { label: "Leads per day", unit: "leads", H: 240, onPick: (d) => S.set({ lview: "", range: "custom", from: d.day, to: d.day }) })),
    h("p", { class: "note" }, `Leads per day: the Leads figure of each day${split === "source" ? ", by the source of the visit they came in on (last touch)" : ""}. A hatched stub is a day not recorded, never zero. Press a day to list its leads.`)];
}

// --------------------------------------------------------------------- map

export function map(m, s, r) {
  const f = convFile(m);
  if (!f) return null;
  // A label's leads carry no country of their own (conversions.json counts labels by stage
  // only): said, never an empty map as if none had a country (2.23).
  if (s.llabel) return h("p", { class: "empty" }, "Leads by country are not split by label: choose Every label to see the map.");
  const days = new Set(r.kind === "today" ? [m.today] : r.days.map((d) => d.day));
  const lead = new Set(f.lead_actions || []);
  const by = {};
  let noCountry = 0;
  for (const e of f.days || []) {
    if (e.state !== "ok" || !days.has(e.day)) continue;
    for (const [a, per] of Object.entries(e.by?.country || {})) if (lead.has(a)) for (const [k, v] of Object.entries(per)) {
      if (/^[A-Za-z]{2}$/.test(k)) by[k.toUpperCase()] = (by[k.toUpperCase()] || 0) + v; else noCountry += v;
    }
  }
  const world = worldMap({ label: "World map of the period's leads", unit: "leads", live: false });
  world.update(Object.fromEntries(Object.entries(by).map(([k, v]) => [k, { visits: v, active: 0 }])));
  const rows = Object.entries(by).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ k, label: k, v }));
  return [h("div", { class: "cols sa-map" }, h("div", { class: "sheet" }, world.el),
    h("div", { class: "sheet" }, table([{ key: "label", label: "Country", fmt: (v) => countryWords(v), country: (x) => x.k }, { key: "v", label: "Leads", num: true }],
      { caption: "Leads by country", rows, file: "leads-by-country.csv", search: false, limit: 12, sortKey: "v", empty: "No lead with a known country in this period." }))),
  h("p", { class: "note" }, `Leads by the country of the visit they came in on: the Leads figure's own breakdown${noCountry ? `; ${n(noCountry)} without a country, not on the map` : ""}.${s.lby ? " Not split by source: every source is shown." : ""}${r.kind === "history" ? ` ${short(r.first)} to ${short(r.last)}.` : ""}`)];
}
