// Every key the address may hold, in one list (2.21): its name, the module that owns
// it, what it means, and its kind. docs/ROUTES.md says the same for people; the
// tests check that every key state.js reads is listed here (tests/js/routes.mjs).
// No DOM and no other module here, so node runs it.
//
//   #<section>/<tab>?<key>=<value>&...      e.g. #traffic/visitors?range=7d&vis=2026-10-20.14
//
// Kinds:
//   global   kept on every tab (the period, the page group, the filters, the drill-down)
//   tab      one tab's own (its `keep` list in js/tabs/s-*.js); another tab starts without it
//   overlay  a drawer or a dialog open over the tab, with what it shows. Opening adds one
//            history entry (Back closes it); a change inside it (a step) replaces the entry;
//            closing it removes the key. Going to another tab closes it.
//   table    a table's or a grid's own state, <ns>_<suffix> (js/tablestate.js); kept while
//            the tab stays. Sub-tabs inside a tab use <ns>_view the same way.
//
// Privacy: no value is ever an address (IPv4 or IPv6), an email or a search for a
// person. Such a value goes into the address as an opaque token (~ and 10 letters or
// digits) that only this browser can read back (js/routemask.js). A token another
// browser made opens the page with one plain line instead.

export const ROUTE_KEYS = [
  // ---- global: every tab
  { key: "range", kind: "global", owner: "state.js", means: "the period: today, yesterday, 7d, 30d, 90d, all (all time) or custom; absent: the section's own (7d on Leads & sales, today elsewhere)" },
  { key: "from", kind: "global", owner: "state.js", means: "a custom period's first day (YYYY-MM-DD)" },
  { key: "to", kind: "global", owner: "state.js", means: "a custom period's last day" },
  { key: "view", kind: "global", owner: "state.js", means: "the page group (a view's slug); all pages when absent" },
  { key: "country", kind: "global", owner: "filterpanel.js", means: "the country filter (two letters)" },
  { key: "path", kind: "global", owner: "filterpanel.js", means: "the page filter (a path, or its start with pathmode=starts)" },
  { key: "pathmode", kind: "global", owner: "filterpanel.js", means: "starts: the page filter matches paths that start with it" },
  { key: "source", kind: "global", owner: "filterpanel.js", means: "the source filter (a source type)" },
  { key: "device", kind: "global", owner: "filterpanel.js", means: "the device filter" },
  { key: "browser", kind: "global", owner: "filterpanel.js", means: "the browser filter" },
  { key: "campaign", kind: "global", owner: "filterpanel.js", means: "the campaign filter" },
  { key: "referrer", kind: "global", owner: "filterpanel.js", means: "the referring-site filter" },
  { key: "rules", kind: "global", owner: "rules.js", means: "the advanced filters' rules, beyond the single filters" },
  { key: "cmp", kind: "global", owner: "modes.js", means: "Compare with: prev, year or custom" },
  { key: "cb", kind: "global", owner: "mode-compare.js", means: "Compare's custom period B (YYYY-MM-DD..YYYY-MM-DD)" },
  { key: "cnorm", kind: "global", owner: "mode-compare.js", means: "Compare: per day" },
  { key: "cgran", kind: "global", owner: "mode-compare.js", means: "Compare's chart grain" },
  { key: "cm", kind: "global", owner: "mode-compare.js", means: "Compare's chart figure" },
  { key: "tz", kind: "global", owner: "tz.js", means: "the time zone: local or utc (the site's when absent)" },
  { key: "dd", kind: "global", owner: "drill.js", means: "the drill-down trail, dim:value|dim:value (an address as a token)" },
  // ---- tab: one tab's own
  { key: "page", kind: "tab", owner: "tabs/pagestory.js", means: "Traffic > Pages: the page whose story is open" },
  { key: "net", kind: "tab", owner: "tabs/tr-social.js", means: "Traffic > Sources: the social network open under the grid (x, linkedin, facebook, ...; with src_seg=social)" },
  { key: "pubfrom", kind: "tab", owner: "tabs/tr-pages.js", means: "Traffic > Pages: published from" },
  { key: "pubto", kind: "tab", owner: "tabs/tr-pages.js", means: "Traffic > Pages: published to" },
  { key: "rg", kind: "tab", owner: "tabs/tr-retention.js", means: "Retention: the cohorts' grain" },
  { key: "rm", kind: "tab", owner: "tabs/tr-retention.js", means: "Retention: the measure" },
  { key: "rs", kind: "tab", owner: "tabs/tr-retention.js", means: "Retention: the segment" },
  { key: "rv", kind: "tab", owner: "tabs/tr-retention.js", means: "Retention: the view" },
  { key: "since", kind: "tab", owner: "tabs/insights.js", means: "Insights: the window" },
  { key: "fn", kind: "tab", owner: "tabs/funnels.js", means: "Funnels: the steps" },
  { key: "fsrc", kind: "tab", owner: "tabs/funnels.js", means: "Funnels: the starting source" },
  { key: "fstep", kind: "tab", owner: "tabs/funnels.js", means: "Funnels: the step open" },
  { key: "fmode", kind: "tab", owner: "tabs/funnels.js", means: "Funnels: reached it or left after it" },
  { key: "lsrc", kind: "tab", owner: "tabs/s-sales.js", means: "Leads & sales: count from" },
  { key: "lact", kind: "tab", owner: "tabs/sa-options.js", means: "Leads & sales: the kind of lead" },
  { key: "llabel", kind: "tab", owner: "tabs/sa-options.js", means: "Leads & sales: the lead label" },
  { key: "lstage", kind: "tab", owner: "tabs/sa-options.js", means: "Leads & sales: the stage" },
  { key: "lnow", kind: "tab", owner: "tabs/sa-leads.js", means: "Leads: the stage now" },
  { key: "lby", kind: "tab", owner: "tabs/sa-leads.js", means: "Leads: the source" },
  { key: "lshow", kind: "tab", owner: "tabs/sa-leads.js", means: "Leads: show left out" },
  { key: "lview", kind: "tab", owner: "tabs/sa-leads.js", means: "Leads: list, board, timeline or map" },
  { key: "lsplit", kind: "tab", owner: "tabs/sa-leads.js", means: "Leads: the split" },
  { key: "cur", kind: "tab", owner: "tabs/sa-revenue.js", means: "Revenue: the currency shown (three letters, e.g. USD); figures are never converted" },
  { key: "by", kind: "tab", owner: "tabs/sa-revenue.js", means: "Revenue: the breakdown (first_source, campaign, landing, country, device, tool, label, tag; source when absent)" },
  { key: "tag", kind: "tab", owner: "tabs/sa-revenue.js", means: "Revenue: one tag, key:value (e.g. plan:pro)" },
  { key: "bact", kind: "tab", owner: "tabs/sa-bookings.js", means: "Bookings: the action" },
  { key: "bshow", kind: "tab", owner: "tabs/sa-bookings.js", means: "Bookings: what to show" },
  { key: "cw", kind: "tab", owner: "tabs/crawlhealth.js", means: "Crawl health: 7 or 30 days" },
  { key: "chb", kind: "tab", owner: "tabs/crawlhealth.js", means: "Crawl health: the crawler" },
  { key: "co", kind: "tab", owner: "tabs/crawlhealth.js", means: "Crawl health: every page or only problems" },
  { key: "ap", kind: "tab", owner: "tabs/ai-answers.js", means: "AI answers: the profile open (its id, or new)" },
  { key: "aq", kind: "tab", owner: "tabs/ai-answers.js", means: "AI answers: the question open" },
  { key: "ip", kind: "tab", owner: "tabs/si-requests.js", means: "Requests: only this address, always as a token" },
  { key: "rq", kind: "tab", owner: "tabs/si-requests.js", means: "Requests: the quick filters (mine, nobots, people, errors, ai)" },
  { key: "strat", kind: "tab", owner: "tabs/speed.js", means: "Speed: desktop (phone when absent)" },
  { key: "part", kind: "tab", owner: "tabs/help.js", means: "Help: the guide or its part open" },
  { key: "note", kind: "tab", owner: "tabs/about.js", means: "About: the note open" },
  { key: "test", kind: "tab", owner: "tabs/sitesadmin.js", means: "Add or remove sites: open a site's wizard at its Test (the site's name)" },
  { key: "sxv", kind: "tab", owner: "tabs/sec-exposed.js", means: "Security > Is anything exposed?: possible, nosize (can't tell) or both" },
  { key: "item", kind: "tab", owner: "tabs/sec-exposed.js", means: "Security: the item an alert names, opened first (an opaque id: x or a and 12 hex)" },
  { key: "sxc", kind: "tab", owner: "tabs/sec-scanners.js", means: "Security > Who is scanning us?: what they looked for" },
  { key: "sxk", kind: "tab", owner: "tabs/sec-scanners.js", means: "Security > Who is scanning us?: all: every suspect, not only scanners" },
  { key: "sxa", kind: "tab", owner: "tabs/sec-attacks.js", means: "Security > Attack attempts: injection, login or burst" },
  // Read by the old Compare page's address only, then rewritten (routes.js).
  { key: "ca", kind: "tab", owner: "routes.js", means: "the old Compare page's period A (rewritten)" },
  { key: "cdim", kind: "tab", owner: "routes.js", means: "the old Compare page's table (rewritten)" },
  // ---- overlay: a drawer or a dialog over the tab
  { key: "vis", kind: "overlay", owner: "tabs/visitor.js", means: "the visitor drawer, by its visit: <day>.<seq>", example: "2026-10-20.14" },
  { key: "who", kind: "overlay", owner: "tabs/visitor.js", means: "Find a person: the search, always as a token (this browser only)", example: "~k2f9a0x7qm" },
  { key: "lead", kind: "overlay", owner: "tabs/sa-leads.js", means: "a lead's drawer, by its row id", example: "1287" },
  { key: "conv", kind: "overlay", owner: "tabs/sa-lists.js", means: "a cancelled, removed or test conversion's drawer: <list>.<n>", example: "test.3" },
  { key: "req", kind: "overlay", owner: "tabs/si-requests.js", means: "one request's detail, by an opaque code of the log line", example: "r8k2m1x" },
  { key: "cohort", kind: "overlay", owner: "tabs/tr-retention.js", means: "Retention: a cell's visitors, <cohort>.<period>", example: "2026-10-05.2" },
  { key: "sq", kind: "overlay", owner: "tabs/tr-search.js", means: "Search: a query's or a page's drawer, <kind>.<engine>:<key>", example: "query.google:skald analytics" },
  { key: "list", kind: "overlay", owner: "tabs/person.js", means: "a list drawer: leftout, or conv-cancelled, conv-removed, conv-test", example: "leftout" },
  { key: "scan", kind: "overlay", owner: "tabs/sec-scanners.js", means: "Security > Who is scanning us?: one scanner's detail, by its first row: <day>.<seq> (never its address)", example: "2026-10-20.3" },
  { key: "ans", kind: "overlay", owner: "tabs/ai-answers.js", means: "AI answers: one stored answer in full, by its id", example: "412" },
  { key: "setup", kind: "overlay", owner: "tabs/setup-dialogs.js, tabs/sitesadmin.js", means: "a Set up dialog (logs, assets, rsc, countries, script, lead, mail, privacy, pack: send set-up to someone); on Add or remove sites, the Add a site wizard (new, or a site's name); a site's name on any tab is its wizard too (Connections' Set up with your AI agent)", example: "rsc" },
  { key: "conn", kind: "overlay", owner: "tabs/connections.js", means: "a Connections dialog: send, api or mcp", example: "api" },
  { key: "step", kind: "overlay", owner: "tabs/conn-ui.js", means: "the step of the dialog open (1 is the first)", example: "2" },
  { key: "agent", kind: "overlay", owner: "tabs/site-wizard.js", means: "Add a site: the AI agent chosen (claude-code, codex, cursor, chat, other), or hand (set it up by hand)", example: "claude-code" },
  { key: "link", kind: "overlay", owner: "tabs/agent-setup.js", means: "Add a site: the agent line being watched, by its link id (16 hex, a hash of the code; the line and its code never go in the address)", example: "0f3a9c2e7b1d4a58" },
  { key: "share", kind: "overlay", owner: "tabs/conn-share.js", means: "Share with your developer: the form is open in the dialog (the link itself never goes in the address)", example: "1" },
  { key: "token", kind: "overlay", owner: "tabs/conn-install.js", means: "the token choice of a by-hand kit (the zips under Other ways): 0 is the zip without the token; absent, the token goes in the zip (the token itself never goes in the address)", example: "0" },
  { key: "pack", kind: "overlay", owner: "tabs/setup-pack.js", means: "Send set-up to someone: the box is open in the dialog (the addresses typed and the keys never go in the address)", example: "1" },
  { key: "dlg", kind: "overlay", owner: "main.js, keys.js, extras.js, report.js, filterpanel.js, tabs/person.js", means: "an app dialog: keys (shortcuts), new (What's new), views (saved views), report (report builder), filters (the Filters panel), find (Find a person, empty)", example: "views" },
];

// A table's or a grid's keys: <ns>_<suffix> (tablestate.js TABLE_KEY).
export const TABLE_SUFFIXES = { q: "the search box", sort: "the order (column:asc|desc)", page: "the page number", size: "rows per page",
  seg: "the segment", fx: "the grid's filters", view: "a sub-tab or a grid's view", sel: "the rows chosen", cf: "the column filters", hide: "the columns taken away" };

export const KEYS = new Map(ROUTE_KEYS.map((k) => [k.key, k]));
export const OVERLAY = ROUTE_KEYS.filter((k) => k.kind === "overlay").map((k) => k.key);
// The keys inside the dialog open (its step, the share form, the kit's token choice, the
// set-up pack's box, Add a site's agent and the line it watches); the other overlay keys
// name the drawer or dialog itself.
export const INSIDE = ["step", "share", "token", "pack", "agent", "link"];
export const OPENERS = OVERLAY.filter((k) => !INSIDE.includes(k));
// Always a token, whatever the value looks like: a search for a person, an address filter.
export const ALWAYS_MASKED = new Set(["who", "ip"]);

// ---- what may never be in the address -----------------------------------------------
const IPV4 = /(?<![\d.])(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?![\d.])/g;
// IPv6: eight groups, or a "::" with groups around it (a shortened one ends in "::").
const IPV6 = /(?<![0-9a-f])(?:(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}|(?:[0-9a-f]{1,4}:){1,7}:(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4})*)?|::(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4})*))(?![0-9a-f:])/gi;
// An email, or anything with an @: the run of characters around it, up to a separator.
const AT = /[^\s|,;:&=?#]*@[^\s|,;:&=?#]*/g;
export const PERSONAL = [IPV4, IPV6, AT];

/* The personal parts of a value: [[start, end]], in order. */
export function personalParts(value) {
  const text = String(value ?? "");
  const out = [];
  for (const re of PERSONAL) {
    re.lastIndex = 0;
    for (let m = re.exec(text); m; m = re.exec(text)) {
      if (!m[0]) { re.lastIndex += 1; continue; }
      out.push([m.index, m.index + m[0].length]);
    }
  }
  out.sort((a, b) => a[0] - b[0]);
  // Overlaps (an address inside an email) become one part.
  const merged = [];
  for (const p of out) {
    const last = merged[merged.length - 1];
    if (last && p[0] <= last[1]) last[1] = Math.max(last[1], p[1]);
    else merged.push([...p]);
  }
  return merged;
}
export const isPersonal = (value) => personalParts(value).length > 0;

/* A short opaque code for a record that has no id of its own (a log line, a conversion):
   FNV-1a, 32 bits, in base 36, with a letter first. The same record gives the same code;
   it cannot be read back. */
export function codeOf(text) {
  let x = 0x811c9dc5;
  for (const ch of String(text)) { x ^= ch.codePointAt(0); x = Math.imul(x, 0x01000193) >>> 0; }
  return `r${x.toString(36)}`;
}

// A token made by js/routemask.js: "~" and 10 letters or digits.
export const TOKEN = /~[a-z0-9]{10}/g;
export const isToken = (value) => /^~[a-z0-9]{10}$/.test(String(value ?? ""));
export const hasToken = (value) => /~[a-z0-9]{10}/.test(String(value ?? ""));
