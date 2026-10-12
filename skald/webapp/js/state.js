// The app's whole state lives in the URL hash, so a link or a reload brings
// back the same tab, range and filters:  #sources?range=30d&view=canada-french&device=Mobile

// Every page, in the menu's order (MENU and SETTINGS_MENU below say how it is grouped).
export const TABS = [
  ["overview", "Overview"], ["live", "Live"], ["insights", "Insights"], ["compare", "Compare"],
  ["visitors", "Visitors"], ["sources", "Sources"], ["pages", "Pages"], ["locations", "Locations & devices"], ["time", "Time of day"],
  ["leads", "Leads"], ["conversions", "Conversions"], ["funnels", "Funnels"], ["events", "Events"],
  ["bots", "AI & crawlers"],
  ["health", "Site health"], ["health/alerts", "Alerts"], ["health/quality", "Data quality"], ["health/speed", "Page speed"], ["health/broken", "Broken links"], ["requests", "Requests"],
  ["settings/account", "Your account"], ["settings/team", "Team"], ["settings/users", "Users"], ["settings/api", "API & tokens"],
  ["settings/sites", "Sites"], ["settings/internal", "Internal traffic"], ["settings/crawlers", "AI crawlers"], ["settings/retention", "Data retention"], ["settings/mail", "Mail"], ["settings/integrations", "Integrations"],
  ["settings/sitesadmin", "Add or remove sites"], ["settings/security", "Security"], ["settings/audit", "Audit log"], ["settings/billing", "Billing"], ["help", "Help"], ["about", "About Skald"],
];
// Sections this server does not offer: Team, Your account and the settings pages come with
// accounts (access.mode: sessions), which replace Users; Billing also needs saas (docs/SAAS.md).
// access.js changes the set once /me has answered (and hides what the reader's role may not open).
export const ACCOUNT_TABS = ["settings/team", "settings/account", "settings/retention", "settings/mail", "settings/sites", "settings/sitesadmin", "settings/integrations", "settings/security", "settings/audit", "settings/billing"];
export const HIDDEN = new Set(ACCOUNT_TABS);
export const shown = (key) => !HIDDEN.has(key);

/* The menu, by what the reader came to find out. The first group has no heading:
   it is where every visit starts (screen readers hear "Home"). A page with
   sub-pages (Site health) shows them as tabs on the page, and in the phone's menu. */
export const MENU = [
  ["Home", ["overview", "live", "insights", "compare"]],
  ["Audience", ["visitors", "sources", "pages", "locations", "time"]],
  ["Results", ["leads", "conversions", "funnels", "events"]],
  ["AI & bots", ["bots"]],
  ["Site & server", ["health", "requests"]],
  ["Help", ["help", "about"]],
];
export const SUB = { health: ["health/alerts", "health/quality", "health/speed", "health/broken"] };
// Settings has a menu of its own, which takes the sidebar's place while a settings page is open.
export const SETTINGS_MENU = [
  ["You", ["settings/account"]],
  ["Team & access", ["settings/team", "settings/users", "settings/api"]],
  ["This site", ["settings/sites", "settings/internal", "settings/crawlers", "settings/retention", "settings/mail", "settings/integrations"]],
  ["Organisation", ["settings/sitesadmin", "settings/security", "settings/audit", "settings/billing"]],
];
export const inSettings = (key) => key.startsWith("settings/");
// The group a page sits in: its heading's name ("Audience"), or "Settings".
export function groupOf(key) {
  const top = key.split("/")[0];
  for (const [name, keys] of [...MENU, ...SETTINGS_MENU]) if (keys.includes(key) || keys.includes(top)) return name;
  return null;
}
// The first settings page this reader may open: where #settings lands.
export const firstSetting = () => SETTINGS_MENU.flatMap(([, keys]) => keys).find(shown) || "about";

// Earlier names of sections, and short ones, so an old link or a saved view still opens the right one.
export const ALIASES = { visits: "visitors", audience: "locations", hours: "time", alerts: "health/alerts", quality: "health/quality", ours: "settings/internal", broken: "health/broken",
  speed: "health/speed", home: "overview", crawlers: "bots", internal: "settings/internal", api: "settings/api", tokens: "settings/api", "settings/tokens": "settings/api",
  team: "settings/team", users: "settings/users", account: "settings/account", billing: "settings/billing", security: "settings/security", audit: "settings/audit",
  mail: "settings/mail", retention: "settings/retention", integrations: "settings/integrations", sites: "settings/sites",
  guides: "help", docs: "help", "settings/help": "help" };
// A section under another (Site health's sub-tabs, Settings' pages): its parent's key and name.
export const parentOf = (key) => (key.includes("/") ? [key.split("/")[0], key.startsWith("health") ? "Site health" : "Settings"] : null);
export const RANGES = [["today", "Today"], ["yesterday", "Yesterday"], ["7d", "7 days"], ["30d", "30 days"], ["90d", "90 days"], ["custom", "Custom"]];
export const FILTERS = ["country", "path", "source", "device", "browser", "campaign", "referrer"];
const DEFAULT = { tab: "overview", range: "30d", view: "all", from: "", to: "", pathmode: "contains", page: "", since: "", cmp: "", ip: "", rq: "", dd: "", tz: "", part: "", note: "", fn: "", fsrc: "", fstep: "", fmode: "", strat: "", ca: "", cb: "", cnorm: "", cgran: "", cm: "", cdim: "", pubfrom: "", pubto: "" };

export function read() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [asked, q = ""] = raw.split("?");
  // #settings opens the first settings page this reader may see.
  const tab = asked === "settings" ? firstSetting() : ALIASES[asked] || asked;
  const p = new URLSearchParams(q);
  const s = { ...DEFAULT, tab: TABS.some(([k]) => k === tab) ? tab : DEFAULT.tab };
  for (const k of ["range", "view", "from", "to", "pathmode", "page", "since", "cmp", "ip", "rq", "dd", "tz", "part", "note", "fn", "fsrc", "fstep", "fmode", "strat", "ca", "cb", "cnorm", "cgran", "cm", "cdim", "pubfrom", "pubto", ...FILTERS]) if (p.get(k)) s[k] = p.get(k);
  if (!RANGES.some(([k]) => k === s.range)) s.range = DEFAULT.range;
  if (s.range === "custom" && !(/^\d{4}-\d\d-\d\d$/.test(s.from) && /^\d{4}-\d\d-\d\d$/.test(s.to))) s.range = DEFAULT.range;
  if (s.pathmode !== "starts") s.pathmode = "contains";
  // The time zone: the link's, else the one this browser chose last, else the reader's own.
  if (!["local", "site", "utc"].includes(s.tz)) {
    let kept = "";
    try { kept = JSON.parse(localStorage.getItem("ti-tz") || '""'); } catch { /* storage blocked */ }
    s.tz = ["local", "site", "utc"].includes(kept) ? kept : "local";
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
  // A page's detail view and the insights' "since" belong to one tab each.
  if (s.page && s.tab === "pages") p.set("page", s.page);
  for (const k of ["pubfrom", "pubto"]) if (s[k] && s.tab === "pages") p.set(k, s[k]);
  if (s.since && s.tab === "insights") p.set("since", s.since);
  if (s.cmp) p.set("cmp", "1");
  if (s.tz && s.tz !== "local") p.set("tz", s.tz);
  // The request log's own toggles and the address it is narrowed to.
  if (s.ip && s.tab === "requests") p.set("ip", s.ip);
  if (s.rq && s.tab === "requests") p.set("rq", s.rq);
  // A part of the About page, and a note of its comparison.
  if (s.part && (s.tab === "about" || s.tab === "help")) p.set("part", s.part);
  if (s.note && s.tab === "about") p.set("note", s.note);
  // A funnel: its steps, starting source, and the step opened.
  if (s.tab === "funnels") for (const k of ["fn", "fsrc", "fstep", "fmode"]) if (s[k]) p.set(k, s[k]);
  // Compare: both periods and its own choices, so the link brings back the same comparison.
  if (s.tab === "compare") for (const k of ["ca", "cb", "cnorm", "cgran", "cm", "cdim"]) if (s[k]) p.set(k, s[k]);
  if (s.strat && s.tab === "health/speed") p.set("strat", s.strat);
  // The drill-down trail, last: it opens over whichever tab it started from.
  if (s.dd) p.set("dd", s.dd);
  const q = p.toString();
  return `#${s.tab}${q ? `?${q}` : ""}`;
}

const listeners = new Set();
export function on(fn) { listeners.add(fn); }

export function set(patch, { replace = false } = {}) {
  const cur = read();
  const next = { ...cur, ...patch };
  // Going to another tab leaves a drill-down behind unless the move carries one.
  if (patch.tab && patch.tab !== cur.tab && !("dd" in patch)) next.dd = "";
  const hash = hashFor(next);
  if (hash === location.hash) return;
  if (replace) history.replaceState(null, "", hash);
  else history.pushState(null, "", hash);
  emit();
}

let last = null;
export function emit(force = false) {
  if (!force && location.hash === last) return;
  last = location.hash;
  const s = read();
  listeners.forEach((fn) => fn(s));
}
addEventListener("hashchange", () => emit());
addEventListener("popstate", () => emit());

export function activeFilters(s) {
  return FILTERS.filter((k) => s[k]).map((k) => [k, s[k]]);
}
