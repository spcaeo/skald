// About Skald, "How Skald compares": Skald at a glance, who should use what,
// the matrix by module (a table on wide screens, a card per feature on
// phones), and the numbered sources. Everything is open; nothing folds.
// A cell with more to say is a button: its full text, notes and sources open
// in a popover. The words come from docs/COMPARISON.md via about-data.js.

import { h } from "../ui.js";
import { MARK } from "../mark.js";
import { store } from "../extras.js";
import { info } from "./tiles.js";

const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
// Matched on the doc's titles, so a reworded item keeps its picture or gets a plain one.
const GLYPHS = [
  [/machines/i, I('<rect x="3" y="5.5" width="10" height="7.5" rx="2"/><path d="M8 2.5v3M6 9.2h.01M10 9.2h.01"/>')],
  [/why an AI/i, I('<path d="M2.5 3h11v7.5H8.5L5.5 13v-2.5h-3z"/><path d="M6.6 5.7a1.4 1.4 0 1 1 1.9 1.3c-.4.2-.5.5-.5.9M8 9h.01"/>')],
  [/checks names/i, I('<path d="M8 1.8l5 2v4c0 3-2.2 5.2-5 6.4-2.8-1.2-5-3.4-5-6.4v-4z"/><path d="M5.8 8l1.6 1.6 3-3.2"/>')],
  [/proven/i, I('<path d="M1.8 8.6l2.6 2.6 4.6-4.7M7.3 11.2l.9.9 6-6.3"/>')],
  [/live|private/i, I('<path d="M1.5 8.5h3l1.6-4.5 3 8.5 1.6-4h3.8"/>')],
  [/search/i, I('<circle cx="7" cy="7" r="4.3"/><path d="M10.3 10.3L14 14"/>')],
  [/inside the page/i, I('<path d="M3.5 2.5l8.5 4-3.7 1.4L6.8 12z"/><path d="M9 9.5l3 3"/>')],
  [/reach|control/i, I('<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.9 2.2 1.9 9.8 0 12M8 2c-1.9 2.2-1.9 9.8 0 12"/>')],
];
const glyph = (title) => (GLYPHS.find(([re]) => re.test(title)) || [null, I('<circle cx="8" cy="8" r="2.5"/>')])[1];

// Each tool: a short name for a narrow column header, and a letter tile. Only Skald's is drawn in colour.
const TOOLS = {
  Skald: ["Skald", null], "Google Analytics 4": ["GA4", "G4"], "Search Console": ["Search Console", "SC"],
  "Bing Webmaster Tools": ["Bing Webmaster", "B"], Plausible: ["Plausible", "P"], Matomo: ["Matomo", "M"],
  Cloudflare: ["Cloudflare", "CF"], GoAccess: ["GoAccess", "GA"], PostHog: ["PostHog", "PH"], "Known Agents": ["Known Agents", "KA"],
};
const DEFAULT = ["Google Analytics 4", "Search Console", "Plausible", "Cloudflare"];
const short = (t) => (TOOLS[t] || [t])[0];
const tile = (t) => (t === "Skald" ? h("span", { class: "tl tl-me", html: MARK, "aria-hidden": "true" })
  : h("span", { class: "tl", "aria-hidden": "true" }, (TOOLS[t] || [, t.slice(0, 2)])[1]));

const MARKS = { "✓": ["yes", "Yes"], "◐": ["part", "Partly"], "✗": ["no", "No"], "?": ["unk", "Not confirmed"], "–": ["na", "Does not apply"], planned: ["plan", "Planned"] };
const SHOW_WORDS = 6;
const NUM = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];

let C = null, SHOWN = null, DIFF = false, FIT = null;
addEventListener("resize", () => FIT?.());
const plain = (segs) => segs.map((x) => x.s ?? x.b ?? x.i ?? x.code ?? x.a ?? "").join("");
const words = (t) => t.trim().split(/\s+/).filter(Boolean).length;

function seg(x) {
  if (x.b != null) return h("strong", null, x.b);
  if (x.i != null) return h("em", null, x.i);
  if (x.code != null) return h("code", null, x.code);
  if (x.a != null) return /^https?:/.test(x.href) ? h("a", { href: x.href, target: "_blank", rel: "noopener noreferrer" }, x.a) : h("a", { href: x.href }, x.a);
  return x.s ?? "";
}

// [12]: a jump to source 12 at the bottom of the page.
function srcRef(n) {
  return h("button", { type: "button", class: "src-ref", "aria-label": `Source ${n}`, onclick: () => {
    closePop(false);
    const li = document.getElementById(`src-${n}`);
    li?.scrollIntoView({ block: "center" });
    li?.classList.remove("flash"); void li?.offsetWidth; li?.classList.add("flash");
    li?.querySelector("a")?.focus({ preventScroll: true });
  } }, `[${n}]`);
}

// ------------------------------------------------------------ popover
let POP = null;
function closePop(refocus = true) {
  if (!POP) return;
  const { el, from, off } = POP;
  POP = null;
  off();
  el.remove();
  from.setAttribute("aria-expanded", "false");
  if (refocus) from.focus({ preventScroll: true });
}

function openPop(from, tool, row, cell) {
  if (POP?.from === from) return closePop();
  closePop(false);
  const [, means] = MARKS[cell.mark] || [null, ""];
  const notes = cell.refs.map((n) => C.notes[n]).filter(Boolean);
  const srcs = [...new Set(notes.flatMap((x) => x.src))];
  const close = h("button", { type: "button", class: "pop-x", "aria-label": "Close" }, "×");
  const el = h("div", { class: "cmp-pop", role: "dialog", "aria-label": `${tool}: ${row.feature}` },
    h("div", { class: "pop-h" }, tile(tool), h("div", null, h("b", null, tool), h("span", null, row.feature)), close),
    cell.mark === "text" ? h("p", { class: "pop-full" }, cell.text) : h("p", { class: `pop-mk ${MARKS[cell.mark][0]}` }, markEl(cell.mark), means),
    notes.filter((x) => x.text.length).map((x) => h("p", { class: "pop-note" }, x.text.map(seg))),
    srcs.length ? h("div", { class: "pop-src" }, h("span", null, srcs.length > 1 ? "Sources" : "Source"),
      h("ul", null, srcs.map((n) => { const s = C.sources[n - 1]; return h("li", null, srcRef(n), " ", source(s)); }))) : null);
  document.body.append(el);
  place(el, from);
  const key = (e) => { if (e.key === "Escape") { e.preventDefault(); closePop(); } };
  const away = (e) => { if (!el.contains(e.target) && !from.contains(e.target)) closePop(false); };
  const moved = (e) => { if (!el.contains(e.target)) closePop(false); };
  document.addEventListener("keydown", key);
  document.addEventListener("pointerdown", away, true);
  window.addEventListener("scroll", moved, true);
  window.addEventListener("resize", moved);
  POP = { el, from, off: () => { document.removeEventListener("keydown", key); document.removeEventListener("pointerdown", away, true); window.removeEventListener("scroll", moved, true); window.removeEventListener("resize", moved); } };
  close.addEventListener("click", () => closePop());
  from.setAttribute("aria-expanded", "true");
  close.focus({ preventScroll: true });
}

// Below the cell when there is room, above it otherwise; never off screen.
function place(el, from) {
  const r = from.getBoundingClientRect(), vw = innerWidth, vh = innerHeight;
  const w = el.offsetWidth, ht = el.offsetHeight;
  el.style.left = `${Math.max(12, Math.min(r.left + r.width / 2 - w / 2, vw - w - 12))}px`;
  const below = r.bottom + 8 + ht <= vh - 12 || r.top - 8 - ht < 12;
  el.style.top = `${below ? Math.min(r.bottom + 8, vh - ht - 12) : r.top - 8 - ht}px`;
}

const source = (s) => (s.href ? h("a", { href: s.href, target: "_blank", rel: "noopener noreferrer" }, s.label, h("span", { class: "host" }, ` ${new URL(s.href).hostname.replace(/^www\./, "")}`))
  : h("span", null, s.label, h("span", { class: "host" }, " in Skald's code")));

// --------------------------------------------------------------- cells
function markEl(mark) {
  const [cls, means] = MARKS[mark] || ["txt", ""];
  if (mark === "planned") return h("span", { class: "mk2 plan" }, "planned");
  return h("span", { class: `mk2 ${cls}`, title: means }, h("span", { "aria-hidden": "true" }, mark), h("span", { class: "vh" }, means));
}

// What a cell shows: its mark and at most six words; true when there is more behind it.
function cellView(cell) {
  const notes = cell.refs.map((n) => C.notes[n]).filter(Boolean);
  const said = notes.map((x) => plain(x.text)).filter(Boolean);
  if (cell.mark === "text") {
    const text = cell.short || cell.text;
    return [h("span", { class: "c-text" }, text), Boolean(cell.short || notes.length)];
  }
  const line = said.length === 1 && words(said[0]) <= SHOW_WORDS ? said[0].replace(/\.$/, "") : "";
  return [[markEl(cell.mark), line ? h("span", { class: "c-note" }, line) : null], notes.length > 0];
}

function cellNode(tool, row, cell, tag) {
  const [view, more] = cellView(cell);
  if (!more) return h(tag, { class: "c-in" }, view);
  return h("button", { type: "button", class: `c-in c-more ${tag === "span" ? "c-line" : ""}`, "aria-expanded": "false", "aria-haspopup": "dialog",
    "aria-label": `${tool}, ${row.feature}: ${cell.mark === "text" ? cell.text : (MARKS[cell.mark] || [, ""])[1]}. Notes and sources`,
    onclick: (e) => openPop(e.currentTarget, tool, row, cell) }, view);
}

// -------------------------------------------------------------- glance
function glance() {
  const card = (x, side) => h("li", { class: `gl-i ${side}` }, h("span", { class: "gl-ic", html: glyph(x.title) }),
    h("h4", null, x.title), h("p", null, x.text.map(seg)),
    side === "them" ? h("p", { class: "gl-who" }, C.tools.filter((t) => t !== "Skald" && plain(x.text).includes(t.replace("Google Analytics 4", "GA4"))).map((t) => h("span", { class: "who-t" }, tile(t), short(t)))) : null);
  return h("div", { class: "glance" },
    h("h3", { class: "cmp-h" }, "Skald at a glance"),
    h("div", { class: "gl-cols" },
      h("div", { class: "gl-side" }, h("p", { class: "gl-cap" }, "Where Skald is strongest"), h("ul", { class: "gl-list us" }, C.where_skald_leads.map((x) => card(x, "us")))),
      h("div", { class: "gl-side" }, h("p", { class: "gl-cap" }, "Where others are better"), h("ul", { class: "gl-list them" }, C.where_others_lead.map((x) => card(x, "them"))))));
}

// --------------------------------------------------------------- guide
function guide() {
  return h("div", { class: "guide" }, h("h3", { class: "cmp-h" }, "Who should use what"), h("p", { class: "cmp-lede" }, C.who_lede),
    h("dl", { class: "guide-l" }, C.who.map((x) => h("div", { class: `guide-r${x.use.includes("Skald") ? " me" : ""}` },
      h("dt", null, x.need),
      h("dd", null, h("span", { class: "guide-use" }, x.use.map((t) => h("span", { class: "who-t" }, tile(t), t))), h("span", { class: "guide-why" }, x.why))))));
}

// -------------------------------------------------------------- matrix
const pick = () => {
  const saved = store.get("ti-about-cmp", null);
  return new Set(["Skald", ...(Array.isArray(saved) && saved.every((t) => C.tools.includes(t)) ? saved : DEFAULT)]);
};
const same = (r, cols) => new Set(cols.map((i) => `${r.cells[i].mark}|${r.cells[i].text}`)).size === 1;

function matrix() {
  SHOWN ||= pick();
  const body = h("div", { class: "cmp-body" });
  const chips = h("div", { class: "add-tools", role: "group", "aria-label": "Tools in the table" });
  const reset = h("button", { type: "button", class: "linkish", onclick: () => { SHOWN = new Set(["Skald", ...DEFAULT]); store.set("ti-about-cmp", DEFAULT); draw(); } }, "Back to the usual five");
  const diff = h("input", { type: "checkbox", checked: DIFF, onchange: (e) => { DIFF = e.target.checked; draw(); } });
  function drawChips() {
    chips.replaceChildren(h("span", { class: "add-l" }, "Add tools"), ...C.tools.filter((t) => t !== "Skald").map((t) => {
      const on = SHOWN.has(t);
      return h("button", { type: "button", class: "tchip2", "aria-pressed": String(on), onclick: () => {
        on ? SHOWN.delete(t) : SHOWN.add(t);
        store.set("ti-about-cmp", C.tools.filter((x) => x !== "Skald" && SHOWN.has(x)));
        draw();
        chips.querySelector(`[data-t="${CSS.escape(t)}"]`)?.focus();
      }, "data-t": t }, h("span", { class: "tc-s", "aria-hidden": "true" }, on ? "✓" : "+"), tile(t), short(t));
    }));
    reset.hidden = DEFAULT.length === SHOWN.size - 1 && DEFAULT.every((t) => SHOWN.has(t));
  }
  function draw() {
    closePop(false);
    drawChips();
    const cols = C.tools.map((t, i) => [t, i]).filter(([t]) => SHOWN.has(t));
    const idx = cols.map(([, i]) => i);
    const mods = C.modules.map((m) => ({ ...m, groups: m.groups.map((g) => ({ ...g, rows: g.rows.filter((r) => !DIFF || !same(r, idx)) })).filter((g) => g.rows.length) }))
      .filter((m) => m.groups.length);
    if (!mods.length) return body.replaceChildren(h("p", { class: "empty" }, "With these tools no row differs. Add a tool above to compare more."));
    body.replaceChildren(table(mods, cols), cards(mods, cols));
    requestAnimationFrame(fit);
  }
  // The table fits the page and its header sticks under the top bar; when it
  // cannot fit, it becomes a framed box that scrolls both ways inside itself.
  function fit() {
    const frame = body.isConnected && body.querySelector(".cmp-frame");
    if (!frame) return;
    frame.classList.remove("boxed");
    frame.classList.toggle("boxed", frame.scrollWidth > frame.clientWidth + 1);
  }
  FIT = fit;
  draw();
  const legend = h("ul", { class: "cmp-key", "aria-label": "What the marks mean" }, C.legend.map((x) => h("li", null, markEl(x.mark), x.means)),
    h("li", { class: "key-more" }, h("span", { class: "dot", "aria-hidden": "true" }), "Click a marked cell for its notes and sources"));
  return h("div", { class: "matrix" }, h("h3", { class: "cmp-h" }, "Feature by feature"),
    h("div", { class: "cmp-ctl" }, chips, h("div", { class: "cmp-ctl2" }, reset, h("label", { class: "rb-check" }, diff, "Only rows that differ"))),
    legend, body);
}

function table(mods, cols) {
  const n = cols.length + 1;
  const head = h("thead", null, h("tr", null, h("th", { scope: "col", class: "c-feat" }, h("span", { class: "vh" }, "Feature")),
    cols.map(([t]) => h("th", { scope: "col", class: t === "Skald" ? "me" : null }, h("span", { class: "th-in" }, tile(t), h("span", null, short(t)))))));
  const bodies = mods.map((m) => h("tbody", null,
    h("tr", { class: "mod-r" }, h("th", { scope: "colgroup", colspan: n }, h("span", { class: "mod-n" }, m.name), h("span", { class: "mod-d" }, m.desc))),
    m.groups.map((g) => [g.name ? h("tr", { class: "grp-r" }, h("th", { scope: "colgroup", colspan: n }, g.name)) : null,
      g.rows.map((r) => h("tr", null, h("th", { scope: "row" }, r.feature, r.sub ? h("small", null, r.sub) : null),
        cols.map(([t, i]) => h("td", { class: `${(MARKS[r.cells[i].mark] || ["txt"])[0]}${t === "Skald" ? " me" : ""}` }, cellNode(t, r, r.cells[i], "div")))))])));
  return h("div", { class: "cmp-frame", style: { "--cols": cols.length } }, h("table", { class: "cmp2" },
    h("caption", { class: "vh" }, "Skald compared, feature by feature"),
    h("colgroup", null, h("col", { class: "col-f" }), cols.map(([t]) => h("col", { class: t === "Skald" ? "col-me" : null }))), head, bodies));
}

// Phones: a card per feature, each tool on its own line.
function cards(mods, cols) {
  return h("div", { class: "cmp-cards" }, mods.map((m) => h("section", { class: "cc-mod" }, h("h4", null, m.name), h("p", { class: "mod-d" }, m.desc),
    m.groups.flatMap((g) => g.rows).map((r) => h("article", { class: "cc" }, h("h5", null, r.feature, r.sub ? h("small", null, r.sub) : null),
      h("ul", null, cols.map(([t, i]) => h("li", { class: t === "Skald" ? "me" : null }, h("span", { class: "cc-t" }, tile(t), short(t)), cellNode(t, r, r.cells[i], "span")))))))));
}

// ----------------------------------------------------- also checked, sources
function also() {
  return h("div", { class: "also" }, h("h3", { class: "cmp-h" }, "Also checked"), h("p", { class: "cmp-lede" }, C.also_lede),
    h("ul", { class: "also-l" }, C.also_checked.map((x) => h("li", null, h("b", null, x.name), " ", x.text.map(seg), " ", x.src.map(srcRef)))));
}

const day = () => new Date(`${C.checked}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
function sources() {
  return h("div", { class: "sources", id: "about-sources" }, h("h3", { class: "cmp-h" }, "Sources"),
    h("p", { class: "cmp-lede" }, `${C.sources.length} sources, each on the vendor's own pages or in Skald's code, checked ${day()}.`),
    h("ol", { class: "src-l" }, C.sources.map((s, i) => h("li", { id: `src-${i + 1}` }, source(s)))));
}

export function compare(data) {
  C = data;
  // The doc's opening line points at this very page; its rules for reading the table go behind an (i).
  const rules = C.intro.filter((b) => b.t === "p" && !b.in.some((x) => x.href?.includes("part=compare"))).map((b) => plain(b.in)).join(" ");
  const lede = h("p", { class: "cmp-lede" }, `Skald beside ${NUM[C.tools.length - 1] || C.tools.length - 1} other tools, feature by feature. Their facts come from their own pages, checked ${day()}; Skald's column claims only what is live today.`,
    rules ? info(rules, "How the table was checked") : null);
  return [lede, glance(), guide(), matrix(), also(), sources()];
}
