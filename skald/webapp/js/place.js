// Pure placement and keyboard helpers, with no DOM, so tests can run them in node.

// Where a tooltip of w x h goes for a point (x, y) in a viewport of vw x vh: centred
// above the point, below it when there is no room above, and always inside the viewport
// with `pad` to spare (a tooltip near an edge slides in; it is never cut).
export function tipBox(x, y, w, h, vw, vh, pad = 8) {
  const left = Math.max(pad, Math.min(vw - w - pad, x - w / 2));
  let top = y - h - 12;
  if (top < pad) top = y + 16;
  top = Math.max(pad, Math.min(vh - h - pad, top));
  return { left: Math.round(left), top: Math.round(top) };
}

// The slot a key moves to among k slots (a chart's days, a row of cells): arrows step,
// Page keys jump a week, Home and End go to the ends. null for any other key.
export function stepKey(key, i, k) {
  if (!(k > 0)) return null;
  const to = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1,
    PageDown: i + 7, PageUp: i - 7, Home: 0, End: k - 1 }[key];
  return to == null ? null : Math.max(0, Math.min(k - 1, to));
}

// One Tab stop for a whole chart (a roving tabindex): Tab reaches its current slot
// (the last one, the latest day, to start), the arrow keys, Page Up/Down, Home and End
// move inside it, and Tab again leaves the chart. Each slot keeps its own label and
// its Enter. `cols` > 1 makes Up and Down move a row in a grid of that many columns.
export function rove(items, { start = items.length - 1, cols = 0 } = {}) {
  items = [...items];
  if (!items.length) return;
  let cur = Math.max(0, Math.min(items.length - 1, start));
  items.forEach((el, i) => {
    el.setAttribute("tabindex", i === cur ? "0" : "-1");
    el.addEventListener("focus", () => {
      if (i === cur) return;
      items[cur].setAttribute("tabindex", "-1");
      el.setAttribute("tabindex", "0");
      cur = i;
    });
    el.addEventListener("keydown", (e) => {
      const key = cols > 1 && (e.key === "ArrowDown" || e.key === "ArrowUp") ? null : e.key;
      let to = key ? stepKey(key, i, items.length) : Math.max(0, Math.min(items.length - 1, i + (e.key === "ArrowDown" ? cols : -cols)));
      if (to == null || to === i) { if (to === i) e.preventDefault(); return; }
      e.preventDefault();
      items[to].focus();
    });
  });
}
