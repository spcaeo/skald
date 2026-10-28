// Live status and the Test button (2.44): one shared way for every "connect" journey to say,
// by itself and in plain words, whether the thing someone was given to do has worked yet.
//
//   poll(el, ask, { onAnswer, until })   ask the helper every 5 s, then every 30 s
//                                        (live-words.js POLL); never while the tab is hidden,
//                                        stops once `el` left the page, on a 401/402/403, or
//                                        once until(answer) is true
//   setRedraw(fn) / redraw(names)        read the page's data files again and draw the tab
//                                        again when they changed (main.js gives fn); at most
//                                        once in REDRAW_GAP, so a lagging file never storms
//   watchBuilt(el, busy, names)          a viewer (who may not ask the helper): read the built
//                                        files again once a minute while busy() says something
//                                        is in progress
//   testButton({ ask, label })           a "Test" / "Check now" button: says plainly whether it
//                                        arrived, what is missing next, the agent's progress
//                                        where Skald knows it, "Last checked 10:42", and the
//                                        technical words behind "Details"
//   arrivedBox(site, what, opts)         a pill and a sentence that update by themselves
//                                        (POST sites/arrived), with its Test button: the piece
//                                        put beside every line, command, snippet, share page
//                                        and webhook address Skald gives someone
//
// The server's side: skald/connect_check.py. The words: js/live-words.js.

import { h } from "../ui.js";
import { call } from "../tabs/ipmanager.js";
import { why } from "../tabs/forms.js";
import { time } from "../tz.js";
import { answerBox } from "../tabs/conn-ui.js";
import { pill } from "./pill.js";
import { fold } from "./fold.js";
import { POLL, delay, REDRAW_GAP, VIEWER_EVERY, kindOf, pillOf, stepLines } from "../live-words.js";

const TICK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8.5l3 3 7-7"/></svg>';
const DOT = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="3.2"/></svg>';
const STOP = new Set([401, 402, 403, 404]);
const hidden = () => typeof document !== "undefined" && !!document.hidden;

/* Ask while `el` is on the page. Returns {now, stop}. */
export function poll(el, ask, { onAnswer = null, until = () => false, timing = POLL, first = 0 } = {}) {
  const started = Date.now();
  let timer = 0;
  let stopped = false;
  const gone = () => stopped || el.isConnected === false;
  async function once() {
    clearTimeout(timer);
    if (gone()) return stop();
    if (hidden()) return undefined;                          // asked again when shown
    const r = await Promise.resolve(ask()).catch(() => null);
    if (gone()) return stop();
    if (onAnswer) onAnswer(r);
    if (r && STOP.has(r.status)) return stop();
    if (r?.ok && until(r)) return stop();
    timer = setTimeout(once, delay(Date.now() - started, timing));
    return undefined;
  }
  const vis = () => { if (!hidden()) once(); };
  function stop() {
    stopped = true;
    clearTimeout(timer);
    if (typeof document !== "undefined") document.removeEventListener?.("visibilitychange", vis);
  }
  if (typeof document !== "undefined") document.addEventListener?.("visibilitychange", vis);
  timer = setTimeout(once, first);
  return { now: once, stop };
}

// ---- reading the page's files again --------------------------------------------------------
let redrawFn = null;
let lastRedraw = 0;
/* main.js: fn(names) reads the files fresh, swaps the model, draws the tab again when one of
   `names` changed, and answers whether it did. */
export function setRedraw(fn) { redrawFn = fn; }
export function redraw(names, { gap = REDRAW_GAP } = {}) {
  if (!redrawFn || Date.now() - lastRedraw < gap) return Promise.resolve(false);
  lastRedraw = Date.now();
  return Promise.resolve(redrawFn([names].flat())).catch(() => false);
}
export const resetRedraw = () => { lastRedraw = 0; };

/* A viewer's page: read the built files again once a minute while busy() is true. */
export function watchBuilt(el, busy, names) {
  if (!busy()) return null;
  return poll(el, () => redraw(names, { gap: 0 }).then((changed) => ({ ok: true, changed })),
    { timing: { every: VIEWER_EVERY, slowAfter: 0, slow: VIEWER_EVERY }, first: VIEWER_EVERY, until: () => !busy() });
}

// ---- the answer ------------------------------------------------------------------------------
function stepEl(x) {
  return h("li", { class: x.done ? "ok" : "wait" },
    h("span", { class: "sl-ic", html: x.done ? TICK : DOT, "aria-hidden": "true" }),
    h("span", { class: "sl-w" }, x.words),
    h("span", { class: "sl-at" }, x.done && x.at ? time(x.at, { label: false }) : ""),
    h("span", { class: "vh" }, x.done ? " (done)" : " (waiting)"));
}

/* A test's answer, drawn: {verdict, head, says, fix, steps, tech, at}. */
export function answerEl(t) {
  const steps = stepLines(t.steps);
  return answerBox(kindOf(t.verdict), t.head || "Checked.",
    t.says ? h("p", null, t.says) : null,
    steps.length ? h("ol", { class: "sl-list lv-steps", "aria-label": "What has happened so far" }, steps.map(stepEl)) : null,
    t.fix ? h("p", null, h("b", null, "Next: "), t.fix) : null,
    t.at ? h("p", { class: "note lv-at" }, `Last checked ${time(t.at, { label: true })}.`) : null,
    t.tech ? fold("Details", [h("pre", { class: "sl-tech" }, t.tech)]) : null);
}

/* The Test button. ask(): a call's answer whose `test` is the answer to draw. */
export function testButton({ ask, label = "Test", onAnswer = null, cls = "" } = {}) {
  const btn = h("button", { type: "button", class: "btn lv-btn" }, label);
  const out = h("div", { class: "lv-out", "aria-live": "polite" });
  const root = h("div", { class: `lv-test${cls ? ` ${cls}` : ""}` }, btn, out);
  async function press() {
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    out.replaceChildren(h("p", { class: "empty" }, "Checking..."));
    const r = await Promise.resolve(ask()).catch(() => null);
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    if (!r || !r.ok || !r.test) {
      out.replaceChildren(answerBox("bad", why(r || {}, "The check could not run."), h("p", null, r?.status === 429 ? "Wait a few minutes, then press it again." : "Try again in a minute.")));
    } else out.replaceChildren(answerEl(r.test));
    if (onAnswer) onAnswer(r);
    return r;
  }
  btn.addEventListener("click", press);
  root.press = press;
  return root;
}

// ---- beside every line, command, snippet, share page and webhook address -----------------
export const arrivedOf = (site, what, press = false) => call("sites/arrived", { site, what, ...(press ? { press: true } : {}) });

/* A pill and one sentence that update by themselves, then its Test button.
   what: connect_check.KINDS (logs, agent:<link id>, tag, hook:<tool>, search, tool:<id>,
   share:<id>, journeys, token:<id>, ...). onDone(test) once it says it worked (the page may
   read its files again). onAnswer(test): every answer (the agent's watch keeps its top line in
   step). ask: {live, press} replace the calls (the tests). */
export function arrivedBox(site, what, { label = "Test", onDone = null, onAnswer = null, ask = {}, watch = true, intro = "" } = {}) {
  const live = ask.live || (() => arrivedOf(site, what));
  const press = ask.press || (() => arrivedOf(site, what, true));
  const mark = h("span", { class: "lv-pill" });
  const words = h("span", { class: "lv-words" }, intro || "Checking whether it has arrived...");
  const at = h("small", { class: "lv-when" });
  const line = h("p", { class: "lv-line", role: "status", "aria-live": "polite" }, mark, " ", words, " ", at);
  let doneSeen = false;
  const show = (t) => {
    if (!t) return;
    const p = pillOf(t.verdict);
    mark.replaceChildren(pill(p[0], p[1]));
    words.textContent = [t.head, t.says].filter(Boolean).join(" ");
    at.textContent = t.at ? `Last checked ${time(t.at, { label: false })}.` : "";
    root.dataset.verdict = t.verdict || "";
    if (onAnswer) onAnswer(t);
    if (t.verdict === "ok" && !doneSeen) { doneSeen = true; if (onDone) onDone(t); }
  };
  const test = testButton({ ask: press, label, onAnswer: (r) => { if (r?.ok) show(r.test); } });
  const root = h("div", { class: "lv", "data-what": what }, line, test);
  if (watch) {
    poll(root, live, {
      onAnswer: (r) => {
        if (r?.ok) show(r.test);
        else if (r && STOP.has(r.status)) { mark.replaceChildren(); words.textContent = ""; line.hidden = true; }
      },
      until: (r) => r.test?.verdict === "ok" || !!r.test?.final,
    });
  } else line.hidden = !intro;
  root.show = show;
  return root;
}
