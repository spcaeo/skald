// Hours: when readers arrive, as a day-by-hour heatmap in the report's time zone.

import { h, n, weekday, short, tip, untip } from "../ui.js";
import { figures, GROUPS, color } from "../data.js";
import { bars } from "../charts.js";
import { head, nothing, coverageNote, panel } from "./common.js";
import { open as openDrill } from "../drill.js";
import { hourLabels, label as tzLabel, sameAsSite, city, siteZone } from "../tz.js";
import * as S from "../state.js";
import { rove } from "../place.js";

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
const WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const span = (hh) => { const i = Number(hh); const a = LABELS[i], b = LABELS[(i + 1) % 24]; return `${a.includes(":") ? a : `${a}:00`} to ${b.includes(":") ? b : `${b}:00`}`; };

// What a cell counts: readers by the hour of their first page, or a group's requests when the day has them.
function measures(days) {
  const out = [["readers", "Visitors", (d) => d.by?.hour, "people"]];
  if (days.some((d) => d.hourly)) for (const [g, name] of GROUPS) out.push([g, `${name} (requests)`, (d) => d.hourly?.[g], g]);
  return out;
}

// Column labels: the chosen zone's clock at each site hour's start (the cells stay whole site hours).
let LABELS = HOURS;
function heat(rows, label, unit, tone) {
  const max = Math.max(1, ...rows.flatMap((r) => r.cells.map((c) => c ?? 0)));
  const grid = h("div", { class: "heat", role: "grid", "aria-label": label },
    h("span", { role: "presentation" }), HOURS.map((hh, i) => h("span", { class: "hh", "aria-hidden": "true" }, i % 3 === 0 ? LABELS[i] : "")));
  rows.forEach((r) => {
    grid.append(h("span", { class: "hl" }, r.label));
    r.cells.forEach((v, i) => {
      const words = v == null ? "not shown" : `${n(v)} ${unit}`;
      const cell = h("span", { class: "hc", tabindex: "0", role: "gridcell", "aria-label": `${r.long || r.label}, ${span(HOURS[i])}: ${words}`,
        style: v == null ? { background: "repeating-linear-gradient(135deg, var(--sunk) 0 3px, var(--gap) 3px 4px)" }
          : { background: v ? `color-mix(in srgb, ${tone} ${Math.round(12 + (v / max) * 88)}%, var(--heat-0))` : "var(--heat-0)" } });
      const show = (x, y) => tip(x, y, `${r.long || r.label}, ${span(HOURS[i])}`, [{ value: v == null ? "-" : n(v), label: v == null ? "not shown" : unit }]);
      cell.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
      cell.addEventListener("pointerleave", untip);
      cell.addEventListener("focus", () => { const b = cell.getBoundingClientRect(); show(b.left + b.width / 2, b.top); });
      cell.addEventListener("blur", untip);
      // A cell opens that hour; a cell of one dated day narrows the range to that day too.
      if (v != null) {
        const pick = () => { untip(); if (r.day) S.set({ range: "custom", from: r.day, to: r.day, dd: `hour:${HOURS[i]}` }); else openDrill("hour", HOURS[i]); };
        cell.addEventListener("click", pick);
        cell.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); pick(); } });
      }
      grid.append(cell);
    });
  });
  // One Tab stop for the grid; arrow keys move between cells, as in a spreadsheet.
  rove(grid.querySelectorAll(".hc"), { start: 0, cols: 24 });
  return h("div", null, grid, h("div", { class: "scale" }, "Fewer", h("span", { class: "ramp", style: { background: `linear-gradient(to right, var(--heat-0), ${tone})` } }), `More (${n(max)} at most)`,
    h("span", { class: "sw hatch", style: { marginLeft: "12px" } }), "not shown"));
}

let measure = "readers";
export default function hours(m, s) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Time", r, "When visitors arrive, by the hour of their first page. Each visitor is counted once.")];
  if (!t) return [...out, nothing(m, r, "hours")];
  const days = r.kind === "today" ? [{ day: m.today, state: "ok", ...m.live.figures }] : r.days;
  LABELS = hourLabels(r.kind === "today" ? m.today : r.first);
  const ms = measures(days);
  if (!ms.some(([k]) => k === measure)) measure = "readers";
  const [, mName, get, g] = ms.find(([k]) => k === measure);
  const tone = color(g), unit = measure === "readers" ? "visitors" : "requests";
  if (ms.length > 1) {
    const sel = h("select", { "aria-label": "What to count" }, ms.map(([k, name]) => h("option", { value: k, selected: k === measure }, name)));
    sel.addEventListener("change", () => { measure = sel.value; const p = document.getElementById("panel"); p.replaceChildren(...hours(m, s).flat(Infinity).filter(Boolean)); });
    out.push(h("label", { class: "ctl", style: { marginBottom: "14px" } }, "Count", sel));
  }
  const byDate = days.length <= 31;
  const rows = byDate
    ? days.filter((d) => d.state !== "before").map((d) => ({ day: r.kind === "today" ? "" : d.day, label: short(d.day), long: `${weekday(d.day)} ${short(d.day)}`,
      cells: HOURS.map((hh) => (d.state === "ok" && get(d) ? get(d)[hh] || 0 : d.state === "ok" && measure === "readers" && !d.by ? null : d.state === "ok" ? 0 : null)) }))
    : WEEK.map((w) => ({ label: w, long: `${w}s`, cells: HOURS.map((hh) => days.filter((d) => d.state === "ok" && weekday(d.day) === w && get(d)).reduce((a, d) => a + (get(d)[hh] || 0), 0)) }));
  out.push(h("section", { class: "s" }, h("h2", null, byDate ? "Each day, hour by hour" : "Each weekday, hour by hour"),
    h("p", { class: "sub" }, `${byDate ? "A hatched cell is an hour of a day that is not shown: withheld, partial or not collected." : `${r.length} days summed by weekday. Only verified days are counted.`} Hours in ${tzLabel()}${sameAsSite() ? "" : `; each row is a ${city(siteZone())} day, so its hours may start on the evening before or end on the morning after in your time`}.`),
    h("div", { class: "sheet" }, heat(rows, `${mName} by ${byDate ? "day" : "weekday"} and hour`, unit, tone))));
  const totals = HOURS.map((hh, i) => ({ label: LABELS[i], title: span(hh), value: days.filter((d) => d.state === "ok" && get(d)).reduce((a, d) => a + (get(d)[hh] || 0), 0) }));
  out.push(h("section", { class: "s" }, panel("All hours together", `${mName}, summed over the range`, bars(totals, { label: `${mName} by hour`, unit, every: 3, color: tone, H: 200, onPick: (i) => openDrill("hour", HOURS[i]) }))));
  out.push(coverageNote(cov, r));
  return out;
}
