// Personal values never go in the address (2.21). An address (IPv4 or IPv6), an
// email, or a search for a person becomes an opaque token, "~" and 10 letters or
// digits, that only this browser reads back: the token and its value are kept in
// this browser's storage (at most 200, each for 30 days), never sent anywhere.
//
//   mask("ip:203.0.113.5|path:/pricing/")  -> "ip:~k2f9a0x7qm|path:/pricing/"
//   unmask("ip:~k2f9a0x7qm|path:/pricing/") -> the value again, in this browser
//   mask(q, true)                           -> the whole value as one token (a person search)
//
// A link made in another browser keeps its token: unmask leaves it as it is, and the
// page that reads it says so in one plain line (js/overlays.js). state.js and
// tablestate.js pass every value of the address through here, both ways.

import { personalParts, TOKEN, isToken } from "./routekeys.js";

const STORE = "ti-route-tokens";
const MAX = 200;
const DAYS = 30;
const mem = new Map();          // token -> [value, at]
let loaded = false;

function load() {
  if (loaded) return;
  loaded = true;
  try {
    const raw = JSON.parse(globalThis.localStorage?.getItem(STORE) || "{}");
    const old = Date.now() - DAYS * 864e5;
    for (const [t, v] of Object.entries(raw)) if (Array.isArray(v) && v[1] > old && isToken(t)) mem.set(t, v);
  } catch { /* storage blocked or broken: this page's memory only */ }
}
function save() {
  const rows = [...mem.entries()].sort((a, b) => b[1][1] - a[1][1]).slice(0, MAX);
  try { globalThis.localStorage?.setItem(STORE, JSON.stringify(Object.fromEntries(rows))); } catch { /* storage blocked */ }
}
function fresh() {
  const a = "abcdefghijklmnopqrstuvwxyz0123456789";
  const bytes = new Uint8Array(10);
  try { globalThis.crypto.getRandomValues(bytes); } catch { for (let i = 0; i < 10; i++) bytes[i] = Math.floor(Math.random() * 256); }
  return `~${[...bytes].map((b) => a[b % 36]).join("")}`;
}

/* The token for a value: the same one each time in this browser. */
export function tokenFor(value) {
  load();
  const v = String(value);
  for (const [t, row] of mem) if (row[0] === v) { row[1] = Date.now(); return t; }
  let t = fresh();
  while (mem.has(t)) t = fresh();
  mem.set(t, [v, Date.now()]);
  save();
  return t;
}
/* The value a token stands for in this browser, or null. */
export function valueOf(token) {
  load();
  return mem.get(token)?.[0] ?? null;
}

/* A value with its personal parts as tokens; `whole`: the whole value as one token. */
export function mask(value, whole = false) {
  const text = String(value ?? "");
  if (!text) return text;
  if (whole) return isToken(text) ? text : tokenFor(text);
  const parts = personalParts(text);
  if (!parts.length) return text;
  let out = "", at = 0;
  for (const [a, b] of parts) { out += text.slice(at, a) + tokenFor(text.slice(a, b)); at = b; }
  return out + text.slice(at);
}
/* A value with each token this browser knows put back; unknown tokens stay. */
export function unmask(value) {
  const text = String(value ?? "");
  if (!text.includes("~")) return text;
  return text.replace(TOKEN, (t) => valueOf(t) ?? t);
}
