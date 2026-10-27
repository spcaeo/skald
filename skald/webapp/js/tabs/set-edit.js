// Settings v2: a page shows each part as rows (its value and a pill); the form to change a
// part opens in a drawer, its id in the address (edit=<id>), so a link, a reload and Back all
// land on it. A page names its parts once, at import:
//
//   editPart(id, { title, body, size })   body(m, s, ctx, id) -> nodes, or a string (the reason
//                                         it cannot open: role, demo, a server without accounts)
//   editPart("ip-", { prefix: true, ... }) one part for many ids: ip-<code> (a code, never a value)
//   ctx.close()                           closes the drawer; ctx.d is the drawer once drawn
//   openEdit(id, m, s)                    the click (and the link, through overlays.js)
//   editRow({ id, m, title, line, ... })  a row that opens it (set-ui.js's statusRow)

import { h, toast } from "../ui.js";
import { openDrawer } from "../drawer.js";
import { statusRow } from "./set-ui.js";

const PARTS = new Map();
const NOT_HERE = "That part is not on this page.";

export function editPart(id, part) { PARTS.set(id, part); }
const partOf = (id) => PARTS.get(id) || [...PARTS].find(([k, p]) => p.prefix && id.startsWith(k) && id.length > k.length)?.[1];
export const hasPart = (id) => !!partOf(id);

async function drawPart(id, m, s = {}) {
  const p = partOf(id);
  if (!p) return NOT_HERE;
  const ctx = { d: null, close: () => ctx.d?.close() };
  const got = await p.body(m, s, ctx, id);
  if (typeof got === "string") return got;
  const title = typeof p.title === "function" ? p.title(m, id) : p.title;
  ctx.d = openDrawer({ title, size: p.size || "md", key: "edit", className: "set-dw set-edit", body: h("div", { class: "set-edit-b" }, got), route: { key: "edit", value: id } });
  return ctx.d;
}
/* A link (overlays.js): the reason, when it cannot open, is said by the page's plain line. */
export const openEditKey = (v, m, s) => (/^[A-Za-z0-9_-]{1,60}$/.test(v) ? drawPart(v, m, s) : NOT_HERE);
/* A click: the reason, when it cannot open, in a toast. */
export async function openEdit(id, m, s = {}) {
  const got = await drawPart(id, m, s);
  if (typeof got === "string") toast(got);
  return got;
}

/* A row that opens a part's drawer: its name, its value in words, a pill when it has a state. */
export function editRow({ id, m, title, line = "", kind = "", word = "", iconName = "", label = "" }) {
  return statusRow({ iconName, title, line, kind, word, label: label || `Change ${title}`, onOpen: () => openEdit(id, m) });
}
