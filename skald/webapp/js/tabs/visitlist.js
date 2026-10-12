// Each visit, as a matrix: one row per anonymous journey (no address, no
// browser string, no identifier), sortable and searchable, with quick
// filters above it. A row opens the whole journey: each step with its
// offset from the visit's first request, and the visit's labels.
// Also the entry pages, with a share bar. Visits.js draws the rest of the tab.

import { openDrawer } from "../drawer.js";
import { when, label as tzLabel } from "../tz.js";
import { h, n, duration, pct1, weekday } from "../ui.js";
import { mark } from "../icons.js";
import { label as named, link } from "../drill.js";
import { table } from "../table.js";
import { ranked } from "../data.js";
import { country, flagEl, withFlag } from "./readers.js";
import { fileName } from "./common.js";
import { visitLikely } from "./likelyai.js";

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
  return { name: via || j.source || "Unknown", type: via ? j.source : "", icon, campaign: campaign && campaign !== "-" ? campaign : "" };
}
const visitor = (j) => (j.returning === true ? "Returning" : j.returning === false ? "New" : "");
const zoned = (j) => when(j.start);
const whenWords = (w) => (w ? `${weekday(w.day)} ${w.date}, ${w.hour}:${w.minute}` : "");

function countryCell(code) {
  const f = flagEl(code);
  return h("span", { class: `named${f ? "" : " unk"}` }, f, h("span", { class: "nm" }, country(code)));
}
function withMark(dim, value, cls) {
  return value ? h("span", { class: `named ${cls || ""}` }, mark(dim, value), h("span", { class: "nm" }, value)) : h("span", { class: "unk" }, "Unknown");
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

// A strip under the length: one tick per page seen, at its offset.
function track(j) {
  const at = (j.trail || []).map((p) => p.at);
  if (!j.seconds || at.length < 2 || at.some((a) => a == null)) return null;
  return h("span", { class: "v-track", "aria-hidden": "true" },
    at.map((a) => h("i", { style: { left: `${Math.min(100, (a / j.seconds) * 100)}%` } })));
}

// ------------------------------------------------------------ the journey
export function visitBody(j) {
  const src = sourceOf(j), seen = j.trail || [];
  const stat = (k, v) => h("div", null, h("dt", null, k), h("dd", null, v));
  const steps = h("ol", { class: "vj-steps" }, seen.map((p, i) => {
    const again = i && seen[i - 1].path === p.path;
    return h("li", { class: p.page ? null : "inapp" },
      h("span", { class: "vj-at" }, offset(p.at) || "-"),
      h("span", { class: "vj-p" }, mark("path", p.path), h("span", { class: "vj-path" }, p.path),
        again ? h("small", null, p.page ? "the same page again (a reload)" : "the same page again") : null,
        p.page ? null : h("small", null, "moved inside the site; no page loaded")));
  }));
  const utm = Object.entries(j.utm || {}).map(([k, v]) => `${k}: ${v}`).join(", ");
  const rows = [
    ["Country", countryCell(j.country)],
    ["Device", withMark("device", j.device)],
    ["Browser", withMark("browser", j.browser)],
    ["System", j.os ? withMark("os", j.os) : ""],
    ["Source type", j.source ? named("source", j.source) : ""],
    ["Came from", j.via ? h("span", { class: "named" }, src.icon, h("span", { class: "nm" }, j.via)) : ""],
    ["Likely AI", visitLikely(j)],
    ["Referring page", j.ref_page], ["Campaign", j.campaign ? j.campaign.split(" / ").filter((x) => x && x !== "-").join(" / ") : ""], ["Tags", utm], ["Paid", j.paid], ["Searched for", j.search_terms],
    ["Visitor", visitor(j) ? `${visitor(j)}${j.days_seen_30d != null ? `, seen on ${j.days_seen_30d} day${j.days_seen_30d === 1 ? "" : "s"} in 30` : ""}` : ""],
    ["Ended on", j.exit],
    ...(j.flags || []).map((f) => ["Note", NOTE[f] || f]),
  ].filter(([, v]) => v);
  const noAt = seen.length && seen.every((p) => p.at == null);
  return h("div", { class: "vj" },
    h("dl", { class: "vj-sum" }, stat("Pages", n(j.pages)), stat("Time on site", duration(j.seconds)), stat("Steps seen", n(seen.length)), stat("Visitor", visitor(j) || "not recorded")),
    h("section", null, h("h3", null, "Pages in order"),
      h("p", { class: "note" }, noAt ? "This visit was kept before step times were: the order is exact, the times are not known."
        : "Time since the visit's first request, rounded like visit lengths. A log sees requests, not reading time."),
      steps, seen.length >= 50 ? h("p", { class: "note" }, "Only the first 50 steps are kept.") : null),
    h("section", null, h("h3", null, "About this visit"),
      h("dl", { class: "rq-dl" }, rows.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)]))),
    h("p", { class: "note" }, `Anonymous: no address, no browser string, no identifier. Journeys are kept ${whenKept} days.`));
}

// Opens the journey in the app's shared drawer; one visit at a time, closed on a redraw.
export function openVisit(j) {
  const w = zoned(j);
  const title = `Visit on ${whenWords(w)}`;
  const subtitle = `${withFlag(j.country, country(j.country))}, ${[j.device, j.browser].filter(Boolean).join(", ")}, from ${sourceOf(j).name}: ${n(j.pages)} page${j.pages === 1 ? "" : "s"} in ${duration(j.seconds)}`;
  return openDrawer({ title, subtitle, body: visitBody(j), key: "visit", scope: "page" });
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
      const words = key === "country" ? country(v) : v;
      const icon = key === "country" ? flagEl(v)
        : key === "device" ? mark("device", v) : key === "source" ? mark("source", v) : null;
      const b = h("button", { type: "button", class: "vq-c", "aria-pressed": "false" }, icon, h("span", null, words), h("span", { class: "vq-n" }, n(k)));
      b.setAttribute("aria-label", `${words}: ${n(k)} visits`);
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
/* all: the range's journeys; list: those the global filters keep. */
export function visitMatrix(all, list, r, keptDays) {
  whenKept = keptDays || 7;
  const rows = list.map((j, i) => {
    const src = sourceOf(j);
    return { j, __k: i, start: j.start, country: country(j.country), device: j.device || "", browser: j.browser || "", src: src.name,
      visitor: visitor(j), pages: j.pages, seconds: j.seconds, path: trailWords(j.trail) };
  });
  const zone = tzLabel();
  const cols = [
    { key: "start", label: `When (${zone})`, cls: "c-when", fmt: (_, x) => {
      const w = zoned(x.j);
      const b = h("button", { type: "button", class: "v-open", "aria-label": `Open the visit on ${whenWords(w)}` },
        h("span", { class: "v-hm" }, w ? `${w.hour}:${w.minute}` : ""), h("span", { class: "v-day" }, w ? `${weekday(w.day)} ${w.date}` : ""));
      b.addEventListener("click", () => openVisit(x.j));
      return b;
    }, csv: (x) => { const w = zoned(x.j); return w ? `${w.day} ${w.hour}:${w.minute}` : ""; } },
    { key: "country", label: "Country", cls: "c-country", fmt: (_, x) => countryCell(x.j.country) },
    { key: "device", label: "Device", cls: "c-device", fmt: (v) => withMark("device", v) },
    { key: "browser", label: "Browser", cls: "c-browser", fmt: (v, x) => h("span", { class: "v-stack" }, withMark("browser", v),
      x.j.os ? h("small", null, x.j.os) : null), csv: (x) => [x.j.browser, x.j.os].filter(Boolean).join(" on ") },
    { key: "src", label: "Source", cls: "c-src", fmt: (v, x) => {
      const s = sourceOf(x.j);
      return h("span", { class: "v-stack" }, h("span", { class: "named" }, s.icon, h("span", { class: "nm" }, v)),
        s.type || s.campaign ? h("small", null, s.type, s.type && s.campaign ? ", " : "", s.campaign ? h("span", { class: "v-camp" }, s.campaign) : null) : null);
    }, csv: (x) => { const s = sourceOf(x.j); return [s.type ? `${s.type}: ${s.name}` : s.name, s.campaign ? `campaign ${s.campaign}` : ""].filter(Boolean).join("; "); } },
    { key: "visitor", label: "Visitor", cls: "c-vis", fmt: (v) => (v ? h("span", { class: `v-vis ${v === "New" ? "new" : "ret"}` }, v) : "") },
    { key: "pages", label: "Pages", num: true, cls: "c-pages", fmt: (v) => h("span", { class: "v-pg", "data-unit": v === 1 ? "page" : "pages" }, n(v)), csv: (x) => x.pages },
    { key: "seconds", label: "Time on site", num: true, cls: "c-time", fmt: (v, x) => h("span", { class: "v-len", "data-pages": `${n(x.pages)} page${x.pages === 1 ? "" : "s"}, ` }, duration(v), track(x.j)), csv: (x) => duration(x.seconds) },
    { key: "path", label: "Pages in order", cls: "c-path", fmt: (_, x) => trailCell(x.j),
      csv: (x) => x.j.trail.map((p) => `${p.path}${p.at != null ? ` (${offset(p.at)})` : ""}${p.page ? "" : " (in-app)"}`).join(" > ") },
  ];
  const tbl = table(cols, {
    caption: "Each visit", rows, file: fileName("visits", r), limit: 25, sortKey: "start", dir: -1,
    placeholder: "Search pages, countries, sources", rowClass: () => "v-row", onRow: (x) => openVisit(x.j),
    empty: all.length ? "No visit matches these filters." : "No visit journeys are kept for this range.",
  });
  tbl.classList.add("vtab");
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
      h("span", { class: "v-bar", "aria-hidden": "true" }, h("i", { style: { width: `${(x.v / max) * 100}%` } })), h("span", null, pct1(x.v, sum))),
    csv: (x) => (sum ? (x.v / sum).toFixed(4) : "") },
  ], { caption: "Entry pages", rows: list, file: fileName("entry-pages", r), limit: 12, empty: "No landing page recorded." });
}
