// Settings › AI › AI assistants (v2): MCP, API and Tokens & links, one page with three tabs.
// Each tab shows the state and one button; how it works is behind the "?" (settings-frame.js).
// The dialogs are conn-read.js's (conn=mcp | conn=api in the address); the MCP dialog asks
// first "Who will do it?" (agent-first.js: your AI agent, or you, step by step).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { sessions, isViewer, VIEWER } from "../access.js";
import { DEMO } from "../demo.js";
import { codeBlock } from "./conn-ui.js";
import { connOpener, basic, quickLook } from "./connections.js";
import { sharesSection } from "./conn-share.js";
import tokens from "./tokens.js";
import { primary } from "./set-ui.js";

const isAdmin = () => !DEMO.on && sessions() && !isViewer();

/* The start button, or why this reader cannot press it. */
function startRow(name, site, words, { onClose = null } = {}) {
  if (DEMO.on) return h("p", { class: "note" }, "In the demo, connecting needs a running Skald.");
  if (!sessions()) return null;
  if (isViewer()) return h("p", { class: "note" }, `${VIEWER} An admin connects it here.`);
  const go = primary(words, connOpener(name, site, { onClose }), { iconName: name === "mcp" ? "bot" : "code" });
  go.classList.add("set-go");
  return go;
}

/* The MCP address, from the sites answer (mcp_url), else this server's. */
function mcpAddress() {
  const slot = h("div", null, codeBlock(`${location.origin}/traffic-mcp`, "the MCP address"));
  if (isAdmin()) call("sites").then((r) => { if (r.ok && r.mcp_url) slot.replaceChildren(codeBlock(r.mcp_url, "the MCP address")); });
  return slot;
}

export function mcpTab(m) {
  const site = m.site;
  let reload = () => {};
  // The assistants connected first (their tokens), then the address; examples on demand.
  const out = [startRow("mcp", site, "Connect an assistant", { onClose: () => reload() })];
  if (isAdmin()) out.push(tokens(m, { only: "mcp", title: "Assistants connected", reloadHook: (fn) => { reload = fn; } }));
  out.push(h("section", { class: "s" }, h("h2", null, "The MCP address"), h("p", { class: "sub" }, "Every assistant connects here, with its token in the Authorization header."), mcpAddress()),
    h("details", { class: "fold set-more" }, h("summary", null, "What you can ask"),
      h("ul", { class: "set-asks" },
        h("li", null, `"How many people visited ${site} this week, and from where?"`),
        h("li", null, "\"Which pages do AI assistants send people to?\""),
        h("li", null, "\"Which leads came in yesterday, and what did they read first?\""))));
  if (!DEMO.on && !sessions()) out.push(...basic());
  return out;
}

export function apiTab(m) {
  const site = m.site;
  const base = `${location.origin}/traffic-api/v1/${site}/`;
  const out = [startRow("api", site, "Set up the API"),
    h("section", { class: "s" }, h("h2", null, "The base address"), h("p", { class: "sub" }, "Add a file's name to it, for example overview. Send the token in the Authorization header."), codeBlock(base, "the base address"))];
  if (!DEMO.on && !sessions()) return [...out, ...basic()];
  out.push(quickLook());
  return out;
}

export function tokensTab(m) {
  if (DEMO.on) return h("div", { class: "state" }, h("div", null, "In the demo, tokens need a running Skald."));
  if (!sessions()) return basic();
  if (isViewer()) return h("div", { class: "state" }, h("div", null, `${VIEWER} Tokens and shared links are for admins.`));
  return [tokens(m), sharesSection()];
}
