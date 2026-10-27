// Help: the guides for the people who use Skald, one per topic, from
// docs/help/*.md (built into help-data.js by tools/build-about.py, loaded only
// when this page opens). #help lists them in a few groups, each guide one line
// (2.42: its summary on hover, so the page is short); #help?part=webhooks opens one,
// with the list of guides on the left (above it, on a phone). howTo() is the small
// "How do I..." link other pages put beside their own content.
//
// In the address: part= the guide, hs= its section (a heading's slug: "Read the guide"
// in a "?" popover, a search's "Found in", the contents line), hq= the search words.

import { h } from "../ui.js";
import * as S from "../state.js";
import { line, blockList } from "../mdview.js";
import INDEX from "../help-index.js";
import { help as helpPop } from "../ui/help.js";

let DATA = null;
let lastPart = null;        // a new guide opens at its top
let lastSec = "";           // ... or at the section in the address (hs)

// The index's groups, in order; a guide not named here goes under "More".
export const GROUPS = [
  ["Start here", "start", ["getting-started", "docker-first-install", "pick-your-road", "sign-in-and-team", "faq"]],
  ["Your visitors", "people", ["real-time", "where-visitors-come-from", "retention", "search", "funnels-and-goals", "internal-traffic"]],
  ["Leads and sales", "leads", ["leads-and-conversions", "revenue", "demo-bookings", "webhooks", "leads-from-your-backend", "tracking-script"]],
  ["AI and bots", "ai", ["ai-and-bots", "crawl-health", "ai-answers", "what-to-fix"]],
  ["Connect and set up", "plug", ["connections", "troubleshooting-connections", "api", "mcp", "settings-and-retention", "client-reports"]],
  ["Security and privacy", "lock", ["security", "privacy"]],
];
const GICON = {
  start: '<path d="M3 13.5V3.5l5 2 5-2v10l-5 2-5-2z"/><path d="M8 5.5v10"/>',
  people: '<circle cx="6" cy="6" r="2.2"/><path d="M2 13c.5-2.2 2-3.4 4-3.4s3.5 1.2 4 3.4"/><circle cx="11.5" cy="6.5" r="1.7"/><path d="M11 9.8c1.6 0 2.7 1 3 3.2"/>',
  leads: '<path d="M2.5 3h11l-4 5v4.5l-3 1.5V8z"/>',
  ai: '<path d="M8 2.5l1.3 3.2 3.2 1.3-3.2 1.3L8 11.5 6.7 8.3 3.5 7l3.2-1.3z"/><path d="M12.5 11.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"/>',
  plug: '<path d="M6 2.5v3M10 2.5v3M4.5 5.5h7v2.5a3.5 3.5 0 0 1-7 0z"/><path d="M8 11.5v2"/>',
  lock: '<rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/>',
  more: '<circle cx="4" cy="8" r=".8"/><circle cx="8" cy="8" r=".8"/><circle cx="12" cy="8" r=".8"/>',
};
const icon = (k) => h("span", { class: "ui-ic", html: `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${GICON[k] || GICON.more}</svg>` });
const query = () => S.read().hq || "";

const BOOK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/></svg>';

/* A link to a guide, for an empty state or a settings page: "How do I connect Calendly?" */
export function howTo(part, words, { block = true } = {}) {
  const known = INDEX.some((g) => g.id === part);
  const a = h("a", { class: "howto", href: `#help?part=${known ? part : ""}`, html: BOOK }, h("span", null, words));
  return block ? h("p", { class: "howto-line" }, a) : a;
}

const plain = (segs) => (segs || []).map((x) => x.s ?? x.b ?? x.i ?? x.code ?? x.a ?? "").join("");
function blockText(b) {
  if (b.text) return b.text;
  if (b.in) return plain(b.in);
  if (b.items) return b.items.map(plain).join(" ");
  if (b.head) return [b.head, ...b.rows].flat().map(plain).join(" ");
  return "";
}
export const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
/* A guide's link, at a section when given (a heading or its slug). */
export const guideHref = (id, section = "") => `#help?part=${id}${section ? `&hs=${slug(section)}` : ""}`;
/* The first sentence of a summary: the index's hover text and a search result's line. */
const firstSentence = (segs) => { const s = plain(segs); const m = /^.*?[.!?](\s|$)/.exec(s); return (m ? m[0] : s).trim(); };

// The guide's sections that hold every word of the search, by their headings.
function matches(g, words) {
  if (!words.length) return { hit: true, where: [] };
  const all = `${g.title} ${plain(g.summary)} ${g.blocks.map(blockText).join(" ")}`.toLowerCase();
  if (!words.every((w) => all.includes(w))) return { hit: false, where: [] };
  const where = [];
  let head = null, text = "";
  const close = () => { if (head && words.every((w) => `${head} ${text}`.toLowerCase().includes(w))) where.push(head); };
  for (const b of g.blocks) {
    if (b.t === "h2") { close(); head = b.text; text = ""; } else text += ` ${blockText(b)}`;
  }
  close();
  return { hit: true, where };
}

function search(s) {
  const input = h("input", { type: "search", class: "help-q", placeholder: "Search the guides: webhook, token, Calendly...", "aria-label": "Search the guides", value: query(),
    spellcheck: "false", autocomplete: "off" });
  input.value = query();
  input.addEventListener("input", () => {
    const at = input.selectionStart;
    // The words go in the address (hq); a guide open goes back to the list to show what matches.
    S.set({ hq: input.value, ...(s.part ? { part: "", hs: "" } : {}) }, { replace: true });
    redraw();
    requestAnimationFrame(() => { const q = document.querySelector(".help-q"); if (q) { q.focus(); q.setSelectionRange?.(at, at); } });
  });
  return input;
}

// ------------------------------------------------------------ the list
function groupCard([name, ic, ids], guides) {
  const list = ids.map((id) => guides.find((g) => g.id === id)).filter(Boolean);
  if (!list.length) return null;
  return h("section", { class: "ui-card help-group" },
    h("h2", { class: "help-gh" }, icon(ic), name),
    h("ul", null, list.map((g) => h("li", null, h("a", { href: guideHref(g.id), title: firstSentence(g.summary) }, g.title)))));
}

function index(s) {
  const q = query();
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const head = [h("div", { class: "head help-head" }, h("h1", null, "Help"),
    helpPop("Help", { text: ["Guides in plain words, one per topic. Each says where to click and what Skald keeps.", "Press ? for the keyboard shortcuts, and Ctrl K (Cmd K on a Mac) to open any guide by its name."] })), search(s)];
  if (!words.length) {
    const named = new Set(GROUPS.flatMap(([, , ids]) => ids));
    const rest = DATA.guides.filter((g) => !named.has(g.id)).map((g) => g.id);
    return [...head, h("div", { class: "help-groups" }, [...GROUPS, ...(rest.length ? [["More", "more", rest]] : [])].map((gr) => groupCard(gr, DATA.guides)))];
  }
  const found = DATA.guides.map((g) => ({ g, ...matches(g, words) })).filter((x) => x.hit);
  if (!found.length) return [...head, h("p", { class: "state" }, `No guide mentions "${q.trim()}". Try fewer words, or `, h("a", { href: "#about" }, "About Skald"), ".")];
  return [...head, h("p", { class: "help-n" }, `${found.length} guide${found.length === 1 ? "" : "s"}`),
    h("ul", { class: "help-found" }, found.map(({ g, where }) => h("li", { class: "ui-card" },
      h("a", { class: "help-ft", href: guideHref(g.id, where[0] || "") }, g.title),
      h("p", null, firstSentence(g.summary)),
      where.length ? h("p", { class: "help-in" }, "Found in: ", ...where.slice(0, 4).flatMap((w, i) => [i ? ", " : "", h("a", { href: guideHref(g.id, w) }, w)])) : null)))];
}

// ------------------------------------------------------------- a guide
function guide(s, g) {
  const i = DATA.guides.indexOf(g), prev = DATA.guides[i - 1], next = DATA.guides[i + 1];
  const list = h("nav", { class: "help-list", "aria-label": "Guides" },
    h("a", { href: "#help", class: "help-all" }, "All guides"),
    h("ul", null, DATA.guides.map((x) => h("li", null, h("a", { href: `#help?part=${x.id}`, "aria-current": x === g ? "page" : null }, x.title)))));
  const sections = g.blocks.filter((b) => b.t === "h2");
  const toc = sections.length > 2 ? h("nav", { class: "help-toc", "aria-label": "On this page" }, h("span", null, "On this page:"),
    sections.map((b) => h("a", { class: "linkish", href: guideHref(g.id, b.text) }, b.text))) : null;
  const body = blockList(g.blocks, { shift: 0, max: 4 });
  // Each section heading gets an id, so the contents and a search can scroll to it.
  body.forEach((el, k) => { if (g.blocks[k].t === "h2") el.id = `help-${g.id}-${slug(g.blocks[k].text)}`; });
  const article = h("article", { class: "help-doc prose-doc" },
    h("p", { class: "help-eyebrow" }, h("a", { href: "#help" }, "Help")),
    h("h1", null, g.title), g.summary.length ? h("p", { class: "help-lede" }, line(g.summary)) : null, toc, body,
    h("nav", { class: "help-pn", "aria-label": "Next and previous guide" },
      prev ? h("a", { href: `#help?part=${prev.id}`, rel: "prev" }, h("small", null, "Previous"), prev.title) : h("span"),
      next ? h("a", { href: `#help?part=${next.id}`, rel: "next" }, h("small", null, "Next"), next.title) : h("span")));
  return [h("div", { class: "help-wrap" }, h("aside", { class: "help-side" }, search(s), list), article)];
}

function page(s) {
  const g = DATA.guides.find((x) => x.id === s.part);
  const sec = s.hs || "";
  if (s.part !== lastPart || sec !== lastSec) {
    // A guide opens at its top, or at the section the address names (hs).
    const first = lastPart === null && !sec;
    const go = () => {
      const el = sec && g ? document.getElementById(`help-${g.id}-${sec}`) : null;
      if (el) el.scrollIntoView({ block: "start" }); else if (!first) window.scrollTo({ top: 0, behavior: "auto" });
    };
    requestAnimationFrame(go);
    // A page opened from a link is scrolled to its top once drawn: go to the section after that.
    if (sec) setTimeout(go, 250);
    lastPart = s.part;
    lastSec = sec;
  }
  return g ? guide(s, g) : index(s);
}

let root = null;
function redraw() { if (root?.isConnected && DATA) root.replaceChildren(...page(S.read()).flat(Infinity).filter(Boolean)); }

export default function help(m, s) {
  root = h("div", { class: "help" });
  if (DATA) root.append(...page(s).flat(Infinity).filter(Boolean));
  else {
    root.append(h("p", { class: "boot" }, "Loading…"));
    const mine = root;
    import("../help-data.js").then((mod) => { DATA = mod.default; if (mine.isConnected) mine.replaceChildren(...page(S.read()).flat(Infinity).filter(Boolean)); })
      .catch((e) => mine.replaceChildren(h("p", { class: "state bad" }, `Help could not be loaded: ${e.message || e}`)));
  }
  return root;
}
