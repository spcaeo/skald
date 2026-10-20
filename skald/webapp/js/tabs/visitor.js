// The visitor drawer (2.12.0): one drawer for a visitor or a visit, wherever it
// appears - the visit grid, Real time's newest visits, Find a person, Leads &
// sales' people and conversion rows, the funnel's journeys and a one-visit flow.
// Same layout and details everywhere:
//
//   summary   first and last seen, visits ("4 visits over 9 days"), where the
//             visitor first came from (and by which link), country (flag, the
//             three-letter code, the name on hover), city when recorded,
//             device, browser and system
//   journey   each visit as a path (journeymap.js), newest first, animated
//   visits    the timeline: when, where from (with the first touch), landing,
//             pages in order, time on site, country (and city), device; the first visit
//             highlighted
//   leads and conversions linked to the visits
//   this visit (opened from a visit): its own labels and tags
//
// openVisitor(key) is the one way in. key is a journey (as app.json carries
// it), {q} (an address, email, visitor ID or lead: the person search), or
// {conversion} (a conversion's story: its visitor ID's visits by day).
//
// Privacy, as before: a journey alone is anonymous (labels, pages, times; its
// first touch is labels only). Every visit of the visitor is asked from the
// helper (people/visitor), for admins and owners only, and only where the site
// keeps addresses; each answer is written to the audit log. Nothing here
// guesses: a visit with no earlier one known says "first visit we know of".

import { h, n, duration, dayDiff } from "../ui.js";
import { when, time as tzTime } from "../tz.js";
import { openDrawer } from "../drawer.js";
import { shown } from "../labels.js";
import { mark } from "../icons.js";
import { DEMO, demoFile } from "../demo.js";
import { journeyMap, replayButton, sourceWords } from "../journeymap.js";
import { call } from "./ipmanager.js";
import { countryWords, flagEl, city, cityPlace, cityName } from "./readers.js";
import { mayFind, personParts } from "./person.js";
import { folded, visitFacts, cityShort } from "./visitlist.js";

const LINKS = ["vid", "address", "hash"];
export const BY = {
  vid: "by its visitor ID (the page script's)",
  address: "by its address and browser (kept visits)",
  hash: "by the 30-day code (no address kept)",
};
const NAMELESS = new Set(["(none)", "(not kept)", "(this site)", ""]);
const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
const dash = (v) => (v == null || v === "" ? "-" : String(v));
const sec = (title, ...kids) => h("section", { class: "dw-sec" }, h("h3", null, title), ...kids);
const today = () => when(Date.now())?.day || "";

// ------------------------------------------------------------ first touch words
/* Where a first touch came from, by name: the site or assistant, else its type. */
export function touchName(ft) {
  if (!ft) return "";
  return ft.via || (!NAMELESS.has(ft.referrer || "") ? ft.referrer : "") || shown(ft.source) || "";
}
export function ago(day) {
  const t = today();
  if (!day || !t) return "";
  const d = dayDiff(day, t);
  return d <= 0 ? "earlier today" : d === 1 ? "yesterday" : `${d} days ago`;
}
/* The grid's line: only when an earlier visit is known and came from elsewhere. */
export function touchLine(j) {
  const ft = j?.first_touch;
  if (!ft || !LINKS.includes(ft.by)) return "";
  const same = (ft.source || "") === (j.source || "") && (ft.via || "") === (j.via || "");
  return same ? "" : `first came from ${touchName(ft)}, ${ago(ft.day)}`;
}
// ------------------------------------------------------------ one model, many roads
/* A visit in the drawer's own shape. */
function visitOf(raw, kind) {
  const trail = (raw.trail || []).map((p) => (Array.isArray(p) ? { path: p[0], page: p[1] !== "app", at: p[2] ?? null } : p));
  const end = raw.end ? when(raw.end)?.t : (when(raw.start)?.t || 0) + (raw.seconds || 0) * 1000;
  return { start: raw.start, stop: raw.end || null, source: raw.source || "", via: raw.via || "", campaign: raw.campaign || "", referrer: raw.referrer || "",
    landing: raw.landing || trail[0]?.path || "", trail: folded(trail).map((p) => ({ ...p })), pages: raw.pages ?? trail.length, seconds: raw.seconds ?? null,
    country: raw.country || "", city: raw.city || "", device: raw.device || "", browser: raw.browser || "", os: raw.os || "", kind, first: !!raw.first,
    posted: (raw.posts || []).length > 0 || (raw.flags || []).includes("posted"), nf: (raw.flags || []).includes("not_found"),
    active: kind !== "script" && Date.now() - end < 5 * 60e3, day: raw.day, seq: raw.seq, first_touch: raw.first_touch, raw };
}

function ends(v, leads, convs) {
  const t0 = when(v.start)?.t || 0, t1 = when(v.stop || v.start)?.t || t0;
  const lead = leads.find((l) => l.visit_start === v.raw.start);
  const booked = convs.find((c) => c.action === "demo" && ["completed", "paid"].includes(c.stage) && (when(c.at)?.t || 0) >= t0 && (when(c.at)?.t || 0) <= t1 + 30 * 60e3);
  if (booked) return { kind: "booked", words: "booked a demo", detail: `A demo booked at ${at(booked.at)}` };
  if (lead) return { kind: "lead", words: `lead #${lead.lead}`, detail: `Lead #${lead.lead}${lead.type ? ` (${lead.type})` : ""}, made ${at(lead.created_at)}: matched by time to a form this visit sent` };
  if (v.posted) return { kind: "form", words: "sent a form" };
  return { kind: "left", words: v.active ? "still here" : "left", detail: v.nf ? "Left. This visit met a page not found (404)." : v.active ? "A request in the last 5 minutes" : "Left the site" };
}

function finish(model) {
  const vs = model.visits.sort((a, b) => (when(b.start)?.t || 0) - (when(a.start)?.t || 0));
  if (vs.length && !vs.some((v) => v.first) && model.firstKnown) vs[vs.length - 1].first = true;
  for (const v of vs) v.endNode = ends(v, model.leads, model.conversions);
  return model;
}

function fromJourney(j) {
  const v = visitOf(j, "journey");
  v.this = true;
  const ft = j.first_touch;
  const visits = [v];
  // The first visit, as far as the first touch knows it: its source and landing page, nothing invented.
  if (ft && LINKS.includes(ft.by)) {
    visits.push({ ...visitOf({ start: ft.start || ft.day, source: ft.source, via: ft.via, campaign: ft.campaign, landing: ft.landing,
      trail: ft.landing ? [{ path: ft.landing, page: true, at: null }] : [], pages: null, seconds: null }, "touch"), first: true, active: false });
  } else if (ft && ft.by === "none") v.first = true;
  return { title: "Visitor", journey: j, visits, leads: [], conversions: [], firstTouch: ft, how: ft && LINKS.includes(ft.by) ? ft.by : null, firstKnown: false };
}

function fromTimeline(j, got) {
  const visits = got.visits.map((r) => {
    const v = visitOf(r, r.kind === "script" ? "script" : "kept");
    if (j && r.day === j.day && r.seq === j.seq) { v.this = true; v.first_touch = j.first_touch; }
    return v;
  });
  return { title: "Visitor", journey: j, visits, leads: got.leads || [], conversions: got.conversions || [], withheld: got.withheld || {},
    firstTouch: j?.first_touch, how: "address", short: got.linked_by === "short_address", vid: got.vid_matched, firstKnown: true };
}

/* A visitor ID's page views ({at, path, source_type}) as visits: 30 minutes apart. */
export function pageViewVisits(views) {
  const out = [];
  let cur = null;
  for (const pv of [...(views || [])].sort((a, b) => String(a.at).localeCompare(String(b.at)))) {
    const t = when(pv.at)?.t || 0;
    if (!cur || t - cur.last > 30 * 60e3) { cur = { start: pv.at, t0: t, last: t, source: pv.source_type || "", trail: [] }; out.push(cur); }
    cur.trail.push({ path: pv.path, page: true, at: Math.round((t - cur.t0) / 1000) });
    cur.last = t;
    cur.end = pv.at;
  }
  return out.map((v) => visitOf({ ...v, landing: v.trail[0]?.path, pages: v.trail.length, seconds: Math.round((v.last - v.t0) / 1000) }, "script"));
}

function fromConversion(x) {
  const visits = x.journey ? pageViewVisits(x.journey) : (x.visits || []).map((d) => visitOf({ start: d.day, source: d.source, landing: (d.paths || [])[0],
    trail: (d.paths || []).map((p) => ({ path: p, page: true, at: null })), pages: (d.paths || []).length, seconds: null }, "script"));
  const steps = (x.steps || []).map((s) => ({ action: s.action, stage: s.stage, at: s.at, tool: s.tool }));
  return { title: "Visitor", visits, leads: [], conversions: steps.length ? steps : [{ action: x.action, stage: "completed", at: x.at, tool: x.tool }],
    how: x.browser ? "vid" : null, firstKnown: true, conversion: x };
}

function fromPerson(got) {
  const visits = (got.visits || []).map((r) => visitOf(r, "kept"));
  return { title: `${{ ip: "IP address", email: "Email", vid: "Visitor ID", lead: "Lead" }[got.query.kind]}: ${got.query.value}`, visits,
    leads: [], conversions: got.conversions || [], withheld: got.withheld || {}, how: "address", short: got.kept?.ip_mode === "short", firstKnown: true, person: got };
}

// ------------------------------------------------------------ the parts
function countryCell(code) {
  if (!code || code === "Unknown") return "Not recorded";
  return countryWords(code);   // "🇺🇸 USA", the full name on hover and for a screen reader (readers.js)
}

/* How the visitor's visits ended, the best of them: a booking, a lead, a form, else none. */
export function outcome(model) {
  const ends = model.visits.map((v) => v.endNode).filter(Boolean);
  const best = ["booked", "lead", "form"].map((k) => ends.find((e) => e.kind === k)).find(Boolean);
  if (best) return { words: best.kind === "booked" ? "Booked a demo" : best.kind === "lead" ? best.words.replace(/^lead/, "Lead") : "Sent a form", lead: true, detail: best.detail };
  // A person search: the leads and conversions it found are linked, even with no visit shown.
  const leads = (model.person?.leads || []).filter((l) => !l.left_out);
  if (leads.length) return { words: `Lead #${leads[0].id ?? leads[0].lead}${leads.length > 1 ? ` and ${n(leads.length - 1)} more` : ""}`, lead: true, detail: "From the lead database: see Leads below" };
  if (model.person && model.conversions.length) return { words: `${n(model.conversions.length)} conversion${model.conversions.length === 1 ? "" : "s"}`, lead: true, detail: "See Conversions below" };
  // Only this visit known (no address kept, or not an admin): say what is known, not more.
  return { words: model.firstKnown ? "No lead linked" : "No form sent", detail: model.firstKnown ? "No lead or conversion linked to these visits" : "None in this visit; other visits are not known here" };
}

const latestOf = (model) => model.visits.find((v) => v.country || v.device) || {};
const visitCount = (model) => model.visits.filter((v) => v.kind !== "touch").length;
function spanDays(model) {
  const times = model.visits.filter((v) => v.kind !== "touch" || v.start).map((v) => when(v.start)).filter(Boolean).sort((a, b) => a.t - b.t);
  return times.length ? { first: times[0], last: times[times.length - 1], days: dayDiff(times[0].day, times[times.length - 1].day) + 1 } : null;
}

function summary(model) {
  const span = spanDays(model);
  const latest = latestOf(model);
  const ft = model.firstTouch;
  const oldest = model.visits[model.visits.length - 1];
  const kind = ft && touchName(ft) !== shown(ft.source) ? `${shown(ft.source)}, ` : "";
  const touch = ft && LINKS.includes(ft.by) ? [touchName(ft), h("small", { title: `Linked ${BY[ft.by]}` }, `${kind}${ago(ft.day)}`)]
    : oldest ? [sourceWords(oldest), h("small", null, model.firstKnown ? `${shown(oldest.source)}: the oldest visit kept` : ft?.by === "none" ? "this visit: the first we know of" : "only this visit is known here")] : "-";
  const cell = (k, v, cls) => h("div", { class: cls || null }, h("dt", null, k), h("dd", null, v));
  const nv = visitCount(model);
  const end = outcome(model);
  // A search that shows no visits (an email, a lead): only what it found, not empty visit facts.
  if (!nv && model.person) {
    return h("dl", { class: "vz-sum" }, cell("Visits", ["None shown", h("small", null, "open an IP address under Linked")]),
      cell("Outcome", h("span", { title: end.detail || null }, end.words), end.lead ? "vz-out lead" : "vz-out"));
  }
  return h("dl", { class: "vz-sum" },
    cell("First seen", span ? at(span.first.t) : "-"),
    cell("Visits", [`${n(nv)}${model.visits.some((v) => v.kind === "touch") ? " shown" : ""}${span && span.days > 1 ? ` over ${n(span.days)} days` : ""}`,
      h("small", null, span && span.days > 1 ? `last ${at(span.last.t)}` : "on one day")]),
    cell("First came from", touch),
    // Only with a city file (logs.city_db) and when it named the address's city; else the country.
    latest.city ? cell("City", h("span", { class: "named", title: cityName(latest.city) }, flagEl(latest.country), h("span", { class: "nm" }, city(latest.city))))
      : cell("Country", countryCell(latest.country)),
    cell("Device", [latest.device ? shown(latest.device) : "Not recorded", latest.browser ? h("small", null, `${latest.browser}${latest.os ? ` on ${latest.os}` : ""}`) : null]),
    cell("Outcome", h("span", { title: end.detail || null }, end.words), end.lead ? "vz-out lead" : "vz-out"));
}

/* The drawer's title and the line under it: "Visitor from Toronto", "3 visits over 12 days, one booked demo". */
function titleOf(model) {
  if (model.person) return null;
  const latest = latestOf(model);
  if (latest.city) return ["Visitor from ", cityShort(latest.city)];
  if (latest.country && flagEl(latest.country)) return ["Visitor from ", countryWords(latest.country)];
  return ["Visitor"];
}
function subtitleOf(model) {
  const nv = visitCount(model), span = spanDays(model);
  const bits = [!nv && model.person ? "No visit shown" : `${n(nv)} visit${nv === 1 ? "" : "s"}${span && span.days > 1 ? ` over ${n(span.days)} days` : ""}`];
  const found = (model.person?.leads || []).filter((l) => !l.left_out).length;
  if (found) bits.push(`${n(found)} lead${found === 1 ? "" : "s"}`);
  const booked = model.visits.filter((v) => v.endNode?.kind === "booked").length;
  if (booked) bits.push(booked === 1 ? "one booked demo" : `${n(booked)} booked demos`);
  if (model.leads.length) bits.push(`${n(model.leads.length)} lead${model.leads.length === 1 ? "" : "s"}`);
  if (model.conversions.length && !booked) bits.push(`${n(model.conversions.length)} conversion${model.conversions.length === 1 ? "" : "s"}`);
  return bits.join(", ");
}

function trailText(v) { return v.trail.map((p) => `${p.path}${p.times > 1 ? ` ×${p.times}` : ""}`).join(" › ") || "-"; }

function timeline(model) {
  const held = model.withheld || {};
  const rows = model.visits.map((v) => {
    const line = v.this || v.first_touch ? touchLine({ ...v.raw, first_touch: v.first_touch }) : "";
    return h("tr", { class: v.first ? "vz-first" : null },
      h("td", null, v.kind === "touch" && !v.start?.includes("T") ? v.start : at(v.start),
        v.first ? h("span", { class: "vz-badge" }, "first") : null, v.this ? h("span", { class: "vz-badge" }, "this visit") : null,
        v.kind === "script" ? h("span", { class: "vz-badge script", title: "Pages the page script sent with the visitor ID" }, "seen by the script") : null,
        held[v.day] ? h("small", { class: "pp-bad", title: "This day's figures did not reconcile: it is withheld from every total." }, " withheld day") : null),
      h("td", null, h("span", { class: "named" }, v.via ? mark("referrer", v.via) : mark("source", v.source), h("span", { class: "nm" }, sourceWords(v))),
        v.via ? h("small", { class: "v-ft" }, shown(v.source)) : null, line ? h("small", { class: "v-ft" }, line) : null),
      h("td", null, h("span", { class: "mono" }, dash(v.landing))),
      h("td", null, v.kind === "touch" ? h("small", null, "only its first page is known here") : trailText(v)),
      h("td", null, v.seconds == null ? "-" : duration(v.seconds)),
      h("td", null, v.country ? countryCell(v.country) : "-", v.city ? h("small", { class: "v-ft", title: cityName(v.city) }, cityPlace(v.city)) : null),
      h("td", null, [v.device ? shown(v.device) : "-", v.browser ? h("small", { class: "v-ft" }, `${v.browser}${v.os ? ` on ${v.os}` : ""}`) : null]));
  });
  return h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Every visit, newest first"),
    h("thead", null, h("tr", null, ["When", "Came from", "Landing", "Pages in order", "Time on site", "Country", "Device"].map((x) => h("th", { scope: "col" }, x)))),
    h("tbody", null, rows)));
}

function leadsAndConversions(model) {
  const items = [
    ...model.leads.map((l) => h("li", null, h("b", null, `Lead #${l.lead}`), `${l.type ? ` (${l.type})` : ""}, made ${at(l.created_at)}`,
      l.left_out ? h("small", { class: "pp-bad" }, ` ${l.status} (left out)`) : "", h("small", { class: "v-ft" }, `matched by time to the form sent in the visit of ${at(l.visit_start)}: likely, never certain`))),
    ...model.conversions.map((c) => h("li", null, h("b", null, `${c.action} ${c.stage}`), `, ${at(c.at)}`, c.tool ? h("small", { class: "v-ft" }, `reported by ${c.tool}`) : null)),
  ];
  return sec("Leads and conversions", items.length ? h("ul", { class: "conv-tl-visits" }, items)
    : h("p", { class: "empty" }, model.journey && !model.firstKnown ? "None linked to this visit." : "No lead or conversion linked to these visits."));
}

function howNote(model, extra) {
  const bits = [];
  if (model.how === "address" && model.short) bits.push("Visits are linked by the same shortened address (its last part removed) with the same browser and system, inside the days the site keeps addresses. This is a weaker link: one shortened address can be several people on the same network, and one person on two devices is two visitors.");
  else if (model.how === "address") bits.push("Visits are linked by the same address with the same browser and system, inside the days the site keeps addresses. One address can be several people (an office), and one person on two devices is two visitors.");
  if (model.vid) bits.push("A visitor ID was matched to a visit by its page view of the landing page within seconds of the visit: matched by time.");
  if (model.how === "vid" && !model.firstKnown) bits.push("Linked by the visitor ID the page script made: one browser, not a person.");
  if (model.how === "hash") bits.push("Linked by the 30-day code: an address and browser family, hashed with a secret; no address is kept.");
  if (extra) bits.push(extra);
  return bits.length ? h("p", { class: "note" }, bits.join(" ")) : null;
}

function draw(d, model, extra) {
  finish(model);
  const vs = model.visits.map((v) => ({ ...v, touch: v.this ? touchLine({ ...v.raw, first_touch: v.first_touch }) : "" }));
  const map = journeyMap(vs);
  const j = model.journey;
  d.body.replaceChildren(...[
    summary(model),
    // No visit to draw (a person search by email or lead): no empty journey or table.
    vs.length ? h("section", { class: "dw-sec vz-journey" }, h("div", { class: "vz-jh" }, h("h3", null, "Journey, newest visit first"), h("small", null, "Time between pages on the line")), map.el) : null,
    vs.length ? h("details", { class: "dw-sec vz-more" }, h("summary", null, "Every visit as a table"), timeline(model)) : null,
    model.person ? null : leadsAndConversions(model),
    j ? sec("This visit", visitFacts(j)) : null,
    model.facts ? sec("This conversion", model.facts) : null,
    ...(model.person ? personParts(model.person) : []),
    howNote(model, extra),
  ].filter(Boolean));
  const title = titleOf(model);
  const t = d.el.querySelector(".dw-title");
  if (title && t) t.replaceChildren(...title);
  const sub = d.el.querySelector(".dw-sub");
  if (sub) sub.textContent = subtitleOf(model);
  // Replay sits in the header, beside the X.
  d.head.querySelector(".jm-replay")?.remove();
  const replay = vs.length ? replayButton(map) : null;   // nothing to play without a visit
  if (replay) d.head.insertBefore(replay, d.head.querySelector(".dw-x"));
}

// ------------------------------------------------------------ the one way in
/* Opens the visitor drawer. key: a journey, {q}, or {conversion}. */
export async function openVisitor(key) {
  if (!key) return null;
  if (key.q != null) return openByQuery(String(key.q).trim());
  if (key.conversion) {
    const x = key.conversion;
    const d = openDrawer({ title: "Visitor", subtitle: " ", key: "visitor", scope: "page", className: "vz-dw" });
    draw(d, { ...fromConversion(x), facts: key.facts || null }, x.browser || x.journey?.length ? "One browser, by the visitor ID the page script made: not a person (one person on two devices is two browsers). Days with visits, as the page script saw them." : "One lead without a browser: no visits are linked.");
    return d;
  }
  const j = key.journey || key;
  const d = openDrawer({ title: "Visitor", subtitle: " ", key: "visitor", scope: "page", className: "vz-dw" });
  draw(d, fromJourney(j), "Anonymous: no address, no browser string, no identifier on this page.");
  const url = j.day && j.seq != null ? `people/visitor?day=${encodeURIComponent(j.day)}&seq=${encodeURIComponent(j.seq)}` : "";
  const ask = url && (mayFind() || (DEMO.on && demoFile(url)));
  if (!ask) {
    if (url && !mayFind()) d.body.append(h("p", { class: "note" }, "Admins and owners see every visit of this visitor here, where the site keeps addresses."));
    return d;
  }
  const got = await call(url);
  if (!d.el.isConnected) return d;
  if (!got.ok) { d.body.append(h("p", { class: "note" }, got.error || "The visitor's other visits could not be read.")); return d; }
  if (!got.found) { d.body.append(h("p", { class: "note" }, got.why || "No other visit is kept for this visitor.")); return d; }
  draw(d, fromTimeline(j, got), "Every visit of this visitor kept with its address: shown to admins and owners, and written to the audit log (never the address).");
  return d;
}

async function openByQuery(q) {
  const d = openDrawer({ title: q || "Find a person", subtitle: "Looking…", key: "person", scope: "app", body: h("p", { class: "empty" }, "Looking in everything kept…") });
  const got = await call(`people?q=${encodeURIComponent(q)}`);
  if (!d.el.isConnected) return d;
  if (!got.ok) { d.body.replaceChildren(h("div", { class: "state bad", role: "alert" }, h("div", null, got.error || "The search could not run."))); return d; }
  d.el.querySelector(".dw-title").textContent = fromPerson(got).title;
  draw(d, fromPerson(got), "This search was written to the audit log (what kind of value, never the value). Deleting a person: skald forget on the server.");
  return d;
}
