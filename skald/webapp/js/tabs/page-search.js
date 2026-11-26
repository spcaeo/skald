// Google Search for one page, in the page drawer (Traffic › Pages, dd=landing:<path> or
// path:<path>; SKALD-64): the page's published and last updated dates, Search Console's
// clicks, impressions, CTR and average position over Google's own days against the days
// before, a chart of impressions and position with a mark for each of the page's updates,
// and the page's top queries and countries.
//
// From GET <page>/api/page-search?path=&days= (search/page_panel.py: the MCP's audited
// per-page figures, never Skald's own count) and page_index.json (the dates). Google has
// no "today" and is two or three days late, so this section keeps Google's days and says so.

import { h, n, short, esc, tip, untip } from "../ui.js";
import { getJSON, need } from "../data.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { rove } from "../place.js";
import { ALPHA3 } from "../countries.js";
import { countryWords } from "./readers.js";
import { rowFor, datesLine, updateMarks, markerSvg, checkWords } from "../page-dates.js";

const SETTINGS = "#settings/site/leads?tool=search";
const BAR = "var(--g-search_engines)";
const LINE = "var(--ink-2)";
const TO2 = Object.fromEntries(Object.entries(ALPHA3).map(([two, three]) => [three, two]));
const pct = (v) => (v == null ? "-" : `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`);
const pos = (v) => (v == null ? "-" : Number(v).toFixed(1));

/* "+12%" / "-3" / "up 2.1": the change against the days before, or "". */
function delta(now, was, kind) {
  if (now == null || was == null) return "";
  if (kind === "position") {
    const d = was - now;                       // a lower position is better
    return Math.abs(d) < 0.05 ? "no move" : `${d > 0 ? "up" : "down"} ${Math.abs(d).toFixed(1)}`;
  }
  if (kind === "ctr") {
    const d = (now - was) * 100;
    return Math.abs(d) < 0.05 ? "same" : `${d > 0 ? "+" : ""}${d.toFixed(1)} pts`;
  }
  if (!was) return now ? "new" : "same";
  const d = Math.round(((now - was) / was) * 100);
  return d === 0 ? "same" : `${d > 0 ? "+" : ""}${d}%`;
}

function kpis(t, b, whole) {
  if (!whole) b = null;                        // the days before are not all stored: no change shown
  const cells = [["Clicks", t?.clicks, b?.clicks, "count", n], ["Impressions", t?.impressions, b?.impressions, "count", n],
    ["CTR", t?.ctr, b?.ctr, "ctr", pct], ["Average position", t?.position, b?.position, "position", pos]];
  return h("div", { class: "dd-kpis" }, cells.map(([name, now, was, kind, fmt]) => h("div", null,
    h("b", null, now == null ? "-" : fmt(now)), h("span", null, name),
    delta(now, was, kind) ? h("small", { class: "muted" }, ` ${delta(now, was, kind)}`) : null)));
}

/* Impressions as bars (left axis), average position as a line (right axis, 1 at the top),
   a dashed mark for each update; a day with no figures is a gap, a provisional one hollow. */
function chart(days, marks, width) {
  if (!days.some((d) => d.impressions != null)) return null;
  const W = Math.max(360, Math.min(width || 640, 900)), H = 200, L = 46, R = 40, T = 12, B = 26;
  const k = days.length, slot = (W - L - R) / Math.max(1, k);
  const x = (i) => L + slot * (i + 0.5);
  const top = Math.max(1, ...days.map((d) => d.impressions || 0));
  const yi = (v) => T + (1 - v / top) * (H - T - B);
  const ps = days.map((d) => d.position).filter((v) => v != null);
  const pTop = ps.length ? Math.max(1, Math.floor(Math.min(...ps))) : 1;
  const pBot = ps.length ? Math.max(pTop + 1, Math.ceil(Math.max(...ps))) : 2;
  const yp = (v) => T + ((v - pTop) / (pBot - pTop)) * (H - T - B);
  const out = [];
  for (const v of [0, top / 2, top]) out.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${yi(v).toFixed(1)}" y2="${yi(v).toFixed(1)}"/><text x="${L - 6}" y="${(yi(v) + 4).toFixed(1)}" text-anchor="end">${esc(n(Math.round(v)))}</text>`);
  for (const v of [pTop, pBot]) out.push(`<text x="${W - R + 6}" y="${(yp(v) + 4).toFixed(1)}">${v}</text>`);
  const gap = k <= 10 ? 1 : k <= 31 ? 7 : 14;
  days.forEach((d, i) => { if ((k - 1 - i) % gap === 0) out.push(`<text x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(short(d.day))}</text>`); });
  days.forEach((d, i) => {
    if (d.impressions == null) return;
    const y = yi(d.impressions), bw = Math.max(1, slot * 0.7);
    out.push(`<rect x="${(x(i) - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, H - B - y).toFixed(1)}" fill="${BAR}" opacity="${d.final ? 0.55 : 0.3}"/>`);
  });
  for (let i = 1; i < k; i++) {
    const a = days[i - 1].position, b = days[i].position;
    if (a == null || b == null) continue;
    const dash = !days[i].final || !days[i - 1].final;
    out.push(`<line x1="${x(i - 1).toFixed(1)}" y1="${yp(a).toFixed(1)}" x2="${x(i).toFixed(1)}" y2="${yp(b).toFixed(1)}" stroke="${LINE}" stroke-width="2"${dash ? ' stroke-dasharray="4 4"' : ""}/>`);
  }
  out.push(markerSvg(marks, days, x, T, H - B));
  days.forEach((d, i) => out.push(`<rect class="hit" data-i="${i}" x="${(L + slot * i).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}" fill="transparent"/>`));
  const el = h("div", { class: "chart" });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc("Impressions per day as bars, average position as a line; 1 is the top")}">${out.join("")}</svg>`;
  const hits = el.querySelectorAll(".hit");
  hits.forEach((hit) => {
    const d = days[Number(hit.dataset.i)];
    const show = (cx, cy) => tip(cx, cy, `${short(d.day)}${d.final ? "" : " (provisional)"}`, d.impressions == null
      ? [{ value: "", label: "Not in that day's top list: not known" }]
      : [{ color: BAR, value: n(d.impressions), label: "Impressions" }, { value: n(d.clicks), label: "Clicks" },
        { value: pct(d.ctr), label: "CTR" }, { color: LINE, value: pos(d.position), label: "Average position" }]);
    hit.addEventListener("pointermove", (ev) => show(ev.clientX, ev.clientY));
    hit.addEventListener("pointerleave", untip);
    hit.addEventListener("focus", () => { const r = hit.getBoundingClientRect(); show(r.left + r.width / 2, r.top + 30); });
    hit.addEventListener("blur", untip);
  });
  rove(hits);
  return el;
}

function queries(got) {
  if (!got.queries?.length) return h("p", { class: "empty" }, "No query is listed for this page in these days: Google keeps each day's largest query and page pairs only.");
  return table([
    { key: "query", label: "Query" }, { key: "clicks", label: "Clicks", num: true }, { key: "impressions", label: "Impressions", num: true },
    { key: "ctr", label: "CTR", num: true, fmt: pct }, { key: "position", label: "Position", num: true, fmt: pos },
  ], { caption: "The page's queries", rows: got.queries, sortKey: "clicks", dir: -1, limit: 10, file: "page-queries.csv",
    rowClass: () => "go", onRow: (q) => S.set({ tab: "traffic/search", dd: "", sq: `query.google:${q.query}` }) });
}

function countries(got) {
  if (!got.countries?.length) return null;
  return table([
    { key: "country", label: "Country", fmt: (v) => { const k = String(v || "").toUpperCase(); return k === "ZZZ" ? "Not recorded by Google" : TO2[k] ? countryWords(TO2[k]) : k; } },
    { key: "clicks", label: "Clicks", num: true }, { key: "impressions", label: "Impressions", num: true },
    { key: "position", label: "Position", num: true, fmt: pos },
  ], { caption: "The page's countries", rows: got.countries, sortKey: "impressions", dir: -1, limit: 5, file: "page-countries.csv", search: false });
}

/* The section, drawn when its answer comes; null when this page has no helper to ask. */
export function pageSearch(m, path, { days = 28, width = 640 } = {}) {
  if (!path || !path.startsWith("/")) return null;
  const box = h("section", { class: "s dd-search" }, h("h3", null, "Google Search"), h("p", { class: "muted", role: "status" }, "Loading Search Console's figures…"));
  const wanted = Math.max(28, Math.min(93, days || 28));
  Promise.all([getJSON(`api/page-search?path=${encodeURIComponent(path)}&days=${wanted}`).catch(() => null), need(m, ["page_index"]).catch(() => null)]).then(([got]) => {
    if (!box.isConnected && !box.parentNode) return;
    if (!got || !got.ok) { box.remove(); return; }
    const p = rowFor(m, path);
    const dates = [datesLine(p), checkWords(p)].filter(Boolean).join(" ");
    const head = [h("h3", null, "Google Search"), dates ? h("p", { class: "se-dates" }, dates) : ""].filter(Boolean);
    if (!got.connected) {
      box.replaceChildren(...head, h("p", { class: "note" }, "Search Console is not connected for this site, so Google's clicks, impressions and positions for this page are not here. ", h("a", { href: SETTINGS }, "Connect it in Settings")));
      return;
    }
    const marks = updateMarks(p);
    const missing = got.not_in_page_table?.length || 0;
    const where = countries(got);
    box.replaceChildren(...[...head,
      h("p", { class: "sub" }, `Search Console's figures, ${short(got.first)} to ${short(got.last)} (Pacific Time days; Google has none for today and is two or three days late), against the ${got.length} days before.${got.address !== got.path ? ` Google lists this page as ${got.address}.` : ""}`),
      kpis(got.totals, got.before?.totals, !got.before?.totals_partial && !got.before?.missing_days?.length),
      chart(got.days || [], marks, width) || h("p", { class: "empty" }, "Google showed this page in no search in these days."),
      h("p", { class: "note" }, [
        "Bars: impressions; line: average position (right axis, 1 is the top).",
        marks.length ? " Dashed marks: the page's updates (hover for the date and where it comes from)." : "",
        missing ? ` ${n(missing)} day${missing === 1 ? " was" : "s were"} below that day's top list of pages, so ${missing === 1 ? "it is" : "they are"} a gap and not in the sums.` : "",
        got.provisional_days?.length ? " Light bars and dashes: provisional, Google may still change them." : "",
        got.before?.totals_partial || got.before?.missing_days?.length ? " No change is shown: Skald does not hold every day of the days before." : ""].join("")),
      h("h3", null, "Its queries"), queries(got), where ? h("h3", null, "Its countries") : "", where || ""].filter(Boolean));
  }).catch(() => box.remove());
  return box;
}
