// Leads & sales (2.20): Leads · Summary · Sources · Calendar bookings · Funnels · Events ·
// Find a person. The Leads & sales builder owns this file. Tab entries and their options:
// see s-overview.js. Each tab answers one question (its subtitle), with at most one row of
// options (sa-options.js), an optional row of numbers and one main table or chart.
//
//   Leads              who are my leads? one row per lead, as a list, board, timeline or map
//                      (sa-leads.js, sa-views.js); names and emails for admins and owners
//   Summary            how many, and is it better than before? (sa-pipeline.js)
//   Sources            where did they come from? (sa-pipeline.js)
//   Revenue            which sources, pages and campaigns made money? (sa-revenue.js, 2.32.0)
//   Calendar bookings  who booked a call? Calendly, Cal.com, Stripe (sa-bookings.js)
//   Find a person      everything kept about one person (sa-people.js)
//
// Summary and Sources count from the lead database by default where the site has one
// (leads.json; the owner's decision, 2026-10-12) or from the tools (conversions.json,
// lsrc=all): never both in one figure. Old #sales/pipeline opens Summary, #leads Summary
// from the lead database, #conversions Summary from the tools (routes.js), so each old
// link shows the figures it showed.

import { summary, sources, tools } from "./sa-pipeline.js";
import leadsTab from "./sa-leads.js";
import revenue from "./sa-revenue.js";
import bookings from "./sa-bookings.js";
import people from "./sa-people.js";
import funnels from "./funnels.js";
import events from "./events.js";

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];

const file = (s) => (tools(s) ? "conversions" : "leads");
const filters = (s) => (tools(s) ? [] : ["source"]);

// One line per tab: tests/test_routes.py reads each tab's keep list from its line.
export default [
  ["leads", "Leads", leadsTab, { file: "conversions", filters: ["country", "source", "device", "campaign"], chips: "tab", keep: ["lact", "llabel", "lnow", "lby", "lshow", "lview", "lsplit"] }],
  ["summary", "Summary", summary, { file, filters, keep: ["lsrc", "lact", "llabel", "lstage"], compare: true }],
  ["sources", "Sources", sources, { file, filters, keep: ["lsrc", "lact", "llabel", "lstage"] }],
  ["revenue", "Revenue", revenue, { file: "conversions", filters: [], keep: ["cur", "by", "tag"] }],
  ["bookings", "Calendar bookings", bookings, { file: "conversions", filters: [], keep: ["bact", "bshow"] }],
  ["funnels", "Funnels", funnels, { file: "funnels", needs: ["pages"], filters: ALL, rules: "visit", keep: ["fn", "fsrc", "fstep", "fmode"] }],
  ["events", "Events", events, { file: "events", filters: ["path", "source"] }],
  ["people", "Find a person", people, { figures: false, ranged: false, period: "Everything kept" }],
];
