// Settings › AI & API (2.40): connect an AI assistant over MCP, read the figures with the API,
// and every token and shared link. Each page says how it works first, as numbered steps, then
// the button that does it; the token is made inside the dialog's step that uses it, never above
// the steps (the owner, 2026-10-26: "the token was above the steps"). The dialogs are
// conn-read.js's (conn=mcp | conn=api in the address).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { sessions, isViewer, VIEWER } from "../access.js";
import { DEMO } from "../demo.js";
import { head1 } from "./forms.js";
import { codeBlock } from "./conn-ui.js";
import { connOpener, basic, quickLook } from "./connections.js";
import { sharesSection } from "./conn-share.js";
import tokens from "./tokens.js";

const isAdmin = () => !DEMO.on && sessions() && !isViewer();

/* How it works: a numbered list of plain steps. */
const howItWorks = (label, items) => h("section", { class: "s set-how", "aria-label": label },
  h("h2", null, "How it works"), h("ol", { class: "set-steps" }, items.map(([b, words]) => h("li", null, h("b", null, b), " ", words))));

/* The start button, or why this reader cannot press it. */
function startRow(name, site, words, { onClose = null } = {}) {
  if (DEMO.on) return h("p", { class: "note" }, "In the demo, connecting needs a running Skald.");
  if (!sessions()) return null;
  if (isViewer()) return h("p", { class: "note" }, `${VIEWER} An admin connects it here.`);
  const go = h("button", { type: "button", class: "btn primary set-go" }, words);
  go.addEventListener("click", connOpener(name, site, { onClose }));
  return h("div", { class: "acts set-start" }, go);
}

/* The MCP address, from the sites answer (mcp_url), else this server's. */
function mcpAddress() {
  const slot = h("div", null, codeBlock(`${location.origin}/traffic-mcp`, "the MCP address"));
  if (isAdmin()) call("sites").then((r) => { if (r.ok && r.mcp_url) slot.replaceChildren(codeBlock(r.mcp_url, "the MCP address")); });
  return slot;
}

export function mcpPage(m) {
  const site = m.site;
  let reload = () => {};
  const out = [head1("AI assistant (MCP)", "Ask Claude, ChatGPT or another assistant about your traffic in plain words: who came, from where, which pages, which leads. It reads this site's figures; it cannot change anything."),
    howItWorks("How connecting an assistant works", [
      ["Choose your assistant.", "Claude Code, Claude Desktop, ChatGPT through the OpenAI API, or any assistant that speaks MCP over HTTP. Or let your AI agent do all of it."],
      ["Make a token for it.", "Skald shows it once, inside the step that needs it. It reads; it changes nothing."],
      ["Paste one command or config.", "Skald fills in the address and the token for the assistant you chose."],
      ["Test.", "This browser connects as your assistant would and lists the tools it gets."]]),
    startRow("mcp", site, "Connect an assistant", { onClose: () => reload() }),
    h("section", { class: "s" }, h("h2", null, "What you can ask"),
      h("ul", { class: "set-asks" },
        h("li", null, `"How many people visited ${site} this week, and from where?"`),
        h("li", null, "\"Which pages do AI assistants send people to?\""),
        h("li", null, "\"Which leads came in yesterday, and what did they read first?\""),
        h("li", null, "\"What should I fix first on the site?\""))),
    h("section", { class: "s" }, h("h2", null, "The MCP address"), h("p", { class: "sub" }, "Every assistant connects here, with its token in the Authorization header."), mcpAddress())];
  if (isAdmin()) out.push(tokens(m, { only: "mcp", title: "Tokens for assistants", reloadHook: (fn) => { reload = fn; } }));
  if (!DEMO.on && !sessions()) out.push(...basic());
  return out;
}

export function apiPage(m) {
  const site = m.site;
  const base = `${location.origin}/traffic-api/v1/${site}/`;
  const out = [head1("Read figures (API)", "Every figure these pages show, as JSON, for a script or a spreadsheet. Read-only."),
    howItWorks("How the API works", [
      ["Pick a file.", "overview, sources, pages and the rest: the same figures as the dashboard, rewritten every 2 minutes."],
      ["Make a read-only token.", "Skald shows it once, in the step that needs it, with the curl command under it."],
      ["Ask with the token.", "Add the file's name to the base address and send the token in the Authorization header."],
      ["Test.", "This browser asks for overview as your script would."]]),
    startRow("api", site, "Set up the API"),
    h("section", { class: "s" }, h("h2", null, "The base address"), h("p", { class: "sub" }, "Add a file's name to it, for example overview."), codeBlock(base, "the base address"),
      h("p", { class: "note" }, "Want each lead pushed to you instead of asking? Leads & integrations › Outgoing webhooks posts each conversion to your CRM, Zapier or Slack."))];
  if (!DEMO.on && !sessions()) return [...out, ...basic()];
  out.push(quickLook());
  return out;
}

export function tokensPage(m) {
  const title = head1("Tokens & links", "Every token of the organisation and the private set-up links shared with a developer. Revoke one here and whatever uses it stops at once.");
  if (DEMO.on) return [title, h("div", { class: "state" }, h("div", null, "In the demo, tokens need a running Skald."))];
  if (!sessions()) return [title, ...basic()];
  if (isViewer()) return [title, h("div", { class: "state" }, h("div", null, `${VIEWER} Tokens and shared links are for admins.`))];
  return [title, tokens(m), sharesSection()];
}
