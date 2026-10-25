// Traffic > Search (P1-6): what Google Search Console and Bing Webmaster Tools say
// about the site's search results: clicks, impressions, CTR and average position by
// day, query, page, country, device and search appearance; and, for Google, its
// clicks beside Skald's own people from Google search (the cross-check).
//
// From search.json (skald/search/data.py). These are the engines' figures,
// synced every few hours: never Skald's count, never added to one. A day the engine
// may still change is "provisional" and drawn dashed. The engine and the period
// (7 days, 28 days, 3 months, 16 months, up to the newest day the engine has) are
// this tab's own; the page's period bar does not apply.

import { h, n, esc, long, short, addDays, tip, untip, ICON } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { lines, legend, scale } from "../charts.js";
import { openDrawer } from "../drawer.js";
import { time as tzTime } from "../tz.js";
import { ALPHA3 } from "../countries.js";
import { rove } from "../place.js";
import { countryWords } from "./readers.js";
import { info } from "./tiles.js";
import { head, notBuiltNote } from "./common.js";
import { figures } from "../data.js";
import { subView } from "../tablestate.js";
import { withUrl, copyIf } from "../urlactions.js";

const PERIODS = [["7", "7 days"], ["28", "28 days"], ["90", "3 months"], ["480", "16 months"]];
const ENGINES = [["google", "Google"], ["bing", "Bing"]];
const COLOR = "var(--g-search_engines)";
const OURS = "var(--g-people)";
const KINDS = [
  ["query", "Queries", "Query"], ["page", "Pages", "Page"], ["country", "Countries", "Country"],
  ["device", "Devices", "Device"], ["appearance", "Search appearance", "Appearance"],
];
const DEVICES = { DESKTOP: "Desktop", MOBILE: "Phone", TABLET: "Tablet" };
const TO2 = Object.fromEntries(Object.entries(ALPHA3).map(([two, three]) => [three, two]));
const SETTINGS = "#settings/integrations";

// This tab's own choices, kept while the page is open.
let engine = "";
let per = "28";
let metric = "clicks";
// The engine, the period and the measure stay in the address (seeng_view, seper_view,
// semet_view: tablestate.js subView), so a link brings the same view back.
const KEPT = { engine: subView("seeng"), per: subView("seper"), metric: subView("semet") };

const pct = (v) => (v == null ? "-" : `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`);
const pos = (v) => (v == null ? "-" : v.toFixed(1));
const ctrOf = (c, i) => (i ? c / i : null);
const nameOf = (e) => (e === "bing" ? "Bing" : "Google");
const toolOf = (e) => (e === "bing" ? "Bing Webmaster Tools" : "Search Console");

function seg(label, items, value, pick) {
  return h("div", { class: "seg plain", role: "group", "aria-label": label },
    items.map(([k, w]) => h("button", { type: "button", "aria-pressed": String(value === k), onclick: () => pick(k) }, w)));
}

function countryLabel(key) {
  const k = String(key || "").toUpperCase();
  if (k === "ZZZ" || !k) return h("span", null, "Not recorded by Google");
  const two = TO2[k];
  return two ? countryWords(two) : h("span", null, k);
}

function labelOf(kind, key) {
  if (kind === "country") return countryLabel(key);
  if (kind === "device") return DEVICES[String(key).toUpperCase()] || key;
  return key;
}

const textOf = (kind, key) => {
  const v = labelOf(kind, key);
  return v instanceof Node ? v.textContent : String(v);
};

function pagePath(url) {
  try { return new URL(url).pathname || "/"; } catch { return url; }
}

// ------------------------------------------------------------------ status

function statusBlock(part, e) {
  const st = part.status || {};
  const sum = part.summary || {};
  const out = [];
  const bits = [];
  if (st.last_sync) bits.push(`Last synced ${tzTime(st.last_sync, { date: true })}`);
  if (st.next_sync && part.connected) bits.push(`next ~${tzTime(st.next_sync, { date: true, label: false })}`);
  if (sum.days) bits.push(`${n(sum.days)} day${sum.days === 1 ? "" : "s"} stored, newest ${long(sum.last)}`);
  if (sum.provisional) bits.push(`${n(sum.provisional)} provisional`);
  if (bits.length) out.push(h("p", { class: "se-status" }, bits.join(" · "),
    sum.provisional ? info(`${toolOf(e)} may still change its newest days. Skald fetches them again on every sync until the engine says they are final.`, "Provisional days") : null));
  if (st.error) out.push(h("div", { class: "state warn", role: "alert", html: ICON.info }, h("div", null,
    h("strong", null, `The ${toolOf(e)} sync is failing${st.error_since ? ` since ${tzTime(st.error_since, { date: true })}` : ""}. `), st.error,
    " The figures already synced stay here. ", h("a", { href: SETTINGS }, "Settings › Integrations › Search"))));
  const b = st.backfill;
  if (b && (b.state === "running" || b.state === "queued")) out.push(h("div", { class: "state" }, h("div", null,
    h("strong", null, "Syncing the history. "), b.of ? `${n(b.done || 0)} of ${n(b.of)} weeks done.` : "Starting...", " Figures appear as each week arrives.")));
  if (b && b.state === "failed") out.push(h("div", { class: "state warn" }, h("div", null, h("strong", null, "The history sync stopped. "), b.error || "")));
  const a = st.audit;
  if (a && a.ok === false) out.push(h("div", { class: "state warn", role: "alert" }, h("div", null,
    h("strong", null, "The second check found a difference. "), "Skald adds the stored figures up again and asks the engine for one day again; this did not agree: ",
    (a.problems || []).slice(0, 3).join("; "), ".")));
  else if (a && a.ok) out.push(h("p", { class: "note" }, `Checked a second way ${tzTime(a.at, { date: true })}: the stored figures add up and the newest final day matches what ${toolOf(e)} says now.`));
  if (st.note) out.push(h("p", { class: "note" }, st.note));
  return out;
}

// ------------------------------------------------------------------ setup

function setupBlock(file, e) {
  const google = e === "google";
  const keySet = file.keys?.[e];
  const steps = google ? [
    keySet ? "The install's Google service-account key is in place." : "An install admin uploads a Google service-account key in Settings › Integrations › Search. One key serves every site.",
    "In Search Console › Settings › Users and permissions, add the service account's email with Restricted (read-only) access. Settings shows the email, and text to send a client whose site it is.",
    "Back in Settings › Integrations › Search: Find my properties, Test connection, then Connect. The history (3 or 16 months) syncs in the background; after that Skald syncs by itself every 6 hours.",
  ] : [
    keySet ? "The install's Bing API key is in place." : "An install admin types a Bing Webmaster Tools API key in Settings › Integrations › Search (Bing Webmaster Tools › Settings › API access).",
    "The site must be added and verified in Bing Webmaster Tools under that key's account; for a client's site, the client adds that account as a user.",
    "Back in Settings › Integrations › Search: Find my sites, Test connection, then Connect. Skald syncs by itself every 6 hours.",
  ];
  return h("div", { class: "state se-setup", html: ICON.info }, h("div", null,
    h("strong", null, google ? "Connect Search Console" : "Connect Bing Webmaster Tools"),
    h("p", null, google ? "The log cannot see a search: no query, no impression, no position. Only Google holds them. Connect Search Console and Skald keeps a copy here, beside its own figures, never mixed with them."
      : "Bing's queries, pages, clicks and impressions, from Bing Webmaster Tools."),
    h("ol", null, steps.map((x) => h("li", null, x))),
    h("p", null, h("a", { class: "btn", href: SETTINGS }, google ? "Connect Search Console" : "Connect Bing"))));
}

// ------------------------------------------------------------------ chart

const METRICS = {
  clicks: { name: "Clicks", get: (d) => d.clicks, fmt: n },
  impressions: { name: "Impressions", get: (d) => d.impressions, fmt: n },
  ctr: { name: "CTR", get: (d) => d.ctr, fmt: pct, unit: 100 },
  position: { name: "Average position", get: (d) => d.position, fmt: pos, invert: true },
};

/* One measure per day (one axis): a solid line for final days, dashed into and
   between provisional ones, a hollow ring on each provisional day. A day the engine
   has no row for breaks the line; it is never drawn as zero. Position runs top down:
   1 is the top result. */
function trend(daysIn, key) {
  const M = METRICS[key];
  const p = document.getElementById("panel");
  const W = Math.max(300, Math.min(1180, Math.round(p ? p.clientWidth - 80 : 720)));
  const H = 220, L = 52, R = 12, T = 14, B = 28;
  const pw = W - L - R, ph = H - T - B;
  const vals = daysIn.map((d) => { const v = M.get(d); return v == null ? null : v * (M.unit || 1); });
  const top = Math.max(0, ...vals.filter((v) => v != null));
  const [max, step] = top < 4 && key === "ctr" ? [Math.max(1, Math.ceil(top)), Math.max(0.25, Math.ceil(top) / 4)] : scale(Math.ceil(top));
  const lo = M.invert ? 1 : 0;
  const k = daysIn.length, slot = pw / Math.max(1, k);
  const y = (v) => (M.invert ? T + ((v - lo) / Math.max(1, max - lo)) * ph : T + ph - (v / max) * ph);
  const x = (i) => L + slot * (i + 0.5);
  const out = [];
  for (let v = M.invert ? lo : 0; v <= max + 1e-9; v += M.invert ? Math.max(1, step) : step) {
    out.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>`,
      `<text x="${L - 8}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${esc(key === "ctr" ? `${+v.toFixed(2)}%` : n(v))}</text>`);
  }
  const gap = k <= 10 ? 1 : k <= 31 ? 7 : k <= 100 ? 14 : 60;
  daysIn.forEach((d, i) => {
    if ((k - 1 - i) % gap === 0) out.push(`<text x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(short(d.day))}</text>`);
  });
  out.push(`<line class="axis" x1="${L}" x2="${W - R}" y1="${T + ph}" y2="${T + ph}"/>`);
  for (let i = 1; i < k; i++) {
    if (vals[i] == null || vals[i - 1] == null) continue;
    const dash = !daysIn[i].final || !daysIn[i - 1].final;
    out.push(`<line x1="${x(i - 1).toFixed(1)}" y1="${y(vals[i - 1]).toFixed(1)}" x2="${x(i).toFixed(1)}" y2="${y(vals[i]).toFixed(1)}" stroke="${COLOR}" stroke-width="2" stroke-linecap="round"${dash ? ' stroke-dasharray="4 4"' : ""}/>`);
  }
  daysIn.forEach((d, i) => {
    if (vals[i] == null) return;
    const lone = (i === 0 || vals[i - 1] == null) && (i === k - 1 || vals[i + 1] == null);
    if (!d.final) out.push(`<circle cx="${x(i).toFixed(1)}" cy="${y(vals[i]).toFixed(1)}" r="4" fill="var(--surface)" stroke="${COLOR}" stroke-width="2"/>`);
    else if (lone) out.push(`<circle cx="${x(i).toFixed(1)}" cy="${y(vals[i]).toFixed(1)}" r="4" fill="${COLOR}" stroke="var(--surface)" stroke-width="2"/>`);
  });
  out.push(`<line class="hair" x1="0" x2="0" y1="${T}" y2="${T + ph}" opacity="0"/><g class="dots"></g>`);
  daysIn.forEach((d, i) => out.push(`<rect class="hit" data-i="${i}" x="${(L + slot * i).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${ph}" aria-label="${esc(`${long(d.day)}: ${M.name} ${M.fmt(M.get(d))}${d.final ? "" : ", provisional"}`)}"/>`));
  const el = h("div", { class: "chart" });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`${M.name} per day`)}">${out.join("")}</svg>`;
  const svg = el.querySelector("svg"), hair = svg.querySelector(".hair"), dots = svg.querySelector(".dots");
  const hits = el.querySelectorAll(".hit");
  hits.forEach((hit) => {
    const i = Number(hit.dataset.i), d = daysIn[i];
    const show = (cx, cy) => {
      hair.setAttribute("x1", x(i)); hair.setAttribute("x2", x(i)); hair.setAttribute("opacity", "1");
      dots.innerHTML = vals[i] == null ? "" : `<circle cx="${x(i)}" cy="${y(vals[i]).toFixed(1)}" r="4" fill="${COLOR}" stroke="var(--surface)" stroke-width="2"/>`;
      tip(cx, cy, long(d.day) + (d.final ? "" : " (provisional)"), d.clicks == null ? [{ value: "", label: "No row from the engine for this day" }] : [
        { color: COLOR, value: n(d.clicks), label: "Clicks" }, { value: n(d.impressions), label: "Impressions" },
        { value: pct(d.ctr), label: "CTR" }, { value: pos(d.position), label: "Average position" }]);
    };
    const hide = () => { hair.setAttribute("opacity", "0"); dots.innerHTML = ""; untip(); };
    hit.addEventListener("pointermove", (ev) => show(ev.clientX, ev.clientY));
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", () => { const r = hit.getBoundingClientRect(); show(r.left + r.width / 2, r.top + 30); });
    hit.addEventListener("blur", hide);
  });
  rove(hits);
  return el;
}

// ------------------------------------------------------------------ tables

function rowDrawer(kind, row, part, period, s, file) {
  const e = engine;
  const facts = [["Clicks", n(row.clicks)], ["Impressions", n(row.impressions)], ["CTR", pct(row.ctr)], ["Average position", pos(row.position)]];
  const body = [h("dl", { class: "se-facts" }, facts.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)])),
    h("p", { class: "note" }, `${toolOf(e)}'s figures, ${short(period.first)} to ${short(period.last)}${e === "google" ? " (Pacific Time days)" : ""}. Summed from each day's top rows: on a day this ${kind} was below the top list it counts in "(all others)" instead.`)];
  if (kind === "page") {
    const path = pagePath(row.key);
    const ours = (file.crosscheck?.pages || []).find((p) => p.path === path);
    if (ours && e === "google") body.push(h("p", null, `Skald's people from Google search on this page, over the cross-check's days: ${n(ours.skald_visits)} (Search Console: ${n(ours.search_console_clicks)} clicks).`));
    body.push(h("p", null, h("a", { href: S.hashFor({ ...s, tab: "traffic/pages", page: path, dd: "" }) }, `Open ${path}: its story since it was published`)));
  }
  if (kind === "query") body.push(h("p", { class: "note" }, "The engine does not give, in this table, which page each query led to."));
  // In the address as sq=<kind>.<engine>:<key> (js/overlays.js): a link reopens it.
  const title = kind === "query" ? copyIf("text", textOf(kind, row.key), String(row.key), { label: "query" }) : kind === "page" ? withUrl(textOf(kind, row.key), String(row.key), { cls: "ua-after" }) : textOf(kind, row.key);
  return openDrawer({ title, subtitle: `${nameOf(e)} search, ${KINDS.find((x) => x[0] === kind)[2].toLowerCase()}`, body: h("div", null, body), size: "md", key: "search-row",
    route: { key: "sq", value: `${kind}.${e}:${row.key}` } });
}

/* sq=<kind>.<engine>:<key>, from a link: the row in the period on screen, else the plain line. */
export function openSearchKey(m, s, value) {
  const [, kind, e, key] = /^([a-z]+)\.(google|bing):(.*)$/s.exec(String(value)) || [];
  const file = m?.x?.search;
  const part = file?.engines?.[e];
  if (!kind || !part?.connected) return "That search row is not in the figures on this page: the engine is not connected here.";
  engine = e;
  const period = part.periods?.[per];
  const row = (period?.[kind]?.rows || []).find((x) => String(x[0]) === key);
  if (!row) return `That search row is not in the ${PERIODS.find(([k]) => k === per)?.[1] || "period"} on screen. Choose a longer period, or it is no longer among the engine's rows.`;
  const [k2, clicks, impressions, ctr, position] = row;
  return rowDrawer(kind, { key: k2, label: textOf(kind, k2), clicks, impressions, ctr, position }, part, period, s, file);
}

function kindTable(kind, title, colName, blob, part, period, s, file) {
  const e = engine;
  const rows = (blob.rows || []).map(([key, clicks, impressions, ctr, position]) => ({ key, label: textOf(kind, key), clicks, impressions, ctr, position }));
  const t = table([
    { key: "label", label: colName, path: kind === "page", href: (r) => r.key, fmt: (v, r) => labelOf(kind, r.key) },
    { key: "clicks", label: "Clicks", num: true },
    { key: "impressions", label: "Impressions", num: true },
    { key: "ctr", label: "CTR", type: "num", fmt: pct },
    { key: "position", label: "Position", type: "num", fmt: pos, title: "Average position: 1 is the top result" },
  ], { caption: `${nameOf(e)} search, ${title.toLowerCase()}`, rows, file: `search-${e}-${kind}-${per}d.csv`, sortKey: "clicks",
    placeholder: `Search ${title.toLowerCase()}`, empty: `No ${title.toLowerCase()} in these days.`, rowDrill: false,
    onRow: (r) => rowDrawer(kind, r, part, period, s, file) });
  const foot = [];
  const o = blob.others || {};
  if (o.rows) foot.push(h("li", null, h("b", null, "(all others) "), `${n(o.rows)} more rows: ${n(o.clicks)} clicks, ${n(o.impressions)} impressions, position ${pos(o.position)}`,
    info("Rows past the top of each day's list, summed. They are real clicks and impressions; they cannot be split further.", "(all others)")));
  const u = blob.unattributed || {};
  if (u.clicks > 0 || u.impressions > 0) foot.push(h("li", null, h("b", null, `Not given by ${nameOf(e)} `), `${n(u.clicks)} clicks, ${n(u.impressions)} impressions`,
    info(kind === "query" ? "Google counts these in its totals but leaves the queries out of its query table (rare or personal searches it anonymises). Shown, never hidden." : `${nameOf(e)} counts these in its total but gives no ${colName.toLowerCase()} for them.`, `Not given by ${nameOf(e)}`)));
  if (u.clicks < 0 || u.impressions < 0) foot.push(h("li", null, h("b", null, "Counted under more than one row "), `${n(-Math.min(0, u.clicks))} clicks, ${n(-Math.min(0, u.impressions))} impressions`,
    info("One result can show in more than one way (say, a rich result and a video), so these rows add up to more than the total.", "Counted under more than one row")));
  if (blob.folded_days) foot.push(h("li", { class: "muted" }, `On ${n(blob.folded_days)} of these days some rows were below the day's top list and are in (all others) for those days, so a row's sum here can be short.`));
  const tot = blob.total || {};
  const head = h("div", { class: "card-h start" }, h("h2", null, title),
    kind === "appearance" ? info("Google's own names, as its API gives them. Its API names no AI Overview or AI Mode figure today; if Google adds one, it appears here under Google's own name.", "Search appearance") : null,
    h("span", { class: "tbl-count" }, `${n(tot.clicks)} clicks · ${n(tot.impressions)} impressions in all`));
  return h("section", { class: "s" }, head, t, foot.length ? h("ul", { class: "se-foot" }, foot) : null);
}

// ------------------------------------------------------------------ cross-check

function crossBlock(x, s) {
  const head = [h("h2", null, "Search Console clicks beside Skald's people from Google"),
    h("p", { class: "sub" }, "Two different counts, side by side: Google's clicks on its results, and the visits Skald saw arrive from Google search and draw a page. They are not expected to match; the difference is shown and explained, never hidden or forced.")];
  if (!x || x.state || !(x.days || []).length) {
    return h("section", { class: "s" }, ...head, h("p", { class: "empty" }, x?.state ? `Not yet: ${x.state}.` : "No day both sides have yet."));
  }
  const t = x.totals || {};
  const out = [...head];
  if (x.flag) out.push(h("div", { class: "state warn", role: "alert" }, h("div", null, x.flag)));
  out.push(h("p", { class: "se-cross-sum" }, `Over ${n(x.days.length)} days: Search Console ${n(t.search_console_clicks)} clicks, Skald ${n(t.skald_visits)} people from Google search; difference ${t.difference > 0 ? "+" : ""}${n(t.difference)}${t.ratio != null ? ` (${t.ratio.toFixed(2)} visits per click)` : ""}.`));
  const days = x.days.map((d) => ({ ...d, state: "ok" }));
  const series = [
    { name: "Search Console clicks", color: COLOR, get: (d) => d.search_console_clicks },
    { name: "Skald: people from Google", color: OURS, get: (d) => d.skald_visits },
  ];
  out.push(h("div", { class: "sheet" }, legend(series.map((z) => [z.name, z.color]), true), lines(days, series, { label: "Search Console clicks and Skald's people from Google search, per day", H: 200 })));
  const diff = (v) => `${v > 0 ? "+" : ""}${n(v)}`;
  out.push(h("div", { class: "cols tr-one" },
    h("div", null, h("h3", null, "Per day"), table([
      { key: "day", label: "Day", type: "date", fmt: (v) => short(v) },
      { key: "search_console_clicks", label: "Search Console clicks", num: true },
      { key: "skald_visits", label: "Skald visits", num: true },
      { key: "difference", label: "Difference", type: "num", fmt: diff },
    ], { caption: "Cross-check per day", rows: x.days, file: "search-crosscheck-days.csv", sortKey: "day", dir: -1, search: false, limit: 10, rowDrill: false })),
    h("div", null, h("h3", null, "Per landing page"), table([
      { key: "path", label: "Page", path: true, fmt: (v) => h("a", { href: S.hashFor({ ...s, tab: "traffic/pages", page: v, dd: "" }) }, v) },
      { key: "search_console_clicks", label: "Search Console clicks", num: true },
      { key: "skald_visits", label: "Skald visits", num: true },
      { key: "difference", label: "Difference", type: "num", fmt: diff },
    ], { caption: "Cross-check per landing page", rows: x.pages || [], file: "search-crosscheck-pages.csv", sortKey: "search_console_clicks", limit: 10, rowDrill: false }))));
  out.push(h("h3", null, "Why they differ"), h("ul", { class: "se-notes" }, (x.notes || []).map((z) => h("li", null, z))));
  if ((x.left_out || []).length) out.push(h("p", { class: "note" }, `Left out: ${x.left_out.map((d) => `${short(d.day)} (${d.why})`).join(", ")}.`));
  return h("section", { class: "s" }, out);
}

// ------------------------------------------------------------------ the tab

export default function search(m, s) {
  const file = m.x.search;
  const root = h("div", { class: "se" });
  const { r } = figures(m, s);
  const top = head("Search", r, "What people searched for, how often the site showed and was clicked, and where it ranked: Google Search Console's and Bing Webmaster Tools' own figures, synced here every 6 hours. Never Skald's own count, and never added to one.",
    { banner: false, period: "The engines' own days, up to the newest they have" });
  if (!file) {
    return [...top, notBuiltNote(m, "search", "Search") || h("div", { class: "state" }, h("div", null, "The search figures appear after the next redraw."))];
  }
  const parts = file.engines || {};
  if (["google", "bing"].includes(KEPT.engine.get())) engine = KEPT.engine.get();
  if (PERIODS.some(([k]) => k === KEPT.per.get())) per = KEPT.per.get();
  if (METRICS[KEPT.metric.get()]) metric = KEPT.metric.get();
  if (!engine) engine = parts.google?.connected || !parts.bing?.connected ? "google" : "bing";

  const paint = () => {
    const part = parts[engine] || {};
    const out = [];
    out.push(h("div", { class: "se-bar" }, seg("Search engine", ENGINES, engine, (k) => { engine = k; KEPT.engine.set(k); paint(); }),
      part.connected && part.summary?.days ? seg("Period", PERIODS, per, (k) => { per = k; KEPT.per.set(k, "28"); paint(); }) : null,
      part.connected ? h("span", { class: "se-src" }, `${toolOf(engine)}: ${part.connected}`) : null));
    if (file.view_note) out.push(h("p", { class: "note" }, file.view_note));
    if (!part.connected) {
      out.push(setupBlock(file, engine));
      if (part.summary?.days) out.push(h("p", { class: "note" }, `Not connected now. ${n(part.summary.days)} days synced before stay in history.`));
      root.replaceChildren(...out);
      return;
    }
    out.push(...statusBlock(part, engine));
    const period = part.periods?.[per];
    if (!period || !part.summary?.days) {
      out.push(h("p", { class: "empty" }, "Connected. The first figures appear after the first sync."));
      root.replaceChildren(...out);
      return;
    }
    const t = period.totals || {};
    const google = engine === "google";
    const tile = (label, value, line, about) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, label, info(about, label)), h("div", { class: "k-n" }, line), h("div", { class: "k-v" }, value), h("div", { class: "k-c" }));
    const when = `${short(period.first)} to ${short(period.last)}${google ? ", Pacific Time days" : ""}`;
    out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
      tile("Clicks", n(t.clicks), when, `Clicks on the site in ${nameOf(engine)}'s results. A click is not a visit: see the cross-check below.`),
      tile("Impressions", n(t.impressions), period.provisional_days?.length ? `${period.provisional_days.length} provisional day${period.provisional_days.length === 1 ? "" : "s"}` : "every day final",
        `How often a result of the site was shown in ${nameOf(engine)}'s results.`),
      tile("CTR", pct(t.ctr), "clicks per impression", "Clicks divided by impressions over these days."),
      tile("Average position", pos(t.position), "1 is the top result", "The average of the site's best position in each result shown, weighted by impressions. Lower is better."))));
    const inRange = (part.days || []).filter((d) => d.day >= period.first && d.day <= period.last);
    if (inRange.length) {
      const byDay = new Map(inRange.map((d) => [d.day, d]));
      const all = [];
      for (let d = period.first; d <= period.last; d = addDays(d, 1)) all.push(byDay.get(d) || { day: d, final: true, clicks: null, impressions: null, ctr: null, position: null });
      out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, `${METRICS[metric].name} per day`),
        seg("Measure", Object.entries(METRICS).map(([k, v]) => [k, v.name]), metric, (k) => { metric = k; KEPT.metric.set(k, "clicks"); paint(); })),
      h("div", { class: "sheet" }, legend([["Final", COLOR], ["Provisional: may still change", "", "ghost"]], true), trend(all, metric))));
    }
    for (const [kind, title, col] of KINDS) {
      const blob = period[kind];
      if (blob) out.push(kindTable(kind, title, col, blob, part, period, s, file));
    }
    if (!google) out.push(h("p", { class: "note" }, "Bing gives its top queries and pages only, updated weekly, each under the date Bing gives; their sum is not the site's whole Bing traffic. Bing's Copilot citations have no API yet, so they are not here."));
    if (google) out.push(crossBlock(file.crosscheck, s));
    root.replaceChildren(...out);
  };
  paint();
  return [...top, root];
}
