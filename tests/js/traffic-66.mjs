// SKALD-66 on Traffic: the chart markers said plainly (charts.js), why the Retention curve
// goes up or down (tabs/ret-reading.js), the Time tab's busiest and quietest hours
// (tabs/hour-stats.js, tabs/hours.js) and the Events page that shows every event the site
// sends (tabs/events.js). The Search tab's part is in tests/js/search-reports.mjs.
//
//   node tests/js/traffic-66.mjs        (tests/test_traffic_66.py runs it)
//
// Example data only: example.com pages.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const C = await import(new URL("charts.js", JS));
const RR = await import(new URL("tabs/ret-reading.js", JS));
const HS = await import(new URL("tabs/hour-stats.js", JS));
const hours = (await import(new URL("tabs/hours.js", JS))).default;
const EV = await import(new URL("tabs/events.js", JS));
const { setContext } = await import(new URL("tabs/common.js", JS));
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const text = (out) => flat(out).map((el) => (typeof el === "string" ? el : el.textContent)).join(" ");
const find = (out, sel) => flat(out).flatMap((el) => (el.querySelectorAll ? [...(el.matches?.(sel) ? [el] : []), ...el.querySelectorAll(sel)] : []));
const go = (hash) => { location.hash = hash; return S.read(); };

// ================================================================ 1d. chart markers
{
  assert.equal(C.markLabel({ kind: "backfill", label: "backfill --force 14 days" }), "Skald recounted 14 past days from the logs");
  assert.equal(C.markLabel({ kind: "backfill", label: "backfill --force 1 days" }), "Skald recounted 1 past day from the logs");
  assert.equal(C.markLabel({ kind: "website_release", label: "v3 live" }), "v3 live", "other markers keep their own words");
  // lines() needs a real SVG parser (the browser check covers the drawing); the key under it:
  const days = ["2026-11-11", "2026-11-12", "2026-11-13"].map((day) => ({ day, state: "ok" }));
  const { h } = await import(new URL("ui.js", JS));
  C.setMarkers(new Map([["2026-11-12", [{ kind: "backfill", label: "backfill --force 6 days" }]]]), true);
  let el = h("div");
  C.markKey(el, days);
  assert.match(el.querySelector(".mk-key").textContent, /A dashed line marks something that happened that day/, "a chart with a marker says what it is");
  C.setMarkers(new Map(), true);
  el = h("div");
  C.markKey(el, days);
  assert.equal(el.querySelector(".mk-key"), null, "no marker, no key");
  C.setMarkers(new Map([["2026-11-12", [{ kind: "backfill", label: "backfill --force 6 days" }]]]), false);
  el = h("div");
  C.markKey(el, days);
  assert.equal(el.querySelector(".mk-key"), null, "markers hidden: no key either");
  C.setMarkers(new Map(), true);
}

// ================================================================ 2. why the retention curve moves
{
  // www.example.com's shape on 26 Nov: two cohorts, the newer one only a week old.
  const A = { start: "2026-11-02", cells: { 1: [34], 2: [31] }, size: 749 };
  const B = { start: "2026-11-09", cells: { 1: [28] }, size: 443 };
  const pick = (c, k) => (c.cells[k] ? { state: "ok", back: c.cells[k][0], size: c.size } : { state: "pending" });
  const st = RR.steps([A, B], 8, pick);
  assert.equal(st.length, 1, "one step: +1 to +2");
  const [s1] = st;
  assert.deepEqual([s1.before.back, s1.before.size, s1.after.back, s1.after.size], [62, 1192, 31, 749]);
  assert.ok(s1.fewer && s1.mixed);
  assert.equal(s1.same.cohorts.length, 1);
  assert.deepEqual([s1.same.before.back, s1.same.after.back, s1.same.after.size], [34, 31, 749]);
  const words = RR.stepWords(s1, "week", (c) => (c.start === "2026-11-02" ? "2 Nov – 8 Nov" : "?"));
  assert.equal(words, "week +1 → week +2: down 1.1 points (5.2% → 4.1%). On the 2 Nov – 8 Nov cohort only (749 new visitors): 4.5% → 4.1% (34 → 31 people). "
    + "Part of the move is that week +2 counts fewer cohorts (1 of 2): the newer ones have not had 2 weeks yet.");
  // the same cohorts at both steps: a change in what people did
  const C2 = { start: "2026-10-26", cells: { 1: [20], 2: [30] }, size: 500 };
  const [same] = RR.steps([C2], 8, pick);
  assert.match(RR.stepWords(same, "week", () => ""), /up 2\.0 points \(4\.0% → 6\.0%\)\. The same cohort at both steps, so this is a change in what people did\./);
  // the move is all mix: the same people hardly moved
  const D = { start: "2026-10-19", cells: { 1: [10], 2: [10] }, size: 1000 }, E = { start: "2026-10-26", cells: { 1: [90] }, size: 1000 };
  const [mix] = RR.steps([D, E], 8, pick);
  assert.match(RR.stepWords(mix, "week", () => "19 Oct"), /On the same people it hardly moved: the rest is that week \+2 counts fewer cohorts/);
  // the same people went the other way: the curve's rise is only who is counted (a live site's shape)
  const G = { start: "2026-11-02", cells: { 1: [614], 2: [421] }, size: 3076 }, H = { start: "2026-11-09", cells: { 1: [80] }, size: 2400 };
  const [other] = RR.steps([G, H], 8, pick);
  assert.match(RR.stepWords(other, "week", () => "2 Nov – 8 Nov"), /up 1\.0 point \(12\.7% → 13\.7%\)\. On the 2 Nov – 8 Nov cohort only \(3,076 new visitors\): 20\.0% → 13\.7% \(614 → 421 people\)\. On the same people it went down: the curve goes up only because of how week \+2 counts fewer cohorts/);
  const one = { start: "2026-11-02", cells: { 1: [1], 2: [1] }, size: 200 }, two = { start: "2026-11-09", cells: { 1: [3] }, size: 100 };
  assert.match(RR.stepWords(RR.steps([one, two], 8, pick)[0], "week", () => "x"), /\(1 → 1 person\)/, "one person, not one people");
  // the curve held, but the same people fell: the newer cohorts hide it (review)
  const I = { start: "2026-11-02", cells: { 1: [100], 2: [70] }, size: 1000 }, J = { start: "2026-11-09", cells: { 1: [40] }, size: 1000 };
  assert.match(RR.stepWords(RR.steps([I, J], 8, pick)[0], "week", () => "2 Nov"), /no change \(7\.0% → 7\.0%\)\. On the 2 Nov cohort only .*10\.0% → 7\.0%.*The curve held, but on the same people it went down 3\.0 points: week \+2 counts fewer cohorts .* and that hides it\./);
  // two steps with no cohort in common: only which cohorts are counted
  const P = { start: "2026-11-02", cells: { 1: [10] }, size: 100, held2: true }, Q = { start: "2026-10-26", cells: { 2: [5] }, size: 100 };
  const pick2 = (c, k) => (c.cells[k] ? { state: "ok", back: c.cells[k][0], size: c.size } : { state: "held" });
  assert.match(RR.stepWords(RR.steps([P, Q], 8, pick2)[0], "week", () => "x"), /No cohort is counted at both steps, so this is only which cohorts are counted: the two steps count different cohorts/);
  // few new visitors: said
  const F = { start: "2026-10-26", cells: { 1: [3], 2: [2] }, size: 40 };
  assert.match(RR.stepWords(RR.steps([F], 8, pick)[0], "day", () => ""), /Too few to trust: under 100 new visitors\./);
  assert.deepEqual(RR.steps([B], 8, pick), [], "one point: nothing to read");
}

// ================================================================ 3. the Time tab's statistics
const zero = () => Array(24).fill(0);
const dayOf = (day, weekday, put) => { const cells = zero(); for (const [hr, v] of Object.entries(put)) cells[hr] = v; return { day, weekday, cells }; };
{
  const days = [dayOf("2026-11-16", "Mon", { 7: 10, 8: 6, 9: 4, 20: 1 }), dayOf("2026-11-17", "Tue", { 7: 8, 8: 5, 9: 3, 23: 2 }), dayOf("2026-11-18", "Wed", { 7: 9, 12: 2, 0: 1 })];
  const st = HS.hourStats(days);
  assert.equal(st.total, 51);
  assert.deepEqual([st.top.hour, st.top.value], [7, 27]);
  assert.deepEqual([st.busy.from, st.busy.value], [7, 45], "07:00 to 10:00");
  assert.equal(st.calm.value, 0);
  assert.equal(st.calm.from, 1, "the first of the quiet stretches");
  assert.equal(st.oneDay, null, "spread over three days");
  assert.equal(st.week, null, "a weekday seen once is not compared");
  // one day makes the peak: said
  const spike = HS.hourStats([dayOf("2026-11-16", "Mon", { 3: 40, 7: 2 }), dayOf("2026-11-17", "Tue", { 3: 1, 7: 3 }), dayOf("2026-11-18", "Wed", { 7: 3 })]);
  assert.deepEqual(spike.oneDay, { day: "2026-11-16", value: 40 });
  // a quiet stretch may run past midnight
  const late = HS.hourStats([dayOf("2026-11-16", "Mon", Object.fromEntries(Array.from({ length: 24 }, (_, i) => [i, [23, 0, 1].includes(i) ? 0 : 5])))]);
  assert.deepEqual([late.calm.from, late.calm.value], [23, 0]);
  // two weeks of every weekday: the busiest and the quietest
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const twoWeeks = Array.from({ length: 14 }, (_, i) => dayOf(`2026-11-${String(i + 2).padStart(2, "0")}`, names[i % 7], { 10: names[i % 7] === "Sat" ? 30 : names[i % 7] === "Sun" ? 2 : 10 }));
  const wk = HS.hourStats(twoWeeks).week;
  assert.deepEqual([wk.busiest.weekday, wk.busiest.avg, wk.quietest.weekday, wk.quietest.avg], ["Sat", 30, "Sun", 2]);
  assert.equal(HS.hourStats(twoWeeks).week.oneDay, null, "spread over its days");
  twoWeeks[12].cells[10] = 31;                       // two near-equal Saturdays: no burst
  assert.equal(HS.hourStats(twoWeeks).week.oneDay, null, "two near-equal days are not one day's burst");
  twoWeeks[5].cells[10] = 300;                       // one Saturday with a burst
  assert.deepEqual(HS.hourStats(twoWeeks).week.oneDay, { day: twoWeeks[5].day, value: 300 }, "a burst on one Saturday is said");
  assert.deepEqual(HS.hourStats([]), { days: 0, total: 0 });
}
{
  // the tab itself: three tiles above the charts, the measure's own unit
  const hr = (put) => Object.fromEntries(Object.entries(put).map(([k, v]) => [String(k).padStart(2, "0"), v]));
  const day = (d, put) => ({ day: d, state: "ok", readers: Object.values(put).reduce((a, v) => a + v, 0), by: { hour: hr(put) } });
  const list = [day("2026-11-19", { 7: 10, 8: 6, 9: 4, 20: 1 }), day("2026-11-20", { 7: 8, 8: 5, 9: 3 }), { day: "2026-11-21", state: "missing" }];
  const m = { site: "example.com", today: "2026-11-22", anchor: "2026-11-21", firstDay: "2026-11-01", byDay: new Map(list.map((d) => [d.day, d])), journeys: [], x: {} };
  setContext(m, go("#traffic/time?range=custom&from=2026-11-19&to=2026-11-21"));
  const out = flat(hours(m, S.read()));
  const tiles = find(out, ".tm-stats .kpi");
  assert.equal(find(out, ".tm-stats .k-n").length, 0, "never a k-n line: quietKpis would fold it away");
  assert.equal(find(out, ".tm-stats .tm-line").length, 3);
  assert.equal(tiles.length, 3);
  assert.match(tiles[0].textContent, /Busiest hours.*07:00–10:00.*97% of the visitors \(36\)\. The busiest single hour: 07:00–08:00, 49%\./);
  assert.match(tiles[1].textContent, /Quietest hours/);
  assert.match(tiles[2].textContent, /Needs each weekday 2 times or more: choose 30 or 90 days\./);
  assert.match(text(out), /Over 2 verified days, hours in .*A visitor counts once, in the hour of their first page\. Few days give a rough picture/);
  // a group's requests: a day with hour counts but none for this group is 0 for it, as the heatmap draws it (review)
  const { statsBlock } = await import(new URL("tabs/hours.js", JS));
  const g = (d) => d.hourly?.bots;
  const rq = [{ day: "2026-11-19", state: "ok", hourly: { bots: { "03": 9 } } }, { day: "2026-11-20", state: "ok", hourly: { people: { "07": 4 } } }, { day: "2026-11-21", state: "ok" }];
  assert.match(statsBlock(rq, g, "requests", {}).textContent, /Over 2 verified days/, "the day without bots is 0 bots; the day with no hour counts is not known");
  const mt = { ...m, live: { state: "ok", day: "2026-11-22", figures: { readers: 1, by: { hour: { "07": 1 } } } } };
  setContext(mt, go("#traffic/time?range=today"));
  const today = flat(hours(mt, S.read()));
  assert.equal(find(today, ".tm-stats").length, 0, "today is not whole: no statistics");
}

// ================================================================ 4. Events: every event the site sends
{
  const rows = [
    ["2026-11-19", "scroll_75", "", "/", "Search engine", 21], ["2026-11-19", "scroll_75", "", "/pricing/", "Direct", 12],
    ["2026-11-19", "form_start", "contact", "/contact/", "Search engine", 44], ["2026-11-19", "form_submit", "contact", "/contact/", "Search engine", 26],
    ["2026-11-19", "outbound_click", "", "/", "Direct", 8],
  ];
  const sent = { scroll_75: 1, form_start: 1, form_submit: 1, outbound_click: 1, copy_text: 1 };
  const evs = ["cta_click", "book_demo_open", "demo_booked", "signup_start", "signup_submit", "outbound_click", "scroll_75", "copy_text", "form_start", "form_submit", "tel_click"]
    .map((name) => ({ name, label: { cta_click: "Button clicks", book_demo_open: "Demo booking opened", demo_booked: "Demo booked", signup_start: "Sign-up started", signup_submit: "Sign-up sent",
      outbound_click: "Links to other sites", scroll_75: "Read three quarters", copy_text: "Copied text", form_start: "Form started", form_submit: "Form sent", tel_click: "Phone link clicks" }[name] }));
  const f = { events: evs, sent, first_day: "2026-11-01", rows, days: [{ day: "2026-11-19", state: "ok" }] };
  const m = { site: "example.com", today: "2026-11-20", anchor: "2026-11-19", firstDay: "2026-11-01", byDay: new Map([["2026-11-19", { day: "2026-11-19", state: "ok", readers: 200 }]]), journeys: [], x: { events: f } };
  setContext(m, go("#traffic/events?range=custom&from=2026-11-19&to=2026-11-19"));
  const out = flat(EV.default(m, S.read()));
  const did = find(out, ".ev-did .ev-t");
  assert.deepEqual(did.map((t) => t.querySelector(".ev-l").textContent), ["Form started", "Read three quarters", "Form sent", "Links to other sites", "Copied text"], "only what the site sends, biggest first");
  assert.match(did[0].textContent, /44.*Times someone started filling in a form\..*22\.0 per 100 visitors; most on \/contact\/ \(44\)/);
  assert.match(did[1].textContent, /33.*most on \/ \(21\), \/pricing\/ \(12\)/);
  assert.match(did[4].textContent, /Copied text0/, "a sent event with none in these days is a real 0");
  const steps = find(out, ".ev-step");
  assert.equal(steps.length, 1, "only the form pair the site sends");
  assert.match(steps[0].textContent, /Form started44.*Form sent26.*26 of 44 went on \(59%\)/);
  const unset = find(out, ".ev-unset")[0];
  assert.match(unset.textContent, /Not set up yet: Button clicks, Sign-up started, Sign-up sent, Demo booking opened, Demo booked\./);
  assert.ok(unset.querySelector("details summary"), "the how is behind one button");
  assert.equal(find(out, ".ev-t.not-set").length, 0, "no big not-set-up tiles any more");
  assert.ok(text(out).includes("Form started"), "by page and by source carry the form events too");
  const byPage = find(out, "table").find((t) => /Events by page/.test(t.textContent));
  // beacon page views (review): a tile at the end, never a chart line or a column that dwarfs the rest
  {
    const f2 = { ...f, sent: { ...sent, page_view: 1 }, events: [...evs, { name: "page_view", label: "Page views (beacon)" }],
      rows: [...rows, ["2026-11-19", "page_view", "", "/", "Direct", 5000]] };
    setContext({ ...m, x: { events: f2 } }, go("#traffic/events?range=custom&from=2026-11-19&to=2026-11-19"));
    const o2 = flat(EV.default({ ...m, x: { events: f2 } }, S.read()));
    const tiles2 = find(o2, ".ev-did .ev-t").map((x) => x.querySelector(".ev-l").textContent);
    assert.equal(tiles2.at(-1), "Page views (beacon)", "page views last, though the biggest");
    const bp = find(o2, "table").find((x) => /Events by page/.test(x.textContent));
    assert.ok(!/Page views/.test(bp.querySelector("thead").textContent), "no page-view column");
  }
  assert.ok(byPage && /Form started/.test(byPage.textContent), "the by-page table has a Form started column");
}

console.log("traffic-66: all passed");
