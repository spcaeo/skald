// Traffic's shared filter (SKALD-62): one Country / Source / Device bar for Visitors, Sources,
// Pages and Places & devices (js/narrow.js, js/tabs/tr-filter.js, tr-narrowed.js).
//
// What is pinned: today's visits split a breakdown only when they give back today's own list
// exactly; the whole days come from the server's compare (its visit records), with B for
// Compare, and an answer that does not add up is withheld; without the server the page works
// them out from its daily cube and leaves browsers, systems and campaigns unsplit; the bar's
// rows count with the other rows' picks; the four tabs sit in one box on the strip, in their
// new order; and each tab draws only the matching visits, saying what it cannot split.
//
//   node tests/js/shared-filter.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
const { TAB } = await import(new URL("sections.js", JS));
const N = await import(new URL("narrow.js", JS));
const { sharedBar } = await import(new URL("tabs/tr-filter.js", JS));
const { tabStrip } = await import(new URL("tabstrip.js", JS));
const { setContext } = await import(new URL("tabs/common.js", JS));
const places = (await import(new URL("tabs/tr-places.js", JS))).default;
const sources = (await import(new URL("tabs/tr-sources.js", JS))).default;
const pages = (await import(new URL("tabs/tr-pages.js", JS))).default;

const go = (hash) => { location.hash = hash; return S.read(); };
const tick = (ms = 10) => new Promise((r) => setTimeout(r, ms));
const text = (x) => [x].flat(Infinity).filter(Boolean).map((e) => (typeof e === "string" ? e : e.textContent)).join(" ");

// ---- the server's compare, stubbed: every request is kept, so the test can read the query.
const asked = [];
let reply = () => null;
globalThis.fetch = async (url) => {
  asked.push(String(url));
  const body = reply(String(url));
  if (body == null) return { status: 404, ok: false, body: { cancel() {} }, headers: { get: () => "" }, json: async () => null };
  return { status: 200, ok: true, headers: { get: () => "application/json" }, json: async () => body };
};

// ---- 1. today's visits: a list is split only when every visit gives back today's own list
const J = (country, source, device, extra = {}) => ({ day: "2026-11-26", country, source, device, browser: "Chrome", os: "Windows", landing: "/", campaign: "", ...extra });
const visits = [J("US", "Direct", "Desktop"), J("US", "Search engine", "Mobile", { browser: "Safari", os: "iOS", landing: "/pricing/" }),
  J("IN", "Direct", "Mobile", { browser: "Safari", os: "iOS" }), J("CA", "Email", "Desktop", { campaign: "newsletter / email / nov" })];
const live = { readers: 4, by: {
  country: { US: 2, IN: 1, CA: 1 }, source: { Direct: 2, "Search engine": 1, Email: 1 }, device: { Desktop: 2, Mobile: 2 },
  browser: { Chrome: 2, Safari: 2 }, os: { Windows: 1, iOS: 2, macOS: 1 },     // os does not match the visits: not split
  campaign: { "(no campaign tag)": 3, "newsletter / email / nov": 1 }, landing: { "/": 3, "/pricing/": 1 } } };
{
  const got = N.fromVisits(live, visits, [["country", "US"]]);
  assert.equal(got.checked, true);
  assert.equal(got.readers, 2, "two visits from the US");
  assert.deepEqual(got.by.source, { Direct: 1, "Search engine": 1 });
  assert.deepEqual(got.by.device, { Desktop: 1, Mobile: 1 });
  assert.deepEqual(got.by.campaign, { "(no campaign tag)": 2 }, "no campaign: the readers' own label");
  assert.equal(got.by.os, null, "a list the visits do not give back exactly is not split");
  assert.equal(got.by.assistant, null, "no assistant list in today's figures: not split");
  const two = N.fromVisits(live, visits, [["country", "US"], ["device", "Mobile"]]);
  assert.equal(two.readers, 1, "the picks cross");
  const short = N.fromVisits({ ...live, readers: 5 }, visits, [["country", "US"]]);
  assert.equal(short.checked, false, "the visits kept are not today's count: nothing is split");
  assert.equal(short.readers, null);
  // The visits sent to the page carry their trail, not a landing field (dashboard_webapp).
  const bare = visits.map(({ landing, ...j }) => ({ ...j, trail: [{ path: landing, page: true }, { path: "/docs/", page: false }] }));
  assert.deepEqual(N.fromVisits(live, bare, [["country", "US"]]).by.landing, { "/": 1, "/pricing/": 1 }, "the landing page from the trail");
  // A pick whose own labels do not give back the day's list: nothing is split, never a guess.
  const off = N.fromVisits({ ...live, by: { ...live.by, device: { Desktop: 3, Mobile: 1 } } }, visits, [["device", "Mobile"]]);
  assert.equal(off.checked, false);
  assert.equal(off.why, "labels");
  // An "(all others)" list still checks: the named entries and the folded rest.
  const folded = N.fromVisits({ ...live, by: { ...live.by, country: { US: 2, "(all others)": 2 } } }, visits, [["device", "Desktop"]]);
  assert.deepEqual(folded.by.country, { US: 1, CA: 1 });
}

// ---- a model: Nov 19 to 25 whole, today live
const day = (d, readers, by) => ({ day: d, state: "ok", readers, visits: readers, views: readers, by });
const DAYS = ["2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25"].map((d) =>
  day(d, 10, { country: { US: 6, IN: 4 }, source: { Direct: 5, "Search engine": 5 }, device: { Desktop: 7, Mobile: 3 }, browser: { Chrome: 10 }, os: { Windows: 10 }, landing: { "/": 6, "/pricing/": 4 }, campaign: { "(no campaign tag)": 10 } }));
const m = { site: "example.com", stamp: "s1", today: "2026-11-26", anchor: "2026-11-25", firstDay: "2026-11-01", byDay: new Map(DAYS.map((d) => [d.day, d])),
  live: { day: "2026-11-26", state: "ok", figures: live }, journeys: visits, files: ["cube", "page_index"], x: {}, options: { country: ["CA", "IN", "JP", "US"] }, view: "all" };

// ---- 2. whole days: the server's answer, with B
const row = (name, a, b = 0) => ({ name, a, b, delta: a - b, delta_pct: null, new: false, gone: false });
const answer = (over = {}) => ({ ok: true, a: { used: 7, days: 7, excluded: [], unmeasured: [] }, b: { used: 7, days: 7, excluded: [], unmeasured: [] },
  metrics: [{ key: "visitors", a: 42, b: 30 }], reconciled: true, problems: [],
  dimensions: { countries: [row("US", 42, 30)], sources: [row("Direct", 20, 18), row("Search engine", 22, 12)], devices: [row("Desktop", 30, 20), row("Mobile", 12, 10)],
    browsers: [row("Chrome", 42, 30)], os: [row("Windows", 42, 30)], campaigns: [row("(no campaign tag)", 42, 30)], landing_pages: [row("/", 25, 20), row("/pricing/", 17, 10)],
    assistants: [], pages: [row("/", 999)], continents: [] }, ...over });
{
  reply = (url) => (url.startsWith("api/compare") ? answer() : null);
  const s = go("#traffic/sources?range=7d&country=US");
  const r = { kind: "history", first: "2026-11-19", last: "2026-11-25", length: 7, days: DAYS };
  const got = await N.narrow(m, s, r, { b: { first: "2026-11-12", last: "2026-11-18" } });
  const q = new URLSearchParams(asked.at(-1).split("?")[1]);
  assert.equal(q.get("a"), "2026-11-19..2026-11-25");
  assert.equal(q.get("b"), "2026-11-12..2026-11-18");
  assert.equal(q.get("country"), "US");
  assert.equal(got.how, "server");
  assert.equal(got.a.readers, 42);
  assert.deepEqual(got.a.by.landing, { "/": 25, "/pricing/": 17 }, "landing pages: the visit records' own, never the page views");
  assert.deepEqual(got.b.by.source, { Direct: 18, "Search engine": 12 }, "B in the same answer");
  // Asked again: the same answer, no second request.
  const before = asked.length;
  await N.narrow(m, s, r, { b: { first: "2026-11-12", last: "2026-11-18" } });
  assert.equal(asked.length, before, "an answer is asked for once");
  // A page group's answer is the group's own: its address is under the group.
  const from = asked.length;
  await N.narrow({ ...m, stamp: "s1g" }, go("#traffic/sources?range=7d&country=US&view=blog"), r);
  const sent = asked.slice(from);
  assert.ok(sent[0].startsWith("blog/api/compare?"), sent.join(" "));
  assert.ok(sent.slice(1).every((u) => u.startsWith("blog/")), "its cube too, when the server does not answer");
  // An answer that does not add up is withheld, with the server's words.
  reply = (url) => (url.startsWith("api/compare") ? answer({ reconciled: false, problems: ["A: the visitor rows add up to 41, not the 42 visitors"] }) : null);
  const bad = await N.narrow({ ...m, stamp: "s2" }, s, r);
  assert.equal(bad.a, null);
  assert.match(bad.problems.join(" "), /add up to 41/);
}

// ---- 3. no server: the page's own daily cube; browsers, systems and campaigns not split
{
  const cube = { dims: ["country", "landing", "source", "assistant", "device", "visits"], cap: 300, days_kept: 90,
    days: DAYS.map((d) => ({ day: d.day, state: "ok", folded: false, rows: [["US", "/", "Direct", "", "Desktop", 4], ["US", "/pricing/", "Search engine", "", "Mobile", 2], ["IN", "/", "Direct", "", "Mobile", 1], ["IN", "/", "Search engine", "", "Desktop", 3]] })) };
  reply = (url) => (url.endsWith("cube.json") ? cube : null);
  const s = go("#traffic/places?range=7d&country=US");
  const r = { kind: "history", first: "2026-11-19", last: "2026-11-25", length: 7, days: DAYS };
  const got = await N.narrow({ ...m, stamp: "s3" }, s, r);
  assert.equal(got.how, "page");
  assert.equal(got.a.readers, 42, "6 a day from the US, 7 days");
  assert.deepEqual(got.a.by.device, { Desktop: 28, Mobile: 14 });
  assert.deepEqual(got.a.by.landing, { "/": 28, "/pricing/": 14 });
  assert.equal(got.a.by.browser, null, "the cube has no browser: not split");
  assert.equal(got.a.by.campaign, null);
}

// ---- 4. today and Include today
{
  const s = go("#traffic/sources?range=today&device=Mobile");
  const t = await N.narrow(m, s, { kind: "today", first: m.today, last: m.today, length: 1, days: [] });
  assert.equal(t.how, "visits");
  assert.equal(t.a.readers, 2);
  assert.deepEqual(t.a.by.country, { US: 1, IN: 1 });
  reply = (url) => (url.startsWith("api/compare") ? answer() : null);
  const inc = await N.narrow({ ...m, stamp: "s4" }, go("#traffic/pages?range=7d&inc=1&country=US"),
    { kind: "history", inc: true, first: "2026-11-20", last: "2026-11-26", length: 7, days: DAYS });
  assert.equal(new URLSearchParams(asked.at(-1).split("?")[1]).get("a"), "2026-11-20..2026-11-25", "the whole days from the server, today apart");
  assert.equal(inc.a.readers, 44, "42 whole-day visits and today's 2 from the US");
  assert.deepEqual(inc.a.by.landing, { "/": 26, "/pricing/": 18 });
}

// ---- 5. the bar: three rows, counts that follow the other rows' picks
{
  reply = (url) => (url.startsWith("api/compare") ? answer() : null);
  setContext(m, go("#traffic/visitors?range=7d"));
  const bar = sharedBar(m, S.read());
  const rows = bar.querySelectorAll(".vq-g").filter((x) => !x.className.includes("tf-list"));
  assert.equal(rows.length, 3);
  const list = bar.querySelector(".tf-list");
  assert.ok(list.hidden, "every other country waits behind More countries");
  const more = bar.querySelector(".tf-more");
  assert.match(more.textContent, /More countries \(2\)/, "CA and JP: the countries outside the period's own list");
  more.click();
  assert.equal(list.hidden, false);
  assert.equal(more.getAttribute("aria-expanded"), "true");
  assert.equal(list.querySelectorAll(".vq-c").length, 2);
  assert.match(rows[0].textContent, /Country/);
  assert.match(rows[0].textContent, /42/, "with nothing picked, the period's own breakdown: US 6 × 7");
  assert.ok(!bar.querySelector(".tf-x"), "nothing picked: no ✕");
  assert.ok(!/Clear filter/.test(bar.textContent));
  const picked = sharedBar({ ...m, stamp: "s5" }, go("#traffic/visitors?range=7d&country=US"));
  const [ctry, , src] = picked.querySelectorAll(".vq-g");
  assert.match(ctry.textContent, /42✕|✕/, "the picked chip has its ✕");
  assert.match(src.textContent, /…/, "the other rows wait for the filtered counts, never the whole site's");
  await tick(30);
  assert.match(src.textContent, /Search engine22/, "then count only the visits from the US");
  assert.match(picked.textContent, /Clear filter/);
  assert.equal(sharedBar(m, go("#traffic/pages?page=%2Fpricing%2F")), null, "a page's story: no bar");
}

// ---- 6. the strip: Places & devices beside Pages, the four in one box, the rest as before
{
  const keys = Object.keys(TAB).filter((k) => k.startsWith("traffic/"));
  assert.deepEqual(keys, ["traffic/visitors", "traffic/sources", "traffic/pages", "traffic/places", "traffic/agentfiles", "traffic/search", "traffic/retention", "traffic/time", "traffic/events"]);
  assert.deepEqual(keys.filter((k) => TAB[k].shared), N.SHARED_TABS);
  for (const k of ["traffic/agentfiles", "traffic/search", "traffic/retention", "traffic/time"]) assert.deepEqual(TAB[k].filters, [], `${k} keeps its own filters`);
  assert.deepEqual(TAB["traffic/events"].filters, ["path", "source"]);
  const tabs = keys.map((k) => ({ key: k, name: TAB[k].name, href: `#${k}`, group: TAB[k].group }));
  const { root } = tabStrip(tabs, "traffic/pages", () => {}, { label: "Traffic" });
  const box = root.querySelector(".stab-grp");
  assert.deepEqual(box.querySelectorAll(".stab").map((x) => x.dataset.key), N.SHARED_TABS);
  assert.equal(root.querySelectorAll(".stab").length, 9, "every tab still one of the tablist's");
}

// ---- 7. the tabs, filtered
{
  reply = (url) => (url.startsWith("api/compare") ? answer() : null);
  const draw = async (fn, hash) => {
    const s = go(hash);
    setContext(m, s);
    const out = [fn({ ...m, stamp: hash }, s)].flat(Infinity).filter(Boolean);
    await tick(40);
    return text(out);
  };
  const pl = await draw(places, "#traffic/places?range=7d&country=US&device=Mobile");
  assert.match(pl, /Only the 42 visits from United States, on mobile/);
  assert.match(pl, /Cities.*Not split by the filter/s, "cities are not crossed with a device");
  assert.doesNotMatch(pl, /Counting the visits/);
  const plC = await draw(places, "#traffic/places?range=7d&country=US");
  assert.doesNotMatch(plC, /Cities.*Not split/s, "a country alone still narrows the cities");
  const so = await draw(sources, "#traffic/sources?range=7d&device=Mobile");
  assert.match(so, /1–2 of 2/, "the two source types of the mobile visits (the grid's own count line)");
  assert.match(so, /Only the 42 visits on mobile/);
  assert.match(so, /not split by the filter/);
  const { sourceColumns } = await import(new URL("tabs/tr-sources.js", JS));
  assert.ok(!sourceColumns({ prev: false, perDay: false, leads: false, c: { ok: false } }).some((c) => ["before", "chg", "chip", "trend"].includes(c.key)),
    "the filtered grid's columns (prev and perDay off): no Before, Change or trend, which are the whole site's");
  const pg = await draw(pages, "#traffic/pages?range=7d&source=Direct");
  assert.match(pg, /1–2 of 2/, "the two landing pages of the matching visits");
  assert.match(pg, /Only the 42 visits from Direct/);
  assert.doesNotMatch(pg, /999/, "never the whole site's page views under the filter");
  assert.match(pg, /page views are not kept by country, source or device/);
}

// ---- 8. Compare's B: only the days with the visit records count; none, and B is not compared
{
  const { compareWith } = await import(new URL("tabs/tr-narrowed.js", JS));
  const c = { on: true, ok: true, perDay: false, used: { a: 7, b: 7 } };
  const side = (used, unmeasured) => ({ readers: 1, by: {}, used, unmeasured: unmeasured.map((d) => d) });
  const ok = compareWith(c, { a: side(7, []), b: side(7, ["d1", "d2"]) });
  assert.equal(ok.ok, true);
  assert.deepEqual(ok.used, { a: 7, b: 5 }, "Per day divides by the days with the records");
  assert.equal(ok.bT.unmeasured.by, 2, "and compareNote names the days left out");
  assert.equal(compareWith(c, { a: side(7, []), b: side(7, ["1", "2", "3", "4", "5", "6", "7"]) }).ok, false, "a B before the records were kept is not compared");
  // Today's visits not yet today's count: the tab says so, never "0 visits".
  const { waiting } = await import(new URL("tabs/tr-narrowed.js", JS));
  const s = go("#traffic/sources?range=today&country=US");
  const hold = waiting({ ...m, journeys: visits.slice(1) }, s, { kind: "today", first: m.today, last: m.today, length: 1, days: [] }, { ok: false }, () => "drawn");
  await tick(20);
  assert.match(hold.textContent, /Not shown for the visits from United States/);
  assert.match(hold.textContent, /not exactly today's count/);
  assert.doesNotMatch(hold.textContent, /drawn|0 visits/);
}

// ---- 9. a page's story: no bar, so the top bar's chips show again
{
  const { filterChips } = await import(new URL("filterpanel.js", JS));
  const story = go("#traffic/pages?page=%2Fpricing%2F&country=US");
  assert.equal(filterChips(m, story).querySelectorAll(".chip").length, 1, "the USA chip shows where the bar does not");
  assert.equal(filterChips(m, go("#traffic/pages?country=US")).querySelectorAll(".chip").length, 0, "Pages itself: in the bar");
}

console.log("shared-filter: all passed");
