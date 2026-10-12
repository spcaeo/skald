// A saved funnel's history (funnels.json `history`, funnel_days.py): counted
// every day from the day it was saved, so it covers any range, not only the
// days journeys are kept. Only verified days count; a day with no count is
// "not recorded", never zero. A rate over fewer than MIN_RATE visits is not
// given: too few to say.

import { h, n, short } from "../ui.js";
import { bars, legend, lines } from "../charts.js";
import { table } from "../table.js";

const MIN_RATE = 10;
const TIMES = ["under 10s", "10-30s", "30s-1m", "1-3m", "3-10m", "10-30m", "30m or more"];
const TONES = ["var(--g-people)", "var(--g-search_engines)", "var(--g-answer_engines)", "var(--g-bots)", "var(--g-ours)", "var(--opp)", "var(--views)", "var(--ink-3)"];
const LEFT = "(left the site)";
// Short names for the time bars, so seven fit at phone width.
const SHORT = { "under 10s": "<10s", "10-30s": "10-30s", "30s-1m": "30s-1m", "1-3m": "1-3m", "3-10m": "3-10m", "10-30m": "10-30m", "30m or more": "30m+" };
const rate = (a, b) => (b >= MIN_RATE && a != null ? `${a && a / b < 0.1 ? ((a / b) * 100).toFixed(1) : Math.round((a / b) * 100)}%` : null);
const FEW = "too few to say";

// The range's verified, recorded days summed: steps, splits, next pages, time to complete.
function sum(days, k) {
  const out = { visits: 0, reached: Array(k).fill(0), by_source: {}, by_device: {}, next: Array.from({ length: k }, () => ({})), complete: {} };
  for (const d of days) {
    out.visits += d.visits || 0;
    (d.reached || []).forEach((v, i) => { if (i < k) out.reached[i] += v; });
    for (const split of ["by_source", "by_device"]) {
      for (const [label, row] of Object.entries(d[split] || {})) {
        const into = out[split][label] || (out[split][label] = Array(k).fill(0));
        row.forEach((v, i) => { if (i < k) into[i] += v; });
      }
    }
    (d.next || []).forEach((c, i) => { if (i < k) for (const [p, v] of Object.entries(c)) out.next[i][p] = (out.next[i][p] || 0) + v; });
    for (const [b, v] of Object.entries(d.complete || {})) out.complete[b] = (out.complete[b] || 0) + v;
  }
  return out;
}

function steps(labels, t) {
  const start = t.reached[0] || 0;
  return h("ol", { class: "fn-chart", "aria-label": "Visits at each step over the range" }, labels.map((label, i) => {
    const v = t.reached[i], prev = i ? t.reached[i - 1] : null;
    const ofStart = i ? rate(v, start) : null, ofPrev = i ? rate(v, prev) : null;
    return h("li", null, h("div", { class: "fn-bar static" },
      h("span", { class: "fn-l" }, h("b", null, `${i + 1}`), h("span", { class: "any" }, label)),
      h("span", { class: "fn-track" }, h("i", { style: { width: `${start ? Math.max(v ? 1.5 : 0, (v / start) * 100) : 0}%` } })),
      h("span", { class: "fn-v" }, h("b", null, n(v)), h("small", null, i ? (ofStart ? `${ofStart} of start` : FEW) : "visits"))),
    i && prev ? h("p", { class: "fn-drop" }, ofPrev ? `${ofPrev} of step ${i} went on (${n(prev - v)} left)` : `${n(prev - v)} of ${n(prev)} left: ${FEW}`) : null);
  }));
}

function splitTable(title, file, labels, rows) {
  const k = labels.length;
  const data = Object.entries(rows).map(([label, r]) => {
    const row = { label: label || "Unknown", through: rate(r[k - 1], r[0]), sortRate: r[0] >= MIN_RATE ? r[k - 1] / r[0] : -1 };
    r.forEach((v, i) => { row[`s${i}`] = v; });
    return row;
  });
  const cols = [{ key: "label", label: title }, ...labels.map((l, i) => ({ key: `s${i}`, label: `${i + 1}. ${l}`, num: true })),
    { key: "through", label: "Went through", fmt: (v) => v || FEW, sort: (r) => r.sortRate, csv: (r) => r.through || "" }];
  return h("div", { class: "sheet" }, h("h3", null, `By ${title.toLowerCase()}`),
    table(cols, { caption: `Funnel steps by ${title.toLowerCase()}`, rows: data, file, search: false, limit: 8, sortKey: "s0", empty: "No visit in this range.",
      note: `"Went through" is the last step as a share of the first, given only over at least ${MIN_RATE} visits.` }));
}

function nextPages(labels, t) {
  const rows = [];
  labels.forEach((label, i) => {
    const left = Object.values(t.next[i]).reduce((a, v) => a + v, 0);
    for (const [page, v] of Object.entries(t.next[i])) rows.push({ step: `${i + 1}. ${label}`, at: i, page: page === LEFT ? "Left the site" : page, n: v, share: rate(v, left), last: i === labels.length - 1 });
  });
  rows.sort((a, b) => a.at - b.at || b.n - a.n);
  return h("div", { class: "sheet" }, h("h3", null, "Where they went next"),
    h("p", { class: "sub" }, "For each step, the visits that went no further: the next page they were seen on, or that they left. After the last step: where the visits that went through went next. Top 10 per step per day; the rest is \"(all others)\"."),
    table([{ key: "step", label: "After step", sort: (r) => r.at }, { key: "page", label: "Next page" }, { key: "n", label: "Visits", num: true },
      { key: "share", label: "Share", fmt: (v) => v || FEW, sort: (r) => (r.share ? r.n : -1) }],
    { caption: "Where visits went after each funnel step", rows, file: "funnel-next-pages.csv", limit: 12, sortKey: "step", dir: 1, empty: "No visit stopped at a step in this range." }));
}

function timeToComplete(t, k) {
  if (k < 2) return null;
  const items = TIMES.map((b) => ({ label: SHORT[b], title: b, value: t.complete[b] || 0 }));
  const all = items.reduce((a, x) => a + x.value, 0);
  return h("div", { class: "sheet" }, h("h3", null, "Time to go through"),
    h("p", { class: "sub" }, `From the first step (the visit's start for any page) to the page that met the last step. ${all >= MIN_RATE ? `${n(all)} visits.` : `${n(all)} visit${all === 1 ? "" : "s"}: ${FEW} how long it usually takes.`}`),
    all ? bars(items, { label: "Visits that went through, by time taken", unit: "visits", H: 170, every: innerWidth < 480 ? 2 : 1 }) : h("p", { class: "empty" }, "No visit went through in this range."));
}

/* The history section for one saved funnel (from funnels.json) over range r. */
export function history(m, r, saved) {
  const hist = saved?.history;
  if (!hist) return [];
  const labels = hist.steps || [];
  const k = labels.length;
  const since = hist.since;
  const byDay = new Map((hist.days || []).map((d) => [d.day, d]));
  const head = (body) => h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "History"),
    h("span", { class: "tbl-count" }, since ? `counted from ${short(since)}` : "not counted yet")), ...body);
  if (!since || !k) return [head([h("p", { class: "empty" }, "This funnel is counted each day from the day it is saved. Its first day shows here after the next daily run.")])];

  const entries = r.kind === "today" ? (hist.today ? [{ ...hist.today, state: "ok" }] : []) : r.days.map((d) => byDay.get(d.day)).filter(Boolean);
  const counted = entries.filter((d) => d.state === "ok" && Array.isArray(d.reached));
  const withheld = entries.filter((d) => d.state === "withheld").length;
  const before = r.kind === "today" ? 0 : r.days.filter((d) => d.day < since).length;
  const notRecorded = (r.kind === "today" ? 1 : r.length) - counted.length - withheld - before;
  const words = [r.kind === "today" ? (counted.length ? "today so far" : "today not counted yet") : `${counted.length} of ${r.length} days counted`,
    before ? `${before} before it was saved: not recorded` : "", withheld ? `${withheld} withheld (did not reconcile): left out` : "",
    notRecorded > 0 ? `${notRecorded} not recorded` : ""].filter(Boolean).join("; ");
  if (!counted.length) return [head([h("p", { class: "empty" }, `Not recorded for this range. ${words}. A funnel's history starts the day it is saved (${short(since)}).`)])];

  const t = sum(counted, k);
  const out = [h("p", { class: "sub" }, `${words}. Visits from ${saved.fsrc || "any source"}, page steps only; lead and event steps have their own history.`),
    h("div", { class: "sheet" }, steps(labels, t))];
  if (r.kind === "history" && r.length > 1) {
    const days = r.days.filter((d) => d.day >= since).map((d) => {
      const e = byDay.get(d.day);
      return e || { day: d.day, state: "missing" };
    });
    const series = labels.map((l, i) => ({ name: `${i + 1}. ${l}`, color: TONES[i % TONES.length], get: (d) => (Array.isArray(d.reached) ? d.reached[i] : null) }));
    out.push(h("div", { class: "sheet" }, h("h3", null, "Visits at each step, per day"),
      h("p", { class: "sub" }, "The gap between two lines is the visits lost between those steps. A break is a day not recorded; a hatched stub a day withheld."),
      legend(series.map((x) => [x.name, x.color]), true),
      lines(days, series, { label: "Visits reaching each funnel step per day", H: 220 })));
  }
  out.push(splitTable("Source type", "funnel-by-source.csv", labels, t.by_source),
    splitTable("Device", "funnel-by-device.csv", labels, t.by_device), nextPages(labels, t), timeToComplete(t, k));
  return [head(out)];
}
