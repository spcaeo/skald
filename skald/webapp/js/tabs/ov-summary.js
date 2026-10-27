// Overview > Summary (2.7.0; one order for every period, 2.13).
//
// Live mode (the period Today, "Today · Live") is its own page, the owner's
// approved layout: the live strip with "vs yesterday at this hour", where
// visitors are and the newest visits, sources and the flow, what converted,
// AI & bots (ov-today.js). One place per answer, each linking to its full tab.
//
// Any other period: every figure is drawn by overview.js exactly as before (the
// same code, the same files); this file arranges what it returns in the same
// order as Live mode, where it applies:
//   tiles (laid out evenly, css/overview.css) and their one-line relation, the
//   main chart, then where (countries, top pages), then where they came from
//   (top sources) beside the AI assistants, then who else came (machines, with
//   a link to AI & bots > Crawlers), then Server requests as one line with its
//   total and a link to Site > Health, then each day's figures.
//
// 2.42 (the UX build's polish): the key figures, the main chart and "What changed" stay
// open; everything after them (countries, top pages and sources, AI assistants, who else
// came, the two release-2 cards, server requests, each day) is one fold, "More for this
// period", kept in the address (ovx_view=open). Each part has its own tab as well.
//
// From your tools (ov-tools.js): after "What changed", outside the fold, one small card with
// the figures of the person's own tools (Google Analytics...), each labelled with its tool;
// one folded line when none is connected.

import { h } from "../ui.js";
import { later } from "../lazy.js";
import overview from "./overview.js";
import today from "./ov-today.js";
import { goTo } from "./ov-live.js";
import { setupStrip } from "./ov-setup.js";
import { figures } from "../data.js";
import { compareOf } from "../mode-compare.js";
import { periodLine } from "../period-line.js";
import { whatChanged } from "./ov-changed.js";
import { workCard } from "./ov-work.js";
import { freshCard } from "./ov-fresh.js";
import { urlFold } from "../ui/fold.js";
import { toolsCard } from "./ov-tools.js";

/* Everything after the chart and What changed, in one fold kept in the address. */
function foldTheRest(out) {
  const chart = out.findIndex((el) => el instanceof Element && el.matches("section.s") && !!el.querySelector(":scope > .sheet"));
  if (chart < 0) return out;
  let cut = chart + 1;
  if (out[cut] instanceof Element && out[cut].matches("section.wc")) cut += 1;
  if (out[cut] instanceof Element && out[cut].matches("section.yt-card")) cut += 1;
  const rest = out.slice(cut).filter(Boolean);
  if (!rest.length) return out;
  return [...out.slice(0, cut), urlFold("ovx", "More for this period: countries, top pages and sources, AI assistants, who else came, pages to work on, new pages, server requests and each day", rest)];
}

/* Live mode is the period Today (the map, section 3): the address keeps
   range=today, so every today-path in data.js stays as it is. */
export const isLive = (s) => s.range === "today";

const is = (el, cls) => el instanceof Element && el.classList.contains(cls);

// The strip of tiles: laid out evenly.
function arrangeTiles(strip) {
  strip.classList.add("ov-tiles");
  strip.dataset.n = String(strip.children.length);
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

/* The four top cards (pages, sources, countries, AI assistants) in Live mode's
   order: where (countries, pages), where from (sources), then AI & bots. */
function inOrder(out) {
  const tops = out.find((el) => el instanceof Element && el.matches(".cols.tops"));
  const others = out.find((el) => el instanceof Element && el.matches("section.s") && el.querySelector(":scope > ul.others"));
  if (!tops || tops.children.length !== 4) return out;
  const [pages, sources, countries, ai] = [...tops.children];
  const where = h("div", { class: "cols tops" }, countries, pages);
  const from = h("div", { class: "cols tops" }, sources, ai);
  return out.flatMap((el) => (el === tops ? [where, from, ...(others ? [others] : [])] : el === others ? [] : [el]));
}

/* Release 2's cards (Main.dc.html S3, S6, S10, S11): the period line under the title,
   "What changed" after the main chart, then "Work on the page, or on traffic?" beside
   "New and updated pages", before the server requests line. */
function release2(m, s, out) {
  const at = (test) => out.findIndex((el) => el instanceof Element && test(el));
  const head = at((el) => is(el, "head"));
  out.splice(head + 1, 0, periodLine(m, s));
  const { r, t } = figures(m, s);
  if (!t) return out;
  const chart = at((el) => el.matches("section.s") && !!el.querySelector(":scope > .sheet"));
  if (chart >= 0) out.splice(chart + 1, 0, ...[whatChanged(m, s, r, t, compareOf(m, s)), toolsCard(m)].filter(Boolean));
  const server = at((el) => is(el, "ov-line"));
  // Each card waits for its page files on its own (lazy.js): the figures above do not wait.
  out.splice(server >= 0 ? server : out.length, 0, h("div", { class: "cols wf" },
    later(m, ["page_trends"], () => workCard(m, s, r, t), "Work on the page, or on traffic?"),
    later(m, ["page_trends", "page_index"], () => freshCard(m, s), "New and updated pages: are they getting found?")));
  return out;
}

export default function summary(m, s, o) {
  // Live mode is today itself: no Include today, no whole period to compare; the period line stays off.
  if (isLive(s)) return today(m, s, o);
  let out = [overview(m, s, o)].flat(Infinity).filter(Boolean);
  const strip = out.find((el) => is(el, "tiles"));
  if (strip) arrangeTiles(strip);
  for (const el of out) if (el instanceof Element && el.matches("section.s") && el.querySelector(":scope > ul.others")) linkOthers(el);
  const i = out.findIndex((el) => el instanceof Element && el.matches("details.fold") && /^Server requests/.test(el.querySelector("summary")?.textContent || ""));
  if (i >= 0) out[i] = serverLine(out[i]);
  out = inOrder(out);
  out = release2(m, s, out);
  out = foldTheRest(out);
  // A new site's first-run checklist (owners and admins, until done or hidden): one line under
  // the title, the list folded (2.41, ov-setup.js), so the figures come first.
  const setup = setupStrip(m);
  if (setup) out.splice(out.findIndex((el) => is(el, "head")) + 1, 0, setup);
  return out.filter(Boolean);
}
