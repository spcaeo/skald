// Traffic > Pages (2.7.0): what people read and where they started.
//
//   Pages by publish date      pagestory.js published (page_index.json)
//   Page leaderboard           pagedetail.js leaderboard (pages.json, its own 30 days)
//   Landing pages, with leads  one grid: the only list of landing pages (by.landing) in the
//                              app now; Sources, Visitors and the old "Where visitors started"
//                              link here
//   Pages read by people       one grid (pages), replacing "Most read" and the old table
//   Links                      pages AI assistants fetched (AI & bots), pages not found (Site)
//
// One page chosen (?page=): its story since it was published, unchanged.

import { h } from "../ui.js";
import { figures, pathMatch } from "../data.js";
import * as S from "../state.js";
import { grid } from "../grid.js";
import { head, nothing, fileName, fixed, ownPeriod } from "./common.js";
import { leaderboard } from "./pagedetail.js";
import { pageStory, published } from "./pagestory.js";
import { leadsBy, leadNote, viewNote } from "./leadfigs.js";
import { leadRows, countRows, labelCol, countCols, leadCols, goTo, compareOf, compareRows, compareCols, compareNote } from "./tr-grid.js";

const TOUCH = "landing page: the page recorded with the lead (its first visit's, when known)";

// The columns, one place per grid (compare mode adds B and ± here).
export const landingColumns = (leads, c) => [labelCol("Page"), ...countCols("Visitors"), ...compareCols(c), ...(leads ? leadCols() : [])];
export const readColumns = (c) => [labelCol("Page"), ...countCols("Page views"), ...compareCols(c)];

export default function pages(m, s) {
  if (s.page) return pageStory(m, s);
  const { r, t } = figures(m, s);
  const out = [...head("Pages", r, "What people read and where they started. Select a page for its story since it was published.")];
  const c = compareOf(m, s);
  out.push(published(m, s));
  if (!t) return [...out, nothing(m, r, "pages")];
  const keep = pathMatch(s);
  if (m.x.pages) {
    // The leaderboard keeps its own last 30 whole days (with change against the 30 before); today's follows the range.
    if (r.kind === "today") out.push(h("section", { class: "s" }, h("h2", null, "Page leaderboard"), leaderboard(m, s, r)));
    else out.push(fixed("Page leaderboard, with change and each page's detail", ownPeriod(m.x.pages.period, r), leaderboard(m, s, r)));
  }
  const sub = s.path ? ` whose path ${s.pathmode === "starts" ? "starts with" : "contains"} ${s.path}` : "";

  if (t.by) {
    const lb = leadsBy(m, s, r, t, "landing");
    const leads = !!(lb && lb.days);
    const g = grid({ ns: "lp", caption: "Landing pages and leads", file: fileName("landing-leads", r), columns: landingColumns(leads, c),
      rows: compareRows(c, leadRows(t.by.landing, lb, { dim: "landing", keep, whole: t.readers }), c.bT?.by?.landing, { dim: "landing", keep, whole: t.readers }), sortKey: "v",
      placeholder: "Search landing pages", empty: s.path ? "No landing page matches." : "No landing page recorded." });
    g.classList.add("tr-grid", "tr-paths", "lead-tbl");
    out.push(h("section", { class: "s" }, h("h2", null, "Landing pages and their leads"),
      h("p", { class: "sub" }, `The first page each visitor read${sub}, and the leads that started there. Sources and landing pages are stored apart, so this is every visitor's landing page, whatever the source filter.`),
      g, compareNote(c), lb ? leadNote(lb, TOUCH) : null, viewNote(m, s)));
  } else out.push(h("section", { class: "s" }, h("h2", null, "Landing pages and their leads"), h("p", { class: "empty" }, "Not recorded for this range.")));

  const g = grid({ ns: "pr", caption: "Pages read by people", file: fileName("pages", r), columns: readColumns(c),
    rows: compareRows(c, countRows(t.pages, { dim: "path", keep }), c.bT?.pages, { dim: "path", keep }), sortKey: "v", placeholder: "Search pages", empty: s.path ? "No page matches." : "No page read." });
  g.classList.add("tr-grid", "tr-paths", "lead-tbl");
  out.push(h("section", { class: "s" }, h("h2", null, "Pages read by people"),
    h("p", { class: "sub" }, `Page views by people${sub}. Share is of the pages listed.`), g, compareNote(c),
    r.kind === "history" && r.length > 1 ? h("p", { class: "note" }, "Each day keeps its top 50 pages, so over several days the long tail is undercounted.") : null));

  out.push(h("section", { class: "s tr-links" },
    goTo(S.hashFor({ ...s, tab: "ai/assistants", dd: "" }), "Pages AI assistants fetched are under", "AI & bots › Assistants"),
    goTo(S.hashFor({ ...s, tab: "site/notfound", dd: "" }), "Pages people could not find (404) are under", "Site › Not found")));
  return out;
}
