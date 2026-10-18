// Overview > Summary in Live mode ("Today · Live", the period Today): the
// owner's approved layout (2.13), one place per answer, each with a link to the
// tab that lists it all:
//
//   (a) the live strip: visitors on the site now and arrivals in the last 5
//       minutes, minute by minute (Real time's answer, every 15 seconds, one
//       Pause for the whole page); then Visitors, Pages read, Leads and
//       Visitors from AI, each against yesterday at this hour (by-now.js)
//   (b) where visitors are (Real time's map, cities pulsing) and the newest
//       visits (each opens the visitor drawer)            ov-today-cards.js
//   (c) where today's visitors came from, (d) how today's visits moved
//   (e) what converted today, (f) AI & bots today          ov-today-more.js
//
// Nothing here counts anything new except "vs yesterday at this hour", which
// by_now.py and conversions_leads.by_now count and audit_by_now.py and
// audit_conversions_leads.py count again. Every other figure is one the page
// already shows elsewhere, from the same field.

import { h, n, long, counter, reduced, tip, untip } from "../ui.js";
import { figures } from "../data.js";
import { head, nothing } from "./common.js";
import { leadsOn, convFile } from "./leadfigs.js";
import { follow } from "./realtime.js";
import { setupChecklist } from "./checklist.js";
import { comparisons, delta, running, arrived } from "../by-now.js";
import { time as tzTime, label as tzLabel } from "../tz.js";
import { placesCard, newestCard } from "./ov-today-cards.js";
import { sourcesCard, flowCard, convertedCard, aiCard } from "./ov-today-more.js";
import { hrefTo } from "./ov-today-bits.js";

const TILE = {
  visitors: ["Visitors", "Visits that read at least one page today so far, counted only when the browser loaded the page's scripts and styles.", "traffic/visitors", "var(--g-people)"],
  pages: ["Pages read", "Page views by visitors today so far.", "traffic/pages", "var(--views)"],
  leads: ["Leads", "Forms sent and demos booked today so far, completed, from the lead store and the tools; test rows never counted.", "sales/pipeline", "var(--leads)"],
  ai: ["Visitors from AI", "Visitors who arrived by following a link in an AI assistant's answer today so far.", "ai/assistants", "var(--g-answer_engines)"],
};

// ------------------------------------------------------------- a tile's spark
const W = 240, H = 40;
function spark(c, colour) {
  const tp = running(c.hoursToday, c.at), yp = running(c.hoursYesterday, c.at);
  if (!tp) return h("div", { class: "td-spark none", "aria-hidden": "true" });
  const top = Math.max(1, ...tp.map((p) => p[1]), ...(yp || []).map((p) => p[1])) * 1.06;
  const X = (hr) => ((hr / 24) * W).toFixed(1), Y = (v) => (H - 1 - (v / top) * (H - 4)).toFixed(1);
  const path = (pts) => `M${pts.map(([a, b]) => `${X(a)} ${Y(b)}`).join("L")}`;
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", class: "td-svg", "aria-hidden": "true" });
  svg.append(el("line", { x1: 0, y1: H - 0.5, x2: W, y2: H - 0.5, class: "td-base" }));
  if (yp) svg.append(el("path", { d: path(yp), class: "td-yest" }));
  const last = tp[tp.length - 1];
  svg.append(el("path", { d: `${path(tp)}L${X(last[0])} ${H - 0.5}L0 ${H - 0.5}Z`, class: "td-area", style: `fill:${colour}` }));
  svg.append(el("path", { d: path(tp), class: "td-line", style: `stroke:${colour}` }));
  const dot = h("span", { class: "td-dot", style: { background: colour, left: `calc(${((last[0] / 24) * 100).toFixed(2)}% - 3.5px)`, top: `${Number(Y(last[1])) - 3.5}px` } });
  const box = h("div", { class: "td-spark" }, svg, dot);
  // Hover: the running totals at that hour, today and yesterday.
  const at = (pts, hr) => { let v = null; for (const [a, b] of pts || []) if (a <= hr) v = b; return v; };
  box.addEventListener("pointermove", (e) => {
    const r = box.getBoundingClientRect();
    const hr = Math.min(last[0], Math.max(0, ((e.clientX - r.left) / r.width) * 24));
    const shownAt = hr >= Math.floor(last[0]) ? last[0] : Math.round(hr);
    const label = shownAt === last[0] ? `By ${c.at}` : `By ${String(shownAt).padStart(2, "0")}:00`;
    tip(e.clientX, r.top, label, [{ color: colour, value: n(at(tp, shownAt)), label: "today" },
      ...(yp ? [{ color: "var(--hatch)", value: n(at(yp, shownAt)), label: "yesterday" }] : [])]);
  });
  box.addEventListener("pointerleave", untip);
  return box;
}

function tile(c, first) {
  const [label, def, route, colour] = TILE[c.key];
  const d = delta(c.today, c.yesterday);
  const value = c.today == null ? "-" : first ? counter(c.today) : n(c.today);
  const was = c.yesterday != null ? (c.key === "leads" ? `vs ${n(c.yesterday)} yesterday by ${c.at}` : `vs ${n(c.yesterday)} yesterday at this hour`) : null;
  const line = d ? h("span", { class: "td-kc" }, h("span", { class: `td-chip ${d.dir}` }, d.dir === "up" ? "▲ " : d.dir === "down" ? "▼ " : "", d.text), h("span", null, was))
    : h("span", { class: "td-kc", title: c.why ? `Not compared: ${c.why}.` : null }, c.today == null ? "Not counted yet today" : "vs yesterday at this hour: not recorded");
  return h("a", { class: "td-k", role: "listitem", href: hrefTo(route), title: `${def} Compared with yesterday from midnight to the same time of day${c.at ? ` (${c.at})` : ""}, counted by the same rules.` },
    h("span", { class: "td-kl" }, label), h("span", { class: "td-kv" }, value), line, spark(c, colour),
    h("span", { class: "td-key", "aria-hidden": "true" }, h("span", null, h("i", { class: "td-sw", style: { background: colour } }), "Today"),
      h("span", null, h("i", { class: "td-sw dash" }), "Yesterday")));
}

// ------------------------------------------------------------- now, minute by minute
function nowPanel(m, rt) {
  const el = h("div", { class: "td-now" });
  const clock = h("span", { class: "td-clock" });
  const pause = h("button", { type: "button", class: "td-pause" });
  pause.addEventListener("click", () => rt.pause(!rt.isPaused()));
  const big = h("div", { class: "td-big" });
  const bars = h("div", { class: "td-bars", "aria-hidden": "true" });
  let seen = false;
  const P = (B) => (B && (B.people_state === "ok" || B.people_state === "stale") ? B.people : null);
  function paused(on) {
    el.classList.toggle("paused", on);
    pause.replaceChildren(h("span", { class: `td-pi ${on ? "play" : "hold"}`, "aria-hidden": "true" }), on ? "Resume live" : "Pause live");
    pause.setAttribute("aria-pressed", String(on));
    tick(rt.body());
  }
  function tick(B) {
    const p = P(B);
    clock.replaceChildren(h("span", { class: "td-live", "aria-hidden": "true" }),
      rt.isPaused() ? `Paused at ${p?.until ? tzTime(p.until, { label: false }) : "-"}` : p?.until ? `Live, as of ${tzTime(p.until, { seconds: true, label: false })}` : "Live: no count yet");
  }
  function draw(B) {
    const p = P(B);
    tick(B);
    const now = p ? p.active?.[p.short ?? 5] ?? null : null;
    const came = p ? arrived(p.per_minute, p.short ?? 5) : null;
    big.replaceChildren(h("span", { class: "td-n" }, now == null ? "-" : !seen && !reduced() ? counter(now) : n(now)),
      h("span", { class: "td-nw" }, h("span", { class: "td-nl" }, `visitor${now === 1 ? "" : "s"} on the site now`),
        p ? h("span", { class: `td-chip ${came ? "up" : "same"}`, title: "Visits whose first request came in the last 5 clock minutes (Real time's minute by minute)." }, `+${n(came)} in the last ${p.short ?? 5} min`)
          : h("span", { class: "td-sub" }, "The visitors now appear with the next live count (every 2 minutes).")));
    const rows = p?.per_minute || [];
    const top = Math.max(1, ...rows.map((r) => r.under_way || 0));
    bars.replaceChildren(...rows.map((r, i) => h("span", { class: i === rows.length - 1 ? "td-bar last" : "td-bar", style: { height: `${Math.max(2, ((r.under_way || 0) / top) * 100)}%` },
      title: `${tzTime(r.at, { label: false })}: ${n(r.under_way || 0)} on the site, ${n(r.started || 0)} arrived` })));
    seen = true;
  }
  el.append(h("div", { class: "td-nowh" }, clock, pause), big, bars,
    h("div", { class: "td-axis", "aria-hidden": "true" }, h("span", null, "30 min ago"), h("span", null, "Visitors a minute"), h("span", null, "now")));
  return { el, draw, tick, paused };
}

// ------------------------------------------------------------- the page
export default function today(m, s, o = {}) {
  const { r, t } = figures(m, s);
  const out = [...head("Overview", r, null)];
  const setup = setupChecklist(m);
  if (setup) out.push(setup);
  const first = !!o.first;
  // One follower of Real time's answer draws every live part of the page.
  const parts = [];
  const strip = h("section", { class: "td-strip", "aria-label": "Right now and today" });
  const rt = follow(m, { el: strip, draw: (B) => parts.forEach((p) => p.draw(B)), clock: (B) => parts.forEach((p) => p.tick?.(B)), paused: (on) => parts.forEach((p) => p.paused?.(on)) });
  const now = nowPanel(m, rt);
  parts.push(now);
  const lf = t ? leadsOn(m, [m.today]) : null;
  const cs = comparisons(m.live, convFile(m), {
    visitors: t && !t.unmeasured?.readers ? t.readers ?? null : null, pages: t?.views ?? null,
    leads: lf?.ok ? lf.leads : null, ai: t?.cited ?? null,
  });
  const shownKeys = convFile(m) ? cs : cs.filter((c) => c.key !== "leads");
  strip.append(now.el, h("div", { class: "td-kpis", role: "list", "data-n": String(shownKeys.length) }, shownKeys.map((c) => tile(c, first))));
  out.push(strip);
  if (!t) return [...out, nothing(m, r)];
  const places = placesCard(m, rt, first), newest = newestCard(m, rt, first);
  parts.push(places, newest);
  out.push(h("div", { class: "td-row td-r1" }, places.el, newest.el));
  out.push(h("div", { class: "td-row td-r2" }, sourcesCard(m, t), flowCard(m, r)));
  const conv = convertedCard(m);
  out.push(h("div", { class: `td-row td-r3${conv ? "" : " one"}` }, conv, aiCard(t)));
  parts.forEach((p) => p.draw(rt.body()));
  parts.forEach((p) => p.paused?.(rt.isPaused()));
  const until = m.live?.generated_at;
  out.push(h("p", { class: "td-foot" }, `Today so far, ${long(m.today)}, 00:00 to ${until ? tzTime(until, { label: false }) : "now"} ${tzLabel()}. `,
    "Visitors now refresh every 15 seconds; the other figures with each live count, every 2 minutes. Yesterday at this hour is yesterday counted again from the log to the same time of day, by the same rules, and recounted by the audit."));
  return out;
}
