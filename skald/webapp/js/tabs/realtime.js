// Real time: who is on the site now. Overview > Real time, and the first thing
// on Overview > Summary in Live mode (ov-summary.js).
//
// Two roads, each with its own clock, never added together:
//   * people (visitors active in the last 5 and 30 minutes, visitors minute by
//     minute, countries, pages, sources, devices, newest visits): the live run's
//     `realtime` part (realtime.py), counted by the day's tally with the same
//     people rule as every figure, every 2 minutes; "as of" its `until`
//   * requests per minute: every request of the site's hosts, read from the end
//     of the log by the helper every 15 seconds (realtime_tail.py), unsorted,
//     so labelled requests, never people
// The block asks the helper (api/realtime) every POLL seconds while it is on
// screen and the page is visible. Without a helper (the demo, a static copy)
// it reads data/realtime.json again instead, and its requests are the 2-minute
// count's, said so. Pause holds everything still. The tab says polls: true, so
// main.js's 2-minute redraw leaves it alone; on Summary the redraw makes a new
// block, which starts from the last answer (no flash).

import { h, n } from "../ui.js";
import { getJSON } from "../data.js";
import { bars } from "../charts.js";
import { blist } from "./common.js";
import { tiles, info } from "./tiles.js";
import { table, REGISTRY } from "../table.js";
import { link, open as openDrill } from "../drill.js";
import { flagEl, country } from "./readers.js";
import { mark } from "../icons.js";
import { time as tzTime, label as tzLabel } from "../tz.js";
import { worldMap } from "./rt-map.js";
import { DEMO } from "../demo.js";

export const POLL = 15;            // seconds between two asks
const TICK = 5;                    // seconds between two looks at the clock
const TABLE = "Countries now: visits today and visitors active";
const LATE = 10 * 60000;           // the people count is late after 10 minutes (it runs every 2)

// One state for every block on screen: the last answer, the clock, Pause.
const st = { body: null, at: 0, timer: 0, busy: false, paused: false, helper: true, blocks: new Set() };

// realtime.json (written with each redraw) as an answer without the 15-second road.
const fromFile = (f) => (f ? { ok: true, file: true, people_state: f.state, people: f.realtime || null, requests: null } : null);

async function poll() {
  if (st.busy) return;
  st.busy = true;
  try {
    let body = null;
    if (st.helper && !DEMO.on) {
      try { body = await getJSON("api/realtime", true); } catch { body = null; }
      if (!body?.ok) st.helper = false;           // no helper here: stop asking it
    }
    if (!body?.ok) body = fromFile(await getJSON("data/realtime.json", true).catch(() => null)) || st.body;
    if (body) st.body = body;
  } finally {
    st.busy = false;
    st.at = Date.now();
  }
  for (const b of st.blocks) if (b.el.isConnected) b.draw();
}

function tick() {
  for (const b of [...st.blocks]) if (!b.el.isConnected) st.blocks.delete(b);
  if (!st.blocks.size) { clearInterval(st.timer); st.timer = 0; return; }
  for (const b of st.blocks) b.clock();
  if (!st.paused && !document.hidden && Date.now() - st.at >= POLL * 1000) poll();
}

// "as of 14:03:12 (40 s ago)"
function ago(ts) {
  const t = Date.parse(ts || "");
  if (!t) return "";
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  return `${tzTime(ts, { seconds: true, label: false })} (${s < 60 ? `${s} s` : s < 3600 ? `${Math.floor(s / 60)} min` : `${Math.floor(s / 3600)} h`} ago)`;
}
const hhmm = (at) => tzTime(at, { label: false });

// ------------------------------------------------------------------ parts
function people(P, s) {
  const a = P.active || {};
  return tiles([
    { label: "Active now", value: a[P.short ?? 5] ?? null, line: `visitors, last ${P.short ?? 5} minutes`,
      info: "Visitors (visits that read a page, as Visitors counts them everywhere) with any request in the last 5 minutes before the time above. People only: AI, crawlers, bots and our own traffic are never in it." },
    { label: "Last 30 minutes", value: a[P.minutes ?? 30] ?? null, line: "visitors with a request in them",
      info: "Visitors with any request in the 30 minutes before the time above." },
    { label: "Visitors today", value: P.visits_today ?? null, line: "so far, the same count as Overview's" },
    { label: "Pages read, 30 min", value: P.page_views ?? null, line: "page views by visitors" },
  ]);
}

function perMinute(P) {
  const rows = P.per_minute || [];
  const last = rows.length - 1;
  return bars(rows.map((r, i) => ({ label: hhmm(r.at), value: r.under_way || 0,
    title: `${hhmm(r.at)} ${tzLabel()}${i === last ? " (still running)" : ""}: ${n(r.under_way || 0)} on the site, ${n(r.started || 0)} arrived`,
    color: i === last ? "color-mix(in srgb, var(--g-people) 55%, var(--surface))" : "var(--g-people)" })),
  { label: "Visitors on the site, minute by minute", unit: "visitors on the site", every: 5, H: 150, half: true });
}

function requestsChart(rows, fromCount) {
  const last = rows.length - 1;
  return bars(rows.map((r, i) => ({ label: hhmm(r.at), value: r.requests || 0,
    title: `${hhmm(r.at)} ${tzLabel()}${i === last ? " (still running)" : ""}`,
    color: i === last ? "color-mix(in srgb, var(--ink-3) 50%, var(--surface))" : "var(--ink-3)" })),
  { label: `Requests per minute${fromCount ? ", from the 2-minute count" : ""}`, unit: "requests (every kind, not people)", every: 5, H: 150, half: true });
}

// The countries table beside the map: the same figures, for a screen reader and a phone.
function countriesTable(P) {
  for (let i = REGISTRY.length - 1; i >= 0; i--) if (REGISTRY[i].caption === TABLE) REGISTRY.splice(i, 1);
  const rows = Object.entries(P.countries || {}).map(([cc, r]) => ({ cc, name: country(cc), visits: r.visits || 0, active: r.active || 0 }));
  return table([
    { key: "name", label: "Country", fmt: (v, r) => link("country", r.cc, { text: v }), csv: (r) => r.name },
    { key: "visits", label: "Visits today", num: true },
    { key: "active", label: "Active, 30 min", num: true },
  ], { caption: TABLE, rows, file: "realtime-countries.csv", limit: 8, empty: "No visitor yet today.", sortKey: "visits", dir: -1 });
}

const pairs = (obj) => Object.entries(obj || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);

function card(title, unit, ...body) {
  return h("div", { class: "sheet card" }, h("div", { class: "card-h" }, h("h3", null, title)), h("p", { class: "card-m" }, unit), ...body);
}

function machines(M = {}) {
  const ai = pairs(M.answer_engines), search = pairs(M.search_engines);
  return card("AI and crawlers now", "requests in the last 30 minutes: machines, never visitors",
    h("p", { class: "rt-sub" }, "AI assistants"),
    blist(ai, { color: "var(--g-answer_engines)", drill: "bot", limit: 6, empty: "None in the last 30 minutes." }),
    h("p", { class: "rt-sub" }, "Search crawlers"),
    blist(search, { color: "var(--g-search_engines)", drill: "bot", limit: 4, empty: "None in the last 30 minutes." }),
    h("p", { class: "rt-line" }, h("i", { class: "rt-k", style: { background: "var(--g-bots)" } }), "Other bots and scanners: ", h("b", null, n(M.bots || 0)), " requests"));
}

function newest(P) {
  const rows = (P.newest || []).map((v) => h("li", null,
    h("span", { class: "s-t" }, tzTime(v.start, { label: false })),
    h("span", { class: "s-i" }, flagEl(v.country) || mark("device", v.device)),
    h("span", { class: "s-w" }, link("country", v.country, { text: country(v.country), bare: true }), `, ${v.device || "device not recorded"}`,
      v.via ? [" from ", link(v.source === "AI assistant" ? "assistant" : "referrer", v.via, { bare: true })] : v.source ? ` · ${v.source}` : "",
      `: ${n(v.pages)} page${v.pages === 1 ? "" : "s"} so far`,
      v.active ? h("span", { class: `rt-now${v.active === "5" ? " on" : ""}` }, v.active === "5" ? "active now" : "active, 30 min") : null,
      h("small", null, `landed on ${v.landing || "?"}`))));
  return card("Newest visits", `times in ${tzLabel()}, newest first; no address, no browser string`,
    rows.length ? h("ul", { class: "stream live-stream" }, rows) : h("p", { class: "empty" }, "No visitor has read a page yet today."));
}

function stateWords(state) {
  if (state === "withheld") return "Today's figures are withheld: the second count disagrees with them, so no visitor figure is shown until it matches. The requests below are a plain count of log lines.";
  if (state === "site") return "";
  return "No live count yet today: the visitor figures appear with the next live run (every 2 minutes).";
}

// ------------------------------------------------------------------ block
export function realtimeBlock(m, s, { tab = false } = {}) {
  if (!st.body && m.x?.realtime) st.body = fromFile(m.x.realtime);
  const el = h("section", { class: `s rt${tab ? " rt-tab" : ""}`, "aria-label": "Real time" });
  const map = worldMap({ onPick: (cc) => openDrill("country", cc), label: "World map: visits today by country, and countries with visitors active in the last 30 minutes" });
  const clockP = h("span", { class: "rt-as" });
  const clockR = h("span", { class: "rt-as" });
  const pause = h("button", { type: "button", class: "btn", "aria-pressed": String(st.paused) }, st.paused ? "Resume" : "Pause");
  pause.addEventListener("click", () => {
    st.paused = !st.paused;
    for (const b of st.blocks) b.paused();
    if (!st.paused) poll();
  });
  const block = { el, draw, clock, paused: () => { pause.textContent = st.paused ? "Resume" : "Pause"; pause.setAttribute("aria-pressed", String(st.paused)); } };

  function clock() {
    const B = st.body || {};
    const P = B.people;
    const late = P?.until && Date.now() - Date.parse(P.until) > LATE && !DEMO.on;
    clockP.textContent = P?.until ? `Visitors as of ${ago(P.until)}${late ? ", late: the live count has not run since" : ""}` : "Visitors: no count yet";
    clockP.classList.toggle("late", !!late);
    const R = B.requests;
    clockR.textContent = R?.until ? `Requests as of ${ago(R.until)}, read from the log every ${POLL} s${R.partial ? " (the log's end is too large to read whole: a floor)" : ""}`
      : P?.until ? `Requests as of ${tzTime(P.until, { seconds: true, label: false })}, from the 2-minute count${DEMO.on ? " (the 15-second count needs a running Skald)" : ""}` : "";
  }

  function draw() {
    const B = st.body || { people_state: "empty" };
    const P = B.people_state === "ok" || B.people_state === "stale" ? B.people : null;
    const reqRows = B.requests?.per_minute || (P?.per_minute || []).map((r) => ({ at: r.at, requests: Object.values(r.requests || {}).reduce((a, b) => a + b, 0) }));
    const top = h("div", { class: "card-h start rt-top" },
      tab ? null : h("h2", null, "Real time"),
      info(`Visitors are counted by the live run every 2 minutes, with the same rules as every figure here, and are shown "as of" that count. Requests per minute are every line the server wrote, read every ${POLL} seconds: pages, files, bots and people alike, so they are never called visitors. Both are recounted by the audit (skald audit --live).`, "Real time"),
      h("span", { class: "rt-clocks" }, clockP, clockR), h("span", { class: "grow" }), pause);
    clock();
    const view = s.view && s.view !== "all" ? h("p", { class: "note" }, "Real time covers the whole site, not only this page group.") : null;
    const words = P ? "" : stateWords(B.people_state);
    el.replaceChildren(...[top, view,
      words ? h("div", { class: `state${B.people_state === "withheld" ? " bad" : ""}`, role: B.people_state === "withheld" ? "alert" : "status" }, h("div", null, words)) : null,
      P ? people(P, s) : null,
      h("div", { class: "cols rt-charts" },
        P ? h("div", { class: "sheet" }, h("h3", null, "Visitors on the site, minute by minute"),
          h("p", { class: "card-m" }, "a visitor is on the site from their first request to their last; the last minute is still running"), perMinute(P)) : null,
        reqRows.length ? h("div", { class: "sheet" }, h("h3", null, "Requests per minute"),
          h("p", { class: "card-m" }, "every request the server logged: pages, files, bots and people alike. Not visitors."), requestsChart(reqRows, !B.requests)) : null),
      P ? h("div", { class: "rt-geo" },
        h("div", { class: "sheet rt-mapcard" }, h("h3", null, "Where visitors are"),
          h("p", { class: "card-m" }, "shaded by visits today; a bubble where visitors were active in the last 30 minutes. Select a country for its detail."), map.el),
        h("div", { class: "sheet rt-ctable" }, h("h3", null, "By country"), countriesTable(P))) : null,
      P ? h("div", { class: "cols rt-lists" },
        card("Pages being read", `page views by visitors in the last 30 minutes (${n(P.page_views || 0)})`,
          blist(pairs(P.pages), { drill: "path", limit: 8, total: P.page_views, empty: "No page read in the last 30 minutes." })),
        newest(P)) : null,
      P ? h("div", { class: "cols three rt-lists" },
        card("Sources now", "visitors active in the last 30 minutes, by where they came from", blist(pairs(P.sources), { drill: "source", limit: 6, empty: "Nobody in the last 30 minutes." })),
        card("Devices now", "visitors active in the last 30 minutes, by device", blist(pairs(P.devices), { drill: "device", limit: 6, empty: "Nobody in the last 30 minutes." })),
        machines(P.machines)) : null].filter(Boolean));
    if (P) map.update(P.countries);
  }

  st.blocks.add(block);
  draw();
  if (!st.timer) st.timer = setInterval(tick, TICK * 1000);
  // A new block asks at once when the last answer is older than a poll (or there is none).
  if (Date.now() - st.at >= POLL * 1000) queueMicrotask(poll);
  return el;
}

// Overview > Real time: the block under the page's own title.
export default function realtimeTab(m, s) {
  return [h("div", { class: "head" }, h("h1", null, "Real time"),
    info("Who is on the site now: visitors (counted every 2 minutes, the same rules as every figure) and requests (read every 15 seconds). It does not follow the period: it is always now.", "Real time"),
    h("span", { class: "period" }, h("span", { class: "pulse", "aria-hidden": "true" }), "Now")),
  realtimeBlock(m, s, { tab: true })];
}

// For a test: what the block keeps between draws.
export const _state = st;
