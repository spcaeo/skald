// Leads: how many sign-ups, contact forms and demo bookings came in, from
// which source (first and last touch), their quality by source, the time from
// first touch to lead, and the funnel from readers to demos per source.
// Counts here; the leads left out (spam, duplicates, test) are listed in full
// from the "Left out" line (person.js), and a person is found with the search.
// A lead is never joined to a visit: the funnel's log steps are visits, the
// lead steps come from the lead store, two systems side by side.
// A block the second count disagreed with arrives as {state: "withheld", why}
// and is said so, never shown as zeros.

import { h, n, counter, addDays, short, pct1, reduced, ICON } from "../ui.js";
import { rangeOf, chartDays } from "../data.js";
import { compareOf, versus } from "../mode-compare.js";
import { columns, legend } from "../charts.js";
import { head, rangeWords, fixed } from "./common.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { howTo } from "./help.js";
import { leadsLikely } from "./likelyai.js";
import { openLeftOut } from "./person.js";
import { neverRecorded } from "../notset.js";

const TYPE = { signup: "Sign-ups", contact: "Contact forms", waitlist: "Early access", demo_opened: "Demo opened", demo_booked: "Demos booked" };
const TONE = { signup: "var(--g-people)", contact: "var(--g-search_engines)", waitlist: "var(--g-bots)", demo_opened: "var(--g-ours)", demo_booked: "var(--opp)" };
const STEP = { readers: "Visitors", pricing: "Saw pricing", form_page: "Opened a form", demo_opened: "Opened the demo", leads: "Became a lead", demo_booked: "Booked a demo" };
const LEAD_TYPES = ["signup", "contact", "waitlist"];   // a "lead"; demo opened and booked are counted beside
const MIN_RATE = 10;   // a rate over fewer than this many is not given: too few to mean anything
const name = (t) => TYPE[t] || t;
const SKIP = new Set(["spam", "duplicate"]);   // statuses that are not leads
const STATUS = [["new", "New"], ["contacted", "Contacted"], ["qualified", "Qualified"], ["won", "Won"], ["lost", "Lost"]];
const WAIT = { "<1h": "Under an hour", "<1d": "1 to 24 hours", "1-7d": "1 to 7 days", "8-30d": "8 to 30 days", "31-90d": "31 to 90 days", ">90d": "Over 90 days" };
const VISITS = { 0: "0", 1: "1 (the first visit)", 2: "2", "3-5": "3 to 5", "6-10": "6 to 10", "11+": "11 or more" };
const withheld = (b) => b && !Array.isArray(b) && b.state === "withheld";
const heldNote = (what, b) => h("div", { class: "state bad", role: "alert", html: ICON.info }, h("div", null, `${what} withheld: nothing is shown rather than a figure that does not reconcile. Why: ${b.why || "the second count of the lead store disagrees."}`));
const rate = (a, b) => (b >= MIN_RATE && a != null ? `${a && a / b < 0.1 ? ((a / b) * 100).toFixed(1) : Math.round((a / b) * 100)}%` : null);

function funnel(fn, s) {
  if (!fn || !(fn.by_source || []).length) return h("p", { class: "empty" }, "No funnel yet: it needs the visits of the last few days and the lead store.");
  const steps = fn.steps || Object.keys(STEP);
  const rows = (fn.by_source || []).filter((x) => !s.source || x.source === s.source).sort((a, b) => (b.readers || 0) - (a.readers || 0));
  const list = [["All sources", fn.total || {}], ...rows.map((x) => [x.source, x])];
  const grid = h("div", { class: "fun", role: "table", "aria-label": "Funnel by source", style: { "--steps": String(steps.length) } },
    h("div", { class: "fun-r fun-h", role: "row" }, h("span", { role: "columnheader" }, "Source"), steps.map((k) => h("span", { role: "columnheader" }, STEP[k] || k))));
  for (const [src, v] of list) {
    const top = v.readers || 0;
    grid.append(h("div", { class: `fun-r${src === "All sources" ? " all" : ""}`, role: "row" },
      h("span", { class: "fun-src", role: "rowheader" }, src),
      steps.map((k, i) => {
        const val = v[k];
        // Every step is rated on the readers: the steps are not nested (a visit can open a form without seeing pricing),
        // and the lead-store steps are another system, so "of the step before" would mislead.
        const prevVal = i ? v.readers : null;
        const step = i && prevVal != null ? rate(val, prevVal) : null;
        const w = top && val != null ? Math.max(val ? 2 : 0, Math.min(100, (val / top) * 100)) : 0;
        return h("span", { class: "fun-c", role: "cell", "aria-label": `${STEP[k] || k}: ${val == null ? "not recorded" : n(val)}${step ? `, ${step} of the step before` : ""}` },
          h("i", { style: { width: `${w}%` } }), h("em", { class: "fun-l", "aria-hidden": "true" }, STEP[k] || k), h("b", null, val == null ? "-" : n(val)),
          i ? h("small", null, val == null ? "" : step ? [step, h("span", { class: "ob" }, " of visitors")] : prevVal ? h("span", { class: "few" }, "too few to rate") : "") : null);
      })));
  }
  return h("div", null, grid, h("p", { class: "note" },
    `${fn.first && fn.last ? `${short(fn.first)} to ${short(fn.last)}. ` : ""}${fn.note || "Visitors, pricing and form steps are visits in the server log; the demo and lead steps come from the lead store, by the lead's first-touch source. Two systems side by side, never joined per visit."} Each step is given as a share of the source's visitors, and only over at least ${MIN_RATE} visitors.`));
}

export default function leads(m, s, { first }) {
  const r = rangeOf(m, s);
  const out = [...head("Pipeline", r, "Sign-ups, contact forms, early-access requests and demo bookings: how many, and where the people who sent them first came from. Counts only; names and messages stay in the website's admin.", { banner: false })];
  const f = m.x.leads;
  if (!f) return [...out, h("div", { class: "state", html: ICON.info }, h("div", null, "Lead counts are not written beside this page yet. They come from the website's lead store as daily totals with no names; when the first file lands this tab fills in. Until then the Sources tab shows where visitors come from.")),
    howTo("leads-and-conversions", "How do leads reach Skald?")];
  if (f.available === false) return [...out, h("div", { class: "state bad", html: ICON.info }, h("div", null, `The lead store could not be read${f.error ? `: ${f.error}` : ""}. Nothing is shown rather than zeros.`)), howTo("leads-and-conversions", "How do leads reach Skald?")];

  // Days before `since` (when the lead store began to be read) are not recorded, whatever they hold.
  // A day the second count disagreed with is withheld: no figures, said once.
  const kept = (f.days || []).filter((d) => !f.since || d.day >= f.since);
  const byDay = new Map(kept.filter((d) => d.state !== "withheld").map((d) => [d.day, d]));
  const wanted = r.kind === "today" ? [m.today] : r.days.map((d) => d.day);
  const inRange = wanted.map((d) => byDay.get(d)).filter(Boolean);
  const held = kept.filter((d) => d.state === "withheld" && wanted.includes(d.day));
  if (held.length) out.push(h("div", { class: "state bad", role: "alert", html: ICON.info }, h("div", null,
    `${held.length} day${held.length === 1 ? "" : "s"} withheld (${held.slice(0, 5).map((d) => short(d.day)).join(", ")}${held.length > 5 ? "..." : ""}): ${held.length === 1 ? "it is" : "they are"} left out of every figure below, never counted as zero. Why: ${held[0].why || "the second count of the lead store disagrees."}`)));
  if (!inRange.length) {
    out.push(h("div", { class: "state", html: ICON.info }, h("div", null, `No lead counts for ${r.kind === "today" ? "today" : `this range (${rangeWords(r)})`}${f.since ? `: the lead store is read from ${short(f.since)} on` : ""}. A day without counts is not recorded, never zero. The sections below cover their own periods.`)));
  } else {
    counts(m, s, r, f, byDay, inRange, first, out);
    ranged(r, f, s, new Set(inRange.map((d) => d.day)), wanted.length, out);
  }
  tail(f, s, out);
  // (2.20) Names and emails: Leads & sales > Leads lists them for admins and owners, where the site keeps them.
  return out;
}

/* Leads & sales › Leads counts its 7, 30 or 90 days up to today, from every tool (demos booked
   too); this count is whole days from the lead database. Said under the tiles so the two
   figures are never read as one (2.42, the UX audit). */
function otherFigure(s, r) {
  if (!String(s.tab || "").startsWith("sales/") || !["7d", "30d", "90d"].includes(s.range) || r.kind !== "history") return null;
  return h("p", { class: "note" }, "Leads › Leads shows another figure for the same choice: its days run up to today, so far, and it counts every tool, demos booked too. This one is whole days from the lead database. ",
    h("a", { href: S.hashFor({ ...s, tab: "sales/leads", dd: "" }) }, "Open Leads ›"));
}

// A kind the lead store has never recorded is "Not set up", never 0 (notset.js neverRecorded).
function notSent(k, s) {
  const demo = k === "demo_opened" || k === "demo_booked";
  return h("div", { class: "kpi not-set" }, h("div", { class: "k-l" }, name(k)), h("div", { class: "k-n" }, "never recorded by the lead store"),
    h("div", { class: "k-v", title: "Not recorded, never zero" }, "Not set up"),
    h("div", { class: "k-c" }, demo ? h("a", { href: S.hashFor({ ...s, tab: "sales/bookings", dd: "" }) }, "From the booking tool: Calendar bookings ›")
      : "The website's lead store sends none of these"));
}

function counts(m, s, r, f, byDay, inRange, first, out) {
  const types = (f.types || Object.keys(TYPE)).slice();
  const sum = {}; let spam = 0, dup = 0;
  for (const d of inRange) { for (const [k, v] of Object.entries(d.leads || {})) sum[k] = (sum[k] || 0) + v; spam += d.spam || 0; dup += d.duplicates || 0; }
  const leadsN = LEAD_TYPES.reduce((a, k) => a + (sum[k] || 0), 0);
  const readers = r.kind === "today" ? null : inRange.reduce((a, d) => { const day = m.byDay.get(d.day); return a + (day?.state === "ok" ? day.readers || 0 : 0); }, 0);
  const label = r.kind === "today" ? "today so far" : `${inRange.length} of ${r.length} days recorded`;
  // Compare mode: B's leads, only when the lead store recorded every day of A and of B.
  const c = compareOf(m, s);
  const covered = c.ok && r.days.every((d) => byDay.has(d.day)) && c.b.days.every((d) => byDay.has(d.day));
  let cmpB = null;
  if (covered) {
    const sumB = {};
    for (const d of c.b.days) for (const [k, v] of Object.entries(byDay.get(d.day).leads || {})) sumB[k] = (sumB[k] || 0) + v;
    const words = c.kind === "custom" ? "B" : c.name;
    // Per day (a custom B of another length): each period as a typical day.
    const per = c.perDay ? [r.days.length, c.b.days.length] : [1, 1];
    cmpB = { c, sumB, words, vs: (a, k) => versus(a / per[0], (k === "*" ? LEAD_TYPES.reduce((x, t) => x + (sumB[t] || 0), 0) : sumB[k] || 0) / per[1]) };
  }
  // The days-recorded line once, on the first tile; the kinds beside it share it.
  const tile = (title, v, note, sw, quiet = false, key = null) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, title), h("div", { class: "k-n" }, note || ""),
    h("div", { class: "k-v" }, v == null ? "-" : first ? counter(v) : n(v)), h("div", { class: "k-c" }, sw ? h("span", { class: "sw", style: { background: sw } }) : null, quiet ? "" : label),
    cmpB && key && v != null ? h("div", { class: "k-vs" }, cmpB.vs(v, key)) : null);
  const per = readers ? rate(leadsN, readers) : null;
  // A kind the lead store has never recorded (every day it was read) is not set up there: said so, never 0.
  const never = neverRecorded(f);
  out.push(h("section", { class: "s" }, h("div", { class: "kpis tight" },
    tile("Leads", leadsN, "sign-ups, contact forms and early access; spam and duplicates removed", "var(--ink)", false, "*"),
    ...types.map((k) => (never.has(k) ? notSent(k, s) : tile(name(k), sum[k] || 0, k === "demo_opened" ? "opened the booking page" : "", TONE[k], true, k))),
    readers != null ? h("div", { class: "kpi" }, h("div", { class: "k-l" }, "Leads per 100 visitors"), h("div", { class: "k-n" }, "visitors from the verified days of the same range"),
      h("div", { class: "k-v" }, per ? ((leadsN / readers) * 100).toFixed(1) : "-"), h("div", { class: "k-c" }, per ? `${n(leadsN)} from ${n(readers)} visitors` : `too few visitors to rate (under ${MIN_RATE})`)) : null)),
    otherFigure(s, r),
    c.ok && !covered ? h("p", { class: "cmp-why" }, "Leads not compared: the lead store does not cover every day of A and of B.") : null,
    cmpB?.c.perDay ? h("p", { class: "note" }, "Per day: each figure against B is a typical day of its period.") : null,
    h("p", { class: "note" }, spam || dup ? `Left out: ${n(spam)} spam and ${n(dup)} duplicate${dup === 1 ? "" : "s"}. ` : "",
      h("button", { type: "button", class: "pp-link", onclick: openLeftOut }, spam || dup ? "Show them, with test leads" : "Show spam, duplicate and test leads")));

  if (r.kind === "history" && r.length > 1) {
    const days = chartDays(r).map((d) => { const e = byDay.get(d.day); return e ? { ...e, state: "ok" } : { day: d.day, state: d.state === "before" ? "before" : "missing" }; });
    const series = types.map((k) => ({ name: name(k), color: TONE[k] || "var(--ink-3)", get: (d) => d.leads?.[k] || 0 }));
    // Leads keep their own days, so the comparison is theirs: every day of A and of B
    // (the global Compare mode's B: previous period, last year or custom) recorded.
    const prev = cmpB ? (d) => {
      const day = addDays(d.day, -cmpB.c.shift);
      if (day < cmpB.c.b.first || day > cmpB.c.b.last) return null;
      const e = byDay.get(day); return e ? { ...e, state: "ok" } : null;
    } : null;
    if (prev) prev.label = cmpB.words.toLowerCase();
    out.push(h("section", { class: "s" }, h("h2", null, "Per day, by kind"),
      h("p", { class: "sub" }, "A hatched stub is a day with no lead counts: not recorded, never zero."),
      h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not recorded", "", "hatch"], ...(prev ? [[cmpB.words, "", "ghost"]] : [])]),
        columns(days, series, { label: "Leads per day by kind", unit: "leads and demos", H: 210, prev }))));
  }
}

// One breakdown, first touch beside last touch. A lead without the field is
// "(none)": left out of the rows and said under them. Last touch counted by an
// older lead store is missing, never zero.
const TOUCH_EMPTY = { source: "No lead with a known source.", ai: "No lead came from an assistant.", utm_campaign: "No lead carried a campaign tag.", landing: "No landing page recorded." };
function touch(title, field, dim, p, s, words) {
  const ft = p.first_touch?.[field] || {}, lt = p.last_touch?.[field];
  const hasLast = lt && Object.keys(lt).length > 0;
  const keys = [...new Set([...Object.keys(ft), ...Object.keys(lt || {})])].filter((k) => k !== "(none)" && (field !== "source" || !s.source || k === s.source));
  const rows = keys.map((k) => ({ k, first: ft[k] || 0, last: hasLast ? lt[k] || 0 : null }));
  const none = [ft["(none)"] || 0, hasLast ? lt["(none)"] || 0 : null];
  const note = [none[0] ? `${n(none[0])} without one at first touch` : "", none[1] ? `${n(none[1])} at last touch` : "", hasLast ? "" : "Last touch is not recorded for this period."].filter(Boolean).join("; ");
  return h("div", { class: "sheet" }, h("h3", null, `By ${words}`),
    table([{ key: "k", label: title, drill: dim, path: field === "landing" }, { key: "first", label: "First touch", num: true }, { key: "last", label: "Last touch", num: true, fmt: (v) => (v == null ? "-" : n(v)) }],
      { caption: `Leads by ${words}, first and last touch`, rows, file: `leads-by-${dim}-first-last.csv`, search: false, limit: 8, empty: TOUCH_EMPTY[field], note: note || undefined }));
}

// The parts with periods of their own: first touch (30 days and today) and the funnel (the visits' days).
function tail(f, s, out) {
  const p = f.period;
  if (withheld(p) && !f.attribution_rows) out.push(heldNote("Where they came from (30 days)", p));
  else if (p?.first_touch && !f.attribution_rows) {
    out.push(fixed("Where they came from", `${short(f.since && f.since > p.first ? f.since : p.first)} to ${short(p.last)}`,
      h("p", { class: "sub" }, "First touch is the source the lead's own browser remembered from its first visit; last touch, the visit it sent the form from. The lead store keeps both for the last 30 days and today."),
      h("div", { class: "cols tops" },
        touch("Source", "source", "source", p, s, "source"),
        touch("AI assistant", "ai", "assistant", p, s, "AI assistant"),
        touch("Campaign", "utm_campaign", "campaign", p, s, "campaign"),
        touch("Landing page", "landing", "landing", p, s, "landing page"))));
  }
  const fn = f.funnel;
  out.push(fixed("Funnel, by source", fn?.first ? `${short(fn.first)} to ${short(fn.last)}` : "the visits' last days",
    h("p", { class: "sub" }, "From visitors to demos booked. The bar under each figure is its share of that source's visitors."),
    withheld(fn) ? heldNote("The funnel is", fn) : h("div", { class: "sheet" }, funnel(fn, s))));
  if (s.source) out.push(h("p", { class: "note" }, `Narrowed to the source ${s.source}. `, h("button", { type: "button", class: "btn", onclick: () => S.set({ source: "" }) }, "Show every source")));
}

// ------------------------------------------------- the range's own figures

// The parts the date range governs, summed from the file's rows over the
// range's recorded days: where leads came from, their quality by source,
// and the time from first touch to lead.
function ranged(r, f, s, days, length, out) {
  const cover = `${days.size} of ${length} day${length === 1 ? "" : "s"} recorded`;
  const rows = f.attribution_rows;
  if (withheld(rows)) out.push(section2("Where they came from", cover, heldNote("Where leads came from and their quality are", rows)));
  else if (Array.isArray(rows)) {
    const cols = f.attribution_columns || ["day", "type", "status", "touch", "source_type", "ai", "campaign", "utm_source", "utm_medium", "landing", "paid", "n"];
    const at = Object.fromEntries(cols.map((c, i) => [c, i]));
    const mine = rows.filter((x) => days.has(x[at.day]));
    const leadRows = mine.filter((x) => !SKIP.has(x[at.status]));
    out.push(section2("Where they came from", cover, sources(leadRows, at, s), leadsLikely(leadRows, at, f)));
    out.push(section2("Lead quality by source", cover, quality(mine, at, s)));
  }
  const t = f.time_to_convert;
  if (withheld(t)) out.push(section2("Time to convert", cover, heldNote("The time to convert is", t)));
  else if (t?.rows) out.push(section2("Time to convert", cover, convert(t, days)));
}

function section2(title, cover, ...body) {
  return h("section", { class: "s" }, h("h2", null, title, " ", h("small", { class: "note" }, cover)), ...body);
}

// First and last touch over the range, in the shape touch() reads.
function sources(rows, at, s) {
  const p = { first_touch: {}, last_touch: {} };
  for (const k of ["source", "ai", "utm_campaign", "landing"]) { p.first_touch[k] = {}; p.last_touch[k] = {}; }
  let paid = 0, leadsN = 0;
  for (const x of rows) {
    const which = x[at.touch] === "last" ? p.last_touch : p.first_touch;
    for (const [k, col] of [["source", "source_type"], ["ai", "ai"], ["utm_campaign", "campaign"], ["landing", "landing"]]) which[k][x[at[col]]] = (which[k][x[at[col]]] || 0) + x[at.n];
    if (x[at.touch] === "first") { leadsN += x[at.n]; if (x[at.paid]) paid += x[at.n]; }
  }
  return [h("p", { class: "sub" }, "First touch is the source the lead's own browser remembered from its first visit; last touch, the visit it sent the form from. Counted here: every kind above (demos too); spam and duplicates left out."),
    h("div", { class: "cols tops" },
      touch("Source", "source", "source", p, s, "source"),
      touch("AI assistant", "ai", "assistant", p, s, "AI assistant"),
      touch("Campaign", "utm_campaign", "campaign", p, s, "campaign"),
      touch("Landing page", "landing", "landing", p, s, "landing page")),
    leadsN ? h("p", { class: "note" }, `${n(paid)} of ${n(leadsN)} leads and demos came first from a paid click (an ad click id or a paid utm_medium).`) : null];
}

// Statuses by first-touch source. "As of now": the team's later changes rewrite past days.
function quality(rows, at, s) {
  const by = new Map();
  let reviewed = 0;
  for (const x of rows) {
    if (x[at.touch] !== "first") continue;
    const src = x[at.source_type], st = x[at.status], v = x[at.n];
    if (s.source && src !== s.source) continue;
    const e = by.get(src) || { k: src, leads: 0, spam: 0, duplicate: 0, ...Object.fromEntries(STATUS.map(([k]) => [k, 0])) };
    if (SKIP.has(st)) e[st] += v;
    else { e.leads += v; e[st] = (e[st] || 0) + v; if (st !== "new") reviewed += v; }
    by.set(src, e);
  }
  const list = [...by.values()].filter((e) => e.leads || e.spam || e.duplicate);
  if (!list.some((e) => e.leads)) return h("p", { class: "empty" }, "No leads in this range.");
  if (!reviewed) return h("div", { class: "state", html: ICON.info }, h("div", null, h("strong", null, "No statuses set yet. "),
    "Every lead in this range is still \u201cnew\u201d, so quality by source would only be zeros. It fills in once the team marks leads contacted, qualified, won or lost in the website's admin."));
  for (const e of list) { e.rev = e.leads - e.new; e.good = e.qualified + e.won; }
  const rate = (e) => (e.rev >= MIN_RATE ? pct1(e.good, e.rev) : null);
  const cols = [{ key: "k", label: "First-touch source", fmt: (v) => (v === "(none)" ? "No first touch recorded" : v) }, { key: "leads", label: "Leads and demos", num: true },
    ...STATUS.map(([k, label]) => ({ key: k, label, num: true })),
    { key: "rate", label: "Qualified or won, of reviewed", num: true, sort: (e) => (e.rev >= MIN_RATE ? e.good / e.rev : null), fmt: (_, e) => rate(e) ?? h("span", { class: "few" }, `too few (${n(e.rev)})`), csv: (e) => (e.rev >= MIN_RATE ? (e.good / e.rev).toFixed(4) : "") },
    { key: "spam", label: "Spam", num: true }, { key: "duplicate", label: "Duplicates", num: true }];
  return [h("p", { class: "sub" }, `Statuses are as the website's admin has them now: when the team changes one, past days change with it. "Reviewed" is every lead no longer new; the share is given over at least ${MIN_RATE} reviewed.`),
    h("div", { class: "sheet" }, table(cols, { caption: "Lead quality by first-touch source", rows: list, file: "leads-quality-by-source.csv", search: false, limit: 10, sortKey: "leads" }))];
}

// A bar list in a fixed order (blist ranks; time buckets must keep theirs).
// Shares only over at least MIN_RATE: below it, counts alone.
function ordered(items, color) {
  const max = Math.max(1, ...items.map(([, v]) => v)), sum = items.reduce((a, [, v]) => a + v, 0);
  return h("ul", { class: `blist${reduced() ? "" : " play"}` }, items.map(([k, v], i) => h("li", null,
    h("span", { class: "bl-bar", style: { width: `${(v / max) * 100}%`, background: color, animationDelay: `${i * 0.03}s` } }),
    h("span", { class: "bl-l", title: k }, k), h("span", { class: "bl-v" }, n(v)), h("span", { class: "bl-p" }, sum >= MIN_RATE ? pct1(v, sum) : ""))));
}

// From first touch to lead, over the range's days; the middle only over 10 or more known times.
function convert(t, days) {
  const got = {}, seen = {};
  for (const [day, , b, v] of t.rows) if (days.has(day)) got[b] = (got[b] || 0) + v;
  for (const [day, , b, v] of t.visits_rows || []) if (days.has(day)) seen[b] = (seen[b] || 0) + v;
  const known = Object.keys(WAIT).map((k) => [k, got[k] || 0]);
  const knownN = known.reduce((a, [, v]) => a + v, 0);
  if (!knownN && !got.unknown && !got.clock_error) return h("p", { class: "empty" }, "No leads in this range.");
  let middle = null;
  if (knownN >= MIN_RATE) { let run = 0; for (const [k, v] of known) { run += v; if (run * 2 >= knownN) { middle = k; break; } } }
  const left = [got.unknown ? `${n(got.unknown)} without a first-touch time` : "", got.clock_error ? `${n(got.clock_error)} with a clock error (the first touch is dated after the lead)` : ""].filter(Boolean);
  const visits = t.visits_rows ? Object.keys(VISITS).map((k) => [VISITS[k], seen[k] || 0]) : null;
  const visitsKnown = visits ? visits.reduce((a, [, v]) => a + v, 0) : 0;
  return h("div", { class: "cols tops" },
    h("div", { class: "sheet" }, h("h3", null, "From first touch to lead"),
      knownN ? ordered(known.map(([k, v]) => [WAIT[k], v]), "var(--g-people)") : h("p", { class: "empty" }, "No lead in this range has a first-touch time."),
      h("p", { class: "note" }, [middle ? `The middle lead of the ${n(knownN)} with a known time came ${WAIT[middle].toLowerCase()} after its first touch. ` : knownN ? `Too few known times to give a middle (${n(knownN)}, under ${MIN_RATE}). ` : "",
        t.median_hours != null ? `Over the file's 180 days the median is ${t.median_hours < 48 ? `${t.median_hours} hours` : `${(t.median_hours / 24).toFixed(1)} days`}. ` : "",
        left.length ? `Left out: ${left.join("; ")}. ` : "", "Elapsed time from the first visit the lead's browser remembered; spam and duplicates left out."].join(""))),
    visits ? h("div", { class: "sheet" }, h("h3", null, "Visits up to the lead"),
      visitsKnown ? ordered(visits, "var(--g-search_engines)") : h("p", { class: "empty" }, "No lead in this range has a visit count."),
      h("p", { class: "note" }, `The browser's own count of its visits when it sent the form.${seen.unknown ? ` ${n(seen.unknown)} without a count, left out.` : ""}`)) : null);
}
