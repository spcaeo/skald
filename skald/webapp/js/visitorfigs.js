// The figures Traffic > Visitors draws in its two cards, worked out here with no
// page around them so tests/js/visitorfigs.mjs can check them:
//
//   newReturning(days)   visits by new and by returning visitors, per day and in all.
//                        Each day's `returning` ({readers, returning}: visitors.py,
//                        recounted by audit.py's "returning readers") must cover that
//                        day's readers exactly, or the whole figure is withheld. A day
//                        counted before returning visitors were is left out and named,
//                        never read as zero.
//   engagement(days)     the pages-per-visit and time-on-site histograms (each visit
//                        once), their medians and the one-page share. Each histogram
//                        must add up to the days' readers, or it is withheld.
//
//   narrowed(days, journeys, keep)
//                        the same days rebuilt from the visits kept (app.json's journeys),
//                        only those `keep` lets through, for a filtered page. Allowed only
//                        when every verified day's kept visits are that day's figures
//                        exactly (count = readers, the returning ones, pages per visit and
//                        time on site, bucketed as visits.py does); otherwise "unchecked",
//                        naming the days, and the page keeps the whole-site figures.
//   narrowedLists(days, journeys, keep)
//                        Where visits ended and Common next steps from the kept visits,
//                        under the same rule (each day's kept visits give back its lists).
//
// A "day" is the app's Day ({day, state, readers, returning?, visit?}); Today is the
// live figures given as one day. Only verified days (state "ok") count.
// Nothing here imports the page: standard JavaScript only.

const ok = (days) => (days || []).filter((d) => d && d.state === "ok");

export function newReturning(days) {
  const all = ok(days);
  const have = all.filter((d) => d.returning);
  const left = all.filter((d) => !d.returning).map((d) => d.day);
  if (!have.length) return { state: all.length ? "none" : "empty", left };
  const off = have.filter((d) => d.returning.readers !== d.readers || d.returning.returning > d.returning.readers || d.returning.returning < 0);
  if (off.length) {
    return { state: "withheld", left, off: off.map((d) => ({ day: d.day, readers: d.readers, counted: d.returning.readers, returning: d.returning.returning })) };
  }
  const per = have.map((d) => ({ day: d.day, visits: d.readers, returning: d.returning.returning, fresh: d.readers - d.returning.returning }));
  const visits = per.reduce((a, x) => a + x.visits, 0), returning = per.reduce((a, x) => a + x.returning, 0);
  return { state: "ok", visits, returning, fresh: visits - returning, days: per, left };
}

// The bins the card draws: the mockup's, coarse enough to read at a glance.
// Each bin is [label, from, to): from counted, to not.
export const PAGE_BINS = [["1", 1, 2], ["2", 2, 3], ["3", 3, 4], ["4", 4, 5], ["5 or more", 5, Infinity]];
export const SEC_BINS = [["under 10 s", 0, 10], ["10–30 s", 10, 30], ["30 s–1 min", 30, 60], ["1–3 min", 60, 180], ["3–10 min", 180, 600], ["over 10 min", 600, Infinity]];

function sumHist(into, hist) {
  for (const [k, v] of Object.entries(hist || {})) into[k] = (into[k] || 0) + (Number(v) || 0);
  return into;
}
const totalOf = (hist) => Object.values(hist).reduce((a, v) => a + v, 0);

/* The median of a {value: count} histogram (the lower middle on an even count). */
export function median(hist) {
  const pairs = Object.entries(hist || {}).map(([k, v]) => [Number(k), v]).filter(([, v]) => v).sort((a, b) => a[0] - b[0]);
  const total = pairs.reduce((s, [, v]) => s + v, 0);
  if (!total) return null;
  let mid = Math.floor((total - 1) / 2);
  for (const [k, v] of pairs) { if (mid < v) return k; mid -= v; }
  return null;
}

export function binned(hist, bins) {
  return bins.map(([label, lo, hi]) => ({ label, value: Object.entries(hist).filter(([k]) => Number(k) >= lo && Number(k) < hi).reduce((a, [, v]) => a + v, 0) }));
}

export function engagement(days) {
  const all = ok(days);
  const have = all.filter((d) => d.visit);
  const left = all.filter((d) => !d.visit).map((d) => d.day);
  if (!have.length) return { state: all.length ? "none" : "empty", left };
  const pages = {}, seconds = {};
  for (const d of have) { sumHist(pages, d.visit.pages); sumHist(seconds, d.visit.seconds); }
  const visits = have.reduce((a, d) => a + (d.readers || 0), 0);
  const tp = totalOf(pages), ts = totalOf(seconds);
  if (tp !== visits || ts !== visits) return { state: "withheld", left, visits, pagesTotal: tp, secondsTotal: ts };
  const pageBins = binned(pages, PAGE_BINS), secBins = binned(seconds, SEC_BINS);
  // The bins cover every value once: a bin set that drops or doubles one is a bug, withheld.
  if (totalOf(Object.fromEntries(pageBins.map((b) => [b.label, b.value]))) !== visits
    || totalOf(Object.fromEntries(secBins.map((b) => [b.label, b.value]))) !== visits) return { state: "withheld", left, visits, pagesTotal: tp, secondsTotal: ts };
  return { state: "ok", visits, pages: pageBins, seconds: secBins, medianPages: median(pages), medianSeconds: median(seconds),
    onePage: pages["1"] || 0, left };
}

// visits.py seconds_bucket: to the second under a minute, 10 s under ten minutes,
// the minute under an hour, then 10 minutes. The days' time-on-site keys are these.
export function bucket(seconds) {
  const x = Math.max(0, Math.trunc(Number(seconds) || 0));
  return x < 60 ? x : x < 600 ? x - (x % 10) : x < 3600 ? x - (x % 60) : x - (x % 600);
}

function tally(rows, key) {
  const out = {};
  for (const j of rows) { const k = String(key(j)); out[k] = (out[k] || 0) + 1; }
  return out;
}
const sameHist = (a, b) => {
  const x = Object.entries(a || {}).filter(([, v]) => Number(v)), y = Object.entries(b || {}).filter(([, v]) => Number(v));
  return x.length === y.length && x.every(([k, v]) => Number(b[k]) === Number(v));
};

/* Why a day's kept visits are not exactly its figures, or "" when they are. */
function mismatch(d, js) {
  if (!js.length && d.readers) return "none";
  if (js.length !== d.readers) return "count";
  if (d.returning && (d.returning.readers !== d.readers || js.filter((j) => j.returning).length !== d.returning.returning)) return "returning";
  if (d.visit && (!sameHist(tally(js, (j) => j.pages), d.visit.pages) || !sameHist(tally(js, (j) => bucket(j.seconds)), d.visit.seconds))) return "lengths";
  return "";
}

export function narrowed(days, journeys, keep) {
  const all = ok(days);
  if (!all.length) return { state: "empty" };
  const by = new Map();
  for (const j of journeys || []) { if (!by.has(j.day)) by.set(j.day, []); by.get(j.day).push(j); }
  const off = [], out = [];
  let whole = 0, kept = 0;
  for (const d of all) {
    const js = by.get(d.day) || [];
    const why = mismatch(d, js);
    if (why) { off.push({ day: d.day, why }); continue; }
    const k = js.filter(keep);
    whole += js.length; kept += k.length;
    out.push({ day: d.day, state: "ok", readers: k.length,
      returning: d.returning ? { readers: k.length, returning: k.filter((j) => j.returning).length } : null,
      visit: d.visit ? { pages: tally(k, (j) => j.pages), seconds: tally(k, (j) => bucket(j.seconds)) } : null });
  }
  if (off.length) return { state: "unchecked", off };
  return { state: "ok", days: out, whole, kept };
}

// Where visits ended and the common next steps, narrowed the same way: visits.py counts
// each visit's last page (exits) and each move from one trail entry to the next (steps),
// then folds each list to its top entries and "(all others)". A day's kept visits must
// give back exactly its stored lists (every named entry, and the folded rest as a sum),
// or the lists are "unchecked" and the page keeps the whole-site ones.
export const OTHER = "(all others)";
export const ARROW = " → ";

const exitsOf = (rows) => tally(rows, (j) => j.exit);
function stepsOf(rows) {
  const out = {};
  for (const j of rows) {
    const t = (j.trail || []).map((x) => x.path);
    for (let i = 1; i < t.length; i++) { const k = t[i - 1] + ARROW + t[i]; out[k] = (out[k] || 0) + 1; }
  }
  return out;
}

/* A full tally against a stored list folded to its top entries. */
export function foldedMatch(full, folded) {
  const named = Object.keys(folded || {}).filter((k) => k !== OTHER);
  if (named.some((k) => Number(full[k] || 0) !== Number(folded[k]))) return false;
  const rest = Object.entries(full).filter(([k]) => !named.includes(k)).reduce((a, [, v]) => a + v, 0);
  return rest === Number(folded?.[OTHER] || 0);
}

function addInto(into, part) {
  for (const [k, v] of Object.entries(part)) into[k] = (into[k] || 0) + v;
  return into;
}

export function narrowedLists(days, journeys, keep) {
  const all = ok(days);
  if (!all.length) return { state: "empty" };
  const by = new Map();
  for (const j of journeys || []) { if (!by.has(j.day)) by.set(j.day, []); by.get(j.day).push(j); }
  const off = [], exits = {}, steps = {};
  let whole = 0, kept = 0;
  for (const d of all) {
    const js = by.get(d.day) || [];
    const why = !js.length && d.readers ? "none" : js.length !== d.readers ? "count"
      : !d.visit || !foldedMatch(exitsOf(js), d.visit.exits) || !foldedMatch(stepsOf(js), d.visit.steps) ? "lists" : "";
    if (why) { off.push({ day: d.day, why }); continue; }
    const k = js.filter(keep);
    whole += js.length; kept += k.length;
    addInto(exits, exitsOf(k));
    addInto(steps, stepsOf(k));
  }
  if (off.length) return { state: "unchecked", off };
  return { state: "ok", exits, steps, whole, kept };
}
