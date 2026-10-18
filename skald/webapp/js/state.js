// The app's whole state lives in the URL hash, so a link or a reload brings
// back the same section, tab, range and filters:
//   #traffic/sources?range=30d&view=canada-french&device=Mobile
//
// Routes (2.7.0): `<section>/<tab>` for the five sections, whose tabs are
// registered by js/sections.js (addSections) from js/tabs/s-*.js; Settings'
// pages, Help and About are listed here. Older addresses redirect (routes.js).

import { resolve, cmpOf, spanOf } from "./routes.js";
import { TABLE_KEY as GRID_KEY } from "./tablestate.js";

// A table's or a data grid's own keys in the hash (search, sort, column filters, hidden
// columns, page: js/tablestate.js, js/grid.js), e.g. pg_q, eachvisit_cf.

// Every page outside the sections, in the menu's order. The sections' tabs are put in
// front of these by addSections, so TABS is every route, in the menu's order.
export const TABS = [
  ["settings/account", "Your account"], ["settings/team", "Team"], ["settings/users", "Users"], ["settings/api", "API & tokens"],
  ["settings/sites", "Sites"], ["settings/internal", "Internal traffic"], ["settings/retention", "Data retention"], ["settings/mail", "Mail"], ["settings/reports", "Reports"], ["settings/integrations", "Integrations"],
  ["settings/sitesadmin", "Add or remove sites"], ["settings/security", "Security"], ["settings/audit", "Audit log"], ["settings/billing", "Billing"], ["help", "Help"], ["about", "About Skald"],
];
// Sections this server does not offer: Team, Your account and the settings pages come with
// accounts (access.mode: sessions), which replace Users; Billing also needs saas (docs/SAAS.md).
// access.js changes the set once /me has answered (and hides what the reader's role may not open).
export const ACCOUNT_TABS = ["settings/team", "settings/account", "settings/retention", "settings/mail", "settings/reports", "settings/sites", "settings/sitesadmin", "settings/integrations", "settings/security", "settings/audit", "settings/billing"];
export const HIDDEN = new Set(ACCOUNT_TABS);
export const shown = (key) => !HIDDEN.has(key);

/* The five sections (js/sections.js fills these once, at load):
     SECTIONS  [{key, name, short, tabs: [[route, name]]}], in the menu's order
     MENU      [[section name, [routes]]]: the report builder's and the shortcuts' groups */
export const SECTIONS = [];
export const MENU = [];
const FIRST = {};                                   // section key -> its first tab's route
const KEEP = { help: ["part"], about: ["part", "note"] };   // route -> parameters it keeps in its address
export function addSections(list) {
  for (const sec of list) {
    const tabs = sec.tabs.map((t) => [t.route, t.name]);
    SECTIONS.push({ key: sec.key, name: sec.name, short: sec.short || sec.name, tabs });
    MENU.push([sec.name, tabs.map(([k]) => k)]);
    FIRST[sec.key] = tabs[0][0];
    for (const t of sec.tabs) {
      KEEP[t.route] = t.keep || [];
      for (const k of KEEP[t.route]) if (!(k in DEFAULT)) DEFAULT[k] = "";
    }
  }
  TABS.unshift(...SECTIONS.flatMap((x) => x.tabs));
}
// The section a route sits in, or null (Settings, Help, About).
export const sectionOf = (key) => SECTIONS.find((x) => String(key).split("/")[0] === x.key) || null;

// Settings has a menu of its own, which takes the sidebar's place while a settings page is open.
// (AI crawlers moved to AI & bots > Crawler rules in 2.7.0; its address redirects.)
export const SETTINGS_MENU = [
  ["You", ["settings/account"]],
  ["Team & access", ["settings/team", "settings/users", "settings/api"]],
  ["This site", ["settings/sites", "settings/internal", "settings/retention", "settings/mail", "settings/reports", "settings/integrations"]],
  ["Organisation", ["settings/sitesadmin", "settings/security", "settings/audit", "settings/billing"]],
];
export const inSettings = (key) => key.startsWith("settings/");
// The group a page sits in: its section's name ("Traffic"), its settings group, or null.
export function groupOf(key) {
  const sec = sectionOf(key);
  if (sec) return sec.name;
  for (const [name, keys] of SETTINGS_MENU) if (keys.includes(key)) return name;
  return null;
}
// The first settings page this reader may open: where #settings lands.
export const firstSetting = () => SETTINGS_MENU.flatMap(([, keys]) => keys).find(shown) || "about";

// Where an asked-for route opens: #settings opens the first settings page this reader may see;
// an old address its new tab (routes.js); a bare section its first tab.
export function route(asked, params = null) {
  if (asked === "settings") return { tab: firstSetting(), patch: {}, moved: true };
  return resolve(asked, FIRST, params);
}
// A page's name, from its route or an older one: "Sources", "Settings".
export function nameOf(key) {
  if (key === "settings") return "Settings";
  const sec = SECTIONS.find((x) => x.key === key);
  if (sec) return sec.name;
  const t = route(key).tab;
  return (TABS.find(([k]) => k === t) || [null, key])[1];
}

export const RANGES = [["today", "Today"], ["yesterday", "Yesterday"], ["7d", "7 days"], ["30d", "30 days"], ["90d", "90 days"], ["custom", "Custom"]];
export const FILTERS = ["country", "path", "source", "device", "browser", "campaign", "referrer"];
const GLOBAL = ["range", "view", "from", "to", "pathmode", "rules", "cmp", "dd", "tz"];
// Kept while Compare is on (2.7.0): the custom B, "Per day", the old Compare page's chart keys.
const CMP_KEYS = ["cb", "cnorm", "cgran", "cm"];
const DEFAULT = { tab: "overview/summary", range: "today", view: "all", from: "", to: "", pathmode: "contains", rules: "", page: "", since: "", cmp: "", ip: "", rq: "", dd: "", tz: "", part: "", note: "", fn: "", fsrc: "", fstep: "", fmode: "", strat: "", ca: "", cb: "", cnorm: "", cgran: "", cm: "", cdim: "", pubfrom: "", pubto: "", rg: "", rm: "", rs: "", rv: "" };

// The state in the address. `moved`: the address was an older one (or the old compare
// switch), and emit() writes the new one in its place.
export function read() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [asked, q = ""] = raw.split("?");
  const p = new URLSearchParams(q);
  const r = route(asked, p);
  const s = { ...DEFAULT, tab: TABS.some(([k]) => k === r.tab) ? r.tab : DEFAULT.tab };
  for (const k of [...Object.keys(DEFAULT), ...FILTERS]) if (k !== "tab" && p.get(k)) s[k] = p.get(k);
  Object.assign(s, r.patch);
  s.moved = r.moved && s.tab === r.tab;
  if (p.get("cmp") === "1") s.moved = true;
  s.cmp = cmpOf(s.cmp);
  // Compare mode (js/mode-compare.js): a custom B needs its period, else the previous one.
  if (s.cmp === "custom" && !spanOf(s.cb)) s.cmp = "prev";
  if (!RANGES.some(([k]) => k === s.range)) s.range = DEFAULT.range;
  if (s.range === "custom" && !(/^\d{4}-\d\d-\d\d$/.test(s.from) && /^\d{4}-\d\d-\d\d$/.test(s.to))) s.range = DEFAULT.range;
  if (s.pathmode !== "starts") s.pathmode = "contains";
  // The time zone: the link's, else the one this browser chose last, else the reader's own.
  if (!["local", "site", "utc"].includes(s.tz)) {
    let kept = "";
    try { kept = JSON.parse(localStorage.getItem("ti-tz") || '""'); } catch { /* storage blocked */ }
    s.tz = ["local", "site", "utc"].includes(kept) ? kept : "site";
  }
  return s;
}

export function hashFor(s) {
  const p = new URLSearchParams();
  if (s.range !== DEFAULT.range) p.set("range", s.range);
  if (s.range === "custom") { p.set("from", s.from); p.set("to", s.to); }
  if (s.view && s.view !== "all") p.set("view", s.view);
  for (const k of FILTERS) if (s[k]) p.set(k, s[k]);
  if (s.path && s.pathmode === "starts") p.set("pathmode", "starts");
  // The advanced filters' rules beyond the single filters above (js/rules.js), on every tab.
  if (s.rules) p.set("rules", s.rules);
  if (cmpOf(s.cmp)) p.set("cmp", cmpOf(s.cmp));
  // Compare mode's own keys, on every tab while it is on: the custom B, "Per day".
  if (cmpOf(s.cmp)) for (const k of CMP_KEYS) if (s[k] && (k !== "cb" || s.cmp === "custom")) p.set(k, s[k]);
  if (s.tz && s.tz !== "site") p.set("tz", s.tz);
  // What belongs to one tab only (a page's story, the insights' "since", a funnel's
  // steps, the request log's toggles...): the tab's `keep` list, js/tabs/s-*.js.
  for (const k of KEEP[s.tab] || []) if (s[k] && !GLOBAL.includes(k)) p.set(k, s[k]);
  // A grid's own keys stay while the tab stays; another tab starts clean.
  if (typeof location !== "undefined") {
    const [here, query = ""] = location.hash.slice(1).split("?");
    if (here === s.tab) for (const [k, v] of new URLSearchParams(query)) if (GRID_KEY.test(k)) p.set(k, v);
  }
  // The drill-down trail, last: it opens over whichever tab it started from.
  if (s.dd) p.set("dd", s.dd);
  const q = p.toString();
  return `#${s.tab}${q ? `?${q}` : ""}`;
}

const listeners = new Set();
export function on(fn) { listeners.add(fn); }

// Move to another state. A tab may be named by any route: an old one, a bare section.
// mark: kept with the history entry (history.state), e.g. how many drill-down steps
// deep it is, so closing the drawer can step Back out of them (drill.js).
export function set(patch, { replace = false, mark = null } = {}) {
  const cur = read();
  const next = { ...cur, ...patch };
  if (patch.tab) { const r = route(patch.tab); Object.assign(next, r.patch, { tab: r.tab }); }
  // Going to another tab leaves a drill-down behind unless the move carries one.
  if (next.tab !== cur.tab && !("dd" in patch)) next.dd = "";
  const hash = hashFor(next);
  if (hash === location.hash) return;
  if (replace) history.replaceState(mark, "", hash);
  else history.pushState(mark, "", hash);
  emit();
}

let last = null;
export function emit(force = false) {
  const s = read();
  // An older address: the new one takes its place in the history, so Back does not loop.
  if (s.moved) {
    const hash = hashFor(s);
    if (hash !== location.hash) history.replaceState(null, "", hash);
  }
  if (!force && location.hash === last) return;
  last = location.hash;
  listeners.forEach((fn) => fn(s));
}
addEventListener("hashchange", () => emit());
addEventListener("popstate", () => emit());

export function activeFilters(s) {
  return FILTERS.filter((k) => s[k]).map((k) => [k, s[k]]);
}
