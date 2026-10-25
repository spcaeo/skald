// The period line on Overview › Summary and Traffic › Pages (release 2, cards S2, S3, P2):
// two switches, "Include today" (inc=1) and "Compare with the period before" (cmp=prev),
// then the exact dates in words: "Last 7 whole days: 18–24 Oct compared with 11–17 Oct",
// what the period means ("On 15 Jan that is 8–14 Jan against 1–7 Jan"), and since when
// the site is measured. When the period before was not measured it says so, and the first
// day a full comparison comes; it never shows a 0 or a rise against nothing.
//
// The period buttons stay in the top bar (one picker for every tab); Today is its
// "Today · Live" switch. Both switches are in the address, so Back and Forward work.

import { h, short } from "./ui.js";
import * as S from "./state.js";
import { rangeOf } from "./data.js";
import { isLive, backRange } from "./mode-live.js";
import { compareOn, compareOf } from "./mode-compare.js";
import { incApplies, incOn, lineWords, notMeasuredWords, beforeState, firstWholeDay } from "./period-dates.js";

function toggle(label, on, { disabled = false, title, onclick }) {
  return h("button", { type: "button", role: "switch", class: `btn pl-sw${on ? " on" : ""}`, "aria-checked": String(on), disabled, title, onclick },
    h("span", { class: "pl-knob", "aria-hidden": "true" }), label);
}

/* The line for this state, or null on a tab without it. */
export function periodLine(m, s) {
  const r = rangeOf(m, s);
  const c = compareOf(m, s);
  const live = isLive(s);
  const inc = incOn(s);
  const words = lineWords(r, s, { b: c.ok || c.inc ? c.b : null, live: m.live, today: m.today });
  const incWhy = live ? "Today · Live is already today so far" : incApplies(s) ? (inc ? "Counting today so far: 7, 30 and 90 days end today" : "Count today so far in the period")
    : "Include today applies to 7, 30 and 90 days";
  const sw = h("div", { class: "pl-sws", role: "group", "aria-label": "Period options" },
    toggle("Include today", inc, { disabled: !incApplies(s), title: incWhy, onclick: () => S.set({ inc: inc ? "" : "1" }) }),
    toggle("Compare with the period before", compareOn(s) || live, { disabled: live, title: live ? "Today · Live is always set against yesterday at the same hour" : null,
      onclick: () => S.set(compareOn(s) ? { cmp: "" } : { ...(live ? backRange() : {}), cmp: "prev" }) }));

  let line;
  if (live) line = [h("b", null, words.now), h("span", { class: "pl-vs" }, " compared with "), h("b", null, words.prev)];
  else if (!c.on) line = [h("b", null, words.now)];
  else if (c.ok) line = [h("b", null, words.now), h("span", { class: "pl-vs" }, " compared with "), h("b", null, words.prev),
    c.kind === "prev" ? null : h("span", { class: "pl-vs" }, c.kind === "year" ? " (the same days last year)" : " (the period you chose)")];
  else line = [h("b", null, words.now)];

  let why = null;
  if (c.on && !c.ok && !live) {
    const notMeasured = !c.inc && c.b && beforeState(c.b) === "not_measured";
    why = notMeasured ? notMeasuredWords(r, s, { firstWhole: firstWholeDay(m.byDay, m.firstDay), site: m.site, firstDay: m.firstDay }) : c.why;
  }
  const first = m.firstDay ? m.byDay?.get(m.firstDay) : null;
  const since = m.firstDay ? `${m.site} is measured from ${short(m.firstDay)}${first && first.state !== "ok" ? " (part of that day)" : ""}` : null;
  return h("div", { class: "pl", role: "region", "aria-label": "Period" },
    sw,
    h("p", { class: "pl-now" }, line),
    why ? h("p", { class: "pl-why", role: "note" }, why) : null,
    h("p", { class: "pl-how" }, [words.how, since, "every day checked against the raw log"].filter(Boolean).join(" · ")));
}
