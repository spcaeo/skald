// Leads & sales (#33, laid out again: eight tabs became four, the owner's "make things simple
// and easy"): Leads · Summary · Revenue · Funnels. The Leads & sales builder owns this file.
// Tab entries and their options: see s-overview.js. Each tab answers one question (its
// subtitle), with at most one row of options (sa-options.js), an optional row of numbers and
// one main table or chart.
//
//   Leads     who are my leads? one row per lead, as a list, board, timeline or map
//             (sa-leads.js, sa-views.js); names and emails for admins and owners. What: Demos
//             is the old Calendar bookings, with its stage steps (sa-steps.js); the Find a
//             person box sits at the right of its head (sa-find.js)
//   Summary   how many, where from, and is it better than before? (sa-pipeline.js); the old
//             Sources tab is its "Where they came from" fold
//   Revenue   which sources, pages and campaigns made money? (sa-revenue.js, 2.32.0)
//   Funnels   how many visits went through a series of pages, and where the rest left
//             (funnels.js)
//
// Events moved to Traffic › Events (s-traffic.js): what visitors did inside the pages is not a
// lead. Every old address opens the same view (routes.js: sales/sources, sales/bookings,
// sales/events, sales/people, #leads, #conversions).
//
// #32: one period on every tab, today included (sa-period.js salesRange). Leads, Summary and
// Revenue are `live`: drawn again every 2 minutes while the period holds today (Funnels only on
// Today, as before: its builder is not redrawn under the reader's hands). No tab here follows
// the compare switch: each compares like for like itself (the period before, to this hour).

import summary from "./sa-pipeline.js";
import leadsTab from "./sa-leads.js";
import revenue from "./sa-revenue.js";
import funnels from "./funnels.js";
import { salesLive } from "./sa-period.js";

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];

// One line per tab: tests/test_routes.py reads each tab's keep list from its line.
export default [
  ["leads", "Leads", leadsTab, { file: "conversions", filters: ["country", "source", "device", "campaign"], chips: "tab", live: salesLive, keep: ["lact", "llabel", "lnow", "lby", "lshow", "lview", "lsplit", "lfind"] }],
  ["summary", "Summary", summary, { file: "conversions", filters: [], live: salesLive, keep: ["lact", "llabel", "lpart"] }],
  ["revenue", "Revenue", revenue, { file: "conversions", filters: [], live: salesLive, keep: ["cur", "rby", "tag"] }],
  ["funnels", "Funnels", funnels, { file: "funnels", needs: ["pages"], filters: ALL, rules: "visit", keep: ["fn", "fsrc", "fstep", "fmode"] }],
];
