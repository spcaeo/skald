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
//   const map = worldMap({ onPick, onCity });   map.el in the page; map.update(countries, cities)
//   countries: {CC: {visits, active}}  (realtime.json `countries`)
//   cities: {"Toronto, Ontario, CA": {visits, active, lat, lon}} (realtime.json `cities`,
//           only with a city file, logs.city_db)
//
// Cities (2.12.0): a dot at each city's own point (its latitude and longitude,
// placed by project(), the very Equal Earth projection tools/world-map.py drew the
// shapes with), on top of the country shading. A city with visitors active in the
// last 30 minutes pings like a country bubble (two staggered rings and a soft
// blink; a still halo with reduced motion); one with visits today only is a small
// hollow dot. A country's own bubble then stands only for its active visitors whose
// city is not recorded. Hover a dot for its figures; select it for the city's
// detail (dd=city:...). The city list beside the map holds the same figures.

import { h, n, tip, untip, reduced } from "../ui.js";
import { WORLD } from "../../vendor/world-110m.js";
import { country, countryName, cityCode, cityName } from "./readers.js";

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

/* Equal Earth (Šavrič, Patterson, Jenny 2018), as tools/world-map.py has it: the
   map is 1000 units wide, its top edge 84° N, so project(lon, lat) -> [x, y] lands
   on the shapes of vendor/world-110m.js. */
const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;
function equalEarth(lon, lat) {
  const lam = (lon * Math.PI) / 180, t = Math.asin(M * Math.sin((lat * Math.PI) / 180));
  const t2 = t * t, t6 = t2 * t2 * t2;
  return [(2 * Math.sqrt(3) * lam * Math.cos(t)) / (3 * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))),
    t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))];
}
const X_MAX = equalEarth(180, 0)[0], Y_TOP = equalEarth(0, 84)[1], SCALE = 1000 / (2 * X_MAX);
export function project(lon, lat) {
  const [x, y] = equalEarth(lon, lat);
  return [(x + X_MAX) * SCALE, (Y_TOP - y) * SCALE];
}
// The cities a map can place: a known point, not the folded tail.
export const placed = (cities) => Object.entries(cities || {}).filter(([k, r]) => k !== "(all others)" && Number.isFinite(r?.lat) && Number.isFinite(r?.lon) && r.visits > 0);

// unit: what a country's number counts ("leads", Leads & sales > Leads); live: false leaves out the "active now" bubbles and words.
export function worldMap({ onPick, onCity, onHover, label = "World map of today's visits", unit = "", live: activeNow = true } = {}) {
  const one = unit ? unit.replace(/s$/, "") : "visit", many = unit || "visits today";
  const box = svg("svg", { viewBox: `0 0 ${WORLD.width} ${WORLD.height}`, class: "rt-svg", role: "group", "aria-label": label });
  const land = svg("g", { class: "rt-land" });
  const bubbles = svg("g", { class: "rt-bubbles", "aria-hidden": "true" });
  // City dots take the pointer (hover and select); the city list is their keyboard road.
  const towns = svg("g", { class: "rt-cities", "aria-hidden": "true" });
  box.append(land, bubbles, towns);
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
    const counted = unit ? `${n(row.visits)} ${row.visits === 1 ? one : many}` : `${n(row.visits)} visit${row.visits === 1 ? "" : "s"} today`;
    return [`${country(cc)}, ${countryName(cc)}`, counted, ...(activeNow ? [`${n(row.active)} active in the last 30 minutes`] : [])];
  };
  const show = (cc, x, y) => {
    const [name, v, a] = words(cc);
    const row = data[cc] || {};
    tip(x, y, name, [{ color: row.visits ? "var(--g-people)" : null, value: n(row.visits || 0), label: many },
      ...(activeNow ? [{ color: row.active ? "var(--rt-live)" : null, value: n(row.active || 0), label: "active in the last 30 minutes" }] : [])]);
    return a ? `${name}: ${v}, ${a}` : `${name}: ${v}`;
  };
  const target = (e) => e.target.closest?.("[data-cc]");
  land.addEventListener("pointermove", (e) => { const t = target(e); if (t) show(t.dataset.cc, e.clientX, e.clientY); else untip(); });
  land.addEventListener("pointerleave", untip);
  land.addEventListener("focusin", (e) => { const t = target(e); if (!t) return; const r = t.getBoundingClientRect(); show(t.dataset.cc, r.left + r.width / 2, r.top); });
  land.addEventListener("focusout", untip);
  const pick = (t) => { if (t && data[t.dataset.cc]?.visits && onPick) { untip(); onPick(t.dataset.cc); } };
  land.addEventListener("click", (e) => pick(target(e)));
  land.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(target(e)); } });

  let places = {};
  towns.addEventListener("pointermove", (e) => {
    const k = e.target.closest?.("[data-city]")?.dataset.city;
    if (!k) return untip();
    const row = places[k] || {};
    tip(e.clientX, e.clientY, cityName(k), [{ color: "var(--g-people)", value: n(row.visits || 0), label: "visits today" },
      { color: row.active ? "var(--rt-live)" : null, value: n(row.active || 0), label: "active in the last 30 minutes" }]);
  });
  towns.addEventListener("pointerleave", () => { untip(); onHover?.(null); });
  towns.addEventListener("pointerover", (e) => { const k = e.target.closest?.("[data-city]")?.dataset.city; if (k) onHover?.(k); });
  towns.addEventListener("click", (e) => { const k = e.target.closest?.("[data-city]")?.dataset.city; if (k && onCity) { untip(); onCity(k); } });

  function update(countries, cities) {
    data = countries || {};
    places = cities || {};
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
    // Bubbles: area by visitors active now, the largest 14 units across. A country's
    // active visitors with a city on the map are that city's dot, not its bubble.
    bubbles.replaceChildren();
    towns.replaceChildren();
    const dots = placed(places);
    const inCities = {};
    for (const [k, r] of dots) { const cc = cityCode(k); if (cc) inCities[cc] = (inCities[cc] || 0) + (r.active || 0); }
    const live = Object.entries(data).map(([cc, r]) => [cc, { ...r, active: Math.max(0, (r.active || 0) - (inCities[cc] || 0)) }])
      .filter(([cc, r]) => r.active > 0 && WORLD.points[cc]).sort((a, b) => b[1].active - a[1].active);
    // With cities on the map, a country's bubble (its visitors with no city) is drawn
    // on the cities' scale, so one visitor is the same size wherever it is drawn.
    const top = Math.max(1, ...live.map(([, r]) => r.active), ...dots.map(([, r]) => r.active || 0));
    const size = (a) => (dots.length ? 2.4 + 5 * Math.sqrt(a / top) : 3 + 11 * Math.sqrt(a / top));
    for (const [cc, r] of live.reverse()) {
      const [x, y] = WORLD.points[cc];
      const rad = size(r.active);
      // Active now: two rings pinging out of the bubble, staggered, and a soft
      // blink on the bubble; with reduced motion, one still halo instead.
      bubbles.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-ring" }));
      if (!reduced()) bubbles.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-ring rt-ring2" }));
      bubbles.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-bub" }));
    }
    // Cities: the quiet ones first (under), then the active ones, the most active on top.
    const order = [...dots].sort((a, b) => (a[1].active || 0) - (b[1].active || 0) || a[1].visits - b[1].visits);
    for (const [k, r] of order) {
      const [x, y] = project(r.lon, r.lat);
      const g = svg("g", { class: "rt-town", "data-city": k });
      if (r.active > 0) {
        const rad = size(r.active);
        g.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-ring" }));
        if (!reduced()) g.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-ring rt-ring2" }));
        g.append(svg("circle", { cx: x, cy: y, r: rad, class: "rt-bub rt-cbub" }));
      } else {
        g.append(svg("circle", { cx: x, cy: y, r: 2.6, class: "rt-cdot" }));
      }
      // A target larger than the mark, so a small dot is easy to point at.
      g.append(svg("circle", { cx: x, cy: y, r: 7, class: "rt-hit" }));
      towns.append(g);
    }
    if (focused) shapes.get(focused)?.focus();
    legend.replaceChildren(
      h("span", { class: "rt-lg-h" }, unit ? many.replace(/^./, (c) => c.toUpperCase()) : "Visits today"),
      ...(list.length ? list.map((b, i) => h("span", { class: "rt-lg-i" }, h("i", { class: `rt-sw s${stepOf(i, list.length)}` }), rangeWords(b)))
        : [h("span", { class: "rt-lg-i" }, h("i", { class: "rt-sw s0" }), "none yet")]),
      activeNow ? h("span", { class: "rt-lg-i" }, h("i", { class: "rt-sw rt-sw-bub" }), "active in the last 30 minutes (size: how many)") : "",
      dots.length ? h("span", { class: "rt-lg-i" }, h("i", { class: "rt-sw rt-sw-town" }), "a city with visits today") : "");
  }
  // A city to make stand out (Overview's live list: a row under the pointer pulses its city), or none.
  function hot(k) {
    for (const g of towns.querySelectorAll(".rt-town")) g.classList.toggle("rt-hot", !!k && g.dataset.city === k);
  }
  update({});
  return { el, update, hot };
}

// For a test or a print: the countries the map can draw, as a set.
export const drawable = () => new Set(Object.keys(WORLD.points));
