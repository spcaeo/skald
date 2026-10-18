// The visitor drawer's journey (2.13, the owner's approved layout): each visit a card,
// newest first, its steps a vertical timeline - where it came from, each page in
// order with the time between pages on the line, and how it ended - and between
// two visits how long after ("12 days later") on a dotted line.
//
// The same visual language as the Sankey (sankey.js): where visits came from in the
// people blue, pages in the page green, leaving in grey; a form, a lead or a booking
// in the leads colour. On open the steps rise in one by one and the lines grow; the
// visit still under way pulses like the real-time map's active countries. Replay plays
// the visits again, oldest first, with their real relative timing compressed (1 second
// per minute, at most 4 seconds a visit). Under prefers-reduced-motion all of it is still.
//
// Only what was seen: the steps are the visit's own kept pages; a visit seen only by
// the page script (a visitor ID's page views) says so. A page opens its page detail;
// hover or focus shows the page, its time and its offset.

import { h, duration, reduced, tip, untip } from "./ui.js";
import { pagesWords } from "./visitpages.js";
import { time as tzTime, when } from "./tz.js";
import { shown } from "./labels.js";
import { mark } from "./icons.js";
import { open } from "./drill.js";

const PER_MINUTE = 1000;      // replay: 1 s per minute of the real visit
const CAP = 4000;             // ... at most 4 s for one visit
const STEP = 70;              // the opening stagger between steps, ms

const daysWords = (a, b) => {
  const ms = b - a;
  if (!(ms > 0)) return "";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins} min later`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} later`;
  const d = Math.round(hours / 24);
  return `${d} day${d === 1 ? "" : "s"} later`;
};

/* A source node's words: the site or assistant that sent it, else its type. */
export function sourceWords(v) {
  return v.via || shown(v.source) || "Not recorded";
}

function withTip(el, head, rows) {
  const show = () => { const r = el.getBoundingClientRect(); tip(r.left + r.width / 2, r.top, head, rows); };
  el.addEventListener("mouseenter", show);
  el.addEventListener("focus", show);
  el.addEventListener("mouseleave", untip);
  el.addEventListener("blur", untip);
  return el;
}

/* One step of the timeline: a dot on the rail and its node. */
function step(kind, node) {
  return h("li", { class: `jm-s ${kind}` }, h("span", { class: "jm-rail", "aria-hidden": "true" }, h("span", { class: "jm-dot" })), node);
}
/* The line between two steps, with the time between them when known. */
function gap(words) {
  return h("li", { class: `jm-s jm-c${words ? "" : " bare"}`, "aria-hidden": words ? null : "true" },
    h("span", { class: "jm-rail", "aria-hidden": "true" }, h("span", { class: "jm-ln" })), words ? h("small", { class: "jm-t" }, words) : null);
}

/* One visit's steps. v: {start, source, via, campaign, trail: [{path, page, at, times, nf}],
   seconds, stop, kind, first, active, endNode: {kind, words, detail}, touch (words or "")}. */
function steps(v) {
  const trail = v.trail || [];
  const icon = v.source === "AI assistant" && v.via ? mark("assistant", v.via) || mark("source", v.source) : v.via ? mark("referrer", v.via) : mark("source", v.source);
  const sub = v.touch || (v.via ? shown(v.source) : !v.via && shown(v.source) === "Direct" ? "no referring site sent" : "");
  const src = withTip(h("span", { class: "jm-n from", tabindex: "0", "aria-label": `Came from ${[sourceWords(v), sub].filter(Boolean).join(", ")}` },
    h("span", { class: "jm-w" }, icon, h("b", null, sourceWords(v))), sub ? h("small", null, sub) : null),
  "Came from", [{ label: [sourceWords(v), v.via ? shown(v.source) : "", v.campaign ? `campaign ${v.campaign}` : ""].filter(Boolean).join(", ") }, ...(v.touch ? [{ label: v.touch }] : [])]);
  const out = [step("from", src)];
  trail.forEach((p, i) => {
    const prev = trail[i - 1];
    out.push(gap(i && p.at != null && prev?.at != null ? duration(Math.max(0, p.at - prev.at)) : ""));
    const at = p.at != null ? `+${p.at < 1 ? "0 s" : duration(p.at)} from the first request` : "time in the visit not kept";
    const btn = withTip(h("button", { type: "button", class: `jm-n pg${p.page === false ? " app" : ""}${p.nf ? " nf" : ""}`,
      "aria-label": `Page ${p.path}, ${at}. Opens its page detail.` }, mark("path", p.path), h("span", { class: "jm-w" }, p.path), p.times > 1 ? h("small", null, `×${p.times}`) : null),
    p.path, [{ label: at }, ...(p.page === false ? [{ label: "seen in the browser: moved inside the site, no page loaded from the server" }] : []), ...(p.nf ? [{ label: "page not found (404)" }] : [])]);
    btn.addEventListener("click", () => { untip(); open("path", p.path); });
    out.push(step(`pg${p.nf ? " nf" : ""}`, btn));
  });
  out.push(gap(""));
  const end = v.endNode || { kind: "left", words: v.active ? "still here" : "left" };
  const lead = ["form", "lead", "booked"].includes(end.kind);
  const words = end.words.charAt(0).toUpperCase() + end.words.slice(1);
  out.push(step(`end ${end.kind}`, withTip(h("span", { class: `jm-n end ${end.kind}`, tabindex: "0", "aria-label": `Ended: ${end.detail || end.words}` },
    lead ? h("span", { class: "jm-ok", "aria-hidden": "true" }, "✓") : null, words), "Ended", [{ label: end.detail || end.words }])));
  return out;
}

function header(v) {
  const w = when(v.start);
  return h("div", { class: "jm-h" },
    h("b", null, w ? `${w.date}, ${w.hour}:${w.minute}` : "Time not kept"),
    v.this ? h("span", { class: "jm-tag this" }, "this visit") : null,
    v.first ? h("span", { class: "jm-tag first" }, "first visit we know of") : null,
    v.active ? h("span", { class: "jm-tag on" }, "active now") : null,
    v.kind === "script" ? h("span", { class: "jm-tag", title: "Pages the page script sent with the visitor ID; the server log's own visit is not kept for them" }, "seen by the script") : null,
    v.kind === "touch" ? h("span", { class: "jm-tag", title: "Only its source and first page are known here" }, "only its first page known") : null,
    // Pages loaded from the server and steps seen in the browser (the dashed nodes), both stated.
    v.kind === "touch" ? null : h("small", null, `${pagesWords({ ...(v.raw || {}), pages: v.pages, trail: v.raw?.trail || v.trail })}${v.seconds != null ? `, ${duration(v.seconds)}` : ""}`));
}

/* Timings for a replay: each step's delay (ms) from the visit's real offsets. */
function timings(v, base) {
  const trail = v.trail || [];
  const last = trail.reduce((m, p) => Math.max(m, p.at || 0), 0);
  const scale = last ? Math.min(1, CAP / ((last / 60) * PER_MINUTE)) : 1;
  const at = (sec) => base + Math.round(((sec || 0) / 60) * PER_MINUTE * scale);
  const out = [base];
  trail.forEach((p) => { out.push(at(p.at) - 40, at(p.at)); });
  const end = at(last) + 260;
  out.push(end - 40, end);
  return { delays: out, end };
}

/* The journey: visits newest first. Returns {el, replay}. */
export function journeyMap(visits) {
  const rows = [];
  const box = h("div", { class: "jm", role: "list", "aria-label": "Each visit, newest first" });
  visits.forEach((v, i) => {
    const older = visits[i + 1];
    const row = h("div", { class: `jm-v${v.active ? " on" : ""}${v.first ? " first" : ""}${i === 0 ? " newest" : ""}`, role: "listitem" }, header(v),
      h("ol", { class: "jm-p" }, steps(v)));
    box.append(row);
    rows.push({ row, v });
    if (older) {
      const a = when(older.stop || older.start)?.t, b = when(v.start)?.t;
      const words = daysWords(a, b);
      box.append(h("div", { class: "jm-gap", "aria-hidden": words ? null : "true" }, words ? h("span", null, words) : null));
    }
  });
  const play = (real) => {
    if (reduced()) return;
    let base = 0;
    // Oldest first, one visit after another; the opening is a quick stagger.
    for (const { row, v } of [...rows].reverse()) {
      const els = [...row.querySelectorAll(".jm-s")];
      if (real) {
        const t = timings(v, base);
        els.forEach((el, k) => el.style.setProperty("--d", `${Math.max(base, t.delays[Math.min(k, t.delays.length - 1)])}ms`));
        base = t.end + 450;
      } else {
        els.forEach((el, k) => el.style.setProperty("--d", `${Math.min(k, 16) * STEP}ms`));
      }
      row.classList.remove("jm-play");
    }
    void box.offsetWidth;          // restart the animations
    for (const { row } of rows) row.classList.add("jm-play");
  };
  requestAnimationFrame(() => play(false));
  return { el: box, replay: () => play(true) };
}

const REPLAY = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/></svg>';

/* The replay button for a journey (none under reduced motion). */
export function replayButton(map) {
  if (reduced()) return null;
  return h("button", { type: "button", class: "btn jm-replay", html: REPLAY, onclick: () => map.replay(),
    title: "Play the visits again, oldest first, at their real pace: 1 second per minute, at most 4 seconds a visit" }, "Replay");
}

export const timeWords = (ts) => tzTime(ts, { date: true, label: false });
