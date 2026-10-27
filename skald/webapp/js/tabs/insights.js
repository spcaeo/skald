// Insights: what is working, what dropped, what is new or gone, what looks
// odd and what is worth fixing. Since 2.13: the five with the most impact first,
// "Show all N" for the rest; one card per subject (a site that is both a
// referring site and an AI assistant is one card); each card one sentence, one
// number and one link (js/insight-rank.js). The rules (whole periods only, a
// floor on tiny numbers) are the data layer's; this only presents them.

import { h, n, short, stateNote } from "../ui.js";
import { pathMatch } from "../data.js";
import * as S from "../state.js";
import { info } from "./tiles.js";
import { fold, sentence, headline } from "../insight-rank.js";
// 2.35: the to-do list above the cards (js/tabs/todos.js).
import { todoSection } from "./todos.js";

export const TYPES = [
  ["working", "Working", "var(--good)", '<path d="M3 11l4-4 3 3 4-5"/><path d="M10 5h4v4"/>'],
  ["dropped", "Dropped", "var(--bad)", '<path d="M3 5l4 4 3-3 4 5"/><path d="M10 11h4V7"/>'],
  ["new", "New", "var(--g-people)", '<path d="M8 3v10M3 8h10"/>'],
  ["gone", "Gone", "var(--ink-3)", '<circle cx="8" cy="8" r="5.5"/><path d="M5.5 8h5"/>'],
  ["anomaly", "Unusual", "var(--warn)", '<path d="M1.5 9h3l2-5 3 8 2-4h3"/>'],
  ["opportunity", "Worth fixing", "var(--opp)", '<path d="M8 2.5l1.7 3.5 3.8.5-2.8 2.6.7 3.8L8 11l-3.4 1.9.7-3.8-2.8-2.6 3.8-.5z"/>'],
];
const icon = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const TOP = 5;

// Where a subject is shown, and the filter that narrows that tab to it.
const TARGET = { page: "traffic/pages", path: "traffic/pages", source: "traffic/sources", referrer: "traffic/sources", campaign: "traffic/sources",
  country: "traffic/places", assistant: "ai/assistants", crawler: "ai/crawlers", site: "overview/summary" };
// Read when drawn: the sections' tabs are registered after this file loads (js/sections.js).
const tabName = (k) => S.nameOf(k);
const KNOWN = new Set(S.FILTERS);

export function target(i) {
  const tab = i.metric === "not_found" ? "site/notfound" : TARGET[i.subject?.kind] || "overview/summary";
  const filter = Object.fromEntries(Object.entries(i.filter || {}).filter(([k]) => KNOWN.has(k)));
  // A page that started leads opens the Pages tab on its landing-page leads, not its story.
  if (i.subject?.kind === "page" && filter.path) return i.metric === "leads" ? { tab: "traffic/pages", ...filter } : { tab: "traffic/pages", page: filter.path, ...filter };
  return { tab, ...filter };
}

// The windows an insight compares, and what each one is.
const WINDOWS = [["today", "Today so far"], ["1", "Yesterday"], ["7", "7 days"], ["30", "30 days"]];
const SAYS = {
  today: "Today lists only what is seen for the first time today: a new page, source, country, campaign or crawler. Rises and drops compare whole days, so they are under Yesterday, 7 days and 30 days.",
  1: "Yesterday against the 14 days before it, and what was new yesterday.",
  7: "The last 7 whole days against the 7 before them.",
  30: "The last 30 whole days against the 30 before them, and pages worth fixing over 30 days.",
};
const length = (i) => {
  const [a, b] = i.period?.after || [];
  return a && b ? String(Math.round((Date.parse(b) - Date.parse(a)) / 864e5) + 1) : "7";
};
const periodWords = (i) => (i.period?.after ? `${short(i.period.after[0])} to ${short(i.period.after[1])}${i.period?.before ? ` against ${short(i.period.before[0])} to ${short(i.period.before[1])}` : ""}` : "");

function card({ lead: i, more }) {
  const [, label, tone, glyph] = TYPES.find(([k]) => k === i.type) || TYPES[0];
  const go = target(i);
  const big = headline(i);
  return h("article", { class: "ins ins-short", style: { "--tone": tone } },
    h("span", { class: "ins-chip", html: icon(glyph) }, label),
    h("p", { class: "ins-say" }, sentence(i)),
    h("p", { class: "ins-big" }, h("b", null, big.value == null ? "-" : n(big.value)), h("span", null, ` ${big.words}`)),
    h("a", { class: "ins-link", href: S.hashFor({ ...S.read(), ...go, dd: "" }), title: periodWords(i),
      onclick: (e) => { e.preventDefault(); S.set(go); } }, `Open in ${go.tab ? tabName(go.tab) : "Overview"}`),
    more.length ? h("details", { class: "ins-more" }, h("summary", null, `${more.length} more about this`),
      h("ul", null, more.map((x) => h("li", null, sentence(x))))) : null);
}

export default function insights(m, s) {
  const file = m.x.insights;
  const out = [h("div", { class: "head" }, h("h1", null, "Insights"),
    info("What changed, in plain words: what is working, what dropped, what is new or gone, what looks unusual, and what is worth fixing. Each compares whole, verified days only and opens the tab that shows it. The five with the most impact come first: a lead counts more than a visit, and a finding on small numbers counts less.", "Insights"),
    h("span", { class: "period" }, "Whole days, compared with the days before · the date range above does not apply"))];
  out.push(todoSection(m, s), h("h2", { class: "ins-h2" }, "What changed"));
  if (!file) return [...out, stateNote("Insights are coming: the data layer has not written insights.json yet. They appear here on the first run that writes it.")];
  const all = [...(file.insights || []).map((i) => ({ ...i, win: length(i) })), ...(file.today || []).map((i) => ({ ...i, win: "today" }))];
  // 2.41: each window counts what it shows, a card per subject (fold), as "Show all N" does;
  // the findings behind them are said once, under the cards (the audit: 31 beside 29 cards).
  const counts = Object.fromEntries(WINDOWS.map(([k]) => [k, fold(all.filter((i) => i.win === k)).length]));
  const since = WINDOWS.some(([k]) => k === s.since) ? s.since : ["7", "1", "30", "today"].find((k) => counts[k]) || "7";
  const keep = pathMatch(s);
  const filtered = all.filter((i) => i.win === since && (!s.path || keep(i.filter?.path ?? i.subject?.name ?? "")) &&
    ["country", "source", "campaign", "referrer"].every((k) => !s[k] || i.filter?.[k] === s[k] || i.subject?.name === s[k]));

  // Every window can be picked, Today too: an empty one says why it is empty.
  const pick = h("div", { class: "seg plain", role: "group", "aria-label": "Compare" },
    WINDOWS.map(([k, name]) => h("button", { type: "button", "aria-pressed": String(k === since), onclick: () => S.set({ since: k }) }, name, counts[k] ? h("span", { class: "ins-n" }, ` ${counts[k]}`) : null)));
  out.push(h("section", { class: "ins-bar" }, pick, h("p", { class: "ins-what" }, SAYS[since])));
  // Lead findings the second count disagreed with are left out, and said so.
  const held = file.leads_withheld || [];
  if (held.length) out.push(h("p", { class: "note", role: "note" }, `${held.length} lead finding${held.length === 1 ? " was" : "s were"} left out: the second count disagreed. ${held[0]}`));
  if (!filtered.length) {
    const words = since === "today" ? "Nothing new so far today. That is usual: most days bring no first-time page, source or country."
      : all.length ? "Nothing passes the thresholds for this window and these filters. That is a quiet period, not missing data." : "No insights yet: they need two complete periods to compare.";
    const other = WINDOWS.filter(([k]) => k !== since && counts[k]);
    const note = stateNote(words);
    if (other.length) note.lastChild.append(" ", ...other.map(([k, name]) => h("button", { type: "button", class: "btn", onclick: () => S.set({ since: k }) }, `${name} (${counts[k]})`)));
    out.push(note);
    return out;
  }
  const cards = fold(filtered);
  const grid = h("div", { class: "ins-grid" }, cards.slice(0, TOP).map(card));
  out.push(h("section", { class: "s" }, cards.length > TOP ? h("h3", null, `The ${TOP} biggest`) : null, grid));
  if (cards.length > TOP) {
    const rest = h("div", { class: "ins-grid", hidden: true }, cards.slice(TOP).map(card));
    const btn = h("button", { type: "button", class: "btn ins-all", "aria-expanded": "false" }, `Show all ${cards.length}`);
    btn.addEventListener("click", () => {
      rest.hidden = !rest.hidden;
      btn.setAttribute("aria-expanded", String(!rest.hidden));
      btn.textContent = rest.hidden ? `Show all ${cards.length}` : "Show the 5 biggest only";
    });
    out.push(h("section", { class: "s ins-rest" }, rest, btn));
  }
  const folded = filtered.length - cards.length;
  if (folded) out.push(h("p", { class: "note" }, `${cards.length} cards from ${filtered.length} findings: a subject found more than once (a site that is both a referring site and an AI assistant, a source's visitors and its leads) has one card; the others are under "more about this".`));
  return out;
}
