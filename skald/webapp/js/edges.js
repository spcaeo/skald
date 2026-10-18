// Sideways scrollers say there is more. A table, a tab strip or a button row that is
// wider than its box gets `edge-x`, plus `edge-l` / `edge-r` while there is more to
// that side; css/layout.css draws the fade and, for a table, keeps its first column
// in place. Started once by main.js; it watches the page for new scrollers itself.

const SCROLLERS = ".scroll, .dg-scroll, .stabs-list, .subtabs, .sk-scroll, .md-table, .fun, .bar .seg";

function mark(el) {
  const max = el.scrollWidth - el.clientWidth;
  const x = Math.abs(el.scrollLeft);
  el.classList.toggle("edge-x", max > 1);
  el.classList.toggle("edge-l", max > 1 && x > 1);
  el.classList.toggle("edge-r", max > 1 && max - x > 1);
}

const seen = new WeakSet();
let sizes = null;
function watch(el) {
  if (seen.has(el)) { mark(el); return; }
  seen.add(el);
  el.addEventListener("scroll", () => mark(el), { passive: true });
  sizes?.observe(el);
  mark(el);
  // A table's rows can grow after it is drawn (Show all, a search): its first child too.
  if (el.firstElementChild) sizes?.observe(el.firstElementChild);
}

function scan(root) {
  if (!(root instanceof Element)) return;
  if (root.matches(SCROLLERS)) watch(root);
  root.querySelectorAll(SCROLLERS).forEach(watch);
}

export function startEdges(root = document.body) {
  if (typeof document === "undefined" || !root) return;
  sizes = typeof ResizeObserver === "function"
    ? new ResizeObserver((entries) => entries.forEach((e) => { const el = e.target.matches?.(SCROLLERS) ? e.target : e.target.parentElement; if (el && seen.has(el)) mark(el); }))
    : null;
  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    // Once per frame, after the tab has drawn: whatever was added is measured laid out.
    requestAnimationFrame(() => { queued = false; scan(root); });
  }).observe(root, { childList: true, subtree: true });
  scan(root);
}
