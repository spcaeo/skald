// SKALD-49: AI fetches as pages, with files counted apart (js/tabs/ai-split.js). The figures that
// say "pages" count pages only (ai_formats "Page"); robots.txt, sitemaps, llms.txt, images,
// styles and scripts are one "files" number beside them, and pages + files is the tier's
// requests. A range with a day before the split says "requests", never a page count of some days.
// The AI feed lists pages only and says how many file fetches it left out.
//
//   node tests/js/ai-pages-files.mjs        (tests/test_navigate_js.py runs it)
//
// Example data only: made-up names, paths and figures.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "ai", name: "AI & bots", tabs: [{ route: "ai/crawlers", name: "Crawlers" }] }]);
location.hash = "#ai/crawlers";
const X = await import(new URL("tabs/ai-split.js", JS));
const P = await import(new URL("tabs/ai-parts.js", JS));
const C = await import(new URL("tabs/ai-crawlers.js", JS));
const T = await import(new URL("tabs/tiles.js", JS));
const F = await import(new URL("tabs/aifeed.js", JS));
const text = (el) => (el == null ? "" : el.textContent);

// ---- the split: pages + files = the tier's requests
const formats = { training: { formats: { Page: 14, "robots.txt": 13, Sitemap: 9, "Other file": 41 },
  by_name: { ClaudeBot: { Page: 14, "robots.txt": 4, "Other file": 41 }, GPTBot: { "robots.txt": 9, Sitemap: 9 } } },
  asked: { formats: {}, by_name: {} } };
const t = { tiers: { training: 77, asked: 0 }, ai_formats: formats, engines: { training: { ClaudeBot: 59, GPTBot: 18 } } };
assert.deepEqual(X.aiSplit(t, "training"), { pages: 14, files: 63, requests: 77 });
assert.deepEqual(X.aiSplitByName(t, "training"), { pages: { ClaudeBot: 14, GPTBot: 0 }, files: { ClaudeBot: 45, GPTBot: 18 } });
assert.equal(X.aiSplit({ ...t, unmeasured: { ai_formats: 3 } }, "training"), null, "a day without the split: no page count");
assert.equal(X.aiSplit({ tiers: { training: 5 } }, "training"), null);
assert.equal(X.filesWords({ files: 1 }, String), "+ 1 file (robots.txt, sitemaps, llms.txt, images, styles and scripts)");

// ---- the Crawlers figure: pages, files beside them; requests without the split
let k = C.trainingKpi(false, t);
assert.equal(text(k.querySelector(".k-v")), "14");
assert.equal(text(k.querySelector(".k-c")), "pages fetched · + 63 files", "the files are on the card, not only in its (i)");
assert.match(text(k.querySelector(".k-n")), /Files: their other requests \(robots\.txt/);
k = C.trainingKpi(false, { ...t, unmeasured: { ai_formats: 2 } });
assert.equal(text(k.querySelector(".k-v")), "77");
assert.match(text(k.querySelector(".k-c")), /^requests$/);
assert.match(text(k.querySelector(".k-n")), /not told apart for days before 18 Oct 2026/);

// ---- the table by name: Pages, then Files; a crawler with files only still has its row
const named = X.aiSplitByName(t, "training");
const tbl = P.countGrid("aicrawl", named.pages, { caption: "c", file: "f", key: "Crawler", value: "Pages", files: named.files });
const heads = tbl.querySelectorAll("th").map(text).map((s) => s.replace(/[↕▾▴▼▲]/g, "").trim());
assert.deepEqual(heads.slice(0, 4), ["Crawler", "Pages", "Files", "Share"]);
const body = tbl.querySelectorAll("tbody tr").map((tr) => tr.querySelectorAll("td").map(text));
assert.deepEqual(body.map((r) => r.slice(0, 3)), [["ClaudeBot", "14", "45"], ["GPTBot", "0", "18"]]);
// Without `files` the old table: rows with a count only.
assert.equal(P.countGrid("x", { A: 0, B: 2 }, { caption: "c", file: "f", key: "K", value: "V" }).querySelectorAll("tbody tr").length, 1);

// ---- Overview's "Who else came": pages, + files
let o = text(T.others(t));
assert.match(o, /AI collecting for training14pages fetched, \+ 63 files/);
o = text(T.others({ ...t, unmeasured: { ai_formats: 1 } }));
assert.match(o, /AI collecting for training77requests/);

// ---- the feed: pages only; files left out, and counted
const ev = (at, name, kind, path, extra = {}) => ({ at: `2026-11-23T${at}-05:00`, name, kind, path, status: 200, country: "US", ip: "192.0.2.7", repeat: false, times_seen_30d: 1, first_seen: "2026-11-23", ...extra });
const events = [
  ev("02:02:57", "ClaudeBot", "training", "/_astro/monday-com-vs-bonterra.jpg"),
  ev("02:02:56", "ClaudeBot", "training", "/robots.txt"),
  ev("02:01:00", "ClaudeBot", "training", "/blog/monday-com-review/"),
  ev("02:00:05", "Claude-User", "asked", "/css/site.css", { role: "file", of: "/pricing/" }),
  ev("02:00:00", "Claude-User", "asked", "/pricing/", { role: "read", of: "/pricing/" }),
  ev("01:59:00", "ChatGPT", "referred", "/features/"),
];
const feed = F.aiFeed({ x: { ai_activity: { today: { events, total: 6 } } }, today: "2026-11-23" }, { limit: 12 });
const items = feed.querySelectorAll("ul.feed li");
assert.deepEqual(items.map((li) => text(li.querySelector(".f-p")).split(" ·")[0].trim()), ["/blog/monday-com-review/", "/pricing/", "/features/"]);
assert.match(text(items[1]), /with 1 file its page loaded/, "a read keeps its folded file");
assert.match(text(feed.querySelector(".f-files")), /^2 file fetches among these not listed \(robots\.txt/);
assert.match(text(feed.querySelector(".tbl-count")), /^4 of 6 latest/);

// ---- the drawer's breadcrumbs: whole names up to 80 characters, then "…" and the name on hover
const DV = await import(new URL("drillview.js", JS));
const long = "Bot or crawler: " + "x".repeat(70);
assert.deepEqual(DV.crumbWords("Bot or crawler: Claude-User"), { text: "Bot or crawler: Claude-User", title: null });
assert.deepEqual(DV.crumbWords("y".repeat(80)), { text: "y".repeat(80), title: null }, "80 characters: whole");
const cut = DV.crumbWords(long);
assert.equal([...cut.text].length, 80);
assert.ok(cut.text.endsWith("…"));
assert.equal(cut.title, long, "the whole name on hover");

// ---- the drawer's request list: one shared rule is said once, above the rows
const row = (rule) => ({ row: { rule }, again: 0, files: [] });
let sr = DV.sharedRule([row("AI training: GPTBot"), row("AI training: GPTBot")], "GPTBot");
assert.deepEqual([sr.head, sr.row("AI training: GPTBot")], ["AI training: GPTBot", ""], "the same rule: once above, rows say nothing more");
sr = DV.sharedRule([row("AI asked: Claude-User"), row("AI page file: Claude-User")], "Claude-User");
assert.deepEqual([sr.head, sr.row("AI asked: Claude-User"), sr.row("AI page file: Claude-User")], [null, "AI asked", "AI page file"], "the bot's own drawer: rows keep only their kind");
sr = DV.sharedRule([row("AI asked: Claude-User"), row("AI page file: Claude-User")]);
assert.deepEqual([sr.head, sr.row("AI asked: Claude-User")], [null, "AI asked: Claude-User"], "not a bot's drawer (a page's): the whole rule, it says who");
sr = DV.sharedRule([row("AI training: GPTBot")], "GPTBot");
assert.deepEqual([sr.head, sr.row("AI training: GPTBot")], [null, "AI training"], "one row: its kind in the bot's own drawer");
assert.equal(DV.sharedRule([row(""), row("")]).head, null);

// ---- the chart's Compare line: a compared day before the split is no point, never 0 pages
const Ch = await import(new URL("charts.js", JS));
assert.equal(C.trainingPages({ ai_formats: formats }), 14);
assert.equal(C.trainingPages({ ai_formats: { asked: { formats: {} } } }), 0, "split, no training: 0 pages");
assert.equal(C.trainingPages({ tiers: { training: 40 } }), null, "no split that day: not known");
const shown = [{ day: "2026-11-01", state: "ok" }, { day: "2026-11-02", state: "ok" }, { day: "2026-11-03", state: "before" }];
const was = { "2026-11-01": { tiers: { training: 40 } }, "2026-11-02": { tiers: { training: 30 }, ai_formats: { training: { formats: { Page: 3 } } } } };
const prevOf = (d) => was[d.day];
assert.deepEqual(Ch.ghostValues(shown, [{ get: C.trainingPages }], prevOf), [null, 3, null], "18 Oct and after: pages; before: none");
assert.deepEqual(Ch.ghostValues(shown, [{ get: (d) => d.tiers?.training || 0 }], prevOf), [40, 30, null], "a getter that never says null: as before");

console.log("ai-pages-files: all passed");
