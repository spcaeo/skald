// Overview > Summary in Live mode, row (b): where visitors are, the map full width (2.20).
// It draws Real time's answer (realtime.py, every 15 seconds through realtime.js follow()):
//   * the map (rt-map.js): countries shaded by visits today, a pulsing dot on each city with
//     someone active in the last 30 minutes; today's visits by country (flag and three-letter
//     code). With a drill-down to a country or a city (dd=country:CA), only that country's
//     shading and cities: the others are dimmed
//   * under it, "What visitors are doing now" (ov-doing.js): the newest visitors' paths and
//     the pages read in the last 30 minutes. It replaced the Newest visits panel and the
//     pages list that sat under the map (2.20), so a visit is never shown twice.
// Each part: {el, draw(body), paused(on)}.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { worldMap } from "./rt-map.js";
import { open as openDrill, chainOf } from "../drill.js";
import { flagEl, country, countryName, cityCode } from "./readers.js";
import { goLink, cardHead, hrefTo } from "./ov-today-bits.js";

const people = (B) => (B && (B.people_state === "ok" || B.people_state === "stale") ? B.people : null);
const NO_COUNT = "The visitors now appear with the next live count (every 2 minutes).";

/* The map's countries and cities, narrowed to a drill-down's country or city (the others dimmed). */
export function mapRows(P, chain) {
  const cc = chain.find(([d]) => d === "country")?.[1] || (chain.find(([d]) => d === "city") ? cityCode(chain.find(([d]) => d === "city")[1]) : "");
  const town = chain.find(([d]) => d === "city")?.[1] || "";
  const countries = P?.countries || {}, cities = P?.cities || null;
  if (!cc) return { countries, cities, only: "" };
  return { countries: countries[cc] ? { [cc]: countries[cc] } : {}, only: cc,
    cities: cities ? Object.fromEntries(Object.entries(cities).filter(([k]) => (town ? k === town : cityCode(k) === cc))) : null };
}

// ------------------------------------------------------------- where visitors are
export function placesCard(m, rt, first, { onHover } = {}) {
  const map = worldMap({ onPick: (cc) => openDrill("country", cc), onCity: (k) => openDrill("city", k), onHover,
    label: "World map: visits today by country, and the cities with visitors active in the last 30 minutes" });
  const chips = h("div", { class: "td-cc" });
  const empty = h("p", { class: "empty", hidden: true }, NO_COUNT);
  const el = h("section", { class: "td-card td-places", "aria-labelledby": "td-map-h" },
    cardHead("td-map-h", "Where visitors are", "Shaded by visits today. A pulsing dot for each city with someone on the site in the last 30 minutes.", goLink("traffic/places", "Traffic › Places")),
    h("div", { class: "td-map" }, map.el), empty, chips);
  function draw(B) {
    const P = people(B);
    empty.hidden = !!P;
    const got = mapRows(P, chainOf(S.read()));
    map.update(got.countries, got.cities);
    el.classList.toggle("td-only", !!got.only);
    const rows = Object.entries(P?.countries || {}).filter(([, r]) => r.visits > 0).sort((a, b) => b[1].visits - a[1].visits);
    const top = rows.slice(0, 5), rest = rows.slice(5);
    const restN = rest.reduce((a, [, r]) => a + r.visits, 0);
    chips.replaceChildren(...(rows.length ? [h("span", { class: "td-ccl" }, "Today by country"),
      ...top.map(([cc, r]) => h("button", { type: "button", class: "td-chipc", title: `${countryName(cc)}: ${n(r.visits)} visit${r.visits === 1 ? "" : "s"} today`, onclick: () => openDrill("country", cc) },
        flagEl(cc), h("b", null, country(cc)), h("span", null, n(r.visits)))),
      rest.length ? h("a", { class: "td-chipc", href: hrefTo("traffic/places"), title: `${rest.length} more countries` }, h("b", null, `+${rest.length}`), h("span", null, n(restN))) : null].filter(Boolean) : []));
  }
  return { el, draw, hot: map.hot };
}
