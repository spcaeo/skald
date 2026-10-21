// Leads & sales > Summary and Sources (2.20; Pipeline until 2.18): the lead figures,
// in two tabs that each answer one question.
//
//   Summary   "How many leads, and is it better than before?"  one row of numbers
//             (leads against the period before, demos booked, won, lost), every action
//             side by side, and the best sources
//   Sources   "Where did they come from?"  where the completed ones came from, first,
//             last and assisted touch, likely from AI, the time to convert, the pages
//             seen before
//
// Both count from one file at a time, never both in one figure (the owner's decision,
// HANDOVER/05): the tools (conversions.json: the page's script tag, the booking and
// payment tools, the site's server, and the lead database's rows) or the lead database
// (leads.json, forms as the team marks them). "Count from" is a quiet option at the end of
// the row; the lead database is the default where the site has one (lsrc=db|all). A site
// with no lead database that is asked for one says so, with one button to the tools.
//
//   What    one kind of lead or action                       lact
//   Label   one lead label (the tools only)                  llabel
//   Status  one status (the lead database only)              lstage
//   Source  the global source filter (the lead database)     source
//
// Options narrow the file the renderer reads (a copy: the days, rows and breakdowns of
// the chosen action or status), so every figure is summed by today's code with today's
// rules (leads.js, conversions.js); a part the file does not split that way is left off
// and the row's (i) says so. With no option chosen the figures are today's, to the digit.

import { h, n, change } from "../ui.js";
import { rangeOf, previousOf } from "../data.js";
import * as S from "../state.js";
import leads from "./leads.js";
import conversions from "./conversions.js";
import { actionName, convFile, leadsOn } from "./leadfigs.js";
import { tiles } from "./tiles.js";
import { blist } from "./common.js";
import { tabHead, optionsRow, choice, select, emptyState, foldNotes } from "./sa-options.js";

// No lead database on this site (leads.json says "not set"): its leads come from its tools.
export const noLeadDb = (m) => { const f = m?.x?.leads; return !!f && f.available === false && /not set/.test(String(f.error || "")); };
// Counting from the tools: chosen, or not chosen on a site with no lead database.
export const tools = (s, m = null) => s.lsrc === "all" || (!s.lsrc && noLeadDb(m));

// The lead database's kinds and statuses, in leads.js's words.
const TYPE = { signup: "Sign-ups", contact: "Contact forms", waitlist: "Early access", demo_opened: "Demo opened", demo_booked: "Demos booked" };
const LEAD_TYPES = ["signup", "contact", "waitlist"];
const STATUS = [["new", "New"], ["contacted", "Contacted"], ["qualified", "Qualified"], ["won", "Won"], ["lost", "Lost"]];
const held = (b) => b && !Array.isArray(b) && b.state === "withheld";
const HELP = "#help?part=leads-and-conversions";

// ---------------------------------------------------------- narrowing a file

function narrowLeads(f, s) {
  if (!f || f.available === false || (!s.lact && !s.lstage)) return f;
  const g = { ...f };
  if (s.lact) {
    g.types = (f.types || Object.keys(TYPE)).filter((k) => k === s.lact);
    // Spam and duplicates are counted per day, not per kind: not shown narrowed (Leads lists them).
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
export function withFile(m, name, f) {
  if (f === m.x[name]) return m;
  const m2 = Object.create(m);
  m2.x = { ...m.x, [name]: f };
  return m2;
}

// -------------------------------------------------------------- the choices

function leadActions(f) {
  return (f?.types || Object.keys(TYPE)).map((k) => [k, TYPE[k] || k]);
}
export function convActions(f) {
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
    bits.push("Spam and duplicates are counted per day, not per kind: the Leads tab lists them. The funnel by source is not split by kind.");
  }
  if (s.lstage) bits.push(`Status ${(STATUS.find(([k]) => k === s.lstage) || [, s.lstage])[1].toLowerCase()}: it narrows where they came from and their quality; the tiles, the days and the time to convert are counted by kind, not by status.`);
  return bits.join(" ");
}

// Label: the tools' lead labels; greyed, with the reason, where there are none to choose.
function labelSelect(s, f, all) {
  const options = all ? convLabels(f, s.lact) : [];
  const off = !all ? "The lead database keeps no label: labels come with the leads your site's server sends (Count from: Tools)."
    : !options.length && !s.llabel ? "No lead has a label yet: your site's server can send one with each lead." : "";
  return select("Label", all ? s.llabel : "", options, (v) => S.set({ llabel: v }), { off, all: "Every label" });
}

// "Count from": quiet, at the end of the row. The words for each side are behind its title.
function countFrom(m, all) {
  return choice("Count from", all ? "all" : "db", [
    ["db", "Lead database", noLeadDb(m) ? "This site has no lead database connected" : "Forms sent on the site, as your team marks them"],
    ["all", "Tools", "The page's script tag, the booking and payment tools and your site's server, with the lead database's rows"]],
  (k) => S.set({ lsrc: k, lact: "", llabel: "", lstage: "" }));
}

function optionsFor(m, s, f, all, part) {
  const controls = [
    select("What", s.lact, all ? convActions(f) : leadActions(f), (v) => S.set({ lact: v }), { all: all ? "Every action" : "Every kind" }),
    all ? labelSelect(s, f, all) : select("Status", s.lstage, STATUS, (v) => S.set({ lstage: v }), { all: "Every status" }),
    !all && part === "sources" ? select("Source", s.source, leadSources(m, f), (v) => S.set({ source: v }), { all: "Every source" }) : null,
  ];
  const from = all
    ? "Counted from the tools: the page's script tag, Calendly, Cal.com, Stripe and the other webhooks, your site's server and the lead database's rows. Never added to the lead database's own counts."
    : `Counted from the lead database: forms sent on the site, as your team marks them. Never added to the tools' counts.${convFile(m) ? " Overview's Leads and Demos booked count from the tools: choose Tools for the same figures." : ""}`;
  return optionsRow(part === "sources" ? "Sources options" : "Summary options", controls, { end: countFrom(m, all), notes: [from, narrowWords(s, all)], help: HELP });
}

// ---------------------------------------------------------------- the parts

// A part's heading: a section's h2, or a fold's summary (its first words).
function titleOf(el) {
  const want = { section: "h2", details: "summary" }[String(el?.tagName || "").toLowerCase()];
  if (!want) return undefined;
  const top = [...(el.childNodes || [])].find((k) => String(k.tagName || "").toLowerCase() === want);
  return top?.firstChild?.textContent?.trim();
}
const isHead = (el) => el?.classList?.contains("head");
// Which renderer parts each tab keeps (the rest belong to another tab or are said there).
const PARTS = {
  summary: { all: ["Every action"], db: [undefined, "Per day, by kind"] },
  sources: { all: ["Where the completed ones came from", "First, last and assisted touch", "Likely from AI assistants (inferred)", "Time to convert", "Pages seen before converting"],
    db: ["Where they came from", "Lead quality by source", "Time to convert", "Funnel, by source"] },
};
// Plain one-line headings for the parts (the question each answers).
const RENAME = { "Every action": "Every action, side by side", "Where the completed ones came from": "Where the completed ones came from",
  "First, last and assisted touch": "First, last and assisted touch", "Per day, by kind": "Leads per day, by kind" };

/* Summary, from the tools: the period's leads against the period before (the same sum as
   Overview's Leads tile, leadfigs.js leadsOn), demos booked, and the won and lost of the
   lead actions (the Every action table's own columns, added up). */
function numbers(m, s, r) {
  const days = r.kind === "today" ? [m.today] : r.days.map((d) => d.day);
  const got = leadsOn(m, days);
  if (!got || !got.ok) return null;
  const p = previousOf(m, r);
  const before = p ? leadsOn(m, p.days.map((d) => d.day)) : null;
  const vs = (cur, was) => {
    if (!before || !before.whole || !got.whole) return h("span", { class: "t-c none", title: "The period before is not wholly recorded: no comparison" }, "no comparison");
    const [arrow, words] = change(cur, was);
    return h("span", { class: "t-c" }, arrow ? h("span", { class: "arrow" }, arrow) : null, `${words} vs the ${n(p.length)} days before`, h("span", { class: "was" }, ` (${n(was)})`));
  };
  const f = convFile(m);
  const leadsSet = new Set(f.lead_actions || []);
  let won = 0, lost = 0;
  for (const day of days) {
    const e = (f.days || []).find((d) => d.day === day);
    if (e?.state !== "ok") continue;
    for (const [a, per] of Object.entries(e.stages || {})) if (leadsSet.has(a)) { won += per.won || 0; lost += per.lost || 0; }
  }
  const cover = got.whole ? "every day of the period" : `${n(got.ok)} of its ${n(got.of)} days recorded`;
  // Narrowed to one kind or label, it is that kind's or label's count, not Overview's figure.
  const same = s.lact || s.llabel ? `Narrowed to ${[s.lact ? actionName(s.lact).toLowerCase() : "", s.llabel ? `the label “${s.llabel}”` : ""].filter(Boolean).join(" and ")}: not Overview's figure, which counts every kind.`
    : "The same figure as Overview's Leads tile.";
  return tiles([
    { label: "Leads", value: got.leads, info: `Forms sent and demos booked, completed; test rows never counted. Counted from the tools on ${cover}. ${same}`, more: HELP, line: vs(got.leads, before?.leads) },
    { label: "Demos booked", value: got.demos, info: `Demos booked, completed, on ${cover}. Calendar bookings shows each step.`, more: "#help?part=demo-bookings", line: vs(got.demos, before?.demos) },
    { label: "Won", value: won, info: "Leads your team or your CRM marked won, on the day the lead came in.", more: HELP, line: h("span", { class: "t-c" }, "as known now") },
    { label: "Lost", value: lost, info: "Leads your team or your CRM marked lost, on the day the lead came in.", more: HELP, line: h("span", { class: "t-c" }, "as known now") },
  ]);
}

/* The best sources: the completed leads of the period by their last-touch source, top
   five (the "By source (last touch)" breakdown of Sources, the lead actions only). */
function bestSources(m, s, r) {
  const f = convFile(m);
  if (!f) return null;
  const days = new Set(r.kind === "today" ? [m.today] : r.days.map((d) => d.day));
  const leadsSet = new Set(f.lead_actions || []);
  const by = {};
  for (const e of f.days || []) {
    if (e.state !== "ok" || !days.has(e.day)) continue;
    for (const [a, per] of Object.entries(e.by?.source_type || {})) if (leadsSet.has(a)) for (const [k, v] of Object.entries(per)) by[k] = (by[k] || 0) + v;
  }
  const rows = Object.entries(by).filter(([, v]) => v).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return null;
  return h("section", { class: "s" }, h("div", { class: "card-h" }, h("h2", null, "Best sources"),
    h("a", { class: "see-all", href: S.hashFor({ ...s, tab: "sales/sources" }) }, "All sources")),
  h("div", { class: "sheet" }, blist(rows, { limit: 5, label: (k) => (k === "Unknown" ? "Not recorded" : k) })));
}

// A site with no lead database, asked to count from one: one message, one button.
function noDatabase(m, s, r, part) {
  return [...tabHead(part === "sources" ? "Sources" : "Summary", QUESTION[part], r),
    ...optionsRow("Count from", [], { end: countFrom(m, false) }),
    emptyState("This site has no lead database connected. Its leads come from its tools (the lead hook, the script tag, booking tools).",
      ["Show leads from the tools", () => S.set({ lsrc: "all", lact: "", lstage: "" })]),
    h("p", { class: "note" }, h("a", { href: "#help?part=leads-and-conversions" }, "How to connect a lead database"), ".")];
}

const QUESTION = { summary: "How many leads came in, and is it better than before?", sources: "Where did the leads come from?" };

function figures(m, s, o, part) {
  const all = tools(s, m);
  const r = rangeOf(m, s);
  if (!all && noLeadDb(m)) return noDatabase(m, s, r, part);
  const name = all ? "conversions" : "leads";
  const f = m.x[name];
  const g = all ? narrowConv(f, s) : narrowLeads(f, s);
  const m2 = withFile(m, name, g);
  const body = [(all ? conversions : leads)(m2, s, o)].flat(Infinity).filter(Boolean).filter((el) => !isHead(el));
  const want = PARTS[part][all ? "all" : "db"];
  // One label: only the parts it splits (Every action); the others say so in the row's (i).
  const keep = (el) => {
    const t = titleOf(el);
    if (t === undefined) return part === "summary" ? !el.matches?.("p.note") || !all : el.classList?.contains("state");
    if (all && s.llabel && t !== "Every action") return false;
    return want.includes(t);
  };
  const kept = body.filter(keep);
  for (const el of kept) { const top = [...(el.childNodes || [])].find((k) => k.tagName === "H2"); const t = titleOf(el); if (top && RENAME[t]) top.firstChild.textContent = RENAME[t]; }
  const ready = all ? convFile(m2) : f && f.available !== false;
  const lead = part === "summary" && all && ready ? numbers(m2, s, r) : null;
  const best = part === "summary" && all && ready && !s.llabel ? bestSources(m2, s, r) : null;
  foldNotes(kept);
  const states = kept.filter((el) => !titleOf(el) && el.classList?.contains("state"));
  const parts = kept.filter((el) => !states.includes(el));
  return [...tabHead(part === "sources" ? "Sources" : "Summary", QUESTION[part], r,
    { help: all ? "Counted from the tools: forms sent and demos booked as the page's script tag, the booking tools and your site's server reported them." : "Counted from the lead database: forms sent on the site, as your team marks them.", more: HELP }),
  ...optionsFor(m, s, f, all, part), ...states, lead, ...parts, best,
  all && f?.as_known ? h("p", { class: "note" }, f.as_known) : null].filter(Boolean);
}

export function summary(m, s, o) { return figures(m, s, o, "summary"); }
export function sources(m, s, o) { return figures(m, s, o, "sources"); }
export default summary;
