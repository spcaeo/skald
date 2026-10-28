// A hook's key (2.45, js/hook-key.js, js/tabs/hook-key-ui.js): found on a site's Calendly, where
// the page said "secret" for Calendly's "signing key", forgot the key once saved, and passed its
// own test while every real booking was refused. Here, with stubbed helper answers:
//
//   - the tool's own word everywhere (key_word, else the local map), never "secret key"
//   - Calendly, Cal.com, Typeform: one question first; the answer is how= in the address
//   - after Make or Save the drawer stays open on "<Key> saved <when> by <who> (pasted|made)"
//   - a paste's answer in plain words: matches, no_match, unsigned, none_held
//   - Test Skald's address says it proves the address only, beside the last real delivery
//   - the row's pill and Leads & tools' state never green while only refused ones came
//   - an older server (no new fields): nothing guessed
//
//   node tests/js/hook-key.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/" });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
Element.prototype.scrollIntoView = function scrollIntoView() {};
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, h) { location.hash = h; }, replaceState(_, __, h) { location.hash = h; }, back() {}, go() {} };
const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const K = await import(new URL("hook-key.js", JS));

// Times today (UTC, the zone the page uses by default), so they read as "10:13".
const day = new Date().toISOString().slice(0, 10);
const T = (hm) => `${day}T${hm}:00Z`;
const ADDR = "https://app.example.com/traffic-hooks/example.com/calendly";
const CAL = { tool: "calendly", name: "Calendly", url: ADDR, rotatable: true, make: true, paste: true, secret_from: "Calendly", deliveries: [] };

// ---- the words ---------------------------------------------------------------------------
assert.equal(K.keyWord({ tool: "calendly" }), "signing key", "the local map");
assert.equal(K.keyWord({ tool: "calendly", key_word: "signing key" }), "signing key");
assert.equal(K.keyWord({ tool: "stripe" }), "signing secret");
assert.equal(K.keyWord({ tool: "hubspot" }), "client secret");
assert.equal(K.keyWord({ tool: "lead" }), "secret");
assert.equal(K.keyWord({ tool: "hubspot", key_word: "app secret" }), "app secret", "the server's word wins");
for (const tool of ["calendly", "calcom", "typeform", "stripe", "hubspot", "lead", "json"]) assert.ok(!/secret key/.test(K.keyWord({ tool })), tool);
assert.equal(K.wayWords(CAL), "Skald gives Calendly a signing key; Calendly signs each booking with it.");
assert.ok(K.wayWords({ tool: "stripe", name: "Stripe", make: false }).startsWith("Stripe makes the signing secret; you paste it here once."));

const q = K.howQuestion(CAL);
assert.equal(q.question, "How was your Calendly webhook made?");
assert.deepEqual(q.choices.map((c) => c.title), ["Not made yet", "Made with an API request that had a signing_key", "Made without a signing key, or not sure"]);
assert.deepEqual(q.choices.map((c) => c.id), ["make", "paste", "remake"]);
assert.equal(K.howQuestion({ tool: "calcom", name: "Cal.com" }).question, "Has Cal.com given you a secret?");
assert.equal(K.howQuestion({ tool: "calcom", name: "Cal.com" }).choices.length, 2, "no remake for Cal.com");
assert.equal(K.howQuestion({ tool: "stripe", name: "Stripe", make: false }), null, "Stripe: no question, it makes its own");
assert.equal(K.howQuestion({ tool: "lead" }), null);
assert.equal(K.howOf(CAL, "remake"), "remake");
assert.equal(K.howOf({ tool: "calcom", name: "Cal.com" }, "remake"), "", "an answer the tool has not");

assert.equal(K.savedWords({ ...CAL, set: false }), null);
assert.equal(K.savedWords({ ...CAL, set: true, saved_at: "2026-10-28T10:16:00Z", saved_by: "Ann Example", saved_how: "pasted" }), "Signing key saved 28 Oct 10:16 by Ann Example (pasted).");
assert.equal(K.savedWords({ ...CAL, set: true, saved_at: null, saved_by: null, saved_how: null }), "Signing key saved.", "no time when not known");
assert.equal(K.savedWords({ ...CAL, set: true }), "Signing key saved.", "an older server");
assert.equal(K.realState({ ...CAL, set: true, since_saved: null }), null, "a key set from the CLI: no since_saved, nothing guessed");
assert.equal(K.savedWords({ ...CAL, set: true, where: "env", env: "SKALD_HOOK_SECRET_CALENDLY" }), "Signing key kept in the server's environment (SKALD_HOOK_SECRET_CALENDLY).");

const now = Date.parse(T("12:00"));
const L1 = { ...CAL, last_real: { at: T("10:13"), outcome: "accepted_held" } };
assert.deepEqual(K.checkWords({ verdict: "matches", held: 8, matched: 8, taken: 8 }, L1, now), { kind: "good", words: "It matches Calendly's booking from 10:13. 8 bookings taken in." });
assert.deepEqual(K.checkWords({ verdict: "no_match", held: 3, refused_last_at: T("11:37") }, CAL, now),
  { kind: "bad", words: "This is not the key Calendly signs with: Calendly's delivery at 11:37 still does not match. Copy the signing_key from the request that made the webhook, not your Calendly token or the webhook address." });
assert.deepEqual(K.checkWords({ verdict: "unsigned", unsigned: 2 }, CAL, now),
  { kind: "bad", words: "Calendly sends no signature: the webhook was made without a signing key. Make it again with Skald's key (steps below)." });
assert.deepEqual(K.checkWords({ verdict: "none_held", held: 0 }, CAL, now), { kind: "info", words: "Saved. Skald checks it against Calendly's next booking." });
assert.equal(K.checkWords(undefined, CAL), null, "an older server: nothing said");

assert.equal(K.lastRealWords(CAL), "", "an older server: no line");
assert.equal(K.lastRealWords({ ...CAL, last_real: null }), "Last real booking: none yet.");
assert.equal(K.lastRealWords({ ...CAL, last_real: { at: T("11:37"), outcome: "bad_signature" } }, undefined, now), "Last real booking: refused at 11:37, the signing key does not match.");
assert.equal(K.lastRealWords({ ...CAL, last_real: { at: T("11:37"), outcome: "accepted" } }, undefined, now), "Last real booking: accepted at 11:37.");
assert.equal(K.lastRealWords({ ...CAL, last_real: { at: T("11:37"), outcome: "unsigned" } }, undefined, now), "Last real booking: refused at 11:37, it had no signature.");
assert.equal(K.lastRealWords({ ...CAL, last_real: { at: "2026-10-01T11:37:00Z", outcome: "accepted" } }, undefined, Date.parse("2026-10-28T12:00:00Z")), "Last real booking: accepted at 1 Oct 11:37.", "another day: its date");

assert.equal(K.realState(CAL), null, "no since_saved: unknown");
assert.equal(K.realState({ since_saved: { accepted: 0, refused: 4, unsigned: 0 } }), "bad");
assert.equal(K.realState({ since_saved: { accepted: 0, refused: 0, unsigned: 2 } }), "bad");
assert.equal(K.realState({ since_saved: { accepted: 1, refused: 4, unsigned: 0 } }), "good");
assert.equal(K.realState({ since_saved: { accepted: 0, refused: 0, unsigned: 0 } }), "wait");
assert.equal(K.realTrouble({ since_saved: { accepted: 0, refused: 0, unsigned: 2 } }), "unsigned");

const tw = K.testWords({ ok: true, status: 200, proves: "address", answer: { records: 1, would_keep: 1 } }, CAL);
assert.equal(tw[0], "ok");
assert.equal(tw[1], "Skald's address answers. This does not check Calendly's signing key: only a real booking does.");
assert.ok(!/connected|working/i.test(tw.join(" ")), "a test never says connected");

// The requests for Calendly: the address and the key filled in; the find-and-delete pair.
const made = K.calendlyCreate(ADDR, "k-sample-0001");
assert.ok(made.includes(`"url": "${ADDR}"`) && made.includes('"signing_key": "k-sample-0001"') && made.includes("invitee_no_show.created"));
const fd = K.calendlyFindDelete(ADDR);
assert.ok(fd.includes("users/me") && fd.includes("webhook_subscriptions?organization=") && fd.includes("curl -X DELETE") && fd.includes(ADDR));

// ---- the pills: never green while only refused ones came --------------------------------
const { toolKind } = await import(new URL("tabs/integrations.js", JS));
const { hookState } = await import(new URL("connect-plan.js", JS));
const { hookWords } = await import(new URL("live-words.js", JS));
const refused = { ...CAL, set: true, state: "received", last_at: T("09:00"), since_saved: { accepted: 0, refused: 3, unsigned: 0 } };
assert.deepEqual(toolKind(refused), ["bad", "Not working"], "received before, refused since the key was saved");
assert.equal(hookState(refused), "failing");
assert.equal(hookWords(refused, "Calendly").verdict, "bad");
assert.deepEqual(toolKind({ ...refused, since_saved: { accepted: 2, refused: 3, unsigned: 0 } }), ["good", "Working"]);
assert.deepEqual(toolKind({ ...CAL, set: true, state: "ready", test_at: T("09:00") }), ["warn", "Waiting"], "a passed test alone is not green");
assert.deepEqual(toolKind({ ...CAL, set: true, state: "received", since_saved: { accepted: 0, refused: 0, unsigned: 0 } }), ["warn", "Waiting"]);
assert.equal(hookState({ ...CAL, set: true, state: "ready" }), "waiting");
assert.deepEqual(toolKind({ ...CAL, set: true, state: "received" }), ["good", "Working"], "an older server: as before");

// ---- the drawer (tool=calendly), with stubbed answers ------------------------------------
let tool = { ...CAL, set: false, state: "needs_secret", words: "needs a secret" };
let answers = {};
const posted = [];
globalThis.fetch = async (path, opts) => {
  const p = String(path);
  const body = opts?.body ? JSON.parse(opts.body) : null;
  if (body) posted.push([p.replace(/^.*\/traffic\/[^/]+\//, ""), body]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => structuredClone(data), headers: { get: () => null } });
  for (const [k, v] of Object.entries(answers)) if (p.includes(k)) return answer(typeof v === "function" ? v(body) : v);
  if (p.includes("sites/arrived")) return answer({ ok: true, test: { verdict: "wait", head: "Waiting for Calendly: nothing real has arrived yet.", fix: "Book a test call on your Calendly page.", steps: [] } });
  if (p.includes("integrations/yourtools")) return answer({ ok: true, tools: [] });
  if (p.includes("integrations")) return answer({ ok: true, site: "example.com", sites: ["example.com"], tools: [tool], status: [], webhooks: [] });
  return answer({ ok: false, error: "not found" }, 404);
};
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "owner", user: "owner@example.com" });
const L = await import(new URL("tabs/set-leads.js", JS));
const m = { site: "example.com", x: {} };
const keyOf = (k) => new URLSearchParams(location.hash.split("?")[1] || "").get(k);
const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const drawer = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
async function open(hash = "#settings/site/leads?tool=calendly") {
  for (const d of document.body.querySelectorAll("dialog")) d.open = false;
  document.body.replaceChildren();
  location.hash = hash;
  await L.openTool("calendly", m);
  await tick(60);
  return drawer();
}
const say = (d) => d.textContent.replace(/\s+/g, " ");
const moreOf = (d) => { const f = d.querySelector(".hk-more"); f.fill(); return f.textContent; };

// 1. Not made yet: the question first, nothing made before the answer; never "secret key".
let d = await open();
assert.ok(d.querySelector(".hk-way").textContent === "Skald gives Calendly a signing key; Calendly signs each booking with it.");
assert.ok(d.querySelector(".hk-how").textContent.includes("How was your Calendly webhook made?"));
assert.ok(!/secret key/i.test(d.textContent), "never \"secret key\"");
assert.ok(!/no screen for/i.test(d.textContent), "no claim about Calendly's screens");
assert.equal(posted.filter(([p]) => p.startsWith("integrations/secret")).length, 0, "nothing made before the answer");
assert.equal(d.querySelector(".hk-test"), null, "no Test while nothing is saved");
const radio = (id) => d.querySelectorAll(".hk-how input").find((r) => r.getAttribute("value") === id);
radio("make").checked = true;
radio("make").dispatchEvent(new Event("change"));
await tick();
assert.equal(keyOf("how"), "make", "the answer is in the address");
d = drawer();
assert.ok(button(d, "Make the signing key"), "the make way");
assert.ok(say(d).includes("Calendly webhooks are made with Calendly's API, usually by a developer."));
// Make: the drawer stays open on the key, shown once, and the request has it filled in.
answers = { "integrations/secret": { ok: true, site: "example.com", tool: "calendly", secret: "k-sample-0001", url: ADDR, check: { verdict: "none_held", held: 0 } } };
tool = { ...CAL, set: false, state: "needs_secret", words: "needs a secret" };
const afterMake = { ...CAL, set: true, state: "never", words: "never received", key_word: "signing key", saved_at: T("10:16"), saved_by: "Ann Example", saved_how: "made by Skald",
  last_real: null, since_saved: { accepted: 0, refused: 0, unsigned: 0 }, held: 0 };
button(d, "Make the signing key").click();
tool = afterMake;
await tick(80);
d = drawer();
assert.ok(d, "the drawer is still open after Make");
assert.ok(d.querySelector(".hk-fresh").textContent.includes("k-sample-0001"), "the key, shown once");
assert.ok(d.querySelector(".hk-fresh").textContent.includes("Shown once: copy it now"));
assert.ok(d.querySelector(".hk-saved").textContent.includes("Signing key saved 10:16 by Ann Example (made by Skald)".replace("saved 10:16", `saved ${new Date(T("10:16")).getUTCDate()} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][new Date(T("10:16")).getUTCMonth()]} 10:16`)), d.querySelector(".hk-saved").textContent);
assert.ok(d.querySelectorAll(".cn-code").some((c) => c.textContent.includes('"signing_key": "k-sample-0001"')), "the request, with the key filled in");
assert.ok(say(d).includes("Saved. Skald checks it against Calendly's next booking."), "the make's answer");
assert.ok(d.querySelector(".lv"), "the live line on top");
assert.ok(say(d).includes("Next: Book a test call on your Calendly page."), "its next action, under it");
assert.ok(button(d, "Test Skald's address"), "the honest Test");
assert.ok(say(d).includes("Last real booking: none yet."));
button(d, "I have copied it").click();
await tick();
d = drawer();
assert.equal(d.querySelector(".hk-fresh"), null, "copied: the key is gone");
assert.ok(d.querySelector(".hk-saved"), "and what is saved stays");

// 2. Saved, pasted, and refused since: Not working, the question open, then a paste that does not match.
tool = { ...CAL, set: true, state: "received", last_at: T("09:00"), words: "last received", saved_at: T("10:16"), saved_by: "Ann Example", saved_how: "pasted",
  last_real: { at: T("11:37"), outcome: "bad_signature", words: "the signing key does not match" }, since_saved: { accepted: 0, refused: 3, unsigned: 0 }, held: 3 };
d = await open();
assert.ok(d.querySelector(".hk-saved").textContent.includes("(pasted)"));
assert.ok(d.querySelector(".hk-how"), "refused since the key was saved: the question is open again");
assert.ok(moreOf(d).includes("Not working"), "the pill in the details agrees");
radio("paste").checked = true;
radio("paste").dispatchEvent(new Event("change"));
await tick();
d = drawer();
assert.equal(keyOf("how"), "paste");
const box = d.querySelector(".hk-paste input");
assert.ok(box && say(d).includes("Paste the signing_key value the request used"));
answers = { "integrations/hooks/paste": { ok: true, site: "example.com", tool: "calendly", replaced: true, check: { held: 3, matched: 0, taken: 0, refused_last_at: T("11:37"), unsigned: 0, verdict: "no_match" } } };
box.value = "not-the-key-0001";
d.querySelector(".hk-paste").dispatchEvent(new Event("submit"));
await tick(80);
d = drawer();
assert.ok(d, "still open after Save");
assert.ok(say(d).includes("This is not the key Calendly signs with: Calendly's delivery at 11:37 still does not match."), say(d));
assert.ok(d.querySelector(".hk-paste"), "the paste box stays for the right one");
assert.deepEqual(posted.filter(([p]) => p === "integrations/hooks/paste").pop()[1], { site: "example.com", tool: "calendly", secret: "not-the-key-0001" });
assert.ok(!location.hash.includes("not-the-key"), "never the key in the address");

// 3. The right one: it matches, and the held bookings are taken in.
answers = { "integrations/hooks/paste": { ok: true, site: "example.com", tool: "calendly", replaced: true, check: { held: 8, matched: 8, taken: 8, refused_last_at: null, unsigned: 0, verdict: "matches" } } };
const good = { ...tool, saved_at: T("11:40"), last_real: { at: T("10:13"), outcome: "accepted_held" }, since_saved: { accepted: 8, refused: 0, unsigned: 0 }, held: 0 };
d.querySelector(".hk-paste input").value = "the-key-0001";
tool = good;
d.querySelector(".hk-paste").dispatchEvent(new Event("submit"));
await tick(80);
d = drawer();
assert.ok(say(d).includes("It matches Calendly's booking from 10:13. 8 bookings taken in."), say(d));
assert.equal(d.querySelector(".hk-how"), null, "it works: the question folds away");
assert.ok(moreOf(d).includes("Working"));
// Test Skald's address: what it proves, beside the last real one.
answers = { "integrations/test": { ok: true, status: 200, proves: "address", answer: { records: 1, would_keep: 1 }, last_real: { at: T("10:13"), outcome: "accepted_held" } } };
button(d, "Test Skald's address").click();
await tick();
assert.ok(say(d).includes("Skald's address answers. This does not check Calendly's signing key: only a real booking does."));
assert.ok(say(d).includes("Last real booking: accepted at 10:13."));

// 4. Made without a signing key: Calendly sends no signature. Make it again, two requests, agent.
answers = {};
tool = { ...CAL, set: true, state: "received", saved_at: T("10:16"), saved_by: "Ann Example", saved_how: "made by Skald",
  last_real: { at: T("11:50"), outcome: "unsigned" }, since_saved: { accepted: 0, refused: 0, unsigned: 2 }, held: 2 };
d = await open();
assert.ok(d.querySelector(".hk-remake"), "the make-it-again way, by itself");
assert.ok(radio("remake").checked);
assert.ok(say(d).includes("Calendly never shows a signing key again"));
const codes = d.querySelectorAll(".hk-remake .cn-code");
assert.equal(codes.length, 2, "two requests, each with its copy");
assert.ok(codes[0].textContent.includes("curl -X DELETE") && codes[1].textContent.includes("webhook_subscriptions"));
assert.ok(button(d, "Make a new signing key"), "Skald's key, made again");
assert.ok(say(d).includes("Last real booking: refused at 11:50, it had no signature."));
button(d, "Let your AI agent do it").click();
await tick();
assert.equal(keyOf("setup"), "lead");
assert.equal(keyOf("way"), "calendly");
assert.equal(keyOf("by"), "agent");
assert.equal(keyOf("tool"), null, "the drawer's key left");

// 5. An older server: no new field, nothing guessed.
tool = { ...CAL, set: true, state: "received", last_at: T("09:00"), words: "last received" };
d = await open();
assert.ok(d.querySelector(".hk-saved").textContent.includes("Signing key saved"), "saved, known from set");
assert.ok(!/ by |pasted|made by Skald/.test(d.querySelector(".hk-saved").textContent), "no time, no name, no way");
assert.equal(d.querySelector(".hk-last"), null, "no last-real line");
assert.equal(d.querySelector(".hk-how"), null, "nothing failing: no question");

// 6. Stripe: no question, its own signing secret pasted.
tool = { tool: "stripe", name: "Stripe", url: "https://app.example.com/traffic-hooks/example.com/stripe", rotatable: true, make: false, paste: true, secret_from: "Stripe", set: false, state: "needs_secret", deliveries: [] };
document.body.replaceChildren();
location.hash = "#settings/site/leads?tool=stripe";
await L.openTool("stripe", m);
await tick(60);
d = drawer();
assert.equal(d.querySelector(".hk-how"), null);
assert.ok(say(d).includes("Paste the signing secret from Stripe") && button(d, "Save signing secret"));

// ---- the set-up dialog (setup=lead&way=calendly): the step is named by the key's word ------
for (const x of document.body.querySelectorAll("dialog")) x.open = false;
document.body.replaceChildren();
posted.length = 0;
tool = { ...CAL, set: false, state: "needs_secret", words: "needs a secret" };
location.hash = "#settings/site/leads?setup=lead&way=calendly&step=2";
const { hookDialog } = await import(new URL("tabs/setup-hook.js", JS));
await hookDialog("example.com", { way: "calendly", start: 1, route: { key: "setup", value: "lead" } });
await tick(60);
d = drawer();
assert.equal(d.querySelector("h3.cn-h").textContent, "Step 2 of 4: The signing key");
assert.ok(d.querySelector(".hk-how"), "the question first");
assert.equal(posted.filter(([p]) => p === "integrations/secret").length, 0, "nothing made before the answer");
button(d, "Next").click();
await tick();
assert.ok(say(d).includes("Say how your Calendly webhook was made first."));
answers = { "integrations/secret": { ok: true, secret: "k-sample-0002", url: ADDR, check: { verdict: "none_held" } } };
const r2 = d.querySelectorAll(".hk-how input").find((r) => r.getAttribute("value") === "remake");
r2.checked = true;
r2.dispatchEvent(new Event("change"));
await tick(80);
d = drawer();
assert.equal(keyOf("how"), "remake");
assert.equal(posted.filter(([p]) => p === "integrations/secret").length, 1, "the key, made once the way is chosen");
assert.ok(d.querySelector(".hk-fresh").textContent.includes("k-sample-0002"));
button(d, "Next").click();
await tick();
d = drawer();
assert.equal(d.querySelector("h3.cn-h").textContent, "Step 3 of 4: Set it up");
assert.ok(d.querySelectorAll(".cn-code").some((c) => c.textContent.includes("curl -X DELETE")), "find and delete the old one");
assert.ok(d.querySelectorAll(".cn-code").some((c) => c.textContent.includes('"signing_key": "k-sample-0002"')), "make it again, the key filled in");
button(d, "Next").click();
await tick();
d = drawer();
assert.ok(button(d, "Test Skald's address") && !button(d, "Send a test lead"));
assert.ok(say(d).includes("Only a real booking from Calendly shows that Calendly signs with the same signing key as Skald"));

console.log("hook-key: all passed");
process.exit(0);
