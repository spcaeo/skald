// Navigation: the sidebar (brand, grouped sections, its foot), its three
// shapes - full, an icon rail, and on a phone a drawer - the phone's bottom
// tab bar, and the top bar's trail. The rest of the top bar is main.js's.
//
// The sidebar has two menus. The dashboard's: the five sections (2.7.0,
// js/sections.js) - Overview, Traffic, Leads & sales, AI & bots, Site - each
// opening its tabs (the strip under the top bar, main.js); Settings, Help and
// About in the foot. While a settings page is open, Settings' own menu takes
// its place (SETTINGS_MENU), with a way back at its top.
//
//   full   wide screens, unless collapsed ([ or the toggle; remembered)
//   icons  a 64px rail with tooltips; the default below 1100px
//   drawer below 768px: off canvas, opened by the menu button or the tab
//          bar's Menu, with a scrim, a close button, Escape to close and
//          focus kept inside while open

import { h, tip, untip, reduced } from "./ui.js";
import * as S from "./state.js";
import { TAB_ICONS, GEAR } from "./tabs/index.js";
import { store } from "./extras.js";
import { logoOf, tile, setTabIcon } from "./logo.js";

const app = document.getElementById("app");
const rail = document.getElementById("rail");
const list = document.getElementById("tabs");
const scrim = document.getElementById("scrim");
const tabbar = document.getElementById("tabbar");

const nameOf = (k) => S.nameOf(k);
const HELP = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/></svg>';
const BACK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 3.5 5 8l4.5 4.5"/></svg>';
const CLOSE = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
const MENU_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2.5 4h11M2.5 8h11M2.5 12h11"/></svg>';
const PERSON = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.7-2.6 2.6-4 5-4s4.3 1.4 5 4"/></svg>';

const phone = () => matchMedia("(max-width: 767px)").matches;
const narrow = () => matchMedia("(max-width: 1099px)").matches;
const ind = h("div", { class: "tab-ind", "aria-hidden": "true" });

// ------------------------------------------------------------ the shape
let wideChoice = store.get("ti-rail", "full");   // what the reader chose on a wide screen
let narrowOpen = false;                          // the rail opened by hand on a narrow one
function shape() {
  if (phone()) return "drawer";
  if (narrow()) return narrowOpen ? "full" : "icons";
  return wideChoice === "icons" ? "icons" : "full";
}
function apply() {
  const sh = shape();
  app.dataset.rail = sh;
  const t = document.getElementById("rail-toggle");
  if (t) {
    const expanded = sh === "full";
    t.setAttribute("aria-expanded", String(expanded));
    t.setAttribute("aria-label", expanded ? "Collapse the sidebar to icons" : "Expand the sidebar");
    t.title = `${expanded ? "Collapse" : "Expand"} the sidebar ([)`;
  }
  if (sh !== "drawer") closeDrawer(false);
  requestAnimationFrame(() => mark(S.read().tab));
}
export function toggleRail() {
  if (phone()) return drawerOpen() ? closeDrawer(true) : openDrawer();
  if (narrow()) narrowOpen = !narrowOpen;
  else { wideChoice = wideChoice === "icons" ? "full" : "icons"; store.set("ti-rail", wideChoice); }
  apply();
}
addEventListener("resize", () => { if (!narrow()) narrowOpen = false; apply(); });

// ----------------------------------------------------------- the drawer
const drawerOpen = () => app.classList.contains("drawer-open");
const openers = () => [document.getElementById("menu-btn"), document.getElementById("tb-menu")].filter(Boolean);
let opener = null;
export function openDrawer() {
  opener = document.activeElement;
  app.classList.add("drawer-open");
  scrim.hidden = false;
  rail.setAttribute("role", "dialog");
  rail.setAttribute("aria-modal", "true");
  rail.setAttribute("aria-label", "Menu");
  openers().forEach((b) => b.setAttribute("aria-expanded", "true"));
  requestAnimationFrame(() => mark(S.read().tab));
  (list.querySelector('[aria-current="page"]') || list.querySelector("a"))?.focus();
}
export function closeDrawer(focusBack = true) {
  if (!drawerOpen()) return;
  app.classList.remove("drawer-open");
  scrim.hidden = true;
  rail.removeAttribute("role");
  rail.removeAttribute("aria-modal");
  rail.setAttribute("aria-label", "Sections and settings");
  openers().forEach((b) => b.setAttribute("aria-expanded", "false"));
  if (focusBack && opener?.isConnected) opener.focus();
}
scrim.addEventListener("click", () => closeDrawer(true));
rail.addEventListener("keydown", (e) => {
  if (!drawerOpen()) return;
  if (e.key === "Escape") { e.preventDefault(); closeDrawer(true); return; }
  if (e.key !== "Tab") return;
  // Focus stays inside the open drawer.
  const f = [...rail.querySelectorAll("button, a[href], select, input")].filter((x) => x.offsetParent !== null);
  if (!f.length) return;
  if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
  else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
});

// ------------------------------------------------------------- sections
// A link keeps the period and the filters; a plain click stays in the page, a
// Ctrl- or middle-click opens the section in a new tab as any link would.
// A section's link goes to its first tab.
const hrefOf = (key) => S.hashFor({ ...S.read(), tab: S.route(key).tab, dd: "" });
function go(e, key) {
  if (e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  closeDrawer(false);
  S.set({ tab: key });
}
// In the icon rail the name is a tooltip, on hover and on keyboard focus.
function tooltip(el, words) {
  const show = () => { if (app.dataset.rail !== "icons") return; const r = el.getBoundingClientRect(); tip(r.right + 84, r.top + r.height / 2 + 14, words, []); };
  el.addEventListener("pointerenter", show);
  el.addEventListener("focus", show);
  el.addEventListener("pointerleave", untip);
  el.addEventListener("blur", untip);
}
// A row of the menu: a section (key "traffic", opening its first tab) or a settings page.
function link(key) {
  const a = h("a", { href: `#${key}`, id: `tab-${key}`, class: "tab", html: TAB_ICONS[key] || "", "data-tab": key, onclick: (e) => go(e, key) },
    h("span", { class: "tab-name" }, nameOf(key)));
  tooltip(a, nameOf(key));
  return a;
}
function group([heading, keys], i, labelled) {
  const on = keys.filter(S.shown);
  if (!on.length) return null;
  const id = `nav-g-${i}`;
  return h("div", { class: "nav-group", role: "group", "aria-labelledby": labelled ? id : null, "aria-label": labelled ? null : heading },
    labelled ? h("p", { class: "nav-h", id }, heading) : null,
    h("ul", null, on.map((key) => h("li", null, link(key)))));
}
// The sections a reader may open (a section whose every tab is hidden is left out).
const sections = () => S.SECTIONS.filter((x) => x.tabs.some(([k]) => S.shown(k)));

let built = "";                 // which menu is drawn, and for which set of hidden pages
let lastApp = "overview";       // where "Back to the dashboard" returns
function draw(settings) {
  const sig = `${settings}|${[...S.HIDDEN].sort().join()}`;
  if (sig === built) return;
  built = sig;
  list.setAttribute("aria-label", settings ? "Settings" : "Sections");
  list.classList.toggle("in-settings", settings);
  if (!settings) {
    list.replaceChildren(ind, group(["Sections", sections().map((x) => x.key)], 0, false));
    return;
  }
  const back = h("a", { href: "#overview", class: "tab nav-back", id: "nav-back", html: BACK, onclick: (e) => go(e, lastApp) }, h("span", { class: "tab-name" }, "Back to the dashboard"));
  tooltip(back, "Back to the dashboard");
  list.replaceChildren(ind, back, h("p", { class: "nav-title" }, "Settings"), ...S.SETTINGS_MENU.map((g, i) => group(g, i, true)).filter(Boolean));
}

export function buildNav() {
  draw(false);
  // Up and down move between sections, as in a menu; Home and End to the ends.
  list.addEventListener("keydown", (e) => {
    const items = [...list.querySelectorAll(".tab")].filter((x) => x.offsetParent !== null);
    const i = items.indexOf(document.activeElement);
    if (i < 0) return;
    const j = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: items.length - 1 }[e.key];
    if (j == null) return;
    e.preventDefault();
    items[(j + items.length) % items.length].focus();
  });
  // On a phone the drawer has its own close button, beside the brand.
  document.getElementById("brand").append(h("button", { type: "button", class: "btn icon drawer-x", "aria-label": "Close the menu", html: CLOSE, onclick: () => closeDrawer(true) }));
  // The phone's bottom bar: the five sections and Menu (the drawer: Settings, Help, About, the reader's choices).
  tabbar.replaceChildren(...sections().map((x) => h("a", { class: "tb-i", href: `#${x.key}`, "data-tab": x.key, html: TAB_ICONS[x.key] || "", "aria-label": x.short !== x.name ? x.name : null, onclick: (e) => go(e, x.key) },
    h("span", { "aria-hidden": x.short !== x.name ? "true" : null }, x.short))),
  h("button", { type: "button", class: "tb-i", id: "tb-menu", "aria-label": "Menu: settings, help and your choices", "aria-controls": "rail", "aria-expanded": "false", onclick: openDrawer,
    html: MENU_ICON }, h("span", { "aria-hidden": "true" }, "Menu")));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "[" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName) || document.querySelector("dialog[open]")) return;
    e.preventDefault();
    toggleRail();
  });
  apply();
}

/* The current section: the right menu drawn, the section marked for screen
   readers (aria-current) and by the moving indicator, and every link carrying
   the period and filters on screen. A section's link opens its first tab. */
export function mark(key) {
  const settings = S.inSettings(key);
  if (!settings) lastApp = key;
  draw(settings);
  const back = document.getElementById("nav-back");
  if (back) back.href = hrefOf(lastApp);
  const here = S.sectionOf(key)?.key || key;
  let sel = null;
  list.querySelectorAll(".tab[data-tab]").forEach((a) => {
    a.href = hrefOf(a.dataset.tab);
    a.removeAttribute("aria-current");
    if (a.dataset.tab === here) sel = a;
  });
  sel?.setAttribute("aria-current", "page");
  tabbar.querySelectorAll(".tb-i[data-tab]").forEach((b) => { b.href = hrefOf(b.dataset.tab); if (b.dataset.tab === here) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
  // The foot's Settings, Help and About carry the mark of their own pages.
  for (const [id, on] of [["nav-settings", settings], ["nav-help", key === "help"], ["nav-about", key === "about"]]) {
    const b = document.getElementById(id);
    if (b) { if (on) b.setAttribute("aria-current", id === "nav-settings" ? "true" : "page"); else b.removeAttribute("aria-current"); }
  }
  if (!sel || !sel.offsetParent) { ind.style.opacity = "0"; return; }
  const y = sel.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
  ind.style.opacity = "1";
  ind.style.height = `${sel.offsetHeight}px`;
  ind.style.transform = `translateY(${y}px)`;
  if (!reduced()) ind.classList.add("moves");
  // The current page in view, when a long menu scrolls.
  const lr = list.getBoundingClientRect(), sr = sel.getBoundingClientRect();
  if (sr.top < lr.top || sr.bottom > lr.bottom) sel.scrollIntoView({ block: "nearest" });
}

export function badge(key, count, words) {
  const b = document.getElementById(`tab-${key}`);
  if (!b) return;
  b.querySelector(".tab-n")?.remove();
  if (count) b.append(h("span", { class: "tab-n", "aria-label": words }, String(count)));
}

/* The top bar's trail: where the page sits. A section's tab shows the section
   (the tab strip under the bar names the tab); a settings page Settings and its
   group. Returns [[words, key or null, class]], the page last. */
export function trailOf(key) {
  const sec = S.sectionOf(key);
  if (sec) return [[sec.name]];
  const group = S.groupOf(key);
  if (S.inSettings(key)) return [["Settings", "settings"], group !== nameOf(key) ? [group, null, "crumb-g"] : null, [nameOf(key)]].filter(Boolean);
  return [[nameOf(key)]];
}

// ---------------------------------------------------- brand and the foot
/* The site button at the top of the sidebar (2.6.0): the site's logo, its
   name and the tool's; it opens the site switcher - each site with its logo
   and today's visitors, a check on this one, then All sites. In the icon
   rail the logo alone is the button; on a phone the top bar has its own
   (siteChip). The list is sites.json (the helper's, with only the reader's
   sites), else this site alone. */
const CHEV = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 6.5 8 10l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CHECK = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5 6.5 11.5 12.5 4.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
let SITE = { site: "", sites: [] };

function siteMenu() {
  const { site, sites } = SITE;
  const list = sites.length ? sites : [{ name: site, path: null }];
  const today = (x) => (x.today?.visitors != null ? `${x.today.visitors.toLocaleString("en-US")} today` : "");
  return h("div", { class: "pop menu site-menu", role: "menu", hidden: true, "aria-label": "Switch site" },
    list.map((x) => {
      const here = x.name === site;
      return h("a", { class: "menu-i site-i", role: "menuitem", href: here ? "./" : `../${x.path}`, "aria-current": here ? "page" : null },
        tile(logoOf(x, x.name), 24, "si-logo"),
        h("b", null, x.name, x.live ? h("span", { class: "live-dot", title: "Live: today is redrawn every 2 minutes" }, h("span", { class: "vh" }, ", live")) : null),
        here ? h("span", { class: "si-end si-check", html: CHECK, "aria-label": "this site", role: "img" })
          : today(x) ? h("small", { class: "si-end" }, today(x)) : null);
    }),
    h("a", { class: "menu-i site-all", role: "menuitem", href: "../" }, "All sites"));
}

// One button and its menu: opens and closes; Escape, a click elsewhere or a
// choice closes it. `float()`: place the menu on screen beside the button
// (the icon rail, the phone's bar), where the sidebar would clip it.
function switcher(btn, float) {
  const menu = siteMenu();
  const wrap = h("span", { class: "site-wrap" }, btn, menu);
  const close = () => { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", () => {
    const open = menu.hidden;
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", String(open));
    untip();
    if (open && float()) {
      const r = btn.getBoundingClientRect(), beside = rail.contains(btn);
      Object.assign(menu.style, { position: "fixed", top: `${beside ? r.top : r.bottom + 6}px`, left: `${beside ? r.right + 8 : Math.max(8, r.left)}px` });
    } else menu.removeAttribute("style");
    if (open) menu.querySelector("a")?.focus();
  });
  menu.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { close(); btn.focus(); return; }
    const items = [...menu.querySelectorAll("a")], i = items.indexOf(document.activeElement);
    const j = { ArrowDown: i + 1, ArrowUp: i - 1 }[e.key];
    if (j != null && items.length) { e.preventDefault(); items[(j + items.length) % items.length].focus(); }
  });
  document.addEventListener("pointerdown", (e) => { if (!menu.hidden && !wrap.contains(e.target)) close(); });
  return wrap;
}

export function brand(site, file = null, tool = "Skald") {
  SITE = { site, sites: (file?.sites || []).filter((x) => x && x.name && x.path) };
  const me = logoOf(SITE.sites.find((x) => x.name === site), site);
  const btn = h("button", { type: "button", class: "site-btn", "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": `Switch site: ${site}`, title: "Switch site" },
    tile(me, 34, "sb-logo"),
    h("span", { class: "sb-txt" }, h("span", { class: "brand-site" }, site), h("span", { class: "sb-tool" }, tool)),
    h("span", { class: "chev", "aria-hidden": "true", html: CHEV }));
  tooltip(btn, `${site}: switch site`);
  document.getElementById("site-slot").replaceChildren(switcher(btn, () => app.dataset.rail === "icons"));
  setTabIcon(me);
}

/* The phone's top bar: the site's logo and name, opening the same switcher. */
export function siteChip() {
  const { site, sites } = SITE;
  if (!site) return null;
  const btn = h("button", { type: "button", class: "site-chip", "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": `Switch site: ${site}` },
    tile(logoOf(sites.find((x) => x.name === site), site), 32, "sc-logo"));
  const wrap = switcher(btn, () => true);
  // The site's name above the page's (the trail), opening the same menu: the logo and the
  // name read as one control, and the page's name keeps its room.
  wrap.insertBefore(h("span", { class: "sc-name", "aria-hidden": "true", onclick: () => btn.click() }, h("span", null, site),
    h("span", { class: "chev", html: CHEV })), btn.nextSibling);
  return wrap;
}

/* The sidebar's foot: Settings (a gear), Help and About, each on its own line;
   below them one row: theme, what's new, the round button with the reader's
   own choices - theme, time zone, shortcuts, what's new, About, the plain
   page, sign out - and the button that folds the sidebar. items: that panel's
   nodes, built by main; initials: the signed-in person's, or none for a person icon. */
export function railFoot(items, initials = "", quick = []) {
  const foot = document.getElementById("rail-foot");
  const toggle = h("button", { type: "button", class: "foot-btn", id: "rail-toggle", "aria-controls": "rail",
    html: '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2.5" width="12" height="11" rx="2"/><path d="M6 2.5v11M10.5 6.5 9 8l1.5 1.5"/></svg>' });
  toggle.addEventListener("click", toggleRail);
  const gear = h("a", { href: "#settings", class: "foot-btn gear", id: "nav-settings", html: GEAR, onclick: (e) => go(e, "settings") }, h("span", { class: "tab-name" }, "Settings"));
  tooltip(gear, "Settings");
  const page = (key, id, icon) => {
    const a = h("a", { href: `#${key}`, class: "foot-btn foot-link", id, html: icon, onclick: (e) => go(e, key) }, h("span", { class: "tab-name" }, nameOf(key)));
    tooltip(a, nameOf(key));
    return a;
  };
  const me = h("button", { type: "button", class: "foot-btn me", "aria-haspopup": "dialog", "aria-expanded": "false", "aria-label": "You: theme, time zone, help and sign out",
    title: "Theme, time zone, help", html: initials ? "" : PERSON }, initials ? h("span", { class: "me-i", "aria-hidden": "true" }, initials) : null);
  const pop = h("div", { class: "pop menu settings-pop", role: "dialog", hidden: true, "aria-label": "You" }, items);
  const wrap = h("div", { class: "foot-me" }, me, pop);
  const close = (focusBack) => { pop.hidden = true; me.setAttribute("aria-expanded", "false"); if (focusBack) me.focus(); };
  me.addEventListener("click", () => {
    const open = pop.hidden;
    pop.hidden = !open;
    me.setAttribute("aria-expanded", String(open));
    // The panel floats above the page (the sidebar would clip it): over the foot, or beside the icon rail.
    if (open) {
      const r = me.getBoundingClientRect(), rr = rail.getBoundingClientRect(), icons = app.dataset.rail === "icons";
      Object.assign(pop.style, { position: "fixed", left: `${icons ? rr.right + 8 : rr.left + 8}px`,
        bottom: `${icons ? innerHeight - r.bottom : innerHeight - r.top + 6}px`, top: "auto" });
      pop.querySelector("button,select,a")?.focus();
    }
  });
  pop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(true); } });
  pop.addEventListener("click", (e) => { if (e.target.closest("a, .menu-i")) close(false); });
  document.addEventListener("pointerdown", (e) => { if (!pop.hidden && !wrap.contains(e.target)) close(false); });
  foot.replaceChildren(gear, page("help", "nav-help", TAB_ICONS.help || HELP), page("about", "nav-about", TAB_ICONS.about || ""), ...quick, wrap, toggle);
  apply();
}
