// Overview > Summary (2.7.0): the old Overview page, with the old Live page's
// own panels in Live mode, and one place per answer.
//
// Every figure is drawn by overview.js exactly as before (the same code, the
// same files); this file only arranges what it returns:
//   * the tiles: one strip laid out evenly (4 + 3; 3 + 3 without demos; two
//     columns on a phone), so no tile sits alone and no trend line stretches
//     across a row (css/overview.css)
//   * Server requests: one line with its total and a link to Site > Health,
//     where the full band is (the map's D16)
//   * Who else came: a link to AI & bots > Crawlers (D3)
//   * Live mode (the period Today, "Today · Live"): Real time first (realtime.js:
//     visitors now, minute by minute, the world map), then "+N this hour" on the
//     Visitors tile, then Right now and today's leads and bookings, short, each
//     with a link to the full list (ov-live.js). The hourly chart, who else came
//     and today's top fives are Overview's own for today. Redrawn every 2 minutes
//     (the `live` option in s-overview.js).

import { h, n } from "../ui.js";
import { figures } from "../data.js";
import overview from "./overview.js";
import { rightNow, leadsToday, thisHour, goTo } from "./ov-live.js";
import { realtimeBlock } from "./realtime.js";

/* Live mode is the period Today (the map, section 3): the address keeps
   range=today, so every today-path in data.js stays as it is. */
export const isLive = (s) => s.range === "today";

const is = (el, cls) => el instanceof Element && el.classList.contains(cls);
const label = (tile) => tile.querySelector(".t-l")?.textContent.trim();

// The strip of tiles: evenly laid out, and "+N this hour" on Visitors in Live mode.
function arrangeTiles(strip, extra) {
  strip.classList.add("ov-tiles");
  strip.dataset.n = String(strip.children.length);
  if (extra == null) return;
  const visitors = [...strip.children].find((t) => label(t) === "Visitors");
  const line = visitors?.querySelector(".t-c");
  // The change line says "—" for a day still running; in Live mode it says how many came this hour.
  if (line) line.replaceWith(h("span", { class: "t-c" }, `+${n(extra)} this hour`));
}

// The server requests fold: its total on one line, the band on Site > Health.
function serverLine(fold) {
  const total = fold.querySelector("summary > span")?.textContent || "-";
  return h("p", { class: "ov-line" }, h("span", null, "Server requests (every file: pages, images, scripts): ", h("b", null, total), "."), " ",
    goTo("site/health", "By kind: Site › Health"));
}

// Who else came: one row here, every machine on AI & bots > Crawlers.
function linkOthers(section) {
  const top = section.querySelector(".card-h");
  if (top && !top.querySelector(".ov-go")) top.append(h("span", { class: "grow" }), goTo("ai/crawlers", "AI & bots › Crawlers"));
}

export default function summary(m, s, o) {
  const out = [overview(m, s, o)].flat(Infinity).filter(Boolean);
  const live = isLive(s);
  const { t } = figures(m, s);
  const strip = out.find((el) => is(el, "tiles"));
  if (strip) arrangeTiles(strip, live && t ? thisHour(m, t) : null);
  for (const el of out) if (el instanceof Element && el.matches("section.s") && el.querySelector(":scope > ul.others")) linkOthers(el);
  const i = out.findIndex((el) => el instanceof Element && el.matches("details.fold") && /^Server requests/.test(el.querySelector("summary")?.textContent || ""));
  if (i >= 0) out[i] = serverLine(out[i]);
  if (live && t) {
    // After the tiles and their one-line relation: what is happening now, then the hour by hour.
    const at = out.findIndex((el) => is(el, "relate"));
    const after = at >= 0 ? at + 1 : out.indexOf(strip) + 1;
    out.splice(after, 0, rightNow(m), leadsToday(m));
  }
  // Live mode opens on Real time: right under the page's title, before the tiles.
  if (live) {
    const at = out.findIndex((el) => is(el, "head"));
    out.splice(at + 1, 0, realtimeBlock(m, s));
  }
  return out.filter(Boolean);
}
