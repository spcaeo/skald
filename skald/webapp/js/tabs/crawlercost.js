// What each crawler costs: per crawler, assistant or bot, the requests it
// made, the bytes the server sent it, how long the server took, how many of its
// requests failed, how many distinct paths it asked for and how often it came back
// to them. And the detail a crawler's drill-down opens: requests by day, pages it
// fetched, its status mix, the server's address check, the countries of its
// requests, the user agents it sent and when it was last seen.
//
// From crawler_cost.json, loaded when a section asks for it (it is the largest
// file beside the page). Sums over the range: costsum.js.

import { h, n, short, pct1 } from "../ui.js";
import { base, getJSON, chartDays, color, ranked } from "../data.js";
import { lines } from "../charts.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { blist, panel, fileName } from "./common.js";
import { time as tzTime } from "../tz.js";
import { verification, badge } from "./botverify.js";
import { sumCosts, detailOf, bytesWords, OTHER } from "./costsum.js";

const GROUP_WORDS = { answer_engines: "AI", search_engines: "Search", bots: "Bot" };
const ms = (v) => (v == null ? "-" : v < 10 ? `${v.toFixed(1)} ms` : `${n(v)} ms`);

// The file, or why there is none: loaded once per page (data.js caches it).
function load(m, s, holder, draw) {
  if (Array.isArray(m.files) && !m.files.includes("crawler_cost.json") && !m.files.includes("crawler_cost")) {
    holder.replaceChildren(h("p", { class: "empty" }, "What each crawler costs is not written beside this page yet. It is counted from the next collected day on."));
    return;
  }
  holder.replaceChildren(h("p", { class: "empty" }, "Loading what each crawler costs…"));
  getJSON(`${base(s.view)}crawler_cost.json`).then((f) => {
    if (!f) holder.replaceChildren(h("p", { class: "empty" }, "What each crawler costs is not written beside this page yet."));
    else if (f.state === "error") holder.replaceChildren(h("div", { class: "state warn" }, h("div", null, `crawler_cost.json could not be built on the last redraw: ${f.error || "no reason given"}.`)));
    else holder.replaceChildren(...[].concat(draw(f)).filter(Boolean));
  }).catch((e) => holder.replaceChildren(h("p", { class: "empty" }, `What each crawler costs could not be loaded: ${e.message || e}.`)));
}

const bytesCell = (x) => (x.bytes == null ? h("span", { class: "muted", title: "No request of this crawler logged a size" }, "not recorded")
  : x.partial ? h("span", { title: `Summed over the ${n(x.sized)} of its ${n(x.requests)} requests that logged a size` }, `${bytesWords(x.bytes)} (partial)`)
    : bytesWords(x.bytes));

/* The table, for the groups a tab is about. opts.keep(group, name, row)
   narrows it (one AI tier); opts.groups names the groups. */
export function costSection(m, s, r, { title = "What each crawler costs", sub, keep = () => true, id = "cost", groupCol = false } = {}) {
  const holder = h("div");
  load(m, s, holder, (f) => {
    const got = sumCosts(f, r, keep);
    const cols = [
      { key: "name", label: "Name", fmt: (v, x) => (x.folded ? h("span", { class: "muted" }, `${OTHER} (${GROUP_WORDS[x.group] || x.group})`) : link("bot", v)), csv: (x) => x.name },
      ...(groupCol ? [{ key: "group", label: "Group", fmt: (v) => GROUP_WORDS[v] || v }] : []),
      { key: "requests", label: "Requests", num: true },
      { key: "bytes", label: "Bytes sent", num: true, fmt: (_, x) => bytesCell(x), csv: (x) => (x.bytes == null ? "" : x.bytes) },
      { key: "mean_ms", label: "Mean time", num: true, fmt: (v) => ms(v), csv: (x) => (x.mean_ms == null ? "" : x.mean_ms.toFixed(1)), title: "Server time per request, weighted by request" },
      ...(got.single ? [{ key: "p90_ms", label: "p90 time", num: true, fmt: (v) => ms(v), csv: (x) => x.p90_ms ?? "", title: "9 in 10 of its timed requests took no longer" }] : []),
      { key: "error_share", label: "Errors", num: true, fmt: (v, x) => (v == null ? "-" : h("span", { title: `${n(x.errors)} of ${n(x.requests)} answered 4xx or 5xx` }, pct1(x.errors, x.requests))), csv: (x) => (x.error_share == null ? "" : x.error_share.toFixed(4)) },
      { key: "paths", label: got.single ? "Distinct paths" : "Paths (per day)", num: true, fmt: (v) => (v == null ? "-" : n(v)), title: "Distinct paths it asked for; over a range, each day's count summed" },
      { key: "recrawl", label: "Re-crawl", num: true, fmt: (v) => (v == null ? "-" : `${v.toFixed(1)}×`), csv: (x) => (x.recrawl == null ? "" : x.recrawl.toFixed(2)), title: "Requests per distinct path (within each day)" },
      { key: "last", label: "Last seen", type: "date", fmt: (v) => (v ? tzTime(v, { date: !got.single, label: false }) : "-") },
    ];
    const rows = got.rows.map((x) => ({ ...x, __k: `${x.group}|${x.name}` }));
    const bits = [];
    if (got.unrecorded) bits.push(`${got.unrecorded} day${got.unrecorded === 1 ? "" : "s"} of the range were collected before this was counted and are left out.`);
    if (rows.some((x) => x.partial)) bits.push("Bytes marked partial are summed over the requests whose log line had a size; the rest are not recorded, not zero.");
    return [
      table(cols, { caption: title, rows, file: fileName(`crawler-cost-${id}`, r), sortKey: "requests", limit: 12, empty: got.days ? "No crawler in this range." : "Not recorded for this range yet.",
        note: [r.kind === "today" || r.length === 1 ? "One day: the p90 time is that day's." : `Summed over ${got.days} whole day${got.days === 1 ? "" : "s"}: requests and bytes add up; the mean time is weighted by request; the p90 time is shown for a single day only (pick one day to see it); distinct paths are counted per day and summed.`,
          "Errors: answered 4xx or 5xx. Re-crawl: requests per distinct path. Each day keeps its 50 busiest names per group; the rest are one \"(all others)\" row.", ...bits].join(" ") }),
    ];
  });
  return h("section", { class: "s" }, h("h2", null, title), sub ? h("p", { class: "sub" }, sub) : null, holder);
}

// The drawer's width, as drillview.js draws its charts.
const chartWidth = () => (innerWidth < 640 ? innerWidth - 32 : Math.min(innerWidth * 0.8, 1360) - 56) - 30;

/* One crawler's detail, for the drill-down drawer (drillview.js). */
export function botDetail(m, s, r, name) {
  const holder = h("div");
  load(m, s, holder, (f) => {
    const d = detailOf(f, r, name);
    if (!d.days) return h("p", { class: "empty" }, "Not recorded for this range yet.");
    const one = sumCosts(f, r, (g, k) => k === name);
    const requests = one.rows.reduce((a, x) => a + x.requests, 0);
    if (!requests) return h("p", { class: "empty" }, `${name} made no request in this range (or was in a busy day's folded tail).`);
    const sized = one.rows.reduce((a, x) => a + x.sized, 0);
    const bytes = sized ? one.rows.reduce((a, x) => a + (x.bytes || 0), 0) : null;
    const timed = one.rows.reduce((a, x) => a + x.timed, 0);
    const msSum = one.rows.reduce((a, x) => a + (x.mean_ms == null ? 0 : x.mean_ms * x.timed), 0);
    const errors = one.rows.reduce((a, x) => a + x.errors, 0);
    const check = verification(m, r)?.byName?.[name];
    const checked = check ? check.verified + check.unverified : 0;
    const kpis = h("div", { class: "dd-kpis" },
      h("div", null, h("b", null, n(requests)), h("span", null, "requests")),
      h("div", null, h("b", null, bytesWords(bytes)), h("span", null, sized && sized < requests ? `bytes sent (partial: ${n(sized)} of ${n(requests)} lines had a size)` : "bytes sent")),
      h("div", null, h("b", null, ms(timed ? msSum / timed : null)), h("span", null, timed ? "mean server time" : "server time not logged")),
      h("div", null, h("b", null, pct1(errors, requests)), h("span", null, "answered 4xx or 5xx")),
      h("div", null, h("b", null, checked ? pct1(check.verified, checked) : "-"), h("span", null, checked ? "from an address checked as theirs" : "address not checked")),
      h("div", null, h("b", null, d.last ? tzTime(d.last, { date: true, label: false }) : "-"), h("span", null, "last seen")));
    const days = r.kind === "history" ? chartDays(r).map((x) => ({ ...x, v: d.perDay.has(x.day) ? d.perDay.get(x.day) : null })) : [];
    const chart = days.length > 1 ? h("div", { class: "sheet" }, lines(days, [{ name: "Requests", color: color("bots"), get: (x) => x.v ?? null, area: true }],
      { label: `${name}: requests per day`, H: 160, width: chartWidth() })) : null;
    const listNote = d.listed < d.days ? `Pages, countries and user agents: from the ${d.listed} of these ${d.days} day${d.days === 1 ? "" : "s"} within the last ${f.detail_days} days.` : null;
    return [
      kpis, chart,
      check ? h("p", { class: "sub" }, "Address check: ", badge(check), ` ${n(check.verified)} verified, ${n(check.unverified)} not verifiable${check.spoofed ? `, and ${n(check.spoofed)} more used its name from an address that is not theirs (counted as "claims to be ${name}")` : ""}.`) : null,
      h("div", { class: "cols three", style: { marginTop: "12px" } },
        panel("Pages it fetched", null, blist(ranked(d.lists.pages), { drill: "path", from: "drill", limit: 10, color: "var(--views)", empty: "Not recorded for these days." })),
        panel("Status mix", null, blist(ranked(d.status), { limit: 6, color: "var(--g-bots)" })),
        panel("Countries of its requests", "From the log's country field or the GeoIP file.", blist(ranked(d.lists.countries), { drill: "country", from: "drill", limit: 8, color: "var(--g-bots)", empty: "Not recorded for these days." }))),
      panel("User agents it sent", "The crawler's own strings, the 5 most used each day.", blist(ranked(d.lists.agents), { limit: 5, color: "var(--g-bots)",
        empty: d.agentsHidden ? "Not kept: these requests may come from a person's browser, so their strings are not stored." : "Not recorded for these days." })),
      h("p", { class: "note" }, [`From ${r.kind === "today" ? "today so far" : `${d.days} whole day${d.days === 1 ? "" : "s"}, ${short(r.first)} to ${short(r.last)}`}. No address is kept.`,
        "Each day keeps the top 10 pages and countries and the top 5 user agents, so these lists are sums of each day's top.", listNote].filter(Boolean).join(" ")),
    ];
  });
  return h("section", { class: "s" }, h("h3", null, "What it costs and what it fetched"), holder);
}
