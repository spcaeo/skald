// A funnel's lead steps on a site whose leads come from its own server or its tools (#25,
// 2.46.4). funnels.json counts a lead step from the lead database only, so on a site with
// none (no `leads.db`) every lead step read "not recorded". Here such a step counts the
// leads in conversions.json instead: the day counts that file already holds, each checked
// by its second count (audit_conversions.py) and withheld when it disagrees. Only the
// days that passed are added up, each lead once (a sign-up that then paid is one lead:
// conversions_data leaves the repeat finish out of the day counts).
//
// A lead step names lead kinds (signup, contact, waitlist, demo_opened, demo_booked) or
// any action the site has sent (xray, trial...). It is counted on the funnel's visit days.
// With a starting source the step is not split: a lead keeps its own first touch, which
// is not the visit's source type.

import { actionName } from "./leadfigs.js";

export const LEAD = { signup: "Sign-up", contact: "Contact form", waitlist: "Early access", demo_opened: "Opened Book a demo", demo_booked: "Demo booked" };
const FINISHED = ["completed", "paid"];
// A lead kind of the lead database, as the tools' actions and stages.
const AS_ACTIONS = { signup: [["signup", FINISHED]], contact: [["contact", FINISHED]], waitlist: [["waitlist", FINISHED]],
  demo_booked: [["demo", FINISHED]], demo_opened: [["demo", ["started"]]] };
export const ACTION = /^[a-z0-9_]{1,40}$/;

export const leadName = (t) => LEAD[t] || actionName(t);
const wanted = (types) => types.flatMap((t) => AS_ACTIONS[t] || [[t, FINISHED]]);
const usable = (f) => !!(f && f.available && Array.isArray(f.days));

/* The actions the site has sent on its checked days, most rows first: [[action, name]]. */
export function sentActions(f) {
  if (!usable(f)) return [];
  const total = {};
  for (const d of f.days) {
    if (d.state !== "ok") continue;
    for (const [a, per] of Object.entries(d.stages || {})) total[a] = (total[a] || 0) + Object.values(per || {}).reduce((x, y) => x + (y || 0), 0);
  }
  return Object.keys(total).filter((a) => total[a]).sort((a, b) => total[b] - total[a] || a.localeCompare(b)).map((a) => [a, actionName(a)]);
}

/* The leads of a step on the given days: {n, days, of} (days: how many of the `of` days were
   checked and added up), or null when there is nothing to count from: no conversions file,
   a starting source, or none of the days checked. */
export function toolLeads(f, types, days, fsrc) {
  if (!usable(f) || fsrc || !types?.length) return null;
  const on = new Set(days);
  const want = wanted(types);
  let n = 0, seen = 0;
  for (const d of f.days) {
    if (!on.has(d.day) || d.state !== "ok") continue;
    seen++;
    for (const [a, stages] of want) for (const st of stages) n += d.stages?.[a]?.[st] || 0;
  }
  return seen ? { n, days: seen, of: on.size } : null;
}

/* True when the site has never sent any of the step's actions (on any checked day). */
export function neverSent(f, types) {
  if (!usable(f)) return false;
  const want = wanted(types);
  return !f.days.some((d) => d.state === "ok" && want.some(([a, stages]) => stages.some((st) => d.stages?.[a]?.[st])));
}
