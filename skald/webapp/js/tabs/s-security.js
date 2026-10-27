// Security (2.21): Is anything exposed? · Your stack · Who is scanning us? · Attack attempts · Fake
// browsers · Block list · Alerts. The Security builder owns this file. Tab entries and their
// options: see s-overview.js.
//
// A section of its own, not a tab of AI & bots: it is about the server and what was tried
// against it, for every host the log names (the bare IP too), where AI & bots is about who
// reads the site. Its route key is "threats" (#threats/exposed) because "#security" has long
// opened Settings > People > Sign-in rules (routes.js). Its tabs read security.json (security_page.py),
// loaded when a tab opens; the addresses come from the helper (owners and admins).

import exposed from "./sec-exposed.js";
import scanners from "./sec-scanners.js";
import attacks from "./sec-attacks.js";
import fake from "./sec-fake.js";
import block from "./sec-block.js";
import alerts from "./sec-alerts.js";
import stack from "./sec-stack.js";

export default [
  ["exposed", "Is anything exposed?", exposed, { filters: [], keep: ["sxv", "item"] }],
  // Your stack: read once a day from outside (stack.py), never the date range.
  ["stack", "Your stack", stack, { filters: [], ranged: false, period: "Checked once a day", keep: ["item"] }],
  ["scanners", "Who is scanning us?", scanners, { filters: [], keep: ["sxc", "sxk"] }],
  ["attacks", "Attack attempts", attacks, { filters: [], keep: ["sxa"] }],
  ["fake", "Fake browsers", fake, { filters: [] }],
  ["block", "Block list", block, { filters: [] }],
  // Alerts: the rules now and the last 30 days of alerts, never the date range.
  ["alerts", "Alerts", alerts, { filters: [], figures: false, ranged: false, period: "Rules now · alerts of the last 30 days" }],
];
