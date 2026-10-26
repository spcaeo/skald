// Overview: Summary · Insights. The Overview builder owns this file.
//
// Each tab: [key, name, render, options]. Its route is "<section>/<key>"
// ("overview/summary"); render(model, state, {first, changed}) draws it.
// Options, all optional (a function of the state `s` where it says so):
//   file     the data file it stands on: "could not be built" when that file failed (s)
//   filters  the global filters it applies; the others show greyed (s)
//   chips    "tab": the tab draws every active filter's chip itself, in its own "Filtered by"
//            line (Leads & sales > Leads, 2.23); the top bar's chip row and banner stand aside
//   keep     the address parameters that belong to this tab (page, fn, ip...)
//   ranged   false: the period bar does not apply (s)
//   period   with ranged false: the tab's own period, in a fixed chip where the bar was (s, m)
//   live     true: redrawn every 2 minutes whatever the period (else only for today)
//   compare  true: it follows the compare switch (cmp)
//   figures  false: a page without figures (the top bar keeps its title and buttons only)
//   polls    true: it refreshes itself; the 2-minute redraw leaves it alone
//   helper   true: it needs the helper; the demo says so instead of drawing it
//   badge    (model) => [count, words] or null: a small number on the tab (open alerts)
//   needs    the big files (data.js LAZY) it is drawn with, beyond its `file`: fetched first,
//            a "Loading" line meanwhile (s)
//   later    the big files its panels wait for on their own (lazy.js later), so the tab is
//            drawn without them (s)

import summary from "./ov-summary.js";
import insights from "./insights.js";
import realtime from "./realtime.js";


// Summary in Live mode (range=today) is the approved Live layout (2.13,
// js/tabs/ov-today.js): the live strip (visitors now, minute by minute, one Pause;
// the four tiles against yesterday at this hour), the map and the newest visits,
// sources and the flow, what converted and AI & bots, each linking to its full tab.

export default [
  // Its work and new-pages cards wait for page_trends and page_index (2.41): the key figures do not.
  ["summary", "Summary", summary, { live: true, compare: true, later: ["page_trends", "page_index"] }],
  // Real time (js/tabs/realtime.js): always now, whatever the period; it asks for
  // fresh figures every 15 seconds itself, so the 2-minute redraw leaves it alone.
  ["realtime", "Real time", realtime, { live: true, polls: true, ranged: false, period: "Now" }],
  ["insights", "Insights", insights, { file: "insights", filters: ["path", "country", "source", "campaign", "referrer"], keep: ["since", "todo", "pchg"], ranged: false, period: "Each insight's own two periods" }],
  // #live and #compare are the global modes now (js/modes.js, routes.js): Summary with
  // range=today, or any tab with cmp set. No Live or Compare tab of their own.
];
