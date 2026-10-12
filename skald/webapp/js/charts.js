// Hand-rolled SVG charts. No library: the page may load nothing from outside.
//
// The honesty rules from the classic page hold here too:
//   * a day that was withheld or not collected is drawn hatched, never as a zero
//   * a partial day is drawn faded and says so in its tooltip
//   * lines break at a day that is not shown; they never bridge a gap
// Every chart has a tooltip on hover and keyboard focus, and the same figures
// in a table elsewhere on the tab.

import { esc, h, n, short, long, tip, untip, reduced } from "./ui.js";
import * as S from "./state.js";
import { time as tzTime } from "./tz.js";

let uid = 0;
// Charts are drawn at the width they will be shown, so text stays 11px at any size.
let W = 720;
function fit(half, width) {
  const p = document.getElementById("panel");
  let inner = width || (p ? p.clientWidth - parseFloat(getComputedStyle(p).paddingLeft) * 2 - 40 : 720);
  if (half && inner > 760) inner = inner / 2 - 30;
  W = Math.max(300, Math.min(1180, Math.round(inner)));
}

export function scale(top) {
  if (!(top > 0)) return [4, 1];
  const rough = top / 4, exp = 10 ** Math.floor(Math.log10(rough));
  let step = exp;
  for (const m of [1, 2, 2.5, 5, 10]) { step = m * exp; if (step >= rough) break; }
  step = Math.max(1, Math.round(step));
  return [step * Math.ceil(top / step), step];
}

function hatchDef(id) {
  return `<defs><pattern id="${id}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(135)">` +
    `<rect width="5" height="5" fill="var(--sunk)"/><line x1="0" y1="0" x2="0" y2="5" stroke="var(--hatch)" stroke-width="1.5"/></pattern></defs>`;
}

export const ABSENT = {
  withheld: "withheld: the figures did not reconcile",
  missing: "not collected",
  before: "before history starts",
};

/* Markers: deploys, rule changes, internal-address changes and notes, drawn as
   a dashed line through their day on every day chart. main.js sets them once
   per render; "Hide markers" turns them off everywhere. */
let MARKS = new Map(), MARKS_ON = true;
export function setMarkers(byDay, on) { MARKS = byDay || new Map(); MARKS_ON = on !== false; }
const marksOf = (d) => (MARKS_ON && d.day ? MARKS.get(d.day) || [] : []);
const MARK_WORDS = { website_release: "Website release", skald_deploy: "Traffic tool deploy", config_change: "Counting rules changed",
  ours_change: "Internal address change", backfill: "History recounted" };
const markRows = (d) => marksOf(d).map((k) => ({ color: "var(--opp)", value: "", label: `${MARK_WORDS[k.kind] || "Marker"}${k.at ? ` at ${tzTime(k.at)}` : ""}: ${k.label}` }));
const markWords = (d) => marksOf(d).map((k) => `; marker: ${k.label}`).join("");
function markLines(days, L, T, ph, slot) {
  const out = [];
  days.forEach((d, i) => {
    const ks = marksOf(d);
    if (!ks.length) return;
    const x = (L + slot * (i + 0.5)).toFixed(1);
    out.push(`<g class="mk"><line x1="${x}" x2="${x}" y1="${T}" y2="${T + ph}"/>` +
      `<path d="M${x},${T - 7}l5,5-5,5-5-5z"/>${ks.length > 1 ? `<text x="${(+x + 8).toFixed(1)}" y="${T + 2}">${ks.length}</text>` : ""}</g>`);
  });
  return out.join("");
}

function frame({ top, days, H, L, R, T, B, every }) {
  const [max, step] = scale(top);
  const pw = W - L - R, ph = H - T - B, out = [];
  for (let v = 0; v <= max; v += step) {
    const y = T + ph - (v / max) * ph;
    out.push(`<line class="grid" x1="${L}" x2="${W - R}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/>`,
      `<text x="${L - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end">${n(v)}</text>`);
  }
  const k = days.length, slot = pw / k, gap = every || (k <= 10 ? 1 : k <= 31 ? 7 : 14);
  days.forEach((d, i) => {
    if ((k - 1 - i) % gap === 0 && d.label !== "") {
      out.push(`<text x="${(L + slot * (i + 0.5)).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(d.label ?? short(d.day))}</text>`);
    }
  });
  out.push(`<line class="axis" x1="${L}" x2="${W - R}" y1="${T + ph}" y2="${T + ph}"/>`);
  return { max, pw, ph, slot, svg: out.join("") };
}

function wrap(svg, label, H) {
  const el = h("div", { class: "chart" });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${svg}</svg>`;
  return el;
}

// Hover and focus on each slot: one tooltip listing every series for that day.
function slots(el, items, describe) {
  const svg = el.querySelector("svg");
  const show = (i, x, y) => {
    const [head, rows] = describe(i);
    el.classList.add("dim");
    svg.querySelectorAll(`.mark[data-i="${i}"]`).forEach((m) => m.classList.add("on"));
    tip(x, y, head, rows);
  };
  const hide = () => {
    el.classList.remove("dim");
    svg.querySelectorAll(".mark.on").forEach((m) => m.classList.remove("on"));
    untip();
  };
  items.forEach((hit) => {
    const i = Number(hit.dataset.i);
    hit.addEventListener("pointermove", (e) => { hide(); show(i, e.clientX, e.clientY); });
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", () => { const r = hit.getBoundingClientRect(); show(i, r.left + r.width / 2, r.top + 20); });
    hit.addEventListener("blur", hide);
  });
}

/* Columns per day, stacked by series.
   days: [{day, state: ok|partial|withheld|missing|before, partial?: "from 14:05", ...}]
   series: [{name, color, get(day) -> number}] */
export function columns(days, series, { label, H = 250, unit = "requests", onPick, prev } = {}) {
  fit(arguments[2]?.half, arguments[2]?.width);
  const L = 52, R = 8, T = 14, B = 28;
  const drawn = days.filter((d) => d.state === "ok" || d.state === "partial");
  const sumOf = (d) => series.reduce((s, x) => s + (x.get(d) || 0), 0);
  // The previous period, as one dashed line of its totals over the columns.
  const ghost = prev ? days.map((d) => { const p = d.state === "before" ? null : prev(d); return p ? sumOf(p) : null; }) : null;
  const top = Math.max(0, ...drawn.map(sumOf), ...(ghost || []).filter((v) => v != null));
  const f = frame({ top, days, H, L, R, T, B });
  const hid = `h${++uid}`, out = [hatchDef(hid), f.svg, markLines(days, L, T, f.ph, f.slot)];
  const bw = Math.min(24, Math.max(1, f.slot - (f.slot > 6 ? 2 : 1)));
  days.forEach((d, i) => {
    const x = L + f.slot * i + (f.slot - bw) / 2;
    if (d.state === "before") return;
    if (d.state !== "ok" && d.state !== "partial") {
      out.push(`<rect class="mark" data-i="${i}" x="${x.toFixed(1)}" y="${T + f.ph - f.ph * 0.18}" width="${bw.toFixed(1)}" height="${(f.ph * 0.18).toFixed(1)}" fill="url(#${hid})" rx="2"/>`);
      return;
    }
    let y = T + f.ph;
    const parts = series.map((s) => s.get(d) || 0);
    const lastIdx = parts.reduce((li, v, j) => (v ? j : li), -1);
    const g = [`<g class="mark" data-i="${i}"${d.state === "partial" ? ' opacity=".45"' : ""}>`];
    parts.forEach((v, j) => {
      if (!v) return;
      const hh = (v / f.max) * f.ph;
      y -= hh;
      const gapPx = j === lastIdx ? 0 : 0;
      // 2px surface gap between stacked segments; the topmost gets the rounded data-end.
      if (j === lastIdx && hh > 4) {
        const r = Math.min(4, bw / 2);
        g.push(`<path d="M${x.toFixed(1)},${(y + hh).toFixed(1)}V${(y + r).toFixed(1)}q0,-${r} ${r},-${r}h${(bw - 2 * r).toFixed(1)}q${r},0 ${r},${r}V${(y + hh).toFixed(1)}z" fill="${series[j].color}"/>`);
      } else {
        g.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.5, hh - (j < lastIdx && hh > 3 ? 2 : 0) - gapPx).toFixed(1)}" fill="${series[j].color}"/>`);
      }
    });
    g.push("</g>");
    out.push(g.join(""));
  });
  if (ghost) out.push(ghostPath(ghost, (i) => L + f.slot * (i + 0.5), (v) => T + f.ph - (v / f.max) * f.ph));
  days.forEach((d, i) => {
    if (d.state === "before") return;
    const was = ghost && ghost[i] != null ? `; previous period ${n(ghost[i])}` : "";
    out.push(`<rect class="hit" data-i="${i}" tabindex="0" x="${(L + f.slot * i).toFixed(1)}" y="${T}" width="${f.slot.toFixed(1)}" height="${f.ph}" aria-label="${esc(describeDay(d, series, unit) + was + markWords(d))}"/>`);
  });
  const el = wrap(out.join(""), label, H);
  slots(el, el.querySelectorAll(".hit"), (i) => {
    const d = days[i];
    const head = long(d.day) + (d.state === "partial" ? ` (partial day${d.partial ? `, ${d.partial}` : ""})` : "");
    const extra = [...(ghost ? [{ color: "var(--ink-3)", value: ghost[i] == null ? "-" : n(ghost[i]), label: "previous period" }] : []), ...markRows(d)];
    if (d.state !== "ok" && d.state !== "partial") return [head, [{ value: "", label: ABSENT[d.state] || d.state }, ...extra]];
    return [head, [{ value: n(sumOf(d)), label: unit }, ...series.slice().reverse().map((s) => ({ color: s.color, value: n(s.get(d)), label: s.name })), ...extra]];
  });
  // A day's column narrows the range to that day (unless the chart says otherwise, or not at all with onPick: false).
  const pick = onPick === false ? null : onPick || ((d) => d.state === "ok" && S.set({ range: "custom", from: d.day, to: d.day }));
  if (pick) el.querySelectorAll(".hit").forEach((hit) => {
    const d = days[Number(hit.dataset.i)];
    if (d.state !== "ok") return;
    hit.classList.add("pick");
    hit.addEventListener("click", () => { untip(); pick(d); });
    hit.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); untip(); pick(d); } });
  });
  return el;
}

// A dashed line through the previous period's values; it breaks where a value is missing.
function ghostPath(values, xOf, yOf, color = "var(--ink-3)") {
  const segs = []; let run = [];
  values.forEach((v, i) => {
    if (v == null) { if (run.length) segs.push(run); run = []; return; }
    run.push(`${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`);
  });
  if (run.length) segs.push(run);
  return segs.map((sg) => (sg.length > 1 ? `<polyline class="ghost" points="${sg.join(" ")}" stroke="${color}"/>`
    : `<circle class="ghost-dot" cx="${sg[0].split(",")[0]}" cy="${sg[0].split(",")[1]}" r="2.5" fill="${color}"/>`)).join("");
}

function describeDay(d, series, unit) {
  if (d.state !== "ok" && d.state !== "partial") return `${long(d.day)}: ${ABSENT[d.state] || d.state}`;
  return `${long(d.day)}${d.state === "partial" ? " (partial day)" : ""}: ` +
    series.map((s) => `${s.name} ${n(s.get(d))}`).join(", ") + ` ${unit}`;
}

/* Lines per day. A value of null breaks the line (a day not shown, or a
   figure not recorded); it is never drawn as zero.
   marks: {name, color, get(day) -> number|null}: a small count per day (the
   day's leads) drawn as a dot on the base line, on its own scale, with its
   number above when there is room; only on days the lines draw. null is
   "not recorded" in the tooltip, never a zero. */
export function lines(days, series, { label, H = 240, prev, marks } = {}) {
  fit(arguments[2]?.half, arguments[2]?.width);
  const L = 52, R = 10, T = 14, B = 28;
  const ok = days.filter((d) => d.state === "ok");
  // The previous period, one dashed line per series in its own colour.
  const ghosts = prev ? series.map((s) => days.map((d) => { const p = d.state === "before" ? null : prev(d); return p ? s.get(p) ?? null : null; })) : null;
  const top = Math.max(0, ...ok.flatMap((d) => series.map((s) => s.get(d) || 0)), ...(ghosts || []).flat().filter((v) => v != null));
  const f = frame({ top, days, H, L, R, T, B });
  const hid = `h${++uid}`, out = [hatchDef(hid), f.svg, markLines(days, L, T, f.ph, f.slot)];
  const pt = (i, v) => [L + f.slot * (i + 0.5), T + f.ph - (v / f.max) * f.ph];
  if (ghosts) ghosts.forEach((g, j) => out.push(ghostPath(g, (i) => pt(i, 0)[0], (v) => pt(0, v)[1], series[j].color)));
  days.forEach((d, i) => {
    if (d.state !== "ok" && d.state !== "partial" && d.state !== "before") {
      out.push(`<rect x="${(L + f.slot * i).toFixed(1)}" y="${T + f.ph - 6}" width="${Math.max(1, f.slot - 1).toFixed(1)}" height="6" fill="url(#${hid})"/>`);
    }
  });
  for (const s of series) {
    let run = [];
    const segs = [];
    days.forEach((d, i) => {
      const v = d.state === "ok" ? s.get(d) : null;
      if (v == null) { if (run.length) segs.push(run); run = []; return; }
      run.push(pt(i, v));
    });
    if (run.length) segs.push(run);
    for (const seg of segs) {
      if (seg.length === 1) out.push(`<circle cx="${seg[0][0].toFixed(1)}" cy="${seg[0][1].toFixed(1)}" r="4" fill="${s.color}" stroke="var(--surface)" stroke-width="2"/>`);
      else {
        const p = seg.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
        if (s.area) out.push(`<polygon points="${seg[0][0].toFixed(1)},${T + f.ph} ${p} ${seg[seg.length - 1][0].toFixed(1)},${T + f.ph}" fill="${s.color}" opacity=".1"/>`);
        out.push(`<polyline class="ln" points="${p}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`);
      }
    }
  }
  const markOf = (d) => (marks && d.state === "ok" ? marks.get(d) : null);
  if (marks) {
    const top = Math.max(1, ...days.map((d) => markOf(d) || 0));
    days.forEach((d, i) => {
      const v = markOf(d);
      if (!v) return;
      const cx = L + f.slot * (i + 0.5), cy = T + f.ph - 6, r = 2.5 + 3.5 * Math.sqrt(v / top);
      out.push(`<circle class="lead-mark" cx="${cx.toFixed(1)}" cy="${cy}" r="${r.toFixed(1)}" fill="${marks.color}" stroke="var(--surface)" stroke-width="1.5"/>`);
      if (f.slot >= 14) out.push(`<text x="${cx.toFixed(1)}" y="${(cy - r - 3).toFixed(1)}" text-anchor="middle" class="lead-n">${n(v)}</text>`);
    });
  }
  const markLine = (d) => (!marks ? "" : markOf(d) == null ? `; ${marks.name} not recorded` : `; ${marks.name} ${n(markOf(d))}`);
  out.push(`<line class="hair" x1="0" x2="0" y1="${T}" y2="${T + f.ph}" opacity="0"/><g class="dots"></g>`);
  days.forEach((d, i) => {
    if (d.state === "before") return;
    const was = ghosts ? `; previous period ${series.map((x, j) => `${x.name} ${n(ghosts[j][i])}`).join(", ")}` : "";
    out.push(`<rect class="hit" data-i="${i}" tabindex="0" x="${(L + f.slot * i).toFixed(1)}" y="${T}" width="${f.slot.toFixed(1)}" height="${f.ph}" aria-label="${esc(describeDay(d, series, "") + (d.state === "ok" ? markLine(d) : "") + was + markWords(d))}"/>`);
  });
  const el = wrap(out.join(""), label, H);
  const svg = el.querySelector("svg"), hair = svg.querySelector(".hair"), dots = svg.querySelector(".dots");
  // Draw the lines in once they are on the page (a path has no length before that).
  if (!reduced()) requestAnimationFrame(() => svg.querySelectorAll(".ln").forEach((p) => {
    let len = 0;
    try { len = p.getTotalLength(); } catch { return; }
    if (!len) return;
    p.animate([{ strokeDasharray: len, strokeDashoffset: len }, { strokeDasharray: len, strokeDashoffset: 0 }],
      { duration: 900, easing: "cubic-bezier(.2,.7,.2,1)" });
  }));
  el.querySelectorAll(".hit").forEach((hit) => {
    const i = Number(hit.dataset.i), d = days[i];
    const show = (x, y) => {
      const cx = L + f.slot * (i + 0.5);
      hair.setAttribute("x1", cx); hair.setAttribute("x2", cx); hair.setAttribute("opacity", "1");
      dots.innerHTML = d.state === "ok" ? series.map((s) => {
        const v = s.get(d); if (v == null) return "";
        const [, yy] = pt(i, v);
        return `<circle cx="${cx}" cy="${yy.toFixed(1)}" r="4" fill="${s.color}" stroke="var(--surface)" stroke-width="2"/>`;
      }).join("") : "";
      const head = long(d.day) + (d.state === "partial" ? " (partial day, left out)" : "");
      const rows = d.state === "ok" ? series.map((s) => ({ color: s.color, value: s.get(d) == null ? "-" : n(s.get(d)), label: s.get(d) == null ? `${s.name} not recorded` : s.name }))
        : [{ value: "", label: d.state === "partial" ? "a partial day is not drawn on this line" : ABSENT[d.state] }];
      if (marks && d.state === "ok") rows.push({ color: marks.color, value: markOf(d) == null ? "-" : n(markOf(d)), label: markOf(d) == null ? `${marks.name} not recorded` : marks.name });
      if (ghosts) rows.push(...series.map((x, j) => ({ color: x.color, value: ghosts[j][i] == null ? "-" : n(ghosts[j][i]), label: `${x.name}, previous period` })));
      rows.push(...markRows(d));
      tip(x, y, head, rows);
    };
    const hide = () => { hair.setAttribute("opacity", "0"); dots.innerHTML = ""; untip(); };
    hit.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", () => { const r = hit.getBoundingClientRect(); show(r.left + r.width / 2, r.top + 30); });
    hit.addEventListener("blur", hide);
  });
  return el;
}

// A sparkline: one series, no axes. Nulls break the line.
export function spark(values, color = "var(--ink-3)") {
  const Hs = 34, Ws = 200, k = values.length;
  const vals = values.filter((v) => v != null);
  if (vals.length < 2) return h("div", { class: "spark" });
  const max = Math.max(1, ...vals), step = Ws / Math.max(1, k - 1);
  const segs = []; let run = [];
  values.forEach((v, i) => {
    if (v == null) { if (run.length) segs.push(run); run = []; return; }
    run.push(`${(i * step).toFixed(1)},${(Hs - 3 - (v / max) * (Hs - 6)).toFixed(1)}`);
  });
  if (run.length) segs.push(run);
  const lastI = values.length - 1 - [...values].reverse().findIndex((v) => v != null);
  const ly = Hs - 3 - (values[lastI] / max) * (Hs - 6);
  const el = h("div", { class: "spark", "aria-hidden": "true" });
  el.innerHTML = `<svg viewBox="-3 0 ${Ws + 6} ${Hs}" preserveAspectRatio="none" style="width:100%;height:${Hs}px;display:block;overflow:visible">` +
    segs.map((s) => s.length > 1 ? `<polyline points="${s.join(" ")}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>` : "").join("") +
    `<circle cx="${(lastI * step).toFixed(1)}" cy="${ly.toFixed(1)}" r="2.5" fill="${color}"/></svg>`;
  return el;
}

/* Columns for a fixed set of labelled slots (hours 00-23, speed buckets...).
   items: [{label, value, title?}] in display order. */
export function bars(items, { label, color = "var(--g-people)", H = 200, unit = "", every = 1, onPick } = {}) {
  fit(arguments[1]?.half, arguments[1]?.width);
  const L = 44, R = 6, T = 12, B = 28;
  // Every `every`-th slot is labelled, counting from the first (00, 03, 06...).
  const days = items.map((it, i) => ({ day: "2000-01-01", label: i % every === 0 ? it.label : "" }));
  const top = Math.max(0, ...items.map((i) => i.value || 0));
  const f = frame({ top, days, H, L, R, T, B, every: 1 });
  const out = [f.svg];
  const bw = Math.min(24, Math.max(2, f.slot - 3));
  items.forEach((it, i) => {
    const v = it.value || 0, hh = (v / f.max) * f.ph, x = L + f.slot * i + (f.slot - bw) / 2, y = T + f.ph - hh;
    const r = Math.min(4, bw / 2, hh);
    if (v) out.push(`<path class="mark" data-i="${i}" d="M${x.toFixed(1)},${(y + hh).toFixed(1)}V${(y + r).toFixed(1)}q0,-${r} ${r},-${r}h${(bw - 2 * r).toFixed(1)}q${r},0 ${r},${r}V${(y + hh).toFixed(1)}z" fill="${it.color || color}"/>`);
    out.push(`<rect class="hit" data-i="${i}" tabindex="0" x="${(L + f.slot * i).toFixed(1)}" y="${T}" width="${f.slot.toFixed(1)}" height="${f.ph}" aria-label="${esc(`${it.title || it.label}: ${n(v)} ${unit}`)}"/>`);
  });
  const el = wrap(out.join(""), label, H);
  slots(el, el.querySelectorAll(".hit"), (i) => [items[i].title || items[i].label, [{ color: items[i].color || color, value: n(items[i].value || 0), label: unit }]]);
  // Picking a bar (click, or Enter on a focused one) opens its slot.
  if (onPick) el.querySelectorAll(".hit").forEach((hit) => {
    const go = () => { untip(); onPick(Number(hit.dataset.i)); };
    hit.classList.add("pick");
    hit.addEventListener("click", go);
    hit.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });
  });
  return el;
}

// The ledger band: every request in one strip, split into the groups, with a 2px gap.
export function band(parts, total, play = true) {
  const el = h("div", { class: `band${play && !reduced() ? " play" : ""}`, role: "img",
    "aria-label": parts.map((p) => `${p.name} ${n(p.value)}`).join(", ") + `, of ${n(total)} requests` });
  parts.forEach((p, i) => {
    if (!p.value) return;
    const seg = h("div", { class: "seg-g", tabindex: "0", style: { flexGrow: String(p.value), background: p.color, animationDelay: `${i * 0.12}s` },
      "aria-label": `${p.name}: ${n(p.value)} requests` });
    const show = (x, y) => tip(x, y, p.name, [{ color: p.color, value: n(p.value), label: `requests, ${total ? Math.round((p.value / total) * 1000) / 10 : 0}% of all` }]);
    seg.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    seg.addEventListener("pointerleave", untip);
    seg.addEventListener("focus", () => { const r = seg.getBoundingClientRect(); show(r.left + r.width / 2, r.top); });
    seg.addEventListener("blur", untip);
    el.append(seg);
  });
  return el;
}

export function legend(items, line = false) {
  return h("ul", { class: "legend" }, items.map(([name, color, kind]) =>
    h("li", null, h("span", { class: `sw${line || kind === "ghost" ? " line" : ""}${kind === "hatch" ? " hatch" : ""}${kind === "ghost" ? " ghost" : ""}`,
      style: kind === "hatch" || kind === "ghost" ? null : { background: color } }), name)));
}
