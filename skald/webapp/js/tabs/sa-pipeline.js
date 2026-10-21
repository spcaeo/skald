// Leads & sales > Pipeline (2.7.0): how many leads, at which stage, from where,
// how fast. One options row over the figures:
//
//   Count from  the lead database (leads.json, the owner's default) or the tools
//               (conversions.json: the page's script tag, Calendly, Cal.com,
//               Stripe and the other webhooks, and the lead database)   lsrc=db|all
//   Source      the global source filter (the lead database splits by it)
//   Action      one kind of lead or action                                lact
//   Label       one lead label (2.18, the tools only: the lead hook's
//               optional token, e.g. a contact form's topic)              llabel
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

import { h, n } from "../ui.js";
import { rangeOf } from "../data.js";
import * as S from "../state.js";
import leads from "./leads.js";
import conversions from "./conversions.js";
import { actionName, convFile, leadsOn } from "./leadfigs.js";
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

export function narrowConv(f, s) {
  if (!f || !f.available || (!s.lact && !s.llabel)) return f;
  const g = s.lact ? byAction(f, s.lact) : f;
  return s.llabel ? byLabel(g, s.llabel) : g;
}

function byAction(f, a) {
  const pick = (o) => (o && a in o ? { [a]: o[a] } : {});
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d, stages: pick(d.stages), abandoned: pick(d.abandoned),
    by: Object.fromEntries(Object.entries(d.by || {}).map(([dim, per]) => [dim, pick(per)])),
    visits_before: pick(d.visits_before), time_to_convert: pick(d.time_to_convert),
    labels: pick(d.labels), labels_abandoned: pick(d.labels_abandoned),
    // A day that records assisted sources keeps saying so, with this action's alone.
    assisted: d.assisted ? pick(d.assisted) : d.assisted, likely_ai: d.likely_ai ? pick(d.likely_ai) : d.likely_ai })) };
}

/* One lead label: each day's stages and abandoned starts become that label's own (the
   file's `labels` and `labels_abandoned`, counted again by the second count). The parts
   not split by label (where they came from, touches, time to convert) are emptied here
   and left off the page by the tab, with a note: never shown as another label's figures. */
function byLabel(f, label) {
  const only = (per) => Object.fromEntries(Object.entries(per || {}).filter(([, x]) => x && label in x).map(([a, x]) => [a, x[label]]));
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d, stages: only(d.labels), abandoned: only(d.labels_abandoned),
    by: Object.fromEntries(Object.keys(d.by || {}).map((dim) => [dim, {}])), visits_before: {}, time_to_convert: {},
    assisted: d.assisted ? {} : d.assisted, likely_ai: d.likely_ai ? {} : d.likely_ai })) };
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
// The lead labels the tools' file holds on its checked days (of the chosen action), most rows first.
export function convLabels(f, action = "") {
  const total = {};
  for (const d of f?.days || []) {
    if (d.state !== "ok") continue;
    for (const [a, per] of Object.entries(d.labels || {})) {
      if (action && a !== action) continue;
      for (const [k, st] of Object.entries(per || {})) total[k] = (total[k] || 0) + Object.values(st || {}).reduce((x, y) => x + y, 0);
    }
  }
  return Object.keys(total).sort((a, b) => total[b] - total[a] || a.localeCompare(b)).map((k) => [k, k]);
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
export const LABEL_WORDS = "Where the completed ones came from, the touches, the time to convert and the pages seen before are not split by label: they show with Every label.";
function narrowWords(s, all) {
  if (all) {
    const bits = [];
    if (s.lact) bits.push(`Narrowed to ${actionName(s.lact).toLowerCase()}.${s.llabel ? "" : " Pages seen before converting is not split by action."}`);
    if (s.llabel) bits.push(`Label “${s.llabel}”: Every action counts only the leads your site's server sent with this label. ${LABEL_WORDS}`);
    return bits.join(" ");
  }
  const bits = [];
  if (s.lact) {
    bits.push(`Narrowed to ${(TYPE[s.lact] || s.lact).toLowerCase()}.`);
    if (!LEAD_TYPES.includes(s.lact)) bits.push("The Leads tile counts sign-ups, contact forms and early access only.");
    bits.push("Spam and duplicates are counted per day, not per kind: Show lists them. The funnel by source is not split by kind.");
  }
  if (s.lstage) bits.push(`Status ${(STATUS.find(([k]) => k === s.lstage) || [, s.lstage])[1].toLowerCase()}: it narrows where they came from and their quality; the tiles, the days and the time to convert are counted by kind, not by status.`);
  return bits.join(" ");
}

// Label: the tools' lead labels; greyed, with the reason, where there are none to choose.
function labelSelect(s, f, all) {
  const options = all ? convLabels(f, s.lact) : [];
  const off = !all ? "The lead database keeps no label: labels come with the leads your site's server sends (Count from: Tools)."
    : !options.length && !s.llabel ? "No lead in this file has a label: your site's server can send one with each lead (label)." : "";
  return select("Label", all ? s.llabel : "", options, (v) => S.set({ llabel: v }), { off, all: "Every label" });
}

function optionsFor(m, s, f, all) {
  const known = (all ? CONV_SHOW : LEAD_SHOW).map(([k]) => k);
  const show = listOf(s.lshow, known);
  const notSplit = "The tools' file does not split its stages by source: Where the completed ones came from lists every source.";
  const controls = [
    choice("Count from", all ? "all" : "db", [["db", "Lead database", "Forms sent on the site, as your team marks them"],
      ["all", "Tools", "conversions.json: the page's script tag, booking and payment tools, and the lead database"]],
    (k) => S.set({ lsrc: k, lact: "", llabel: "", lstage: "", lshow: "" })),
    select("Source", s.source, all ? [] : leadSources(m, f), (v) => S.set({ source: v }), { off: all ? notSplit : "", all: "Every source" }),
    select("Action", s.lact, all ? convActions(f) : leadActions(f), (v) => S.set({ lact: v }), { all: all ? "Every action" : "Every kind" }),
    labelSelect(s, f, all),
    select("Stage", all ? "" : s.lstage, all ? [] : STATUS, (v) => S.set({ lstage: v }),
      { off: all ? "The tools' file keeps every stage side by side (the table below); where they came from counts completed ones only." : "", all: all ? "Every stage" : "Every status" }),
    toggles("Show left out", show, all ? CONV_SHOW : LEAD_SHOW, (list) => S.set({ lshow: list.join(",") })),
    period(s, m),
  ];
  const from = all
    ? "Counted from the tools (conversions.json): the page's script tag, Calendly, Cal.com, Stripe and the other webhooks, and the lead database. Never added to the lead database's own counts."
    : `Counted from the lead database: forms sent on the site. Never added to the tools' counts; switch Count from to see those.${convFile(m) ? " Overview's Leads and Demos booked count from the tools: choose Tools for the same figures." : ""}`;
  return { row: optionsRow("Pipeline options", controls, from, narrowWords(s, all)), show };
}

// ------------------------------------------------------------------- the tab

/* Counting from the tools, the leads and demos booked of the period in one line: the
   same sum (leadfigs.js leadsOn, the same days) as Overview's Leads and Demos booked
   tiles, so the two places say the same number. */
function overviewLine(m, s) {
  if (s.lact || s.llabel) return null;
  const r = rangeOf(m, s);
  const got = leadsOn(m, r.kind === "today" ? [m.today] : r.days.map((d) => d.day));
  if (!got || !got.ok) return null;
  return h("p", { class: "note sa-total" }, h("b", null, `Leads: ${n(got.leads)}`), ", of them ", h("b", null, `demos booked: ${n(got.demos)}`),
    ` (completed forms and demos, test rows left out; ${got.ok === got.of ? `every day of the period` : `${n(got.ok)} of its ${n(got.of)} days, the others not recorded`}). The same figures as Overview's Leads and Demos booked tiles.`);
}

// A part's heading: a section's h2, or a fold's summary (its first words).
function titleOf(el) {
  const want = { section: "h2", details: "summary" }[String(el?.tagName || "").toLowerCase()];
  if (!want) return undefined;
  const top = [...(el.childNodes || [])].find((k) => String(k.tagName || "").toLowerCase() === want);
  return top?.firstChild?.textContent?.trim();
}
const MOVED = new Set(["Demo funnel", "Latest conversions", "Cancelled, removed and test"]);

export default function pipeline(m, s, o) {
  const all = tools(s);
  const name = all ? "conversions" : "leads";
  const f = m.x[name];
  // No lead database on this site, and no one chose one: the leads it has came from its tools
  // (its server's lead hook, the script tag, bookings), so open those rather than an empty page.
  if (!all && !s.lsrc && f && f.available === false && /not set/.test(String(f.error || ""))) {
    queueMicrotask(() => S.set({ lsrc: "all" }, { replace: true }));
    return h("p", { class: "empty" }, "This site has no lead database: opening the leads from its tools...");
  }
  const g = all ? narrowConv(f, s) : narrowLeads(f, s);
  let body = [(all ? conversions : leads)(withFile(m, name, g), s, o)].flat(Infinity).filter(Boolean);
  if (all) body = body.filter((el) => !MOVED.has(titleOf(el)));
  // One label: only the parts it splits (Every action); the others say so in the options' note.
  if (all && s.llabel) body = body.filter((el) => { const t = titleOf(el); return t == null || t === "Every action"; });
  const { row, show } = optionsFor(m, s, f, all);
  // The lists follow the chosen action and label too (a listing, never added to a figure).
  const only = s.lact ? (a) => a === s.lact : null;
  const lists = show.length ? [all ? convList(show, { only, label: s.llabel || "" }) : leadList(show, { only })] : [];
  const moved = all && f?.available ? h("p", { class: "note" }, "The demo funnel is on ", h("a", { href: S.hashFor({ ...s, tab: "sales/bookings" }) }, "Bookings"),
    "; the latest conversions are on ", h("a", { href: S.hashFor({ ...s, tab: "sales/people" }) }, "People"), ".") : null;
  // The options under the tab's heading (its period line), the lists under the options.
  const at = body.findIndex((el) => el.classList?.contains("head")) + 1;
  return [...body.slice(0, at), ...row, all ? overviewLine(m, s) : null, ...lists, ...body.slice(at), moved];
}
