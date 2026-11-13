// Leads › What: Demos (#33): Calendar bookings was a tab of its own until #33; it is this
// filter of Leads now, with its stage steps above the list. One short strip: opened the booking,
// chose a time, booked, then what happened to the bookings (cancelled, rescheduled, no-show,
// won, lost), as counts on the period's checked days of conversions.json (the same days and the
// same file as the Leads figure). A step this site never sends is left off; "Chose a time" is
// the page's own event count (events.json), shown only where the page sends it.
//
// Booked of opened is a completion rate, so it follows the one rule (sa-rate.js): shown only
// when every booking came from the page's script, else "not comparable" and why.
//
//   isBooking(f, a)              a demo action, or one a booking or payment tool reported
//   stepsOf(f, a, days, events)  [[key, words, n | null]] and the tools that reported it
//   bookingSteps(m, s, r, a)     the strip (null when the action is not a booking)

import { h, n, reduced } from "../ui.js";
import { convFile, actionName, toolName } from "./leadfigs.js";
import { periodDays } from "./sa-period.js";
import { rateOf } from "./sa-rate.js";
import { connectCard } from "../ui/connect.js";
import { fedFromData } from "../connect-plan.js";

// Tools that book or take payment: an action any of them reported is a booking action.
export const BOOKING_TOOLS = new Set(["calendly", "calcom", "stripe"]);
const FIN = ["completed", "paid"];

export function isBooking(f, a) {
  if (!f || !a) return false;
  if ((f.demo_actions || ["demo"]).includes(a)) return true;
  return (f.days || []).some((d) => d.state === "ok" && Object.keys(d.by?.tool?.[a] || {}).some((t) => BOOKING_TOOLS.has(t)));
}

/* The steps of action `a` over `days` (ISO): {steps: [[key, words, n|null]], tools: {tool: n},
   ok: days counted}. A stage the site never sent on any day of the file is left off. */
export function stepsOf(f, a, days, events = null) {
  const want = new Set(days);
  const sum = {}, ever = new Set(), tools = {};
  let ok = 0;
  for (const d of f?.days || []) {
    if (d.state !== "ok") continue;
    for (const [st, v] of Object.entries(d.stages?.[a] || {})) if (v) ever.add(st);
    if (!want.has(d.day)) continue;
    ok += 1;
    for (const [st, v] of Object.entries(d.stages?.[a] || {})) sum[st] = (sum[st] || 0) + v;
    for (const [t, v] of Object.entries(d.by?.tool?.[a] || {})) tools[t] = (tools[t] || 0) + v;
  }
  let chosen = null;
  if (events && (events.events || []).some((e) => e.name === "calendly_time_selected") && (f.demo_actions || ["demo"]).includes(a)) {
    chosen = (events.days || []).filter((d) => want.has(d.day) && d.state === "ok").reduce((x, d) => x + (d.events?.calendly_time_selected || 0), 0);
  }
  const steps = [
    ever.has("started") ? ["started", "Opened the booking", sum.started || 0] : null,
    chosen != null ? ["chosen", "Chose a time", chosen] : null,
    ["booked", "Booked", FIN.reduce((x, st) => x + (sum[st] || 0), 0)],
    ...[["cancelled", "Cancelled"], ["rescheduled", "Rescheduled"], ["no_show", "No-show"], ["won", "Won"], ["lost", "Lost"]]
      .filter(([k]) => ever.has(k)).map(([k, w]) => [k, w, sum[k] || 0]),
  ].filter(Boolean);
  return { steps, tools, ok };
}

export function bookingSteps(m, s, r, a) {
  const f = convFile(m);
  if (!isBooking(f, a)) return null;
  const { steps, tools, ok } = stepsOf(f, a, periodDays(m, r), m.x.events);
  if (!ok) return null;
  const top = Math.max(1, ...steps.map(([, , v]) => v || 0));
  const started = steps.find(([k]) => k === "started")?.[2] || 0, booked = steps.find(([k]) => k === "booked")?.[2] || 0;
  const rate = started ? rateOf({ started, done: booked, tools }, f.min_rate || 10) : null;
  const by = Object.keys(tools).filter((t) => tools[t]).sort((x, y) => tools[y] - tools[x]).map(toolName);
  const noTool = (f.demo_actions || ["demo"]).includes(a) && fedFromData("bookings", m) === false
    ? connectCard(m, "bookings", { s, mode: "line", title: "No booking tool connected", line: "Calendly or Cal.com would add each booking's every step." }) : null;
  return h("section", { class: "s sa-steps", "aria-label": `${actionName(a)}: each step` },
    h("h2", null, `${actionName(a)}: each step`),
    h("ul", { class: `blist${reduced() ? "" : " play"}` }, steps.map(([k, words, v], i) => h("li", null,
      h("span", { class: "bl-bar", style: { width: `${((v || 0) / top) * 100}%`, background: ["started", "chosen", "booked"].includes(k) ? "var(--g-people)" : "var(--ink-3)", animationDelay: `${i * 0.03}s` } }),
      h("span", { class: "bl-l" }, words), h("span", { class: "bl-v" }, v == null ? "not tracked" : n(v)),
      h("span", { class: "bl-p" }, k === "booked" && rate ? (rate.rate != null ? `${rate.words} of opened` : h("span", { class: "few", title: rate.why }, rate.words)) : "")))),
    h("p", { class: "note" }, `${by.length ? `Reported by ${by.join(", ")}. ` : ""}Counted on the period's checked days, when each booking came in; the list below has one row per booking.${rate && rate.rate == null && rate.why ? ` Booked of opened: ${rate.words}. ${rate.why}` : ""}`),
    noTool);
}
