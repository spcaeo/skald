// Per-page figures over a period (release 2: skald/webapp/js/page-figs.js) and the
// cards and columns drawn from them: the sums over whole days only (a day not recorded is
// counted apart, never as zero), "Work on the page, or on traffic?" and its thresholds,
// the "Needs work" and Rising / Falling orders, AI reads by page now against before, the
// "New and updated pages" card and Summary's key figures and "What changed".
//
//   node tests/js/page-work.mjs        (tests/test_navigate_js.py runs it)
//
// Example data only: made-up paths and figures.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, hash) { location.hash = hash; }, replaceState(_, __, hash) { location.hash = hash; }, back() {}, go() {} };
location.hash = "#overview/summary?range=7d";

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const F = await import(new URL("page-figs.js", JS));
await import(new URL("sections.js", JS));
const { setContext } = await import(new URL("tabs/common.js", JS));
const { workCard } = await import(new URL("tabs/ov-work.js", JS));
const { freshCard } = await import(new URL("tabs/ov-fresh.js", JS));
const { whatChanged, changeRows, sayWhat } = await import(new URL("tabs/ov-changed.js", JS));
const { keyTiles } = await import(new URL("tabs/ov-tiles.js", JS));
const { aiTrend } = await import(new URL("tabs/ai-trend.js", JS));
const C = await import(new URL("mode-compare.js", JS));
const D = await import(new URL("data.js", JS));

// [visits, one_page, views, search, ai]
const L = (pages, folded = 0) => ({ fields: ["visits", "one_page", "views", "search", "ai"], top: 200, folded, pages });
const Fx = (paths, folded = 0) => ({ paths, folded });
const pt = {
  first_day: "2026-10-20",
  days: [
    { day: "2026-10-18", state: "ok", landings: null, fetches: null },                                  // before landings were kept
    { day: "2026-10-19", state: "partial", landings: L({ "/a/": [50, 50, 50, 0, 0] }), fetches: null }, // partial: never added
    { day: "2026-10-20", state: "ok", landings: L({ "/a/": [8, 8, 8, 0, 0], "/b": [3, 3, 3, 3, 0], "/c/": [4, 1, 9, 1, 1] }), fetches: Fx({ "/c/": { "chatgpt.com": 2 } }) },
    { day: "2026-10-21", state: "ok", landings: L({ "/a/": [4, 3, 5, 0, 0], "/b": [2, 2, 2, 1, 0], "(all others)": [1, 1, 1, 0, 0] }, 1), fetches: Fx({ "/c/": { "chatgpt.com": 1, "claude.ai": 1 }, "/a/": { "perplexity.ai": 1 } }) },
  ],
  today: { state: "ok", landings: L({ "/a/": [1, 1, 1, 0, 0] }), fetches: Fx({ "/c/": { "chatgpt.com": 5 } }) },
  changed: { days: 30, since: "2026-09-22", until: "2026-10-21", pages: [
    { path: "/c/", changed: "2026-10-20", source: "sitemap", visits: 5, search: 1, first_search: "2026-10-20", counted_from: "2026-10-20", unmeasured: 0, at_least: false, google: true, google_last: "2026-10-21" },
    { path: "/new/", changed: "2026-10-21", source: "sitemap", visits: 0, search: 0, first_search: null, counted_from: "2026-10-21", unmeasured: 0, at_least: true, google: false, google_last: null },
  ], counts: { pages: 2, measured: 2, visited: 1, searched: 1, none: 1, google: 1 } },
  same_day: null,
};
const range = (days) => ({ kind: "history", first: days[0].day, last: days[days.length - 1].day, length: days.length, days });

{
  const r = range([{ day: "2026-10-18", state: "ok" }, { day: "2026-10-19", state: "partial" }, { day: "2026-10-20", state: "ok" }, { day: "2026-10-21", state: "ok" }]);
  const s = F.pageSums(pt, r);
  assert.equal(s.of, 3);                      // whole days only
  assert.equal(s.days, 2);                    // 18 Oct: not recorded, counted apart
  assert.deepEqual(s.missing, ["2026-10-18"]);
  assert.equal(s.fetchDays, 2);
  assert.equal(s.folded, true);
  assert.deepEqual([s.rows["/a/"].visits, s.rows["/a/"].one_page, s.rows["/a/"].views], [12, 11, 13]);   // never the partial 19 Oct
  assert.deepEqual(s.rows["/c/"].fetches, { "chatgpt.com": 3, "claude.ai": 1 });
  assert.equal(s.rows["/c/"].reads, 4);
  assert.equal(F.leftShare(s.rows["/a/"]).toFixed(3), (11 / 12).toFixed(3));
  assert.equal(F.perVisit(s.rows["/c/"]), 9 / 4);
  // Today (Include today): the live block counts as one more day.
  const ri = range([{ day: "2026-10-20", state: "ok" }, { day: "2026-10-21", state: "ok" }, { day: "2026-10-22", state: "ok", live: true }]);
  const si = F.pageSums(pt, ri);
  assert.equal(si.rows["/a/"].visits, 13);
  assert.equal(si.rows["/c/"].reads, 9);
  // A page group, or no file: null, never zeros.
  assert.equal(F.pageSums({ whole_site_only: true }, r), null);
  assert.equal(F.pageSums(null, r), null);
  assert.equal(F.pageSums(pt, { kind: "today", days: [] }), null);

  // The work lists: /a/ has 12 visits, 92% left at once, no lead: improve. /b: 4 from search, all left: both.
  const w = F.workLists(s, { "/c/": 1 });
  assert.deepEqual(w.improve.map((x) => x.path), ["/a/"]);
  assert.deepEqual(w.both.map((x) => x.path), ["/b"]);
  // A lead from /a/ takes it off "Improve the page"; leads not recorded keep it, said so.
  assert.deepEqual(F.workLists(s, { "/a/": 1 }).improve, []);
  assert.equal(F.workLists(s, null).improve[0].leads, null);
  // Under 10 visits: not judged.
  assert.equal(F.workScore({ visits: 9, left: 1 }), null);
  assert.ok(F.workScore({ visits: 12, left: 0.95 }) > F.workScore({ visits: 400, left: 0.9 }));
  // The sorts: Rising and Falling need Compare.
  assert.deepEqual(F.sortOf("rising", true), { key: "d", dir: "desc" });
  assert.deepEqual(F.sortOf("falling", true), { key: "d", dir: "asc" });
  assert.equal(F.sortOf("rising", false).fallback, true);
  assert.deepEqual(F.sortOf("changed", false), { key: "chg", dir: "desc" });
  assert.deepEqual(F.sortOf("", false), { key: "v", dir: "desc" });
  // AI reads, now against before; a before not recorded is null, never 0.
  const a = F.pageSums(pt, range([{ day: "2026-10-21", state: "ok" }]));
  const b = F.pageSums(pt, range([{ day: "2026-10-20", state: "ok" }]));
  const t = F.readsTrend(a, b);
  assert.deepEqual(t.map((x) => [x.path, x.now, x.before]), [["/c/", 2, 2], ["/a/", 1, 0]]);
  const none = F.readsTrend(a, F.pageSums(pt, range([{ day: "2026-10-18", state: "ok" }])));
  assert.ok(none.every((x) => x.before === null));
  assert.equal(F.pageKey("/b?x=1"), "/b/");
}

// ---- the cards, drawn ------------------------------------------------------------------
(await import(new URL("urlactions.js", JS))).setSiteBase("example.com");
const day =(d, readers, by) => ({ day: d, state: "ok", readers, views: readers * 2, visits: readers, cited: 1, cited_by: { "chatgpt.com": 1 }, returning: { returning: 3 },
  by: { source: by, landing: { "/a/": readers - 2, "/b": 2 } } });
const byDay = new Map([day("2026-10-14", 125, { "Search engine": 8, "Direct or unknown": 117 }), day("2026-10-20", 30, { "Search engine": 5, "Direct or unknown": 25 }),
  day("2026-10-21", 75, { "Search engine": 5, "Direct or unknown": 70 })].map((d) => [d.day, d]));
const m = { today: "2026-10-22", anchor: "2026-10-21", firstDay: "2026-10-14", byDay, site: "example.com", views: [], x: { page_trends: pt, page_index: { pages: [] } }, live: null };
{
  const s = { tab: "overview/summary", range: "yesterday", cmp: "prev", view: "all", inc: "" };
  setContext(m, s);
  const r = D.rangeOf(m, s), t = D.total(r.days), c = C.compareOf(m, s);
  assert.equal(c.ok, true);
  const [cap, tiles] = keyTiles(m, s, r, t, c);
  assert.equal(cap, null, "with Compare on, each tile says its change: no caption (2.42)");
  const text = tiles.textContent;
  assert.match(text, /People\s*i?75▲ 150% · before: 30/);
  assert.match(text, /From search engines\s*i?5≈ about the same · before: 5/);
  assert.equal(tiles.querySelectorAll(".tile").length, 5);
  // Compare off: no change line at all.
  const off = keyTiles(m, { ...s, cmp: "" }, r, t, C.compareOf(m, { ...s, cmp: "" }))[1].textContent;
  assert.doesNotMatch(off, /before:|▲|▼/);
  // 7 days: before not measured, never a 0 or a rise.
  const s7 = { ...s, range: "7d" };
  const r7 = D.rangeOf(m, s7), c7 = C.compareOf(m, s7);
  const t7 = keyTiles(m, s7, r7, D.total(r7.days), c7)[1].textContent;
  assert.match(t7, /before: not measured/);
  assert.doesNotMatch(t7, /▲|before: 0/);
  const wc = whatChanged(m, s7, r7, D.total(r7.days), c7).textContent;
  assert.match(wc, /Before: not measured/);
  const wcy = whatChanged(m, s, r, t, c).textContent;
  assert.match(wcy, /More people than the period before: 75 against 30\./);
  assert.match(wcy, /≈ about the same/);
  assert.match(wcy, /Now.*Before.*Change/);
  assert.deepEqual(changeRows({ x: 1, y: 9 }, { y: 2, z: 4 }).map((x) => x.k), ["y", "z", "x"]);
  assert.equal(sayWhat(10, 9, []), "About as many people as the period before: 10 against 9.");

  const wk = workCard(m, { ...s, range: "7d" }, r7, D.total(r7.days));
  assert.match(wk.textContent, /Left at once: the visit loaded that one page and no other/);
  assert.match(wk.textContent, /Improve the page/);
  assert.ok(wk.querySelector(".ua"), "a path shown has copy and open");
  // Owner's rule (2026-10-25): every path or URL a new card or column shows has copy and
  // open-in-a-new-tab (urlactions.js withUrl), the same look and the green tick.
  const urlIcons = (el, what) => {
    const boxes = [...el.querySelectorAll(".ua")];
    assert.ok(boxes.length, `${what}: its paths have the icons`);
    for (const b of boxes) {
      assert.ok(b.querySelector(".ua-copy"), `${what}: copy`);
      assert.ok(b.querySelector(".ua-open")?.getAttribute("href")?.startsWith("https://example.com/"), `${what}: open, on the site's own address`);
    }
  };
  urlIcons(wk, "Work on the page, or on traffic?");
  urlIcons(freshCard(m, s), "New and updated pages");
  urlIcons(whatChanged(m, s, r, t, c).querySelector(".wc-cols").children[1], "What changed: landing pages");
  urlIcons(aiTrend(m, s7, r7, D.total(r7.days)), "AI reads by page");
  const frEl = freshCard(m, s), fr = frEl.textContent;
  assert.match(fr, /2 pages changed since 22 Sep: 1 had a visit, 1 a visit from search, 1 none yet\. Google fetched 1 of them/);
  assert.ok([...frEl.querySelectorAll("tbody td")].some((td) => td.textContent === "21 Oct"), "the last Google fetch");
  assert.match(fr, /not yet/);
  assert.match(fr, /≥ 0/);                    // a folded day: a floor
  assert.doesNotMatch(fr, /build times/);
  const same = freshCard({ ...m, x: { ...m.x, page_trends: { ...pt, same_day: { day: "2026-10-06", pages: 9, of: 12 } } } }, s).textContent;
  assert.match(same, /Dates look like build times: 9 of the 12 dated pages/);
  const ai = aiTrend(m, s7, r7, D.total(r7.days)).textContent;
  assert.match(ai, /AI reads by page/);
  assert.match(ai, /\/c\/4not measured-chatgpt.com 3 · claude.ai 11/);   // fetches 4, before not measured, 1 AI visit
  assert.match(ai, /Before: not measured/);
  assert.doesNotMatch(ai.split("Leads↕")[1], /▲|▼/);                    // the rows (the header's ▼ is the sort)
  // Yesterday against the day before: both recorded, so a change.
  const ay = aiTrend(m, s, r, t).textContent;
  assert.match(ay, /\/c\/22≈ about the same/);
}

console.log("page-work: all passed");
