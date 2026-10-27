// Traffic > Search's reports as the page draws them (js/tabs/tr-search-reports.js, from
// search/reports.py's part of search.json): the coverage said plainly (days before the
// history, gaps, provisional, no impressions), why new and lost is not listed, the move
// words, the small position line with its gaps, the drawer's position chart (provisional
// dashed and hollow), every list's state in the address (seopr, senl, sepk, seall: Show
// all), the page each opportunity is linked to, copy icons on queries and pages, and the
// tab's own words when Search Console is connected with no figures.
//
//   node tests/js/search-reports.mjs        (tests/test_search_reports.py runs it)
//
// Example data only: example.com pages, made-up queries.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const R = await import(new URL("tabs/tr-search-reports.js", JS));
const T = await import(new URL("tabs/tr-search.js", JS));
const U = await import(new URL("urlactions.js", JS));
U.setSiteBase("example.com");

const go = (hash) => history.replaceState(null, "", hash);
const q = () => new URLSearchParams(location.hash.split("?")[1] || "");
const text = (el) => el.textContent;
const rowsOf = (el) => el.querySelectorAll("tbody tr");
const buttons = (el) => el.querySelectorAll("button");
const press = (el, words) => { const b = buttons(el).find((x) => text(x).startsWith(words)); assert.ok(b, `a button "${words}"`); b.click(); };

// ---- coverage, plainly
{
  assert.deepEqual(R.coverageLines({ days: 7, stored: 7, before_history: 0, missing: [], provisional: [], history_first: "2026-08-01", empty: false }), [], "a whole, final period says nothing");
  const lines = R.coverageLines({ days: 90, stored: 60, before_history: 29, missing: ["2026-10-04"], provisional: ["2026-10-24", "2026-10-25"], history_first: "2026-08-27", empty: false });
  assert.equal(lines[0], "Only 60 of these 90 days are in the history here: it starts 27 Aug.");
  assert.equal(lines[1], "1 day has no figures: 4 Oct.");
  assert.equal(lines[2], "The newest 2 days (24 Oct to 25 Oct) are provisional: Google may still change them.");
  assert.deepEqual(R.coverageLines({ days: 7, stored: 0, before_history: 7, missing: [], provisional: [] }), ["Search Console has no figures for these days."]);
  assert.match(R.coverageLines({ days: 7, stored: 7, before_history: 0, missing: [], provisional: [], empty: true }).join(" "), /shows no impressions for the site/);
  assert.match(R.coverageLines({ days: 7, stored: 7, before_history: 0, missing: [], provisional: ["2026-10-25"] }, "Bing Webmaster Tools")[0], /25 Oct is provisional: Bing may still change it\./);
}

// ---- new and lost: why not, plainly
{
  assert.equal(R.changesWhy({ state: "ok" }), null);
  assert.match(R.changesWhy({ state: "too_long" }, "16 months"), /longer than the 16 months Search Console keeps/);
  assert.match(R.changesWhy({ state: "no_final" }), /no final day yet/);
  assert.match(R.changesWhy({ state: "short", need_from: "2026-04-18", history_first: "2026-08-01", not_whole: 3 }), /whole days from 18 Apr, and the history here starts 1 Aug \(3 days missing or still provisional\)/);
}

// ---- the move words, never a glyph
{
  assert.equal(R.moveWords(0.54), "up 0.5");
  assert.equal(R.moveWords(-1.27), "down 1.3");
  assert.equal(R.moveWords(0.01), "no change");
  assert.equal(R.moveWords(null), "-");
}

// ---- the small line: a gap breaks it, never drawn as 0
{
  const el = R.spark([3.2, null, 2.9, 2.5]);
  assert.equal((el._html.match(/M/g) || []).length, 2, "a new stroke after the gap");
  assert.ok(el._html.includes("<circle"), "the lone first point has a dot");
  assert.equal(el.getAttribute("aria-label"), "Position from 3.2 to 2.5");
  assert.equal(text(R.spark([null, null])), "-");
}

// ---- the drawer's chart: provisional dashed and hollow; nothing to draw is nothing
{
  const block = { size: 1, buckets: [{ first: "2026-10-23", last: "2026-10-23", provisional: false }, { first: "2026-10-24", last: "2026-10-24", provisional: false }, { first: "2026-10-25", last: "2026-10-25", provisional: true }] };
  const el = R.positionChart(block, { points: [4.1, 3.9, 3.5] });
  assert.ok(el._html.includes('stroke-dasharray="4 4"'));
  assert.ok(el._html.includes('fill="var(--surface)"'), "the provisional point is hollow");
  assert.match(el._html, /from 4\.1 to 3\.5; 1 is the top/);
  assert.equal(R.positionChart(block, { points: [null, null, null] }), null);
}

// ---- a period of search.json, as search/reports.py writes it
const HOST = "https://example.com";
const opp = (query, rule, impressions, clicks, position, page, pages = 1, share = 1) => ({ query, rule, impressions, clicks, ctr: impressions ? Math.round((clicks / impressions) * 1e4) / 1e4 : null, position, page, pages, page_share: page ? share : null });
const many = Array.from({ length: 14 }, (_, i) => opp(`long tail ${String(i).padStart(2, "0")}`, "near", 400 - i, 1, 12 + i / 10, `${HOST}/guides/tail-${i}`));
const period = {
  first: "2026-09-28", last: "2026-10-25",
  query: { rows: [["example", 40, 400, 0.1, 1.2]] },
  opportunities: { days: 28, count: 16, by_rule: { low_ctr: 1, near: 15 }, rules: { many: 140, some: 30, low_ctr: 0.01, high: 8, near: [8, 20] }, pages_from: "2026-10-20", pages_days: 6,
    rows: [opp("robots.txt for ai crawlers", "near", 807, 1, 14.65, null, 0, null), opp("example company", "low_ctr", 696, 2, 4.16, `${HOST}/about/`, 2, 0.8), ...many] },
  changes: { state: "ok", now: { first: "2026-09-27", last: "2026-10-24" }, before: { first: "2026-08-30", last: "2026-09-26" },
    new: { count: 1, clicks: 10, impressions: 249, rows: [["gptbot user agent", 10, 249, 0.0402, 7.58]] },
    lost: { count: 1, clicks: 42, impressions: 1304, rows: [["example beta", 42, 1304, 0.0322, 2.67]] }, queries_now: 22, queries_before: 22, folded_days: 0 },
  positions: { size: 1, buckets: [{ first: "2026-10-24", last: "2026-10-24", days: 1, provisional: false }, { first: "2026-10-25", last: "2026-10-25", days: 1, provisional: true }],
    query: { keys: 120, rows: [{ key: "ai crawler analytics", clicks: 5, impressions: 300, position: 6.1, points: [6.5, 5.7], shown: [150, 150], first: 6.5, last: 5.7, change: 0.8 }] },
    page: { keys: 2, rows: [{ key: `${HOST}/features/`, clicks: 9, impressions: 500, position: 5.0, points: [null, 5.0], shown: [null, 250], first: 5.0, last: 5.0, change: null }] } },
};

// ---- opportunities: the rule in the address, the page linked with copy and open, Show all kept
{
  go("#traffic/search?sesec_view=opps");
  const opened = [];
  const ctx = { open: (kind, key) => opened.push([kind, key]), label: "28 days" };
  let el = R.opportunities(period, ctx);
  assert.equal(text(el.querySelector("h2")), "Opportunities");
  assert.ok(el.querySelector(".ui-help"), "the rules are behind a ?");
  assert.match(text(el), /16 queries: 1 shown a lot but rarely clicked, 15 at positions 8-20\./);
  assert.equal(rowsOf(el).length, 10, "the first 10, then Show all");
  assert.match(text(rowsOf(el)[0]), /robots\.txt for ai crawlers.*Not known/, "a page not known says so, never a guess");
  const first = rowsOf(el)[1];
  assert.match(text(first), /example company/);
  assert.match(text(first), /Rarely clicked/);
  assert.match(text(first), /\/about\//);
  assert.ok(first.querySelector(".ua"), "the query and the page carry their copy (and open) icons");
  first.dispatchEvent(new Event("click"));
  assert.deepEqual(opened, [["query", "example company"]]);
  // Show all: into the address, and back from it
  el.querySelector(".more-rows").click();
  assert.equal(q().get("seall_view"), "opp-all");
  assert.equal(rowsOf(el).length, 16);
  el = R.opportunities(period, ctx);
  assert.equal(rowsOf(el).length, 16, "a link with seall shows every row");
  // the rule: one press, in the address; Show all leaves it
  press(el, "Rarely clicked");
  assert.equal(q().get("seopr_view"), "low_ctr");
  assert.equal(q().get("seall_view"), null);
  assert.equal(rowsOf(el).length, 1);
  el = R.opportunities(period, ctx);
  assert.equal(rowsOf(el).length, 1, "a link keeps the rule");
  press(el, "All");
  assert.equal(q().get("seopr_view"), null, "the default leaves the address clean");
}

// ---- new and lost: in the address; not listed says why
{
  go("#traffic/search?sesec_view=changes");
  const ctx = { open: () => {}, label: "28 days" };
  let el = R.changes(period, ctx);
  assert.match(text(el), /27 Sep to 24 Oct against 30 Aug to 26 Sep: 1 new query, 10 clicks, 249 impressions\./);
  assert.match(text(rowsOf(el)[0]), /gptbot user agent/);
  press(el, "Lost (1)");
  assert.equal(q().get("senl_view"), "lost");
  assert.match(text(el), /1 lost query, 42 clicks, 1,304 impressions before\./);
  assert.match(text(el), /Clicks before/);
  el = R.changes(period, ctx);
  assert.match(text(rowsOf(el)[0]), /example beta/, "a link keeps lost");
  el = R.changes({ ...period, changes: { state: "too_long" } }, { ...ctx, label: "16 months" });
  assert.match(text(el.querySelector(".empty")), /longer than the 16 months/);
  assert.equal(rowsOf(el).length, 0);
}

// ---- positions: plainly an average; queries or pages in the address; a page has its icons
{
  go("#traffic/search?sesec_view=positions");
  const opened = [];
  let el = R.positions(period, { open: (k, key) => opened.push([k, key]), label: "28 days" });
  assert.match(text(el), /Google's position is an average, weighted by impressions; 1 is the top\. One point per day\. The 1 shown most of 120 are tracked\./);
  assert.match(text(rowsOf(el)[0]), /ai crawler analytics.*6\.1.*6\.5.*5\.7.*up 0\.8/);
  press(el, "Pages");
  assert.equal(q().get("sepk_view"), "page");
  assert.match(text(rowsOf(el)[0]), /\/features\//);
  assert.ok(rowsOf(el)[0].querySelector(".ua"));
  rowsOf(el)[0].dispatchEvent(new Event("click"));
  assert.deepEqual(opened, [["page", `${HOST}/features/`]]);
  el = R.positions(period, { open: () => {}, label: "28 days" });
  assert.match(text(rowsOf(el)[0]), /\/features\//, "a link keeps pages");
}

// ---- the drawer finds a row the period's own table does not hold
{
  assert.equal(R.findRow(period, "query", "gptbot user agent").impressions, 249, "a new query");
  assert.equal(R.findRow(period, "query", "long tail 03").position, 12.3, "an opportunity");
  assert.equal(R.findRow(period, "page", `${HOST}/features/`).clicks, 9, "a tracked page");
  assert.equal(R.findRow(period, "query", "never seen"), null);
}

// ---- connected with no figures: said plainly
{
  assert.match(T.noFigures({ status: { note: "Search Console has no data for this property in the last 10 days." } }, "google"), /^Connected\. Search Console has no data .* a few days after it is verified\.$/);
  assert.match(T.noFigures({ status: {} }, "google"), /first figures appear after the first sync/);
  assert.match(T.noFigures({ status: { backfill: { state: "running" } } }, "google"), /history is syncing now/);
  assert.match(T.noFigures({ status: { last_sync: "2026-10-25T10:00:00Z", ok: true } }, "bing"), /Bing Webmaster Tools has no figures for this site yet/);
  assert.match(T.noFigures({ status: { last_sync: "2026-10-25T10:00:00Z", ok: false } }, "google"), /sync is failing/);
}

console.log("search reports: all passed");
