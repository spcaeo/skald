// The detail view a drill-down opens: one value (or a trail of them), with
// its trend over the chosen range, what the visits behind it did, and the
// recent requests behind it. Every value in here drills further.
//
// Three sources, each named where it is used, because they differ:
//   * history: whole verified days, one breakdown at a time - so a trend
//     exists for a single value, never for two crossed
//   * visits: anonymous journeys of the last few days - they can be crossed
//     (Canada AND /pricing/ AND Google), which is how deeper steps work
//   * requests: the last hours of the raw log - addresses, statuses, bots

import { time as tzTime, label as tzLabel } from "./tz.js";
import { h, n, short, duration, clock } from "./ui.js";
import { rangeOf, chartDays, ranked, base, getJSON, color, GROUPS } from "./data.js";
import { lines, band } from "./charts.js";
import * as S from "./state.js";
import { DIMS, chainOf, encode, label, link } from "./drill.js";
import { blist, panel } from "./tabs/common.js";
import { openDrawer } from "./drawer.js";

const STATUS_CLASS = (code) => (code >= 500 ? "5xx" : code === 404 ? "404" : code >= 400 ? "4xx" : code >= 300 ? "3xx" : "2xx");
const landing = (j) => j.landing || j.trail?.[0]?.path || j.trail?.[0]?.[0] || "";
const trailPaths = (j) => (j.trail || []).map((p) => p.path ?? p[0]);
const campaignName = (j) => (j.campaign || "").split(" / ").pop() || j.utm?.campaign || "";

// Does a visit match a step? undefined: visits do not carry this kind of value.
function visitHas(j, dim, v) {
  switch (dim) {
    case "country": case "device": case "browser": case "os": case "source": return j[dim] === v;
    case "path": return trailPaths(j).includes(v);
    case "landing": return landing(j) === v;
    case "assistant": return j.via === v;
    case "referrer": return j.ref_host === v || j.via === v;
    case "campaign": return j.campaign === v || campaignName(j) === v || j.utm?.campaign === v;
    case "hour": return String(j.start || "").slice(11, 13) === v;
    default: return undefined;
  }
}
function requestHas(r, dim, v) {
  switch (dim) {
    case "country": case "device": case "os": case "ip": case "source": return r[dim] === v;
    case "path": case "landing": return r.path === v;
    case "assistant": return r.assistant === v;
    case "referrer": return r.ref_host === v;
    case "campaign": return r.utm?.campaign === v || [r.utm?.source, r.utm?.medium, r.utm?.campaign].filter(Boolean).join(" / ") === v;
    case "browser": case "bot": return r.agent === v;
    case "hour": return String(r.at || "").slice(11, 13) === v;
    case "status": return String(r.status) === v || STATUS_CLASS(r.status) === v;
    default: return false;
  }
}

/* One value's figure on one stored day, from history; null when that day
   does not keep this kind of value. Only for a single step: history keeps
   each breakdown on its own. */
const BY = ["country", "device", "browser", "os", "source", "referrer", "campaign", "landing", "hour"];
function series(dim, v) {
  const sum = (...xs) => (xs.every((x) => x == null) ? null : xs.reduce((a, x) => a + (x || 0), 0));
  if (BY.includes(dim)) return [{ name: "Visitors", color: color("people"), get: (d) => (d.by ? d.by[dim]?.[v] || 0 : null), area: true }];
  if (dim === "path") return [
    { name: "Page views", color: color("people"), get: (d) => (d.pages ? d.pages[v] || 0 : null), area: true },
    { name: "AI fetches", color: color("answer_engines"), get: (d) => (d.ai_pages ? d.ai_pages[v] || 0 : null) },
    { name: "404s to people", color: "var(--warn)", get: (d) => (d.not_found ? d.not_found[v] || 0 : null) },
  ];
  if (dim === "assistant") return [
    { name: "Visitors it sent", color: color("people"), get: (d) => (d.cited_by ? d.cited_by[v] || 0 : null), area: true },
    { name: "Fetches", color: color("answer_engines"), get: (d) => (d.engines ? sum(d.engines.training?.[v], d.engines.asked?.[v]) || 0 : null) },
  ];
  if (dim === "bot") return [{ name: "Requests", color: color("bots"), get: (d) => (d.bot_agents || d.search_engines || d.engines
    ? sum(d.bot_agents?.[v], d.search_engines?.[v], d.engines?.training?.[v], d.engines?.asked?.[v]) || 0 : null), area: true }];
  if (dim === "status") return [{ name: "Responses", color: "var(--warn)", get: (d) => (d.statuses ? Object.values(d.statuses).reduce((a, g) => a + (g[/x|^404$/.test(v) ? v : STATUS_CLASS(Number(v))] || 0), 0) : null), area: true }];
  return null;
}

function crumbs(m, s, chain) {
  const tab = (S.TABS.find(([k]) => k === s.tab) || [null, s.tab])[1];
  const nav = h("nav", { class: "crumbs", "aria-label": "Drill-down trail" },
    h("ol", null, h("li", null, h("button", { type: "button", class: "crumb", onclick: () => S.set({ dd: "" }) }, tab)),
      chain.map(([d, v], i) => h("li", null, i === chain.length - 1
        ? h("span", { class: "crumb now", "aria-current": "page" }, `${DIMS[d].name}: `, label(d, v))
        : h("button", { type: "button", class: "crumb", onclick: () => S.set({ dd: encode(chain.slice(0, i + 1)) }) }, `${DIMS[d].name}: ${DIMS[d].say(v)}`)))));
  return nav;
}

// Lists from a set of visits, each value drilling one step further.
function visitLists(js, chain) {
  const has = new Set(chain.map(([d]) => d));
  const count = (get) => { const o = {}; for (const j of js) for (const k of [].concat(get(j))) if (k) o[k] = (o[k] || 0) + 1; return o; };
  const lists = [
    ["path", "Pages they read", (j) => [...new Set(trailPaths(j))]],
    ["landing", "Where they landed", landing],
    ["source", "Sources", (j) => j.source],
    ["assistant", "AI assistants that sent them", (j) => (j.source === "AI assistant" ? j.via : "")],
    ["referrer", "Referring sites", (j) => j.ref_host || (j.source === "Other website" ? j.via : "")],
    ["campaign", "Campaigns", campaignName],
    ["country", "Countries", (j) => j.country],
    ["device", "Devices", (j) => j.device],
    ["browser", "Browsers", (j) => j.browser],
    ["os", "Systems", (j) => j.os],
    ["hour", "Hour they started", (j) => String(j.start || "").slice(11, 13)],
  ].filter(([d]) => !has.has(d));
  return h("div", { class: "cols three" }, lists.map(([d, title, get]) => {
    const rows = ranked(count(get));
    return rows.length ? panel(title, null, blist(rows, { drill: d, from: "drill", limit: 6, color: d === "path" || d === "landing" ? "var(--views)" : "var(--g-people)" })) : null;
  }));
}

function visitList(js) {
  return h("ul", { class: "stream dd-visits" }, js.slice(0, 15).map((j) => h("li", null,
    h("span", { class: "s-t" }, tzTime(j.start, { date: true, label: false })),
    h("span", { class: "s-d", style: { background: color("people") }, "aria-hidden": "true" }),
    h("span", { class: "s-w" }, label("country", j.country), ` ${[j.device, j.browser].filter((x) => x && x !== "Other").join(", ")}, ${j.source}${j.via ? ` (${j.via})` : ""}: ${n(j.pages)} page${j.pages === 1 ? "" : "s"}, ${duration(j.seconds)}`,
      h("small", null, trailPaths(j).join("  >  "))))));
}

function requestPart(m, s, chain, holder) {
  holder.replaceChildren(h("p", { class: "empty" }, "Loading the recent requests…"));
  if (Array.isArray(m.files) && !m.files.includes("requests")) { holder.replaceChildren(h("p", { class: "empty" }, "The recent request log is not written beside this page yet.")); return; }
  getJSON(`${base(s.view)}requests.json`).then((f) => {
    const rows = (f?.rows || []).filter((r) => chain.every(([d, v]) => requestHas(r, d, v)));
    if (!rows.length) { holder.replaceChildren(h("p", { class: "empty" }, `No request in the last ${f?.window_hours || "few"} hours matches.`)); return; }
    const by = {};
    for (const r of rows) by[r.group] = (by[r.group] || 0) + 1;
    const parts = [...GROUPS, ["excluded", "Other hosts"]].map(([g, name]) => ({ g, name, value: by[g] || 0, color: color(g) })).filter((x) => x.value);
    const count = (get) => { const o = {}; for (const r of rows) { const k = get(r); if (k) o[k] = (o[k] || 0) + 1; } return ranked(o); };
    const has = new Set(chain.map(([d]) => d));
    const lists = [["status", "Statuses", (r) => String(r.status)], ["path", "Paths", (r) => r.path], ["ip", "Addresses", (r) => (r.ip !== "(removed)" ? r.ip : "")],
      ["bot", "Agents", (r) => (r.group !== "people" && r.group !== "ours" ? r.agent : "")], ["country", "Countries", (r) => r.country]].filter(([d]) => !has.has(d));
    const toTab = { ip: "ip", path: "path", country: "country", device: "device", browser: "browser", referrer: "referrer", campaign: "campaign", source: "source" };
    const patch = { tab: "requests", dd: "", ...Object.fromEntries(chain.filter(([d]) => toTab[d]).map(([d, v]) => [toTab[d], v])) };
    holder.replaceChildren(
      h("p", { class: "sub" }, `${n(rows.length)} of the ${n(f.rows.length)} requests kept from ${tzTime(f.from, { label: false })} to ${tzTime(f.until)}.`),
      band(parts, rows.length, false),
      h("ul", { class: "legend", style: { marginTop: "8px" } }, parts.map((x) => h("li", null, h("span", { class: "sw", style: { background: x.color } }), `${x.name} ${n(x.value)}`))),
      h("div", { class: "cols three", style: { marginTop: "14px" } }, lists.map(([d, title, get]) => { const r = count(get); return r.length ? panel(title, null, blist(r, { drill: d, from: "drill", limit: 6, color: "var(--g-bots)" })) : null; })),
      h("ul", { class: "stream" }, rows.slice(0, 12).map((r) => h("li", null, h("span", { class: "s-t" }, tzTime(r.at, { seconds: true, label: false })),
        h("span", { class: "s-d", style: { background: color(r.group) }, "aria-hidden": "true" }),
        h("span", { class: "s-w" }, `${r.status} ${r.method || ""} `, link("path", r.path, { from: "drill" }), ` ${r.rule}`,
          h("small", null, r.ip && r.ip !== "(removed)" ? link("ip", r.ip, { from: "drill" }) : "", r.country ? ` ${r.country}` : ""))))),
      h("button", { type: "button", class: "btn", onclick: () => S.set(patch) }, "Open these in the Requests tab"));
  }).catch((e) => holder.replaceChildren(h("p", { class: "empty" }, `The recent requests could not be loaded: ${e.message || e}.`)));
}

/* The daily cube (cube.json): visits per day by country, landing page,
   source, assistant and device - crossed, for 90 days. A trail made only of
   those five gets its trend and lists over the whole period from here. */
const CUBE = ["country", "landing", "source", "assistant", "device"];
const CUBE_NAMES = { country: "Countries", landing: "Where they landed", source: "Sources", assistant: "AI assistants that sent them", device: "Devices" };
function cubePart(m, s, chain, r, holder) {
  if (!chain.every(([d]) => CUBE.includes(d))) return false;
  if (Array.isArray(m.files) && !m.files.includes("cube")) return false;
  holder.replaceChildren(h("p", { class: "empty" }, "Loading the period's visits…"));
  getJSON(`${base(s.view)}cube.json`).then((f) => {
    if (!f || !Array.isArray(f.dims)) { holder.replaceChildren(h("p", { class: "empty" }, "The period's crossed figures are not written beside this page yet.")); return; }
    const at = Object.fromEntries(f.dims.map((d, i) => [d, i]));
    const match = (row) => chain.every(([d, v]) => row[at[d]] === v);
    const byDay = new Map((f.days || []).map((d) => [d.day, d]));
    const days = r.kind === "today" ? (f.today?.rows ? [{ ...f.today, day: m.today, state: "ok" }] : [])
      : chartDays(r).map((d) => { const e = byDay.get(d.day); return e && e.state === "ok" && e.rows ? e : { day: d.day, state: d.state === "before" ? "before" : "missing" }; });
    const counted = days.filter((d) => d.rows);
    if (!counted.length) { holder.replaceChildren(h("p", { class: "empty" }, "No whole day of this period is in the cube yet.")); return; }
    let folded = 0, total = 0;
    const lists = Object.fromEntries(CUBE.map((d) => [d, {}]));
    for (const d of counted) for (const row of d.rows) {
      const v = row[at.visits] || 0;
      if (row[0] === "(all others)") { folded += v; continue; }
      if (!match(row)) continue;
      total += v;
      for (const dim of CUBE) { const k = row[at[dim]]; if (k) lists[dim][k] = (lists[dim][k] || 0) + v; }
    }
    const has = new Set(chain.map(([d]) => d));
    const per = days.map((d) => (d.rows ? { ...d, v: d.rows.filter((row) => row[0] !== "(all others)" && match(row)).reduce((a, row) => a + (row[at.visits] || 0), 0) } : d));
    holder.replaceChildren(...[
      h("div", { class: "dd-kpis" }, h("div", null, h("b", null, n(total)), h("span", null, r.kind === "today" ? "visits today so far" : `visits over ${counted.length} whole day${counted.length === 1 ? "" : "s"}`)),
        folded ? h("div", null, h("b", null, n(folded)), h("span", null, "more could not be sliced (a busy day's long tail)")) : null),
      chain.length > 1 && per.length > 1 ? h("div", { class: "sheet" }, lines(per, [{ name: "Visits", color: color("people"), get: (d) => d.v ?? null, area: true }], { label: "Visits per day", H: 150, width: chartWidth() })) : null,
      h("div", { class: "cols three", style: { marginTop: "12px" } }, CUBE.filter((d) => !has.has(d)).map((d) => {
        const rows = ranked(lists[d]);
        return rows.length ? panel(CUBE_NAMES[d], null, blist(rows, { drill: d, from: "drill", limit: 6, color: d === "landing" ? "var(--views)" : "var(--g-people)" })) : null;
      }))].filter(Boolean));
  }).catch((e) => holder.replaceChildren(h("p", { class: "empty" }, `The period's crossed figures could not be loaded: ${e.message || e}.`)));
  return true;
}

// The charts are drawn for the drawer's width (drawer.css: 80% of the screen, capped; the whole width on a phone).
const chartWidth = () => (innerWidth < 640 ? innerWidth - 32 : Math.min(innerWidth * 0.8, 1360) - 56) - 30;

let wasOpen = false;
export function drillView(m, s) {
  const chain = chainOf(s);
  if (!chain.length) { wasOpen = false; return null; }
  const [dim, value] = chain[chain.length - 1];
  const r = rangeOf(m, s);
  const body = document.createDocumentFragment();
  const back = h("button", { type: "button", class: "btn", html: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3.5L5.5 8l4.5 4.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' }, "Back");
  back.addEventListener("click", () => S.set({ dd: encode(chain.slice(0, -1)) }));
  // ---- trend, from history (one step only)
  const ser = chain.length === 1 ? series(dim, value) : null;
  if (ser && r.kind === "history") {
    const days = chartDays(r);
    const totals = ser.map((x) => days.reduce((a, d) => a + (d.state === "ok" ? x.get(d) || 0 : 0), 0));
    body.append(h("section", { class: "s" }, h("h3", null, `Per day, ${short(r.first)} to ${short(r.last)}`),
      h("div", { class: "dd-kpis" }, ser.map((x, i) => h("div", null, h("b", null, n(totals[i])), h("span", null, x.name)))),
      h("div", { class: "sheet" }, lines(days, ser, { label: `${DIMS[dim].name} ${value} per day`, H: 170, width: chartWidth() })),
      h("p", { class: "note" }, "From whole, verified days. Each day keeps its longest lists in full and folds the tail, so a rare value can read 0 on a day it was in the tail.")));
  } else if (ser && r.kind === "today" && m.live?.state === "ok") {
    const t = m.live.figures;
    body.append(h("div", { class: "dd-kpis" }, ser.map((x) => h("div", null, h("b", null, n(x.get(t))), h("span", null, `${x.name}, today so far`)))));
  }

  // ---- the whole period, crossed, from the daily cube
  const cube = h("div");
  const cubeSec = h("section", { class: "s" }, h("h3", null, `Over the period: ${r.kind === "today" ? "today so far" : `${short(r.first)} to ${short(r.last)}`}`),
    h("p", { class: "sub" }, `Visits by country, landing page, source, assistant and device, crossed, ${r.kind === "today" ? "today so far" : "from the whole days of the period"}.`), cube);
  if (cubePart(m, s, chain, r, cube)) body.append(cubeSec);
  else if (chain.length > 1) body.append(h("p", { class: "note" }, "History keeps most breakdowns on their own, so this trail is shown from the recent visits below."));

  // ---- visits (anonymous journeys), which can be crossed
  const applies = chain.map(([d, v]) => visitHas({}, d, v) !== undefined).every(Boolean);
  const vs = h("section", { class: "s" }, h("h3", null, "The visits behind it"));
  if (!applies) vs.append(h("p", { class: "empty" }, "Visits are anonymous: they carry no address, status or bot name. The requests below show those."));
  else {
    const js = (m.journeys || []).filter((j) => chain.every(([d, v]) => visitHas(j, d, v))).sort((a, b) => String(b.start).localeCompare(String(a.start)));
    if (!js.length) vs.append(h("p", { class: "empty" }, `No visit in the last ${m.journey_days || 7} days matches.`));
    else {
      const secs = js.map((j) => j.seconds).filter((x) => x != null).sort((a, b) => a - b);
      vs.append(h("p", { class: "sub" }, `${n(js.length)} visit${js.length === 1 ? "" : "s"} in the last ${m.journey_days || 7} days (anonymous; kept that long, then deleted).`),
        h("div", { class: "dd-kpis" },
          h("div", null, h("b", null, n(js.length)), h("span", null, "visits")),
          h("div", null, h("b", null, (js.reduce((a, j) => a + (j.pages || 0), 0) / js.length).toFixed(1)), h("span", null, "pages per visit")),
          h("div", null, h("b", null, secs.length ? duration(secs[Math.floor(secs.length / 2)]) : "-"), h("span", null, "median length"))),
        visitLists(js, chain), h("h3", { style: { marginTop: "6px" } }, "Latest visits"), visitList(js));
    }
  }
  body.append(vs);

  // ---- requests, the last few hours of the raw log
  const rq = h("div");
  body.append(h("section", { class: "s" }, h("h3", null, "Recent requests behind it"), rq));
  requestPart(m, s, chain, rq);
  const d = openDrawer({
    title: label(dim, value), head: [back, crumbs(m, s, chain)], className: "dd", key: "drill", scope: "page", still: wasOpen,
    subtitle: chain.length > 1 ? `${chain.map(([d, v]) => `${DIMS[d].name.toLowerCase()} ${DIMS[d].say(v)}`).join(", and ")}. Select any value below to narrow further.`
      : `${DIMS[dim].name}. Select any value below to narrow further.`,
    body, onClose: () => { wasOpen = false; if (S.read().dd) S.set({ dd: "" }); },
  });
  wasOpen = true;
  return d.el;
}

