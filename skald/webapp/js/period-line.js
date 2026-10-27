// The period line on Overview › Summary and Traffic › Pages (release 2, cards S2, S3, P2):
// two switches, "Include today" (inc=1) and "Compare with the period before" (cmp=prev),
// then the exact dates in words: "Last 7 whole days: 18–24 Oct compared with 11–17 Oct",
// what the period means ("On 15 Jan that is 8–14 Jan against 1–7 Jan"), and since when
// the site is measured. When the period before was not measured it says so, and the first
// day a full comparison comes; it never shows a 0 or a rise against nothing.
//
// The period buttons stay in the top bar (one picker for every tab); Today is its
// "Today · Live" switch. Both switches are in the address, so Back and Forward work.
//
// 2.42 (the UX build's polish): the two switches moved to the top bar, so each has one
// place: Compare is the bar's Compare menu, Include today is in the period's More menu
// (main.js rangeMore). This line keeps the dates in words; what the period means and since
// when the site is measured are behind its (i).
//
// 2.43: Include today is one press again, as a switch at the start of this line (it took two:
// More, then the item). Its one place is here, on the two tabs it changes; the More menu no
// longer has it. The period itself is still said once, in the title's line above; the switch
// changes those words ("Last 7 days including today ...") and says no dates of its own.

import { h, short } from "./ui.js";
import * as S from "./state.js";
import { info } from "./tabs/tiles.js";
import { rangeOf } from "./data.js";
import { isLive } from "./mode-live.js";
import { compareOf } from "./mode-compare.js";
import { incApplies, incOn, lineWords, notMeasuredWords, beforeState, firstWholeDay } from "./period-dates.js";

/* Include today, one press: shown only where it changes the figures (Summary and Pages, at 7,
   30 or 90 days, not Today live). The address key is inc=1 (kept as it was). */
export function incSwitch(s) {
  if (!incApplies(s) || isLive(s)) return null;
  const on = incOn(s);
  return h("button", { type: "button", role: "switch", class: `btn pl-sw${on ? " on" : ""}`, "aria-checked": String(on),
    title: on ? "Counting today so far: the period ends today. Press to count whole days only." : "Count today so far: the period ends today instead of yesterday.",
    onclick: () => S.set({ inc: on ? "" : "1" }) },
  h("span", { class: "pl-knob", "aria-hidden": "true" }), "Include today");
}

/* The line for this state, or null on a tab without it. */
export function periodLine(m, s) {
  const r = rangeOf(m, s);
  const c = compareOf(m, s);
  const live = isLive(s);
  const words = lineWords(r, s, { b: c.ok || c.inc ? c.b : null, live: m.live, today: m.today });

  // The scope line above (tabs/common.js periodWords) already gives this period's dates, so this
  // line only adds what it is compared with: one statement of the period per page.
  let line = null;
  if (live || (c.on && c.ok)) line = [h("span", { class: "pl-vs" }, "Compared with "), h("b", null, words.prev),
    live || c.kind === "prev" ? null : h("span", { class: "pl-vs" }, c.kind === "year" ? " (the same days last year)" : " (the period you chose)")];

  let why = null;
  if (c.on && !c.ok && !live) {
    const notMeasured = !c.inc && c.b && beforeState(c.b) === "not_measured";
    why = notMeasured ? notMeasuredWords(r, s, { firstWhole: firstWholeDay(m.byDay, m.firstDay), site: m.site, firstDay: m.firstDay }) : c.why;
  }
  const first = m.firstDay ? m.byDay?.get(m.firstDay) : null;
  const since = m.firstDay ? `${m.site} is measured from ${short(m.firstDay)}${first && first.state !== "ok" ? " (part of that day)" : ""}` : null;
  const sw = incSwitch(s);
  if (!line && !why && !sw) return null;
  return h("div", { class: "pl", role: "region", "aria-label": "Period" },
    line || sw ? h("p", { class: "pl-now" }, sw, line, line ? " " : null, line ? info([words.how, since, "every day checked against the raw log"].filter(Boolean).join(" · "), "this period") : null) : null,
    why ? h("p", { class: "pl-why", role: "note" }, why) : null,
  );
}
