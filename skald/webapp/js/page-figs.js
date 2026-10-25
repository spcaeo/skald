// Per-page figures over a period, from page_trends.json (release 2): what Summary's "Work on
// the page, or on traffic?" card, Traffic › Pages' new columns and sorts, and AI & bots ›
// Assistants' "AI reads by page" stand on.
//
// Nothing new is counted per day: each day's blob is the stored, audited day kind
// (`landings`, audit_landings.py; the assistants' fetches, audit_page_trends.py). Here the
// days of the period are added up, as data.js total() adds up any day figure: only whole,
// verified ("ok") days; a day whose blob was not recorded is counted apart (`missing`), never
// as zero; a day that folded a page into "(all others)" makes its figures a floor (`folded`).
//
// Pure: no DOM, so node tests it (tests/js/page-work.mjs).

import { addDays } from "./ui.js";

export const OTHER = "(all others)";

// One page whether written with or without its trailing slash or a query (page_trends.py key).
export const pageKey = (p) => { const x = String(p || "").split("?")[0].split("#")[0]; return x.endsWith("/") ? x : `${x}/`; };

// The first day of "Changed in the last 30 days": page_trends.json's own, else 30 days to the last recorded day.
export const changedSince = (m) => m?.x?.page_trends?.changed?.since || addDays(m.anchor, -29);
export const F = { visits: 0, one_page: 1, views: 2, search: 3, ai: 4 };
// The one definition, said in the UI and the help (docs/help/summary-and-pages.md).
export const LEFT_WORDS = "Left at once: the visit loaded that one page and no other (one page view in the server's log).";

/* The thresholds of "Work on the page, or on traffic?" and the "Needs work" sort, in one place.
     MIN_VISITS   a page needs 10 visits that started on it before its share is judged: under
                  that, one visit moves the share by more than 10 points
     LEFT_SHARE   "Improve the page": 9 in 10 of those visits left at once (one page view)
     MIN_SEARCH   "Both": search found the page at least 3 times in the period, so it is not one
                  stray click
     BOTH_LEFT    ... and 8 in 10 of its visits left at once
     SHOW         at most 5 pages in each list; the rest are on Traffic › Pages, "Needs work" */
export const WORK = { MIN_VISITS: 10, LEFT_SHARE: 0.9, MIN_SEARCH: 3, BOTH_LEFT: 0.8, SHOW: 5 };

/* The days of page_trends.json for a range: [{day, state, landings, fetches}], today from its
   `today` block. */
function trendDays(pt, r) {
  const by = new Map((pt?.days || []).map((d) => [d.day, d]));
  return r.days.map((d) => (d.live ? { day: d.day, ...(pt?.today || {}), state: pt?.today?.state === "ok" && d.state === "ok" ? "ok" : "missing" }
    : by.get(d.day) ? { ...by.get(d.day), state: d.state } : { day: d.day, state: d.state }));
}

/* {rows: {path: {visits, one_page, views, search, ai, fetches: {assistant: n}, reads}},
   of: whole days, days: of them with landings, fetchDays: with fetches, folded, fetchFolded}.
   null without the file (or on a page group, whose file says whole_site_only). */
export function pageSums(pt, r) {
  if (!pt || pt.whole_site_only || !Array.isArray(pt.days) || r?.kind !== "history") return null;
  const rows = {};
  const row = (p) => rows[p] || (rows[p] = { visits: 0, one_page: 0, views: 0, search: 0, ai: 0, fetches: {}, reads: 0 });
  const out = { rows, of: 0, days: 0, fetchDays: 0, folded: false, fetchFolded: false, missing: [], fetchMissing: [] };
  for (const d of trendDays(pt, r)) {
    if (d.state !== "ok") continue;
    out.of += 1;
    if (d.landings) {
      out.days += 1;
      if (d.landings.folded) out.folded = true;
      for (const [p, v] of Object.entries(d.landings.pages || {})) {
        const x = row(p);
        x.visits += v[F.visits]; x.one_page += v[F.one_page]; x.views += v[F.views]; x.search += v[F.search]; x.ai += v[F.ai];
      }
    } else out.missing.push(d.day);
    if (d.fetches) {
      out.fetchDays += 1;
      if (d.fetches.folded) out.fetchFolded = true;
      for (const [p, per] of Object.entries(d.fetches.paths || {})) {
        const x = row(p);
        for (const [who, k] of Object.entries(per)) { x.fetches[who] = (x.fetches[who] || 0) + k; x.reads += k; }
      }
    } else out.fetchMissing.push(d.day);
  }
  return out;
}

export const leftShare = (x) => (x && x.visits ? x.one_page / x.visits : null);
export const perVisit = (x) => (x && x.visits ? x.views / x.visits : null);

/* The two lists of the card. leads: {path: n} from conversions (leadfigs.js leadsBy), or null
   when leads are not recorded for these days: then a page is listed with "forms: not recorded". */
export function workLists(sums, leads, w = WORK) {
  if (!sums) return null;
  const all = Object.entries(sums.rows).filter(([p, x]) => p !== OTHER && x.visits).map(([path, x]) => ({ path, ...x, left: leftShare(x),
    leads: leads ? leads[path] || 0 : null }));
  const improve = all.filter((x) => x.visits >= w.MIN_VISITS && x.left >= w.LEFT_SHARE && (x.leads == null || x.leads === 0))
    .sort((a, b) => b.visits - a.visits || a.path.localeCompare(b.path));
  const taken = new Set(improve.map((x) => x.path));
  const both = all.filter((x) => !taken.has(x.path) && x.search >= w.MIN_SEARCH && x.left >= w.BOTH_LEFT)
    .sort((a, b) => b.search - a.search || b.visits - a.visits || a.path.localeCompare(b.path));
  return { improve: improve.slice(0, w.SHOW), both: both.slice(0, w.SHOW), improveAll: improve.length, bothAll: both.length };
}

/* The "Needs work" order: pages with enough visits first, the most left at once first, then the
   most visits; a page under MIN_VISITS has no score (it sorts last). */
export function workScore(x, w = WORK) {
  if (!x || x.visits < w.MIN_VISITS || x.left == null) return null;
  return x.left * 1e6 + x.visits;
}

/* The landing pages' order on Traffic › Pages (psort): [column key, direction]. Rising and
   Falling need Compare (the ± column); without it they fall back to Most visits. */
export const SORTS = [
  ["visits", "Most visits", "The most visits that started on the page first"],
  ["rising", "Rising", "Needs Compare: the biggest gain against the period before first"],
  ["falling", "Falling", "Needs Compare: the biggest drop against the period before first"],
  ["changed", "Recently changed", "The newest change date first (the website's, else your sitemap's)"],
  ["work", "Needs work", "Many visits, most leave at once, no forms"],
];
export function sortOf(psort, compared) {
  if ((psort === "rising" || psort === "falling") && !compared) return { key: "v", dir: "desc", fallback: true };
  return { visits: { key: "v", dir: "desc" }, rising: { key: "d", dir: "desc" }, falling: { key: "d", dir: "asc" },
    changed: { key: "chg", dir: "desc" }, work: { key: "work", dir: "desc" } }[psort] || { key: "v", dir: "desc" };
}

/* AI reads by page, now against before (AI & bots › Assistants): rows {path, now, before,
   who: {assistant: n}, ai} where `ai` is the proven AI visits that started there now. before
   null: B's days are not all recorded. */
export function readsTrend(a, b) {
  if (!a) return [];
  const bOk = b && b.of > 0 && b.fetchDays === b.of;
  const paths = new Set([...Object.keys(a.rows).filter((p) => a.rows[p].reads || a.rows[p].ai), ...(bOk ? Object.keys(b.rows).filter((p) => b.rows[p].reads) : [])]);
  paths.delete(OTHER);
  return [...paths].map((path) => ({ path, now: a.rows[path]?.reads || 0, before: bOk ? b.rows[path]?.reads || 0 : null,
    who: a.rows[path]?.fetches || {}, ai: a.rows[path]?.ai || 0 }))
    .sort((x, y) => y.now - x.now || (y.before ?? 0) - (x.before ?? 0) || x.path.localeCompare(y.path));
}
