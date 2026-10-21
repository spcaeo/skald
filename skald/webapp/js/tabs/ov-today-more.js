// Overview > Summary in Live mode, rows (c) to (f): where today's visitors came
// from, how today's visits moved, what converted today, and AI & bots today.
// Every figure is one the page already holds for today, from the same field:
//   sources     the live count's readers by source (by.source, adds up to the
//               visitors); an AI assistant's own rows from today's journeys,
//               only when every visit of today is kept (flow.keptFor)
//   flow        flow.js over the same journeys, two pages deep (sankey.js)
//   converted   conversions.json today: the finished forms and bookings,
//               the same rows the Leads tile counts (leadfigs.js)
//   AI & bots   the live count's AI fetches by tier, visitors sent by AI,
//               search crawlers, other bots and our own (the "who else came" row)

import { h, n, share } from "../ui.js";
import { open as openDrill, link } from "../drill.js";
import { mark } from "../icons.js";
import { shown, assistantName } from "../labels.js";
import { flowOf, check, keptFor, OTHER, OTHER_SOURCES } from "../flow.js";
import { sankey } from "../sankey.js";
import { flagEl, country, countryName } from "./readers.js";
import { convFile, leadsOn, oneAction } from "./leadfigs.js";
import { time as tzTime } from "../tz.js";
import { goLink, cardHead } from "./ov-today-bits.js";
import { subView } from "../tablestate.js";
import { withUrl } from "../urlactions.js";

const pick = { sort: "visitors" };
// The sources' order stays in the address (tsrc_view=name: tablestate.js subView).
const SORT = subView("tsrc");
const todayJourneys = (m) => keptFor(m, { kind: "today" }).journeys;

// ------------------------------------------------------------- sources
export function sourcesCard(m, t) {
  const box = h("div", { class: "td-src", role: "table", "aria-label": "Visitors today by where they came from" });
  const seg = h("div", { class: "seg plain td-sort", role: "group", "aria-label": "Sort sources" });
  const el = h("section", { class: "td-card", "aria-labelledby": "td-src-h" },
    cardHead("td-src-h", "Where today's visitors came from", "Visitors today so far, by the source of their first page.", goLink("traffic/sources", "Traffic › Sources")), seg, box);
  const all = Object.entries(t.by?.source || {}).filter(([, v]) => v > 0);
  const total = t.readers ?? all.reduce((a, [, v]) => a + v, 0);
  // An AI assistant's own rows: today's kept journeys sent by one (they add up to the row).
  const js = todayJourneys(m);
  const ai = {};
  for (const j of js) if (j.source === "AI assistant" && j.via) ai[j.via] = (ai[j.via] || 0) + 1;
  const aiRows = Object.entries(ai).sort((a, b) => b[1] - a[1]);
  const aiWhole = js.length && aiRows.reduce((a, [, v]) => a + v, 0) === (t.by?.source?.["AI assistant"] || 0);
  const most = Math.max(1, ...all.map(([, v]) => v));
  pick.sort = SORT.get() === "name" ? "name" : "visitors";
  const draw = () => {
    const rows = [...all].sort(pick.sort === "name" ? (a, b) => shown(a[0]).localeCompare(shown(b[0])) : (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    seg.replaceChildren(...[["visitors", "Most visitors"], ["name", "Name"]].map(([k, w]) =>
      h("button", { type: "button", "aria-pressed": String(pick.sort === k), onclick: () => { pick.sort = k; SORT.set(k, "visitors"); draw(); } }, w)));
    const line = (cls, name, v, sh, bar, colour) => h("div", { class: cls, role: "row" },
      h("span", { role: "cell", class: "td-sn" }, h("i", { class: "td-sbar", style: { width: `${bar}%`, background: colour }, "aria-hidden": "true" }), name),
      h("span", { role: "cell", class: "td-num" }, n(v)), h("span", { role: "cell", class: "td-num td-sh" }, sh));
    box.replaceChildren(h("div", { class: "td-sr td-shd", role: "row" }, h("span", { role: "columnheader" }, "Source"),
      h("span", { role: "columnheader", class: "td-num" }, "Visitors"), h("span", { role: "columnheader", class: "td-num" }, "Share")),
    ...(rows.length ? rows.flatMap(([k, v]) => [line("td-sr", h("span", { class: "td-snm" }, mark("source", k), link("source", k, { text: shown(k), bare: true })), v, share(v, total) || "-", (v / most) * 100,
      k === "AI assistant" ? "var(--g-answer_engines)" : "var(--g-people)"),
    ...(k === "AI assistant" && aiWhole ? aiRows.map(([via, c]) => line("td-sr sub", h("span", { class: "td-snm" }, link("assistant", via, { text: assistantName(via), bare: true })), c, "", (c / most) * 100, "var(--g-answer_engines)")) : [])])
      : [h("p", { class: "empty" }, "No visitor yet today.")]),
    h("div", { class: "td-sr td-stot", role: "row" }, h("span", { role: "cell" }, "All visitors"), h("span", { role: "cell", class: "td-num" }, n(total)), h("span", { role: "cell" })));
  };
  draw();
  return el;
}

// ------------------------------------------------------------- flow
function words(nd) {
  if (nd.label === OTHER) return "Other pages";
  if (nd.label === OTHER_SOURCES) return "Other sources";
  if (nd.col === 0 && nd.drill?.[0] === "source") return shown(nd.label) || "Not recorded";
  // The last column has little room: its ends in short words (the legend and the table say them in full).
  if (nd.kind === "more") return "More pages";
  if (nd.kind === "left" && nd.col === 3) return `Left after ${String(nd.key).replace("left", "")}`;
  return nd.label;
}

export function flowCard(m) {
  const js = todayJourneys(m);
  const el = h("section", { class: "td-card td-flow", "aria-labelledby": "td-flow-h" },
    cardHead("td-flow-h", "How today's visits moved", "Where each visit came from, its first two pages, then where it left. Band width is visits.", goLink("traffic/visitors", "Full flow")));
  if (!js.length) {
    el.append(h("p", { class: "empty" }, m.live?.figures?.readers ? "Today's visits are not all kept yet, so no flow is drawn." : "No visit yet today."));
    return el;
  }
  const flow = flowOf(js, { depth: 2, top: 4, start: "source" });
  const off = check(flow);
  if (off.length) {
    el.append(h("div", { class: "state bad", role: "alert" }, h("div", null, `The flow is withheld: it does not add up (${off.slice(0, 2).join("; ")}).`)));
    return el;
  }
  const nodes = flow.columns.flatMap((c) => c.nodes);
  const one = nodes.find((nd) => nd.key === "left1")?.value || 0;
  const more = nodes.find((nd) => nd.kind === "more")?.value || 0;
  // Drawn at the card's own width once it is on the page (beside the sources on a wide
  // screen); never under 620, so on a phone the map keeps its room and scrolls sideways.
  const panel = document.getElementById("panel");
  const draw = (width) => sankey(flow, { label: "How today's visits moved", file: "today-flow.csv", width: Math.max(620, width), unit: "visits", say: words,
    onPick: (nd) => nd.drill && openDrill(nd.drill[0], nd.drill[1]) });
  const guess = Math.max(620, Math.round(((panel ? panel.clientWidth : 1000) - 96) * 0.62));
  let map = draw(guess);
  requestAnimationFrame(() => {
    const room = el.isConnected ? el.clientWidth - 38 : 0;
    if (room > 0 && Math.abs(Math.max(620, room) - guess) > 16) { const again = draw(room); map.replaceWith(again); map = again; }
  });
  el.append(map,
  h("p", { class: "td-cap" }, `${n(flow.total)} visit${flow.total === 1 ? "" : "s"} today. ${n(one)} left after their first page; ${n(more)} went on past page 2. Each column folds its smaller pages into Other pages, so every column adds up.`));
  return el;
}

// ------------------------------------------------------------- converted
export function convertedCard(m) {
  const f = convFile(m);
  if (!f) return null;
  const el = h("section", { class: "td-card td-conv", "aria-labelledby": "td-conv-h" });
  const go = goLink("sales/leads", "Leads & sales", {});
  const b = f.today;
  const lf = leadsOn(m, [m.today]);
  if (!b || b.day !== m.today) {
    el.append(cardHead("td-conv-h", "What converted today", "Today's list is written with the next update (every 2 minutes).", go));
    return el;
  }
  if (b.state !== "ok" || !lf?.ok) {
    el.append(cardHead("td-conv-h", "What converted today", null, go),
      h("div", { class: "state bad", role: "alert" }, h("div", null, `Withheld: ${b.why || "the second count disagrees."} None of today's leads are shown or counted until it matches.`)));
    return el;
  }
  const leads = new Set(f.lead_actions || []), demos = new Set(f.demo_actions || ["demo"]), fin = new Set(f.finished || ["completed", "paid"]);
  const rows = (b.rows || []).filter((x) => leads.has(x.action) && fin.has(x.stage) && !x.test);
  const forms = lf.leads - lf.demos;
  const sub = lf.leads ? `${n(lf.leads)} lead${lf.leads === 1 ? "" : "s"}: ${n(forms)} form${forms === 1 ? "" : "s"} sent, ${n(lf.demos)} demo${lf.demos === 1 ? "" : "s"} booked.${rows.length < lf.leads ? ` The latest ${n(rows.length)} are listed.` : ""}`
    : "Forms sent and demos booked today, completed.";
  el.append(cardHead("td-conv-h", "What converted today", sub, go));
  if (!rows.length) { el.append(h("p", { class: "empty" }, "No form sent or demo booked yet today.")); return el; }
  const head = h("div", { class: "td-cr td-shd", role: "row" }, ...["When", "What", "Visitor", "Came from"].map((w) => h("span", { role: "columnheader" }, w)));
  el.append(h("div", { class: "td-cv", role: "table", "aria-label": "Leads today" }, head, ...rows.map((x) => {
    const demo = demos.has(x.action);
    const first = x.first_source && x.first_source !== x.source ? `First came from ${shown(x.first_source)}` : "";
    return h("div", { class: "td-cr", role: "row" },
      h("span", { role: "cell", class: "td-vt" }, tzTime(x.at, { label: false })),
      h("span", { role: "cell" }, h("span", { class: `td-badge${demo ? " demo" : ""}` }, demo ? "Demo booked" : oneAction(x.action)), x.landing ? h("small", { class: "td-mono" }, withUrl(h("span", null, x.landing), x.landing, { cls: "ua-after" })) : null),
      h("span", { role: "cell" }, x.country ? h("span", { class: "td-vc", title: countryName(x.country) }, flagEl(x.country), h("b", null, country(x.country))) : h("span", { class: "muted" }, "Country not recorded"),
        x.device ? h("small", null, x.device) : null),
      h("span", { role: "cell" }, h("b", null, shown(x.source) || "Source not recorded"), first ? h("small", null, first) : null));
  })));
  return el;
}

// ------------------------------------------------------------- AI & bots
const top3 = (obj) => Object.entries(obj || {}).filter(([k, v]) => v > 0 && k !== "(all others)").sort((a, b) => b[1] - a[1]);

export function aiCard(t) {
  const asked = t.tiers?.asked ?? 0, sent = t.cited ?? 0;
  const training = t.tiers?.training ?? 0, search = t.hits?.search_engines ?? 0;
  const crawl = training + search;
  const stat = (colour, label, sub, v, unit) => h("div", { class: "td-ai" },
    h("span", null, h("span", { class: "td-ail" }, h("i", { class: "td-sw sq", style: { background: colour } }), label), h("small", null, sub)),
    h("span", { class: "td-aiv" }, n(v), h("small", null, unit)));
  const readers = top3(t.engines?.asked).slice(0, 3);
  const most = Math.max(1, ...readers.map(([, v]) => v));
  const names = top3({ ...(t.engines?.training || {}), ...(t.search_engines || {}) }).slice(0, 3);
  const others = Math.max(0, crawl - names.reduce((a, [, v]) => a + v, 0));
  const segs = [...names.map(([k, v], i) => [k, v, `var(--td-b${i + 1})`]), ...(others ? [["Others", others, "var(--td-b0)"]] : [])];
  return h("section", { class: "td-card td-aibox", "aria-labelledby": "td-ai-h" },
    cardHead("td-ai-h", "AI & bots today", "Read from the server log. Requests are not people.", goLink("ai/assistants", "AI & bots")),
    h("div", { class: "td-ais" },
      stat("var(--g-answer_engines)", "AI read pages for people", "An assistant fetched a page while answering someone", asked, "fetches"),
      stat("var(--g-people)", "AI sent visitors", "People who clicked through from an answer", sent, "visitors"),
      stat("var(--g-bots)", "Crawler requests", "Search indexing and AI training crawlers, not people", crawl, "requests")),
    readers.length ? h("div", { class: "td-aib" }, h("b", null, "Who read the most pages for people"),
      ...readers.map(([k, v]) => h("div", { class: "td-air" }, link("bot", k, { bare: true }), h("span", { class: "td-pgb", "aria-hidden": "true" }, h("i", { style: { width: `${(v / most) * 100}%`, background: "var(--g-answer_engines)" } })), h("span", { class: "td-num" }, n(v)))))
      : h("p", { class: "empty" }, "No assistant fetched a page for someone yet today."),
    crawl ? h("div", { class: "td-aib" }, h("b", null, "Crawler requests by bot"),
      h("div", { class: "td-stack", "aria-hidden": "true" }, segs.map(([, v, c]) => h("i", { style: { flex: `${v} 1 0`, background: c } }))),
      h("div", { class: "td-lg" }, segs.map(([k, v, c]) => h("span", null, h("i", { class: "td-sw sq", style: { background: c } }), k, " ", h("b", null, n(v)))))) : null,
    h("p", { class: "td-cap" }, `Other bots and scanners: ${n(t.hits?.bots ?? 0)} requests. Our own: ${n(t.hits?.ours ?? 0)} requests. `, goLink("ai/crawlers", "Every crawler: AI & bots › Crawlers")));
}
