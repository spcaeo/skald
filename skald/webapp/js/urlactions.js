// Copy and open in a new tab, on every URL and site path the page draws (2.21; the
// owner's rule: "if there is a URL on a mouse over, show two small icons at the end").
//
//   withUrl(node, "/pricing/")          the cell or chip, with the two icons at its end
//   urlActions("/pricing/")             the two icons alone (a span), or null
//   withCopy(node, "u-119797")          an ID (2.25): the copy icon alone, the same behaviour
//   fullUrl("/pricing/")                "https://example.com/pricing/"
//   copyCell(column, row, content)      a table's or a grid's cell (2.35): the copy icon when
//                                       its column holds text to paste elsewhere (copyKind)
//   copyIf("ip", node, "192.0.2.4")     a drawer's or a card's value of a kind: the icon or not
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
//
// The owner's rule (2026-10-25): every URL or path gets copy and open; every text value
// someone may paste elsewhere (an address, a user agent, an email, a name, a search term,
// a crawler, a campaign, a reference, a reason) gets the copy icon alone, the same look.
// Labels, headings, buttons, plain numbers and percentages get none; chart tooltips none.

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

/* ---- text to paste elsewhere (2.35) -------------------------------------------------
   A table's or a grid's column that holds such text gets the copy icon on each cell by
   itself: by its key or its label, or a drilled value (an address, a referrer, a campaign,
   a crawler, an assistant). copy: "ip" | "ua" | "email" | "text" | true says it outright,
   copy: false leaves a column out; copyValue(row) gives the words when the cell shows
   something shorter (a user agent cut down to its browser). */
const COPY_DIMS = { ip: "ip", referrer: "text", campaign: "text", bot: "text", assistant: "text" };
const RAW_DIMS = new Set(["bot", "referrer", "campaign", "ip"]);
const COPY_KEYS = { ip: "ip", email: "email", ua: "ua", user_agent: "ua" };
export const COPY_LABELS = {
  "IP address": "ip", Address: "ip", "User agent": "ua", Email: "email",
  Name: "text", Company: "text", Phone: "text", Crawler: "text", Assistant: "text", "Likely assistant": "text",
  "AI assistant": "text", Competitor: "text", Question: "text", "Search term": "text", Query: "text",
  "Referring site": "text", Campaign: "text", "Campaign or UTM tag": "text", utm: "text", Reference: "text",
  "Lead or reference": "text", "Visitor ID": "text", Network: "text", Host: "text", Why: "text", Error: "text",
  "What happened": "text", File: "text", Title: "text", "Page title": "text", Token: "text",
};
/* The copy kind of a drilled dimension's values (a bar list's, a link's), or null. */
export const dimKind = (dim) => COPY_DIMS[dim] || null;
export function copyKind(c) {
  if (!c || c.copy === false || isUrlColumn(c) || c.num || ["num", "date", "badge"].includes(c.type)) return null;
  if (c.copy) return c.copy === true ? "text" : String(c.copy);
  return COPY_DIMS[c.drill] || COPY_KEYS[c.key] || COPY_LABELS[c.label] || null;
}

// Words that stand for "nothing here": no icon.
const BLANK = /^(-|–|—|none|none yet|none close|not listed|not shown|\((none|removed|not set|all others|no host|no campaign tag|this site)\)|removed|removed on request|not recorded|not known|not set|unknown|n\/a)$/i;
const FITS = {
  ip: (t) => /^[0-9a-f:.]+(\/\d{1,3})?$/i.test(t) && /[.:]/.test(t),
  email: (t) => /^[^\s@]+@[^\s@]+$/.test(t),
};

/* What a cell shows, as text: the words a reader sees (not .vh, [hidden], a decorative
   mark's letters or the icons). */
export function shownWords(x) {
  if (x == null || x === false) return "";
  if (typeof x !== "object") return String(x);
  if (typeof x.tagName !== "string") return x.childNodes?.length ? [...x.childNodes].map(shownWords).join("") : (x.textContent || "");
  if (x.classList?.contains("vh") || x.classList?.contains("ua") || x.hasAttribute?.("hidden") || x.getAttribute?.("aria-hidden") === "true") return "";
  return [...(x.childNodes || [])].map(shownWords).join("");
}

/* The words the copy icon writes for a value of this kind, or "" for none: text copies what
   the cell shows; an address, an email or a user agent its whole stored value (or text
   whose value is given: given). */
export function copyWords(kind, raw, content, given = false) {
  let r = typeof raw === "string" || typeof raw === "number" ? String(raw).trim() : "";
  // A drilled crawler, referrer or campaign copies its own name ("ChatGPT-User"), not the
  // words its link adds ("ChatGPT-User user fetcher"): the value its link opens (drill.js).
  const dl = content && typeof content === "object" ? (content.classList?.contains("dl") ? content : content.querySelector?.("button.dl")) : null;
  if (kind === "text" && !given && dl && RAW_DIMS.has(dl.dataset?.dim) && dl.dataset.value) { r = dl.dataset.value; given = true; }
  const seen = () => shownWords(content).replace(/\s+/g, " ").trim();
  const t = kind === "text" && !given ? seen() || r : r || seen();
  if (!t || BLANK.test(t)) return "";
  if (FITS[kind] && !FITS[kind](t)) return "";
  return t;
}

const hasIcons = (x) => !!(x && typeof x === "object" && (x.classList?.contains("ua-host") || x.querySelector?.(".ua")));
const said = (what, value) => `${what ? `${what} ` : ""}${value.length > 60 ? `${value.slice(0, 57)}...` : value}`;

/* A table's or a grid's cell with the copy icon at its end when its column holds text to
   paste (copyKind); the content alone otherwise, or when it already has its icons. */
export function copyCell(c, row, content) {
  const kind = copyKind(c);
  if (!kind || hasIcons(content)) return content;
  const value = copyWords(kind, c.copyValue ? c.copyValue(row) : row?.[c.key], content, !!c.copyValue);
  return value ? withCopy(content, value, { label: said((c.copyLabel || c.label || "").toLowerCase(), value) }) : content;
}

/* A drawer's fact (a <dt> and its <dd>): the copy icon when its name is one of the column
   names above or these, the content alone otherwise. raw: the whole value, as for copyIf. */
const FACT_LABELS = { Agent: "text", "Campaign tags": "text", "Decided by": "text", Tags: "text", Customer: "text", Rule: "text" };
export function copyFact(name, content, raw = null) {
  const kind = COPY_LABELS[name] || FACT_LABELS[name];
  return kind ? copyIf(kind, content, raw, { label: String(name).toLowerCase() }) : content;
}

/* A drawer's, a card's or a list's value of a kind ("ip", "ua", "email", "text"): the copy
   icon at its end (ua-after: after the words, not over them), or the content alone when
   there is nothing to copy. raw: the whole value when the node shows less. */
export function copyIf(kind, content, raw = null, { label = "", cls = "ua-after" } = {}) {
  if (hasIcons(content)) return content;
  const value = copyWords(kind, raw, content, raw != null);
  return value ? withCopy(content, value, { label: said(label, value), cls }) : content;
}
