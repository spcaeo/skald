// AI & bots > Crawl health: what each crawler fetched beside the site's sitemap, and
// the problems crawlers hit. Coverage cards per crawler (Google, Bing, each AI
// crawler and user fetcher), sitemap pages a crawler never fetched (orphans), pages
// fetched that the sitemap does not list, 404s and 410s, 5xx, redirects, slow and
// large answers, and the daily trend.
//
// From crawl_health.json (crawl_health.py; DATA-CONTRACT-CRAWL-HEALTH.md): the last 7
// or 30 days and today, judged by the sitemap list kept today. Loaded when the tab
// opens. The window and the crawler sit in the address (cw, chb, co); chb, not cb, which is Compare's period B.

import { h, n, short, pct1, stateNote } from "../ui.js";
import { base, getJSON, color } from "../data.js";
import { lines, spark } from "../charts.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { time as tzTime, ago } from "../tz.js";
import * as S from "../state.js";
import { tiles } from "./tiles.js";
import { bytesWords } from "./costsum.js";

const KIND = { search: "Search", ai_training: "AI crawler", ai_asked: "AI user fetcher" };
const INK = { search: color("search_engines"), ai_training: color("answer_engines"), ai_asked: color("answer_engines") };
// The drill-down knows crawlers by the name in their user agent.
const BOT = { Google: "Googlebot", Bing: "bingbot" };
const LEDE = "Which of the site's pages each crawler fetched, which it never did, which pages it fetched that the sitemap does not list, and the pages that answer crawlers with an error, a redirect, slowly or with a large body. Google and Bing, and every AI crawler and AI user fetcher by name.";
const pick = (v, ok, dflt) => (ok.includes(v) ? v : dflt);
const when = (v) => (v ? tzTime(v, { date: true, label: false }) : "-");
const crawlerLink = (name) => link("bot", BOT[name] || name, { text: name });
const byWords = (by, top = 3) => {
  const got = Object.entries(by || {}).sort((a, b) => b[1] - a[1]);
  return got.slice(0, top).map(([k, v]) => `${k} ${n(v)}`).join(", ") + (got.length > top ? `, +${got.length - top} more` : "");
};

const head = () => [h("div", { class: "head" }, h("h1", null, "Crawl health")), h("p", { class: "sub ai-lede" }, LEDE)];

export default function crawlHealth(m, s) {
  const holder = h("div", { class: "ch-tab" }, h("p", { class: "empty" }, "Loading crawl health…"));
  if (Array.isArray(m.files) && !m.files.includes("crawl_health") && !m.files.includes("crawl_health.json")) {
    holder.replaceChildren(stateNote("Crawl health is not written beside this page yet. It is counted from the next collected day on."));
  } else {
    getJSON(`${base(s.view)}crawl_health.json`).then((f) => {
      if (!f) holder.replaceChildren(stateNote("Crawl health is not written beside this page yet."));
      else if (f.state === "error") holder.replaceChildren(stateNote(`crawl_health.json could not be built on the last redraw: ${f.error || "no reason given"}.`, true));
      else holder.replaceChildren(...draw(f, s).filter(Boolean));
    }).catch((e) => holder.replaceChildren(stateNote(`Crawl health could not be loaded: ${e.message || e}.`, true)));
  }
  return [...head(), holder];
}

/* ---------------------------------------------------------------- the sitemap */
function sitemapLine(sm) {
  if (!sm.enabled) return stateNote("The sitemap is not read: crawl_health.sitemap is off in the settings. The problems below still count; coverage and orphans need the sitemap.");
  if (sm.paths == null) {
    return h("div", { class: "state ch-empty", role: "status" }, h("div", null,
      h("strong", null, "No sitemap found yet, so coverage and orphans cannot be counted. "),
      sm.error ? `The last try said: ${sm.error}. ` : "",
      "Skald reads the site's sitemap once a day, as its own check (site-version-check): the files named on robots.txt's Sitemap: lines, and /sitemap.xml on the site's own host. To add one:",
      h("ol", null,
        h("li", null, "Make a sitemap. Most site builders and CMSs write one (WordPress, Shopify, Webflow, Squarespace); a framework has a plugin (next-sitemap, @astrojs/sitemap, gatsby-plugin-sitemap)."),
        h("li", null, "Publish it on the site's own host, for example ", h("code", null, "https://www.example.com/sitemap.xml"), " (an index, gzip and plain text lists are read too)."),
        h("li", null, "Name it in robots.txt: ", h("code", null, "Sitemap: https://www.example.com/sitemap.xml"), ", or under ", h("code", null, "crawl_health.sitemaps"), " in the config.")),
      "The next live run reads it; coverage counts from the next collected day."));
  }
  const files = (sm.sources || []).map((u) => u.replace(/^https?:\/\/[^/]+/, ""));
  return h("p", { class: "sub ch-sitemap" }, h("b", null, `${n(sm.paths)} pages`), " in the sitemap",
    files.length ? [" (", files.map((x, i) => [i ? ", " : "", h("code", null, x)]), ")"] : "",
    sm.fetched_at ? `, read ${ago(sm.fetched_at)}` : "", ".",
    sm.truncated ? " The list was cut at its size limit." : "",
    sm.skipped ? ` ${n(sm.skipped)} URL${sm.skipped === 1 ? "" : "s"} on other hosts left out.` : "",
    sm.ok === false && sm.error ? ` The last try failed (${sm.error}); the list kept on ${short(sm.day)} is used.` : "");
}

/* ---------------------------------------------------------------- the tab */
function draw(f, s) {
  if (f.whole_site_only) return [stateNote("Crawl health is counted for the whole site. Choose All pages to see it.")];
  const w = pick(s.cw, ["7", "30"], "30");
  const win = f.windows?.[w] || { crawlers: [], unlisted: { rows: [], total: 0 }, problems: {} };
  const sm = f.sitemap || {};
  const names = win.crawlers.map((c) => c.name);
  const cb = pick(s.chb, names, names[0]);
  const days = f.days || [];
  const seg = h("div", { class: "seg plain", role: "group", "aria-label": "Window" },
    [["7", "Last 7 days and today"], ["30", "Last 30 days and today"]].map(([k, words]) =>
      h("button", { type: "button", "aria-pressed": String(k === w), onclick: () => S.set({ cw: k }) }, words)));
  const out = [sitemapLine(sm), h("div", { class: "ch-bar" }, seg,
    h("span", { class: "muted" }, `${n(win.days)} recorded day${win.days === 1 ? "" : "s"} counted, today so far included`))];
  if (!win.crawlers.length) {
    out.push(stateNote("No Google, Bing or AI crawler request in this window yet."));
    return out;
  }
  out.push(cards(win, days, sm));
  out.push(crawlerTable(win, sm, w));
  out.push(trend(days, f.today, cb, names, sm));
  if (f.pages) out.push(orphans(f.pages, cb, names, w, s));
  if (sm.paths != null) out.push(unlisted(win.unlisted, w));
  out.push(problems(win.problems, f, w));
  out.push(h("p", { class: "note" }, `Judged by the sitemap kept ${sm.day ? short(sm.day) : "today"}: a page added since is counted from the day it was listed in. Slow: the server took ${n(f.slow_ms)} ms or more. Large: a body of ${bytesWords(f.large_bytes)} or more. Redirect chains cannot be told from a log (it carries no Location), so each redirect is counted on its own. Every figure is recounted from the raw log by the audit.`));
  return out;
}

const coverageOf = (c) => (c.coverage == null ? null : c.coverage * 100);

function cards(win, days, sm) {
  if (sm.paths == null) return null;            // coverage needs the sitemap: the table below has the rest
  const top = win.crawlers.slice(0, 6);
  return h("section", { class: "s" }, h("h2", null, "Coverage by crawler"),
    h("p", { class: "sub" }, "The share of the sitemap's pages each crawler fetched at least once in this window; the line under it, each recorded day's share. Every crawler is in the table below."),
    tiles(top.map((c) => ({
      label: c.name,
      value: c.coverage == null ? null : `${Math.round(c.coverage * 100)}%`,
      info: c.coverage == null ? "No sitemap list: not recorded." : `${n(c.listed)} of ${n(sm.paths)} sitemap pages fetched${c.folded ? " (at least: a busy day folded its rarest paths)" : ""}.`,
      line: c.coverage == null ? `${KIND[c.kind] || c.kind} · ${n(c.requests)} requests` : `${KIND[c.kind] || c.kind} · ${n(c.listed)} of ${n(sm.paths)} pages, ${n(c.orphans)} never fetched`,
      trend: spark(days.map((d) => { const x = d.crawlers?.[c.name]; return d.crawlers == null ? null : x?.listed == null ? (x ? null : 0) : x.sitemap ? (x.listed / x.sitemap) * 100 : null; }), INK[c.kind]),
    }))));
}

function crawlerTable(win, sm, w) {
  const has = sm.paths != null;
  const cols = [
    { key: "name", label: "Crawler", fmt: (v) => crawlerLink(v), csv: (c) => c.name },
    { key: "kind", label: "Kind", cls: "nowrap", hide: true, fmt: (v) => KIND[v] || v },
    { key: "requests", label: "Requests", num: true },
    ...(has ? [
      { key: "coverage", label: "Coverage", num: true, sort: (c) => c.coverage ?? -1, fmt: (v, c) => (v == null ? "-" : h("span", { title: `${n(c.listed)} of ${n(sm.paths)} sitemap pages` }, pct1(c.listed, sm.paths))), csv: (c) => (c.coverage == null ? "" : c.coverage) },
      { key: "orphans", label: "Never fetched", num: true, title: "Sitemap pages it did not fetch once in this window" },
      { key: "unlisted", label: "Not in sitemap", num: true, title: "Pages it fetched that the sitemap does not list" },
      { key: "per_page", label: "Fetches per page", num: true, fmt: (v) => (v == null ? "-" : v.toFixed(1)), hide: true, title: "Requests per sitemap page it fetched: how often it comes back" },
    ] : []),
    { key: "not_found", label: "404 / 410", num: true },
    { key: "server_errors", label: "5xx", num: true },
    { key: "redirects", label: "Redirects", num: true },
    { key: "last", label: "Last crawl", type: "date", cls: "nowrap", fmt: (v) => when(v) },
  ];
  // Kind and fetches per page start hidden ("Columns" shows them), so the table fits at 1280.
  return h("section", { class: "s" }, h("h2", null, "Each crawler"),
    h("p", { class: "sub" }, "Kind and fetches per page are under Columns. Open a crawler for its detail by day."),
    table(cols, { caption: "Crawl health by crawler", rows: win.crawlers, file: `crawl-health-crawlers-${w}d.csv`, sortKey: "requests", limit: 20, empty: "No crawler in this window." }));
}

function trend(days, today, cb, names, sm) {
  if (sm.paths == null || days.length < 2) return null;
  const sel = h("select", { "aria-label": "Crawler on the chart", onchange: (e) => S.set({ chb: e.target.value }) },
    names.map((k) => h("option", { value: k, selected: k === cb }, k)));
  const kind = days.map((d) => d.crawlers?.[cb]?.kind).find(Boolean) || today?.crawlers?.[cb]?.kind || "search";
  const get = (d) => { const x = d.crawlers?.[cb]; return d.crawlers == null ? null : !x ? 0 : x.listed; };
  const sizes = [...new Set(days.map((d) => d.crawlers && Object.values(d.crawlers)[0]?.sitemap).filter(Boolean))];
  return h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Sitemap pages fetched per day"), sel),
    h("p", { class: "sub" }, `How many of the sitemap's ${sizes.length === 1 ? n(sizes[0]) : "listed"} pages ${cb} fetched each recorded day (30 days). A day with no request from it is 0; a day not recorded is a gap.`),
    h("div", { class: "sheet" }, lines(days, [{ name: `${cb}: sitemap pages fetched`, color: INK[kind], get, area: true }], { label: `${cb}: sitemap pages fetched per day`, H: 200 })));
}

function orphans(pages, cb, names, w, s) {
  const only = s.co !== "all";
  const k = w === "7" ? 0 : 1;
  const rows = pages.rows.map((p) => {
    const c = p.crawls?.[cb];
    return { path: p.path, n7: c ? c[0] : 0, n30: c ? c[1] : 0, last: c ? c[2] : null, others: Object.keys(p.crawls || {}).filter((x) => x !== cb).length, fetched: c ? c[k] : 0 };
  }).filter((r) => !only || !r.fetched);
  const sel = h("select", { "aria-label": "Crawler", onchange: (e) => S.set({ chb: e.target.value }) }, names.map((x) => h("option", { value: x, selected: x === cb }, x)));
  const seg = h("div", { class: "seg plain", role: "group", "aria-label": "Which pages" },
    [["", "Never fetched"], ["all", "Every sitemap page"]].map(([v, words]) =>
      h("button", { type: "button", "aria-pressed": String((s.co === "all" ? "all" : "") === v), onclick: () => S.set({ co: v }) }, words)));
  const cols = [
    { key: "path", label: "Page", path: true, drill: "path" },
    { key: "fetched", label: w === "7" ? "Fetches, 7 days" : "Fetches, 30 days", num: true },
    ...(w === "7" ? [{ key: "n30", label: "Fetches, 30 days", num: true }] : []),
    { key: "last", label: "Last fetched", type: "date", fmt: (v) => (v ? when(v) : h("span", { class: "muted" }, "not in 30 days")), csv: (r) => r.last || "" },
    { key: "others", label: "Other crawlers that fetched it", num: true, title: `How many of the other crawlers fetched it in 30 days` },
  ];
  return h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Sitemap pages and when each was fetched"), sel, seg),
    h("p", { class: "sub" }, only ? `Sitemap pages ${cb} did not fetch in the last ${w} days and today: orphans to it. Link to them from pages it does read, or check they are not blocked.` : `Every sitemap page, with ${cb}'s fetches and its last fetch.`),
    table(cols, { caption: `Sitemap pages, ${cb}`, rows, file: `crawl-health-sitemap-${cb}-${w}d.csv`, sortKey: only ? "others" : "fetched", limit: 15,
      empty: only ? `${cb} fetched every sitemap page in this window.` : "The sitemap is empty.",
      note: pages.total > pages.rows.length ? `The sitemap's ${n(pages.rows.length)} least fetched pages of ${n(pages.total)}.` : null }));
}

function unlisted(u, w) {
  const cols = [
    { key: "path", label: "Page", path: true, drill: "path" },
    { key: "pages", label: "Fetched as a page", num: true },
    { key: "by", label: "By", sortable: false, fmt: (v) => byWords(v), csv: (r) => byWords(r.by, 99) },
    { key: "days", label: "Days", num: true, title: "Days it was fetched on" },
    { key: "last", label: "Last fetched", type: "date", fmt: (v) => when(v) },
  ];
  return h("section", { class: "s" }, h("h2", null, "Fetched but not in the sitemap"),
    h("p", { class: "sub" }, "Pages crawlers fetched (and the site served) that the sitemap does not list. Add the ones people should find; redirect, remove or keep out the rest."),
    table(cols, { caption: "Fetched but not in the sitemap", rows: u.rows, file: `crawl-health-not-in-sitemap-${w}d.csv`, sortKey: "pages", limit: 10, empty: "Every page crawlers fetched is in the sitemap.",
      note: u.total > u.rows.length ? `The ${n(u.rows.length)} most fetched of ${n(u.total)}.` : null }));
}

const PROBLEMS = [
  ["not_found", "Not found (404 and 410)", "Pages crawlers keep asking for that are gone. Redirect the ones with a new home; remove links and sitemap entries to the rest.", "Answered 404 or 410"],
  ["server_errors", "Server errors (5xx)", "The server failed a crawler. Several in a row make crawlers slow down or drop the page.", "Answered 5xx"],
  ["redirects", "Redirects (3xx)", "Crawlers still asking for an old address. Point links and the sitemap at the final address.", "Redirected"],
  ["slow", "Slow for crawlers", "Pages the server took a second or more to answer a crawler.", "Took 1 s or more"],
  ["large", "Large answers", "Bodies of 1 MB or more sent to crawlers.", "1 MB or more"],
];

function problems(p, f, w) {
  const parts = PROBLEMS.map(([key, title, sub, count]) => {
    const got = p[key] || { rows: [], total: 0 };
    const cols = [
      { key: "path", label: "Page", path: true, drill: "path" },
      { key: "n", label: count, num: true },
      { key: "requests", label: "Crawler requests", num: true },
      ...(key === "slow" ? [{ key: "mean_ms", label: "Mean time", num: true, fmt: (v) => (v == null ? "-" : `${n(v)} ms`) }] : []),
      ...(key === "large" ? [{ key: "max_bytes", label: "Largest", num: true, fmt: (v) => bytesWords(v) }] : []),
      { key: "by", label: "Crawlers", sortable: false, fmt: (v) => byWords(v), csv: (r) => byWords(r.by, 99) },
      ...(f.sitemap?.paths != null ? [{ key: "listed", label: "In sitemap", type: "bool", fmt: (v) => (v ? h("span", { class: "rb warn" }, "Listed") : "-"), csv: (r) => (r.listed ? "yes" : "no") }] : []),
      { key: "last", label: "Last crawl", type: "date", cls: "nowrap", fmt: (v) => when(v) },
    ];
    return h("div", { class: "ch-prob" }, h("h3", null, title, h("span", { class: "muted" }, got.total ? ` · ${n(got.total)} page${got.total === 1 ? "" : "s"}` : "")),
      h("p", { class: "sub" }, sub),
      !got.rows.length ? h("p", { class: "empty" }, "None in this window.") : table(cols, { caption: title, rows: got.rows, file: `crawl-health-${key.replace("_", "-")}-${w}d.csv`, sortKey: "n", limit: 8, search: got.rows.length > 8, empty: "None in this window.",
        note: got.total > got.rows.length ? `The ${n(got.rows.length)} biggest of ${n(got.total)}.` : null }));
  });
  return h("section", { class: "s" }, h("h2", null, "Problems crawlers hit"), ...parts);
}
