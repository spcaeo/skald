// Compare, worked out in the browser for a server without the compare API:
// the same answer shape as GET <page>/api/compare (DATA-CONTRACT.md), from
// the days this page already holds (180 days). A filter on its own comes from
// the daily breakdowns; country, source and device together from the daily
// cube (90 days); any other mix cannot be split here and says so.

import { addDays } from "../ui.js";
import { daysBetween, pathMatch } from "../data.js";
import * as S from "../state.js";

const LEAD_TYPES = ["signup", "contact", "waitlist", "demo_booked"];
const MARGINAL = ["country", "source", "device", "browser", "campaign", "referrer"];
const CUBE_DIMS = ["country", "source", "device"];
export const METRICS = ["visitors", "pages_read", "visitors_from_ai", "ai_asked", "ai_training", "search", "leads", "returning", "pages_per_visitor", "not_found_people"];
export const SERIES = ["visitors", "pages_read", "visitors_from_ai", "ai_asked", "ai_training", "search", "leads"];

export function filterMode(s) {
  const f = S.activeFilters(s).filter(([k]) => k !== "path");
  if (!f.length) return { kind: "none", f };
  if (f.length === 1 && MARGINAL.includes(f[0][0])) return { kind: "one", f };
  if (f.every(([k]) => CUBE_DIMS.includes(k))) return { kind: "cube", f };
  return { kind: "split", f };
}

// One day's figure; null when this day cannot give it under these filters.
function measure(key, d, ctx) {
  const { mode, path, keep, leads, cube } = ctx;
  if (key === "leads") {
    if (mode.kind !== "none" || path) return null;
    const e = leads?.get(d.day);
    return e ? LEAD_TYPES.reduce((a, t) => a + (e.leads?.[t] || 0), 0) : null;
  }
  if (path) {
    if (key === "pages_read") return d.pages ? Object.entries(d.pages).filter(([p]) => keep(p)).reduce((a, [, v]) => a + v, 0) : null;
    if (key === "ai_asked" || key === "ai_training") return null;
    return null;
  }
  if (mode.kind === "none") {
    switch (key) {
      case "visitors": return d.readers ?? null;
      case "pages_read": return d.views ?? null;
      case "visitors_from_ai": return d.cited ?? null;
      case "ai_asked": return d.tiers?.asked ?? null;
      case "ai_training": return d.tiers?.training ?? null;
      case "search": return d.search ?? null;
      case "returning": return d.returning ? d.returning.returning ?? null : null;
      case "not_found_people": return d.not_found ? Object.values(d.not_found).reduce((a, b) => a + b, 0) : null;
      default: return null;
    }
  }
  if (mode.kind === "one") {
    const [k, v] = mode.f[0];
    if (key === "visitors") return d.by ? d.by[k]?.[v] || 0 : null;
    if (key === "visitors_from_ai" && k === "source") return d.by ? (v === "AI assistant" ? d.by.source?.[v] || 0 : 0) : null;
    return null;
  }
  if (mode.kind === "cube" && cube && (key === "visitors" || key === "visitors_from_ai")) {
    const e = cube.byDay.get(d.day);
    if (!e || e.state !== "ok" || !e.rows) return null;
    return e.rows.reduce((a, row) => (row[0] !== "(all others)" && cube.match(row) && (key === "visitors" || row[cube.at.source] === "AI assistant") ? a + (row[cube.at.visits] || 0) : a), 0);
  }
  return null;
}

const DIM_GET = {
  pages: (d) => d.pages, sources: (d) => d.by?.source, assistants: (d) => d.cited_by, countries: (d) => d.by?.country,
  devices: (d) => d.by?.device, browsers: (d) => d.by?.browser, os: (d) => d.by?.os, campaigns: (d) => d.by?.campaign,
};
const CUBE_COL = { pages: "landing", sources: "source", assistants: "assistant", countries: "country", devices: "device" };

function dim(name, ok, ctx) {
  const out = {};
  if (ctx.mode.kind === "cube" || (ctx.mode.kind === "one" && ctx.cube && CUBE_COL[name] && CUBE_DIMS.includes(ctx.mode.f[0][0]))) {
    if (!ctx.cube || !CUBE_COL[name]) return null;
    const col = ctx.cube.at[CUBE_COL[name]];
    for (const d of ok) {
      const e = ctx.cube.byDay.get(d.day);
      if (!e?.rows) continue;
      for (const row of e.rows) if (row[0] !== "(all others)" && ctx.cube.match(row) && row[col]) out[row[col]] = (out[row[col]] || 0) + (row[ctx.cube.at.visits] || 0);
    }
    return out;
  }
  if (ctx.mode.kind !== "none" || (ctx.path && name !== "pages")) return null;
  let seen = false;
  for (const d of ok) {
    const obj = DIM_GET[name](d);
    if (!obj) continue;
    seen = true;
    for (const [k, v] of Object.entries(obj)) if (name !== "pages" || !ctx.path || ctx.keep(k)) out[k] = (out[k] || 0) + v;
  }
  return seen ? out : null;
}

function range(m, r, ctx) {
  const days = daysBetween(m, r.first, r.last);
  const ok = days.filter((d) => d.state === "ok");
  const sums = {};
  for (const key of METRICS) {
    if (key === "pages_per_visitor") continue;
    const vals = ok.map((d) => measure(key, d, ctx));
    sums[key] = ok.length && vals.every((v) => v != null) ? vals.reduce((a, b) => a + b, 0) : null;
  }
  sums.pages_per_visitor = sums.visitors && sums.pages_read != null ? sums.pages_read / sums.visitors : null;
  const series = days.map((d) => (d.state === "ok" ? Object.fromEntries([["day", d.day], ["state", "ok"], ...SERIES.map((k) => [k, measure(k, d, ctx)])]) : { day: d.day, state: d.state }));
  return { days, ok, sums, series, info: { from: r.first, to: r.last, days: days.length, used: ok.length, excluded: days.filter((d) => d.state !== "ok").map((d) => ({ day: d.day, state: d.state })), unmeasured: [] } };
}

export function cubeCtx(f, filters) {
  if (!f || !Array.isArray(f.dims)) return null;
  const at = Object.fromEntries(f.dims.map((d, i) => [d, i]));
  const want = filters.filter(([k]) => k in at);
  return { at, byDay: new Map((f.days || []).map((d) => [d.day, d])), match: (row) => want.every(([k, v]) => row[at[k]] === v), first: (f.days || [])[0]?.day };
}

// The answer, in the API's shape. delta = a - b: A is looked at, B is what it is compared with.
export function local(m, s, a, b, cube) {
  const mode = filterMode(s);
  const leads = m.x.leads?.days ? new Map(m.x.leads.days.filter((d) => !m.x.leads.since || d.day >= m.x.leads.since).map((d) => [d.day, d])) : null;
  const ctx = { mode, path: s.path || "", keep: pathMatch(s), leads, cube };
  const A = range(m, a, ctx), B = range(m, b, ctx);
  const metrics = METRICS.map((key) => {
    const va = A.sums[key], vb = B.sums[key];
    return { key, a: va, b: vb, delta: va != null && vb != null ? va - vb : null, delta_pct: va != null && vb ? ((va - vb) / vb) * 100 : null };
  });
  const dimensions = {};
  for (const name of Object.keys(DIM_GET)) {
    const da = dim(name, A.ok, ctx), db = dim(name, B.ok, ctx);
    if (!da && !db) { dimensions[name] = null; continue; }
    const keys = [...new Set([...Object.keys(da || {}), ...Object.keys(db || {})])];
    dimensions[name] = keys.map((k) => {
      const va = da?.[k] || 0, vb = db?.[k] || 0;
      return { name: k, a: va, b: vb, delta: va - vb, delta_pct: vb ? ((va - vb) / vb) * 100 : null, new: k !== "(all others)" && va > 0 && !vb, gone: k !== "(all others)" && vb > 0 && !va };
    }).sort((x, y) => y.a - x.a || y.b - x.b);
  }
  dimensions.continents = null;
  const problems = [];
  if (mode.kind === "split") problems.push(`These filters together (${mode.f.map(([k, v]) => `${k} ${v}`).join(", ")}) cannot be split from the days this page holds; keep one, or only country, source and device.`);
  if ((mode.kind === "cube" || mode.kind === "one") && cube?.first && [a.first, b.first].some((d) => d < cube.first)) problems.push(`Tables split by a filter come from the daily cube, which starts on ${cube.first}; earlier days are not in them.`);
  if (ctx.path) problems.push("Here the page filter narrows Pages read and the Pages table only; the page's own visitors, fetches and sources need the server's compare.");
  return { ok: true, local: true, a: A.info, b: B.info, filtered: mode.kind !== "none" || !!ctx.path, metrics, dimensions, series: { a: A.series, b: B.series }, problems,
    presets: { previous: { from: addDays(a.first, -(A.days.length)), to: addDays(a.first, -1) } } };
}
