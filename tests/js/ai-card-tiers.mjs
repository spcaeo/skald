// Overview's "AI and crawlers now" card (SKALD-53, js/tabs/realtime.js): AI requests split by
// why they came, in AI & bots' words: "AI reading for someone" (a person asked just then) and
// "AI collecting for training" (nobody is waiting). A snapshot from before the split, with one
// AI list only, still shows that list under one heading for its one 30-second cycle.
//
//   node tests/js/ai-card-tiers.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "overview", name: "Overview", tabs: [{ route: "overview/summary", name: "Summary" }] }]);
const RT = await import(new URL("tabs/realtime.js", JS));
const text = (el) => (el == null ? "" : el.textContent);
location.hash = "#overview/summary";

const subs = (el) => el.querySelectorAll(".rt-sub").map(text);
const lists = (el) => el.querySelectorAll("ul.blist, p.empty");

// ---- both tiers
let card = RT.machines({
  answer_engines: { PerplexityBot: 11, "ChatGPT-User": 2 },
  answer_tiers: { asked: { "ChatGPT-User": 2 }, training: { PerplexityBot: 11 } },
  search_engines: { GoogleOther: 3 }, bots: 14 });
document.body.append(card);
assert.deepEqual(subs(card), ["AI reading for someone", "AI collecting for training", "Search crawlers"]);
let L = lists(card);
assert.match(text(L[0]), /ChatGPT-User/);
assert.doesNotMatch(text(L[0]), /PerplexityBot/, "a training crawler is never under reading for someone");
assert.match(text(L[1]), /PerplexityBot/);
assert.match(text(L[1]), /100%/, "each list's share is of its own list");
assert.doesNotMatch(text(card), /AI assistants/, "the old heading is gone");
assert.match(text(card), /Other bots and scanners: 14/);

// ---- one tier empty: its own "none" line, the other list as usual
card = RT.machines({ answer_engines: { PerplexityBot: 11 }, answer_tiers: { asked: {}, training: { PerplexityBot: 11 } }, search_engines: {}, bots: 0 });
L = lists(card);
assert.equal(text(L[0]), "None in the last 30 minutes.");
assert.match(text(L[1]), /PerplexityBot/);

// ---- a snapshot from before the split: the one list, under the old words
card = RT.machines({ answer_engines: { GPTBot: 1 }, search_engines: {}, bots: 0 });
assert.deepEqual(subs(card), ["AI assistants and AI crawlers", "Search crawlers"]);
assert.match(text(lists(card)[0]), /GPTBot/);

console.log("ai-card-tiers: all passed");
