// AI & bots > Assistants (2.7.0): the AI that works for a person waiting on an answer.
// Which assistants fetched pages to answer a question, the visitors who followed an
// AI citation, the visits likely sent by an AI answer (inferred, always apart), the
// fetches followed by a visit, the pages assistants fetched, and AI reading changes.
// Today (Live): every AI event so far, with its address (aifeed.js), on top.
//
// The owner's decision (2026-10-12): AI visits live only here; Traffic links here.
// Figures are today's, from the same fields: app.json `tiers.asked`, `engines.asked`,
// `cited`, `cited_by`, `ai_pages`; ai_activity.json (likely, feed); bots.json (Check);
// robots.json (robots.txt); alerts.json (AI reading changes).

import { h, share } from "../ui.js";
import { color, figures, pathMatch, ranked } from "../data.js";
import { table } from "../table.js";
import { head, nothing, blist, panel, fileName, notBuiltNote } from "./common.js";
import { verification, badge, badgeOf } from "./botverify.js";
import { robotsOf, robotsBadge, robotsWords } from "./robots.js";
import { followedSection, sourcesPanel } from "./likelyai.js";
import { aiChanges } from "./alerts.js";
import { aiFeed } from "./aifeed.js";
import { kpi, tierChart, countGrid, tabLink } from "./ai-parts.js";

const LEDE = "AI assistants at work for someone waiting on an answer: the pages they fetched for a question, the visitors who then came from their answers, and changes in how they read the site. Fetched is not read. Crawlers with nobody waiting (training, search, bots) are on Crawlers.";

// The assistants that fetched for a question, by name, with the server's address check and the robots.txt verdict.
function byName(m, s, r, t) {
  const rows = ranked(t.engines?.asked).map(([name, v]) => ({ name, v, __k: name }));
  const sum = rows.reduce((a, x) => a + x.v, 0);
  const checks = verification(m, r);
  const rb = robotsOf(m);
  const cols = [{ key: "name", label: "Assistant", drill: "bot" },
    ...(checks?.seen ? [{ key: "check", label: "Check", fmt: (_, x) => badge(checks.byName[x.name]), csv: (x) => badgeOf(checks.byName[x.name]) || "" }] : []),
    ...(rb.size ? [{ key: "robots", label: "robots.txt", fmt: (_, x) => robotsBadge(rb.get(x.name)), csv: (x) => robotsWords(rb.get(x.name)) }] : []),
    { key: "v", label: "Fetches", num: true },
    { key: "share", label: "Share", num: true, sort: (x) => x.v, fmt: (_, x) => share(x.v, sum), csv: (x) => (share(x.v, sum) ? (x.v / sum).toFixed(4) : "") }];
  return h("section", { class: "s" }, h("h2", null, "Assistants answering a question, by name"),
    h("p", { class: "sub" }, "Pages fetched for a person's question, by assistant. Check: is the address really theirs. robots.txt: what the site's rules say to it (", tabLink(s, "rules", "Crawler rules"), ")."),
    notBuiltNote(m, "bots", "The Check column"),
    table(cols, { caption: "AI assistants answering a question, by name", rows, file: fileName("ai-assistants", r), sortKey: "v", empty: "No assistant fetched a page to answer a question in this range." }));
}

export default function assistants(m, s, { first }) {
  const { r, t } = figures(m, s);
  const out = [...head("AI assistants", r, LEDE)];
  if (!t) return [...out, nothing(m, r)];
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    kpi(first, "AI answering a question now", t.tiers?.asked ?? 0, "pages fetched; someone is waiting on each", "people"),
    kpi(first, "Visitors from AI", t.cited ?? null, "followed a link in an AI answer; counted once per visitor, so an undercount", "answer_engines", "visitors"))));
  // Live: every AI event today so far, with its address, before the day's totals.
  if (r.kind === "today") {
    out.push(h("section", { class: "s ai-feed" }, h("h2", null, "All AI activity today"),
      h("p", { class: "sub" }, "Every assistant fetch and every visitor an assistant sent, newest first. Training crawls are listed too, marked as such."),
      notBuiltNote(m, "ai_activity", "Today's AI activity"), aiFeed(m, { limit: 12 })));
  }
  out.push(tierChart(m, s, r, { title: "Pages fetched to answer a question, per day", name: "Answering a question now", tier: "asked", group: "people", label: "AI fetches for a question per day" }));
  out.push(byName(m, s, r, t));
  out.push(h("div", { class: "cols" },
    panel("AI assistants that sent visitors", "Visitors who followed a citation, by assistant. Counted once per visitor; undercounts.",
      blist(ranked(t.cited_by), { drill: "assistant", color: color("answer_engines"), empty: "Nobody arrived by following an AI citation in this range." }),
      h("p", { class: "note" }, "Google AI Overview clicks look exactly like ordinary Google clicks and are counted as search.")),
    h("div", null, notBuiltNote(m, "ai_activity", "Likely from AI assistants"), sourcesPanel(m, r))));
  out.push(followedSection(m, r));
  out.push(h("section", { class: "s" }, h("h2", null, "Pages AI assistants fetched"),
    h("p", { class: "sub" }, "Every AI fetch by page: for a question, and for training or AI search."),
    countGrid("aipages", t.ai_pages, { caption: "Pages AI assistants fetched", file: fileName("ai-pages", r), key: "Page", value: "Fetches", keep: pathMatch(s), drill: "path", empty: "No answer-engine fetches." })));
  out.push(notBuiltNote(m, "alerts", "AI reading changes"), aiChanges(m));
  return out;
}
