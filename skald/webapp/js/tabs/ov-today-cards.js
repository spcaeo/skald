// Overview > Summary in Live mode, row (b): where visitors are, and the newest
// visits. Both draw Real time's answer (realtime.py, every 15 seconds through
// realtime.js follow()), the same fields the Real time tab lists in full:
//   * the map (rt-map.js): countries shaded by visits today, a pulsing dot on
//     each city with someone active in the last 30 minutes; today's visits by
//     country (flag and three-letter code); the pages read in the last 30 minutes
//   * the newest visits, newest first; each opens the visitor drawer
//     (realtime.openNewest: the day's journey when the page holds it). A row
//     new since the last answer slides in (none with reduced motion).
// Each part: {el, draw(body), paused(on)}.

import { h, n, reduced } from "../ui.js";
import { worldMap } from "./rt-map.js";
import { open as openDrill } from "../drill.js";
import { flagEl, country, countryName, cityName } from "./readers.js";
import { mark } from "../icons.js";
import { shown, assistantName } from "../labels.js";
import { time as tzTime } from "../tz.js";
import { openNewest } from "./realtime.js";
import { touchLine } from "./visitor.js";
import { pagesOf } from "../flow.js";
import { goLink, cardHead, hrefTo } from "./ov-today-bits.js";

const people = (B) => (B && (B.people_state === "ok" || B.people_state === "stale") ? B.people : null);
const NO_COUNT = "The visitors now appear with the next live count (every 2 minutes).";

// ------------------------------------------------------------- where visitors are
export function placesCard(m, rt) {
  const map = worldMap({ onPick: (cc) => openDrill("country", cc), onCity: (k) => openDrill("city", k),
    label: "World map: visits today by country, and the cities with visitors active in the last 30 minutes" });
  const chips = h("div", { class: "td-cc" });
  const pages = h("div", { class: "td-pg" });
  const empty = h("p", { class: "empty", hidden: true }, NO_COUNT);
  const el = h("section", { class: "td-card td-places", "aria-labelledby": "td-map-h" },
    cardHead("td-map-h", "Where visitors are", "Shaded by visits today. A pulsing dot for each city with someone on the site in the last 30 minutes.", goLink("traffic/places", "Traffic › Places")),
    h("div", { class: "td-map" }, map.el), empty, chips, pages);
  function draw(B) {
    const P = people(B);
    empty.hidden = !!P;
    map.update(P?.countries || {}, P?.cities || null);
    const rows = Object.entries(P?.countries || {}).filter(([, r]) => r.visits > 0).sort((a, b) => b[1].visits - a[1].visits);
    const top = rows.slice(0, 5), rest = rows.slice(5);
    const restN = rest.reduce((a, [, r]) => a + r.visits, 0);
    chips.replaceChildren(...(rows.length ? [h("span", { class: "td-ccl" }, "Today by country"),
      ...top.map(([cc, r]) => h("button", { type: "button", class: "td-chipc", title: `${countryName(cc)}: ${n(r.visits)} visit${r.visits === 1 ? "" : "s"} today`, onclick: () => openDrill("country", cc) },
        flagEl(cc), h("b", null, country(cc)), h("span", null, n(r.visits)))),
      rest.length ? h("a", { class: "td-chipc", href: hrefTo("traffic/places"), title: `${rest.length} more countries` }, h("b", null, `+${rest.length}`), h("span", null, n(restN))) : null] : []));
    const read = Object.entries(P?.pages || {}).filter(([k, v]) => v > 0 && k !== "(all others)").sort((a, b) => b[1] - a[1]).slice(0, 5);
    const most = Math.max(1, ...read.map(([, v]) => v));
    pages.replaceChildren(...(P ? [h("div", { class: "td-pgh" }, h("b", null, "Read in the last 30 minutes"), h("span", null, `${n(P.page_views || 0)} page view${P.page_views === 1 ? "" : "s"} by visitors`)),
      ...(read.length ? read.map(([path, v]) => h("div", { class: "td-pgr" },
        h("button", { type: "button", class: "td-path", title: `Open ${path}`, onclick: () => openDrill("path", path) }, path),
        h("span", { class: "td-pgb", "aria-hidden": "true" }, h("i", { style: { width: `${(v / most) * 100}%` } })), h("span", { class: "td-num" }, n(v))))
        : [h("p", { class: "empty" }, "No page read in the last 30 minutes.")])] : []));
  }
  return { el, draw };
}

// ------------------------------------------------------------- newest visits
const seen = { keys: null };
const keyOf = (v) => `${v.start}|${v.seq ?? ""}|${v.country}|${v.landing}`;

function journeyOf(m, v) {
  const day = String(v.start || "").slice(0, 10);
  return v.seq != null ? (m.journeys || []).find((x) => x.seq === v.seq && x.day === day) || null : null;
}

function leftAt(j) {
  const t = Date.parse(j?.start || "");
  if (!t || j.seconds == null) return "";
  return tzTime(new Date(t + j.seconds * 1000).toISOString(), { label: false });
}

function row(m, v, cls) {
  const j = journeyOf(m, v);
  const trail = j ? pagesOf(j) : v.landing ? [v.landing] : [];
  const ai = v.source === "AI assistant";
  const who = v.via ? (ai ? assistantName(v.via) : v.via) : shown(v.source) || "Source not recorded";
  const kind = v.via ? shown(v.source) : "";
  const place = v.city ? String(v.city).split(", ")[0] : "";
  const ft = touchLine(v);
  const openIt = () => openNewest(m, v);
  return h("li", { class: cls || null },
    h("div", { class: "td-vrow", role: "button", tabindex: "0", "aria-label": `Open this visitor: ${v.city ? cityName(v.city) : countryName(v.country)}, from ${who}, landed on ${v.landing || "a page"}`,
      onclick: openIt, onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openIt(); } } },
      h("span", { class: "td-vt" }, tzTime(v.start, { label: false })),
      h("span", { class: "td-vb" },
        h("span", { class: "td-vl" },
          h("span", { class: "td-vc", title: countryName(v.country) }, flagEl(v.country), h("b", null, country(v.country))),
          place ? h("span", null, place) : null,
          v.device ? h("span", { class: "td-vd", title: v.device }, mark("device", v.device) || v.device) : null,
          h("span", { class: "td-vs" }, mark(ai || v.via ? "referrer" : "source", v.via || v.source), h("b", null, who), kind ? h("small", null, kind) : null)),
        ft ? h("span", { class: "td-vf" }, ft.replace(/^first/, "First")) : null,
        h("span", { class: "td-vp" }, trail.length ? trail.join(" › ") : "landing page not recorded")),
      h("span", { class: "td-vr" },
        h("span", { class: "td-num" }, h("b", null, n(v.pages ?? 0)), ` page${v.pages === 1 ? "" : "s"}`),
        v.active === "5" ? h("span", { class: "td-act" }, h("i", { "aria-hidden": "true" }), "Active now")
          : leftAt(j) ? h("span", { class: "td-left" }, `Left ${leftAt(j)}`)
            : v.active ? h("span", { class: "td-left" }, "Seen in the last 30 min") : null)));
}

export function newestCard(m, rt, first) {
  const list = h("ol", { class: "td-feed", "aria-live": "polite" });
  const held = h("div", { class: "td-held", role: "status", hidden: true });
  const el = h("section", { class: "td-card td-newest", "aria-labelledby": "td-feed-h" },
    cardHead("td-feed-h", "Newest visits", "Updates as visitors arrive. Select one for its journey.", goLink("traffic/visitors", "Traffic › Visitors")), held, list);
  function draw(B) {
    const P = people(B);
    const rows = (P?.newest || []).slice(0, 8);
    const before = seen.keys;
    seen.keys = new Set(rows.map(keyOf));
    const motion = !reduced();
    list.replaceChildren(...(rows.length ? rows.map((v, i) => {
      // New since the last answer: slides in. The first draw: the top rows rise once.
      const fresh = motion && before && !before.has(keyOf(v));
      const cls = fresh ? "td-in" : motion && !before && first && i < 3 ? `td-rise td-rise${i}` : "";
      return row(m, v, cls);
    }) : [h("li", { class: "empty" }, P ? "No visitor has read a page yet today." : NO_COUNT)]));
  }
  function paused(on) {
    held.hidden = !on;
    held.replaceChildren(h("span", null, "Paused: the visitors now, the map and this list hold still."),
      h("button", { type: "button", class: "btn", onclick: () => rt.pause(false) }, "Resume"));
  }
  return { el, draw, paused };
}
