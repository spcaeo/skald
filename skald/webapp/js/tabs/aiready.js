// AI readiness (2.35): the block in a page's story (Traffic › Pages, `page=`) and the site's
// list "Pages AI can't read well" on AI & bots › Assistants. ai_ready.json is fetched when
// one of them is drawn (it is not one of the files every tab loads); the lines are
// js/ai-ready.js's. Every path gets copy and open; every crawler name, robots.txt line and
// status gets copy.
//
// Address: `psec=ai` opens a page's story at this block (the list's rows do that);
// `arw` is the list's filter (copy, 404, errors, robots, slow; all when absent).

import { h, n, short } from "../ui.js";
import { getJSON, base } from "../data.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { withUrl, withCopy } from "../urlactions.js";
import { readiness, STATE_WORDS, needWords, needAction, needKeep, wholeSite, NEED_FILTERS } from "../ai-ready.js";

export function loadReady(m, s) { return load(m, s); }
function load(m, s) {
  if (Array.isArray(m.files) && !m.files.includes("ai_ready") && !m.files.includes("ai_ready.json")) return Promise.resolve(null);
  return getJSON(`${base(s.view)}ai_ready.json`).then((f) => (f && f.schema_version === 1 && f.state !== "error" ? f : f?.state === "error" ? { failed: f.error || "no reason given" } : null));
}

const note = (text, bad) => h("div", { class: `state${bad ? " bad" : ""}` }, h("div", null, text));
const names = (by) => Object.entries(by || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .flatMap(([k, v], i) => [i ? ", " : "", withCopy(h("span", null, k), k, { label: `the name ${k}` }), ` ${n(v)}`]);
const codes = (o) => Object.entries(o || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .flatMap(([c, v], i) => [i ? ", " : "", withCopy(h("code", null, c), c, { label: `status ${c}` }), ` × ${n(v)}`]);

function detail(line) {
  const d = line.detail || [];
  if (line.id === "robots") {
    return h("ul", { class: "ar-ev" }, d.map((x) => h("li", null, withCopy(h("b", null, x.name), x.name, { label: `the name ${x.name}` }), x.role ? h("span", { class: "muted" }, ` (${x.role})`) : null, ": ",
      x.rule ? withCopy(h("code", null, x.rule), x.rule, { label: "the robots.txt line" }) : "no rule", " under ", withCopy(h("code", null, x.group), x.group, { label: "the robots.txt line" }),
      x.whole ? h("span", { class: "muted" }, ", for the whole site") : null)));
  }
  if (line.id === "copy") {
    return h("ul", { class: "ar-ev" }, d.map((x) => h("li", null, withUrl(h("code", null, x.path), x.path), ": ", codes(x.codes), x.by ? h("span", { class: "muted" }, " · ") : null, names(x.by))));
  }
  if (line.id === "errors" || line.id === "notfound") {
    return h("ul", { class: "ar-ev" }, d.map((x) => h("li", null, Object.keys(x.codes || {}).length ? [codes(x.codes), " · "] : [h("span", null, "slow"), " · "], names(x.by))));
  }
  return null;
}

function lineEl(line) {
  return h("li", { class: `ar-line ar-${line.state}` },
    h("span", { class: "ar-dot", "aria-hidden": "true" }),
    h("div", { class: "ar-body" },
      h("div", { class: "ar-top" }, h("b", null, line.title), h("span", { class: `ar-st ${line.state}` }, STATE_WORDS[line.state])),
      h("p", { class: "ar-says" }, line.says),
      detail(line),
      line.action ? h("p", { class: "ar-do" }, h("span", { class: "ar-arrow", "aria-hidden": "true" }, "→ "), line.action) : null,
      line.snippet ? withCopy(h("pre", { class: "ar-snip" }, line.snippet), line.snippet, { label: "the robots.txt lines", tag: "div", cls: "ar-snip-host" }) : null));
}

/* The block in a page's story. */
export function readyBlock(m, s, path) {
  const sec = h("section", { class: "s ar", id: "ai-readiness" }, h("h3", null, "AI readiness"), h("p", { class: "empty" }, "Checking what AI gets from this page…"));
  load(m, s).then((f) => {
    const head = [h("h3", null, "AI readiness")];
    if (!f) return sec.replaceChildren(...head, note("Not written beside this page yet: it comes with the next redraw."));
    if (f.failed) return sec.replaceChildren(...head, note(`ai_ready.json could not be built on the last redraw: ${f.failed}.`, true));
    if (f.whole_site_only) return sec.replaceChildren(...head, note("Counted for the whole site only: choose All pages."));
    const lines = readiness(f, m.x?.page_trends, path, m.anchor);
    const bad = lines.filter((x) => x.state === "attention").length, unk = lines.filter((x) => x.state === "unknown").length;
    sec.replaceChildren(h("div", { class: "card-h start" }, ...head,
      h("span", { class: `ar-sum ${bad ? "attention" : "good"}` }, bad ? `${bad} of ${lines.length} need attention` : unk ? `Nothing needs attention; ${unk} not known` : "Nothing needs attention")),
      h("p", { class: "sub" }, "Can AI crawlers and assistants read this page well? From your server's log and Skald's own copies of robots.txt and the sitemap; no AI is asked anything. ",
        f.window?.recorded ? `What AI got back: ${short(f.window.since)} to ${short(f.window.last)}.` : ""),
      h("ol", { class: "ar-lines" }, lines.map(lineEl)));
    if (s.psec === "ai") requestAnimationFrame?.(() => sec.scrollIntoView?.({ block: "start" }));
  }).catch((e) => sec.replaceChildren(h("h3", null, "AI readiness"), note(`AI readiness could not be loaded: ${e.message || e}.`, true)));
  return sec;
}

/* The list's "Who": the first three names, each with copy, then how many more (the
   page's block names them all; the CSV has them all). */
const WHO_SHOWN = 3;
function who(v) {
  if (!v?.length) return "-";
  const first = v.slice(0, WHO_SHOWN), more = v.length - WHO_SHOWN;
  // the comma goes after a name, so a narrow cell breaks the line after it, not before
  const shown = first.flatMap((x, i) => [h("span", { class: "ar-nb" }, withCopy(h("span", null, x), x, { label: `the name ${x}` }), i < first.length - 1 ? "," : ""), i < first.length - 1 ? " " : ""]);
  return h("span", { class: "ar-who", title: v.join(", ") }, ...shown, more > 0 ? h("span", { class: "muted" }, ` and ${n(more)} more`) : null);
}

/* AI & bots › Assistants: the pages AI can't read well, worst first. */
export function notReadWell(m, s) {
  const sec = h("section", { class: "s ar-list" }, h("h2", null, "Pages AI can't read well"), h("p", { class: "empty" }, "Checking…"));
  load(m, s).then((f) => {
    const head = h("h2", null, "Pages AI can't read well");
    if (!f) return sec.replaceChildren(head, note("Not written beside this page yet: it comes with the next redraw."));
    if (f.failed) return sec.replaceChildren(head, note(`ai_ready.json could not be built on the last redraw: ${f.failed}.`, true));
    if (f.whole_site_only) return sec.replaceChildren(head, note("Counted for the whole site only: choose All pages."));
    const w = f.window || {};
    const want = NEED_FILTERS.some(([k]) => k === s.arw) ? s.arw || "" : "";
    const rows = (f.attention?.rows || []).map((r, i) => ({ ...r, __k: r.path, rank: i + 1, what: needWords(r), fix: needAction(r) })).filter(needKeep(want));
    const chips = h("div", { class: "seg plain ar-chips", role: "group", "aria-label": "Show the pages with" }, NEED_FILTERS.map(([k, label]) =>
      h("button", { type: "button", "aria-pressed": String(want === k), onclick: () => S.set({ arw: k }, { replace: true }) }, label)));
    const cols = [
      { key: "rank", label: "#", num: true, title: "Worst first: errors and 404s, then robots.txt, then slow answers, then redirects" },
      { key: "path", label: "Page", path: true },
      { key: "what", label: "What AI got", sort: (r) => r.copy_errors + r.not_found + r.server_errors + r.blocked },
      { key: "by", label: "Who", sort: (r) => r.by.join(", "), fmt: who, csv: (r) => r.by.join(", ") },
      { key: "listed", label: "In sitemap", sort: (r) => (r.listed == null ? -1 : r.listed ? 1 : 0), fmt: (v) => (v == null ? h("span", { class: "few" }, "not known") : v ? "yes" : "no"), csv: (r) => (r.listed == null ? "" : r.listed ? "yes" : "no") },
      { key: "fix", label: "What to do" },
    ];
    const site = wholeSite(f);
    sec.replaceChildren(...[head,
      h("p", { class: "sub" }, `Pages where AI crawlers or assistants got an error, a 404 or a slow answer, asked for a Markdown copy that does not answer, or that robots.txt shuts them out of, in the last ${w.days || 30} days. Redirects are shown beside them but do not put a page on the list: the log does not say where a redirect leads. Worst first; select a page for its AI readiness.`),
      site.length ? h("div", { class: "state warn" }, h("div", null, "robots.txt keeps ", site.flatMap((x, i) => [i ? ", " : "", withCopy(h("b", null, x), x, { label: `the name ${x}` })]), " out of the whole site; that is said here once, not on every page.")) : null,
      !f.robots?.crawlers && !f.robots?.missing ? note("Skald has no copy of the site's robots.txt, so robots.txt is not checked.") : null,
      w.recorded ? null : note("What AI gets back is not recorded yet: it is kept from the next collected day on. Only robots.txt is checked until then."),
      chips,
      table(cols, { caption: "Pages AI can't read well", rows, file: `pages-ai-cant-read-${w.first}-to-${w.last}.csv`, sortKey: "rank", dir: 1, limit: 12, rowClass: () => "go",
        onRow: (r) => S.set({ tab: "traffic/pages", page: r.path, psec: "ai" }), empty: want ? "No page has that problem." : "No page needs attention: AI gets what it asks for." }),
      h("p", { class: "note" }, [
        w.recorded ? `What AI got back covers ${n(w.recorded)} of the ${n(w.of)} days with figures (${short(w.since)} to ${short(w.last)}).` : "",
        f.attention?.total > (f.attention?.rows || []).length ? ` The ${n(f.attention.rows.length)} worst of ${n(f.attention.total)} pages are listed.` : "",
        w.folded ? ` On ${n(w.folded)} days more addresses had such answers than Skald keeps (1,000 a day); those are summed, not listed.` : "",
      ].join(""))].filter(Boolean));
  }).catch((e) => sec.replaceChildren(h("h2", null, "Pages AI can't read well"), note(`The list could not be loaded: ${e.message || e}.`, true)));
  return sec;
}

/* AI & bots › Assistants, answer first (2.42): one card, "N pages AI can't read well", what
   kinds, and the screen's one primary button, "Let AI read the site better" (tabs/fixit.js,
   fixit=airead). Nothing to fix: one quiet line, and no button. The full list is under
   "Open the details". */
export function readCard(m, s, { onFix }) {
  const sec = h("section", { class: "ui-card ar-card", "aria-label": "Pages AI can't read well" }, h("p", { class: "empty" }, "Checking what AI gets from your pages…"));
  load(m, s).then(async (f) => {
    if (!f || f.failed || f.whole_site_only) {
      const why = !f ? "What AI gets from your pages is not written yet: it comes with the next redraw." : f.failed ? `ai_ready.json could not be built on the last redraw: ${f.failed}.` : "What AI gets from your pages is counted for the whole site only: choose All pages.";
      return sec.replaceChildren(h("p", { class: "note" }, why));
    }
    const { causesOf } = await import("./fixit.js");
    const causes = causesOf(f);
    const total = f.attention?.total ?? (f.attention?.rows || []).length;
    if (!total) {
      sec.classList.add("quiet");
      return sec.replaceChildren(h("p", { class: "ui-meta" }, `AI gets what it asks for on every page Skald checked in the last ${f.window?.days || 30} days.`));
    }
    const { primary } = await import("../ui/primary.js");
    sec.replaceChildren(h("div", { class: "ui-card-h" }, h("h3", { class: "ui-grow" }, `${n(total)} page${total === 1 ? "" : "s"} AI can't read well`),
      primary("Let AI read the site better", onFix)),
    h("p", { class: "ui-meta" }, `Of these: ${causes.map(([, , , list, words]) => `${n(list.length)} ${words}`).join(" · ")}. A page can have more than one.`));
  }).catch((e) => sec.replaceChildren(h("p", { class: "note" }, `What AI gets from your pages could not be loaded: ${e.message || e}.`)));
  return sec;
}

