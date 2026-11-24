// Overview's "From your tools" card (docs/TOOLS.md): one line per tool connected with the
// person's own key (Google Analytics...), its key figures, the tool's own period, what the
// tool said about its answer (sampled, thresholded) and how fresh it is. Every figure is
// labelled "Counted from: <tool>": these are the tool's counts, never Skald's, and never added
// to Skald's own. A figure the tool did not give says "Not given", never 0. None connected: one
// quiet line with how to connect one (2.43, js/ui/connect.js). GET integrations/yourtools/figures
// (any member; yourtools/api.py view).
//
// SKALD-55: on Overview › Today too (ov-today.js, { today: true }: each tool's own days, said
// so, since they are never today's). A figure with a unit reads as the tool means it (a share
// as 56.8%, seconds as 1m 34s, names.TOOL_UNITS); with the tool's "previous" report each
// figure says its change against the days before. "All figures from <tool>" opens the drawer
// with every table the tool gave (ov-tools-drawer.js, ytool=<id> in the address).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { pill } from "../ui/pill.js";
import { help } from "../ui/help.js";
import { connectCard, sourceLink } from "../ui/connect.js";
import { DEMO } from "../demo.js";
import { withCopy } from "../urlactions.js";

export const FIGURES_PATH = "integrations/yourtools/figures";
// Skald's own figures, beside a tool's (yourtools/names.py COUNTED_FROM, LOG_SOURCE).
export const LOG_LABEL = "Counted from: your server log";
const num = (v) => (v == null ? "Not given" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 }));

/* A tool's figure as the tool means it (yourtools/api.py shown(), the same words in the mail):
   a share as a percent, seconds as minutes and seconds, a count with its commas. */
export function said(v, unit) {
  if (v == null) return "Not given";
  if (unit === "share") return `${(v * 100).toFixed(1)}%`;
  if (unit === "seconds") { const s = Math.round(v); return s >= 60 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s` : `${s}s`; }
  return num(v);
}

/* The change against the days before: a share in points (56.8% from 54.4% is +2.4 pts), any
   other figure in percent. None when either side is not given, or there was nothing before. */
export function change(now, before, unit) {
  if (now == null || before == null) return null;
  if (unit === "share") {
    const d = (now - before) * 100;
    return { dir: Math.abs(d) < 0.05 ? "flat" : d > 0 ? "up" : "down", text: `${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d).toFixed(1)} pts` };
  }
  if (!before) return null;
  const p = ((now - before) / Math.abs(before)) * 100, a = Math.abs(p);
  return { dir: a < 0.5 ? "flat" : p > 0 ? "up" : "down", text: `${p > 0 ? "+" : p < 0 ? "−" : ""}${a === 0 ? 0 : a < 10 ? a.toFixed(1) : Math.round(a)}%` };
}

/* Any table beyond the headline: worth the drawer. */
export const hasMore = (t) => Object.entries(t.reports || {}).some(([k, r]) => k !== "totals" && (r.figures || []).length);

function figure(t, f) {
  const was = t.before ? t.before[f.name] : null;
  const c = change(f.value, was, f.unit);
  const then = t.before_period ? `${t.before_period.start} to ${t.before_period.end}` : "the days before";
  return h("span", { class: "yt-fig" }, h("small", null, f.label),
    withCopy(h("b", null, said(f.value, f.unit)), f.value == null ? "" : String(f.value), { label: `${t.name} ${f.label}` }),
    c ? h("span", { class: `yt-chg ${c.dir}`, title: `${f.label}: ${said(was, f.unit)} in ${then}, the tool's own days before these` }, c.dir === "up" ? "▲ " : c.dir === "down" ? "▼ " : "", c.text) : null);
}

/* One tool's line: its name and "Counted from", its key figures, its period and freshness. */
export function toolLine(t) {
  const figs = t.withheld ? [h("span", { class: "msg err" }, t.withheld)]
    : (t.headline || []).map((f) => figure(t, f));
  const flags = Object.values(t.reports || {}).flatMap((r) => r.flags || []);
  const period = t.period ? `Its own ${t.period.start} to ${t.period.end}${t.period.note ? ` (${t.period.note})` : ""}` : "No answer kept yet";
  return h("li", { class: "yt-line", "data-tool": t.id },
    h("div", { class: "yt-name" }, h("b", null, t.name), h("small", { class: "yt-from" }, t.counted_from)),
    h("div", { class: "yt-figs" }, ...figs),
    h("div", { class: "yt-meta" }, pill(t.pill, t.words), h("small", null, ` Last answer ${t.ago}. ${period}.`),
      t.before_period && !t.withheld ? h("small", { class: "yt-vs" }, ` Changes: against its own ${t.before_period.start} to ${t.before_period.end}.`) : null,
      flags.length ? h("small", { class: "yt-flags" }, ` As ${t.name} said: ${[...new Set(flags)].join("; ")}.`) : null,
      !t.withheld && hasMore(t) ? h("button", { type: "button", class: "btn yt-open", "data-tool": t.id, onclick: async () => (await import("./ov-tools-drawer.js")).openToolFigures(t) }, `All figures from ${t.name}`) : null));
}

/* The card, filled once the figures come; nothing in the demo or without accounts. */
export function toolsCard(m = null, { today = false } = {}) {
  if (DEMO.on) return null;                 // without accounts the helper answers 404: no card
  const box = h("section", { class: "s yt-card", "aria-label": "From your tools" });
  call(FIGURES_PATH).then((r) => {
    const tools = (r.ok && r.tools) || [];
    if (!r.ok) { box.remove(); return; }
    const q = () => help("From your tools", { text: "Figures from your own tools, read with your own keys. They are each tool's own counts, over the tool's own days, kept apart from Skald's: never added to them.", guide: "your-tools" });
    // The "?" beside the title, the link at the end (the page's card heads: .grow between).
    const title = h("div", { class: "card-h" }, h("h2", null, "From your tools"), q(), h("span", { class: "grow" }), sourceLink("tools"));
    if (!tools.length) {
      // 2.43: one quiet line with how to connect one (js/ui/connect.js): the GA4 tag the site
      // check found, else any tool; a viewer reads "Ask an admin to connect it".
      box.replaceChildren(connectCard(m || { site: "" }, "tools", { mode: "line", title: "From your tools: none connected",
        line: "Google Analytics and your other tools can show their own figures here, never mixed into Skald's." }));
      return;
    }
    const lines = h("ul", { class: "yt-lines" }, tools.map(toolLine));
    if (today) {
      // Today: one card as Today's others (ov-today-bits.js cardHead's look: td-card, td-h).
      box.className = "td-card yt-card yt-today";
      box.setAttribute("aria-labelledby", "td-tools-h");
      box.replaceChildren(h("div", { class: "td-h" },
        h("div", null, h("div", { class: "yt-t" }, h("h2", { id: "td-tools-h" }, "From your tools"), q()),
          h("p", { class: "td-sub" }, `Each tool's own days, shown on its line, never today's; never added to Skald's figures (${LOG_LABEL.toLowerCase()}).`)),
        sourceLink("tools")), lines);
      return;
    }
    box.replaceChildren(title, h("p", { class: "sub yt-sub" }, `Skald's figures on this page: ${LOG_LABEL}. Below: each tool's own, never added to them.`),
      h("div", { class: "sheet" }, lines));
  });
  return box;
}
