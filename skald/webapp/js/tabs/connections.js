// Settings > Connections (route settings/api, so old links keep working).
// Three tasks, each a card whose Set up opens a short dialog with steps:
// send a site's visits to Skald (conn-send.js), read the figures with the API,
// connect an AI assistant over MCP (conn-read.js). Below, the organisation's
// tokens (tokens.js). The dialogs need accounts (access.mode: sessions); a
// server with one shared login keeps the server-command way, folded away.
// A viewer reads what each part is for; tokens and dialogs are for admins.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, isViewer, VIEWER, sessions } from "../access.js";
import { head1, copyable } from "./forms.js";
import { howTo } from "./help.js";
import { taskCard, ICONS } from "./conn-ui.js";
import { sendDialog } from "./conn-send.js";
import { apiDialog, mcpDialog } from "./conn-read.js";
import tokens from "./tokens.js";
import { sharesSection } from "./conn-share.js";

const PAGE = () => location.pathname.replace(/[^/]*$/, "");   // this page's folder: /traffic/<site>/[<view>/]
const SITE_PART = () => PAGE().replace(/^\/traffic\//, "");   // <site>/[<view>/]
const LEDE = "Send a site's visits to Skald, read your figures from a script, or connect an AI assistant.";

function fileList() {
  const files = h("div", { class: "api-files" }, h("p", { class: "empty" }, "Loading the list..."));
  call("api/v1/").then((r) => {
    if (!r.ok || !Array.isArray(r.files)) { files.replaceChildren(h("p", { class: "empty" }, r.missing ? "The API is not switched on for this page yet." : r.error)); return; }
    files.replaceChildren(...r.files.map((name) => h("a", { class: "api-f", href: `api/v1/${name}`, target: "_blank", rel: "noopener" }, name)));
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

export default function connections(m) {
  const title = head1("Connections", LEDE);
  const guides = h("div", { class: "howto-row" }, howTo("connections", "How do I connect a site, a script or an assistant?", { block: false }),
    howTo("troubleshooting-connections", "Something does not work?", { block: false }));
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
  const open = (fn) => async () => { const d = data || await loaded; fn(site, d, { onClose: () => reloadTokens() }); };
  const cards = h("section", { class: "s cn-cards", "aria-label": "Set up a connection" },
    taskCard({ icon: ICONS.send, title: "Send this site's visits to Skald", line: `For ${site} when its web server is not this Skald's server: a shipper, Cloudflare, Vercel or Netlify, or only the script tag.`, onOpen: open(sendDialog) }),
    taskCard({ icon: ICONS.read, title: "Read your figures (API)", line: "Every figure as JSON, for a script or a spreadsheet, with a read-only token.", onOpen: open(apiDialog) }),
    taskCard({ icon: ICONS.mcp, title: "Connect an AI assistant (MCP)", line: "Ask Claude, ChatGPT or another assistant about your traffic in plain words.", onOpen: open(mcpDialog) }));
  return [title, guides, cards,
    tokens(m, { reloadHook: (fn) => { reloadTokens = fn; } }), sharesSection(),
    h("details", { class: "fold" }, h("summary", null, "Quick look while you are signed in"),
      h("p", { class: "sub" }, "The figures as JSON in this browser, with no token, while you are signed in here."),
      copyable(`${location.origin}${PAGE()}api/v1/overview`, "the address while signed in"), h("h3", null, "Files this page serves"), fileList())];
}
