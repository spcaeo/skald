// Your AI agent, in every set-up job (2.39, docs/plans/2026-10-26-agent-everywhere.md).
// The set-up dialogs with an agent job (the checklist's logs, script, lead, rsc, assets and
// privacy, search, and Settings > AI assistants' MCP dialog) open on the app's one question,
// "Who will do it?" (js/ui/who.js whoStep, Settings v2), as their step 1:
//
//   Me             the dialog as it was, its steps numbered from 2 (pressing Me goes there)
//   My developer   the set-up in one mail or one zip (setup-pack.js packBox), for the lines a
//                  developer does (logs, script, lead, rsc, assets: setup-finish.js TECH);
//                  not offered for privacy, search or MCP
//   My AI agent    the agent tiles (agent-setup.js agentChooser, without the chat-only one: a
//                  chat in the browser cannot change a site); a tile goes on to Send this line
//                  (linePanel: POST sites/agentlink {site, jobs: [<job>]}) and Watch your agent
//                  work (agent-watch.js watchPanel), the same code as Add a site's
//
// In the address: setup=<act>&step=<n>&by=me|dev|agent (the MCP dialog: conn=mcp&...), with
// agent=<id>&link=<link id> once My AI agent has them; link the line watched, never the line
// or its code. An older agent=hand link opens Me (by=me). A reload comes back to the same
// step; Back on the dialog's first step returns to the question.
//
// The checklist's "Set up everything left with your AI agent" (setup=all&jobs=<id>.<id>...):
// allDialog: no question (it is the agent's by name), the tiles, the line and its watch.

import { wizard } from "./conn-ui.js";
import { sendState } from "./conn-send.js";
import { agentChooser, linePanel } from "./agent-setup.js";
import { watchPanel } from "./agent-watch.js";
import { AGENTS, HAND, agentOf, agentKey, isLinkId, jobsInOrder, jobsWords } from "./agent-words.js";
import { store } from "../extras.js";
import { QUESTION, whoStep } from "../ui/who.js";
import { h } from "../ui.js";

// The agent this reader last chose (this browser): the Finish set-up dialog offers it first.
const LAST = "ti-agent-last";
export const lastAgent = () => { const id = store.get(LAST, ""); return agentOf(id)?.shell ? id : ""; };
export const rememberAgent = (id) => { if (agentOf(id)?.shell) store.set(LAST, id); };

// The agents that run commands: a chat in the browser cannot change a site's code or server.
export const SHELL_AGENTS = AGENTS.filter((a) => a.shell);
export const BY_HAND = { title: "Me", sub: "Skald walks you through it, step by step." };
// The lines a developer does from the set-up pack (as setup-finish.js TECH, less countries).
const DEV_JOBS = new Set(["logs", "script", "lead", "rsc", "assets"]);

const introFor = (jobs, hand) => (jobs.length > 1
  ? `Skald writes one line for your agent, for ${jobsWords(jobs)}. The agent checks each one first, changes only what is missing, and reports back here. You watch each step.`
  : `Your AI agent can do this: Skald writes one line for it, and you watch it work.${hand ? " Or do it yourself, step by step." : ""}`);

/* The wrap for wizard() (conn-ui.js): the question, then the line and the watch, or the
   dialog's own steps, or (My developer) the pack and nothing after. jobs: ids (agent-words.js
   JOBS); agent, link, by: the address's. hand: the Me words, or null for no question
   (allDialog: the tiles only). auto: the agent was chosen a step before (the Finish set-up
   dialog): its line is made at once. */
export function agentFirst(jobs, site, { agent = "", link = "", by = "", hand = BY_HAND, auto = false } = {}) {
  const list = jobsInOrder(jobs);
  const dev = Boolean(hand) && list.length === 1 && DEV_JOBS.has(list[0]);
  return ({ steps: own, start }) => {
    // agent=hand (before by=) is Me; by=me wins over an agent left in the address.
    const want = by === "me" && hand ? HAND : agentKey(agent);
    const ok = want === HAND ? Boolean(hand) : Boolean(agentOf(want)?.shell);
    const ag = { site, jobs: list, agent: ok ? want : "", link: isLinkId(link) ? link : "", send: sendState(site, {}), autoLine: Boolean(auto && ok && want !== HAND) };
    // The answer: me, dev or agent (from the agent, else the address's by=); "" until chosen.
    ag.by = ag.agent === HAND ? "me" : ag.agent ? "agent" : ["me", "agent"].includes(by) || (by === "dev" && dev) ? by : "";
    if (ag.by === "me") { ag.agent = HAND; ag.link = ""; }
    const steps = [];
    const after = () => (!hand ? [line, watch] : ag.by === "me" ? own : ag.by === "dev" ? [] : [line, watch]);
    const sync = () => { steps.splice(1, steps.length - 1, ...after()); };
    const pick = (wz, id) => {
      ag.agent = id;
      ag.by = "agent";
      ag.autoLine = true;                  // reached the line by a tile: it may make the line by itself
      rememberAgent(id);
      wz.keep({ by: hand ? "agent" : "", agent: id, link: ag.link });
      sync();
      wz.say("");
      wz.go(1);
    };
    const tiles = (wz, words) => agentChooser(ag, (id) => pick(wz, id), { agents: SHELL_AGENTS, hand: null, intro: words });
    // Who answered: the step count follows (Me: the dialog's own steps; My developer: none).
    const answered = (wz, k) => {
      ag.by = k;
      if (k === "me") { ag.agent = HAND; ag.link = ""; wz.keep({ agent: "", link: "" }); } else if (ag.agent === HAND) ag.agent = "";
      wz.say("");
      wz.drawBar();
    };
    const question = (wz) => {
      const route = wz.route ? { key: wz.route.key, value: wz.route.value } : null;
      const paths = {
        me: () => h("p", { class: "note" }, `Skald walks you through it, step by step${own.length ? `: ${own.length} step${own.length === 1 ? "" : "s"}` : ""}.`),
        ...(dev ? { dev: async () => (await import("./setup-pack.js")).packBox(site) } : {}),
        agent: () => tiles(wz, introFor(list, false)),
      };
      const st = whoStep({ paths, route, from: ag.by, onPick: (k) => answered(wz, k),
        subs: dev ? { dev: "Send them the set-up in one mail or one zip." } : {} });
      ag.by = st.choice();
      if (ag.by === "me") ag.agent = HAND;
      st.el.querySelector(".ui-who-q")?.remove();        // the step's heading asks it
      // A press on Me goes on to the dialog's own steps (an arrow key only chooses).
      st.el.querySelector('[data-who="me"]')?.addEventListener("click", () => wz.go(1));
      return st.el;
    };
    const choice = { name: hand ? QUESTION : "Your AI agent", title: hand ? QUESTION : "Which AI agent are you using?",
      draw: (wz) => (hand ? question(wz) : tiles(wz, introFor(list, false))),
      check: () => (!hand ? (ag.agent ? "" : "Choose your AI agent.") : !ag.by ? "Choose who will do it." : ag.by === "agent" && !ag.agent ? "Choose your AI agent." : ""),
      next: () => { if (ag.by === "agent" || !hand) ag.autoLine = true; return true; } };
    const line = { name: "Send this line", draw: (wz) => linePanel(ag, wz, { onMade: (r) => { if (r.link_id) wz.keep({ link: r.link_id }); } }) };
    const watch = { name: "Watch it work", title: "Watch your agent work", draw: () => watchPanel(ag) };
    steps.push(choice);
    sync();
    return { steps, start, sync, attach: (wz) => {
      wz.agent = ag;
      wz.keep({ ...(hand ? { by: ag.by } : {}), agent: ag.agent === HAND ? "" : ag.agent, link: ag.link });
    } };
  };
}

/* "Set up everything left with your AI agent": one line for every job in `jobs`. */
export function allDialog(site, jobs, { onClose = null, route = null, start = 0, agent = "", link = "", auto = false } = {}) {
  const list = jobsInOrder(jobs);
  const w = wizard({ route, start, title: "Your AI agent sets it up", subtitle: `For ${site}: ${jobsWords(list)}.`,
    key: "setup-all", onClose, done: "Close", steps: [], wrap: agentFirst(list, site, { agent, link, hand: null, auto }) });
  w.keep({ jobs: list.join(".") });
  return w;
}
