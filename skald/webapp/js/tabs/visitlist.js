// Each visit, as a matrix: one row per anonymous journey (no address, no
// browser string, no identifier), sortable and searchable, with quick
// filters above it. Under a visit's source, where its visitor first came from
// (first_touch, firsttouch.py) when that was elsewhere. A row opens the visitor
// drawer (visitor.js); visitFacts is its "This visit" part.
// Also the entry pages, with a share bar. Visits.js draws the rest of the tab.

import { when, label as tzLabel } from "../tz.js";
import { h, n, duration, share, weekday } from "../ui.js";
import { shown } from "../labels.js";
import { mark } from "../icons.js";
import { label as named, link } from "../drill.js";
import { table } from "../table.js";
import { ranked } from "../data.js";
import { country, countryName, countryWords, flag, flagEl, withFlag, city, cityPlace, cityName } from "./readers.js";
import { fileName } from "./common.js";
import { visitLikely, visitRead } from "./likelyai.js";
import { visitDirect } from "./likelydirect.js";
import { openVisitor, touchLine, touchName, ago } from "./visitor.js";
import { pagesWords, visitPages } from "../visitpages.js";
import { withUrl, copyIf } from "../urlactions.js";

export const NOTE = { not_found: "met a page not found (404)", posted: "sent a form", in_app: "moved inside the site without loading a page" };
const BADGE = { posted: "form sent", not_found: "404" };
let whenKept = 7;   // journey_days, set by visitMatrix

// "+0 s", "+40 s", "+4 min": a step's offset (bucketed by the server). None when not kept.
export const offset = (sec) => (sec == null ? "" : `+${sec < 1 ? "0 s" : duration(sec)}`);

/* Steps in a row on the same page fold into one, with how many times it was
   seen: a reload reads "/ ×2", not "/ › /". */
export function folded(trail) {
  const out = [];
  for (const p of trail || []) {
    const last = out[out.length - 1];
    if (last && last.path === p.path) { last.times += 1; last.page = last.page || p.page; }
    else out.push({ path: p.path, page: p.page, at: p.at, times: 1 });
  }
  return out;
}
export const trailWords = (trail) => folded(trail).map((p) => `${p.path}${p.times > 1 ? ` ×${p.times}` : ""}`).join(" › ");

// Where a visit came from: the assistant or site named, else its source type.
function sourceOf(j) {
  const via = j.via || "";
  const host = /\./.test(via);
  const icon = j.source === "AI assistant" && via ? mark("assistant", via) || mark("source", j.source)
    : host ? mark("referrer", via) : mark("source", j.source);
  const campaign = j.utm?.campaign || (j.campaign ? j.campaign.split(" / ").pop() : "");
  return { name: via || shown(j.source) || "Not recorded", type: via ? j.source : "", icon, campaign: campaign && campaign !== "-" ? campaign : "" };
}
const visitor = (j) => (j.returning === true ? "Returning" : j.returning === false ? "New" : "");
const zoned = (j) => when(j.start);
const whenWords = (w) => (w ? `${weekday(w.day)} ${w.date}, ${w.hour}:${w.minute}` : "");

function countryCell(code) {
  const el = countryWords(code);   // "🇺🇸 USA", the full name in its tooltip and its text for search
  if (!flag(code)) el.classList.add("unk");
  return el;
}
function withMark(dim, value, cls) {
  return value ? h("span", { class: `named ${cls || ""}` }, mark(dim, value), h("span", { class: "nm" }, value)) : h("span", { class: "unk" }, "Not recorded");
}

// The trail in one line: the landing page, then the rest; the whole of it on hover.
function trailCell(j) {
  const steps = folded(j.trail);
  const line = h("span", { class: "vt-line", title: trailWords(j.trail) },
    steps.map((p, i) => [i ? h("i", { "aria-hidden": "true" }, " › ") : null,
      h("span", { class: `vt-s${i ? "" : " land"}${p.page ? "" : " inapp"}` }, p.path, p.times > 1 ? h("b", null, ` ×${p.times}`) : null)]));
  const badges = (j.flags || []).filter((f) => BADGE[f]).map((f) => h("span", { class: `vt-b ${f}`, title: NOTE[f] }, BADGE[f]));
  return h("span", { class: "vt" }, line, badges);
}

// ------------------------------------------------------------ the visit
/* This visit's own labels and tags: the visitor drawer's "This visit" part
   (visitor.js draws the rest: the visitor, the journey, every visit). */
export function visitFacts(j) {
  const src = sourceOf(j);
  const utm = Object.entries(j.utm || {}).map(([k, v]) => `${k}: ${v}`).join(", ");
  const rows = [
    ["Country", countryCell(j.country)],
    // Only with a city file (logs.city_db) and when it named the address's city.
    ["City", j.city ? h("span", { class: "named", title: cityName(j.city) }, flagEl(j.country), h("span", { class: "nm" }, city(j.city))) : ""],
    ["Device", withMark("device", j.device)],
    ["Browser", withMark("browser", j.browser)],
    ["System", j.os ? withMark("os", j.os) : ""],
    ["Source type", j.source ? named("source", j.source) : ""],
    ["Came from", j.via ? copyIf("text", h("span", { class: "named" }, src.icon, h("span", { class: "nm" }, j.via)), j.via, { label: "referrer" }) : ""],
    ["First came from", touchLine(j) ? touchLine(j).replace(/^first came from /, "") : ""],
    ["Likely AI", visitLikely(j)],
    ["Likely cause", visitDirect(j)],
    ["Referring page", j.ref_page ? withUrl(h("span", { class: "mono" }, j.ref_page), /^[a-z0-9.-]+\.[a-z]{2,}(\/|$)/i.test(j.ref_page) ? `https://${j.ref_page}` : "", { cls: "ua-after" }) : ""],
    ["Campaign", j.campaign ? copyIf("text", j.campaign.split(" / ").filter((x) => x && x !== "-").join(" / ")) : ""], ["Tags", utm ? copyIf("text", utm) : ""], ["Paid", j.paid], ["Searched for", j.search_terms ? copyIf("text", j.search_terms) : ""],
    ["Visitor", visitor(j) ? `${visitor(j)}${j.days_seen_30d != null ? `, seen on ${j.days_seen_30d} day${j.days_seen_30d === 1 ? "" : "s"} in 30` : ""}` : ""],
    ["Ended on", j.exit ? withUrl(h("span", { class: "mono" }, j.exit), j.exit, { cls: "ua-after" }) : ""],
    ...(j.flags || []).map((f) => ["Note", NOTE[f] || f]),
  ].filter(([, v]) => v);
  const seen = j.trail || [];
  const noAt = seen.length && seen.every((p) => p.at == null);
  return [visitRead(j),
    h("dl", { class: "rq-dl" }, rows.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)])),
    h("p", { class: "note" }, `${noAt ? "This visit was kept before step times were: the order is exact, the times are not known. " : ""}Journeys are kept ${whenKept} days. A log sees requests, not reading time.`)].filter(Boolean);
}

// Opens the visit in the visitor drawer (visitor.js): one drawer for every visit and visitor.
export const openVisit = (j) => openVisitor(j);

/* A city in a word: "Toronto". A city named as its country is followed by the code, so it
   never reads as the country: "Singapore, SGP". */
export function cityShort(label) {
  const name = cityPlace(label).split(", ")[0];
  const cc = /, ([A-Z]{2})$/.exec(label || "")?.[1];
  return cc && name === countryName(cc) ? `${name}, ${country(cc)}` : name;
}

// ------------------------------------------------------------ quick filters
const GROUPS = [
  ["source", "Source", (j) => j.source || "Unknown", 0],
  ["device", "Device", (j) => j.device || "Unknown", 0],
  ["country", "Country", (j) => j.country || "Unknown", 5],
  ["visitor", "Visitor", (j) => visitor(j), 0],
];
function quick(list, onChange) {
  const picked = {};
  const wrap = h("div", { class: "vq", role: "group", "aria-label": "Quick filters for this list" });
  for (const [key, title, of, top] of GROUPS) {
    const counts = new Map();
    for (const j of list) { const v = of(j); if (v) counts.set(v, (counts.get(v) || 0) + 1); }
    let vals = [...counts].sort((a, b) => b[1] - a[1]);
    if (top) vals = vals.slice(0, top);
    if (vals.length < 2) continue;
    const btns = vals.map(([v, k]) => {
      const words = key === "country" ? country(v) : shown(v);
      const icon = key === "country" ? flagEl(v)
        : key === "device" ? mark("device", v) : key === "source" ? mark("source", v) : null;
      const b = h("button", { type: "button", class: "vq-c", "aria-pressed": "false" }, icon, h("span", null, words), h("span", { class: "vq-n" }, n(k)));
      b.setAttribute("aria-label", `${key === "country" ? countryName(v) : words}: ${n(k)} visits`);
      if (key === "country") b.title = countryName(v);
      b.addEventListener("click", () => {
        const on = picked[key] !== v;
        picked[key] = on ? v : null;
        for (const x of btns) x.setAttribute("aria-pressed", "false");
        if (on) b.setAttribute("aria-pressed", "true");
        onChange(list.filter((j) => GROUPS.every(([k2, , f2]) => !picked[k2] || f2(j) === picked[k2])));
      });
      return b;
    });
    wrap.append(h("div", { class: "vq-g", role: "group", "aria-label": title }, h("span", { class: "vq-l" }, title), btns));
  }
  return wrap;
}

// ------------------------------------------------------------ the matrix
/* The table's columns. Each says its key, its label and its type (text, date, num,
   badge), and the row carries the plain value under that key, so the shared table's
   sorting, column filters, column chooser and export (table.js) work on them as on
   any other table; fmt draws the cell, csv writes it. */
function columns(hasCity) {
  const zone = tzLabel();
  return [
    { key: "start", label: `When (${zone})`, type: "date", cls: "c-when", fmt: (_, x) => {
      const w = zoned(x.j);
      const b = h("button", { type: "button", class: "v-open", "aria-label": `Open the visit on ${whenWords(w)}` },
        h("span", { class: "v-hm" }, w ? `${w.hour}:${w.minute}` : ""), h("span", { class: "v-day" }, w ? `${weekday(w.day)} ${w.date}` : ""));
      b.addEventListener("click", () => openVisit(x.j));
      return b;
    }, csv: (x) => { const w = zoned(x.j); return w ? `${w.day} ${w.hour}:${w.minute}` : ""; } },
    // Flag and three-letter code; the name on hover, and in the CSV (table.js COUNTRY_CSV).
    { key: "country", label: "Country", type: "text", cls: "c-country", fmt: (_, x) => countryCell(x.j.country), country: (x) => x.j.country },
    // Only with a city file (logs.city_db): the column is left out when no visit here has a city.
    hasCity ? { key: "city", label: "City", type: "text", cls: "c-city", fmt: (v, x) => (x.j.city ? h("span", { class: "v-city", title: cityName(x.j.city) }, v) : h("span", { class: "unk" }, "Not recorded")),
      csv: (x) => (x.j.city ? cityPlace(x.j.city) : "") } : null,
    { key: "device", label: "Device", type: "text", cls: "c-device", fmt: (v, x) => h("span", { class: "v-stack" }, withMark("device", v),
      x.j.browser || x.j.os ? h("small", null, [x.j.browser, x.j.os].filter(Boolean).join(", ")) : null),
    csv: (x) => [x.j.device, [x.j.browser, x.j.os].filter(Boolean).join(" on ")].filter(Boolean).join(", ") },
    { key: "src", label: "Source", type: "text", cls: "c-src", fmt: (v, x) => {
      const s = sourceOf(x.j);
      const ft = touchLine(x.j);
      return h("span", { class: "v-stack" }, h("span", { class: "named" }, s.icon, h("span", { class: "nm" }, v)),
        s.type || s.campaign ? h("small", null, s.type, s.type && s.campaign ? ", " : "", s.campaign ? h("span", { class: "v-camp" }, s.campaign) : null) : null,
        ft ? h("small", { class: "v-ft", title: "The first visit we know of for this visitor (visitor ID, kept address or 30-day code)" },
          "First came from ", h("b", null, touchName(x.j.first_touch)), `, ${ago(x.j.first_touch.day)}`) : null);
    }, csv: (x) => { const s = sourceOf(x.j); return [s.type ? `${s.type}: ${s.name}` : s.name, s.campaign ? `campaign ${s.campaign}` : "", touchLine(x.j)].filter(Boolean).join("; "); } },
    { key: "visitor", label: "Visitor", type: "badge", cls: "c-vis", fmt: (v) => (v ? h("span", { class: `v-vis ${v === "New" ? "new" : "ret"}` }, v) : "") },
    // Pages: loaded from the server plus steps seen in the browser, the browser ones said (visitpages.js).
    { key: "pages", label: "Pages", type: "num", num: true, cls: "c-pages", fmt: (v, x) => {
      const b = visitPages(x.j).browser;
      return h("span", { class: "v-pg", "data-unit": v === 1 ? "page" : "pages", title: pagesWords(x.j) }, n(v), b ? h("small", null, ` (${n(b)} in the browser)`) : null);
    }, csv: (x) => x.pages },
    { key: "seconds", label: "Time on site", type: "num", num: true, cls: "c-time", fmt: (v, x) => h("span", { class: "v-len", "data-pages": `${pagesWords(x.j)}, ` }, duration(v)), csv: (x) => duration(x.seconds) },
    { key: "path", label: "Pages in order", type: "text", cls: "c-path", fmt: (_, x) => trailCell(x.j),
      csv: (x) => x.j.trail.map((p) => `${p.path}${p.at != null ? ` (${offset(p.at)})` : ""}${p.page ? "" : " (in-app)"}`).join(" > ") },
  ].filter(Boolean);
}

// The row whose visitor is open stays marked until its drawer closes.
function markOpen(tr) {
  for (const x of tr.parentElement?.querySelectorAll("tr.on") || []) x.classList.remove("on");
  const dlg = [...document.querySelectorAll("dialog.dw[open]")].pop();
  if (!dlg) return;
  tr.classList.add("on");
  dlg.addEventListener("close", () => tr.classList.remove("on"), { once: true });
}

/* all: the range's journeys; list: those the global filters keep. */
export function visitMatrix(all, list, r, keptDays) {
  whenKept = keptDays || 7;
  const rows = list.map((j, i) => {
    const src = sourceOf(j);
    return { j, __k: i, start: j.start, country: j.country || "", city: j.city ? cityShort(j.city) : "", device: j.device || "", src: src.name, ft: touchLine(j),
      visitor: visitor(j), pages: visitPages(j).all ?? j.pages, seconds: j.seconds, path: trailWords(j.trail) };
  });
  const tbl = table(columns(list.some((j) => j.city)), {
    caption: "Each visit", rows, file: fileName("visits", r), limit: 25, sortKey: "start", dir: -1,
    placeholder: "Search pages, cities, sources", rowClass: () => "v-row", onRow: (x) => openVisit(x.j),
    empty: all.length ? "No visit matches these filters." : "No visit journeys are kept for this range.",
  });
  tbl.classList.add("vtab");
  // The drawer is open once the click (or Enter) is handled: mark its row then.
  const later = (e) => { const tr = e.target.closest?.("tr.v-row"); if (tr) setTimeout(() => markOpen(tr)); };
  tbl.addEventListener("click", later);
  tbl.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") later(e); });
  const byJourney = new Map(rows.map((x) => [x.j, x]));
  const chips = quick(list, (kept) => tbl.update(kept.map((j) => byJourney.get(j))));
  return h("div", { class: "vmatrix" }, chips, tbl);
}

// ------------------------------------------------------------ entry pages
export function entryTable(obj, { keep, total, r }) {
  const list = ranked(obj, keep).map(([k, v]) => ({ k, v }));
  const sum = total ?? list.reduce((s, x) => s + x.v, 0);
  const max = list.reduce((m, x) => Math.max(m, x.v), 0) || 1;
  return table([
    { key: "k", label: "Page", path: true, cls: "c-entry", fmt: (v) => link("landing", v), csv: (x) => x.k },
    { key: "v", label: "Visits", num: true },
    { key: "share", label: "Share", num: true, cls: "c-share", sort: (x) => x.v, fmt: (_, x) => h("span", { class: "v-share" },
      h("span", { class: "v-bar", "aria-hidden": "true" }, h("i", { style: { width: `${(x.v / max) * 100}%` } })), h("span", null, share(x.v, sum))),
    csv: (x) => (share(x.v, sum) ? (x.v / sum).toFixed(4) : "") },
  ], { caption: "Entry pages", rows: list, file: fileName("entry-pages", r), limit: 12, empty: "No landing page recorded." });
}
