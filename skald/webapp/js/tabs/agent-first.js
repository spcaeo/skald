// Your AI agent, in every set-up job (2.39, docs/plans/2026-10-26-agent-everywhere.md).
// The set-up dialogs with an agent job (the checklist's logs, script, lead, rsc, assets and
// privacy, and Settings > AI assistant (MCP)'s dialog) open on one first choice: Your AI agent
// (the tiles of Add a site's step 3, agent-setup.js agentChooser, without the chat-only one:
// a chat in the browser cannot change a site) or By hand (the dialog as it was, its steps
// numbered from 2). Your AI agent then has two steps: Send this line (agent-setup.js
// linePanel: POST sites/agentlink {site, jobs: [<job>]}) and Watch your agent work
// (agent-watch.js watchPanel), the same code as Add a site's.
//
// In the address, as Add a site: setup=<act>&step=<n>&agent=<id>&link=<link id> (the MCP
// dialog: conn=mcp&...). agent is an agent's id or hand; link the line watched, never the
// line or its code. A reload comes back to the same step; Back on the dialog's first step
// returns to the choice.
//
// The checklist's "Set up everything left with your AI agent" (setup=all&jobs=<id>.<id>...):
// allDialog, the same choice and steps for every open line an agent can do, with no By hand.

import { wizard } from "./conn-ui.js";
import { sendState } from "./conn-send.js";
import { agentChooser, linePanel } from "./agent-setup.js";
import { watchPanel } from "./agent-watch.js";
import { AGENTS, HAND, agentOf, agentKey, isLinkId, jobsInOrder, jobsWords } from "./agent-words.js";

// The agents that run commands: a chat in the browser cannot change a site's code or server.
export const SHELL_AGENTS = AGENTS.filter((a) => a.shell);
export const BY_HAND = { title: "By hand", sub: "Skald walks you through it, step by step." };

const introFor = (jobs, hand) => (jobs.length > 1
  ? `Skald writes one line for your agent, for ${jobsWords(jobs)}. The agent checks each one first, changes only what is missing, and reports back here. You watch each step.`
  : `Your AI agent can do this for you. Skald writes one line for it. The agent checks what is already done, changes only what is missing, and reports back here. You watch each step.${hand ? " Or do it yourself, by hand." : ""}`);

/* The wrap for wizard() (conn-ui.js): the choice, then the line and the watch, or the
   dialog's own steps. jobs: ids (agent-words.js JOBS); agent, link: the address's.
   hand: the By hand words, or null for none (allDialog). */
export function agentFirst(jobs, site, { agent = "", link = "", hand = BY_HAND } = {}) {
  const list = jobsInOrder(jobs);
  return ({ steps: own, start }) => {
    const want = agentKey(agent);
    const ok = want === HAND ? Boolean(hand) : Boolean(agentOf(want)?.shell);
    const ag = { site, jobs: list, agent: ok ? want : "", link: isLinkId(link) ? link : "", send: sendState(site, {}), autoLine: false };
    const steps = [];
    const sync = () => { steps.splice(1, steps.length - 1, ...(ag.agent === HAND ? own : [line, watch])); };
    const pick = (wz, id) => {
      ag.agent = id;
      ag.autoLine = id !== HAND;           // reached the line by a tile: it may make the line by itself
      if (id === HAND) ag.link = "";
      wz.keep({ agent: id, link: ag.link });
      sync();
      wz.say("");
      wz.go(1);
    };
    const choice = { name: hand ? "Agent or by hand" : "Your AI agent", title: hand ? "Your AI agent, or by hand?" : "Which AI agent are you using?",
      draw: (wz) => agentChooser(ag, (id) => pick(wz, id), { agents: SHELL_AGENTS, hand, intro: introFor(list, Boolean(hand)) }),
      check: () => (ag.agent ? "" : hand ? "Choose your AI agent, or By hand." : "Choose your AI agent."),
      next: () => { if (ag.agent !== HAND) ag.autoLine = true; return true; } };
    const line = { name: "Send this line", draw: (wz) => linePanel(ag, wz, { onMade: (r) => { if (r.link_id) wz.keep({ link: r.link_id }); } }) };
    const watch = { name: "Watch it work", title: "Watch your agent work", draw: () => watchPanel(ag) };
    steps.push(choice);
    sync();
    return { steps, start, sync, attach: (wz) => { wz.agent = ag; wz.keep({ agent: ag.agent, link: ag.link }); } };
  };
}

/* "Set up everything left with your AI agent": one line for every job in `jobs`. */
export function allDialog(site, jobs, { onClose = null, route = null, start = 0, agent = "", link = "" } = {}) {
  const list = jobsInOrder(jobs);
  const w = wizard({ route, start, title: "Set up everything left with your AI agent", subtitle: `For ${site}: ${jobsWords(list)}.`,
    key: "setup-all", onClose, done: "Close", steps: [], wrap: agentFirst(list, site, { agent, link, hand: null }) });
  w.keep({ jobs: list.join(".") });
  return w;
}
