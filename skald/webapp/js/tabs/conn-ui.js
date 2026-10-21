// Settings > Connections and the "Add a site" wizard: the dialog with steps
// (a step bar, Back and Next, in the app's one drawer, js/drawer.js), a task
// card, and a block of commands with its Copy button.
//
//   const w = wizard({ title, subtitle, steps: [{ name, draw(w) -> nodes,
//                      check(w) -> "" or why Next is refused, next(w) -> async, false stops }],
//                      start, onStep(i), onClose, done: "Done" });
//   w.go(i); w.redraw(); w.close(); w.say(text, ok); w.state (the dialog's own memory)

import { h } from "../ui.js";
import { openDrawer } from "../drawer.js";
import { status } from "./forms.js";

export function wizard({ title, subtitle = "", steps, start = 0, onStep = null, onClose = null, done = "Done", key = "conn-wizard", state = {} }) {
  const w = { at: Math.max(0, Math.min(start, steps.length - 1)), state, steps };
  const bar = h("ol", { class: "cn-bar", "aria-label": "Steps" });
  const body = h("div", { class: "cn-step" });
  const msg = status();
  const back = h("button", { type: "button", class: "btn" }, "Back");
  const next = h("button", { type: "button", class: "btn primary" }, "Next");
  const d = openDrawer({ title, subtitle, size: "md", key, className: "cn-dw", body: [bar, body, msg],
    footer: [h("span", { class: "grow" }), back, next], onClose });
  w.el = d.el;
  w.close = () => d.close();
  w.say = (text, ok = false) => msg.say(text, ok);

  w.redraw = () => {
    const step = steps[w.at];
    bar.replaceChildren(...steps.map((s, i) => h("li", { class: i === w.at ? "on" : i < w.at ? "past" : null, "aria-current": i === w.at ? "step" : null },
      h("span", { class: "cn-n" }, String(i + 1)), h("span", { class: "cn-t" }, s.name))));
    // A step may return null, false or nested lists for parts it leaves out: drop them here,
    // or the DOM would print "null" (seen on the mail dialog and Add a site, step 3).
    const parts = [].concat(step.draw(w) || []).flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false && x !== "");
    body.replaceChildren(h("h3", { class: "cn-h" }, `Step ${w.at + 1} of ${steps.length}: ${step.name}`), ...parts);
    back.hidden = w.at === 0;
    next.textContent = w.at === steps.length - 1 ? done : "Next";
    next.disabled = false;
    msg.say("");
  };
  w.go = (i) => {
    w.at = Math.max(0, Math.min(i, steps.length - 1));
    w.redraw();
    if (onStep) onStep(w.at, w);
  };
  back.addEventListener("click", () => w.go(w.at - 1));
  next.addEventListener("click", async () => {
    const step = steps[w.at];
    const why = step.check ? step.check(w) : "";
    if (why) { msg.say(why); return; }
    if (step.next) {
      next.disabled = true;
      let go = true;
      try { go = await step.next(w); } finally { next.disabled = false; }
      if (go === false) return;
    }
    if (w.at === steps.length - 1) { w.close(); return; }
    w.go(w.at + 1);
  });
  w.redraw();
  if (onStep) onStep(w.at, w);
  return w;
}

// A task card at the top of Connections: an icon, a title, one line, a Set up button.
export function taskCard({ icon, title, line, button = "Set up", onOpen, note = null, disabled = false }) {
  const btn = h("button", { type: "button", class: "btn primary", disabled, "aria-label": `${button}: ${title}` }, button);
  btn.addEventListener("click", onOpen);
  return h("div", { class: "cn-card" }, h("span", { class: "cn-ic", html: icon }), h("h3", null, title), h("p", null, line),
    note ? h("p", { class: "note" }, note) : null, h("div", { class: "acts" }, btn));
}

// A command or snippet, kept as typed (several lines), with a Copy button.
export function codeBlock(text, label) {
  const btn = h("button", { type: "button", class: "btn cp", "aria-label": `Copy ${label}` }, "Copy");
  btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; } catch { btn.textContent = "Select and copy"; }
    setTimeout(() => { btn.textContent = "Copy"; }, 1600);
  });
  return h("div", { class: "cn-code" }, h("pre", null, h("code", null, text)), btn);
}

// Numbered instructions: each item a line of words, or [words, node...].
export function steps(...items) {
  return h("ol", { class: "cn-list" }, items.filter(Boolean).map((x) => h("li", null, x)));
}

// The plain-words answer of a Test: ok, waiting or bad, a headline and what to do.
export function answerBox(kind, head, ...more) {
  return h("div", { class: `state cn-answer ${kind === "ok" ? "ok" : kind === "bad" ? "bad" : "warn"}`, role: "status" },
    h("div", null, h("p", null, h("strong", null, head)), ...more));
}

// A sentence and a "?" link to a help guide part.
export const helpLink = (part, words) => h("a", { class: "cn-help", href: `#help?part=${part}` }, words);

export const ICONS = {
  send: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h12M12 6l6 6-6 6"/><path d="M20 4v16"/></svg>',
  read: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7 3 12l5 5M16 7l5 5-5 5"/></svg>',
  mcp: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v10h-9l-5 4v-4H4z"/><path d="M9 10h.01M12 10h.01M15 10h.01"/></svg>',
};
