// "No mail server", said at once (2.42, the UX audit's "Get the daily mail" finding). Before,
// a dialog with no mail server behind it waited for good for a confirm mail that could never
// go ("Waiting for owner@example.com to press the link..."), and said nothing about why.
//
// The helper's answers say whether this install can send mail at all:
//   GET settings, POST settings/save     mail_server: {ready, missing} (settings_api.py)
//   GET settings/reports                 mail_ready: true | false (client_reports_api.py)
//
//   mailReady(answer)              true, false, or null when the answer does not say
//   mailMissing(answer)            the plain sentence of what is missing ("" when it works)
//   waitingWords(answer, waiting)  the line about recipients not confirmed yet, which never
//                                  says "waiting" when no mail can be sent
//   mailServerNote(answer, opts)   null when mail works; else one card: a pill, what it
//                                  stops, what is missing, and "Who will set it up?" (Me for
//                                  an install admin: the page to fill; My developer: a message
//                                  to copy). opts: { what, site, route, origin }
//                                  what: what cannot go, e.g. "the confirm mail and the daily mail"
//                                  route: {key, value} of the dialog it is drawn in, so the
//                                  answer is kept in the address as by= (ui/who.js)
//
// Settings › Mail & reports (tabs/prefs.js, the Settings builder's) shows the same card:
// mailServerNote(r, { what: "the daily and weekly mail", site, route: null }) above the recipients, and
// waitingWords(r, r.mail_waiting) in place of its "A confirm link was mailed to ..." line.

import { h } from "./ui.js";
import { pill } from "./ui/pill.js";
import { whoStep, devPath, mePath } from "./ui/who.js";
import { ME } from "./access.js";

export const MAIL_PAGE = "#settings/site/mail?edit=smtp";     // Settings v2: the Mail server (SMTP) drawer

/* true or false from either answer's shape; null when it does not say (an older helper). */
export function mailReady(r) {
  if (!r || r.ok === false) return null;
  if (r.mail_server && typeof r.mail_server.ready === "boolean") return r.mail_server.ready;
  if (typeof r.mail_ready === "boolean") return r.mail_ready;
  return null;
}

export function mailMissing(r) {
  if (mailReady(r) !== false) return "";
  return r.mail_server?.missing || "Skald needs an SMTP server and a sender address.";
}

const list = (xs) => (xs.length < 3 ? xs.join(" and ") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

/* The recipients not confirmed yet, in one line; "" when nobody waits. */
export function waitingWords(r, waiting = r?.mail_waiting || []) {
  const who = (waiting || []).filter(Boolean);
  if (!who.length) return "";
  if (mailReady(r) === false) return `${list(who)} will get a link to confirm once the mail server is set. Until then no mail can go.`;
  return `A link to confirm was mailed to ${list(who)}. They get no reports until they press it.`;
}

/* What to send a developer: plain words, no secret, the place to do it. */
export function devMessage(origin = (typeof location !== "undefined" ? location.origin : "")) {
  return [`Please set up the mail server of our Skald${origin ? ` (${origin})` : ""}: it needs an SMTP server and a sender address.`,
    "As an install admin: Settings › Mail & reports › Mail server (SMTP), then Send a test mail.",
    "Or in its Docker settings: SKALD_SMTP_HOST, SKALD_SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SKALD_MAIL_FROM, then restart it."].join("\n");
}

const MAIL_IC = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5 8 9l5.5-4.5"/></svg>';

/* The card, or null when mail works (or the answer does not say). */
export function mailServerNote(r, { what = "the mail", site = "", route = null, origin } = {}) {
  if (mailReady(r) !== false) return null;
  const link = `${typeof location !== "undefined" ? `${location.origin}${location.pathname}` : ""}${MAIL_PAGE}`;
  const paths = {
    ...(ME.install_admin ? { me: mePath(() => [
      h("p", null, "Fill the SMTP server, its port, the sign-in and the sender address, then press Send a test mail."),
      h("p", null, h("a", { class: "btn", href: MAIL_PAGE }, "Set the mail server")),
    ]) } : {}),
    dev: devPath({ site, message: devMessage(origin), link }),
  };
  let who;
  if (Object.keys(paths).length > 1) {
    who = whoStep({ paths, route, question: "Who will set it up?", fallback: "me",
      subs: { me: "You are an install admin: one form in Settings.", dev: "Whoever runs this Skald server: a message to send them." } }).el;
  } else {
    // Only an install admin can set it: the message for them, without a question of one answer.
    who = h("div", { class: "ui-who-path" }, h("p", { class: "ui-who-q" }, "Whoever runs this Skald server sets it. Send them this:"));
    Promise.resolve(paths.dev()).then((nodes) => who.append(...[nodes].flat(Infinity).filter(Boolean)));
  }
  return h("section", { class: "ui-card bad mr-note", role: "status", "aria-label": "No mail server" },
    h("div", { class: "ui-card-h" }, h("span", { class: "ui-ic", html: MAIL_IC }), h("h3", null, "Skald cannot send mail yet"), h("span", { class: "ui-grow" }), pill("off", "Not set up")),
    h("p", { class: "ui-meta" }, `No mail server is set, so ${what} cannot go. ${mailMissing(r)}`),
    who);
}
