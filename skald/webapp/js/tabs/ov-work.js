// Overview › Summary, card "Work on the page, or on traffic?" (release 2, card S10).
//
//   Improve the page   many visits started on the page and nearly all left at once, with no
//                      form sent from it: the page, not the traffic, is the problem (CRO)
//   Both               search finds the page, but most who land on it leave at once: work on
//                      the page and on how it is found
//
// "Left at once": the visit loaded that one page and no other, one page view in the server's
// log (the day kind `landings`, `one_page`). The thresholds are page-figs.js WORK. Leads come
// from the conversions data (leadfigs.js leadsBy, by landing page), on the days both are whole.

import { h, n, pct1 } from "../ui.js";
import * as S from "../state.js";
import { goTo } from "./ov-live.js";
import { leadsBy } from "./leadfigs.js";
import { withUrl } from "../urlactions.js";
import { spanWords } from "../mode-compare.js";
import { pageSums, workLists, WORK, LEFT_WORDS } from "../page-figs.js";

const pageLink = (s, path) => withUrl(h("a", { class: "mono wk-p", href: S.hashFor({ ...s, tab: "traffic/pages", page: path, dd: "" }), title: `${path}: its story` }, path), path);

function group(tag, cls, title, rows, s, words) {
  return h("div", { class: "wk-g" },
    h("div", { class: "wk-gh" }, h("span", { class: `pill ${cls}` }, tag), h("b", null, title)),
    rows.length ? h("ul", { class: "wk-list" }, rows.map((x) => h("li", null, pageLink(s, x.path), h("span", { class: "wk-t" }, words(x)))))
      : h("p", { class: "muted wk-empty" }, "No page fits this period."));
}

export function workCard(m, s, r, t) {
  const sec = h("section", { class: "s wk", "aria-label": "Page or traffic" },
    h("h2", null, "Work on the page, or on traffic?"),
    h("p", { class: "sub" }, `${r.kind === "history" ? `${spanWords(r)}. ` : ""}Many visits that leave at once with no form: improve the page (CRO). Search finds a page but few read on: work on both the page and its traffic. ${LEFT_WORDS}`));
  const pt = m.x.page_trends;
  if (pt?.whole_site_only) return (sec.append(h("p", { class: "note" }, "Counted for the whole site only: choose All pages to see it.")), sec);
  const sums = pageSums(pt, r);
  if (!sums) return (sec.append(h("p", { class: "note" }, r.kind === "today" ? "Turn Today · Live off: this card adds up whole days." : "Not recorded yet: visits by landing page come with the next day collected.")), sec);
  if (!sums.days) {
    sec.append(h("p", { class: "note" }, `Not recorded for these days: visits by landing page are counted from ${pt.first_day || "the next day collected"} on, never shown as zero.`));
    return sec;
  }
  const lb = leadsBy(m, s, r, t, "landing");
  const leads = lb && lb.days ? lb.leads : null;
  const w = workLists(sums, leads);
  const noForm = (x) => (x.leads == null ? "forms: not recorded" : "no form");
  sec.append(
    group("Improve the page", "wk-improve", "Many visits leave at once, no form", w.improve, s,
      (x) => `${n(x.visits)} visits · ${pct1(x.one_page, x.visits)} left at once · ${noForm(x)}`),
    group("Both", "wk-both", "Search finds them, few read on", w.both, s,
      (x) => `${n(x.search)} from search · ${pct1(x.one_page, x.visits)} left at once`));
  const total = leads ? Object.values(leads).reduce((a, b) => a + b, 0) : null;
  const best = leads ? Object.entries(leads).filter(([k, v]) => v && k !== "Unknown").sort((a, b) => b[1] - a[1])[0] : null;
  sec.append(h("p", { class: "sub" },
    leads == null ? "Which pages bring leads: not recorded for these days (leads by landing page need the conversions data)."
      : best ? `Which pages bring leads: ${n(best[1])} of the ${n(total)} leads began on ${best[0]}${lb.days < lb.of ? `, over the ${n(lb.days)} of ${n(lb.of)} days whose leads are checked` : ""}.`
        : "Which pages bring leads: no lead began on a known landing page in these days.",
    sums.days < sums.of ? ` Pages are counted over ${n(sums.days)} of the ${n(sums.of)} whole days; the others were collected before visits by landing page were kept.` : "",
    sums.folded ? " On some days a page with few visits was folded into “(all others)”, so its figures are a floor." : "",
    ` Lists need ${WORK.MIN_VISITS} visits (or ${WORK.MIN_SEARCH} from search) and show at most ${WORK.SHOW}.`),
  h("p", { class: "ov-more" }, goTo("traffic/pages", `Every page, by Needs work: Traffic › Pages${w.improveAll + w.bothAll > w.improve.length + w.both.length ? ` (${n(w.improveAll + w.bothAll)} in all)` : ""}`, { psort: "work" })));
  return sec;
}
