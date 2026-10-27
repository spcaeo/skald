// "Who will do it? Me / My developer / My AI agent" (2.41, docs/UI-RULES.md rule 2): the
// first question of every dialog that fixes or sets up something. Then only that person's
// path is shown. The paths are the flows Skald already has:
//
//   agent   the agent line (tabs/agent-setup.js linePanel: POST sites/agentlink with the
//           job ids kit/agent_jobs.py knows), then its watch (tabs/agent-watch.js)
//   dev     the private link for a developer (tabs/conn-share.js shareBox: POST sites/share)
//           when the job has one; else the message to copy, with the link to this place
//   me      the by-hand steps the caller already draws (its own nodes)
//
// A path the caller does not give is not offered: never a choice that leads nowhere.
//
// In the address: by=me|dev|agent inside the dialog open (the dialog's own family, e.g.
// alfix=<kind>, names the dialog). Insights' first Fix this links said fixby=agent|me|someone:
// read as by, someone as dev. Remembered per person in this browser: the next dialog opens
// on the last choice. Not "who": that key is Find a person's (always masked).
//
//   whoStep({ paths, route, key, fallback, question, onPick, subs }) -> { el, choice(), pick(k), ready }
//     paths: {me, dev, agent}, each ({ pressed }) -> nodes; pressed: chosen by a press now
//     subs: the answers' second lines for this dialog (the titles never change)
//     from: the answer to open on, when the caller read it already (else the address's)
//   whoDialog({ title, subtitle, route, paths, ... }) -> the drawer, with whoStep inside
//   agentPath({ site, jobs }), devPath({ site, task, method, message, link }), mePath(nodes)

import { h } from "../ui.js";
import * as S from "../state.js";
import { stepped } from "../overlays.js";
import { ME } from "../access.js";
import { codeOf } from "../routekeys.js";

export const WHO = ["me", "dev", "agent"];
// The question, word for word: a set-up dialog's first step (tabs/agent-first.js) asks it too.
export const QUESTION = "Who will do it?";
export const KEY = "by";
const ALIAS = { someone: "dev" };
export const WORDS = {
  me: { title: "Me", sub: "I can do it myself: Skald shows the steps." },
  dev: { title: "My developer", sub: "Skald gives you a link or a message to send them." },
  agent: { title: "My AI agent", sub: "One line for Claude Code, Codex or Cursor. You watch it work." },
};
const ICONS = {
  me: '<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5a5 5 0 0 1 10 0"/>',
  dev: '<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5 8 9l5.5-4.5"/>',
  agent: '<rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M5 7l2 1.5L5 10M8.5 10.5H11"/>',
};
const svg = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;

// ---- remembered per person, in this browser (the person's address is never stored: a code of it)
const memKey = () => `ti-who:${codeOf(ME.user || "anyone")}`;
export function remembered() {
  try { const v = JSON.parse(localStorage.getItem(memKey()) || "null"); return WHO.includes(v) ? v : ""; } catch { return ""; }
}
export function remember(choice) {
  if (!WHO.includes(choice)) return false;
  try { localStorage.setItem(memKey(), JSON.stringify(choice)); return true; } catch { return false; }
}

/* The choice to open on: the address's (when offered), else the remembered one (when offered),
   else the caller's fallback (when offered), else none. */
export function startChoice(offered, { fromUrl = "", fallback = "" } = {}) {
  for (const k of [ALIAS[fromUrl] || fromUrl, remembered(), fallback]) if (k && offered.includes(k)) return k;
  return "";
}

/* The question and its answers; the chosen path drawn under them. paths: {me, dev, agent},
   each a function () -> nodes (or a Promise of nodes). route: {key, value} of the dialog open,
   so the choice is written in place inside it (overlays.js stepped). */
export function whoStep({ paths, route = null, key = KEY, fallback = "", question = QUESTION, onPick = null, subs = {}, from = null } = {}) {
  const offered = WHO.filter((k) => typeof paths?.[k] === "function");
  // from: the caller's own reading of the address (a dialog opened with a state of its own).
  const st = route ? S.read() : {};
  const fromUrl = from ?? (st[key] || (key === KEY ? st.fixby || "" : ""));
  let now = startChoice(offered, { fromUrl, fallback });
  const list = h("div", { class: "ui-who-list", role: "radiogroup", "aria-label": question });
  const body = h("div", { class: "ui-who-path", "aria-live": "polite" });
  const btns = offered.map((k) => {
    const b = h("button", { type: "button", role: "radio", class: "ui-who-c", "data-who": k, "aria-checked": "false" },
      h("span", { class: "ui-ic", html: svg(ICONS[k]) }), h("span", null, h("b", null, WORDS[k].title), h("small", null, subs[k] || WORDS[k].sub)));
    b.addEventListener("click", () => pick(k));
    b.addEventListener("keydown", (e) => {
      const i = offered.indexOf(k);
      const to = e.key === "ArrowDown" || e.key === "ArrowRight" ? offered[(i + 1) % offered.length]
        : e.key === "ArrowUp" || e.key === "ArrowLeft" ? offered[(i - 1 + offered.length) % offered.length] : null;
      if (!to) return;
      e.preventDefault();
      pick(to);
      list.querySelector(`[data-who="${to}"]`)?.focus();
    });
    return b;
  });
  list.append(...btns);
  let seq = 0;
  const out = { el: h("div", { class: "ui-who" }, h("p", { class: "ui-who-q" }, question), list, body), choice: () => now, ready: Promise.resolve() };
  function mark() {
    btns.forEach((b) => {
      const on = b.dataset.who === now;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on || (!now && b === btns[0]) ? 0 : -1;
    });
  }
  // pressed: the reader chose it now (a press), not an address or the remembered choice.
  function draw(pressed = false) {
    const mine = ++seq;
    if (!now) { body.replaceChildren(); return Promise.resolve(); }
    body.replaceChildren(h("p", { class: "empty" }, "Loading…"));
    let got;
    try { got = paths[now]({ pressed }); } catch (e) { got = Promise.reject(e); }
    return Promise.resolve(got).then((nodes) => {
      if (mine !== seq) return;
      body.replaceChildren(...[nodes].flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false && x !== ""));
    }, (e) => { if (mine === seq) body.replaceChildren(h("p", { class: "msg err" }, `This part could not be drawn: ${e?.message || e}`)); });
  }
  function pick(k) {
    if (!offered.includes(k)) return out.ready;
    now = k;
    remember(k);
    // The older fixby (Insights' first links) leaves once by is written.
    if (route) stepped(route.key, route.value, { [key]: k, ...(key === KEY && S.read().fixby ? { fixby: "" } : {}) });
    mark();
    out.ready = draw(true);
    onPick?.(k);
    return out.ready;
  }
  out.pick = pick;
  mark();
  out.ready = draw();
  return out;
}

/* The dialog: a drawer over the page with the question first. footer: extra buttons
   (the caller's one primary, e.g. "I have done it"); Close is always there. */
export async function whoDialog({ title, subtitle = "", route, paths, key = KEY, fallback = "", question, subs, top = null, footer = [], onClose = null, drawerKey = "who" }) {
  const { openDrawer } = await import("../drawer.js");
  const step = whoStep({ paths, route, key, fallback, question, subs });
  const close = h("button", { type: "button", class: "btn" }, "Close");
  const d = openDrawer({ title, subtitle, size: "md", key: drawerKey, scope: "page", className: "ui-who-dw",
    body: [top, step.el].filter(Boolean), footer: [h("span", { class: "grow" }), close, ...[].concat(footer)], onClose, route,
    focus: step.el.querySelector('[aria-checked="true"]') || step.el.querySelector(".ui-who-c") });
  close.addEventListener("click", () => d.close());
  d.who = step;
  return d;
}

// ---- the existing flows, as paths --------------------------------------------------

/* My AI agent: which agent (the agent tiles, remembered in the address as agent=<id>), then
   the line for these jobs (sites/agentlink) and its watch. jobs: ids kit/agent_jobs.py knows
   (tabs/agent-words.js JOBS); a job it does not know gets no agent path (pass none). */
export function agentPath({ site, jobs, route = null }) {
  const st = { site, jobs, agent: "", link: "", autoLine: false, send: null };
  return async () => {
    const [{ agentChooser }, { linePanel }, { watchPanel }, { SHELL_AGENTS }, { sendState }, { agentKey, agentOf, isLinkId }] = await Promise.all([
      import("../tabs/agent-setup.js"), import("../tabs/agent-setup.js"), import("../tabs/agent-watch.js"),
      import("../tabs/agent-first.js"), import("../tabs/conn-send.js"), import("../tabs/agent-words.js")]);
    if (!st.send) {
      st.send = sendState(site, {});
      const s = route ? S.read() : {};
      const want = agentKey(s.agent || "");
      if (agentOf(want)?.shell) st.agent = want;
      if (isLinkId(s.link)) st.link = s.link;
    }
    const box = h("div", { class: "ui-who-agent" });
    const keep = (patch) => { if (route) stepped(route.key, route.value, patch); };
    const w = { redraw: () => draw(), keep, say: () => {} };
    function draw() {
      if (!st.agent) {
        box.replaceChildren(...[agentChooser(st, (id) => { st.agent = id; st.autoLine = true; keep({ agent: id }); draw(); },
          { agents: SHELL_AGENTS, hand: null, intro: "Which AI agent are you using?" })].flat(Infinity).filter(Boolean));
        return;
      }
      box.replaceChildren(...[linePanel(st, w, { onMade: (r) => { if (r.link_id) keep({ link: r.link_id }); } }),
        h("h4", null, "Watch your agent work"), watchPanel(st)].flat(Infinity).filter(Boolean));
    }
    draw();
    return box;
  };
}

/* My developer or host: the private link to the steps (Share with your developer) when the
   job is one conn-share.js knows (send, script, hook, nextjs); else the message to copy. */
export function devPath({ site, task = "", method = "", message = "", link = "" }) {
  return async () => {
    if (task) return (await import("../tabs/conn-share.js")).shareBox(site, task, method);
    const { withCopy, withUrl } = await import("../urlactions.js");
    return [h("p", null, "Send them this message. It says what is wrong and where to look; the link opens this place in Skald for anyone on your team."),
      h("div", { class: "ui-card quiet" }, withCopy(h("p", { class: "ui-msg" }, message), message, { label: "the message", tag: "div" })),
      link ? h("p", { class: "note" }, "Link: ", withUrl(h("code", null, link), link, { label: "the link to this place" })) : null];
  };
}

/* Me: the steps the caller draws (nodes, or a function that returns them). */
export const mePath = (nodes) => () => (typeof nodes === "function" ? nodes() : nodes);
