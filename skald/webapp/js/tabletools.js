// The controls every table and grid shares (table.js, grid.js): the per-column
// filter cells, the column chooser and "Export what you see". The logic behind
// them is tablestate.js's; these only draw it and say what changed.

import { h, n } from "./ui.js";
import { filterKind, filterOn, parseAmount } from "./tablestate.js";

export const TT_ICON = {
  cols: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2.5" width="12" height="11" rx="1.6"/><path d="M6 2.5v11M10 2.5v11"/></svg>',
  funnel: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M2.5 3h11l-4.2 5v4.4l-2.6 1.3V8z"/></svg>',
  down: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2.5v8M4.5 7.5 8 11l3.5-3.5M3 13.5h10"/></svg>',
  chev: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5 8 10l3.5-3.5"/></svg>',
};

// One small popover at a time, closed by Escape or a press outside; focus goes back to its button.
let openOne = null, listening = false;
const outside = (e) => { if (openOne && !openOne.wrap.contains(e.target)) openOne.close(false); };
export function popper(toggle, pop, { onOpen } = {}) {
  const wrap = h("span", { class: "tt-pw" }, toggle, pop);
  pop.hidden = true;
  toggle.setAttribute("aria-expanded", "false");
  const close = (focusBack) => {
    pop.hidden = true; toggle.setAttribute("aria-expanded", "false");
    if (openOne?.wrap === wrap) openOne = null;
    if (focusBack) toggle.focus();
  };
  toggle.addEventListener("click", () => {
    if (!pop.hidden) return close(false);
    openOne?.close(false);
    if (!listening) { document.addEventListener("pointerdown", outside); listening = true; }
    pop.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    // Open toward the side with room.
    pop.classList.remove("tt-left");
    const box = pop.getBoundingClientRect?.();
    if (box && box.right > (globalThis.innerWidth || 0) - 8 && box.left > box.width) pop.classList.add("tt-left");
    openOne = { wrap, close };
    onOpen?.();
    pop.querySelector("input,button")?.focus();
  });
  pop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(true); } });
  return wrap;
}

/* The column chooser: a checkbox per column; the first column (the row's name, and its
   link) always stays. onChange(hiddenKeys). */
export function chooser(columns, hidden, onChange, caption = "this table") {
  const count = h("span", { class: "tt-meta" });
  const toggle = h("button", { type: "button", class: "btn tt-btn", html: TT_ICON.cols, "aria-haspopup": "true" }, h("span", { class: "tt-w" }, "Columns"), count);
  const pop = h("div", { class: "tt-pop", role: "group", "aria-label": `Columns shown in ${caption}` });
  const say = () => {
    const shown = columns.length - hidden.length;
    count.textContent = shown < columns.length ? ` ${shown} of ${columns.length}` : "";   // said only when some are hidden
    toggle.setAttribute("aria-label", `Columns: ${shown} of ${columns.length} shown`);
  };
  pop.append(h("p", { class: "tt-pop-h" }, "Show columns"), ...columns.map((c, i) => {
    const box = h("input", { type: "checkbox", checked: !hidden.includes(c.key), disabled: i === 0 });
    box.addEventListener("change", () => {
      hidden = box.checked ? hidden.filter((k) => k !== c.key) : [...hidden, c.key];
      say();
      onChange(hidden);
    });
    return h("label", { class: "tt-opt", title: i === 0 ? "The row's name: always shown" : null }, box, h("span", null, c.label || c.key));
  }));
  say();
  return popper(toggle, pop);
}

/* "Export": the rows that match, in their order, with the columns shown, as CSV. The button
   says only "Export" (one size on every table); what it holds is on hover and to a screen
   reader ("CSV, 37 rows, 8 columns: what you see"). */
export function exportButton(onClick) {
  const b = h("button", { type: "button", class: "btn tt-btn tt-export", html: TT_ICON.down }, h("span", { class: "tt-w" }, "Export"));
  b.addEventListener("click", onClick);
  b.say = (rows, cols, caption) => {
    const words = `CSV, ${n(rows)} row${rows === 1 ? "" : "s"}, ${cols} column${cols === 1 ? "" : "s"}: what you see`;
    b.title = words;
    b.setAttribute("aria-label", `Export ${caption || "this table"}: ${words}`);
    b.disabled = !rows;
  };
  return b;
}

/* The filters that are on, as chips above the table ("Stage: won ×", "Visits: 3 to 10 ×"),
   each removable, and "Clear all" with two or more: what is applied is always in sight,
   as Search Console shows it. say(columns, filters) redraws them; none on: nothing shown. */
export function filterChips(onRemove) {
  const el = h("div", { class: "tt-chips", role: "group", "aria-label": "Filters on", hidden: true });
  el.say = (columns, filters) => {
    const on = filters.filter(filterOn);
    el.hidden = !on.length;
    el.replaceChildren(...on.map((f) => {
      const c = columns.find((x) => x.key === f.key);
      const name = c?.label || f.key;
      const what = f.op === "has" ? `contains “${f.value}”` : f.op === "in" ? f.value.map((v) => v || "Not recorded").join(", ")
        : f.value[0] != null && f.value[1] != null ? `${f.value[0]} to ${f.value[1]}` : f.value[0] != null ? `at least ${f.value[0]}` : `at most ${f.value[1]}`;
      return h("span", { class: "chip tt-chip" }, h("b", null, `${name}:`), ` ${what}`,
        h("button", { type: "button", "aria-label": `Remove the filter on ${name}`, title: "Remove", onclick: () => onRemove(f.key) }, "×"));
    }), on.length > 1 ? h("button", { type: "button", class: "linkish tt-clear-all", onclick: () => onRemove(null) }, "Clear all") : "");
  };
  return el;
}

/* The filter toggle: shows the row of column filters under the headers; says how many are on. */
export function filterToggle(onToggle) {
  const k = h("span", { class: "tt-k", hidden: true });
  const b = h("button", { type: "button", class: "btn tt-btn", html: TT_ICON.funnel, "aria-pressed": "false" }, h("span", { class: "tt-w" }, "Filter"), k);
  b.addEventListener("click", () => onToggle(b.getAttribute("aria-pressed") !== "true"));
  b.say = (open, active) => {
    b.setAttribute("aria-pressed", String(!!open));
    k.hidden = !active;
    k.textContent = String(active);
    b.setAttribute("aria-label", active ? `Filter columns: ${active} on` : "Filter columns");
  };
  return b;
}

/* One column's filter cell. kind: "text" | "num" | "enum"; f: its filter or null;
   options(): [[shown words, rows]] for an enum; set(filter | null) on a change.
   Typing waits a moment before the rows change, so a fast typist is not slowed. */
export function filterCell(c, kind, f, options, set) {
  const label = c.label || c.key;
  let timer = 0;
  const later = (fn) => { clearTimeout(timer); timer = setTimeout(fn, 180); };
  if (kind === "text") {
    const inp = h("input", { type: "search", class: "tt-in", value: f?.value || "", placeholder: "Contains", "aria-label": `Filter ${label}: contains`, spellcheck: "false", autocomplete: "off" });
    inp.addEventListener("input", () => later(() => set(inp.value.trim() ? { key: c.key, op: "has", value: inp.value } : null)));
    return h("div", { class: "tt-f" }, inp);
  }
  if (kind === "num") {
    const [lo, hi] = f?.value || [null, null];
    const mk = (v, word) => h("input", { type: "text", class: "tt-in tt-num", inputmode: "decimal", value: v ?? "", placeholder: word, "aria-label": `Filter ${label}: ${word === "min" ? "at least" : "at most"}`, autocomplete: "off" });
    const a = mk(lo, "min"), b = mk(hi, "max");
    const go = () => later(() => {
      const value = [parseAmount(a.value), parseAmount(b.value)];
      const next = { key: c.key, op: "range", value };
      set(filterOn(next) ? next : null);
    });
    a.addEventListener("input", go);
    b.addEventListener("input", go);
    return h("div", { class: "tt-f tt-range" }, a, h("span", { "aria-hidden": "true" }, "–"), b);
  }
  if (kind === "enum") {
    let picked = f?.value ? [...f.value] : [];
    const words = h("span", null);
    const say = () => { words.textContent = !picked.length ? "Any" : picked.length === 1 ? picked[0] : `${picked.length} picked`; };
    const toggle = h("button", { type: "button", class: `tt-enum${picked.length ? " on" : ""}`, "aria-haspopup": "true", "aria-label": `Filter ${label}: pick values` }, words, h("i", { html: TT_ICON.chev }));
    const pop = h("div", { class: "tt-pop", role: "group", "aria-label": `Values of ${label}` });
    const draw = () => {
      const opts = options();
      pop.replaceChildren(...(opts.length ? opts.map(([v, k]) => {
        const box = h("input", { type: "checkbox", checked: picked.includes(v) });
        box.addEventListener("change", () => {
          picked = box.checked ? [...picked, v] : picked.filter((x) => x !== v);
          say();
          toggle.classList.toggle("on", picked.length > 0);
          set(picked.length ? { key: c.key, op: "in", value: picked } : null);
        });
        return h("label", { class: "tt-opt" }, box, h("span", null, v || "Not recorded"), h("small", null, n(k)));
      }) : [h("p", { class: "tt-pop-h" }, "No values in these rows.")]),
      picked.length ? h("button", { type: "button", class: "linkish tt-clear", onclick: () => { picked = []; say(); toggle.classList.remove("on"); set(null); draw(); } }, "Clear") : "");
    };
    say();
    return h("div", { class: "tt-f" }, popper(toggle, pop, { onOpen: draw }));
  }
  return h("div", { class: "tt-f" });
}

export { filterKind };
