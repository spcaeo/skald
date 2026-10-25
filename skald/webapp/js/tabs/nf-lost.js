// Site > Not found's lost pages (2.35), above the 404 listings: old addresses people,
// search engines and AI still ask for that now fail, each with the closest live page
// Skald found (exact, likely or guess: skald/closest_page.py) and the server line
// to copy: a 301 redirect for nginx or Apache, or "410 gone". Skald never changes the web
// server; whoever runs it adds the line. Three tabs, kept in the address:
//
//   nfk=lost     Lost pages (the default)
//   nfk=md       AI asks for Markdown: the .md copies of live pages AI asked for
//   nfk=fixed    After the fix: what came for each address marked fixed, after the mark
//   nfsrv=apache the lines for Apache (nginx when absent)
//
// The figures are lost_pages.json's (skald/lost_pages.py), over its own window of
// whole days, checked by a second count (audit_todos.py); withheld when it disagreed.

import { h, n, short, stateNote } from "../ui.js";
import { download, table } from "../table.js";
import * as S from "../state.js";
import { withCopy } from "../urlactions.js";
import { tiles } from "./tiles.js";
import { MARKS, loadMarks, markItem, markOf } from "./todo-marks.js";
import { MATCH_WORDS } from "./todos.js";

export const KINDS = [["lost", "Lost pages"], ["md", "AI asks for Markdown"], ["fixed", "After the fix"]];
export const SERVERS = [["nginx", "nginx"], ["apache", "Apache"]];
const kindOf = (s) => (KINDS.some(([k]) => k === s.nfk) ? s.nfk : "lost");
const serverOf = (s) => (s.nfsrv === "apache" ? "apache" : "nginx");

const matchBadge = (v) => h("span", { class: `lp-m lp-${v || "none"}` }, MATCH_WORDS[v || "none"]);
const line = (text, label) => (text ? withCopy(h("code", { class: "lp-line" }, text), text, { label }) : h("span", { class: "muted" }, "write it by hand: the address has characters a server line cannot take as they are"));
const pathItem = (path) => `path:${path}`;

/* The redirect map: every suggested line for the server chosen, as a file to add. */
export function redirectMap(rows, server) {
  const out = [`# Skald's suggested ${server === "apache" ? "Apache" : "nginx"} lines for old addresses that still get asked for.`,
    "# Check each one before you add it: a Loose match is a guess. Skald never changes the server itself."];
  for (const r of rows) {
    const text = r[server];
    if (!text) continue;
    out.push(r.target ? `${text}${r.match === "guess" ? "   # loose match" : ""}` : `${text}   # no live page close to it`);
  }
  return `${out.join("\n")}\n`;
}

function fixCell(r, redraw) {
  const item = pathItem(r.path);
  const mark = markOf(item, r.marked ? { state: "fixed", day: r.marked } : null);
  const can = MARKS.ok && MARKS.can_mark;
  if (mark) {
    return h("span", { class: "lp-fixed" }, `Marked fixed ${short(mark.day)}`, can ? [" ", button("Undo", item, "open", redraw)] : null);
  }
  return can ? button("Mark fixed", item, "fixed", redraw) : h("span", { class: "muted" }, "-");
}

function button(words, item, state, redraw) {
  const b = h("button", { type: "button", class: "btn sm" }, words);
  b.addEventListener("click", async (e) => {
    e.stopPropagation();
    b.disabled = true;
    const r = await markItem(item, state);
    if (!r.ok) { b.disabled = false; b.textContent = `${words}: not saved`; b.title = r.error || ""; return; }
    redraw();
  });
  return b;
}

function lostPanel(f, s, redraw) {
  const server = serverOf(s);
  const rows = f.lost || [];
  const pick = h("div", { class: "seg plain", role: "group", "aria-label": "Your web server" },
    SERVERS.map(([k, name]) => h("button", { type: "button", "aria-pressed": String(k === server), onclick: () => S.set({ nfsrv: k === "nginx" ? "" : k }, { replace: true }) }, name)));
  const lines = rows.filter((r) => r[server]).length;
  const columns = [
    { key: "path", label: "Old address", path: true },
    { key: "people", label: "People", num: true },
    { key: "search", label: "Search engines", num: true },
    { key: "ai", label: "AI", num: true },
    { key: "target", label: "Closest live page", path: true, fmt: (v) => v || h("span", { class: "muted td-none" }, "none close"), csv: (r) => r.target || "" },
    { key: "match", label: "How close", type: "badge", fmt: (v) => matchBadge(v), csv: (r) => MATCH_WORDS[r.match || "none"], sort: (r) => ["exact", "likely", "guess"].indexOf(r.match) >>> 0 },
    { key: server, label: "Line to add", fmt: (v, r) => h("div", { class: "lp-lines" }, line(v, r.target ? "the redirect line" : "the gone line"),
      r.gone?.[server] ? h("div", { class: "lp-or" }, h("span", { class: "muted" }, "or gone: "), line(r.gone[server], "the gone line")) : null), csv: (r) => r[server] || "" },
    ...(f.marks ? [{ key: "marked", label: "Fixed?", fmt: (_, r) => fixCell(r, redraw), csv: (r) => (markOf(pathItem(r.path), r.marked ? { state: "fixed", day: r.marked } : null)?.day || "") }] : []),
  ];
  return [
    h("p", { class: "sub" }, "Pick what happens to each one. Skald suggests the closest live page and says how close it is: Same page (the same address written another way), Same topic (most of its words), Loose (only its section). Copy the line for your server, or answer 410 gone. Scanner and hacking paths are never listed here."),
    h("div", { class: "lp-bar" }, pick,
      h("button", { type: "button", class: "btn", disabled: lines ? null : true, onclick: () => download(`redirects-${server}.conf`, redirectMap(rows, server), "text/plain;charset=utf-8") }, `Download the ${server === "apache" ? "Apache" : "nginx"} lines (${n(lines)})`)),
    table(columns, { caption: "Old pages, most asked for first", rows, file: "lost-pages.csv", ns: "lp", limit: 12, sortKey: "people", empty: "No old address fails for people, search engines or AI in these days. Good." }),
    f.marks ? null : h("p", { class: "note" }, MARKS.why || "Marking an address fixed needs accounts."),
  ];
}

function mdPanel(f, s) {
  const server = serverOf(s);
  const md = f.markdown || { live: [], other: [] };
  const t = f.totals || {};
  const cols = [
    { key: "path", label: "Asked for", path: true },
    { key: "ai", label: "AI asks", num: true },
    { key: "page", label: "The page", path: true, fmt: (v) => v || h("span", { class: "muted td-none" }, "not live"), csv: (r) => r.page || "" },
    { key: server, label: "Line to add", fmt: (v) => line(v, "the line"), csv: (r) => r[server] || "" },
  ];
  return [
    h("p", { class: "sub" }, md.live.length
      ? `AI assistants asked for .md versions of ${n(t.md_live)} live page${t.md_live === 1 ? "" : "s"}, ${n(t.md_live_asks)} times, and got "not found". One fix covers all of them: serve a Markdown copy at each .md address, or redirect .md to the page.`
      : "No AI asked for a Markdown copy of a live page in these days."),
    table(cols, { caption: "Markdown copies of live pages", rows: md.live, file: "markdown-asks.csv", ns: "lpmd", limit: 12, sortKey: "ai", empty: "None." }),
    md.other.length ? h("details", { class: "fold" }, h("summary", null, `The other ${n(md.other.length)} .md addresses: copies of old pages`),
      h("p", { class: "note" }, "Their page is not live; they follow the choice made for that page on Lost pages."),
      table(cols, { caption: "Markdown copies of old pages", rows: md.other, file: "markdown-asks-old.csv", ns: "lpmo", limit: 12, sortKey: "ai", empty: "None." })) : null,
  ];
}

const VERDICT = { waiting: "Waiting for a whole day", not_yet: "Not yet", fixed: "Fixed" };

function fixedPanel(f, redraw) {
  const rows = [...(f.fixed || [])];
  // Marked since the last data update: listed, waiting for it.
  if (MARKS.ok) {
    for (const [item, mk] of Object.entries(MARKS.marks)) {
      if (!item.startsWith("path:") || mk.state !== "fixed") continue;
      const path = item.slice(5);
      const at = rows.findIndex((r) => r.path === path);
      if (at < 0) rows.push({ path, marked_day: mk.day, days: 0, people: null, search: null, ai: null, served: null, verdict: "waiting", today: null });
    }
    for (let i = rows.length - 1; i >= 0; i--) if (!markOf(pathItem(rows[i].path))) rows.splice(i, 1);
  }
  const failed = (r) => (r.people == null ? null : r.people + r.search + r.ai);
  const cols = [
    { key: "path", label: "Address", path: true },
    { key: "marked_day", label: "Marked fixed", type: "date", fmt: (v) => short(v) },
    { key: "days", label: "Whole days since", num: true },
    { key: "failed", label: "Not found since", num: true, fmt: (_, r) => (failed(r) == null ? "-" : n(failed(r))), csv: (r) => failed(r) ?? "", sort: (r) => failed(r) ?? -1 },
    { key: "served", label: "Served as a page since", num: true, fmt: (v) => (v == null ? "-" : n(v)) },
    { key: "today", label: "Today so far", fmt: (v) => (v ? `${n(v.people + v.search + v.ai)} not found, ${n(v.served)} served` : "-"), csv: (r) => (r.today ? `${r.today.people + r.today.search + r.today.ai} not found; ${r.today.served} served` : "") },
    { key: "verdict", label: "Did it work?", type: "badge", fmt: (v) => h("span", { class: `td-verdict v-${v}` }, VERDICT[v] || v), csv: (r) => VERDICT[r.verdict] || r.verdict },
    ...(MARKS.ok && MARKS.can_mark ? [{ key: "undo", label: "", fmt: (_, r) => button("Undo", pathItem(r.path), "open", redraw), csv: () => "" }] : []),
  ];
  return [
    h("p", { class: "sub" }, "Each address marked fixed is re-checked from the log on every whole day after the mark: the not-found answers to people, search engines and AI, and the times it was served as a page. Zero not-found answers after the mark: fixed."),
    table(cols, { caption: "After the fix", rows, file: "after-the-fix.csv", ns: "lpf", limit: 15, sortKey: "days", empty: f.marks ? "No address is marked fixed yet. Mark one on Lost pages once its line is on the server." : "Marking an address fixed needs accounts." }),
  ];
}

/* The lost pages part, drawn now and again once the marks have answered. */
export function lostPages(m, s) {
  const f = m.x.lost_pages;
  const box = h("section", { class: "s lp-box", "aria-label": "Lost pages" });
  if (!f) return null;
  const draw = () => box.replaceChildren(...body(f, S.read(), draw));
  box.replaceChildren(...body(f, s, draw));
  if (!MARKS.loaded) loadMarks().then(draw);
  return box;
}

function body(f, s, redraw) {
  const w = f.window || {};
  const when = w.first ? `${short(w.first)} to ${short(w.last)}, ${w.days} whole day${w.days === 1 ? "" : "s"} · its own period, not the date range above` : "no whole day yet";
  const out = [h("div", { class: "td-top" }, h("h2", null, "Old addresses still asked for"), h("span", { class: "period" }, when))];
  if (f.withheld?.length) return [...out, stateNote("Withheld: the second count of these addresses disagreed, so no figure is shown.", true), ...f.withheld.map((x) => h("p", { class: "note" }, withCopy(String(x), String(x))))];
  const t = f.totals || {};
  out.push(tiles([
    { label: "Old addresses asked for", value: t.paths ?? null, info: "Page addresses that answered 404 or 410 to people, search engines or AI in these days and are not live now. Scanner probes left out." },
    { label: "People asked", value: t.people ?? null, info: "Real people's requests for those addresses: each one got 'not found'." },
    { label: "Search engines asked", value: t.search ?? null, info: "Search crawlers keep checking addresses that are gone, until they redirect or answer 410." },
    { label: "AI asked for .md", value: t.md_asks ?? null, line: t.md_paths != null ? `${n(t.md_paths)} .md addresses; ${n(t.md_live)} are copies of live pages` : "", info: "AI fetchers' requests for a .md copy of a page that answered 404." },
  ]));
  const kind = kindOf(s);
  out.push(h("div", { class: "seg plain lp-kinds", role: "tablist", "aria-label": "Lost pages" },
    KINDS.map(([k, name]) => h("button", { type: "button", role: "tab", "aria-selected": String(k === kind), "aria-pressed": String(k === kind), onclick: () => S.set({ nfk: k === "lost" ? "" : k }) }, name))));
  out.push(h("div", { class: "lp-panel", role: "tabpanel" }, kind === "md" ? mdPanel(f, s) : kind === "fixed" ? fixedPanel(f, redraw) : lostPanel(f, s, redraw)));
  return out;
}
