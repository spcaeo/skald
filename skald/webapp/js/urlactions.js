// Copy and open in a new tab, on every URL and site path the page draws (2.21; the
// owner's rule: "if there is a URL on a mouse over, show two small icons at the end").
//
//   withUrl(node, "/pricing/")          the cell or chip, with the two icons at its end
//   urlActions("/pricing/")             the two icons alone (a span), or null
//   withCopy(node, "u-119797")          an ID (2.25): the copy icon alone, the same behaviour
//   fullUrl("/pricing/")                "https://example.com/pricing/"
//
// A path is joined with the site's own address: https:// and the site's name, as the
// site is named in Skald (setSiteBase, from main.js on each draw). A full URL is used as
// it is; anything else (a folded "(all others)", a blank) gets no icons.
//
// Behaviour (css/urlactions.css): the icons show on hover or keyboard focus of the cell
// and sit over its end, so nothing moves; on a touch screen they always show. Copy writes
// the full URL and turns into a green tick for 1.5 s, then the icons hide; Open opens the
// full URL in a new tab (noopener noreferrer) and hides them. A failed copy says
// "Copy failed: select and copy" instead of the tick. Neither click reaches the row under
// it, so a row that opens a drawer or a page's story keeps doing so.

import { h } from "./ui.js";

let BASE = "";
export function setSiteBase(site) {
  const name = String(site || "").trim().replace(/^[a-z][a-z0-9+.-]*:\/\//i, "").replace(/\/+$/, "");
  BASE = name ? `https://${name}` : "";
}
export const siteBase = () => BASE;

export const TIMING = { tick: 1500, failed: 2600 };

/* The full URL for a path in the site or a URL, or null when it is neither. */
export function fullUrl(target) {
  const t = String(target ?? "").trim();
  if (/^https?:\/\/[^\s/]+/i.test(t)) return t;
  if (t.startsWith("/") && !t.startsWith("//") && !/\s/.test(t) && BASE) return `${BASE}${t}`;
  return null;
}

const ICON_COPY = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><rect x="5.5" y="5.5" width="8" height="8" rx="1.6"/><path d="M10.5 5.5V3.6c0-.6-.5-1.1-1.1-1.1H3.6c-.6 0-1.1.5-1.1 1.1v5.8c0 .6.5 1.1 1.1 1.1h1.9"/></svg>';
const ICON_OPEN = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5"/><path d="M11.5 9.5v3c0 .6-.5 1-1 1h-7c-.6 0-1-.4-1-1v-7c0-.6.4-1 1-1h3"/></svg>';
const ICON_TICK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 8.4 6.5 11.6 12.8 4.6"/></svg>';

/* The words the page writes to the clipboard: the Clipboard API, else a selected field. */
export async function copyText(text) {
  try {
    if (globalThis.navigator?.clipboard?.writeText) { await navigator.clipboard.writeText(text); return true; }
  } catch { /* refused: try the old way */ }
  try {
    if (typeof document.execCommand !== "function") return false;
    const ta = h("textarea", { class: "vh", readonly: "", "aria-hidden": "true" });
    ta.value = text;
    document.body.append(ta);
    ta.select?.();
    const ok = document.execCommand("copy");
    ta.remove();
    return !!ok;
  } catch { return false; }
}

const stop = (e) => e.stopPropagation();

/* The two icons for one URL or path, or null when it has no full URL. */
export function urlActions(target, { label = null } = {}) {
  const url = fullUrl(target);
  if (!url) return null;
  return icons(url, label || String(target).trim(), true);
}

/* The copy icon alone, for an ID (2.25: a lead's reference, an account ID): the same look
   and behaviour as a URL's, with nothing to open. null for a blank value. */
export function idActions(value, { label = null } = {}) {
  const text = value == null ? "" : String(value).trim();
  if (!text) return null;
  return icons(text, label || text, false);
}

function icons(url, name, opens) {
  const words = opens ? `link to ${name}` : name;
  const copy = h("button", { type: "button", class: "ua-b ua-copy", "aria-label": `Copy ${words}`, title: `Copy ${url}`, html: ICON_COPY });
  const open = opens ? h("a", { class: "ua-b ua-open", href: url, target: "_blank", rel: "noopener noreferrer", "aria-label": `Open ${name} in a new tab`, title: `Open ${url} in a new tab`, html: ICON_OPEN }) : null;
  const said = h("span", { class: "ua-msg", role: "status", "aria-live": "polite" });
  const box = h("span", { class: "ua" }, copy, open, said);
  let timer = 0;
  // Hidden after a use until the pointer leaves the cell or the focus moves on.
  const gone = () => { box.classList.add("ua-gone"); };
  const back = () => { box.classList.remove("ua-gone"); };
  const host = () => box.closest?.(".ua-host") || box.parentNode;
  const reset = () => {
    clearTimeout(timer);
    box.classList.remove("ua-ok", "ua-bad");
    copy.innerHTML = ICON_COPY;
    copy.setAttribute("aria-label", `Copy ${words}`);
    said.textContent = "";
  };
  for (const ev of ["click", "pointerdown", "mousedown", "keydown"]) { copy.addEventListener(ev, stop); open?.addEventListener(ev, stop); }
  copy.addEventListener("click", async (e) => {
    e.preventDefault();
    reset();
    const ok = await copyText(url);
    if (ok) {
      box.classList.add("ua-ok");
      copy.innerHTML = ICON_TICK;
      copy.setAttribute("aria-label", `Copied ${opens ? "the link to " : ""}${name}`);
      said.textContent = "Copied";
    } else {
      box.classList.add("ua-bad");
      said.textContent = "Copy failed: select and copy";
    }
    timer = setTimeout(() => { reset(); gone(); copy.blur?.(); }, ok ? TIMING.tick : TIMING.failed);
  });
  open?.addEventListener("click", () => { reset(); gone(); setTimeout(() => open.blur?.(), 0); });
  // Space on the link opens it too, as on a button.
  open?.addEventListener("keydown", (e) => { if (e.key === " ") { e.preventDefault(); open.click(); } });
  // Shown again once the reader leaves the cell and comes back.
  box.attach = (el) => {
    el.addEventListener("mouseleave", back);
    el.addEventListener("focusout", (e) => { if (!el.contains?.(e.relatedTarget)) back(); });
  };
  box.url = url;
  box.host = host;
  return box;
}

/* A cell's or a chip's content with the icons at its end; the content alone when the
   target has no full URL. tag: the wrapper's element (span by default). */
export function withUrl(content, target, { label = null, tag = "span", cls = "" } = {}) {
  return hosted(content, urlActions(target, { label }), tag, cls);
}

/* An ID's content with the copy icon at its end; the content alone for a blank value. */
export function withCopy(content, value, { label = null, tag = "span", cls = "" } = {}) {
  return hosted(content, idActions(value, { label }), tag, cls);
}

function hosted(content, ua, tag, cls) {
  if (!ua) return content;
  const kids = [content].flat().filter((x) => x !== null && x !== undefined && x !== false);
  const el = h(tag, { class: `ua-host${cls ? ` ${cls}` : ""}` }, ...kids, ua);
  ua.attach(el);
  return el;
}

/* A table's or a grid's column whose values are site paths or URLs (table.js, grid.js):
   path: true or url: true, or a column drilled by page or landing page. */
export const isUrlColumn = (c) => !!(c && (c.path || c.url || c.drill === "path" || c.drill === "landing"));
