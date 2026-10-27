// Live: today so far, from the snapshot the live run rewrites every two
// minutes. Partial by nature: never stored as a day, never compared, never
// mailed. Laid out like Overview, people first:
//
//   header (one line: today so far, updated N s ago) - people tiles -
//   who else came - right now (latest visits and AI activity, side by side) -
//   today's leads and bookings as they arrive (conversions.json `today`) -
//   hour by hour - today's top lists

import { h, n, duration } from "../ui.js";
import { pagesWords } from "../visitpages.js";
import { color, rangeOf, ranked } from "../data.js";
import { bars } from "../charts.js";
import { head, nothing } from "./common.js";
import { flag, flagEl, country } from "./readers.js";
import { link, open as openDrill } from "../drill.js";
import { mark } from "../icons.js";
import { tiles, others, top, info } from "./tiles.js";
import { leadsOver } from "./overview.js";
import { aiFeed } from "./aifeed.js";
import { time as tzTime, hourLabels, label as tzLabel, when } from "../tz.js";
import { convFile, convDay, dayLeads, oneAction, STAGE, toolName, LEAD_WORDS } from "./leadfigs.js";
import { withUrl } from "../urlactions.js";

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
const KIND = { asked: "answering a question", training: "collecting for training", referred: "sent a visitor" };

// Kept between the two-minute redraws: what was on screen, to mark what is new; and the pause.
const st = { seen: null, paused: false, frozen: null };

// "updated 32 s ago", kept current while the tab is on screen.
function ago(ts) {
  const el = h("span", { class: "ago" });
  const tick = () => {
    if (!el.isConnected && el.dataset.on) return clearInterval(timer);
    el.dataset.on = "1";
    const s = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
    el.textContent = s < 60 ? `${s} s ago` : s < 3600 ? `${Math.floor(s / 60)} min ago` : `at ${tzTime(ts)}`;
  };
  const timer = setInterval(tick, 5000);
  tick();
  return el;
}

function visitRow(j, fresh) {
  const trail = (j.trail || []).map((p) => p.path ?? p[0]);
  return h("li", { class: fresh ? "fresh" : null },
    h("span", { class: "s-t" }, tzTime(j.start, { label: false })),
    h("span", { class: "s-i" }, flagEl(j.country) || mark("device", j.device)),
    h("span", { class: "s-w" }, link("country", j.country, { text: country(j.country), bare: true }), ", ",
      [j.device, j.browser !== "Other" ? j.browser : ""].filter(Boolean).join(", "),
      j.via ? h("span", null, " from ", link(j.source === "AI assistant" ? "assistant" : "referrer", j.via, { bare: true })) : null,
      `: ${pagesWords(j)}, ${duration(j.seconds)}`,
      h("small", null, trail.join("  >  "))));
}

function aiRow(e, fresh) {
  return h("li", { class: fresh ? "fresh" : null },
    h("span", { class: "s-t" }, tzTime(e.at, { label: false })),
    h("span", { class: "s-i" }, mark("assistant", e.name || "?")),
    h("span", { class: "s-w" }, h("b", null, link(e.kind === "referred" ? "referrer" : "bot", e.name, { bare: true })), ` ${KIND[e.kind] || e.kind}`,
      flag(e.country) ? h("span", { class: "flag s-f", title: e.country_name || country(e.country) }, ` ${flag(e.country)}`) : null,
      h("small", null, withUrl(h("span", null, e.path), e.path, { cls: "ua-after" }))));
}

// " · the last one 59 min ago": a quiet hour reads as quiet, not as a stalled feed.
function lastSeen(m, js) {
  const t = js.length ? when(js[0].start)?.t : null, now = Date.parse(m.live?.generated_at || "");
  if (!t || !now) return "";
  const min = Math.max(0, Math.round((now - t) / 60000));
  return min < 2 ? " · the last one just now" : min < 120 ? ` · the last one ${min} min ago` : ` · the last one at ${tzTime(js[0].start)}`;
}

// The two streams, newest first; a row not on screen at the last redraw is marked new (a soft flash, none with reduced motion).
function rightNow(m, js, events) {
  const keyJ = (j) => `j${j.start}|${j.country}|${j.landing || ""}|${j.pages}`;
  const keyE = (e) => `e${e.at}|${e.name}|${e.path}`;
  if (!st.paused) st.frozen = { js: js.slice(0, 10), events: events.slice(0, 10) };
  const shown = st.frozen || { js: [], events: [] };
  const seen = st.seen;
  st.seen = new Set([...shown.js.map(keyJ), ...shown.events.map(keyE)]);
  const isNew = (k) => !!seen && !seen.has(k);
  const pause = h("button", { type: "button", class: "btn", "aria-pressed": String(st.paused) }, st.paused ? "Resume" : "Pause");
  pause.addEventListener("click", () => { st.paused = !st.paused; pause.textContent = st.paused ? "Resume" : "Pause"; pause.setAttribute("aria-pressed", String(st.paused)); });
  const panel = (title, unit, list, empty) => h("div", { class: "sheet card" }, h("div", { class: "card-h" }, h("h3", null, title)), h("p", { class: "card-m" }, unit),
    list.length ? h("ul", { class: "stream live-stream", "aria-live": "polite" }, list) : h("p", { class: "empty" }, empty));
  return h("section", { class: "s" },
    h("div", { class: "card-h start" }, h("h2", null, "Right now"), info("The newest visits and AI activity, newest first. New rows since the last update are marked; Pause holds the lists still.", "Right now"), h("span", { class: "grow" }), pause),
    h("div", { class: "cols tops" },
      panel("Latest visits", `visitors who read a page, times in ${tzLabel()}${lastSeen(m, js)}`, shown.js.map((j) => visitRow(j, isNew(keyJ(j)))), "No visitor has read a page yet today."),
      panel("Latest AI activity", "assistants fetching pages, and visitors they sent", shown.events.map((e) => aiRow(e, isNew(keyE(e)))), "No AI assistant has come yet today.")));
}

/* Today's leads and bookings, newest first, from the same rows the
   Conversions tab counts: every stage of a form or a booking, with its
   source, landing page and country. A row marked test is listed, marked and
   never counted. Withheld with today's conversions; null without the file. */
// "source / medium / name" with only the parts known: "newsletter / - / -" reads "campaign newsletter".
function campaignWords(c) {
  if (!c || c === "(no campaign tag)") return "";
  const known = String(c).split(" / ").filter((p) => p && p !== "-");
  return known.length ? `campaign ${known.join(" / ")}` : "";
}
const REPORTED = { beacon: "the script tag", site: "the lead database", lead: "your site's server" };
function leadsToday(m) {
  const f = convFile(m);
  if (!f) return null;
  const b = f.today;
  const fin = new Set(f.finished || ["completed", "paid"]);
  const head = h("div", { class: "card-h start" }, h("h2", null, "Leads and bookings today"),
    info(`Every form and booking reported today, newest first, from the script tag, the tools' webhooks and the lead database, as on the Conversions page. ${LEAD_WORDS} A started form or an opened booking is listed with its stage and is not a lead.`, "Leads and bookings today"));
  if (!b || b.day !== m.today) return h("section", { class: "s" }, head, h("p", { class: "empty" }, "Today's list is written with the next update (every 2 minutes)."));
  if (b.state !== "ok") return h("section", { class: "s" }, head, h("div", { class: "state bad", role: "alert" }, h("div", null, `Withheld: ${b.why || "the second count disagrees."} None of today's leads are shown or counted until it matches.`)));
  const row = (x) => {
    const done = fin.has(x.stage);
    const facts = [x.source ? `from ${x.source}` : "source not recorded", x.landing ? `landed on ${x.landing}` : "", x.country ? country(x.country) : ""].filter(Boolean).join(", ");
    return h("li", { class: x.test ? "lead-test" : null },
      h("span", { class: "s-t" }, tzTime(x.at, { label: false })),
      h("span", { class: "s-i" }, flagEl(x.country) || mark("device", x.device)),
      h("span", { class: "s-w" }, h("b", null, oneAction(x.action)), h("span", { class: `lead-tag${done ? " done" : ""}` }, STAGE[x.stage] || x.stage),
        x.test ? h("span", { class: "lead-tag", title: "Marked test by the server admin: listed, never counted" }, "test, not counted") : null,
        ` ${facts}`, h("small", null, [`reported by ${REPORTED[x.tool] || toolName(x.tool)}`, x.first_source && x.first_source !== x.source ? `first came from ${x.first_source}` : "", campaignWords(x.campaign), x.device || ""].filter(Boolean).join(" · "))));
  };
  const rows = b.rows || [];
  const more = b.total > rows.length ? h("p", { class: "note" }, `The latest ${n(rows.length)} of ${n(b.total)} are listed; the Conversions page counts them all.`) : null;
  const tests = b.tests ? ` · ${n(b.tests)} marked test, not counted` : "";
  return h("section", { class: "s" }, head,
    h("div", { class: "sheet card" }, h("p", { class: "card-m" }, `times in ${tzLabel()}${tests}`),
      rows.length ? h("ul", { class: "stream live-stream lead-stream", "aria-live": "polite" }, rows.map(row)) : h("p", { class: "empty" }, "No form or booking yet today."), more));
}

export default function live(m, s) {
  const r = rangeOf(m, { ...s, range: "today" });
  const L = m.live;
  const fresh = L && L.day === m.today && L.state === "ok";
  const period = fresh ? h("span", null, "Today so far · updated ", ago(L.generated_at), " (every 2 min)") : "Today so far";
  const out = [...head("Live", r, "Today since midnight, counted again every 2 minutes and whenever you press Refresh. A day still running is not checked against a whole day, compared or mailed. The date range does not apply here.", { period })];
  if (!fresh) return [...out, nothing(m, r)];
  const t = L.figures;
  const nowHour = Number(String(L.generated_at || "").slice(11, 13));
  const thisHour = t.by?.hour ? t.by.hour[String(nowHour).padStart(2, "0")] || 0 : null;
  const conv = convFile(m);
  // Today's conversions: "ok" (read, even when every lead was spam or test: 0), withheld, or not recorded (-).
  const entry = conv ? convDay(conv, m.today) : null;
  const today = conv ? dayLeads(conv, entry) : null;
  const leads = conv ? today?.leads ?? null : leadsOver(m, [m.today]);
  const leadLine = !conv || today ? null : entry?.state === "withheld" ? "withheld: the second count disagrees" : "not recorded";
  out.push(tiles([
    { label: "Visitors", value: t.readers ?? null, info: `Visits that read at least one page today, counted only when the browser loaded the page's scripts and styles, so automated programs are left out; ${n(t.visits)} browser sessions in all, including ones that loaded no page.`,
      line: thisHour != null ? `+${n(thisHour)} this hour` : null },
    { label: "Pages read", value: t.views ?? null, info: "Page views by visitors today." },
    { label: "Visitors from AI", value: t.cited ?? null, info: "Visitors who followed a link in an AI assistant's answer; once per visitor, so it undercounts." },
    { label: "Leads today", value: leads, line: leadLine, info: conv ? `${LEAD_WORDS} From the Conversions data, checked by the second count; "-" while today's conversions are withheld.` : "Sign-ups, contact forms and early-access requests from the lead store, spam and duplicates removed." },
    conv ? { label: "Demos booked today", value: today?.demos ?? null, line: leadLine, info: "Demo bookings completed today, from the booking tool's webhook, the script tag and the lead database. Part of the leads." } : null,
    { label: "Returning", value: null, info: "Counted once the day is whole: returning visitors appear on Overview from tomorrow." },
  ]));
  out.push(others(t, { probes: true }));
  const js = (m.journeys || []).filter((j) => j.day === m.today).sort((a, b) => String(b.start).localeCompare(String(a.start)));
  const events = m.x.ai_activity?.today?.events || (L.events || []).map((e) => ({ at: e.at, name: e.who, kind: e.kind === "citation" ? "referred" : e.kind, path: e.path }));
  out.push(rightNow(m, js, events));
  out.push(leadsToday(m));

  const labels = hourLabels(m.today);
  out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, `Hour by hour (${tzLabel()})`),
    info("Visitors by the hour of their first page. The current hour is still filling. Select an hour for its detail.", "Hour by hour")),
  h("div", { class: "sheet" }, bars(HOURS.map((hh, i) => ({ label: labels[i], title: `${labels[i]} to ${labels[(i + 1) % 24]} ${tzLabel()}${i === nowHour ? " (filling)" : ""}`,
    value: i > nowHour ? 0 : t.by?.hour?.[hh] || 0, color: i === nowHour ? "color-mix(in srgb, var(--g-people) 50%, var(--surface))" : color("people") })),
  { label: "Visitors by hour today", unit: "visitors", every: 3, H: 170, onPick: (i) => openDrill("hour", HOURS[i]) }))));

  const ai = {};
  for (const tier of ["asked", "training"]) for (const [k, v] of Object.entries(t.engines?.[tier] || {})) ai[k] = (ai[k] || 0) + v;
  out.push(h("div", { class: "cols tops" },
    top("Top pages today", "pages read", "pages", ranked(t.pages), { drill: "path", empty: "No page read yet today." }),
    top("Top sources today", "visitors, by where they came from", "sources", ranked(t.by?.source), { drill: "source", total: t.readers, empty: "No visitor yet today." }),
    top("Countries today", "visitors", "locations", ranked(t.by?.country), { drill: "country", total: t.readers, empty: "No visitor yet today." }),
    top("AI assistants today", "requests, answering a question or collecting for training", "bots", ranked(ai), { drill: "bot", color: color("answer_engines"), empty: "No AI assistant yet today." })));
  if (m.x.ai_activity?.today) out.push(h("details", { class: "fold" }, h("summary", null, "All AI activity today, with addresses", h("span", null, `${n(m.x.ai_activity.today.total ?? events.length)} today`)),
    aiFeed(m, { limit: 20, globalCountry: s.country })));
  return out;
}
