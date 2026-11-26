// Traffic > Retention: why the curve goes up or down (SKALD-66).
//
// The curve's point at step k averages every cohort with that cell counted, so two
// points can rest on different cohorts: a newer cohort has not had k weeks yet. A move
// from one step to the next is then partly who is counted, not what people did. Each
// step is read twice: as the curve draws it, and on the cohorts counted at both steps
// only (the same people), so the two can be told apart.
//
// Nothing new is counted: every figure is a sum of the triangle's cells, which
// retention.py counts and audit_retention.py recounts, as the curve itself is.

import { n } from "../ui.js";

export const FEW = 100;          // a point over fewer new visitors is "too few to trust"
const p1 = (back, size) => (size ? `${((back / size) * 100).toFixed(1)}%` : "-");
const people = (k) => `${n(k)} ${k === 1 ? "person" : "people"}`;
const pts = (d) => `${Math.abs(d).toFixed(1)} point${Math.abs(d).toFixed(1) === "1.0" ? "" : "s"}`;

/* Each step between two counted points: the curve's move, and the move on the same cohorts.
   pick(c, k) -> {state, back, size} as the triangle reads a cell. */
export function steps(cohorts, K, pick) {
  const at = (k) => cohorts.map((c) => ({ c, x: pick(c, k) })).filter(({ x }) => x.state === "ok" && x.back != null && x.size);
  const out = [];
  for (let k = 2; k <= K; k += 1) {
    const a = at(k - 1), b = at(k);
    if (!a.length || !b.length) continue;
    const sum = (list) => list.reduce((s, { x }) => ({ back: s.back + x.back, size: s.size + x.size }), { back: 0, size: 0 });
    const A = sum(a), B = sum(b);
    const both = b.map(({ c }) => c).filter((c) => a.some((y) => y.c === c));
    const sa = sum(a.filter(({ c }) => both.includes(c))), sb = sum(b.filter(({ c }) => both.includes(c)));
    out.push({
      from: k - 1, to: k,
      before: { ...A, cohorts: a.length }, after: { ...B, cohorts: b.length },
      move: (B.back / B.size - A.back / A.size) * 100,
      same: both.length ? { cohorts: both, before: sa, after: sb, move: (sb.back / sb.size - sa.back / sa.size) * 100 } : null,
      fewer: b.length < a.length,
      mixed: !(both.length === a.length && both.length === b.length),
      few: B.size < FEW,
    });
  }
  return out;
}

const mixWords = (st, at, unit) => (st.fewer
  ? `that ${at(st.to)} counts fewer cohorts (${n(st.after.cohorts)} of ${n(st.before.cohorts)}): the newer ones have not had ${st.to} ${unit}s yet`
  : `that the two steps count different cohorts (a cell held back or not recorded)`);

/* One plain sentence per step. unit: "week" or "day"; name(c): a cohort's name. */
export function stepWords(st, unit, name) {
  const at = (k) => `${unit} +${k}`;
  const dir = Math.abs(st.move) < 0.05 ? "no change" : `${st.move > 0 ? "up" : "down"} ${pts(st.move)}`;
  let line = `${at(st.from)} → ${at(st.to)}: ${dir} (${p1(st.before.back, st.before.size)} → ${p1(st.after.back, st.after.size)}).`;
  if (st.mixed && st.same) {
    const who = st.same.cohorts.length === 1 ? `the ${name(st.same.cohorts[0])} cohort` : `the same ${n(st.same.cohorts.length)} cohorts`;
    const m = st.same.move;
    line += ` On ${who} only (${n(st.same.after.size)} new visitors): ${p1(st.same.before.back, st.same.before.size)} → ${p1(st.same.after.back, st.same.after.size)} (${n(st.same.before.back)} → ${people(st.same.after.back)}).`;
    // "Hardly moved": under a quarter point, or under a quarter of the curve's own move.
    // "The other way": the same people moved against the curve, so its move is all who is counted.
    if (Math.abs(st.move) < 0.05 && Math.abs(m) >= 0.25) {
      line += ` The curve held, but on the same people it went ${m > 0 ? "up" : "down"} ${pts(m)}: ${mixWords(st, at, unit).replace(/^that /, "")}, and that hides it.`;
    } else if (Math.abs(m) >= 0.25 && Math.abs(st.move) >= 0.05 && Math.sign(m) !== Math.sign(st.move)) {
      line += ` On the same people it went ${m > 0 ? "up" : "down"}: the curve goes ${st.move > 0 ? "up" : "down"} only because of ${mixWords(st, at, unit).replace(/^that /, "how ")}.`;
    } else {
      line += Math.abs(m) < 0.25 || Math.abs(m) < Math.abs(st.move) / 4
        ? ` On the same people it hardly moved: the rest is ${mixWords(st, at, unit)}.`
        : ` Part of the move is ${mixWords(st, at, unit)}.`;
    }
  } else if (st.mixed) {
    line += ` No cohort is counted at both steps, so this is ${mixWords(st, at, unit).replace(/^that /, "only which cohorts are counted: ")}.`;
  } else {
    line += ` The same ${st.after.cohorts === 1 ? "cohort" : `${n(st.after.cohorts)} cohorts`} at both steps, so this is a change in what people did.`;
  }
  if (st.few) line += ` Too few to trust: under ${FEW} new visitors.`;
  return line;
}
