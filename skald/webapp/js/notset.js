// What a site has never sent or never set up, so a page says "not set up" with how
// to set it up, never 0, 0% or a day-long "outage" (the rule: a figure not recorded
// is not recorded, never zero). Pure functions over the data files, no page code:
// tests/js/notset.mjs checks them.
//
//   everSent(events, e)    the beacon has recorded event e on some day (events.json `sent`)
//   howToSend(e)           one line: how the site sends event e
//   neverRecorded(leads)   the lead kinds the lead store has never recorded (leads.json)
//   heartbeatOn(ours)      the heartbeat has been seen on some day (ours.json)
//   quietLimit(day)        minutes of log silence that are long for this day's traffic

/* events.json `sent` names every event the beacon recorded on any day, withheld days
   included. An older file without it: its own rows and today's spool. */
export function everSent(f, e) {
  if (!f) return false;
  if (f.sent && typeof f.sent === "object") return Object.prototype.hasOwnProperty.call(f.sent, e);
  return (f.rows || []).some((x) => x[1] === e && x[5] > 0) || !!f.today?.events?.[e];
}

/* The script tag has never sent any event for this site, not even a page view (2.43: the page
   shows how to connect it, js/ui/connect.js). No events file at all counts as never. */
export function neverSentAny(f) {
  if (!f) return true;
  if (f.sent && typeof f.sent === "object") return !Object.keys(f.sent).length;
  return !(f.rows || []).some((x) => x[5] > 0) && !Object.keys(f.today?.events || {}).length;
}

const HOW = {
  cta_click: "Add data-skald-cta=\"name\" to a button or link.",
  book_demo_open: "Your site's own code sends it: one line, in Help › The tracking script.",
  demo_booked: "Your site's own code sends it: one line, in Help › The tracking script.",
  signup_start: "Mark the sign-up form data-skald=\"signup\": the tag sends it when someone starts filling it in.",
  signup_submit: "Mark the sign-up form data-skald=\"signup\": the tag sends it on submit. A form your script sends without a submit needs one line of your own code (Help › The tracking script).",
  contact_submit: "Mark the contact form data-skald=\"contact\": the tag sends it on submit.",
  waitlist_submit: "Mark the early-access form data-skald=\"waitlist\": the tag sends it on submit.",
};
export const howToSend = (e) => HOW[e] || "The tracking tag sends it by itself the first time it happens on a page.";

const LEAD_KINDS = ["signup", "contact", "waitlist", "demo_opened", "demo_booked"];

/* The kinds the lead store has not recorded on any day it was read (from `since`,
   withheld days left out): the website does not send them there. Demo bookings
   usually come from the booking tool instead (Bookings). */
export function neverRecorded(f) {
  const seen = new Set();
  for (const d of f?.days || []) {
    if (d.state === "withheld" || (f.since && d.day < f.since)) continue;
    for (const [k, v] of Object.entries(d.leads || {})) if (v) seen.add(k);
  }
  return new Set((f?.types || LEAD_KINDS).filter((k) => !seen.has(k)));
}

/* A heartbeat never seen is "not set up": no 0% uptime and no outage list for a check
   that does not exist. One seen once and silent since stays an outage, as it should. */
export function heartbeatOn(f) {
  return [...(f?.days || []), f?.today].some((d) => (d?.heartbeat?.seen || 0) > 0);
}

/* A silent stretch is worth a look only when it is long for this site: at least an
   hour, and 40 times the day's average wait between two lines. On a quiet site (a few
   hundred lines a day) a night's lull of an hour or more is normal, and every day
   would be amber; a busy site that goes quiet for an hour has stopped logging. */
export const quietLimit = (d) => Math.max(60, Math.round((40 * 1440) / Math.max(1, d?.lines || 0)));
