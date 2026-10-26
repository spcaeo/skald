// The six sections (2.7.0; Security in 2.21): their keys, names, icons and order. Each section's
// tabs come from its own file, js/tabs/s-<section>.js, which its builder owns:
// [key, name, render, options] (the options are described in s-overview.js).
// The shell owns this file; section builders do not need to change it.
//
// Routes are "<section>/<tab>" (#traffic/sources); a bare section opens its first
// tab. Older addresses redirect (routes.js).

import * as S from "./state.js";
import { LAZY } from "./data.js";
import overview from "./tabs/s-overview.js";
import traffic from "./tabs/s-traffic.js";
import sales from "./tabs/s-sales.js";
import ai from "./tabs/s-ai.js";
import security from "./tabs/s-security.js";
import site from "./tabs/s-site.js";

const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;

// short: the phone's bottom bar, where a long name does not fit.
export const SECTIONS = [
  { key: "overview", name: "Overview", tabs: overview,
    icon: I('<rect x="2" y="9" width="3" height="5" rx="1"/><rect x="6.5" y="5" width="3" height="9" rx="1"/><rect x="11" y="2" width="3" height="12" rx="1"/>') },
  { key: "traffic", name: "Traffic", tabs: traffic,
    icon: I('<circle cx="3.5" cy="4" r="1.5"/><circle cx="12.5" cy="12" r="1.5"/><path d="M5 4h4.5a2.5 2.5 0 0 1 0 5h-3a2.5 2.5 0 0 0 0 5H11"/>') },
  { key: "sales", name: "Leads & sales", short: "Leads", tabs: sales,
    icon: I('<path d="M2 3h12l-4.5 5.5V13l-3-1.5v-3z"/>') },
  { key: "ai", name: "AI & bots", tabs: ai,
    icon: I('<rect x="3" y="5" width="10" height="8" rx="2"/><path d="M8 2.5V5M6 9h.01M10 9h.01M1.5 9v2M14.5 9v2"/>') },
  // Security (2.21): route key "threats", as "#security" opens Settings > Sign-in rules. bar: false
  // keeps it off the phone's bottom bar (five sections and Menu fill it); the menu has it.
  { key: "threats", name: "Security", tabs: security, bar: false,
    icon: I('<path d="M8 1.8 13.2 4v4c0 3.2-2.2 5.4-5.2 6.4C5 13.4 2.8 11.2 2.8 8V4z"/><path d="M8 5.5v3M8 10.6h.01"/>') },
  { key: "site", name: "Site", tabs: site,
    icon: I('<path d="M1.5 8.5h3l1.5-4 3 8 1.5-4h4"/>') },
];

/* Every section tab by its route: {section, key, name, render, ...options}. */
export const TAB = {};
for (const sec of SECTIONS) {
  for (const [key, name, render, opts = {}] of sec.tabs) TAB[`${sec.key}/${key}`] = { ...opts, section: sec.key, key, name, render };
}
S.addSections(SECTIONS.map((sec) => ({ key: sec.key, name: sec.name, short: sec.short,
  tabs: sec.tabs.map(([key, name, , opts = {}]) => ({ route: `${sec.key}/${key}`, name, keep: opts.keep })) })));

export const SECTION_ICONS = Object.fromEntries(SECTIONS.map((x) => [x.key, x.icon]));

/* A tab's option for this state: opt("traffic/pages", "ranged", s, true). A route
   outside the sections (Settings, Help, About) has none, so it gets the fallback. */
export function opt(route, name, s, fallback) {
  const v = TAB[route]?.[name];
  if (v === undefined) return fallback;
  return typeof v === "function" ? v(s) : v;
}

/* The big files (data.js LAZY) a tab is drawn with: its `file` and its `needs`, fetched before
   it is drawn. With panels: also its `later`, the files its panels wait for on their own
   (lazy.js), for a report, which is drawn once and printed. */
export function tabFiles(route, s, { panels = false } = {}) {
  const file = opt(route, "file", s, null);
  const all = [file, ...(opt(route, "needs", s, null) || []), ...(panels ? opt(route, "later", s, null) || [] : [])];
  return [...new Set(all.filter((n) => LAZY.includes(n)))];
}
