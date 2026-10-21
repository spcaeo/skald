// The one drawer every detail and dialog opens in: anchored right, 80% of the
// screen on a laptop (capped on wide screens), the whole width on a phone,
// the page behind masked. Header with the title and an X, a body that scrolls,
// and an optional footer for actions (right-aligned, the primary last).
//
//   const d = openDrawer({ title, subtitle, body, footer, size });
//   d.close();   d.el (the <dialog>), d.body (the scrolling body)
//
// Options beyond those:
//   size      "lg" (default, tables and charts) or "md" (forms, lists, notes)
//   head      nodes drawn above the title (a Back button, a trail)
//   className extra classes on the <dialog>
//   key       a drawer opened with the key of one already open replaces it
//   scope     "page": closed with the page on every redraw (main.js); "app": kept
//   still     no slide-in (a redraw reopening the same drawer)
//   focus     the element to focus first (default: the X)
//   onClose   called once, after the reader or the code closed it
//   route     {key, value[, step]}: what the address says while it is open (js/overlays.js):
//             written when it opens (Back closes it), taken away when it closes
//
// A <dialog> opened with showModal() makes the page behind inert; the focus
// trap, Escape, the mask's click, focus return and the scroll lock are here.

import { h, reduced } from "./ui.js";
import { opened as routeOpened, closed as routeClosed } from "./overlays.js";

const X = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 4l8 8M12 4l-8 8"/></svg>';
const stack = [];            // the open drawers, the top one last
const handoff = new Map();   // key -> opener, kept across a redraw that reopens the same drawer
let seq = 0;

const focusable = (root) => [...root.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex="-1"])')]
  .filter((x) => !x.disabled && !x.closest("[hidden]") && x.getClientRects().length);

function lock(on) {
  document.documentElement.classList.toggle("dw-lock", on);
}

export function openDrawer({ title = "", subtitle = "", body = null, footer = null, size = "lg", head = null, className = "", key = "", scope = "app",
  still = false, focus = null, onClose = null, route = null } = {}) {
  let opener = document.activeElement;
  if (key) {
    const same = stack.find((d) => d.key === key);
    if (same) { opener = same.opener; same.close({ instant: true, silent: true, focusBack: false }); }
    // A drawer a redraw closed and the address opens again: no slide-in, and focus goes back to where it was.
    else if (handoff.has(key)) { opener = handoff.get(key); still = true; }
    handoff.delete(key);
  }
  const id = `dw-${++seq}`;
  const x = h("button", { type: "button", class: "dw-x", "aria-label": "Close", title: "Close (Esc)", html: X });
  const titleEl = h("h2", { class: "dw-title", id: `${id}-t` }, title);
  const subEl = subtitle ? h("p", { class: "dw-sub", id: `${id}-s` }, subtitle) : null;
  const bodyEl = h("div", { class: "dw-body" }, body);
  const footEl = footer ? h("footer", { class: "dw-foot" }, footer) : null;
  const headEl = h("header", { class: "dw-head" }, h("div", { class: "dw-titles" }, head ? h("div", { class: "dw-pre" }, head) : null, titleEl, subEl), x);
  const el = h("dialog", { class: `dw dw-${size}${still ? " still" : ""}${className ? ` ${className}` : ""}`, "aria-labelledby": `${id}-t`,
    "aria-describedby": subEl ? `${id}-s` : null, "data-scope": scope }, h("div", { class: "dw-panel" }, headEl, bodyEl, footEl));

  let closed = false;
  const d = { el, body: bodyEl, head: headEl, key, scope, opener, close };
  function close({ instant = false, silent = false, focusBack = true } = {}) {
    if (closed) return;
    closed = true;
    const i = stack.indexOf(d);
    if (i >= 0) stack.splice(i, 1);
    stack[stack.length - 1]?.el.classList.remove("dw-under");
    if (!stack.length) lock(false);
    const done = () => {
      if (el.open) el.close();
      el.remove();
      if (!focusBack) return;
      const o = d.opener;
      const back = o && o !== document.body && o.isConnected && !o.closest("dialog:not([open])") ? o : stack[stack.length - 1]?.el.querySelector(".dw-x") || document.getElementById("panel");
      back?.focus?.({ preventScroll: true });
    };
    if (instant || reduced() || !el.isConnected) done();
    else {
      el.classList.add("dw-out");
      let t = 0;
      const end = () => { clearTimeout(t); el.removeEventListener("animationend", end); done(); };
      el.addEventListener("animationend", end);
      t = setTimeout(end, 320);
    }
    // The reader (or the code) closed it: its key leaves the address. A redraw's silent close keeps it.
    if (!silent && route) routeClosed(route.key, route.value);
    if (!silent && onClose) onClose();
  }

  x.addEventListener("click", () => close());
  // Escape: the dialog's own cancel, turned into our close so it animates and hands focus back.
  el.addEventListener("cancel", (e) => { e.preventDefault(); close(); });
  // The mask: a press that starts and ends outside the panel. (Selecting text and letting go outside does not close it.)
  let downOut = false;
  el.addEventListener("pointerdown", (e) => { downOut = e.target === el; });
  el.addEventListener("click", (e) => { if (e.target === el && downOut) close(); downOut = false; });
  // Tab and Shift+Tab stay inside, never out to the browser's own bar.
  el.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    const f = focusable(el);
    if (!f.length) { e.preventDefault(); return; }
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || !el.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || !el.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
  });

  stack[stack.length - 1]?.el.classList.add("dw-under");
  stack.push(d);
  lock(true);
  document.body.append(el);
  el.showModal();
  (focus || x).focus({ preventScroll: true });
  bodyEl.scrollTop = 0;
  if (route) routeOpened(route.key, route.value, { close: () => close(), isOpen: () => !closed && el.isConnected }, { step: route.step ?? null });
  return d;
}

/* Close every drawer of a scope at once, without animation or callbacks: the
   page is about to be redrawn. A drawer with a key passes its opener on, so a
   redraw that reopens it still hands focus back to where the reader was. */
export function closeDrawers(scope = "page") {
  for (const d of [...stack].reverse()) {
    if (d.scope !== scope) continue;
    if (d.key) handoff.set(d.key, d.opener);
    d.close({ instant: true, silent: true, focusBack: false });
  }
}

export const drawerIsOpen = () => stack.length > 0;
