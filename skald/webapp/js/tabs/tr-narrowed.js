// What Sources, Pages and Places & devices share while Traffic's filter bar is on (SKALD-62):
// a holder that waits for the filtered figures (narrow.js) and draws the tab's body with them,
// the line that says what is counted and how, the words for a list the filter cannot split,
// and Compare's B from the same answer.

import { h, n } from "../ui.js";
import { shown } from "../labels.js";
import { countryName } from "./readers.js";
import { narrow, picksOf, gapWords } from "../narrow.js";

/* "visits from the USA, on mobile" */
export function pickWords(s) {
  return picksOf(s).map(([k, v]) => (k === "country" ? `from ${countryName(v)}` : k === "source" ? `from ${shown(v)}` : `on ${shown(v).toLowerCase()}`)).join(", ");
}

/* The tab's body drawn from the filtered figures: build(N, c) -> nodes, once they are here. */
export function waiting(m, s, r, c, build) {
  const holder = h("div", { class: "tf-wait", "aria-live": "polite" },
    h("p", { class: "empty", role: "status" }, `Counting the visits ${pickWords(s)}…`));
  narrow(m, s, r, { b: c.ok ? c.b : null }).then((N) => {
    // Nothing known for the filter (an answer that did not add up, today's visits not yet
    // today's count): said, with why, never as 0 visits.
    if (!N.a || N.a.readers == null) {
      holder.replaceChildren(h("div", { class: "state bad", role: "alert" }, h("div", null, h("strong", null, `Not shown for the visits ${pickWords(s)}. `),
        (N.problems || []).join(" ") || "The filtered figures did not add up.", " Clear the filter to see every visit.")));
      return;
    }
    const cn = compareWith(c, N);
    const notes = (N.problems || []).map((x) => h("p", { class: "note tf-problem" }, x));
    if (c.ok && !cn.ok) notes.unshift(h("p", { class: "note tf-problem" }, "Not compared under the filter: B has no day with the visit records this filter needs (they are kept from the day they began), so A stands alone."));
    holder.replaceChildren(...[build(N, cn), notes].flat(Infinity).filter(Boolean));
  }).catch((e) => holder.replaceChildren(h("p", { class: "empty", role: "alert" }, `The filtered figures could not be drawn: ${e.message || e}. Clear the filter to see every visit.`)));
  return holder;
}

/* Compare mode on the filtered figures: B from the same answer, or off when it has none. */
export function compareWith(c, N) {
  if (!c?.ok || !N.b) return { on: !!c?.on, ok: false };
  // Only the days that hold the crossed figures count, on each side: a B before they were kept
  // is not compared (it would read as nothing, and every row as new), and Per day divides by them.
  const counted = (x) => Math.max(0, (x.used ?? 0) - (x.unmeasured?.length || 0));
  const a = counted(N.a), b = counted(N.b);
  if (!a || !b) return { on: true, ok: false };
  return { ...c, bT: { by: N.b.by, readers: N.b.readers, unmeasured: N.b.unmeasured?.length ? { by: N.b.unmeasured.length } : null },
    used: { a, b }, perDay: c.perDay };
}

/* The figures as a tab's totals: {readers, by}. */
export const totalsOf = (N) => ({ readers: N.a.readers, by: N.a.by });

/* What the filtered lists count, and from where: under the tab's lists. */
export function howNote(m, s, N) {
  const from = N.how === "visits" ? "counted from today's visits, each list used only when they give back today's own figures exactly"
    : N.how?.startsWith("page") ? `worked out on this page from the daily cube (the last 90 days): a busy day's smallest combinations cannot be split and are left out${N.how.includes("+") ? "; today from today's visits" : ""}`
    : N.how?.includes("+") ? "counted from every visit of the whole days (the verified visit records) and from today's visits"
    : "counted from every visit of the whole days (the verified visit records, all labels at once)";
  const gaps = gapWords(N.a);
  return h("p", { class: "note tf-how" }, `Only the ${n(N.a.readers)} visits ${pickWords(s)}: ${from}.${gaps ? ` ${gaps[0].toUpperCase()}${gaps.slice(1)}.` : ""}`);
}

/* A list the filter cannot split: said where the list would be, never the whole site's. */
export function notSplit(title, why, { level = "h2" } = {}) {
  return h("section", { class: "s tf-not" }, h(level, null, title), h("p", { class: "empty" }, `Not split by the filter: ${why} Clear the filter to see it for every visit.`));
}
export function notSplitLine(why) {
  return h("p", { class: "empty" }, `Not split by the filter: ${why}`);
}
