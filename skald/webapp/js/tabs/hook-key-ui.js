// A hook's key, drawn (the words: js/hook-key.js). Leads & tools' drawer for one tool
// (tool=<id>, tabs/integrations.js hookDrawer below) and the set-up dialog's key step
// (tabs/setup-hook.js) both draw from here, so the two never say different things:
//
//   liveTop(site, t)        the live line on top (ui/live.js arrivedBox): a pill, one sentence,
//                           the next action under it, "Check for a real one"
//   keyStatus(t, {...})     "Signing key saved 28 Oct 10:16 by Ann (pasted) · Replace"; a key
//                           Skald just made, shown once with copy; the paste's answer
//   howPicker(t, how, pick) the one question first for Calendly, Cal.com and Typeform
//   pasteForm(t, save)      the tool's own key, typed in once (write-only)
//   remakePart(t, {...})    Calendly made without a signing key: why, and the two requests
//   testPart(site, t)       Test Skald's address: what it proves, and the last real delivery
//   hookDrawer(t, ctx)      the drawer, top to bottom: live line, way, key, question, path,
//                           address, event types, Test, details folded

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why, copyable, confirmIn } from "./forms.js";
import { codeBlock, steps, answerBox } from "./conn-ui.js";
import { pill } from "../ui/pill.js";
import { fold } from "../ui/fold.js";
import { arrivedBox } from "../ui/live.js";
import { withUrl } from "../urlactions.js";
import { keyWord, cap, wayWords, howQuestion, howOf, savedWords, checkWords, lastRealWords, realTrouble,
  testWords, calendlyCreate, calendlyFindDelete, CAL_EVENTS } from "../hook-key.js";

const KIND = { good: "ok", bad: "bad", warn: "warn", info: "warn" };
export const PLACE = (t) => `<the ${keyWord(t)}>`;

/* The live line on top: whether a real one has come, by itself; the next action under it. */
export function liveTop(site, t, opts = {}) {
  return arrivedBox(site, `hook:${t.tool}`, { label: "Check for a real one", next: true, intro: `Checking ${t.name}...`, ...opts });
}

/* The key's state: what is saved (when, by whom, how) with Replace; a key just made, shown once;
   the last paste's or make's answer. null when there is nothing to say. */
export function keyStatus(t, { fresh = null, check = null, onReplace = null, onCopied = null } = {}) {
  const k = keyWord(t);
  const saved = savedWords(t);
  const said = checkWords(check, t);
  if (!saved && !fresh && !said) return null;
  const kids = [];
  if (saved) {
    const rep = onReplace && t.rotatable !== false ? h("button", { type: "button", class: "hk-replace" }, "Replace") : null;
    if (rep) rep.addEventListener("click", onReplace);
    // "Saved" says what is saved; whether it works is the live line's and the answer's to say.
    kids.push(h("p", { class: "hk-saved" }, pill(said?.kind === "good" ? "good" : "info", "Saved"), " ",
      h("span", null, saved.replace(/\.$/, ""), rep ? [" · ", rep] : null)));
  }
  if (fresh) {
    const done = onCopied ? h("button", { type: "button", class: "btn" }, "I have copied it") : null;
    if (done) done.addEventListener("click", onCopied);
    kids.push(h("div", { class: "state ok hk-fresh", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `${cap(k)} made by Skald. `), "Shown once: copy it now. ", `Give it to ${t.name}; a new one replaces the old one at once.`),
      copyable(fresh.secret, `the ${k}`), done ? h("div", { class: "acts" }, done) : null)));
  }
  if (said) kids.push(answerBox(KIND[said.kind] || "warn", said.words));
  return h("div", { class: "hk-status", "data-verdict": check?.verdict || "" }, ...kids);
}

/* The one question first: radios, the answer in the address (how=). */
export function howPicker(t, how, pick) {
  const q = howQuestion(t);
  if (!q) return null;
  const name = `hk-how-${t.tool}-${Math.random().toString(36).slice(2, 7)}`;
  return h("fieldset", { class: "cn-ways hk-how" }, h("legend", null, h("b", null, q.question)),
    q.choices.map((c) => {
      const radio = h("input", { type: "radio", name, value: c.id });
      radio.checked = how === c.id;
      radio.addEventListener("change", () => pick(c.id));
      return h("label", { class: "cn-way" }, radio, h("span", null, h("b", null, c.title), h("small", null, c.sub)));
    }));
}

/* The tool's own key, typed in once. save(value) -> the call's answer. */
export function pasteForm(t, save, { onSaid = null } = {}) {
  const k = keyWord(t);
  const box = input({ type: "password", autocomplete: "off", maxlength: "500", placeholder: t.set ? "saved: paste to replace" : "not saved yet" });
  const btn = h("button", { type: "submit", class: "btn" }, `Save ${k}`);
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const label = t.tool === "calendly" ? "Paste the signing_key value the request used" : `Paste the ${k} from ${t.secret_from || t.name}`;
  const hint = t.tool === "calendly" ? "The value of signing_key in the request that made the webhook: not your Calendly token, not the webhook's address. Write-only: it is never shown again."
    : t.make === false ? `${t.name} makes its own ${k}; Skald cannot make one for it. Write-only: it is never shown again.`
      : "Write-only: it is never shown again.";
  const form = h("form", { class: "af-row hk-paste", novalidate: true }, field(label, box, hint), btn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!box.value.trim()) { said.textContent = `Paste the ${k} first.`; said.className = "msg err"; box.focus(); return; }
    btn.disabled = true;
    const r = await save(box.value);
    btn.disabled = false;
    if (!r?.ok) { said.textContent = why(r || {}, "It was not saved."); said.className = "msg err"; return; }
    box.value = "";
    said.textContent = "";
    if (onSaid) onSaid(r);
  });
  return h("div", null, form, said);
}

/* Make (or make again) Skald's key: a button, with a yes first when one is saved. make() -> answer. */
export function makeButton(t, make, { fresh = null } = {}) {
  const k = keyWord(t);
  const acts = h("div", { class: "acts hk-make" });
  const draw = () => {
    const btn = h("button", { type: "button", class: "btn", disabled: t.rotatable === false }, t.set ? `Make a new ${k}` : `Make the ${k}`);
    if (t.rotatable === false) btn.title = `This ${k} is set in the server's environment.`;
    btn.addEventListener("click", () => {
      if (!t.set || fresh) { btn.disabled = true; make(); return; }
      confirmIn(acts, `Make a new ${k} for ${t.name}? The one saved now stops working at once.`, "Yes, make a new one", make, draw);
    });
    acts.replaceChildren(btn);
  };
  draw();
  return acts;
}

/* Calendly, made without a signing key (or not sure): why, then the two requests. */
export function remakePart(t, { addr, key = "", make = null, fresh = null, agent = null } = {}) {
  const k = keyWord(t);
  const ag = agent ? h("button", { type: "button", class: "btn hk-agent" }, "Let your AI agent do it") : null;
  if (ag) ag.addEventListener("click", agent);
  return h("div", { class: "hk-remake" },
    h("p", null, `A webhook made without a ${k} sends no signature, and Calendly cannot add one later. Delete the old webhook, then make it again with Skald's ${k}:`),
    steps(
      [h("span", null, `Make Skald's ${k}${key ? " (done: it is filled in below)" : ""}.`), !key && make ? makeButton(t, make, { fresh }) : null],
      [h("span", null, "Find the old webhook and delete it:"), codeBlock(calendlyFindDelete(addr), "the requests that find and delete the old webhook")],
      [h("span", null, `Make it again with Skald's ${k}:`), codeBlock(calendlyCreate(addr, key || PLACE(t)), "the request that makes the webhook")]),
    h("p", { class: "note" }, `Put your Calendly personal access token where you see <your-calendly-token>.${key ? "" : ` Put the ${k} where you see ${PLACE(t)}.`}`),
    ag ? h("p", { class: "sub" }, "Your AI agent can run both requests with your Calendly token, and never shows the key. ", ag) : null);
}

/* Calendly, not made yet: the steps and the one request, the key filled in when Skald just made it. */
export function calendlyMake(t, addr, key) {
  const k = keyWord(t);
  return [steps([h("span", null, "Calendly webhooks are made with Calendly's API, usually by a developer. Make one with this address: "),
    withUrl(h("code", null, addr), addr, { cls: "ua-after" })],
  `Give it Skald's ${k} as signing_key. Calendly never shows it again.`, `Events: ${CAL_EVENTS.join(", ")}.`),
  codeBlock(calendlyCreate(addr, key || PLACE(t)), "the request that makes the webhook"),
  h("p", { class: "note" }, `Put your Calendly personal access token where you see <your-calendly-token>.${key ? "" : ` Put the ${k} where you see ${PLACE(t)}.`}`)];
}

/* Test Skald's address, and beside it the last real delivery. */
export function testPart(site, t, { onDone = null } = {}) {
  const out = h("div", { class: "hk-test-out" });
  const last = h("p", { class: "note hk-last" }, lastRealWords(t));
  const btn = h("button", { type: "button", class: "btn", disabled: !t.set }, "Test Skald's address");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const r = await call("integrations/test", { site, tool: t.tool });
    btn.disabled = false;
    const [kind, head, more] = testWords(r, t);
    out.replaceChildren(answerBox(kind, head, more ? h("p", null, more) : null));
    if (r?.ok && r.last_real !== undefined) last.textContent = lastRealWords(t, r.last_real);
    if (onDone) onDone(r);
  });
  return h("div", { class: "hk-test" }, h("div", { class: "acts" }, btn), out, last.textContent ? last : null);
}

/* What to show now: {way: make|paste|remake|"", ask: the question shows}. how: the address's
   answer; asking: Replace was pressed; what Skald saw (since_saved) opens the question by itself,
   and a Calendly webhook that sends no signature goes to "make it again". */
export function wayNow(t, how = "", { asking = false } = {}) {
  const trouble = realTrouble(t);
  if (howQuestion(t)) {
    const way = howOf(t, how) || (t.tool === "calendly" && trouble === "unsigned" ? "remake" : "");
    return { way, ask: !t.set || asking || !!way || !!trouble };
  }
  if (t.make === false) return { way: !t.set || asking || trouble ? "paste" : "", ask: false };
  return { way: "make", ask: false };      // Skald's own (lead, json): Make, or Make a new one
}

/* The chosen way's part: the paste box, Make (with Calendly's request), or Calendly's make it again. */
export function wayPart(t, way, { make, paste, fresh = null, agent = null, onSaid = null } = {}) {
  const key = fresh?.secret || "";
  if (way === "paste") return pasteForm(t, paste, { onSaid });
  if (way === "remake" && t.tool === "calendly") return remakePart(t, { addr: t.url, key, make, fresh, agent });
  if (way === "make" || way === "remake") {
    return h("div", { class: "hk-path" }, key && howQuestion(t) ? null : makeButton(t, make, { fresh }), t.tool === "calendly" ? calendlyMake(t, t.url, key) : null);
  }
  return null;
}

/* One tool's drawer. ctx: {site, fresh, check, how, asking, onHow(id), onAsk(), make(), paste(v),
   onCopied(), agent(), types, more: [nodes in the folded details]}. */
export function hookDrawer(t, ctx) {
  const { site, fresh = null, check = null, how = "", asking = false } = ctx;
  const k = keyWord(t);
  const { way, ask } = wayNow(t, how, { asking });
  return h("div", { class: "integ integ-one hk", "data-tool": t.tool, "data-way": way },
    t.problem ? h("p", { class: "msg err" }, t.problem) : null,
    t.set || t.where === "env" ? liveTop(site, t) : null,
    h("p", { class: "hk-way" }, wayWords(t)),
    keyStatus(t, { fresh, check, onReplace: howQuestion(t) || t.make === false ? ctx.onAsk : null, onCopied: ctx.onCopied }),
    ask ? howPicker(t, way, ctx.onHow) : null,
    wayPart(t, way, { make: ctx.make, paste: ctx.paste, fresh, agent: ctx.agent }),
    h("div", { class: "hk-addr" }, h("p", { class: "hk-lbl" }, `The address for ${t.name}`), copyable(t.url, `the address for ${t.name}`)),
    ctx.types || null,
    t.set ? testPart(site, t) : null,
    fold(`Details: the last deliveries, Remove the ${k}`, [...(ctx.more || [])], { cls: "hk-more" }));
}
