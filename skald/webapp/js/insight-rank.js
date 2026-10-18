// Insights, ordered and folded (2.13): the biggest first, one card per subject,
// one sentence each. No DOM and no other module here, so tests/js/insights.mjs
// runs it in node. Nothing is counted here: every number shown is one the data
// layer wrote into insights.json (insights.py, conversions_leads.py).

/* Impact: how much changed, in what it is worth. A lead counts as ten visits; an AI
   fetch or a crawl as a quarter (no one waits on it); a finding the data layer gave
   low confidence (small numbers) counts less. An order only: never shown as a figure. */
const WORTH = { leads: 10, readers: 1, visits: 1, entries: 1, not_found: 1, requests: 1, ai_fetches: 0.25, bots: 0.1, search: 0.1, server_errors: 2 };
const SURE = { high: 1, medium: 0.6, low: 0.3 };
export function impact(i) {
  const moved = Math.abs((i.after ?? 0) - (i.before ?? 0));
  return moved * (WORTH[i.metric] ?? 1) * (SURE[i.confidence] ?? 0.3);
}

/* The subject a finding is about, the same whatever list it came from:
   chatgpt.com as a referring site and as an AI assistant is one subject. */
export function subjectKey(i) {
  const name = String(i.subject?.name ?? "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "");
  return name || `${i.type}:${i.title}`;
}

/* One card per subject: the finding with the most impact leads it, the others ride
   along under it ("2 more about chatgpt.com"). Leaders come biggest first. */
export function fold(list) {
  const by = new Map();
  for (const i of [...list].sort((a, b) => impact(b) - impact(a) || String(a.title).localeCompare(String(b.title)))) {
    const k = subjectKey(i);
    if (!by.has(k)) by.set(k, { lead: i, more: [] });
    else {
      const g = by.get(k);
      // The same words twice (a referring site and an assistant say the same thing): kept once.
      if (sentence(i) !== sentence(g.lead) && !g.more.some((x) => sentence(x) === sentence(i))) g.more.push(i);
    }
  }
  return [...by.values()];
}

// The data layer's metric names, in words.
const WORDS = { ai_fetches: "AI fetches", server_errors: "server errors", not_found: "404s", search: "search crawls" };
/* The finding in one sentence: its title, with metric names in words and without the
   "(188 to 228)" the number beside it already says. */
export function sentence(i) {
  let t = String(i.title || "");
  for (const [k, w] of Object.entries(WORDS)) t = t.replace(new RegExp(`\\b${k}\\b`, "g"), w);
  if (i.before != null && i.after != null) t = t.replace(/\s*\([\d,.]+ to [\d,.]+\)\s*$/, "");
  return t.trim();
}

/* The one number on the card and the words under it. */
export function headline(i) {
  const n = (v) => Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
  const metric = WORDS[i.metric] || i.metric || "";
  if (i.type === "gone") return { value: i.before, words: `${metric} before, none now` };
  if (i.type === "anomaly") return { value: i.after, words: i.before != null ? `against a usual ${n(i.before)}` : metric };
  if (i.type === "opportunity") {
    if (i.metric === "ai_fetches") return { value: i.before, words: "AI fetches in 30 days" };
    if (i.metric === "entries") return { value: i.before, words: "visits started here" };
    return { value: i.after, words: "people from links elsewhere" };
  }
  if (i.before == null) return { value: i.after, words: i.type === "new" ? `${metric}, first time` : metric };
  // The sentence says the change; the number says where it stands and where it was.
  return { value: i.after, words: `${metric}, was ${n(i.before)}` };
}
