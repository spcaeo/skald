// Traffic › Agent files (SKALD-56): files a site publishes for AI agents and tools
// rather than for people - Markdown copies of pages, an OKF bundle, llms.txt, agent
// cards under /.well-known/, and robots.txt and sitemaps beside them - and who
// fetched each, from every group: AI assistants, AI crawlers, search engines, other
// bots and tools, people.
//
//   the cards      requests per kind of file, and how many came from AI
//   the kinds      a row of chips narrows everything below to one kind
//   the chart      requests per day, stacked by who asked
//   who            each group's share, then every name with its requests per kind
//   files          every file fetched (the 50 busiest a day are kept, 30 days back):
//                  its page, requests, the AI share, its answers, the last fetch; a
//                  row opens the file's drawer (agent-files-drawer.js, afile=<path>)
//   needs a look   files that answered 4xx/5xx (an agent asked and got nothing) or
//                  moved elsewhere (3xx)
//
// From agent_files.json (agent_files.py, recounted by audit_agent_files.py), summed
// over the range by agent-files-sum.js. The whole site's only: a page group says so.

import { h, n, pct1 } from "../ui.js";
import { base, getJSON, chartDays, rangeOf } from "../data.js";
import { columns, legend, band } from "../charts.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { head, fileName } from "./common.js";
import { time as tzTime } from "../tz.js";
import { pageOf } from "../ai-ready.js";
import { KINDS, WHO, KIND_WORDS, KIND_ONE, KIND_SAYS, WHO_WORDS, WHO_SAYS, WHO_COLOR, OTHER,
  sumRange, answers, attention, aiOf } from "./agent-files-sum.js";

const LEDE = "Files a site publishes for AI agents and tools rather than for people: a Markdown copy of each page, an OKF bundle, llms.txt, agent cards, and robots.txt and sitemaps beside them. Who fetched each, from every group: AI assistants and crawlers, search engines, other bots and tools, and people. Only the address decides, so a request that got a 404 still counts: someone asked for it.";

let kindPick = "";

const plural = (k, one, many = `${one}s`) => `${n(k)} ${k === 1 ? one : many}`;

/* The file, or why there is none (data.js caches it). */
export function loadFile(m, s) {
  if (Array.isArray(m.files) && !m.files.includes("agent_files.json") && !m.files.includes("agent_files")) return Promise.resolve({ missing: true });
  return getJSON(`${base(s.view)}agent_files.json`).then((f) => f || { missing: true });
}

function why(f) {
  if (f.missing) return h("p", { class: "empty" }, "Agent files are not written beside this page yet. They are counted from the next collected day on.");
  if (f.state === "error") return h("div", { class: "state warn" }, h("div", null, `agent_files.json could not be built on the last redraw: ${f.error || "no reason given"}.`));
  if (f.whole_site_only) return h("p", { class: "empty" }, "Agent files are counted for the whole site only, not for a page group. Switch to the whole site to see them.");
  return null;
}

function card(label, value, note, foot, sw) {
  return h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note),
    h("div", { class: "k-v" }, n(value)),
    h("div", { class: "k-c" }, sw ? h("span", { class: "sw", style: { background: sw } }) : null, foot));
}

const aiFoot = (requests, who) => (requests ? `requests · ${pct1(aiOf(who), requests)} from AI` : "nobody asked");

function cards(got) {
  const k = got.kinds;
  const get = (x) => k[x] || { requests: 0, who: {} };
  const rs = { requests: get("robots_txt").requests + get("sitemap").requests,
    who: Object.fromEntries(WHO.map((w) => [w, (get("robots_txt").who[w] || 0) + (get("sitemap").who[w] || 0)])) };
  const allWho = {};
  for (const v of Object.values(k)) for (const [w, x] of Object.entries(v.who)) allWho[w] = (allWho[w] || 0) + x;
  return h("div", { class: "kpis af-kpis" },
    card("All agent files", got.total, "requests for any file made for machines", aiFoot(got.total, allWho), WHO_COLOR.ai_asked),
    card("Markdown copies", get("markdown").requests, "pages' .md versions", aiFoot(get("markdown").requests, get("markdown").who)),
    ...(get("okf").requests ? [card("OKF bundle", get("okf").requests, "files of the Open Knowledge bundle", aiFoot(get("okf").requests, get("okf").who))] : []),
    card("llms.txt", get("llms_txt").requests, "llms.txt and llms-full.txt", aiFoot(get("llms_txt").requests, get("llms_txt").who)),
    card("Agent cards", get("agent_card").requests, "agent and MCP cards in /.well-known/", aiFoot(get("agent_card").requests, get("agent_card").who)),
    card("robots.txt and sitemaps", rs.requests, "the files crawlers have always read", aiFoot(rs.requests, rs.who)));
}

function chips(got, redraw) {
  const present = KINDS.filter((k) => got.kinds[k]?.requests);
  if (present.length < 2 && !kindPick) return null;
  const chip = (k, words) => h("button", { type: "button", class: `af-chip${kindPick === k ? " on" : ""}`, "aria-pressed": String(kindPick === k),
    onclick: () => { kindPick = k; redraw(); } }, words);
  return h("div", { class: "af-chips", role: "group", "aria-label": "Which files" },
    chip("", "All files"), ...present.map((k) => chip(k, `${KIND_WORDS[k]} ${n(got.kinds[k].requests)}`)));
}

function chart(r, got) {
  if (r.kind !== "history" || r.length < 2) return null;
  const days = chartDays(r).map((d) => (got.series.has(d.day) ? d : { ...d, state: d.state === "ok" ? "before" : d.state }));
  const series = WHO.map((w) => ({ name: WHO_WORDS[w], color: WHO_COLOR[w], get: (d) => got.series.get(d.day)?.[w] || 0 }));
  return h("section", { class: "s" }, h("h2", null, "Requests per day, by who asked"),
    h("p", { class: "sub" }, "A hatched day was not counted: before Skald counted agent files, or not a whole, verified day."),
    h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not counted", "", "hatch"]]),
      columns(days, series, { label: "Agent-file requests per day", unit: "requests", H: 220 })));
}

function whoSection(r, got) {
  const parts = WHO.map((w) => ({ name: WHO_WORDS[w], value: got.who[w] || 0, color: WHO_COLOR[w] }));
  const kinds = kindPick ? [] : KINDS.filter((k) => got.kinds[k]?.requests);
  const cols = [
    { key: "name", label: "Name", fmt: (v, x) => (x.folded ? h("span", { class: "muted" }, `${OTHER} (${WHO_WORDS[x.who]})`) : x.who === "people" ? v : link("bot", v)), csv: (x) => x.name },
    { key: "who", label: "Who", fmt: (v) => h("span", { title: WHO_SAYS[v] }, WHO_WORDS[v] || v), csv: (x) => WHO_WORDS[x.who] || x.who },
    ...kinds.map((k) => ({ key: `k_${k}`, label: KIND_WORDS[k], num: true, sort: (x) => x.kinds[k] || 0, fmt: (_, x) => (x.kinds[k] ? n(x.kinds[k]) : h("span", { class: "muted" }, "-")), csv: (x) => x.kinds[k] || 0 })),
    { key: "requests", label: "Requests", num: true },
    { key: "share", label: "Share", num: true, sort: (x) => x.requests, fmt: (_, x) => pct1(x.requests, got.shown), csv: (x) => (got.shown ? (x.requests / got.shown).toFixed(4) : "") },
  ];
  const rows = got.names.map((x) => ({ ...x, __k: `${x.who}|${x.name}` }));
  return h("section", { class: "s" }, h("h2", null, "Who fetches them"),
    h("p", { class: "sub" }, "Every request by who sent it. ", h("b", null, "Other bots and tools"), " holds SEO tools, monitors, scripts (curl, Python), AI tools Skald does not name yet, and browser-like clients that never showed a page: many AI agents fetch with a browser's name."),
    got.shown ? band(parts, got.shown) : null,
    got.shown ? legend(parts.filter((p) => p.value).map((p) => [`${p.name} ${pct1(p.value, got.shown)}`, p.color])) : null,
    table(cols, { caption: "Who fetched agent files", rows, file: fileName("agent-files-who", r), sortKey: "requests", limit: 12, search: rows.length > 12,
      empty: "Nobody fetched these files in this range.",
      note: "Each day keeps the 20 busiest names of each group; the rest are one \"(all others)\" row per group." }));
}

const answerCell = (st) => {
  const a = answers(st);
  const bits = [];
  if (a.ok) bits.push(h("span", { class: "af-ok" }, `${n(a.ok)} ok`));
  if (a.moved) bits.push(h("span", { class: "af-mv" }, `${n(a.moved)} moved`));
  if (a.failed) bits.push(h("span", { class: "af-bad" }, `${n(a.failed)} failed`));
  return h("span", { class: "af-ans", title: Object.entries(st).map(([c, k]) => `${c}: ${n(k)}`).join(", ") }, ...bits.flatMap((b, i) => (i ? [" · ", b] : [b])));
};

const pageCell = (x) => (x.kind === "markdown" ? link("path", pageOf(x.path)) : h("span", { class: "muted" }, "-"));

async function openRow(m, s, x) {
  (await import("./agent-files-drawer.js")).openFileDrawer(m, s, x);
}

function filesSection(m, s, r, got) {
  const cols = [
    { key: "path", label: "File", fmt: (v) => h("code", { class: "af-path", title: v }, v) },
    { key: "kind", label: "Kind", fmt: (v) => h("span", { title: KIND_SAYS[v] }, KIND_ONE[v] || v), csv: (x) => KIND_ONE[x.kind] || x.kind },
    { key: "page", label: "Copy of", sort: (x) => (x.kind === "markdown" ? pageOf(x.path) : ""), fmt: (_, x) => pageCell(x), csv: (x) => (x.kind === "markdown" ? pageOf(x.path) : ""), title: "The page a Markdown copy belongs to" },
    { key: "requests", label: "Requests", num: true },
    { key: "ai", label: "From AI", num: true, sort: (x) => aiOf(x.who) / (x.requests || 1), fmt: (_, x) => pct1(aiOf(x.who), x.requests), csv: (x) => aiOf(x.who), title: "AI assistants and AI crawlers" },
    { key: "answers", label: "Answers", sortable: false, fmt: (_, x) => answerCell(x.status), csv: (x) => Object.entries(x.status).map(([c, k]) => `${c}:${k}`).join(" ") },
    { key: "last", label: "Last fetched", type: "date", fmt: (v) => (v ? tzTime(v, { date: true, label: false }) : "-") },
  ];
  const rows = got.files.map((x) => ({ ...x, __k: x.path }));
  const restN = Object.values(got.rest).reduce((a, v) => a + v.requests, 0);
  const restF = Object.values(got.rest).reduce((a, v) => a + v.files, 0);
  const notes = ["Select a file for its days, answers and who fetched it."];
  if (got.filesDays < got.days) notes.push(`Files are kept for the last 30 days: they are listed for ${plural(got.filesDays, "day")} of the ${plural(got.days, "day")} counted; the cards, chart and names above cover them all.`);
  if (restN) notes.push(`Beyond each day's 50 busiest files: ${plural(restN, "more request")} (${plural(restF, "file")}, counted per day), in the totals above but not listed.`);
  return h("section", { class: "s" }, h("h2", null, kindPick ? KIND_WORDS[kindPick] : "Every file fetched"),
    h("p", { class: "sub" }, kindPick ? KIND_SAYS[kindPick] : "Each file for machines that someone asked for, busiest first. Copy of: the page a Markdown copy stands for."),
    table(cols, { caption: "Agent files fetched", rows, file: fileName("agent-files", r), sortKey: "requests", limit: 15,
      empty: got.filesDays ? "No file of this kind was fetched in this range." : "Files are listed for the last 30 days only.",
      rowClass: () => "go", onRow: (x) => openRow(m, s, x), note: notes.join(" ") }));
}

function todo(x) {
  if (x.a.failed) {
    if (x.kind === "llms_txt" || x.kind === "agent_card") return "Agents ask for it and the site has none. Publish one, or leave it if you do not want to.";
    return "Agents asked and got nothing: fix the file, or remove the link that points to it.";
  }
  return "It sends agents elsewhere. Fine when on purpose; else link the final address.";
}

function attentionSection(r, got) {
  const rows = attention(got.files).map((x) => ({ ...x, __k: x.path }));
  if (!rows.length) return null;
  const cols = [
    { key: "path", label: "File", fmt: (v) => h("code", { class: "af-path", title: v }, v) },
    { key: "kind", label: "Kind", fmt: (v) => KIND_ONE[v] || v },
    { key: "answers", label: "Answered", sortable: false, fmt: (_, x) => Object.entries(x.status).filter(([c]) => c[0] !== "2" && c !== "304").map(([c, k]) => `${c} × ${n(k)}`).join(", ") },
    { key: "who", label: "Asked by", sortable: false, fmt: (_, x) => WHO.filter((w) => x.who[w]).map((w) => `${WHO_WORDS[w]} ${n(x.who[w])}`).join(", ") },
    { key: "todo", label: "What to do", sortable: false, fmt: (_, x) => todo(x), csv: (x) => todo(x) },
  ];
  return h("section", { class: "s" }, h("h2", null, "Needs a look"),
    h("p", { class: "sub" }, "Files that answered an error (an agent asked and got nothing) or sent the agent to another address."),
    table(cols, { caption: "Agent files that need a look", rows, file: fileName("agent-files-attention", r), sortKey: "requests", limit: 10, search: false }));
}

function howSection() {
  return h("section", { class: "s af-how" }, h("h2", null, "How Skald counts this"),
    h("ul", null,
      h("li", null, "Only the address decides: a path ending .md, .mdx or .markdown is a Markdown copy (in an okf folder, the OKF bundle); llms.txt and llms-full.txt anywhere; agent-card.json, agent.json, agents.json, mcp.json, mcp/, ai-plugin.json and ai-catalog.json under /.well-known/; /robots.txt; sitemap*.xml."),
      h("li", null, "An agent can also ask for the page's own address with the header Accept: text/markdown and get Markdown back. A server log does not keep that header, so those requests look like page views of bots and are not counted here."),
      h("li", null, "Markdown copies are never page views: Pages leaves them out. Every figure here has a second count from the raw log lines, as all of Skald's do.")));
}

export default function agentFiles(m, s) {
  const r = rangeOf(m, s);
  const out = [...head("Agent files", r, LEDE)];
  const holder = h("div", { class: "af" }, h("p", { class: "empty" }, "Loading agent files…"));
  out.push(holder);
  loadFile(m, s).then((f) => {
    const no = why(f);
    if (no) { holder.replaceChildren(no); return; }
    const draw = () => {
      const got = sumRange(f, r, kindPick);
      if (kindPick && !got.kinds[kindPick]?.requests) { kindPick = ""; draw(); return; }
      if (!got.days) {
        const first = (f.days || []).find((d) => d.files)?.day;
        holder.replaceChildren(h("p", { class: "empty" }, got.unrecorded
          ? `Not counted for this range: Skald counts agent files from ${first || "the next collected day"} on.`
          : "No whole, verified day in this range yet."));
        return;
      }
      const bits = [];
      if (got.unrecorded) bits.push(h("p", { class: "msg" }, `${plural(got.unrecorded, "day")} of the range came before Skald counted agent files and ${got.unrecorded === 1 ? "is" : "are"} left out.`));
      holder.replaceChildren(...[...bits, h("section", { class: "s" }, cards(got)), chips(got, draw), chart(r, got),
        whoSection(r, got), attentionSection(r, got), filesSection(m, s, r, got), howSection()].filter(Boolean));
    };
    draw();
  }).catch((e) => holder.replaceChildren(h("p", { class: "empty" }, `Agent files could not be loaded: ${e.message || e}.`)));
  return out;
}
