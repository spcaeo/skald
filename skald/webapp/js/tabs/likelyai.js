// "Likely sent by an AI assistant": an inferred figure, never a count. A
// direct, untagged visit that landed on a page an assistant's user fetcher
// (ChatGPT-User, Perplexity-User, Claude-User...) fetched just before is
// likely the click from that answer (ai_likely.py). Shown apart from the
// real AI source everywhere, always as "likely" with an (i) saying how.
// The parts here are shared by Sources, Bots and AI crawlers, Leads,
// Conversions and the visitor drawer.

import { h, n, pct1 } from "../ui.js";

const MIN_SHARE = 10;   // a share of fewer than this many is not given, only the counts
import { table } from "../table.js";
import { panel, blist } from "./common.js";
import { info } from "./tiles.js";
import { ASSISTANTS } from "../labels.js";

export const MANY = "(more than one)";
const LABEL = { ...ASSISTANTS, [MANY]: "More than one",
  "(none)": "None", "(not recorded)": "Not recorded", Unknown: "Not recorded" };
export const aiLabel = (name) => LABEL[name] || name;
const ASSISTANT = (k) => !["(none)", "(not recorded)", "Unknown"].includes(k);

// The method in one sentence, with the window the file says it used.
export function method(f, windows) {
  const w = windows && windows.size === 1 ? [...windows][0] : f?.likely_ai?.window_minutes ?? 15;
  const base = f?.likely_ai?.method || `Inferred, not counted: a visit with no referrer and no campaign tag that landed on a page an AI assistant's user fetcher (ChatGPT-User, Perplexity-User, Claude-User, ...) had fetched in the same minute or up to ${w} minutes before. Likely, never certain.`;
  const mixed = windows && windows.size > 1 ? ` The days in this range used different windows (${[...windows].sort((a, b) => a - b).join(", ")} minutes).` : "";
  return base + mixed;
}

// The range's ai_likely day blobs from ai_activity.json: verified days only (or today).
export function likelyDays(m, r) {
  const f = m.x?.ai_activity;
  if (!f) return { f: null, blobs: [], days: 0 };
  const days = r.kind === "today" ? (f.today ? [f.today] : [])
    : (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  return { f, blobs: days.map((d) => d.ai_likely).filter(Boolean), days: days.length };
}

const addTo = (into, obj) => { for (const [k, v] of Object.entries(obj || {})) into[k] = (into[k] || 0) + v; };
export function sumLikely(blobs) {
  // reads, readsFollowed: only when every day kept them (ai_reads.py), else null.
  const t = { likely: 0, direct: 0, visits: 0, by: {}, pages: {}, fetches: {}, followed: {}, windows: new Set(),
    reads: blobs.length && blobs.every((b) => b.reads) ? {} : null, readsFollowed: {} };
  for (const b of blobs) {
    t.likely += b.likely || 0; t.direct += b.direct || 0; t.visits += b.visits || 0;
    addTo(t.by, b.by_assistant); addTo(t.pages, b.pages); addTo(t.fetches, b.fetches); addTo(t.followed, b.followed);
    if (t.reads) { addTo(t.reads, b.reads); addTo(t.readsFollowed, b.reads_followed); }
    if (b.window_minutes != null) t.windows.add(b.window_minutes);
  }
  return t;
}

const rankedOf = (obj) => Object.entries(obj).filter(([, v]) => v).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
const head3 = (title, text) => h("h3", null, title, " ", info(text, title));
const off = (f) => f?.likely_ai && f.likely_ai.on === false;

// Sources: beside "AI assistants that sent visitors", never added to it.
export function sourcesPanel(m, r) {
  const { f, blobs, days } = likelyDays(m, r);
  const t = sumLikely(blobs);
  const text = method(f, t.windows);
  const box = h("div", { class: "sheet" }, head3("Likely from AI assistants (inferred)", text),
    h("p", { class: "sub" }, "Direct visits that probably came from an AI answer. An estimate, kept apart from the counted AI source."));
  if (off(f)) { box.append(h("p", { class: "empty" }, "Turned off (attribution.ai_likely).")); return box; }
  if (!blobs.length) { box.append(h("p", { class: "empty" }, "Not recorded for this range: it is counted from this release on.")); return box; }
  box.append(blist(rankedOf(t.by), { label: aiLabel, color: "var(--g-answer_engines)", total: t.likely, empty: "No direct visit followed an assistant's fetch of its page in this range." }),
    h("p", { class: "note" }, `${n(t.likely)} likely of ${n(t.direct)} direct, untagged visits${t.direct >= MIN_SHARE ? ` (${pct1(t.likely, t.direct)} of them)` : ""}${blobs.length < days ? `, over ${n(blobs.length)} of ${n(days)} recorded days` : ""}. ${text}`));
  return box;
}

// Bots and AI crawlers: how often an assistant's fetch was followed by a likely visit.
export function followedSection(m, r) {
  const { f, blobs } = likelyDays(m, r);
  if (!blobs.length || off(f)) return null;
  const t = sumLikely(blobs);
  // Reads, not requests, once every day of the range kept them: a page asked for again in a
  // few seconds, or its CSS and JS, is no second chance to be followed (ai_reads.py).
  const byReads = !!t.reads;
  const rows = Object.keys(t.fetches).map((k) => ({ k, fetches: (byReads ? t.reads[k] : t.fetches[k]) || 0, followed: (byReads ? t.readsFollowed[k] : t.followed[k]) || 0 }));
  const unit = byReads ? "read" : "request";
  const text = `${method(f, t.windows)} A ${unit} counts as followed when a direct, untagged visit landed on the same page within the window after it; a visit two assistants fetched for follows one of each.${byReads ? " A read is one assistant reading one page: its repeat requests within 30 seconds and the page's own files are not counted again." : " Requests, not reads: these days were counted before reads were."}`;
  return h("section", { class: "s" }, h("h2", null, `${byReads ? "Reads" : "Requests"} followed by a visit (likely) `, info(text, "Followed by a visit")),
    h("p", { class: "sub" }, `Of each assistant's ${unit}s for someone's question, how many were likely followed by that person's click. Inferred, never certain.`),
    table([{ key: "k", label: "Assistant", fmt: aiLabel, csv: (x) => aiLabel(x.k) }, { key: "fetches", label: byReads ? "Reads for a question" : "Requests for a question", num: true },
      { key: "followed", label: "Likely followed by a visit", num: true },
      { key: "share", label: "Share (likely)", num: true, sort: (x) => (x.fetches >= MIN_SHARE ? x.followed / x.fetches : null), fmt: (_, x) => (x.fetches >= MIN_SHARE ? pct1(x.followed, x.fetches) : h("span", { class: "few" }, `too few (${n(x.fetches)})`)), csv: (x) => (x.fetches >= MIN_SHARE ? (x.followed / x.fetches).toFixed(4) : "") }],
    { caption: "AI fetches likely followed by a visit", rows, file: `ai-fetches-followed-${r.first}-to-${r.last}.csv`, search: false, sortKey: "fetches", empty: "No assistant fetched a page for a question in this range." }));
}

// Leads: first and last touch by their likely assistant (attribution_rows' likely_ai column).
export function leadsLikely(rows, at, f) {
  if (at.likely_ai == null) return null;
  const first = {}, last = {};
  for (const x of rows) addTo(x[at.touch] === "last" ? last : first, { [x[at.likely_ai]]: x[at.n] });
  const keys = [...new Set([...Object.keys(first), ...Object.keys(last)])].filter(ASSISTANT);
  const unknown = [first["(not recorded)"] || 0, last["(not recorded)"] || 0];
  const text = `${method(f)} For a lead: its first or last touch had no referrer and no campaign tag, and an assistant fetched that touch's landing page in the window before the touch's time.`;
  return h("div", { class: "sheet" }, head3("Likely AI (inferred)", text),
    keys.length ? table([{ key: "k", label: "Likely assistant", fmt: aiLabel, csv: (x) => aiLabel(x.k) }, { key: "first", label: "First touch", num: true }, { key: "last", label: "Last touch", num: true }],
      { caption: "Leads likely sent by an AI assistant (inferred)", rows: keys.map((k) => ({ k, first: first[k] || 0, last: last[k] || 0 })), file: "leads-likely-ai.csv", search: false, limit: 8 })
      : h("p", { class: "empty" }, "No direct lead touch followed an assistant's fetch of its landing page."),
    h("p", { class: "note" }, `Likely, not counted in the AI assistant source.${unknown[0] || unknown[1] ? ` Not recorded (the fetches of that time were not kept): ${n(unknown[0])} first touch, ${n(unknown[1])} last touch.` : ""}`));
}

// Conversions: completed ones by the likely assistant of their direct first touch.
export function conversionsLikely(days, acts, f) {
  const got = days.filter((d) => d.likely_ai);
  if (!got.length) return null;
  const all = {};
  for (const d of got) for (const a of acts) addTo(all, d.likely_ai[a]);
  const keys = Object.keys(all).filter(ASSISTANT);
  const text = `${method(f)} For a conversion: its first touch was Direct (no referrer, no utm_source or utm_medium, no ad click id), and an assistant fetched its landing page in the window before it.`;
  return h("section", { class: "s" }, h("h2", null, "Likely from AI assistants (inferred) ", info(text, "Likely from AI assistants")),
    keys.length ? h("div", { class: "sheet" }, table([{ key: "k", label: "Likely assistant", fmt: aiLabel, csv: (x) => aiLabel(x.k) }, { key: "all", label: "Completed", num: true }],
      { caption: "Completed conversions likely sent by an AI assistant (inferred)", rows: keys.map((k) => ({ k, all: all[k] })), file: "conversions-likely-ai.csv", search: false, limit: 8 }))
      : h("p", { class: "empty" }, "No completed conversion's direct first touch followed an assistant's fetch of its page in this range."),
    h("p", { class: "note" }, `Likely, never certain, and not part of the sources above.${all.Unknown ? ` ${n(all.Unknown)} not recorded (no first touch, or the fetches of that time were not kept).` : ""}`));
}

// ------------------------------------------- what the AI read before (ai_read.py)
const bare = (p) => (String(p || "").split(/[?#]/)[0].slice(0, 70).replace(/\/+$/, "") || "/");
const READ_NOTE = "The pages the assistant's user fetcher (ChatGPT-User, Perplexity-User, Claude-User, ...) fetched in the window before this visit's first request: likely what it read to write the answer. Training crawlers are never listed. Context, not people: a fetch can be for someone else. At most 10 pages are kept a visit.";

// The visit drawer: "Fetched by ChatGPT in the 15 minutes before", nearest first.
export function visitRead(j) {
  const a = j?.ai_read;
  if (!a || !(a.paths || []).length) return null;
  const many = (a.names || []).length > 1;
  const who = many ? a.names.map(aiLabel).join(" and ") : aiLabel(a.name);
  const landing = bare(j.trail?.find((p) => p.page)?.path ?? j.trail?.[0]?.path);
  const how = a.how === "cited" ? `This visit followed a link in a ${who} answer.` : `This visit is likely from ${who} (inferred).`;
  return h("section", null, h("h3", null, "What the AI read before this visit ", info(READ_NOTE, "What the AI read before this visit")),
    h("p", { class: "note" }, `Fetched by ${who} in the ${a.window_minutes} minutes before. ${how}`),
    h("ol", { class: "vj-steps ai-read" }, a.paths.map(([path, by, min]) => h("li", null,
      h("span", { class: "vj-at" }, min ? `${min} min before` : "same minute"),
      h("span", { class: "vj-p" }, h("span", { class: "vj-path" }, path),
        many ? h("small", null, aiLabel(by)) : null,
        bare(path) === landing ? h("small", null, "the page this visit landed on") : null)))),
    a.more ? h("p", { class: "note" }, `And ${n(a.more)} more page${a.more === 1 ? "" : "s"}, not kept.`) : null);
}

// AI assistants: per assistant, visits from its answers whose landing page it had just fetched.
export function readSection(m, r) {
  const f = m.x?.ai_activity;
  if (!f || off(f)) return null;
  const days = r.kind === "today" ? (f.today ? [f.today] : [])
    : (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  const blobs = days.map((d) => d.ai_read).filter(Boolean);
  if (!blobs.length) return null;
  const by = {}, windows = new Set();
  for (const b of blobs) {
    if (b.window_minutes != null) windows.add(b.window_minutes);
    for (const [k, v] of Object.entries(b.by_assistant || {})) addTo(by[k] = by[k] || {}, v);
  }
  const w = windows.size === 1 ? `${[...windows][0]} minutes` : "window";
  const rows = Object.entries(by).map(([k, v]) => ({ k, cited: v.cited || 0, fetched: v.fetched || 0, same: v.same_page || 0, likely: v.likely || 0 }));
  const text = `For each visit that followed an assistant's citation, Skald looks at what that assistant's user fetcher fetched in the ${w} before the visit. "Landed on a page it fetched": the visit's landing page was one of them (fetch → visit to the same page). Likely visits always land on a page the assistant fetched: that is how they are inferred, so they are shown apart. Visits, never people. Assistants with no known user fetcher (You.com, Phind, Poe) are not in this table.`;
  return h("section", { class: "s" }, h("h2", null, "What the AI read before it sent a visitor ", info(text, "What the AI read before it sent a visitor")),
    h("p", { class: "sub" }, `Visits from each assistant's answers, and how many landed on a page its user fetcher fetched in the ${w} before.${blobs.length < days.length ? ` Over ${n(blobs.length)} of ${n(days.length)} days: the others were not recorded.` : ""} Open a visit on Traffic > Visitors to see the pages.`),
    table([{ key: "k", label: "Assistant", fmt: aiLabel, csv: (x) => aiLabel(x.k) },
      { key: "cited", label: "Visits from its answers", num: true },
      { key: "fetched", label: "It fetched pages first", num: true },
      { key: "same", label: "Landed on a page it fetched", num: true },
      { key: "likely", label: "Likely visits (inferred)", num: true }],
    { caption: "What the AI read before it sent a visitor", rows, file: `ai-read-before-${r.first}-to-${r.last}.csv`, search: false, sortKey: "cited", empty: "No visit from an assistant with a user fetcher in this range." }));
}

// The visitor drawer's line: "Likely from ChatGPT (inferred: it fetched this page 2 min before)".
export function visitLikely(j) {
  const l = j?.likely_ai;
  if (!l) return "";
  const who = l.name === MANY ? (l.names || []).map(aiLabel).join(" and ") || "more than one assistant" : aiLabel(l.name);
  const fetched = l.name === MANY ? "they fetched" : "it fetched";
  const when = l.minutes ? `${l.minutes} min before` : "in the same minute";
  return h("span", null, `Likely from ${who} (inferred: ${fetched} this page ${when}) `,
    info("This visit came with no referrer and no campaign tag, and an AI assistant's user fetcher fetched the page it landed on just before. So it was likely a click from that assistant's answer. Likely, never certain.", "Likely from an AI assistant"));
}
