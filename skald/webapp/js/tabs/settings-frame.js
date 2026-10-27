// The frame every settings page is drawn in (v2, docs/plans/2026-10-26-settings-redesign.md):
// the page shows its state and its action; what it is for is behind a "?" (the owner,
// 2026-10-26: "all the information, notes, etc. should be only on demand").
//
//   the phone's menu     a "Settings page" select, grouped as the sidebar's menu; below 768px
//                        the sidebar is a drawer, so this keeps every page one tap away
//   the title and "?"    the menu's name; the "?" opens a short note (settings-menu.js `about`)
//                        with the page's Help guide (#help?part=<id>) and its public page
//                        (<home>/docs/<id>/, with copy and open icons)
//   in-page tabs         a page with tabs (settings-menu.js `tabs`): the strip, each tab its own
//                        address (sub=<key>), its own "?" note; a tab the reader may not open
//                        (<route>#<sub> in HIDDEN) is left out
//   cards' "?"           a card's explaining line (an h2's p.sub) goes behind a "?" by its title
//
// framed(route, render) -> (m, s, opts) => nodes. render: a function, or {sub: function} for
// a page with tabs; the page's own head1 is taken off (the frame's title is the page's).

import { h } from "../ui.js";
import * as S from "../state.js";
import { pageOf, subOf, helpOf, aboutOf, docsPath, tabKey, SETTINGS_PAGES, SETTINGS_GROUPS } from "../settings-menu.js";
import { tabStrip } from "../tabstrip.js";
import { withUrl } from "../urlactions.js";
import { home } from "../build.js";
import INDEX from "../help-index.js";
import { help } from "../ui/help.js";
import { screenHead } from "../ui/primary.js";
import { orgLine } from "./org-line.js";

export const Q = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.2"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/></svg>';
const BOOK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 3.5h4a1.5 1.5 0 0 1 1.5 1.5v8.5a1.5 1.5 0 0 0-1.5-1.5h-4zM13.5 3.5h-4A1.5 1.5 0 0 0 8 5v8.5a1.5 1.5 0 0 1 1.5-1.5h4z"/></svg>';
const GLOBE = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 1.7 2.6 3.7 2.6 6S9.8 12.3 8 14C6.2 12.3 5.4 10.3 5.4 8S6.2 3.7 8 2z"/></svg>';

export const guideTitle = (id) => INDEX.find((g) => g.id === id)?.title || "";
// The public page for a path under the home address: "docs/mcp/" -> https://<home>/docs/mcp/
export const docsUrl = (path) => `${home()}/${String(path || "docs/").replace(/^\/+/, "")}`;

/* A "?" and what it opens: the app's one help popover (ui/help.js), with these nodes in it.
   label: what it explains. { btn } is the "?" with its popover; box is kept for old callers. */
export function tip(label, ...kids) {
  const btn = help(label);
  const pop = btn.querySelector(".ui-help-pop");
  const more = pop.querySelector(".ui-help-more");
  for (const k of kids.flat(Infinity)) if (k) more ? pop.insertBefore(k, more) : pop.append(k);
  return { btn, box: null };
}

/* The page's note: what it is for, its guide in the app and its public page. */
export function helpLinks(route, sub = "") {
  const id = helpOf(route, sub), title = guideTitle(id);
  const url = docsUrl(docsPath(route, sub));
  const help = id ? h("a", { class: "set-help", href: `#help?part=${id}`, html: BOOK }, h("span", null, title ? `Guide: ${title}` : "Guide")) : null;
  const docs = withUrl(h("a", { class: "set-docs", href: url, target: "_blank", rel: "noopener", html: GLOBE, "aria-label": `Docs: ${title || "Skald"} (opens in a new tab)` },
    h("span", null, "Docs")), url, { label: `the docs for ${title || "Skald"}`, cls: "ua-after set-docs-w" });
  return h("p", { class: "set-links" }, help, docs);
}

/* The phone's menu: every settings page this reader may open, grouped as the sidebar. */
export function jumpMenu(route) {
  const sel = h("select", { id: "set-jump", "aria-label": "Settings page" },
    S.SETTINGS_MENU.map(([group, keys]) => {
      const opts = keys.filter(S.shown).map((k) => h("option", { value: k, selected: k === route }, S.nameOf(k)));
      if (!opts.length) return null;
      return group ? h("optgroup", { label: group }, opts) : opts;
    }));
  sel.addEventListener("change", () => S.set({ tab: sel.value }));
  return h("div", { class: "set-jump" }, h("label", { for: "set-jump" }, "Settings page"), sel);
}

const flat = (x) => [x].flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false && n !== "");
const isHead = (n) => n?.classList?.contains("page-head");

/* The nodes without their own title; the title's line, if any, is returned for the "?". */
function untitled(nodes) {
  let lede = "";
  const out = [];
  for (const n of nodes) {
    if (isHead(n) && !n.classList.contains("set-keep")) { lede = lede || n.querySelector?.(".lede")?.textContent || ""; continue; }
    out.push(n);
  }
  return { out, lede };
}

/* A card's explaining line (h2 + p.sub) behind a "?" by its title (ui/help.js). Runs again as
   answers draw. */
export function tipify(root) {
  let subs = [];
  try { subs = [...root.querySelectorAll("p.sub")]; } catch { return; }
  for (const p of subs) {
    const up = p.parentElement;
    const kids = up ? [...up.children] : [];
    const h2 = kids[kids.indexOf(p) - 1];
    if (!h2 || h2.tagName !== "H2" || p.dataset?.tip || !p.textContent.trim()) continue;
    p.dataset.tip = "1";
    h2.classList.add("has-tip");
    h2.append(help(h2.textContent.trim(), { text: p.textContent.trim() }));
    p.remove();
  }
}
/* The page's one primary button (set-ui.js primary()), wherever the page drew it: beside the
   title. A newer one replaces the one there; none drawn leaves the slot empty. */
function lift(root, slot) {
  if (!slot) return;
  const got = root.querySelectorAll(".set-primary");
  const last = got[got.length - 1];
  if (!last) return;
  got.forEach((b) => { if (b !== last) b.remove(); });
  slot.replaceChildren(last);
}
function watch(root, slot) {
  tipify(root);
  lift(root, slot);
  if (typeof MutationObserver === "undefined") return;
  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => { queued = false; tipify(root); lift(root, slot); });
  }).observe(root, { childList: true, subtree: true });
}

/* The title row: the page's name, its "?" and the note; the page's one primary on the right. */
function titleRow(route, name, sub, lede, slot) {
  const about = aboutOf(route, sub) || lede;
  const t = tip(name, about ? h("p", null, about) : null, helpLinks(route, sub));
  return h("div", { class: "page-head set-head" }, screenHead(name, { help: t.btn, action: slot, level: "h1" }));
}

export function framed(route, render) {
  return (m, s, opts = {}) => {
    const page = pageOf(route) || { name: S.nameOf(route), line: "" };
    const ok = (k) => S.shown(k);
    const sub = subOf(route, s.sub, ok);
    // Its group, for the cards' tint (settings.css): site, ai, org, you; To do is the site's.
    const g = SETTINGS_GROUPS.find((x) => x.pages.some((p) => p.route === route))?.key || "site";
    const body = h("div", { class: "set-body", "data-g": g });
    let lede = "";
    if (page.tabs && render && typeof render === "object") {
      const shownTabs = page.tabs.filter(([k]) => ok(tabKey(route, k)));
      const first = shownTabs[0]?.[0] || page.tabs[0][0];
      const fn = render[sub] || render[first];
      const got = untitled(flat(fn(m, s, opts)));
      lede = got.lede;
      if (shownTabs.length > 1) {
        const tabs = shownTabs.map(([k, name]) => ({ key: k, name, href: S.hashFor({ ...s, tab: route, sub: k === first ? "" : k }) }));
        const strip = tabStrip(tabs, sub, (k) => S.set({ sub: k === first ? "" : k }), { label: page.name });
        strip.root.classList.add("set-tabs");
        strip.panel.append(...got.out);
        body.append(strip.root);
      } else body.append(...got.out);
    } else {
      const got = untitled(flat(render ? render(m, s, opts) : []));
      lede = got.lede;
      body.append(...got.out);
    }
    const slot = h("span", { class: "set-act" });
    watch(body, slot);
    // Settings › Organisation: which organisation these pages are, and Switch (org-line.js).
    const line = g === "org" ? orgLine(route) : null;
    return [jumpMenu(route), line, titleRow(route, page.name, sub, lede, slot), body].filter(Boolean);
  };
}

// For tests: every page this reader may open, in the menu's order.
export const shownPages = () => SETTINGS_PAGES.filter((p) => S.shown(p.route));
