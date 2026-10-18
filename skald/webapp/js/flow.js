// Visitor flow: how visits moved from where they came from, through their
// pages in order, to where they left. Pure: no DOM, so node can test it
// (tests/js/flow.mjs). sankey.js draws what this returns.
//
// Nothing is counted anew. A flow is the anonymous journeys the page already
// holds (visits.py writes them; the last `journey_days` days and today), each
// visit read once, by one stated rule:
//
//   * column 0 is the visit's source type (or who sent it); column k is the
//     k-th page it was seen on, in-app moves included, exactly as "Common next
//     steps" counts them
//   * the same page twice in a row (a reload) is one step: "/a → /a" is not a move
//   * a visit that ends after its k-th page flows to "Left after k pages"; one
//     with more pages than the columns flows to "Went on to more pages"
//   * each column keeps its `top` biggest values and folds the rest into
//     "(other pages)", so every column still adds up to the visits
//
// So the first page column is "Where visits started", the moves between pages
// are "Common next steps" less the reloads, and the pages each "Left" band
// comes from are "Where visits ended". check() proves a flow adds up; a flow
// that does not is withheld, never drawn.

export const OTHER = "(other pages)";
export const OTHER_SOURCES = "(other sources)";

// A visit's pages in order, a reload counted once.
export function pagesOf(j) {
  const out = [];
  for (const p of j.trail || []) {
    const path = typeof p === "string" ? p : p.path ?? p[0];
    if (path && out[out.length - 1] !== path) out.push(path);
  }
  return out;
}

const plural = (k, one, many) => `${k} ${k === 1 ? one : many}`;
const leftWords = (k) => `Left after ${plural(k, "page", "pages")}`;

/* Who started a visit: its source type, or (by: "via") the assistant or site that
   sent it, else its source type. drill: the value a click opens (drill.js). */
export function startOf(j, by = "source") {
  const source = j.source || "Unknown";
  if (by !== "via" || !j.via) return { key: source, drill: ["source", source] };
  return { key: j.via, drill: [source === "AI assistant" ? "assistant" : "referrer", j.via] };
}

// The `top` biggest keys of a count; the rest fold. Ties by name, so a flow draws the same twice.
function keepers(count, top) {
  const ranked = [...count].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
  return new Set((ranked.length > top ? ranked.slice(0, top - 1) : ranked).map(([k]) => k));
}

/* The flow of a list of journeys:
     { total, columns: [{title, nodes: [Node]}], links: [{source, target, value}] }
     Node = { id, col, key, label, value, kind: start|page|other|left|more, end, drill }
   depth: page columns drawn (after the start column); top: values kept per column. */
export function flowOf(journeys, { depth = 4, top = 7, start = "source" } = {}) {
  const seqs = journeys.map((j) => ({ start: startOf(j, start), pages: pagesOf(j) })).filter((x) => x.pages.length);
  const counts = Array.from({ length: depth + 1 }, () => new Map());
  for (const x of seqs) {
    counts[0].set(x.start.key, (counts[0].get(x.start.key) || 0) + 1);
    x.pages.slice(0, depth).forEach((p, i) => counts[i + 1].set(p, (counts[i + 1].get(p) || 0) + 1));
  }
  const kept = counts.map((c) => keepers(c, top));
  const nodes = new Map(), links = new Map();
  const node = (col, key, make) => {
    const id = `${col}\u0001${key}`;
    let got = nodes.get(id);
    if (!got) nodes.set(id, got = { id, col, key, value: 0, ...make() });
    got.value += 1;
    return got;
  };
  const link = (a, b) => {
    const id = `${a.id}\u0002${b.id}`;
    const got = links.get(id);
    if (got) got.value += 1;
    else links.set(id, { source: a.id, target: b.id, value: 1 });
  };
  for (const x of seqs) {
    const s = kept[0].has(x.start.key) ? x.start : { key: OTHER_SOURCES, drill: null };
    let prev = node(0, s.key, () => ({ label: s.key, kind: s.drill ? "start" : "other", drill: s.drill }));
    const shown = x.pages.slice(0, depth);
    shown.forEach((p, i) => {
      const keep = kept[i + 1].has(p);
      const here = node(i + 1, keep ? p : OTHER, () => (keep
        ? { label: p, kind: "page", drill: [i ? "path" : "landing", p] }
        : { label: OTHER, kind: "other", drill: null }));
      link(prev, here);
      prev = here;
    });
    const k = shown.length;
    const end = x.pages.length > depth
      ? node(depth + 1, "more", () => ({ label: "Went on to more pages", kind: "more", end: true, drill: null }))
      : node(k + 1, `left${k}`, () => ({ label: leftWords(k), kind: "left", end: true, drill: null }));
    link(prev, end);
  }
  // Within a column: the biggest first, the folded tail after them, then the ends.
  const rank = { start: 0, page: 0, other: 1, more: 2, left: 3 };
  const columns = Array.from({ length: depth + 2 }, (_, i) => ({
    title: i === 0 ? (start === "via" ? "Came from" : "Source") : i === depth + 1 ? "After" : `Page ${i}`,
    nodes: [...nodes.values()].filter((nd) => nd.col === i)
      .sort((a, b) => rank[a.kind] - rank[b.kind] || b.value - a.value || String(a.key).localeCompare(String(b.key))),
  })).filter((c) => c.nodes.length);
  return { total: seqs.length, depth, columns, links: [...links.values()] };
}

/* A funnel as a flow (funnels.js): the starting source, then each page step a
   visit reached, in order, and "Left after step k" for those that went no
   further. reached: [{j, r}] with r the page steps a visit reached (funnels.reached);
   names: the page steps' names. A visit that never met step 1 is not in the funnel. */
export function funnelFlowOf(reached, names) {
  const nodes = new Map(), links = new Map();
  const node = (col, key, make) => {
    const id = `${col}\u0001${key}`;
    let got = nodes.get(id);
    if (!got) nodes.set(id, got = { id, col, key, value: 0, ...make() });
    got.value += 1;
    return got;
  };
  const link = (a, b) => {
    const id = `${a.id}\u0002${b.id}`;
    const got = links.get(id);
    if (got) got.value += 1;
    else links.set(id, { source: a.id, target: b.id, value: 1 });
  };
  const last = names.length;
  let total = 0;
  for (const { j, r } of reached) {
    if (r < 1) continue;
    total += 1;
    const s = startOf(j);
    let prev = node(0, s.key, () => ({ label: s.key, kind: "start", drill: s.drill }));
    for (let k = 1; k <= Math.min(r, last); k++) {
      const here = node(k, `step${k}`, () => ({ label: names[k - 1], kind: "step", step: k, end: k === last, drill: null }));
      link(prev, here);
      prev = here;
    }
    if (r < last) link(prev, node(r + 1, `left${r}`, () => ({ label: `Left after step ${r}`, kind: "left", step: r, end: true, drill: null })));
  }
  const rank = { start: 0, step: 0, left: 1 };
  const columns = Array.from({ length: last + 1 }, (_, i) => ({
    title: i ? `Step ${i}` : "Source",
    nodes: [...nodes.values()].filter((nd) => nd.col === i).sort((a, b) => rank[a.kind] - rank[b.kind] || b.value - a.value || String(a.key).localeCompare(String(b.key))),
  })).filter((c) => c.nodes.length);
  return { total, depth: last, columns, links: [...links.values()] };
}

/* Does a flow add up? Every visit starts once and ends once; what flows into a
   node flows out of it; each column's nodes sum to the visits still moving.
   [] when it does; else what is off, in words. */
export function check(flow) {
  const out = [];
  const into = new Map(), from = new Map();
  for (const l of flow.links) {
    into.set(l.target, (into.get(l.target) || 0) + l.value);
    from.set(l.source, (from.get(l.source) || 0) + l.value);
  }
  const all = flow.columns.flatMap((c) => c.nodes);
  const sum = (xs) => xs.reduce((a, x) => a + x.value, 0);
  const starts = flow.columns[0]?.nodes || [];
  if (sum(starts) !== flow.total) out.push(`the starts sum to ${sum(starts)}, not the ${flow.total} visits`);
  const ends = all.filter((nd) => nd.end);
  if (sum(ends) !== flow.total) out.push(`the ends sum to ${sum(ends)}, not the ${flow.total} visits`);
  for (const nd of all) {
    if (nd.col > 0 && (into.get(nd.id) || 0) !== nd.value) out.push(`${nd.label} (column ${nd.col}) takes in ${into.get(nd.id) || 0}, not ${nd.value}`);
    if (!nd.end && (from.get(nd.id) || 0) !== nd.value) out.push(`${nd.label} (column ${nd.col}) sends on ${from.get(nd.id) || 0}, not ${nd.value}`);
  }
  return out;
}

/* The flow's own figures by name, at full depth and unfolded: what it must match.
     landing {page: visits}, moves {"/a → /b": times, reloads left out}, exits {page: visits}, starts {source: visits} */
export function ledger(journeys, start = "source") {
  const f = flowOf(journeys, { depth: 50, top: Infinity, start });
  const byId = new Map(f.columns.flatMap((c) => c.nodes).map((nd) => [nd.id, nd]));
  const out = { visits: f.total, starts: {}, landing: {}, moves: {}, exits: {} };
  const add = (o, k, v) => { o[k] = (o[k] || 0) + v; };
  for (const nd of f.columns[0]?.nodes || []) add(out.starts, nd.key, nd.value);
  for (const l of f.links) {
    const a = byId.get(l.source), b = byId.get(l.target);
    if (a.col === 0) add(out.landing, b.key, l.value);
    else if (b.kind === "page") add(out.moves, `${a.key} → ${b.key}`, l.value);
    else if (b.end) add(out.exits, a.key, l.value);
  }
  return out;
}

/* Which journeys a range can draw: those of its verified days whose journeys are
   all kept (a day's journeys number its visitors), and today's when the live
   count is whole. A day without them is left out and said, never filled in.
     { journeys, days: [day] drawn, short: [day] with only some journeys kept } */
export function keptFor(m, r) {
  const per = new Map();
  for (const j of m.journeys || []) (per.get(j.day) || per.set(j.day, []).get(j.day)).push(j);
  if (r.kind === "today") {
    const js = per.get(m.today) || [];
    const want = m.live?.state === "ok" && m.live.day === m.today ? m.live.figures?.readers : null;
    return want != null && js.length === want ? { journeys: js, days: [m.today], short: [] } : { journeys: [], days: [], short: [m.today] };
  }
  const out = { journeys: [], days: [], short: [] };
  for (const d of r.days || []) {
    if (d.state !== "ok") continue;
    const js = per.get(d.day) || [];
    if (d.readers != null && js.length === d.readers) { out.days.push(d.day); out.journeys.push(...js); }
    else if (js.length) out.short.push(d.day);   // some kept, not all: left out, and said
    // none kept: older than journey_days, said by the days covered
  }
  return out;
}
