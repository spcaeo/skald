// Visits: what a reader's visit looked like - how many pages, how long, where
// it started and ended, and each journey on its own (no address, no browser
// string, no identifier: a time, labels and the pages in order).

import { time as tzTime } from "../tz.js";
import { h, n, duration, pct1, counter } from "../ui.js";
import { base, color, figures, getJSON, pathMatch, ranked } from "../data.js";
import { bars } from "../charts.js";
import { table } from "../table.js";
import { head, nothing, coverageNote, blist, panel, fileName } from "./common.js";
import { visitMatrix, entryTable, folded, offset, NOTE } from "./visitlist.js";
import { label as valueLabel } from "../drill.js";

const MIN_RATE = 10;   // no rate over fewer visits than this: too few to mean anything
const FEW = "too few to say";

const PAGE_BINS = [["1", (k) => k === 1], ["2", (k) => k === 2], ["3", (k) => k === 3], ["4", (k) => k === 4], ["5", (k) => k === 5], ["6 to 9", (k) => k >= 6 && k <= 9], ["10+", (k) => k >= 10]];
const SEC_BINS = [["under 10 s", 0, 10], ["10 to 30 s", 10, 30], ["30 s to 1 min", 30, 60], ["1 to 3 min", 60, 180], ["3 to 10 min", 180, 600], ["10 to 30 min", 600, 1800], ["30 min or more", 1800, Infinity]];

function median(hist) {
  const pairs = Object.entries(hist || {}).map(([k, v]) => [Number(k), v]).filter(([, v]) => v).sort((a, b) => a[0] - b[0]);
  const total = pairs.reduce((s, [, v]) => s + v, 0);
  if (!total) return null;
  let mid = Math.floor((total - 1) / 2);
  for (const [k, v] of pairs) { if (mid < v) return k; mid -= v; }
  return null;
}

export function journeyFilter(s) {
  const keep = pathMatch(s);
  return (j) => (!s.country || j.country === s.country) && (!s.source || j.source === s.source) && (!s.device || j.device === s.device) &&
    (!s.browser || j.browser === s.browser) && (!s.path || j.trail.some((p) => keep(p.path))) &&
    (!s.campaign || j.campaign === s.campaign || Object.values(j.utm || {}).includes(s.campaign)) &&
    (!s.referrer || j.ref_host === s.referrer || j.via === s.referrer);
}

export function journey(j) {
  const item = h("li", { class: "jr", "data-open": "false" });
  const id = `j${Math.random().toString(36).slice(2, 8)}`;
  const fold = folded(j.trail);
  const steps = fold.slice(0, 6).flatMap((p, i) => [i ? h("i", { "aria-hidden": "true" }, "›") : null, h("span", null, p.path, p.times > 1 ? ` ×${p.times}` : null)]);
  if (fold.length > 6) steps.push(h("i", null, `+${fold.length - 6}`));
  const btn = h("button", { type: "button", "aria-expanded": "false", "aria-controls": id },
    h("span", { class: "j-t" }, tzTime(j.start, { date: true, label: false })),
    h("span", { class: "j-p" }, steps),
    h("span", { class: "j-m" }, `${n(j.pages)} page${j.pages === 1 ? "" : "s"}, ${duration(j.seconds)}`,
      ...Object.entries(j.utm || {}).slice(0, 2).map(([k, v]) => h("span", { class: "utm", style: { marginLeft: "6px" } }, `${k}: ${v}`)),
      j.returning ? h("span", { class: "rep yes", style: { marginLeft: "6px" } }, "returning") : null));
  const detail = h("div", { class: "j-d", id }, h("div", null,
    h("ol", null, j.trail.map((p) => h("li", null, p.at != null ? h("small", { class: "j-at" }, offset(p.at)) : null, p.path, p.page ? null : h("small", null, "moved inside the site; no page loaded")))),
    h("dl", null, [["Country", j.country ? valueLabel("country", j.country, j.country) : ""], ["Device", j.device], ["Browser", j.browser], ["System", j.os], ["Came from", j.via || j.source],
      ["Referring page", j.ref_page], ["Campaign", j.campaign], ["Paid", j.paid], ["Searched for", j.search_terms],
      ["Seen in 30 days", j.days_seen_30d != null ? `${j.days_seen_30d} day${j.days_seen_30d === 1 ? "" : "s"}` : ""], ["Ended on", j.exit],
      ...(j.flags || []).map((f) => ["Note", NOTE[f] || f])].filter(([, v]) => v).flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)]))));
  btn.addEventListener("click", () => {
    const open = item.dataset.open !== "true";
    item.dataset.open = String(open);
    btn.setAttribute("aria-expanded", String(open));
  });
  item.append(btn, detail);
  return item;
}

function journeys(m, s, r) {
  const inRange = r.kind === "today" ? (j) => j.day === m.today : (j) => j.day >= r.first && j.day <= r.last;
  const all = (m.journeys || []).filter(inRange);
  return visitMatrix(all, all.filter(journeyFilter(s)), r, m.journey_days);
}

export default function visits(m, s, { first }) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Visits", r, "A visit is one visitor: a browser that read at least one page, with no gap longer than 30 minutes. Arriving again from another outside source (an AI assistant, a search, another site, a campaign link) starts a new visit. Logs see what was loaded, not how long someone read, so a long read of one page shows as a short visit.")];
  if (!t) return [...out, nothing(m, r, "visits")];
  const v = t.visit;
  const readers = t.readers ?? 0, views = t.views ?? 0;
  const med = v ? median(v.seconds) : null;
  const one = v ? v.pages?.["1"] || 0 : null;
  const k = (label, val, note) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note), h("div", { class: "k-v" }, val), h("div", { class: "k-c" }));
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    k("Visits that read a page", first ? counter(readers) : n(readers), "visitors; an upper bound on people"),
    k("Pages per visit", readers ? (views / readers).toFixed(1) : "-", "pages read divided by visitors"),
    k("Typical visit length", med == null ? "-" : duration(med), "the median: half were shorter"),
    k("One-page visits", one == null ? "-" : pct1(one, readers), one == null ? "not recorded for this range" : `${n(one)} read a single page and left`),
    k("New and returning", t.returning && !t.unmeasured?.returning ? `${n(t.returning.readers - t.returning.returning)} / ${n(t.returning.returning)}` : "-",
      t.returning && !t.unmeasured?.returning ? `${pct1(t.returning.returning, t.returning.readers)} were seen on an earlier day in 30` : "not recorded for this range")),
  v && t.unmeasured?.visit ? h("p", { class: "note" }, `${t.unmeasured.visit} of these days were collected before visit lengths were recorded; the length and page figures leave them out.`) : null,
  coverageNote(cov, r)));
  if (v) {
    const pageItems = PAGE_BINS.map(([label, test]) => ({ label, value: Object.entries(v.pages || {}).filter(([kk]) => test(Number(kk))).reduce((a, [, x]) => a + x, 0) }));
    const secItems = SEC_BINS.map(([label, lo, hi]) => ({ label, value: Object.entries(v.seconds || {}).filter(([kk]) => Number(kk) >= lo && Number(kk) < hi).reduce((a, [, x]) => a + x, 0) }));
    out.push(h("div", { class: "cols" },
      panel("Pages per visit", "Visits by how many pages they loaded", bars(pageItems.map((x) => ({ ...x, title: `${x.label} page${x.label === "1" ? "" : "s"}` })), { label: "Visits by pages loaded", unit: "visits", H: 180, half: true })),
      panel("Visit length", "From the first request to the last", bars(secItems, { label: "Visits by length", unit: "visits", H: 180, half: true, color: "var(--views)" }))));
  }
  const keep = pathMatch(s);
  out.push(h("div", { class: "cols three" },
    panel("Where visits started", "The first page each visitor read", blist(ranked(t.by?.landing, keep), { drill: "landing", empty: "No landing page recorded." })),
    panel("Where visits ended", "The last page a visitor was seen on", blist(ranked(v?.exits, keep), { drill: "path", color: "var(--views)", empty: v ? "No exit page recorded." : "Not recorded for this range." })),
    panel("Common next steps", "From one page to the next", blist(ranked(v?.steps, (x) => x.split(" → ").some(keep)), { color: "var(--ink-3)", empty: v ? "No visit went past one page." : "Not recorded for this range." }))));
  out.push(...engagement(s, r));
  out.push(h("section", { class: "s" }, h("h2", null, "Each visit"),
    h("p", { class: "sub" }, `Newest first, one row per visit; open a row for its pages in order. Every global filter applies, and the buttons below narrow the list further. Anonymous, kept ${m.journey_days || 7} days.`),
    journeys(m, s, r)));
  out.push(h("section", { class: "s" }, h("h2", null, "Entry pages"),
    h("p", { class: "sub" }, "The first page of each visit."),
    entryTable(t.by?.landing, { keep, total: readers, r })));
  return out;
}

// ------------------------------------------- engagement and returning by source
// From visits.json (DATA-CONTRACT.md, "Day kind engagement"): count rows per
// day, summed here over the range's verified days. Fetched once, then cached.

function sumRows(blobs) {
  const out = {};
  for (const blob of blobs) for (const [k, x] of Object.entries(blob || {})) {
    const o = out[k] || (out[k] = { visits: 0, views: 0, one_page: 0, seconds: {}, readers: 0, returning: 0 });
    for (const f of ["visits", "views", "one_page", "readers", "returning"]) o[f] += x[f] || 0;
    for (const [b, v] of Object.entries(x.seconds || {})) o.seconds[b] = (o.seconds[b] || 0) + v;
  }
  return out;
}

// The range's part of visits.json: rows summed over the verified days that have them.
function engagementOf(file, r) {
  let days;
  if (r.kind === "today") days = file?.today?.state === "ok" ? [file.today] : [];
  else days = (file?.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  const eng = days.filter((d) => d.engagement), ret = days.filter((d) => d.returning_by_source);
  return {
    days: days.length, today: r.kind === "today",
    source: eng.length ? sumRows(eng.map((d) => d.engagement.by_source)) : null,
    device: eng.length ? sumRows(eng.map((d) => d.engagement.by_device)) : null,
    engMissing: days.length - eng.length,
    returning: ret.length ? sumRows(ret.map((d) => d.returning_by_source.by_source)) : null,
    retMissing: days.length - ret.length,
    warming: ret.some((d) => d.returning_by_source.warming_up),
  };
}

const few = (v, fmt) => (v == null ? h("span", { style: { color: "var(--ink-3)" } }, FEW) : fmt(v));
const rated = (part, whole) => (whole >= MIN_RATE ? part / whole : null);
const pctOf = (x) => (x > 0 && x < 0.01 ? "<1%" : `${Math.round(x * 100)}%`);

function engagementTable(rows, dim, label, r) {
  const list = Object.entries(rows).map(([k, x]) => ({ k, visits: x.visits, ppv: rated(x.views, x.visits), one: rated(x.one_page, x.visits), med: x.visits >= MIN_RATE ? median(x.seconds) : null }));
  return table([
    { key: "k", label, drill: dim },
    { key: "visits", label: "Visits", num: true, fmt: (v) => n(v) },
    { key: "ppv", label: "Pages per visit", num: true, fmt: (v) => few(v, (x) => x.toFixed(1)), csv: (x) => (x.ppv == null ? "" : x.ppv.toFixed(2)) },
    { key: "one", label: "One-page", num: true, fmt: (v) => few(v, pctOf), csv: (x) => (x.one == null ? "" : x.one.toFixed(4)) },
    { key: "med", label: "Typical length", num: true, fmt: (v) => few(v, duration), csv: (x) => x.med ?? "" },
  ], { caption: `Engagement by ${dim}`, rows: list, file: fileName(`engagement-by-${dim}`, r), limit: 10, search: false, empty: "No visits recorded." });
}

function returningTable(rows, r) {
  const list = Object.entries(rows).map(([k, x]) => ({ k, readers: x.readers, fresh: x.readers - x.returning, returning: x.returning, share: rated(x.returning, x.readers) }));
  return table([
    { key: "k", label: "Source", drill: "source" },
    { key: "readers", label: "Visits", num: true, fmt: (v) => n(v) },
    { key: "fresh", label: "New", num: true, fmt: (v) => n(v) },
    { key: "returning", label: "Returning", num: true, fmt: (v) => n(v) },
    { key: "share", label: "Returning share", num: true, fmt: (v) => few(v, pctOf), csv: (x) => (x.share == null ? "" : x.share.toFixed(4)) },
  ], { caption: "New and returning by source", rows: list, file: fileName("returning-by-source", r), limit: 10, search: false, empty: "No visits recorded." });
}

function engagementBody(e, s, r) {
  const missing = (k) => (k ? h("p", { class: "note" }, `${n(k)} of these days ${k === 1 ? "was" : "were"} collected before this was recorded; the figures leave ${k === 1 ? "it" : "them"} out.`) : null);
  const filtered = ["country", "path", "browser", "campaign", "referrer", "source", "device"].some((k) => s[k]);
  const eng = [h("h2", null, "Engagement by source and device"),
    h("p", { class: "sub" }, `Each visit by where it came from and its device. A rate is given only over ${MIN_RATE} visits or more; under that it says ${FEW}.`)];
  if (!e.source) eng.push(h("p", { class: "empty" }, e.days ? "Not recorded for this range." : "No verified day in this range."));
  else eng.push(h("div", { class: "cols" },
    panel("By source", "The source of each visit's first page", engagementTable(e.source, "source", "Source", r)),
    panel("By device", "The device each visit used", engagementTable(e.device, "device", "Device", r))), missing(e.engMissing));
  const ret = [h("h2", null, "New and returning by source"),
    h("p", { class: "sub" }, "Returning: the same visitor (a keyed hash, kept 30 days) was seen on an earlier day in the 30 before. Labelled by this visit's source.")];
  if (!e.returning) ret.push(h("p", { class: "empty" }, e.days ? "Not recorded for this range: returning visitors are counted only when the visitor key is set." : "No verified day in this range."));
  else ret.push(returningTable(e.returning, r), missing(e.retMissing),
    e.warming ? h("p", { class: "note" }, "Warming up: some of these days have fewer than 30 earlier days of visitor hashes behind them, so their returning counts are too low.") : null);
  if (filtered) eng.push(h("p", { class: "note" }, "These tables are for all visits: the filters above do not narrow them."));
  return [h("section", { class: "s" }, ...eng), h("section", { class: "s" }, ...ret)];
}

function engagement(s, r) {
  const a = h("section", { class: "s" }, h("h2", null, "Engagement by source and device"), h("p", { class: "sub" }, "Loading..."));
  const b = h("section", { class: "s" }, h("h2", null, "New and returning by source"));
  getJSON(`${base(s.view)}visits.json`).then((file) => {
    if (!file) { a.lastChild.textContent = "Not written yet for this page."; b.remove(); return; }
    const [x, y] = engagementBody(engagementOf(file, r), s, r);
    a.replaceChildren(...x.childNodes);
    b.replaceChildren(...y.childNodes);
  }, () => { a.lastChild.textContent = "visits.json could not be read."; b.remove(); });
  return [a, b];
}
