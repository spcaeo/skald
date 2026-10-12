// Loading the JSON files written beside the page, and summing days into ranges.
//
// The honesty rules live here, so no tab can forget them:
//   * a range is summed from verified ("ok") days only; partial, withheld and
//     missing days are counted and named, never added in as zeros
//   * a change against the previous range is given only when both ranges are
//     complete - every day verified - otherwise "not comparable"
//   * "today" is the live snapshot: partial by nature, never compared
//   * breakdowns are stored each on its own, so a filter narrows the list it
//     belongs to and is never crossed with another (Canada AND Chrome)

import { addDays, dayDiff, clock, long } from "./ui.js";
import { adapt } from "./adapt.js";
import { csrfHeaders } from "./tabs/ipmanager.js";
import { DEMO, DEMO_SAYS, setDemo, demoFile } from "./demo.js";

export const GROUPS = [
  ["people", "People"], ["answer_engines", "AI assistants"], ["search_engines", "Search engines"],
  ["bots", "Bots and scanners"], ["ours", "Our own"],
];
export const color = (g) => `var(--g-${g})`;

const cache = new Map();
export async function getJSON(url, fresh) {
  // The demo has no helper: its answers are files beside the page, or there is none to ask.
  if (DEMO.on && /^api\//.test(url)) { url = demoFile(url); if (!url) return null; }
  if (!fresh && cache.has(url)) return cache.get(url);
  const res = await fetch(url, { cache: "no-store", credentials: "same-origin" });
  // A body nobody reads keeps the connection busy: let it go.
  if (res.status === 404) { res.body?.cancel(); return null; }
  if (!res.ok) { res.body?.cancel(); throw new Error(`${url} answered ${res.status}`); }
  const body = await res.json();
  cache.set(url, body);
  return body;
}

// Where a view's files are: the site's own beside this page, a view's in its folder.
export const base = (view) => (view && view !== "all" ? `${view}/data/` : "data/");

// Files the data layer writes beside app.json (DATA-CONTRACT.md). Each is
// optional: a tab whose file is not there yet says so instead of failing.
export const EXTRA = ["insights", "not_found", "ai_activity", "campaigns", "pages", "overview", "ours", "bots", "alerts", "quality", "markers", "leads", "favicons", "sites", "robots", "speed", "funnels", "page_index", "events", "conversions"];
// requests.json is today's whole request log: the Requests tab fetches it itself, only when it is open.

export async function load(s, { fresh = false } = {}) {
  const get = (name) => getJSON(base(s.view) + name, fresh);
  const raw = await adapt(get);
  setDemo(raw.demo);
  // app.json lists the files written beside it; ask only for those, so a file not there yet is not a failed request.
  // sites.json is written beside app.json by the site list (multisite.py), not by the data
  // files app.json lists, so it is always asked for (2.6.0: before, the switcher never had it).
  const listed = (n) => n === "sites" || !Array.isArray(raw.files) || raw.files.includes(n);
  // favicons.json and sites.json live in the site's own data folder only; a view's page reads those.
  const fetchOne = (n) => (n === "favicons" || n === "sites" ? getJSON(`data/${n}.json`, fresh) : get(`${n}.json`));
  const extra = await Promise.all(EXTRA.map((n) => (listed(n) ? fetchOne(n).catch(() => null) : null)));
  // A file whose builder failed holds only {"state": "error", "error"}: kept apart, so a tab says
  // "could not be built" rather than showing it empty.
  raw.failed = Object.fromEntries(EXTRA.map((n, i) => [n, extra[i]?.state === "error" ? extra[i].error || "no reason given" : null]).filter(([, e]) => e));
  raw.x = Object.fromEntries(EXTRA.map((n, i) => [n, extra[i] && extra[i].schema_version === 1 && extra[i].state !== "error" ? extra[i] : null]));
  // Returning readers come from overview.json; merge them into the days they belong to.
  for (const d of raw.x.overview?.days || []) {
    const day = raw.byDay.get(d.day);
    if (day && d.returning) day.returning = d.returning;
  }
  raw.view = s.view || "all";
  raw.options = options(raw);
  raw.stamp = stampOf(raw);
  raw.liveStamp = raw.live?.generated_at || "";
  return raw;
}

// The bar's "last updated": the live count's time today, else the last day recorded.
function stampOf(m) {
  if (m.live?.generated_at && m.live.day === m.today) return `Updated ${clock(m.live.generated_at)}`;
  return `Recorded to ${long(m.anchor)}`;
}

export function viewList(m) {
  return [["all", "All pages"], ...(m.views || []).map((v) => [v.slug, v.name])];
}

// ---------------------------------------------------------------- ranges
export function rangeOf(m, s) {
  if (s.range === "today") return { kind: "today", first: m.today, last: m.today, length: 1, days: [] };
  // Yesterday is the calendar day before today, recorded or not: before the
  // morning run it shows as not recorded yet, never as an older day.
  if (s.range === "yesterday") {
    const d = addDays(m.today, -1);
    return { kind: "history", first: d, last: d, length: 1, days: daysBetween(m, d, d) };
  }
  let first, last = m.anchor;
  if (s.range === "custom") { first = s.from; last = s.to; }
  else first = addDays(m.anchor, -(Number.parseInt(s.range, 10) - 1));
  if (last > m.anchor) last = m.anchor;
  if (first > last) first = last;
  const length = dayDiff(first, last) + 1;
  return { kind: "history", first, last, length, days: daysBetween(m, first, last) };
}

export function previousOf(m, r) {
  if (r.kind !== "history") return null;
  const last = addDays(r.first, -1), first = addDays(last, -(r.length - 1));
  return { kind: "history", first, last, length: r.length, days: daysBetween(m, first, last) };
}

export function daysBetween(m, first, last) {
  const out = [];
  for (let d = first; d <= last; d = addDays(d, 1)) {
    const e = m.byDay.get(d);
    if (e) out.push(e);
    else out.push({ day: d, state: m.firstDay && d < m.firstDay ? "before" : "missing" });
  }
  return out;
}

// The days a chart draws: from the first day history holds, never a run of
// empty slots before it - but at least a week, so one day is not one wide bar.
export function chartDays(r) {
  const i = r.days.findIndex((d) => d.state !== "before");
  if (i < 0) return r.days;
  return r.days.slice(Math.max(0, Math.min(i, r.days.length - 7)));
}

export function coverage(r) {
  const c = { ok: 0, partial: [], withheld: [], missing: [], before: 0 };
  for (const d of r.days) {
    if (d.state === "ok") c.ok += 1;
    else if (d.state === "before") c.before += 1;
    else (c[d.state] || c.missing).push(d.day);
  }
  c.complete = c.ok === r.length;
  return c;
}

// ------------------------------------------------------------------- sums
const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);
function merge(into, from) {
  for (const [k, v] of Object.entries(from)) {
    if (typeof v === "number") into[k] = (into[k] || 0) + v;
    else if (isObj(v)) merge(into[k] || (into[k] = {}), v);
  }
  return into;
}

/* A range's totals: every number and every nested {label: count} summed over
   its verified days only. `unmeasured` counts the verified days that lack a
   figure because they were collected before it existed; a tab that shows such
   a figure says so instead of summing some of the days. */
export function total(days) {
  const ok = days.filter((d) => d.state === "ok");
  if (!ok.length) return null;
  const out = {};
  for (const d of ok) merge(out, d);
  out.days = ok.length;
  out.unmeasured = {
    by: ok.filter((d) => !d.by).length,
    readers: ok.filter((d) => d.readers == null).length,
    visit: ok.filter((d) => !d.visit).length,
    health: ok.filter((d) => !d.statuses).length,
    returning: ok.filter((d) => !d.returning).length,
  };
  return out;
}

// The figures a tab reads for the chosen range: totals of the days, or today's snapshot.
export function figures(m, s) {
  const r = rangeOf(m, s);
  if (r.kind === "today") return { r, t: m.live && m.live.state === "ok" && m.live.day === m.today ? m.live.figures : null, live: true };
  return { r, t: total(r.days), cov: coverage(r) };
}

// ---------------------------------------------------------------- filters
// Which global filters each tab can apply is its `filters` option (js/tabs/s-*.js); the rest
// are shown greyed, with a reason.

export function pathMatch(s) {
  if (!s.path) return () => true;
  const p = s.path.toLowerCase();
  return s.pathmode === "starts" ? (x) => String(x).toLowerCase().startsWith(p) : (x) => String(x).toLowerCase().includes(p);
}

// {label: n} -> [[label, n]], biggest first, keeping only labels the filter lets through.
export function ranked(obj, keep = () => true) {
  return Object.entries(obj || {}).filter(([k, v]) => v && keep(k)).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function options(m) {
  const seen = { country: new Set(), source: new Set(), device: new Set(), browser: new Set(), campaign: new Set(), referrer: new Set() };
  const add = (by) => { if (!by) return; for (const k of Object.keys(seen)) for (const v of Object.keys(by[k] || {})) seen[k].add(v); };
  for (const d of m.byDay.values()) add(d.by);
  add(m.live?.figures?.by);
  for (const j of m.journeys || []) for (const k of Object.keys(seen)) if (j[k]) seen[k].add(j[k]);
  for (const k of Object.keys(seen)) seen[k].delete("(all others)");
  const out = {};
  for (const [k, set] of Object.entries(seen)) out[k] = [...set].sort();
  return out;
}

// ---------------------------------------------------------------- refresh
// POST <page>/refresh: the helper runs `live` and answers 303 back to the page.
export async function refresh(m) {
  if (DEMO.on) return { ok: false, message: `${DEMO_SAYS} The figures here are a fixed sample.` };
  try {
    const res = await fetch(m.refreshUrl || "refresh", { method: "POST", credentials: "same-origin", redirect: "follow", cache: "no-store", headers: csrfHeaders() });
    if (res.ok) return { ok: true };
    if (res.status === 403) return { ok: false, message: "Refresh refused: it only works from this page." };
    if (res.status === 502 || res.status === 504) return { ok: false, message: "The refresh helper is not running; figures update every 2 minutes anyway." };
    return { ok: false, message: `Refresh failed (${res.status}); figures update every 2 minutes anyway.` };
  } catch {
    return { ok: false, message: "Refresh failed: the server could not be reached." };
  }
}

// ---------------------------------------------------------------- compare
/* "Compare to previous period": the range against the one just before it,
   of the same length. Given only when both are whole - every day verified -
   otherwise `why` says what stands in the way, in words a tab can show. */
export function comparison(m, s) {
  const r = rangeOf(m, s);
  if (!s.cmp) return { on: false };
  if (r.kind === "today") return { on: true, ok: false, why: "Today is live and partial, so it is never compared. Pick Yesterday or longer to compare." };
  const prev = previousOf(m, r);
  const cov = coverage(r), pcov = coverage(prev);
  if (!cov.complete) return { on: true, ok: false, prev, why: `Not compared: only ${cov.ok} of this range's ${r.length} days are whole and verified.` };
  if (!pcov.complete) {
    const held = pcov.ok ? `only ${pcov.ok} of its ${r.length} days are whole and verified` : "history does not reach back that far yet";
    return { on: true, ok: false, prev, why: `Not compared: the ${r.length} days before (${prev.first} to ${prev.last}) are not complete; ${held}.` };
  }
  return { on: true, ok: true, prev, prevT: total(prev.days), shift: r.length };
}

// The day a period earlier, for a chart's ghost series: same position in the previous range.
export function ghostDay(m, shift) {
  return (d) => {
    const e = m.byDay.get(addDays(d.day, -shift));
    return e && e.state === "ok" ? e : null;
  };
}

// Markers (deploys, rule changes, internal-address changes, notes) by day, for the charts.
export function markersByDay(m) {
  const out = new Map();
  for (const k of m.x?.markers?.markers || []) {
    const day = k.day || String(k.at || "").slice(0, 10);
    if (!day) continue;
    (out.get(day) || out.set(day, []).get(day)).push(k);
  }
  return out;
}
