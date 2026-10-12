// The top bar's second row of controls: compare to the previous period, the
// chart markers, saved views and the alerts bell. Each is small; they live
// here so main.js stays the router.

import { h, toast } from "./ui.js";
import * as S from "./state.js";
import { CHOICES, choiceWords } from "./tz.js";
import { openDrawer } from "./drawer.js";
import { withFlag } from "./tabs/readers.js";

// Browser storage may be blocked (private windows, strict settings): every
// read and write is wrapped, and the app works the same without it.
export const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
  },
};

const BELL = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11.5V7a4 4 0 0 1 8 0v4.5l1.2 1.3H2.8z"/><path d="M6.6 14a1.5 1.5 0 0 0 2.8 0"/></svg>';
const STAR = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M4 2.5h8v11L8 10.8 4 13.5z"/></svg>';
const CMP = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 12l3.5-4 3 2.5L14 4"/><path d="M2 13.5h12" stroke-dasharray="2 2"/></svg>';
const MARK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 4.5v10" stroke-dasharray="2 2"/><path d="M8 1l3 3-3 3-3-3z"/></svg>';

// --------------------------------------------------------------- markers
export const marksOn = () => store.get("ti-marks", true) !== false;

// ---------------------------------------------------------- the toggles
export function toggles(s, onMarks) {
  const cmp = h("button", { type: "button", class: "btn tog", "aria-pressed": String(!!s.cmp), html: CMP, "aria-label": "Compare to the previous period",
    title: "Compare to the previous period: the period before, of the same length, beside each figure and chart" });
  cmp.addEventListener("click", () => S.set({ cmp: s.cmp ? "" : "1" }));
  const mk = h("button", { type: "button", class: "btn tog", "aria-pressed": String(marksOn()), html: MARK, "aria-label": "Markers on the day charts",
    title: "Markers: releases, counting changes and internal-address changes on the day charts" });
  mk.addEventListener("click", () => {
    const on = !marksOn();
    store.set("ti-marks", on);
    mk.setAttribute("aria-pressed", String(on));
    onMarks(on);
  });
  return h("div", { class: "togs", role: "group", "aria-label": "Chart options" }, cmp, mk);
}

// ------------------------------------------------------- the time zone
export function zonePicker(s) {
  const sel = h("select", { "aria-label": "Show times in", title: "Show times in this zone. Days stay the site's." },
    CHOICES.map((c) => h("option", { value: c, selected: c === s.tz }, choiceWords(c))));
  sel.addEventListener("change", () => { store.set("ti-tz", sel.value); S.set({ tz: sel.value }); });
  return h("label", { class: "ctl tzp" }, h("span", { class: "vh" }, "Times in"), sel);
}

// ------------------------------------------------------------ the bell
export function bell(m) {
  const f = m.x?.alerts;
  if (!f) return null;
  const open = (f.open || []).length;
  const high = (f.open || []).some((a) => a.severity === "high");
  const b = h("button", { type: "button", class: `btn bell${open ? " on" : ""}${high ? " high" : ""}`, html: BELL,
    "aria-label": open ? `Alerts: ${open} open. Open the alerts.` : "Alerts: none open. Open the alerts." },
  open ? h("span", { class: "bell-n", "aria-hidden": "true" }, String(open)) : null);
  b.addEventListener("click", () => S.set({ tab: "health/alerts" }));
  return b;
}

// --------------------------------------------------------- saved views
/* A saved view is a name and the whole state in the URL hash: tab, range,
   view, filters and the compare switch. Kept in this browser only. */
const KEY = "ti-saved";
export const savedViews = () => { const v = store.get(KEY, []); return Array.isArray(v) ? v.filter((x) => x && x.name && x.hash) : []; };

let openPop = null;
document.addEventListener("pointerdown", (e) => { if (openPop && !openPop.wrap.contains(e.target)) openPop.close(false); });

// The saved views, drawn into any box (the popover, or a dialog on a narrow screen).
function savedContent(box, close, { heading = true } = {}) {
  const draw = () => {
    const list = savedViews();
    const name = h("input", { type: "text", placeholder: "e.g. Canada, mobile, 30 days", maxlength: "60", "aria-label": "Name for this view" });
    const form = h("form", { class: "save-row" }, name, h("button", { type: "submit", class: "btn primary" }, "Save"));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const n = name.value.trim();
      if (!n) { name.focus(); return; }
      const next = [...list.filter((v) => v.name !== n), { name: n, hash: location.hash || "#overview" }];
      if (store.set(KEY, next)) { toast(`Saved "${n}"`); draw(); } else toast("Saving needs browser storage, which is blocked here.");
    });
    const items = list.length ? h("ul", { class: "saved-list" }, list.map((v) => h("li", null,
      h("button", { type: "button", class: "saved-go", onclick: () => { close(false); location.hash = v.hash; } }, h("b", null, v.name), h("small", null, describe(v.hash))),
      h("button", { type: "button", class: "saved-x", "aria-label": `Delete the saved view ${v.name}`, onclick: () => {
        store.set(KEY, list.filter((x) => x !== v)); toast(`Deleted "${v.name}"`); draw(); box.querySelector("input")?.focus();
      } }, "×"))))
      : h("p", { class: "note", style: { margin: 0 } }, "No saved views yet. A saved view keeps the tab, range, page group, filters and the compare switch, in this browser only.");
    box.replaceChildren(...[heading ? h("h3", null, "Saved views") : null, items, h("p", { class: "sub", style: { margin: "6px 0 0" } }, "Save what is on screen now"), form].filter(Boolean));
  };
  draw();
}

export function saved() {
  const toggle = h("button", { type: "button", class: "btn icon", "aria-expanded": "false", "aria-haspopup": "dialog", html: STAR, "aria-label": "Saved views", title: "Saved views" });
  const pop = h("div", { class: "pop saved", hidden: true, role: "dialog", "aria-label": "Saved views" });
  const wrap = h("div", { class: "more" }, toggle, pop);
  const close = (focusBack) => { pop.hidden = true; toggle.setAttribute("aria-expanded", "false"); openPop = null; if (focusBack) toggle.focus(); };
  toggle.addEventListener("click", () => {
    if (!pop.hidden) return close(false);
    if (openPop) openPop.close(false);
    savedContent(pop, close);
    pop.hidden = false;
    // Open toward the side with room: right-aligned unless that runs off the left edge.
    pop.classList.remove("from-left");
    if (pop.getBoundingClientRect().left < 8) pop.classList.add("from-left");
    toggle.setAttribute("aria-expanded", "true");
    openPop = { wrap, close };
    pop.querySelector("input,button")?.focus();
  });
  pop.addEventListener("keydown", (e) => { if (e.key === "Escape") close(true); });
  return wrap;
}

// The same, in the drawer: from the top bar's "more" menu when the screen is too narrow for the button.
export function savedDialog() {
  const box = h("div", { class: "dw-sec dw-saved" });
  const d = openDrawer({ title: "Saved views", subtitle: "Open a tab with the period and filters you saved, or save what is on screen now.",
    size: "md", key: "saved", body: box });
  savedContent(box, (focusBack) => d.close({ focusBack }), { heading: false });
}

// "Requests · 7 days · country CA" from a saved hash, so a name is not the only clue.
function describe(hash) {
  const [tab, q = ""] = hash.replace(/^#/, "").split("?");
  const p = new URLSearchParams(q);
  const name = (S.TABS.find(([k]) => k === tab) || [null, tab])[1];
  const range = (S.RANGES.find(([k]) => k === (p.get("range") || "30d")) || [null, p.get("range")])[1];
  const bits = [name, range];
  for (const k of S.FILTERS) if (p.get(k)) bits.push(`${k} ${k === "country" ? withFlag(p.get(k)) : p.get(k)}`);
  if (p.get("view")) bits.push(p.get("view"));
  if (p.get("cmp")) bits.push("compared");
  return bits.join(", ");
}
