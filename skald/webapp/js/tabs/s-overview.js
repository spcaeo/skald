// Overview: Summary · Insights. The Overview builder owns this file.
//
// Each tab: [key, name, render, options]. Its route is "<section>/<key>"
// ("overview/summary"); render(model, state, {first, changed}) draws it.
// Options, all optional (a function of the state `s` where it says so):
//   file     the data file it stands on: "could not be built" when that file failed (s)
//   filters  the global filters it applies; the others show greyed (s)
//   keep     the address parameters that belong to this tab (page, fn, ip...)
//   ranged   false: the period bar does not apply (s)
//   live     true: redrawn every 2 minutes whatever the period (else only for today)
//   compare  true: it follows the compare switch (cmp)
//   figures  false: a page without figures (the top bar keeps its title and buttons only)
//   polls    true: it refreshes itself; the 2-minute redraw leaves it alone
//   helper   true: it needs the helper; the demo says so instead of drawing it
//   badge    (model) => [count, words] or null: a small number on the tab (open alerts)

import summary from "./ov-summary.js";
import insights from "./insights.js";


// Summary in Live mode (range=today) holds what the old Live page showed: the
// tiles with "+N this hour", Right now (5 visits, 5 AI events, Pause), today's
// leads and bookings (5, with a link to Pipeline), visitors by hour, who else
// came and today's top fives (js/tabs/ov-summary.js, ov-live.js).

export default [
  ["summary", "Summary", summary, { live: true, compare: true }],
  ["insights", "Insights", insights, { file: "insights", filters: ["path", "country", "source", "campaign", "referrer"], keep: ["since"] }],
  // #live and #compare are the global modes now (js/modes.js, routes.js): Summary with
  // range=today, or any tab with cmp set. No Live or Compare tab of their own.
];
