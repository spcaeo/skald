// Overview's "Right now" card (#43): what is current, on top of Overview whatever the period.
// Real time and Summary were two tabs showing the same thing; they are one page now.
//
//   head    "Right now", how old the count is ("Updated 40 s ago", from the live count's
//           `until`), Pause, and Refresh now: counts this site at once (POST <page>/refresh,
//           one site only, refresh_server.py) and draws the answer
//   left    visitors on the site now (last 5 minutes), visitors minute by minute (30 bars),
//           visitors in the last 30 minutes. The number opens the list of everyone
//   right   the people here now: the live run's `doing` rows (realtime.py), the newest
//           activity first. Each: where and device, a pill (New or Returning: visitors.py's
//           label; Lead or Customer: #31's mark on the visit, when the page holds it), the
//           page they are on now (copy and open), time on the site, pages, where they came
//           from. A row opens the visitor drawer (their journey). The first SHOWN are open,
//           the rest in a fold kept in the address (rn_view=open)
//
// Nothing here is counted anew: every number is Real time's (audit_realtime.py) and every
// label is one the visit list already shows. It follows Real time's answer (realtime.js
// follow()), every 15 seconds while on screen.

import { h, n, reduced, counter } from "../ui.js";
import { when, time as tzTime } from "../tz.js";
import { follow, openNewest, pollNow } from "./realtime.js";
import { arrived } from "../by-now.js";
import { flagEl, country, countryName, cityName } from "./readers.js";
import { mark } from "../icons.js";
import { withUrl } from "../urlactions.js";
import { shown, assistantName } from "../labels.js";
import { pill } from "../ui/pill.js";
import { urlFold } from "../ui/fold.js";
import { touchName, ago as dayAgo } from "./visitor.js";
import { middle } from "./ov-doing.js";
import { refreshSite } from "../refresh-hook.js";

export const SHOWN = 6;
const people = (B) => (B && (B.people_state === "ok" || B.people_state === "stale") ? B.people : null);
const ms = (ts) => when(ts)?.t ?? NaN;

/* "just now", "40 s ago", "6 min ago", "2 h ago". */
export function agoWords(ts, now = Date.now()) {
  const t = ms(ts);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  return s < 5 ? "just now" : s < 60 ? `${s} s ago` : s < 3600 ? `${Math.floor(s / 60)} min ago` : `${Math.floor(s / 3600)} h ago`;
}

/* Time on the site: first request to the newest. "under a minute", "6 min", "1 h 12 min". */
export function stayWords(v) {
  const a = ms(v.start), b = ms(v.last);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return "";
  const m = Math.max(0, Math.round((b - a) / 60000));
  return m < 1 ? "under a minute" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

/* The page they are on now: the last of their pages. */
export const nowOn = (v) => (v.trail?.length ? v.trail[v.trail.length - 1] : v.landing || "");

/* #31's mark on this visit, from the page's journeys (app.json `won`): "lead", "customer" or "". */
export function wonOf(v, journeys) {
  const day = String(v.start || "").slice(0, 10);
  const j = v.seq == null ? null : (journeys || []).find((x) => x.seq === v.seq && x.day === day);
  return j?.won === "lead" || j?.won === "customer" ? j.won : "";
}

/* Who they are, in labels the visit list already uses: [kind, words, title] pills, and one
   line of detail ("seen on 3 of the last 30 days", "first came from Google, 9 days ago"). */
export function whoOf(v, journeys) {
  const pills = [];
  if (v.returning === true) pills.push(["ret", "Returning", "Seen on an earlier day in the last 30 days (the same rule as Returning people)."]);
  else if (v.returning === false) pills.push(["new", "New", "Not seen on an earlier day in the last 30 days."]);
  const won = wonOf(v, journeys);
  if (won === "lead") pills.push(["info", "Lead", "This visit sent a lead (proven: the only visit that sent a form at the lead's time)."]);
  if (won === "customer") pills.push(["good", "Customer", "This visit sent a form for someone who has paid (proven)."]);
  const ft = v.first_touch;
  const bits = [];
  if (v.returning === true && v.days_seen > 1) bits.push(`seen on ${n(v.days_seen)} of the last 30 days`);
  if (ft?.day && ft.day < String(v.start || "").slice(0, 10)) bits.push(`first came from ${touchName(ft)}, ${dayAgo(ft.day)}`);
  return { pills, line: bits.join(" · ") };
}

const whoPill = ([kind, words, title]) => (kind === "new" || kind === "ret"
  ? h("span", { class: `v-vis ${kind}`, title }, words) : pill(kind, words, { title }));

const sourceName = (v) => (v.via ? (v.source === "AI assistant" ? assistantName(v.via) : v.via) : shown(v.source) || "Source not recorded");

/* The rows to list: active in the last 5 minutes first, then the rest of the 30, each group
   newest activity first (the order `doing` already has inside a group). */
export function ordered(doing) {
  const rows = doing || [];
  return [...rows.filter((v) => v.active === "5"), ...rows.filter((v) => v.active !== "5")];
}

function row(m, v) {
  const who = whoOf(v, m.journeys);
  const place = v.city ? String(v.city).split(", ")[0] : country(v.country);
  const page = nowOn(v);
  const openIt = () => openNewest(m, v);
  const here = v.active === "5";
  return h("li", { class: `rn-row${here ? "" : " quiet"}` },
    h("span", { class: "rn-who" },
      h("button", { type: "button", class: "rn-name", onclick: openIt, "aria-label": `Open this visitor: ${v.city ? cityName(v.city) : countryName(v.country)}, now on ${page || "a page"}` },
        flagEl(v.country), h("b", null, place || "Place not recorded"), v.device ? h("span", { class: "rn-dev", title: v.device }, mark("device", v.device) || v.device) : null),
      ...who.pills.map(whoPill),
      who.line ? h("span", { class: "rn-sub" }, who.line) : null),
    h("span", { class: "rn-now" }, here ? h("i", { class: "td-pdot", "aria-hidden": "true" }) : null,
      here ? "Now on " : "Last on ", page ? withUrl(h("span", { class: "rn-path", title: page }, middle(page)), page, { cls: "ua-after" }) : "a page not recorded"),
    h("span", { class: "rn-meta" }, [stayWords(v), `${n(v.trail?.length || v.pages || 0)} page${(v.trail?.length || v.pages) === 1 ? "" : "s"}`, sourceName(v)].filter(Boolean).join(" · ")),
    h("button", { type: "button", class: "rn-go", onclick: openIt, "aria-label": "Open their journey", title: "Their journey" }, "›"));
}

/* The card. o.first: the page's first draw (the number counts up). */
export function rightNow(m, s, o = {}) {
  const clock = h("span", { class: "rn-clock" });
  const pause = h("button", { type: "button", class: "td-pause" });
  const btn = h("button", { type: "button", class: "btn rn-refresh", title: "Count this site now, instead of waiting for the next live count" });
  const said = h("span", { class: "rn-said", role: "status", "aria-live": "polite" });
  const big = h("button", { type: "button", class: "rn-big", title: "Everyone on the site now" });
  const bars = h("div", { class: "td-bars", "aria-hidden": "true" });
  const last30 = h("button", { type: "button", class: "rn-30" });
  const list = h("ol", { class: "rn-list", "aria-label": "People on the site now" });
  const more = h("div", { class: "rn-more" });
  const el = h("section", { class: "rn", "aria-labelledby": "rn-h" },
    h("div", { class: "rn-head" }, h("h2", { id: "rn-h" }, h("span", { class: "td-live", "aria-hidden": "true" }), "Right now"),
      h("span", { class: "grow" }), clock, said, pause, btn),
    h("div", { class: "rn-body" },
      h("div", { class: "rn-left" }, big, bars, h("div", { class: "td-axis", "aria-hidden": "true" }, h("span", null, "30 min ago"), h("span", null, "now")), last30),
      h("div", { class: "rn-right" }, list, more)));
  let seen = !o.first;
  let busy = false;
  const rt = follow(m, { el, draw: (B) => draw(B), clock: (B) => tick(B), paused: (on) => paused(on) });
  const toList = () => { const f = more.querySelector("details"); if (f && !f.open) f.open = true; (f || list).scrollIntoView?.({ block: "nearest", behavior: reduced() ? "auto" : "smooth" }); };
  big.addEventListener("click", toList);
  last30.addEventListener("click", toList);
  pause.addEventListener("click", () => rt.pause(!rt.isPaused()));

  function label() { btn.replaceChildren(h("span", { class: `rn-ic${busy ? " spin" : ""}`, "aria-hidden": "true" }, "↻"), busy ? "Counting this site…" : "Refresh now"); }
  btn.addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    said.textContent = "";
    label();
    try {
      const res = await refreshSite();
      said.textContent = res.ok ? (res.result === "recent" ? "Counted a moment ago" : res.result === "busy" ? "Another count is running; it shows when it ends" : "Counted just now") : ""; // a failure is said once, by the page's toast (main.js)
      await pollNow();
    } finally {
      busy = false;
      if (el.isConnected) { btn.disabled = false; btn.removeAttribute("aria-busy"); label(); }
    }
  });
  label();

  function tick(B) {
    const p = people(B);
    const late = p?.until && Date.now() - ms(p.until) > 10 * 60000;
    clock.replaceChildren(rt.isPaused() ? `Paused at ${p?.until ? tzTime(p.until, { label: false }) : "-"}`
      : p?.until ? `Updated ${agoWords(p.until)}` : "No live count yet");
    clock.classList.toggle("late", !!late);
    clock.title = p?.until ? `Visitors as of ${tzTime(p.until, { seconds: true })}. Asked for again every 15 seconds; the live count itself runs every few minutes. Refresh now counts this site at once.` : "";
  }
  function paused(on) {
    el.classList.toggle("paused", on);
    pause.replaceChildren(h("span", { class: `td-pi ${on ? "play" : "hold"}`, "aria-hidden": "true" }), on ? "Resume" : "Pause");
    pause.setAttribute("aria-pressed", String(on));
    tick(rt.body());
  }
  function draw(B) {
    const p = people(B);
    tick(B);
    const now = p ? p.active?.[p.short ?? 5] ?? null : null;
    const in30 = p ? p.active?.[p.minutes ?? 30] ?? null : null;
    const came = p ? arrived(p.per_minute, p.short ?? 5) : null;
    big.replaceChildren(h("span", { class: "rn-n" }, now == null ? "-" : !seen && !reduced() ? counter(now) : n(now)),
      h("span", { class: "rn-nl" }, `${now === 1 ? "person" : "people"} on your site now`,
        p && came ? h("span", { class: "td-chip up", title: "Visits whose first request came in the last 5 minutes." }, `+${n(came)} in ${p.short ?? 5} min`) : null));
    last30.textContent = in30 == null ? "" : `${n(in30)} in the last 30 minutes`;
    const rows = p?.per_minute || [];
    const top = Math.max(1, ...rows.map((r) => r.under_way || 0));
    bars.replaceChildren(...rows.map((r, i) => h("span", { class: i === rows.length - 1 ? "td-bar last" : "td-bar", style: { height: `${Math.max(2, ((r.under_way || 0) / top) * 100)}%` },
      title: `${tzTime(r.at, { label: false })}: ${n(r.under_way || 0)} on the site, ${n(r.started || 0)} arrived` })));
    const all = ordered(p?.doing);
    list.replaceChildren(...(all.length ? all.slice(0, SHOWN).map((v) => row(m, v))
      : [h("li", { class: "empty" }, !p ? "The people on the site appear with the next live count. Press Refresh now to count at once." : "Nobody has been on the site in the last 30 minutes.")]));
    const rest = all.slice(SHOWN);
    more.replaceChildren(...(rest.length ? [urlFold("rn", `Everyone else in the last 30 minutes (${n(rest.length)})`, () => h("ol", { class: "rn-list" }, rest.map((v) => row(m, v))))] : []));
    seen = true;
  }
  draw(rt.body());
  paused(rt.isPaused());
  return el;
}
