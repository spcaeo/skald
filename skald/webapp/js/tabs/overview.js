// Overview: people first. One period rules the page - the date range, page
// group and filters above - and every figure here follows it: today so far,
// or the whole verified days of the range, never a mix.
//
//   1. five tiles (ov-tiles.js): people, from search engines, returning people,
//      leads, sent by AI assistants - each with its change while Compare is on
//   2. one line on how they relate to the files the server sent
//   3. the main chart: visitors and pages, by hour today, by day otherwise
//   4. who else came (machines, each in its own unit)
//   5. top pages, sources, countries and AI assistants
//   6. collapsed: server load (requests) and each day's figures

import { h, n, long } from "../ui.js";
import { GROUPS, color, figures, chartDays, ranked } from "../data.js";
import { lines, legend, bars } from "../charts.js";
import { table } from "../table.js";
import { open as openDrill } from "../drill.js";
import { head, nothing, fileName, compareFor } from "./common.js";
import { others, top } from "./tiles.js";
import { keyTiles } from "./ov-tiles.js";
import { compareOf, spanWords } from "../mode-compare.js";
import { serverLoad, LOAD_NAMES } from "./load.js";
import { hourLabels, label as tzLabel } from "../tz.js";
import { convFile, convDay, dayLeads } from "./leadfigs.js";

const LEAD_TYPES = ["signup", "contact", "waitlist"];
const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));

// Leads over the same days, from the lead store; null when none of them is recorded there.
export function leadsOver(m, days) {
  const f = m.x.leads;
  if (!f || f.available === false) return null;
  const by = new Map((f.days || []).filter((d) => !f.since || d.day >= f.since).map((d) => [d.day, d]));
  const got = days.map((d) => by.get(d)).filter(Boolean);
  if (!got.length) return null;
  return got.reduce((a, d) => a + LEAD_TYPES.reduce((b, k) => b + (d.leads?.[k] || 0), 0), 0);
}

/* Leads per day for the main chart's marks: a day's leads only when it is
   whole in the log (the chart draws no other) and checked in conversions;
   else null, "not recorded" in the tooltip. null without the file. */
function leadMarks(m) {
  const f = convFile(m);
  if (!f) return null;
  return { name: "Leads", color: "var(--leads)", get: (d) => dayLeads(f, convDay(f, d.day))?.leads ?? null };
}

function dailyTable(r) {
  const rows = r.days.filter((d) => d.state !== "before").reverse().map((d) => ({
    __k: d.day, day: d.day, state: d.state, readers: d.state === "ok" ? d.readers : null, views: d.state === "ok" ? d.views : null, cited: d.state === "ok" ? d.cited : null,
    visits: d.state === "ok" ? d.visits : null, ...Object.fromEntries(GROUPS.map(([g]) => [g, d.state === "ok" || d.state === "partial" ? d.hits?.[g] ?? null : null])),
  }));
  const words = { ok: "", partial: "partial, left out of totals", withheld: "withheld: did not add up", missing: "not collected" };
  const cols = [
    { key: "day", label: "Day", fmt: (v, row) => `${long(v)}${words[row.state] ? ` (${words[row.state]})` : ""}`, csv: (row) => row.day },
    { key: "state", label: "State", fmt: (v) => (v === "ok" ? "verified" : v) },
    { key: "readers", label: "Visitors", num: true }, { key: "views", label: "Pages read", num: true }, { key: "cited", label: "From AI", num: true },
    { key: "visits", label: "Browser sessions", num: true },
    ...GROUPS.map(([g]) => ({ key: g, label: `${LOAD_NAMES[g]} (requests)`, num: true })),
  ];
  return table(cols, { caption: "Each day's figures", rows, file: fileName("daily", r), limit: 10, sortKey: "day", dir: -1,
    rowClass: (row) => (row.state === "ok" ? null : "withheld"),
    note: "Browser sessions include ones that loaded no page, such as an image shown in an email or a chat preview." });
}

export default function overview(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Overview", r, null, { cov })];
  if (!t) return [...out, nothing(m, r)];
  const c = compareOf(m, s);
  const cmp = compareFor(m, s);

  out.push(...keyTiles(m, s, r, t, c));
  if (t.readers != null && t.views != null) {
    out.push(h("p", { class: "relate" }, `${n(t.readers)} visitor${t.readers === 1 ? "" : "s"} read ${n(t.views)} page${t.views === 1 ? "" : "s"}, which took ${n(t.hits?.people ?? 0)} requests to the server (pages, images, scripts and styles).`,
      c.ok ? h("span", { class: "muted" }, ` Changes are against ${spanWords(c.b)}.`) : null));
  }

  // The main chart: by hour for one day, by day for a longer period.
  if (r.kind === "today" || r.length === 1) {
    const hours = (r.kind === "today" ? t.by?.hour : r.days[0]?.by?.hour) || null;
    const now = r.kind === "today" ? Number(String(m.live?.generated_at || "").slice(11, 13)) : 24;
    const labels = hourLabels(r.kind === "today" ? m.today : r.first);
    if (hours) out.push(h("section", { class: "s" }, h("h2", null, `Visitors by hour (${tzLabel()})`),
      h("p", { class: "sub" }, `By the hour of their first page.${r.kind === "today" ? " The current hour is still filling." : ""} Select an hour for its detail.`),
      h("div", { class: "sheet" }, bars(HOURS.map((hh, i) => ({ label: labels[i], title: `${labels[i]} to ${labels[(i + 1) % 24]} ${tzLabel()}${i === now ? " (so far)" : ""}`,
        value: i > now ? 0 : hours[hh] || 0, color: i === now ? "color-mix(in srgb, var(--g-people) 55%, var(--surface))" : color("people") })),
      { label: "Visitors by hour", unit: "visitors", every: 3, H: 180, onPick: (i) => openDrill("hour", HOURS[i]) }))));
  } else {
    const marks = leadMarks(m);
    out.push(h("section", { class: "s" }, h("h2", null, marks ? "Visitors, pages read and leads, by day" : "Visitors and pages read, by day"),
      h("p", { class: "sub" }, `A line breaks at a day that is not whole. Purple marks are releases and changes; select a day to narrow the period to it.${marks ? " Pink dots on the base line are the day's leads (forms sent and demos booked), on whole days with checked conversions only." : ""}`),
      cmp.note,
      h("div", { class: "sheet" }, legend([["Visitors", color("people")], ["Pages read", "var(--views)"], ...(marks ? [["Leads", "var(--leads)"]] : []), ...cmp.legend], true),
        lines(chartDays(r), [
          { name: "Visitors", color: color("people"), get: (d) => d.readers ?? null, area: true },
          { name: "Pages read", color: "var(--views)", get: (d) => d.views ?? null },
        ], { label: "Visitors and pages read per day", prev: cmp.prev, H: 220, marks }))));
  }

  out.push(others(t));

  const ai = {};
  for (const tier of ["asked", "training"]) for (const [k, v] of Object.entries(t.engines?.[tier] || {})) ai[k] = (ai[k] || 0) + v;
  out.push(h("div", { class: "cols tops" },
    top("Top pages", "pages read", "pages", ranked(t.pages), { drill: "path", empty: "No page read in this period." }),
    top("Top sources", "visitors, by where they came from", "sources", ranked(t.by?.source), { drill: "source", total: t.readers, empty: "Not recorded for this period." }),
    top("Countries", "visitors", "locations", ranked(t.by?.country), { drill: "country", total: t.readers, empty: "Not recorded for this period." }),
    top("AI assistants", "pages fetched, answering a question or collecting for training", "bots", ranked(ai), { drill: "bot", color: color("answer_engines"), empty: "No AI assistant came in this period." })));

  out.push(h("details", { class: "fold" }, h("summary", null, "Server requests (every file: pages, images, scripts)", h("span", null, n(t.requests ?? Object.values(t.hits || {}).reduce((a, b) => a + b, 0)))),
    serverLoad(t, r, cov)));
  if (r.kind === "history" && r.length > 1) out.push(h("details", { class: "fold" }, h("summary", null, "Each day, in numbers", h("span", null, `${cov.ok} whole of ${r.length}`)), dailyTable(r)));
  return out;
}
