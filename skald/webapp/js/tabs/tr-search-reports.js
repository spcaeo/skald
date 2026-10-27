// Traffic > Search: Search Console's reports, from the days Skald already synced
// (skald/search/reports.py, each period of search.json): where a page could win
// more clicks (opportunities), the queries that came and went (new and lost, on whole
// days only), each query's and page's average position over time, and how much of the
// period the history holds (coverage). Drawn by tabs/tr-search.js, one section at a time.
//
// The address keeps every choice (tablestate.js subView, <ns>_view): the rule shown
// (seopr), new or lost (senl), queries or pages (sepk), and which list is fully shown
// (seall, "Show all"). Each table keeps its sort, filters and search under its own name.
// Method, thresholds and caveats are behind each "?" (help()); the screen holds the
// figures and one line each.

import { h, n, esc, short } from "../ui.js";
import { table } from "../table.js";
import { help } from "../ui/help.js";
import { pill } from "../ui/pill.js";
import { subView } from "../tablestate.js";

export const KEPT = { rule: subView("seopr"), side: subView("senl"), kind: subView("sepk"), all: subView("seall") };
const COLOR = "var(--g-search_engines)";

const pct = (v) => (v == null ? "-" : `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`);
export const pos = (v) => (v == null ? "-" : v.toFixed(1));
const plural = (k, one, many = `${one}s`) => `${n(k)} ${k === 1 ? one : many}`;
export const pathOf = (url) => { try { return new URL(url).pathname || "/"; } catch { return url; } };
const span = (a, b) => (a === b ? short(a) : `${short(a)} to ${short(b)}`);

// ------------------------------------------------------------------ words

/* The coverage of a period in plain lines (none when every day is there and final). */
export function coverageLines(cov, tool = "Search Console") {
  if (!cov) return [];
  const out = [];
  if (!cov.stored) return [`${tool} has no figures for these days.`];
  if (cov.before_history) out.push(`Only ${n(cov.stored)} of these ${n(cov.days)} days are in the history here: it starts ${short(cov.history_first)}.`);
  if ((cov.missing || []).length) out.push(`${plural(cov.missing.length, "day")} ${cov.missing.length === 1 ? "has" : "have"} no figures: ${cov.missing.slice(0, 5).map(short).join(", ")}${cov.missing.length > 5 ? ", ..." : ""}.`);
  const p = cov.provisional || [];
  if (p.length) out.push(`${p.length === 1 ? `${short(p[0])} is` : `The newest ${n(p.length)} days (${span(p[0], p.at(-1))}) are`} provisional: ${tool === "Search Console" ? "Google" : "Bing"} may still change ${p.length === 1 ? "it" : "them"}.`);
  if (cov.empty) out.push(`${tool} shows no impressions for the site in these days.`);
  return out;
}

export const RULE_WORDS = { low_ctr: "Rarely clicked", near: "Positions 8-20" };
const RULE_KIND = { low_ctr: "warn", near: "info" };

/* A move in position: positive is up (a smaller number is a better place). */
export function moveWords(change) {
  if (change == null) return "-";
  if (Math.abs(change) < 0.05) return "no change";
  return `${change > 0 ? "up" : "down"} ${Math.abs(change).toFixed(1)}`;
}

/* Why new and lost queries are not listed, in plain words; null when they are. */
export function changesWhy(ch, label) {
  if (!ch) return "No figures yet.";
  if (ch.state === "ok") return null;
  if (ch.state === "too_long") return `Not for ${label}: the period and the one before it are longer than the 16 months Search Console keeps. Pick a shorter period.`;
  if (ch.state === "no_final") return "Not yet: Search Console has no final day yet. Its newest days are provisional, and only whole days are compared.";
  if (ch.state === "short") {
    const from = ch.need_from ? short(ch.need_from) : "";
    return `Not yet: this needs whole days from ${from}${ch.history_first ? `, and the history here starts ${short(ch.history_first)}` : ""}${ch.not_whole ? ` (${plural(ch.not_whole, "day")} missing or still provisional)` : ""}. Pick a shorter period, or fetch more history in Settings.`;
  }
  return "Not available.";
}

// ------------------------------------------------------------------ the shared bits

/* "Show all" kept in the address (seall=<id>): the table's own button, remembered. */
export function keepAll(t, id) {
  const more = t.querySelector?.(".more-rows");
  if (!more) return t;
  let restoring = false;
  more.addEventListener("click", () => { if (!restoring) KEPT.all.set(KEPT.all.get() === id ? "" : id); });
  if (KEPT.all.get() === id && !more.hidden) { restoring = true; more.click(); restoring = false; }
  return t;
}

function seg(label, items, value, pick) {
  return h("div", { class: "seg plain", role: "group", "aria-label": label },
    items.map(([k, w]) => h("button", { type: "button", "aria-pressed": String(value === k), onclick: () => pick(k) }, w)));
}

function headOf(title, helpEl, tools) {
  return h("div", { class: "card-h start" }, h("h2", null, title), helpEl, tools || null);
}

/* A small line of positions (1 at the top); a bucket with no position breaks the line. */
export function spark(points, { W = 84, H = 22 } = {}) {
  const have = points.filter((p) => p != null);
  if (!have.length) return h("span", { class: "muted" }, "-");
  const lo = Math.min(...have), hi = Math.max(...have);
  const k = points.length;
  const x = (i) => (k === 1 ? W / 2 : 2 + (i * (W - 4)) / (k - 1));
  const y = (v) => (hi === lo ? H / 2 : 2 + ((v - lo) / (hi - lo)) * (H - 4));
  let d = "";
  points.forEach((v, i) => { if (v == null) return; d += `${i && points[i - 1] != null ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`; });
  const dots = points.map((v, i) => (v != null && (i === 0 || points[i - 1] == null) && (i === k - 1 || points[i + 1] == null)
    ? `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="1.8" fill="${COLOR}"/>` : "")).join("");
  const el = h("span", { class: "se-spark", role: "img", "aria-label": `Position from ${pos(have[0])} to ${pos(have.at(-1))}` });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true"><path d="${d}" fill="none" stroke="${COLOR}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>${dots}</svg>`;
  return el;
}

/* A query's or a page's position per bucket, for its drawer: 1 at the top, dashed into a
   provisional bucket, a hollow ring on it, a gap where it had no row. */
export function positionChart(posBlock, row) {
  const b = posBlock?.buckets || [];
  const pts = row?.points || [];
  if (!b.length || !pts.some((p) => p != null)) return null;
  const W = 520, H = 180, L = 36, R = 10, T = 12, B = 26;
  const have = pts.filter((p) => p != null);
  const top = Math.max(1, Math.floor(Math.min(...have))), bottom = Math.max(top + 1, Math.ceil(Math.max(...have)));
  const k = b.length, slot = (W - L - R) / Math.max(1, k);
  const x = (i) => L + slot * (i + 0.5);
  const y = (v) => T + ((v - top) / (bottom - top)) * (H - T - B);
  const out = [];
  const step = Math.max(1, Math.ceil((bottom - top) / 4));
  for (let v = top; v <= bottom; v += step) out.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${v}</text>`);
  const gap = k <= 10 ? 1 : k <= 31 ? 7 : 3;
  b.forEach((bk, i) => { if ((k - 1 - i) % gap === 0) out.push(`<text x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(short(bk.last))}</text>`); });
  for (let i = 1; i < k; i++) {
    if (pts[i] == null || pts[i - 1] == null) continue;
    const dash = b[i].provisional || b[i - 1].provisional;
    out.push(`<line x1="${x(i - 1).toFixed(1)}" y1="${y(pts[i - 1]).toFixed(1)}" x2="${x(i).toFixed(1)}" y2="${y(pts[i]).toFixed(1)}" stroke="${COLOR}" stroke-width="2" stroke-linecap="round"${dash ? ' stroke-dasharray="4 4"' : ""}/>`);
  }
  pts.forEach((v, i) => {
    if (v == null) return;
    const lone = (i === 0 || pts[i - 1] == null) && (i === k - 1 || pts[i + 1] == null);
    if (b[i].provisional) out.push(`<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="4" fill="var(--surface)" stroke="${COLOR}" stroke-width="2"/>`);
    else if (lone) out.push(`<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="3.5" fill="${COLOR}"/>`);
  });
  const el = h("div", { class: "chart se-poschart" });
  const per = posBlock.size === 1 ? "day" : `${posBlock.size} days`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`Average position per ${per}, from ${pos(have[0])} to ${pos(have.at(-1))}; 1 is the top`)}">${out.join("")}</svg>`;
  return el;
}

/* A row for the search drawer (tr-search.js rowDrawer) from the reports, when the period's
   own table does not hold it (a query below its top 300, a new one, an opportunity). */
export function findRow(period, kind, key) {
  const k = String(key);
  const tracked = (period?.positions?.[kind]?.rows || []).find((r) => String(r.key) === k);
  if (tracked) return { key: tracked.key, clicks: tracked.clicks, impressions: tracked.impressions, ctr: tracked.impressions ? tracked.clicks / tracked.impressions : null, position: tracked.position };
  if (kind !== "query") return null;
  const opp = (period?.opportunities?.rows || []).find((r) => String(r.query) === k);
  if (opp) return { key: opp.query, clicks: opp.clicks, impressions: opp.impressions, ctr: opp.ctr, position: opp.position };
  const ch = period?.changes;
  const got = ch?.state === "ok" && [...(ch.new?.rows || [])].find((r) => String(r[0]) === k);
  return got ? { key: got[0], clicks: got[1], impressions: got[2], ctr: got[3], position: got[4] } : null;
}

// ------------------------------------------------------------------ opportunities

export function opportunities(period, { open, label }) {
  const o = period.opportunities;
  if (!o) return null;
  const r = o.rules || {};
  const helpEl = help("Opportunities", { guide: "search#opportunities", text: [
    `Queries a page could win more clicks from, over ${label}, by two simple rules:`,
    `Rarely clicked: shown at least ${n(r.many)} times (the larger of 100 and 5 a day), clicked by under ${(r.low_ctr ?? 0.01) * 100}% of the people who saw it, and on average above position ${r.high ?? 8}. It already ranks high: a clearer title and description is the usual fix.`,
    `Positions ${r.near?.[0] ?? 8}-${r.near?.[1] ?? 20}: on average at position ${r.near?.[0] ?? 8} to ${r.near?.[1] ?? 20} and shown at least ${n(r.some)} times (the larger of 30 and 1 a day): the foot of page one or the top of page two. More on the page about the query can lift it.`,
    "Page: the page the query showed most, by impressions." + (o.pages_from ? ` Known from ${short(o.pages_from)}: days synced before Skald kept each query's page have none.` : " Not known yet: Skald keeps each query's page from its next sync on."),
    "Search Console's figures, summed from each day's top 500 queries. Its position is an average, weighted by impressions.",
  ] });
  const by = o.by_rule || {};
  const wrap = h("section", { class: "s se-rep" });
  const paint = () => {
    const pick = ["low_ctr", "near"].includes(KEPT.rule.get()) ? KEPT.rule.get() : "all";
    const rows = (o.rows || []).filter((x) => pick === "all" || x.rule === pick)
      .map((x) => ({ ...x, path: x.page ? pathOf(x.page) : null }));
    const tools = seg("Rule", [["all", `All (${n(o.count)})`], ["low_ctr", `${RULE_WORDS.low_ctr} (${n(by.low_ctr || 0)})`], ["near", `${RULE_WORDS.near} (${n(by.near || 0)})`]], pick,
      (k) => { KEPT.rule.set(k, "all"); KEPT.all.set(""); paint(); });
    const t = table([
      // The rule's pill under the query (the switch above picks a rule); the copy is the query alone.
      { key: "query", label: "Query", copy: "text", copyValue: (x) => x.query, fmt: (v, x) => h("span", { class: "se-q" }, h("span", null, v), pill(RULE_KIND[x.rule], RULE_WORDS[x.rule])) },
      { key: "rule", label: "Rule", hide: true, copy: false, filter: "enum", fmt: (v) => RULE_WORDS[v] },
      { key: "path", label: "Page", path: true, href: (x) => x.page, fmt: (v) => v ?? h("span", { class: "muted" }, "Not known"), csv: (x) => x.page || "" },
      { key: "impressions", label: "Impressions", num: true },
      { key: "clicks", label: "Clicks", num: true },
      { key: "ctr", label: "CTR", type: "num", fmt: pct },
      { key: "position", label: "Position", type: "num", fmt: pos, title: "Average position: 1 is the top result" },
    ], { caption: "Search opportunities", ns: "seopp", rows, file: `search-opportunities-${label.replace(/\s+/g, "")}.csv`, sortKey: "impressions", limit: 10,
      placeholder: "Search opportunities", empty: o.days ? "No query meets either rule in these days." : "No query figures in these days.", rowDrill: false,
      onRow: (x) => open("query", x.query) });
    const line = o.count ? `${plural(o.count, "query", "queries")}: ${n(by.low_ctr || 0)} shown a lot but rarely clicked, ${n(by.near || 0)} at positions 8-20.` : null;
    wrap.replaceChildren(...[headOf("Opportunities", helpEl, tools), line ? h("p", { class: "se-line" }, line) : null, keepAll(t, `opp-${pick}`)].filter(Boolean));
  };
  paint();
  return wrap;
}

// ------------------------------------------------------------------ new and lost

export function changes(period, { open, label }) {
  const ch = period.changes;
  const helpEl = help("New and lost queries", { guide: "search#new-and-lost-queries", text: [
    "New: a query in Search Console's query rows in these days and on no day of the same number of days before. Lost: the other way round.",
    "Whole days only: both stretches end at the newest final day, so the provisional days are left out, and every day of both must be in the history.",
    "Google gives each day's top queries (Skald keeps 500 a day) and leaves rare and personal queries out. A query just below that line can look new or lost when it only moved across it.",
  ] });
  const why = changesWhy(ch, label);
  if (why) return h("section", { class: "s se-rep" }, headOf("New and lost queries", helpEl), h("p", { class: "empty" }, why));
  const wrap = h("section", { class: "s se-rep" });
  const paint = () => {
    const s = KEPT.side.get() === "lost" ? "lost" : "new";
    const part = ch[s];
    const rows = (part.rows || []).map(([query, clicks, impressions, ctr, position]) => ({ query, clicks, impressions, ctr, position }));
    const tools = seg("New or lost", [["new", `New (${n(ch.new.count)})`], ["lost", `Lost (${n(ch.lost.count)})`]], s, (k) => { KEPT.side.set(k, "new"); KEPT.all.set(""); paint(); });
    const t = table([
      { key: "query", label: "Query" },
      { key: "impressions", label: s === "lost" ? "Impressions before" : "Impressions", num: true },
      { key: "clicks", label: s === "lost" ? "Clicks before" : "Clicks", num: true },
      { key: "ctr", label: "CTR", type: "num", fmt: pct },
      { key: "position", label: s === "lost" ? "Position before" : "Position", type: "num", fmt: pos },
    ], { caption: s === "lost" ? "Lost search queries" : "New search queries", ns: s === "lost" ? "selost" : "senew", rows, file: `search-${s}-queries.csv`, sortKey: "impressions", limit: 10,
      placeholder: `Search ${s} queries`, empty: s === "lost" ? "No query was lost." : "No new query.", rowDrill: false,
      onRow: s === "new" ? (x) => open("query", x.query) : undefined });
    const shownCount = part.count > (part.rows || []).length ? ` The ${n(part.rows.length)} most shown are listed.` : "";
    const line = `${span(ch.now.first, ch.now.last)} against ${span(ch.before.first, ch.before.last)}: ${plural(part.count, s === "new" ? "new query" : "lost query", s === "new" ? "new queries" : "lost queries")}, ${n(part.clicks)} clicks, ${n(part.impressions)} impressions${s === "lost" ? " before" : ""}.${shownCount}`;
    wrap.replaceChildren(...[headOf("New and lost queries", helpEl, tools), h("p", { class: "se-line" }, line),
      ch.folded_days ? h("p", { class: "note" }, `On ${plural(ch.folded_days, "day")} some queries were below the day's top list.`) : null,
      keepAll(t, s)].filter(Boolean));
  };
  paint();
  return wrap;
}

// ------------------------------------------------------------------ positions

export function positions(period, { open, label }) {
  const p = period.positions;
  if (!p) return null;
  const per = p.size === 1 ? "day" : `${p.size} days`;
  const prov = (p.buckets || []).filter((b) => b.provisional).length;
  const helpEl = help("Position tracking", { guide: "search#position-tracking", text: [
    "Google's position is an average: the site's best place in each result shown, added up and divided by the times it was shown (weighted by impressions). It is not a rank you can check by searching: it differs by place, device and person.",
    `Each point is one ${per}. Lower is better: 1 is the top result. Move compares the first point with the latest.`,
    "Gaps: a point where the query or page had no row (not shown, or below that day's top list) is empty, never 0. Rare and personal queries are not in Google's rows at all.",
    prov ? `The newest ${prov === 1 ? "point is" : `${prov} points are`} provisional: Google may still change ${prov === 1 ? "it" : "them"}. In a drawer's chart they are hollow and dashed.` : "Every point here is from final days.",
    "The 100 queries and the 100 pages shown most in these days are tracked.",
  ] });
  const wrap = h("section", { class: "s se-rep" });
  const paint = () => {
    const kind = KEPT.kind.get() === "page" ? "page" : "query";
    const block = p[kind] || { rows: [], keys: 0 };
    const rows = block.rows.map((r) => ({ ...r, label: kind === "page" ? pathOf(r.key) : r.key }));
    const tools = seg("Queries or pages", [["query", "Queries"], ["page", "Pages"]], kind, (k) => { KEPT.kind.set(k, "query"); KEPT.all.set(""); paint(); });
    const t = table([
      kind === "page" ? { key: "label", label: "Page", path: true, href: (r) => r.key } : { key: "label", label: "Query" },
      { key: "position", label: "Average", type: "num", fmt: pos, title: `Average position over ${label}` },
      { key: "first", label: "Start", type: "num", fmt: pos },
      { key: "last", label: "Latest", type: "num", fmt: pos },
      { key: "change", label: "Move", type: "num", fmt: moveWords, title: "Up: a better place (a smaller number)" },
      { key: "impressions", label: "Impressions", num: true },
      { key: "points", label: `Per ${per}`, copy: false, filter: false, sort: (r) => r.change ?? -999, fmt: (v) => spark(v || []), csv: (r) => (r.points || []).map((x) => (x == null ? "" : x)).join(" ") },
    ], { caption: kind === "page" ? "Position of pages" : "Position of queries", ns: kind === "page" ? "sepospg" : "seposq", rows, file: `search-positions-${kind}.csv`, sortKey: "impressions", limit: 10,
      placeholder: kind === "page" ? "Search pages" : "Search queries", empty: "No position in these days.", rowDrill: false,
      onRow: (r) => open(kind, r.key) });
    const tracked = block.keys > block.rows.length ? ` The ${n(block.rows.length)} shown most of ${n(block.keys)} are tracked.` : "";
    wrap.replaceChildren(headOf("Position tracking", helpEl, tools),
      h("p", { class: "se-line" }, `Google's position is an average, weighted by impressions; 1 is the top. One point per ${per}.${tracked}`),
      keepAll(t, `pos-${kind}`));
  };
  paint();
  return wrap;
}
