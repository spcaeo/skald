// Traffic > Visitors' two cards under the visit list (2.13):
//
//   New and returning visitors   the visits by new and by returning visitors: the two
//                                figures, one bar of their shares, and each day as a
//                                stacked column (returning at the base, new on top)
//   How engaged visits were      pages per visit and time on site, each visit once,
//                                and one line: the median visit and the one-page share
//
// The figures are js/visitorfigs.js's: they add up to the days' readers or the card
// says it is withheld; a day counted before the figure existed is left out and named.
// With a filter on, both cards count only the visits the filters keep: the days rebuilt
// from the kept visits (visitorfigs.narrowed), allowed only when every day's kept visits
// are that day's own figures exactly. When they cannot be (a period longer than the
// visits are kept, or a day that does not match), the cards show every visit and say why.

import { h, n, short, weekday, duration, tip, untip, share } from "../ui.js";
import { scale } from "../charts.js";
import { newReturning, engagement, narrowed } from "../visitorfigs.js";
import { leaves, without, fromState } from "../rules.js";
import { onePageOf, journeyFilter } from "./visits.js";

const NEW = "var(--g-people)", RET = "var(--ink-2)";

/* The range's days as visitorfigs reads them: Today is the live figures as one day. */
export function rangeDays(m, r) {
  if (r.kind !== "today") return r.days || [];
  const L = m.live;
  if (!L || L.day !== m.today || !L.figures) return [];
  return [{ day: m.today, state: L.state === "ok" ? "ok" : L.state, ...L.figures }];
}

const pctOf = (part, whole) => share(part, whole) || "";
const dayWords = (d) => `${weekday(d)} ${short(d)}`;
const leftWords = (left, what) => (left.length ? `${n(left.length)} day${left.length === 1 ? " was" : "s were"} counted before ${what} ${left.length === 1 ? "was" : "were"}: left out (${left.length <= 3 ? left.map(short).join(", ") : `${short(left[0])} to ${short(left[left.length - 1])}`}).` : null);

function card(id, title, sub, ...body) {
  return h("section", { class: "s vs-card", "aria-labelledby": id }, h("div", { class: "vs-card-h" }, h("h3", { id }, title), sub ? h("p", { class: "sub" }, sub) : null), ...body);
}
/* A filter is on that a visit can carry (a crawler-only rule is not: the banner says so). */
export const filtersOn = (s) => leaves(without(fromState(s), "visit")).length > 0;

/* The days a card counts, and its line about the filters: with a filter a visit can
   carry, the kept visits (when they are the days' own figures exactly), else every visit. */
export function cardDays(m, s, r) {
  const days = rangeDays(m, r);
  if (!filtersOn(s)) return { days, note: null, narrow: false };
  const keep = journeyFilter(s);
  const f = keep ? narrowed(days, m.journeys, keep) : { state: "unchecked", off: [] };
  if (f.state === "ok") {
    return { days: f.days, narrow: true, kept: f.kept,
      note: `Filtered: ${n(f.kept)} of ${n(f.whole)} visits, counted from each visit kept and checked against the days' own figures.` };
  }
  const old = f.state === "unchecked" && f.off.some((x) => x.why === "none");
  const why = f.state !== "unchecked" ? "" : old ? ` Visits are kept ${m.journey_days || 7} days; pick a period inside them to narrow it.`
    : f.off.length ? ` The visits kept on ${short(f.off[0].day)} are not exactly that day's figures.` : "";
  return { days, narrow: false, note: `For all visits: the filters above do not narrow this card.${why}` };
}
const filterNote = (src) => (src.note ? h("p", { class: "note" }, src.note) : null);
const withheld = (words) => h("div", { class: "state bad", role: "alert" }, h("div", null, words));

// A mark that shows its figures on hover and on focus.
function tipped(el, head, rows) {
  const show = () => { const b = el.getBoundingClientRect(); tip(b.left + b.width / 2, b.top, head, rows); };
  el.addEventListener("pointerenter", show);
  el.addEventListener("focus", show);
  el.addEventListener("pointerleave", untip);
  el.addEventListener("blur", untip);
  return el;
}

/* Bars with their values on top, and labels under them: HTML, so the labels wrap. */
function histogram(title, items, color, total) {
  const max = Math.max(1, ...items.map((x) => x.value));
  const cols = `repeat(${items.length}, minmax(0, 1fr))`;
  return h("div", { class: "vs-hist" },
    h("h4", null, title),
    h("div", { class: "vs-hist-plot", style: { gridTemplateColumns: cols } }, items.map((x, i) => tipped(
      h("span", { class: "vs-hist-col", tabindex: "0", style: { "--i": i }, "aria-label": `${title}, ${x.label}: ${n(x.value)} visits${pctOf(x.value, total) ? `, ${pctOf(x.value, total)}` : ""}` },
        h("b", { "aria-hidden": "true" }, n(x.value)),
        h("span", { class: "vs-bar", "aria-hidden": "true", style: { height: x.value ? `max(2px, ${(x.value / max) * 82}%)` : "0", background: color } })),
      x.label, [{ color, value: n(x.value), label: `visits${pctOf(x.value, total) ? `, ${pctOf(x.value, total)} of ${n(total)}` : ""}` }]))),
    h("div", { class: "vs-hist-x", "aria-hidden": "true", style: { gridTemplateColumns: cols } }, items.map((x) => h("span", null, x.label))));
}

/* Each day as a stacked column: returning at the base, new on top. */
function perDay(days) {
  const [max, step] = scale(Math.max(1, ...days.map((d) => d.visits)));
  const ticks = [];
  for (let v = max; v >= 0; v -= step) ticks.push(v);
  const every = Math.max(1, Math.ceil(days.length / 10));
  const cols = `repeat(${days.length}, minmax(0, 1fr))`;
  return h("div", { class: "nr-chart", style: { "--cols": days.length } },
    h("div", { class: "nr-y", "aria-hidden": "true" }, ticks.map((v) => h("span", null, n(v)))),
    h("div", { class: "nr-plot" },
      h("div", { class: "nr-grid", "aria-hidden": "true" }, ticks.map(() => h("span"))),
      h("div", { class: "nr-cols", style: { gridTemplateColumns: cols } }, days.map((d, i) => tipped(
        h("span", { class: "nr-col", tabindex: "0", style: { height: `${(d.visits / max) * 100}%`, "--i": i },
          "aria-label": `${dayWords(d.day)}: ${n(d.visits)} visits, ${n(d.fresh)} new, ${n(d.returning)} returning` },
          d.fresh ? h("span", { class: "nr-new", style: { flexGrow: d.fresh } }) : null,
          d.returning ? h("span", { class: "nr-ret", style: { flexGrow: d.returning } }) : null),
        dayWords(d.day), [{ color: NEW, value: n(d.fresh), label: "new" }, { color: RET, value: n(d.returning), label: "returning" }, { value: n(d.visits), label: "visits" }])))),
    h("span"),
    h("div", { class: "nr-x", "aria-hidden": "true", style: { gridTemplateColumns: cols } },
      days.map((d, i) => h("span", null, i % every !== 0 ? "" : days.length <= 14 ? [h("span", { class: "wd" }, `${weekday(d.day)} `), short(d.day).split(" ")[0]] : short(d.day)))));
}

export function newReturningCard(m, s, r, src = cardDays(m, s, r)) {
  const f = newReturning(src.days);
  const sub = "Each visit, by whether its visitor was seen on an earlier day in the 30 before (a keyed hash of the address and browser, kept 30 days). Counted per visit, so two visits on a first day are both new.";
  const c = card("nr-h", "New and returning visitors", sub);
  if (f.state === "empty") c.append(h("p", { class: "empty" }, r.kind === "today" ? "Today's figures are not in yet." : "No verified day in this range."));
  else if (src.narrow && !src.kept) c.append(h("p", { class: "empty" }, "No visit in this period matches the filters."));
  else if (f.state === "none") c.append(h("p", { class: "empty" }, "Not recorded for this range: returning visitors are counted only when the visitor key is set."));
  else if (f.state === "withheld") {
    const x = f.off[0];
    c.append(withheld(`Withheld: on ${short(x.day)} the visits counted as new or returning (${n(x.counted)}) are not the day's ${n(x.readers)} visits${f.off.length > 1 ? `, and on ${f.off.length - 1} more day${f.off.length === 2 ? "" : "s"}` : ""}.`));
  } else {
    const fig = (label, color, v) => h("div", { class: "nr-fig" }, h("span", { class: "nr-l" }, h("span", { class: "sw", style: { background: color } }), label),
      h("span", { class: "nr-v" }, n(v), pctOf(v, f.visits) ? h("small", null, pctOf(v, f.visits)) : null));
    c.append(h("div", { class: "nr-figs" }, fig("New", NEW, f.fresh), fig("Returning", RET, f.returning)),
      h("div", { class: "nr-bar", role: "img", "aria-label": `${n(f.fresh)} new and ${n(f.returning)} returning of ${n(f.visits)} visits` },
        f.fresh ? h("span", { style: { flexGrow: f.fresh, background: NEW } }) : null, f.returning ? h("span", { style: { flexGrow: f.returning, background: RET } }) : null));
    if (f.days.length > 1) c.append(perDay(f.days));
    c.append(h("p", { class: "note" }, `${n(f.visits)} visits${f.days.length > 1 ? ` on ${n(f.days.length)} days` : r.kind === "today" ? " today so far" : ""}: ${n(f.fresh)} new and ${n(f.returning)} returning, ${f.days.length > 1 ? "each day" : "the day"} checked against its visits.`));
  }
  c.append(...[leftWords(f.left || [], "returning visitors")].filter(Boolean).map((t) => h("p", { class: "note" }, t)), filterNote(src) || "");
  return c;
}

/* f: visitorfigs.engagement, for the title line and the tab's own summary. */
export function engagementCard(m, s, r, src = cardDays(m, s, r)) {
  const f = engagement(src.days);
  const c = card("en-h", "How engaged visits were", f.state === "ok" ? `Each chart adds up to the ${n(f.visits)} visits. Hover a bar for its share.` : "Pages per visit and time on site, each visit once.");
  const line = h("p", { class: "vs-line" });
  if (f.state === "empty") c.append(h("p", { class: "empty" }, r.kind === "today" ? "Today's figures are not in yet." : "No verified day in this range."));
  else if (src.narrow && !src.kept) c.append(h("p", { class: "empty" }, "No visit in this period matches the filters."));
  else if (f.state === "none") c.append(h("p", { class: "empty" }, "Not recorded for this range: these days were collected before visit lengths were."));
  else if (f.state === "withheld") c.append(withheld(`Withheld: the visits by pages (${n(f.pagesTotal)}) and by time on site (${n(f.secondsTotal)}) do not both add up to the ${n(f.visits)} visits.`));
  else {
    c.append(h("div", { class: "vs-hists" }, histogram("Pages per visit", f.pages, "var(--views)", f.visits), histogram("Time on site", f.seconds, "var(--g-people)", f.visits)));
    line.textContent = `Typical visit (the median): ${n(f.medianPages)} page${f.medianPages === 1 ? "" : "s"} over ${duration(f.medianSeconds)}. ${pctOf(f.onePage, f.visits) || n(f.onePage)} of visits read one page and left.`;
    c.append(line, h("p", { class: "note" }, "Time on site runs from the first request to the last: a log sees what was loaded, not how long someone read, so a long read of one page shows as a short visit."));
  }
  c.append(...[leftWords(f.left || [], "visit lengths")].filter(Boolean).map((t) => h("p", { class: "note" }, t)), filterNote(src) || "");
  // Filled in when visits.json's rows arrive (tr-visitors.js): the AI assistant visits' own one-page share
  // (whole-site rows, so not beside figures narrowed by the filters).
  c.withAssistants = (e) => {
    if (src.narrow) return;
    const ai = onePageOf(e, "AI assistant");
    if (f.state === "ok" && ai) line.append(` That share is ${Math.round(ai.share * 100)}% for the ${n(ai.visits)} visits sent by an AI assistant.`);
  };
  return c;
}
