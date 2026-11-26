// Traffic › Agent files (SKALD-56): files a site publishes for AI agents and tools
// rather than for people - Markdown copies of pages, an OKF bundle, llms.txt, agent
// cards under /.well-known/, and robots.txt and sitemaps beside them - and who
// fetched each, from every group: AI assistants, AI crawlers, search engines, other
// bots and tools, people.
//
//   the cards      requests per kind of file, how many came from AI and how many of its
//                  listed files need a look; a kind's card goes to its section (SKALD-65)
//   the chart      requests per day, stacked by who asked (a period of 2 days or more)
//   the sections   one per kind someone fetched, in the owner's order: Markdown copies,
//                  llms.txt, Sitemaps, robots.txt, agent cards, OKF bundle. Each has its
//                  own figures, who asked, Needs a look and files (agent-files-kind.js);
//                  every file's address has Copy and Open, Copy writing the full address.
//                  A file row opens its drawer (agent-files-drawer.js, afile=<path>)
//   who            at the bottom: each group's share, then every name with its requests
//                  per kind
//
// SKALD-65 (2026-11-26) replaced the one mixed file list, the one Needs a look list and
// the chips that narrowed them with these sections, at the owner's request.
//
// From agent_files.json (agent_files.py, recounted by audit_agent_files.py), summed
// over the range by agent-files-sum.js. The whole site's only: a page group says so.

import { h, n, pct1, reduced } from "../ui.js";
import { base, getJSON, chartDays, rangeOf } from "../data.js";
import { columns, legend, band } from "../charts.js";
import { table } from "../table.js";
import { link } from "../drill.js";
import { head, fileName } from "./common.js";
import { KINDS, WHO, KIND_WORDS, WHO_WORDS, WHO_SAYS, WHO_COLOR, OTHER, sumRange, aiOf } from "./agent-files-sum.js";
import { sectionKinds, sectionId, kindSection, looksOf } from "./agent-files-kind.js";

const LEDE = "Files a site publishes for AI agents and tools rather than for people: a Markdown copy of each page, an OKF bundle, llms.txt, agent cards, and robots.txt and sitemaps beside them. Who fetched each, from every group: AI assistants and crawlers, search engines, other bots and tools, and people. Only the address decides, so a request that got a 404 still counts: someone asked for it.";

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

/* Go to a kind's section: scroll to it and move the focus to its heading, so the
   keyboard carries on from there (smooth unless the reader asked for less motion). */
export function goTo(k) {
  const sec = document.getElementById?.(sectionId(k));
  if (!sec) return;
  sec.scrollIntoView?.({ behavior: reduced() ? "auto" : "smooth", block: "start" });
  sec.querySelector("h2")?.focus?.({ preventScroll: true });
}

function card(label, value, note, foot, { sw = null, looks = 0, jump = null } = {}) {
  // Inside a button only phrasing content is valid: spans (a .kpi is a grid, so they
  // lay out as the divs of the other cards do).
  const tag = jump ? "span" : "div";
  const kids = [h(tag, { class: "k-l" }, label), h(tag, { class: "k-n" }, note),
    h(tag, { class: "k-v" }, n(value)),
    h(tag, { class: "k-c" }, sw ? h("span", { class: "sw", style: { background: sw } }) : null, foot),
    looks ? h(tag, { class: "af-kw" }, h("span", { class: "af-dot", "aria-hidden": "true" }), looks === 1 ? "1 needs a look" : `${n(looks)} need a look`) : null];
  if (!jump) return h("div", { class: "kpi" }, ...kids);
  // A kind someone fetched: the card goes to its section.
  return h("button", { type: "button", class: "kpi af-jump", title: `Go to ${label}`, "data-jump": jump, onclick: () => goTo(jump) }, ...kids);
}

const aiFoot = (requests, who) => (requests ? `requests · ${pct1(aiOf(who), requests)} from AI` : "nobody asked");

/* The cards: all files, then one per kind in the sections' order (the OKF bundle only
   when someone fetched it). per[k] is sumRange(file, r, k). */
function cards(got, per) {
  const blank = { requests: 0, who: {} };
  const looks = {};
  let all = 0;
  for (const [k, g] of Object.entries(per)) { looks[k] = looksOf(g); all += looks[k]; }
  const kindCard = (k, note) => {
    const x = got.kinds[k] || blank;
    return card(KIND_WORDS[k], x.requests, note, aiFoot(x.requests, x.who), { looks: looks[k] || 0, jump: x.requests ? k : null });
  };
  return h("div", { class: "kpis af-kpis" },
    card("All agent files", got.total, "requests for any file made for machines", aiFoot(got.total, got.who), { sw: WHO_COLOR.ai_asked, looks: all }),
    kindCard("markdown", "pages' .md versions"),
    kindCard("llms_txt", "llms.txt and llms-full.txt"),
    kindCard("sitemap", "sitemap*.xml"),
    kindCard("robots_txt", "the rules crawlers read first"),
    kindCard("agent_card", "agent and MCP cards in /.well-known/"),
    ...(got.kinds.okf?.requests ? [kindCard("okf", "files of the Open Knowledge bundle")] : []));
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
  const kinds = KINDS.filter((k) => got.kinds[k]?.requests);
  const cols = [
    { key: "name", label: "Name", fmt: (v, x) => (x.folded ? h("span", { class: "muted" }, `${OTHER} (${WHO_WORDS[x.who]})`) : x.who === "people" ? v : link("bot", v)), csv: (x) => x.name },
    { key: "who", label: "Who", fmt: (v) => h("span", { title: WHO_SAYS[v] }, WHO_WORDS[v] || v), csv: (x) => WHO_WORDS[x.who] || x.who },
    ...kinds.map((k) => ({ key: `k_${k}`, label: KIND_WORDS[k], num: true, sort: (x) => x.kinds[k] || 0, fmt: (_, x) => (x.kinds[k] ? n(x.kinds[k]) : h("span", { class: "muted" }, "-")), csv: (x) => x.kinds[k] || 0 })),
    { key: "requests", label: "Requests", num: true },
    { key: "share", label: "Share", num: true, sort: (x) => x.requests, fmt: (_, x) => pct1(x.requests, got.shown), csv: (x) => (got.shown ? (x.requests / got.shown).toFixed(4) : "") },
  ];
  const rows = got.names.map((x) => ({ ...x, __k: `${x.who}|${x.name}` }));
  return h("section", { class: "s" }, h("h2", null, "Who fetches them: all agent files"),
    h("p", { class: "sub" }, "Every request by who sent it, with each kind of file. ", h("b", null, "Other bots and tools"), " holds SEO tools, monitors, scripts (curl, Python), AI tools Skald does not name yet, and browser-like clients that never showed a page: many AI agents fetch with a browser's name."),
    got.shown ? band(parts, got.shown) : null,
    got.shown ? legend(parts.filter((p) => p.value).map((p) => [`${p.name} ${pct1(p.value, got.shown)}`, p.color])) : null,
    table(cols, { caption: "Who fetched agent files", rows, file: fileName("agent-files-who", r), sortKey: "requests", limit: 12, search: rows.length > 12,
      empty: "Nobody fetched these files in this range.",
      note: "Each day keeps the 20 busiest names of each group; the rest are one \"(all others)\" row per group." }));
}

async function openRow(m, s, x) {
  (await import("./agent-files-drawer.js")).openFileDrawer(m, s, x);
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
    const got = sumRange(f, r);
    if (!got.days) {
      const first = (f.days || []).find((d) => d.files)?.day;
      holder.replaceChildren(h("p", { class: "empty" }, got.unrecorded
        ? `Not counted for this range: Skald counts agent files from ${first || "the next collected day"} on.`
        : "No whole, verified day in this range yet."));
      return;
    }
    const bits = [];
    if (got.unrecorded) bits.push(h("p", { class: "msg" }, `${plural(got.unrecorded, "day")} of the range came before Skald counted agent files and ${got.unrecorded === 1 ? "is" : "are"} left out.`));
    const kinds = sectionKinds(got);
    const per = Object.fromEntries(kinds.map((k) => [k, sumRange(f, r, k)]));
    const sections = kinds.map((k) => kindSection(m, s, r, k, per[k], openRow));
    if (!kinds.length) sections.push(h("p", { class: "empty" }, "Nobody fetched these files in this range."));
    holder.replaceChildren(...[...bits, h("section", { class: "s" }, cards(got, per)), chart(r, got),
      ...sections, whoSection(r, got), howSection()].filter(Boolean));
  }).catch((e) => holder.replaceChildren(h("p", { class: "empty" }, `Agent files could not be loaded: ${e.message || e}.`)));
  return out;
}
