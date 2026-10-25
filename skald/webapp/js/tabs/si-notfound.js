// Site > Not found (2.7.0): every 404 and 410, led by the ones real people hit -
// where they came from, when, and whether a redirect now fixes it. Scanner probes
// (/.env, /wp-login.php...) are noise, kept in their own folded group.
//
// The figures are broken.js's, unchanged. What changed: the two long listings are
// Data Grids (js/grid.js), their search, filters, sort and page kept in the address
// (nf_*, nfp_*); and this is the one place for the pages people could not find
// (D15 in docs/plans/2026-10-12-ui-consolidation-map.md: Health and Pages link here).

import { h, n, short, share } from "../ui.js";
import { figures, pathMatch, ranked, chartDays, color } from "../data.js";
import { columns, legend } from "../charts.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { head, nothing, fileName, panel, blist, fixed } from "./common.js";
import { tiles } from "./tiles.js";
import { grid } from "../grid.js";
// 2.35: the old addresses still asked for, with the closest live page (js/tabs/nf-lost.js).
import { lostPages } from "./nf-lost.js";
import { copyIf } from "../urlactions.js";

const FIX = {
  fixed: ["fixed", "Fixed: the path answers again"],
  redirected: ["fixed", "Fixed: redirected"],
  gone: ["gone", "Gone on purpose (410)"],
  open: ["open", "Still broken"],
};
const GROUP_NAME = { people: "Real people", ai_asked: "AI, for a live question", ai_training: "AI, to train or index",
  search_engines: "Search engines", bots: "Bots and scanners", ours: "Our own traffic" };
const isOpen = (p) => !p.fix || p.fix === "open";

function fixBadge(row) {
  const [cls, words] = FIX[row.fix] || FIX.open;
  const to = row.fix === "redirected" && row.fix_to ? ` to ${row.fix_to}` : row.fix === "fixed" && row.fix_status ? ` (${row.fix_status})` : "";
  return h("span", { class: `fix ${cls}`, title: words + to }, row.fix === "redirected" ? "fixed" : row.fix || "open");
}

function sources(obj) {
  const list = ranked(obj).slice(0, 4);
  if (!list.length) return h("span", { class: "muted" }, "no referrer");
  return h("span", { class: "srcs" }, list.map(([k, v]) => h("span", { class: "src" }, copyIf("text", h("span", null, k), k, { label: "referrer" }), ` ${n(v)}`)));
}

/* The pages people could not find in the period (the day figures' not_found): Page,
   Times hit, Share. Shares are of every such hit in the period (the path filter
   applied), never of the rows on screen. */
function couldNotFind(t, r, keep) {
  const rows = ranked(t.not_found, keep).map(([path, v]) => ({ path, v }));
  const sum = rows.reduce((a, x) => a + x.v, 0);
  return grid({
    ns: "nf", caption: "Pages people could not find", file: fileName("broken-links", r),
    columns: [
      { key: "path", label: "Page", drill: "path" },
      { key: "v", label: "Times hit", num: true },
      { key: "share", label: "Share", num: true, sort: (x) => x.v, fmt: (_, x) => share(x.v, sum), csv: (x) => (share(x.v, sum) ? (x.v / sum).toFixed(4) : "") },
    ],
    rows, sortKey: "v", placeholder: "Search pages",
    empty: "No person met a missing page in this period.",
  });
}

export default function notFound(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Not found", r, "Pages that answered 404 (not found) or 410 (gone). The ones real people hit come first: each is a visitor who wanted something and did not get it. Scanner probes are folded away at the bottom.")];
  const f = m.x.not_found;
  const lost = lostPages(m, s);
  if (lost) out.push(lost);
  if (!t) return [...out, nothing(m, r, "broken links")];
  const keep = pathMatch(s);
  // Without not_found.json: the 404s people met, by path, from the day figures.
  if (!f) {
    return [...out,
      h("p", { class: "note" }, "Where people came from, first and last seen, and whether a redirect fixes each path arrive with the next data update. Until then, the paths people hit:"),
      h("section", { class: "s" }, couldNotFind(t, r, keep))];
  }
  const src = s.source;
  const paths = (f.paths || []).filter((p) => keep(p.path) && (!src || Object.keys(p.sources || {}).some((k) => k === src)));
  const people = paths.filter((p) => !p.probe && p.people > 0);
  const probes = paths.filter((p) => p.probe);
  const others = paths.filter((p) => !p.probe && !p.people);
  const open = people.filter(isOpen);

  // The tiles follow the date range (the day figures); the per-path detail below keeps its own 30 days.
  const inRange = ranked(t.not_found, keep);
  out.push(tiles([
    { label: "Missing pages people met", value: t.nf ?? null, info: "404 answers to real people's page requests in this period." },
    { label: "Pages people could not find", value: inRange.length, info: "Distinct paths that answered 404 to people in this period." },
    { label: "Scanner probes", value: t.probes ?? null, info: "Requests for paths no real site has, such as /.env: scanners hunting for passwords. Noise.",
      line: h("a", { class: "t-c si-more", href: S.hashFor({ ...s, tab: "ai/crawlers" }) }, "With the other bots, on AI & bots") },
  ]));

  // Trend: from not_found.json's own days where it has them, drawn over the chosen range.
  if (r.kind === "history" && r.length > 1) {
    const byDay = new Map((f.days || []).map((d) => [d.day, d]));
    const days = chartDays(r).map((d) => {
      const e = byDay.get(d.day);
      return e && e.state === "ok" && e.totals ? { ...d, state: "ok", nf: e.totals } : { ...d, state: d.state === "ok" ? "missing" : d.state };
    });
    const series = [
      { name: "Real people", color: color("people"), get: (d) => d.nf?.people || 0 },
      { name: "Everything else", color: "var(--ink-3)", get: (d) => Math.max(0, (d.nf?.all || 0) - (d.nf?.people || 0) - (d.nf?.probes || 0)) },
      { name: "Scanner probes", color: color("bots"), get: (d) => d.nf?.probes || 0 },
    ];
    out.push(h("section", { class: "s" }, h("h2", null, "Missing pages per day"),
      h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"]]),
        columns(days, series, { label: "404 and 410 responses per day", unit: "responses", H: 210 }))));
  }

  out.push(h("section", { class: "s" }, h("h2", null, "Pages people could not find"), couldNotFind(t, r, keep)));

  if (r.kind === "today" && f.today?.rows?.length) {
    out.push(h("section", { class: "s" }, h("h2", null, "Today so far"),
      table([{ key: "path", label: "Page", path: true }, { key: "group", label: "Who", fmt: (v) => GROUP_NAME[v] || v }, { key: "source", label: "Came from" },
        { key: "n", label: "Times", num: true }, { key: "first", label: "First", type: "date" }, { key: "last", label: "Last", type: "date" }],
      { caption: "Missing pages today", rows: f.today.rows.filter((x) => keep(x.path) && !x.probe), file: fileName("broken-links", r), sortKey: "n" })));
  }

  const groups = {};
  for (const p of paths) for (const [g, v] of Object.entries(p.groups || {})) groups[g] = (groups[g] || 0) + v;
  const each = grid({
    ns: "nfp", caption: "Missing pages real people hit", file: "broken-links-people.csv",
    columns: [
      { key: "path", label: "Page", drill: "path" },
      { key: "people", label: "People", num: true },
      { key: "sources", label: "Came from", fmt: (v) => sources(v), csv: (row) => ranked(row.sources).map(([a, b]) => `${a} ${b}`).join("; "), sort: (row) => ranked(row.sources)[0]?.[0] || "" },
      { key: "first_day", label: "First seen", type: "date", fmt: (v) => (v ? short(v) : "-"), csv: (row) => row.first_day || "" },
      { key: "last_day", label: "Last seen", type: "date", fmt: (v) => (v ? short(v) : "-"), csv: (row) => row.last_day || "" },
      { key: "fix", label: "Status", type: "badge", fmt: (_, row) => fixBadge(row), csv: (row) => row.fix || "open", sort: (row) => (isOpen(row) ? 0 : 1) },
    ],
    rows: people, sortKey: "people", placeholder: "Search pages and where people came from",
    segments: [
      { id: "all", label: "All" },
      { id: "open", label: "Still broken", test: isOpen },
      { id: "fixed", label: "Fixed", test: (p) => p.fix === "fixed" || p.fix === "redirected" },
      { id: "gone", label: "Gone (410)", test: (p) => p.fix === "gone" },
    ],
    empty: s.path || src ? "No missing page matches these filters." : "No real person hit a missing page. Good.",
  });
  const fold = fixed("Each broken path, with where people came from and its fix", "last 30 days and today",
    h("p", { class: "sub" }, `${n(open.length)} still broken: people hit these and nothing redirects them. Fix the open ones first: add a redirect to the page they meant.`),
    each,
    h("div", { class: "cols", style: { marginTop: "14px" } },
      panel("Who hit missing pages", "Every 404 and 410 by group, probes included", blist(ranked(groups), { label: (g) => GROUP_NAME[g] || g, color: "var(--ink-3)" })),
      panel("Other missing pages", "Hit by crawlers and assistants, not by people", blist(others.map((p) => [p.path, p.n]).sort((a, b) => b[1] - a[1]), { drill: "path", color: color("answer_engines"), empty: "None." }))));
  // A link that carries this grid's search, filter or page opens the fold it lives in.
  if (/[?&]nfp_/.test(location.hash)) fold.open = true;
  out.push(fold);

  out.push(fixed(`Probes and scanner noise (${n(probes.length)} paths)`, "last 30 days and today",
    h("p", { class: "note" }, "Requests for files no real site serves, such as /.env and /wp-login.php: scanners hunting for passwords. Nothing to fix; shown so the totals add up."),
    table([{ key: "path", label: "Path", path: true }, { key: "n", label: "Requests", num: true }, { key: "last_day", label: "Last seen", type: "date", fmt: (v) => (v ? short(v) : "-") }],
      { caption: "Scanner probes", rows: probes, file: "broken-links-probes.csv", sortKey: "n", empty: "No probes." })));

  return out;
}
