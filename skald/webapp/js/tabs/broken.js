// Broken links: every 404 and 410, led by the ones real people hit - where
// they came from, when, and whether a redirect now fixes it. Scanner probes
// (/.env, /wp-login.php...) are noise, kept in their own folded group.

import { h, n, short, long } from "../ui.js";
import { figures, pathMatch, ranked, chartDays, color } from "../data.js";
import { columns, legend } from "../charts.js";
import { table } from "../table.js";
import { head, nothing, coverageNote, countTable, fileName, panel, blist, fixed, healthTabs } from "./common.js";
import { tiles } from "./tiles.js";

const FIX = {
  fixed: ["fixed", "Fixed: the path answers again"],
  redirected: ["fixed", "Fixed: redirected"],
  gone: ["gone", "Gone on purpose (410)"],
  open: ["open", "Still broken"],
};
const GROUP_NAME = { people: "Real people", ai_asked: "AI, for a live question", ai_training: "AI, to train or index",
  search_engines: "Search engines", bots: "Bots and scanners", ours: "Our own traffic" };

function fixBadge(row) {
  const [cls, words] = FIX[row.fix] || FIX.open;
  const to = row.fix === "redirected" && row.fix_to ? ` to ${row.fix_to}` : row.fix === "fixed" && row.fix_status ? ` (${row.fix_status})` : "";
  return h("span", { class: `fix ${cls}`, title: words + to }, row.fix === "redirected" ? "fixed" : row.fix || "open");
}

function sources(obj) {
  const list = ranked(obj).slice(0, 4);
  if (!list.length) return h("span", { class: "muted" }, "no referrer");
  return h("span", { class: "srcs" }, list.map(([k, v]) => h("span", { class: "src" }, `${k} ${n(v)}`)));
}

// Without not_found.json: the 404s people met, by path, from the day figures.
function basic(m, s, r, t, cov) {
  return [
    h("p", { class: "note" }, "Where people came from, first and last seen, and whether a redirect fixes each path arrive with the next data update. Until then, the paths people hit:"),
    h("section", { class: "s" }, countTable(t.not_found, { caption: "Pages people could not find", file: fileName("broken-links", r), key: "Page", value: "Times hit", keep: pathMatch(s), path: true, drill: "path", empty: "No person met a missing page in this range." })),
    coverageNote(cov, r),
  ];
}

export default function broken(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [healthTabs(m, "health/broken"), ...head("Broken links", r, "Pages that answered 404 (not found) or 410 (gone). The ones real people hit come first: each is a visitor who wanted something and did not get it. Scanner probes are folded away at the bottom.")];
  const f = m.x.not_found;
  if (!f) return t ? [...out, ...basic(m, s, r, t, cov)] : [...out, nothing(m, r, "broken links")];
  const keep = pathMatch(s);
  const src = s.source;
  const paths = (f.paths || []).filter((p) => keep(p.path) && (!src || Object.keys(p.sources || {}).some((k) => k === src)));
  const people = paths.filter((p) => !p.probe && p.people > 0);
  const probes = paths.filter((p) => p.probe);
  const others = paths.filter((p) => !p.probe && !p.people);
  const open = people.filter((p) => !p.fix || p.fix === "open");

  // The tiles follow the date range (the day figures); the per-path detail below keeps its own 30 days.
  if (!t) return [...out, nothing(m, r, "broken links")];
  const inRange = ranked(t.not_found, keep);
  out.push(tiles([
    { label: "Missing pages people met", value: t.nf ?? null, info: "404 answers to real people's page requests in this period." },
    { label: "Pages people could not find", value: inRange.length, info: "Distinct paths that answered 404 to people in this period." },
    { label: "Scanner probes", value: t.probes ?? null, info: "Requests for paths no real site has, such as /.env: scanners hunting for passwords. Noise." },
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

  const cols = [
    { key: "path", label: "Page", path: true },
    { key: "people", label: "People", num: true },
    { key: "sources", label: "Came from", fmt: (v) => sources(v), csv: (row) => ranked(row.sources).map(([a, b]) => `${a} ${b}`).join("; "), sort: (row) => ranked(row.sources)[0]?.[0] || "" },
    { key: "first_day", label: "First seen", fmt: (v) => (v ? short(v) : "-") },
    { key: "last_day", label: "Last seen", fmt: (v) => (v ? short(v) : "-") },
    { key: "fix", label: "Status", fmt: (_, row) => fixBadge(row), csv: (row) => row.fix || "open", sort: (row) => (row.fix === "open" || !row.fix ? 0 : 1) },
  ];
  out.push(h("section", { class: "s" }, h("h2", null, "Pages people could not find"),
    countTable(t.not_found, { caption: "Pages people could not find", file: fileName("broken-links", r), key: "Page", value: "Times hit", keep, path: true, drill: "path", empty: "No person met a missing page in this period." })));

  if (r.kind === "today" && f.today?.rows?.length) {
    out.push(h("section", { class: "s" }, h("h2", null, "Today so far"),
      table([{ key: "path", label: "Page", path: true }, { key: "group", label: "Who", fmt: (v) => GROUP_NAME[v] || v }, { key: "source", label: "Came from" },
        { key: "n", label: "Times", num: true }, { key: "first", label: "First" }, { key: "last", label: "Last" }],
      { caption: "Missing pages today", rows: f.today.rows.filter((x) => keep(x.path) && !x.probe), file: fileName("broken-links", r), sortKey: "n" })));
  }

  const groups = {};
  for (const p of paths) for (const [g, v] of Object.entries(p.groups || {})) groups[g] = (groups[g] || 0) + v;
  out.push(fixed("Each broken path, with where people came from and its fix", "last 30 days and today",
    h("p", { class: "sub" }, `${n(open.length)} still broken: people hit these and nothing redirects them. Fix the open ones first: add a redirect to the page they meant.`),
    table(cols, { caption: "Missing pages real people hit", rows: people, file: "broken-links-people.csv", sortKey: "people", empty: s.path || src ? "No missing page matches these filters." : "No real person hit a missing page. Good." }),
    h("div", { class: "cols", style: { marginTop: "14px" } },
      panel("Who hit missing pages", "Every 404 and 410 by group, probes included", blist(ranked(groups), { label: (g) => GROUP_NAME[g] || g, color: "var(--ink-3)" })),
      panel("Other missing pages", "Hit by crawlers and assistants, not by people", blist(others.map((p) => [p.path, p.n]).sort((a, b) => b[1] - a[1]), { drill: "path", color: color("answer_engines"), empty: "None." })))));

  out.push(fixed(`Probes and scanner noise (${n(probes.length)} paths)`, "last 30 days and today",
    h("p", { class: "note" }, "Requests for files no real site serves, such as /.env and /wp-login.php: scanners hunting for passwords. Nothing to fix; shown so the totals add up."),
    table([{ key: "path", label: "Path", path: true }, { key: "n", label: "Requests", num: true }, { key: "last_day", label: "Last seen", fmt: (v) => (v ? short(v) : "-") }],
      { caption: "Scanner probes", rows: probes, file: "broken-links-probes.csv", sortKey: "n", empty: "No probes." })));

  return out;
}
