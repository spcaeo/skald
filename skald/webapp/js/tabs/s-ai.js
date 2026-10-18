// AI & bots: Assistants · Crawlers · Crawl health · Crawler rules · llms.txt. The AI & bots builder
// owns this file. Tab entries and their options: see s-overview.js.
//
// Assistants: AI working for someone waiting on an answer, and the visitors AI sent
// (the only place for AI visits; Traffic links here). Crawlers: everything with nobody
// waiting (training, search, bots), each checked. Crawler rules: the policy editor
// that was Settings > AI crawlers, and robots.txt. llms.txt: the suggested file.

import assistants from "./ai-assistants.js";
import crawlers from "./ai-crawlers.js";
import { rules, llms } from "./ai-rules.js";
import crawlHealth from "./crawlhealth.js";

export default [
  // bots.json gives only the Check column here, so its failure is said beside it, not over the whole tab.
  ["assistants", "Assistants", assistants, { filters: ["path"], compare: true }],
  ["crawlers", "Crawlers", crawlers, { file: "bots", filters: [], compare: true }],
  // crawl_health.json, its own 7 or 30 days and today (cw), a crawler (cb), orphans or all (co).
  ["crawl", "Crawl health", crawlHealth, { file: "crawl_health", ranged: false, filters: [], keep: ["cw", "chb", "co"], period: (s) => `Last ${s.cw === "7" ? 7 : 30} days and today` }],
  // Settings, and robots.txt with its own 30 days: the period does not apply. polls: the
  // 2-minute redraw (range=today) must not throw away an unsaved policy edit.
  ["rules", "Crawler rules", rules, { file: "bots", ranged: false, period: "Rules now · robots.txt: 30 days and today", figures: false, polls: true }],
  ["llms", "llms.txt", llms, { ranged: false, figures: false, polls: true }],
];
