// Events: what readers did inside the pages, counted by the site's own
// beacon on its own server (events.json, docs/BEACON.md): button clicks,
// form steps, demo bookings opened and made, links out, reading three
// quarters of a page, copying text, meeting the not-found page. People only;
// every figure is an aggregate with no visit key, so nothing here is joined
// to a visit. Only verified days count; today's spool is "not yet checked".
// Goals (beacon.goals, or Settings > Data > Script tag & goals): each goal per 100 visits
// by source, from days whose events, sources and log figures all passed
// their checks. skald.js sends every event here except CODE_ONLY
// (beacon.CODE_ONLY), which only the site's own code sends.

import { h, n, short } from "../ui.js";
import { rangeOf, pathMatch } from "../data.js";
import { lines, legend } from "../charts.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { head } from "./common.js";
import { info } from "./tiles.js";
import { sessions, isViewer } from "../access.js";
import { everSent, howToSend, neverSentAny } from "../notset.js";
import { connectCard, sourceLink, hashOf } from "../ui/connect.js";
import { formsOn } from "./leadfigs.js";

const COLS = ["cta_click", "book_demo_open", "demo_booked", "signup_start", "signup_submit", "contact_submit", "waitlist_submit", "outbound_click", "scroll_75", "copy_text", "404_view"];
const SHORT = { cta_click: "Clicks", book_demo_open: "Demo opened", demo_booked: "Demo booked", signup_start: "Sign-up started", signup_submit: "Sign-up sent", contact_submit: "Contact sent",
  waitlist_submit: "Early access", form_start: "Form started", form_submit: "Form sent", tel_click: "Phone", mailto_click: "Email", outbound_click: "Links out", scroll_75: "Read ¾", copy_text: "Copied", "404_view": "Not found", page_view: "Page views" };
// Sent by the site's own code only, never by the tag (beacon.CODE_ONLY).
const CODE_ONLY = ["book_demo_open", "demo_booked"];
const LINE = ["var(--g-people)", "var(--good)", "var(--opp)", "var(--ink-3)"];
// SKALD-66: what each event is, in one plain sentence (the tile says it under the count).
export const MEANING = {
  cta_click: "clicks on buttons and links marked as a call to action",
  book_demo_open: "times the demo booking was opened",
  demo_booked: "demos booked",
  signup_start: "times someone started the sign-up form",
  signup_submit: "sign-up forms sent",
  contact_submit: "contact forms sent",
  waitlist_submit: "early-access forms sent",
  outbound_click: "clicks on links to other sites",
  scroll_75: "times a visitor scrolled to three quarters of a page (a page that fits on the screen never counts)",
  copy_text: "times a visitor copied text from a page",
  "404_view": "visits to the not-found page",
  form_start: "times someone started filling in a form",
  form_submit: "times a form's send button was pressed (not forms received)",
  calendly_open: "times the Calendly booking was opened", calendly_time_selected: "times a time was chosen in Calendly", calendly_booked: "meetings booked in Calendly",
  cal_open: "times the Cal.com booking was opened", cal_booked: "meetings booked in Cal.com",
  hubspot_meeting_booked: "meetings booked in HubSpot",
  tel_click: "clicks on a phone number", mailto_click: "clicks on an email address",
  neetocal_open: "times the NeetoCal booking was opened", neetocal_time_selected: "times a time was chosen in NeetoCal", neetocal_booked: "meetings booked in NeetoCal",
  page_view: "page views the tag sent",
};
// The form and booking steps, start to end: a pair is shown when the site sends either side.
export const PAIRS = [["signup_start", "signup_submit"], ["form_start", "form_submit"], ["book_demo_open", "demo_booked"],
  ["calendly_open", "calendly_booked"], ["cal_open", "cal_booked"], ["neetocal_open", "neetocal_booked"]];
// The events worth setting up on any site; a booking tool's own events count themselves once its widget is on a page.
export const CORE = ["cta_click", "signup_start", "signup_submit", "book_demo_open", "demo_booked"];
const ORDER = [...COLS, "form_start", "form_submit", "tel_click", "mailto_click", "calendly_open", "calendly_time_selected", "calendly_booked", "cal_open", "cal_booked",
  "hubspot_meeting_booked", "neetocal_open", "neetocal_time_selected", "neetocal_booked", "page_view"];

// SKALD-67: the version from which the tag counts a form only when it has a field a person types
// into (or a data-skald mark), and never a pop-up's close button. Days before it cannot be recounted.
export const FORMS_SINCE = "2.60.0";

/* Under the form step (SKALD-67): what Form sent counts; the forms Leads & sales received on the
   same verified days from the site's server or form tools, never the tag's own rows (leadfigs.js
   formsOn; the whole site only; only when a hook reports forms); what the tag counted before FORMS_SINCE. */
export function formNotes(m, s, days) {
  const out = [h("p", { class: "note ev-sent" }, "Form sent counts presses of a form's send button, not forms received: a send that the form's own code refuses, or that fails, still counts.")];
  const got = days && days.length ? formsOn(m, days) : null;
  if (got && got.ok && (s.path || s.source || (s.view && s.view !== "all"))) out.push(h("p", { class: "note ev-leads" }, "Forms received is for the whole site: clear the page, source and page-group filters to see it here."));
  else if (got && got.ok) {
    const left = [got.held.length ? `${got.held.map(short).join(", ")} did not pass Leads & sales' checks` : "", got.before.length ? `${got.before.map(short).join(", ")} not recorded there` : ""].filter(Boolean).join("; ");
    const part = got.whole ? "" : ` (on ${n(got.ok)} of the ${n(got.of)} days counted above: ${left})`;
    out.push(h("p", { class: "note ev-leads" }, h("b", null, `Forms received: ${n(got.forms)}`), `${part}. Forms your site's server or form tools reported to Leads & sales on the same days, not counted by the tag; demo bookings are not in it. `,
      h("a", { href: hashOf({ tab: "sales/summary" }) }, "Leads & sales")));
  }
  out.push(h("p", { class: "note ev-before" }, `Before Skald ${FORMS_SINCE}, Form started and Form sent also counted a pop-up's close button, pickers and quizzes. Days counted before the update keep those and cannot be recounted.`));
  return out;
}

// An event the site has never sent is "not set up" with how to send it, never 0 or 0% (notset.js).
export { everSent, howToSend };

export const eventLabel = (f, e) => (f?.events || []).find((x) => x.name === e)?.label || SHORT[e] || e;

// The rows of a range: [day, event, label, path, source, n] on verified days, or today's spool.
export function eventRows(f, r, today) {
  if (!f) return { rows: [], days: [], live: false };
  if (r.kind === "today") {
    const t = f.today;
    return { rows: t && t.state === "ok" ? (t.rows || []).map((x) => [today, ...x]) : [], days: [], live: true, state: t?.state || "empty" };
  }
  const days = (f.days || []).filter((d) => d.day >= r.first && d.day <= r.last);
  const ok = new Set(days.filter((d) => d.state === "ok").map((d) => d.day));
  return { rows: (f.rows || []).filter((x) => ok.has(x[0])), days, ok, live: false };
}
const totals0 = (rows, e) => rows.some((x) => x[1] === e && x[5] > 0);
const sum = (rows, key) => { const out = {}; for (const x of rows) { const k = key(x); if (k != null) out[k] = (out[k] || 0) + x[5]; } return out; };

function pivot(rows, by, names) {
  const out = new Map();
  for (const x of rows) {
    const k = by(x);
    if (!out.has(k)) out.set(k, { k });
    const row = out.get(k);
    row[x[1]] = (row[x[1]] || 0) + x[5];
    row.total = (row.total || 0) + x[5];
  }
  return [...out.values()].map((row) => Object.fromEntries([["k", row.k], ["total", row.total], ...names.map((e) => [e, row[e] || 0])]));
}

function leftOut(days) {
  const bad = days.filter((d) => d.state === "withheld" || d.state === "missing");
  if (!bad.length) return null;
  return h("p", { class: "note" }, `Left out: ${bad.map((d) => `${short(d.day)} ${d.state === "withheld" ? "(did not pass the checks)" : "(not collected)"}`).join(", ")}.`);
}

// Goals: events per 100 visits by source over the range's countable days
// (events.json goals). Visits are the log's, by the visit's source; events
// are the beacon's, by the source the helper worked out. Two counts side by
// side, never joined per visit; no rate over fewer than min_rate visits.
const add = (into, obj) => { for (const [k, v] of Object.entries(obj || {})) into[k] = (into[k] || 0) + v; return into; };
function goals(f, r, s) {
  const g = f.goals;
  const edit = sessions() && !isViewer() ? h("a", { class: "linkish", href: "#settings/site/data?sub=script" }, "Edit goals") : null;
  const title = h("div", { class: "card-h start" }, h("h2", null, "Goals"), info("Each goal's events per 100 visits from each source. Visits come from the server log, events from the beacon: two counts side by side, never joined per visit. A day counts only when both passed their checks. No rate is given over fewer than 10 visits.", "Goals"), edit);
  if (!g) return h("section", { class: "s" }, title, h("p", { class: "note" }, sessions()
    ? "No goal is set. An admin chooses the events that count as goals in Settings > Data > Script tag & goals (Edit goals), for example Sign-up sent or Demo booked, to see each one per 100 visits by source."
    : "No goal is set. Name the events that count as goals under beacon.goals in the config (for example demo_booked, signup_submit) to see each one per 100 visits by source."));
  if (r.kind === "today") return h("section", { class: "s" }, title, h("p", { class: "note" }, "Goals count checked days only: today's appear after midnight."));
  const min = g.min_rate || 10;
  const days = (g.days || []).filter((d) => d.day >= r.first && d.day <= r.last);
  const ok = days.filter((d) => d.state === "ok");
  const out = [title];
  const visits = ok.reduce((a, d) => add(a, d.visits), {});
  const allVisits = Object.values(visits).reduce((a, v) => a + v, 0);
  const rate = (e, v) => (v >= min ? `${((100 * e) / v).toFixed(1)}` : "too few to say");
  if (!ok.length) out.push(h("p", { class: "note" }, days.length ? "No day in this range can be counted for goals yet." : "No beacon day in this range yet."));
  else {
    for (const goal of g.names || []) {
      const ev = ok.reduce((a, d) => add(a, d.events?.[goal]), {});
      const sources = [...new Set([...Object.keys(visits), ...Object.keys(ev)])].filter((k) => !s.source || k === s.source);
      const rows = sources.map((k) => ({ k, visits: visits[k] || 0, events: ev[k] || 0 }));
      const allEvents = Object.values(ev).reduce((a, v) => a + v, 0);
      const cols = [{ key: "k", label: "Source", drill: "source" }, { key: "visits", label: "Visits", num: true }, { key: "events", label: g.labels?.[goal] || eventLabel(f, goal), num: true },
        { key: "rate", label: "Per 100 visits", num: true, sort: (x) => (x.visits >= min ? x.events / x.visits : -1), fmt: (_, x) => rate(x.events, x.visits), csv: (x) => (x.visits >= min ? ((100 * x.events) / x.visits).toFixed(2) : "") }];
      out.push(h("h3", null, `${g.labels?.[goal] || eventLabel(f, goal)}: ${allVisits >= min ? `${rate(allEvents, allVisits)} per 100 visits` : "too few visits to say"}`),
        table(cols, { caption: `${g.labels?.[goal] || goal} per 100 visits by source`, rows, file: `goal-${goal}-${r.first}-to-${r.last}.csv`, sortKey: "visits", search: false, limit: 10,
          empty: "No visit or goal event in these days." }));
    }
    if (s.path) out.push(h("p", { class: "note" }, "Goals are for the whole site: visits by source cannot be split by page, so the page filter does not apply here."));
  }
  const left = days.filter((d) => d.state !== "ok");
  if (left.length) {
    const why = new Map();
    for (const d of left) why.set(d.why || "not counted", [...(why.get(d.why || "not counted") || []), short(d.day)]);
    out.push(h("p", { class: "note" }, `Left out of goals: ${[...why].map(([w, ds]) => `${ds.join(", ")} (${w})`).join("; ")}.`));
  }
  return h("section", { class: "s" }, ...out);
}

function refused(f) {
  const hp = f?.helper;
  if (!hp?.today && !hp?.yesterday) return null;
  const words = (c) => {
    if (!c) return "nothing yet";
    const ref = Object.entries(c).filter(([k]) => k.startsWith("refused_")).reduce((a, [, v]) => a + v, 0);
    return [`${n(c.accepted || 0)} accepted`, c.declined ? `${n(c.declined)} declined (Do Not Track or Global Privacy Control)` : null, c.not_people ? `${n(c.not_people)} from machines` : null,
      c.accepted_ours ? `${n(c.accepted_ours)} from our own addresses` : null, ref ? `${n(ref)} refused as malformed or from elsewhere` : null].filter(Boolean).join(", ");
  };
  return h("p", { class: "note" }, `What the beacon took in, today: ${words(hp.today)}; yesterday: ${words(hp.yesterday)}. The rules are in docs/BEACON.md in Skald's code.`);
}

export default function events(m, s) {
  const f = m.x.events;
  const r = rangeOf(m, s);
  // Traffic › Events since #33 (Leads & sales until then): Traffic's period, whole days.
  const out = [...head("Events", r, "What visitors did inside the pages, counted by the site's own beacon on its own server: buttons, forms, demo bookings, links out, reading three quarters of a page, copying text. People only, as totals: no event is tied to a visit or a person.", { banner: false })].filter(Boolean);
  // 2.43: the script tag is the source here; its row in Leads & tools, and its card when never sent.
  const back = sourceLink("leads");
  if (back) out[0].insertBefore(back, out[0].querySelector(".period"));
  if (!f || neverSentAny(f)) return [...out, connectCard(m, "script", { s })];
  const keep = pathMatch(s);
  const got = eventRows(f, r, m.today);
  const rows = got.rows.filter((x) => keep(x[3]) && (!s.source || x[4] === s.source));
  // SKALD-66: every event the site sends, not only the first eleven (form_start and the rest were never shown).
  const names = (f.events || []).map((x) => x.name).filter((e) => everSent(f, e) || totals0(rows, e));
  const totals = sum(rows, (x) => x[1]);
  // Visitors of the same verified days, for a rate per 100.
  const readers = got.live ? null : [...(got.ok || [])].reduce((a, d) => a + (m.byDay.get(d)?.state === "ok" ? m.byDay.get(d).readers || 0 : 0), 0);
  if (got.live) out.push(h("p", { class: "note" }, got.state === "ok" ? "Today so far, not yet checked: today's events are verified after midnight." : "No event recorded today yet."));
  if (!rows.length) {
    out.push(h("div", { class: "state" }, h("div", null, f.first_day ? `No event in this range${s.path || s.source ? " with these filters" : ""}. The beacon counts from ${short(f.first_day)}.` : "No event counted yet: the beacon starts counting the day the website release with it goes live.")), leftOut(got.days) || "", refused(f) || "");
    return out;
  }
  // The figures (SKALD-66): what visitors did, the events this site sends, biggest first, each
  // with what it is, its rate per 100 visitors and the pages it happened on most.
  // Beacon page views go last and stay out of the chart and the columns: they would dwarf the rest.
  const sent = names.filter((e) => everSent(f, e)).sort((a, b) => (a === "page_view") - (b === "page_view") || (totals[b] || 0) - (totals[a] || 0) || ORDER.indexOf(a) - ORDER.indexOf(b));
  const acts = sent.filter((e) => e !== "page_view");
  const topPages = (e) => Object.entries(sum(rows.filter((x) => x[1] === e), (x) => x[3])).sort((a, b) => b[1] - a[1]).slice(0, 2);
  const rate = (e) => (readers ? `${((100 * (totals[e] || 0)) / readers).toFixed(1)} per 100 visitors` : got.live ? "today so far" : "");
  out.push(h("section", { class: "s" }, h("h2", null, "What visitors did"),
    h("div", { class: "ev-tiles ev-did" }, sent.map((e) => {
      const most = topPages(e);
      return h("div", { class: "ev-t" }, h("span", { class: "ev-l" }, eventLabel(f, e)), h("b", null, n(totals[e] || 0)),
        h("small", { class: "ev-what" }, MEANING[e] ? `${MEANING[e][0].toUpperCase()}${MEANING[e].slice(1)}.` : ""),
        h("small", null, [CODE_ONLY.includes(e) && !totals[e] ? "sent by your own code" : rate(e),
          most.length ? `${rate(e) ? "; " : ""}most on ${most.map(([pth, v]) => `${pth} (${n(v)})`).join(", ")}` : ""].join("")));
    })),
    h("p", { class: "note" }, "Counts of events, not of people: one person can send the same event twice. A figure here is 0 only for an event this site has sent before."),
    leftOut(got.days)));
  // The steps through the forms and bookings the site uses: a side never sent is "Not set up",
  // and no share is given across it.
  const val = (e) => (everSent(f, e) ? h("b", null, n(totals[e] || 0)) : h("b", { class: "not-set", title: "Never sent by this site" }, "Not set up"));
  const step = (a, b) => {
    const unsent = [a, b].filter((e) => !everSent(f, e));
    return h("div", { class: "ev-step" }, h("div", null, h("span", null, eventLabel(f, a)), val(a)), h("span", { class: "ev-arrow", "aria-hidden": "true" }, "→"),
      h("div", null, h("span", null, eventLabel(f, b)), val(b)),
      unsent.length ? h("small", { class: "how" }, `No share: ${unsent.map((e) => eventLabel(f, e)).join(" and ")} never sent. ${howToSend(unsent[unsent.length - 1])}`)
        : h("small", null, totals[a] >= 5 ? `${n(totals[b] || 0)} of ${n(totals[a])} went on (${Math.round((100 * (totals[b] || 0)) / totals[a])}%)` : totals[a] ? "too few to rate" : ""));
  };
  const pairs = PAIRS.filter(([a, b]) => everSent(f, a) || everSent(f, b));
  if (pairs.length) out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, "Through the forms"), info("Each count is of events, not of people: one person can start a form twice. A share is given from five starts on.", "Through the forms")),
    h("div", { class: "ev-steps" }, pairs.map(([a, b]) => step(a, b))),
    pairs.some(([a]) => a === "form_start") ? formNotes(m, s, got.live ? null : [...(got.ok || [])].sort()) : null));
  // Not set up yet: one line, the how behind one button (it was six big tiles of set-up words).
  const unset = CORE.filter((e) => !everSent(f, e) && !pairs.some((pr) => pr.includes(e)));
  if (unset.length) out.push(h("section", { class: "s ev-unset" }, h("p", null, h("b", null, "Not set up yet: "), `${unset.map((e) => eventLabel(f, e)).join(", ")}. This site has never sent ${unset.length === 1 ? "it" : "them"}, so there is no count, not a zero.`),
    h("details", null, h("summary", null, "How to set them up"),
      h("ul", null, unset.map((e) => h("li", null, h("b", null, `${eventLabel(f, e)}: `), howToSend(e)))),
      h("p", { class: "note" }, "The tracking tag sends the rest by itself, booking tools included (Calendly, Cal.com, NeetoCal, HubSpot), once they are on a page. Demo booking opened and Demo booked come from your site's own code: the Help guide “The tracking script” shows the one line."))));
  // Per day.
  if (!got.live && r.length > 1) {
    const byDay = new Map(got.days.map((d) => [d.day, d]));
    const perDay = new Map();
    for (const x of rows) { const o = perDay.get(x[0]) || {}; o[x[1]] = (o[x[1]] || 0) + x[5]; perDay.set(x[0], o); }
    const days = [];
    for (let d = r.first; d <= r.last; d = new Date(Date.parse(`${d}T12:00:00Z`) + 864e5).toISOString().slice(0, 10)) {
      const e = byDay.get(d);
      days.push(e?.state === "ok" ? { day: d, state: "ok", ev: perDay.get(d) || {} } : { day: d, state: e?.state === "withheld" ? "withheld" : e?.state === "before" ? "before" : "missing" });
    }
    const series = acts.filter((e) => totals[e]).slice(0, LINE.length).map((e, i) => ({ name: eventLabel(f, e), color: LINE[i], get: (d) => d.ev?.[e] ?? 0 }));
    if (series.length) out.push(h("section", { class: "s" }, h("h2", null, "Per day"), h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not counted", "", "hatch"]], true),
      lines(days, series, { label: "Events per day", H: 210 }))));
  }
  if (f.goals !== undefined) out.push(goals(f, r, s));
  // Which button or form, on which page.
  const which = Object.entries(sum(rows, (x) => `${x[1]}\u0001${x[2]}\u0001${x[3]}`)).map(([k, v]) => { const [e, label, path] = k.split("\u0001"); return { e: eventLabel(f, e), label: label || "-", path, v }; });
  out.push(h("section", { class: "s" }, h("h2", null, "Which button or form"),
    table([{ key: "e", label: "Event" }, { key: "label", label: "Which" }, { key: "path", label: "Page", path: true, drill: "path" }, { key: "v", label: "Count", num: true }],
      { caption: "Events by button or form and page", rows: which, file: `events-which-${r.first}-to-${r.last}.csv`, sortKey: "v", limit: 12 })));
  // By page and by source: one column per kind of event that happened.
  const seen = acts.filter((e) => totals[e]);
  const cols = (first, key) => [first, ...seen.map((e) => ({ key: e, label: SHORT[e] || eventLabel(f, e), num: true })), { key: "total", label: "All", num: true }];
  const flagged = new Set((got.days || []).flatMap((d) => (d.anomalies || []).filter((a) => a.kind === "path").map((a) => a.path)));
  out.push(h("section", { class: "s" }, h("h2", null, "By page"),
    table(cols({ key: "k", label: "Page", path: true, fmt: (v) => h("span", null, h("button", { type: "button", class: "linkish ev-pg", title: "This page's story", onclick: () => S.set({ tab: "traffic/pages", page: v }) }, v),
      flagged.has(v) ? h("span", { class: "rb warn", title: "More events than page views allow on a day: checked, and left in only if it passed" }, "flagged") : null), csv: (x) => x.k }),
    { caption: "Events by page", rows: pivot(rows, (x) => x[3], seen), file: `events-by-page-${r.first}-to-${r.last}.csv`, sortKey: "total", limit: 12 })));
  // A day whose sources did not recount keeps its totals but not its sources (source null).
  const unsourced = (got.days || []).filter((d) => d.by_source === "withheld").map((d) => short(d.day));
  out.push(h("section", { class: "s" }, h("h2", null, "By source"), h("p", { class: "sub" }, "The source of the visit each event happened in."),
    table(cols({ key: "k", label: "Source", drill: "source" }), { caption: "Events by source", rows: pivot(rows.filter((x) => x[4] != null), (x) => x[4], seen), file: `events-by-source-${r.first}-to-${r.last}.csv`, sortKey: "total", search: false }),
    unsourced.length ? h("p", { class: "note" }, `Left out by source: ${unsourced.join(", ")} (the recount by source did not match; the day's totals stand).`) : null));
  out.push(refused(f));
  return out;
}
