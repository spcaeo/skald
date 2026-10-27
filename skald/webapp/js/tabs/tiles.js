// The pieces every tab builds its top from, so they all look and read alike:
// a strip of tiles (label, (i), number, one small line, trend), the "who else
// came" row of machines in their own units, and a top-5 card with See all.

import { h, n, tip, untip } from "../ui.js";
import { color } from "../data.js";
import * as S from "../state.js";
import { blist } from "./common.js";
import { popper } from "../tabletools.js";

/* An (i) that says what something counts, on hover and on keyboard focus. With `more` (a
   help address, "#help?part=..."), a press opens a small popover instead: the same words
   and "Learn more" into the guide at the right part (2.20, the help-in-context rule). */
export function info(text, label, more = "") {
  const b = h("button", { type: "button", class: "info-i", "aria-label": `About ${label}: ${text}` }, "i");
  const show = () => { if (b.getAttribute("aria-expanded") === "true") return; const r = b.getBoundingClientRect(); tip(r.left + r.width / 2, r.top, label, [{ value: "", label: text }]); };
  b.addEventListener("pointerenter", show);
  b.addEventListener("pointerleave", untip);
  b.addEventListener("focus", show);
  b.addEventListener("blur", untip);
  if (!more) return b;
  const pop = h("div", { class: "tt-pop info-pop", role: "dialog", "aria-label": label },
    h("p", { class: "info-pop-h" }, label), h("p", null, text), h("a", { href: more, class: "info-more" }, "Learn more"));
  b.addEventListener("click", untip);
  return popper(b, pop);
}

/* items: [{label, value (number|string|null), info, line (node|string), trend (node), fmt}]
   A null value is "-": the period cannot give it honestly. The strip wraps
   with no empty cell: the last row's tiles share its width. */
export function tiles(items) {
  return h("div", { class: "tiles", role: "list" }, items.filter(Boolean).map((x) => h("div", { class: "tile", role: "listitem" },
    h("div", { class: "t-top" }, h("span", { class: "t-l" }, x.label), x.info ? info(x.info, x.label, x.more) : null),
    h("div", { class: "t-v" }, x.value == null ? "-" : typeof x.value === "number" ? (x.fmt || n)(x.value) : x.value),
    typeof x.line === "string" ? h("span", { class: "t-c t-wrap" }, x.line) : x.line || h("span", { class: "t-c none" }, ""),
    x.trend || h("div", { class: "spark" }))));
}

// Who else came: the machines, each in the unit it is counted in.
export function others(t, { probes = false } = {}) {
  // Reads, not requests (ai-reads.js), once every day of the range has them.
  const reads = t.ai_reads && !t.unmeasured?.ai_reads ? t.ai_reads.reads ?? 0 : null;
  const items = [
    reads != null
      ? ["answer_engines", "AI answering a question now", reads, `page reads (${n(t.tiers?.asked ?? 0)} requests)`, "An assistant read the page because someone asked it a question just then. Its repeat requests for the page and the page's own files are counted once, as one read."]
      : ["answer_engines", "AI answering a question now", t.tiers?.asked ?? 0, "requests", "An assistant fetched the page because someone asked it a question just then. Requests, the page's own files included."],
    ["answer_engines", "AI collecting for training", t.tiers?.training ?? 0, "pages fetched", "Crawls that feed an assistant's training or index; nobody is waiting."],
    ["search_engines", "Search engines", t.search ?? 0, "pages fetched", "Indexing by Google, Bing and others; ads quality checks not included."],
    ["bots", "Bots and scanners", t.hits?.bots ?? 0, probes && t.probes ? `requests, ${n(t.probes)} of them probes` : "requests", "Monitors, SEO tools, link previews and scanners probing for weak spots."],
    ["ours", "Our own", t.hits?.ours ?? 0, "requests", "The office, our tests, our crawler and the five-minute heartbeat."],
  ];
  return h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Who else came"), info("Machines are counted by what they fetched, never as visitors.", "Who else came")),
    h("ul", { class: "others" }, items.map(([g, label, v, unit, why]) => h("li", { title: why },
      h("span", { class: "k-sw", style: { background: color(g) } }), h("span", { class: "o-l" }, label), h("b", null, n(v)), h("small", null, unit)))));
}

// A top-5 card: title, what it counts, the list, and See all (the tab).
export function top(title, unit, tab, rows, opts) {
  const all = h("button", { type: "button", class: "see-all", onclick: () => S.set({ tab }) }, "See all");
  return h("div", { class: "sheet card" }, h("div", { class: "card-h" }, h("h3", null, title), all),
    h("p", { class: "card-m" }, unit), blist(rows, { limit: 5, ...opts }));
}

/* Older tabs build their figures as .kpi cells with a sentence under each
   label. After a draw, each sentence moves into an (i) beside its label,
   so every tab's figures read like the tiles. */
export function quietKpis(root) {
  root.querySelectorAll(".kpi .k-n").forEach((note) => {
    const text = note.textContent.trim();
    const lab = note.parentElement.querySelector(".k-l");
    if (text && lab && !lab.querySelector(".info-i")) lab.append(" ", info(text, lab.textContent.trim()));
    note.remove();
  });
}
