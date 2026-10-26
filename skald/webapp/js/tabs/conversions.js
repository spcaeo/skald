// Conversions: every action that counts (a demo booked, a form sent, a
// sign-up, a payment), from the page's script tag, the tools' webhooks and
// the site's lead database, side by side: started, completed, abandoned and
// the rate between; the demo funnel; where the completed ones came from;
// the pages seen before converting; first, last and assisted touch; the time
// it took; and the latest conversions as anonymous timelines.
// A visitor ID is a browser, never a person: journeys say "browsers".
// A day the second count disagreed with arrives withheld and is left out of
// every sum, said once; a rate or a share over fewer than min_rate is not
// given (the counts are).

import { h, n, short, pct1, reduced, ICON } from "../ui.js";
import { shown } from "../labels.js";
import { rangeOf } from "../data.js";
import { stamp } from "../tz.js";
import { head, rangeWords, fixed } from "./common.js";
import { table } from "../table.js";
import { howTo } from "./help.js";
import { conversionsLikely } from "./likelyai.js";
import { withFlag } from "./readers.js";
import { label as valueLabel } from "../drill.js";
import { openConversionList } from "./person.js";
import { STAGE, actionName, toolName } from "./leadfigs.js";

const DIM = { source_type: "Source (last touch)", first_source: "First touch", campaign: "Campaign", landing: "Landing page", country: "Country", device: "Device", tool: "Reported by" };
const WAIT = { "<1h": "Under an hour", "<1d": "1 to 24 hours", "1-7d": "1 to 7 days", "8-30d": "8 to 30 days", "31-90d": "31 to 90 days", ">90d": "Over 90 days" };
const VISITS = { 0: "0", 1: "1", 2: "2", "3-5": "3 to 5", "6-10": "6 to 10", "11+": "11 or more" };
const info = (...kids) => h("div", { class: "state", html: ICON.info }, h("div", null, ...kids));
const bad = (...kids) => h("div", { class: "state bad", role: "alert", html: ICON.info }, h("div", null, ...kids));

// What to turn on, for an empty tab: each source of conversions and whether it is on.
function setup(f) {
  const on = f?.set_up || {};
  const item = (ok, title, how) => h("li", null, h("strong", null, `${ok ? "On" : "Off"}: ${title}. `), ok ? "" : how);
  return h("div", { class: "sheet" }, h("h3", null, "Where conversions come from"),
    h("ul", { class: "conv-setup" },
      item(on.beacon, "the script tag", "Add the one-line script tag to every page (Settings > Collect data > Script tag & goals has it to copy). It sees forms started and sent, phone and email clicks, and booking widgets opened and booked."),
      item(on.visitor_ids, "visitor IDs", "Turn on beacon.visitor_ids so each browser gets a random ID: then abandoned forms and bookings, journeys, assisted sources and the pages seen before converting can be counted. The privacy notice must say so."),
      item((on.hooks || []).length, `webhooks${(on.hooks || []).length ? ` (${on.hooks.map(toolName).join(", ")})` : ""}`, "Give Calendly, Cal.com, Stripe, HubSpot, Typeform or Zapier the hook address and secret from Settings > Leads & integrations, so bookings, payments and cancellations made off the site come back."),
      item(on.leads_db, "the lead database", "Set leads.db to the website's lead database: every lead becomes a conversion, with its status (won, lost) and its first and last touch, with no change to the website.")));
}

// The days of the range the file has, the withheld ones apart.
function daysOf(m, r, f) {
  const wanted = r.kind === "today" ? [m.today] : rangeDays(r);
  const at = new Map((f.days || []).map((d) => [d.day, d]));
  const got = wanted.map((d) => at.get(d)).filter(Boolean);
  return { wanted, ok: got.filter((d) => d.state === "ok"), held: got.filter((d) => d.state === "withheld"), before: got.filter((d) => d.state === "before").length };
}
function rangeDays(r) {
  const out = [];
  for (let d = new Date(`${r.first}T00:00:00Z`); out.length < 400; d.setUTCDate(d.getUTCDate() + 1)) {
    const iso = d.toISOString().slice(0, 10);
    out.push(iso);
    if (iso >= r.last) break;
  }
  return out;
}

const add = (o, k, v) => { o[k] = (o[k] || 0) + v; };
function sum(days, f) {
  const fin = new Set(f.finished || ["completed", "paid"]);
  const t = { stages: {}, done: {}, abandoned: {}, by: {}, visits: {}, wait: {}, assisted: {}, hasAssisted: false };
  for (const d of days) {
    for (const [a, per] of Object.entries(d.stages || {})) {
      t.stages[a] = t.stages[a] || {};
      for (const [st, v] of Object.entries(per)) { add(t.stages[a], st, v); if (fin.has(st)) add(t.done, a, v); }
    }
    for (const [a, v] of Object.entries(d.abandoned || {})) add(t.abandoned, a, v);
    for (const [dim, table_] of Object.entries(d.by || {})) {
      t.by[dim] = t.by[dim] || {};
      for (const [a, per] of Object.entries(table_)) for (const [k, v] of Object.entries(per)) { t.by[dim][a] = t.by[dim][a] || {}; add(t.by[dim][a], k, v); }
    }
    for (const [name, into] of [["visits_before", t.visits], ["time_to_convert", t.wait]]) {
      for (const per of Object.values(d[name] || {})) for (const [k, v] of Object.entries(per)) add(into, k, v);
    }
    if (d.assisted) { t.hasAssisted = true; for (const per of Object.values(d.assisted)) for (const [k, v] of Object.entries(per)) add(t.assisted, k, v); }
  }
  return t;
}

const rateOf = (a, b, min) => (b >= min ? pct1(a, b) : null);

// Every action side by side.
function actions(t, f, min) {
  const names = Object.keys(t.stages).sort((a, b) => (t.done[b] || 0) - (t.done[a] || 0) || a.localeCompare(b));
  if (!names.length) return h("p", { class: "empty" }, "No conversion in this range.");
  const rows = names.map((a) => {
    const st = t.stages[a];
    const started = st.started || 0, done = t.done[a] || 0;
    return { k: a, started, done, abandoned: t.abandoned[a] || 0, cancelled: (st.cancelled || 0) + (st.no_show || 0), won: st.won || 0, lost: st.lost || 0 };
  });
  const cols = [{ key: "k", label: "Action", fmt: actionName },
    { key: "started", label: "Started", num: true, fmt: (v) => (v ? n(v) : h("span", { class: "few" }, "not seen")) },
    { key: "done", label: "Completed", num: true },
    { key: "abandoned", label: "Abandoned", num: true },
    { key: "rate", label: "Completion rate", num: true, sort: (e) => (e.started >= min ? e.done / e.started : null),
      fmt: (_, e) => (!e.started ? h("span", { class: "few" }, "no starts seen") : rateOf(Math.min(e.done, e.started), e.started, min) ?? h("span", { class: "few" }, `too few to say (${n(e.started)})`)),
      csv: (e) => (e.started >= min ? (Math.min(e.done, e.started) / e.started).toFixed(4) : "") },
    { key: "cancelled", label: "Cancelled or no-show", num: true }, { key: "won", label: "Won", num: true }, { key: "lost", label: "Lost", num: true }];
  return [h("div", { class: "sheet" }, table(cols, { caption: "Every action side by side", rows, file: "conversions-by-action.csv", search: false, limit: 12, sortKey: "done" })),
    h("p", { class: "note" }, `Completed counts completed and paid. Abandoned: started with a visitor ID and not completed by the same browser within ${f.abandon_hours || 24} hours (a start still inside that window is not counted yet; a start without a visitor ID cannot be judged). A rate is given over at least ${min} starts. Starts are seen only by the script tag; an action only a tool reports has none. A browser's repeat of the same start within ${f.repeat_minutes || 30} minutes is kept once, so Started can be lower than Events' count of the same event, which counts every one.`)];
}

// The demo funnel: opened, time chosen (the page's own event, from events.json), booked, then what happened to the booking.
function demoFunnel(m, t, days) {
  const st = t.stages.demo;
  if (!st) return null;
  const ev = m.x.events;
  let chosen = null;
  if (ev && (ev.events || []).some((e) => e.name === "calendly_time_selected")) {
    const want = new Set(days.map((d) => d.day));
    chosen = (ev.days || []).filter((d) => want.has(d.day) && d.state === "ok").reduce((a, d) => a + (d.events?.calendly_time_selected || 0), 0);
  }
  const steps = [["Opened the booking", st.started], ["Chose a time", chosen], ["Booked", (st.completed || 0) + (st.paid || 0)],
    ["Cancelled", st.cancelled], ["Rescheduled", st.rescheduled], ["No-show", st.no_show], ["Won", st.won]];
  const top = Math.max(1, ...steps.map(([, v]) => v || 0));
  return h("div", { class: "sheet" },
    h("ul", { class: `blist${reduced() ? "" : " play"}` }, steps.map(([k, v], i) => h("li", null,
      h("span", { class: "bl-bar", style: { width: `${((v || 0) / top) * 100}%`, background: i < 3 ? "var(--g-people)" : "var(--ink-3)", animationDelay: `${i * 0.03}s` } }),
      h("span", { class: "bl-l" }, k), h("span", { class: "bl-v" }, v == null ? "not tracked" : n(v)), h("span", { class: "bl-p" }, "")))),
    h("p", { class: "note" }, "Opened and booked come from the page's script tag, the booking tool's webhooks and the lead database together. “Chose a time” is the page's own event count (events, not browsers). Cancelled, rescheduled and no-show need the booking tool's webhook."));
}

// One breakdown of the completed conversions: a row per label, a column per action.
// A breakdown whose every completed row is "Unknown" (or that has none) says nothing:
// it joins one line naming every such breakdown instead of a card of its own.
function unrecorded(dim, t, acts) {
  const per = t.by[dim] || {};
  return acts.every((a) => Object.entries(per[a] || {}).every(([k, v]) => !v || k === "Unknown"));
}
function unrecordedNote(dims) {
  if (!dims.length) return null;
  const names = dims.map((d) => DIM[d].toLowerCase());
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return h("p", { class: "bk-none" }, h("b", null, "Not recorded for these: "), `${list}. The tool that reported them (a booking or payment webhook) does not carry ${names.length === 1 ? "it" : "them"}; the page's script tag on the booking page adds the visit's source, landing page, country and device.`);
}

function breakdown(dim, t, acts) {
  const per = t.by[dim] || {};
  const labels = new Map();
  for (const a of acts) for (const [k, v] of Object.entries(per[a] || {})) labels.set(k, (labels.get(k) || 0) + v);
  const rows = [...labels.entries()].map(([k, all]) => ({ k, all, ...Object.fromEntries(acts.map((a) => [a, per[a]?.[k] || 0])) }));
  const cols = [{ key: "k", label: DIM[dim], fmt: dim === "tool" ? toolName : dim === "country" ? (v) => valueLabel("country", v, v) : undefined, country: dim === "country" ? (r) => r.k : undefined, path: dim === "landing" }, { key: "all", label: "All", num: true },
    ...acts.slice(0, 4).map((a) => ({ key: a, label: actionName(a), num: true }))];
  return h("div", { class: "sheet" }, h("h3", null, DIM[dim]),
    table(cols, { caption: `Completed conversions by ${DIM[dim].toLowerCase()}`, rows, file: `conversions-by-${dim}.csv`, search: false, limit: 8, sortKey: "all", empty: "None in this range." }));
}

// First touch, last touch and assisted, side by side.
function touches(t, acts) {
  const first = {}, last = {};
  for (const a of acts) {
    for (const [k, v] of Object.entries(t.by.first_source?.[a] || {})) add(first, k, v);
    for (const [k, v] of Object.entries(t.by.source_type?.[a] || {})) add(last, k, v);
  }
  const keys = [...new Set([...Object.keys(first), ...Object.keys(last), ...Object.keys(t.assisted)])];
  const rows = keys.map((k) => ({ k, first: first[k] || 0, last: last[k] || 0, assisted: t.hasAssisted ? t.assisted[k] || 0 : null }));
  return h("div", { class: "sheet" }, table([{ key: "k", label: "Source" }, { key: "first", label: "First touch", num: true }, { key: "last", label: "Last touch", num: true },
    { key: "assisted", label: "Assisted", num: true, fmt: (v) => (v == null ? "-" : n(v)) }],
  { caption: "Completed conversions by first, last and assisting source", rows, file: "conversions-touches.csv", search: false, limit: 10, sortKey: "last" }),
  h("p", { class: "note" }, `First touch: where the browser (or the lead) first came from; last touch: the visit it converted in. Assisted: a source seen earlier in a converting browser's journey that was not its last touch, each conversion counted once per source${t.hasAssisted ? "" : "; it needs visitor IDs (beacon.visitor_ids)"}. "Not recorded" is never guessed.`));
}

// A bar list in a fixed order. Shares only over at least `min` (a share of 1 is always 100%).
function ordered(items, color, min) {
  const max = Math.max(1, ...items.map(([, v]) => v)), all = items.reduce((a, [, v]) => a + v, 0);
  return h("ul", { class: `blist${reduced() ? "" : " play"}` }, items.map(([k, v], i) => h("li", null,
    h("span", { class: "bl-bar", style: { width: `${(v / max) * 100}%`, background: color, animationDelay: `${i * 0.03}s` } }),
    h("span", { class: "bl-l", title: k }, k), h("span", { class: "bl-v" }, n(v)), h("span", { class: "bl-p" }, all >= min ? pct1(v, all) : ""))));
}

const fewWords = (all, min) => (all && all < min ? `Counts only: shares are given over at least ${min}. ` : "");

function timing(t, min) {
  const wait = Object.keys(WAIT).map((k) => [WAIT[k], t.wait[k] || 0]);
  const visits = Object.keys(VISITS).map((k) => [VISITS[k], t.visits[k] || 0]);
  const wk = wait.reduce((a, [, v]) => a + v, 0), vk = visits.reduce((a, [, v]) => a + v, 0);
  return h("div", { class: "cols tops" },
    h("div", { class: "sheet" }, h("h3", null, "From first touch to converting"),
      wk ? ordered(wait, "var(--g-people)", min) : h("p", { class: "empty" }, "No completed conversion in this range has a first-touch time."),
      h("p", { class: "note" }, [fewWords(wk, min), t.wait.unknown ? `${n(t.wait.unknown)} without a first-touch time, left out. ` : "", t.wait.clock_error ? `${n(t.wait.clock_error)} with a clock error, left out. ` : "", "The first touch is what the browser or the tool remembered."].join(""))),
    h("div", { class: "sheet" }, h("h3", null, "Visits before converting"),
      vk ? ordered(visits, "var(--g-search_engines)", min) : h("p", { class: "empty" }, "No completed conversion in this range has a visit count."),
      h("p", { class: "note" }, fewWords(vk, min) + (t.visits.unknown ? `${n(t.visits.unknown)} without a count, left out.` : "As the site or the tool counted them."))));
}

// The pages seen before converting, against browsers that did not convert (the file's last 30 days).
function pages(f, min) {
  const p = f.pages_before;
  const period = f.period ? `${short(f.period.first)} to ${short(f.period.last)}` : "the last 30 days";
  if (p == null) return fixed("Pages seen before converting", period, info("This needs visitor IDs: turn on beacon.visitor_ids (and the script tag) so each browser's pages can be followed up to the moment it converts."));
  if (p.state === "withheld") return fixed("Pages seen before converting", period, bad(`Withheld: the second count disagrees. ${p.why || ""}`));
  const share = (v, all) => (all >= min ? pct1(v, all) : null);
  const rows = (p.pages || []).map(([path, c, o]) => ({ k: path, c, o, cs: share(c, p.converting), os: share(o, p.other) }));
  return fixed("Pages seen before converting", period,
    h("p", { class: "sub" }, `Of ${n(p.converting)} converting browsers and ${n(p.other)} browsers that did not convert, the share that saw each page (before converting, for the first). Does the pricing page help? Shares are given over at least ${min} browsers.`),
    h("div", { class: "sheet" }, table([{ key: "k", label: "Page", path: true },
      { key: "c", label: "Converting browsers", num: true, fmt: (v, e) => `${n(v)}${e.cs ? ` (${e.cs})` : ""}` },
      { key: "o", label: "Other browsers", num: true, fmt: (v, e) => `${n(v)}${e.os ? ` (${e.os})` : ""}` }],
    { caption: "Pages seen before converting", rows, file: "conversions-pages-before.csv", search: true, limit: 12, sortKey: "c", empty: "No converting browser had a journey in this period." })));
}

// A moment in the one date family (tz.js): "7 Oct 16:05 EDT", in the chosen zone.
const at = (iso) => (iso ? stamp(iso) : "");
function timeline(f) {
  const list = f.timeline || [];
  const period = f.period ? `${short(f.period.first)} to ${short(f.period.last)}` : "the last 30 days";
  if (!list.length) return fixed("Latest conversions", period, h("p", { class: "empty" }, "No completed conversion in this period."));
  const one = (x) => {
    const first = x.visits?.[0]?.day;
    const visits = (x.visits || []).map((v) => {
      const k = first ? Math.round((Date.parse(`${v.day}T00:00:00Z`) - Date.parse(`${first}T00:00:00Z`)) / 864e5) + 1 : 1;
      return h("li", null, h("strong", null, `Day ${k} (${short(v.day)}), ${shown(v.source) || "source not recorded"}: `), (v.paths || []).join(", "));
    });
    const steps = (x.steps || []).map((s) => `${actionName(s.action).replace(/s$/, "")} ${STAGE[s.stage] || s.stage} ${at(s.at)}`);
    const facts = [x.first_source ? `first came from ${x.first_source}` : "", x.source ? `converted from ${x.source}` : "", x.landing ? `landed on ${x.landing}` : "",
      x.country ? withFlag(x.country) : "", x.device ? x.device : "", x.visits_before != null ? `${n(x.visits_before)} visits before` : ""].filter(Boolean).join(" · ");
    return h("li", { class: "conv-tl-item" },
      h("p", null, h("strong", null, `${actionName(x.action)}, ${at(x.at)}`), ` via ${toolName(x.tool)}${x.browser ? ", one browser" : ""}`),
      facts ? h("p", { class: "note" }, facts) : null,
      visits.length ? h("ul", { class: "conv-tl-visits" }, visits) : x.browser ? null : h("p", { class: "note" }, "No journey: this conversion carries no visitor ID."),
      h("p", { class: "conv-tl-steps" }, steps.join(" → ")));
  };
  return fixed("Latest conversions", period,
    h("p", { class: "sub" }, "Each line is one browser (or one lead without a browser): its visits by day, the pages it read and its conversion steps. No name, email or visitor ID is shown here: an admin finds the person with the search at the top. A browser is not a person: one person on two devices is two browsers."),
    h("ol", { class: "conv-tl" }, list.map(one)));
}

export default function conversions(m, s) {
  const r = rangeOf(m, s);
  const out = [...head("Conversions", r, "Every action that counts, from the page's script tag, the tools' webhooks and the lead database: started, completed, abandoned, and where the completed ones came from.", { banner: false })];
  const f = m.x.conversions;
  const guide = [howTo("webhooks", "How do I connect Calendly, Stripe, a form tool or my own site?"), howTo("leads-and-conversions", "What do started, completed and abandoned mean?")];
  if (!f) return [...out, info("The conversions file is not written beside this page yet. It appears with the next redraw once a source of conversions is on."), setup(null), guide];
  if (f.state === "error") return [...out, bad(`The conversions file could not be built: ${f.error || "no reason given"}.`)];
  if (!f.available) return [...out, info(h("strong", null, "No conversions yet. "), f.reason ? `${f.reason}. ` : "", "Turn on at least one of the sources below."), setup(f), guide];
  const min = f.min_rate || 10;
  const { ok, held, wanted } = daysOf(m, r, f);
  if (held.length) out.push(bad(`${held.length} day${held.length === 1 ? "" : "s"} withheld (${held.slice(0, 5).map((d) => short(d.day)).join(", ")}${held.length > 5 ? "..." : ""}): left out of every figure below, never counted as zero. Why: ${held[0].why || "the second count disagrees."}`));
  if (!ok.length) {
    out.push(info(`No conversion figures for ${r.kind === "today" ? "today" : `this range (${rangeWords(r)})`}${f.since ? `: conversions are recorded from ${short(f.since)} on` : ""}. A day before that is not recorded, never zero.`));
  } else {
    const t = sum(ok, f);
    const acts = Object.keys(t.done).sort((a, b) => t.done[b] - t.done[a]);
    const cover = `${ok.length} of ${wanted.length} day${wanted.length === 1 ? "" : "s"} recorded`;
    out.push(h("section", { class: "s" }, h("h2", null, "Every action", " ", h("small", { class: "note" }, cover)), ...[actions(t, f, min)].flat()));
    const demo = demoFunnel(m, t, ok);
    if (demo) out.push(h("section", { class: "s" }, h("h2", null, "Demo funnel"), demo));
    if (acts.length) {
      const dims = (f.dims || Object.keys(DIM)).filter((d) => DIM[d]);
      const blank = dims.filter((d) => d !== "tool" && unrecorded(d, t, acts));
      out.push(h("section", { class: "s" }, h("h2", null, "Where the completed ones came from"),
        h("div", { class: "cols tops" }, ...dims.filter((d) => !blank.includes(d)).map((d) => breakdown(d, t, acts))), unrecordedNote(blank)));
      out.push(h("section", { class: "s" }, h("h2", null, "First, last and assisted touch"), touches(t, acts)));
      out.push(conversionsLikely(ok, acts, f));
      out.push(h("section", { class: "s" }, h("h2", null, "Time to convert"), timing(t, min)));
    }
  }
  out.push(pages(f, min), timeline(f));
  // Nothing hidden (2.4.0): the rows the figures do not show as completed, listed in full.
  out.push(h("section", { class: "s" }, h("h2", null, "Cancelled, removed and test"),
    h("p", { class: "sub" }, "Every conversion stays visible: cancelled bookings and no-shows, rows a lead-database sync took away (with when and why), and conversions marked test (kept, never counted). Each with its row and journey where known."),
    h("div", { class: "acts" }, [["cancelled", "Cancelled and no-show"], ["removed", "Removed"], ["test", "Marked test"]].map(([k, t]) =>
      h("button", { type: "button", class: "btn", onclick: () => openConversionList(k) }, t)))));
  out.push(h("p", { class: "note" }, f.as_known || "Conversions are as known now: a later cancellation or status changes past days."));
  if (!f.set_up?.visitor_ids || !f.set_up?.beacon) out.push(setup(f), ...guide);
  return out;
}
