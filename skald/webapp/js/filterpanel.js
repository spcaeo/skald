// The Filters button, its panel (the advanced filter builder) and the chips under the
// top bar (2.13). The rules are js/rules.js's; this file draws them:
//
//   * rule rows over every dimension a visit carries, with is / is not / contains /
//     starts with / at least / at most; "all" or "any"; one level of groups
//   * a live count: how many of the visits kept for the period on screen match, and
//     how many each rule keeps alone (the journeys: kept journey_days days)
//   * Apply ("Show N visits"), Clear all, Save as a view; the saved views beside the
//     rules, each with Copy link (the address holds the rules: no share token, so
//     whoever opens it signs in first), Rename and Delete
//   * the chips: each top rule or group, removable on its own, greyed where this tab
//     cannot apply it; the banner (main.js) says which and where they do apply.

import * as S from "./state.js";
import { opened as routeOpened, closed as routeClosed } from "./overlays.js";
import { h, n, toast, reduced, ICON } from "./ui.js";
import { rangeOf } from "./data.js";
import { opt } from "./sections.js";
import { shown } from "./labels.js";
import { short } from "./ui.js";
import { DIMS, DIM, OPS, NR, NONE, opsOf, tidy, matcher, without, cannot, fromState, toState, singles, ruleWords, treeWords, leaves, timeWords } from "./rules.js";
import { parseAmount } from "./tablestate.js";
import { country, countryName, withFlag, flagEl, city, cityName } from "./tabs/readers.js";
import { encode as encodeDrill } from "./drill.js";
import { savedViews, saveView, deleteView, viewLink, copyText, renameInPlace, describe } from "./extras.js";

const GROUPS = [
  ["Where they were", ["country", "city"]],
  ["How they came", ["source", "referrer", "campaign", "assistant", "first"]],
  ["What they read", ["landing", "page", "pages", "seconds", "form"]],
  ["What they used", ["device", "browser", "os"]],
  ["Who", ["visitor"]],
  ["Requests only", ["crawler"]],
];
const TRASH = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 4.5h11M6 4.5V2.5h4v2M4 4.5l.7 9h6.6l.7-9"/></svg>';
const PLUS = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M8 3v10M3 8h10"/></svg>';
const GROUP = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="1.8" y="3" width="12.4" height="10" rx="2" stroke-dasharray="2.2 2"/><path d="M8 5.8v4.4M5.8 8h4.4"/></svg>';
const LINK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M3 10.5V3.5a1 1 0 0 1 1-1h7"/></svg>';
const TICK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5l3 3 6-7"/></svg>';

// ---- what the tab on screen can apply ---------------------------------------------------
const kindOf = (s) => opt(s.tab, "rules", s, null);            // "visit" | "request" | null
const supportOf = (s) => opt(s.tab, "filters", s, []);         // the single filters it applies
const isLeaf = (x) => x && typeof x.dim === "string";
/* Does this tab apply a top rule or group? Lists of visits or requests apply every rule
   their rows carry; a tab that counts breakdowns applies a rule a single filter can say. */
export function applies(s, item, tree) {
  const kind = kindOf(s);
  if (kind) return leaves({ items: [item] }).every((r) => DIM[r.dim]?.[kind]);
  if (!isLeaf(item)) return false;
  const one = [...singles(tree)].find(([, x]) => x === item);
  return !!one && supportOf(s).includes(one[0]);
}

// ---- words for values ------------------------------------------------------------------
export function valueWords(dim, v) {
  if (v === NR) return "Not recorded";
  if (v === NONE) return "None";
  if (dim === "country") return withFlag(v, country(v));
  if (dim === "city") return city(v);
  if (dim === "seconds") return timeWords(Number(v));
  return shown(v);
}
const valueTitle = (dim, v) => (dim === "country" ? countryName(v) : dim === "city" ? cityName(v) : null);
function valueNode(dim, v) {
  if (dim === "country" && v !== NR) return h("span", { class: "fp-v", title: countryName(v) }, flagEl(v), country(v));
  return h("span", { class: "fp-v", title: valueTitle(dim, v) }, valueWords(dim, v));
}

// ---- the visits a count is over ----------------------------------------------------------
function kept(m, s) {
  const r = rangeOf(m, s);
  const inRange = r.kind === "today" ? (j) => j.day === m.today : (j) => j.day >= r.first && j.day <= r.last;
  const list = (m.journeys || []).filter(inRange);
  const days = [...new Set(list.map((j) => j.day))].sort();
  const span = !days.length ? "" : days.length === 1 ? short(days[0]) : `${short(days[0])} to ${short(days[days.length - 1])}`;
  const cut = r.kind === "history" && days.length && days.length < r.length;
  return { list, r, span, cut, keptDays: m.journey_days || 7 };
}
// Values seen in the kept visits, most first; a crawler's from the days' crawler counts.
function valuesOf(m, dim, list) {
  const d = DIM[dim];
  const seen = new Map();
  if (d.visit) for (const j of list) {
    const raw = d.visit(j);
    for (const v of Array.isArray(raw) ? raw : raw == null ? [] : [raw]) if (v !== "" && v !== NONE) seen.set(v, (seen.get(v) || 0) + 1);
  } else if (dim === "crawler") {
    for (const day of m.byDay?.values?.() || []) for (const [k, v] of Object.entries(day.bot_agents || {})) seen.set(k, (seen.get(k) || 0) + v);
  }
  if (dim === "visitor") for (const v of ["New", "Returning"]) if (!seen.has(v)) seen.set(v, 0);
  if (dim === "form") for (const v of ["Yes", "No"]) if (!seen.has(v)) seen.set(v, 0);
  return [...seen].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]))).slice(0, 200);
}

// ---- the panel --------------------------------------------------------------------------
let open = null;   // {close}
const blank = (dim = "country") => ({ dim, op: opsOf(dim)[0], vals: [] });
const clone = (t) => JSON.parse(JSON.stringify(t));

export function openFilters(m, s, from) {
  if (open) open.close(false);
  const base = kept(m, s);
  const total = base.list.length;
  let draft = clone(fromState(s));
  if (!draft.items.length) draft.items.push(blank());
  let name = "";
  let focusKey = null;

  const shade = h("div", { class: "fp-shade", "aria-hidden": "true" });
  const box = h("div", { class: "fp", role: "dialog", "aria-modal": "true", "aria-labelledby": "fp-h" });
  const main = h("div", { class: "fp-main" });
  const aside = h("aside", { class: "fp-views", "aria-labelledby": "fp-vh" });
  box.append(main, aside);

  // The count: the draft's rules over the kept visits, with what a typed value would add.
  const countEl = h("b", { class: "fp-n" });
  const barEl = h("i");
  const ofEl = h("small");
  const status = h("div", { class: "fp-count", role: "status", "aria-live": "polite" },
    h("span", { class: "fp-big" }, countEl, h("span", null, " visits match")), h("span", { class: "fp-bar", "aria-hidden": "true" }, barEl), ofEl);
  const applyBtn = h("button", { type: "button", class: "btn primary fp-apply", onclick: () => apply() });
  const live = () => {
    const t = clone(draft);
    const add = (x) => { if (isLeaf(x) && x._pending) { x.vals = [...x.vals, x._pending]; } if (x.items) x.items.forEach(add); };
    t.items.forEach(add);
    return tidy(t);
  };
  const countOf = (tree) => { const f = matcher(without(tree, "visit"), "visit"); return base.list.filter(f).length; };
  function recount() {
    const t = live();
    const k = countOf(t);
    countEl.textContent = n(k);
    barEl.style.width = `${total ? (k / total) * 100 : 0}%`;
    const skip = cannot(t, "visit");
    ofEl.textContent = total ? `of ${n(total)} visit${total === 1 ? "" : "s"} kept${base.span ? `, ${base.span}` : ""}${base.cut ? ` (visits are kept ${base.keptDays} days)` : ""}${skip.length ? ". Crawler rules count requests: Site › Requests applies them" : ""}`
      : "No single visits are kept for this period.";
    applyBtn.textContent = t.items.length ? `Show ${n(k)} visit${k === 1 ? "" : "s"}` : "Show every visit";
    for (const el of main.querySelectorAll("[data-alone]")) {
      const x = el._rule;
      const one = tidy({ mode: "all", items: [{ ...x, vals: x._pending ? [...x.vals, x._pending] : x.vals }] });
      el.textContent = !DIM[x.dim]?.visit ? "requests only" : one.items.length ? `${n(countOf(one))} alone` : "";
    }
  }

  function apply() {
    const t = live();
    close(false);
    S.set(toState(t));
  }
  function clearAll() { draft = { mode: "all", items: [blank()] }; focusKey = "r0-f"; draw(); }

  // One rule's row. path: where it is ("r2", "g1-r0"); list: the array holding it.
  function ruleRow(x, path, list, joinWord) {
    const d = DIM[x.dim];
    const field = h("select", { class: "fp-sel fp-field", "data-k": `${path}-f`, "aria-label": "Dimension" },
      GROUPS.map(([g, keys]) => h("optgroup", { label: g }, keys.map((k) => h("option", { value: k, selected: k === x.dim }, DIM[k].label)))));
    field.addEventListener("change", () => { Object.assign(x, blank(field.value)); delete x._pending; focusKey = `${path}-f`; draw(); });
    const op = h("select", { class: "fp-sel fp-op", "data-k": `${path}-o`, "aria-label": `How ${d.label} is matched` },
      opsOf(x.dim).map((o) => h("option", { value: o, selected: o === x.op }, OPS[o])));
    op.addEventListener("change", () => { x.op = op.value; if (d.type === "num") x.vals = x.vals.slice(0, 1); focusKey = `${path}-o`; draw(); });

    const val = h("div", { class: "fp-val" });
    const chip = (v, i) => h("span", { class: "fp-chip" }, valueNode(x.dim, v),
      h("button", { type: "button", "data-k": `${path}-x${i}`, "aria-label": `Remove ${valueWords(x.dim, v)}`, onclick: () => { x.vals.splice(i, 1); focusKey = `${path}-v`; draw(); } }, "×"));
    if (d.type === "num") {
      const inp = h("input", { type: "text", class: "fp-in fp-num", inputmode: "decimal", "data-k": `${path}-v`, value: x.vals[0] != null ? (d.unit === "time" ? timeWords(Number(x.vals[0])) : x.vals[0]) : "",
        placeholder: d.unit === "time" ? "e.g. 1 min, 90 s" : "a number", "aria-label": `${d.label}, ${OPS[x.op]}` });
      inp.addEventListener("input", () => { const v = parseAmount(inp.value); x.vals = v == null ? [] : [String(v)]; recount(); });
      val.append(inp);
    } else {
      val.append(...x.vals.map(chip));
      const opts = valuesOf(m, x.dim, base.list).filter(([v]) => !x.vals.includes(v));
      if (d.type === "enum" || x.op === "is" || x.op === "not") {
        // Pick from the values seen; "Not recorded" and "None" where they are answers.
        const extra = [...(x.op === "is" ? [[NR, null]] : []), ...(d.none ? [[NONE, null]] : [])].filter(([v]) => !x.vals.includes(v));
        if (d.type === "enum") {
          const sel = h("select", { class: "fp-sel fp-pick", "data-k": `${path}-v`, "aria-label": `Add a value to ${d.label}` },
            h("option", { value: "" }, x.vals.length ? "Add another…" : "Pick a value…"),
            opts.map(([v, k]) => h("option", { value: v, title: valueTitle(x.dim, v) }, `${valueWords(x.dim, v)}${k ? ` (${n(k)})` : ""}`)),
            extra.map(([v]) => h("option", { value: v }, valueWords(x.dim, v))));
          sel.addEventListener("change", () => { if (sel.value) { x.vals.push(sel.value); focusKey = `${path}-v`; draw(); } });
          val.append(sel);
        }
      }
      if (d.type === "text") {
        const listId = `fp-dl-${path}`;
        const inp = h("input", { type: "text", class: "fp-in", "data-k": `${path}-v`, list: listId, spellcheck: "false", autocomplete: "off",
          placeholder: x.vals.length ? "or…" : x.dim === "page" || x.dim === "landing" ? "/pricing/" : "type, then Enter", "aria-label": `${d.label}, ${OPS[x.op]}` });
        const commit = () => { const v = inp.value.trim().replace(/,$/, ""); if (v && !x.vals.includes(v)) x.vals.push(v); delete x._pending; inp.value = ""; focusKey = `${path}-v`; draw(); };
        inp.addEventListener("input", () => { if (inp.value.endsWith(",")) return commit(); x._pending = inp.value.trim() || undefined; recount(); });
        inp.addEventListener("keydown", (e) => {
          if (e.key === "Enter") { e.preventDefault(); if (inp.value.trim()) commit(); else apply(); }
          if (e.key === "Backspace" && !inp.value && x.vals.length) { x.vals.pop(); focusKey = `${path}-v`; draw(); }
        });
        inp.addEventListener("change", () => { if (inp.value.trim()) commit(); });
        val.append(inp, h("datalist", { id: listId }, opts.slice(0, 60).map(([v]) => h("option", { value: v }))));
      }
    }
    const alone = h("small", { class: "fp-alone", "data-alone": "" });
    alone._rule = x;
    val.append(alone);
    const del = h("button", { type: "button", class: "fp-del", html: TRASH, "data-k": `${path}-d`,
      "aria-label": `Remove the rule ${d.label} ${OPS[x.op]}${x.vals.length ? ` ${x.vals.map((v) => valueWords(x.dim, v)).join(", ")}` : ""}`,
      onclick: () => { list.splice(list.indexOf(x), 1); focusKey = "add"; draw(); } });
    return h("li", { class: "fp-li" }, joinWord ? h("span", { class: `fp-join ${draft.mode}` }, joinWord) : null,
      h("div", { class: "fp-rule" }, field, op, val, del));
  }

  function groupRow(g, gi) {
    const seg = segmented([["all", "All"], ["any", "Any"]], g.mode, (k) => { g.mode = k; focusKey = `g${gi}-m-${k}`; draw(); }, "This group matches", `g${gi}-m`);
    const rows = g.items.map((x, i) => ruleRow(x, `g${gi}-r${i}`, g.items, i ? (g.mode === "any" ? "OR" : "AND") : null));
    rows.forEach((li) => li.querySelector(".fp-join")?.setAttribute("class", `fp-join ${g.mode}`));
    return h("li", { class: "fp-li" }, h("span", { class: `fp-join ${draft.mode}` }, draft.mode === "any" ? "OR" : "AND"),
      h("div", { class: "fp-group", role: "group", "aria-label": "Group of rules" },
        h("div", { class: "fp-ghead" }, h("span", null, "Group: match"), seg, h("span", { class: "grow" }),
          h("button", { type: "button", class: "linkish fp-gx", "data-k": `g${gi}-x`, onclick: () => { draft.items.splice(draft.items.indexOf(g), 1); focusKey = "add"; draw(); } }, "Remove group")),
        h("ol", { class: "fp-rules" }, rows),
        h("button", { type: "button", class: "btn fp-addg", html: PLUS, "data-k": `g${gi}-add`, onclick: () => { g.items.push(blank()); focusKey = `g${gi}-r${g.items.length - 1}-f`; draw(); } }, "Add a rule to the group")));
  }

  function views() {
    const list = savedViews();
    const items = list.map((v, i) => {
      const t = fromState(Object.fromEntries(new URLSearchParams(v.hash.split("?")[1] || "")));
      const countable = t.items.length && !cannot(t, "visit").length;
      const nameBtn = h("button", { type: "button", class: "fp-vname", "data-k": `v${i}-o`, title: "Open this view", onclick: () => { close(false); location.hash = v.hash; } }, v.name);
      const copy = h("button", { type: "button", class: "fp-copy", "data-k": `v${i}-c`, "aria-label": `Copy the link to ${v.name}` }, h("i", { html: LINK }), h("span", null, "Copy link"));
      copy.addEventListener("click", async () => {
        const ok = await copyText(viewLink(v.hash));
        if (!ok) return toast("Copying is blocked here; open the view and copy the address.");
        copy.classList.add("done");
        copy.replaceChildren(h("i", { html: TICK }), h("span", null, "Link copied"));
        toast(`Link to "${v.name}" copied. Whoever opens it signs in first.`);
      });
      return h("li", { class: "fp-view" },
        h("div", { class: "fp-vtop" }, h("span", { class: "fp-vnames" }, nameBtn, h("small", null, describe(v.hash))),
          countable ? h("span", { class: "fp-vcount", title: "Visits kept for the period on screen that match this view's rules" }, `${n(countOf(t))} visits`) : null),
        h("div", { class: "fp-vact" }, h("span", { class: "fp-vlink", title: viewLink(v.hash) }, viewLink(v.hash).replace(/^https?:\/\//, "")), copy,
          h("button", { type: "button", class: "linkish", "data-k": `v${i}-r`, onclick: (e) => renameInPlace(nameBtn, v.name, () => { focusKey = `v${i}-o`; draw(); }) }, "Rename"),
          h("button", { type: "button", class: "linkish fp-vdel", "data-k": `v${i}-d`, "aria-label": `Delete the saved view ${v.name}`, onclick: () => { deleteView(v.name); toast(`Deleted "${v.name}"`); focusKey = "name"; draw(); } }, "Delete")));
    });
    aside.replaceChildren(h("h3", { id: "fp-vh" }, "Saved views"),
      h("p", null, "A view keeps the tab, the period, these rules and each table's sort, filters and columns. Its link opens the same page for anyone on your team, after they sign in."),
      items.length ? h("ul", { class: "fp-vlist" }, items) : h("p", { class: "fp-empty" }, "No saved views yet. Name the rules and press Save view."));
  }

  function draw() {
    const joinWord = draft.mode === "any" ? "OR" : "AND";
    const rows = draft.items.map((x, i) => (isLeaf(x) ? ruleRow(x, `r${i}`, draft.items, i ? joinWord : null) : groupRow(x, i)));
    // A group's first line carries the join already; the first item never does.
    if (rows[0]) rows[0].querySelector(":scope > .fp-join")?.remove();
    const hasGroup = draft.items.some((x) => !isLeaf(x));
    const nameIn = h("input", { type: "text", class: "fp-in fp-name", "data-k": "name", value: name, maxlength: "60", placeholder: "e.g. North America, AI first touch" });
    nameIn.addEventListener("input", () => { name = nameIn.value; });
    nameIn.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } });
    const save = () => {
      const nm = nameIn.value.trim();
      if (!nm) { nameIn.focus(); return toast("Name the view first."); }
      const hash = S.hashFor({ ...S.read(), ...toState(live()) });
      if (!saveView(nm, hash)) return toast("Saving needs browser storage, which is blocked here.");
      toast(`Saved "${nm}"`);
      name = "";
      close(false);
      if (hash !== location.hash) location.hash = hash;
    };
    main.replaceChildren(
      h("div", { class: "fp-top" },
        h("div", null, h("h2", { id: "fp-h" }, "Filter visits"),
          h("p", null, "Lists of single visits apply every rule; a tab that counts breakdowns applies the ones it can and says which it cannot. The count updates as you edit.")),
        status),
      h("div", { class: "fp-box" },
        h("div", { class: "fp-mode" }, h("span", null, "Show visits that match"),
          segmented([["all", "All rules", "AND"], ["any", "Any rule", "OR"]], draft.mode, (k) => { draft.mode = k; focusKey = `m-${k}`; draw(); }, "Match all rules or any", "m")),
        h("ol", { class: "fp-rules" }, rows),
        h("div", { class: "fp-adds" },
          h("button", { type: "button", class: "btn", html: PLUS, "data-k": "add", onclick: () => { draft.items.push(blank(nextDim())); focusKey = `r${draft.items.length - 1}-f`; draw(); } }, "Add rule"),
          h("button", { type: "button", class: "btn", html: GROUP, "data-k": "addg", disabled: hasGroup, title: hasGroup ? "One group at a time" : null,
            onclick: () => { draft.items.push({ mode: draft.mode === "any" ? "all" : "any", items: [blank("source"), blank("source")] }); focusKey = `g${draft.items.length - 1}-r0-f`; draw(); } }, "Add group"))),
      h("div", { class: "fp-foot" },
        h("label", { class: "fp-save" }, h("span", null, "Save as a view"), nameIn),
        h("button", { type: "button", class: "btn", "data-k": "save", onclick: save }, "Save view"),
        h("span", { class: "grow" }),
        h("button", { type: "button", class: "btn ghost", "data-k": "clear", onclick: clearAll }, "Clear all"),
        applyBtn));
    views();
    recount();
    if (focusKey) { const el = box.querySelector(`[data-k="${focusKey}"]`); (el || box.querySelector("select,input,button"))?.focus(); focusKey = null; }
  }
  const nextDim = () => { const used = new Set(leaves(draft).map((x) => x.dim)); return DIMS.find((d) => d.visit && !used.has(d.key))?.key || "country"; };

  function place() {
    const bar = document.getElementById("bar")?.getBoundingClientRect();
    const area = document.getElementById("panel")?.getBoundingClientRect();
    const top = Math.max(8, Math.round((bar?.bottom || 56) + 8));
    box.style.setProperty("--fp-top", `${top}px`);
    shade.style.top = `${Math.round(bar?.bottom || 0)}px`;
    const w = Math.min(940, innerWidth - 16);
    const left = area && area.width > w ? area.left + (area.width - w) / 2 : (innerWidth - w) / 2;
    box.style.left = `${Math.max(8, Math.round(left))}px`;
    box.style.width = `${w}px`;
  }

  function close(focusBack = true) {
    if (!box.isConnected) return;
    box.remove(); shade.remove();
    routeClosed("dlg", "filters");
    removeEventListener("resize", place);
    from?.setAttribute("aria-expanded", "false");
    from?.classList.remove("on");
    open = null;
    if (focusBack) from?.focus();
  }
  shade.addEventListener("click", () => close(true));
  box.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(true); return; }
    if (e.key !== "Tab") return;
    // The focus stays in the panel while it is open.
    const all = [...box.querySelectorAll("button:not([disabled]),select,input")].filter((el) => el.offsetParent !== null);
    if (!all.length) return;
    if (e.shiftKey && document.activeElement === all[0]) { e.preventDefault(); all[all.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === all[all.length - 1]) { e.preventDefault(); all[0].focus(); }
  });
  document.body.append(shade, box);
  if (!reduced()) box.classList.add("fp-in-anim");
  place();
  addEventListener("resize", place);
  from?.setAttribute("aria-expanded", "true");
  from?.classList.add("on");
  focusKey = "r0-f";
  draw();
  open = { close };
  // In the address as dlg=filters while it is open (js/overlays.js): Back closes it.
  routeOpened("dlg", "filters", { close: () => close(false), isOpen: () => box.isConnected });
  return open;
}

/* A two- or three-way switch: [key, words, short?]. key: the data-k prefix for focus. */
function segmented(options, value, onPick, label, key) {
  return h("span", { class: "fp-seg", role: "group", "aria-label": label }, options.map(([k, words, hint]) =>
    h("button", { type: "button", "aria-pressed": String(k === value), "data-k": `${key}-${k}`, onclick: () => { if (k !== value) onPick(k); } }, words, hint ? h("small", null, hint) : null)));
}

// ---- in the top bar ------------------------------------------------------------------------
export function filtersButton(m, s) {
  const k = fromState(s).items.length;
  const b = h("button", { type: "button", class: "btn fp-btn", "aria-haspopup": "dialog", "aria-expanded": "false", html: ICON.filter,
    "aria-label": k ? `Filters, ${k} active` : "Filters" }, h("span", { class: "f-l" }, "Filters"), k ? h("span", { class: "count", "aria-hidden": "true" }, String(k)) : null);
  b.addEventListener("click", () => (open ? open.close(true) : openFilters(m, S.read(), b)));
  return b;
}

/* The chips: each top rule or group, removable; greyed where this tab cannot apply it. */
export function filterChips(m, s, { noData = false } = {}) {
  const tree = fromState(s);
  if (!tree.items.length || noData) return h("div", { class: "chips", "aria-label": "Active filters" });
  const drop = (item) => S.set(toState({ mode: tree.mode, items: tree.items.filter((x) => x !== item) }));
  const chips = tree.items.map((x) => {
    const on = applies(s, x, tree);
    if (isLeaf(x)) {
      const w = ruleWords(x, valueWords);
      return h("span", { class: `chip${on ? "" : " off"}` }, w.field, " ", h("span", { class: "chip-op" }, w.op), " ",
        h("b", { title: x.dim === "country" ? x.vals.map(countryName).join(", ") : null }, x.dim === "country" && x.vals.length === 1 && x.vals[0] !== NR ? [flagEl(x.vals[0]), country(x.vals[0])] : w.val),
        h("button", { type: "button", "aria-label": `Remove the filter ${w.field} ${w.op} ${w.val}`, onclick: () => drop(x) }, "×"));
    }
    const words = treeWords({ mode: "all", items: [x] }, valueWords);
    return h("span", { class: `chip grp${on ? "" : " off"}` }, h("b", null, words), h("button", { type: "button", "aria-label": `Remove the group ${words}`, onclick: () => drop(x) }, "×"));
  });
  const join = tree.items.length > 1 ? h("span", { class: "chips-join" }, tree.mode === "any" ? "Any of" : "All of") : null;
  const edit = h("button", { type: "button", class: "chip-edit", onclick: (e) => openFilters(m, S.read(), document.querySelector(".fp-btn") || e.currentTarget) }, "Edit filters");
  return h("div", { class: "chips", "aria-label": "Active filters" }, join, chips, edit);
}

/* What this tab cannot apply, said once at the top, with where it does apply: a single
   value's own view (the drill-down; a page on Traffic › Pages), or the list that keeps
   each visit (Traffic › Visitors) or each request (Site › Requests). Never only a grey chip. */
export function rulesBanner(m, s) {
  const tree = fromState(s);
  const off = tree.items.filter((x) => !applies(s, x, tree));
  const scope = opt(s.tab, "rulesScope", s, null);
  if (!off.length) return tree.items.length && scope ? h("div", { class: "filter-banner scope", role: "note" }, h("p", null, scope)) : null;
  const kind = kindOf(s);
  const one = new Map([...singles(tree)].map(([k, x]) => [x, k]));
  const crawler = off.some((x) => leaves({ items: [x] }).some((r) => r.dim === "crawler"));
  const go = (x) => {
    const k = one.get(x);
    if (k && !kind) {
      const v = x.vals[0];
      const to = k === "path" ? () => S.set({ tab: "traffic/pages" }) : () => S.set({ dd: encodeDrill([[k, v]]) });
      return h("button", { type: "button", class: "linkish fb-go", onclick: to }, k === "path" ? `pages that ${x.op === "starts" ? "start with" : "contain"} ${v}, on Traffic › Pages →` : `${valueWords(x.dim, v)}'s own view →`);
    }
    return null;
  };
  const words = off.map((x) => treeWords({ mode: "all", items: [x] }, valueWords));
  const own = off.map(go).filter(Boolean);
  const where = kind === "visit" || crawler
    ? h("a", { class: "linkish fb-go", href: S.hashFor({ ...s, tab: "site/requests", dd: "" }) }, "the request log, on Site › Requests →")
    : h("a", { class: "linkish fb-go", href: S.hashFor({ ...s, tab: "traffic/visitors", dd: "" }) }, "each visit, on Traffic › Visitors →");
  const rules = h("span", { class: "fb-rules" }, words.join("; "));
  if (kind) {
    const what = kind === "visit" ? "visits" : "requests";
    return h("div", { class: "filter-banner", role: "note" },
      h("p", null, h("b", null, "Not applied here: "), rules, `. ${off.length === 1 ? "It needs" : "They need"} something these ${what} do not carry. See `, where));
  }
  return h("div", { class: "filter-banner", role: "note" },
    h("p", null, h("b", null, "This tab shows all visitors. "),
      `${off.length === 1 ? "This filter does" : "These filters do"} not apply here: its figures cannot be split that way (`,
      rules, "). See ", ...own.flatMap((b) => [b, " · "]), where));
}
