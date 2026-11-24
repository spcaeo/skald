// SKALD-48: Overview's "Requests per minute" was drawn for half the page's width but shown
// across the whole row, so the browser stretched it about 2x: 11px axis text at ~22px and a
// 150px chart at ~300px. Now it is drawn for the width it gets: half only beside the
// visitors chart (the Real time tab), shorter when alone, with its figures in one line.
//
//   node tests/js/rpm-chart.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
// A 1,400px panel with 20px padding: a wide screen.
const panel = document.getElementById("panel");
panel.clientWidth = 1400;
globalThis.getComputedStyle = () => ({ paddingLeft: "20px", getPropertyValue: () => "" });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "overview", name: "Overview", tabs: [{ route: "overview/summary", name: "Summary" }] }]);
const RT = await import(new URL("tabs/realtime.js", JS));

// 01:34 to 02:03, one row a minute.
const rows = Array.from({ length: 30 }, (_, i) => { const t = 94 + i;
  return { at: `2026-11-23T0${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`, requests: [27, 92, 139, 51, 33, 38, 38, 17, 12, 17][i % 10] }; });
rows[29].requests = 4;                       // the minute still running
// The drawing's size, from the chart's markup (dom-lite does not parse SVG).
const box = (el) => { const html = (el.querySelector(".chart") || el).innerHTML; return html.match(/viewBox="([^"]+)"/)[1].split(" ").map(Number); };

// Alone (Overview): drawn for the whole row (1,400 - 40 - 40 = 1,320, capped at 1,180), 120 high.
let [, , w, hgt] = box(RT.requestsChart(rows, false));
assert.equal(w, 1180, "alone: the row's width, so 1px of the drawing is 1px on screen");
assert.equal(hgt, 120, "alone: a compact 120px");
// Beside the visitors chart (Real time tab): half the row each, 150 high, as before.
[, , w, hgt] = box(RT.requestsChart(rows, false, { half: true }));
assert.equal(w, 630, "beside the visitors chart: half the row");
assert.equal(hgt, 150);
// Sky blue, as Right now's minute bars (--td-bar), the running minute paler.
const html = RT.requestsChart(rows, false).innerHTML;
assert.ok(html.includes('fill="var(--td-bar)"'), "sky-blue bars");
assert.ok(html.includes('fill="color-mix(in srgb, var(--td-bar) 50%, var(--surface))"'), "the running minute paler");

// The figures line: every request in the window, the busiest finished minute, the average of
// the finished minutes (the running one would pull it down).
const sum = RT.requestsSummary(rows).textContent;
const total = rows.reduce((a, r) => a + r.requests, 0);
const done = rows.slice(0, -1);
assert.match(sum, new RegExp(`^${total.toLocaleString("en-US")} in 30 min`));
assert.match(sum, /139 at 01:36, the busiest minute/);
assert.match(sum, new RegExp(`${Math.round(done.reduce((a, r) => a + r.requests, 0) / done.length)} a minute on average$`));
assert.equal(RT.requestsSummary([]), null);
assert.doesNotMatch(RT.requestsSummary([{ at: "2026-11-23T01:34", requests: 0 }]).textContent, /busiest/, "no busiest minute of none");

// The block: Overview's merged block draws the requests chart alone, full width.
RT._state.body = { ok: true, people_state: "ok", people: { until: "2026-11-23T02:03:00Z", per_minute: [], countries: {}, active: {} },
  requests: { until: "2026-11-23T02:03:08Z", per_minute: rows } };
RT._state.at = Date.now();
const merged = RT.realtimeBlock({ x: {} }, { view: "all" }, { merged: true });
const card = merged.querySelector(".rt-rq");
assert.ok(card && card.className.includes("alone"), "alone on Overview");
assert.equal(box(card)[2], 1180);
assert.ok(card.querySelector(".rt-rq-sum"), "the figures line is in the card");
// The Real time tab: the visitors chart beside it, so both are drawn for half the row.
const tab = RT.realtimeBlock({ x: {} }, { view: "all" }, { tab: true });
const pairCard = tab.querySelector(".rt-rq");
assert.ok(pairCard && !pairCard.className.includes("alone"));
assert.equal(box(pairCard)[2], 630);

console.log("rpm-chart: all passed");
process.exit(0);
