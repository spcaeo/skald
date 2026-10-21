// One set of rows, several shapes (2.20): a small row of icon buttons that picks how a
// tab shows the same rows and filters (a list, a board, a timeline, a map). Built to be
// reused by any section; wired into Leads & sales > Leads first. The choice lives in the
// address (the caller's key), so a link or a reload keeps it.
//
//   viewSwitch("Show leads as", value, VIEWS, (key) => S.set({ lview: key }))
//   VIEWS: [[key, words, icon svg]]; the first is the default.
//
// A radio-like group: one is pressed; arrows move between them, as the tab strips do.

import { h } from "./ui.js";

const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const VIEW_ICON = {
  list: I('<path d="M5.5 4h8M5.5 8h8M5.5 12h8M2.5 4h.01M2.5 8h.01M2.5 12h.01"/>'),
  board: I('<rect x="2" y="2.5" width="3.4" height="11" rx="1"/><rect x="6.3" y="2.5" width="3.4" height="7.5" rx="1"/><rect x="10.6" y="2.5" width="3.4" height="9.2" rx="1"/>'),
  timeline: I('<path d="M2 13.5h12"/><path d="M4 11.5V8M7 11.5V4.5M10 11.5V6.5M13 11.5V9.5"/>'),
  map: I('<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 1.7 2.7 3.7 2.7 6S9.8 12.3 8 14c-1.8-1.7-2.7-3.7-2.7-6S6.2 3.7 8 2z"/>'),
};

export function viewSwitch(name, value, views, pick) {
  const known = views.some(([k]) => k === value) ? value : views[0][0];
  const buttons = views.map(([k, words, icon]) => h("button", { type: "button", class: "vw-b", "aria-pressed": String(k === known), title: words,
    "aria-label": words, html: icon || VIEW_ICON[k] || "", tabindex: k === known ? "0" : "-1", "data-k": k,
    onclick: () => { if (k !== known) pick(k); } }));
  const el = h("div", { class: "vw", role: "group", "aria-label": name }, buttons);
  el.addEventListener("keydown", (e) => {
    const i = buttons.indexOf(e.target);
    if (i < 0) return;
    const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: buttons.length - 1 }[e.key];
    if (to == null) return;
    e.preventDefault();
    const b = buttons[(to + buttons.length) % buttons.length];
    b.focus();
    b.click();
  });
  return el;
}

// The view a tab shows: the address's when known, else the first.
export const viewOf = (value, views) => (views.some(([k]) => k === value) ? value : views[0][0]);
