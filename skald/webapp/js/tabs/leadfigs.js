// Leads everywhere (2.5.0): the lead figures other tabs show beside their
// visitors, all from conversions.json - the same checked days the
// Conversions tab sums. A lead is a completed (or paid) form or demo
// booking (the file's lead_actions); demos booked are its demo_actions.
// Rows marked test are never in these days. The honesty rules:
//   * only days the file holds as "ok" (checked by the second count) are
//     summed; withheld and not-recorded days are named, never zero
//   * a rate puts leads over the visitors of the same days only: days whole
//     in the log AND checked in conversions; over fewer than min_rate
//     visitors, the count alone
//   * conversions do not know about page groups: on a view, no lead figure
//
// Every other tab imports from here; this file imports no tab.

import { h, n, pct1, share } from "../ui.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { countryName } from "../countries.js";

export const ACTION = { demo: "Demos", contact: "Contact forms", signup: "Sign-ups", waitlist: "Early access", paid: "Payments", deal: "Deals", call: "Phone clicks", email: "Email clicks", cta: "Button clicks", trial: "Trials" };
export const ONE = { demo: "Demo booking", contact: "Contact form", signup: "Sign-up", waitlist: "Early access", trial: "Trial", paid: "Payment", deal: "Deal" };
export const STAGE = { started: "started", completed: "completed", paid: "paid", cancelled: "cancelled", rescheduled: "rescheduled", no_show: "no-show", won: "won", lost: "lost" };
export const TOOL = { beacon: "The page (script tag)", site: "Lead database", lead: "Site's server", json: "Zapier, Make or a script", calendly: "Calendly", calcom: "Cal.com", stripe: "Stripe", typeform: "Typeform", hubspot: "HubSpot" };
export const toolName = (t) => TOOL[t] || t;
export const actionName = (a) => ACTION[a] || a.replace(/[_.:-]/g, " ").replace(/^./, (c) => c.toUpperCase());
export const oneAction = (a) => ONE[a] || actionName(a).replace(/s$/, "");
// A lead's label (2.18: the lead hook's optional token, e.g. a contact form's topic) as a
// small tag; null without one (h() leaves null out, so it never prints).
export const labelTag = (label) => (label ? h("span", { class: "lbl-tag", title: `Label: ${label}` }, String(label)) : null);
// An action with its label's tag beside it: one node, for a table cell.
export const actionWithLabel = (action, label) => h("span", null, actionName(action || ""), labelTag(label));

const LEADS = ["contact", "signup", "waitlist", "trial", "demo"];
// The log's breakdown name -> conversions.json's (last touch for sources).
export const DIM = { source: "source_type", landing: "landing", country: "country" };
export const LEAD_WORDS = "Leads: forms sent (contact, sign-up, early access, trial) and demos booked, completed. Rows marked test are never counted.";

// The conversions file when it holds figures, else null.
export function convFile(m) {
  const f = m.x?.conversions;
  return f && f.available && Array.isArray(f.days) ? f : null;
}
const sets = new WeakMap();
function meta(f) {
  if (!sets.has(f)) sets.set(f, { fin: new Set(f.finished || ["completed", "paid"]), leads: new Set(f.lead_actions || LEADS),
    demos: new Set(f.demo_actions || ["demo"]), at: new Map(f.days.map((d) => [d.day, d])) });
  return sets.get(f);
}
export const convDay = (f, day) => meta(f).at.get(day) || null;
export const minRate = (f) => f?.min_rate || 10;

// One "ok" day's leads and demos booked; null for any other day.
export function dayLeads(f, e) {
  if (!e || e.state !== "ok") return null;
  const { fin, leads, demos } = meta(f);
  let l = 0, d = 0;
  for (const [a, per] of Object.entries(e.stages || {})) for (const [st, v] of Object.entries(per)) {
    if (!fin.has(st)) continue;
    if (leads.has(a)) l += v;
    if (demos.has(a)) d += v;
  }
  return { leads: l, demos: d };
}

/* Leads and demos booked over a list of days (ISO): summed from the checked
   days, with what was left out. null without a conversions file. */
export function leadsOn(m, days) {
  const f = convFile(m);
  if (!f) return null;
  const out = { leads: 0, demos: 0, ok: 0, of: days.length, held: [], before: [] };
  for (const day of days) {
    const e = convDay(f, day), got = dayLeads(f, e);
    if (got) { out.leads += got.leads; out.demos += got.demos; out.ok += 1; }
    else if (e?.state === "withheld") out.held.push(day);
    else out.before.push(day);
  }
  out.whole = out.ok === out.of && out.of > 0;
  return out;
}

// One "ok" day's leads by a conversions breakdown: {label: n}.
function dayBy(f, e, dim) {
  const { leads } = meta(f), out = {};
  for (const [a, per] of Object.entries(e.by?.[dim] || {})) if (leads.has(a)) for (const [k, v] of Object.entries(per)) out[k] = (out[k] || 0) + v;
  return out;
}

/* Leads by a log breakdown (source, landing, country) over the days of the
   range that are whole in the log and checked in conversions, and the
   visitors of those same days for the rate. t: the range's totals (the
   live snapshot's for today). null without a file, or on a page group. */
export function leadsBy(m, s, r, t, logDim) {
  const f = convFile(m);
  if (!f || (s.view && s.view !== "all")) return null;
  const dim = DIM[logDim];
  const out = { leads: {}, visitors: {}, days: 0, of: 0, min: minRate(f), f };
  const add = (into, obj) => { for (const [k, v] of Object.entries(obj || {})) into[k] = (into[k] || 0) + v; };
  if (r.kind === "today") {
    out.of = 1;
    const e = convDay(f, m.today);
    if (t && e?.state === "ok") { out.days = 1; add(out.leads, dayBy(f, e, dim)); add(out.visitors, t.by?.[logDim]); }
    return out;
  }
  for (const d of r.days) {
    if (d.state !== "ok" || !d.by) continue;
    out.of += 1;
    const e = convDay(f, d.day);
    if (e?.state !== "ok") continue;
    out.days += 1;
    add(out.leads, dayBy(f, e, dim));
    add(out.visitors, d.by[logDim]);
  }
  return out;
}

// The rate for one label: leads over that label's visitors of the same days, or null under the minimum.
export function rateOf(lb, k) {
  const base = lb.visitors[k] || 0;
  return base >= lb.min ? (lb.leads[k] || 0) / base : null;
}

// What the leads cover, in one line.
export function coverWords(lb) {
  if (!lb.of) return "No whole day in this range to put leads beside.";
  if (!lb.days) return `No day of this range has both whole visitor figures and checked conversions, so no lead is shown here (not recorded, never zero).`;
  return lb.days === lb.of ? `Leads and the lead rate cover every whole day of the range (${n(lb.days)}).`
    : `Leads and the lead rate cover ${n(lb.days)} of the ${n(lb.of)} whole days: the days whose conversions are checked. The others are not recorded or withheld, never zero.`;
}

/* A {label: visitors} breakdown as a table with Leads and Lead rate beside
   it: the common countTable, with two columns more. lb from leadsBy (or
   null: the plain table, with a line saying why). */
export function leadTable(obj, lb, { caption, file, key = "Label", keep = () => true, label, path = false, total, limit = 12, empty, drill, touch } = {}) {
  const names = new Set(Object.keys(obj || {}).filter((k) => obj[k]));
  if (lb && lb.days) for (const [k, v] of Object.entries(lb.leads)) if (v) names.add(k);
  const rows = [...names].filter(keep).map((k) => ({ k, label: label ? label(k) : k, v: k in (obj || {}) ? obj[k] : null,
    leads: lb && lb.days ? lb.leads[k] || 0 : null, rate: lb && lb.days ? rateOf(lb, k) : null }));
  const sum = total ?? rows.reduce((a, x) => a + (x.v || 0), 0);
  const min = lb?.min || 10;
  // "Not recorded" sorts last whatever the column: its sort value is null.
  const by = (f) => (x) => (x.k === UNKNOWN ? null : f(x));
  const cols = [
    labelColumn(key, drill, path),
    { key: "v", label: "Visitors", num: true, sort: by((x) => x.v), fmt: (v) => (v == null ? h("span", { class: "few", title: "Not in this list's visitors" }, "-") : n(v)) },
    // A row with no visitors of its own (Not recorded, a label only the leads have) has no share, never 0%.
    { key: "share", label: "Share", num: true, sort: by((x) => x.v), fmt: (_, x) => (x.v == null ? h("span", { class: "few", title: "No share: not in this list's visitors" }, "-") : share(x.v, sum)), csv: (x) => (x.v && sum ? (x.v / sum).toFixed(4) : "") },
  ];
  if (lb && lb.days) {
    cols.push({ key: "leads", label: "Leads", num: true, sort: by((x) => x.leads), title: `${LEAD_WORDS} By ${touch}.` },
      { key: "rate", label: "Lead rate", num: true, sort: by((x) => x.rate), title: `Leads per visitor of the same days, given over at least ${min} visitors.`,
        fmt: (v, x) => (v != null ? pct1(x.leads, lb.visitors[x.k]) : x.k !== UNKNOWN && lb.visitors[x.k] ? h("span", { class: "few" }, `too few to say (${n(lb.visitors[x.k])})`)
          : h("span", { class: "few", title: x.k === UNKNOWN ? "No rate: the label was not recorded" : "No rate: no visitor of this label in the same days" }, "-")),
        csv: (x) => (x.rate == null ? "" : x.rate.toFixed(4)) });
  }
  const t = table(cols, { caption, rows: rows.sort((a, b) => (a.k === UNKNOWN) - (b.k === UNKNOWN) || (b.v || 0) - (a.v || 0) || (b.leads || 0) - (a.leads || 0) || a.k.localeCompare(b.k)), file, limit, empty });
  t.classList.add("lead-tbl");
  return [t, leadNote(lb, touch)];
}

/* A label cell that never breaks a letter a line: one line, cut with an
   ellipsis, the whole label in its tooltip, its mark on the same line. A
   value not recorded reads "Not recorded", muted. */
export const UNKNOWN = "Unknown";
export function labelCell(drill, k, text) {
  if (k === UNKNOWN) return h("span", { class: "cell-l none", title: "Not recorded, never guessed" }, "Not recorded");
  const words = text ?? k;
  return h("span", { class: "cell-l", title: drill === "country" ? countryName(k) : words }, drill ? link(drill, k, { text: words }) : words);
}
export function labelColumn(key, drill, path = false) {
  return { key: "label", label: key, cls: path ? "lbl lp" : "lbl", sort: (x) => (x.k === UNKNOWN ? null : x.label),
    fmt: (v, x) => labelCell(drill, x.k, v ?? x.k), csv: (x) => (x.k === UNKNOWN ? "Not recorded" : x.label ?? x.k),
    ...(drill === "country" ? { country: (x) => x.k } : {}) };
}

// The line under a table with lead columns: what Leads are, which touch, the days they cover.
export function leadNote(lb, touch) {
  if (!lb) return null;
  return h("p", { class: "note" }, `${LEAD_WORDS} Attributed by ${touch}. ${coverWords(lb)} A rate is given over at least ${lb.min} visitors; below that, the count alone.`);
}

// The line a page group shows instead of lead columns.
export function viewNote(m, s) {
  if (!convFile(m) || !s.view || s.view === "all") return null;
  return h("p", { class: "note" }, "Leads are counted for the whole site, not per page group: choose All pages to see them beside the visitors.");
}
