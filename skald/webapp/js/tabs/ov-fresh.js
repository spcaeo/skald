// Overview › Summary, card "New and updated pages: are they getting found?" (release 2,
// card S11): the pages whose change date (the website's own, else the sitemap's <lastmod>)
// is in the last 30 days, and what happened since: visits, visits from search, the first
// search visit, and whether Googlebot fetched the page. page_trends.json `changed`, worked
// out again by audit_page_trends.py. Its own period (the last 30 days to yesterday), said in
// the card, never the bar's. When most sitemap dates fall on one day they look like build
// times, and the card says so.

import { h, n, short } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { goTo } from "./ov-live.js";

const LIMIT = 8;

function sourceWords(rows) {
  const from = new Set(rows.map((x) => x.source || "sitemap"));
  if (from.size === 1 && from.has("website")) return "Dates from your website's page list.";
  if (from.size === 1) return "Dates from your sitemap (“last changed”).";
  return "Dates from your website's page list, else your sitemap (“last changed”).";
}

const measured = (v, x) => (x.visits == null ? h("span", { class: "few", title: "No whole, recorded day since the change yet" }, "-") : `${x.at_least ? "≥ " : ""}${n(v)}`);

export function freshCard(m, s) {
  const sec = h("section", { class: "s fr", "aria-label": "New and updated pages" }, h("h2", null, "New and updated pages: are they getting found?"));
  const pt = m.x.page_trends;
  if (pt?.whole_site_only) return (sec.append(h("p", { class: "note" }, "Change dates are the whole site's: choose All pages to see them.")), sec);
  const ch = pt?.changed;
  if (!ch) return (sec.append(h("p", { class: "note" }, "Not recorded yet: this card comes with the next redraw.")), sec);
  const c = ch.counts;
  if (!ch.pages.length) {
    const dated = m.x.page_index?.pages?.some((p) => p.updated);
    sec.append(h("p", { class: "sub" }, dated ? `No page changed in the last ${ch.days} days (since ${short(ch.since)}), by the dates Skald has.`
      : "Skald has no change dates for this site yet: they come from the website's page list or the sitemap's “last changed” dates, read once a day."));
    return sec;
  }
  const notYet = c.pages - c.measured;
  sec.append(h("p", { class: "sub" }, `${sourceWords(ch.pages)} ${n(c.pages)} page${c.pages === 1 ? "" : "s"} changed since ${short(ch.since)}: ${n(c.visited)} had a visit, ${n(c.searched)} a visit from search, ${n(c.none)} none yet${notYet ? `, ${n(notYet)} not measured yet` : ""}. Google fetched ${n(c.google)} of them. Its own period: the last ${ch.days} days to ${short(ch.until)}.`));
  if (pt.same_day) sec.append(h("p", { class: "note fr-same", role: "note" },
    `Dates look like build times: ${n(pt.same_day.pages)} of the ${n(pt.same_day.of)} dated pages in your sitemap say ${short(pt.same_day.day)}. A site that stamps every page when it is built makes every page look changed; check how your sitemap sets “last changed”.`));
  const story = (path) => S.hashFor({ ...s, tab: "traffic/pages", page: path, dd: "" });
  const cols = [
    { key: "path", label: "Page", path: true, fmt: (v) => h("a", { class: "mono", href: story(v) }, v), csv: (x) => x.path },
    { key: "changed", label: "Changed", type: "date", fmt: (v) => short(v) },
    { key: "visits", label: "Visits", num: true, fmt: measured, sort: (x) => x.visits },
    { key: "search", label: "Search", num: true, fmt: measured, sort: (x) => x.search },
    { key: "first_search", label: "1st search", type: "date", fmt: (v, x) => (v ? short(v) : x.visits == null ? "-" : "none yet") },
    { key: "google", label: "Google fetched", title: "The last day Googlebot fetched the page since the change", fmt: (v, x) => (v ? short(x.google_last) : v === false ? "not yet" : h("span", { class: "few", title: "No crawl health for those days" }, "not recorded")),
      sort: (x) => (x.google ? x.google_last : x.google === false ? "0" : null), csv: (x) => (x.google == null ? "" : x.google ? x.google_last : "no") },
  ];
  sec.append(table(cols, { caption: "New and updated pages", rows: ch.pages, file: `changed-pages-${ch.since}-to-${ch.until}.csv`, limit: LIMIT, search: false, tools: false,
    sortKey: "changed", dir: -1, empty: "None." }));
  sec.append(h("p", { class: "ov-more" }, goTo("traffic/pages", `All ${n(c.pages)}${c.none ? `, and the ${n(c.none)} with no visit yet` : ""}: Traffic › Pages`, { chgfrom: ch.since, psort: "changed" })));
  return sec;
}
