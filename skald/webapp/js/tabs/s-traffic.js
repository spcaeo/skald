// Traffic: Visitors · Sources · Pages · Places & devices | Agent files · Search · Retention · Time · Events. The
// Traffic builder owns this file. Tab entries and their options: see s-overview.js. Events (what
// visitors did inside the pages, from the script tag) moved here from Leads & sales in #33.
//
// One place per answer (2.7.0): source types, referring sites and campaigns are one
// grid on Sources; landing pages are on Pages only; countries on Places & devices only;
// AI visits and the pages AI assistants fetched live under AI & bots, linked from here.
// Compare mode: the Sources, Pages and Places grids get B and ± (tr-grid.js).
//
// SKALD-62 (Palak, 26 Nov): the first four share one Country / Source / Device filter, a bar
// under the strip (tr-filter.js, narrow.js); `group` boxes them on the strip, and Places &
// devices moved up beside Pages. The other five keep their own filters, as before.

import visitors from "./tr-visitors.js";
import sources from "./tr-sources.js";
import pages from "./tr-pages.js";
import places from "./tr-places.js";
import agentFiles from "./tr-agentfiles.js";
import hours from "./hours.js";
import search from "./tr-search.js";
import retention from "./tr-retention.js";
import events from "./events.js";

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];
// The four tabs that share the bar's Country / Source / Device filter (SKALD-62): one box on the strip.
const GROUP = "These four tabs share one filter: country, source and device";
// A page's story (Pages, ?page=) has no bar: there the top bar's chips show, greyed, as before.
const story = (s) => s.tab === "traffic/pages" && !!s.page;
const SHARED = { group: GROUP, shared: (s) => !story(s), chips: (s) => (story(s) ? "" : "shared") };

export default [
  // rules: the advanced filters apply here, to each visit (js/rules.js); elsewhere the banner says they do not.
  // rulesScope: what on the tab the filters narrow, said under the bar while some are on.
  ["visitors", "Visitors", visitors, { ...SHARED, filters: ALL, rules: "visit",
    rulesScope: "The filters narrow the visitor flow and the visit list, and, within the days visits are kept, the new and returning and engagement cards and where visits ended; a table they do not narrow says so." }],
  // Each list narrows by its own filter; the landing pages (path) moved to Pages. The bar's
  // filters narrow every list that can be split by them (narrow.js); the rest say they are not.
  // net: the social network open under the grid (tr-social.js).
  ["sources", "Sources", sources, { ...SHARED, filters: ["source", "referrer", "campaign", "country", "device"], compare: true, keep: ["net"] }],
  // A page's story (?page=) has a period of its own.
  ["pages", "Pages", pages, { needs: ["pages", "page_index", "page_trends"], ...SHARED, filters: (s) => (s.page ? ["path"] : ["path", "country", "source", "device"]), keep: ["page", "psec", "pubfrom", "pubto", "chgfrom", "psort", "pchg"], ranged: (s) => !s.page, compare: (s) => !s.page }],
  ["places", "Places & devices", places, { ...SHARED, filters: ["country", "device", "browser", "source"], compare: true }],
  // SKALD-56: files made for machines (Markdown copies, OKF, llms.txt, agent cards) and who
  // fetched them, from agent_files.json; the whole site's, so no filter narrows it.
  ["agentfiles", "Agent files", agentFiles, { filters: [] }],
  // Search (P1-6): Search Console's and Bing's own figures, synced every 6 hours
  // (search.json). Its own engine and period chips: the engines' days, not the bar's.
  ["search", "Search", search, { file: "search", filters: [], ranged: false, period: "The engines' own days" }],
  // Retention cohorts (tr-retention.js): a period of their own, the last 12 weeks
  // (or 30 days) of first visits; the whole site's, never filtered.
  ["retention", "Retention", retention, { file: "retention", filters: [], ranged: false, keep: ["rg", "rm", "rs", "rv"],
    period: (s) => (s.rg === "day" ? "30 days of first visits" : "12 weeks of first visits") }],
  ["time", "Time", hours, { filters: [] }],
  // #33: from Leads & sales (#sales/events opens it, routes.js). Its page and source filters apply.
  ["events", "Events", events, { file: "events", filters: ["path", "source"] }],
];
