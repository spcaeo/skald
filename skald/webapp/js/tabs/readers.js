// Sources, Pages and Audience: the readers broken down one label at a time.
// Each breakdown adds up to the readers exactly (verify withholds a day where
// one does not), and each is stored on its own, so a filter narrows the list
// it belongs to and is never crossed with another.

import { h, n, change, pct1 } from "../ui.js";
import { color, figures, pathMatch, ranked, previousOf, total, coverage, chartDays } from "../data.js";
import { spark } from "../charts.js";
import { table } from "../table.js";
import { head, nothing, coverageNote, blist, panel, countTable, fileName, fixed } from "./common.js";
import { aiFeed } from "./aifeed.js";
import { campaigns } from "./campaigns.js";
import { leaderboard } from "./pagedetail.js";
import { pageStory, published } from "./pagestory.js";
import { link } from "../drill.js";
import { sourcesPanel } from "./likelyai.js";

let regions = null;
export function country(code) {
  if (!code || code === "Unknown") return "Unknown";
  try { regions ||= new Intl.DisplayNames(["en"], { type: "region" }); return regions.of(code) || code; } catch { return code; }
}
/* The one flag helper: the emoji flag for a two-letter country code, or ""
   for anything else (Unknown, "-", a folded tail, and the codes ISO keeps
   for private use: AA, QM-QZ, XA-XZ but XK Kosovo, ZZ; and AP, an old
   "Asia/Pacific"). The text beside it stays, so the flag is decoration:
   flagEl marks it aria-hidden, withFlag is for plain text (a select's
   option, a title, a sentence). */
export function flag(code) {
  if (!/^[A-Z]{2}$/.test(code || "") || /^(AA|AP|Q[M-Z]|X[A-JL-Z]|ZZ)$/.test(code)) return "";
  return String.fromCodePoint(...[...code].map((c) => 0x1f1a5 + c.charCodeAt(0)));
}
export function flagEl(code) {
  const f = flag(code);
  return f ? h("span", { class: "flag", "aria-hidden": "true" }, f) : null;
}
export const withFlag = (code, text = code) => { const f = flag(code); return f ? `${f} ${text ?? ""}` : String(text ?? ""); };

// Change per row against the previous range, only when both ranges are complete.
function changes(m, r, cov, t, dim) {
  const prev = previousOf(m, r);
  if (!prev || !cov?.complete || !coverage(prev).complete) return null;
  const p = total(prev.days);
  if (!p || p.unmeasured?.by) return null;
  return (k) => { const [a, w] = change(t.by?.[dim]?.[k] || 0, p.by?.[dim]?.[k] || 0); return `${a}${a ? " " : ""}${w}`; };
}

// Each source type's readers per day, its change and a working/dropped/new chip.
function trendTable(m, r, cov, t) {
  const prev = previousOf(m, r);
  const complete = prev && cov?.complete && coverage(prev).complete;
  const p = complete ? total(prev.days) : null;
  const days = r.kind === "history" ? chartDays(r) : [];
  const rows = ranked(t.by.source).map(([k, v]) => {
    const before = p && !p.unmeasured?.by ? p.by?.source?.[k] || 0 : null;
    let chip = "";
    if (before === 0 && v > 0) chip = "new";
    else if (before != null && before > 0) {
      const pc = (v - before) / before;
      chip = pc >= 0.2 ? "working" : pc <= -0.2 ? "dropped" : "";
    }
    return { k, v, before, chip, trend: days.map((d) => (d.state === "ok" && d.by ? d.by.source?.[k] || 0 : null)) };
  });
  const cols = [
    { key: "k", label: "Source", drill: "source" },
    { key: "v", label: "Visitors", num: true },
    { key: "before", label: "Before", num: true },
    { key: "chg", label: "Change", num: true, sort: (row) => (row.before ? (row.v - row.before) / row.before : null),
      fmt: (_, row) => { const [a, w] = change(row.v, row.before); return `${a}${a ? " " : ""}${w}`; }, csv: (row) => change(row.v, row.before)[1] },
    { key: "chip", label: "", fmt: (v) => (v ? h("span", { class: `trend-chip ${v}` }, v) : ""), csv: (row) => row.chip },
    { key: "trend", label: "Per day", fmt: (v) => (v.filter((x) => x != null).length > 1 ? spark(v, color("people")) : "-"), csv: (row) => row.trend.join(" ") },
  ];
  return table(cols, { caption: "Sources over time", rows, file: fileName("sources-trend", r), search: false, sortKey: "v" });
}

function unmeasured(t) {
  return t.unmeasured?.by ? h("p", { class: "note" }, `${t.unmeasured.by} of these days were collected before breakdowns existed. They are left out of every list here, so the lists add up to fewer visitors than the headline.`) : null;
}

function only(value) { return value ? (k) => k === value : () => true; }

export function sources(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Sources", r, "Where visitors came from, by the referrer of the first page they read. Referrers are often stripped, so Direct includes everyone whose browser did not say.")];
  if (!t || !t.by) return [...out, nothing(m, r, "sources")];
  const ch = changes(m, r, cov, t, "source");
  const keep = pathMatch(s);
  out.push(h("div", { class: "cols" },
    panel("Traffic sources", ch ? "Visitors, with the change against the range before" : "Visitors by kind of source",
      blist(ranked(t.by.source, only(s.source)), { drill: "source", total: t.readers, limit: 12, change: ch, empty: s.source ? `No visitor came from ${s.source} in this range.` : "No visitor recorded." })),
    panel("AI assistants that sent visitors", "Visitors who followed a citation, by assistant. Counted once per visitor; undercounts.",
      blist(ranked(t.cited_by), { drill: "assistant", color: color("answer_engines"), empty: "Nobody arrived by following an AI citation in this range." }),
      h("p", { class: "note" }, "Google AI Overview clicks look exactly like ordinary Google clicks and are counted as search.")),
    sourcesPanel(m, r)));
  out.push(h("div", { class: "cols" },
    panel("Referring sites", "The first page's referrer, host only", blist(ranked(t.by.referrer), { drill: "referrer", limit: 12, color: "var(--views)", empty: "No referring site recorded." })),
    panel("Campaigns", "utm_ tags or an ad click id on the landing address", blist(ranked(t.by.campaign), { drill: "campaign", limit: 12, color: "var(--g-bots)", empty: "No tagged link was followed in this range." }))));
  out.push(h("section", { class: "s" }, h("h2", null, "Each source over time"),
    h("p", { class: "sub" }, "Working, dropped and new compare this range with the one before it, only when both are fully verified; a change under 20% is not called either way."),
    trendTable(m, r, cov, t)));
  out.push(h("section", { class: "s" }, h("h2", null, "Campaigns and referrers"), campaigns(m, s, r)));
  out.push(h("section", { class: "s" }, h("h2", null, "Landing pages of these visitors"),
    h("p", { class: "sub" }, "Sources and landing pages are stored apart, so this list is every visitor's landing page, whatever the source filter."),
    countTable(t.by.landing, { caption: "Landing pages", file: fileName("landing", r), key: "Page", value: "Visitors", keep, path: true, total: t.readers, drill: "landing" })));
  out.push(h("div", { class: "cols" },
    h("section", { class: "s" }, h("h2", null, "All sources"), countTable(t.by.source, { caption: "Traffic sources", file: fileName("sources", r), key: "Source", value: "Visitors", keep: only(s.source), total: t.readers, drill: "source" })),
    h("section", { class: "s" }, h("h2", null, "All referring sites"), countTable(t.by.referrer, { caption: "Referring sites", file: fileName("referrers", r), key: "Site", value: "Visitors", drill: "referrer" }))));
  out.push(unmeasured(t), coverageNote(cov, r));
  return out;
}

export function pages(m, s) {
  // One page selected: its story since publishing.
  if (s.page) return pageStory(m, s);
  const { r, t, cov } = figures(m, s);
  const out = [...head("Pages", r, "What people read, where they started, what AI assistants fetched and the pages that were not there. Select a page for its story since it was published.")];
  out.push(published(m, s));
  if (!t) return [...out, nothing(m, r, "pages")];
  const keep = pathMatch(s);
  if (m.x.pages) {
    // The leaderboard keeps its own last 30 whole days (with change against the 30 before); today's follows the range.
    if (r.kind === "today") out.push(h("section", { class: "s" }, h("h2", null, "Page leaderboard"), leaderboard(m, s, r)));
    else out.push(fixed("Page leaderboard, with change and each page's detail", m.x.pages.period?.first ? `${m.x.pages.period.first} to ${m.x.pages.period.last}` : "last 30 whole days", leaderboard(m, s, r)));
  }
  const sub = s.path ? ` whose path ${s.pathmode === "starts" ? "starts with" : "contains"} ${s.path}` : "";
  out.push(h("div", { class: "cols" },
    panel("Most read", `Page views by people${sub}`, blist(ranked(t.pages, keep), { drill: "path", limit: 12, empty: "No page matches." })),
    panel("Where visitors started", `Landing pages${sub}`, blist(ranked(t.by?.landing, keep), { drill: "landing", limit: 12, color: "var(--views)", total: t.readers, empty: t.by ? "No page matches." : "Not recorded for this range." }))));
  out.push(h("section", { class: "s" }, h("h2", null, "Pages read by people"),
    countTable(t.pages, { caption: "Pages read by people", file: fileName("pages", r), key: "Page", value: "Page views", keep, path: true, limit: 15, drill: "path" }),
    r.kind === "history" && r.length > 1 ? h("p", { class: "note" }, "Each day keeps its top 50 pages, so over several days the long tail is undercounted.") : null));
  out.push(h("div", { class: "cols" },
    h("section", { class: "s" }, h("h2", null, "Pages AI assistants fetched"),
      countTable(t.ai_pages, { caption: "Pages AI assistants fetched", file: fileName("ai-pages", r), key: "Page", value: "Fetches", keep, path: true, empty: "No answer-engine fetches.", drill: "path" })),
    h("section", { class: "s" }, h("h2", null, "Page not found, seen by people"),
      countTable(t.not_found, { caption: "404s seen by people", file: fileName("not-found", r), key: "Page", value: "404s", keep, path: true, drill: "path", empty: t.statuses ? "No person met a missing page." : "Not recorded for this range." }))));
  out.push(coverageNote(cov, r));
  return out;
}

export function audience(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Audience", r, "Visitors by country, device, browser and system, each counted once, at their first page. Browser, system and device are what the browser says about itself.")];
  if (!t || !t.by) return [...out, nothing(m, r, "breakdowns")];
  const credit = m.credit ? h("p", { class: "note" }, h("a", { href: m.credit.url || null, rel: "noreferrer" }, m.credit.text)) : null;
  out.push(h("div", { class: "cols" },
    panel("Countries", "From the log's country field; Unknown when it had none, never guessed",
      blist(ranked(t.by.country, only(s.country)), { drill: "country", total: t.readers, limit: 12 }), credit),
    h("div", { style: { display: "grid", gap: "18px", alignContent: "start" } },
      panel("Devices", null, meter(t.by.device, t.readers, s.device)),
      panel("Browsers", "Brave counts as Chrome; an in-app browser by its app", blist(ranked(t.by.browser, only(s.browser)), { drill: "browser", total: t.readers, limit: 8, color: "var(--views)" })),
      panel("Systems", "An iPad asking for the desktop site counts as macOS", blist(ranked(t.by.os), { drill: "os", total: t.readers, limit: 8, color: "var(--ink-3)" })))));
  out.push(h("section", { class: "s" }, h("h2", null, "All countries"),
    countTable(t.by.country, { caption: "Visitors by country", file: fileName("countries", r), key: "Country", value: "Visitors", keep: only(s.country), total: t.readers, label: country, drill: "country" })));
  out.push(unmeasured(t), coverageNote(cov, r));
  return out;
}

const DEVICE_TONES = { Desktop: "var(--g-people)", Mobile: "var(--views)", Tablet: "var(--g-bots)" };
function meter(obj, whole, pick) {
  const rows = ranked(obj);
  if (!rows.length) return h("p", { class: "empty" }, "None recorded.");
  return h("div", null,
    h("div", { class: "meter", role: "img", "aria-label": rows.map(([k, v]) => `${k} ${n(v)}`).join(", ") },
      rows.map(([k, v]) => h("i", { style: { flexGrow: String(v), background: DEVICE_TONES[k] || "var(--ink-3)", opacity: pick && pick !== k ? ".3" : "1" } }))),
    h("ul", { class: "legend", style: { marginTop: "10px" } }, rows.map(([k, v]) => h("li", null,
      h("span", { class: "sw", style: { background: DEVICE_TONES[k] || "var(--ink-3)" } }), link("device", k), ` ${n(v)} (${pct1(v, whole)})`))));
}
