// Leads & sales > Leads: one filter system (2.23). Before, the Leads tab had three: the top
// bar's Filters (the whole dashboard's), the options row (What, Label, Stage now, Source,
// Show left out) and the table's own Filter button. Now the options row is THE filter row,
// the table has no Filter button of its own, and every filter that is on, from either
// place, is one removable chip in a single "Filtered by" line under the row, with Clear all.
//
// What each filter narrows, honestly:
//   * the list (and the board): every filter, row by row (sa-leads.js keepRows)
//   * the Leads figure (the count line, the timeline, the map, the empty state's counts):
//     What and Label (sa-pipeline.js narrowConv), and ONE breakdown at a time: the lead's
//     source (Source, or the dashboard's Source filter), country, device or campaign, from
//     conversions.json's own `by` tables (finished rows only, recounted by the second
//     count). Breakdowns are kept each on its own, never crossed, so two at once, or a
//     breakdown with a Label, cannot be counted: the line then says so and counts the rows
//     listed instead, never a figure that is not there. Stage now and Show left out are the
//     list's own (the figure counts a lead when it came in, test rows never).
//   * the dashboard filters a lead does not carry (a page read, a browser, a referring site,
//     the advanced rules) are chips too, greyed, with the reason: never silently ignored.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { fromState, toState, singles, ruleWords, leaves, NR, NONE } from "../rules.js";
import { shown } from "../labels.js";
import { countryName, withFlag } from "./readers.js";
import { actionName, convFile } from "./leadfigs.js";
import { narrowConv } from "./sa-pipeline.js";

// The dashboard's single filters a lead row carries: state key -> [row field, conversions.json `by` dim].
export const LEAD_DIMS = { source: ["source", "source_type"], country: ["country", "country"], device: ["device", "device"], campaign: ["campaign", "campaign"] };
const GLOBAL_WORDS = { source: "Source", country: "Country", device: "Device", campaign: "Campaign" };
export const STAGE_WORDS = { open: "New or open", won: "Won", lost: "Lost", cancelled: "Cancelled or no-show", out: "Left out" };

const sourceWords = (v) => (v === "Unknown" ? "Not recorded" : shown(v));
const valueWords = (dim, v) => (v === NR ? "Not recorded" : v === NONE ? "None" : dim === "country" ? withFlag(String(v).toUpperCase(), countryName(String(v).toUpperCase())) : shown(v));

/* Every filter that is on, in one list: {id, field, value, applied, why, drop (a state patch)}.
   applied: false (the chip greyed, why said) for a dashboard filter a lead does not carry,
   and for what the view on screen cannot apply: the timeline and the map count a lead when it
   came in (not by its stage now, never a left-out row); the map counts by country alone. */
export function activeFilters(s, view = "list") {
  const out = [];
  const counted = view === "timeline" || view === "map";
  const NOW = counted ? `Not applied in the ${view}: it counts a lead when it came in, not by its stage now.` : "";
  const BY = view === "map" ? "Not applied on the map: leads by country are not split by another breakdown." : "";
  const add = (x, why = "") => out.push({ ...x, applied: !why, why: why || x.why });
  if (s.lact) add({ id: "lact", field: "What", value: actionName(s.lact), drop: { lact: "", llabel: "" } });
  if (s.llabel) add({ id: "llabel", field: "Label", value: s.llabel, drop: { llabel: "" } });
  if (s.lnow) add({ id: "lnow", field: "Stage now", value: STAGE_WORDS[s.lnow] || s.lnow, drop: { lnow: "", ...(s.lnow === "out" ? { lshow: "" } : {}) } }, NOW);
  if (s.lby) add({ id: "lby", field: "Source", value: sourceWords(s.lby), drop: { lby: "" } }, BY);
  if (String(s.lshow || "").split(",").includes("out") && s.lnow !== "out") add({ id: "lshow", field: "Show", value: "Left out too", drop: { lshow: "" } }, NOW);
  // The dashboard's filters (the top bar's Filters), each top rule or group on its own.
  const tree = fromState(s);
  const one = new Map([...singles(tree, { tidied: true })].map(([k, x]) => [x, k]));
  for (const x of tree.items) {
    const k = one.get(x);
    const drop = toState({ mode: tree.mode, items: tree.items.filter((y) => y !== x) });
    if (k && LEAD_DIMS[k]) {
      add({ id: `g-${k}`, field: GLOBAL_WORDS[k], value: valueWords(x.dim, x.vals[0]), global: true, drop }, k === "country" ? "" : BY);
      continue;
    }
    const words = leaves({ items: [x] }).map((r) => { const w = ruleWords(r, valueWords); return `${w.field} ${w.op} ${w.val}`; }).join(" and ");
    out.push({ id: `g-${out.length}`, field: "Dashboard filter", value: words, applied: false, global: true, drop,
      why: "Not applied to leads: a lead carries its source, country, device and campaign, not this." });
  }
  return out;
}

// Clear all: every filter of the row and every dashboard filter.
export const CLEAR_ALL = { lact: "", llabel: "", lnow: "", lby: "", lshow: "", ...toState({ mode: "all", items: [] }) };

// "Source = Search engine · Country = Canada": what is applied, for the count line.
export const appliedWords = (list) => list.filter((x) => x.applied).map((x) => `${x.field} = ${x.value}`).join(" · ");

/* The one "Filtered by" line: a chip per filter, each with ×, and Clear all. Nothing when
   no filter is on. */
export function filteredBy(list, set = S.set) {
  if (!list.length) return null;
  const chips = list.map((x) => h("span", { class: `chip${x.applied ? "" : " off"}${x.global ? " glob" : ""}`, title: x.why || (x.global ? "A dashboard filter: it applies on every tab" : null) },
    `${x.field} `, h("span", { class: "chip-op" }, x.applied ? "=" : ":"), " ", h("b", null, x.value),
    h("button", { type: "button", "aria-label": `Remove the filter ${x.field} ${x.value}`, onclick: () => set(x.drop) }, "×")));
  const off = list.filter((x) => !x.applied);
  return h("div", { class: "sa-filtered", role: "group", "aria-label": "Filtered by" },
    h("span", { class: "sa-filtered-l" }, "Filtered by"), chips,
    h("button", { type: "button", class: "linkish sa-clear", onclick: () => set(CLEAR_ALL) }, "Clear all"),
    off.length ? h("span", { class: "vh" }, off.map((x) => x.why).join(" ")) : null);
}

// The breakdowns asked for (Source in the row, the dashboard's source, country, device,
// campaign) as [dim, value], each once.
export function breakdowns(s) {
  const out = [];
  const add = (dim, v) => { if (v && !out.some(([d, x]) => d === dim && x === v)) out.push([dim, v]); };
  if (s.lby) add("source_type", s.lby);
  for (const [k, [, dim]] of Object.entries(LEAD_DIMS)) if (s[k]) add(dim, k === "country" ? String(s[k]).toUpperCase() : s[k]);
  return out;
}

/* One breakdown's leads as the figure: each checked day's finished rows of that value only
   (`by[dim][action][value]`, which adds up per action to the day's finished stages). The
   other breakdowns are emptied, so no part of the page can cross two of them. */
export function byBreakdown(f, dim, value) {
  const done = (f.finished || ["completed", "paid"])[0];
  const pick = (per) => Object.fromEntries(Object.entries(per || {}).map(([a, x]) => [a, x && value in x ? { [value]: x[value] } : {}]));
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d,
    stages: Object.fromEntries(Object.entries(d.by?.[dim] || {}).map(([a, x]) => [a, x && x[value] ? { [done]: x[value] } : {}])),
    abandoned: {}, labels: {}, labels_abandoned: {},
    by: Object.fromEntries(Object.keys(d.by || {}).map((k) => [k, k === dim ? pick(d.by[k]) : {}])) })) };
}

/* The file the Leads figure is counted from for these filters: {f, dim, why}. f is null (and
   why says so) when the figure cannot be split that way; dim names the one breakdown applied. */
export function figureFile(m, s) {
  const f = convFile(m);
  if (!f) return { f: null, dim: null, why: "" };
  const g = narrowConv(f, s);
  const asked = breakdowns(s);
  if (!asked.length) return { f: g, dim: null, why: "" };
  const name = (dim) => ({ source_type: "source", country: "country", device: "device", campaign: "campaign" }[dim] || dim);
  if (s.llabel) return { f: null, dim: null, why: `The Leads figure is not split by label and ${name(asked[0][0])} together.` };
  if (asked.length > 1) return { f: null, dim: null, why: `The Leads figure keeps each breakdown on its own: it is never split by ${asked.map(([d]) => name(d)).filter((x, i, a) => a.indexOf(x) === i).join(" and ")} at once.` };
  return { f: byBreakdown(g, asked[0][0], asked[0][1]), dim: asked[0][0], why: "" };
}

// The list's own filters (the figure counts a lead when it came in, test rows never).
export const listOnly = (s) => !!s.lnow || String(s.lshow || "").split(",").includes("out");

// "3 leads" / "1 lead".
export const leadsWord = (k) => `${n(k)} lead${k === 1 ? "" : "s"}`;
