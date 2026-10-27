// Leads & sales > Leads: its period (2.27). The owner, 2026-10-22: "if you are looking at 7
// days it should also show today ... today is 1 + last 6 = 7 days", and "show clear dates
// from and to so it's not confusing".
//
// On Leads, 7, 30 and 90 days are calendar days ending today: today so far and the 6 (29, 89)
// whole days before it. Every other preset, and every other tab of the section (Summary,
// Sources: whole days, up to yesterday), is as before.
//
//   leadsRange(m, s)          the period Leads lists and counts (data.js rangeOf otherwise)
//   spanWords(a, b, today)    "Thu 16 Oct to Wed 22 Oct (today, so far)"; the year only when
//                             the days cross a year, or are not this year
//   headWords(r, m)           "Last 7 days: Thu 16 Oct to Wed 22 Oct (today, so far)"
//   versusLive(...)           the change against the period before, like for like: its whole
//                             days, then its last day to this hour (conversions.json
//                             today.same_time, recounted by audit_conversions_leads)
//   liveNote(...)             today's part of the period ("2 of them today so far", Show
//                             today (live)) and what is verified, in one short line
//
// Today's part is the lead store's rows now: conversions.json counts today like every day,
// and its second count (audit_conversions.py) recounts it on every redraw; the morning run
// counts it again once it is whole. A part-day is never said as a whole one.

import { h, n, change, addDays, parseDay } from "../ui.js";
import * as S from "../state.js";
import { rangeOf, daysBetween } from "../data.js";
import { time as tzTime } from "../tz.js";
import { leadsOn, convFile } from "./leadfigs.js";

// The presets that end today on Leads, and their length in days.
export const LIVE = { "7d": 7, "30d": 30, "90d": 90 };

export function leadsRange(m, s) {
  const k = LIVE[s?.range];
  if (!k || !m?.today) return rangeOf(m, s);
  const first = addDays(m.today, -(k - 1));
  return { kind: "history", live: true, first, last: m.today, length: k, days: daysBetween(m, first, m.today) };
}

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

// The heading's period: "Last 7 days: Thu 16 Oct to Wed 22 Oct (today, so far)".
export const headWords = (r, m) => `Last ${n(r.length)} days: ${spanWords(r.first, r.last, m.today)}`;

// Inside a sentence ("No new leads in ..."): "the last 7 days, Thu 16 Oct to Wed 22 Oct (today,
// so far)"; brief, after a first one: "the last 30 days, Wed 23 Sep to today".
export const sentenceWords = (r, m, brief = false) => `the last ${n(r.length)} days, ${spanWords(r.first, r.last, m.today, brief)}`;

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
  if (!r?.live || !got) return "";
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

/* Today's part of the period, and what is verified, in one line under the count:
   "Today so far: 2 of these 4 leads · Show today (live) → · Fri 16 Oct to Wed 21 Oct are
   whole days, verified; today is live and verified again once it is whole. Summary and
   Sources count whole days: Thu 15 Oct to Wed 21 Oct." today: today's figure with the same
   filters as the count (null when the count line counts rows: then no number); total: the
   period's figure. */
export function liveNote(m, s, r, today, total = null) {
  if (!r?.live) return null;
  const yday = addDays(m.today, -1);
  const other = rangeOf(m, s);
  const bits = [];
  if (today && today.ok && today.leads) {
    const k = `${n(today.leads)} new lead${today.leads === 1 ? "" : "s"}`;
    bits.push("Today so far: ", h("b", null, total == null || total < today.leads ? k : total === today.leads ? `${k}, all of the period's` : `${n(today.leads)} of these ${n(total)} leads`), " ",
      h("button", { type: "button", class: "linkish sa-today-go", onclick: () => S.set({ range: "today" }) }, "Show today (live)", h("span", { "aria-hidden": "true" }, " →")), " · ");
  } else if (today && today.ok) bits.push("Today so far: none yet · ");
  bits.push(`${spanWords(r.first, yday, m.today)} are whole days, verified; today is live and verified again once it is whole.`);
  // Why Summary's Leads figure is another number (2.42, the UX audit): said here, in plain words.
  if (other.kind === "history" && !other.all) {
    const span = spanWords(other.first, other.last, m.today);
    const db = !(m?.x?.leads && m.x.leads.available === false && /not set/.test(String(m.x.leads.error || "")));
    bits.push(db ? ` Summary and Sources count other leads, so their figures differ: whole days only (${span}), from the lead database (sign-ups, contact forms and early access, no demos booked).`
      : ` Summary and Sources count whole days only (${span}), so their figures differ by today's leads and the day before the period.`);
  }
  return h("p", { class: "sa-today sa-live", role: "status",
    title: "Today's leads are the lead store's rows now, counted like every day and recounted on every redraw. Once today is whole, the morning run counts it again." },
  h("span", { class: "live-dot", "aria-hidden": "true" }), ...bits);
}
