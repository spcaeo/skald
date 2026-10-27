// Settings v2's small parts, on the app's shared pieces (docs/UI-RULES.md: js/ui/pill.js,
// primary.js, fold.js, help.js and css/ui.css). Every Settings page draws through here.
//
//   pill(kind, word)          ui/pill.js: good | warn | bad | off | info
//   primary(label, onClick)   ui/primary.js, the page's one; the frame moves it beside the title
//   fold, doneFold, help      ui/fold.js and ui/help.js, as they are
//   strip(word, text, fix)    the red line when something is broken, with its Fix
//   statusRow({...})          a thing that is set up: icon, name, one line, pill, and its menu
//   quietLine(title, text, action)  what is not set up: one quiet line, one action
//   ic(name)                  the menu's line icons (16 px, stroke 1.5)

import { h } from "../ui.js";
import { pill, KINDS } from "../ui/pill.js";
import { primary as uiPrimary } from "../ui/primary.js";
export { fold, doneFold } from "../ui/fold.js";
export { help } from "../ui/help.js";
export { pill, KINDS };

const P = {
  plug: '<path d="M6 2.5v3M10 2.5v3M4.5 5.5h7v2.5a3.5 3.5 0 0 1-7 0z"/><path d="M8 11.5v2"/>',
  plus: '<path d="M8 3v10M3 8h10"/>',
  fix: '<path d="M10.5 2.5a3 3 0 0 0-3 4L3 11a1.4 1.4 0 0 0 2 2l4.5-4.5a3 3 0 0 0 4-3l-2 2-2-2z"/>',
  more: '<circle cx="3.5" cy="8" r=".9"/><circle cx="8" cy="8" r=".9"/><circle cx="12.5" cy="8" r=".9"/>',
  out: '<path d="M3 8h10M9 4l4 4-4 4"/>',
  search: '<circle cx="7" cy="7" r="4.3"/><path d="M10.2 10.2l3.6 3.6"/>',
  check: '<path d="M3.5 8.5l3 3 6-7"/>',
  next: '<path d="M6 3.5 10.5 8 6 12.5"/>',
  server: '<rect x="2.5" y="3" width="11" height="4" rx="1"/><rect x="2.5" y="9" width="11" height="4" rx="1"/><path d="M5 5h.01M5 11h.01"/>',
  bot: '<rect x="3" y="5" width="10" height="8" rx="2"/><path d="M8 2.5V5M6 9h.01M10 9h.01M1.5 9v2M14.5 9v2"/>',
  person: '<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5a5 5 0 0 1 10 0"/>',
  people: '<circle cx="6" cy="6" r="2.2"/><circle cx="11.3" cy="6.6" r="1.7"/><path d="M2 13a4 4 0 0 1 8 0M10 10.4a3.2 3.2 0 0 1 4 2.6"/>',
  mail: '<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5 8 9l5.5-4.5"/>',
  terminal: '<rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M4.5 6.5 6.5 8l-2 1.5M8 10h3.5"/>',
  code: '<path d="M6 4.5 2.5 8 6 11.5M10 4.5 13.5 8 10 11.5"/>',
  key: '<circle cx="5.5" cy="10.5" r="2.5"/><path d="M7.3 8.7 13 3M11 5l1.5 1.5"/>',
};
/* A line icon from the menu's set, as markup for h(..., { html }). */
export const icon = (name) => `<svg class="ic" viewBox="0 0 16 16" aria-hidden="true">${P[name] || P.plug}</svg>`;
export const ic = (name, cls = "ic-w") => h("span", { class: cls, html: icon(name) });

/* The page's one primary button (the accent). settings-frame.js moves it beside the title,
   wherever the page draws it, and again when the page draws it anew. */
export function primary(label, onClick, { iconName = "plus", disabled = false } = {}) {
  const b = uiPrimary(label, onClick, { icon: iconName ? icon(iconName) : "" });
  b.classList.add("set-primary");
  if (disabled) b.disabled = true;
  return b;
}

/* The red line: what is broken, in one line, and Fix (or what Fix opens, inline). */
export function strip(word, text, fix = null, { kind = "bad" } = {}) {
  let btn = null;
  if (typeof fix === "function") {
    btn = h("button", { type: "button", class: "btn set-fix" }, h("span", { html: icon("fix") }), "Fix");
    btn.addEventListener("click", () => fix(btn));
  }
  return h("div", { class: `ui-strip set-strip s-${kind}`, role: kind === "bad" ? "alert" : "status" }, pill(kind, word), h("span", { class: "ui-grow" }, text), btn);
}

/* A thing that is set up: the whole row opens its details (onOpen), the "more" icon says so.
   line: one short line under the name. */
export function statusRow({ iconName = "plug", title, line = "", kind = "off", word = "", onOpen = null, label = "", action = null }) {
  const kids = [iconName ? h("span", { class: "ui-ic", html: icon(iconName) }) : null, h("span", { class: "grow sr-t" }, h("b", null, title), line ? h("small", null, line) : null),
    word ? pill(kind, word) : null];
  if (action) return h("div", { class: "set-row" }, ...kids, action);
  if (!onOpen) return h("div", { class: "set-row" }, ...kids);
  const b = h("button", { type: "button", class: "set-row is-open", "aria-label": label || `${title}: ${word}. Open its details` }, ...kids, ic("more", "sr-more"));
  b.addEventListener("click", () => onOpen(b));
  return b;
}

/* A card of rows, with its heading and count: "Connected (3)". */
export function rowsCard(title, rows, { help: q = null } = {}) {
  return h("section", { class: "ui-card set-rows" }, h("div", { class: "ui-card-h" }, h("h2", null, title), q), h("div", { class: "set-list" }, rows));
}

/* What is not set up: one quiet line. */
export function quietLine(title, text, action = null) {
  return h("div", { class: "ui-card quiet set-quiet" }, h("b", null, title), h("span", { class: "grow muted" }, text), action);
}

/* A link-looking button (the quiet line's action). */
export function quietButton(label, onClick) {
  const b = h("button", { type: "button", class: "linkish" }, label);
  b.addEventListener("click", onClick);
  return b;
}
