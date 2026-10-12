// A section's tabs as spcaeo/ui Folder Tabs (vendor/spcaeo-ui, MIT): the active tab
// is the panel's own sheet; arrows, Home and End move along the strip; the strip
// scrolls sideways with arrow buttons when it overflows (phones).
//
// Skald's tabs are routes, so each tab is a link (<a role="tab" href="#traffic/sources?…">):
// Ctrl-, Cmd- and middle-click open it in a new browser tab, a plain click follows it,
// and a keyboard move replaces the address (one Back leaves the section, not one per
// arrow press). The redraw that follows builds a new strip; if the reader was moving
// along the old one with the keyboard, focus lands on the new strip's active tab.
//
//   const tabs = folderTabs({
//     name: "traffic", label: "Traffic",
//     tabs: [{ key: "traffic/visitors", label: "Visitors", href: S.hashFor({ ...s, tab: "traffic/visitors" }) }, …],
//     active: s.tab,
//     content: [panel nodes],          // goes inside the tab panel
//   });
//   container.append(tabs);            // tabs.panel is the panel, tabs.destroy() tears it down
//
// A tab may carry `count` (a small number beside its name), `disabled: true` with
// `title` (why: it stays focusable, as WAI-ARIA asks, but neither opens nor links).
// `onSelect(key, tab)` replaces the default navigation when a section wants S.set instead.

import { initFolderTabs } from "../vendor/spcaeo-ui/folder-tabs/vanilla/folder-tabs.js";
import { h } from "./ui.js";
import { track } from "./mounts.js";

const ARROW = (d) => `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
const slug = (key) => String(key).replace(/[^a-z0-9]+/gi, "-");

// The strip whose keyboard move started the current redraw: its successor takes focus.
let refocus = null;

export function folderTabs({ name, label, tabs, active, content = [], onSelect }) {
  const id = `ft-${slug(name)}`;
  const panelId = `${id}-panel`;
  const tabId = (key) => `${id}-${slug(key)}`;
  let current = tabs.some((t) => t.key === active) ? active : tabs.find((t) => !t.disabled)?.key;

  const links = tabs.map((t) => h("a", {
    class: "fldr-tab", role: "tab", id: tabId(t.key), "data-key": t.key,
    href: t.disabled ? null : t.href, title: t.title || null,
    "data-state": t.key === current ? "active" : "inactive", "aria-selected": String(t.key === current),
    "aria-controls": t.key === current ? panelId : null, "aria-disabled": t.disabled ? "true" : null,
  }, t.label, t.count != null ? h("span", { class: "fldr-count" }, String(t.count)) : null));
  const strip = h("div", { class: "fldr-scroll" }, links);
  const arrows = h("div", { class: "fldr-arrows" },
    h("button", { class: "fldr-arrow", type: "button", "data-dir": "-1", tabindex: "-1", "aria-label": "Scroll tabs left", html: ARROW("m15 6-6 6 6 6") }),
    h("button", { class: "fldr-arrow", type: "button", "data-dir": "1", tabindex: "-1", "aria-label": "Scroll tabs right", html: ARROW("m9 6 6 6-6 6") }));
  const rail = h("div", { class: "fldr-rail", role: "tablist", "aria-label": label || name }, strip, arrows);
  const panel = h("div", { class: "fldr-panel", id: panelId, role: "tabpanel", tabindex: "0", "aria-labelledby": current ? tabId(current) : null });
  const host = h("div", { "data-folder-tabs": "", class: "sk-tabs", id }, rail, panel);

  // A click with a modifier (or not the main button) belongs to the browser: a new
  // tab or window. Upstream would also switch tabs here, so it never hears of it.
  let clicking = null;
  strip.addEventListener("click", (e) => {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) { e.stopPropagation(); return; }
    clicking = e;
  }, true);
  host.addEventListener("click", () => { clicking = null; });

  host.addEventListener("folder-tabs:change", (e) => {
    const tab = e.detail?.tab;
    if (!tab || e.target !== host) return;
    // Upstream hides the old tab's panel; Skald has one panel, owned by the tab now active.
    for (const a of links) a.removeAttribute("aria-controls");
    tab.setAttribute("aria-controls", panelId);
    panel.setAttribute("aria-labelledby", tab.id);
    panel.hidden = false;
    const key = tab.dataset.key;
    const click = clicking;
    clicking = null;
    if (key === current) return;  // the first select() on wiring, or Enter on the open tab
    current = key;
    const t = tabs.find((x) => x.key === key);
    if (onSelect) {
      click?.preventDefault();
      if (!click) refocus = id;
      onSelect(key, t);
      return;
    }
    if (click) return;  // the link itself goes there
    refocus = id;
    if (t?.href && location.hash !== t.href) location.replace(t.href);
  });

  // initFolderTabs wires the [data-folder-tabs] inside what it is given, so give it a fragment
  // holding the host: the strip is wired before the panel's content (which may hold grids) is added.
  const frag = document.createDocumentFragment();
  frag.append(host);
  const off = initFolderTabs(frag);
  panel.append(...[content].flat(Infinity).filter((k) => k != null && k !== false));

  host.panel = panel;
  host.destroy = track(host, off);
  if (refocus === id) {
    refocus = null;
    // Once the redraw has put the new strip on the page.
    let tries = 0;
    const land = () => {
      if (!host.isConnected) { if (++tries < 30) requestAnimationFrame(land); return; }
      host.querySelector('.fldr-tab[data-state="active"]')?.focus({ preventScroll: true });
    };
    requestAnimationFrame(land);
  }
  return host;
}
