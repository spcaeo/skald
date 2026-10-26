// Settings › This site (2.40): the pages a site's set-up runs through, in the order a person
// does it. The parts come from the pages they lived on before (connections.js, prefs.js,
// integrations.js, checklist.js); this file only lays them out.
//
//   Set-up checklist   what works and what is left (checklist.js), each Set up a dialog; the
//                      AI agent for all of it; Send set-up to someone
//   Collect data       Send logs: the send card, the AI agent, Test a sample, the log file
//                      Script tag & goals: the tag to copy, visitor IDs, the goals
//                      What counts: page assets, Next.js pages opened inside the site, not pages

import { h } from "../ui.js";
import { sessions, isViewer, VIEWER } from "../access.js";
import { DEMO } from "../demo.js";
import { head1, status } from "./forms.js";
import { setupChecklist, mayManage } from "./checklist.js";
import { sendCard, agentButton } from "./connections.js";
import { sites as siteCards } from "./prefs.js";
import { integrationsPart } from "./integrations.js";
import { taskCard } from "./conn-ui.js";

const NEXT_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v14H4z"/><path d="M8 9l3 3-3 3M13 15h3"/></svg>';
const BOT = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="8" width="14" height="11" rx="2.5"/><path d="M12 4v4M9 13h.01M15 13h.01M9.5 16.5h5"/></svg>';

/* Set-up checklist: the list, always shown here (ticks and all), and the AI agent. */
export function setupPage(m) {
  const title = head1("Set-up checklist", `What works and what is left for ${m.site}. Each line ticks itself once Skald sees it working; Set up walks you through it.`);
  if (!DEMO.on && !sessions()) return [title, h("div", { class: "state" }, h("div", null, "The set-up checklist comes with team accounts. On this server, the site is set up in the config file; the doctor command says what works."))];
  if (!DEMO.on && !mayManage()) return [title, h("div", { class: "state" }, h("div", null, `${isViewer() ? `${VIEWER} ` : ""}An owner or an admin sets this site up here.`))];
  const msg = status();
  const agent = DEMO.on ? null : h("section", { class: "s cn-cards cn-one", "aria-label": "Set up with your AI agent" },
    taskCard({ icon: BOT, title: "Or let your AI agent do it", button: "Choose your agent",
      line: "Claude Code, Codex, Cursor or another agent that runs commands: Skald writes one line for it. The agent checks what is done, changes only what is missing, and reports back here while you watch.",
      onOpen: () => agentButton(m.site, msg).click() }));
  return [title, setupChecklist(m, { where: "connections" }), agent, msg];
}

/* Collect data › Send logs. */
export function collectLogs(m) {
  return [head1("", "The server's access log is where Skald counts visits. On this Skald's own server it is read as it is; from another server or a platform, it is sent here."),
    sendCard(m), siteCards(m, "logs", { bare: true })];
}

/* Collect data › Script tag & goals. */
export function collectScript(m) {
  return [...integrationsPart("script"), siteCards(m, "script", { bare: true })];
}

/* Next.js pages opened inside the site: the set-up dialog (setup=rsc, setup-dialogs.js). */
function nextjsCard(m) {
  if (DEMO.on || !mayManage()) return null;
  return h("section", { class: "s cn-cards cn-one", "aria-label": "Next.js pages opened inside the site" },
    taskCard({ icon: NEXT_ICON, title: "Next.js: count pages opened inside the site", line: "A Next.js site opens most pages without a full page load, so the log sees only a data request. One field in the log, or the script tag, counts them as pages.",
      onOpen: async () => { const { openSetup } = await import("./setup-dialogs.js"); openSetup("rsc", m.site, {}); } }));
}

/* Collect data › What counts. */
export function collectCounting(m) {
  return [head1("", "Which visits count as people, and which addresses count as pages."), siteCards(m, "counting", { bare: true }), nextjsCard(m)];
}

/* Site details. */
export const siteDetails = (m) => siteCards(m, "details");
