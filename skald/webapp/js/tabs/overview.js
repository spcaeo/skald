// Overview: people first. One period rules the page - the date range, page
// group and filters above - and every figure here follows it: today so far,
// or the whole verified days of the range, never a mix.
//
//   1. seven tiles: visitors, pages read, leads, visitors from AI, demos
//      booked, returning visitors, pages per visit - each with its trend and
//      its change (leads and demos from conversions.json's checked days)
//   2. one line on how they relate to the files the server sent
//   3. the main chart: visitors and pages, by hour today, by day otherwise
//   4. who else came (machines, each in its own unit)
//   5. top pages, sources, countries and AI assistants
//   6. collapsed: server load (requests) and each day's figures

import { h, n, change, short, long } from "../ui.js";
import { GROUPS, color, figures, previousOf, total, coverage, chartDays, ranked } from "../data.js";
import { lines, spark, legend, bars } from "../charts.js";
import { table } from "../table.js";
import { open as openDrill } from "../drill.js";
import { head, nothing, fileName, compareFor } from "./common.js";
import { info, others, top } from "./tiles.js";
import { serverLoad, LOAD_NAMES } from "./load.js";
import { hourLabels, label as tzLabel } from "../tz.js";
import { convFile, convDay, dayLeads, leadsOn, LEAD_WORDS } from "./leadfigs.js";
import * as S from "../state.js";

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

/* The six measures: [key, label, what it counts (the ⓘ), value from a total
   or a day]. A value the period cannot give honestly is null, shown "-". */
const TILES = [
  ["visitors", "Visitors", "Visits that read at least one page, counted only when the browser loaded the page's scripts and styles, so automated programs are left out. One person on two devices is two visitors.", (t) => (t.unmeasured?.readers ? null : t.readers ?? null)],
  ["pages", "Pages read", "Page views by visitors. Images, scripts and data the page loads are not pages.", (t) => t.views ?? null],
  ["leads", "Leads", "Sign-ups, contact forms and early-access requests from the website's lead store, spam and duplicates removed.", null],
  ["ai", "Visitors from AI", "Visitors who arrived by following a link in an AI assistant's answer. Counted once per visitor; the true number is higher, as many assistants hide the link they came from.", (t) => t.cited ?? null],
  ["demos", "Demos booked", "Demo bookings completed, from every booking road: the booking tool's webhook, the script tag and the lead database. Part of the leads.", null],
  ["returning", "Returning visitors", "Visitors seen on an earlier day in the 30 days before.", (t) => (t.unmeasured?.returning || !t.returning ? null : t.returning.returning)],
  ["ppv", "Pages per visit", "Pages read divided by visitors.", (t) => (t.readers && t.views != null && !t.unmeasured?.readers ? t.views / t.readers : null)],
];

/* Leads and demos booked from conversions.json: summed over the range's
   checked days; a change only when both periods are whole in the log and
   every day of both is checked in conversions. null without the file. */
function leadFigures(m, r, both) {
  if (!convFile(m)) return null;
  const now = leadsOn(m, r.kind === "today" ? [m.today] : r.days.map((d) => d.day));
  const before = r.kind === "history" ? leadsOn(m, previousOf(m, r).days.map((d) => d.day)) : null;
  const whole = both && now.whole && before?.whole;
  const cover = now.ok === now.of ? "" : ` Covers ${now.ok} of the ${now.of} days: the others are ${now.held.length ? "withheld or " : ""}not recorded, never zero.`;
  return { now, before: whole ? before : null, cover,
    why: !both ? null : "Not compared: not every day of both periods has checked conversions." };
}

/* Which count a lead tile is, and where the same figure is listed: Leads & sales ›
   Summary counts from the lead database unless told otherwise, so the link opens it on
   the tools when the tile counts from them (the same days, the same figure). */
function leadSource(s, key, tools) {
  const to = key === "demos" ? { tab: "sales/bookings", lsrc: "" } : { tab: "sales/summary", lsrc: tools ? "all" : "" };
  const words = key === "demos" ? "From the booking tools" : tools ? "From the tools" : "From the lead database";
  return h("a", { class: "t-src", href: S.hashFor({ ...s, ...to, dd: "" }), title: key === "demos" ? "The same count as Leads & sales › Calendar bookings"
    : `The same count as Leads & sales › Summary, counted from ${tools ? "the tools" : "the lead database"}` }, `${words} · ${key === "demos" ? "Calendar bookings" : "Summary"} ›`);
}

function tiles(m, r, t, prevT, both, why, s) {
  const days = r.kind === "history" ? chartDays(r) : [];
  const dayList = r.kind === "today" ? [m.today] : r.days.filter((d) => d.state === "ok").map((d) => d.day);
  const prevDays = both ? previousOf(m, r).days.map((d) => d.day) : [];
  const lf = leadFigures(m, r, both);
  const conv = convFile(m);
  const LEADS_NOTE = `${LEAD_WORDS} From the Conversions data: the script tag, the tools' webhooks and the lead database.`;
  const shown = TILES.filter(([key]) => key !== "demos" || lf);
  return h("div", { class: "tiles", role: "list" }, shown.map(([key, label, baseNote, get]) => {
    const lead = (key === "leads" || key === "demos") && lf;
    const pick = (x) => (x == null ? null : key === "demos" ? x.demos : x.leads);
    const note = lead ? `${key === "leads" ? LEADS_NOTE : baseNote}${lf.cover}` : baseNote;
    const v = lead ? (lf.now.ok ? pick(lf.now) : null) : key === "leads" ? leadsOver(m, dayList) : get(t);
    const p = !both ? null : lead ? pick(lf.before) : key === "leads" ? leadsOver(m, prevDays) : get(prevT);
    const whyHere = lead && both && p == null && v != null ? lf.why : why;
    const fmt = (x) => (x == null ? "-" : key === "ppv" ? x.toFixed(1) : n(x));
    let chg;
    if (r.kind === "today" || !both || v == null || p == null) {
      const reason = v == null && lead && lf.now.held.length ? "Withheld: the second count disagrees with these days' conversions, so none is shown." : r.kind === "today" ? "Today is still running; it is compared once it is a whole day." : v == null ? "Not counted for this period." : whyHere;
      chg = h("span", { class: "t-c none", title: reason }, h("span", { "aria-hidden": "true" }, "—"), h("span", { class: "vh" }, `No change shown: ${reason}`));
    } else {
      const [arrow, words] = change(v, p);
      chg = h("span", { class: "t-c" }, arrow ? h("span", { class: "arrow", "aria-hidden": "true" }, arrow) : null, words, h("span", { class: "was" }, `from ${fmt(p)}`));
    }
    let trend = null;
    if (days.length > 1 && lead) trend = spark(days.map((d) => pick(dayLeads(conv, convDay(conv, d.day)))), "var(--leads)");
    else if (days.length > 1 && key !== "leads" && key !== "demos") trend = spark(days.map((d) => (d.state === "ok" ? get(d) : null)), key === "ai" ? color("answer_engines") : color("people"));
    else if (r.kind === "today" && key === "visitors" && t.by?.hour) trend = spark(HOURS.map((hh) => t.by.hour[hh] ?? 0).slice(0, Number(String(m.live?.generated_at || "").slice(11, 13)) + 1), color("people"));
    return h("div", { class: "tile", role: "listitem" },
      h("div", { class: "t-top" }, h("span", { class: "t-l" }, label), info(note, label)),
      h("div", { class: "t-v", title: v == null && lead ? (lf.now.held.length ? "Withheld, never zero" : "Not recorded, never zero") : null }, fmt(v)), chg,
      key === "leads" || key === "demos" ? leadSource(s, key, !!lf) : null, trend || h("div", { class: "spark" }));
  }));
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
  const prev = previousOf(m, r);
  const pcov = prev ? coverage(prev) : null;
  const prevT = prev ? total(prev.days) : null;
  const both = !!(prev && cov.complete && pcov.complete && prevT);
  const why = !cov?.complete ? "Not every day of this period is whole, so it is not compared."
    : `The ${r.length} days before (${prev ? `${short(prev.first)} to ${short(prev.last)}` : ""}) are not all recorded, so there is nothing whole to compare with.`;
  const cmp = compareFor(m, s);

  out.push(tiles(m, r, t, prevT, both, why, s));
  if (t.readers != null && t.views != null) {
    out.push(h("p", { class: "relate" }, `${n(t.readers)} visitor${t.readers === 1 ? "" : "s"} read ${n(t.views)} page${t.views === 1 ? "" : "s"}, which took ${n(t.hits?.people ?? 0)} requests to the server (pages, images, scripts and styles).`,
      both ? h("span", { class: "muted" }, ` Changes are against ${short(prev.first)} to ${short(prev.last)}.`) : null));
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
