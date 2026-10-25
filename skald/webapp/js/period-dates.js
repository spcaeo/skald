// The period's exact dates, in words (release 2: Overview › Summary and Traffic › Pages).
//
//   "Include today" (inc=1 in the address): 7, 30 and 90 days end today, with today so far,
//   instead of yesterday. Only Summary and Pages honour it (INC_TABS); elsewhere a period
//   is whole days, as before. On 15 Jan:
//     7 days including today   9–15 Jan, the period before 2–8 Jan
//     7 whole days             8–14 Jan, the period before 1–7 Jan
//   A period that includes today is never compared: today is not over, and no earlier day
//   is kept cut at the same hour (only yesterday is, for Today · Live).
//
// Pure: dates are ISO days (YYYY-MM-DD) in the site's zone; no DOM, so node tests it
// (tests/js/period.mjs). data.js rangeOf builds the days; period-line.js draws the words.

import { addDays, dayDiff, short, weekday, clock } from "./ui.js";

export const INC_TABS = new Set(["overview/summary", "traffic/pages"]);
export const INC_RANGES = { "7d": 7, "30d": 30, "90d": 90 };
// "About the same": a change of this many visits or fewer is normal day-to-day swing at
// the small counts most sites have; above it the arrow and the percentage are shown.
export const SAME = 3;

export const incTab = (s) => INC_TABS.has(s?.tab) && !s?.page;
export const incApplies = (s) => incTab(s) && Object.hasOwn(INC_RANGES, s?.range || "");
export const incOn = (s) => s?.inc === "1" && incApplies(s);

const year = (iso) => iso.slice(0, 4);
const month = (iso) => iso.slice(0, 7);

/* "9–15 Jan", "29 Oct–4 Nov", "28 Dec 2026–3 Jan 2027", "15 Jan". */
export function span(first, last) {
  if (first === last) return short(first);
  if (year(first) !== year(last)) return `${short(first)} ${year(first)}–${short(last)} ${year(last)}`;
  if (month(first) === month(last)) return `${Number(first.slice(8))}–${short(last)}`;
  return `${short(first)}–${short(last)}`;
}

/* The two windows of a k-day period on `today`: A ends today (inc) or yesterday, B is the
   k days just before A. {a: {first, last}, b: {first, last}}. */
export function windows(today, k, inc) {
  const last = inc ? today : addDays(today, -1);
  const first = addDays(last, -(k - 1));
  const bLast = addDays(first, -1);
  return { a: { first, last }, b: { first: addDays(bLast, -(k - 1)), last: bLast } };
}

/* The first day a full k against k is there, when history's first whole day is `firstWhole`:
   B then starts on it. {on, a, b}: the day, and that day's two windows. */
export function firstFull(firstWhole, k, inc) {
  const on = addDays(firstWhole, inc ? 2 * k - 1 : 2 * k);
  const w = windows(on, k, inc);
  return { on, ...w };
}

/* The first whole, verified day of history, or null. `byDay` a Map of day -> {state}. */
export function firstWholeDay(byDay, firstDay) {
  const days = [...(byDay?.keys?.() || [])].filter((d) => !firstDay || d >= firstDay).sort();
  return days.find((d) => byDay.get(d)?.state === "ok") || null;
}

/* B's state while Compare is on, for a tile or a row: "ok", "not_measured" (B reaches back
   before history, or a day was never collected), or "not_whole" (a day of B is partial or
   withheld). `b` a range with days. */
export function beforeState(b) {
  if (!b?.days?.length) return "not_measured";
  if (b.days.some((d) => d.state === "before" || d.state === "missing")) return "not_measured";
  return b.days.every((d) => d.state === "ok") ? "ok" : "not_whole";
}

/* The change in a tile's or a row's words: {text, dir} with dir up, down, same or none.
   prev null: not measured. |now - prev| <= SAME: about the same. */
export function changeWords(now, prev, { state = "ok" } = {}) {
  if (state !== "ok" || prev == null) return { text: state === "not_whole" ? "before: not complete" : "before: not measured", dir: "none" };
  if (now == null) return { text: "not recorded", dir: "none" };
  if (Math.abs(now - prev) <= SAME) return { text: "≈ about the same", dir: "same" };
  const up = now > prev;
  const pct = prev ? `${Math.round(Math.abs((now - prev) / prev) * 100)}%` : "new";
  return { text: `${up ? "▲" : "▼"} ${pct}`, dir: up ? "up" : "down" };
}

/* The words of the period line (S3): {now, prev, how, kind}.
   r: data.js rangeOf's range; b: B's range or null; live: m.live (Today); example: the
   "On 15 Jan" day the line uses to show what the period means (default: 15 Jan this year). */
export function lineWords(r, s, { b = null, live = null, today, example } = {}) {
  const k = INC_RANGES[s.range];
  const ex = example || `${String(today || r.last || "").slice(0, 4) || "2027"}-01-15`;
  if (r.kind === "today") {
    const at = live?.generated_at ? clock(live.generated_at) : "";
    return { kind: "today", now: at ? `Today until ${at}` : "Today so far", prev: at ? `yesterday until ${at}` : "yesterday at the same hour",
      how: "Today so far against the same hours of yesterday, so the two are fair to compare" };
  }
  if (s.range === "yesterday") {
    return { kind: "yesterday", now: `Yesterday, ${weekday(r.first)} ${short(r.first)}`, prev: b ? `${weekday(b.first)} ${short(b.first)}` : null,
      how: "A whole day against the day before (Include today does not change it)" };
  }
  if (k && r.inc) {
    const w = windows(ex, k, true);
    return { kind: "inc", now: `Last ${k} days including today: ${span(r.first, r.last)}`, prev: b ? span(b.first, b.last) : null,
      how: `${k} calendar days ending today, with today so far. On ${short(ex)} that is ${span(w.a.first, w.a.last)} against ${span(w.b.first, w.b.last)}` };
  }
  if (k) {
    const w = windows(ex, k, false);
    return { kind: "whole", now: `Last ${k} whole days: ${span(r.first, r.last)}`, prev: b ? span(b.first, b.last) : null,
      how: `${k} complete days ending yesterday. On ${short(ex)} that is ${span(w.a.first, w.a.last)} against ${span(w.b.first, w.b.last)}` };
  }
  const len = dayDiff(r.first, r.last) + 1;
  return { kind: r.all ? "all" : "custom", now: `${r.all ? "All time: " : ""}${span(r.first, r.last)}${len > 1 ? `, ${len} days` : ""}`,
    prev: b ? span(b.first, b.last) : null, how: r.all ? "Every whole day this site has, to yesterday" : "The whole days you chose" };
}

/* Why B is not there, in the line's words, when Compare is on and B was not measured:
   "before: not measured", and the first day a full comparison comes. */
export function notMeasuredWords(r, s, { firstWhole, site = "this site", firstDay } = {}) {
  const k = INC_RANGES[s.range] || (r.kind === "history" ? r.length : 1);
  const since = firstDay ? ` (measured from ${short(firstDay)})` : "";
  if (!firstWhole) return `Before: not measured. ${site} has no whole, verified day yet${since}, so there is nothing to compare with. Skald says so instead of showing a rise.`;
  if (s.range === "custom" || r.all) return `Before: not measured. That period was before ${site} was measured${since}, so there is nothing to compare with. Skald says so instead of showing a rise.`;
  const f = firstFull(firstWhole, k, false);
  const what = k === 1 ? "a day against the day before" : `${k} days against the ${k} before`;
  return `Before: not measured. ${span(addDays(r.first, -k), addDays(r.first, -1))} was before ${site} was measured${since}, so there is nothing to compare with yet. Skald says so instead of showing a rise. The first full ${what} is on ${short(f.on)}${year(f.on) !== year(r.last) ? ` ${year(f.on)}` : ""} (${span(f.a.first, f.a.last)} against ${span(f.b.first, f.b.last)}).`;
}
