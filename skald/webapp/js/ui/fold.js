// Folds (2.41, docs/UI-RULES.md rules 10 and 11): what is done, closed or not set up is one
// quiet line that opens on a press, never a card per item.
//
//   fold(summary, body, { open, cls })      -> <details class="ui-fold"> (body: nodes, or a
//                                              function drawn the first time it opens)
//   doneFold(items, draw, { words })        -> "3 done", with a tick, that opens on the list
//                                              (null when there are none)
//   urlFold(ns, summary, body, { open })     -> a fold whose open state is in the address,
//                                              <ns>_view=open (2.42: every state has a URL)

import { h } from "../ui.js";
import { subView } from "../tablestate.js";

const TICK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8.5l3 3 7-7"/></svg>';

export function fold(summary, body, { open = false, cls = "" } = {}) {
  const inner = h("div", { class: "ui-fold-b" });
  const d = h("details", { class: `ui-fold${cls ? ` ${cls}` : ""}`, open: open || null }, h("summary", null, summary), inner);
  let drawn = false;
  const fill = () => {
    if (drawn) return;
    drawn = true;
    inner.append(...[typeof body === "function" ? body() : body].flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false));
  };
  if (open) fill();
  d.addEventListener("toggle", () => { if (d.open || d.hasAttribute?.("open")) fill(); });
  d.fill = fill;
  return d;
}

/* "N done" (the tick is the menu's line icon, never a ✓ glyph). */
export function doneFold(items, draw, { words = "done", open = false } = {}) {
  const list = (items || []).filter(Boolean);
  if (!list.length) return null;
  const sum = h("span", { class: "ui-done" }, h("span", { class: "ui-done-ic", html: TICK, style: { color: "var(--good)", display: "inline-flex" } }), `${list.length} ${words}`);
  return fold(sum, () => list.map(draw), { open, cls: "ui-fold-done" });
}

/* A fold kept in the address: <ns>_view=open while it is open, so a link or a reload opens it
   again. `open`: open it anyway (a filter inside it is set). */
export function urlFold(ns, summary, body, { open = false, cls = "" } = {}) {
  const v = subView(ns);
  const d = fold(summary, body, { open: open || v.get() === "open", cls });
  d.addEventListener("toggle", () => v.set(d.open || d.hasAttribute?.("open") ? "open" : "", ""));
  return d;
}
