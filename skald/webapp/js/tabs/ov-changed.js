// Overview › Summary, card "What changed: is it working?" (release 2, card S6).
//
// While Compare is on and both periods are whole and verified (mode-compare.js compareOf):
// two lists, Sources (source types) and Landing pages, each Now · Before · Change, from the
// two periods' own totals (data.js total, the same sums every tab shows). A change of 3
// visits or fewer reads "≈ about the same" (period-dates.js SAME). Each row opens its
// drill-down. Off, the card says how to switch Compare on; on but not comparable, why.
// Nothing new is counted: both columns are figures the app already shows for each period.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { fileName } from "./common.js";
import { goTo } from "./ov-live.js";
import { shownText } from "../labels.js";
import { changeWords, beforeState, notMeasuredWords, firstWholeDay, SAME } from "../period-dates.js";
import { spanWords } from "../mode-compare.js";
import { info } from "./tiles.js";

const LIMIT = 8;
const SHOWN = 5;     // rows shown before "Show all" (2.42: Summary's first screen stays short)

/* {label: n} of A and B -> rows {k, now, before}, the biggest of either first. */
export function changeRows(a, b, { limit = LIMIT, skip = () => false } = {}) {
  const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})].filter((k) => !skip(k) && ((a || {})[k] || (b || {})[k])));
  return [...keys].map((k) => ({ k, now: (a || {})[k] || 0, before: (b || {})[k] || 0 }))
    .sort((x, y) => Math.max(y.now, y.before) - Math.max(x.now, x.before) || x.k.localeCompare(y.k)).slice(0, limit);
}

/* One sentence: more or fewer people, and the biggest rise and drop (more than SAME). */
export function sayWhat(peopleNow, peopleBefore, rows) {
  const bits = [];
  if (peopleNow != null && peopleBefore != null) {
    const d = peopleNow - peopleBefore;
    bits.push(Math.abs(d) <= SAME ? `About as many people as the period before: ${n(peopleNow)} against ${n(peopleBefore)}.`
      : `${d > 0 ? "More" : "Fewer"} people than the period before: ${n(peopleNow)} against ${n(peopleBefore)}.`);
  }
  const moves = rows.map((r) => ({ ...r, d: r.now - r.before })).filter((r) => Math.abs(r.d) > SAME);
  const up = moves.filter((r) => r.d > 0).sort((a, b) => b.d - a.d)[0];
  const down = moves.filter((r) => r.d < 0).sort((a, b) => a.d - b.d)[0];
  if (up) bits.push(`Biggest rise: ${shownText(up.k)} (${n(up.before)} to ${n(up.now)}).`);
  if (down) bits.push(`Biggest drop: ${shownText(down.k)} (${n(down.before)} to ${n(down.now)}).`);
  return bits.join(" ");
}

function list(title, dim, rows, r, c) {
  const cols = [
    { key: "k", label: title, drill: dim, csv: (x) => x.k },
    { key: "now", label: "Now", num: true },
    { key: "before", label: "Before", num: true },
    { key: "d", label: "Change", sort: (x) => x.now - x.before, csv: (x) => x.now - x.before,
      fmt: (_, x) => { const w = changeWords(x.now, x.before); return h("span", { class: `wc-c ${w.dir}` }, w.text); } },
  ];
  return table(cols, { caption: `What changed: ${title.toLowerCase()}`, rows, file: fileName(`what-changed-${dim}`, r).replace(/\.csv$/, `-vs-${c.b.first}.csv`),
    limit: SHOWN, search: false, tools: false, sortKey: "now", empty: "None in either period." });
}

export function whatChanged(m, s, r, t, c) {
  const sub = !c.on ? "Switch on Compare to see what rose and fell." : c.ok ? `${spanWords(r)} against ${spanWords(c.b)}.` : "Not compared.";
  const same = `"About the same" means the gap is ${SAME} visits or fewer: normal day-to-day swing at these numbers. Each row opens its detail.`;
  const headRow = h("div", { class: "card-h wc-h" }, h("div", null, h("h2", null, "What changed: is it working? ", c.ok ? info(same, "What changed") : null), h("p", { class: "sub" }, sub)),
    h("span", { class: "grow" }), goTo("overview/insights", "What to do about it: Insights"));
  const out = h("section", { class: "s wc", "aria-label": "What changed" }, headRow);
  if (!c.on) {
    out.append(h("div", { class: "wc-none" }, "Compare this period with the one before to see which sources and landing pages rose and fell. ",
      h("button", { type: "button", class: "btn", onclick: () => S.set({ cmp: "prev" }) }, "Compare with the period before")));
    return out;
  }
  if (!c.ok) {
    const notMeasured = !c.inc && c.b && beforeState(c.b) === "not_measured";
    out.append(h("div", { class: "wc-none", role: "note" }, notMeasured
      ? notMeasuredWords(r, s, { firstWhole: firstWholeDay(m.byDay, m.firstDay), site: m.site, firstDay: m.firstDay }) : c.why));
    return out;
  }
  const b = c.bT || {};
  if (!t.by || !b.by || t.unmeasured?.by || b.unmeasured?.by) {
    out.append(h("div", { class: "wc-none", role: "note" }, "Not compared: some days of one period were collected before sources and landing pages were kept, so the lists would not add up."));
    return out;
  }
  const src = changeRows(t.by.source, b.by.source);
  const land = changeRows(t.by.landing, b.by.landing, { skip: (k) => k === "(all others)" });
  out.append(h("p", { class: "wc-say" }, sayWhat(t.readers, b.readers, [...src, ...land])),
    h("div", { class: "wc-cols" }, list("Sources", "source", src, r, c), list("Landing pages", "landing", land, r, c)));
  return out;
}
