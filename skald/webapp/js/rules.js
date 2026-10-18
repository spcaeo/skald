// The advanced filters (2.13): rules over every dimension a visit carries, joined by
// "all" (AND) or "any" (OR), with one level of groups. Pure, so node runs it
// (tests/js/rules.mjs); filterpanel.js draws the builder, state.js keeps the rules
// in the address, and the tabs that list single visits apply them.
//
//   tree  = {mode: "all"|"any", items: [rule | group]}
//   group = {mode: "all"|"any", items: [rule]}          (one level: a group holds rules)
//   rule  = {dim, op, vals: [string]}
//
// In the address (state.js `rules`):
//   all(country:is:US,CA;source:not:Direct%20or%20unknown;pages:ge:3;any(via:is:ChatGPT;via:is:Perplexity))
// A value is percent-encoded (and its brackets), so , ; : ( ) inside it never split it.
//
// The single filters older links carry (country=, path=, source=, device=, browser=,
// campaign=, referrer=) are rules too: fromState reads them in, toState writes a rule
// back as one when it can, so the tabs that count breakdowns (which can apply one value
// per breakdown, never crossed) keep applying them, and old links keep working.
//
// Honest matching: a value nobody recorded matches no rule ("is not Direct" does not
// keep a visit whose source is not recorded: it could have been Direct), except a rule
// that names "Not recorded" itself. Where having no value is an answer (no campaign, no
// assistant), "None" is a value like any other.

import { visitPages } from "./visitpages.js";

export const NR = "(not recorded)";   // the value "Not recorded" in a rule
export const NONE = "(none)";         // the value "None" where having none is an answer

export const OPS = { is: "is", not: "is not", has: "contains", starts: "starts with", ge: "at least", le: "at most" };
export const OP_SIGN = { is: "is", not: "is not", has: "contains", starts: "starts with", ge: "≥", le: "≤" };
const OPS_BY = { enum: ["is", "not"], text: ["is", "not", "has", "starts"], num: ["ge", "le", "is"] };

const LINKS = ["vid", "address", "hash"];
const NAMELESS = new Set(["(none)", "(not kept)", "(this site)", ""]);
const blank = (v) => v == null || v === "" || v === "Unknown";
const host = (v) => (/\./.test(v || "") ? v : "");
const trailPaths = (j) => (j.trail || []).map((p) => (Array.isArray(p) ? p[0] : p?.path)).filter(Boolean);

/* Every dimension Skald keeps per visit (the journeys, DATA-CONTRACT.md "visits.json")
   and per request (the request log). visit(j) / request(r): the value or values, null
   when not recorded; absent: a dimension the list does not carry (the rule cannot apply).
   none: having no value is an answer, said "None". */
export const DIMS = [
  { key: "country", label: "Country", type: "enum", legacy: "country", visit: (j) => (blank(j.country) ? null : j.country), request: (r) => r.country || null },
  { key: "city", label: "City", type: "enum", visit: (j) => (blank(j.city) ? null : j.city) },
  { key: "source", label: "Source type", type: "enum", legacy: "source", visit: (j) => j.source || null, request: (r) => (r.group === "people" ? r.source || null : NONE), none: true },
  { key: "referrer", label: "Referring site", type: "text", legacy: "referrer", none: true,
    visit: (j) => [...new Set([j.ref_host, host(j.via)].filter(Boolean))], request: (r) => [...new Set([r.ref_host, r.referrer].filter(Boolean))] },
  { key: "campaign", label: "Campaign or UTM tag", type: "text", legacy: "campaign", none: true,
    visit: (j) => [...new Set([j.campaign, ...String(j.campaign || "").split(" / "), ...Object.values(j.utm || {})].filter((x) => x && x !== "-"))],
    request: (r) => [...new Set([[r.utm?.source, r.utm?.medium, r.utm?.campaign].filter(Boolean).join(" / "), ...Object.values(r.utm || {})].filter(Boolean))] },
  { key: "landing", label: "Landing page", type: "text", visit: (j) => j.landing || trailPaths(j)[0] || null },
  { key: "page", label: "Read a page", type: "text", legacy: "path", visit: (j) => trailPaths(j), request: (r) => r.path || null },
  { key: "device", label: "Device", type: "enum", legacy: "device", visit: (j) => j.device || null, request: (r) => r.device || null },
  { key: "browser", label: "Browser", type: "enum", legacy: "browser", visit: (j) => j.browser || null, request: (r) => (r.group === "people" || r.group === "ours" ? r.agent || null : NONE), none: true },
  { key: "os", label: "Operating system", type: "enum", visit: (j) => j.os || null, request: (r) => r.os || null },
  { key: "assistant", label: "AI assistant", type: "enum", none: true,
    visit: (j) => (j.source === "AI assistant" ? j.via || null : []), request: (r) => (r.assistant ? [r.assistant] : []) },
  { key: "crawler", label: "Crawler", type: "enum", none: true,
    request: (r) => (["answer_engines", "search_engines", "bots"].includes(r.group) ? r.agent || null : []) },
  { key: "visitor", label: "New or returning", type: "enum", visit: (j) => (j.returning === true ? "Returning" : j.returning === false ? "New" : null) },
  { key: "first", label: "First came from", type: "text",
    visit: (j) => {
      const ft = j.first_touch;
      if (!ft) return null;
      if (LINKS.includes(ft.by)) return ft.via || (!NAMELESS.has(ft.referrer || "") ? ft.referrer : "") || ft.source || null;
      if (ft.by === "none") return j.via || j.source || null;   // this visit was the first
      return null;
    } },
  { key: "pages", label: "Pages read", type: "num", visit: (j) => visitPages(j).all ?? (Number.isFinite(j.pages) ? j.pages : null) },
  { key: "seconds", label: "Time on site", type: "num", unit: "time", visit: (j) => (Number.isFinite(j.seconds) ? j.seconds : null) },
  { key: "form", label: "Sent a form (lead)", type: "enum",
    visit: (j) => ((j.flags || []).includes("posted") || j.posted > 0 ? "Yes" : "No") },
];
export const DIM = Object.fromEntries(DIMS.map((d) => [d.key, d]));
export const opsOf = (dim) => OPS_BY[DIM[dim]?.type] || [];

// ---- matching ------------------------------------------------------------------------
const low = (v) => String(v).toLowerCase();
const isLeaf = (x) => x && typeof x.dim === "string";

/* Does one rule keep this value (or list of values)? Not recorded: only a rule that names it. */
export function ruleKeeps(rule, raw, d = DIM[rule.dim]) {
  const vals = rule.vals || [];
  if (raw == null || (typeof raw === "number" && Number.isNaN(raw))) return rule.op === "is" && vals.includes(NR);
  const list = (Array.isArray(raw) ? raw : [raw]).filter((x) => x != null && x !== "");
  if (!list.length || (list.length === 1 && list[0] === NONE)) {
    // No value, and having none is an answer: "is None" keeps it, "is not X" keeps it.
    if (!d?.none) return rule.op === "is" && vals.includes(NR);
    return rule.op === "is" ? vals.includes(NONE) : rule.op === "not" ? !vals.includes(NONE) : false;
  }
  if (d?.type === "num") {
    const x = Number(list[0]), lim = Number(vals[0]);
    if (!Number.isFinite(x) || !Number.isFinite(lim)) return false;
    return rule.op === "ge" ? x >= lim : rule.op === "le" ? x <= lim : rule.op === "is" ? x === lim : false;
  }
  const have = list.map(low), want = vals.filter((v) => v !== NR && v !== NONE).map(low);
  if (rule.op === "is") return have.some((x) => want.includes(x));
  if (rule.op === "not") return !have.some((x) => want.includes(x));
  if (rule.op === "has") return have.some((x) => want.some((w) => x.includes(w)));
  if (rule.op === "starts") return have.some((x) => want.some((w) => x.startsWith(w)));
  return false;
}

// Every rule of a tree, groups opened.
export const leaves = (tree) => (tree?.items || []).flatMap((x) => (isLeaf(x) ? [x] : leaves(x)));
export const ruleCount = (tree) => (tree?.items || []).length;

/* The rules a list cannot apply: "visit" (the journeys) or "request" (the request log). */
export function cannot(tree, kind = "visit") {
  return leaves(tree).filter((r) => !DIM[r.dim]?.[kind]);
}

/* The tree without the rules a list cannot apply (the banner names those). */
export function without(tree, kind = "visit") {
  const keep = (x) => (isLeaf(x) ? !!DIM[x.dim]?.[kind] : true);
  const strip = (t) => ({ mode: t.mode, items: t.items.filter(keep).map((x) => (isLeaf(x) ? x : strip(x))) });
  return tidy(strip(tidy(tree)));
}

/* A test for one item of a list, or null when a rule names a dimension the list does not carry. */
export function matcher(tree, kind = "visit") {
  if (!tree || !tree.items?.length) return () => true;
  if (cannot(tree, kind).length) return null;
  const one = (x) => {
    if (isLeaf(x)) { const d = DIM[x.dim]; return (row) => ruleKeeps(x, d[kind](row), d); }
    const tests = x.items.map(one);
    return x.mode === "any" ? (row) => tests.some((t) => t(row)) : (row) => tests.every((t) => t(row));
  };
  return one(tree);
}

// ---- tidy: what the builder may hand over -------------------------------------------
/* Drops rules with no dimension, operator or value, groups left empty, and any group
   below the first level (its rules join its parent). */
export function tidy(tree, depth = 0) {
  const items = [];
  for (const x of tree?.items || []) {
    if (isLeaf(x)) {
      const d = DIM[x.dim];
      const vals = (x.vals || []).map((v) => String(v).trim()).filter((v) => v !== "");
      if (!d || !opsOf(x.dim).includes(x.op) || !vals.length) continue;
      if (d.type === "num" && !Number.isFinite(Number(vals[0]))) continue;
      items.push({ dim: x.dim, op: x.op, vals: d.type === "num" ? [String(Number(vals[0]))] : [...new Set(vals)] });
    } else if (x && Array.isArray(x.items)) {
      const inner = tidy(x, depth + 1).items;
      if (depth >= 1) items.push(...inner);
      else if (inner.length === 1) items.push(inner[0]);
      else if (inner.length) items.push({ mode: x.mode === "any" ? "any" : "all", items: inner });
    }
  }
  return { mode: tree?.mode === "any" ? "any" : "all", items };
}

// ---- in the address ------------------------------------------------------------------
const escV = (v) => encodeURIComponent(v).replace(/\(/g, "%28").replace(/\)/g, "%29");
export function encode(tree) {
  const t = tidy(tree);
  if (!t.items.length) return "";
  const item = (x) => (isLeaf(x) ? `${x.dim}:${x.op}:${x.vals.map(escV).join(",")}` : `${x.mode}(${x.items.map(item).join(";")})`);
  return `${t.mode}(${t.items.map(item).join(";")})`;
}

// Read a tree back; anything garbled is left out, never guessed.
export function decode(text) {
  const s = String(text || "").trim();
  let i = 0;
  const group = () => {
    const m = /^(all|any)\(/.exec(s.slice(i));
    if (!m) return null;
    i += m[0].length;
    const items = [];
    while (i < s.length && s[i] !== ")") {
      if (/^(all|any)\(/.test(s.slice(i))) { const g = group(); if (g) items.push(g); else return null; }
      else {
        let j = i;
        while (j < s.length && s[j] !== ";" && s[j] !== ")") j++;
        const [dim, op, vals = ""] = s.slice(i, j).split(":");
        try { items.push({ dim, op, vals: vals.split(",").map(decodeURIComponent) }); } catch { /* a garbled value */ }
        i = j;
      }
      if (s[i] === ";") i++;
    }
    if (s[i] !== ")") return null;
    i++;
    return { mode: m[1], items };
  };
  const t = group();
  return tidy(t || { mode: "all", items: [] });
}

// ---- the single filters older links carry --------------------------------------------
export const LEGACY = ["country", "path", "source", "device", "browser", "campaign", "referrer"];
const DIM_OF = Object.fromEntries(DIMS.filter((d) => d.legacy).map((d) => [d.legacy, d.key]));

/* The whole filter of a state: its single filters as rules, and its `rules`. */
export function fromState(s) {
  const legacy = LEGACY.filter((k) => s[k]).map((k) => ({ dim: DIM_OF[k], op: k === "path" ? (s.pathmode === "starts" ? "starts" : "has") : "is", vals: [s[k]] }));
  const r = decode(s.rules);
  if (!legacy.length) return r;
  if (r.mode === "all" || r.items.length === 1) return tidy({ mode: "all", items: [...legacy, ...r.items] });
  return tidy({ mode: "all", items: [...legacy, { mode: "any", items: leaves(r) }] });
}

/* The top rules a single filter can say: in an "all" tree (or a tree of one rule), the
   first one-value rule of each breakdown the single filters know. */
export function singles(tree, { tidied = false } = {}) {
  const t = tidied ? tree : tidy(tree);
  const out = new Map();   // single filter key -> its rule
  if (t.mode !== "all" && t.items.length !== 1) return out;
  for (const x of t.items) {
    const k = isLeaf(x) && DIM[x.dim]?.legacy;
    const fits = k && !out.has(k) && x.vals.length === 1 && x.vals[0] !== NR && x.vals[0] !== NONE
      && (k === "path" ? x.op === "has" || x.op === "starts" : x.op === "is");
    if (fits) out.set(k, x);
  }
  return out;
}
export const sameRule = (a, b) => isLeaf(a) && isLeaf(b) && a.dim === b.dim && a.op === b.op && a.vals.join("\u0001") === b.vals.join("\u0001");

/* A tree as state keys: every rule a single filter can say becomes one (the tabs that
   count breakdowns apply those); the rest stays in `rules`. */
export function toState(tree) {
  const t = tidy(tree);
  const patch = Object.fromEntries(LEGACY.map((k) => [k, ""]));
  patch.pathmode = "contains";
  patch.rules = "";
  const one = singles(t, { tidied: true });
  for (const [k, x] of one) { patch[k] = x.vals[0]; if (k === "path") patch.pathmode = x.op === "starts" ? "starts" : "contains"; }
  const taken = new Set(one.values());
  const rest = t.items.filter((x) => !taken.has(x));
  if (rest.length) patch.rules = encode({ mode: one.size ? "all" : t.mode, items: rest });
  return patch;
}

// ---- words ----------------------------------------------------------------------------
/* "Country is USA, CAN"; fmt(dim, value) says a value (a country's flag and code). */
export function ruleWords(rule, fmt = (d, v) => v) {
  const d = DIM[rule.dim];
  const say = (v) => (v === NR ? "Not recorded" : v === NONE ? "None" : d?.unit === "time" ? timeWords(Number(v)) : fmt(rule.dim, v));
  return { field: d?.label || rule.dim, op: OP_SIGN[rule.op] || rule.op, val: rule.vals.map(say).join(rule.op === "not" ? " or " : ", ") };
}
export function treeWords(tree, fmt) {
  const t = tidy(tree);
  const one = (x) => (isLeaf(x) ? (({ field, op, val }) => `${field} ${op} ${val}`)(ruleWords(x, fmt)) : `(${x.items.map(one).join(x.mode === "any" ? " or " : " and ")})`);
  return t.items.map(one).join(t.mode === "any" ? "; or " : "; ");
}
export function timeWords(sec) {
  if (!Number.isFinite(sec)) return "";
  if (sec < 60) return `${sec} s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  return m < 60 ? `${m} min${s ? ` ${s} s` : ""}` : `${Math.floor(m / 60)} h ${m % 60} min`;
}
