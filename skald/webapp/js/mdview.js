// Words from the docs, drawn with the page's own elements. tools/build-about.py
// turns the markdown into plain data (about-data.js, help-data.js); this draws
// it. No HTML from the docs is ever injected: every piece is a text node.
//
//   segments  {s} text, {b} bold, {i} italic, {code}, {a, href} a link, {ref: n} a footnote
//   blocks    {t: p|quote|ul|ol|h2|h3|h4|pre|table}

import { h } from "./ui.js";

export function seg(x) {
  if (x.b != null) return h("strong", null, x.b);
  if (x.i != null) return h("em", null, x.i);
  if (x.code != null) return h("code", null, x.code);
  if (x.a != null) {
    // Links to other sites open in a new tab and send no referrer; links inside the app stay.
    const outside = /^https?:/.test(x.href);
    return h("a", { href: x.href, class: x.cite ? "cite" : null, ...(outside ? { target: "_blank", rel: "noopener noreferrer" } : {}) }, x.a);
  }
  if (x.ref != null) return `[${x.ref}]`;
  return x.s;
}
export const line = (segs) => (segs || []).map(seg);

// shift: how many levels a heading moves down (the About page draws a doc's ## as h3), max: the deepest.
export function blockList(blocks, { shift = 1, max = 4 } = {}) {
  return blocks.map((b) => {
    if (b.t === "p") return h("p", null, line(b.in));
    if (b.t === "quote") return h("blockquote", null, line(b.in));
    if (b.t === "ul" || b.t === "ol") return h(b.t, b.start ? { start: b.start } : null, b.items.map((it) => h("li", null, line(it))));
    if (/^h[2-4]$/.test(b.t)) return h(`h${Math.min(max, Number(b.t[1]) + shift)}`, null, b.text);
    if (b.t === "pre") return h("pre", { class: "md-pre", tabindex: "0" }, h("code", null, b.text));
    if (b.t === "table") {
      return h("div", { class: "md-table", tabindex: "0" }, h("table", null,
        h("thead", null, h("tr", null, b.head.map((c) => h("th", { scope: "col" }, line(c))))),
        h("tbody", null, b.rows.map((r) => h("tr", null, r.map((c) => h("td", null, line(c))))))));
    }
    return null;
  });
}
