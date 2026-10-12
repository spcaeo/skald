// Site: Health · Alerts · Requests · Not found · Speed · Data quality. The Site builder
// owns this file. Tab entries and their options: see s-overview.js.
//
// 2.7.0: Health (si-health.js) also holds the heartbeat's outages; Requests and Not
// found (si-requests.js, si-notfound.js) are Data Grids; Speed and Alerts are today's
// pages with a link to where a shared figure lives (si-wrap.js); Data quality is as
// it was. The request log is listed here only (Live shows visits, not log lines).

import health from "./si-health.js";
import requests from "./si-requests.js";
import notFound from "./si-notfound.js";
import { speed, alerts } from "./si-wrap.js";
import quality from "./quality.js";

const ALL = ["country", "path", "source", "device", "browser", "campaign", "referrer"];

export default [
  ["health", "Health", health, { filters: ["path"], compare: true }],
  ["alerts", "Alerts", alerts, { file: "alerts", badge: (m) => { const n = (m.x?.alerts?.open || []).length; return n ? [n, `${n} open`] : null; } }],
  // The request log polls every 30 seconds on its own; a redraw would close its detail panel.
  ["requests", "Requests", requests, { file: "requests", filters: ALL, keep: ["ip", "rq"], polls: true }],
  ["notfound", "Not found", notFound, { file: "not_found", filters: ["path", "source"] }],
  ["speed", "Speed", speed, { file: "speed", keep: ["strat"] }],
  ["quality", "Data quality", quality],
];
