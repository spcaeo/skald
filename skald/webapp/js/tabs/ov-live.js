// Overview > Summary's links to the full lists. The Live mode panels that lived
// here (Right now, today's leads and bookings, "+N this hour") gave way in 2.13
// to the approved Live layout (ov-today.js), where each answer has one place:
// the newest visits, what converted today and AI & bots today.

import { h } from "../ui.js";
import * as S from "../state.js";

/* A link to another section's tab, keeping the period, page group and filters
   (so in Live mode it opens that tab in Live mode too). */
export function goTo(route, words, extra = {}) {
  const s = S.read();
  return h("a", { class: "ov-go", href: S.hashFor({ ...s, ...extra, tab: route, dd: "" }) }, words, h("span", { "aria-hidden": "true" }, " →"));
}
