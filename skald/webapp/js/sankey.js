// A flow map (a Sankey diagram), drawn by hand in SVG: no library, nothing
// loaded from outside. It draws any flow shaped as flow.js makes one:
//
//   { total, columns: [{title, nodes: [{id, col, label, value, kind, end, drill}]}],
//     links: [{source, target, value}] }
//
// A node's height is its visits; a band's width is the visits that moved from
// one node to the next, so what enters a node leaves it. Nodes are coloured by
// what they are (where visits came from, a page, the folded tail, leaving); the
// bands are a quiet grey that takes the node's colour on hover or focus.
//
// Every node is a tab stop: hover or focus shows its visits, its share and its
// biggest moves, and lights its bands; a click (or Enter) calls onPick, which a
// tab uses to drill. The same figures are one click away as a table (the only
// view on a narrow screen), for screen readers and for a CSV.

import { h, n, share, tip, untip } from "./ui.js";
import { legend } from "./charts.js";
import { table } from "./table.js";

const NS = "http://www.w3.org/2000/svg";
const KIND = {
  start: ["Where visits came from", "var(--g-people)"],
  step: ["A funnel step", "var(--views)"],
  page: ["A page", "var(--views)"],
  other: ["Folded: the smaller values", "var(--hatch)"],
  more: ["Went on to more pages", "var(--ink-2)"],
  left: ["Left the site", "var(--ink-3)"],
};
const NARROW = 620;   // under this width the table is shown first
const NODE_W = 10, PAD = 10, TOP = 26, BOTTOM = 6, CHAR = 6.4;

function svg(tag, attrs, text) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, String(v));
  if (text != null) el.textContent = text;   // labels are data: never markup
  return el;
}
const cut = (s, room) => (s.length * CHAR <= room ? s : room < CHAR * 4 ? "" : `${s.slice(0, Math.max(1, Math.floor(room / CHAR) - 1))}…`);
// Room kept right of the last column for its labels.
const tail = (W) => Math.round(Math.min(180, Math.max(110, W * 0.18)));
const say = (opts, nd) => (opts.say ? opts.say(nd) : nd.label);

/* Where everything goes: x and y of each node, and each band's two ends. */
function place(flow, W, H) {
  const cols = flow.columns, C = cols.length;
  const most = Math.max(...cols.map((c) => c.nodes.length));
  const biggest = Math.max(...cols.map((c) => c.nodes.reduce((a, nd) => a + nd.value, 0)), 1);
  const k = Math.max(0.0001, (H - TOP - BOTTOM - PAD * (most - 1)) / biggest);
  const step = C > 1 ? (W - tail(W) - NODE_W) / (C - 1) : 0;
  const at = new Map();
  cols.forEach((c, i) => {
    const tall = c.nodes.reduce((a, nd) => a + nd.value * k, 0) + PAD * (c.nodes.length - 1);
    let y = TOP + (H - TOP - BOTTOM - tall) / 2;
    for (const nd of c.nodes) {
      const hgt = nd.value * k;
      at.set(nd.id, { nd, x: i * step, y, h: hgt, out: y, in: y, i });
      y += hgt + PAD;
    }
  });
  // Bands leave a node in the order of where they go, and enter in the order of where they came from.
  const by = (end) => (a, b) => at.get(a[end]).y - at.get(b[end]).y;
  const bands = flow.links.map((l) => ({ ...l, w: l.value * k }));
  for (const l of [...bands].sort(by("target"))) { const a = at.get(l.source); l.y0 = a.out; a.out += l.w; }
  for (const l of [...bands].sort(by("source"))) { const b = at.get(l.target); l.y1 = b.in; b.in += l.w; }
  return { at, bands, step };
}

function bandPath(a, b, l) {
  const x0 = a.x + NODE_W, x1 = b.x, xm = (x0 + x1) / 2, w = Math.max(l.w, 0.6);
  const f = (v) => v.toFixed(1);
  return `M${f(x0)},${f(l.y0)}C${f(xm)},${f(l.y0)} ${f(xm)},${f(l.y1)} ${f(x1)},${f(l.y1)}` +
    `L${f(x1)},${f(l.y1 + w)}C${f(xm)},${f(l.y1 + w)} ${f(xm)},${f(l.y0 + w)} ${f(x0)},${f(l.y0 + w)}Z`;
}

function draw(flow, opts, W) {
  const unit = opts.unit || "visits";
  const most = Math.max(...flow.columns.map((c) => c.nodes.length));
  const H = opts.height || Math.max(240, Math.min(620, 140 + most * 34));
  const { at, bands, step } = place(flow, W, H);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: "sk-svg", role: "group", "aria-label": opts.label || "Flow map" });
  // Column titles.
  flow.columns.forEach((c, i) => root.append(svg("text", { x: i * step, y: 12, class: "sk-col" }, c.title)));
  const gBands = svg("g", { class: "sk-bands" }), gNodes = svg("g", { class: "sk-nodes" });
  root.append(gBands, gNodes);
  const bandEls = new Map();
  for (const l of bands) {
    const a = at.get(l.source), b = at.get(l.target);
    const p = svg("path", { d: bandPath(a, b, l), class: "sk-band" });
    p.style.setProperty("--k", KIND[a.nd.kind]?.[1] || "var(--ink-3)");
    const show = (e) => {
      root.classList.add("on");
      p.classList.add("hi");
      tip(e.clientX, e.clientY, `${say(opts, a.nd)} → ${say(opts, b.nd)}`, [
        { color: KIND[a.nd.kind]?.[1], value: n(l.value), label: unit },
        ...(share(l.value, a.nd.value) ? [{ value: share(l.value, a.nd.value), label: `of the ${n(a.nd.value)} at ${say(opts, a.nd)}` }] : []),
        ...(share(l.value, flow.total) ? [{ value: share(l.value, flow.total), label: `of all ${n(flow.total)}` }] : [])]);
    };
    p.addEventListener("pointermove", show);
    p.addEventListener("pointerleave", () => { root.classList.remove("on"); p.classList.remove("hi"); untip(); });
    gBands.append(p);
    for (const id of [l.source, l.target]) (bandEls.get(id) || bandEls.set(id, []).get(id)).push(p);
  }
  const lastCol = flow.columns.length - 1;
  for (const { nd, x, y, h: hgt, i } of at.values()) {
    const color = KIND[nd.kind]?.[1] || "var(--ink-3)";
    const words = say(opts, nd);
    const pick = opts.onPick && (nd.drill || opts.pickAll) ? () => { untip(); opts.onPick(nd); } : null;
    const g = svg("g", { class: `sk-node${pick ? " pick" : ""}`, tabindex: 0, role: pick ? "button" : "img",
      "aria-label": `${flow.columns[i].title}: ${words}, ${n(nd.value)} ${unit}${share(nd.value, flow.total) ? `, ${share(nd.value, flow.total)} of all` : ""}${pick ? ". Open it" : ""}` });
    // The hit area is wider than the bar, and never under 12px tall.
    g.append(svg("rect", { x: x - 4, y: y - Math.max(0, (12 - hgt) / 2), width: NODE_W + 8, height: Math.max(12, hgt), class: "sk-hit" }),
      svg("rect", { x, y, width: NODE_W, height: Math.max(hgt, 1), rx: 2, fill: color, class: "sk-bar" }));
    // A label where it fits, right of the bar; the whole of it is in the tooltip and the table.
    if (hgt + PAD >= 13) {
      const room = (i < lastCol ? step : tail(W)) - NODE_W - 14;
      const num = ` ${n(nd.value)}`;
      const text = cut(words, room - num.length * CHAR);
      if (text) {
        const t = svg("text", { x: x + NODE_W + 6, y: y + hgt / 2 + 4, class: "sk-lab" });
        t.append(svg("tspan", null, text), svg("tspan", { class: "sk-n" }, num));
        g.append(t);
      }
    }
    const outs = flow.links.filter((l) => l.source === nd.id).sort((a, b) => b.value - a.value);
    const show = (cx, cy) => {
      root.classList.add("on");
      for (const p of bandEls.get(nd.id) || []) p.classList.add("hi");
      const next = outs.slice(0, 3).map((l) => ({ value: n(l.value), label: `→ ${say(opts, at.get(l.target).nd)}` }));
      tip(cx, cy, words, [{ color, value: n(nd.value), label: `${unit}${share(nd.value, flow.total) ? `, ${share(nd.value, flow.total)} of all` : ""}` },
        ...next, ...(outs.length > 3 ? [{ value: "", label: `and ${outs.length - 3} more` }] : []),
        ...(pick ? [{ value: "", label: "Click to open it" }] : [])]);
    };
    const hide = () => { root.classList.remove("on"); for (const p of bandEls.get(nd.id) || []) p.classList.remove("hi"); untip(); };
    g.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    g.addEventListener("pointerleave", hide);
    g.addEventListener("focus", () => { const r = g.getBoundingClientRect(); show(r.left + r.width / 2, r.top); });
    g.addEventListener("blur", hide);
    if (pick) {
      g.addEventListener("click", pick);
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    }
    gNodes.append(g);
  }
  return root;
}

// The same figures as rows: one per band, with the visits at its start.
function asTable(flow, opts) {
  const byId = new Map(flow.columns.flatMap((c) => c.nodes).map((nd) => [nd.id, nd]));
  const title = (nd) => flow.columns.find((c) => c.nodes.includes(nd))?.title || "";
  const rows = flow.links.map((l, i) => {
    const a = byId.get(l.source), b = byId.get(l.target);
    return { __k: i, step: `${title(a)} → ${title(b)}`, from: say(opts, a), at: a.value, to: say(opts, b), v: l.value, col: a.col, sh: a.value ? l.value / a.value : 0 };
  }).sort((x, y) => x.col - y.col || y.v - x.v);
  return table([
    { key: "step", label: "Step" },
    { key: "from", label: "From" },
    { key: "at", label: `${opts.unitTitle || "Visits"} there`, num: true },
    { key: "to", label: "To" },
    { key: "v", label: opts.unitTitle || "Visits", num: true },
    { key: "sh", label: "Share of From", num: true, fmt: (_, x) => share(x.v, x.at) || "-", csv: (x) => x.sh.toFixed(4) },
  ], { caption: opts.label || "Flow", rows, file: opts.file, limit: 12, sortKey: "col", dir: 1, search: true, placeholder: "Search pages or sources", empty: "Nothing moved." });
}

/* The map, a legend, and a Map / Table switch. opts: label, unit, unitTitle,
   say(node) -> words, onPick(node), pickAll, width, height, file (CSV name), note. */
export function sankey(flow, opts = {}) {
  if (!flow || !flow.total) return h("p", { class: "empty" }, opts.empty || "No visit to draw.");
  const W = Math.max(300, Math.round(opts.width || fitWidth()));
  const wrap = h("div", { class: "sk" });
  const map = h("div", { class: "sk-map" }, h("div", { class: "sk-scroll" }, draw(flow, opts, Math.max(W, 120 * flow.columns.length))));
  const kinds = [...new Set(flow.columns.flatMap((c) => c.nodes.map((nd) => nd.kind)))];
  const key = legend(Object.keys(KIND).filter((k) => kinds.includes(k)).map((k) => [opts.kindWords?.[k] || KIND[k][0], KIND[k][1]]));
  map.append(key);
  let tbl = null;
  const tableBox = h("div", { class: "sk-table" });
  const showTable = (on) => {
    if (on && !tbl) tableBox.append(tbl = asTable(flow, opts));
    map.hidden = on;
    tableBox.hidden = !on;
    bMap.setAttribute("aria-pressed", String(!on));
    bTable.setAttribute("aria-pressed", String(on));
  };
  const bMap = h("button", { type: "button", onclick: () => showTable(false) }, "Map");
  const bTable = h("button", { type: "button", onclick: () => showTable(true) }, "Table");
  wrap.append(h("div", { class: "sk-tools" }, opts.tools || null, h("span", { class: "grow" }),
    h("div", { class: "seg plain", role: "group", "aria-label": "Show the flow as" }, bMap, bTable)), map, tableBox);
  showTable(W < NARROW);
  if (opts.note) wrap.append(h("p", { class: "note" }, opts.note));
  return wrap;
}

// The width a full-width chart is drawn at (charts.js does the same).
function fitWidth() {
  const p = document.getElementById("panel");
  return p ? p.clientWidth - parseFloat(getComputedStyle(p).paddingLeft) * 2 - 40 : 720;
}
