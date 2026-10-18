// AI & bots > Crawlers (2.7.0): everything that fetches with nobody waiting. AI
// collecting for training, search engines indexing, bots and scanners (scanner
// probes among them), each crawler beside the server's check of its address
// (verified, not verifiable, spoofed), browsers with warning signs, link previews.
//
// Figures are today's, from the same fields: app.json `tiers.training`,
// `engines.training`, `search`, `search_engines`, `hits.bots`, `probes`,
// `bot_agents`, `ai_formats` (What they fetch); bots.json (checks); robots.json (robots.txt column).

import { h } from "../ui.js";
import { figures, ranked } from "../data.js";
import { head, nothing, fileName } from "./common.js";
import { verification, verifySection, badge, badgeOf } from "./botverify.js";
import { robotsOf, robotsBadge, robotsWords } from "./robots.js";
import { kpi, tierChart, countGrid, tabLink, formatsSection } from "./ai-parts.js";
import { costSection } from "./crawlercost.js";

const ADS = /ads quality|AdsBot/i;
const LEDE = "Crawlers with nobody waiting: AI collecting pages for training or AI search, search engines indexing the site, and bots and scanners. A crawler's name is what it calls itself; the server checks the address of the well-known ones. Assistants answering someone's question are on Assistants.";

export default function crawlersTab(m, s, { first }) {
  const { r, t } = figures(m, s);
  const out = [...head("Crawlers", r, LEDE)];
  if (!t) return [...out, nothing(m, r)];
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    kpi(first, "AI collecting for training", t.tiers?.training ?? 0, "pages fetched; nobody is waiting on these", "answer_engines"),
    kpi(first, "Search engines", t.search ?? 0, "pages fetched for indexing; ads checks apart", "search_engines"),
    kpi(first, "Bots and scanners", t.hits?.bots ?? 0, "requests: monitors, SEO tools, link previews, probes, and browser-like visits that never rendered the page", "bots", "requests"),
    kpi(first, "of which scanner probes", t.probes ?? 0, "requests hunting for credentials on paths no real site serves", "bots", "requests"))));
  out.push(tierChart(m, s, r, { title: "AI pages fetched for training, per day", name: "Collecting for training", tier: "training", group: "answer_engines", label: "AI fetches for training per day" }));

  // The AI crawlers by name, with the address check and the robots.txt verdict, as on Assistants.
  const checks = verification(m, r);
  const rb = robotsOf(m);
  const extra = [
    ...(checks?.seen ? [{ key: "check", label: "Check", sortable: false, fmt: (_, x) => badge(checks.byName[x.k]), csv: (x) => badgeOf(checks.byName[x.k]) || "" }] : []),
    ...(rb.size ? [{ key: "robots", label: "robots.txt", sortable: false, fmt: (_, x) => robotsBadge(rb.get(x.k)), csv: (x) => robotsWords(rb.get(x.k)) }] : []),
  ];
  out.push(h("section", { class: "s" }, h("h2", null, "AI collecting for training, by name"),
    h("p", { class: "sub" }, "Pages fetched to train a model or feed AI search. To let one in or keep it out, see ", tabLink(s, "rules", "Crawler rules"), "."),
    countGrid("aicrawl", t.engines?.training, { caption: "AI crawlers collecting for training", file: fileName("ai-training-crawlers", r), key: "Crawler", value: "Fetches", drill: "bot", extra, empty: "No training crawls in this range." })));
  out.push(formatsSection(t, r, "training", { who: "AI crawlers", file: "ai-training-fetch" }));

  const searchRows = ranked(t.search_engines);
  out.push(h("section", { class: "s" }, h("h2", null, "Search engines"),
    countGrid("aisearch", t.search_engines, { caption: "Search engines", file: fileName("search-engines", r), key: "Crawler", value: "Fetches", drill: "bot", empty: "No search crawlers in this range." }),
    searchRows.some(([name]) => ADS.test(name)) ? h("p", { class: "note" }, "Ads quality checks are Google's ad systems checking ad landing pages. They are in the search group but not in the indexing figure.") : null));
  out.push(h("section", { class: "s" }, h("h2", null, "Bots and scanners by name"),
    countGrid("aibots", t.bot_agents, { caption: "Bots and scanners", file: fileName("bots", r), key: "What", value: "Requests", drill: "bot", empty: "No bots in this range." })));
  // What each one costs (crawler_cost.json): training AI, search engines, bots.
  out.push(costSection(m, s, r, { id: "crawlers", groupCol: true,
    sub: "Per crawler: requests, bytes the server sent, its time per request, failed requests, distinct paths and how often it fetched them again. Select a name for its detail.",
    keep: (g, name, e) => g !== "answer_engines" || e.tier !== "asked" }));
  out.push(verifySection(m, r));
  return out;
}
