// A page's own dates in words (SKALD-64): published and last updated, where each
// came from, and every modified date Skald kept (page_index.json and the page story,
// lifecycle.py / page_dates.py). Shared by Page story, the Search drawers and the
// landing-page drawer, so each says the same thing the same way.
//
// A value is a date ("2024-11-05"), a UTC time ("2026-11-26T05:42:14Z", shown in the
// chosen zone) or a time the page gave without a zone (shown as written).

import { short, long } from "./ui.js";
import { stamp } from "./tz.js";
import { pageKey } from "./page-figs.js";

const FROM = { jsonld: "the page's structured data", meta: "the page's meta tags", time: "the page's date tag", sitemap: "your sitemap" };
export const fromWords = (src) => FROM[src] || src || "";

/* "26 Nov 05:42 EST" / "5 Nov 2024" / "26 Nov 2026, 05:42 (as the page wrote it)". */
export function whenWords(at, fmt = long) {
  const v = String(at || "");
  if (!v) return "";
  if (v.endsWith("Z")) return stamp(v);
  if (v.length > 10) return `${fmt(v.slice(0, 10))}, ${v.slice(11, 16)} (as the page wrote it)`;
  return fmt(v);
}

/* The page_index row of a path (every spelling of it), or null. */
export function rowFor(m, path) {
  const k = pageKey(path || "");
  return (m?.x?.page_index?.pages || []).find((p) => pageKey(p.path) === k) || null;
}

/* "Published 5 Nov 2024 · Last updated 26 Nov 05:42 EST", with where each came from, or "". */
export function datesLine(p, fmt = short) {
  if (!p) return "";
  const parts = [];
  if (p.published) {
    parts.push(p.date_source === "page" ? `Published ${p.published_at ? whenWords(p.published_at, fmt) : fmt(p.published)} (from ${fromWords(p.published_from)})`
      : p.date_source === "website" ? `Published ${fmt(p.published)} (from the website's page list)`
      : `First seen ${fmt(p.published)} (no publish date known)`);
  }
  if (p.updated) {
    parts.push(p.updated_source === "page" ? `Last updated ${p.updated_at ? whenWords(p.updated_at, fmt) : fmt(p.updated)} (from the page)`
      : p.updated_source === "sitemap" ? `Last changed ${fmt(p.updated)} (from your sitemap)` : `Last updated ${fmt(p.updated)}`);
  }
  return parts.join(" · ");
}

/* Each update day to mark on a chart: [{day, at, sources}], oldest first. The page's own
   and the sitemap's (p.changes) when Skald reads the page; else the sitemap's dates. */
export function updateMarks(p) {
  if (!p) return [];
  if (Array.isArray(p.changes) && p.changes.length) return p.changes;
  return (p.lastmod_seen || []).map(([d]) => ({ day: d, at: d, sources: ["sitemap"] }));
}

export const markWords = (c) => `Updated ${whenWords(c.at)} (from ${c.sources.map(fromWords).join(" and ")})`;

/* The last read of the page, when it could not read the dates: a short line, else "". */
export function checkWords(p) {
  const c = p?.check;
  if (!c || ["dated", "not_given", "not_html"].includes(c.outcome)) {
    return c?.outcome === "not_given" ? `The page gives no published or updated date (read ${stamp(c.at)}).` : "";
  }
  if (c.outcome === "redirected") return `Skald could not read the page's own dates on ${stamp(c.at)}: it redirects to another site. It looks again in a month, or when your sitemap says the page changed.`;
  const why = c.outcome === "blocked" ? "a bot check stopped Skald's request" : c.error || "it did not answer";
  return `Skald could not read the page's own dates on ${stamp(c.at)}: ${why}. It tries again within a day; until then the other dates Skald has are shown.`;
}

/* SVG for update markers on a chart drawn with x(i) over `days` (each {day} or a bucket
   {first, last}): a dashed line and a dot per marked slot, a <title> for the hover. */
export function markerSvg(marks, slots, x, top, bottom, color = "var(--ink-3)") {
  if (!marks.length || !slots.length) return "";
  const slotOf = (day) => slots.findIndex((s) => (s.first ? day >= s.first && day <= s.last : s.day === day));
  const at = new Map();
  for (const c of marks) {
    const i = slotOf(c.day);
    if (i >= 0) at.set(i, [...(at.get(i) || []), c]);
  }
  const esc = (t) => String(t).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
  return [...at].map(([i, list]) => {
    const cx = x(i).toFixed(1);
    return `<g class="upd-mark"><title>${esc(list.map(markWords).join("\n"))}</title>`
      + `<line x1="${cx}" x2="${cx}" y1="${top}" y2="${bottom}" stroke="${color}" stroke-width="1" stroke-dasharray="2 3"/>`
      + `<circle cx="${cx}" cy="${bottom}" r="4.5" fill="var(--surface)" stroke="${color}" stroke-width="1.6"/></g>`;
  }).join("");
}
