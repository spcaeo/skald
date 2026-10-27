// Traffic > Sources (2.7.0): where visitors came from, in one grid.
//
// One Data Grid, four segments: Source type (by.source), Social network (campaigns.json's
// social_networks: the Social media row by network, tr-social.js), Referring site
// (by.referrer) and Campaign (by.campaign). Each segment is its own breakdown,
// stored apart in the log, so the segments are never added together and each
// share is over its own list (as the lists they replace: the source types over
// the range's visitors, the sites and campaigns over their own sum).
// It replaces Traffic sources, Each source over time, All sources with their leads,
// Referring sites, All referring sites and Campaigns: the same figures, in one place.
//
// Below it, under one fold kept in the address (srcx_view=open, 2.42: answer first): the
// likely causes of Direct, where returning visitors first came from (tr-firsttouch.js), then
// Campaigns and referrers (campaigns.json: UTM tags, referring sites down to the page, paid
// networks, tag problems). The grid's method notes are behind its "?". AI visits live under
// AI & bots > Assistants (owner's decision, 2026-10-12): this tab links there. Landing pages
// live on Pages.

import { h, change } from "../ui.js";
import { color, figures, previousOf, total, coverage, chartDays } from "../data.js";
import { spark } from "../charts.js";
import * as S from "../state.js";
import { grid } from "../grid.js";
import { head, nothing, fileName } from "./common.js";
import { campaigns } from "./campaigns.js";
import { firstTouch } from "./tr-firsttouch.js";
import { leadsBy, leadNote, viewNote } from "./leadfigs.js";
import { leadRows, labelCol, countCols, leadCols, goTo, compareOf, compareRows, compareCols, compareNote } from "./tr-grid.js";
import { directPanel } from "./likelydirect.js";
import { urlFold } from "../ui/fold.js";
import { help } from "../ui/help.js";
import { SEGMENT as SOCIAL, socialRows, netCell, socialNote, networkPanel } from "./tr-social.js";

const TOUCH = "last touch: the source of the visit the lead was sent from";
const only = (value) => (value ? (k) => k === value : () => true);

export const SEGMENTS = [
  { id: "type", label: "Source type", dim: "source", noLeads: null },
  SOCIAL,
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
  // A social network's label opens its detail (net=, tr-social.js) instead of a drill-down.
  const label = labelCol("Source");
  const own = label.fmt;
  label.fmt = (v, x) => (x.dim === SOCIAL.dim ? netCell(x) : own(v, x));
  const cols = [label, ...countCols("Visitors"), ...compareCols(c)];
  if (prev) cols.push(
    { key: "before", label: "Before", num: true, csv: (x) => x.before ?? "" },
    { key: "chg", label: "Change", num: true, sort: (x) => (x.before ? (x.v - x.before) / x.before : null),
      fmt: (_, x) => { if (x.before == null) return "-"; const [a, w] = change(x.v || 0, x.before); return `${a}${a ? " " : ""}${w}`; },
      // A fraction, as every share in a CSV is (0.0612, not "6%"); none when there was nothing before.
      csv: (x) => (x.before ? ((x.v || 0) - x.before) / x.before : null)?.toFixed(4) ?? "" },
    { key: "chip", label: "Trend", type: "badge", sortable: false, fmt: (v) => (v ? h("span", { class: `trend-chip ${v}` }, v) : ""), csv: (x) => x.chip || "" });
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
  const seg = (id) => SEGMENTS.find((x) => x.id === id);
  // The networks only while no source filter names another type (they break down Social media).
  const social = !s.source || s.source === "Social media" ? socialRows(m, s, r, c) : { rows: [], a: null };
  return {
    lb, prev: !!p, perDay: r.kind === "history" && r.length > 1, c, social,
    rows: [...compareRows(c, types, bBy.source, { dim: "source", keep: only(s.source), whole: t.readers }),
      ...social.rows,
      ...compareRows(c, other(seg("site"), t.by.referrer, only(s.referrer)), bBy.referrer, { dim: "referrer", keep: only(s.referrer) }),
      ...compareRows(c, other(seg("campaign"), t.by.campaign, only(s.campaign)), bBy.campaign, { dim: "campaign", keep: only(s.campaign) })],
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
  const out = [...head("Sources", r, "Where visitors came from, by the referrer of the first page they read. Direct: no referrer and no campaign tag. Referrers are often stripped, so Direct includes everyone whose browser did not say. Source types, referring sites and campaigns are stored apart, so each segment adds up on its own and they are never added together.")];
  if (!t || !t.by) return [...out, nothing(m, r, "sources")];
  const { lb, prev, perDay, rows, c, social } = sourceRows(m, s, r, t, cov);
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
    placeholder: "Search sources, networks, sites, campaigns",
    empty: "No visitor recorded for this segment.",
    onFiltered: (_, q) => { box.dataset.seg = q.segment || SEGMENTS[0].id; },
  });
  g.classList.add("tr-grid", "lead-tbl");
  box.append(g);
  const ai = S.hashFor({ ...s, tab: "ai/assistants", dd: "" });
  // What the grid counts and how: behind its "?", never a stack of notes under it.
  const about = [c.ok ? "Visitors by source type, social network, referring site or campaign, in A against B. Each segment is its own list."
    : prev ? "Visitors by source type, social network, referring site or campaign. Before, Change and the trend compare source types and networks with the period before, only when both are fully verified; a change under 20% is not called either way."
    : "Visitors by source type, social network, referring site or campaign. Each segment is its own list. Open a network for the hosts it rolls up and where its visitors landed.",
  compareNote(c), socialNote(social), lb ? leadNote(lb, TOUCH) : null,
  leads ? "Leads are split by source type only, so social networks, referring sites and campaigns list their visitors alone." : null]
    .map((x) => (x && typeof x !== "string" ? x.textContent : x)).filter(Boolean);
  out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Sources"), help("Sources", { text: about, guide: "where-visitors-come-from" })),
    box,
    viewNote(m, s),
    goTo(ai, "Visitors sent by AI assistants, counted and likely (inferred), are under", "AI & bots › Assistants"),
    goTo(S.hashFor({ ...s, tab: "traffic/pages", dd: "" }), "The pages these visitors landed on, with their leads, are on", "Pages")));
  // The open social network (net=x): how its visitors were matched and where they landed.
  out.push(networkPanel(m, s, r));
  out.push(urlFold("srcx", "Open the details: the likely causes of Direct, where returning visitors first came from, campaigns and referrers", () => [
    // Under Direct: its likely causes (inferred, direct_likely.py), never added to any row.
    // Not in compare mode: the split is the range's own, not A against B.
    c.ok ? null : h("section", { class: "s" }, directPanel(m, r)),
    firstTouch(t, r, { live: r.kind === "today" }),
    h("section", { class: "s" }, h("h2", null, "Campaigns and referrers"), campaignParts(m, s, r)),
    unmeasured(t)]));
  return out;
}
