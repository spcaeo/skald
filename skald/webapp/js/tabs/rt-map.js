// Real time's world map: every country shaded by today's visits (one blue,
// light to dark, five steps at most), a bubble on each country with visitors
// active in the last 30 minutes (its area follows how many), hover or focus for
// the figures, and a click (Enter or Space) opens the country's detail - the
// same drill-down as any country anywhere in the app (dd=country:XX).
//
// The shapes: vendor/world-110m.js (Natural Earth 1:110m, public domain; built
// by tools/world-map.py, credited in About). A country too small for those
// shapes is a dot. Only countries with a visit today take the keyboard focus,
// in the order of their visits; the table beside the map holds the same figures.
//
//   const map = worldMap({ onPick });   map.el in the page; map.update(countries)
//   countries: {CC: {visits, active}}  (realtime.json `countries`)

import { h, n, tip, untip, reduced } from "../ui.js";
import { WORLD } from "../../vendor/world-110m.js";
import { country } from "./readers.js";

const NS = "http://www.w3.org/2000/svg";
const STEPS = 5;
const svg = (tag, attrs = {}) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, String(v));
  return el;
};

/* The shading's steps for a top value: up to five ranges [lo, hi], growing
   by the same factor (visits by country are skewed: a few countries hold most). */
export function bins(max) {
  const out = [];
  let lo = 1;
  for (let k = 1; k <= STEPS && lo <= max; k++) {
    const hi = k === STEPS ? max : Math.min(max, Math.max(lo, Math.round(max ** (k / STEPS))));
    out.push([lo, hi]);
    lo = hi + 1;
  }
  return out;
}
// The colour step (1-5) of a bin when there are `count` of them: spread over the ramp, darkest last.
export const stepOf = (i, count) => (count <= 1 ? 3 : 1 + Math.round((i * (STEPS - 1)) / (count - 1)));
export function binOf(v, list) {
  if (!(v > 0)) return -1;
  return list.findIndex(([, hi]) => v <= hi);
}
const rangeWords = ([lo, hi]) => (lo === hi ? n(lo) : `${n(lo)}–${n(hi)}`);

export function worldMap({ onPick, label = "World map of today's visits" } = {}) {
  const box = svg("svg", { viewBox: `0 0 ${WORLD.width} ${WORLD.height}`, class: "rt-svg", role: "group", "aria-label": label });
  const land = svg("g", { class: "rt-land" });
  const bubbles = svg("g", { class: "rt-bubbles", "aria-hidden": "true" });
  box.append(land, bubbles);
  const shapes = new Map();
  for (const [cc, d] of Object.entries(WORLD.paths)) {
    const p = svg("path", { d, "data-cc": cc, class: "rt-c" });
    shapes.set(cc, p);
    land.append(p);
  }
  for (const cc of WORLD.dots) {
    const [x, y] = WORLD.points[cc];
    const c = svg("circle", { cx: x, cy: y, r: 2.6, "data-cc": cc, class: "rt-c rt-dot" });
    shapes.set(cc, c);
    land.append(c);
  }
  const legend = h("div", { class: "rt-legend", "aria-hidden": "true" });
  const el = h("div", { class: "rt-map" }, h("div", { class: "rt-frame" }, box), legend);
  let data = {};

  const words = (cc) => {
    const row = data[cc] || { visits: 0, active: 0 };
    return [country(cc), `${n(row.visits)} visit${row.visits === 1 ? "" : "s"} today`, `${n(row.active)} active in the last 30 minutes`];
  };
  const show = (cc, x, y) => {
    const [name, v, a] = words(cc);
    const row = data[cc] || {};
    tip(x, y, name, [{ color: row.visits ? "var(--g-people)" : null, value: n(row.visits || 0), label: "visits today" },
      { color: row.active ? "var(--rt-live)" : null, value: n(row.active || 0), label: "active in the last 30 minutes" }]);
    return `${name}: ${v}, ${a}`;
  };
  const target = (e) => e.target.closest?.("[data-cc]");
  land.addEventListener("pointermove", (e) => { const t = target(e); if (t) show(t.dataset.cc, e.clientX, e.clientY); else untip(); });
  land.addEventListener("pointerleave", untip);
  land.addEventListener("focusin", (e) => { const t = target(e); if (!t) return; const r = t.getBoundingClientRect(); show(t.dataset.cc, r.left + r.width / 2, r.top); });
  land.addEventListener("focusout", untip);
  const pick = (t) => { if (t && data[t.dataset.cc]?.visits && onPick) { untip(); onPick(t.dataset.cc); } };
  land.addEventListener("click", (e) => pick(target(e)));
  land.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(target(e)); } });

  function update(countries) {
    data = countries || {};
    const max = Math.max(0, ...Object.values(data).map((r) => r.visits || 0));
    const list = bins(max);
    const focused = document.activeElement?.closest?.(".rt-land [data-cc]")?.dataset.cc;
    for (const [cc, el2] of shapes) {
      const row = data[cc];
      const i = binOf(row?.visits || 0, list);
      el2.setAttribute("class", `rt-c${el2.tagName === "circle" ? " rt-dot" : ""} ${i < 0 ? "s0" : `s${stepOf(i, list.length)}`}`);
      if (i >= 0) {
        el2.setAttribute("tabindex", "0");
        el2.setAttribute("role", "button");
        el2.setAttribute("aria-label", `${words(cc).join(", ")}. Open its detail.`);
      } else {
        for (const a of ["tabindex", "role", "aria-label"]) el2.removeAttribute(a);
      }
    }
    // Keyboard order: the most visits first (moving the shape in the group moves its Tab stop).
    Object.entries(data).filter(([cc, r]) => r.visits && shapes.has(cc)).sort((a, b) => b[1].visits - a[1].visits)
      .forEach(([cc]) => land.append(shapes.get(cc)));
    // Bubbles: area by visitors active now, the largest 14 units across.
    bubbles.replaceChildren();
    const live = Object.entries(data).filter(([cc, r]) => r.active > 0 && WORLD.points[cc]).sort((a, b) => b[1].active - a[1].active);
    const top = Math.max(1, ...live.map(([, r]) => r.active));
    for (const [cc, r] of live.reverse()) {
      const [x, y] = WORLD.points[cc];
      const rad = 3 + 11 * Math.sqrt(r.active / top);
      if (!reduced()) bubbles.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-ring" }));
      bubbles.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-bub" }));
    }
    if (focused) shapes.get(focused)?.focus();
    legend.replaceChildren(
      h("span", { class: "rt-lg-h" }, "Visits today"),
      ...(list.length ? list.map((b, i) => h("span", { class: "rt-lg-i" }, h("i", { class: `rt-sw s${stepOf(i, list.length)}` }), rangeWords(b)))
        : [h("span", { class: "rt-lg-i" }, h("i", { class: "rt-sw s0" }), "none yet")]),
      h("span", { class: "rt-lg-i" }, h("i", { class: "rt-sw rt-sw-bub" }), "active in the last 30 minutes (size: how many)"));
  }
  update({});
  return { el, update };
}

// For a test or a print: the countries the map can draw, as a set.
export const drawable = () => new Set(Object.keys(WORLD.points));
