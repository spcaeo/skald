// AI & bots > Crawlers (2.7.0): everything that fetches with nobody waiting. AI
// collecting for training, search engines indexing, bots and scanners (scanner
// probes among them), each crawler beside the server's check of its address
// (verified, not verifiable, spoofed), browsers with warning signs, link previews.
//
// Figures are today's, from the same fields: app.json `tiers.training`,
// `engines.training`, `search`, `search_engines`, `hits.bots`, `probes`,
// `bot_agents`, `ai_formats` (What they fetch); bots.json (checks); robots.json (robots.txt column).

import { h, n } from "../ui.js";
import { figures, ranked } from "../data.js";
import { head, nothing, fileName } from "./common.js";
import { verification, verifySection, badge, badgeOf } from "./botverify.js";
import { robotsOf, robotsBadge, robotsWords } from "./robots.js";
import { kpi, tierChart, countGrid, tabLink, formatsSection } from "./ai-parts.js";
import { aiSplit, aiSplitByName, FILE_WORDS } from "./ai-split.js";
import { costSection } from "./crawlercost.js";
import { urlFold } from "../ui/fold.js";

const ADS = /ads quality|AdsBot/i;
const LEDE = "Crawlers with nobody waiting: AI collecting pages for training or AI search, search engines indexing the site, and bots and scanners. A crawler's name is what it calls itself; the server checks the address of the well-known ones. Assistants answering someone's question are on Assistants.";

export default function crawlersTab(m, s, { first }) {
  const { r, t } = figures(m, s);
  const out = [...head("Crawlers", r, LEDE)];
  if (!t) return [...out, nothing(m, r)];
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    trainingKpi(first, t),
    kpi(first, "Search engines", t.search ?? 0, "pages fetched for indexing; ads checks apart", "search_engines"),
    kpi(first, "Bots and scanners", t.hits?.bots ?? 0, "requests: monitors, SEO tools, link previews, probes, and browser-like visits that never rendered the page", "bots", "requests"),
    kpi(first, "of which scanner probes", t.probes ?? 0, "requests hunting for credentials on paths no real site serves", "bots", "requests"))));
  out.push(trainingChart(m, s, r));

  // The AI crawlers by name, with the address check and the robots.txt verdict, as on Assistants.
  const checks = verification(m, r);
  const rb = robotsOf(m);
  const extra = [
    ...(checks?.seen ? [{ key: "check", label: "Check", type: "badge", sortable: false, fmt: (_, x) => badge(checks.byName[x.k]), csv: (x) => badgeOf(checks.byName[x.k]) || "" }] : []),
    ...(rb.size ? [{ key: "robots", label: "robots.txt", type: "badge", sortable: false, fmt: (_, x) => robotsBadge(rb.get(x.k)), csv: (x) => robotsWords(rb.get(x.k)) }] : []),
  ];
  const named = aiSplitByName(t, "training");
  out.push(h("section", { class: "s" }, h("h2", null, "AI collecting for training, by name"),
    h("p", { class: "sub" }, named ? `Pages fetched to train a model or feed AI search; Files: their other requests (${FILE_WORDS}). To let one in or keep it out, see ` : "Requests made to train a model or feed AI search, pages and files together (not told apart for days before 18 Oct 2026). To let one in or keep it out, see ", tabLink(s, "rules", "Crawler rules"), "."),
    named
      ? countGrid("aicrawl", named.pages, { caption: "AI crawlers collecting for training", file: fileName("ai-training-crawlers", r), key: "Crawler", value: "Pages", drill: "bot", extra, files: named.files, empty: "No training crawls in this range." })
      : countGrid("aicrawl", t.engines?.training, { caption: "AI crawlers collecting for training", file: fileName("ai-training-crawlers", r), key: "Crawler", value: "Requests", drill: "bot", extra, empty: "No training crawls in this range." }),
    named && "(all others)" in named.pages ? h("p", { class: "note" }, "Each day keeps the 20 names with the most fetches; the rest are summed in (all others).") : null));

  const searchRows = ranked(t.search_engines);
  out.push(h("section", { class: "s" }, h("h2", null, "Search engines"),
    countGrid("aisearch", t.search_engines, { caption: "Search engines", file: fileName("search-engines", r), key: "Crawler", value: "Fetches", drill: "bot", empty: "No search crawlers in this range." }),
    searchRows.some(([name]) => ADS.test(name)) ? h("p", { class: "note" }, "Ads quality checks are Google's ad systems checking ad landing pages. They are in the search group but not in the indexing figure.") : null));
  out.push(h("section", { class: "s" }, h("h2", null, "Bots and scanners by name"),
    countGrid("aibots", t.bot_agents, { caption: "Bots and scanners", file: fileName("bots", r), key: "What", value: "Requests", drill: "bot", empty: "No bots in this range." })));
  // 2.42 (answer first): what they fetch, what each one costs (crawler_cost.json) and the
  // address check, under one fold kept in the address (crawl_view=open).
  out.push(urlFold("crawl", "Open the details: what they fetch, what each one costs, and the address check", () => [
    formatsSection(t, r, "training", { who: "AI crawlers", file: "ai-training-fetch" }),
    costSection(m, s, r, { id: "crawlers", groupCol: true,
      sub: "Per crawler: requests, bytes the server sent, its time per request, failed requests, distinct paths and how often it fetched them again. Select a name for its detail.",
      keep: (g, name, e) => g !== "answer_engines" || e.tier !== "asked" }),
    verifySection(m, r)], { cls: "ai-details" }));
  return out;
}

/* SKALD-49: pages, with the files beside them; requests when the range cannot split them. */
export function trainingKpi(first, t) {
  const x = aiSplit(t, "training");
  return x
    ? kpi(first, "AI collecting for training", x.pages, `Pages fetched to train a model or feed AI search; nobody is waiting on these. Files: their other requests (${FILE_WORDS}).`, "answer_engines", `pages fetched · + ${n(x.files)} files`)
    : kpi(first, "AI collecting for training", t.tiers?.training ?? 0, "requests, pages and files together (not told apart for days before 18 Oct 2026); nobody is waiting on these", "answer_engines", "requests");
}

/* A day's training pages; null (not known) on a day without the split, so a compared
   day before 18 Oct 2026 is no point on the dashed line, never 0 pages. */
export const trainingPages = (d) => (d.ai_formats ? d.ai_formats.training?.formats?.Page || 0 : null);

/* Pages per day once every day of the range has the split; requests per day otherwise. */
function trainingChart(m, s, r) {
  const split = r.kind === "history" && (r.days || []).filter((d) => d.state === "ok").every((d) => d.ai_formats);
  return split
    ? tierChart(m, s, r, { title: "AI pages fetched for training, per day", name: "Pages", tier: "training", group: "answer_engines", label: "AI pages fetched for training per day", get: trainingPages, unit: "pages" })
    : tierChart(m, s, r, { title: "AI requests for training, per day", name: "Requests", tier: "training", group: "answer_engines", label: "AI requests for training per day", unit: "requests" });
}
