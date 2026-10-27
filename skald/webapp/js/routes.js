// Old addresses and where they open now (2.7.0, the five sections). No DOM
// here, so tests/test_routes.py runs it in node. state.js read() and set()
// pass every address through resolve(); the shell then rewrites the address
// bar with history.replaceState, so Back never lands on the old address and
// loops. Bookmarks, saved views and links in help, mails and insights keep
// working. The map: docs/plans/2026-10-12-ui-consolidation-map.md, section 5.
//
// Each row: old route -> [new route, parameters it sets]. The old route's own
// parameters (ip, rq, page, fn, strat...) are kept by the new tab when it
// keeps them (its `keep` list in js/tabs/s-*.js).

import { OLD_SETTINGS, CONNECTIONS, connectionsHome } from "./settings-menu.js";

export const REDIRECTS = {
  // Overview
  overview: ["overview/summary"], home: ["overview/summary"],
  insights: ["overview/insights"],
  // Live and Compare are global modes (js/modes.js): Live is the period Today, on
  // Overview; the old Compare page opens the tab that holds its table (fromCompare).
  live: ["overview/summary", { range: "today", cmp: "" }],
  compare: ["overview/summary", { cmp: "prev" }],
  // Traffic
  visitors: ["traffic/visitors"], visits: ["traffic/visitors"],
  sources: ["traffic/sources"],
  pages: ["traffic/pages"],
  locations: ["traffic/places"], audience: ["traffic/places"],
  time: ["traffic/time"], hours: ["traffic/time"],
  // Leads & sales: each old page opens the figures it showed
  leads: ["sales/summary", { lsrc: "db" }],
  conversions: ["sales/summary", { lsrc: "all" }],
  // 2.20: Pipeline became Summary (the figures) and Sources (where from); Leads lists them.
  "sales/pipeline": ["sales/summary"],
  funnels: ["sales/funnels"],
  events: ["sales/events"],
  // AI & bots
  bots: ["ai/assistants"], crawlers: ["ai/assistants"],
  "settings/crawlers": ["ai/rules"],
  // Site
  health: ["site/health"],
  "health/alerts": ["site/alerts"], alerts: ["site/alerts"],
  requests: ["site/requests"],
  "health/broken": ["site/notfound"], broken: ["site/notfound"],
  "health/speed": ["site/speed"], speed: ["site/speed"],
  "health/quality": ["site/quality"], quality: ["site/quality"],
  // Settings' pages before 2.40 and their short names: js/settings-menu.js (OLD_SETTINGS; the
  // old Connections page by the dialog it named, connectionsHome). Help's short names:
  ...OLD_SETTINGS,
  guides: ["help"], docs: ["help"],
};

// The compare switch was "1"; it is "prev" (the previous period) now.
const CMP = new Set(["prev", "year", "custom"]);
export function cmpOf(v) {
  if (!v) return "";
  if (v === "1") return "prev";
  return CMP.has(v) ? v : "";
}
// (2.7.0) "year": the same period 52 weeks earlier; "custom": the period in `cb`.

// A period written "2026-08-01..2026-08-31": the old Compare page's ca and cb, and cb now.
export function spanOf(v) {
  const m = /^(\d{4}-\d\d-\d\d)\.\.(\d{4}-\d\d-\d\d)$/.exec(v || "");
  return m && m[1] <= m[2] ? { first: m[1], last: m[2] } : null;
}
const shift = (iso, k) => { const d = new Date(`${iso}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + k); return d.toISOString().slice(0, 10); };
const span = (x) => Math.round((Date.parse(`${x.last}T00:00:00Z`) - Date.parse(`${x.first}T00:00:00Z`)) / 864e5) + 1;

/* The old Compare page (#compare?ca&cb&cdim...) opens the tab holding the table it
   showed (cdim), A as the period and Compare on: B the previous period, the same
   period a year earlier, or the custom B. "Per day" and the chart's keys ride along. */
const CDIM = { pages: "traffic/pages", sources: "traffic/sources", campaigns: "traffic/sources", assistants: "traffic/sources",
  countries: "traffic/places", continents: "traffic/places", devices: "traffic/places", browsers: "traffic/places", os: "traffic/places" };
function fromCompare(p) {
  const patch = { cmp: "prev", ca: "", cb: "", cdim: "" };
  for (const k of ["cnorm", "cgran", "cm"]) if (p.get(k)) patch[k] = p.get(k);
  const a = spanOf(p.get("ca")), b = spanOf(p.get("cb"));
  if (a) Object.assign(patch, { range: "custom", from: a.first, to: a.last });
  if (b) {
    const prev = a && b.last === shift(a.first, -1) && span(a) === span(b);
    const year = a && b.first === shift(a.first, -364) && b.last === shift(a.last, -364);
    if (year) patch.cmp = "year";
    else if (!prev) Object.assign(patch, { cmp: "custom", cb: `${b.first}..${b.last}` });
  }
  return { tab: CDIM[p.get("cdim")] || "overview/summary", patch, moved: true };
}

/* Where an address opens. asked: the route ("sources", "traffic",
   "traffic/sources"); first: a section's key -> its first tab's route (from
   the registry, js/sections.js); params: the address's parameters, if any (the
   old Compare page's choose its tab). Returns {tab, patch, moved}: the route to
   open, the parameters the redirect sets, and whether the address changed. */
export function resolve(asked, first = {}, params = null) {
  const key = String(asked || "").replace(/^\/+|\/+$/g, "");
  if (key === "compare" && params) return fromCompare(params);
  // The old Connections page (#settings/api): the page of the dialog it named (2.40).
  if (CONNECTIONS.has(key)) { const [tab, patch] = connectionsHome(params); return { tab, patch: { ...(patch || {}) }, moved: true }; }
  // Leads & tools had tabs (sub=) until Settings v2: Search Console and the outgoing webhooks
  // open in their drawer (tool=), the others are the page itself.
  if (key === "settings/site/leads" && params?.get?.("sub")) {
    const sub = params.get("sub");
    return { tab: key, patch: { sub: "", ...(["search", "webhooks"].includes(sub) ? { tool: sub } : {}) }, moved: true };
  }
  // Settings v2: Site › Alerts' switches (alerts_view=switches) are a settings page now.
  if (key === "site/alerts" && params?.get?.("alerts_view") === "switches") return { tab: "settings/site/alerts", patch: { alerts_view: "" }, moved: true };
  // 2.41: Revenue's breakdown was by=, now rby= (by is "Who will do it?", ui/who.js): an old link keeps its breakdown.
  const oldBy = key === "sales/revenue" ? params?.get?.("by") || "" : "";
  if (oldBy && !["me", "dev", "agent"].includes(oldBy)) return { tab: key, patch: { by: "", rby: oldBy }, moved: true };
  const row = REDIRECTS[key];
  if (row) return { tab: row[0], patch: { ...(row[1] || {}) }, moved: true };
  if (first[key]) return { tab: first[key], patch: {}, moved: true };
  return { tab: key, patch: {}, moved: false };
}
