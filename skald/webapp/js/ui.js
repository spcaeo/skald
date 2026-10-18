// Small DOM and formatting helpers shared by every tab.
// Every label that came from the logs (paths, sites, names) goes in through
// textContent or esc(), never as markup. A stored label is drawn in the words
// labels.js gives it ("Direct or unknown" is shown as "Direct").

import { shownText } from "./labels.js";
import { tipBox } from "./place.js";

export const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;  // trusted markup only (our own SVG)
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") {
      for (const [prop, val] of Object.entries(v)) {
        if (prop.startsWith("--")) el.style.setProperty(prop, val);
        else el.style[prop] = val;
      }
    }
    else el.setAttribute(k, v === true ? "" : k === "title" || k === "aria-label" ? shownText(String(v)) : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(shownText(String(kid))));
  }
  return el;
}

export function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const nf = new Intl.NumberFormat("en-US");
export const n = (v) => (v == null ? "-" : nf.format(Math.round(v)));
export function compact(v) {
  if (v == null) return "-";
  if (Math.abs(v) < 10000) return n(v);
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
}
export const pct = (part, whole) => (whole ? `${Math.round((part / whole) * 100)}%` : "-");
export function pct1(part, whole) {
  if (!whole) return "-";
  const p = (part / whole) * 100;
  return p > 0 && p < 1 ? "<1%" : `${Math.round(p)}%`;
}
// A share of a tiny base misleads (one lead is "100%"): below MIN_SHARE, the
// same minimum as conversions' min_rate, only the counts are shown.
export const MIN_SHARE = 10;
export const share = (part, whole) => (whole >= MIN_SHARE ? pct1(part, whole) : "");

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
// Days are ISO strings (YYYY-MM-DD) in the report's time zone; never parse them as UTC instants.
export function parseDay(iso) { const [y, m, d] = iso.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); }
export function isoDay(dt) { return dt.toISOString().slice(0, 10); }
export function addDays(iso, k) { const d = parseDay(iso); d.setUTCDate(d.getUTCDate() + k); return isoDay(d); }
export function dayDiff(a, b) { return Math.round((parseDay(b) - parseDay(a)) / 864e5); }
export function short(iso) { const d = parseDay(iso); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`; }
export function long(iso) { const d = parseDay(iso); return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; }
export function weekday(iso) { return DAYS[parseDay(iso).getUTCDay()]; }
// "16:40" from an ISO timestamp that carries its own offset: the wall clock it was written in.
export function clock(ts, seconds = false) {
  const m = /T(\d\d):(\d\d)(?::(\d\d))?/.exec(ts || "");
  return m ? (seconds && m[3] ? `${m[1]}:${m[2]}:${m[3]}` : `${m[1]}:${m[2]}`) : "";
}
/* A moment written in any offset (the server writes some in UTC), told as
   the site's wall clock: "14:05", or "6 Oct 14:05" with the date. */
export function zoned(ts, tz, withDate = false) {
  const t = Date.parse(ts || "");
  if (!t) return "";
  try {
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: tz, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
      .formatToParts(new Date(t)).map((p) => [p.type, p.value]));
    return withDate ? `${parts.day} ${parts.month} ${parts.hour}:${parts.minute}` : `${parts.hour}:${parts.minute}`;
  } catch { return clock(ts); }
}

export function duration(sec) {
  if (sec == null) return "-";
  if (sec < 1) return "under 1 s";
  if (sec < 60) return `${Math.round(sec)} s`;
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return m < 60 ? `${m} min${s ? ` ${s} s` : ""}` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

// A number that counts up to its value once, the first time it is drawn.
export function counter(value, fmt = n) {
  const el = h("span", { class: "num" }, fmt(value));
  if (value == null || reduced() || !value) return el;
  el.dataset.to = value;
  const start = performance.now(), dur = 700 + Math.min(500, Math.log10(value + 1) * 150);
  const tick = (t) => {
    const k = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(value * e);
    if (k < 1 && el.isConnected !== false) requestAnimationFrame(tick);
    else el.textContent = fmt(value);
  };
  requestAnimationFrame(tick);
  return el;
}

// change() from kpi.py: direction only, never good or bad. None = not comparable.
export function change(cur, prev) {
  if (cur == null) return ["", "not recorded"];
  if (prev == null) return ["", "not comparable"];
  if (prev === 0) return cur === 0 ? ["", "no change"] : ["▲", "new"];
  const p = ((cur - prev) / prev) * 100;
  if (Math.round(p) === 0) return ["", "about the same"];
  return [p > 0 ? "▲" : "▼", `${Math.abs(p).toFixed(0)}%`];
}

// One tooltip for the whole app. rows: [{key colour, value, label}]
// (Made again if a closed drawer took it away with it.)
const tipEl = () => document.getElementById("tip")
  || document.body.appendChild(h("div", { class: "tip", id: "tip", role: "status", "aria-live": "polite", hidden: true }));
// An open drawer (a modal <dialog>) sits in the top layer, over anything outside it:
// the tooltip moves into the topmost one while it is open, and back to the page after.
function tipHost(el) {
  let modal = null;
  try { modal = [...document.querySelectorAll("dialog:modal")].pop() || null; } catch { /* no :modal */ }
  const host = modal || document.body;
  if (el.parentNode !== host) host.append(el);
  // A dialog sliding in (a transform) is the tooltip's frame: measure from its corner.
  if (!modal || getComputedStyle(modal).transform === "none") return [0, 0];
  const r = modal.getBoundingClientRect();
  return [r.left, r.top];
}
export function tip(x, y, head, rows) {
  const el = tipEl();
  el.replaceChildren(h("div", { class: "t-h" }, head),
    ...rows.map((r) => h("div", { class: "t-r" },
      r.color ? h("span", { class: "t-k", style: { background: r.color } }) : null,
      h("b", null, r.value), h("span", null, r.label))));
  const [ox, oy] = tipHost(el);
  // Measured at the corner, so its last place near an edge does not squeeze it.
  Object.assign(el.style, { left: "0px", top: "0px", transform: "none" });
  el.hidden = false;
  const box = tipBox(x, y, el.offsetWidth, el.offsetHeight, innerWidth, innerHeight);
  el.style.left = `${box.left - ox}px`;
  el.style.top = `${box.top - oy}px`;
}
export function untip() { const el = tipEl(); if (el) el.hidden = true; }

export function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("on");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("on"), 2600);
}

export function section(title, sub, ...body) {
  return h("section", { class: "s" }, h("h2", null, title), sub ? h("p", { class: "sub" }, sub) : null, ...body);
}

export function stateNote(text, bad = false) {
  return h("div", { class: `state${bad ? " bad" : ""}`, role: bad ? "alert" : null, html: ICON.info }, h("div", null, text));
}

export const ICON = {
  info: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 7v4M8 4.6v.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  check: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor" opacity=".16"/><path d="M4.8 8.2l2.1 2.1 4.3-4.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  cross: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7" fill="currentColor" opacity=".16"/><path d="M5.5 5.5l5 5m0-5l-5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  refresh: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13 8a5 5 0 1 1-1.5-3.6M13 2.5v3h-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  download: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v8m-3.2-3.2L8 10.5l3.2-3.2M3 13.5h10" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  filter: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 4h11M4.5 8h7M6.5 12h3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
};
