// Insights, short (js/insight-rank.js): the biggest first, one card per subject
// (a site that is a referring site and an AI assistant is one), each one sentence
// and one number, and every number one the data layer wrote. With an
// insights.json (tests/test_navigate_js.py passes the demo's): no subject twice
// in a window, and nothing lost - every finding is a card or under one.
//
//   node tests/js/insights.mjs [path/to/insights.json]
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { impact, fold, subjectKey, sentence, headline } from "../../skald/webapp/js/insight-rank.js";

const I = (type, kind, name, metric, before, after, title, confidence = "high", change_pct = null) => ({ type, subject: { kind, name }, metric, before, after, title, confidence, change_pct });
const list = [
  I("working", "referrer", "claude.ai", "readers", 24, 33, "claude.ai: readers up 38% 30 days on the 30 before (24 to 33)", "high", 37.5),
  I("working", "assistant", "claude.ai", "readers", 24, 33, "claude.ai: readers up 38% 30 days on the 30 before (24 to 33)", "high", 37.5),
  I("working", "site", "leads", "leads", 18, 32, "Leads up 78% week on week (18 to 32)", "medium", 77.8),
  I("working", "page", "/pricing/", "readers", 837, 1005, "/pricing/: readers up 20% 30 days on the 30 before (837 to 1,005)", "high", 20.1),
  I("working", "crawler", "GPTBot", "ai_fetches", 52, 79, "GPTBot: ai_fetches up 52% week on week (52 to 79)", "high", 51.9),
  I("dropped", "page", "/pricing/", "leads", 7, 4, "Leads that started on /pricing/ down 43% week on week (7 to 4)", "low", -42.9),
  I("gone", "referrer", "gemini.google.com", "readers", 5, 0, "gemini.google.com: no readers in the last 7 days (was 5)", "low", -100),
  I("opportunity", "page", "/blog/a.md", "ai_fetches", 52, 0, "/blog/a.md: assistants fetched it 52 times in 30 days, 0 people read it", "low"),
  I("new", "country", "NZ", "readers", null, 4, "New country: NZ (4 readers)", "low"),
];

// ---- impact: what moved, by what it is worth; an order only
{
  assert.ok(impact(list[3]) > impact(list[2]), "168 readers move more than 14 leads");
  assert.ok(impact(list[2]) > impact(list[0]), "14 leads (medium) outweigh 9 readers");
  assert.ok(impact(list[4]) < impact(list[0]) * 1.5, "an AI fetch counts a quarter of a visit");
  assert.equal(impact(list[8]), 4 * 1 * 0.3, "new: its count, low confidence");
}

// ---- one card per subject, the biggest first, nothing lost
{
  const cards = fold(list);
  const keys = cards.map((c) => subjectKey(c.lead));
  assert.equal(new Set(keys).size, keys.length, "no subject twice");
  assert.equal(keys[0], "/pricing/", "the biggest first");
  const pricing = cards[0];
  assert.equal(pricing.lead.metric, "readers");
  assert.deepEqual(pricing.more.map((x) => x.metric), ["leads"], "its leads finding rides under it");
  const claude = cards.find((c) => subjectKey(c.lead) === "claude.ai");
  assert.deepEqual(claude.more, [], "the same sentence as a referring site and as an assistant: kept once");
  assert.equal(subjectKey({ subject: { name: "https://www.Example.org" } }), "example.org");
}

// ---- one sentence, one number: no "(24 to 33)" twice, metric names in words
{
  assert.equal(sentence(list[0]), "claude.ai: readers up 38% 30 days on the 30 before");
  assert.equal(sentence(list[4]), "GPTBot: AI fetches up 52% week on week");
  assert.equal(sentence(list[6]), "gemini.google.com: no readers in the last 7 days (was 5)", "kept: the number shows 5 too, but the words need it");
  assert.deepEqual(headline(list[0]), { value: 33, words: "readers, was 24" });
  assert.deepEqual(headline(list[6]), { value: 5, words: "readers before, none now" });
  assert.deepEqual(headline(list[7]), { value: 52, words: "AI fetches in 30 days" });
  assert.deepEqual(headline(list[8]), { value: 4, words: "readers, first time" });
  for (const i of list) {
    const v = headline(i).value;
    assert.ok(v === i.before || v === i.after, `${i.title}: the number is one the data layer wrote`);
  }
}

// ---- the demo's insights.json: per window, every finding is a card or under one
const file = process.argv[2];
if (file) {
  const got = JSON.parse(readFileSync(file, "utf8"));
  const span = (i) => { const [a, b] = i.period?.after || []; return a && b ? Math.round((Date.parse(b) - Date.parse(a)) / 864e5) + 1 : 7; };
  const wins = new Map();
  for (const i of got.insights || []) (wins.get(span(i)) || wins.set(span(i), []).get(span(i))).push(i);
  let all = 0, cards = 0;
  for (const [, items] of wins) {
    const f = fold(items);
    const keys = f.map((c) => subjectKey(c.lead));
    assert.equal(new Set(keys).size, keys.length);
    const kept = new Set(f.flatMap((c) => [c.lead, ...c.more]).map(sentence));
    for (const i of items) assert.ok(kept.has(sentence(i)), `${i.title} is shown`);
    for (let k = 1; k < f.length; k++) assert.ok(impact(f[k - 1].lead) >= impact(f[k].lead));
    all += items.length; cards += f.length;
  }
  console.log(`insights: the demo's ${all} findings make ${cards} cards`);
}
console.log("insights: all passed");
