// Traffic > Visitors (2.13, the owner's approved layout): what visits looked like.
// 2.42 (the UX audit's task 8): the list first. A List / Flow switch sits above it, kept in
// the address (vis_view=flow; the list when absent); the cards follow, and the lists and
// tables after them are under one fold kept in the address (visx_view=open).
//
//   Each visit          one row per visit, newest first (visitlist.js); a row opens the
//                       visitor drawer (visitor.js)
//   Visitor flow        where visits came from, their pages in order, where they left
//                       (flowview.js, sankey.js); Pages 3 / 4 / 5
//   New and returning   and How engaged visits were: two cards (vis-cards.js); with a
//                       filter on, both count the filtered visits when that reconciles
//   Open the details    Where visits ended, Common next steps, and the engagement tables by
//                       source and device (visits.js)
//
// Landing pages live on Traffic > Pages (a line links there). Nothing is recounted
// here: the figures are the days' own, checked in js/visitorfigs.js.

import * as S from "../state.js";
import { h, n, short } from "../ui.js";
import { figures, pathMatch, ranked } from "../data.js";
import { head, nothing, coverageNote, blist, panel } from "./common.js";
import { goTo } from "./tr-grid.js";
import { visitMatrix } from "./visitlist.js";
import { visitorFlow } from "./flowview.js";
import { journeyFilter, engagementTables } from "./visits.js";
import { newReturningCard, engagementCard, rangeDays, cardDays, filtersOn } from "./vis-cards.js";
import { newReturning, narrowedLists, ARROW } from "../visitorfigs.js";
import { subView } from "../tablestate.js";
import { urlFold } from "../ui/fold.js";
import { recordedCard } from "./recorded.js";

// List or Flow, in the address (vis_view): the list when absent.
const VIEW = subView("vis");
function listOrFlow(m, s, r) {
  const holder = h("div", { class: "vs-which" });
  const draw = (k) => holder.replaceChildren(k === "flow" ? visitorFlow(m, s, r) : eachVisit(m, s, r));
  const btns = [["list", "List"], ["flow", "Flow"]].map(([k, words]) => h("button", { type: "button", "aria-pressed": String(VIEW.get("list") === k), "data-k": k,
    onclick: () => { VIEW.set(k, "list"); for (const b of btns) b.setAttribute("aria-pressed", String(b.dataset.k === k)); draw(k); } }, words));
  draw(VIEW.get("list"));
  return [h("div", { class: "seg plain vs-switch", role: "group", "aria-label": "Show the visits as" }, btns), holder];
}

const LEDE = "Each visit here read at least one page: one browser, with no gap longer than 30 minutes. Arriving again from another outside source (an AI assistant, a search, another site, a campaign link) starts a new visit. Logs see what was loaded, not how long someone read, so a long read of one page shows as a short visit.";

// The line beside the title: the visits, and how many were by new and returning visitors when that adds up.
// With the filters narrowing the cards (vis-cards.cardDays), the line says the filtered visits.
function summary(m, r, t, src) {
  const f = newReturning(src.narrow ? src.days : rangeDays(m, r));
  const when = r.kind === "today" ? "today so far" : r.length === 1 ? `on ${short(r.first)}` : `${short(r.first)} to ${short(r.last)}`;
  if (src.narrow) {
    const of = `${n(src.kept)} visit${src.kept === 1 ? "" : "s"} ${when} match the filters, of ${n(t.readers ?? 0)}`;
    return f.state === "ok" && !f.left.length && src.kept ? `${of}: ${n(f.fresh)} by new visitors and ${n(f.returning)} by returning ones.` : `${of}.`;
  }
  const visits = n(t.readers ?? 0);
  if (f.state === "ok" && !f.left.length) return `${visits} visits ${when}: ${n(f.fresh)} by new visitors and ${n(f.returning)} by returning ones.`;
  return `${visits} visits ${when}.`;
}

function eachVisit(m, s, r) {
  const inRange = r.kind === "today" ? (j) => j.day === m.today : (j) => j.day >= r.first && j.day <= r.last;
  const all = (m.journeys || []).filter(inRange);
  // The list reaches back only as far as journeys are kept: a longer period above is said here, not silently cut.
  const kept = r.kind === "history" ? [...new Set(all.map((j) => j.day))].sort() : [];
  const own = kept.length && kept.length < r.length ? h("span", { class: "own-period", title: `Journeys are kept ${m.journey_days || 7} days: the period above is longer` },
    `${short(kept[0])} to ${short(kept[kept.length - 1])} · its own period`) : null;
  return h("section", { class: "s vs-card vs-visits", "aria-labelledby": "ev-h" },
    h("div", { class: "vs-card-h" }, h("h3", { id: "ev-h" }, "Each visit", own ? " " : null, own),
      h("p", { class: "sub" }, `Newest first, one row per visit. Select a row to see that visitor's whole journey. Every filter applies. Anonymous, kept ${m.journey_days || 7} days.`)),
    visitMatrix(all, all.filter(journeyFilter(s)), r, m.journey_days));
}

/* Where visits ended and Common next steps: with a filter a visit can carry, counted from
   the kept visits when each day's kept visits give back its own lists (visitorfigs
   narrowedLists); otherwise the whole site's (narrowed by a page filter only) and said so. */
function endLists(m, s, r, v) {
  const keep = pathMatch(s);
  const whole = { exits: ranked(v?.exits, keep), steps: ranked(v?.steps, (x) => x.split(ARROW).some(keep)), narrow: false };
  if (!filtersOn(s)) return { ...whole, note: () => null };
  const f = narrowedLists(rangeDays(m, r), m.journeys, journeyFilter(s) || (() => true));
  if (f.state === "ok") {
    const words = `Filtered: ${n(f.kept)} of ${n(f.whole)} visits, counted from each visit kept and checked against the days' own lists.`;
    return { exits: ranked(f.exits), steps: ranked(f.steps), narrow: true, note: () => h("p", { class: "note" }, words) };
  }
  const old = f.state === "unchecked" && f.off.some((x) => x.why === "none");
  const words = `For all visits: the filters above do not narrow this.${old ? ` Visits are kept ${m.journey_days || 7} days; pick a period inside them to narrow it.` : ""}`;
  return { ...whole, note: () => h("p", { class: "note" }, words) };
}

export default function visitors(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Visitors", r, LEDE)];
  if (!t) return [...out, nothing(m, r, "visits")];
  const src = cardDays(m, s, r);
  out.push(h("div", { class: "vs-title" }, h("h2", null, "Visitors"), h("p", null, summary(m, r, t, src))));
  const v = t.visit;
  out.push(coverageNote(cov, r));
  out.push(...listOrFlow(m, s, r));
  out.push(recordedCard(m, s, r));     // 2.43: what the site sent itself, labelled, never added to the visits
  const eng = engagementCard(m, s, r, src);
  out.push(h("div", { class: "vs-pair" }, newReturningCard(m, s, r, src), eng));
  // Drawn now (its visits.json also fills the engagement card's assistants), shown in the fold.
  const tables = engagementTables(s, r, (e) => eng.withAssistants(e));
  out.push(urlFold("visx", "Open the details: where visits ended, common next steps, and engagement by source and device", () => {
    const L = endLists(m, s, r, v);
    return [h("div", { class: "cols" },
      panel("Where visits ended", "The last page a visitor was seen on", blist(L.exits, { drill: "path", color: "var(--views)", empty: L.narrow ? "No visit matches the filters." : v ? "No exit page recorded." : "Not recorded for this range." }), L.note()),
      panel("Common next steps", "From one page to the next", blist(L.steps, { color: "var(--ink-3)", empty: L.narrow ? "No matching visit went past one page." : v ? "No visit went past one page." : "Not recorded for this range." }), L.note())),
    ...tables];
  }));
  out.push(goTo(S.hashFor({ ...s, tab: "traffic/pages", dd: "" }), "Where visits started: the landing pages, with their leads, are on", "Traffic › Pages"));
  return out.filter(Boolean);
}
