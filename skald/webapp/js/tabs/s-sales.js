// Leads & sales: Pipeline · Bookings · Funnels · Events · People. The Leads & sales
// builder owns this file. Tab entries and their options: see s-overview.js.
//
// Pipeline counts from the lead database by default (leads.json; the owner's
// decision, 2026-10-12) or from the tools (conversions.json, lsrc=all): never
// both in one figure. Old #leads opens lsrc=db, old #conversions lsrc=all
// (routes.js), so each old link shows the figures it showed. Bookings is the
// tools' booking actions; People the person search and the recent conversions.
// The tabs' own files: sa-pipeline.js, sa-bookings.js, sa-people.js, with
// sa-options.js (the options row) and sa-lists.js (what the figures leave out).

import pipeline, { tools } from "./sa-pipeline.js";
import bookings from "./sa-bookings.js";
import people from "./sa-people.js";
import funnels from "./funnels.js";
import events from "./events.js";

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];

const file = (s) => (tools(s) ? "conversions" : "leads");
const filters = (s) => (tools(s) ? [] : ["source"]);

// One line per tab: tests/test_routes.py reads each tab's keep list from its line.
export default [
  ["pipeline", "Pipeline", pipeline, { file, filters, keep: ["lsrc", "lact", "lstage", "lshow"], compare: true }],
  ["bookings", "Bookings", bookings, { file: "conversions", filters: [], keep: ["bact", "bshow"] }],
  ["funnels", "Funnels", funnels, { file: "funnels", filters: ALL, keep: ["fn", "fsrc", "fstep", "fmode"] }],
  ["events", "Events", events, { file: "events", filters: ["path", "source"] }],
  ["people", "People", people, { figures: false }],
];
