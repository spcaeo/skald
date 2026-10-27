// The top bar's two global modes (2.7.0), beside the period:
//   * "Today" (Live): the first choice of the period's group since 2.42 (liveSegment;
//     it was its own "Today · Live" switch). Picked, the period is Today on every
//     section, redrawn every 2 minutes, with a pulsing dot (mode-live.js).
//   * "Compare with…": previous period, same period last year, or a custom B.
//     On, every table and chart that registers compare support shows A · B · ±
//     or B as a dashed line (mode-compare.js); a tab that does not says so in
//     one quiet line. Live and Compare are never on together.
// main.js puts barModes() in the bar's slot (.bar-modes), liveSegment() in the period group, modeBanner() at the
// top of a section's tab, and modeActions() in the command palette.
// Section builders import mode-live.js and mode-compare.js, never this file.

import { h, short } from "./ui.js";
import * as S from "./state.js";
import { opt } from "./sections.js";
import { rangeOf } from "./data.js";
import { DEMO } from "./demo.js";
import { time as tzTime } from "./tz.js";
import { isLive, setLive, backRange, liveState } from "./mode-live.js";
import { compareOn, compareOf, rangeB, spanWords, KINDS, MAX_DAYS } from "./mode-compare.js";
import { incTab } from "./period-dates.js";

const CMP = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 12l3.5-4 3 2.5L14 4"/><path d="M2 13.5h12" stroke-dasharray="2 2"/></svg>';
const SHORT = { prev: "previous period", year: "last year" };

/* 2.42 (the UX audit's task 5): Today sits in the period's own group (main.js, liveSegment),
   so the bar keeps only Compare here, and only on a tab that compares (a control that does
   nothing on a tab is not shown). Compare is on by default (state.js defaultCmp). */
export function barModes(m, s) {
  return opt(s.tab, "compare", s, false) && opt(s.tab, "ranged", s, true) ? [compareMenu(m, s)] : [];
}

/* "Today" as the first choice of the period's group: the live dot (pulsing while the live
   count is fresh), the words, and what picking it does: Today so far, redrawn every 2 minutes. */
export function liveSegment(m, s) {
  const on = isLive(s);
  const st = liveState(m);
  const fresh = DEMO.on ? !!st.at : st.fresh;
  return [h("span", { class: on ? `pulse${fresh ? "" : " stale"}` : "m-dot", "aria-hidden": "true" }), "Today"];
}
export { setLive };

// ---------------------------------------------------------------- Compare
// The state Compare would use: Live's Today gives way to the period before it.
const outOfLive = (s) => (isLive(s) ? { ...s, ...backRange() } : s);

function compareMenu(m, s) {
  const kind = compareOn(s) ? s.cmp : "";
  const here = opt(s.tab, "compare", s, false);
  const base = outOfLive(s);
  const a = rangeOf(m, base);
  const bOf = (k) => rangeB(m, base, a, k);
  const b = kind ? bOf(kind) : null;
  const long = kind === "custom" && b ? `vs ${short(b.first)} – ${short(b.last)}` : kind ? `vs ${SHORT[kind]}` : "Compare with…";
  const shortWords = kind ? (kind === "custom" ? "vs B" : kind === "prev" ? "vs prev." : "vs year") : "Compare";
  const title = kind ? `Compared with ${kind === "custom" ? "B" : SHORT[kind]}${b ? `: ${spanWords(b)}` : ""}.${here ? "" : " No compare on this tab."} Change or turn off.`
    : "Compare with another period: the previous one, the same one last year, or any days";
  const btn = h("button", { type: "button", class: `btn mode-cmp${kind ? " on" : ""}${kind && !here ? " idle" : ""}`, "aria-pressed": String(!!kind),
    "aria-haspopup": "dialog", "aria-expanded": "false", title, html: CMP,
    "aria-label": kind ? `Compare with: ${kind === "custom" ? "custom period" : SHORT[kind]}${b ? `, ${spanWords(b)}` : ""}${here ? "" : ". No compare on this tab"}` : "Compare with…" },
  h("span", { class: "m-l" }, long), h("span", { class: "m-s" }, shortWords));

  const choose = (patch) => { close(true); S.set({ ...(isLive(s) ? backRange() : {}), ...patch }); };
  const item = (k, name, sub) => h("button", { type: "button", class: "menu-i mode-opt", "aria-pressed": String(kind === k), onclick: () => choose({ cmp: k }) },
    h("b", null, name), sub ? h("small", null, sub) : null);
  const span = (x) => (x ? spanWords(x) : "not available for this period");

  // Custom: B's dates, by default the period before A.
  const cb = kind === "custom" && b ? b : bOf("prev") || { first: m.anchor, last: m.anchor };
  const lo = m.firstDay || m.anchor;
  const from = h("input", { type: "date", value: cb.first, min: lo, max: m.anchor, "aria-label": "B from" });
  const to = h("input", { type: "date", value: cb.last, min: lo, max: m.anchor, "aria-label": "B to" });
  const say = h("p", { class: "mode-say", role: "status" });
  const apply = h("button", { type: "button", class: "btn primary", onclick: () => {
    if (!from.value || !to.value || from.value > to.value) { say.textContent = "The start must be on or before the end."; return; }
    if ((Date.parse(to.value) - Date.parse(from.value)) / 864e5 + 1 > MAX_DAYS) { say.textContent = "At most 12 months."; return; }
    choose({ cmp: "custom", cb: `${from.value}..${to.value}` });
  } }, "Compare");

  const pop = h("div", { class: "pop mode-pop", role: "dialog", "aria-label": "Compare with", hidden: true },
    h("p", { class: "mode-h" }, "Compare with…"),
    isLive(s) ? h("p", { class: "note" }, "Today is never compared: choosing one moves the period to 7 days.") : null,
    h("div", { class: "mode-opts" },
      item("prev", KINDS[0][1], span(bOf("prev"))),
      item("year", KINDS[1][1], span(bOf("year"))),
      h("div", { class: `mode-custom${kind === "custom" ? " on" : ""}` },
        h("b", null, KINDS[2][1]), h("span", { class: "pair" }, from, h("span", null, "to"), to), apply, say)),
    kind ? h("button", { type: "button", class: "btn mode-off", onclick: () => choose({ cmp: "" }) }, "Turn compare off") : null,
    h("p", { class: "note" }, "A is the period above, B the one chosen here. Previous period and last year compare only when both are whole and verified; a custom B counts whole days and names any left out."));

  const wrap = h("div", { class: "more mode-cmp-wrap" }, btn, pop);
  const away = (e) => { if (!wrap.contains(e.target)) close(false); };
  const esc = (e) => { if (e.key === "Escape") close(true); };
  function close(focusBack) {
    if (pop.hidden) return;
    pop.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", away, true);
    document.removeEventListener("keydown", esc);
    if (focusBack) btn.focus();
  }
  btn.addEventListener("click", () => {
    if (!pop.hidden) return close(false);
    pop.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    pop.classList.remove("from-right");
    if (pop.getBoundingClientRect().right > innerWidth - 8) pop.classList.add("from-right");
    document.addEventListener("pointerdown", away, true);
    document.addEventListener("keydown", esc);
    (pop.querySelector('.mode-opt[aria-pressed="true"]') || pop.querySelector(".mode-opt"))?.focus();
  });
  return wrap;
}

/* The line at the top of a section's tab while Compare is on: what A and B are
   (and the days a custom B leaves out, and "Per day" when the lengths differ),
   or why they are not compared; on a tab that does not compare, one quiet line. */
export function modeBanner(m, s) {
  if (!compareOn(s) || !S.sectionOf(s.tab) || opt(s.tab, "figures", s, true) === false) return null;
  // Compare on by default (state.js defaultCmp): a tab that does not compare says nothing then.
  if (!opt(s.tab, "compare", s, false)) return s.cmpAuto ? null : h("p", { class: "cmp-none mode-banner" }, "No compare on this tab: its figures are not set against another period.");
  // Summary and Pages say A and B in their own period line (period-line.js).
  if (incTab(s)) return null;
  const c = compareOf(m, s);
  if (!c.ok) return h("p", { class: "cmp-why mode-banner", role: "note" }, c.why);
  const perDay = c.kind === "custom" && c.differ ? h("label", { class: "rb-check cmp-per" },
    h("input", { type: "checkbox", checked: c.perDay, onchange: (e) => S.set({ cnorm: e.target.checked ? "1" : "" }, { replace: true }) }), "Per day") : null;
  return h("div", { class: "cmp-line mode-banner", role: "note" },
    h("p", null, h("span", { class: "cmp-a" }, h("i", { class: "sa", "aria-hidden": "true" }), h("b", null, "A "), spanWords(c.a)),
      " against ", h("span", { class: "cmp-b" }, h("i", { class: "sb", "aria-hidden": "true" }), h("b", null, "B "), spanWords(c.b)),
      c.kind === "custom" ? "" : ` (${c.name.toLowerCase()})`, ". ",
      h("span", { class: "muted" }, c.kind === "custom" ? "Whole, verified days only; any day left out is named." : "Both periods whole and verified."),
      ...c.gaps.map((g) => h("span", { class: "cmp-gap" }, ` ${g}`))),
    perDay);
}

// The command palette's two lines (main.js actions).
export function modeActions() {
  return [
    { label: "Today, live: on or off", hint: "", run: () => setLive(!isLive(S.read())) },
    { label: "Compare with the previous period: on or off", hint: "", run: () => {
      const s = S.read();
      S.set(compareOn(s) ? { cmp: "" } : { ...(isLive(s) ? backRange() : {}), cmp: "prev" });
    } },
  ];
}
