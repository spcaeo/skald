// Overview's "From your tools" card (docs/TOOLS.md): one line per tool connected with the
// person's own key (Google Analytics...), its key figures, the tool's own period, what the
// tool said about its answer (sampled, thresholded) and how fresh it is. Every figure is
// labelled "Counted from: <tool>": these are the tool's counts, never Skald's, and never added
// to Skald's own. A figure the tool did not give says "Not given", never 0. None connected: one
// quiet line with how to connect one (2.43, js/ui/connect.js). GET integrations/yourtools/figures
// (any member; yourtools/api.py view).

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

/* One tool's line: its name and "Counted from", its key figures, its period and freshness. */
export function toolLine(t) {
  const figs = t.withheld ? [h("span", { class: "msg err" }, t.withheld)]
    : (t.headline || []).map((f) => h("span", { class: "yt-fig" }, h("small", null, f.label), withCopy(h("b", null, num(f.value)), f.value == null ? "" : String(f.value), { label: `${t.name} ${f.label}` })));
  const flags = Object.values(t.reports || {}).flatMap((r) => r.flags || []);
  const period = t.period ? `Its own ${t.period.start} to ${t.period.end}${t.period.note ? ` (${t.period.note})` : ""}` : "No answer kept yet";
  return h("li", { class: "yt-line", "data-tool": t.id },
    h("div", { class: "yt-name" }, h("b", null, t.name), h("small", { class: "yt-from" }, t.counted_from)),
    h("div", { class: "yt-figs" }, ...figs),
    h("div", { class: "yt-meta" }, pill(t.pill, t.words), h("small", null, ` Last answer ${t.ago}. ${period}.`),
      flags.length ? h("small", { class: "yt-flags" }, ` As ${t.name} said: ${[...new Set(flags)].join("; ")}.`) : null));
}

/* The card, filled once the figures come; nothing in the demo or without accounts. */
export function toolsCard(m = null) {
  if (DEMO.on) return null;                 // without accounts the helper answers 404: no card
  const box = h("section", { class: "s yt-card", "aria-label": "From your tools" });
  call(FIGURES_PATH).then((r) => {
    const tools = (r.ok && r.tools) || [];
    if (!r.ok) { box.remove(); return; }
    const title = h("div", { class: "card-h" }, h("h2", null, "From your tools"),
      help("From your tools", { text: "Figures from your own tools, read with your own keys. They are each tool's own counts, over the tool's own days, kept apart from Skald's: never added to them.", guide: "your-tools" }),
      sourceLink("tools"));
    if (!tools.length) {
      // 2.43: one quiet line with how to connect one (js/ui/connect.js): the GA4 tag the site
      // check found, else any tool; a viewer reads "Ask an admin to connect it".
      box.replaceChildren(connectCard(m || { site: "" }, "tools", { mode: "line", title: "From your tools: none connected",
        line: "Google Analytics and your other tools can show their own figures here, never mixed into Skald's." }));
      return;
    }
    box.replaceChildren(title, h("p", { class: "sub yt-sub" }, `Skald's figures on this page: ${LOG_LABEL}. Below: each tool's own, never added to them.`),
      h("div", { class: "sheet" }, h("ul", { class: "yt-lines" }, tools.map(toolLine))));
  });
  return box;
}
