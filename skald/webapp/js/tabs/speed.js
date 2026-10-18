// Site health > Page speed: how fast the most visited pages are for real
// people (Core Web Vitals from Google, when it has enough Chrome users) and in
// Google's lab test, on a phone or a desktop; the 30-day trend; and beside it
// how fast our own server answered. From speed.json (PageSpeed Insights, once
// a day for the top 5 landing pages) and the health figures.

import { h, n, long, short, addDays, ICON } from "../ui.js";
import { figures } from "../data.js";
import { lines, legend } from "../charts.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { head, healthTabs } from "./common.js";
import { bucketAt } from "./health.js";

// Google's own bands: good up to the first figure, poor past the second.
const BANDS = { lcp_ms: [2500, 4000], cls: [0.1, 0.25], inp_ms: [200, 500] };
const WORDS = { good: "Good", ni: "Needs work", poor: "Poor" };
export function band(metric, v) {
  if (v == null) return null;
  if (metric === "score") return v >= 90 ? "good" : v >= 50 ? "ni" : "poor";
  const [a, b] = BANDS[metric];
  return v <= a ? "good" : v <= b ? "ni" : "poor";
}
const FMT = { lcp_ms: (v) => `${(v / 1000).toFixed(1)} s`, cls: (v) => v.toFixed(2), inp_ms: (v) => `${n(v)} ms`, score: (v) => String(Math.round(v)) };
function pill(metric, v, title = "") {
  if (v == null) return h("span", { class: "cwv none", title: title || "Not measured" }, "-");
  const b = band(metric, v);
  return h("span", { class: `cwv ${b}`, title: `${WORDS[b]}${title ? `. ${title}` : ""}` }, h("i", { "aria-hidden": "true" }), FMT[metric](v), h("span", { class: "vh" }, `, ${WORDS[b]}`));
}

// The value people felt (field) when Google has it, else the lab test's.
const pick = (t, k) => (t.field?.[k] ?? (k === "inp_ms" ? null : t.lab?.[k] ?? null));
const from = (t) => (t.field ? "Real users" : "Lab test");

export default function speed(m, s) {
  const file = m.x.speed;
  const strat = s.strat === "desktop" ? "desktop" : "mobile";
  const { r, t } = figures(m, s);
  const out = [healthTabs(m, "health/speed"), ...head("Page speed", r, "How fast the most visited pages load and respond, from Google PageSpeed Insights once a day: what real Chrome users felt when Google has enough of them, otherwise Google's lab test. The server's own answer time follows the date range.", { banner: false })];
  const seg = h("div", { class: "seg plain", role: "group", "aria-label": "Device" },
    [["mobile", "Phone"], ["desktop", "Desktop"]].map(([k, w]) => h("button", { type: "button", "aria-pressed": String(strat === k), onclick: () => S.set({ strat: k === "mobile" ? "" : k }, { replace: true }) }, w)));
  if (!file) return [...out, h("div", { class: "state" }, h("div", null, "Page speed is not measured yet. The server tests the top pages with Google PageSpeed Insights once a day; this page fills in after the first run."))];

  // Google refused every test of the newest run: say so plainly, above any old figures.
  if (file.status?.state === "failing") out.push(h("div", { class: "state warn", role: "alert" }, h("div", null, h("b", null, file.status.message),
    file.status.day ? ` Last tried ${long(file.status.day)}.` : "")));
  const latest = (file.latest || []).filter((x) => x.strategy === strat);
  const tested = latest.map((x) => x.day).filter(Boolean).sort().pop();
  const origin = latest.find((x) => x.origin_field)?.origin_field || null;
  const trend = file.trend?.[strat] || [];
  const median = (k) => { const v = latest.filter((x) => x.ok).map((x) => pick(x, k)).filter((x) => x != null).sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null; };
  const score = (() => { const v = latest.filter((x) => x.ok && x.score != null).map((x) => x.score).sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null; })();
  const tile = (label, node, note) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note), h("div", { class: "k-v sp-v" }, node), h("div", { class: "k-c" }));
  const vit = (k) => origin?.[k] ?? median(k);
  const vitNote = origin ? "real Chrome users, the whole site, last 28 days (Google)" : "the tested pages' median, lab test";
  // The same figure as Site health: the exact median when kept, else the bucket it falls in.
  const p50 = !t ? null : t.speed_p50 != null ? `${t.speed_p50} s` : bucketAt(t.speeds || {}, 0.5);

  // Never tested, on either device: not set up. Say what to switch on, not a row of dashes.
  const everTested = (file.latest || []).length > 0 || (file.days || []).some((d) => (d.tests || []).length);
  const serverTile = tile("Server answer time", h("span", { class: "sp-plain" }, p50 || "-"), p50 ? "our own server, the typical page view for people, over the date range above"
    : "not in the log: the server's log format needs the request time (Help › Getting started says how)");
  if (!everTested && file.status?.state !== "failing") {
    out.push(h("div", { class: "state sp-setup", html: ICON.info }, h("div", null, h("strong", null, "Page speed is not set up yet: no page has been tested. "),
      "The daily run tests the top 5 landing pages on a phone and a desktop with Google PageSpeed Insights once pagespeed.enabled is on (it is by default when the site's hosts are set) and a free PageSpeed API key is in pagespeed.api_key or the PSI_API_KEY setting; without a key Google often refuses. The first figures appear the day after.")),
    h("section", { class: "s" }, h("div", { class: "kpis" }, serverTile)));
    return out;
  }
  out.push(h("div", { class: "sp-bar" }, seg, h("span", { class: "sp-when" }, tested ? `Tested ${long(tested)}` : "Not tested yet")));
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    tile("Performance score", pill("score", score), "Google's lab score, median of the tested pages (0 to 100)"),
    tile("Largest paint (LCP)", pill("lcp_ms", vit("lcp_ms")), `when the main content showed; ${vitNote}`),
    tile("Layout shift (CLS)", pill("cls", vit("cls")), `how much the page jumped while loading; ${vitNote}`),
    tile("Response to input (INP)", pill("inp_ms", vit("inp_ms"), "Only real-user data has INP"), "how fast a tap or click showed a change; real users only"),
    serverTile)));

  const rows = latest.map((x) => ({ ...x, lcp: pick(x, "lcp_ms"), cls_v: pick(x, "cls"), inp: pick(x, "inp_ms"), src: x.ok ? from(x) : "Test failed" }));
  out.push(h("section", { class: "s sp-tbl" }, h("h2", null, `The top pages, on a ${strat === "mobile" ? "phone" : "desktop"}`),
    table([
      { key: "path", label: "Page", drill: "path", path: true },
      { key: "score", label: "Score", num: true, fmt: (v) => pill("score", v) },
      { key: "lcp", label: "LCP", num: true, fmt: (v) => pill("lcp_ms", v) },
      { key: "cls_v", label: "CLS", num: true, fmt: (v) => pill("cls", v) },
      { key: "inp", label: "INP", num: true, fmt: (v) => pill("inp_ms", v, "Only real-user data has INP") },
      { key: "src", label: "Measured", fmt: (v, x) => (x.ok ? v : h("span", { class: "status-bad", title: x.error || "" }, v)) },
    ], { caption: `Page speed of the top pages, ${strat}`, rows, file: `page-speed-${strat}.csv`, search: false, sortKey: "score", dir: 1, empty: "No page was tested on this device yet." })));

  // The trend: the site's median score on a phone and a desktop, a day without a test left blank.
  const last = trend.length ? trend[trend.length - 1].day : tested;
  if (last) {
    const by = { mobile: new Map((file.trend?.mobile || []).map((d) => [d.day, d])), desktop: new Map((file.trend?.desktop || []).map((d) => [d.day, d])) };
    const days = Array.from({ length: 30 }, (_, i) => addDays(last, i - 29)).map((day) => ({ day, state: by.mobile.has(day) || by.desktop.has(day) ? "ok" : "missing" }));
    const series = [
      { name: "Phone", color: "var(--g-people)", get: (d) => by.mobile.get(d.day)?.score ?? null },
      { name: "Desktop", color: "var(--g-search_engines)", get: (d) => by.desktop.get(d.day)?.score ?? null },
    ];
    out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Performance score, last 30 days"), h("span", { class: "tbl-count" }, `${short(days[0].day)} to ${short(last)}`)),
      h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not tested", "", "hatch"]], true),
        lines(days, series, { label: "Median performance score per day, phone and desktop", H: 200 }))));
  }
  return out;
}
