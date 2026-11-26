// Traffic's shared filter bar (SKALD-62, Palak's approved mock-up, 26 Nov): Country, Source and
// Device, under the tab strip of the four tabs that share it (Visitors, Sources, Pages, Places &
// devices; s-traffic.js `shared`). Each value is a chip with its visits in the period; a chip
// picked is dark with ✕ and sets the address's own filter (country=, source=, device=, state.js),
// so it stays on from tab to tab, a link keeps it, and the top bar's Filters button edits the
// same filters.
//
// The counts follow the other rows' picks: with USA picked, Source and Device count only the
// visits from the USA (narrow.js), and Country counts every country, so another one can be
// picked. With nothing picked in the other rows, a row's counts are the period's own
// breakdown. While a filtered count is on its way a chip shows "…", never a whole-site figure.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { figures, ranked } from "../data.js";
import { shown } from "../labels.js";
import { mark } from "../icons.js";
import { country, countryName, flagEl } from "./readers.js";
import { picksOf, narrow, OTHER } from "../narrow.js";

const ROWS = [["country", "Country", 6], ["source", "Source", 0], ["device", "Device", 0]];
const HIDE = new Set([OTHER, "Unknown", ""]);   // a value nobody can pick: the rest, not recorded
// A pick redraws the page: the control picked takes the focus back in the new bar (data-f).
let refocus = "";
const pickTo = (key, patch) => { refocus = key; S.set(patch); };

function chip(dim, v, count, on) {
  const words = dim === "country" ? country(v) : shown(v);
  const icon = dim === "country" ? flagEl(v) : mark(dim, v);
  const b = h("button", { type: "button", class: "vq-c", "aria-pressed": String(on), "data-v": v, "data-f": `${dim}|${v}` },
    icon, h("span", null, words), h("span", { class: "vq-n" }, count == null ? "…" : n(count)),
    on ? h("span", { class: "tf-x", "aria-hidden": "true" }, "✕") : null);
  const name = dim === "country" ? countryName(v) : words;
  b.setAttribute("aria-label", `${name}${count == null ? "" : `: ${n(count)} visits`}${on ? ", picked: select to remove" : ""}`);
  if (dim === "country") b.title = countryName(v);
  b.addEventListener("click", () => pickTo(`${dim}|${v}`, { [dim]: on ? "" : v }));
  return b;
}

/* A row's chips: the values with visits (the top few countries), the picked one always; for
   the countries, a "More countries" button that opens every other one as chips (`list`). */
function chips(m, s, dim, counts, top, pending, list) {
  const picked = s[dim] || "";
  let vals = ranked(counts || {}, (k) => !HIDE.has(k)).map(([k, v]) => [k, v]);
  if (top) vals = vals.slice(0, top);
  if (picked && !vals.some(([k]) => k === picked)) vals.push([picked, counts ? counts[picked] || 0 : null]);
  const out = vals.map(([k, v]) => chip(dim, k, pending ? null : v, k === picked));
  if (counts === null && !pending) out.push(h("span", { class: "tf-none" }, "not split by the other filters for this period"));
  else if (!vals.length) out.push(h("span", { class: "tf-none" }, "no visits in this period"));
  // More countries than the top ones: every other country this site has seen, A to Z.
  if (dim === "country" && top && list) {
    const rest = (m.options?.country || []).filter((k) => !HIDE.has(k) && !vals.some(([x]) => x === k))
      .sort((a, b) => countryName(a).localeCompare(countryName(b)));
    list.replaceChildren(...rest.map((k) => chip(dim, k, pending ? null : counts?.[k] || 0, false)));
    if (rest.length) {
      const more = h("button", { type: "button", class: "vq-c tf-more", "aria-expanded": String(!list.hidden), "aria-controls": list.id, "data-f": "country|more" },
        `More countries (${rest.length})`);
      more.addEventListener("click", () => { list.hidden = !list.hidden; more.setAttribute("aria-expanded", String(!list.hidden)); });
      out.push(more);
    }
  }
  return out;
}

export function sharedBar(m, s) {
  if (s.tab === "traffic/pages" && s.page) return null;    // a page's story has a period of its own
  const { r, t } = figures(m, s);
  const picks = picksOf(s);
  const rows = h("div", { class: "vq tf-rows" });
  const list = h("div", { class: "vq-g tf-list", id: "tf-more-countries", role: "group", "aria-label": "Every other country" });
  list.hidden = true;
  for (const [dim, title, top] of ROWS) {
    const label = h("span", { class: "vq-l" }, title);
    const row = h("div", { class: "vq-g", role: "group", "aria-label": title });
    rows.append(row);
    if (dim === "country") rows.append(list);
    const fill = (counts, pending) => { row.replaceChildren(label, ...chips(m, s, dim, counts, top, pending, list)); focusBack(rows); };
    const others = picks.filter(([k]) => k !== dim);
    const own = t?.by?.[dim] || {};
    if (!others.length) { fill(own, false); continue; }
    fill(own, true);
    // A filtered count not known (today's visits not yet today's count) is said, never 0.
    narrow(m, s, r, { picks: others }).then((got) => fill(got.a && got.a.readers != null ? got.a.by[dim] : null, false)).catch(() => fill(null, false));
  }
  const words = picks.length
    ? `Showing ${picks.map(([k, v]) => (k === "country" ? countryName(v) : shown(v))).join(", ")} only, on these four tabs. It stays on as you move between them.`
    : "Pick a country, source or device: Visitors, Sources, Pages and Places & devices then show only those visits. It stays on as you move between them.";
  const side = h("div", { class: "tf-side" }, h("p", null, words, " Counts are visits in the period above."),
    picks.length ? h("button", { type: "button", class: "btn", "data-f": "clear", onclick: () => pickTo("country|first", { country: "", source: "", device: "" }) }, "Clear filter") : null);
  const bar = h("section", { class: `tf${picks.length ? " on" : ""}`, "aria-label": "Filter for Visitors, Sources, Pages and Places & devices" },
    h("div", null, h("p", { class: "tf-tag" }, "Filter for Visitors, Sources, Pages and Places & devices"), rows), side);
  focusBack(bar);
  return bar;
}

/* After a pick, the control picked (or, after Clear, the first chip) takes the focus again. */
function focusBack(root) {
  if (!refocus) return;
  const want = refocus;
  setTimeout(() => {
    if (!root.isConnected || refocus !== want) return;
    const el = want === "country|first" ? root.querySelector(".vq-c") : root.querySelector(`[data-f="${globalThis.CSS?.escape ? globalThis.CSS.escape(want) : want}"]`);
    if (el) { el.focus({ preventScroll: true }); refocus = ""; }
  }, 0);
}
