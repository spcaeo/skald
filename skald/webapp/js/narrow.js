// Traffic's shared filter (SKALD-62): Country, Source and Device for Visitors, Sources, Pages
// and Places & devices, as one bar under the tabs (tabs/tr-filter.js). This file says which
// tabs share it and works out the figures those tabs show with it on: visitors by country,
// source, device, browser, system, campaign, landing page and AI assistant, only the visits
// that match.
//
// History keeps each breakdown on its own, so "visitors from the USA by browser" is not in
// the days' totals. Where the crossed figures come from:
//
//   whole days   the server's compare (GET <page>/api/compare, DATA-CONTRACT-COMPARE.md): the
//                visit cube, every reader's visit by all its labels at once, kept 400 days,
//                verified against the readers breakdowns and recounted by the audit. A B
//                period comes in the same answer, for Compare mode.
//   no server    (the demo, a page without the helper) the daily cube (cube.json, 90 days) on
//                this page, as Compare does it (tabs/versuslocal.js): country, source, device,
//                landing page and assistant only; the rest is said not to be split.
//   today        today's visits (the journeys), one per visit: a breakdown is used only when
//                every visit counted gives back today's own list exactly (visitorfigs.js
//                foldedMatch), else it is said not to be split. Never a guess.
//
// A breakdown that cannot be split by the filter is null, and the tab says so: never the
// whole site's figure under a filter.

import { getJSON, base, daysBetween } from "./data.js";
import { addDays } from "./ui.js";
import { foldedMatch } from "./visitorfigs.js";
import { local, cubeCtx } from "./tabs/versuslocal.js";
import { DEMO } from "./demo.js";

/* The bar's three filters and the four tabs that share them, in their order on the strip. */
export const SHARED = ["country", "source", "device"];
export const SHARED_TABS = ["traffic/visitors", "traffic/sources", "traffic/pages", "traffic/places"];
export const sharedTab = (tab) => SHARED_TABS.includes(tab);

/* The bar's filters that are on: [[dim, value]]. */
export const picksOf = (s) => SHARED.filter((k) => s[k]).map((k) => [k, s[k]]);
export const filtered = (s) => picksOf(s).length > 0;

/* What a breakdown is called in the answer. DIMS: ours; API: the compare answer's. */
export const DIMS = ["country", "source", "device", "browser", "os", "campaign", "landing", "assistant"];
const API = { country: "countries", source: "sources", device: "devices", browser: "browsers", os: "os",
  campaign: "campaigns", landing: "landing_pages", assistant: "assistants" };
// The browser's own cube (no server) keeps the landing page as Compare's "pages".
const LOCAL = { ...API, landing: "pages" };
const NO_CAMPAIGN = "(no campaign tag)";   // dimensions.NO_CAMPAIGN: the readers' label for none
export const OTHER = "(all others)";

// ------------------------------------------------------------------ today
// A visit's label as the readers breakdowns hold it (aggregate.py _reader).
const LABEL = {
  country: (j) => j.country || "Unknown",
  source: (j) => j.source || "",
  device: (j) => j.device || "",
  browser: (j) => j.browser || "",
  os: (j) => j.os || "",
  campaign: (j) => j.campaign || NO_CAMPAIGN,
  // The visits sent to the page carry their trail, not a landing field: its first page.
  landing: (j) => j.landing || ((j.trail || []).find((x) => x && x.page !== false) || (j.trail || [])[0] || {}).path || "",
};
const tally = (rows, f) => {
  const out = {};
  for (const j of rows) { const k = f(j); out[k] = (out[k] || 0) + 1; }
  return out;
};
const keeper = (picks) => (j) => picks.every(([k, v]) => LABEL[k](j) === v);

/* One day from its visits: `day` the day's own figures ({readers, by}), `journeys` its
   visits. Each breakdown is split only when all the visits give back the day's own list. */
export function fromVisits(day, journeys, picks) {
  const js = journeys || [];
  const empty = { readers: null, by: Object.fromEntries(DIMS.map((k) => [k, null])), checked: false };
  if (!day || day.readers == null || js.length !== day.readers) return { ...empty, why: js.length ? "count" : "none" };
  const kept = js.filter(keeper(picks));
  const by = {};
  for (const k of DIMS) {
    const f = LABEL[k];
    by[k] = f && day.by?.[k] && foldedMatch(tally(js, f), day.by[k]) ? tally(kept, f) : null;
  }
  // A pick is trusted only when the visits' own labels for it give back the day's list: else
  // the visits kept could be the wrong ones, and nothing is split.
  if (picks.some(([k]) => by[k] == null)) return { ...empty, why: "labels" };
  return { readers: kept.length, by, checked: true, whole: js.length };
}

// ------------------------------------------------------------ whole days
const ANSWERS = new Map();   // the server's answers, by query, for this page's life
const CUBES = new Map();     // the page's daily cube, by data stamp and page group

function query(a, b, picks) {
  const q = new URLSearchParams({ a: `${a.first}..${a.last}`, b: `${b.first}..${b.last}` });
  for (const [k, v] of picks) q.set(k, v);
  return q.toString();
}

/* The answer's rows, {label: visitors}, or null when the answer cannot split it. */
function rowsOf(dims, name, side) {
  const list = dims?.[name];
  if (!Array.isArray(list)) return null;
  const out = {};
  for (const r of list) if (r[side]) out[r.name] = (out[r.name] || 0) + r[side];
  return out;
}
const visitorsOf = (res, side) => res.metrics?.find?.((x) => x.key === "visitors")?.[side] ?? null;

function sideOf(res, side, map) {
  const info = res[side] || {};
  return { readers: visitorsOf(res, side), by: Object.fromEntries(DIMS.map((k) => [k, rowsOf(res.dimensions, map[k], side)])),
    used: info.used ?? null, days: info.days ?? null, excluded: info.excluded || [], unmeasured: info.unmeasured || [] };
}

function viaPage(m, s, a, b, picks) {
  const only = { ...s, path: "", browser: "", campaign: "", referrer: "", country: "", source: "", device: "", ...Object.fromEntries(picks) };
  const key = `${m.stamp}|${s.view || "all"}`;
  if (!CUBES.has(key)) CUBES.set(key, Array.isArray(m.files) && !m.files.includes("cube") ? Promise.resolve(null) : getJSON(`${base(s.view)}cube.json`).catch(() => null));
  return CUBES.get(key).then((cube) => local(m, only, a, b, cube ? cubeCtx(cube, picks) : null));
}

/* The whole days a and b (b may be a itself), filtered: the server's answer, else the page's. */
function wholeDays(m, s, a, b, picks) {
  const q = query(a, b, picks);
  const key = `${m.stamp}|${s.view || "all"}|${q}`;
  if (!ANSWERS.has(key)) {
    // A page group's answer is the group's own: its address is under the group (refresh_server COMPARE_PATH).
    const at = s.view && s.view !== "all" ? `${s.view}/` : "";
    const server = DEMO.on ? Promise.reject(new Error("demo")) : getJSON(`${at}api/compare?${q}`, true)
      .then((res) => (res && res.ok ? { res, how: "server" } : Promise.reject(new Error(res?.error || "no answer"))));
    ANSWERS.set(key, server.catch(() => viaPage(m, s, a, b, picks).then((res) => ({ res, how: "page" }))));
  }
  return ANSWERS.get(key);
}

// --------------------------------------------------------------- the period
const sum = (x, y) => {
  if (x == null || y == null) return null;
  const out = { ...x };
  for (const [k, v] of Object.entries(y)) out[k] = (out[k] || 0) + v;
  return out;
};

/* The period r, filtered by `picks` (default: the bar's), and its B when `b` is a range:
   Promise of { how, a: {readers, by, used, days, excluded, unmeasured}, b, problems }. */
export function narrow(m, s, r, { picks = picksOf(s), b = null } = {}) {
  const today = () => {
    const live = m.live && m.live.day === m.today && m.live.state === "ok" ? m.live.figures : null;
    return fromVisits(live, (m.journeys || []).filter((j) => j.day === m.today), picks);
  };
  const todayOnly = (t) => ({ how: "visits", a: { ...t, used: t.checked ? 1 : 0, days: 1, excluded: t.checked ? [] : [{ day: m.today, state: "unchecked" }], unmeasured: [] },
    b: null, problems: t.checked ? [] : [t.why === "none" ? "Today's visits are not kept on this page yet."
      : t.why === "labels" ? "Today's visits kept here do not give back today's own list for this filter, so they are not split by it."
      : "Today's visits kept here are not exactly today's count yet: wait for the next update."] });
  if (r.kind === "today") return Promise.resolve(todayOnly(today()));
  // Include today (Pages): the whole days from the answer, today from its visits, added.
  const last = r.inc ? addDays(m.today, -1) : r.last;
  const a = { first: r.first, last };
  const whole = last >= r.first ? wholeDays(m, s, a, b || a, picks) : Promise.resolve(null);
  return whole.then((got) => {
    const res = got?.res;
    const map = got?.how === "page" ? LOCAL : API;
    const A = res ? sideOf(res, "a", map) : { readers: 0, by: Object.fromEntries(DIMS.map((k) => [k, {}])), used: 0, days: 0, excluded: [], unmeasured: [] };
    // The page's own cube: the visitors are its rows' own sum (a filter's day breakdown would
    // count the visits its folded rows hold, which no list can show), so the lists add up.
    if (got?.how === "page" && A.by.country) A.readers = Object.values(A.by.country).reduce((x, y) => x + y, 0);
    const problems = [...(res?.problems || [])];
    if (res && res.reconciled === false) return { how: got.how, a: null, b: null, problems: problems.length ? problems : ["The crossed figures did not add up."] };
    if (r.inc) {
      const t = today();
      if (!t.checked) A.excluded = [...A.excluded, { day: m.today, state: "unchecked" }];
      else {
        A.readers = (A.readers ?? 0) + t.readers;
        for (const k of DIMS) A.by[k] = sum(A.by[k], t.by[k]);
        A.used = (A.used || 0) + 1;
      }
      A.days = (A.days || 0) + 1;
    }
    const B = b && res ? sideOf(res, "b", map) : null;
    if (B && got.how === "page" && B.by.country) B.readers = Object.values(B.by.country).reduce((x, y) => x + y, 0);
    return { how: r.inc ? `${got?.how || "visits"}+visits` : got?.how, a: A, b: B, problems };
  });
}

/* The whole period's days that hold no crossed figures, in words, or "". */
export function gapWords(side) {
  if (!side) return "";
  const out = [];
  const shortDay = (d) => d.slice(5).replace("-", "/");
  if (side.excluded?.length) out.push(`${side.excluded.length} day${side.excluded.length === 1 ? "" : "s"} not whole or not checked (${side.excluded.slice(0, 3).map((x) => shortDay(x.day)).join(", ")}${side.excluded.length > 3 ? ", …" : ""}) left out`);
  if (side.unmeasured?.length) out.push(`${side.unmeasured.length} day${side.unmeasured.length === 1 ? "" : "s"} counted before the crossed figures were kept left out`);
  return out.join("; ");
}

/* The days of r that are in history, for a note: how many of them the answer counted. */
export const periodDays = (m, r) => (r.kind === "today" ? 1 : r.inc ? r.length : daysBetween(m, r.first, r.last).length);
