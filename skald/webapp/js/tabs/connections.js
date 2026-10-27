// The connection dialogs and the parts of the old Settings > Connections page (2.40: the page
// is gone; its parts live where a person looks for them, docs/plans/2026-10-26-settings-redesign.md):
//
//   connOpener()    a button's opener for a dialog: send, sample, api, mcp (v2: Data and
//                   AI assistants each have one button; Send logs goes through Finish set-up)
//   basic()         a server with one shared login: the API with the dashboard login, and the
//                   token commands (AI assistants › API)
//   quickLook()     the figures as JSON while signed in, and the files this page serves
//   openConnKey()   conn=send|api|mcp|sample&step=<n>(&agent=<id>&link=<id>), from a link
//                   (js/overlays.js): the dialog at that step for an admin; the line otherwise.
// The dialogs need accounts (access.mode: sessions). A viewer reads what each part is for.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, isViewer, VIEWER, sessions } from "../access.js";
import { copyable, status } from "./forms.js";
import { sendDialog } from "./conn-send.js";
import { apiDialog, mcpDialog } from "./conn-read.js";
import { sampleDialog } from "./conn-sample.js";
import { agentFirst } from "./agent-first.js";
import { DEMO } from "../demo.js";
import { withUrl } from "../urlactions.js";

export const PAGE = () => location.pathname.replace(/[^/]*$/, "");   // this page's folder: /traffic/<site>/[<view>/]
const SITE_PART = () => PAGE().replace(/^\/traffic\//, "");          // <site>/[<view>/]

export function fileList() {
  const files = h("div", { class: "api-files" }, h("p", { class: "empty" }, "Loading the list..."));
  call("api/v1/").then((r) => {
    if (!r.ok || !Array.isArray(r.files)) { files.replaceChildren(h("p", { class: "empty" }, r.missing ? "The API is not switched on for this page yet." : r.error)); return; }
    files.replaceChildren(...r.files.map((name) => withUrl(h("a", { class: "api-f", href: `api/v1/${name}`, target: "_blank", rel: "noopener" }, name), `${location.origin}${PAGE()}api/v1/${name}`, { label: name, cls: "ua-after" })));
  });
  return files;
}

// One shared login (basic mode): the API with the dashboard password, and tokens made on the server.
export function basic() {
  const origin = location.origin;
  const withLogin = `${origin}${PAGE()}api/v1/overview`;
  const withToken = `${origin}/traffic-api/v1/${SITE_PART()}overview`;
  return [
    h("div", { class: "state" }, h("div", null, "The set-up dialogs (sending a site's log, tokens for scripts, AI assistants) need team accounts. This server uses one shared login, so tokens are made on the server.")),
    h("details", { class: "fold" }, h("summary", null, "Read the figures with the dashboard login, or a token made on the server"),
      h("p", { class: "sub" }, "With the dashboard login, for a quick look or a spreadsheet:"),
      copyable(withLogin, "the address with your login"), copyable(`curl -u ${ME.user || "name"} ${withLogin}`, "the curl command"),
      h("p", { class: "sub" }, "With a token, for a script:"),
      copyable(`curl -H "Authorization: Bearer <token>" ${withToken}`, "the curl command with a token"),
      isViewer() ? h("p", { class: "note" }, VIEWER) : [
        h("p", { class: "sub" }, "Tokens are made on the server by an admin, printed once. --private lets a token read the files with visitor addresses. A token for an AI assistant needs --scope mcp."),
        copyable(`skald token create "Weekly sheet" --site ${SITE_PART().split("/")[0]}`, "the command to make a token"),
        copyable("skald token list", "the command to list tokens"),
        copyable("skald token revoke <id>", "the command to revoke a token")],
      h("h3", null, "Files this page serves"), fileList()),
  ];
}

// The figures as JSON in this browser while signed in, with no token.
export function quickLook({ open = false } = {}) {
  return h("details", { class: "fold", open }, h("summary", null, "Quick look while you are signed in"),
    h("p", { class: "sub" }, "The figures as JSON in this browser, with no token, while you are signed in here."),
    copyable(`${location.origin}${PAGE()}api/v1/overview`, "the address while signed in"), h("h3", null, "Files this page serves"), fileList());
}

const DIALOGS = { send: sendDialog, api: apiDialog, mcp: mcpDialog, sample: sampleDialog };
// 2.39: the MCP dialog opens on "Who will do it?" (agent-first.js, job mcp: Me or My AI agent);
// agent, link and by: the address's.
export function openConn(name, site, data, { onClose = null, start = 0, agent = "", link = "", by = "" } = {}) {
  const wrap = name === "mcp" ? agentFirst(["mcp"], site, { agent, link, by }) : null;
  return DIALOGS[name](site, data, { onClose, route: { key: "conn", value: name }, start, wrap });
}

/* conn=send|api|mcp&step=<n>(&by=me|agent&agent=<id>&link=<id>), from a link: the dialog at that step for
   an admin; the line otherwise. s: the address's state. */
export async function openConnKey(name, m, step = 1, share = false, s = {}) {
  if (!DIALOGS[name]) return "That connection dialog is not in this version of the page.";
  if (DEMO.on) return "Setting up a connection needs a running Skald: not available in the demo.";
  if (!sessions() || isViewer()) return "Not available to your role.";
  const r = await call("sites");
  return openConn(name, m.site, r.ok ? r : {}, { start: Math.max(0, step - 1), agent: s.agent || "", link: s.link || "", by: s.by || "" });
}

/* A button that opens a connection dialog: the sites answer asked once, when first pressed.
   onClose: after the dialog (a token list to read again). */
export function connOpener(name, site, { onClose = null } = {}) {
  let data = null;
  return async () => {
    if (!data) { const r = await call("sites"); data = r.ok ? r : {}; }
    openConn(name, site, data, { onClose });
  };
}

