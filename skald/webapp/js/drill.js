// Drill-down: any value in any list, table or chart opens a detail view for
// it, and a value in that view narrows it further (country, then a page,
// then a source...). The trail lives in the URL hash as `dd`, so a step can
// be bookmarked, shared, or undone with the browser's Back button.
//
//   #audience?range=30d&dd=country:CA|path:/pricing/

import { h } from "./ui.js";
import { shown, assistantName } from "./labels.js";
import * as S from "./state.js";
import { mark } from "./icons.js";
import { country, countryName, countryWords, flagEl, withFlag, city, cityCode, cityName } from "./tabs/readers.js";

// The values a step can be about, and how each is said.
export const DIMS = {
  country: { name: "Country", say: (v) => country(v) },
  city: { name: "City", say: (v) => city(v) },
  path: { name: "Page", say: shown },
  landing: { name: "Landing page", say: shown },
  source: { name: "Source", say: shown },
  assistant: { name: "AI assistant", say: assistantName },
  referrer: { name: "Referring site", say: assistantName },
  campaign: { name: "Campaign", say: shown },
  device: { name: "Device", say: shown },
  browser: { name: "Browser", say: shown },
  os: { name: "System", say: shown },
  hour: { name: "Hour", say: (v) => `${v}:00 to ${String((Number(v) + 1) % 24).padStart(2, "0")}:00` },
  ip: { name: "Address", say: shown },
  status: { name: "Status", say: shown },
  bot: { name: "Bot or crawler", say: shown },
};

// The same as plain text, for a crumb, a title or a sentence: a country with its flag ("🇺🇸 USA"),
// a city with its country's ("🇨🇦 Toronto, Ontario, CAN"). A tooltip says it whole: titled() ("United States").
export const said = (dim, v) => (dim === "country" ? withFlag(v, country(v)) : dim === "city" ? withFlag(cityCode(v), city(v)) : DIMS[dim].say(v));
export const titled = (dim, v) => (dim === "country" ? countryName(v) : dim === "city" ? cityName(v) : dim === "bot" && fetcherOf(v) ? `${v}, the fetcher ${fetcherOf(v)} sends when a user asks it about a page` : DIMS[dim].say(v));

// A user fetcher (ChatGPT-User, Claude-User, Perplexity-User...) keeps its bot name and says
// what it is: it is not the assistant itself, only what reads a page for one user's question.
export const fetcherOf = (v) => (/^[A-Za-z]+-User$/.test(v || "") ? v.slice(0, -5) : null);

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
  // Each step is one entry in the history, counted, so closing the drawer steps Back
  // out of all of them (close below) and Back then leaves the page as it was.
  const deep = (s.dd && history.state?.drill) || 0;
  S.set({ dd: encode(chain) }, { mark: { drill: deep + 1 } });
}

// Close the drill-down: Back over the steps this page opened, else a new entry without it.
export function close() {
  const steps = history.state?.drill;
  if (steps > 0 && S.read().dd) history.go(-steps);
  else S.set({ dd: "" });
}

// What a value looks like anywhere: its mark (or flag) and its words.
export function label(dim, value, text) {
  const words = text ?? DIMS[dim]?.say(value) ?? value;
  // A country: "🇺🇸 USA" on screen whatever words were passed, its full name in the tooltip and for a screen reader.
  if (dim === "country") return countryWords(value);
  // A city: its country's flag and "Toronto, Ontario, CAN"; the country's full name in the tooltip.
  if (dim === "city") return h("span", { class: "named", title: cityName(value) }, flagEl(cityCode(value)), h("span", { class: "nm" }, words));
  const kind = dim === "bot" && fetcherOf(value) ? [" ", h("small", { class: "nm-kind" }, "user fetcher")] : null;
  return h("span", { class: "named" }, mark(dim, value), h("span", { class: "nm" }, words, kind));
}

/* The clickable form: a button that opens the value's detail. `from`
   "drill" keeps the trail (used inside the detail view). Values that are
   folded tails or absences are not drillable. */
// A value that has a detail: folded tails and absences have none.
export const drillable = (dim, value) => {
  const v = String(value ?? "");
  return !!DIMS[dim] && !!v && !/^\((none|all others|this site|no campaign tag)\)$/.test(v) && !(v === "Unknown" && dim !== "country");
};

export function link(dim, value, { text, from, bare = false } = {}) {
  const v = String(value ?? "");
  const words = () => (bare ? (dim === "country" ? countryWords(v, { flag: false }) : h("span", { class: "nm" }, text ?? v)) : label(dim, v, text));
  if (!drillable(dim, v)) return words();
  // bare: the words only, where a mark is already drawn beside them.
  const b = h("button", { type: "button", class: "dl", title: `Open ${DIMS[dim].name.toLowerCase()} ${titled(dim, v)}` }, words());
  // What it opens, for a whole row around it (drillRow) and for tests.
  b.dataset.dim = dim;
  b.dataset.value = v;
  b.addEventListener("click", (e) => { e.stopPropagation(); open(dim, v, { from }); });
  return b;
}

/* The whole row opens its value (2.13): a table row, a grid row or a bar-list line
   that holds a value's link (above) becomes one target - a click anywhere on it,
   Enter or Space while it has focus - with the same hover, the chevron (features.css
   .drow) and the same drawer. The row's first link names the value: a row's first
   column is what the row is about. Buttons, links and fields inside keep their own
   click. A row that opens something else (a visit: the caller's onRow) is left alone.
   Every table builder calls this (table.js, grid.js, blist in tabs/common.js), so a
   new table gets it for free. Returns the button it opens, or null.
   drillRow(row, open): a row about a visit or a visitor opens the one visitor drawer
   instead (open: () => openVisitor(j), tabs/visitor.js); the values inside it keep
   their own links. */
const INNER = "button,a,input,select,textarea,label,summary,[role=button]";
export function drillRow(row, open = null) {
  if (!row) return null;
  if (open) return visitRow(row, open);
  const b = row.querySelector("button.dl");
  if (row.dataset.drow) return b;
  row.dataset.drow = b ? "1" : "0";
  if (!b) return null;
  row.classList.add("drow");
  row.tabIndex = 0;
  // One stop per row for the keyboard: the row, not the link inside it.
  b.tabIndex = -1;
  // The link is looked up on each use: a grid may draw a row's cells again in place.
  const go = () => row.querySelector("button.dl")?.click();
  wholeRow(row, go);
  return b;
}
function visitRow(row, open) {
  if (row.dataset.drow) return null;
  row.dataset.drow = "visit";
  row.classList.add("vrow");
  row.tabIndex = 0;
  if (!row.title) row.title = "Open this visitor";
  wholeRow(row, open);
  return null;
}
function wholeRow(row, go) {
  row.addEventListener("click", (e) => {
    const inner = e.target.closest?.(INNER);
    if (inner && inner !== row) return;
    if (globalThis.getSelection?.()?.toString()) return;   // selecting text to copy is not a click
    go();
  });
  row.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target === row) { e.preventDefault(); go(); }
  });
}
