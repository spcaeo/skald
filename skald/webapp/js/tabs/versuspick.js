// The two date ranges of Compare: A (the period looked at, blue) and B (what
// it is compared with, orange). Each opens a popover with presets and a from/to
// calendar. Ranges end on the last whole day; at most 12 months long.

import { h, short, addDays, dayDiff } from "../ui.js";

export const MAX_DAYS = 366;
const parse = (v) => { const m = /^(\d{4}-\d\d-\d\d)\.\.(\d{4}-\d\d-\d\d)$/.exec(v || ""); return m && m[1] <= m[2] ? { first: m[1], last: m[2] } : null; };
export const fmt = (r) => `${r.first}..${r.last}`;
export const length = (r) => dayDiff(r.first, r.last) + 1;

// Keep a range inside history's reach: never past the last whole day, never longer than 12 months.
export function clamp(r, anchor) {
  let { first, last } = r;
  if (last > anchor) last = anchor;
  if (first > last) first = last;
  if (dayDiff(first, last) + 1 > MAX_DAYS) first = addDays(last, -(MAX_DAYS - 1));
  return { first, last };
}

// The two ranges from the link, or: A the last 30 whole days, B the 30 before.
export function ranges(s, anchor) {
  const a = clamp(parse(s.ca) || { first: addDays(anchor, -29), last: anchor }, anchor);
  const b = clamp(parse(s.cb) || before(a), anchor);
  return { a, b };
}
export function before(r) { const last = addDays(r.first, -1); return { first: addDays(last, -(length(r) - 1)), last }; }
export function yearBefore(r) { return { first: addDays(r.first, -364), last: addDays(r.last, -364) }; }   // 52 weeks: the same weekdays

const ym = (iso) => [Number(iso.slice(0, 4)), Number(iso.slice(5, 7))];
const iso = (y, mo, d) => `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
const monthEnd = (y, mo) => new Date(Date.UTC(y, mo, 0)).getUTCDate();
function presets(anchor) {
  const [y, mo] = ym(anchor);
  const lmY = mo === 1 ? y - 1 : y, lm = mo === 1 ? 12 : mo - 1;
  const q = Math.floor((mo - 1) / 3), qFirst = q * 3 + 1;
  const lqY = q === 0 ? y - 1 : y, lqFirst = q === 0 ? 10 : qFirst - 3;
  return [
    ["Last 7 days", { first: addDays(anchor, -6), last: anchor }],
    ["Last 30 days", { first: addDays(anchor, -29), last: anchor }],
    ["Last 90 days", { first: addDays(anchor, -89), last: anchor }],
    ["This month", { first: iso(y, mo, 1), last: anchor }],
    ["Last month", { first: iso(lmY, lm, 1), last: iso(lmY, lm, monthEnd(lmY, lm)) }],
    ["This quarter", { first: iso(y, qFirst, 1), last: anchor }],
    ["Last quarter", { first: iso(lqY, lqFirst, 1), last: iso(lqY, lqFirst + 2, monthEnd(lqY, lqFirst + 2)) }],
    ["Last 6 months", { first: addDays(anchor, -182), last: anchor }],
  ];
}

/* One range's button and popover. `rel` adds presets that depend on the
   other range (for B: the period just before A, and A a year earlier). */
export function picker(side, r, anchor, firstDay, onPick, rel = []) {
  const id = `vp-${side}`;
  const btn = h("button", { type: "button", class: `vs-range vs-${side.toLowerCase()}`, "aria-haspopup": "dialog", "aria-expanded": "false", "aria-controls": id },
    h("span", { class: "vs-tag", "aria-hidden": "true" }, side),
    h("span", { class: "vs-dates" }, `${short(r.first)} – ${short(r.last)} ${r.last.slice(0, 4)}`),
    h("span", { class: "vs-len" }, `${length(r)} day${length(r) === 1 ? "" : "s"}`),
    h("span", { class: "vh" }, `, range ${side}. Change it`));
  const from = h("input", { type: "date", value: r.first, max: anchor, min: firstDay ? addDays(firstDay, -366) : null, "aria-label": `Range ${side} from` });
  const to = h("input", { type: "date", value: r.last, max: anchor, "aria-label": `Range ${side} to` });
  const say = h("p", { class: "vs-say", role: "status" });
  const pick = (x) => { close(); onPick(clamp(x, anchor)); };
  const apply = h("button", { type: "button", class: "btn primary", onclick: () => {
    if (!from.value || !to.value || from.value > to.value) { say.textContent = "The start must be on or before the end."; return; }
    if (dayDiff(from.value, to.value) + 1 > MAX_DAYS) { say.textContent = "At most 12 months."; return; }
    pick({ first: from.value, last: to.value });
  } }, "Apply");
  const pop = h("div", { class: `pop vs-pop vs-${side.toLowerCase()}`, id, role: "dialog", "aria-label": `Range ${side}`, hidden: true },
    h("div", { class: "vs-presets" }, [...rel, ...presets(anchor)].map(([name, x]) => h("button", { type: "button", class: "menu-i", onclick: () => pick(x) }, name))),
    h("div", { class: "vs-custom" }, h("p", { class: "vs-h" }, "Custom"), h("label", null, "From", from), h("label", null, "To", to), say, apply,
      h("p", { class: "note" }, "Whole days only, up to yesterday; at most 12 months.")));
  const close = () => { pop.hidden = true; btn.setAttribute("aria-expanded", "false"); document.removeEventListener("pointerdown", away, true); document.removeEventListener("keydown", esc); };
  const away = (e) => { if (!wrap.contains(e.target)) close(); };
  const esc = (e) => { if (e.key === "Escape") { close(); btn.focus(); } };
  btn.addEventListener("click", () => {
    if (!pop.hidden) return close();
    pop.hidden = false; btn.setAttribute("aria-expanded", "true");
    document.addEventListener("pointerdown", away, true); document.addEventListener("keydown", esc);
    pop.querySelector("button")?.focus();
  });
  const wrap = h("div", { class: "vs-pick" }, btn, pop);
  return wrap;
}
