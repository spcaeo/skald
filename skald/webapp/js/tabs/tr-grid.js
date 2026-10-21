// Traffic's long breakdowns as Data Grids (2.7.0): one place for the rows and the
// columns of every "label · visitors · share · leads · lead rate" grid on Sources,
// Pages and Places & devices. The figures are leadfigs.js leadTable's, unchanged:
// the same rows, the same share base, the same lead and rate rules and minimums.
// Only where they are drawn changed (js/grid.js instead of table.js).
//
// A row may come from any breakdown (Sources mixes source types, referring sites
// and campaigns as segments of one grid), so each row carries what it needs:
//   { dim, k, label, v, whole, lb, leads, rate }
//   dim    the drill dimension of its label (source, referrer, campaign, landing, country)
//   whole  the base its share is over (the range's visitors, or its list's sum)
//   lb     leadsBy() for its breakdown, or null: its breakdown has no lead split
// Compare mode adds its A · B · ± columns to these lists, here, in one place.

import { h, n, pct1, share } from "../ui.js";
import { ranked } from "../data.js";
import { UNKNOWN, labelCell, rateOf } from "./leadfigs.js";
import { compareOf, change as cmpChange } from "../mode-compare.js";

/* {label: visitors} -> grid rows, with the leads of the same breakdown beside them.
   As leadTable: a label with leads but no visitor in the list still gets a row. */
export function leadRows(obj, lb, { dim, keep = () => true, label, whole, noLeads } = {}) {
  const names = new Set(Object.keys(obj || {}).filter((k) => obj[k]));
  const has = lb && lb.days;
  if (has) for (const [k, v] of Object.entries(lb.leads)) if (v) names.add(k);
  const rows = [...names].filter(keep).map((k) => ({ dim, k, label: label ? label(k) : k, v: k in (obj || {}) ? obj[k] : null,
    lb: has ? lb : null, noLeads, leads: has ? lb.leads[k] || 0 : null, rate: has ? rateOf(lb, k) : null }));
  const sum = whole ?? rows.reduce((a, x) => a + (x.v || 0), 0);
  for (const x of rows) x.whole = sum;
  // leadTable's order: Not recorded last, then visitors, then leads, then the label.
  return rows.sort((a, b) => (a.k === UNKNOWN) - (b.k === UNKNOWN) || (b.v || 0) - (a.v || 0) || (b.leads || 0) - (a.leads || 0) || a.k.localeCompare(b.k));
}

// {label: count} -> rows with a share over their own sum (countTable's figures).
export function countRows(obj, { dim, keep, label, whole } = {}) {
  const rows = ranked(obj, keep).map(([k, v]) => ({ dim, k, label: label ? label(k) : k, v }));
  const sum = whole ?? rows.reduce((a, x) => a + x.v, 0);
  for (const x of rows) x.whole = sum;
  return rows;
}

// "Not recorded" sorts last whatever the column and the direction: its sort value is null.
const by = (f) => (x) => (x.k === UNKNOWN ? null : f(x));
const dash = (title) => h("span", { class: "few", title }, "-");

// A row's own address, when it has one: a page (path, landing) or a referring site.
const hrefOf = (x) => (x.dim === "path" || x.dim === "landing" ? x.k : x.dim === "referrer" && /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(x.k || "") ? `https://${x.k}` : "");
export function labelCol(name) {
  // url: copy and open in a new tab on a page's or a referring site's cell (urlactions.js).
  return { key: "label", label: name, url: true, href: hrefOf, sort: by((x) => x.label),
    fmt: (v, x) => labelCell(x.dim, x.k, v ?? x.k), csv: (x) => (x.k === UNKNOWN ? "Not recorded" : x.label ?? x.k) };
}

export function countCols(value = "Visitors") {
  return [
    { key: "v", label: value, num: true, sort: by((x) => x.v), fmt: (v) => (v == null ? dash("Not in this list's visitors") : n(v)), csv: (x) => x.v ?? "" },
    // A row with no visitors of its own (Not recorded, a label only the leads have): no share, never 0%.
    { key: "share", label: "Share", num: true, sort: by((x) => x.v), fmt: (_, x) => (x.v == null ? dash("No share: not in this list's visitors") : share(x.v, x.whole)), csv: (x) => (x.v && x.whole ? (x.v / x.whole).toFixed(4) : "") },
  ];
}

/* Leads and Lead rate, as leadTable draws them. A row whose breakdown has no
   lead split (a referring site, a campaign) says so with "-", never 0. */
export function leadCols() {
  const none = (x) => dash(x.noLeads || "Leads are not split this way");
  return [
    { key: "leads", label: "Leads", num: true, sort: by((x) => x.leads), fmt: (v, x) => (x.lb ? n(v) : none(x)), csv: (x) => x.leads ?? "" },
    { key: "rate", label: "Lead rate", num: true, sort: by((x) => x.rate),
      fmt: (v, x) => {
        if (!x.lb) return none(x);
        if (v != null) return pct1(x.leads, x.lb.visitors[x.k]);
        if (x.k !== UNKNOWN && x.lb.visitors[x.k]) return h("span", { class: "few" }, `too few to say (${n(x.lb.visitors[x.k])})`);
        return dash(x.k === UNKNOWN ? "No rate: the label was not recorded" : "No rate: no visitor of this label in the same days");
      },
      csv: (x) => (x.rate == null ? "" : x.rate.toFixed(4)) },
  ];
}

/* A line that sends the reader to the one place a figure lives now. */
export function goTo(href, words, where) {
  return h("p", { class: "tr-goto" }, words, " ", h("a", { href }, where, h("span", { "aria-hidden": "true" }, " ›")));
}

// ------------------------------------------------------------- Compare mode
// With "Compare with…" on (mode-compare.js), a grid's rows get B's figure from
// B's totals (summed by data.js total(), as A's are) and the grid two more
// columns: B and ±. A row only B has is added with 0 in A. "Per day" (a custom
// B of another length) shows A and B as typical days, the visitors column
// keeping A's total. The lead and share columns stay A's.

/* rows: a grid's A rows of one breakdown; bObj: B's {label: count} of the same
   breakdown. Returns the rows to show (A's, then B-only ones). */
export function compareRows(c, rows, bObj, { dim, keep = () => true, label, whole } = {}) {
  if (!c?.ok) return rows;
  const b = bObj || {};
  const seen = new Set(rows.map((x) => x.k));
  for (const x of rows) x.b = x.v == null ? null : b[x.k] || 0;
  const like = rows.find((x) => x.lb) || rows[0] || {};
  const extra = Object.keys(b).filter((k) => b[k] && !seen.has(k) && keep(k)).map((k) => ({
    dim, k, label: label ? label(k) : k, v: 0, b: b[k], whole: whole ?? like.whole ?? 0, seg: like.seg, noLeads: like.noLeads,
    lb: like.lb || null, leads: like.lb ? like.lb.leads[k] || 0 : null, rate: like.lb ? rateOf(like.lb, k) : null }));
  return [...rows, ...extra];
}

const num1 = (v) => (v == null ? "-" : Math.abs(v) < 100 && !Number.isInteger(v) ? v.toFixed(1) : n(v));

/* B and ± (and "A per day" when Per day is on), after the count column. */
export function compareCols(c) {
  if (!c?.ok) return [];
  const pd = !!c.perDay, ua = Math.max(1, c.used.a), ub = Math.max(1, c.used.b);
  const per = (v, u) => (v == null ? null : pd ? v / u : v);
  const fmt = (v) => (v == null ? "-" : pd ? num1(v) : n(v));
  const min = pd ? 10 / Math.max(ua, ub) : 10;
  const delta = (x) => (x.v == null || x.b == null ? null : per(x.v, ua) - per(x.b, ub));
  return [
    ...(pd ? [{ key: "apd", label: "A per day", num: true, sort: by((x) => per(x.v, ua)), fmt: (_, x) => fmt(per(x.v, ua)), csv: (x) => per(x.v, ua) ?? "" }] : []),
    { key: "b", label: pd ? "B per day" : "B", num: true, sort: by((x) => per(x.b, ub)), fmt: (_, x) => fmt(per(x.b, ub)), csv: (x) => per(x.b, ub) ?? "" },
    { key: "d", label: "±", num: true, sort: by(delta),
      fmt: (_, x) => (x.v == null || x.b == null ? "-" : cmpChange(per(x.v, ua), per(x.b, ub), { min, fmt: pd ? num1 : (v) => n(v), inline: true })),
      csv: (x) => delta(x) ?? "" },
  ];
}

/* What a compared grid needs said under it, or null. */
export function compareNote(c) {
  if (!c?.ok) return null;
  const parts = [];
  if (c.perDay) parts.push("Per day: A and B as a typical day of each period; Visitors and Share stay A's totals.");
  if (c.bT?.unmeasured?.by) parts.push(`${c.bT.unmeasured.by} of B's days were collected before breakdowns existed, so B's lists hold fewer visitors than its headline.`);
  parts.push("Leads, shares and rates are A's.");
  return h("p", { class: "note" }, parts.join(" "));
}

export { compareOf };
