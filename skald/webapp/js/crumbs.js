// The breadcrumb line (T9): the path someone took through the dashboard in this tab,
// each step a link back to the exact view it was (period, filters, sort, what was open),
// and "← Back to <the step before>". The address stays the source of truth: a step is
// the address it had; the trail only remembers which addresses came before, in this
// tab's sessionStorage (never sent, gone with the tab).
//
//   a place     where a step is: the tab, and what is open in it (a page's story, the
//               drill-down's steps, a to-do's list, a visitor's or a lead's drawer...).
//               A change in place (a sort, a filter, a period) keeps the step and takes the
//               new address; a new place adds a step; a place already on the trail (Back,
//               a crumb, a link to it) cuts the trail back to it. A move from one tab to
//               another of the same section, with nothing open on either, replaces the step
//               (the tab strip is a move sideways, not down).
//   a fresh link a copied address opened in a new tab starts its own trail from the
//               address alone: section › tab, then the item (Traffic › Pages / /pricing/).
//               A reload or Back into the page keeps the tab's trail.
//   scrolling   each step keeps where the page was scrolled; Back, Forward, a crumb or a
//               reload put it back once the tab is drawn (history.scrollRestoration is
//               manual: the page draws after the browser would have scrolled). The last 40
//               addresses' scrolls are kept too, so Forward to a step the trail had cut
//               finds its place.
//
// Pure parts (placeOf, note, fromUrl) take no DOM, so tests/js/crumbs.mjs runs them in node.

import { h } from "./ui.js";
import * as S from "./state.js";
import { chainOf, said } from "./drill.js";
import { withUrl } from "./urlactions.js";

export const STORE = "ti-crumbs";
export const MOST = 12;          // steps kept
const SEEN = 40;                 // addresses whose scroll is kept, for Forward
const SHOW = 5;                  // steps shown before the middle folds into "…"

// A record open over the tab: [key, how it is said].
const RECORDS = [
  ["vis", (v) => { const d = String(v).split(".")[0]; return /^\d{4}-\d\d-\d\d$/.test(d) ? `A visit on ${shortDay(d)}` : "A visit"; }],
  ["lead", (v) => `Lead ${v}`], ["conv", () => "A conversion"], ["req", () => "A request"],
  ["cohort", (v) => `Cohort of ${shortDay(String(v).split(".")[0])}`],
  ["sq", (v) => { const i = String(v).indexOf(":"); return i > 0 ? `Search: ${String(v).slice(i + 1)}` : "Search"; }],
  ["list", (v) => ({ leftout: "Left out", "conv-cancelled": "Cancelled", "conv-removed": "Removed", "conv-test": "Test" }[v] || "A list")],
  ["scan", () => "A scanner"], ["ans", (v) => `Answer ${v}`], ["who", () => "Find a person"],
];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function shortDay(iso) {
  const m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(iso || "");
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}` : iso;
}

/* Where a state is: {key, parts, item}. parts are said: ["Traffic", "Pages", "/pricing/"]. */
export function placeOf(s, m = null) {
  const sec = S.sectionOf(s.tab);
  const head = sec ? [sec.name, S.nameOf(s.tab)] : S.inSettings(s.tab) ? ["Settings", S.nameOf(s.tab)] : [S.nameOf(s.tab)];
  const items = [], keys = [s.tab];
  if (s.page) { items.push(s.page); keys.push(`page=${s.page}`); }
  if (s.todo) {
    const t = (m?.x?.todos?.todos || []).find((x) => x.id === s.todo);
    items.push(t ? t.title : "A to-do"); keys.push(`todo=${s.todo}`);
  }
  if (s.part && s.tab === "help") { items.push(String(s.part).replace(/[-_]/g, " ")); keys.push(`part=${s.part}`); }
  for (const [dim, value] of chainOf(s)) { items.push(`${dimName(dim)}: ${safeSaid(dim, value)}`); keys.push(`dd=${dim}:${value}`); }
  for (const [k, say] of RECORDS) if (s[k]) { items.push(say(s[k])); keys.push(`${k}=${s[k]}`); }
  return { key: keys.join("|"), parts: [...head, ...items], item: items.length > 0, tab: s.tab, section: sec?.key || null };
}
const DIM_NAMES = { country: "Country", city: "City", path: "Page", landing: "Landing page", source: "Source", assistant: "AI assistant", referrer: "Referring site",
  campaign: "Campaign", device: "Device", browser: "Browser", os: "System", hour: "Hour", ip: "Address", status: "Status", bot: "Bot or crawler" };
const dimName = (d) => DIM_NAMES[d] || d;
function safeSaid(dim, value) {
  try { return said(dim, value); } catch { return value; }
}

/* The trail after a visit to `place` at `hash` (pure). */
export function note(trail, place, hash) {
  const steps = Array.isArray(trail) ? trail.slice() : [];
  const step = { key: place.key, hash, parts: place.parts, item: place.item, tab: place.tab, section: place.section, scroll: 0 };
  const i = steps.findIndex((x) => x.key === place.key);
  if (i >= 0) return [...steps.slice(0, i), { ...steps[i], hash, parts: place.parts }];
  const last = steps[steps.length - 1];
  // Sideways: one tab of a section to another, nothing open on either.
  if (last && !last.item && !place.item && last.section && last.section === place.section) return [...steps.slice(0, -1), step];
  return [...steps, step].slice(-MOST);
}

/* A trail from the address alone, for a link opened fresh: the tab, then what is open. */
export function fromUrl(s, m, hashFor) {
  const place = placeOf(s, m);
  const here = { key: place.key, hash: hashFor(s), parts: place.parts, item: place.item, tab: place.tab, section: place.section, scroll: 0 };
  if (!place.item) return [here];
  const bare = { ...s, page: "", todo: "", dd: "", part: "", ...Object.fromEntries(RECORDS.map(([k]) => [k, ""])) };
  const top = placeOf(bare, m);
  return [{ key: top.key, hash: hashFor(bare), parts: top.parts, item: false, tab: top.tab, section: top.section, scroll: 0 }, here];
}

/* What a crumb says: its parts after those it shares with the step before it. */
export function crumbWords(steps, i) {
  const p = steps[i].parts, q = i > 0 ? steps[i - 1].parts : [];
  let k = 0;
  while (k < p.length - 1 && k < q.length && p[k] === q[k]) k += 1;
  return p.slice(k).join(" › ");
}

// ------------------------------------------------------------------ the tab's trail
let TRAIL = null, restoreNext = false, saving = 0, SCROLLS = new Map();
const storage = () => { try { return globalThis.sessionStorage || null; } catch { return null; } };
function load() {
  try { const got = JSON.parse(storage()?.getItem(STORE) || "null"); return Array.isArray(got) ? got : []; } catch { return []; }
}
function write() {
  try {
    storage()?.setItem(STORE, JSON.stringify(TRAIL || []));
    storage()?.setItem(`${STORE}-y`, JSON.stringify([...SCROLLS]));
  } catch { /* storage blocked: the trail lives in memory */ }
}
function save() {
  clearTimeout(saving);
  saving = setTimeout(write, 50);
}
function seen(hash, y) {
  SCROLLS.delete(hash);
  SCROLLS.set(hash, y);
  while (SCROLLS.size > SEEN) SCROLLS.delete(SCROLLS.keys().next().value);
}
function navType() {
  try { return globalThis.performance?.getEntriesByType?.("navigation")?.[0]?.type || "navigate"; } catch { return "navigate"; }
}

/* Once, at boot: the stored trail on a reload or Back into the page, else a fresh one. */
export function start() {
  const kind = navType();
  TRAIL = kind === "reload" || kind === "back_forward" ? load() : null;
  try { SCROLLS = new Map(TRAIL ? JSON.parse(storage()?.getItem(`${STORE}-y`) || "[]") : []); } catch { SCROLLS = new Map(); }
  restoreNext = kind === "reload" || kind === "back_forward";
  try { if ("scrollRestoration" in history) history.scrollRestoration = "manual"; } catch { /* old browser */ }
  addEventListener("popstate", () => { restoreNext = true; });
  let ticking = false;
  addEventListener("scroll", () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      // While a step's scroll is being put back, the page's own jumps (a shorter page drawn) are not the reader's.
      if (restoreNext) return;
      const last = TRAIL?.[TRAIL.length - 1];
      if (last && last.hash === location.hash) { last.scroll = Math.round(scrollY); seen(last.hash, last.scroll); save(); }
    });
  }, { passive: true });
  addEventListener("pagehide", write);
}

/* The trail with the state on screen noted; a fresh tab starts from the address. */
export function visit(s, m) {
  if (TRAIL === null) TRAIL = fromUrl(s, m, S.hashFor);
  else TRAIL = note(TRAIL, placeOf(s, m), location.hash || S.hashFor(s));
  save();
  return TRAIL;
}
export const trail = () => TRAIL || [];

/* Go to a step: its address, a new entry; its scroll comes back once drawn. */
function go(step) {
  restoreNext = true;
  if (step.hash === location.hash) return;
  history.pushState(null, "", step.hash);
  S.emit();
}

/* After a draw: Back, Forward, a crumb or a reload put the step's scroll back. */
export function restore() {
  // A frame later: the popstate that asked for it has reached every listener by then.
  requestAnimationFrame(() => {
    if (!restoreNext) return;
    restoreNext = false;
    const last = TRAIL?.[TRAIL.length - 1];
    const y = last && last.hash === location.hash ? last.scroll || SCROLLS.get(last.hash) || 0 : null;
    if (y == null) return;
    let moved = false;
    const put = () => {
      if (moved && Math.abs(scrollY - y) > 40) return;      // the reader scrolled since: leave it
      if (Math.abs(scrollY - y) > 2 && document.documentElement.scrollHeight - innerHeight >= y - 2) { scrollTo({ top: y, behavior: "auto" }); moved = true; }
    };
    put();
    setTimeout(put, 300);        // a part drawn later (a page's story, a chart) made the page taller
    setTimeout(put, 900);
  });
}

/* The line over the tab, or null when there is nothing to go back to. */
export function crumbLine(m, s) {
  const steps = visit(s, m);
  const box = h("nav", { class: "crumbs", "aria-label": "Breadcrumb", id: "crumbs" });
  draw(box, steps, false);
  return steps.length > 1 || steps[0]?.item ? box : h("nav", { class: "crumbs", id: "crumbs", hidden: true, "aria-label": "Breadcrumb" });
}
/* A drawer opened or closed over the tab (no redraw): the trail and the line, in place. */
export function crumbUpdate(m, s) {
  const steps = visit(s, m);
  const old = typeof document !== "undefined" ? document.getElementById("crumbs") : null;
  if (!old) return;
  old.hidden = !(steps.length > 1 || steps[0]?.item);
  draw(old, steps, false);
}

function draw(box, steps, open) {
  const back = steps.length > 1 ? steps[steps.length - 2] : null;
  const link = (st, i) => {
    const a = h("a", { href: st.hash, title: st.parts.join(" › ") }, crumbWords(steps, i));
    a.addEventListener("click", (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; e.preventDefault(); go(st); });
    return a;
  };
  const items = steps.map((st, i) => (i === steps.length - 1
    ? h("li", null, withUrl(h("span", { class: "cr-now", "aria-current": "page" }, crumbWords(steps, i)), location.href, { label: "this exact view" }))
    : h("li", null, link(st, i))));
  let shown = items;
  if (!open && items.length > SHOW) {
    const more = h("button", { type: "button", class: "cr-more", "aria-label": `Show all ${items.length} steps` }, "…");
    more.addEventListener("click", () => draw(box, steps, true));
    shown = [items[0], h("li", null, more), ...items.slice(-(SHOW - 2))];
  }
  const backBtn = back ? h("a", { class: "cr-back", href: back.hash, title: back.parts.join(" › ") }, `← Back to ${back.parts[back.parts.length - 1]}`) : null;
  backBtn?.addEventListener("click", (e) => { e.preventDefault(); go(back); });
  box.replaceChildren(...[backBtn, h("ol", null, shown)].filter(Boolean));
}
