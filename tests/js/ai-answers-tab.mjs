// AI & bots › AI answers (js/tabs/ai-answers.js, ai-answers-parts.js), SKALD-30:
// - the empty "From an answer to a lead" card says what it measures: Skald's own sample of
//   API answers (none when AI answers are not set up), never "no assistant cited you", and
//   points to AI assistants for the visitors assistants sent;
// - with no profile, the "New profile" form opens only on "+ New profile" (ap=new), never by
//   itself; the settings are asked once as the tab opens, so the form opens without a wait.
//
//   node tests/js/ai-answers-tab.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

const asked = [];
const AIA = { ok: true, editable: true, providers: [{ id: "openai", name: "OpenAI", key: false }],
  lists: { questions: [], brands: [], competitors: [], keep_days: 400 }, profiles: [], keys: { openai: false } };
globalThis.fetch = async (path) => {
  const p = String(path).split("?")[0];
  asked.push(p);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (p === "ai-answers") return answer(AIA);
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "ann@example.com" });
const { TAB_RENDER } = await import(new URL("tabs/index.js", JS));
const { noChain } = await import(new URL("tabs/ai-answers-parts.js", JS));
const { asideShown } = await import(new URL("tabs/ai-answers.js", JS));

const flat = (parts) => parts.map((p) => (typeof p === "string" ? p : p.textContent)).join("");
const BASE = { providers: AIA.providers, profiles: [], chain: [], trend: [], last: {}, competitors: {}, chain_first: "2026-10-18", chain_last: "2026-11-16" };

// ---- the empty chain's words
{
  const off = flat(noChain({ ...BASE, state: "not set up" }));
  assert.ok(!/No assistant cited/.test(off), "never 'no assistant cited' when nothing was sampled");
  assert.match(off, /sample of AI answers, which is not set up here/);
  assert.match(off, /counted either way, in AI assistants/);
  const on = flat(noChain({ ...BASE, state: "ok" }));
  assert.match(on, /None of the answers Skald sampled from 18 Oct to 16 Nov cited one of your pages/);
  assert.match(on, /not every answer people get/);
  const link = noChain({ ...BASE, state: "ok" }).find((p) => typeof p !== "string");
  assert.equal(link.getAttribute("href"), "#ai/assistants");
}

// ---- the aside: for a profile or on "+ New profile", never by itself
assert.equal(asideShown(null, { ap: "" }), false);
assert.equal(asideShown(null, { ap: "new" }), true);
assert.equal(asideShown({ id: 1 }, { ap: "" }), true);

const today = "2026-11-17";
const m = { x: { ai_answers: { ...BASE, state: "not set up", setup: { steps: [{ words: "Add a key", done: false }] } } }, byDay: new Map(), today, days: [] };
const draw = (ap) => {
  const root = document.createElement("div");
  root.append(...TAB_RENDER["ai/answers"](m, { ...S.read(), tab: "ai/answers", ap }, {}).flat(9).filter(Boolean));
  return root;
};
let root = draw("");
assert.equal(root.querySelector(".aa-aside"), null, "no profile: no New profile form by itself");
assert.ok(root.querySelector(".aa-cols.solo"), "the cards take the whole width");
assert.ok(!/No assistant cited/.test(root.textContent));
await tick();
assert.equal(asked.filter((p) => p === "ai-answers").length, 1, "the settings are asked once as the tab opens");
root = draw("new");
const side = root.querySelector(".aa-aside");
assert.ok(side, "+ New profile opens the form");
assert.ok(!/Loading the settings/.test(side.textContent), "the settings are already in: no wait");
assert.equal(asked.filter((p) => p === "ai-answers").length, 1, "and not asked again");

console.log("ai-answers-tab: all passed");
