// What the command palette finds in the figures (2.13): the pages, countries, cities,
// sources, referring sites, campaigns, AI assistants and crawlers seen in the
// chosen period, each opening the tab that lists it with its detail open
// (dd=<dim>:<value>). No DOM and no other module here, so tests/js/finder.mjs
// runs it in node.
//
// It lists names only, never a new figure: the count kept with each name is the
// same per-day count the tabs add up, used only to put the busiest first.

// [dimension, the words for its kind, the tab that lists it, where a day keeps it]
export const KINDS = [
  ["path", "Page", "traffic/pages", (d) => [d.pages]],
  ["country", "Country", "traffic/places", (d) => [d.by?.country]],
  // Only the days counted with a city file hold cities (logs.city_db): "Toronto, Ontario, CA".
  ["city", "City", "traffic/places", (d) => [d.by?.city]],
  ["source", "Source type", "traffic/sources", (d) => [d.by?.source]],
  ["referrer", "Referring site", "traffic/sources", (d) => [d.by?.referrer]],
  ["campaign", "Campaign", "traffic/sources", (d) => [d.by?.campaign]],
  ["assistant", "AI assistant", "ai/assistants", (d) => [d.cited_by]],
  ["bot", "Crawler or bot", "ai/crawlers", (d) => [d.engines?.training, d.engines?.asked, d.search_engines, d.bot_agents]],
  ["device", "Device", "traffic/places", (d) => [d.by?.device]],
  ["browser", "Browser", "traffic/places", (d) => [d.by?.browser]],
  ["os", "System", "traffic/places", (d) => [d.by?.os]],
];
// Folded tails and absences are not things to open (drill.js drillable).
const NOT_A_NAME = /^\((none|all others|this site|no campaign tag)\)$|^Unknown$/;

/* Every name the given days hold, by kind, with its count over those days.
   days: the period's verified days (app.json days) or today's live figures.
   say(dim, value): the words it is shown by ("🇨🇦 CAN" for CA), searched too.
   alias(dim, value): more words it is found by, never shown ("Canada"). */
export function findIndex(days, say = (_, v) => v, alias = () => "") {
  const seen = new Map();
  for (const d of days || []) {
    if (!d) continue;
    for (const [dim, group, tab, get] of KINDS) {
      for (const obj of get(d)) {
        for (const [value, n] of Object.entries(obj || {})) {
          if (!value || NOT_A_NAME.test(value) || (dim === "country" && value === "Unknown")) continue;
          const key = `${dim}\u0001${value}`;
          const e = seen.get(key) || { dim, group, tab, value, words: String(say(dim, value) ?? value), alias: String(alias(dim, value) || ""), n: 0 };
          e.n += Number(n) || 0;
          seen.set(key, e);
        }
      }
    }
  }
  return [...seen.values()];
}

/* How well an entry's text answers the query: 0 exact, 1 starts with it, 2 a word
   starts with it, 3 somewhere inside, null not at all. Every word of the query
   must be in the text; the first word decides the rank. */
export function score(text, q) {
  const t = String(text).toLowerCase();
  const words = String(q).trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length || !words.every((w) => t.includes(w))) return null;
  const whole = words.join(" ");
  if (t === whole) return 0;
  if (t.startsWith(whole)) return 1;
  if (new RegExp(`(^|[\\s/._:-])${whole.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(t)) return 2;
  return 3;
}

// The entries a query finds, the best first: rank, then the busiest, then by name.
export function find(entries, q, limit = 40) {
  const out = [];
  for (const e of entries) {
    const r = [score(e.words, q), score(e.value, q), e.alias ? score(e.alias, q) : null, score(`${e.words} ${e.group}`, q)].filter((x) => x != null);
    if (r.length) out.push([Math.min(...r), e]);
  }
  out.sort((a, b) => a[0] - b[0] || b[1].n - a[1].n || a[1].words.localeCompare(b[1].words));
  return out.slice(0, limit).map(([, e]) => e);
}

// What a found name opens: its tab, with its detail drawer open.
export const targetOf = (e) => ({ tab: e.tab, dd: `${e.dim}:${String(e.value).replace(/%/g, "%25").replace(/\|/g, "%7C")}` });

// A query that looks like a person's key: an IP address, an email or a lead's number.
export const personLike = (q) => /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-f]{0,4}(:[0-9a-f]{0,4}){2,7}$|^[^\s@]+@[^\s@]+\.[^\s@]+$|^#?\d{1,9}$/i.test(String(q).trim());
