// Boot, the top bar and the tab router. The sidebar, its drawer and the
// phone's tab bar are nav.js's.
//
// The top bar, one slim row: the section and drill-down trail on the left;
// the modes (modes.js: Today · Live, Compare with…), the period, page group
// and filters in the middle; saved views,
// refresh, export, alerts and the command palette on the right. What does
// not fit a narrow screen moves into the "more" menu. Active filters make a
// second row, only when there are some.

import * as S from "./state.js";
import { h, ICON, reduced, toast, untip } from "./ui.js";
import { load, refresh as postRefresh, viewList, rangeOf, markersByDay } from "./data.js";
import { TAB_RENDER } from "./tabs/index.js";
import { TAB, opt } from "./sections.js";
import { tabStrip } from "./tabstrip.js";
import { barModes, modeBanner, modeActions } from "./modes.js";
import { country, flagEl, withFlag } from "./tabs/readers.js";
import { setMarkers } from "./charts.js";
import { saved, savedDialog, bell, marksOn, zonePicker, store } from "./extras.js";
import { setZone, time as tzTime } from "./tz.js";
import { keys, help, whatsNew, newUnseen, palette } from "./keys.js";
import { drillView } from "./drillview.js";
import { closeDrawers } from "./drawer.js";
import { chainOf, DIMS, said } from "./drill.js";
import { setFavicons } from "./icons.js";
import { REGISTRY, showAllRows } from "./table.js";
import { exportMenu, builder, exportZip, exportJSON, printTab } from "./report.js";
import { setContext } from "./tabs/common.js";
import { loadBuild, buildLine, toolName, newerBuild, releaseLine, BUILD, REPO } from "./build.js";
import { searchBox, openSearch, mayFind, SEARCH_HINT } from "./tabs/person.js";
import { info, quietKpis } from "./tabs/tiles.js";
import { PRIVACY } from "./tabs/about.js";
import { buildNav, mark, badge, brand, siteChip, railFoot, openDrawer, trailOf } from "./nav.js";
import { ME, loadMe, sessions, signOut } from "./access.js";
import { planBanner } from "./tabs/billing.js";
import { updateBanner } from "./updates.js";
import { DEMO, demoBanner, demoState } from "./demo.js";

const app = document.getElementById("app");
const panel = document.getElementById("panel");
const bar = document.getElementById("bar");
let model = null, current = null, firstPaint = true;

// ------------------------------------------------------------------ theme
const THEMES = [["system", "System"], ["light", "Light"], ["dark", "Dark"]];
function theme(next) {
  let t = "system";
  try { t = next ?? localStorage.getItem("ti-theme") ?? "system"; } catch { /* storage blocked */ }
  if (!THEMES.some(([k]) => k === t)) t = "system";
  if (t === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("ti-theme", t); } catch { /* storage blocked */ }
  document.querySelectorAll(".theme-seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.t === t)));
  return t;
}
const HELP_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="6.2"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.4"/><circle cx="8" cy="11.4" r=".5" fill="currentColor" stroke="none"/></svg>';
const SUN = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="3"/><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1"/></svg>';
const MOON = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1z"/></svg>';
const AUTO = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5.6"/><path d="M8 2.4v11.2A5.6 5.6 0 0 0 8 2.4z" fill="currentColor"/></svg>';
const SPARK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M8 1.8l1.5 4.2 4.3 1.6-4.3 1.6L8 13.4 6.5 9.2 2.2 7.6l4.3-1.6z"/></svg>';
const cycleTheme = () => theme(THEMES[(THEMES.findIndex(([k]) => k === (document.documentElement.getAttribute("data-theme") || "system")) + 1) % 3][0]);
theme();

let lastW = innerWidth;
addEventListener("resize", () => {
  if (!current) return;
  clearTimeout(render.t);
  // Charts are drawn to the panel's width: redraw when it changes, not on every pixel.
  render.t = setTimeout(() => { if (Math.abs(innerWidth - lastW) > 40) { lastW = innerWidth; render(current, { keepScroll: true }); } }, 250);
});

// ------------------------------------------------------------- the top bar
/* The dark pill under the chosen period. The bar is drawn again on every
   change, so the pill starts where the last one stood and slides once; and
   it is placed again whenever a button's size changes (the bar settling,
   a narrower screen, a font), never left where an early measure put it. */
let pillAt = null;
function segmented(options, value, onPick, label) {
  const ind = h("span", { class: "seg-ind", "aria-hidden": "true" });
  const btns = options.map(([k, name]) => h("button", { type: "button", "aria-pressed": String(k === value), onclick: () => onPick(k) }, name));
  const seg = h("div", { class: "seg", role: "group", "aria-label": label }, ind, btns);
  let now = null;
  const put = (x, w) => { now = { x, w }; ind.style.width = `${w}px`; ind.style.transform = `translateX(${x}px)`; };
  const place = (slide) => {
    const on = btns.find((b) => b.getAttribute("aria-pressed") === "true");
    if (!seg.isConnected) return;
    if (!on || !on.offsetWidth) { now = null; ind.style.width = "0"; return; }
    const r = on.getBoundingClientRect(), box = seg.getBoundingClientRect();
    const x = r.left - box.left - seg.clientLeft, w = r.width;
    pillAt = { x, w };
    if (now && Math.abs(now.x - x) < 0.5 && Math.abs(now.w - w) < 0.5) return;
    if (!slide) ind.style.transition = "none";
    put(x, w);
    if (!slide) { void ind.offsetWidth; ind.style.transition = ""; }
  };
  // Where the last pill stood, then (a frame later, laid out) where this one belongs.
  const slide = !!pillAt;
  if (slide) { ind.style.transition = "none"; put(pillAt.x, pillAt.w); }
  requestAnimationFrame(() => { ind.style.transition = ""; place(slide); });
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => { if (!seg.isConnected) return ro.disconnect(); place(false); });
    btns.forEach((b) => ro.observe(b));
  }
  return seg;
}

// One popover open at a time; a press outside closes it.
let closePop = null;
document.addEventListener("pointerdown", (e) => closePop && closePop(e));

const FILTER_LABEL = { country: "Country", path: "Page path", source: "Source", device: "Device", browser: "Browser", campaign: "Campaign", referrer: "Referring site" };
const MORE = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><circle cx="3.5" cy="8" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="12.5" cy="8" r="1.4"/></svg>';
const MENU = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2.5 4h11M2.5 8h11M2.5 12h11"/></svg>';
const CMDK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="7" cy="7" r="4.3"/><path d="M10.2 10.2l3.6 3.6"/></svg>';

function filtersPop(s) {
  const opts = model.options;
  const pop = h("div", { class: "pop", hidden: true, role: "dialog", "aria-label": "Filters" });
  const fields = {};
  const pick = (k, list) => {
    const sel = h("select", { id: `f-${k}` }, h("option", { value: "" }, "Any"),
      list.map((v) => h("option", { value: v, selected: s[k] === v }, k === "country" ? withFlag(v, country(v)) : v)));
    fields[k] = sel;
    return h("label", { class: "fld", for: `f-${k}` }, FILTER_LABEL[k], sel);
  };
  const mode = h("select", { "aria-label": "Match" }, h("option", { value: "contains", selected: s.pathmode !== "starts" }, "contains"),
    h("option", { value: "starts", selected: s.pathmode === "starts" }, "starts with"));
  const pathIn = h("input", { type: "text", id: "f-path", value: s.path || "", placeholder: "/pricing", spellcheck: "false", autocomplete: "off" });
  fields.path = pathIn;
  pop.append(pick("country", opts.country), h("label", { class: "fld", for: "f-path" }, "Page path", h("span", { class: "pair" }, mode, pathIn)),
    pick("source", opts.source), pick("campaign", opts.campaign), pick("referrer", opts.referrer), pick("device", opts.device), pick("browser", opts.browser),
    h("p", { class: "note" }, "Logs keep each breakdown on its own, so filters narrow the lists they belong to and cannot be crossed (Canada AND Chrome). A tab says which filters it cannot apply."),
    h("div", { class: "row" },
      h("button", { type: "button", class: "btn", onclick: () => { S.set(Object.fromEntries(S.FILTERS.map((k) => [k, ""]))); } }, "Clear all"),
      h("button", { type: "button", class: "btn primary", onclick: () => {
        const patch = { pathmode: mode.value };
        for (const k of S.FILTERS) patch[k] = fields[k].value.trim();
        S.set(patch);
      } }, "Apply filters")));
  const n = S.activeFilters(s).length;
  const toggle = h("button", { type: "button", class: "btn", "aria-expanded": "false", "aria-haspopup": "dialog", html: ICON.filter, "aria-label": n ? `Filters, ${n} active` : "Filters" },
    h("span", { class: "f-l" }, "Filters"), n ? h("span", { class: "count", "aria-label": `${n} active` }, String(n)) : null);
  return popover(toggle, pop, () => pop.querySelector("select,input")?.focus());
}

// A button and its popover: open, close on Escape or a press outside, focus back on close.
function popover(toggle, pop, onOpen) {
  const wrap = h("div", { class: "more" }, toggle, pop);
  const close = (focusBack) => { pop.hidden = true; toggle.setAttribute("aria-expanded", "false"); if (closePop === outside) closePop = null; if (focusBack) toggle.focus(); };
  const outside = (e) => { if (!pop.hidden && !wrap.contains(e.target)) close(false); };
  toggle.addEventListener("click", () => {
    if (!pop.hidden) return close(false);
    if (closePop) closePop({ target: document.body });
    pop.hidden = false;
    pop.classList.remove("from-left");
    if (pop.getBoundingClientRect().left < 8) pop.classList.add("from-left");
    toggle.setAttribute("aria-expanded", "true");
    closePop = outside;
    onOpen?.();
  });
  pop.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close(true);
    if (e.key === "Enter" && e.target.tagName === "INPUT" && pop.querySelector(".btn.primary")) pop.querySelector(".btn.primary").click();
  });
  return wrap;
}

// "32s ago", kept current.
function ago(ts) {
  const el = h("span", { class: "ago" });
  const tick = () => {
    if (el.dataset.on && !el.isConnected) return clearInterval(timer);
    el.dataset.on = "1";
    const sec = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 1000));
    el.textContent = sec < 60 ? `${sec}s ago` : sec < 3600 ? `${Math.floor(sec / 60)}m ago` : tzTime(ts);
  };
  const timer = setInterval(tick, 5000);
  tick();
  return el;
}

const actions = () => [
  ...(mayFind() ? [{ label: `Find a person: ${SEARCH_HINT}`, hint: "", run: openSearch }] : []),
  ...modeActions(),        // Today · Live and Compare with… (modes.js)
  { label: "Colour theme: next", hint: "", run: cycleTheme },
  { label: "Sidebar: collapse or expand", hint: "[", run: () => document.getElementById("rail-toggle")?.click() },
  { label: "Settings: every settings page", hint: "g ,", run: () => S.set({ tab: "settings" }) },
  ...(model?.canRefresh ? [{ label: "Refresh now: recount today", hint: "", run: () => document.querySelector(".bar .refresh")?.click() }] : []),
  { label: "Report builder: print, PDF or download", hint: "", run: () => builder(model, S.read(), (next) => load(next, { previous: model })) },
  { label: "What's new", hint: "", run: () => whatsNew(document.querySelector(".new-dot")) },
  { label: "Keyboard shortcuts", hint: "?", run: help },
  { label: "Help: every guide", hint: "", group: "Help", run: () => S.set({ tab: "help", part: "" }) },
];

// Pages without figures keep only their title and the buttons that always apply; a section's tab says so itself (figures: false).
const NO_DATA = new Set(["about", "help", "settings/api", "settings/users", "settings/team", "settings/account", ...S.ACCOUNT_TABS]);
const noData = (s) => NO_DATA.has(s.tab) || opt(s.tab, "figures", s, true) === false;
let chip = null;            // the phone's site button (nav.js siteChip), made once
function drawBar(s) {
  // A section's tab is named by its section here; the tab strip under the bar names the tab.
  const name = S.sectionOf(s.tab)?.name || S.nameOf(s.tab);
  // Left: the menu button (phones), the section and the drill-down trail.
  const chain = chainOf(s);
  const last = chain[chain.length - 1];
  // The trail: the group or the parent (nav.js trailOf), the page, then the drill-down's last step.
  const trail = trailOf(s.tab);
  chip = chip || siteChip();
  const title = h("div", { class: "tb-title" },
    h("button", { type: "button", class: "btn icon menu-btn", id: "menu-btn", html: MENU, "aria-label": "Open the menu", "aria-expanded": "false", "aria-controls": "rail", onclick: openDrawer }),
    chip,
    h("nav", { class: "trail", "aria-label": "You are here" }, h("ol", null,
      trail.slice(0, -1).map(([words, key, cls]) => h("li", { class: cls || null }, key
        ? h("button", { type: "button", class: "crumb", onclick: () => S.set({ tab: key }) }, words) : h("span", { class: "crumb" }, words))),
      h("li", null, chain.length ? h("button", { type: "button", class: "crumb", onclick: () => S.set({ dd: "" }) }, name) : h("span", { class: "crumb now", "aria-current": "page" }, name)),
      last ? h("li", null, h("span", { class: "crumb now", "aria-current": "page" }, `${DIMS[last[0]].name}: ${said(last[0], last[1])}`)) : null)));

  // Middle: the modes (Today · Live, Compare with…: modes.js), the period, the page group, the filters.
  // Today is the "Today · Live" switch (modes.js), so the period bar starts at Yesterday.
  const range = segmented(S.RANGES.filter(([k]) => k !== "today"), s.range, (k) => {
    if (k === "custom") { const r = rangeOf(model, s); S.set({ range: "custom", from: r.first, to: r.last }); } else S.set({ range: k });
  }, "Date range");
  // Compare has two periods of its own, and Live is always today so far: the period above does not apply there.
  const ranged = opt(s.tab, "ranged", s, true);
  const mid = [h("div", { class: "bar-modes", id: "bar-modes" }, barModes(model, s)), ranged ? range : null].filter(Boolean);
  if (ranged && s.range === "custom") {
    const lo = model.firstDay || model.anchor, hi = model.anchor;
    const from = h("input", { type: "date", value: s.from, min: lo, max: hi, "aria-label": "From" });
    const to = h("input", { type: "date", value: s.to, min: lo, max: hi, "aria-label": "To" });
    const apply = () => { if (from.value && to.value && from.value <= to.value) S.set({ from: from.value, to: to.value }, { replace: true }); };
    from.addEventListener("change", apply);
    to.addEventListener("change", apply);
    mid.push(h("span", { class: "ctl dates" }, from, "to", to));
  }
  const views = viewList(model);
  if (views.length > 1) {
    const sel = h("select", { "aria-label": "Page group", title: "Page group" }, views.map(([k, nm]) => h("option", { value: k, selected: k === s.view }, nm)));
    sel.addEventListener("change", () => S.set({ view: sel.value }));
    mid.push(h("label", { class: "ctl view-sel" }, h("span", { class: "vh" }, "Page group"), sel));
  }
  mid.push(filtersPop(s));

  // Right: saved views, refresh, export, alerts, the palette; and "more" for what a narrow screen hides.
  // (The compare toggle became "Compare with…" in the modes' slot, 2.7.0.)
  const right = [h("div", { class: "wide-only" }, saved())];
  const live = model.live?.generated_at && model.live.day === model.today;
  if (model.canRefresh) {
    const btn = h("button", { type: "button", class: "btn refresh", html: ICON.refresh, title: "Recount today now" }, h("span", { class: "r-l" }, "Refresh"),
      live ? h("span", { class: "r-ago" }, ago(model.live.generated_at)) : null);
    btn.addEventListener("click", () => doRefresh(btn));
    right.push(btn);
  } else right.push(h("span", { class: "stamp" }, model.stamp));
  right.push(h("div", { class: "wide-only" }, exportMenu(() => model, s, (next) => load(next, { previous: model }))));
  const helpBtn = h("a", { class: "btn icon help-btn", href: "#help", html: HELP_ICON, "aria-label": "Help and guides", title: "Help and guides" });
  const always = [...searchBox(), helpBtn, bell(model), h("button", { type: "button", class: "btn icon kbd-btn", html: CMDK, "aria-label": "Command palette (Ctrl or Cmd + K)", title: "Go to, or do (Ctrl K)", "aria-keyshortcuts": "Control+K Meta+K", onclick: () => palette(actions()) })];
  right.push(...always);
  right.push(moreMenu(s));

  // Active filters, each removable on its own; greyed where this tab cannot apply it.
  const support = opt(s.tab, "filters", s, []);
  const chips = h("div", { class: "chips", "aria-label": "Active filters" }, S.activeFilters(s).map(([k, v]) => {
    const words = k === "path" ? `${s.pathmode === "starts" ? "starts with" : "contains"} ${v}` : v;
    return h("span", { class: `chip${support.includes(k) ? "" : " off"}` }, FILTER_LABEL[k], " ", h("b", null, k === "country" ? flagEl(v) : null, words),
      h("button", { type: "button", "aria-label": `Remove the ${FILTER_LABEL[k].toLowerCase()} filter`, onclick: () => S.set({ [k]: "" }) }, "×"));
  }));
  // A page with no figures (About) keeps only its title, the bell and the palette.
  if (noData(s)) bar.replaceChildren(h("div", { class: "bar-row" }, title, h("div", { class: "bar-mid" }), h("div", { class: "bar-right" }, always.filter(Boolean))));
  else bar.replaceChildren(h("div", { class: "bar-row" }, title, h("div", { class: "bar-mid" }, mid), h("div", { class: "bar-right" }, right.filter(Boolean))), chips);
  fitBar();
  const open = (model.x?.alerts?.open || []).length;
  badge("site", open, `${open} open alert${open === 1 ? "" : "s"}`);
}

/* The bar never overlaps itself. When the middle (period, page group, filters)
   does not fit between the trail and the buttons, the trail's group and parent
   and the refresh words give way first ("tight"); if that is not enough, the
   middle takes a row of its own ("two-rows"). Measured, not guessed by width:
   a long page name, an admin's extra buttons or a wider search all count.
   Phones (below 768px) have their own two-row bar. */
const wideBar = matchMedia("(min-width: 768px)");
function fitBar() {
  const row = bar.querySelector(".bar-row"), mid = row?.querySelector(".bar-mid");
  bar.classList.remove("tight", "tighter", "two-rows");
  watchBar(row?.querySelector(".bar-right"));
  if (!mid || !wideBar.matches) return;
  const over = () => mid.scrollWidth > mid.clientWidth + 1 || row.scrollWidth > row.clientWidth + 1;
  if (!over()) return;
  bar.classList.add("tight");
  if (!over()) return;
  // Then the Export button's word (its icon and name stay), so a longer section name keeps one row.
  bar.classList.add("tighter");
  if (!over()) return;
  bar.classList.remove("tight", "tighter");
  bar.classList.add("two-rows");
  if (over()) bar.classList.add("tight");
}
// Fitted again when the bar's width changes (window, sidebar) or its buttons' (the search opening).
const barSizes = new WeakMap();
const barRO = window.ResizeObserver ? new ResizeObserver((list) => {
  let moved = false;
  for (const e of list) {
    const w = Math.round(e.contentRect.width);
    if (barSizes.get(e.target) !== w) { barSizes.set(e.target, w); moved = true; }
  }
  if (moved) fitBar();
}) : null;
let watched = null;
function watchBar(right) {
  if (!barRO || right === watched) return;
  if (watched) barRO.unobserve(watched);
  barRO.observe(bar);
  if (right) { barRO.observe(right); barSizes.set(right, Math.round(right.getBoundingClientRect().width)); }
  watched = right;
}

// The "more" menu: markers always; saved views and export too when the screen hides their buttons.
function moreMenu(s) {
  const toggle = h("button", { type: "button", class: "btn icon", html: MORE, "aria-label": "More", "aria-haspopup": "menu", "aria-expanded": "false", title: "More" });
  const item = (text, sub, fn, cls = "") => h("button", { type: "button", role: "menuitem", class: `menu-i ${cls}`, onclick: () => { pop.hidden = true; toggle.setAttribute("aria-expanded", "false"); fn(); } },
    h("b", null, text), sub ? h("small", null, sub) : null);
  const pop = h("div", { class: "pop menu", role: "menu", hidden: true, "aria-label": "More" });
  pop.append(
    item(`Markers on charts: ${marksOn() ? "on" : "off"}`, "releases and changes, as dashed lines", () => { store.set("ti-marks", !marksOn()); setMarkers(markersByDay(model), marksOn()); render(current, { keepScroll: true }); }),
    item("Saved views", "keep this tab, period and filters under a name", savedDialog, "narrow-only"),
    item("Tables on this tab (ZIP)", "every table, as CSV files", () => exportZip(model, s), "narrow-only"),
    item("This tab as JSON", "the tables and the period's totals", () => exportJSON(model, s), "narrow-only"),
    item("Print this tab", "choose Save as PDF to keep it", () => printTab(model, s), "narrow-only"),
    item("Report builder", "sections, period, page group, filters", () => builder(model, s, (next) => load(next, { previous: model }))));
  const wrap = popover(toggle, pop, () => [...pop.querySelectorAll(".menu-i")].find((x) => x.offsetParent !== null)?.focus());
  pop.addEventListener("keydown", (e) => {
    const items = [...pop.querySelectorAll(".menu-i")].filter((x) => x.offsetParent !== null), i = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length]?.focus(); }
  });
  return wrap;
}

async function doRefresh(btn) {
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  const res = await postRefresh(model);
  try {
    if (res.ok) {
      model = await load(S.read(), { fresh: true, previous: model });
      toast(res.recent ? "Updated a moment ago; showing the latest figures" : "Today's figures recounted");
      render(S.read(), { keepScroll: true, changed: true });
    } else toast(res.message);
  } finally {
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
  }
}

// ------------------------------------------------------------- the footer
/* One quiet line: what is deployed, how fresh the figures are, where
   addresses appear, help and the plain page. Returns its clock. */
function footer() {
  const foot = document.getElementById("foot");
  const fresh = h("span", { class: "fresh" });
  const tick = () => {
    const L = model.live;
    if (!L?.generated_at || L.day !== model.today) { fresh.textContent = `data recorded to ${model.anchor}`; return; }
    if (DEMO.on) { fresh.textContent = `sample data, updated ${tzTime(L.generated_at, { label: false })}`; return; }
    const next = Date.parse(L.generated_at) + 120000 - Date.now();
    fresh.textContent = `data updated ${tzTime(L.generated_at, { label: false })} · next ${next > 0 ? `in ${Math.max(1, Math.round(next / 60000))} min` : "any moment"}`;
  };
  tick();
  setInterval(tick, 15000);
  // Left: what is running and how fresh it is. Right: About, Help, and the privacy note behind an (i).
  const ver = () => releaseLine(model?.releaseZones);
  const build = h("span", { class: "build", title: ver().title }, ver().text);
  // No build.json, no release words: the line starts at the data's freshness, with no separator before it.
  const sep = h("span", { "aria-hidden": "true", hidden: !ver().text }, " · ");
  foot.replaceChildren(h("div", { class: "foot-line" },
    h("p", { class: "foot-left" }, build, sep, fresh),
    h("p", { class: "foot-right" }, h("a", { class: "linkish", href: "#about" }, "About"), h("a", { class: "linkish", href: "#help" }, "Help"),
      h("a", { class: "linkish", href: REPO, target: "_blank", rel: "noopener", title: "Skald on GitHub: source, releases, issues. A star helps others find it." }, "★ GitHub"),
      h("span", { class: "privacy" }, "Privacy", info(PRIVACY, "Privacy")))));
  return () => { tick(); const v = ver(); build.textContent = v.text; build.title = v.title; sep.hidden = !v.text; };
}
let footTick = () => {};

// What a printed page says at its top (hidden on screen): site, tab, period, filters.
function printHead(s, name) {
  const r = rangeOf(model, s);
  const f = S.activeFilters(s).map(([k, v]) => `${FILTER_LABEL[k]}: ${k === "country" ? withFlag(v) : v}`).join("; ");
  return h("div", { class: "print-head", "aria-hidden": "true" }, h("b", null, `${model.site}: ${name}`),
    ` ${r.kind === "today" ? `today so far, ${model.today}` : `${r.first} to ${r.last}`}${f ? `. Filters: ${f}` : ""}. Printed ${new Date().toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}.`,
    buildLine() ? h("span", { class: "ph-build" }, ` ${buildLine()}`) : null);
}
// Ctrl+P on a tab prints every row of its tables, not only the first page of them.
addEventListener("beforeprint", () => { if (current && !document.body.classList.contains("reporting")) { showAllRows(true); render(current, { keepScroll: true }); } });
addEventListener("afterprint", () => { if (current && !document.body.classList.contains("reporting")) { showAllRows(false); render(current, { keepScroll: true }); } });

// ------------------------------------------------------------------ router
// The data file a tab stands on, beyond the core files that are always built: its `file` (js/tabs/s-*.js).
function notBuilt(name, file, error) {
  const since = model.x.quality?.builders_failing?.find((b) => b.file === `${file}.json` || b.file === file)?.since;
  return [h("div", { class: "head" }, h("h1", null, name)),
    h("div", { class: "state warn", role: "alert", html: ICON.info }, h("div", null, h("strong", null, `${name} could not be built on the last redraw. `),
      `Its data file (${file}.json) failed${since ? ` since ${tzTime(since, { date: true })}` : ""}: ${error}. Nothing is shown rather than empty figures; Data quality lists every file that failed, and the next redraw tries again.`))];
}

async function render(s, { keepScroll = false, changed = false } = {}) {
  const prev = current;
  current = s;
  const viewChanged = prev && prev.view !== s.view;
  if (viewChanged) {
    app.classList.add("loading");
    try { model = await load(s, { previous: model }); } catch (e) { return fail(e); } finally { app.classList.remove("loading"); }
  }
  untip();
  // A page's drawers (drill-down, request detail) belong to the render that opened them.
  closeDrawers("page");
  setZone(s.tz, model.tz);
  mark(s.tab);
  drawBar(s);
  footTick();
  setMarkers(markersByDay(model), marksOn());
  setFavicons(model.x?.favicons, "data/");
  REGISTRY.length = 0;
  setContext(model, s);
  const name = S.nameOf(s.tab), sec = S.sectionOf(s.tab);
  document.title = `${model.site} · ${sec ? `${name} · ${sec.name}` : name} — ${toolName()}`;
  const file = opt(s.tab, "file", s, null), broken = file && model.failed?.[file];
  const body = broken ? notBuilt(name, file, broken)
    : DEMO.on && S.inSettings(s.tab) ? demoState(name) : DEMO.on && opt(s.tab, "helper", s, false) ? demoState(name) : TAB_RENDER[s.tab](model, s, { first: firstPaint, changed });
  // modeBanner: while Compare is on, what A and B are, or why not (modes.js).
  const banners = [demoBanner(), updateBanner(), planBanner(), modeBanner(model, s)].filter(Boolean);
  const content = [body].flat(Infinity).filter(Boolean);
  if (sec) {
    // A section: its tabs right under the bar's title, the notices and the chosen tab's page in the strip's panel.
    const tabs = sec.tabs.filter(([k]) => S.shown(k)).map(([k, nm]) => {
      const [count, countLabel] = TAB[k].badge?.(model) || [];
      return { key: k, name: nm, href: S.hashFor({ ...s, tab: k, dd: "" }), count, countLabel };
    });
    const strip = tabStrip(tabs, s.tab, (k) => S.set({ tab: k }), { label: sec.name });
    strip.panel.append(...banners, ...content);
    panel.replaceChildren(printHead(s, `${sec.name}: ${name}`), strip.root);
  } else panel.replaceChildren(printHead(s, name), ...banners, ...content);
  quietKpis(panel);
  const tabChanged = !prev || prev.tab !== s.tab;
  if (tabChanged && !reduced()) {
    panel.classList.remove("enter");
    void panel.offsetWidth;
    panel.classList.add("enter");
  }
  if (tabChanged && !keepScroll && !firstPaint) {
    window.scrollTo({ top: 0, behavior: "auto" });
  }
  firstPaint = false;
  drillView(model, s);
}

function fail(e) {
  app.dataset.state = "error";
  panel.replaceChildren(h("div", { class: "state bad", role: "alert", html: ICON.info },
    h("div", null, h("strong", null, "The figures could not be loaded. "),
      `${e && e.message ? e.message : e}. The plain page has the same figures: `, h("a", { href: "classic.html" }, "open the plain page"), ".")));
}

async function boot() {
  buildNav();
  keys(actions);
  const s = S.read();
  try {
    [model] = await Promise.all([load(s), loadBuild()]);
  } catch (e) {
    return fail(e);
  }
  // The sidebar: the site button (its logo, its name, the tool's name from build.json), which
  // opens the site switcher; the tab's icon becomes the site's (nav.js brand, logo.js). Its foot below.
  brand(model.site, model.x.sites, toolName());
  await loadMe(model);
  setZone(s.tz, model.tz);
  // The sidebar's foot: Settings opens the settings pages (their own menu); the round
  // button beside it holds the reader's choices: theme, time zone, help, sign out.
  const dot = h("span", { class: "new-dot", "aria-hidden": "true", hidden: !newUnseen() });
  const row = (text, fn, extra) => h("button", { type: "button", class: "menu-i set-i", onclick: fn }, h("b", null, text), extra || null);
  const seg = h("div", { class: "seg theme-seg", role: "group", "aria-label": "Colour theme" }, THEMES.map(([k, nm]) =>
    h("button", { type: "button", "data-t": k, "aria-pressed": "false", onclick: () => theme(k) }, nm)));
  // Theme and What's new also sit in the foot itself, one click away.
  const themeIcon = { light: SUN, dark: MOON, system: AUTO };
  const themeNow = () => document.documentElement.getAttribute("data-theme") || "system";
  const themeBtn = h("button", { type: "button", class: "foot-btn quick", id: "foot-theme" });
  const showTheme = () => {
    const t = themeNow(), name = (THEMES.find(([k]) => k === t) || [t, t])[1];
    themeBtn.innerHTML = themeIcon[t] || AUTO;
    themeBtn.title = `Theme: ${name}. Click to change.`;
    themeBtn.setAttribute("aria-label", `Theme: ${name}. Change theme`);
  };
  themeBtn.addEventListener("click", () => { cycleTheme(); showTheme(); });
  showTheme();
  const newDot = h("span", { class: "new-dot", "aria-hidden": "true", hidden: !newUnseen() });
  const newBtn = h("button", { type: "button", class: "foot-btn quick", id: "foot-new", title: "What's new", "aria-label": "What's new",
    html: SPARK }, newDot);
  newBtn.addEventListener("click", () => whatsNew(newDot));
  const who = ME.name || ME.user || "";
  const initials = who.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  railFoot([
    who ? h("p", { class: "set-who" }, "Signed in as ", h("b", null, who), ME.role ? ` (${ME.role})` : "") : h("p", { class: "pop-h" }, "Your choices"),
    h("div", { class: "set-row" }, h("span", null, "Theme"), seg),
    h("div", { class: "set-row" }, h("span", null, "Time zone"), zonePicker(s)),
    sessions() ? h("a", { class: "menu-i set-i", href: "#settings/account" }, h("b", null, "Your account"), h("small", null, "name, password, two-step sign-in")) : null,
    h("a", { class: "menu-i set-i", href: "#settings" }, h("b", null, "All settings"), h("small", null, "every settings page, in groups")),
    h("hr", { class: "set-rule" }),
    h("a", { class: "menu-i set-i", href: "#help" }, h("b", null, "Help"), h("small", null, "guides: webhooks, API, MCP, leads and more")),
    row("Keyboard shortcuts", help, h("kbd", null, "?")),
    row("What's new", () => whatsNew(dot), dot),
    h("a", { class: "menu-i set-i", href: "#about" }, h("b", null, "About Skald")),
    h("a", { class: "menu-i set-i", href: REPO, target: "_blank", rel: "noopener" }, h("b", null, "★ Skald on GitHub"), h("small", null, "star it, see releases, report a problem")),
    h("a", { class: "menu-i set-i", href: "classic.html" }, h("b", null, "Plain page"), h("small", null, "every figure, without scripts")),
    sessions() ? row("Sign out", signOut) : null,
  ], initials, [themeBtn, newBtn]);
  theme();
  footTick = footer();
  // A new site has no whole day yet: open on today so far rather than an empty month.
  if (!/[?&]range=/.test(location.hash) && ![...model.byDay.values()].some((d) => d.state === "ok") && model.live?.state === "ok") {
    S.set({ range: "today" }, { replace: true });
  }
  app.dataset.state = "ready";
  S.on((next) => render(next));
  S.emit(true);
  // Keep "today" current while the page is open: the live snapshot is rewritten every two minutes.
  setInterval(async () => {
    if (document.hidden) return;
    // A page left open across a release keeps its old screens: offer the new one.
    const newer = await newerBuild();
    if (newer && !document.querySelector(".update")) {
      document.body.append(h("div", { class: "update", role: "status" }, `${toolName()} was updated to release ${newer.release}.`,
        h("button", { type: "button", class: "btn", onclick: () => location.reload() }, "Reload")));
    }
    try {
      const next = await load(S.read(), { fresh: true, previous: model });
      if (next.liveStamp !== model.liveStamp) {
        model = next;
        // A tab that polls on its own (the request log, every 30 seconds) is left alone: a redraw would close its detail panel.
        if (!opt(current.tab, "polls", current, false) && (opt(current.tab, "live", current, false) || current.range === "today")) render(S.read(), { keepScroll: true, changed: true });
        else { drawBar(current); footTick(); }
      }
    } catch { /* keep the frame; the next tick tries again */ }
  }, 120000);
}

boot();
