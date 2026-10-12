// Site > Health (2.7.0): what the server answered (status classes per group),
// the errors, how fast it answered people's page views, and whether the site was
// up, with every outage the heartbeat saw. The figures and their sums are
// health.js's, unchanged; what moved (docs/plans/2026-10-12-ui-consolidation-map.md):
//   * the pages people could not find (D15) are on Site > Not found only; the
//     tile here keeps its count and links there
//   * the heartbeat's outages and gaps (D18), on Settings > Internal traffic until
//     2.7.0, are here under "Is the site up?"
//   * no sub-tab row: the Site section's tab strip names Alerts, Speed and the rest

import { h, n, share } from "../ui.js";
import { GROUPS, color, figures, pathMatch, ranked, chartDays } from "../data.js";
import { bars, columns, legend } from "../charts.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { head, nothing, panel, countTable, fileName, compareFor } from "./common.js";
import { bucketAt } from "./health.js";
import { uptime } from "./uptime.js";
import { serverLoad } from "./load.js";
import { time as tzTime, siteWall } from "../tz.js";

const STATUSES = ["2xx", "3xx", "404", "4xx", "5xx", "other"];
const STATUS_WORDS = { "2xx": "answered", "3xx": "redirected", "404": "not found", "4xx": "other client errors", "5xx": "server errors", other: "other" };
const STATUS_TONE = { "2xx": "var(--good)", "3xx": "var(--g-people)", "404": "var(--warn)", "4xx": "var(--g-bots)", "5xx": "var(--bad)", other: "var(--ink-3)" };
const SPEEDS = ["under 0.2 s", "0.2 to 0.5 s", "0.5 to 1 s", "1 to 3 s", "3 s or more"];

function statusRows(st) {
  return GROUPS.map(([g, name]) => {
    const row = st?.[g] || {};
    const sum = STATUSES.reduce((a, k) => a + (row[k] || 0), 0);
    return { g, name, sum, ...Object.fromEntries(STATUSES.map((k) => [k, row[k] || 0])) };
  });
}

// Every heartbeat gap longer than 10 minutes in the range (ours.json, the days the
// heartbeat card above counts). A gap's times are the site's wall clock on its day.
function gapsOf(f, r) {
  const days = (f?.days || []).filter((d) => d.day >= r.first && d.day <= r.last && d.heartbeat);
  if (r.kind === "today" && f?.today?.heartbeat) days.push(f.today);
  return days.flatMap((d) => (d.heartbeat.gaps || []).map((g) => {
    const from = siteWall(`${d.day}T${g.from}`);
    return { ...g, day: d.day, at: from, until: Number.isNaN(from) || g.minutes == null ? NaN : from + g.minutes * 60000 };
  }));
}

function upSection(m, r) {
  const sec = uptime(m, r);
  if (!sec) return null;
  const gaps = gapsOf(m.x.ours, r);
  const outages = h("div", { class: "si-outages", id: "si-outages" }, h("h3", null, "Outages and heartbeat gaps"),
    h("p", { class: "sub" }, "Each stretch of more than 10 minutes without an answered heartbeat: the site was down, or the heartbeat itself stopped."),
    table([
      { key: "at", label: "From", fmt: (v) => (Number.isNaN(v) ? "-" : tzTime(v, { date: true })), csv: (x) => `${x.day} ${x.from}` },
      { key: "until", label: "To", fmt: (v) => (Number.isNaN(v) ? "-" : tzTime(v, { date: true })), csv: (x) => x.to },
      { key: "minutes", label: "Minutes", num: true },
    ], { caption: "Outages and heartbeat gaps", rows: gaps, file: fileName("heartbeat-gaps", r), search: false, sortKey: "at", dir: -1, limit: 10, empty: "No gap longer than 10 minutes in this range." }));
  // The heartbeat card's "Every gap" (uptime.js) links here; on this tab the gaps are right below.
  for (const a of sec.querySelectorAll('a[href="#site/health"]')) {
    a.replaceWith(h("button", { type: "button", class: "linkish", onclick: () => outages.scrollIntoView({ block: "start", behavior: "smooth" }) }, "Every gap, below"));
  }
  sec.append(h("div", { class: "sheet" }, outages));
  return sec;
}

export default function health(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Site health", r, "Every response, by status and by who asked; server errors; how fast the server answered people's page views; and whether the site was up. The pages people could not find are on Not found.")];
  if (!t) return [...out, nothing(m, r)];
  if (!t.statuses || t.unmeasured?.health) out.push(h("p", { class: "note" }, t.statuses ? `${t.unmeasured.health} of these days were collected before health figures existed; they are left out here.` : "Health figures were not recorded for this range."));
  const keep = pathMatch(s);
  out.push(h("section", { class: "s" }, h("h2", null, "Server requests (every file: pages, images, scripts)"),
    h("p", { class: "sub" }, "Every request the server answered in this period, by who asked. This is server load, not people."),
    h("div", { class: "sheet" }, serverLoad(t, r, cov))));
  const speeds = t.speeds || {};
  const views = SPEEDS.reduce((a, b) => a + (speeds[b] || 0), 0);
  const slow = (speeds["1 to 3 s"] || 0) + (speeds["3 s or more"] || 0);
  const p50 = t.speed_p50 != null ? `${t.speed_p50} s` : bucketAt(speeds, 0.5), p95 = t.speed_p95 != null ? `${t.speed_p95} s` : bucketAt(speeds, 0.95);
  const err = t.err ?? 0;
  const tile = (label, v, note, tone) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note),
    h("div", { class: "k-v", style: tone ? { color: tone } : null }, v), h("div", { class: "k-c" }));
  const nfTile = tile("Page not found, seen by people", t.nf == null ? "-" : n(t.nf), "404s people met, not scanners");
  nfTile.lastChild.append(h("a", { class: "si-more", href: S.hashFor({ ...s, tab: "site/notfound" }) }, "Which pages, on Not found"));
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    tile("Server errors (5xx)", n(err), err ? "responses to anyone; should be zero" : "none: as it should be", err ? "var(--bad)" : null),
    nfTile,
    tile("Typical answer time", p50 || "-", "the median page view for people; only buckets are kept"),
    tile("Slowest 5%", p95 || "-", "the 95th percentile falls in this bucket"),
    tile("Slow page views", share(slow, views) || (views ? n(slow) : "-"), `${n(slow)} took a second or more`))));
  out.push(upSection(m, r));
  if (r.kind === "history" && r.length > 1) {
    const series = [{ name: "Server errors (5xx)", color: "var(--bad)", get: (d) => d.err || 0 }, { name: "404s seen by people", color: "var(--warn)", get: (d) => d.nf || 0 }];
    const cmp = compareFor(m, s);
    out.push(h("section", { class: "s" }, h("h2", null, "Errors per day"), cmp.note,
      h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"], ...cmp.legend]), columns(chartDays(r), series, { label: "Errors per day", unit: "responses", H: 200, prev: cmp.prev }))));
  }
  const rows = statusRows(t.statuses);
  out.push(h("section", { class: "s" }, h("h2", null, "Responses by status, for each group"),
    h("div", { class: "sheet" }, legend(STATUSES.map((k) => [`${k} ${STATUS_WORDS[k]}`, STATUS_TONE[k]])),
      h("div", { class: "si-status" }, rows.map((row) => h("div", null,
        h("div", { class: "si-status-h" },
          h("span", null, h("span", { class: "sw", style: { background: color(row.g) } }), row.name), h("span", { class: "tbl-count" }, `${n(row.sum)} requests`)),
        h("div", { class: "meter", role: "img", "aria-label": `${row.name}: ` + STATUSES.filter((k) => row[k]).map((k) => `${k} ${n(row[k])}`).join(", ") },
          STATUSES.filter((k) => row[k]).map((k) => h("i", { title: `${k}: ${n(row[k])}`, style: { flexGrow: String(row[k]), background: STATUS_TONE[k] } }))))))),
    table([{ key: "name", label: "Group" }, ...STATUSES.map((k) => ({ key: k, label: k, num: true })), { key: "sum", label: "All", num: true }],
      { caption: "Responses by status and group", rows, file: fileName("statuses", r), search: false, sortKey: "sum" })));
  out.push(h("div", { class: "cols" },
    panel("How fast people's pages were answered", "Server time per page view ($request_time)",
      bars(SPEEDS.map((b, i) => ({ label: b.replace(" to ", "-"), title: b, value: speeds[b] || 0, color: i >= 3 ? "var(--warn)" : "var(--good)" })), { label: "Page views by answer time", unit: "page views", H: 190, half: true }),
      speeds["not logged"] ? h("p", { class: "note" }, `${n(speeds["not logged"])} page views had no time in the log line.`) : null),
    h("section", { class: "s" }, h("h2", null, "Slow pages"), countTable(t.slow_pages, { caption: "Slow pages", file: fileName("slow-pages", r), key: "Page", value: "Slow views", keep, path: true, drill: "path", empty: "No page took a second or more." }))));
  const posts = Object.entries(t.posts || {}).flatMap(([g, p]) => ranked(p.pages, keep).map(([page, v]) => ({ group: GROUPS.find(([k]) => k === g)?.[1] || g, page, v })));
  out.push(h("div", { class: "cols" },
    h("section", { class: "s" }, h("h2", null, "Server errors by page"), countTable(t.server_errors, { caption: "5xx by page", file: fileName("server-errors", r), key: "Page", value: "5xx", keep, path: true, drill: "path", empty: "No server errors. Good." })),
    h("section", { class: "s" }, h("h2", null, "Form posts"), h("p", { class: "sub" }, "Counted, never read: what was sent is not in the log."),
      table([{ key: "group", label: "From" }, { key: "page", label: "Page", path: true, drill: "path" }, { key: "v", label: "Posts", num: true }], { caption: "POST requests", rows: posts, file: fileName("posts", r), empty: "No form posts in this range." }))));
  return out;
}
