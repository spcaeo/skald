// Settings > Connections (route settings/api, so old links keep working).
// At the top, for owners and admins: "Set up <site>", the same checklist as Overview's,
// always shown (all ticks and "All set" once done; js/tabs/checklist.js).
// Three tasks, each a card whose Set up opens a short dialog with steps:
// send a site's visits to Skald (conn-send.js), read the figures with the API,
// connect an AI assistant over MCP (conn-read.js). Below, the organisation's
// tokens (tokens.js). The dialogs need accounts (access.mode: sessions); a
// server with one shared login keeps the server-command way, folded away.
// A viewer reads what each part is for; tokens and dialogs are for admins.
// Each dialog is in the address as conn=send|api|mcp|sample&step=<n> (js/overlays.js). The send
// card's "Test a sample" (2.35) opens the dry run of a pasted log sample (conn-sample.js). The send
// card's "Set up with your AI agent" opens this site's Add a site wizard at its step 3,
// "Which AI agent are you using?" (setup=<site>&step=3, site-wizard.js).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, isViewer, VIEWER, sessions } from "../access.js";
import { head1, copyable, status } from "./forms.js";
import { howTo } from "./help.js";
import { taskCard, ICONS } from "./conn-ui.js";
import { sendDialog } from "./conn-send.js";
import { apiDialog, mcpDialog } from "./conn-read.js";
import { sampleDialog } from "./conn-sample.js";
import tokens from "./tokens.js";
import { sharesSection } from "./conn-share.js";
import { setupChecklist } from "./checklist.js";
import { DEMO } from "../demo.js";
import { withUrl } from "../urlactions.js";

const PAGE = () => location.pathname.replace(/[^/]*$/, "");   // this page's folder: /traffic/<site>/[<view>/]
const SITE_PART = () => PAGE().replace(/^\/traffic\//, "");   // <site>/[<view>/]
const LEDE = "Send a site's visits to Skald, read your figures from a script, or connect an AI assistant.";

function fileList() {
  const files = h("div", { class: "api-files" }, h("p", { class: "empty" }, "Loading the list..."));
  call("api/v1/").then((r) => {
    if (!r.ok || !Array.isArray(r.files)) { files.replaceChildren(h("p", { class: "empty" }, r.missing ? "The API is not switched on for this page yet." : r.error)); return; }
    files.replaceChildren(...r.files.map((name) => withUrl(h("a", { class: "api-f", href: `api/v1/${name}`, target: "_blank", rel: "noopener" }, name), `${location.origin}${PAGE()}api/v1/${name}`, { label: name, cls: "ua-after" })));
  });
  return files;
}

// One shared login (basic mode): the API with the dashboard password, and tokens made on the server.
function basic() {
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
        h("p", { class: "sub" }, "Tokens are made on the server by an admin, printed once. --private lets a token read the files with visitor addresses."),
        copyable(`skald token create "Weekly sheet" --site ${SITE_PART().split("/")[0]}`, "the command to make a token"),
        copyable("skald token list", "the command to list tokens"),
        copyable("skald token revoke <id>", "the command to revoke a token")],
      h("h3", null, "Files this page serves"), fileList()),
  ];
}

const DIALOGS = { send: sendDialog, api: apiDialog, mcp: mcpDialog, sample: sampleDialog };
function openConn(name, site, data, { onClose = null, start = 0 } = {}) {
  return DIALOGS[name](site, data, { onClose, route: { key: "conn", value: name }, start });
}

/* conn=send|api|mcp&step=<n>, from a link: the dialog at that step for an admin; the line otherwise. */
export async function openConnKey(name, m, step = 1) {
  if (!DIALOGS[name]) return "That connection dialog is not in this version of the page.";
  if (DEMO.on) return "Setting up a connection needs a running Skald: not available in the demo.";
  if (!sessions() || isViewer()) return "Not available to your role.";
  const r = await call("sites");
  return openConn(name, m.site, r.ok ? r : {}, { start: Math.max(0, step - 1) });
}

// The demo: the set-up list, the three tasks and the tokens, from the demo's own answers.
function demoPage(m, title, guides) {
  const note = "In the demo, setting up needs a running Skald.";
  const card = (icon, t, line) => taskCard({ icon, title: t, line, note, disabled: true, onOpen: () => {} });
  return [setupChecklist(m, { where: "connections" }), title, guides,
    h("section", { class: "s cn-cards", "aria-label": "Set up a connection" },
      card(ICONS.send, "Send this site's visits to Skald", `For ${m.site} when its web server is not this Skald's server: a shipper, Cloudflare, Vercel or Netlify, or only the script tag.`),
      card(ICONS.read, "Read your figures (API)", "Every figure as JSON, for a script or a spreadsheet, with a read-only token."),
      card(ICONS.mcp, "Connect an AI assistant (MCP)", "Ask Claude, ChatGPT or another assistant about your traffic in plain words.")),
    tokens(m)];
}

export default function connections(m) {
  const title = head1("Connections", LEDE);
  const guides = h("div", { class: "howto-row" }, howTo("connections", "How do I connect a site, a script or an assistant?", { block: false }),
    howTo("troubleshooting-connections", "Something does not work?", { block: false }));
  if (DEMO.on) return demoPage(m, title, guides);
  if (!sessions()) return [title, guides, ...basic()];
  if (isViewer()) {
    return [title, guides, h("div", { class: "state" }, h("div", null,
      `${VIEWER} An admin sets up connections here: a site's server sending its log to Skald, tokens for scripts that read the figures, and AI assistants (MCP).`)),
    h("section", { class: "s" }, h("h2", null, "While you are signed in"), h("p", { class: "sub" }, "For a quick look in this browser: the figures as JSON, while you are signed in here."),
      copyable(`${location.origin}${PAGE()}api/v1/overview`, "the address while signed in"))];
  }
  const site = m.site;
  let data = null;
  const loaded = call("sites").then((r) => { data = r.ok ? r : {}; return data; });
  let reloadTokens = () => {};
  const open = (name) => async () => { const d = data || await loaded; openConn(name, site, d, { onClose: () => reloadTokens() }); };
  // The AI agent's way: the site's wizard at "Which AI agent are you using?", whatever was saved.
  const msg = status();
  const agent = h("button", { type: "button", class: "btn", "aria-label": `Set up ${site} with your AI agent` }, "Set up with your AI agent");
  agent.addEventListener("click", async () => {
    const got = await (await import("./sitesadmin.js")).openSiteKey(site, 3, { pick: true });
    if (typeof got === "string") msg.say(got);
  });
  // Test a sample: can Skald read a log source? Known before the next daily run.
  const sample = h("button", { type: "button", class: "btn", "aria-label": `Test a sample of a log for ${site}` }, "Test a sample");
  sample.addEventListener("click", open("sample"));
  const cards = h("section", { class: "s cn-cards", "aria-label": "Set up a connection" },
    taskCard({ icon: ICONS.send, title: "Send this site's visits to Skald", line: `For ${site} when its web server is not this Skald's server: a shipper, Cloudflare, Vercel or Netlify, or only the script tag. Or one line for your AI agent. Not sure Skald can read a log? Test a sample first.`, onOpen: open("send"), more: [agent, sample] }),
    taskCard({ icon: ICONS.read, title: "Read your figures (API)", line: "Every figure as JSON, for a script or a spreadsheet, with a read-only token.", onOpen: open("api") }),
    taskCard({ icon: ICONS.mcp, title: "Connect an AI assistant (MCP)", line: "Ask Claude, ChatGPT or another assistant about your traffic in plain words.", onOpen: open("mcp") }));
  return [setupChecklist(m, { where: "connections" }), title, guides, cards, msg,
    tokens(m, { reloadHook: (fn) => { reloadTokens = fn; } }), sharesSection(),
    h("details", { class: "fold" }, h("summary", null, "Quick look while you are signed in"),
      h("p", { class: "sub" }, "The figures as JSON in this browser, with no token, while you are signed in here."),
      copyable(`${location.origin}${PAGE()}api/v1/overview`, "the address while signed in"), h("h3", null, "Files this page serves"), fileList())];
}
