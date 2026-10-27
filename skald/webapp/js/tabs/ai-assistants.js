// AI & bots > Assistants (2.7.0): the AI that works for a person waiting on an answer.
// Answer first (2.42, the UX audit's task 4): three figures with their change, which
// assistants sent people and which read for someone (five each, "Show all"), and one card
// for what to fix, "N pages AI can't read well", with the screen's one primary button (Let AI
// read the site better: tabs/fixit.js, fixit=airead). Everything else (the day chart, the
// tables by name, what AI read before it sent a visitor, the formats, the costs, the pages
// fetched, AI reading changes and the full list of pages AI can't read well) is under one
// fold, "Open the details", drawn when it opens.
// Today (Live): every AI event so far, with its address (aifeed.js), under the answers.
//
// The owner's decision (2026-10-12): AI visits live only here; Traffic links here.
// Figures are today's, from the same fields: app.json `ai_reads` (reads, not requests:
// ai-reads.js), `tiers.asked`, `engines.asked` (requests),
// `cited`, `cited_by`, `ai_pages`; ai_activity.json (likely, feed); bots.json (Check);
// robots.json (robots.txt); alerts.json (AI reading changes); `ai_formats` (What they fetch).

import { h, n, share } from "../ui.js";
import { color, figures, pathMatch, ranked } from "../data.js";
import { table } from "../table.js";
import { head, nothing, blist, fileName, notBuiltNote } from "./common.js";
import { verification, badge, badgeOf } from "./botverify.js";
import { robotsOf, robotsBadge, robotsWords } from "./robots.js";
import { followedSection, readSection, sourcesPanel } from "./likelyai.js";
import { aiChanges } from "./alerts.js";
import { aiFeed } from "./aifeed.js";
import { tierChart, countGrid, tabLink, formatsSection } from "./ai-parts.js";
import { costSection } from "./crawlercost.js";
import { aiTrend } from "./ai-trend.js";
import { notReadWell, readCard } from "./aiready.js";
import { compareOf } from "../mode-compare.js";
import { changeLine } from "./ov-tiles.js";
import { tiles } from "./tiles.js";
import { urlFold } from "../ui/fold.js";
import { help } from "../ui/help.js";
import { showAll } from "../ui/showall.js";
import { readsOf, notYet, requestsWords, READ_WORDS } from "./ai-reads.js";

const LEDE = "AI assistants at work for someone waiting on an answer: the pages they fetched for a question, the visitors who then came from their answers, and changes in how they read the site. Fetched is not read. Crawlers with nobody waiting (training, search, bots) are on Crawlers.";

// The assistants that fetched for a question, by name, with the server's address check and the robots.txt verdict.
function byName(m, s, r, t) {
  const x = readsOf(m, t, r);
  const rows = ranked(t.engines?.asked).map(([name, v]) => ({ name, v, reads: x.known ? x.names[name]?.reads ?? 0 : null, __k: name }));
  const sum = rows.reduce((a, x) => a + x.v, 0);
  const checks = verification(m, r);
  const rb = robotsOf(m);
  const cols = [{ key: "name", label: "Assistant", drill: "bot" },
    ...(checks?.seen ? [{ key: "check", label: "Check", type: "badge", fmt: (_, x) => badge(checks.byName[x.name]), csv: (x) => badgeOf(checks.byName[x.name]) || "" }] : []),
    ...(rb.size ? [{ key: "robots", label: "robots.txt", type: "badge", fmt: (_, x) => robotsBadge(rb.get(x.name)), csv: (x) => robotsWords(rb.get(x.name)) }] : []),
    { key: "reads", label: "Reads", num: true, title: READ_WORDS, fmt: (v) => (v == null ? h("span", { class: "few", title: notYet(x) }, "-") : n(v)) },
    { key: "v", label: "Requests", num: true, title: "Every request, the page's own files and repeats included" },
    { key: "share", label: "Share", num: true, sort: (x) => x.v, fmt: (_, x) => share(x.v, sum), csv: (x) => (share(x.v, sum) ? (x.v / sum).toFixed(4) : "") }];
  return h("section", { class: "s" }, h("h2", null, "Assistants answering a question, by name"),
    h("p", { class: "sub" }, "Pages read for a person's question, by assistant, and every request they made. Check: is the address really theirs. robots.txt: what the site's rules say to it (", tabLink(s, "rules", "Crawler rules"), ").", x.known ? "" : ` ${notYet(x)}.`),
    notBuiltNote(m, "bots", "The Check column"),
    table(cols, { caption: "AI assistants answering a question, by name", rows, file: fileName("ai-assistants", r), sortKey: x.known ? "reads" : "v", empty: "No assistant fetched a page to answer a question in this range." }));
}

/* The three figures, each with its change against the period before (Compare, on by default). */
function aiTiles(m, s, r, t) {
  const c = compareOf(m, s);
  const b = c.ok ? c.bT : null;
  const fmt = (x) => (x == null ? "-" : n(x));
  const tile = (label, v, p, about) => ({ label, value: v, info: about, line: changeLine(c, v, p, fmt) });
  // Reads first, requests as the second, smaller number (ai-reads.js).
  const x = readsOf(m, t, r);
  const bx = b ? readsOf(m, b, c.b || r) : null;
  const read = tile("Pages AI read for someone", x.known ? x.reads : null, bx?.known ? bx.reads : null,
    `Pages an assistant fetched because someone asked it a question just then. ${READ_WORDS} Fetched is not read by a person.`);
  read.line = h("span", { class: "t-c t-wrap" }, x.known ? requestsWords(x) : `${notYet(x)}; ${requestsWords(x)}`, read.line ? [" · ", read.line] : null);
  return h("section", { class: "s" }, tiles([
    tile("Visitors sent by AI", t.cited ?? null, b ? b.cited ?? null : null, "Visitors who followed a link in an AI assistant's answer, counted once per visitor. The true number is higher: many assistants hide the link they came from, and Google AI Overview clicks look like ordinary Google clicks."),
    read,
    tile("AI collecting for training", t.tiers?.training ?? null, b ? b.tiers?.training ?? null : null, "Pages fetched to train a model or feed AI search; nobody is waiting on these. By name on Crawlers."),
  ]));
}

/* A ranked list's first five, then "Show all (N)". */
function shortList(title, about, rows, opts) {
  return h("div", { class: "sheet" }, h("div", { class: "card-h start" }, h("h3", null, title), help(title, { text: about, guide: "ai-and-bots" })),
    rows.length ? showAll((k) => blist(rows, { ...opts, limit: k }), rows.length, { label: title.toLowerCase() }) : h("p", { class: "empty" }, opts.empty));
}

export default function assistants(m, s) {
  const { r, t } = figures(m, s);
  const out = [...head("AI assistants", r, LEDE)];
  if (!t) return [...out, nothing(m, r)];
  out.push(aiTiles(m, s, r, t));
  const x = readsOf(m, t, r);
  out.push(h("div", { class: "cols" },
    shortList("Which assistant sent people", "Visitors who followed a citation, by assistant. Counted once per visitor, so an undercount. Google AI Overview clicks look exactly like ordinary Google clicks and are counted as search.",
      ranked(t.cited_by), { drill: "assistant", color: color("answer_engines"), empty: "Nobody arrived by following an AI citation in this period." }),
    shortList("Which assistant read for someone", `Pages read for a person's question, by assistant. ${READ_WORDS} ${x.known ? "" : `${notYet(x)}: until then this list counts requests. `}The server's address check and the robots.txt verdict for each are in the table under Open the details.`,
      ranked(x.known ? x.byName : t.engines?.asked), { drill: "bot", color: color("answer_engines"), empty: "No assistant fetched a page to answer a question in this period." })));
  out.push(readCard(m, s, { onFix: () => import("./fixit.js").then((x) => x.openFixit("airead", m)) }));
  // Live: every AI event today so far, with its address.
  if (r.kind === "today") {
    out.push(h("section", { class: "s ai-feed" }, h("h2", null, "All AI activity today"),
      h("p", { class: "sub" }, "Every assistant fetch and every visitor an assistant sent, newest first. Training crawls are listed too, marked as such."),
      notBuiltNote(m, "ai_activity", "Today's AI activity"), aiFeed(m, { limit: 6 })));
  }
  // The fold's open state is in the address (ai_view=open); the list's filter (arw) opens it too.
  out.push(urlFold("ai", "Open the details: each day, each assistant, what they read and fetched, what they cost, and AI reading changes", () => details(m, s, r, t), { open: !!s.arw, cls: "ai-details" }));
  return out;
}

function details(m, s, r, t) {
  const out = [];
  out.push(readsOf(m, t, r).known
    ? tierChart(m, s, r, { title: "Pages read to answer a question, per day", name: "Reads", tier: "asked", group: "people", label: "AI reads for a question per day", get: (d) => d.ai_reads?.reads || 0, unit: "reads" })
    : tierChart(m, s, r, { title: "Requests to answer a question, per day", name: "Requests", tier: "asked", group: "people", label: "AI requests for a question per day" }));
  out.push(byName(m, s, r, t));
  // Release 2 (L1): AI reads by page, now against before, followed to visits and leads.
  out.push(aiTrend(m, s, r, t));
  // Release 2 (L2): the pages AI can't read well (ai_ready.json, its own last 30 days).
  out.push(notReadWell(m, s));
  out.push(formatsSection(t, r, "asked", { who: "assistants", file: "ai-assistants-fetch" }));
  out.push(costSection(m, s, r, { id: "assistants", title: "What each assistant costs",
    sub: "Per assistant answering a question: requests, bytes the server sent, its time per request, failed requests, distinct paths and how often it fetched them again. Select a name for its detail.",
    keep: (g, name, e) => g === "answer_engines" && e.tier === "asked" }));
  out.push(h("div", null, notBuiltNote(m, "ai_activity", "Likely from AI assistants"), sourcesPanel(m, r)));
  out.push(followedSection(m, r));
  out.push(readSection(m, r));
  out.push(h("section", { class: "s" }, h("h2", null, "Pages AI assistants fetched"),
    h("p", { class: "sub" }, "Every AI request for a page: for a question, and for training or AI search. Requests, not reads: a page asked for twice in a few seconds counts twice here."),
    countGrid("aipages", t.ai_pages, { caption: "Pages AI assistants fetched", file: fileName("ai-pages", r), key: "Page", value: "Requests", keep: pathMatch(s), drill: "path", empty: "No answer-engine fetches." })));
  out.push(notBuiltNote(m, "alerts", "AI reading changes"), aiChanges(m));
  return out;
}
