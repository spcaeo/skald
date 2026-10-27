// The app's whole state lives in the URL hash, so a link or a reload brings
// back the same section, tab, range and filters:
//   #traffic/sources?range=30d&view=canada-french&device=Mobile
//
// Routes (2.7.0): `<section>/<tab>` for the five sections, whose tabs are
// registered by js/sections.js (addSections) from js/tabs/s-*.js; Settings'
// pages, Help and About are listed here. Older addresses redirect (routes.js).

import { resolve, cmpOf, spanOf } from "./routes.js";
import { TABLE_KEY as GRID_KEY } from "./tablestate.js";
import { OVERLAY, ALWAYS_MASKED, isPersonal } from "./routekeys.js";
import { mask, unmask } from "./routemask.js";
import { SETTINGS_PAGES, SETTINGS_GROUPS, SETTINGS_HOME } from "./settings-menu.js";
export { SETTINGS_HOME };
// Every key, its owner and what it means: js/routekeys.js (and docs/ROUTES.md).

// A table's or a data grid's own keys in the hash (search, sort, column filters, hidden
// columns, page: js/tablestate.js, js/grid.js), e.g. pg_q, eachvisit_cf.

// Every page outside the sections, in the menu's order. The sections' tabs are put in
// front of these by addSections, so TABS is every route, in the menu's order.
// Settings' pages come from js/settings-menu.js (2.40: grouped by what a person comes to do).
export const TABS = [...SETTINGS_PAGES.map((p) => [p.route, p.name]), ["help", "Help"], ["about", "About Skald"]];
// Sections this server does not offer: Team, Your account and the settings pages come with
// accounts (access.mode: sessions), which replace Users; Billing also needs saas (docs/SAAS.md).
// access.js changes the set once /me has answered (and hides what the reader's role may not open).
// Every settings page but To do, Site (its Internal traffic tab), AI assistants (they say how it
// works without accounts), Alerts (its switches say where they are set without accounts) and People (Users: the one shared login's own page). A tab that needs
// accounts on a page that does not is hidden as <route>#<sub> (settings-menu.js tabKey).
const WITHOUT_ACCOUNTS = new Set([SETTINGS_HOME, "settings/site/details", "settings/site/alerts", "settings/ai/assistants", "settings/org/people"]);
const ACCOUNT_SUBS = ["settings/site/details#details", "settings/org/people#security"];
export const ACCOUNT_TABS = [...SETTINGS_PAGES.map((p) => p.route).filter((k) => !WITHOUT_ACCOUNTS.has(k)), ...ACCOUNT_SUBS];
export const HIDDEN = new Set(ACCOUNT_TABS);
export const shown = (key) => !HIDDEN.has(key);

/* The five sections (js/sections.js fills these once, at load):
     SECTIONS  [{key, name, short, tabs: [[route, name]]}], in the menu's order
     MENU      [[section name, [routes]]]: the report builder's and the shortcuts' groups */
export const SECTIONS = [];
export const MENU = [];
const FIRST = {};                                   // section key -> its first tab's route
const KEEP = { help: ["part", "hs", "hq"], about: ["part", "note"], "settings/org/sites": ["test"], "settings/site/leads": ["lt"] };   // route -> parameters it keeps in its address
// A settings page with in-page tabs keeps the tab open (sub=, js/settings-menu.js).
for (const p of SETTINGS_PAGES) if (p.tabs) KEEP[p.route] = ["sub"];
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

// Settings has a menu of its own, which takes the sidebar's place while a settings page is open:
// To do, then the groups of js/settings-menu.js (This site, AI, Organisation, You). Help is in
// the sidebar's foot. (AI crawlers moved to AI & bots > Crawler rules in 2.7.0; its address redirects.)
export const SETTINGS_MENU = [["", [SETTINGS_HOME]], ...SETTINGS_GROUPS.map((g) => [g.name, g.pages.map((p) => p.route)])];
export const inSettings = (key) => key.startsWith("settings/");
// The group a page sits in: its section's name ("Traffic"), its settings group, or null.
export function groupOf(key) {
  const sec = sectionOf(key);
  if (sec) return sec.name;
  for (const [name, keys] of SETTINGS_MENU) if (name && keys.includes(key)) return name;
  return null;
}
// Where #settings lands: To do (what needs this reader now), shown to everyone.
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

// "all" (2.23): All time, from the first day this site has data (data.js rangeOf).
export const RANGES = [["today", "Today"], ["yesterday", "Yesterday"], ["7d", "7 days"], ["30d", "30 days"], ["90d", "90 days"], ["all", "All time"], ["custom", "Custom"]];
export const FILTERS = ["country", "path", "source", "device", "browser", "campaign", "referrer"];
const GLOBAL = ["range", "view", "from", "to", "pathmode", "rules", "cmp", "dd", "tz", "inc"];
// Kept while Compare is on (2.7.0): the custom B, "Per day", the old Compare page's chart keys.
const CMP_KEYS = ["cb", "cnorm", "cgran", "cm"];
const DEFAULT = { tab: "overview/summary", range: "today", view: "all", from: "", to: "", inc: "", pathmode: "contains", rules: "", page: "", since: "", cmp: "", ip: "", rq: "", dd: "", tz: "", part: "", hs: "", hq: "", note: "", fn: "", fsrc: "", fstep: "", fmode: "", strat: "", ca: "", cb: "", cnorm: "", cgran: "", cm: "", cdim: "", pubfrom: "", pubto: "", chgfrom: "", rg: "", rm: "", rs: "", rv: "", test: "", sub: "", lt: "",
  ...Object.fromEntries(OVERLAY.map((k) => [k, ""])) };
/* The period a section opens on when the address names none (2.23). Leads & sales opens on
   the last 7 days: a lead is rare, and Today so far was too often empty (the owner,
   2026-10-22). Every other section opens on Today. An address's own range= always wins.
   s.auto is the period read() or set() filled in as the tab's default, "" when the period
   was named (in the address, or picked): hashFor leaves an auto period out, so the next
   section opens on its own default (Overview's Today is not carried into Leads & sales),
   and writes a named one, which stays from section to section. A period picked that is the
   tab's own default (Today on Overview, 7 days on Leads & sales) counts as the default. */
export const SECTION_RANGE = { sales: "7d" };
export const defaultRange = (tab) => SECTION_RANGE[String(tab || "").split("/")[0]] || DEFAULT.range;
/* Compare is on by default (the UX audit's task 5, 2.42): a period of whole days (Yesterday,
   7, 30 or 90 days, Custom) is set against the period before it unless the address says
   otherwise. Today (live and partial), All time (nothing before it) and a period that
   includes today are never compared, so they default to off. s.cmpAuto: no compare was
   named, so it follows the period (a move to Today drops it, a move back brings it) and
   hashFor leaves it out. Named (picked, or turned off: cmp=off), it is written while it
   differs from the period's default. */
export const defaultCmp = (s) => (!["today", "all"].includes(s.range) && s.inc !== "1" ? "prev" : "");
// Every key read() knows, for the route keys' test (tests/js/routes.mjs).
export const KNOWN = () => [...Object.keys(DEFAULT).filter((k) => k !== "tab"), ...FILTERS];

// The state in the address. `moved`: the address was an older one (or the old compare
// switch), and emit() writes the new one in its place.
export function read() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [asked, q = ""] = raw.split("?");
  const p = new URLSearchParams(q);
  const r = route(asked, p);
  const s = { ...DEFAULT, tab: TABS.some(([k]) => k === r.tab) ? r.tab : DEFAULT.tab };
  // A personal value (an address, an email) is a token in the address (js/routemask.js);
  // an older link that carries one as it is is rewritten with the token.
  let personal = false;
  for (const k of [...Object.keys(DEFAULT), ...FILTERS]) {
    const v = k !== "tab" ? p.get(k) : "";
    if (!v) continue;
    if (isPersonal(v)) personal = true;
    s[k] = unmask(v);
  }
  Object.assign(s, r.patch);
  s.moved = (r.moved || personal) && s.tab === r.tab;
  if (p.get("cmp") === "1") s.moved = true;
  const offed = s.cmp === "off";
  s.cmp = cmpOf(s.cmp);
  // Compare mode (js/mode-compare.js): a custom B needs its period, else the previous one.
  if (s.cmp === "custom" && !spanOf(s.cb)) s.cmp = "prev";
  // No range, or one not known: the section's own (SECTION_RANGE), kept as s.auto (hashFor).
  // Named: the address's own range= (an old address's, #live, only when not the tab's default).
  const own = defaultRange(s.tab), named = r.patch?.range || p.get("range");
  if (!named || !RANGES.some(([k]) => k === s.range)) s.range = own;
  if (s.range === "custom" && !(/^\d{4}-\d\d-\d\d$/.test(s.from) && /^\d{4}-\d\d-\d\d$/.test(s.to))) s.range = own;
  s.auto = s.range !== named || (r.patch?.range && s.range === own) ? s.range : "";
  if (s.pathmode !== "starts") s.pathmode = "contains";
  // Include today (period-dates.js): "1" or nothing; only Summary and Pages honour it.
  if (s.inc !== "1") s.inc = "";
  // No compare named: the period's default (defaultCmp); s.cmpAuto says it follows the period.
  s.cmpAuto = !offed && !s.cmp && !p.get("cmp");
  if (s.cmpAuto) s.cmp = defaultCmp(s);
  // The time zone: the link's, else the one this browser chose last, else the reader's own.
  if (!["local", "site", "utc"].includes(s.tz)) {
    let kept = "";
    try { kept = JSON.parse(localStorage.getItem("ti-tz") || '""'); } catch { /* storage blocked */ }
    s.tz = ["local", "site", "utc"].includes(kept) ? kept : "site";
  }
  return s;
}

export function hashFor(s) {
  const all = new URLSearchParams();
  // Every value goes in through mask(): no address or email is ever in the address.
  const p = { set: (k, v) => all.set(k, mask(v, ALWAYS_MASKED.has(k))), toString: () => all.toString() };
  // The period, unless it was filled in as a default (s.auto; a state built without it: the
  // tab's own default): Overview's Today is not carried into Leads & sales.
  if (s.range !== (s.auto ?? defaultRange(s.tab))) p.set("range", s.range);
  if (s.range === "custom") { p.set("from", s.from); p.set("to", s.to); }
  if (s.view && s.view !== "all") p.set("view", s.view);
  for (const k of FILTERS) if (s[k]) p.set(k, s[k]);
  if (s.path && s.pathmode === "starts") p.set("pathmode", "starts");
  // The advanced filters' rules beyond the single filters above (js/rules.js), on every tab.
  if (s.rules) p.set("rules", s.rules);
  // Compare: written when it differs from the period's default (defaultCmp), "off" for none;
  // a compare filled in as the default (s.cmpAuto) is never written.
  const cmpNow = cmpOf(s.cmp);
  if (!s.cmpAuto && cmpNow !== defaultCmp(s)) p.set("cmp", cmpNow || "off");
  // Compare mode's own keys, on every tab while it is on: the custom B, "Per day".
  if (cmpOf(s.cmp)) for (const k of CMP_KEYS) if (s[k] && (k !== "cb" || s.cmp === "custom")) p.set(k, s[k]);
  if (s.tz && s.tz !== "site") p.set("tz", s.tz);
  // Include today: kept on every tab, so Summary and Pages share it (others ignore it).
  if (s.inc === "1") p.set("inc", "1");
  // What belongs to one tab only (a page's story, the insights' "since", a funnel's
  // steps, the request log's toggles...): the tab's `keep` list, js/tabs/s-*.js.
  for (const k of KEEP[s.tab] || []) if (s[k] && !GLOBAL.includes(k)) p.set(k, s[k]);
  // A grid's own keys stay while the tab stays; another tab starts clean.
  if (typeof location !== "undefined") {
    const [here, query = ""] = location.hash.slice(1).split("?");
    if (here === s.tab) for (const [k, v] of new URLSearchParams(query)) if (GRID_KEY.test(k)) p.set(k, v);
  }
  // A drawer or a dialog open over the tab (js/overlays.js), on its own tab only: a link
  // drawn to another tab (the menu, the tab strip) never carries it. Then the drill-down
  // trail, last: it opens over whichever tab it started from.
  const [at, atQuery = ""] = typeof location !== "undefined" ? location.hash.replace(/^#\/?/, "").split("?") : [s.tab];
  if (at === s.tab || route(at, new URLSearchParams(atQuery)).tab === s.tab) for (const k of OVERLAY) if (s[k]) p.set(k, s[k]);
  if (s.dd) p.set("dd", s.dd);
  const q = p.toString();
  return `#${s.tab}${q ? `?${q}` : ""}`;
}

/* Whether two states differ only in what is open over the tab (a drawer, a dialog, its
   step): main.js then opens or closes it without drawing the tab again. */
export function onlyOverlay(a, b) {
  if (!a || !b) return false;
  for (const k of [...Object.keys(DEFAULT), ...FILTERS]) if (!OVERLAY.includes(k) && (a[k] ?? "") !== (b[k] ?? "")) return false;
  return true;
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
  // A period picked is named (written, carried), unless it is this tab's own default.
  if ("range" in patch) next.auto = next.range === defaultRange(next.tab) ? next.range : "";
  // A compare chosen (or turned off) is named from now on; one left alone follows the period.
  if ("cmp" in patch) next.cmpAuto = false;
  // Going to another tab leaves a drill-down, a drawer and a dialog behind unless the move carries them.
  if (next.tab !== cur.tab) for (const k of ["dd", ...OVERLAY]) if (!(k in patch)) next[k] = "";
  const hash = hashFor(next);
  if (hash === location.hash) return;
  // A change in place keeps the entry's mark (a drill-down's depth, a drawer's), unless it names one.
  if (replace) history.replaceState(mark ?? history.state ?? null, "", hash);
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
