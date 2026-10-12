// Traffic > Visitors (2.7.0): what a visit looked like. visits.js draws the tab;
// this file takes out what has one place elsewhere now:
//   * "Visits that read a page" and "Pages per visit": Overview's tiles hold them
//     (the map's D1); the bars "Pages per visit" below stay
//   * "Where visits started" and "Entry pages": landing pages live on Traffic > Pages
//     (the map's D9), so a line links there instead
// Nothing is recounted: every figure left is visits.js's own.

import * as S from "../state.js";
import visits from "./visits.js";
import { goTo } from "./tr-grid.js";

const ON_OVERVIEW = new Set(["Visits that read a page", "Pages per visit"]);
const textOf = (el, sel) => el.querySelector(sel)?.textContent.trim();

export default function visitors(m, s, o) {
  const pages = S.hashFor({ ...s, tab: "traffic/pages", dd: "" });
  return visits(m, s, o).flatMap((node) => {
    if (!(node instanceof Element)) return [node];
    // The tiles: the two Overview holds are dropped.
    for (const k of node.querySelectorAll(".kpis > .kpi")) if (ON_OVERVIEW.has(textOf(k, ".k-l"))) k.remove();
    // Where visits started: dropped from the row of three, with a line to the landing pages under it.
    if (node.matches(".cols.three")) {
      const start = [...node.children].find((c) => textOf(c, "h3") === "Where visits started");
      if (start) {
        start.remove();
        node.classList.remove("three");
        return [node, goTo(pages, "Where visits started: the landing pages, with their leads, are on", "Traffic › Pages")];
      }
    }
    // Entry pages: the same list as the landing pages; dropped.
    return node.matches("section.s") && textOf(node, ":scope > h2") === "Entry pages" ? [] : [node];
  });
}
