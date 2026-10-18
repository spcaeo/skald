// The palette's search in the figures (js/finder.js): the names a period's days
// hold, found by their words or their stored value, the closest and busiest
// first, each opening its tab with its detail; folded tails and absences never.
// With an app.json (tests/test_navigate_js.py passes the demo's), every name a
// tab lists for the last 30 days is findable by its own words.
//
//   node tests/js/finder.mjs [path/to/app.json]
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { findIndex, find, score, targetOf, personLike, KINDS } from "../../skald/webapp/js/finder.js";

const NAMES = { CA: "Canada", US: "United States", DE: "Germany" };
const say = (dim, v) => (dim === "country" ? NAMES[v] || v : v === "Direct or unknown" ? "Direct" : v);
const days = [
  { pages: { "/pricing/": 9, "/blog/pricing-for-small-teams": 2, "/": 20 }, by: { country: { US: 5, CA: 2, Unknown: 4 }, source: { "Direct or unknown": 6, "Search engine": 3 },
    referrer: { "google.com": 3, "(none)": 6 }, campaign: { "(no campaign tag)": 5, "google / cpc / fall-launch": 2 } }, cited_by: { "claude.ai": 1 },
    engines: { training: { ClaudeBot: 4 }, asked: { "Claude-User": 2 } }, search_engines: { Googlebot: 7 }, bot_agents: { "(all others)": 3 } },
  { pages: { "/pricing/": 1 }, by: { country: { CA: 1 }, city: { "Toronto, Ontario, CA": 3, Unknown: 2 } } },
];

// ---- the index: every name once per kind, summed over the days, no tails or absences
{
  const ix = findIndex(days, say);
  const one = (dim, value) => ix.find((e) => e.dim === dim && e.value === value);
  assert.equal(one("path", "/pricing/").n, 10, "summed over the period's days");
  assert.equal(one("country", "CA").words, "Canada");
  assert.equal(one("country", "Unknown"), undefined, "not recorded is not a place to go");
  assert.equal(one("city", "Toronto, Ontario, CA").tab, "traffic/places", "a city opens Places with its detail");
  assert.equal(one("city", "Unknown"), undefined);
  // Shown by its code, found by its name (owner, 2026-10-18).
  const byCode = findIndex(days, (d, v) => (d === "country" ? { CA: "CAN", US: "USA" }[v] || v : v), (d, v) => (d === "country" ? NAMES[v] || "" : ""));
  assert.equal(find(byCode, "canada")[0].words, "CAN", "the name finds the country, its code is shown");
  assert.equal(one("referrer", "(none)"), undefined);
  assert.equal(one("campaign", "(no campaign tag)"), undefined);
  assert.equal(one("bot", "(all others)"), undefined);
  assert.equal(one("bot", "ClaudeBot").group, "Crawler or bot");
  assert.equal(one("source", "Direct or unknown").words, "Direct", "said as shown, kept as stored");
  assert.deepEqual(new Set(ix.map((e) => e.tab)), new Set(KINDS.filter(([d]) => ix.some((e) => e.dim === d)).map(([, , t]) => t)));
  assert.deepEqual(findIndex([null, undefined, {}], say), []);
}

// ---- finding: "pricing" finds the pages (the review's "Nothing matches"), the exact first
{
  const ix = findIndex(days, say);
  assert.deepEqual(find(ix, "pricing").map((e) => e.value), ["/pricing/", "/blog/pricing-for-small-teams"]);
  assert.deepEqual(find(ix, "canada").map((e) => [e.dim, e.value]), [["country", "CA"]], "a country by its name");
  assert.deepEqual(find(ix, "ca").map((e) => e.value).slice(0, 1), ["CA"], "and by its code, the exact match first");
  const claude = find(ix, "claude").map((e) => `${e.dim}:${e.value}`);
  assert.deepEqual(claude, ["bot:ClaudeBot", "bot:Claude-User", "assistant:claude.ai"], "the busiest of equal matches first");
  assert.deepEqual(find(ix, "direct").map((e) => e.value), ["Direct or unknown"]);
  assert.deepEqual(find(ix, "google cpc").map((e) => e.value), ["google / cpc / fall-launch"], "every word must be there");
  assert.deepEqual(find(ix, "nothing like this"), []);
  assert.equal(find(ix, "o", 3).length, 3, "the limit holds");
  assert.equal(score("/pricing/", "/pricing/"), 0);
  assert.equal(score("/pricing/", "/pri"), 1);
  assert.equal(score("/blog/pricing-for-small-teams", "pricing"), 2);
  assert.equal(score("Googlebot", "bot"), 3);
  assert.equal(score("abc", "x"), null);
}

// ---- where each opens: its tab and its detail (the drill trail's own escaping)
{
  assert.deepEqual(targetOf({ dim: "path", value: "/pricing/", tab: "traffic/pages" }), { tab: "traffic/pages", dd: "path:/pricing/" });
  assert.deepEqual(targetOf({ dim: "campaign", value: "a|b 100%", tab: "traffic/sources" }), { tab: "traffic/sources", dd: "campaign:a%7Cb 100%25" });
  for (const q of ["192.0.2.10", "2001:db8::1", "lead@example.com", "#42", "42"]) assert.ok(personLike(q), q);
  for (const q of ["pricing", "claude.ai", "/blog/", "google / cpc"]) assert.ok(!personLike(q), q);
}

// ---- the demo: every name the last 30 whole days list is findable by its words
const file = process.argv[2];
if (file) {
  const app = JSON.parse(readFileSync(file, "utf8"));
  const ok = app.days.filter((d) => d.state === "ok").slice(-30);
  const ix = findIndex(ok, (d, v) => v);
  const pages = new Set(ok.flatMap((d) => Object.keys(d.pages || {})));
  for (const p of pages) assert.ok(find(ix, p, 500).some((e) => e.dim === "path" && e.value === p), p);
  assert.ok(find(ix, "pricing").some((e) => e.value === "/pricing/"), "the demo's /pricing/ is found");
  console.log(`finder: all ${pages.size} pages of the demo's last 30 days found`);
}
console.log("finder: all passed");
