// A section's tabs: the strip under the section's title, and the panel the
// chosen tab draws into. Plain and accessible, in Skald's own styles
// (css/shell.css): one tab stop, the arrows move between tabs, Home and End go
// to the ends, Enter or Space opens the tab (manual activation: each tab is a
// page, so moving the focus never redraws). Each tab is a link, so Ctrl- and
// middle-click open it in a new browser tab as any link would.
//
// The one place the strip is made: spcaeo/ui Folder Tabs will replace the
// inside of this file and keep its interface.
//
//   tabStrip(tabs, active, onPick, { label }) -> { root, panel }
//     tabs    [{ key, name, href, count?, countLabel? }]: count, a small number on the tab
//     active  the chosen tab's key
//     onPick  (key) => void: a plain click, Enter or Space on a tab
//     label   the strip's accessible name (the section's name)
//   root   the strip and its panel, to put on the page
//   panel  role=tabpanel, labelled by the chosen tab: put the tab's content in it

import { h } from "./ui.js";

let refocus = false;    // a tab was opened from the strip: the new strip takes the focus back

export function tabStrip(tabs, active, onPick, { label = "" } = {}) {
  const id = (key) => `stab-${String(key).replace(/[^a-z0-9-]/gi, "-")}`;
  const pick = (e, key) => {
    if (e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    refocus = true;
    onPick(key);
  };
  const items = tabs.map((t) => h("a", { href: t.href, role: "tab", class: "stab", id: id(t.key), "data-key": t.key,
    "aria-selected": String(t.key === active), "aria-controls": "stabs-panel", tabindex: t.key === active ? "0" : "-1",
    onclick: (e) => pick(e, t.key) },
  h("span", { class: "stab-name" }, t.name),
  t.count ? h("span", { class: "tab-n", "aria-label": t.countLabel || String(t.count) }, String(t.count)) : null));
  const list = h("div", { class: "stabs-list", role: "tablist", "aria-label": label, "aria-orientation": "horizontal" }, items);
  list.addEventListener("keydown", (e) => {
    const i = items.indexOf(document.activeElement);
    if (i < 0) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      refocus = true;
      onPick(items[i].dataset.key);
      return;
    }
    const j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: items.length - 1 }[e.key];
    if (j == null) return;
    e.preventDefault();
    const next = items[(j + items.length) % items.length];
    items.forEach((x) => x.setAttribute("tabindex", x === next ? "0" : "-1"));
    next.focus();
  });
  const on = items.find((x) => x.dataset.key === active);
  const panel = h("div", { class: "stabs-panel", id: "stabs-panel", role: "tabpanel", "aria-labelledby": on ? on.id : null });
  const root = h("div", { class: "stabs" }, list, panel);
  // Once on the page: the chosen tab in view (the strip scrolls sideways on a phone),
  // and the focus back on it when the reader opened it from the strip.
  const back = refocus;
  refocus = false;
  requestAnimationFrame(() => {
    if (!root.isConnected || !on) return;
    if (on.offsetLeft < list.scrollLeft || on.offsetLeft + on.offsetWidth > list.scrollLeft + list.clientWidth) list.scrollLeft = Math.max(0, on.offsetLeft - 24);
    if (back) on.focus({ preventScroll: true });
  });
  return { root, panel };
}
