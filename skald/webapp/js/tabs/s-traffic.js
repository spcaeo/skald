// Traffic: Visitors · Sources · Pages · Places & devices · Search · Retention · Time. The Traffic builder
// owns this file. Tab entries and their options: see s-overview.js.
//
// One place per answer (2.7.0): source types, referring sites and campaigns are one
// grid on Sources; landing pages are on Pages only; countries on Places & devices only;
// AI visits and the pages AI assistants fetched live under AI & bots, linked from here.
// Compare mode: the Sources, Pages and Places grids get B and ± (tr-grid.js).

import visitors from "./tr-visitors.js";
import sources from "./tr-sources.js";
import pages from "./tr-pages.js";
import places from "./tr-places.js";
import hours from "./hours.js";
import search from "./tr-search.js";
import retention from "./tr-retention.js";

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];

export default [
  // rules: the advanced filters apply here, to each visit (js/rules.js); elsewhere the banner says they do not.
  // rulesScope: what on the tab the filters narrow, said under the bar while some are on.
  ["visitors", "Visitors", visitors, { filters: ALL, rules: "visit",
    rulesScope: "The filters narrow the visitor flow and the visit list, and, within the days visits are kept, the new and returning and engagement cards and where visits ended; a table they do not narrow says so." }],
  // Each list narrows by its own filter; the landing pages (path) moved to Pages.
  // net: the social network open under the grid (tr-social.js).
  ["sources", "Sources", sources, { filters: ["source", "referrer", "campaign"], compare: true, keep: ["net"] }],
  // A page's story (?page=) has a period of its own.
  ["pages", "Pages", pages, { needs: ["pages", "page_index", "page_trends"], filters: ["path"], keep: ["page", "psec", "pubfrom", "pubto", "chgfrom", "psort", "pchg"], ranged: (s) => !s.page, compare: (s) => !s.page }],
  ["places", "Places & devices", places, { filters: ["country", "device", "browser"], compare: true }],
  // Search (P1-6): Search Console's and Bing's own figures, synced every 6 hours
  // (search.json). Its own engine and period chips: the engines' days, not the bar's.
  ["search", "Search", search, { file: "search", filters: [], ranged: false, period: "The engines' own days" }],
  // Retention cohorts (tr-retention.js): a period of their own, the last 12 weeks
  // (or 30 days) of first visits; the whole site's, never filtered.
  ["retention", "Retention", retention, { file: "retention", filters: [], ranged: false, keep: ["rg", "rm", "rs", "rv"],
    period: (s) => (s.rg === "day" ? "30 days of first visits" : "12 weeks of first visits") }],
  ["time", "Time", hours, { filters: [] }],
];
