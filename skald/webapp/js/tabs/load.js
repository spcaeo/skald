// Server load: every request the server answered - each file, not each page -
// split into the five groups that add up to the log. Shown collapsed at the
// bottom of Overview and at the top of Site health, never as a headline:
// one page view loads about twenty files, so requests dwarf people.

import { h, n, counter, pct1, ICON, reduced } from "../ui.js";
import { GROUPS, color } from "../data.js";
import { band } from "../charts.js";

// What each group's requests are, in words that say the unit.
export const LOAD_NAMES = {
  people: "Files loaded for people's visits",
  answer_engines: "Fetched by AI assistants",
  search_engines: "Fetched by search engines",
  bots: "Bots and scanners",
  ours: "Our own tools",
};

// Files per page view, from the period's own figures: "about 20".
export function filesPerPage(t) {
  const files = t.hits?.people, pages = t.views;
  return files && pages ? Math.round(files / pages) : null;
}

export function serverLoad(t, r, cov, { play = false } = {}) {
  const parts = GROUPS.map(([g]) => ({ g, name: LOAD_NAMES[g], value: t.hits?.[g] || 0, color: color(g) }));
  const sumOf = parts.reduce((s, p) => s + p.value, 0);
  const requests = t.requests ?? sumOf;
  const adds = sumOf === requests;
  const per = filesPerPage(t);
  return h("div", { class: "load" },
    h("div", { class: "load-top" }, h("b", { class: "load-n" }, play ? counter(requests) : n(requests)),
      h("span", null, `requests ${r.kind === "today" ? "so far today" : `over ${cov?.ok === 1 ? "the 1 whole day" : `the ${cov?.ok ?? r.length} whole days`}`}: every file the server sent, pages, images, scripts and data.`)),
    band(parts, requests, play),
    h("div", { class: "load-keys" }, parts.map((p) => h("div", { class: "key" },
      h("div", { class: "k-name" }, h("span", { class: "k-sw", style: { background: p.color } }), p.name),
      h("div", { class: "k-v" }, n(p.value)), h("div", { class: "k-p" }, `${pct1(p.value, requests)} of requests`)))),
    h("p", { class: "note" }, per ? `One page view loads about ${per} files here, so requests are much larger than pages read.` : "One page view loads many files, so requests are much larger than pages read."),
    h("div", { class: `sum${adds ? "" : " bad"}${play && !reduced() ? " play" : ""}`, html: adds ? ICON.check : ICON.cross },
      h("span", null, adds ? `The five groups add up to ${n(requests)} exactly.` : `The groups do not add up to the requests (${n(sumOf)} against ${n(requests)}). These figures should not be trusted.`)));
}
