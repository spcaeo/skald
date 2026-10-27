// An assistant's reads, not its requests (ai_reads.py). A user fetcher can ask
// for one page twice and then for the page's own files: Google NotebookLM fetches
// a page, renders it, and loads its CSS and JS, so one read was four requests and a
// stylesheet showed as something "AI asked". A read is one assistant, one page,
// counted once in WINDOW seconds; the page's files are folded under it.
//
// Day figures: app.json days[].ai_reads (and live.figures.ai_reads), summed by
// data.js total(); `unmeasured.ai_reads` counts the whole days stored before reads
// were counted. A range with such a day shows "Reads counted from <day>", never a
// guess and never 0.

import { h, n, short } from "../ui.js";
import { panel, blist } from "./common.js";
import { help } from "../ui/help.js";

export const WINDOW = 30;
const OTHER = "(all others)";

// What each user fetcher's read means, in one line (the drawer's "?").
const ABOUT = {
  "chatgpt-user": "ChatGPT fetches a page when someone asks it a question the page answers, or pastes the page's link.",
  "claude-user": "Claude fetches a page when someone asks it about the page or it looks something up to answer.",
  "claude-web": "Claude's older fetcher, for a page someone asked about on claude.ai.",
  "perplexity-user": "Perplexity fetches a page when someone asks it a question or opens one of its sources.",
  "gemini-user": "Gemini fetches a page when someone asks it about the page.",
  "google-notebooklm": "Google NotebookLM fetches a page when someone adds it as a source to a notebook, or refreshes one.",
  "google-gemininotebook": "Google NotebookLM (its newer name) fetches a page when someone adds it as a source to a notebook, or refreshes one.",
  "google-agent": "Google's agent opens a page while doing a task someone gave it.",
  "googleagent-mariner": "Google's Project Mariner opens a page while browsing for someone.",
  "mistralai-user": "Mistral's Le Chat fetches a page when someone asks it a question.",
  "meta-externalfetcher": "Meta AI fetches a page when someone shares its link or asks about it.",
  "bingpreview": "Copilot (Bing) fetches a page to preview it or answer about it.",
  "amzn-user": "Alexa fetches a page to answer someone's question.",
};
export const aboutOf = (name) => ABOUT[String(name || "").toLowerCase()] || null;
export const READ_WORDS = `A read is one assistant reading one page: its requests for that page within ${WINDOW} seconds count once, and the files the page loaded (styles, scripts, images, fonts) are folded under it, never counted as reads.`;

/* The first day with reads stored, else null (today counts once the snapshot has them). */
function firstDay(m) {
  const days = [...(m.byDay?.values?.() || [])].filter((d) => d.ai_reads).map((d) => d.day).sort();
  if (days.length) return days[0];
  return m.live?.figures?.ai_reads ? m.today : null;
}

/* The range's reads: {known, reads, requests, files, repeats, byName: {name: reads},
   pages: {name: {path: {reads, files}}}, names}, or {known: false, from, requests}. */
export function readsOf(m, t, r) {
  const a = t?.ai_reads;
  if (a && (r?.kind === "today" || !t.unmeasured?.ai_reads)) {
    const names = a.by_name || {};
    return { known: true, reads: a.reads || 0, requests: a.requests || 0, files: a.files || 0, repeats: a.repeats || 0,
      byName: Object.fromEntries(Object.entries(names).map(([k, v]) => [k, v.reads || 0])), pages: a.pages || {}, names };
  }
  return { known: false, from: firstDay(m), requests: t?.tiers?.asked ?? null };
}

/* "Reads counted from 27 Oct": what a range before reads were counted says instead. */
export const notYet = (x) => (x.from ? `Reads counted from ${short(x.from)}` : "Reads are counted from the next update");

/* "4 requests, 2 of them files the page loaded": the second, smaller number. */
export function requestsWords(x) {
  if (x.requests == null) return "";
  const files = x.known && x.files ? `, ${n(x.files)} of them files its pages loaded` : "";
  return `${n(x.requests)} request${x.requests === 1 ? "" : "s"}${files}`;
}

/* Is this name a user fetcher (it has reads in the range, or a known line)? */
export const isFetcher = (x, name) => !!(aboutOf(name) || (x.known && x.names?.[name]));

/* A bot drawer's "What it read": the range's reads of this fetcher by page, each with
   the files the page loaded, and what a read means behind "?". */
export function readsSection(m, t, r, name) {
  const x = readsOf(m, t, r);
  if (!isFetcher(x, name)) return null;
  const about = aboutOf(name);
  const title = h("div", { class: "card-h start" }, h("h3", null, "What it read"),
    help(`What ${name} read`, { text: [about || `${name} fetches pages for someone using an AI assistant.`, READ_WORDS], guide: "ai-and-bots" }));
  if (!x.known) return h("section", { class: "s" }, title, h("p", { class: "note" }, `${notYet(x)}. Its requests are counted below.`));
  const mine = x.names[name] || null;
  const pages = x.pages[name] || {};
  const rows = Object.entries(pages).filter(([p]) => p !== OTHER).map(([p, v]) => [p, v.reads || 0, v.files || 0]).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const filesOf = Object.fromEntries(rows.map(([p, , f]) => [p, f]));
  const kpis = h("div", { class: "dd-kpis" },
    h("div", null, h("b", null, n(mine?.reads ?? 0)), h("span", null, "reads")),
    h("div", null, h("b", null, n(mine?.requests ?? 0)), h("span", null, "requests")),
    h("div", null, h("b", null, n(mine?.files ?? 0)), h("span", null, "files its pages loaded")));
  const list = rows.length ? blist(rows.map(([p, v]) => [p, v]), { drill: "path", from: "drill", limit: 10, color: "var(--g-answer_engines)",
    change: (p) => (filesOf[p] ? `with ${n(filesOf[p])} file${filesOf[p] === 1 ? "" : "s"}` : "") })
    : h("p", { class: "empty" }, "No page read in this range.");
  const tail = pages[OTHER] ? h("p", { class: "note" }, `Each day keeps its 10 pages with most reads; ${n(pages[OTHER].reads)} more reads are in other pages.`) : null;
  return h("section", { class: "s dd-reads" }, title, kpis, panel("Pages it read", null, list), tail);
}

/* Fold a list of request rows (newest first) so a read's repeats and the files its page
   loaded sit under the read's own row. Each row: {name, path, at, role, of}. Returns
   [{row, again, files: [rows]}]; a file or repeat whose read is not in the list stays a
   row of its own. */
export function foldReads(rows, nameOf = (r) => r.name) {
  const out = [];
  const reads = [];
  const items = new Map();
  rows.forEach((row, i) => { if (row.role === "read") { const it = { row, again: 0, files: [] }; items.set(i, it); reads.push([i, row]); } });
  rows.forEach((row, i) => {
    if (row.role === "read") { out.push(items.get(i)); return; }
    if (row.role === "repeat" || row.role === "file") {
      // The read it belongs to: same assistant, its page, the latest at or before this row.
      let hit = null;
      for (const [j, r] of reads) {
        // `of` is the read's path cut at 70 characters (ai_reads.bare); a row's may be longer.
        if (j === i || nameOf(r) !== nameOf(row) || String(r.path).slice(0, 70) !== row.of || String(r.at) > String(row.at)) continue;
        if (!hit || String(r.at) > String(hit[1].at)) hit = [j, r];
      }
      if (hit && row.of) {
        const it = items.get(hit[0]);
        if (row.role === "repeat") it.again += 1; else it.files.push(row);
        return;
      }
    }
    out.push({ row, again: 0, files: [] });
  });
  return out;
}

/* " · asked 2 times, with 2 files": what a folded read row adds. */
export function foldWords(it) {
  const bits = [];
  if (it.again) bits.push(`asked ${it.again + 1} times`);
  if (it.files.length) bits.push(`with ${it.files.length} file${it.files.length === 1 ? "" : "s"} its page loaded`);
  return bits.length ? ` · ${bits.join(", ")}` : "";
}
