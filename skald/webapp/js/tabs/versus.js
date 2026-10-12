// Compare: two periods side by side. A is the period looked at (blue), B what
// it is compared with (orange); every change reads A against B. The figures
// come from the server's compare (GET <page>/api/compare, any two ranges up to
// 400 days, every filter crossed) when it has one, else from versuslocal.js.
// Only whole, verified days count; any day left out is named.

import { h, n, short, addDays, tip, untip } from "../ui.js";
import { getJSON, base } from "../data.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import * as S from "../state.js";
import { info } from "./tiles.js";
import { ranges, picker, fmt, length, before, yearBefore } from "./versuspick.js";
import { local, filterMode, cubeCtx, SERIES } from "./versuslocal.js";
import { DEMO } from "../demo.js";

const LABEL = {
  visitors: ["Visitors", "readers: browsers that read at least one page"],
  pages_read: ["Pages read", "pages people read"],
  visitors_from_ai: ["Visitors from AI", "people who came from an AI assistant's answer"],
  ai_asked: ["AI fetches: asked", "an assistant fetched a page because someone asked it just then"],
  ai_training: ["AI fetches: training", "crawls that feed an assistant's training or index"],
  search: ["Search crawls", "pages fetched by search engines"],
  leads: ["Leads", "sign-ups, contact forms, early access and demos booked, from the lead store"],
  returning: ["Returning", "visitors seen on an earlier day in 30"],
  pages_per_visitor: ["Pages per visit", "pages read divided by visitors"],
  not_found_people: ["Pages not found", "404s people met"],
};
const DIMS = [
  ["pages", "Pages", "Page", "path"], ["sources", "Sources", "Source", "source"], ["assistants", "AI assistants", "AI assistant", "assistant"],
  ["countries", "Countries", "Country", "country"], ["continents", "Continents", "Continent", null], ["devices", "Devices", "Device", "device"],
  ["browsers", "Browsers", "Browser", "browser"], ["os", "OS", "System", "os"], ["campaigns", "Campaigns", "Campaign", "campaign"],
];
let CUBE = null, CUBE_ASKED = false;
const ANSWERS = new Map();   // the server's answers, by query, for this page's life

// ---------------------------------------------------------------- numbers
const fmtV = (v, key, perDay) => (v == null ? "-" : key === "pages_per_visitor" ? v.toFixed(1) : perDay && Math.abs(v) < 100 ? v.toFixed(1) : n(v));
const pctWords = (p) => `${p > 0 ? "+" : "−"}${Math.abs(p) < 10 ? Math.abs(p).toFixed(1) : Math.round(Math.abs(p))}%`;
function delta(a, b, key, perDay) {
  if (a == null || b == null) return h("span", { class: "vs-d none" }, "no change shown");
  const d = a - b;
  // A change too small to show at this precision reads as no change.
  const dir = Number(fmtV(Math.abs(d), key, perDay).replace(/[^\d.]/g, "")) === 0 ? "flat" : d > 0 ? "up" : "down";
  // Colour says good or bad, the arrow says up or down: more pages not found is bad.
  const tone = dir === "flat" ? "" : (d > 0) === (key !== "not_found_people") ? " good" : " bad";
  return h("span", { class: `vs-d ${dir}${tone}` }, h("span", { "aria-hidden": "true" }, { up: "▲", down: "▼", flat: "■" }[dir]), " ",
    dir === "flat" ? "no change" : `${d > 0 ? "+" : "−"}${fmtV(Math.abs(d), key, perDay)}`,
    dir === "flat" ? null : h("small", null, b ? ` ${pctWords((d / b) * 100)}` : " new in A"),
    h("span", { class: "vh" }, dir === "up" ? " (up)" : dir === "down" ? " (down)" : ""));
}
const per = (v, used, perDay, key) => (v == null ? null : perDay && key !== "pages_per_visitor" ? v / Math.max(1, used) : v);

function kpis(res, perDay) {
  return h("div", { class: "vs-kpis" }, res.metrics.filter((x) => LABEL[x.key]).map((x) => {
    const [label, about] = LABEL[x.key];
    const a = res.a.used ? per(x.a, res.a.used, perDay, x.key) : null, b = res.b.used ? per(x.b, res.b.used, perDay, x.key) : null;
    return h("div", { class: "vs-kpi" }, h("div", { class: "k-l" }, label, info(about, label)),
      a == null && b == null && res.a.used && res.b.used ? h("div", { class: "vs-na" }, res.filtered ? "not split by these filters" : "not recorded on these days") : [
        h("div", { class: "vs-pair" }, h("span", { class: "vs-main" }, h("i", { class: "sa", "aria-hidden": "true" }), h("span", { class: "vh" }, "A "), fmtV(a, x.key, perDay)),
          h("span", { class: "vs-other" }, "vs ", h("i", { class: "sb", "aria-hidden": "true" }), h("span", { class: "vh" }, "B "), fmtV(b, x.key, perDay))),
        delta(a, b, x.key, perDay)]);
  }));
}

// The chart: A and B on one axis, day 1 with day 1. Buckets of 1, 7 or 30 days.
function buckets(list, key, size, perDay) {
  const out = [];
  for (let i = 0; i < list.length; i += size) {
    const part = list.slice(i, i + size);
    const vals = part.filter((d) => d.state === "ok" && d[key] != null).map((d) => d[key]);
    out.push({ first: part[0].day, last: part[part.length - 1].day, v: vals.length ? vals.reduce((x, y) => x + y, 0) / (perDay ? vals.length : 1) : null, n: vals.length, of: part.length });
  }
  return out;
}
function chart(res, key, size, perDay) {
  const a = buckets(res.series.a, key, size, perDay), b = buckets(res.series.b, key, size, perDay);
  const word = size === 1 ? "Day" : size === 7 ? "Week" : "Month";
  const box = h("div", { class: "vs-chart", role: "img", "aria-label": `${LABEL[key][0]}, A and B by ${word.toLowerCase()}` });
  const draw = () => {
    const W = Math.max(300, box.clientWidth || 900), H = 230, L = 46, R = 12, T = 12, Bm = 26;
    const len = Math.max(a.length, b.length);
    const top = Math.max(1, ...a.map((x) => x.v || 0), ...b.map((x) => x.v || 0));
    const step = (W - L - R) / Math.max(1, len - 1);
    const x = (i) => L + (len === 1 ? (W - L - R) / 2 : i * step);
    const y = (v) => T + (H - T - Bm) * (1 - v / top);
    const path = (list) => { let d = "", pen = false; list.forEach((p, i) => { if (p.v == null) { pen = false; return; } d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`; pen = true; }); return d; };
    const dots = (list, c) => (len > 60 ? "" : list.map((p, i) => (p.v == null ? "" : `<circle cx="${x(i).toFixed(1)}" cy="${y(p.v).toFixed(1)}" r="2.6" fill="${c}"/>`)).join(""));
    const grid = [0, 0.25, 0.5, 0.75, 1].map((f) => { const yy = y(top * f); return `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" class="g"/><text x="${L - 8}" y="${yy + 4}" text-anchor="end">${top < 5 ? (top * f).toFixed(1) : fmtV(top * f, key, perDay)}</text>`; }).join("");
    const every = Math.max(1, Math.ceil(len / Math.floor((W - L - R) / 64)));
    const ticks = Array.from({ length: len }, (_, i) => (i % every === 0 ? `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${word} ${i + 1}</text>` : "")).join("");
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">${grid}${ticks}<path d="${path(b)}" class="lb"/><path d="${path(a)}" class="la"/>${dots(b, "var(--vb)")}${dots(a, "var(--va)")}<line class="hair" x1="0" x2="0" y1="${T}" y2="${H - Bm}" opacity="0"/></svg>`;
    const svg = box.querySelector("svg"), hair = svg.querySelector(".hair");
    const span = (p) => (p ? (p.first === p.last ? short(p.first) : `${short(p.first)} to ${short(p.last)}`) : "");
    const row = (p, nm, color) => ({ color, value: p?.v == null ? "-" : fmtV(p.v, key, perDay), label: `${nm}, ${span(p)}${p && p.n < p.of ? ` (${p.n} of ${p.of} days counted)` : ""}` });
    svg.onpointermove = (e) => {
      const r = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(len - 1, Math.round((e.clientX - r.left - L) / (step || 1))));
      hair.setAttribute("x1", x(i)); hair.setAttribute("x2", x(i)); hair.setAttribute("opacity", "1");
      tip(e.clientX, e.clientY, `${word} ${i + 1}`, [row(a[i], "A", "var(--va)"), row(b[i], "B", "var(--vb)")]);
    };
    svg.onpointerleave = () => { hair.setAttribute("opacity", "0"); untip(); };
  };
  requestAnimationFrame(draw);
  if (typeof ResizeObserver === "function") new ResizeObserver(() => box.isConnected && draw()).observe(box);
  return box;
}

function dimTable(res, tab, perDay) {
  const [, name, one, drill] = DIMS.find(([k]) => k === tab);
  const list = res.dimensions?.[tab];
  if (!list) {
    const why = tab === "continents" && res.local ? "Continents come with the server's compare." : res.filtered ? `${name} cannot be split by these filters.` : `${name} were not recorded on these days.`;
    return h("p", { class: "empty" }, why);
  }
  const unit = tab === "pages" ? "pages read" : "visitors";
  const both = res.a.used > 0 && res.b.used > 0;
  const rows = list.map((x) => ({ k: x.name, a: res.a.used ? per(x.a, res.a.used, perDay) : null, b: res.b.used ? per(x.b, res.b.used, perDay) : null, isNew: both && x.new, gone: both && x.gone }))
    .map((x) => ({ ...x, d: both ? x.a - x.b : null, pct: both && x.b ? ((x.a - x.b) / x.b) * 100 : null }));
  const movers = new Set(rows.filter((x) => x.d && x.k !== "(all others)").sort((x, y) => Math.abs(y.d) - Math.abs(x.d)).slice(0, 3).map((x) => x.k));
  const num = (v) => (v == null ? "-" : perDay && Math.abs(v) < 100 ? v.toFixed(1) : n(v));
  return table([
    { key: "k", label: one, path: tab === "pages", fmt: (v) => (v === "(all others)" || !drill ? v : link(drill, v)), csv: (x) => x.k },
    { key: "a", label: `A ${unit}`, num: true, fmt: num },
    { key: "b", label: `B ${unit}`, num: true, fmt: num },
    { key: "d", label: "Change", num: true, fmt: (v) => (v == null ? "-" : h("span", { class: `vs-d ${v > 0 ? "up good" : v < 0 ? "down bad" : "flat"}` }, v ? `${v > 0 ? "+" : "−"}${num(Math.abs(v))}` : "0")) },
    { key: "pct", label: "Change %", num: true, fmt: (v, x) => (v == null ? (both && x.a ? "new" : "-") : v ? pctWords(v) : "0%") },
    { key: "badge", label: "", sort: (x) => (x.isNew ? 2 : x.gone ? 1 : 0), fmt: (_, x) => h("span", null,
      x.isNew ? h("span", { class: "vs-badge new", title: "In A, not in B" }, "New") : null, x.gone ? h("span", { class: "vs-badge gone", title: "In B, not in A" }, "Gone") : null,
      movers.has(x.k) ? h("span", { class: "vs-badge mover", title: "One of the three biggest changes" }, "Top mover") : null),
      csv: (x) => [x.isNew ? "new" : "", x.gone ? "gone" : "", movers.has(x.k) ? "top mover" : ""].filter(Boolean).join("; ") },
  ], { caption: `${name}, A against B`, rows, file: `compare-${tab}-${res.a.from}-to-${res.a.to}-vs-${res.b.from}-to-${res.b.to}.csv`, sortKey: "a", limit: 15,
    rowClass: (x) => (movers.has(x.k) ? "vs-mover" : null), empty: "Nothing recorded in either period." });
}

// Leave-outs, named: "6 Oct partial; 1 to 5 Oct not collected".
function absent(excluded) {
  const groups = {};
  for (const e of excluded || []) (groups[e.state] ||= []).push(e.day);
  const runs = (list) => {
    const out = [];
    for (const day of list.sort()) { const last = out[out.length - 1]; if (last && addDays(last[1], 1) === day) last[1] = day; else out.push([day, day]); }
    return out.map(([a, b]) => (a === b ? short(a) : `${short(a)} to ${short(b)}`)).join(", ");
  };
  const words = { partial: "partial", withheld: "withheld (did not pass the checks)", missing: "not collected", before: "before history begins" };
  return Object.entries(groups).map(([k, l]) => `${runs(l)} ${words[k] || k}`).join("; ");
}

// --------------------------------------------------------- where it comes from
function query(s, a, b) {
  const q = new URLSearchParams({ a: fmt(a), b: fmt(b) });
  for (const [k, v] of S.activeFilters(s)) q.set(k === "path" ? "page" : k, v);
  return q.toString();
}
function answer(m, s, a, b) {
  if (Array.isArray(m.files) && m.files.includes("page_index")) {
    const q = query(s, a, b);
    // If the server's compare does not answer, the page works it out itself and says so.
    if (!ANSWERS.has(q)) ANSWERS.set(q, getJSON(`api/compare?${q}`, true).then((r) => (r && r.ok ? r : Promise.reject(new Error(r?.error || "no answer"))))
      .catch((e) => inBrowser(m, s, a, b).then((res) => ({ ...res, problems: [DEMO.on ? "In the demo, these two periods are worked out on this page from the days it holds; a running Skald's server answers any two periods and any filters."
        : `The server's compare did not answer (${e.message || e}), so these figures are worked out on this page from the days it holds.`, ...res.problems] }))));
    return ANSWERS.get(q);
  }
  return inBrowser(m, s, a, b);
}
function inBrowser(m, s, a, b) {
  const mode = filterMode(s);
  if ((mode.kind === "cube" || mode.kind === "one") && !CUBE && !CUBE_ASKED && (!Array.isArray(m.files) || m.files.includes("cube"))) {
    CUBE_ASKED = true;
    return getJSON(`${base(s.view)}cube.json`).then((f) => { CUBE = f; return local(m, s, a, b, cubeCtx(CUBE, mode.f)); }, () => local(m, s, a, b, null));
  }
  return Promise.resolve(local(m, s, a, b, CUBE ? cubeCtx(CUBE, mode.f) : null));
}

// ------------------------------------------------------------------- page
export default function versus(m, s) {
  const { a, b } = ranges(s, m.anchor);
  const set = (patch) => S.set(patch, { replace: true });
  const bar = h("div", { class: "vs-bar" },
    picker("A", a, m.anchor, m.firstDay, (x) => set({ ca: fmt(x) })),
    h("span", { class: "vs-vs", "aria-hidden": "true" }, "vs"),
    picker("B", b, m.anchor, m.firstDay, (x) => set({ cb: fmt(x) }), [["Previous period", before(a)], ["Same period last year", yearBefore(a)]]));
  const body = h("div", { class: "vs-body" }, h("p", { class: "empty" }, "Comparing…"));
  const head = h("div", { class: "head" }, h("h1", null, "Compare"),
    info("Two periods side by side. A is the period you are looking at, B what it is compared with; every change reads A against B. Only whole, verified days count, and any day left out is named. The link keeps both periods and the filters, so it can be bookmarked or shared.", "Compare"),
    h("span", { class: "period" }, "A against B, whole verified days only"));
  answer(m, s, a, b).then((res) => {
    const differ = length(a) !== length(b) || res.a.used !== res.b.used;
    const perDay = differ && s.cnorm === "1";
    if (differ) bar.append(h("span", { class: "grow" }), h("label", { class: "rb-check vs-norm", title: "The periods count a different number of days: compare a typical day instead of the totals" },
      h("input", { type: "checkbox", checked: perDay, onchange: (e) => set({ cnorm: e.target.checked ? "1" : "" }) }), "Per day"));
    const gran = ["day", "week", "month"].includes(s.cgran) ? s.cgran : Math.max(length(a), length(b)) > 92 ? "week" : "day";
    const size = gran === "week" ? 7 : gran === "month" ? 30 : 1;
    const key = SERIES.includes(s.cm) ? s.cm : "visitors";
    const tab = DIMS.some(([k]) => k === s.cdim) ? s.cdim : "pages";
    const gaps = [["A", res.a], ["B", res.b]].map(([nm, x]) => [nm, x, absent(x.excluded)]).filter(([, , t]) => t);
    const emptySide = [["A", res.a], ["B", res.b]].filter(([, x]) => !x.used).map(([nm]) => nm);
    const first = m.firstDay ? short(m.firstDay) : "the first day";
    const empty = emptySide.length ? h("div", { class: "state" }, h("div", null, h("strong", null, `${emptySide.join(" and ")} ${emptySide.length > 1 ? "have" : "has"} no whole, verified day, so nothing can be compared yet. `),
      `History begins ${first}: pick ${emptySide.length > 1 ? "periods" : `a ${emptySide[0]}`} from then on${emptySide.includes("B") ? ", or wait until there are enough days for a period before A" : ""}.`)) : null;
    const notes = [...gaps.map(([nm, x, t]) => h("p", null, h("b", null, `${nm}: `), `left out ${t}; ${x.used} whole verified day${x.used === 1 ? "" : "s"} counted.`)), ...(res.problems || []).map((p) => h("p", null, p))];
    const gseg = h("div", { class: "seg plain", role: "group", "aria-label": "Granularity" }, [["day", "Daily"], ["week", "Weekly"], ["month", "Monthly"]].map(([k, w]) =>
      h("button", { type: "button", "aria-pressed": String(gran === k), onclick: () => set({ cgran: k }) }, w)));
    const msel = h("select", { "aria-label": "Measure on the chart", onchange: (e) => set({ cm: e.target.value }) }, SERIES.map((k) => h("option", { value: k, selected: k === key }, LABEL[k][0])));
    const tabs = h("nav", { class: "subtabs vs-tabs", "aria-label": "Compare by" }, DIMS.map(([k, w]) =>
      h("button", { type: "button", class: "subtab", "aria-current": k === tab ? "page" : null, onclick: () => set({ cdim: k }) }, w)));
    if (emptySide.length === 2) return body.replaceChildren(empty, h("div", { class: "vs-honest", role: "note" }, notes));
    body.replaceChildren(empty || "",
      notes.length ? h("div", { class: "vs-honest", role: "note" }, notes) : "",
      kpis(res, perDay),
      res.series ? h("section", { class: "s" }, h("div", { class: "card-h start vs-ch" }, h("h2", null, "A against B"),
        h("span", { class: "vs-key" }, h("i", { class: "ka" }), "A", h("i", { class: "kb" }), "B"), h("span", { class: "grow" }), msel, gseg),
        h("div", { class: "sheet" }, chart(res, key, size, perDay)),
        h("p", { class: "note" }, `Day 1 of A is drawn with day 1 of B${size > 1 ? `; each point is ${size} days${perDay ? ", as a typical day" : ", added up"}` : ""}. A day not counted is a gap, never a zero.`)) : "",
      h("section", { class: "s" }, tabs, dimTable(res, tab, perDay)));
  }).catch((e) => body.replaceChildren(h("div", { class: "state bad" }, h("div", null, `The comparison could not be made: ${e.message || e}.`))));
  return [head, bar, body];
}
