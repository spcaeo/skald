// AI & bots › Assistants, "AI reads by page: now against before" (release 2, L1).
//
// Per page: the reads by assistants answering a user (ChatGPT-User, Perplexity-User,
// Claude-User and the other user fetchers: the day kind ai_fetches, its reads column; one
// assistant asking for a page again within 30 seconds, or for the page's files, is one read),
// now and in the period before, by assistant, and its requests; then what followed on the site: the visits an AI answer sent that
// started on the page (the day kind landings, `ai`: a referrer or a tag, never a guess) and
// the leads that began there (conversions, leadfigs.js leadsBy). page_trends.json by day,
// added up over whole, verified days (page-figs.js); no model is asked anything.
//
// "Before" is Compare's period B while Compare is on, else the same number of days just
// before. When those days are not all recorded it says "not measured", never 0.

import { h, n, short } from "../ui.js";
import { previousOf, coverage, pathMatch } from "../data.js";
import { table } from "../table.js";
import { fileName } from "./common.js";
import { leadsBy } from "./leadfigs.js";
import { compareOf, spanWords } from "../mode-compare.js";
import { pageSums, readsTrend, pageKey } from "../page-figs.js";
import { changeWords } from "../period-dates.js";

const who = (per) => Object.entries(per || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([k, v]) => `${k} ${n(v)}`).join(" · ");

export function aiTrend(m, s, r, t) {
  const sec = h("section", { class: "s ai-trend" }, h("h2", null, "AI reads by page: now against before"));
  const pt = m.x.page_trends;
  if (pt?.whole_site_only) return (sec.append(h("p", { class: "note" }, "Counted for the whole site only: choose All pages to see it.")), sec);
  const a = pageSums(pt, r);
  if (!a) return (sec.append(h("p", { class: "note" }, r.kind === "today" ? "This list adds up whole days: pick Yesterday or longer." : "Not recorded yet: it comes with the next redraw.")), sec);
  const c = compareOf(m, s);
  const bRange = c.ok ? c.b : previousOf(m, r);
  const bSums = bRange && coverage(bRange).complete ? pageSums(pt, bRange) : null;
  const lb = leadsBy(m, s, r, t, "landing");
  const leads = lb && lb.days ? Object.entries(lb.leads).reduce((o, [k, v]) => ((o[pageKey(k)] = (o[pageKey(k)] || 0) + v), o), {}) : null;
  const keep = pathMatch(s);
  const rows = readsTrend(a, bSums).filter((x) => keep(x.path)).map((x) => ({ ...x, leads: leads ? leads[pageKey(x.path)] || 0 : null }));
  const bOk = rows.length ? rows[0].before != null : !!(bSums && bSums.readDays === bSums.of);
  sec.append(h("p", { class: "sub" }, `Pages read by assistants answering someone (ChatGPT-User, Perplexity-User, Claude-User and others) in ${spanWords(r)}, against ${bRange ? spanWords(bRange) : "the period before"}${c.ok ? " (Compare's B)" : ""}, then the visits an AI answer sent to the page and the leads that began there. A read is one assistant reading one page; it is not a person reading it. An AI visit is a person who followed the answer's link.`));
  const cols = [
    { key: "path", label: "Page", drill: "path", csv: (x) => x.path },
    { key: "now", label: "Reads", num: true, title: "One assistant, one page, counted once in 30 seconds; the page's own files are not reads" },
    { key: "before", label: "Before", num: true, fmt: (v) => (v == null ? h("span", { class: "few", title: "Those days are not all recorded" }, "not measured") : n(v)) },
    { key: "d", label: "Change", sort: (x) => (x.before == null ? null : x.now - x.before), csv: (x) => (x.before == null ? "" : x.now - x.before),
      fmt: (_, x) => { if (x.before == null) return h("span", { class: "few", title: "Before: not measured" }, "-"); const w = changeWords(x.now, x.before); return h("span", { class: `wc-c ${w.dir}` }, w.text); } },
    { key: "who", label: "By assistant", sort: (x) => who(x.who), fmt: (v) => who(v) || "-", csv: (x) => who(x.who) },
    { key: "requests", label: "Requests", num: true, title: "Every request for the page, repeats included" },
    { key: "ai", label: "AI visits", num: true, title: "Visits that followed an AI answer's link and started on this page" },
    { key: "leads", label: "Leads", num: true, fmt: (v) => (v == null ? h("span", { class: "few", title: "Leads by landing page are not recorded for these days" }, "-") : n(v)) },
  ];
  sec.append(table(cols, { caption: "AI reads by page", rows, file: fileName("ai-reads-by-page", r), sortKey: "now", limit: 12, empty: "No assistant fetched a page for someone in this period." }));
  const notes = [];
  if (a.readDays < a.of) notes.push(a.readFrom ? `Reads counted from ${short(a.readFrom)}: they cover ${n(a.readDays)} of the ${n(a.of)} whole days.` : "Reads are counted from the next update; these days have requests only.");
  if (a.days < a.of) notes.push(`AI visits cover ${n(a.days)} of the ${n(a.of)} whole days; the others were collected before visits by landing page were kept.`);
  if (!bOk) notes.push("Before: not measured: the period before is not whole and recorded, so no change is shown.");
  if (a.fetchFolded) notes.push("A day keeps its 200 pages with most fetches; the rest are summed as (all others), not listed.");
  if (notes.length) sec.append(h("p", { class: "note" }, notes.join(" ")));
  return sec;
}
