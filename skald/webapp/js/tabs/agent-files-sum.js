// Traffic › Agent files (SKALD-56), summed over a range: agent_files.json's days
// (agent_files.py, recounted by audit_agent_files.py). No DOM here, so node can
// test the sums (tests/js/agent-files-sum.mjs).
//
// The honesty rules, as costsum.js keeps them:
//   * only verified ("ok") days are summed; a day without the figure (counted
//     before it existed) is counted in `unrecorded`, never added in as zero
//   * the files are kept for the last 30 days only: a range reaching further
//     back sums the kinds and names over every day, the files over the days that
//     kept them (`filesDays`), and says so
//   * each day keeps its 50 busiest files and 20 busiest names per group; the rest
//     are summed per kind (`rest`) and as one "(all others)" name, so every total
//     still adds up

export const OTHER = "(all others)";
export const KINDS = ["markdown", "okf", "llms_txt", "agent_card", "robots_txt", "sitemap"];
export const WHO = ["ai_asked", "ai_training", "search_engines", "bots", "people"];

export const KIND_WORDS = {
  markdown: "Markdown copies", okf: "OKF bundle", llms_txt: "llms.txt",
  agent_card: "Agent cards", robots_txt: "robots.txt", sitemap: "Sitemaps",
};
export const KIND_ONE = {
  markdown: "Markdown copy", okf: "OKF bundle file", llms_txt: "llms.txt",
  agent_card: "Agent card", robots_txt: "robots.txt", sitemap: "Sitemap",
};
export const KIND_SAYS = {
  markdown: "A page's Markdown copy (page.md), the version an AI agent reads instead of the HTML.",
  okf: "Files of an OKF bundle (Open Knowledge Format): a folder of Markdown files, /okf/index.md, that indexes the site for AI.",
  llms_txt: "/llms.txt or /llms-full.txt: a Markdown list of the site's main pages for AI assistants.",
  agent_card: "Files under /.well-known/ that describe an AI agent or MCP server: agent-card.json, agent.json, mcp.json, ai-plugin.json, ai-catalog.json.",
  robots_txt: "/robots.txt: the rules crawlers read before they crawl.",
  sitemap: "sitemap*.xml: the list of the site's pages for crawlers.",
};
export const WHO_WORDS = {
  ai_asked: "AI assistants", ai_training: "AI crawlers", search_engines: "Search engines",
  bots: "Other bots and tools", people: "People",
};
export const WHO_SAYS = {
  ai_asked: "an assistant fetching for someone's question, seconds ago",
  ai_training: "an AI company's crawler collecting for training or AI search",
  search_engines: "Google, Bing and the other search crawlers",
  bots: "SEO tools, monitors, scripts, AI tools Skald does not name yet, and browser-like clients that never showed a page",
  people: "a person's browser",
};
export const WHO_COLOR = {
  ai_asked: "var(--g-answer_engines)", ai_training: "var(--af-training)",
  search_engines: "var(--g-search_engines)", bots: "var(--g-bots)", people: "var(--g-people)",
};

/* The days of a range that hold the figure: [[day, blob]] and how many lack it.
   A range that ends today takes today's blob too, when there is one. */
export function daysOf(file, r) {
  if (!file) return { used: [], unrecorded: 0 };
  if (r.kind === "today") {
    const t = file.today;
    return t && t.files ? { used: [[t.day || "today", t.files]], unrecorded: 0 } : { used: [], unrecorded: t ? 1 : 0 };
  }
  const used = [];
  let unrecorded = 0;
  for (const d of file.days || []) {
    if (d.day < r.first || d.day > r.last) continue;
    if (d.state !== "ok") continue;
    if (d.files) used.push([d.day, d.files]);
    else unrecorded += 1;
  }
  const t = file.today;
  if (r.inc && t && t.files && t.day && t.day >= r.first && t.day <= r.last) used.push([t.day, t.files]);
  return { used, unrecorded };
}

const addTo = (into, from) => { for (const [k, v] of Object.entries(from || {})) into[k] = (into[k] || 0) + (v || 0); return into; };
const total = (o) => Object.values(o || {}).reduce((a, v) => a + (v || 0), 0);

/* Everything the tab shows for a range. `kind` narrows the names and files to one kind. */
export function sumRange(file, r, kind = "") {
  const { used, unrecorded } = daysOf(file, r);
  const kinds = {};
  const names = new Map();
  const files = new Map();
  const rest = {};
  const series = new Map();
  let filesDays = 0;
  for (const [day, blob] of used) {
    const perDay = {};
    for (const [k, v] of Object.entries(blob.kinds || {})) {
      const a = kinds[k] || (kinds[k] = { requests: 0, status: {}, who: {} });
      a.requests += v.requests || 0;
      addTo(a.status, v.status);
      addTo(a.who, v.who);
      if (!kind || kind === k) addTo(perDay, v.who);
    }
    series.set(day, perDay);
    for (const [who, byName] of Object.entries(blob.names || {})) {
      for (const [name, byKind] of Object.entries(byName)) {
        const n = kind ? byKind[kind] || 0 : total(byKind);
        if (!n) continue;
        const key = `${who}\u0000${name}`;
        const a = names.get(key) || { who, name, folded: name === OTHER, requests: 0, kinds: {} };
        a.requests += n;
        addTo(a.kinds, kind ? { [kind]: byKind[kind] } : byKind);
        names.set(key, a);
      }
    }
    if (blob.files) {
      filesDays += 1;
      for (const [path, f] of Object.entries(blob.files)) {
        if (kind && f.kind !== kind) continue;
        const a = files.get(path) || { path, kind: f.kind, requests: 0, status: {}, who: {}, names: {}, last: null, days: [] };
        a.requests += f.requests || 0;
        addTo(a.status, f.status);
        addTo(a.who, f.who);
        addTo(a.names, f.names);
        if (f.last && (!a.last || f.last > a.last)) a.last = f.last;
        a.days.push([day, f.requests || 0]);
        files.set(path, a);
      }
      for (const [k, v] of Object.entries(blob.rest || {})) {
        if (kind && k !== kind) continue;
        const a = rest[k] || (rest[k] = { files: 0, requests: 0 });
        a.files += v.files || 0;
        a.requests += v.requests || 0;
      }
    }
  }
  const all = Object.values(kinds).reduce((a, k) => a + k.requests, 0);
  const shown = kind ? kinds[kind]?.requests || 0 : all;
  const who = {};
  for (const [k, v] of Object.entries(kinds)) if (!kind || kind === k) addTo(who, v.who);
  const status = {};
  for (const [k, v] of Object.entries(kinds)) if (!kind || kind === k) addTo(status, v.status);
  return {
    days: used.length, unrecorded, filesDays, total: all, shown, kinds, who, status,
    names: [...names.values()].sort((a, b) => b.requests - a.requests || a.name.localeCompare(b.name)),
    files: [...files.values()].sort((a, b) => b.requests - a.requests || a.path.localeCompare(b.path)),
    rest, series,
  };
}

/* A file's answers in three words: ok (2xx, 304), moved (3xx but 304), failed (4xx, 5xx). */
export function answers(status) {
  const out = { ok: 0, moved: 0, failed: 0 };
  for (const [code, n] of Object.entries(status || {})) {
    const c = String(code);
    if (c === "304" || c[0] === "2") out.ok += n;
    else if (c[0] === "3") out.moved += n;
    else if (c[0] === "4" || c[0] === "5") out.failed += n;
  }
  return out;
}

/* The files that need a look: any request answered 4xx or 5xx, or moved
   elsewhere (3xx). Failed ones first, then by requests. */
export function attention(files) {
  return files.map((f) => ({ ...f, a: answers(f.status) })).filter((f) => f.a.failed || f.a.moved)
    .sort((x, y) => (y.a.failed > 0) - (x.a.failed > 0) || y.a.failed + y.a.moved - (x.a.failed + x.a.moved) || x.path.localeCompare(y.path));
}

/* The AI share of a who map: assistants plus AI crawlers. */
export const aiOf = (who) => (who?.ai_asked || 0) + (who?.ai_training || 0);
