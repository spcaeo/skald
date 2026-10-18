// Visitor flow, where it is shown: Traffic > Visitors ("Visitor flow", for the
// range and the filters) and the drill-down drawer ("How these visitors moved",
// for any dd= trail, so Overview > Summary?dd=country:CA has it too). Funnels
// draws its own from its steps (funnels.js). The flow is flow.js's, from the
// journeys the page holds; sankey.js draws it.

import { h, n, short } from "../ui.js";
import { shown } from "../labels.js";
import { flowOf, check, keptFor, OTHER, OTHER_SOURCES } from "../flow.js";
import { sankey } from "../sankey.js";
import { open } from "../drill.js";
import { country, city } from "./readers.js";
import { journeyFilter } from "./visits.js";
import { fileName } from "./common.js";
import { openVisitor } from "./visitor.js";
import { time as tzTime } from "../tz.js";

// The reader's choices, kept while the page is open.
const pick = { start: "source", depth: 4 };
const TOP = 7;

const RULE = "Each visit once: where it came from, then its pages in order (a page loaded twice in a row counts once; moves inside the site count, as in Common next steps), then where it left. Each column keeps its 7 biggest values and folds the rest, so every column adds up to the visits.";

function words(nd) {
  if (nd.label === OTHER) return "Other pages";
  if (nd.label === OTHER_SOURCES) return "Other sources";
  if (nd.col === 0 && nd.drill?.[0] === "source") return shown(nd.label) || "Not recorded";
  return nd.label;
}

function controls(redraw) {
  const seg = (label, key, opts) => h("div", { class: "seg plain", role: "group", "aria-label": label },
    opts.map(([v, w]) => h("button", { type: "button", "aria-pressed": String(pick[key] === v),
      onclick: () => { pick[key] = v; redraw(); } }, w)));
  return h("div", { class: "sk-pick" },
    h("span", { class: "add-l" }, "Start from"), seg("Start the flow from", "start", [["source", "Source type"], ["via", "Who sent them"]]),
    h("span", { class: "add-l" }, "Pages"), seg("Pages drawn", "depth", [[3, "3"], [4, "4"], [5, "5"]]));
}

/* The map of a list of journeys, with its controls; withheld when it does not add up.
   from: "drill" narrows the drawer's trail on a click; else a click opens a new one. */
function flowBlock(js, { label, file, from, note, width }) {
  const holder = h("div", { class: "sheet sk-holder" });
  const redraw = () => {
    const flow = flowOf(js, { depth: pick.depth, top: TOP, start: pick.start });
    const off = check(flow);
    if (off.length) {
      holder.replaceChildren(h("div", { class: "state bad", role: "alert" }, h("div", null, `The flow is withheld: it does not add up (${off.slice(0, 2).join("; ")}).`)));
      return;
    }
    // few() is null past a few visits: replaceChildren would write it as the word "null".
    holder.replaceChildren(...[sankey(flow, {
      label, file, width, unit: "visits", say: words, note,
      tools: controls(redraw),
      onPick: (nd) => open(nd.drill[0], nd.drill[1], { from }),
    }), few(js)].filter(Boolean));
  };
  redraw();
  return holder;
}

/* Narrowed to a few visits (FEW or fewer): each opens in the visitor drawer (visitor.js). */
const FEW = 5;
function few(js) {
  if (!js.length || js.length > FEW) return null;
  return h("div", { class: "jm-tools" }, h("span", { class: "add-l" }, js.length === 1 ? "This visit:" : "These visits:"),
    js.map((j) => h("button", { type: "button", class: "btn", onclick: () => openVisitor(j) },
      `${tzTime(j.start, { date: true, label: false })}, ${shown(j.via || j.source) || "source not recorded"}`)));
}

const span = (days) => (!days.length ? "" : days.length === 1 ? short(days[0]) : `${short(days[0])} to ${short(days[days.length - 1])}`);

/* Traffic > Visitors: the range's journeys, through the global filters, as Each visit lists them. */
export function visitorFlow(m, s, r) {
  const kept = keptFor(m, r);
  const js = kept.journeys.filter(journeyFilter(s));
  // Like "Each visit": visits are kept fewer days than a long period, so the flow's own days are said beside its title.
  const days = [...kept.days].sort();
  const own = r.kind !== "today" && days.length && days.length < (r.days || []).length
    ? h("span", { class: "own-period", title: `Visits are kept ${m.journey_days || 7} days: the period above is longer` },
      `${short(days[0])} to ${short(days[days.length - 1])} · its own period`) : null;
  const sec = h("section", { class: "s vs-card sk-sec", "aria-labelledby": "vf-h" }, h("div", { class: "vs-card-h" }, h("h3", { id: "vf-h" }, "Visitor flow", own ? " " : null, own),
    h("p", { class: "sub" }, "Where visits came from, the pages they read in order, and when they left. Band width is visits. Hover or focus a bar for its figures; select it to open its visits.")));
  if (!kept.days.length) {
    sec.append(h("p", { class: "empty" }, r.kind === "today" ? "Today's visits are not all kept yet, so no flow is drawn."
      : `No day of this range has its visits kept: they are kept ${m.journey_days || 7} days. Choose Today or 7 days.`));
    return sec;
  }
  if (!js.length) { sec.append(h("p", { class: "empty" }, "No visit matches these filters.")); return sec; }
  const wide = r.kind !== "today" && kept.days.length < (r.days || []).length;
  const note = [`${n(js.length)} visit${js.length === 1 ? "" : "s"} ${r.kind === "today" ? "today so far" : `on ${span(kept.days)}`}${wide ? `, the ${kept.days.length} day${kept.days.length === 1 ? "" : "s"} of this range whose visits are kept (the lists above cover every verified day)` : ""}.`,
    kept.short.length ? ` Left out: ${kept.short.join(", ")}, whose visits are only partly kept.` : "",
    ` ${RULE}`].join("");
  sec.append(flowBlock(js, { label: "Visitor flow", file: fileName("visitor-flow", r), note }));
  return sec;
}

/* The drill drawer: the same visits as "The visits behind it". */
export function drillFlow(js, chain, width) {
  const who = chain.map(([d, v]) => (d === "country" ? country(v) : d === "city" ? city(v) : shown(v))).join(", ");
  return h("div", { class: "sk-drill" }, h("h3", null, "How these visitors moved"),
    h("p", { class: "sub" }, `The same ${n(js.length)} visit${js.length === 1 ? "" : "s"} (${who}): where they came from, their pages in order, and when they left. Click a page or source to narrow further.`),
    flowBlock(js, { label: `How visitors from ${who} moved`, file: "visitor-flow-drill.csv", from: "drill", width, note: RULE }));
}
