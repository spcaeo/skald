// Leads & sales (2.7.0): the options row above a tab's figures. One row of
// labelled controls, each kept in the address by the tab's `keep` list
// (s-sales.js), so a link or a reload brings back the same view:
//
//   #sales/pipeline?lsrc=all&lact=demo&lshow=cancelled,removed
//
//   optionsRow(label, [controls], ...notes)    the row, then its notes
//   choice(name, value, [[key, words]], pick)  one of a few (segmented buttons)
//   select(name, value, [[key, words]], pick, {off})  one of many; off: why it does not apply
//   toggles(name, list, [[key, words]], pick)  on/off buttons, any number on
//   period(s, m)                               the period, the same as the bar's
//
// A control that does not apply to the chosen file stays in its place, greyed,
// with the reason on hover and to a screen reader (never silently ignored).

import { h } from "../ui.js";
import * as S from "../state.js";
import { rangeOf } from "../data.js";

let seq = 0;
const uid = (p) => `${p}-${++seq}`;

export function optionsRow(label, controls, ...notes) {
  return [h("div", { class: "sa-block" }, h("div", { class: "sa-opts", role: "group", "aria-label": label }, controls.filter(Boolean)),
    ...notes.filter(Boolean).map((x) => (x instanceof Node ? x : h("p", { class: "note sa-says" }, x))))];
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

// The period, the same choice as the top bar's (one state: changing either changes both).
export function period(s, m) {
  return select("Period", s.range, S.RANGES, (k) => {
    if (k === "custom") { const r = rangeOf(m, s); S.set({ range: "custom", from: r.first, to: r.last }); } else S.set({ range: k });
  }, { all: null });
}
