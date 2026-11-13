// Leads & sales: the one period every tab counts (2.27 on Leads; #32 on every tab). The owner,
// 2026-10-22: "if you are looking at 7 days it should also show today ... today is 1 + last 6 =
// 7 days", and "show clear dates from and to so it's not confusing". #32 (11 Nov): the same
// click showed different counts on Leads and on Summary, because Leads counted today and the
// others did not. Now every tab of the section (Leads, Summary, Revenue, Funnels) asks this
// file for its period, and no tab builds its own (tests/js/sales-period.mjs checks the source).
//
// The rule: a period includes today, and today's part is marked live.
//   7, 30, 90 days   today so far and the 6 (29, 89) whole days before it
//   All time         from the first day there is data to today so far
//   Custom           as chosen; a custom period that reaches today ends today, so far
//   Today            today so far (live)
//   Yesterday        one whole day (the one choice that ends before today)
//
//   salesRange(m, s)          the period (data.js rangeOf's shape: {kind, first, last, length,
//                             days}, plus live: true when it ends today)
//   salesLive(s)              true when the period may end today (the 2-minute redraw)
//   periodDays(m, r)          the period's days (ISO), as the lead figures count them
//   periodBefore(m, r)        the whole period before one of whole days (Yesterday), or null
//   spanWords(a, b, today)    "Thu 16 Oct to Wed 22 Oct (today, so far)"; the year only when
//                             the days cross a year, or are not this year
//   headWords(r, m)           "Last 7 days: Thu 16 Oct to Wed 22 Oct (today, so far)"
//   versusLive(...)           the change against the period before, like for like: its whole
//                             days, then its last day to this hour (conversions.json
//                             today.same_time, recounted by audit_conversions_leads)
//   periodCheck(...)          the period's Leads figure against conversions.json
//                             today.periods (its second count: one SQL window per period);
//                             a figure that does not match is withheld
//   liveNote(...)             today's part of the period ("2 of them today so far", Show
//                             today (live)) and what is verified, in one short line
//
// Today's part is the lead store's rows now: conversions.json counts today like every day,
// and its second count (audit_conversions.py) recounts it on every redraw; the morning run
// counts it again once it is whole. A part-day is never said as a whole one.

import { h, n, change, addDays, dayDiff, parseDay } from "../ui.js";
import * as S from "../state.js";
import { rangeOf, allTime, daysBetween, previousOf } from "../data.js";
import { time as tzTime } from "../tz.js";
import { leadsOn, convFile } from "./leadfigs.js";

// The presets that end today, and their length in days.
export const LIVE = { "7d": 7, "30d": 30, "90d": 90 };

// A live range: first to today, today's day included (a day not yet in history is "missing"
// there; the lead files hold today like every day).
function toToday(m, first, extra = {}) {
  const f = first > m.today ? m.today : first;
  return { kind: "history", live: true, first: f, last: m.today, length: dayDiff(f, m.today) + 1, days: daysBetween(m, f, m.today), ...extra };
}

/* The one period of every Leads & sales tab (see the top of this file). */
export function salesRange(m, s) {
  if (!m?.today) return rangeOf(m, s);
  const k = LIVE[s?.range];
  if (k) return toToday(m, addDays(m.today, -(k - 1)));
  if (s?.range === "all") {
    const a = allTime(m);
    return toToday(m, a.first, { all: true, begins: a.begins, cut: a.cut });
  }
  if (s?.range === "custom" && /^\d{4}-\d\d-\d\d$/.test(s.from || "") && /^\d{4}-\d\d-\d\d$/.test(s.to || "") && s.to >= m.today && s.from <= s.to) return toToday(m, s.from, { custom: true });
  // Today (live) and Yesterday (one whole day): data.js's own.
  return rangeOf(m, { ...s, inc: "" });
}
// Kept for older callers and tests: Leads' period is the section's period.
export const leadsRange = salesRange;

/* The period's days, as the lead figures count them (ISO). All time starts at the leads' own
   first day (conversions.json `since`) when the site's history began earlier: before it nothing
   could be recorded, so those days are not "not recorded" here. */
export function periodDays(m, r) {
  if (r.kind === "today") return [m.today];
  const since = r.all ? convFile(m)?.since : null;
  return r.days.map((d) => d.day).filter((d) => !since || d >= since);
}

/* The whole period before a period of whole days (Yesterday, an older custom period), for its
   change; null for one that ends today (its comparison is versusLive, to this hour). */
export const periodBefore = (m, r) => (r?.live ? null : previousOf(m, r));

/* The period may end today (every choice but Yesterday and a custom period before today):
   the tab is drawn again every 2 minutes (s-overview.js `live`). */
export const salesLive = (s) => s?.range !== "yesterday";

const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// "Thu 16 Oct", or "Thu 16 Oct 2026" with the year.
export function dayWords(iso, year = false) {
  const d = parseDay(iso);
  return `${WD[d.getUTCDay()]} ${d.getUTCDate()} ${MON[d.getUTCMonth()]}${year ? ` ${d.getUTCFullYear()}` : ""}`;
}

/* From and to, in words. today: the site's today, so a range ending today says so, and a
   range not of this year carries its year (as does one crossing a year). */
export function spanWords(first, last, today = "", brief = false) {
  const year = first.slice(0, 4) !== last.slice(0, 4) || (today && last.slice(0, 4) !== today.slice(0, 4));
  const end = last !== today ? dayWords(last, !!year) : brief ? "today" : `${dayWords(last, !!year)} (today, so far)`;
  return first === last ? end : `${dayWords(first, !!year)} to ${end}`;
}

// The heading's period: "Last 7 days: Thu 16 Oct to Wed 22 Oct (today, so far)"; All time and
// a custom period that reach today say so in the same shape.
export const headWords = (r, m) => `${r.all ? "All time" : LIVE[`${r.length}d`] === r.length && !r.custom ? `Last ${n(r.length)} days` : `${n(r.length)} days`}: ${spanWords(r.first, r.last, m.today)}`;

// Inside a sentence ("No new leads in ..."): "the last 7 days, Thu 16 Oct to Wed 22 Oct (today,
// so far)"; brief, after a first one: "the last 30 days, Wed 23 Sep to today".
export const sentenceWords = (r, m, brief = false) => `${r.all ? "all time" : `the last ${n(r.length)} days`}, ${spanWords(r.first, r.last, m.today, brief)}`;

// The CSV's name: the period's days, unambiguous (ISO).
export const csvName = (r, m) => {
  const a = r.kind === "today" ? m.today : r.first, b = r.kind === "today" ? m.today : r.last;
  return a === b ? `leads-${a}.csv` : `leads-${a}-to-${b}.csv`;
};

/* The period before r (live), like for like: the same number of days, its last day counted
   to this hour. {first, last, whole: [days], cut: same_time entry} or null. */
export function previousLive(m, r) {
  const st = convFile(m)?.today;
  const k = r.length, first = addDays(r.first, -k), last = addDays(m.today, -k);
  const whole = [];
  for (let d = first; d < last; d = addDays(d, 1)) whole.push(d);
  const cut = st?.state === "ok" && st.day === m.today ? (st.same_time?.days || []).find((e) => e.back === k && e.day === last) || null : null;
  return { first, last, whole, cut };
}

/* "100% more than the 7 days before (2 leads: Thu 9 Oct to Wed 15 Oct, up to 14:00 EDT)".
   fm: the model with the Leads figure's file for the filters on; got: the period's figure.
   The day cut to this hour is counted by kind (What) only: with a label or a breakdown on,
   no comparison, and the words say why. Never a part-day against whole ones. */
export function versusLive(fm, m, r, got, s = {}, fig = {}) {
  if (!r?.live || r.all || !got) return "";
  const p = previousLive(m, r);
  if (s.llabel || fig.dim) return `no change shown with this filter: the ${n(r.length)} days before are counted to this hour by kind only`;
  const was = leadsOn(fm, p.whole);
  if (!p.cut || p.cut.state !== "ok" || !was || !was.whole || !got.whole) return "";
  const cut = s.lact ? (p.cut.actions || {})[s.lact] || 0 : p.cut.leads;
  const before = was.leads + cut;
  if (!got.leads && !before) return "";
  const cmp = change(got.leads, before);
  const when = `${n(before)} lead${before === 1 ? "" : "s"}: ${spanWords(p.first, p.last, m.today)}, up to ${tzTime(p.cut.until)}`;
  const head = cmp[0] ? `${cmp[1]} ${cmp[0] === "▲" ? "more" : "fewer"} than` : `${cmp[1]} as`;
  return `${head} the ${n(r.length)} days before (${when})`;
}

/* The period's Leads figure against its second count (#32): conversions.json today.periods
   holds each 7, 30 and 90 days that end today as the server summed them, recounted in one SQL
   window by audit_conversions_leads.check_periods. got: leadsOn over the period (s.lact: one
   kind, which the file states by action). {ok: true} when they agree or there is nothing to
   check against (another period, a label or a breakdown on, a period not whole); {ok: false,
   why} when they differ: the figure is then withheld, never shown. */
export function periodCheck(m, r, got, s = {}, fig = {}) {
  const f = convFile(m);
  if (!r?.live || !got || !f || s.llabel || fig.dim) return { ok: true };
  const st = f.today;
  if (!st || st.state !== "ok" || st.day !== m.today) return { ok: true };
  const e = (st.periods || []).find((x) => x.back === r.length && x.first === r.first && x.last === r.last);
  if (!e || e.state !== "ok" || !got.whole) return { ok: true };
  const want = s.lact ? (e.actions || {})[s.lact] || 0 : e.leads;
  return want === got.leads ? { ok: true, checked: true }
    : { ok: false, why: `The ${n(r.length)} days' leads do not reconcile: ${n(got.leads)} summed day by day, ${n(want)} counted for the whole period. Withheld until the next redraw counts them again.` };
}

/* Today's part of the period, and what is verified, in one line under the count:
   "Today so far: 2 of these 4 leads · Show today (live) → · Fri 16 Oct to Wed 21 Oct are
   whole days, verified; today is live and verified again once it is whole." today: today's
   figure with the same filters as the count (null when the count line counts rows: then no
   number); total: the period's figure. Every Leads & sales tab counts the same days (#32),
   so no line says another tab's figure differs. */
export function liveNote(m, s, r, today, total = null) {
  if (!r?.live) return null;
  const yday = addDays(m.today, -1);
  const bits = [];
  if (today && today.ok && today.leads) {
    const k = `${n(today.leads)} new lead${today.leads === 1 ? "" : "s"}`;
    bits.push("Today so far: ", h("b", null, total == null || total < today.leads ? k : total === today.leads ? `${k}, all of the period's` : `${n(today.leads)} of these ${n(total)} leads`), " ",
      h("button", { type: "button", class: "linkish sa-today-go", onclick: () => S.set({ range: "today" }) }, "Show today (live)", h("span", { "aria-hidden": "true" }, " →")), " · ");
  } else if (today && today.ok) bits.push("Today so far: none yet · ");
  bits.push(r.first <= yday ? `${spanWords(r.first, yday, m.today)} ${r.first === yday ? "is a whole day" : "are whole days"}, verified; today is live and verified again once it is whole.`
    : "Today is live and verified again once it is whole.");
  return h("p", { class: "sa-today sa-live", role: "status",
    title: "Today's leads are the lead store's rows now, counted like every day and recounted on every redraw. Once today is whole, the morning run counts it again." },
  h("span", { class: "live-dot", "aria-hidden": "true" }), ...bits);
}
