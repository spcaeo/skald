// Visits, the parts other tabs share: the global filters on a journey
// (journeyFilter), one journey as a list row (the funnel's), and the
// engagement and returning tables by source and device (from visits.json).
// Traffic > Visitors itself is drawn by tr-visitors.js.

import { time as tzTime } from "../tz.js";
import { h, n, duration } from "../ui.js";
import { pagesWords } from "../visitpages.js";
import { base, getJSON, pathMatch } from "../data.js";
import { median } from "../visitorfigs.js";
import { fromState, matcher, without, leaves } from "../rules.js";
import { table } from "../table.js";
import { panel, fileName } from "./common.js";
import { folded } from "./visitlist.js";
import { openVisitor, touchLine } from "./visitor.js";

const MIN_RATE = 10;   // no rate over fewer visits than this: too few to mean anything
const FEW = "too few to say";

/* The visits the filters keep: the single filters and the advanced rules (js/rules.js),
   all but those a visit does not carry (a crawler: the banner says so). */
export function journeyFilter(s) {
  return matcher(without(fromState(s), "visit"), "visit");
}

/* One journey in a list (the funnel's): a row that opens the visitor drawer
   (visitor.js), the same drawer as every visit. */
export function journey(j) {
  const item = h("li", { class: "jr" });
  const fold = folded(j.trail);
  const steps = fold.slice(0, 6).flatMap((p, i) => [i ? h("i", { "aria-hidden": "true" }, "›") : null, h("span", null, p.path, p.times > 1 ? ` ×${p.times}` : null)]);
  if (fold.length > 6) steps.push(h("i", null, `+${fold.length - 6}`));
  const ft = touchLine(j);
  const btn = h("button", { type: "button", "aria-haspopup": "dialog", title: "Open this visitor" },
    h("span", { class: "j-t" }, tzTime(j.start, { date: true, label: false })),
    h("span", { class: "j-p" }, steps),
    h("span", { class: "j-m" }, `${pagesWords(j)}, ${duration(j.seconds)}`,
      ...Object.entries(j.utm || {}).slice(0, 2).map(([k, v]) => h("span", { class: "utm", style: { marginLeft: "6px" } }, `${k}: ${v}`)),
      j.returning ? h("span", { class: "rep yes", style: { marginLeft: "6px" } }, "returning") : null,
      ft ? h("small", { class: "v-ft" }, ft) : null));
  btn.addEventListener("click", () => openVisitor(j));
  item.append(btn);
  return item;
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

// A rate over too few visits is left blank, and the table says so once under it
// (not "too few to say" in every cell).
const few = (v, fmt) => (v == null ? "" : fmt(v));
const rated = (part, whole) => (whole >= MIN_RATE ? part / whole : null);
const pctOf = (x) => (x > 0 && x < 0.01 ? "<1%" : `${Math.round(x * 100)}%`);
const fewNote = (k) => (k ? `A blank rate: ${k === 1 ? "this row has" : `${n(k)} rows have`} fewer than ${MIN_RATE} visits, ${FEW}.` : null);

function engagementTable(rows, dim, label, r) {
  const list = Object.entries(rows).map(([k, x]) => ({ k, visits: x.visits, ppv: rated(x.views, x.visits), one: rated(x.one_page, x.visits), med: x.visits >= MIN_RATE ? median(x.seconds) : null }));
  return table([
    { key: "k", label, type: "text", drill: dim },
    { key: "visits", label: "Visits", num: true, fmt: (v) => n(v) },
    { key: "ppv", label: "Pages per visit", num: true, fmt: (v) => few(v, (x) => x.toFixed(1)), csv: (x) => (x.ppv == null ? "" : x.ppv.toFixed(2)) },
    { key: "one", label: "One-page", num: true, fmt: (v) => few(v, pctOf), csv: (x) => (x.one == null ? "" : x.one.toFixed(4)) },
    { key: "med", label: "Typical length", num: true, fmt: (v) => few(v, duration), csv: (x) => x.med ?? "" },
  ], { caption: `Engagement by ${dim}`, rows: list, file: fileName(`engagement-by-${dim}`, r), limit: 10, search: false, empty: "No visits recorded.",
    note: fewNote(list.filter((x) => x.ppv == null).length) });
}

function returningTable(rows, r) {
  const list = Object.entries(rows).map(([k, x]) => ({ k, readers: x.readers, fresh: x.readers - x.returning, returning: x.returning, share: rated(x.returning, x.readers) }));
  return table([
    { key: "k", label: "Source", type: "text", drill: "source" },
    { key: "readers", label: "Visits", num: true, fmt: (v) => n(v) },
    { key: "fresh", label: "New", num: true, fmt: (v) => n(v) },
    { key: "returning", label: "Returning", num: true, fmt: (v) => n(v) },
    { key: "share", label: "Returning share", num: true, fmt: (v) => few(v, pctOf), csv: (x) => (x.share == null ? "" : x.share.toFixed(4)) },
  ], { caption: "New and returning by source", rows: list, file: fileName("returning-by-source", r), limit: 10, search: false, empty: "No visits recorded.",
    note: fewNote(list.filter((x) => x.share == null).length) });
}

function engagementBody(e, s, r) {
  const missing = (k) => (k ? h("p", { class: "note" }, `${n(k)} of these days ${k === 1 ? "was" : "were"} collected before this was recorded; the figures leave ${k === 1 ? "it" : "them"} out.`) : null);
  // Any filter a visit can carry, the advanced rules too: these rows are whole-site sums
  // (visits.json), so each table says the filters do not narrow it.
  const filtered = leaves(without(fromState(s), "visit")).length > 0;
  const allNote = () => (filtered ? h("p", { class: "note" }, "For all visits: the filters above do not narrow this table.") : null);
  const eng = [h("h2", null, "Engagement by source and device"),
    h("p", { class: "sub" }, `Each visit by where it came from and its device. A rate is given over ${MIN_RATE} visits or more.`)];
  if (!e.source) eng.push(h("p", { class: "empty" }, e.days ? "Not recorded for this range." : "No verified day in this range."));
  else eng.push(h("div", { class: "cols" },
    panel("By source", "The source of each visit's first page", engagementTable(e.source, "source", "Source", r)),
    panel("By device", "The device each visit used", engagementTable(e.device, "device", "Device", r))), missing(e.engMissing));
  const ret = [h("h2", null, "New and returning by source"),
    h("p", { class: "sub" }, "Each visit, labelled by its own source. Returning: the same visitor (a keyed hash, kept 30 days) was seen on an earlier day in the 30 before.")];
  if (!e.returning) ret.push(h("p", { class: "empty" }, e.days ? "Not recorded for this range: returning visitors are counted only when the visitor key is set." : "No verified day in this range."));
  else ret.push(returningTable(e.returning, r), missing(e.retMissing),
    e.warming ? h("p", { class: "note" }, "Warming up: some of these days have fewer than 30 earlier days of visitor hashes behind them, so their returning counts are too low.") : null);
  if (filtered) { eng.push(h("p", { class: "note" }, "For all visits: the filters above do not narrow these tables.")); ret.push(allNote()); }
  return [h("section", { class: "s" }, ...eng), h("section", { class: "s" }, ...ret)];
}

/* The two sections, filled when visits.json arrives. onRows(e): the summed rows, for
   a caller that says more from them (the engagement card's AI assistant line). */
export function engagementTables(s, r, onRows) {
  const a = h("section", { class: "s" }, h("h2", null, "Engagement by source and device"), h("p", { class: "sub" }, "Loading..."));
  const b = h("section", { class: "s" }, h("h2", null, "New and returning by source"));
  getJSON(`${base(s.view)}visits.json`).then((file) => {
    if (!file) { a.lastChild.textContent = "Not written yet for this page."; b.remove(); return; }
    const e = engagementOf(file, r);
    const [x, y] = engagementBody(e, s, r);
    a.replaceChildren(...x.childNodes);
    b.replaceChildren(...y.childNodes);
    if (onRows) onRows(e);
  }, () => { a.lastChild.textContent = "visits.json could not be read."; b.remove(); });
  return [a, b];
}

/* One source's one-page share, when it has enough visits to say: {visits, share} or null. */
export function onePageOf(e, source) {
  const x = e?.source?.[source];
  return x && x.visits >= MIN_RATE ? { visits: x.visits, share: x.one_page / x.visits } : null;
}
