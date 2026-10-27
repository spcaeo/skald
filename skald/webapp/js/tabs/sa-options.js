// Leads & sales (2.7.0, laid out again in 2.20): every tab has the same shape, top to bottom:
//
//   tabHead(title, question, r, help)   the title, the question the tab answers (its
//                                       subtitle, in plain words), an (i) with Learn more,
//                                       and the period line (the period itself is chosen
//                                       once, in the top bar)
//   optionsRow(label, controls, opts)   at most one row of the filters that matter for that
//                                       question; the rest folded under "More"; the view
//                                       switcher, when the tab has views, at its right end
//   a number row (optional), the main table or chart, and small notes at the bottom
//
// Each control is kept in the address by the tab's `keep` list (s-sales.js), so a link or
// a reload brings back the same view:
//
//   #sales/leads?lact=demo&lnow=won&lview=board
//
//   choice(name, value, [[key, words, title]], pick)   one of a few (segmented buttons)
//   select(name, value, [[key, words]], pick, {off})  one of many; off: why it does not apply
//   toggles(name, list, [[key, words]], pick)          on/off buttons, any number on
//
// A control that does not apply stays in its place, greyed, with the reason on hover and
// to a screen reader (never silently ignored).

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { head, context } from "./common.js";
import { info } from "./tiles.js";
import { leadsOn } from "./leadfigs.js";
import { sourceLink } from "../ui/connect.js";

/* Today so far, beside a period that ends before today (2.23). Leads & sales opens on whole
   days (7 days, All time), so a lead that came in today is not in its figures: this one line
   says how many there are, with a button to Today (live). N is the live Leads figure, the same
   as Overview's Leads tile today (leadsOn over today: every lead, before this page's filters).
   It is never added to the period's own figure: verified days and today's live part do not mix.
   No line when today has no lead, or when the figure for today is not there. */
export function todayNote(m, s, r) {
  if (!m || !s || !r || r.kind === "today" || !(r.last < m.today)) return null;
  const got = leadsOn(m, [m.today]);
  if (!got || !got.ok || !got.leads) return null;
  return h("p", { class: "sa-today", role: "status", title: "Today's leads so far, the live Leads figure (the same as Overview's Leads tile today), every lead before this page's filters. Not in the period's figures above, which count whole days." },
    "Today so far: ", h("b", null, `${n(got.leads)} new lead${got.leads === 1 ? "" : "s"}`), " ",
    h("button", { type: "button", class: "linkish sa-today-go", onclick: () => S.set({ range: "today" }) }, "Show today (live)", h("span", { "aria-hidden": "true" }, " →")));
}

let seq = 0;
const uid = (p) => `${p}-${++seq}`;

/* The tab's head: its title, the question it answers, an (i) with the longer words and a
   Learn more link into the guide, and the period line (common.js head). source: the group in
   Settings › Leads & tools that feeds this tab (2.43): its "Sources" link, for an admin. */
export function tabHead(title, question, r, { help = "", more = "", period, source = "" } = {}) {
  const top = head(title, r, null, { banner: false, period });
  const bar = top[0];
  if (help) bar.insertBefore(info(help, title, more), bar.querySelector(".period"));
  const back = source ? sourceLink(source) : null;
  if (back) bar.insertBefore(back, bar.querySelector(".period"));
  // Leads & sales only (Security draws its heads here too); a tab with a period of its own
  // (Find a person) has no "Today so far" line.
  const { m, s } = context();
  const today = !period && S.sectionOf(s?.tab)?.key === "sales" ? todayNote(m, s, r) : null;
  return [bar, question ? h("p", { class: "lede sa-q" }, question) : null, today].filter(Boolean);
}

/* One options row. opts: {more: [controls] folded under "More", end: a node at the right
   end (the view switcher), notes: [words] said behind an (i) at the row's end, help: a
   Learn more address for them}. */
export function optionsRow(label, controls, { more = [], end = null, notes = [], help = "" } = {}) {
  const extra = more.filter(Boolean);
  const words = notes.filter(Boolean);
  const fold = extra.length ? h("details", { class: "sa-more" }, h("summary", null, "More"), h("div", { class: "sa-more-body" }, extra)) : null;
  const row = h("div", { class: "sa-opts", role: "group", "aria-label": label }, controls.filter(Boolean), fold,
    words.length ? h("span", { class: "sa-why" }, info(words.join(" "), label, help)) : null,
    end ? h("span", { class: "sa-end" }, end) : null);
  return [h("div", { class: "sa-block" }, row)];
}

export function choice(name, value, options, pick) {
  const id = uid("sa-l");
  return h("div", { class: "sa-opt" }, h("span", { class: "sa-opt-l", id }, name),
    h("div", { class: "sa-seg", role: "group", "aria-labelledby": id }, options.map(([k, words, title]) =>
      h("button", { type: "button", "aria-pressed": String(k === value), title: title || null, onclick: () => { if (k !== value) pick(k); } }, words))));
}

export function select(name, value, options, pick, { off = "", all = "All" } = {}) {
  const id = uid("sa-s");
  const known = options.some(([k]) => k === value);
  const sel = h("select", { id, disabled: !!off, title: off || null, "aria-describedby": off ? `${id}-why` : null },
    all == null ? null : h("option", { value: "" }, all),
    value && !known ? h("option", { value, selected: true }, value) : null,
    options.map(([k, words]) => h("option", { value: k, selected: k === value }, words)));
  sel.addEventListener("change", () => pick(sel.value));
  return h("div", { class: `sa-opt${off ? " off" : ""}` }, h("label", { class: "sa-opt-l", for: id }, name), sel,
    off ? h("span", { class: "vh", id: `${id}-why` }, off) : null);
}

// Toggles: `on` is the list of keys switched on; pick gets the new list.
export function toggles(name, on, options, pick) {
  const id = uid("sa-t");
  return h("div", { class: "sa-opt" }, h("span", { class: "sa-opt-l", id }, name),
    h("div", { class: "sa-togs", role: "group", "aria-labelledby": id }, options.map(([k, words]) => {
      const pressed = on.includes(k);
      return h("button", { type: "button", class: "sa-tog", "aria-pressed": String(pressed),
        onclick: () => pick(pressed ? on.filter((x) => x !== k) : [...on, k]) }, words);
    })));
}

// A comma list kept in one address key ("spam,test"), only the known keys.
export const listOf = (v, known) => String(v || "").split(",").filter((k) => known.includes(k));

/* An empty state, the same on every tab: one line on what is missing and one button (or
   link) that fixes it. action: [words, onclick] or [words, href]. */
export function emptyState(words, action = null, { bad = false } = {}) {
  const [label, go] = action || [];
  const btn = !action ? null : typeof go === "string" ? h("a", { class: "btn", href: go }, label) : h("button", { type: "button", class: "btn primary", onclick: go }, label);
  return h("div", { class: `sa-empty${bad ? " bad" : ""}`, role: bad ? "alert" : "status" }, h("p", null, words), btn);
}

/* Long notes inside the parts a tab draws (renderers older than the redesign) go behind
   an (i) beside the part's heading: the page keeps its headings, figures and tables, and
   the explanations are one press away. A note that says something is missing or withheld
   (.state) stays in place. */
export function foldNotes(nodes, { min = 140 } = {}) {
  for (const el of nodes) {
    if (!el?.querySelectorAll) continue;
    const top = el.querySelector("h2, summary");
    if (!top) continue;
    const said = [];
    for (const p of [...el.querySelectorAll("p.note, p.sub")]) {
      const t = (p.textContent || "").trim();
      if (t.length >= min) { said.push(t); p.remove(); }
    }
    if (said.length) top.append(" ", info(said.join(" "), (top.firstChild?.textContent || "About this").trim()));
  }
  return nodes;
}
