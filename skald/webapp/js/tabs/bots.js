// Bots and AI crawlers: answer engines by name and by why they came (to train,
// or because someone just asked), search engines, and the bots and scanners;
// each crawler beside the site's robots.txt.

import { h, n, counter } from "../ui.js";
import { color, figures, pathMatch, ranked, chartDays } from "../data.js";
import { columns, legend } from "../charts.js";
import { table } from "../table.js";
import { head, nothing, coverageNote, blist, panel, countTable, fileName, compareFor } from "./common.js";
import { verification, verifySection, badge, badgeOf } from "./botverify.js";
import { robotsOf, robotsBadge, robotsWords, robotsSection } from "./robots.js";
import { followedSection } from "./likelyai.js";
import { aiChanges } from "./alerts.js";
import { costSection } from "./crawlercost.js";

const ADS = /ads quality|AdsBot/i;

export default function bots(m, s, { first }) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Bots and AI crawlers", r, "Assistants are split by why they came, because the reasons mean different things: a crawl to train or index has nobody waiting; a fetch for a live question has a person at the other end. Fetched is not read.")];
  // robots.txt keeps its own period (30 days and today), so it shows whatever the range holds.
  if (!t) return [...out, nothing(m, r), robotsSection(m)];
  const k = (label, v, note, g, unit = "requests") => h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note),
    h("div", { class: "k-v" }, first ? counter(v) : n(v)), h("div", { class: "k-c" }, h("span", { class: "sw", style: { background: color(g) } }), unit));
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    k("AI collecting for training", t.tiers?.training ?? 0, "pages fetched; nobody is waiting on these", "answer_engines", "pages fetched"),
    k("AI answering a question now", t.tiers?.asked ?? 0, "pages fetched; someone is waiting on each", "people", "pages fetched"),
    k("Search engines", t.search ?? 0, "pages fetched for indexing; ads checks apart", "search_engines", "pages fetched"),
    k("Bots and scanners", t.hits?.bots ?? 0, "requests: monitors, SEO tools, link previews, probes, and browser-like visits that never rendered the page", "bots"),
    k("of which scanner probes", t.probes ?? 0, "requests hunting for credentials on paths no real site serves", "bots"))));
  if (r.kind === "history" && r.length > 1) {
    const series = [
      { name: "Collecting for training", color: color("answer_engines"), get: (d) => d.tiers?.training || 0 },
      { name: "Answering a question now", color: color("people"), get: (d) => d.tiers?.asked || 0 },
    ];
    const cmp = compareFor(m, s);
    out.push(h("section", { class: "s" }, h("h2", null, "AI pages fetched, per day"), cmp.note,
      h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"], ...cmp.legend]),
        columns(chartDays(r), series, { label: "AI fetches per day by tier", unit: "fetches", H: 220, prev: cmp.prev }))));
  }
  const rows = [
    ...ranked(t.engines?.training).map(([name, v]) => ({ name, why: "collecting for training", v })),
    ...ranked(t.engines?.asked).map(([name, v]) => ({ name, why: "answering a question now", v })),
  ];
  out.push(h("div", { class: "cols" },
    panel("AI collecting for training", "pages fetched; nobody is waiting", blist(ranked(t.engines?.training), { drill: "bot", color: color("answer_engines"), limit: 10, empty: "No training crawls in this range." })),
    panel("AI answering a question now", "pages fetched; someone is waiting on each", blist(ranked(t.engines?.asked), { drill: "bot", color: color("people"), limit: 10, empty: "No assistant fetched a page to answer a question in this range." }))));
  const checks = verification(m, r);
  const rb = robotsOf(m);
  const robotsCol = rb.size ? [{ key: "robots", label: "robots.txt", fmt: (_, x) => robotsBadge(rb.get(x.name)), csv: (x) => robotsWords(rb.get(x.name)) }] : [];
  const checkCol = checks?.seen ? [{ key: "check", label: "Check", fmt: (_, x) => badge(checks.byName[x.name]), csv: (x) => badgeOf(checks.byName[x.name]) || "" }] : [];
  out.push(h("section", { class: "s" }, h("h2", null, "AI assistants by name"),
    table([{ key: "name", label: "Assistant", drill: "bot" }, ...checkCol, ...robotsCol, { key: "why", label: "Why it came" }, { key: "v", label: "Fetches", num: true }],
      { caption: "AI assistants by name and tier", rows, file: fileName("ai-assistants", r), empty: "No answer engines in this range." })));
  out.push(followedSection(m, r));
  out.push(aiChanges(m));
  const searchRows = ranked(t.search_engines);
  out.push(h("div", { class: "cols" },
    h("section", { class: "s" }, h("h2", null, "Search engines"),
      countTable(t.search_engines, { caption: "Search engines", file: fileName("search-engines", r), key: "Crawler", value: "Fetches", empty: "No search crawlers in this range.", drill: "bot" }),
      searchRows.some(([name]) => ADS.test(name)) ? h("p", { class: "note" }, "Ads quality checks are Google's ad systems checking ad landing pages. They are in the search group but not in the indexing figure.") : null),
    h("section", { class: "s" }, h("h2", null, "Bots and scanners by name"),
      countTable(t.bot_agents, { caption: "Bots and scanners", file: fileName("bots", r), key: "What", value: "Requests", empty: "No bots in this range.", drill: "bot" }))));
  out.push(h("section", { class: "s" }, h("h2", null, "Pages AI assistants fetched"),
    countTable(t.ai_pages, { caption: "Pages AI assistants fetched", file: fileName("ai-pages", r), key: "Page", value: "Fetches", keep: pathMatch(s), path: true, empty: "No answer-engine fetches.", drill: "path" })));
  out.push(costSection(m, s, r, { id: "all", groupCol: true,
    sub: "Per assistant, crawler and bot: requests, bytes the server sent, its time per request, failed requests, distinct paths and how often it fetched them again." }));
  out.push(verifySection(m, r));
  out.push(robotsSection(m));
  out.push(coverageNote(cov, r));
  return out;
}
