// Traffic > Sources (2.7.0): where visitors came from, in one grid.
//
// One Data Grid, three segments: Source type (by.source), Referring site
// (by.referrer) and Campaign (by.campaign). Each segment is its own breakdown,
// stored apart in the log, so the segments are never added together and each
// share is over its own list (as the lists they replace: the source types over
// the range's visitors, the sites and campaigns over their own sum).
// It replaces Traffic sources, Each source over time, All sources with their leads,
// Referring sites, All referring sites and Campaigns: the same figures, in one place.
//
// Below it: Campaigns and referrers (campaigns.json: UTM tags, referring sites down
// to the page, paid networks, tag problems). AI visits live under AI & bots > Assistants
// (owner's decision, 2026-10-12): this tab links there. Landing pages live on Pages.

import { h, change } from "../ui.js";
import { color, figures, previousOf, total, coverage, chartDays } from "../data.js";
import { spark } from "../charts.js";
import * as S from "../state.js";
import { grid } from "../grid.js";
import { head, nothing, fileName } from "./common.js";
import { campaigns } from "./campaigns.js";
import { leadsBy, leadNote, viewNote } from "./leadfigs.js";
import { leadRows, labelCol, countCols, leadCols, goTo, compareOf, compareRows, compareCols, compareNote } from "./tr-grid.js";

const TOUCH = "last touch: the source of the visit the lead was sent from";
const only = (value) => (value ? (k) => k === value : () => true);

export const SEGMENTS = [
  { id: "type", label: "Source type", dim: "source", noLeads: null },
  { id: "site", label: "Referring site", dim: "referrer", noLeads: "Leads are split by source type only, not by referring site" },
  { id: "campaign", label: "Campaign", dim: "campaign", noLeads: "Leads are split by source type only, not by campaign" },
];

/* The previous range, when this one may be compared with it: both whole and verified,
   both with breakdowns (readers.js changes() and trendTable()'s rule). */
function before(m, r, cov) {
  const prev = previousOf(m, r);
  if (!prev || !cov?.complete || !coverage(prev).complete) return null;
  const p = total(prev.days);
  return p && !p.unmeasured?.by ? p : null;
}

/* The grid's columns: the one place they are defined (compare mode adds B and ± here).
   Before, Change and the working/dropped/new chip are the source types' only, as
   "Each source over time" had them, and only when the range before is comparable;
   Per day only over several days. */
export function sourceColumns({ prev, perDay, leads, c }) {
  const cols = [labelCol("Source"), ...countCols("Visitors"), ...compareCols(c)];
  if (prev) cols.push(
    { key: "before", label: "Before", num: true, csv: (x) => x.before ?? "" },
    { key: "chg", label: "Change", num: true, sort: (x) => (x.before ? (x.v - x.before) / x.before : null),
      fmt: (_, x) => { if (x.before == null) return "-"; const [a, w] = change(x.v || 0, x.before); return `${a}${a ? " " : ""}${w}`; },
      csv: (x) => (x.before == null ? "" : change(x.v || 0, x.before)[1]) },
    { key: "chip", label: "Trend", sortable: false, fmt: (v) => (v ? h("span", { class: `trend-chip ${v}` }, v) : ""), csv: (x) => x.chip || "" });
  if (perDay) cols.push({ key: "trend", label: "Per day", sortable: false,
    fmt: (v) => (v && v.filter((x) => x != null).length > 1 ? spark(v, color("people")) : "-"), csv: (x) => (x.trend || []).join(" ") });
  if (leads) cols.push(...leadCols());
  return cols;
}

export function sourceRows(m, s, r, t, cov) {
  const lb = leadsBy(m, s, r, t, "source");
  // Compare mode: B and ± take the place of Before, Change and the trend chip.
  const c = compareOf(m, s);
  const p = c.ok ? null : before(m, r, cov);
  const days = r.kind === "history" ? chartDays(r) : [];
  const types = leadRows(t.by.source, lb, { dim: "source", keep: only(s.source), whole: t.readers });
  for (const x of types) {
    x.seg = "type";
    // A row with leads but no visitor in the list (Not recorded) has no trend: "-", as before.
    if (x.v == null) { x.before = null; x.chip = ""; x.trend = null; continue; }
    x.before = p ? p.by?.source?.[x.k] || 0 : null;
    x.chip = "";
    if (x.before === 0 && x.v > 0) x.chip = "new";
    else if (x.before > 0) { const pc = ((x.v || 0) - x.before) / x.before; x.chip = pc >= 0.2 ? "working" : pc <= -0.2 ? "dropped" : ""; }
    x.trend = days.map((d) => (d.state === "ok" && d.by ? d.by.source?.[x.k] || 0 : null));
  }
  const other = (seg, obj, keep) => leadRows(obj, null, { dim: seg.dim, keep, noLeads: seg.noLeads }).map((x) => ({ ...x, seg: seg.id }));
  const bBy = c.ok ? c.bT?.by || {} : {};
  return {
    lb, prev: !!p, perDay: r.kind === "history" && r.length > 1, c,
    rows: [...compareRows(c, types, bBy.source, { dim: "source", keep: only(s.source), whole: t.readers }),
      ...compareRows(c, other(SEGMENTS[1], t.by.referrer, only(s.referrer)), bBy.referrer, { dim: "referrer", keep: only(s.referrer) }),
      ...compareRows(c, other(SEGMENTS[2], t.by.campaign, only(s.campaign)), bBy.campaign, { dim: "campaign", keep: only(s.campaign) })],
  };
}

function unmeasured(t) {
  return t.unmeasured?.by ? h("p", { class: "note" }, `${t.unmeasured.by} of these days were collected before breakdowns existed. They are left out of every list here, so the lists add up to fewer visitors than the headline.`) : null;
}

// Campaigns and referrers, without its "Sent by an AI assistant" card: AI visits live under AI & bots.
function campaignParts(m, s, r) {
  const box = campaigns(m, s, r);
  for (const card of box.querySelectorAll?.(".sheet") || []) {
    if (card.querySelector("h3")?.textContent !== "Sent by an AI assistant") continue;
    const row = card.parentElement;
    card.remove();
    if (row?.classList.contains("cols") && row.children.length === 1) row.classList.add("tr-one");
  }
  return box;
}

export default function sources(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Sources", r, "Where visitors came from, by the referrer of the first page they read. Referrers are often stripped, so Direct includes everyone whose browser did not say. Source types, referring sites and campaigns are stored apart, so each segment adds up on its own and they are never added together.")];
  if (!t || !t.by) return [...out, nothing(m, r, "sources")];
  const { lb, prev, perDay, rows, c } = sourceRows(m, s, r, t, cov);
  const leads = !!(lb && lb.days);
  // The segment on show, for the styles: a referring site or a campaign has no
  // trend or lead split, so only its label, visitors and share are shown.
  const box = h("div", { class: "tr-src", "data-seg": "type" });
  const g = grid({
    ns: "src", caption: "Sources", file: fileName("sources", r),
    columns: sourceColumns({ prev, perDay, leads, c }),
    rows,
    segments: SEGMENTS.map((x) => ({ id: x.id, label: x.label, test: (row) => row.seg === x.id })),
    sortKey: "v",
    placeholder: "Search sources, sites, campaigns",
    empty: "No visitor recorded for this segment.",
    onFiltered: (_, q) => { box.dataset.seg = q.segment || SEGMENTS[0].id; },
  });
  g.classList.add("tr-grid", "lead-tbl");
  box.append(g);
  const ai = S.hashFor({ ...s, tab: "ai/assistants", dd: "" });
  out.push(h("section", { class: "s" }, h("h2", null, "Sources"),
    h("p", { class: "sub" }, c.ok
      ? "Visitors by source type, referring site or campaign, in A against B. Each segment is its own list."
      : prev
      ? "Visitors by source type, referring site or campaign. Before, Change and the trend compare source types with the range before, only when both are fully verified; a change under 20% is not called either way."
      : "Visitors by source type, referring site or campaign. Each segment is its own list."),
    box,
    compareNote(c),
    lb ? leadNote(lb, TOUCH) : null,
    leads ? h("p", { class: "note" }, "Leads are split by source type only, so referring sites and campaigns list their visitors alone.") : null,
    viewNote(m, s),
    goTo(ai, "Visitors sent by AI assistants, counted and likely (inferred), are under", "AI & bots › Assistants"),
    goTo(S.hashFor({ ...s, tab: "traffic/pages", dd: "" }), "The pages these visitors landed on, with their leads, are on", "Pages")));
  out.push(h("section", { class: "s" }, h("h2", null, "Campaigns and referrers"), campaignParts(m, s, r)));
  out.push(unmeasured(t));
  return out;
}
