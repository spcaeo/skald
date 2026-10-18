// Site health: what the server answered (status classes per group), the
// errors, and how fast it answered people's page views.

import { h, n, share } from "../ui.js";
import { GROUPS, color, figures, pathMatch, ranked, chartDays } from "../data.js";
import { bars, columns, legend } from "../charts.js";
import { table } from "../table.js";
import { head, nothing, coverageNote, panel, countTable, fileName, compareFor, healthTabs } from "./common.js";
import { uptime } from "./uptime.js";
import { serverLoad } from "./load.js";

const STATUSES = ["2xx", "3xx", "404", "4xx", "5xx", "other"];
const STATUS_WORDS = { "2xx": "answered", "3xx": "redirected", "404": "not found", "4xx": "other client errors", "5xx": "server errors", other: "other" };
const STATUS_TONE = { "2xx": "var(--good)", "3xx": "var(--g-people)", "404": "var(--warn)", "4xx": "var(--g-bots)", "5xx": "var(--bad)", other: "var(--ink-3)" };
const SPEEDS = ["under 0.2 s", "0.2 to 0.5 s", "0.5 to 1 s", "1 to 3 s", "3 s or more"];

// The bucket holding a percentile: honest about precision, since only buckets are kept.
export function bucketAt(speeds, q) {
  const total = SPEEDS.reduce((a, b) => a + (speeds[b] || 0), 0);
  if (!total) return null;
  let seen = 0;
  for (const b of SPEEDS) { seen += speeds[b] || 0; if (seen >= q * total) return b; }
  return SPEEDS[SPEEDS.length - 1];
}

function statusRows(st) {
  return GROUPS.map(([g, name]) => {
    const row = st?.[g] || {};
    const sum = STATUSES.reduce((a, k) => a + (row[k] || 0), 0);
    return { g, name, sum, ...Object.fromEntries(STATUSES.map((k) => [k, row[k] || 0])) };
  });
}

export default function health(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [healthTabs(m, "health"), ...head("Site health", r, "Every response, by status and by who asked; the pages people could not find; server errors; and how fast the server answered people's page views.")];
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
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    tile("Server errors (5xx)", n(err), err ? "responses to anyone; should be zero" : "none: as it should be", err ? "var(--bad)" : null),
    tile("Page not found, seen by people", t.nf == null ? "-" : n(t.nf), "404s people met, not scanners"),
    tile("Typical answer time", p50 || "-", "the median page view for people; only buckets are kept"),
    tile("Slowest 5%", p95 || "-", "the 95th percentile falls in this bucket"),
    tile("Slow page views", share(slow, views) || (views ? n(slow) : "-"), `${n(slow)} took a second or more`))));
  out.push(uptime(m, r));
  if (r.kind === "history" && r.length > 1) {
    const series = [{ name: "Server errors (5xx)", color: "var(--bad)", get: (d) => d.err || 0 }, { name: "404s seen by people", color: "var(--warn)", get: (d) => d.nf || 0 }];
    const cmp = compareFor(m, s);
    out.push(h("section", { class: "s" }, h("h2", null, "Errors per day"), cmp.note,
      h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"], ...cmp.legend]), columns(chartDays(r), series, { label: "Errors per day", unit: "responses", H: 200, prev: cmp.prev }))));
  }
  const rows = statusRows(t.statuses);
  out.push(h("section", { class: "s" }, h("h2", null, "Responses by status, for each group"),
    h("div", { class: "sheet" }, legend(STATUSES.map((k) => [k === "other" ? "Any other status" : `${k} ${STATUS_WORDS[k]}`, STATUS_TONE[k]])),
      h("div", { style: { display: "grid", gap: "12px" } }, rows.map((row) => h("div", null,
        h("div", { style: { display: "flex", justifyContent: "space-between", fontSize: "13px", marginBottom: "4px" } },
          h("span", null, h("span", { class: "sw", style: { background: color(row.g), marginRight: "8px" } }), row.name), h("span", { class: "tbl-count" }, `${n(row.sum)} requests`)),
        h("div", { class: "meter", role: "img", "aria-label": `${row.name}: ` + STATUSES.filter((k) => row[k]).map((k) => `${k} ${n(row[k])}`).join(", ") },
          STATUSES.filter((k) => row[k]).map((k) => h("i", { title: `${k}: ${n(row[k])}`, style: { flexGrow: String(row[k]), background: STATUS_TONE[k] } }))))))),
    table([{ key: "name", label: "Group" }, ...STATUSES.map((k) => ({ key: k, label: k, num: true })), { key: "sum", label: "All", num: true }],
      { caption: "Responses by status and group", rows, file: fileName("statuses", r), search: false, sortKey: "sum" })));
  out.push(h("div", { class: "cols" },
    panel("How fast people's pages were answered", "Time the server took to answer each page view",
      bars(SPEEDS.map((b, i) => ({ label: b.replace(" to ", "-"), title: b, value: speeds[b] || 0, color: i >= 3 ? "var(--warn)" : "var(--good)" })), { label: "Page views by answer time", unit: "page views", H: 190, half: true }),
      speeds["not logged"] ? h("p", { class: "note" }, `${n(speeds["not logged"])} page views had no time in the log line.`) : null),
    h("section", { class: "s" }, h("h2", null, "Slow pages"), countTable(t.slow_pages, { caption: "Slow pages", file: fileName("slow-pages", r), key: "Page", value: "Slow views", keep, path: true, drill: "path", empty: "No page took a second or more." }))));
  out.push(h("div", { class: "cols" },
    h("section", { class: "s" }, h("h2", null, "Server errors by page"), countTable(t.server_errors, { caption: "5xx by page", file: fileName("server-errors", r), key: "Page", value: "5xx", keep, path: true, drill: "path", empty: "No server errors. Good." })),
    h("section", { class: "s" }, h("h2", null, "Page not found, seen by people"), countTable(t.not_found, { caption: "404s seen by people", file: fileName("not-found", r), key: "Page", value: "404s", keep, path: true, drill: "path", empty: "No person met a missing page." }))));
  const posts = Object.entries(t.posts || {}).flatMap(([g, p]) => ranked(p.pages, keep).map(([page, v]) => ({ group: GROUPS.find(([k]) => k === g)?.[1] || g, page, v })));
  out.push(h("section", { class: "s" }, h("h2", null, "Form posts"), h("p", { class: "sub" }, "Counted, never read: what was sent is not in the log."),
    table([{ key: "group", label: "From" }, { key: "page", label: "Page", path: true, drill: "path" }, { key: "v", label: "Posts", num: true }], { caption: "POST requests", rows: posts, file: fileName("posts", r), empty: "No form posts in this range." })));
  out.push(coverageNote(cov, r));
  return out;
}
