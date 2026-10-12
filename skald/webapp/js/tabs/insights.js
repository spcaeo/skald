// Insights: what is working, what dropped, what is new or gone, what looks
// odd and what is worth fixing - each a plain sentence with its numbers and
// a way into the tab that shows it. The rules (complete periods only, a
// floor on tiny numbers) are the data layer's; this only presents them.

import { h, n, short, change, stateNote, ICON } from "../ui.js";
import { pathMatch } from "../data.js";
import { spark } from "../charts.js";
import * as S from "../state.js";
import { info } from "./tiles.js";
import { country, withFlag } from "./readers.js";

export const TYPES = [
  ["working", "Working", "var(--good)", '<path d="M3 11l4-4 3 3 4-5"/><path d="M10 5h4v4"/>'],
  ["dropped", "Dropped", "var(--bad)", '<path d="M3 5l4 4 3-3 4 5"/><path d="M10 11h4V7"/>'],
  ["new", "New", "var(--g-people)", '<path d="M8 3v10M3 8h10"/>'],
  ["gone", "Gone", "var(--ink-3)", '<circle cx="8" cy="8" r="5.5"/><path d="M5.5 8h5"/>'],
  ["anomaly", "Anomalies", "var(--warn)", '<path d="M1.5 9h3l2-5 3 8 2-4h3"/>'],
  ["opportunity", "Opportunities", "var(--opp)", '<path d="M8 2.5l1.7 3.5 3.8.5-2.8 2.6.7 3.8L8 11l-3.4 1.9.7-3.8-2.8-2.6 3.8-.5z"/>'],
];
const icon = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;

// Where a subject is shown, and the filter that narrows that tab to it.
const TARGET = { page: "pages", path: "pages", source: "sources", referrer: "sources", campaign: "sources",
  country: "locations", assistant: "bots", crawler: "bots", site: "overview" };
const TAB_NAME = Object.fromEntries(S.TABS);
const KNOWN = new Set(S.FILTERS);

function target(i) {
  const tab = i.metric === "not_found" ? "health/broken" : TARGET[i.subject?.kind] || "overview";
  const filter = Object.fromEntries(Object.entries(i.filter || {}).filter(([k]) => KNOWN.has(k)));
  if (i.subject?.kind === "page" && filter.path) return { tab: "pages", page: filter.path, ...filter };
  return { tab, ...filter };
}

const WINDOWS = [["today", "Today so far"], ["1", "Yesterday"], ["7", "7 days"], ["30", "30 days"]];
const length = (i) => {
  const [a, b] = i.period?.after || [];
  return a && b ? String(Math.round((Date.parse(b) - Date.parse(a)) / 864e5) + 1) : "7";
};

function card(i) {
  const [, label, tone, glyph] = TYPES.find(([k]) => k === i.type) || TYPES[0];
  const [arrow, words] = i.before == null ? ["", ""] : change(i.after, i.before);
  const go = target(i);
  const name = i.subject?.kind === "country" ? withFlag(i.subject.name, country(i.subject.name)) : i.subject?.name;
  const trend = i.trend ? Object.keys(i.trend).sort().map((d) => i.trend[d]) : null;
  return h("article", { class: "ins", style: { "--tone": tone } },
    h("div", { class: "ins-top" },
      h("span", { class: "ins-chip", html: icon(glyph) }, label),
      h("span", { class: `conf conf-${i.confidence}`, title: `${i.confidence} confidence` }, h("i"), h("i"), h("i"), h("span", { class: "vh" }, `${i.confidence} confidence`))),
    h("h3", { class: "ins-title" }, i.title),
    h("div", { class: "ins-nums" },
      i.before == null ? null : h("span", { class: "was" }, n(i.before)),
      i.before == null ? null : h("span", { class: "to", "aria-label": "to" }, "→"),
      h("span", { class: "now" }, n(i.after)),
      words ? h("span", { class: "pct" }, arrow ? `${arrow} ` : "", words) : null),
    trend && trend.length > 1 ? spark(trend, tone) : null,
    h("p", { class: "ins-meta" }, `${i.subject?.kind || ""}${name ? `: ${name}` : ""}`, i.period?.after ? `, ${short(i.period.after[0])} to ${short(i.period.after[1])}` : "",
      i.period?.before ? ` against ${short(i.period.before[0])} to ${short(i.period.before[1])}` : ""),
    h("button", { type: "button", class: "btn ins-go", onclick: () => S.set(go) }, `Open in ${TAB_NAME[go.tab] || "Overview"}`));
}

export default function insights(m, s) {
  const file = m.x.insights;
  // No range badge: each insight carries its own two periods.
  const out = [h("div", { class: "head" }, h("h1", null, "Insights"),
    info("What changed, in plain words: what is working, what dropped, what is new or gone, what looks unusual, and what is worth fixing. Each compares whole, verified periods only and opens the tab that shows it.", "Insights"),
    h("span", { class: "period" }, "Each insight compares its own two whole periods · the date range above does not apply"))];
  if (!file) return [...out, stateNote("Insights are coming: the data layer has not written insights.json yet. They appear here on the first run that writes it.")];
  const all = [...(file.insights || []).map((i) => ({ ...i, win: length(i) })), ...(file.today || []).map((i) => ({ ...i, win: "today" }))];
  const have = new Set(all.map((i) => i.win));
  const counts = Object.fromEntries(WINDOWS.map(([k]) => [k, all.filter((i) => i.win === k).length]));
  const since = s.since && have.has(s.since) ? s.since : ["7", "1", "30", "today"].find((k) => have.has(k)) || "7";
  const keep = pathMatch(s);
  const filtered = all.filter((i) => i.win === since && (!s.path || keep(i.filter?.path ?? i.subject?.name ?? "")) &&
    ["country", "source", "campaign", "referrer"].every((k) => !s[k] || i.filter?.[k] === s[k] || i.subject?.name === s[k]));

  const pick = h("div", { class: "seg plain", role: "group", "aria-label": "Since" },
    WINDOWS.map(([k, name]) => h("button", { type: "button", "aria-pressed": String(k === since), disabled: !have.has(k),
      title: have.has(k) ? null : "No insights for this window yet", onclick: () => S.set({ since: k }) }, name, counts[k] ? ` ${counts[k]}` : "")));

  // The one loud moment: the week in six numbers, each a way down to its cards.
  const tally = h("div", { class: "tally" }, TYPES.map(([k, label, tone, glyph]) => {
    const c = filtered.filter((i) => i.type === k).length;
    return h("a", { class: `tally-i${c ? "" : " zero"}`, href: `#ins-${k}`, style: { "--tone": tone },
      onclick: (e) => { e.preventDefault(); document.getElementById(`ins-${k}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); } },
      h("span", { class: "tally-n" }, String(c)), h("span", { class: "tally-l", html: icon(glyph) }, label));
  }));
  out.push(h("section", { class: "ins-hero" }, h("div", { class: "ins-hero-top" }, h("h2", null, "Since"), pick), tally));
  if (!filtered.length) {
    out.push(stateNote(all.length ? "Nothing passes the thresholds for this window and these filters. That is a quiet period, not missing data." : "No insights yet: they need two complete periods to compare."));
    return out;
  }
  for (const [k, label] of TYPES) {
    const list = filtered.filter((i) => i.type === k);
    if (!list.length) continue;
    out.push(h("section", { class: "s", id: `ins-${k}` }, h("h2", null, `${label} (${list.length})`), h("div", { class: "ins-grid" }, list.map(card))));
  }
  return out;
}
