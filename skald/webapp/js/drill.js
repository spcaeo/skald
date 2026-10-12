// Drill-down: any value in any list, table or chart opens a detail view for
// it, and a value in that view narrows it further (country, then a page,
// then a source...). The trail lives in the URL hash as `dd`, so a step can
// be bookmarked, shared, or undone with the browser's Back button.
//
//   #audience?range=30d&dd=country:CA|path:/pricing/

import { h } from "./ui.js";
import * as S from "./state.js";
import { mark } from "./icons.js";
import { country, flagEl, withFlag } from "./tabs/readers.js";

// The values a step can be about, and how each is said.
export const DIMS = {
  country: { name: "Country", say: (v) => country(v) },
  path: { name: "Page", say: (v) => v },
  landing: { name: "Landing page", say: (v) => v },
  source: { name: "Source", say: (v) => v },
  assistant: { name: "AI assistant", say: (v) => v },
  referrer: { name: "Referring site", say: (v) => v },
  campaign: { name: "Campaign", say: (v) => v },
  device: { name: "Device", say: (v) => v },
  browser: { name: "Browser", say: (v) => v },
  os: { name: "System", say: (v) => v },
  hour: { name: "Hour", say: (v) => `${v}:00 to ${String((Number(v) + 1) % 24).padStart(2, "0")}:00` },
  ip: { name: "Address", say: (v) => v },
  status: { name: "Status", say: (v) => v },
  bot: { name: "Bot or crawler", say: (v) => v },
};

// The same as plain text, for a crumb, a title or a sentence: a country with its flag.
export const said = (dim, v) => (dim === "country" ? withFlag(v, country(v)) : DIMS[dim].say(v));

export function chainOf(s) {
  if (!s.dd) return [];
  return s.dd.split("|").map((part) => {
    const i = part.indexOf(":");
    let value = part.slice(i + 1);
    try { value = decodeURIComponent(value); } catch { /* a hand-typed "%": keep it as typed */ }
    const dim = part.slice(0, i);
    return DIMS[dim] && value ? [dim, value] : null;
  }).filter(Boolean);
}
// Only "%" and "|" are escaped in a value: the hash stays readable (dd=country:CA|path:/pricing/).
export const encode = (chain) => chain.map(([d, v]) => `${d}:${String(v).replace(/%/g, "%25").replace(/\|/g, "%7C")}`).join("|");

// Open a value: from the detail view it narrows the trail; elsewhere it starts one.
export function open(dim, value, { from = null } = {}) {
  const s = S.read();
  const base = from === "drill" ? chainOf(s) : [];
  const chain = [...base.filter(([d]) => d !== dim), [dim, String(value)]];
  S.set({ dd: encode(chain) });
}

// What a value looks like anywhere: its mark (or flag) and its words.
export function label(dim, value, text) {
  const words = text ?? DIMS[dim]?.say(value) ?? value;
  if (dim === "country") return h("span", { class: "named" }, flagEl(value), h("span", { class: "nm" }, words));
  return h("span", { class: "named" }, mark(dim, value), h("span", { class: "nm" }, words));
}

/* The clickable form: a button that opens the value's detail. `from`
   "drill" keeps the trail (used inside the detail view). Values that are
   folded tails or absences are not drillable. */
export function link(dim, value, { text, from, bare = false } = {}) {
  const v = String(value ?? "");
  const words = () => (bare ? h("span", { class: "nm" }, text ?? v) : label(dim, v, text));
  if (!DIMS[dim] || !v || /^\((none|all others|this site|no campaign tag)\)$/.test(v) || v === "Unknown" && dim !== "country") return words();
  // bare: the words only, where a mark is already drawn beside them.
  const b = h("button", { type: "button", class: "dl", title: `Open ${DIMS[dim].name.toLowerCase()} ${DIMS[dim].say(v)}` }, words());
  b.addEventListener("click", (e) => { e.stopPropagation(); open(dim, v, { from }); });
  return b;
}
