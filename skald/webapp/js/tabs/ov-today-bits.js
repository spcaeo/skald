// Small pieces every card of Overview's Live mode (ov-today*.js) shares.

import { h } from "../ui.js";
import * as S from "../state.js";

/* A link to another tab, keeping the period and filters ("Traffic › Places"). */
export const hrefTo = (route, extra = {}) => S.hashFor({ ...S.read(), ...extra, tab: route, dd: "" });
export const goLink = (route, words, extra = {}) => h("a", { class: "td-go", href: hrefTo(route, extra) }, words);

/* A card's head: its title, one line on what it counts, and its link. */
export function cardHead(id, title, sub, go) {
  return h("div", { class: "td-h" }, h("div", null, h("h2", { id }, title), sub ? h("p", { class: "td-sub" }, sub) : null), go);
}
