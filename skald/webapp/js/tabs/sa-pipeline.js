// Leads & sales > Pipeline (2.7.0): how many leads, at which stage, from where,
// how fast. One options row over the figures:
//
//   Count from  the lead database (leads.json, the owner's default) or the tools
//               (conversions.json: the page's script tag, Calendly, Cal.com,
//               Stripe and the other webhooks, and the lead database)   lsrc=db|all
//   Source      the global source filter (the lead database splits by it)
//   Action      one kind of lead or action                                lact
//   Stage       one status (the lead database's statuses)                 lstage
//   Show        the lists of what the figures leave out, on the page      lshow
//   Period      the same period as the top bar's
//
// The two files are never added together and never share a table: the figures
// below are one file's, drawn by its own renderer (leads.js or conversions.js),
// and the row says which. Options narrow the file the renderer reads (a copy:
// the days, rows and breakdowns of the chosen action or status), so every figure
// is summed by today's code with today's rules; a part the file does not split
// that way is left as it is and the row says so. With no option chosen the
// renderer reads the file itself: the figures are today's, to the digit.
//
// Moved out of the tools' figures, so each answer has one place: the demo funnel
// (Bookings), the latest conversions (People), the cancelled, removed and test
// lists (Show, above the figures).

import { h } from "../ui.js";
import * as S from "../state.js";
import leads from "./leads.js";
import conversions from "./conversions.js";
import { actionName } from "./leadfigs.js";
import { optionsRow, choice, select, toggles, listOf, period } from "./sa-options.js";
import { leadList, convList, LEAD_SHOW, CONV_SHOW } from "./sa-lists.js";

export const tools = (s) => s.lsrc === "all";

// The lead database's kinds and statuses, in leads.js's words.
const TYPE = { signup: "Sign-ups", contact: "Contact forms", waitlist: "Early access", demo_opened: "Demo opened", demo_booked: "Demos booked" };
const LEAD_TYPES = ["signup", "contact", "waitlist"];
const STATUS = [["new", "New"], ["contacted", "Contacted"], ["qualified", "Qualified"], ["won", "Won"], ["lost", "Lost"]];
const held = (b) => b && !Array.isArray(b) && b.state === "withheld";

// ---------------------------------------------------------- narrowing a file

function narrowLeads(f, s) {
  if (!f || f.available === false || (!s.lact && !s.lstage)) return f;
  const g = { ...f };
  if (s.lact) {
    g.types = (f.types || Object.keys(TYPE)).filter((k) => k === s.lact);
    // Spam and duplicates are counted per day, not per kind: not shown narrowed (the Show lists have them).
    g.days = (f.days || []).map((d) => (d.state === "withheld" ? d : { ...d, leads: d.leads && s.lact in d.leads ? { [s.lact]: d.leads[s.lact] } : {}, spam: null, duplicates: null }));
  }
  if (Array.isArray(f.attribution_rows)) {
    const cols = f.attribution_columns || ["day", "type", "status"];
    const ti = cols.indexOf("type"), si = cols.indexOf("status");
    g.attribution_rows = f.attribution_rows.filter((x) => (!s.lact || x[ti] === s.lact) && (!s.lstage || x[si] === s.lstage));
  }
  const t = f.time_to_convert;
  if (s.lact && t && !held(t) && Array.isArray(t.rows)) {
    g.time_to_convert = { ...t, rows: t.rows.filter((x) => x[1] === s.lact), visits_rows: t.visits_rows ? t.visits_rows.filter((x) => x[1] === s.lact) : t.visits_rows };
  }
  return g;
}

function narrowConv(f, s) {
  if (!f || !f.available || !s.lact) return f;
  const a = s.lact;
  const pick = (o) => (o && a in o ? { [a]: o[a] } : {});
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d, stages: pick(d.stages), abandoned: pick(d.abandoned),
    by: Object.fromEntries(Object.entries(d.by || {}).map(([dim, per]) => [dim, pick(per)])),
    visits_before: pick(d.visits_before), time_to_convert: pick(d.time_to_convert),
    // A day that records assisted sources keeps saying so, with this action's alone.
    assisted: d.assisted ? pick(d.assisted) : d.assisted, likely_ai: d.likely_ai ? pick(d.likely_ai) : d.likely_ai })) };
}

// The model the renderer reads: the same, with one file narrowed.
function withFile(m, name, f) {
  if (f === m.x[name]) return m;
  const m2 = Object.create(m);
  m2.x = { ...m.x, [name]: f };
  return m2;
}

// -------------------------------------------------------------- the choices

function leadActions(f) {
  return (f?.types || Object.keys(TYPE)).map((k) => [k, TYPE[k] || k]);
}
function convActions(f) {
  const total = {};
  for (const d of f?.days || []) if (d.state === "ok") for (const [a, per] of Object.entries(d.stages || {})) total[a] = (total[a] || 0) + Object.values(per).reduce((x, y) => x + y, 0);
  return Object.keys(total).sort((a, b) => total[b] - total[a] || a.localeCompare(b)).map((a) => [a, actionName(a)]);
}
function leadSources(m, f) {
  const seen = new Set(m.options?.source || []);
  if (Array.isArray(f?.attribution_rows)) {
    const i = (f.attribution_columns || []).indexOf("source_type");
    if (i >= 0) for (const x of f.attribution_rows) if (x[i] && x[i] !== "(none)") seen.add(x[i]);
  }
  return [...seen].sort().map((v) => [v, v]);
}

// What the chosen options narrow, and what they cannot.
function narrowWords(s, all) {
  if (all) return s.lact ? `Narrowed to ${actionName(s.lact).toLowerCase()}. Pages seen before converting is not split by action.` : "";
  const bits = [];
  if (s.lact) {
    bits.push(`Narrowed to ${(TYPE[s.lact] || s.lact).toLowerCase()}.`);
    if (!LEAD_TYPES.includes(s.lact)) bits.push("The Leads tile counts sign-ups, contact forms and early access only.");
    bits.push("Spam and duplicates are counted per day, not per kind: Show lists them. The funnel by source is not split by kind.");
  }
  if (s.lstage) bits.push(`Status ${(STATUS.find(([k]) => k === s.lstage) || [, s.lstage])[1].toLowerCase()}: it narrows where they came from and their quality; the tiles, the days and the time to convert are counted by kind, not by status.`);
  return bits.join(" ");
}

function optionsFor(m, s, f, all) {
  const known = (all ? CONV_SHOW : LEAD_SHOW).map(([k]) => k);
  const show = listOf(s.lshow, known);
  const notSplit = "The tools' file does not split its stages by source: Where the completed ones came from lists every source.";
  const controls = [
    choice("Count from", all ? "all" : "db", [["db", "Lead database", "leads.json: forms sent on the site, as your team marks them"],
      ["all", "Tools", "conversions.json: the page's script tag, booking and payment tools, and the lead database"]],
    (k) => S.set({ lsrc: k, lact: "", lstage: "", lshow: "" })),
    select("Source", s.source, all ? [] : leadSources(m, f), (v) => S.set({ source: v }), { off: all ? notSplit : "", all: "Every source" }),
    select("Action", s.lact, all ? convActions(f) : leadActions(f), (v) => S.set({ lact: v }), { all: all ? "Every action" : "Every kind" }),
    select("Stage", all ? "" : s.lstage, all ? [] : STATUS, (v) => S.set({ lstage: v }),
      { off: all ? "The tools' file keeps every stage side by side (the table below); where they came from counts completed ones only." : "", all: all ? "Every stage" : "Every status" }),
    toggles("Show left out", show, all ? CONV_SHOW : LEAD_SHOW, (list) => S.set({ lshow: list.join(",") })),
    period(s, m),
  ];
  const from = all
    ? "Counted from the tools (conversions.json): the page's script tag, Calendly, Cal.com, Stripe and the other webhooks, and the lead database. Never added to the lead database's own counts."
    : "Counted from the lead database (leads.json): forms sent on the site. Never added to the tools' counts; switch Count from to see those.";
  return { row: optionsRow("Pipeline options", controls, from, narrowWords(s, all)), show };
}

// ------------------------------------------------------------------- the tab

// A part's heading: a section's h2, or a fold's summary (its first words).
const titleOf = (el) => (el?.matches?.("section") ? el.querySelector(":scope > h2")?.firstChild?.textContent
  : el?.matches?.("details") ? el.querySelector(":scope > summary")?.firstChild?.textContent : null)?.trim();
const MOVED = new Set(["Demo funnel", "Latest conversions", "Cancelled, removed and test"]);

export default function pipeline(m, s, o) {
  const all = tools(s);
  const name = all ? "conversions" : "leads";
  const f = m.x[name];
  const g = all ? narrowConv(f, s) : narrowLeads(f, s);
  let body = [(all ? conversions : leads)(withFile(m, name, g), s, o)].flat(Infinity).filter(Boolean);
  if (all) body = body.filter((el) => !MOVED.has(titleOf(el)));
  const { row, show } = optionsFor(m, s, f, all);
  // The lists follow the chosen action too (a listing, never added to a figure).
  const only = s.lact ? (a) => a === s.lact : null;
  const lists = show.length ? [all ? convList(show, { only }) : leadList(show, { only })] : [];
  const moved = all && f?.available ? h("p", { class: "note" }, "The demo funnel is on ", h("a", { href: S.hashFor({ ...s, tab: "sales/bookings" }) }, "Bookings"),
    "; the latest conversions are on ", h("a", { href: S.hashFor({ ...s, tab: "sales/people" }) }, "People"), ".") : null;
  // The options under the tab's heading (its period line), the lists under the options.
  const at = body.findIndex((el) => el.classList?.contains("head")) + 1;
  return [...body.slice(0, at), ...row, ...lists, ...body.slice(at), moved];
}
