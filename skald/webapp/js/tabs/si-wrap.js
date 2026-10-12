// Site > Speed and Site > Alerts (2.7.0): today's pages (speed.js, alerts.js),
// drawn as they are, with one link each to where a shared figure now lives
// (docs/plans/2026-10-12-ui-consolidation-map.md):
//   D17  Speed's "Server answer time" is the same figure as Health's "Typical
//        answer time": the tile stays and says so, with a link to Health
//   D21  AI reading changes (the alerts' AI filter) have their own panel on
//        AI & bots > Assistants: a line links there

import { h } from "../ui.js";
import * as S from "../state.js";
import speedPage from "./speed.js";
import alertsPage from "./alerts.js";

const nodes = (out) => [out].flat(Infinity).filter((x) => x instanceof Node);

export function speed(m, s, o) {
  const out = speedPage(m, s, o);
  for (const el of nodes(out)) {
    for (const k of el.querySelectorAll?.(".kpi") || []) {
      if (k.querySelector(".k-l")?.textContent !== "Server answer time") continue;
      k.querySelector(".k-c")?.append(h("a", { class: "si-more", href: S.hashFor({ ...s, tab: "site/health" }) }, "The same figure as Health"));
    }
  }
  return out;
}

export function alerts(m, s, o) {
  const out = alertsPage(m, s, o);
  if (!m.x.alerts) return out;
  return [out, h("p", { class: "note si-also" }, "AI assistants starting or stopping reading a page also show, page by page, on ",
    h("a", { href: S.hashFor({ ...s, tab: "ai/assistants" }) }, "AI & bots > Assistants"), ".")];
}
