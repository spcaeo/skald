// Page story: what happened to one page since it was published - its dates,
// the first time each kind of visitor came (a crawler, an assistant, a
// person, a lead), the days since publish, and where its readers came from.
// From GET <page>/api/page?path= (milestones kept for good, days from the
// publish date); without it, what the stored days show, said as such.
// Also the Pages filter "Published between", from page_index.json.
// Change dates: `updated` is the website's own date, else the latest <lastmod> of the
// sitemap (`updated_source` "sitemap"), said as "changed (from your sitemap)": a change
// date, never a publish date. `lastmod_seen` lists each date with the day Skald first saw it.

import { h, n, short, long, addDays, dayDiff } from "../ui.js";
import { getJSON, ranked } from "../data.js";
import { lines, legend } from "../charts.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { blist, panel, notBuiltNote } from "./common.js";
import { time as tzTime } from "../tz.js";
import { eventLabel } from "./events.js";
import { withUrl } from "../urlactions.js";
import { readyBlock } from "./aiready.js";
import { changeTracker } from "./pagechange.js";

const hasApi = (m) => Array.isArray(m.files) && m.files.includes("page_index");
const STORIES = new Map();

// ------------------------------------------------------------- the story data
function fromDays(m, path) {
  // Without the page API: the days this page holds, from the first day the page was read.
  const days = [...m.byDay.values()].sort((a, b) => (a.day < b.day ? -1 : 1));
  const firstRead = days.find((d) => d.pages?.[path]);
  const firstAi = days.find((d) => d.ai_pages?.[path]);
  const start = [firstRead?.day, firstAi?.day].filter(Boolean).sort()[0];
  if (!start) return null;
  const list = days.filter((d) => d.day >= start).map((d) => (d.state === "ok" ? { day: d.day, state: "ok", readers: d.by?.landing?.[path] ?? null, views: d.pages?.[path] || 0, ai_asked: null, ai_training: null, ai: d.ai_pages?.[path] || 0, search: null } : { day: d.day, state: d.state }));
  return { ok: true, local: true, path, title: null, published: null, updated: null, date_source: "first seen", first_seen: start, days_since_publish: null,
    milestones: { human: firstRead ? { at: firstRead.day, day: true } : null, ai_any: firstAi ? { at: firstAi.day, day: true } : null }, days: list };
}
function story(m, path) {
  if (!hasApi(m)) return Promise.resolve(fromDays(m, path));
  if (!STORIES.has(path)) STORIES.set(path, getJSON(`api/page?path=${encodeURIComponent(path)}`, true).then((r) => (r && r.ok ? r : fromDays(m, path)), () => fromDays(m, path)));
  return STORIES.get(path);
}

// -------------------------------------------------------------- the timeline
// [key, what happened, kind, what it says while it has not happened yet]
const MILESTONES = [
  ["googlebot", "Googlebot crawled it", "search", "Googlebot has not crawled it yet"], ["bingbot", "Bingbot crawled it", "search", "Bingbot has not crawled it yet"],
  ["ai_training", "crawled it to train or index", "ai", "No AI crawler has fetched it to train yet"], ["ai_asked", "fetched it to answer someone", "ai", "No assistant has fetched it for a question yet"],
  ["ai_any", "An AI assistant fetched it", "ai", "No AI assistant has fetched it yet"],
  ["human", "The first person read it", "people", "Nobody has read it yet"], ["from_search", "The first visitor from a search engine", "people", "No visitor from search yet"],
  ["from_ai", "The first visitor from an AI answer", "people", "No visitor from an AI answer yet"],
  ["lead_landed", "The first lead who had landed here", "lead", "No lead has landed here yet"], ["lead_sent", "The first lead sent from a form here", "lead", "No lead sent from a form here yet"],
];
// How long after publishing, in days: the website gives a date, not a time.
function after(at, start) {
  if (!start || !at) return "";
  const d = dayDiff(start, String(at).slice(0, 10));
  if (!Number.isFinite(d)) return "";
  return d < 0 ? "before publishing" : d === 0 ? "the same day" : d === 1 ? "the next day" : `${d} days after`;
}
// "changed 24 Oct (from your sitemap)" / "updated 24 Oct": the change date and where it comes from.
export const changedWords = (p, fmt = short) => (!p?.updated ? "" : p.updated_source === "sitemap" ? `changed ${fmt(p.updated)} (from your sitemap)` : `updated ${fmt(p.updated)}`);
// Each change date the sitemap gave, with the day Skald first saw it: timeline entries.
function changes(st) {
  return (st.lastmod_seen || []).map(([d, seen]) => ({ key: "lastmod", kind: "change", at: d, words: "Changed (from your sitemap)",
    when: `${long(d)}${seen && seen !== d ? `, in the sitemap Skald read on ${long(seen)}` : ""}` }));
}
function timeline(st) {
  const start = st.published || st.first_seen;
  const items = changes(st), missing = [];
  for (const [key, words, kind, yet] of MILESTONES) {
    const v = st.milestones?.[key];
    if (v === undefined) continue;
    const list = Array.isArray(v) ? v : v ? [v] : [];
    if (!list.length) { missing.push([yet, kind]); continue; }
    for (const e of list) items.push({ key, kind, at: e.at, day: e.day, who: e.who, words: key === "ai_training" || key === "ai_asked" ? `${e.who} ${words}` : e.who ? `${words} (${e.who})` : words });
  }
  items.sort((a, b) => (a.at < b.at ? -1 : 1));
  return h("ol", { class: "ps-line" },
    h("li", { class: "ps-i start" }, h("span", { class: "ps-dot" }), h("div", null, h("b", null, st.published ? "Published" : start ? "First seen in the logs" : "Not seen in the logs yet"), start ? h("span", { class: "ps-when" }, long(start)) : null)),
    items.map((x) => h("li", { class: `ps-i ${x.kind}` }, h("span", { class: "ps-dot" }), h("div", null, h("b", null, x.words),
      h("span", { class: "ps-when" }, x.when || (x.day ? `${long(x.at)} (the first day in the stored days)` : `${tzTime(x.at, { date: true })}, ${after(x.at, start)}`))))),
    missing.map(([yet, kind]) => h("li", { class: `ps-i ${kind} not` }, h("span", { class: "ps-dot" }), h("div", null, h("b", null, yet)))));
}

// What readers did inside the page since it was published (events.json): by kind and by which button or form.
function inside(m, path, since) {
  const f = m.x.events;
  if (!f) return null;
  const slash = (x) => x.split("?")[0].replace(/\/+$/, "") || "/";
  const here = (x) => slash(x) === slash(path);
  const ok = new Set((f.days || []).filter((d) => d.state === "ok").map((d) => d.day));
  const rows = (f.rows || []).filter((x) => ok.has(x[0]) && x[0] >= since && here(x[3])).map((x) => [x[1], x[2], x[5]]);
  if (f.today?.state === "ok") rows.push(...(f.today.rows || []).filter((x) => here(x[2])).map((x) => [x[0], x[1], x[4]]));
  const by = (key) => { const o = {}; for (const x of rows) { const k = key(x); if (k) o[k] = (o[k] || 0) + x[2]; } return o; };
  const kinds = by((x) => eventLabel(f, x[0]));
  const which = by((x) => (x[1] ? `${eventLabel(f, x[0])}: ${x[1]}` : null));
  return h("div", { class: "cols" },
    panel("What visitors did on it", `events from the beacon since ${short(since)}${f.today?.state === "ok" ? ", today included (not yet checked)" : ""}`, blist(ranked(kinds), { color: "var(--ink-3)", empty: f.first_day ? "No event on this page yet." : "The beacon has not counted any event yet." })),
    panel("Which button or form", "the buttons and forms used on it", blist(ranked(which), { color: "var(--g-people)", empty: "No button or form used on it yet." })));
}

// --------------------------------------------------------------- the page
export function pageStory(m, s) {
  const path = s.page;
  const back = h("button", { type: "button", class: "btn ps-back", onclick: () => S.set({ page: "", psec: "" }) }, "← All pages");
  const body = h("div", { class: "ps" }, h("p", { class: "empty" }, "Telling the page's story…"));
  story(m, path).then((st) => {
    if (!st) { body.replaceChildren(h("p", { class: "empty" }, `Nothing was recorded for ${path} in the stored days.`)); return; }
    const start = st.published || st.first_seen;
    const since = start ? dayDiff(start, m.anchor) + 1 : null;
    // Compare this page: A its last 7 whole days, B its first 7 after publishing (Compare mode on Pages).
    const cmp = h("button", { type: "button", class: "btn primary", onclick: () => S.set({ tab: "traffic/pages", path, pathmode: "contains", page: "",
      range: "custom", from: addDays(m.anchor, -6), to: m.anchor, cmp: "custom", cb: `${start}..${addDays(start, 6)}` }) }, "Compare this page");
    const days = (st.days || []).map((d) => ({ ...d, ai: d.ai ?? ((d.ai_asked ?? 0) + (d.ai_training ?? 0)) }));
    const ok = days.filter((d) => d.state === "ok");
    const sum = (k) => ok.reduce((a, d) => { const o = d[k]; if (o) for (const [x, v] of Object.entries(o)) a[x] = (a[x] || 0) + v; return a; }, {});
    const gaps = days.filter((d) => d.state !== "ok").map((d) => short(d.day));
    const series = [
      { name: "Visitors", color: "var(--g-people)", get: (d) => d.readers ?? null },
      { name: "Pages read", color: "var(--ink-2)", get: (d) => d.views ?? null },
      { name: "AI fetches", color: "var(--g-answer_engines)", get: (d) => d.ai ?? null },
      { name: "Search crawls", color: "var(--g-search_engines)", get: (d) => d.search ?? null },
    ].filter((x) => ok.some((d) => x.get(d) != null));
    // The chart sits in the wider of two columns (one column under 1000px): drawn at that width.
    const panelEl = document.getElementById("panel");
    const full = panelEl ? panelEl.clientWidth - parseFloat(getComputedStyle(panelEl).paddingLeft) * 2 : 900;
    const width = Math.round(innerWidth > 1000 ? ((full - 18) * 2.2) / 3.2 - 34 : full - 34);
    body.replaceChildren(...[
      h("div", { class: "ps-head" }, h("div", null, h("h2", { class: "ps-path" }, withUrl(h("span", null, path), path, { cls: "ua-after" })), st.title ? h("p", { class: "ps-title" }, st.title) : null,
        h("p", { class: "ps-meta" }, st.published ? `Published ${long(st.published)}` : st.first_seen ? `First seen ${long(st.first_seen)}; the website does not give a publish date` : "Listed in your sitemap, not seen in the logs yet",
          st.updated ? `, ${changedWords(st, long)}` : "", since ? `. Day ${since} since ${st.published ? "publishing" : "first seen"}.` : ".")), start ? cmp : null),
      st.local ? h("p", { class: "note" }, "This server does not keep page histories yet, so the story below is what the stored days show: the first day the page was read and fetched, its page views and the visitors who started on it.") : null,
      changeTracker(m, s),        // Did my change work? (pagechange.js)
      h("div", { class: "ps-grid" },
        h("section", { class: "s ps-tl" }, h("h3", null, "Firsts"), timeline(st)),
        h("section", { class: "s" }, h("h3", null, "Every day since"), series.length && ok.length > 1 ? h("div", { class: "sheet" }, legend(series.map((x) => [x.name, x.color]), true),
          lines(days, series, { label: `${path}, every day since ${st.published ? "publishing" : "first seen"}`, H: 220, width })) : h("p", { class: "empty" }, "Fewer than two whole days so far."),
          gaps.length ? h("p", { class: "note" }, `Not drawn: ${gaps.join(", ")} (not whole, verified days).`) : null)),
      // AI readiness (2.35): can AI read it well? psec=ai opens the story here.
      readyBlock(m, s, path),
      h("div", { class: "cols three" },
        panel("Where its visitors came from", "since publishing", blist(ranked(sum("sources")), { drill: "source", empty: st.local ? "Needs the server's page history." : "No visitor yet." })),
        panel("Countries", "since publishing", blist(ranked(sum("countries")), { drill: "country", empty: st.local ? "Needs the server's page history." : "No visitor yet." })),
        panel("AI assistants that sent people", "since publishing", blist(ranked(sum("assistants")), { drill: "assistant", color: "var(--g-answer_engines)", empty: st.local ? "Needs the server's page history." : "None yet." }))),
      start ? inside(m, path, start) : null].filter(Boolean));
  }).catch((e) => body.replaceChildren(h("div", { class: "state bad" }, h("div", null, `The page's story could not be loaded: ${e.message || e}.`))));
  return [h("div", { class: "head" }, h("h1", null, "Page story"), h("span", { class: "period" }, "since the page was published")), back, body];
}

// ------------------------------------------------------- published between
export function published(m, s) {
  const idx = m.x.page_index;
  if (!idx) return notBuiltNote(m, "page_index", "Pages by publish date");
  if (!idx.pages?.length) return null;
  const set = (patch) => S.set(patch, { replace: true });
  const from = h("input", { type: "date", value: s.pubfrom || "", "aria-label": "Published from", onchange: (e) => set({ pubfrom: e.target.value }) });
  const to = h("input", { type: "date", value: s.pubto || "", "aria-label": "Published to", onchange: (e) => set({ pubto: e.target.value }) });
  const month = (k) => { const d = new Date(`${m.anchor}T12:00:00Z`); d.setUTCMonth(d.getUTCMonth() - k, 1); const f = d.toISOString().slice(0, 10); d.setUTCMonth(d.getUTCMonth() + 1, 0); return [f, d.toISOString().slice(0, 10)]; };
  const quick = [["This month", month(0)], ["Last month", month(1)], ["Last 90 days", [addDays(m.anchor, -89), m.anchor]], ["Any time", ["", ""]]];
  const all = idx.pages.filter((p) => (!s.pubfrom || (p.published && p.published >= s.pubfrom)) && (!s.pubto || (p.published && p.published <= s.pubto))
    && (!s.chgfrom || (p.updated && p.updated >= s.chgfrom)));
  // A Markdown copy of a post (/blog/post.md) is not a page of its own: the copies are one row that opens to list them.
  const rows = all.filter((p) => !isCopy(p.path)), copies = all.filter((p) => isCopy(p.path));
  const rel = (at, p) => (at ? after(at, p.published || p.first_seen) || short(at.slice(0, 10)) : "not yet");
  const dated = idx.pages.some((p) => p.updated);
  const changed = dated ? h("span", { class: "ps-range" }, "Changed since", h("input", { type: "date", value: s.chgfrom || "", "aria-label": "Changed since", onchange: (e) => set({ chgfrom: e.target.value }) }),
    s.chgfrom ? h("button", { type: "button", class: "linkish", onclick: () => set({ chgfrom: "" }) }, "Any time") : null) : null;
  const file = (what) => `pages-${what}-${s.pubfrom || "any"}-to-${s.pubto || "any"}${s.chgfrom ? `-changed-since-${s.chgfrom}` : ""}.csv`;
  const lm = idx.meta?.lastmod;
  const odd = lm ? [lm.invalid ? `${n(lm.invalid)} with a date that does not parse` : "", lm.future ? `${n(lm.future)} dated in the future` : ""].filter(Boolean) : [];
  return h("section", { class: "s ps-pub" },
    h("div", { class: "card-h start" }, h("h2", null, "Pages by publish date"),
      h("span", { class: "ps-range" }, "Published between", from, "and", to),
      h("span", { class: "ps-quick" }, quick.map(([w, [f, t]]) => h("button", { type: "button", class: "linkish", onclick: () => set({ pubfrom: f, pubto: t }) }, w))), changed),
    pubTable(rows, rel, { caption: "Pages by publish date", file: file("published"), empty: s.chgfrom ? "No page in these dates changed since then." : "No page was published in these dates.", dated }),
    copies.length ? h("details", { class: "md-copies" }, h("summary", null, `.md copies (${copies.length}): Markdown versions of pages, kept for AI assistants`),
      pubTable(copies, rel, { caption: "Markdown copies by publish date", file: file("published-md-copies"), empty: "", dated })) : null,
    h("p", { class: "note" }, `Publish dates come from ${idx.meta?.source === "website" ? "the website" : "the first day the page was seen in the logs"}; * marks a page the website gives no date for.`,
      dated ? ` Changed: the website's own updated date, else the last change date your sitemap gives (its lastmod), a change date, not a publish date${lm?.day ? `; ${n(lm.dated || 0)} of the sitemap's pages had one on ${short(lm.day)}${odd.length ? ` (${odd.join(", ")}: left out)` : ""}` : ""}.` : "",
      " Select a page for its story."));
}

export const isCopy = (path) => /\.md\/?$/i.test(path || "");

function pubTable(rows, rel, { caption, file, empty, dated }) {
  return table([
    { key: "path", label: "Page", path: true, fmt: (v, p) => h("span", null, v, p.title ? h("small", { class: "ps-t" }, p.title) : null) },
    { key: "published", label: "Published", type: "date", fmt: (v, p) => (v ? short(v) : p.first_seen ? h("span", { class: "muted", title: "The website gives no date; first seen" }, `${short(p.first_seen)}*`) : h("span", { class: "muted", title: "Listed in your sitemap; no request for it in the logs yet" }, "not seen yet")), sort: (p) => p.published || p.first_seen || "" },
    ...(dated ? [{ key: "updated", label: "Changed", type: "date", sort: (p) => p.updated || "",
      fmt: (v, p) => (!v ? h("span", { class: "muted" }, "no date") : p.updated_source === "sitemap" ? h("span", { title: "From your sitemap (lastmod): a change date, not a publish date" }, short(v), h("small", { class: "ps-t" }, "from your sitemap")) : h("span", { title: "From the website's own page list" }, short(v))),
      csv: (p) => (p.updated ? `${p.updated}${p.updated_source === "sitemap" ? " (sitemap)" : ""}` : "") }] : []),
    { key: "days_since_publish", label: "Days since", num: true },
    { key: "views_7d", label: "Views, 7 days", num: true },
    { key: "views_30d", label: "Views, 30 days", num: true },
    { key: "readers_30d", label: "Visitors, 30 days", num: true },
    { key: "g", label: "First Google crawl", type: "date", sort: (p) => p.milestones?.googlebot || "~", fmt: (_, p) => rel(p.milestones?.googlebot, p), csv: (p) => p.milestones?.googlebot || "" },
    { key: "hu", label: "First visitor", type: "date", sort: (p) => p.milestones?.human || "~", fmt: (_, p) => rel(p.milestones?.human, p), csv: (p) => p.milestones?.human || "" },
  ], { caption, rows, file, sortKey: "published", dir: -1, limit: 15,
    rowClass: () => "go", onRow: (p) => S.set({ page: p.path }), empty });
}
