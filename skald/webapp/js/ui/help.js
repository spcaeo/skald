// The "?" next to a heading or a figure (2.41, docs/UI-RULES.md rule 9): help on demand,
// never a paragraph on the working screen. A press opens a small popover with a title,
// a few plain sentences and "Read the guide" into Help at the right guide. It opens on a
// press (so it works on a phone, where there is no hover), closes on Escape, on the x, on
// a second press or a press outside, and the focus goes back to the "?".
//
//   help(label, { text, guide })   -> <span class="ui-help-w"> with the button and its popover
//     label  what the "?" is about ("Visitors", "Alerts"); its aria-label is "Help: <label>"
//     text   the words (a string, or a list of strings: one paragraph each); when absent, the
//            guide's own summary (help-index.js) is shown
//     guide  a Help guide's id (docs/help/<id>.md, e.g. "what-to-fix"), or "<id>#<section>" with
//            a heading's slug: "Read the guide" opens #help?part=<id>(&hs=<section>) there.
//            An id that is not a guide gets no link (tests/js/help-guides.mjs checks each one).

import { h } from "../ui.js";
import INDEX from "../help-index.js";

let openOne = null;          // one popover open at a time
let seq = 0;
const outside = (e) => { if (openOne && !openOne.wrap.contains(e.target)) openOne.close(false); };

export const guideOf = (id) => INDEX.find((g) => g.id === String(id || "").split("#")[0]) || null;
// "id#section" (2.42): the guide at that section (its heading's slug, hs= in the address).
const sectionOf = (guide) => String(guide || "").split("#")[1] || "";

export function help(label, { text = "", guide = "" } = {}) {
  const g = guideOf(guide);
  const sec = sectionOf(guide);
  const words = [].concat(text || (g ? g.summary : "")).filter(Boolean);
  const id = `ui-help-${++seq}`;
  const btn = h("button", { type: "button", class: "ui-help", "aria-label": `Help: ${label}`, "aria-expanded": "false", "aria-controls": id, title: `What is ${label}?` }, "?");
  const x = h("button", { type: "button", class: "ui-help-x", "aria-label": "Close the help" }, "×");
  const pop = h("div", { class: "ui-help-pop", id, role: "dialog", "aria-label": label, hidden: true },
    x, h("h4", null, label), ...words.map((w) => h("p", null, w)),
    g ? h("a", { class: "ui-help-more", href: `#help?part=${g.id}${sec ? `&hs=${sec}` : ""}` }, "Read the guide") : null);
  const wrap = h("span", { class: "ui-help-w" }, btn, pop);
  const me = { wrap, close };
  function close(focusBack) {
    if (pop.hidden) return;
    pop.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    if (openOne === me) openOne = null;
    if (focusBack) btn.focus();
  }
  function open() {
    if (openOne && openOne !== me) openOne.close(false);
    pop.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    pop.classList.remove("left");
    const r = pop.getBoundingClientRect?.();
    if (r && r.right > (globalThis.innerWidth || 0) - 8) pop.classList.add("left");
    openOne = me;
    document.addEventListener("pointerdown", outside);
    (pop.querySelector("a") || x).focus();
  }
  btn.addEventListener("click", (e) => { e.stopPropagation?.(); if (pop.hidden) open(); else close(false); });
  x.addEventListener("click", () => close(true));
  wrap.addEventListener("keydown", (e) => { if (e.key === "Escape" && !pop.hidden) { e.stopPropagation?.(); e.preventDefault?.(); close(true); } });
  wrap.open = open;
  wrap.close = close;
  return wrap;
}
