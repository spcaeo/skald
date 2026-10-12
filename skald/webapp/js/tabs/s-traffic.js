// Traffic: Visitors · Sources · Pages · Places & devices · Time. The Traffic builder
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

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];

export default [
  ["visitors", "Visitors", visitors, { filters: ALL }],
  // Each list narrows by its own filter; the landing pages (path) moved to Pages.
  ["sources", "Sources", sources, { filters: ["source", "referrer", "campaign"], compare: true }],
  // A page's story (?page=) has a period of its own.
  ["pages", "Pages", pages, { filters: ["path"], keep: ["page", "pubfrom", "pubto"], ranged: (s) => !s.page, compare: (s) => !s.page }],
  ["places", "Places & devices", places, { filters: ["country", "device", "browser"], compare: true }],
  ["time", "Time", hours, { filters: [] }],
];
