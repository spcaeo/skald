// Overview > Summary in Live mode (2.20): "What visitors are doing now", under the full-width
// map. One block, two parts side by side (stacked on a phone):
//
//   left    the 5 visitors with the newest activity (active in the last 30 minutes): flag and
//           city, device, source, and their pages in order as a path, the page they are on now
//           highlighted ("now on /pricing · 20 s ago"); a long path folds in the middle, whole
//           in its tooltip. A row opens the visitor drawer. Live: on each answer (Real time's,
//           every 15 seconds, realtime.js follow()) a new visitor slides in at the top, one who
//           moved gets the new page appended, one who went quiet fades out (no motion with
//           prefers-reduced-motion)
//   right   "Pages read in the last 30 minutes": Real time's page figure as it was (its count
//           and its audit unchanged), top pages with bars. A page narrows the list to the
//           visitors who read it (a second press opens the page's detail)
//
// The rows are the snapshot's `doing` (realtime.py; recounted by audit_realtime.py): labels
// and paths only, as the newest visits always were. Nothing here is counted anew.
//
// The drill-down (dd=, e.g. country:CA) narrows the live list too: the visitors matching it,
// from the same rows. A kind the rows do not carry says so in one line instead of showing
// everyone silently. The pages figure is not split by it, and says so.
//
// Map and list: a row under the pointer pulses its city on the map (hot()), and a city under
// the pointer marks its rows (mark()).

import { h, n, reduced } from "../ui.js";
import * as S from "../state.js";
import { chainOf, open as openDrill, said } from "../drill.js";
import { flagEl, country, countryName, cityName } from "./readers.js";
import { mark } from "../icons.js";
import { shown, assistantName } from "../labels.js";
import { openNewest } from "./realtime.js";
import { goLink, cardHead } from "./ov-today-bits.js";

export const SHOWN = 5;
const people = (B) => (B && (B.people_state === "ok" || B.people_state === "stale") ? B.people : null);
export const keyOf = (v) => `${v.start}|${v.seq ?? ""}|${v.country}|${v.landing}`;

/* What a drill-down step means for one live row; null: the rows do not carry it. */
const MATCH = {
  country: (v, x) => v.country === x,
  city: (v, x) => v.city === x,
  source: (v, x) => v.source === x,
  device: (v, x) => v.device === x,
  landing: (v, x) => v.landing === x,
  path: (v, x) => (v.trail || []).includes(x),
  assistant: (v, x) => v.via === x,
  referrer: (v, x) => v.via === x,
};

/* The live rows the drill-down keeps, and the steps it could not apply. */
export function narrow(rows, chain) {
  const can = chain.filter(([d]) => MATCH[d]), cannot = chain.filter(([d]) => !MATCH[d]);
  return { rows: (rows || []).filter((v) => can.every(([d, x]) => MATCH[d](v, x))), can, cannot };
}

/* A path, folded in the middle when long: / → … → /pricing → /book-a-demo. */
export function folded(trail, keep = 4) {
  const t = trail || [];
  return t.length <= keep ? t : [t[0], "…", ...t.slice(-(keep - 2))];
}

const ago = (last, until) => {
  const s = Math.max(0, Math.round((Date.parse(until) - Date.parse(last)) / 1000));
  return !Number.isFinite(s) ? "" : s < 60 ? `${s} s ago` : `${Math.round(s / 60)} min ago`;
};

function steps(v, grew) {
  const t = v.trail?.length ? v.trail : v.landing ? [v.landing] : [];
  const f = folded(t);
  const out = [];
  f.forEach((p, i) => {
    if (i) out.push(h("i", { class: "td-arrow", "aria-hidden": "true" }, "→"));
    const last = i === f.length - 1;
    out.push(p === "…" ? h("span", { class: "td-st gap" }, "…") : h("span", { class: `td-st${last ? " now" : ""}${last && grew ? " td-step-new" : ""}` }, p));
  });
  return h("span", { class: "td-steps", title: t.join(" → ") }, out);
}

function rowOf(m, v, until, cls, grew) {
  const ai = v.source === "AI assistant";
  const who = v.via ? (ai ? assistantName(v.via) : v.via) : shown(v.source) || "Source not recorded";
  const place = v.city ? String(v.city).split(", ")[0] : country(v.country);
  const t = v.trail?.length ? v.trail : [v.landing].filter(Boolean);
  const openIt = () => openNewest(m, v);
  return h("li", { class: cls || null, "data-k": keyOf(v), "data-city": v.city || null },
    h("div", { class: "td-prow", role: "button", tabindex: "0", "aria-label": `Open this visitor: ${v.city ? cityName(v.city) : countryName(v.country)}, from ${who}, ${t.length} page${t.length === 1 ? "" : "s"}, now on ${t[t.length - 1] || "a page"}`,
      onclick: openIt, onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openIt(); } } },
      h("span", { class: "td-pw" },
        h("span", { class: "td-vc", title: countryName(v.country) }, flagEl(v.country), h("b", null, place || "Not recorded")),
        v.device ? h("span", { class: "td-vd", title: v.device }, mark("device", v.device) || v.device) : null,
        h("span", { class: "td-vs" }, mark(ai || v.via ? "referrer" : "source", v.via || v.source), h("b", null, who))),
      steps(v, grew),
      h("span", { class: "td-pnow" }, v.active === "5" ? h("i", { class: "td-pdot", "aria-hidden": "true" }) : null,
        `now on ${t[t.length - 1] || "a page"}`, v.last && until ? ` · ${ago(v.last, until)}` : "")));
}

export function doingCard(m, rt, first, { onHover } = {}) {
  const list = h("ol", { class: "td-paths", "aria-live": "polite" });
  const note = h("p", { class: "td-note", hidden: true });
  const chip = h("div", { class: "td-pick", hidden: true });
  const pages = h("div", { class: "td-pg" });
  const held = h("div", { class: "td-held", role: "status", hidden: true });
  const el = h("section", { class: "td-card td-doing", "aria-labelledby": "td-doing-h" },
    cardHead("td-doing-h", "What visitors are doing now", "The visitors with the newest activity, and the pages they read. Select one for its journey.", goLink("traffic/visitors", "See every visit")),
    held, note,
    h("div", { class: "td-dg" }, h("div", { class: "td-dl" }, chip, list), pages));
  let prev = null;            // key -> pages shown, at the last draw
  let pick = "";              // a page chosen on the right: the visitors who read it
  let last = null;
  list.addEventListener("pointerover", (e) => { const li = e.target.closest?.("li[data-city]"); onHover?.(li ? li.dataset.city : null); });
  list.addEventListener("pointerleave", () => onHover?.(null));

  function draw(B) {
    last = B;
    const P = people(B);
    const chain = chainOf(S.read());
    const got = narrow(P?.doing || [], chain);
    const rows = (pick ? got.rows.filter((v) => (v.trail || []).includes(pick)) : got.rows).slice(0, SHOWN);
    const words = [];
    if (got.can.length) words.push(`Only the visitors matching ${got.can.map(([d, x]) => said(d, x)).join(", ")}: ${n(rows.length)} shown.`);
    if (got.cannot.length) words.push("Live list shows every visitor: this filter can't apply to it.");
    note.hidden = !words.length;
    note.textContent = words.join(" ");
    chip.hidden = !pick;
    chip.replaceChildren(...(pick ? [h("span", { class: "chip" }, "Read ", h("b", null, pick),
      h("button", { type: "button", "aria-label": "Show every visitor again", onclick: () => { pick = ""; draw(last); } }, "×"))] : []));
    const motion = !reduced();
    const before = prev;
    const old = new Map([...list.children].filter((li) => li.dataset?.k).map((li) => [li.dataset.k, li]));
    prev = new Map(rows.map((v) => [keyOf(v), (v.trail || []).length]));
    const drawn = rows.map((v, i) => {
      const k = keyOf(v);
      const fresh = motion && before && !before.has(k);
      const grew = motion && before && before.has(k) && before.get(k) < (v.trail || []).length;
      const cls = fresh ? "td-in" : motion && !before && first && i < 3 ? `td-rise td-rise${i}` : "";
      return rowOf(m, v, P?.until || B?.until, cls, grew);
    });
    // A visitor who went quiet fades out, then leaves.
    const gone = motion && before ? [...before.keys()].filter((k) => !prev.has(k) && old.has(k)).map((k) => { const li = old.get(k); li.classList.add("td-out"); return li; }) : [];
    if (gone.length) setTimeout(() => gone.forEach((li) => li.remove()), 450);
    list.replaceChildren(...(drawn.length || gone.length ? [...drawn, ...gone]
      : [h("li", { class: "empty" }, !P ? "The visitors now appear with the next live count (every 2 minutes)."
        : got.can.length || pick ? "No visitor matching this is on the site now." : "Nobody has been on the site in the last 30 minutes.")]));
    drawPages(P, chain);
  }

  function drawPages(P, chain) {
    const read = Object.entries(P?.pages || {}).filter(([k, v]) => v > 0 && k !== "(all others)").sort((a, b) => b[1] - a[1]).slice(0, 6);
    const most = Math.max(1, ...read.map(([, v]) => v));
    pages.replaceChildren(...(P ? [h("div", { class: "td-pgh" }, h("b", null, "Pages read in the last 30 minutes"),
      h("span", null, `${n(P.page_views || 0)} page view${P.page_views === 1 ? "" : "s"} by visitors`)),
    ...(read.length ? read.map(([path, v]) => h("div", { class: `td-pgr${pick === path ? " on" : ""}` },
      h("button", { type: "button", class: "td-path", title: pick === path ? `${path}: press again for its detail` : `${path}: the visitors who read it`,
        onclick: () => { if (pick === path) openDrill("path", path); else { pick = path; draw(last); } } }, middle(path)),
      h("span", { class: "td-pgb", "aria-hidden": "true" }, h("i", { style: { width: `${(v / most) * 100}%` } })), h("span", { class: "td-num" }, n(v))))
      : [h("p", { class: "empty" }, "No page read in the last 30 minutes.")]),
    chain.length ? h("p", { class: "td-note" }, "These counts are every visitor's: they are not split by the filter.") : null].filter(Boolean) : []));
  }

  function paused(on) {
    held.hidden = !on;
    held.replaceChildren(h("span", null, "Paused: the visitors now, the map and this list hold still."),
      h("button", { type: "button", class: "btn", onclick: () => rt.pause(false) }, "Resume"));
  }
  // A city under the pointer on the map: its rows stand out.
  function marked(k) { for (const li of list.children) li.classList?.toggle("td-hot", !!k && li.dataset?.city === k); }
  return { el, draw, paused, mark: marked };
}

// A long path cut in the middle: /healthcare-software-dev…/offshore-healthcare (whole in the tooltip).
export function middle(path, max = 46) {
  const p = String(path);
  if (p.length <= max) return p;
  const head = Math.ceil((max - 1) * 0.55), tail = max - 1 - head;
  return `${p.slice(0, head)}…${p.slice(-tail)}`;
}
