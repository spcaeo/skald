// Overview › Summary's key figures (release 2, card S4): five tiles, each with its change
// against the period before while Compare is on: "▼ 40% · before: 125", "≈ about the same
// · before: 12" (a change of 3 or fewer, period-dates.js SAME), or "before: not measured"
// when the earlier period was not counted. Never a 0 for a figure not recorded, never a rise
// against nothing. Every figure here is one the app already shows: the range's totals
// (data.js total), B's totals (mode-compare.js compareOf), the leads from conversions.json's
// checked days (leadfigs.js leadsOn), else from the lead store (overview.js leadsOver), as the
// tiles counted before. Nothing new is counted.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { info } from "./tiles.js";
import { convFile, leadsOn, LEAD_WORDS } from "./leadfigs.js";
import { leadsOver } from "./overview.js";
import { changeWords, beforeState } from "../period-dates.js";

const SEARCH = "Search engine";
const top3 = (obj) => Object.entries(obj || {}).filter(([, v]) => v).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 3)
  .map(([k, v]) => `${k} ${n(v)}`).join(" · ");

/* [key, label, the (i), value from a total, the note under it, the tab it opens]. */
export const TILES = [
  ["people", "People", "Visits that read at least one page, counted only when the browser loaded the page's scripts and styles, so automated programs are left out. One person on two devices is two visits.",
    (t) => (t.unmeasured?.readers ? null : t.readers ?? null), () => "visits by people", "traffic/visitors"],
  ["search", "From search engines", "Visits whose first page came from a search engine's results (Google, Bing, DuckDuckGo and others), by the referrer.",
    (t) => (t.unmeasured?.by || !t.by?.source ? null : t.by.source[SEARCH] || 0), () => "first page from a search result", "traffic/sources"],
  ["returning", "Returning people", "Visitors seen on an earlier day in the 30 days before.",
    (t) => (t.unmeasured?.returning || !t.returning ? null : t.returning.returning ?? null), () => "seen on an earlier day", "traffic/retention"],
  ["leads", "Leads", `${LEAD_WORDS} From the Conversions data: the script tag, the tools' webhooks and the lead database.`, null, null, "sales/summary"],
  ["ai", "Sent by AI assistants", "Visits that followed a link in an AI assistant's answer (a referrer or a tag). The true number is higher: many assistants hide the link they came from.",
    (t) => t.cited ?? null, (t) => top3(t.cited_by) || "none in this period", "traffic/sources"],
];

/* Leads over A's days and B's: {now, before} from conversions.json's checked days; before
   only when every day of B is checked. null without the file. */
function leadsAB(m, r, c) {
  if (!convFile(m)) return null;
  const now = leadsOn(m, r.kind === "today" ? [m.today] : r.days.map((d) => d.day));
  const before = c.ok ? leadsOn(m, c.b.days.map((d) => d.day)) : null;
  return { now, before: before?.whole ? before : null, held: before && !before.whole };
}

/* Which count the Leads tile is, and where the same figure is listed: Leads & sales >
   Summary counts from the lead database unless told otherwise, so the link opens it on
   the tools when the tile counts from them (the same days, the same figure). */
export function leadSource(s, tools) {
  const to = { tab: "sales/summary", lsrc: tools ? "all" : "" };
  return h("a", { class: "t-src", href: S.hashFor({ ...s, ...to, dd: "" }), title: `The same count as Leads & sales › Summary, counted from ${tools ? "the tools" : "the lead database"}` },
    `${tools ? "From the tools" : "From the lead database"} · Summary ›`);
}

function changeLine(c, v, p, fmt, { held = false } = {}) {
  if (!c.on) return null;
  let w;
  if (!c.ok) w = c.inc ? { text: "not compared: today is included", dir: "none" } : changeWords(v, null, { state: beforeState(c.b) });
  else if (held || p == null) w = { text: "before: not recorded", dir: "none" };
  else w = changeWords(v, p);
  const known = c.ok && p != null && !held;
  return h("span", { class: `t-c t-cmp ${w.dir}` }, w.text, known ? h("span", { class: "was" }, ` · before: ${fmt(p)}`) : null);
}

/* The five tiles. r: the range; t: its totals; c: compareOf. */
export function keyTiles(m, s, r, t, c) {
  const lf = leadsAB(m, r, c);
  const fmt = (x) => (x == null ? "-" : n(x));
  const cards = TILES.map(([key, label, about, get, noteOf, tab]) => {
    let v, p = null, note, held = false;
    if (key === "leads" && !lf) {
      // No conversions file: the lead store's count, as before (null when it has none of these days).
      v = leadsOver(m, r.days.filter((d) => d.state === "ok").map((d) => d.day));
      p = c.ok && v != null ? leadsOver(m, c.b.days.map((d) => d.day)) : null;
      note = v == null ? "no lead data for this period" : "forms sent";
    } else if (key === "leads") {
      v = lf.now.ok ? lf.now.leads : null;
      p = lf.before ? lf.before.leads : null;
      held = !!lf.held;
      note = lf.now.ok === lf.now.of ? "forms sent and demos booked" : `covers ${lf.now.ok} of ${lf.now.of} days (the others not checked)`;
    } else {
      v = get(t);
      p = c.ok && c.bT ? get(c.bT) : null;
      note = v == null ? "not recorded for this period" : noteOf(t);
    }
    const href = S.hashFor({ ...s, tab, dd: "" });
    // The whole tile opens the tab (the label's link is stretched over it, css/overview.css);
    // the (i) stays a button of its own above it.
    return h("div", { class: "tile t-link", role: "listitem" },
      h("div", { class: "t-top" }, h("a", { class: "t-l", href, title: `Open ${S.nameOf(tab)}` }, label), info(about, label)),
      h("div", { class: "t-v", title: v == null ? "Not recorded, never zero" : null }, fmt(v)),
      key === "leads" && v == null ? null : changeLine(c, v, p, fmt, { held }),
      h("span", { class: "t-n" }, note),
      key === "leads" && v != null ? leadSource(s, !!lf) : null);
  });
  const words = c.on ? "Key figures, each with its change against the period before" : "Key figures. Switch on Compare with the period before to see each one's change";
  return [h("p", { class: "ov-cap" }, words), h("div", { class: "tiles ov-five", role: "list", "aria-label": "Key figures" }, cards)];
}
