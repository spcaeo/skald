// Overview > Insights (#5, #6, the owner's rule of 2026-11-09): only the issues that have a
// problem, nothing else: the to-dos still open and the fixes that failed, three plain lines
// each, and one small link to the fixes being checked (js/tabs/todos.js). Until 2.45 this
// tab also listed "What changed" (insights.json, js/insight-rank.js); its figures stay on
// the tabs they come from.

import { h } from "../ui.js";
import { todoSection } from "./todos.js";

export default function insights(m, s) {
  return [h("div", { class: "head" }, h("h1", null, "Insights")), todoSection(m, s)];
}
