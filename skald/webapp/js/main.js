// Boot, the top bar and the tab router. The sidebar, its drawer and the
// phone's tab bar are nav.js's.
//
// The top bar, one slim row, the approved mockup's seven (the UX audit's tasks 2 and 5):
// the section's title; the period, one group (Today, live; 7, 30, 90 days; More, with
// Yesterday, All time and Custom inside it); Compare (modes.js, on by default, only on a
// tab that compares); then on the right the filter (an icon; the page group is inside),
// the one search (the command palette), the alerts and More (recount today, saved views,
// export, markers). Active filters and the page group make a second row, only when there
// are some.

import * as S from "./state.js";
import { h, ICON, reduced, toast, untip, short } from "./ui.js";
import { load, refresh as postRefresh, rangeOf, markersByDay, has, need } from "./data.js";
import { TAB_RENDER } from "./tabs/index.js";
import { framed } from "./tabs/settings-frame.js";
import { TAB, opt, tabFiles } from "./sections.js";
import { tabStrip } from "./tabstrip.js";
import { barModes, modeBanner, modeActions, liveSegment, setLive } from "./modes.js";
import { country, countryName, withFlag, city, cityCode, cityName } from "./tabs/readers.js";
import { setMarkers } from "./charts.js";
import { savedDialog, bell, marksOn, zonePicker, store } from "./extras.js";
import { needsYou } from "./alert-groups.js";
import { setZone, time as tzTime } from "./tz.js";
import { keys, help, whatsNew, newUnseen, palette } from "./keys.js";
import { drillView } from "./drillview.js";
import { closeDrawers } from "./drawer.js";
import { sync as syncOverlays, addRestorer } from "./overlays.js";
import { setSiteBase } from "./urlactions.js";
import { chainOf, DIMS, said, titled, close as closeDrill } from "./drill.js";
import { setFavicons } from "./icons.js";
import { REGISTRY, showAllRows } from "./table.js";
import { openExport } from "./export-dialog.js";
import { setContext } from "./tabs/common.js";
import { loadBuild, buildLine, toolName, newerBuild, releaseLine, BUILD, REPO } from "./build.js";
import { openSearch, openPerson, mayFind, SEARCH_HINT } from "./tabs/person.js";
import { findIndex } from "./finder.js";
import { showSetup } from "./tabs/checklist.js";
import { shown } from "./labels.js";
import { info, quietKpis } from "./tabs/tiles.js";
import { PRIVACY } from "./tabs/about.js";
import { buildNav, mark, badge, brand, siteChip, railFoot, openDrawer, trailOf } from "./nav.js";
import { ME, loadMe, sessions, signOut } from "./access.js";
import { planBanner } from "./tabs/billing.js";
import { updateBanner } from "./updates.js";
import { welcomeBanner } from "./welcome.js";
import { DEMO, demoBanner, demoState, demoTab } from "./demo.js";
import { startEdges } from "./edges.js";
import { filtersButton, filterChips, rulesBanner, openFilters } from "./filterpanel.js";
import { fromState, treeWords } from "./rules.js";
import { afterMark } from "./tabs/leadref.js";
import { setRedraw } from "./ui/live.js";
import { crumbLine, crumbUpdate, restore as restoreScroll, start as startCrumbs } from "./crumbs.js";

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
/* `tail`: a last button in the group that is not a period (the period's More). The group is
   one stop for the keyboard: Tab reaches the chosen period, the arrows, Home and End move
   along the group, Enter or Space picks. */
function segmented(options, value, onPick, label, tail = null) {
  const ind = h("span", { class: "seg-ind", "aria-hidden": "true" });
  const btns = options.map(([k, name]) => h("button", { type: "button", "aria-pressed": String(k === value), onclick: () => onPick(k) }, name));
  const all = tail ? [...btns, tail] : btns;
  const seg = h("div", { class: "seg", role: "group", "aria-label": label }, ind, all);
  const stop = btns.find((b) => b.getAttribute("aria-pressed") === "true") || all[0];
  all.forEach((b) => { b.tabIndex = b === stop ? 0 : -1; });
  seg.addEventListener("keydown", (e) => {
    const i = all.indexOf(document.activeElement);
    const to = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: all.length - 1 }[e.key];
    if (i < 0 || to === undefined) return;
    e.preventDefault();
    const next = all[(to + all.length) % all.length];
    all.forEach((b) => { b.tabIndex = b === next ? 0 : -1; });
    next.focus();
  });
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

const MORE = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><circle cx="3.5" cy="8" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="12.5" cy="8" r="1.4"/></svg>';
const MENU = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2.5 4h11M2.5 8h11M2.5 12h11"/></svg>';
const CMDK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="7" cy="7" r="4.3"/><path d="M10.2 10.2l3.6 3.6"/></svg>';

// A button and its popover: open, close on Escape or a press outside, focus back on close.
// `host`: an element that already holds the button (the period group); the popover goes in it.
function popover(toggle, pop, onOpen, host = null) {
  const wrap = host || h("div", { class: "more" }, toggle, pop);
  if (host) host.append(pop);
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

/* What the palette searches in the figures (finder.js): the names seen in the period
   on screen (today: the live count), the days kept before it when the period has
   none, and a person for an admin (the same search as Find a person). */
const finds = () => {
  if (!model) return null;
  const s = S.read(), r = rangeOf(model, s);
  // A country shown by its flag and three letters (a city as the Cities table says it), found by its full name too ("canada").
  const say = (dim, v) => (dim === "country" ? withFlag(v, country(v)) : dim === "city" ? withFlag(cityCode(v), city(v)) : shown(v));
  const alias = (dim, v) => (dim === "country" ? countryName(v) : dim === "city" ? cityName(v) : "");
  const live = model.live?.state === "ok" && model.live.day === model.today ? [model.live.figures] : [];
  const days = r.kind === "today" ? live : r.days.filter((d) => d.state === "ok");
  const period = r.kind === "today" ? "today so far" : r.length === 1 ? short(r.first) : `${short(r.first)} to ${short(r.last)}`;
  return { entries: findIndex(days, say, alias), period, earlier: () => findIndex([...model.byDay.values()].filter((d) => d.state === "ok"), say, alias),
    person: mayFind() ? openPerson : null };
};

const actions = () => [
  ...(mayFind() ? [{ label: `Find a person: ${SEARCH_HINT}`, hint: "", run: openSearch }] : []),
  ...modeActions(),        // Today · Live and Compare with… (modes.js)
  { label: "Filters: rules over every dimension, saved views", hint: "", run: () => openFilters(model, S.read(), document.querySelector(".fp-btn")) },
  { label: "Colour theme: next", hint: "", run: cycleTheme },
  { label: "Sidebar: collapse or expand", hint: "[", run: () => document.getElementById("rail-toggle")?.click() },
  { label: "Settings: what needs you (To do)", hint: "g ,", run: () => S.set({ tab: "settings" }) },
  // 2.40: the settings people looked for and could not find, by the words they would type (v2 addresses).
  ...(S.shown("settings/ai/assistants") ? [{ label: "MCP: connect Claude, ChatGPT or another AI assistant", hint: "", group: "Settings, AI", run: () => S.set({ tab: "settings/ai/assistants", sub: "" }) },
    { label: "API: read your figures from a script", hint: "", group: "Settings, AI", run: () => S.set({ tab: "settings/ai/assistants", sub: "api" }) },
    { label: "Tokens: see or revoke a token", hint: "", group: "Settings, AI", run: () => S.set({ tab: "settings/ai/assistants", sub: "tokens" }) }] : []),
  ...(S.shown("settings/site/data") ? [{ label: "Script tag: copy it, goals", hint: "", group: "Settings, This site", run: () => S.set({ tab: "settings/site/data", sub: "script" }) },
    { label: "Test a sample of a log", hint: "", group: "Settings, This site", run: () => S.set({ tab: "settings/site/data", sub: "sample" }) }] : []),
  ...(S.shown("settings/site/details") ? [{ label: "Internal traffic: your own machines", hint: "", group: "Settings, This site", run: () => S.set({ tab: "settings/site/details", sub: "internal" }) }] : []),
  ...(S.shown("settings/org/sites") ? [{ label: "Sites: add, pause, remove or delete a site", hint: "", group: "Settings, Organisation", run: () => S.set({ tab: "settings/org/sites" }) }] : []),
  ...(S.shown("settings/org/people") ? [{ label: "Invite someone to the team", hint: "", group: "Settings, Organisation", run: () => S.set({ tab: "settings/org/people", sub: "" }) }] : []),
  ...(model?.canRefresh ? [{ label: "Refresh now: recount today", hint: "", run: () => refreshNow() }] : []),
  { label: "Export: a PDF, the tables as CSV, a report by mail or JSON", hint: "", run: () => openExport(model, S.read(), (next) => load(next, { previous: model })) },
  ...(!DEMO.on && sessions() && (["owner", "admin"].includes(ME.role) || ME.install_admin) ? [{ label: "Setup checklist: show it again on Overview", hint: "", run: () => showSetup(model.site) }] : []),
  { label: "What's new", hint: "", run: () => whatsNew(document.querySelector(".new-dot")) },
  { label: "Keyboard shortcuts", hint: "?", run: help },
  { label: "Help: every guide", hint: "", group: "Help", run: () => S.set({ tab: "help", part: "" }) },
];

// Pages without figures keep only their title and the buttons that always apply; a section's tab says so itself (figures: false).
// Every settings page is a form, not figures: no period, page group or filters there.
const NO_DATA = new Set(["about", "help"]);
const noData = (s) => NO_DATA.has(s.tab) || S.inSettings(s.tab) || opt(s.tab, "figures", s, true) === false;

/* A tab with a period of its own (Real time, Insights, Alerts, the request log...):
   the period bar does not apply there, so it is not shown; a fixed chip says the
   tab's own period instead (the tab's `period` option, s-*.js). Never a picker
   that is ignored. */
function periodChip(s) {
  const p = TAB[s.tab]?.period;
  const words = typeof p === "function" ? p(s, model) : p;
  if (!words) return null;
  return h("span", { class: "period-chip", role: "note", title: `${words}: this tab keeps its own period, so the date range does not apply here` },
    h("span", { class: "pc-l" }, "Period"), h("b", null, words));
}
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
      h("li", null, chain.length ? h("button", { type: "button", class: "crumb", onclick: closeDrill }, name) : h("span", { class: "crumb now", "aria-current": "page" }, name)),
      last ? h("li", null, h("span", { class: "crumb now", "aria-current": "page", title: last[0] === "country" || last[0] === "city" ? titled(last[0], last[1]) : null }, `${DIMS[last[0]].name}: ${said(last[0], last[1])}`)) : null)));

  // Middle: the period and Compare (modes.js, only on a tab that compares).
  // One group, Today (live) · 7 · 30 · 90 days · More (Yesterday, All time, Custom; the one
  // picked shows in the group while it is the period). The page group is in the Filters
  // panel, and shows as a chip while one is chosen.
  const pickRange = (k) => {
    if (k === "today") return setLive(true, s);
    if (k === "custom") { const r = rangeOf(model, s); S.set({ range: "custom", from: r.first, to: r.last }); } else S.set({ range: k });
  };
  const more = rangeMore(s, pickRange);
  const range = h("div", { class: "bar-range" },
    segmented(S.RANGES.filter(([k]) => k === "today" || MAIN_RANGES.includes(k) || k === s.range).map(([k, nm]) => [k, k === "today" ? liveSegment(model, s) : nm]),
      s.range, pickRange, "Date range", more.toggle));
  popover(more.toggle, more.pop, () => more.pop.querySelector(".menu-i")?.focus(), range);
  // Compare has two periods of its own, and Live is always today so far: the period above does not apply there.
  const ranged = opt(s.tab, "ranged", s, true);
  const modes = barModes(model, s);
  const mid = [ranged ? range : periodChip(s), modes.length ? h("div", { class: "bar-modes", id: "bar-modes" }, modes) : null].filter(Boolean);
  if (ranged && s.range === "custom") {
    const lo = model.firstDay || model.anchor, hi = model.anchor;
    const from = h("input", { type: "date", value: s.from, min: lo, max: hi, "aria-label": "From" });
    const to = h("input", { type: "date", value: s.to, min: lo, max: hi, "aria-label": "To" });
    const apply = () => { if (from.value && to.value && from.value <= to.value) S.set({ from: from.value, to: to.value }, { replace: true }); };
    from.addEventListener("change", apply);
    to.addEventListener("change", apply);
    mid.push(h("span", { class: "ctl dates" }, from, "to", to));
  }

  // Right (the UX audit's task 2): the filter, one search, the alerts, and More. Refresh, saved
  // views and export are in More; Help is in the menu (one door each). The search is the palette:
  // it finds pages, sources and countries, goes anywhere and, for an admin, finds a person (2.13).
  const right = [];
  if (!model.canRefresh) right.push(h("span", { class: "stamp" }, model.stamp));
  const filters = filtersButton(model, s);
  filters.title = "Filters: rules over every dimension, the page group, saved views";
  right.push(filters);
  const always = [h("button", { type: "button", class: "btn kbd-btn ui-search", "aria-label": "Search or jump to (Ctrl or Cmd + K)", title: "Search pages, sources, countries, a person, or go anywhere (Ctrl K)", "aria-keyshortcuts": "Control+K Meta+K", onclick: () => palette(actions(), finds) },
    h("span", { class: "ui-search-ic", html: CMDK, "aria-hidden": "true" }), h("span", { class: "ui-search-l" }, "Search or jump to"), h("kbd", { class: "ui-search-k", "aria-hidden": "true" }, "Ctrl K")), bell(model)];
  right.push(...always);
  right.push(moreMenu(s));

  // Active filters (the single ones and the advanced rules), each removable on its own;
  // greyed where this tab cannot apply it (filterpanel.js).
  // A tab that draws them itself (chips: "tab", Leads) has them in its own "Filtered by" line.
  const chips = filterChips(model, s, { noData: noData(s) || opt(s.tab, "chips", s, "") === "tab" });
  // A page with no figures (About) keeps only its title, the bell and the palette.
  if (noData(s)) bar.replaceChildren(h("div", { class: "bar-row" }, title, h("div", { class: "bar-mid" }, periodChip(s)), h("div", { class: "bar-right" }, always.filter(Boolean))));
  else bar.replaceChildren(h("div", { class: "bar-row" }, title, h("div", { class: "bar-mid" }, mid), h("div", { class: "bar-right" }, right.filter(Boolean))), chips);
  fitBar();
  // The Site badge counts what needs you (alert-groups.js), as the bell and Site › Alerts do.
  const open = (model.x?.alerts?.open || []).length, need = needsYou(model.x?.alerts);
  badge("site", need, `${need} alert${need === 1 ? "" : "s"} need${need === 1 ? "s" : ""} you (${open} open)`);
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
  const live = model.live?.generated_at && model.live.day === model.today;
  pop.append(...[
    model.canRefresh ? item("Recount today now", live ? `today's figures, counted ${ago(model.live.generated_at)}` : "today's figures, from the log", () => refreshNow()) : null,
    item("Saved views", "keep this tab, period and filters under a name", savedDialog),
    item("Export", "a PDF, the tables as CSV, a report by mail or JSON", () => openExport(model, s, (next) => load(next, { previous: model }))),
    item(`Markers on charts: ${marksOn() ? "on" : "off"}`, "releases and changes, as dashed lines", () => { store.set("ti-marks", !marksOn()); setMarkers(markersByDay(model), marksOn()); render(current, { keepScroll: true }); }),
  ].filter(Boolean));
  const wrap = popover(toggle, pop, () => [...pop.querySelectorAll(".menu-i")].find((x) => x.offsetParent !== null)?.focus());
  pop.addEventListener("keydown", (e) => {
    const items = [...pop.querySelectorAll(".menu-i")].filter((x) => x.offsetParent !== null), i = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length]?.focus(); }
  });
  return wrap;
}

const MAIN_RANGES = ["7d", "30d", "90d"];
// The other periods, one press away (2.41): Yesterday, All time, Custom. Their button is the
// period group's last (the mockup's "More"); main.js drawBar hangs the menu on the group.
// Include today (inc=1) is not here since 2.43: it is one press on Summary's and Pages' period
// line (period-line.js incSwitch), the two tabs it changes.
function rangeMore(s, onPick) {
  const toggle = h("button", { type: "button", class: "ui-more-range", "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": "More periods", title: "Yesterday, All time, or your own dates" }, "More");
  const pop = h("div", { class: "pop menu", role: "menu", hidden: true, "aria-label": "More periods" },
    S.RANGES.filter(([k]) => k !== "today" && !MAIN_RANGES.includes(k)).map(([k, name]) => h("button", { type: "button", role: "menuitemradio", class: "menu-i", "aria-checked": String(k === s.range),
      onclick: () => { pop.hidden = true; toggle.setAttribute("aria-expanded", "false"); onPick(k); } }, h("b", null, name))));
  return { toggle, pop };
}
// Recount today, from More or the palette: the same as the old Refresh button, with its words.
function refreshNow() {
  const btn = h("button", { type: "button", hidden: true });
  toast("Recounting today's figures…");
  return doRefresh(btn);
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
  const f = treeWords(fromState(s), (d, v) => (d === "country" ? withFlag(v) : v));
  return h("div", { class: "print-head", "aria-hidden": "true" }, h("b", null, `${model.site}: ${name}`),
    ` ${r.kind === "today" ? `today so far, ${model.today}` : `${r.first} to ${r.last}`}${f ? `. Filters: ${f}` : ""}. Printed ${new Date().toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}.`,
    buildLine() ? h("span", { class: "ph-build" }, ` ${buildLine()}`) : null);
}
// Ctrl+P on a tab prints every row of its tables, not only the first page of them.
addEventListener("beforeprint", () => { if (current && !document.body.classList.contains("reporting")) { showAllRows(true); render(current, { keepScroll: true }); } });
addEventListener("afterprint", () => { if (current && !document.body.classList.contains("reporting")) { showAllRows(false); render(current, { keepScroll: true }); } });

/* Filters this tab cannot apply (logs keep each breakdown on its own): said in one
   clear line at the top, with where they do apply (filterpanel.js rulesBanner). */
function filterBanner(s) {
  return noData(s) || opt(s.tab, "chips", s, "") === "tab" ? null : rulesBanner(model, s);
}

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
  // The big files this tab is drawn with (data.js LAZY), when the page does not have them yet:
  // a "Loading" line in the panel meanwhile, never a blank page (2.41). The 2-minute refresh
  // may swap the model while we wait: ask the new one too.
  const want = tabFiles(s.tab, s);
  if (!has(model, want)) {
    panel.replaceChildren(h("div", { class: "state lazy-wait", role: "status", "aria-busy": "true" },
      h("div", null, h("strong", null, `Loading ${S.nameOf(s.tab)}…`), " Its page lists are fetched the first time it opens.")));
    while (!has(model, want)) {
      await need(model, want);
      if (current !== s) return;
    }
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
  setSiteBase(model.site);
  const name = S.nameOf(s.tab), sec = S.sectionOf(s.tab);
  // The area's tint (css/ui.css): the section's key, settings, help or about.
  app.dataset.area = sec ? sec.key : S.inSettings(s.tab) ? "settings" : String(s.tab || "").split("/")[0];
  document.title = `${model.site} · ${sec ? `${name} · ${sec.name}` : name} — ${toolName()}`;
  const file = opt(s.tab, "file", s, null), broken = file && model.failed?.[file];
  const body = broken ? notBuilt(name, file, broken)
    : DEMO.on && demoTab(s.tab) ? TAB_RENDER[s.tab](model, s, { first: firstPaint, changed })
    : DEMO.on && S.inSettings(s.tab) ? framed(s.tab, () => demoState(name))(model, s) : DEMO.on && opt(s.tab, "helper", s, false) ? demoState(name) : TAB_RENDER[s.tab](model, s, { first: firstPaint, changed });
  // modeBanner: while Compare is on, what A and B are, or why not (modes.js).
  const banners = [demoBanner(), welcomeBanner(), updateBanner(), planBanner(), modeBanner(model, s), filterBanner(s)].filter(Boolean);
  const content = [body].flat(Infinity).filter(Boolean);
  if (sec) {
    // A section: its tabs right under the bar's title, the notices and the chosen tab's page in the strip's panel.
    const tabs = sec.tabs.filter(([k]) => S.shown(k)).map(([k, nm]) => {
      const [count, countLabel] = TAB[k].badge?.(model) || [];
      return { key: k, name: nm, href: S.hashFor({ ...s, tab: k, dd: "" }), count, countLabel };
    });
    const strip = tabStrip(tabs, s.tab, (k) => S.set({ tab: k }), { label: sec.name });
    strip.panel.append(...banners, ...content);
    panel.replaceChildren(printHead(s, `${sec.name}: ${name}`), crumbLine(model, s), strip.root);
  // Settings (v2): no trail line; the menu on the left already says where the page is.
  } else panel.replaceChildren(printHead(s, name), ...(S.inSettings(s.tab) ? [] : [crumbLine(model, s)]), ...banners, ...content);
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
  // What the address opens over the tab (a drawer, a dialog: overlays.js), then the drill-down on top.
  syncOverlays(model, s);
  drillView(model, s);
  // Back, Forward, a breadcrumb or a reload: the step's scroll back (crumbs.js).
  restoreScroll();
}

function fail(e) {
  app.dataset.state = "error";
  panel.replaceChildren(h("div", { class: "state bad", role: "alert", html: ICON.info },
    h("div", null, h("strong", null, "The figures could not be loaded. "),
      `${e && e.message ? e.message : e}. The plain page has the same figures: `, h("a", { href: "classic.html" }, "open the plain page"), ".")));
}

async function boot() {
  startCrumbs();
  startEdges();
  buildNav();
  keys(actions, finds);
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
    sessions() ? h("a", { class: "menu-i set-i", href: "#settings/you/account" }, h("b", null, "Your account"), h("small", null, "name, password, two-step sign-in")) : null,
    h("a", { class: "menu-i set-i", href: "#settings" }, h("b", null, "Settings"), h("small", null, "what needs you, then every settings page")),
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
  // A drawer or a dialog opening or closing (its key only) is not a redraw: overlays.js opens or closes it.
  S.on((next) => { if (current && S.onlyOverlay(current, next)) { current = next; syncOverlays(model, next); crumbUpdate(model, next); } else render(next); });
  // 2.42: Export asks what you need (export-dialog.js); the report builder's old links open its PDF path, Change open.
  addRestorer("dlg:export", () => { const s = S.read(); return openExport(model, s, (next) => load(next, { previous: model }), { kind: s.kind, change: s.xch === "1" }); });
  addRestorer("dlg:report", () => openExport(model, S.read(), (next) => load(next, { previous: model }), { kind: "pdf", change: true }));
  // A lead marked test (or not) from a drawer (2.25, leadref.js): the helper drew the files
  // again, so read them and redraw; the row moves to or from Show left out, the counts follow.
  afterMark(async () => {
    try {
      model = await load(S.read(), { fresh: true, previous: model });
      render(S.read(), { keepScroll: true, changed: true });
    } catch { /* the next two-minute tick reads them */ }
  });
  // 2.44: a live state moved past the page's files (ui/live.js redraw: Search connected while
  // its file still said not): read them again, and draw the tab again only when one changed.
  setRedraw(async (names) => {
    const next = await load(S.read(), { fresh: true, previous: model });
    const same = names.every((n) => JSON.stringify(next.x?.[n] ?? null) === JSON.stringify(model.x?.[n] ?? null));
    model = next;
    if (!same && current) render(S.read(), { keepScroll: true, changed: true });
    return !same;
  });
  addRestorer("dlg:filters", () => openFilters(model, S.read(), document.querySelector(".fp-btn")));
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
