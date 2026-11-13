// Leads & sales > Summary (2.20; Pipeline until 2.18; #33: Sources folded in): "How many leads
// came in, where from, and is it better than before?" One answer, top to bottom:
//
//   the tiles          Leads (the same figure as the Leads tab and Overview's Leads tile),
//                      Sales (the Revenue tab's), Demos booked, Won, Lost: only those this
//                      site ever sends
//   Each kind of lead  every lead action side by side: started, completed, abandoned, the
//                      completion rate (only where the page's script saw both: sa-rate.js),
//                      cancelled, won, lost, sales and value
//   Where they came    the best five sources, then one fold with every breakdown, first, last
//   from               and assisted touch, likely from AI and the time to convert (the old
//                      Sources tab; its address opens this fold: lpart=sources, routes.js)
//
// #32: leads only, from one file. Every figure here counts the lead actions of conversions.json
// (forms sent and demos booked, from the page's script tag, the booking tools, the site's
// server and the lead database's rows), never a button click, a phone click, a payment or a
// site's own action (an app's runs): the file is narrowed to the lead actions first
// (leadsOnly). The lead database's own counts (leads.json) are no longer a second way to count
// here ("Count from" is gone): Summary's Leads tile and the Leads tab count the same thing.
// The period is the section's one period (sa-period.js salesRange), today included.
//
//   What    one kind of lead          lact
//   Label   one lead label            llabel
//
// Options narrow the file the renderer reads (a copy: the days, rows and breakdowns of the
// chosen kind or label), so every figure is summed by today's code with today's rules
// (conversions.js); a part the file does not split that way is left off and the row's (i)
// says so.

import { h, n, change } from "../ui.js";
import * as S from "../state.js";
import conversions, { everSent } from "./conversions.js";
import { money } from "./revfigs.js";
import { actionName, convFile, leadsOn } from "./leadfigs.js";
import { tiles } from "./tiles.js";
import { blist } from "./common.js";
import { tabHead, optionsRow, select, emptyState, foldNotes } from "./sa-options.js";
import { salesRange, periodDays, periodBefore, versusLive, periodCheck, liveNote } from "./sa-period.js";
import { writeKeys } from "../tablestate.js";
import { connectCard } from "../ui/connect.js";

const HELP = "#help?part=leads-and-conversions";
const LEADS = ["contact", "signup", "waitlist", "trial", "demo"];

// ---------------------------------------------------------- narrowing a file

const leadSet = (f) => new Set(f?.lead_actions || LEADS);

// A day's revenue narrowed to some actions' own sales (`by.action`, 2.46.3); none when unsplit.
function revenueOf(r, keep) {
  if (!r || typeof r !== "object" || Array.isArray(r) || r.state) return r;
  const out = {};
  for (const [cur, x] of Object.entries(r)) {
    const per = Object.entries(x?.by?.action || {}).filter(([a]) => keep(a));
    if (!per.length) continue;
    out[cur] = { sales: per.reduce((a, [, c]) => a + (c.sales || 0), 0), net_minor: per.reduce((a, [, c]) => a + (c.net_minor || 0), 0), by: { action: Object.fromEntries(per) } };
  }
  return out;
}

// Every part of an "ok" day keyed by action, kept for the actions `keep` says.
function byActions(f, keep) {
  const pick = (o) => (o && typeof o === "object" ? Object.fromEntries(Object.entries(o).filter(([a]) => keep(a))) : o);
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d, stages: pick(d.stages), abandoned: pick(d.abandoned),
    by: Object.fromEntries(Object.entries(d.by || {}).map(([dim, per]) => [dim, pick(per)])),
    visits_before: pick(d.visits_before), time_to_convert: pick(d.time_to_convert),
    labels: pick(d.labels), labels_abandoned: pick(d.labels_abandoned),
    // A day that records assisted sources keeps saying so, with these actions' alone.
    assisted: d.assisted ? pick(d.assisted) : d.assisted, likely_ai: d.likely_ai ? pick(d.likely_ai) : d.likely_ai,
    revenue: revenueOf(d.revenue, keep) })) };
}

/* #32: the file with the lead actions only (forms sent and demos booked): never a button or
   phone click, a payment or a site's own action. Nothing else changes. */
export function leadsOnly(f) {
  if (!f || !f.available || !Array.isArray(f.days)) return f;
  const keep = leadSet(f);
  return byActions(f, (a) => keep.has(a));
}

export function narrowConv(f, s) {
  if (!f || !f.available || (!s.lact && !s.llabel)) return f;
  const g = s.lact ? byActions(f, (a) => a === s.lact) : f;
  return s.llabel ? byLabel(g, s.llabel) : g;
}

/* One lead label: each day's stages and abandoned starts become that label's own (the
   file's `labels` and `labels_abandoned`, counted again by the second count). The parts
   not split by label (where they came from, touches, time to convert) are emptied here
   and left off the page by the tab, with a note: never shown as another label's figures. */
function byLabel(f, label) {
  const only = (per) => Object.fromEntries(Object.entries(per || {}).filter(([, x]) => x && label in x).map(([a, x]) => [a, x[label]]));
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d, stages: only(d.labels), abandoned: only(d.labels_abandoned),
    by: Object.fromEntries(Object.keys(d.by || {}).map((dim) => [dim, {}])), visits_before: {}, time_to_convert: {},
    assisted: d.assisted ? {} : d.assisted, likely_ai: d.likely_ai ? {} : d.likely_ai, revenue: undefined })) };
}

// The model the renderer reads: the same, with one file narrowed.
export function withFile(m, name, f) {
  if (f === m.x[name]) return m;
  const m2 = Object.create(m);
  m2.x = { ...m.x, [name]: f };
  return m2;
}

// -------------------------------------------------------------- the choices

/* The kinds of lead the file holds on its checked days, most rows first (the lead actions
   only: #32). */
export function convActions(f) {
  const keep = leadSet(f), total = {};
  for (const d of f?.days || []) if (d.state === "ok") for (const [a, per] of Object.entries(d.stages || {})) if (keep.has(a)) total[a] = (total[a] || 0) + Object.values(per).reduce((x, y) => x + y, 0);
  return Object.keys(total).sort((a, b) => total[b] - total[a] || a.localeCompare(b)).map((a) => [a, actionName(a)]);
}
// The lead labels the file holds on its checked days (of the chosen action), most rows first.
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

// What the chosen options narrow, and what they cannot.
export const LABEL_WORDS = "Where the completed ones came from, the touches, the time to convert and the sales are not split by label: they show with Every label.";
function narrowWords(s) {
  const bits = [];
  if (s.lact) bits.push(`Narrowed to ${actionName(s.lact).toLowerCase()}.`);
  if (s.llabel) bits.push(`Label “${s.llabel}”: only the leads your site's server sent with this label. ${LABEL_WORDS}`);
  return bits.join(" ");
}

function optionsFor(s, f) {
  const labels = convLabels(f, s.lact);
  const controls = [
    select("What", s.lact, convActions(f), (v) => S.set({ lact: v }), { all: "Every kind" }),
    select("Label", s.llabel, labels, (v) => S.set({ llabel: v }), { all: "Every label",
      off: !labels.length && !s.llabel ? "No lead has a label yet: your site's server can send one with each lead." : "" }),
  ];
  const from = "Leads only: forms sent and demos booked, from the page's script tag, the booking tools (Calendly, Cal.com), your site's server and the lead database's rows. The same figures as the Leads tab.";
  return optionsRow("Summary options", controls, { notes: [from, narrowWords(s)], help: HELP });
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
// The renderer's parts Summary keeps: the table first, then where the leads came from (the old
// Sources tab). The demo funnel is on Leads (What: Demos); the pages seen before converting and
// the latest conversions count every kind of conversion, so they are not here (#32).
const TABLE = "Every action";
const SOURCES = ["Where the completed ones came from", "First, last and assisted touch", "Likely from AI assistants (inferred)", "Time to convert"];
const RENAME = { "Every action": "Each kind of lead", "Where the completed ones came from": "By source, page, country and device" };

const vsWords = (cur, was, p) => {
  const [arrow, words] = change(cur, was);
  return h("span", { class: "t-c" }, arrow ? h("span", { class: "arrow" }, arrow) : null, `${words} vs the ${n(p.length)} days before`, h("span", { class: "was" }, ` (${n(was)})`));
};

/* The tiles: the period's leads (the same sum as the Leads tab and Overview's Leads tile,
   leadfigs.js leadsOn, checked against its second count: sa-period.js periodCheck), against
   the period before like for like; sales (the Revenue tab's, every action's: `raw`, the file
   before the leads-only narrowing); demos booked; won and lost. */
function numbers(m, raw, s, r) {
  const days = periodDays(m, r);
  const got = leadsOn(m, days);
  if (!got || !got.ok) return null;
  const f = convFile(m);
  const check = periodCheck(m, r, got, s);
  let line;
  if (!check.ok) line = h("span", { class: "t-c none" }, "withheld");
  else if (r.live) {
    const vs = versusLive(m, m, r, got, s);
    line = h("span", { class: `t-c${vs ? " t-wrap" : " none"}` }, vs || (r.all ? "all time: nothing before it" : "no comparison"));
  } else {
    const p = periodBefore(m, r);
    const before = p ? leadsOn(m, p.days.map((d) => d.day)) : null;
    line = before?.whole && got.whole ? vsWords(got.leads, before.leads, p) : h("span", { class: "t-c none", title: "The period before is not wholly recorded: no comparison" }, "no comparison");
  }
  const leadsSet = new Set(f.lead_actions || LEADS);
  let won = 0, lost = 0, sold = 0, held_ = 0;
  const value = {};
  for (const day of days) {
    const e = (f.days || []).find((d) => d.day === day);
    if (e?.state !== "ok") continue;
    for (const [a, per] of Object.entries(e.stages || {})) if (leadsSet.has(a)) { won += per.won || 0; lost += per.lost || 0; }
    // Sales (2.46.3): the period's sales and their value, per currency (the Revenue tab's figures).
    const rv = (raw.days || []).find((d) => d.day === day)?.revenue;
    if (!rv || typeof rv !== "object" || Array.isArray(rv)) continue;
    if (rv.state === "withheld") { held_ += 1; continue; }
    for (const [cur, x] of Object.entries(rv)) if (/^[A-Z]{3}$/.test(cur) && x) { sold += x.sales || 0; value[cur] = (value[cur] || 0) + (x.net_minor || 0); }
  }
  const ever = everSent(f), money_ = everSent(raw).has("money");
  const cover = got.whole ? "every day of the period" : `${n(got.ok)} of its ${n(got.of)} days recorded`;
  // Narrowed to one kind or label, it is that kind's or label's count, not Overview's figure.
  const same = s.lact || s.llabel ? `Narrowed to ${[s.lact ? actionName(s.lact).toLowerCase() : "", s.llabel ? `the label “${s.llabel}”` : ""].filter(Boolean).join(" and ")}: not Overview's figure, which counts every kind.`
    : "The same figure as the Leads tab and Overview's Leads tile.";
  const worth = Object.keys(value).sort().map((c) => money(value[c], c, raw)).join(" · ");
  const demosSeen = (f.days || []).some((d) => d.state === "ok" && d.stages?.demo) || (f.set_up?.hooks || []).some((k) => ["calendly", "calcom"].includes(k));
  const demosAt = S.hashFor({ ...s, tab: "sales/leads", lact: "demo", llabel: "", dd: "" });
  return tiles([
    { label: "Leads", value: check.ok ? got.leads : null, info: check.ok ? `Forms sent and demos booked, completed; test rows never counted. Counted on ${cover}. ${same}` : check.why, more: HELP, line },
    money_ && !s.llabel ? { label: "Sales", value: held_ ? null : sold, info: `Sales with a value in the period, counted on the day they were paid, less refunds, per currency: the Revenue tab's figures.${held_ ? " Withheld: the second count disagreed on a day of the period." : ""}`, more: "#help?part=revenue", line: h("span", { class: "t-c" }, held_ ? "withheld" : worth || "none") } : null,
    demosSeen ? { label: "Demos booked", value: got.demos, info: `Demos booked, completed, on ${cover}. Leads › What: Demos shows each step.`, more: demosAt, line: h("a", { class: "t-c", href: demosAt }, "Each step ›") } : null,
    ever.has("won") ? { label: "Won", value: won, info: "Leads your team or your CRM marked won, on the day the lead came in.", more: HELP, line: h("span", { class: "t-c" }, "as known now") } : null,
    ever.has("lost") ? { label: "Lost", value: lost, info: "Leads your team or your CRM marked lost, on the day the lead came in.", more: HELP, line: h("span", { class: "t-c" }, "as known now") } : null,
  ].filter(Boolean));
}

/* Where they came from: the period's completed leads by their last-touch source, top five,
   then the old Sources tab in one fold (open: lpart=sources, kept in the address). */
function whereFrom(m, s, r, parts) {
  const f = convFile(m);
  const days = new Set(periodDays(m, r));
  const leadsSet = new Set(f.lead_actions || LEADS);
  const by = {};
  for (const e of f.days || []) {
    if (e.state !== "ok" || !days.has(e.day)) continue;
    for (const [a, per] of Object.entries(e.by?.source_type || {})) if (leadsSet.has(a)) for (const [k, v] of Object.entries(per)) by[k] = (by[k] || 0) + v;
  }
  const rows = Object.entries(by).filter(([, v]) => v).sort((a, b) => b[1] - a[1]);
  if (!rows.length && !parts.length) return null;
  const open = s.lpart === "sources";
  const fold = parts.length ? h("details", { class: "fold sa-src", open: open || null, id: "sa-sources" },
    h("summary", null, "Every source, touch and time to convert"), ...parts) : null;
  // Opening or closing it is kept in the address, without drawing the tab again.
  fold?.addEventListener("toggle", () => writeKeys({ lpart: fold.open || fold.hasAttribute?.("open") ? "sources" : "" }));
  return h("section", { class: "s" }, h("h2", null, "Where they came from"),
    rows.length ? h("div", { class: "sheet" }, blist(rows, { limit: 5, label: (k) => (k === "Unknown" ? "Not recorded" : k) })) : null, fold);
}

const QUESTION = "How many leads came in, where from, and is it better than before?";

export function summary(m, s, o) {
  const r = salesRange(m, s);
  const top = tabHead("Summary", QUESTION, r, { help: "Leads only: forms sent and demos booked, from every road (the page's script tag, the booking tools, your site's server and the lead database). The same figures as the Leads tab.", more: HELP, source: "leads" });
  const raw = convFile(m);
  if (!raw) {
    const f0 = m.x.conversions;
    if (f0?.state === "error") return [...top, emptyState(`The leads could not be built: ${f0.error || "no reason given"}.`, null, { bad: true })];
    return [...top, connectCard(m, "leads", { s })];
  }
  const g = narrowConv(leadsOnly(raw), s);
  const m2 = withFile(m, "conversions", g);
  const body = [conversions(m2, s, o)].flat(Infinity).filter(Boolean).filter((el) => !isHead(el));
  const keep = (el) => {
    const t = titleOf(el);
    if (t === undefined) return el.classList?.contains("state");
    if (s.llabel && t !== TABLE) return false;
    return t === TABLE || SOURCES.includes(t);
  };
  const kept = body.filter(keep);
  for (const el of kept) { const top_ = [...(el.childNodes || [])].find((k) => k.tagName === "H2"); const t = titleOf(el); if (top_ && RENAME[t]) top_.firstChild.textContent = RENAME[t]; }
  foldNotes(kept);
  const states = kept.filter((el) => !titleOf(el));
  const table = kept.filter((el) => titleOf(el) === RENAME[TABLE] || titleOf(el) === TABLE);
  const parts = kept.filter((el) => !states.includes(el) && !table.includes(el));
  // Sales: every action's (the Revenue tab's figure), or the chosen kind's own.
  const lead = numbers(m2, s.lact ? byActions(raw, (a) => a === s.lact) : raw, s, r);
  // Today's part of a period that ends today, in one line (the same line as on Leads).
  const days = periodDays(m2, r);
  const live = r.live ? liveNote(m, s, r, leadsOn(m2, [m.today]), leadsOn(m2, days)?.leads ?? null) : null;
  // An old Sources link (lpart=sources) opens with where they came from first, its fold open,
  // under the figures: on screen without a scroll (the scroll a hash change puts back would undo one).
  const where = s.llabel ? null : whereFrom(m2, s, r, parts);
  const first = s.lpart === "sources";
  return [...top, ...optionsFor(s, leadsOnly(raw)), ...states, lead, live, first ? where : null, ...table,
    first ? null : where,
    raw.as_known ? h("p", { class: "note" }, raw.as_known) : null].filter(Boolean);
}

export default summary;
