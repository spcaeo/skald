// Overview > Summary in Live mode (2.7.0): the panels of the old Live page that
// have no other home, short, each with a link to the tab that lists them all.
// The figures come from the same files and fields the Live page read; nothing
// here counts anything new.
//
//   rightNow     the 5 newest visits and the 5 newest AI events, with Pause
//                (all of today's visits: Traffic > Visitors in Live mode;
//                every AI event with its address: AI & bots > Assistants)
//   leadsToday   the 5 newest forms and bookings (conversions.json `today`),
//                every one of them on Leads & sales > Pipeline
//   thisHour     "+N this hour", the Visitors tile's line
//
// Moved here from js/tabs/live.js (rightNow, visitRow, aiRow, leadsToday), which
// the old Live page still draws until its route points at Summary.

import { h, n, duration } from "../ui.js";
import * as S from "../state.js";
import { flag, flagEl, country } from "./readers.js";
import { link } from "../drill.js";
import { mark } from "../icons.js";
import { info } from "./tiles.js";
import { time as tzTime, label as tzLabel, when } from "../tz.js";
import { convFile, oneAction, STAGE, toolName, LEAD_WORDS } from "./leadfigs.js";

export const SHORT = 5;
const KIND = { asked: "answering a question", training: "collecting for training", referred: "sent a visitor" };

// Kept between the two-minute redraws: what was on screen, to mark what is new; and the pause.
const st = { seen: null, paused: false, frozen: null };

/* A link to another section's tab, keeping the period, page group and filters
   (so in Live mode it opens that tab in Live mode too). */
export function goTo(route, words, extra = {}) {
  const s = S.read();
  return h("a", { class: "ov-go", href: S.hashFor({ ...s, ...extra, tab: route, dd: "" }) }, words, h("span", { "aria-hidden": "true" }, " →"));
}

// "+N this hour" for the Visitors tile; null when today has no hours.
export function thisHour(m, t) {
  const hour = Number(String(m.live?.generated_at || "").slice(11, 13));
  if (!t.by?.hour || Number.isNaN(hour)) return null;
  return t.by.hour[String(hour).padStart(2, "0")] || 0;
}

function visitRow(j, fresh) {
  const trail = (j.trail || []).map((p) => p.path ?? p[0]);
  return h("li", { class: fresh ? "fresh" : null },
    h("span", { class: "s-t" }, tzTime(j.start, { label: false })),
    h("span", { class: "s-i" }, flagEl(j.country) || mark("device", j.device)),
    h("span", { class: "s-w" }, link("country", j.country, { text: country(j.country), bare: true }), ", ",
      [j.device, j.browser !== "Other" ? j.browser : ""].filter(Boolean).join(", "),
      j.via ? h("span", null, " from ", link(j.source === "AI assistant" ? "assistant" : "referrer", j.via, { bare: true })) : null,
      `: ${n(j.pages)} page${j.pages === 1 ? "" : "s"}, ${duration(j.seconds)}`,
      h("small", null, trail.join("  >  "))));
}

function aiRow(e, fresh) {
  return h("li", { class: fresh ? "fresh" : null },
    h("span", { class: "s-t" }, tzTime(e.at, { label: false })),
    h("span", { class: "s-i" }, mark("assistant", e.name || "?")),
    h("span", { class: "s-w" }, h("b", null, link(e.kind === "referred" ? "referrer" : "bot", e.name, { bare: true })), ` ${KIND[e.kind] || e.kind}`,
      flag(e.country) ? h("span", { class: "flag s-f", title: e.country_name || country(e.country) }, ` ${flag(e.country)}`) : null,
      h("small", null, e.path)));
}

// " · the last one 59 min ago": a quiet hour reads as quiet, not as a stalled feed.
function lastSeen(m, js) {
  const t = js.length ? when(js[0].start)?.t : null, now = Date.parse(m.live?.generated_at || "");
  if (!t || !now) return "";
  const min = Math.max(0, Math.round((now - t) / 60000));
  return min < 2 ? " · the last one just now" : min < 120 ? ` · the last one ${min} min ago` : ` · the last one at ${tzTime(js[0].start)}`;
}

/* The two streams, newest first, five each; a row not on screen at the last
   redraw is marked new (a soft flash, none with reduced motion). */
export function rightNow(m) {
  const js = (m.journeys || []).filter((j) => j.day === m.today).sort((a, b) => String(b.start).localeCompare(String(a.start)));
  const L = m.live;
  const events = m.x.ai_activity?.today?.events || (L?.events || []).map((e) => ({ at: e.at, name: e.who, kind: e.kind === "citation" ? "referred" : e.kind, path: e.path }));
  const keyJ = (j) => `j${j.start}|${j.country}|${j.landing || ""}|${j.pages}`;
  const keyE = (e) => `e${e.at}|${e.name}|${e.path}`;
  if (!st.paused) st.frozen = { js: js.slice(0, SHORT), events: events.slice(0, SHORT) };
  const shown = st.frozen || { js: [], events: [] };
  const seen = st.seen;
  st.seen = new Set([...shown.js.map(keyJ), ...shown.events.map(keyE)]);
  const isNew = (k) => !!seen && !seen.has(k);
  const pause = h("button", { type: "button", class: "btn", "aria-pressed": String(st.paused) }, st.paused ? "Resume" : "Pause");
  pause.addEventListener("click", () => { st.paused = !st.paused; pause.textContent = st.paused ? "Resume" : "Pause"; pause.setAttribute("aria-pressed", String(st.paused)); });
  const aiTotal = m.x.ai_activity?.today?.total ?? events.length;
  const panel = (title, unit, list, empty, more) => h("div", { class: "sheet card" }, h("div", { class: "card-h" }, h("h3", null, title)), h("p", { class: "card-m" }, unit),
    list.length ? h("ul", { class: "stream live-stream", "aria-live": "polite" }, list) : h("p", { class: "empty" }, empty), h("p", { class: "ov-more" }, more));
  return h("section", { class: "s ov-now" },
    h("div", { class: "card-h start" }, h("h2", null, "Right now"), info(`The ${SHORT} newest visits and AI events, newest first. New rows since the last update are marked; Pause holds the lists still.`, "Right now"), h("span", { class: "grow" }), pause),
    h("div", { class: "cols tops" },
      panel("Latest visits", `visitors who read a page, times in ${tzLabel()}${lastSeen(m, js)}`, shown.js.map((j) => visitRow(j, isNew(keyJ(j)))), "No visitor has read a page yet today.",
        goTo("traffic/visitors", "Every visit today: Traffic › Visitors")),
      panel("Latest AI activity", "assistants fetching pages, and visitors they sent", shown.events.map((e) => aiRow(e, isNew(keyE(e)))), "No AI assistant has come yet today.",
        goTo("ai/assistants", `All AI activity today, with addresses (${n(aiTotal)}): AI & bots › Assistants`))));
}

// "source / medium / name" with only the parts known: "newsletter / - / -" reads "campaign newsletter".
function campaignWords(c) {
  if (!c || c === "(no campaign tag)") return "";
  const known = String(c).split(" / ").filter((p) => p && p !== "-");
  return known.length ? `campaign ${known.join(" / ")}` : "";
}
const REPORTED = { beacon: "the script tag", site: "the lead database", lead: "your site's server" };

/* Today's leads and bookings, the 5 newest, from the same rows Pipeline (every
   road) counts: every stage of a form or a booking, with its source, landing
   page and country. A row marked test is listed, marked and never counted.
   Withheld with today's conversions; null without the file. */
export function leadsToday(m) {
  const f = convFile(m);
  if (!f) return null;
  const b = f.today;
  const fin = new Set(f.finished || ["completed", "paid"]);
  const all = goTo("sales/pipeline", "Every lead and booking: Leads & sales › Pipeline", { lsrc: "all" });
  const head = h("div", { class: "card-h start" }, h("h2", null, "Leads and bookings today"),
    info(`The ${SHORT} newest forms and bookings reported today, from the script tag, the tools' webhooks and the lead database, as Pipeline counts every road. ${LEAD_WORDS} A started form or an opened booking is listed with its stage and is not a lead.`, "Leads and bookings today"));
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
  const rows = (b.rows || []).slice(0, SHORT);
  const total = Math.max(b.total ?? 0, (b.rows || []).length);
  const tests = b.tests ? ` · ${n(b.tests)} marked test, not counted` : "";
  const shown = total > rows.length ? `the latest ${n(rows.length)} of ${n(total)} reported today` : `${n(total)} reported today`;
  return h("section", { class: "s" }, head,
    h("div", { class: "sheet card" }, h("p", { class: "card-m" }, `${rows.length ? `${shown} · ` : ""}times in ${tzLabel()}${tests}`),
      rows.length ? h("ul", { class: "stream live-stream lead-stream", "aria-live": "polite" }, rows.map(row)) : h("p", { class: "empty" }, "No form or booking yet today."),
      h("p", { class: "ov-more" }, all)));
}
