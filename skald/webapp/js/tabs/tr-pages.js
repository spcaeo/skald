// Traffic > Pages (2.7.0): what people read and where they started.
//
//   the period line           period-line.js: Include today, Compare, the exact dates (release 2)
//   Pages by publish date     pagestory.js published (page_index.json)
//   Page leaderboard          pagedetail.js leaderboard (pages.json, its own 30 days)
//   Landing pages, with leads one grid: the only list of landing pages (by.landing) in the
//                             app now; Sources, Visitors and the old "Where visitors started"
//                             link here. Release 2 adds Pages per visit, Left after one page,
//                             AI reads and Changed (page_trends.json, page_index.json; page-figs.js),
//                             the sort chips (psort: Most visits, Rising, Falling, Recently
//                             changed, Needs work) and "Changed in the last 30 days" (chgfrom)
//   Pages read by people      one grid (pages), replacing "Most read" and the old table
//   Links                     pages AI assistants fetched (AI & bots), pages not found (Site)
//
// One page chosen (?page=): its story since it was published, unchanged.
//
// 2.42 (the UX audit's task 7, answer first): the landing pages grid comes first (its search
// box finds a page; a row opens its story, page=); the grid's method notes are behind its
// "?"; Pages by publish date, the leaderboard and Pages read by people are under one fold
// kept in the address (pgx_view=open).

import { h, n, short, pct1 } from "../ui.js";
import { figures, pathMatch } from "../data.js";
import * as S from "../state.js";
import { grid, HASH } from "../grid.js";
import { head, nothing, fileName, fixed, ownPeriod } from "./common.js";
import { leaderboard } from "./pagedetail.js";
import { pageStory, published } from "./pagestory.js";
import { leadsBy, leadNote, viewNote } from "./leadfigs.js";
import { leadRows, countRows, labelCol, countCols, leadCols, goTo, compareOf, compareRows, compareCols, compareNote } from "./tr-grid.js";
import { periodLine } from "../period-line.js";
import { urlFold } from "../ui/fold.js";
import { help } from "../ui/help.js";
import { pageSums, perVisit, leftShare, workScore, workLists, SORTS, sortOf, changedSince, pageKey, OTHER, WORK, LEFT_WORDS } from "../page-figs.js";

const TOUCH = "landing page: the page recorded with the lead (its first visit's, when known)";
const few = (title) => h("span", { class: "few", title }, "-");

/* Release 2's page columns, after the counts: Pages per visit, Left after one page, AI reads,
   Changed, and Needs work (hidden: it holds the "Needs work" order). */
export const pageCols = (sums) => (sums ? [
  { key: "ppv", label: "Pages per visit", num: true, title: "Page views per visit that started on the page, on every page it went on to", sort: (x) => x.ppv,
    fmt: (v) => (v == null ? few("Not recorded for these days") : v.toFixed(1)), csv: (x) => (x.ppv == null ? "" : x.ppv.toFixed(2)) },
  { key: "left", label: "Left after one page", num: true, title: LEFT_WORDS, sort: (x) => x.left,
    fmt: (_, x) => (x.left == null ? few("Not recorded for these days") : `${pct1(x.one, x.visits)}${x.atLeast ? "+" : ""}`), csv: (x) => (x.left == null ? "" : x.left.toFixed(4)) },
  { key: "reads", label: "AI reads", num: true, title: "Pages read by AI assistants answering a user (ChatGPT-User, Perplexity-User, Claude-User and others): one assistant, one page, once in 30 seconds, as AI & bots › Assistants counts them", sort: (x) => x.reads,
    fmt: (v) => (v == null ? few("Not recorded for these days") : n(v)) },
  { key: "chg", label: "Changed", type: "date", title: "The page's change date: the website's own, else your sitemap's “last changed”", sort: (x) => x.chg,
    fmt: (v) => (v ? short(v) : few("No change date")) },
  { key: "work", label: "Needs work", hide: true, title: "Improve the page: many visits, nearly all left at once, no form. Both: search finds it, most leave at once.", sort: (x) => x.work,
    fmt: (_, x) => x.workWhy || "", csv: (x) => x.workWhy || "" },
] : []);

// The columns, one place per grid (compare mode adds B and ± here).
export const landingColumns = (leads, c, sums) => [labelCol("Page"), ...countCols("Visitors"), ...compareCols(c), ...(leads ? leadCols() : []), ...pageCols(sums)];
export const readColumns = (c) => [labelCol("Page"), ...countCols("Page views"), ...compareCols(c)];

/* Each landing row gets the page's own figures over the period (page-figs.js). */
export function addPageFigures(rows, sums, dates, lb) {
  if (!sums) return rows;
  const byKey = new Map();
  for (const [p, x] of Object.entries(sums.rows)) if (p !== OTHER) {
    const k = pageKey(p), cur = byKey.get(k);
    byKey.set(k, cur ? { visits: cur.visits + x.visits, one_page: cur.one_page + x.one_page, views: cur.views + x.views, search: cur.search + x.search, ai: cur.ai + x.ai, reads: cur.reads + x.reads, fetches: {} } : x);
  }
  const counted = sums.days > 0;
  const leads = lb && lb.days ? lb.leads : null;
  const lists = workLists({ rows: Object.fromEntries(byKey) }, leads ? Object.fromEntries(Object.entries(leads).map(([k, v]) => [pageKey(k), v])) : null, { ...WORK, SHOW: Infinity });
  const improve = new Set(lists.improve.map((x) => x.path)), both = new Set(lists.both.map((x) => x.path));
  for (const x of rows) {
    const k = pageKey(x.k), f = byKey.get(k);
    x.chg = dates.get(k) || null;
    if (!counted) { x.ppv = x.left = x.reads = x.work = null; continue; }
    x.visits = f?.visits || 0;
    x.one = f?.one_page || 0;
    x.ppv = f ? perVisit(f) : null;
    x.left = f ? leftShare(f) : null;
    x.atLeast = sums.folded && !f;
    x.reads = sums.readDays ? f?.reads || 0 : null;
    x.work = workScore({ visits: x.visits, left: x.left });
    x.workWhy = improve.has(k) ? "Improve the page" : both.has(k) ? "Both" : "";
  }
  return rows;
}

function sortChips(s, c, sums) {
  const asked = HASH.read().get("lp_sort");
  const pick = (k) => {
    const p = HASH.read();
    for (const key of ["lp_sort", "lp_page"]) p.delete(key);
    HASH.write(p);
    S.set({ psort: k === "visits" ? "" : k });
  };
  const cur = s.psort || "visits";
  const chips = SORTS.filter(([k]) => sums || (k !== "work")).map(([k, words, title]) => h("button", { type: "button", class: `r2-chip${!asked && cur === k ? " on" : ""}`,
    "aria-pressed": String(!asked && cur === k), title, onclick: () => pick(k) }, words));
  const needs = (cur === "rising" || cur === "falling") && !c.ok;
  return h("div", { class: "pg-sorts" }, h("span", { class: "pg-l" }, "Sort"), h("div", { class: "r2-chips", role: "group", "aria-label": "Sort the landing pages" }, chips),
    needs ? h("p", { class: "note pg-need", role: "note" }, `${cur === "rising" ? "Rising" : "Falling"} needs Compare: switch on Compare with the period before. Shown by most visits until then. `,
      h("button", { type: "button", class: "linkish", onclick: () => S.set({ cmp: "prev" }) }, "Compare with the period before")) : null);
}

function changedChip(m, s) {
  const since = changedSince(m);
  if (s.chgfrom) return h("p", { class: "pg-chg" }, h("span", { class: "r2-chip on" }, `Changed since ${short(s.chgfrom)}`,
    h("button", { type: "button", class: "r2-x", "aria-label": "Remove: changed since", onclick: () => S.set({ chgfrom: "" }) }, "×")),
  h("span", { class: "muted" }, " The landing pages and the pages read show only pages changed since then (the website's date, else your sitemap's)."));
  return h("p", { class: "pg-chg" }, h("button", { type: "button", class: "r2-chip", onclick: () => S.set({ chgfrom: since, psort: "changed" }),
    title: "Only the pages whose change date is in the last 30 days" }, "Changed in the last 30 days"),
  h("span", { class: "muted" }, " New and updated pages, by the website's dates, else your sitemap's “last changed”."));
}

export default function pages(m, s) {
  if (s.page) return pageStory(m, s);
  const { r, t } = figures(m, s);
  const out = [...head("Pages", r, "What people read and where they started. Select a page for its story since it was published."), periodLine(m, s), changedChip(m, s)];
  const c = compareOf(m, s);
  if (!t) return [...out, published(m, s), nothing(m, r, "pages")];
  // Changed since (chgfrom): the page index's change dates narrow both grids too.
  const dates = new Map((m.x.page_index?.pages || []).filter((p) => p.updated).map((p) => [pageKey(p.path), p.updated]));
  const path = pathMatch(s);
  const keep = s.chgfrom ? (k) => path(k) && (dates.get(pageKey(k)) || "") >= s.chgfrom : path;
  const details = [published(m, s)];
  if (m.x.pages) {
    // The leaderboard keeps its own last 30 whole days (with change against the 30 before); today's follows the range.
    if (r.kind === "today") details.push(h("section", { class: "s" }, h("h2", null, "Page leaderboard"), leaderboard(m, s, r)));
    else details.push(fixed("Page leaderboard, with change and each page's detail", ownPeriod(m.x.pages.period, r), leaderboard(m, s, r)));
  }
  const sub = `${s.path ? ` whose path ${s.pathmode === "starts" ? "starts with" : "contains"} ${s.path}` : ""}${s.chgfrom ? `, changed since ${short(s.chgfrom)}` : ""}`;

  if (t.by) {
    const lb = leadsBy(m, s, r, t, "landing");
    const leads = !!(lb && lb.days);
    const sums = pageSums(m.x.page_trends, r);
    const order = sortOf(s.psort, c.ok);
    const rows = addPageFigures(compareRows(c, leadRows(t.by.landing, lb, { dim: "landing", keep, whole: t.readers }), c.bT?.by?.landing, { dim: "landing", keep, whole: t.readers }), sums, dates, lb);
    const g = grid({ ns: "lp", caption: "Landing pages and leads", file: fileName("landing-leads", r), columns: landingColumns(leads, c, sums),
      rows, sortKey: order.key, dir: order.dir,
      placeholder: "Search landing pages", empty: s.path || s.chgfrom ? "No landing page matches." : "No landing page recorded." });
    g.classList.add("tr-grid", "tr-paths", "lead-tbl");
    const about = [`The first page each visitor read${sub}, and the leads that started there. Sources and landing pages are stored apart, so this is every visitor's landing page, whatever the source filter. Search for a page; select it for its story since it was published.`,
      compareNote(c), sums ? pageNote(sums, m) : null, lb ? leadNote(lb, TOUCH) : null].map((x) => (x && typeof x !== "string" ? x.textContent : x)).filter(Boolean);
    out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Landing pages and their leads"), help("Landing pages and their leads", { text: about, guide: "getting-started" })),
      sortChips(s, c, sums), g, viewNote(m, s)));
  } else out.push(h("section", { class: "s" }, h("h2", null, "Landing pages and their leads"), h("p", { class: "empty" }, "Not recorded for this range.")));

  const g = grid({ ns: "pr", caption: "Pages read by people", file: fileName("pages", r), columns: readColumns(c),
    rows: compareRows(c, countRows(t.pages, { dim: "path", keep }), c.bT?.pages, { dim: "path", keep }), sortKey: "v", placeholder: "Search pages", empty: s.path || s.chgfrom ? "No page matches." : "No page read." });
  g.classList.add("tr-grid", "tr-paths", "lead-tbl");
  details.push(h("section", { class: "s" }, h("h2", null, "Pages read by people"),
    h("p", { class: "sub" }, `Page views by people${sub}. Share is of the pages listed.`), g, compareNote(c),
    r.kind === "history" && r.length > 1 ? h("p", { class: "note" }, "Each day keeps its top 50 pages, so over several days the long tail is undercounted.") : null));
  // Drawn now (the publish list and the leaderboard load their own files), shown when the fold opens.
  out.push(urlFold("pgx", "Open the details: pages by publish date, the page leaderboard, and pages read by people", details, { open: !!(s.pubfrom || s.pubto) }));

  out.push(h("section", { class: "s tr-links" },
    goTo(S.hashFor({ ...s, tab: "ai/assistants", dd: "" }), "Pages AI assistants fetched are under", "AI & bots › Assistants"),
    goTo(S.hashFor({ ...s, tab: "site/notfound", dd: "" }), "Pages people could not find (404) are under", "Site › Not found")));
  return out;
}

// What the page columns cover, in one line.
function pageNote(sums, m) {
  const bits = [`${LEFT_WORDS} Pages per visit and Left after one page count the visits that started on the page (each visit once).`];
  if (!sums.days) bits.push(`Not recorded for these days: they are counted from ${m.x.page_trends?.first_day || "the next day collected"} on.`);
  else if (sums.days < sums.of) bits.push(`They cover ${n(sums.days)} of the ${n(sums.of)} whole days; the others were collected before they were kept.`);
  if (sums.folded) bits.push("A day keeps its 200 landing pages with most visits; a page outside them is marked +, a floor.");
  return h("p", { class: "note" }, bits.join(" "));
}
