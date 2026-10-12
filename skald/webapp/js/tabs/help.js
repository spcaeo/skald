// Help: the guides for the people who use Skald, one per topic, from
// docs/help/*.md (built into help-data.js by tools/build-about.py, loaded only
// when this page opens). #help lists them; #help?part=webhooks opens one, with
// the list of guides on the left (above it, on a phone). howTo() is the small
// "How do I..." link other pages put beside their own content.

import { h } from "../ui.js";
import * as S from "../state.js";
import { line, blockList } from "../mdview.js";
import INDEX from "../help-index.js";

let DATA = null;
let query = "";             // the search box, kept while the reader moves between guides
let lastPart = null;        // a new guide opens at its top
let jumpTo = "";            // a section to scroll to once the guide is drawn

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
const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

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
  const input = h("input", { type: "search", class: "help-q", placeholder: "Search the guides: webhook, token, Calendly…", "aria-label": "Search the guides", value: query,
    spellcheck: "false", autocomplete: "off" });
  input.addEventListener("input", () => {
    query = input.value;
    const at = input.selectionStart;
    if (s.part) S.set({ part: "" }, { replace: true });
    else redraw();
    requestAnimationFrame(() => { const q = document.querySelector(".help-q"); if (q) { q.focus(); q.setSelectionRange(at, at); } });
  });
  return input;
}

// ------------------------------------------------------------ the list
function index(s) {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const found = DATA.guides.map((g) => ({ g, ...matches(g, words) })).filter((x) => x.hit);
  return [
    h("div", { class: "head" }, h("h1", null, "Help")),
    h("p", { class: "lede" }, "Guides in plain words, one per topic. Each says where to click and what Skald keeps."),
    search(s),
    found.length ? h("ul", { class: "help-cards" }, found.map(({ g, where }) => h("li", null,
      h("a", { class: "help-card sheet card", href: `#help?part=${g.id}`, onclick: () => { jumpTo = where[0] || ""; } },
        h("b", null, g.title), h("span", null, line(g.summary)),
        where.length ? h("small", null, `Found in: ${where.slice(0, 4).join(", ")}`) : null))))
      : h("p", { class: "state" }, `No guide mentions "${query.trim()}". Try fewer words, or `, h("a", { href: "#about" }, "About Skald"), "."),
    h("p", { class: "note" }, "Press ? for the keyboard shortcuts, and Ctrl K (Cmd K on a Mac) to open any guide by its name."),
  ];
}

// ------------------------------------------------------------- a guide
function guide(s, g) {
  const i = DATA.guides.indexOf(g), prev = DATA.guides[i - 1], next = DATA.guides[i + 1];
  const list = h("nav", { class: "help-list", "aria-label": "Guides" },
    h("a", { href: "#help", class: "help-all", onclick: () => { query = ""; } }, "All guides"),
    h("ul", null, DATA.guides.map((x) => h("li", null, h("a", { href: `#help?part=${x.id}`, "aria-current": x === g ? "page" : null }, x.title)))));
  const sections = g.blocks.filter((b) => b.t === "h2");
  const toc = sections.length > 2 ? h("nav", { class: "help-toc", "aria-label": "On this page" }, h("span", null, "On this page:"),
    sections.map((b) => h("button", { type: "button", class: "linkish", onclick: () => document.getElementById(`help-${g.id}-${slug(b.text)}`)?.scrollIntoView({ block: "start" }) }, b.text))) : null;
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
  if (s.part !== lastPart) {
    // A guide opened from another opens at its top (or at the section a search found).
    if (lastPart !== null) requestAnimationFrame(() => {
      const el = jumpTo && g ? document.getElementById(`help-${g.id}-${slug(jumpTo)}`) : null;
      if (el) el.scrollIntoView({ block: "start" }); else window.scrollTo({ top: 0, behavior: "auto" });
      jumpTo = "";
    });
    lastPart = s.part;
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
