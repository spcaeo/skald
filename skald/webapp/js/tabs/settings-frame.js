// The frame every settings page is drawn in (2.40, docs/plans/2026-10-26-settings-redesign.md):
//
//   the phone's menu     a "Settings page" select, grouped as the sidebar's menu; below 768px
//                        the sidebar is a drawer, so this keeps every page one tap away
//   the title            the page's own (its head1), or the menu's name and line
//   Help · Docs          under the title: the page's in-app guide (#help?part=<id>) and its
//                        public page (<home>/docs/<id>/, a new tab, with copy and open icons)
//   in-page tabs         a page with tabs (settings-menu.js `tabs`): the strip, each tab its own
//                        address (sub=<key>), its own guide in Help · Docs
//   Next step            at the foot: where to go next, in words
//
// framed(route, render) -> (m, s, opts) => nodes. render: a function, or {sub: function} for
// a page with tabs; a tab's own head1 is taken off (the page's title is the frame's) and its
// lede kept as the tab's first line.

import { h } from "../ui.js";
import * as S from "../state.js";
import { pageOf, subOf, helpOf, docsPath, SETTINGS_PAGES } from "../settings-menu.js";
import { tabStrip } from "../tabstrip.js";
import { withUrl } from "../urlactions.js";
import { home } from "../build.js";
import INDEX from "../help-index.js";

const BOOK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/></svg>';
const GLOBE = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 1.7 2.6 3.7 2.6 6S9.8 12.3 8 14C6.2 12.3 5.4 10.3 5.4 8S6.2 3.7 8 2z"/></svg>';
const ARROW = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8h10M9 4l4 4-4 4"/></svg>';

export const guideTitle = (id) => INDEX.find((g) => g.id === id)?.title || "";
// The public page for a path under the home address: "docs/mcp/" -> https://<home>/docs/mcp/
export const docsUrl = (path) => `${home()}/${String(path || "docs/").replace(/^\/+/, "")}`;

/* Help · Docs: the in-app guide and the public page, for a page (and its tab). */
export function helpLinks(route, sub = "") {
  const id = helpOf(route, sub), title = guideTitle(id);
  const url = docsUrl(docsPath(route, sub));
  const help = id ? h("a", { class: "set-help", href: `#help?part=${id}`, title: title ? `The guide: ${title}` : null, html: BOOK },
    h("span", null, "Help", title ? h("span", { class: "set-help-t" }, `: ${title}`) : null)) : null;
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

/* Next step: the page that comes next in its flow, in words. */
export function nextCard(route) {
  const p = pageOf(route);
  if (!p?.next) return null;
  const [to, words] = p.next;
  if (!S.shown(to)) return null;
  return h("nav", { class: "set-next", "aria-label": "Next step" },
    h("span", { class: "set-next-l" }, "Next step"),
    h("a", { href: `#${to}`, onclick: (e) => { if (e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); S.set({ tab: to }); } },
      h("span", null, words), h("span", { class: "set-next-i", html: ARROW })));
}

const flat = (x) => [x].flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false && n !== "");
const isHead = (n) => n?.classList?.contains("page-head");

/* A tab's nodes without their own title: the lede stays as the tab's first line. */
function untitled(nodes) {
  const out = [];
  for (const n of nodes) {
    if (isHead(n)) {
      const lede = n.querySelector?.(".lede");
      if (lede?.textContent) out.push(h("p", { class: "lede set-tab-lede" }, lede.textContent));
      continue;
    }
    out.push(n);
  }
  return out;
}

export function framed(route, render) {
  return (m, s, opts = {}) => {
    const page = pageOf(route) || { name: S.nameOf(route), line: "" };
    const sub = subOf(route, s.sub);
    const links = helpLinks(route, sub);
    const jump = jumpMenu(route);
    const out = [jump];
    if (page.tabs && render && typeof render === "object") {
      const tabs = page.tabs.map(([k, name]) => ({ key: k, name, href: S.hashFor({ ...s, tab: route, sub: k === page.tabs[0][0] ? "" : k }) }));
      const strip = tabStrip(tabs, sub, (k) => S.set({ sub: k === page.tabs[0][0] ? "" : k }), { label: page.name });
      strip.root.classList.add("set-tabs");
      const fn = render[sub] || render[page.tabs[0][0]];
      strip.panel.append(...untitled(flat(fn(m, s, opts))));
      out.push(h("div", { class: "page-head set-head" }, h("div", { class: "head" }, h("h1", null, page.name)), page.line ? h("p", { class: "lede" }, page.line) : null, links), strip.root);
    } else {
      const body = flat(render ? render(m, s, opts) : []);
      const at = body.findIndex(isHead);
      // A page with figures (Internal traffic) has the figures' header (common.js head): the links under it.
      const fig = at < 0 ? body.findIndex((n) => n?.classList?.contains("head")) : -1;
      if (at >= 0) {
        // The menu's name is the title (Data retention's page is Privacy & retention now); a
        // title that holds it says more and stays ("Team of Kiwi").
        const h1 = body[at].querySelector?.("h1");
        if (h1 && !h1.textContent.includes(page.name)) h1.textContent = page.name;
        body[at].classList.add("set-head");
        body[at].append(links);
      } else if (fig >= 0) body.splice(fig + 1, 0, links); else body.unshift(h("div", { class: "page-head set-head" }, h("div", { class: "head" }, h("h1", null, page.name)), page.line ? h("p", { class: "lede" }, page.line) : null, links));
      out.push(...body);
    }
    out.push(nextCard(route));
    return out.filter(Boolean);
  };
}

// For tests and the All settings page: every page this reader may open, in the menu's order.
export const shownPages = () => SETTINGS_PAGES.filter((p) => S.shown(p.route));
