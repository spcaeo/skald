// Settings > API and Settings > Users. The read-only API serves every data
// file as it is (docs/API.md): with the dashboard password, or with a token
// for a script. Tokens and users are made on the server with the tool, by an
// admin, so these pages show this site's real addresses, the files it
// serves, who is signed in, and the exact commands; nothing secret is shown.
// With accounts (access.mode: sessions) tokens are made here instead
// (tokens.js), and Users points to Team.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, isViewer, VIEWER, sessions } from "../access.js";
import { head1, copyable } from "./forms.js";
import { howTo } from "./help.js";
import tokens from "./tokens.js";

const PAGE = () => location.pathname.replace(/[^/]*$/, "");   // this page's folder: /traffic/<site>/[<view>/]
const SITE_PART = () => PAGE().replace(/^\/traffic\//, "");   // <site>/[<view>/]

export function api(m) {
  const origin = location.origin;
  const withLogin = `${origin}${PAGE()}api/v1/overview`;
  const withToken = `${origin}/traffic-api/v1/${SITE_PART()}overview`;
  const files = h("div", { class: "api-files" }, h("p", { class: "empty" }, m.x.funnels ? "Loading the list..." : "The API comes with the next server release."));
  if (m.x.funnels) {
    call("api/v1/").then((r) => {
      if (!r.ok || !Array.isArray(r.files)) { files.replaceChildren(h("p", { class: "empty" }, r.missing ? "The API is not switched on for this page yet." : r.error)); return; }
      files.replaceChildren(...r.files.map((name) => h("a", { class: "api-f", href: `api/v1/${name}`, target: "_blank", rel: "noopener" }, name)));
    });
  }
  const admin = !isViewer();
  return [
    head1("API", "Read-only: every figure on these pages, as JSON."),
    h("div", { class: "howto-row" }, howTo("api", "How do I use the API, with curl examples?", { block: false }),
      howTo("mcp", "How do I connect Claude, ChatGPT or another assistant (MCP)?", { block: false })),
    h("section", { class: "s" }, h("div", { class: "cols tops" },
      sessions() ? h("div", { class: "sheet" }, h("h3", null, "While you are signed in"), h("p", { class: "sub" }, "For a quick look in this browser: the address works while you are signed in here."),
        copyable(withLogin, "the address while signed in"))
        : h("div", { class: "sheet" }, h("h3", null, "With your dashboard login"), h("p", { class: "sub" }, "For a quick look or a spreadsheet: the same password as these pages."),
          copyable(withLogin, "the address with your login"), copyable(`curl -u ${ME.user || "name"} ${withLogin}`, "the curl command")),
      h("div", { class: "sheet" }, h("h3", null, "With a token, for a script"), h("p", { class: "sub" }, "No password in the script: a token sent in the Authorization header."),
        copyable(withToken, "the address for a token"), copyable(`curl -H "Authorization: Bearer <token>" ${withToken}`, "the curl command with a token")),
      // MCP needs accounts (a token with the mcp scope), so a server with one shared login does not offer it.
      sessions() ? h("div", { class: "sheet" }, h("h3", null, "For an AI assistant (MCP)"), h("p", { class: "sub" }, "Claude, ChatGPT or any MCP client: this address, with a token that has the MCP scope."),
        copyable(`${origin}/traffic-mcp`, "the MCP address"),
        copyable(`claude mcp add --transport http skald ${origin}/traffic-mcp --header "Authorization: Bearer <token>"`, "the Claude Code command")) : null)),
    h("section", { class: "s" }, h("h2", null, "Files this page serves"), h("p", { class: "sub" }, "Replace overview in the addresses above with any of these. Each is described in the data contract; they are rewritten every 2 minutes."), files),
    sessions() ? tokens(m) : h("section", { class: "s" }, h("h2", null, "Tokens"),
      admin ? [
        h("p", { class: "sub" }, "Made on the server by an admin. A token is printed once, when it is made; only a fingerprint of it is kept. A token cannot read the request log or the AI activity, which hold visitor addresses, unless it is made with --private."),
        copyable('skald token create "Weekly sheet" --site ' + SITE_PART().split("/")[0], "the command to make a token"),
        copyable("skald token list", "the command to list tokens"),
        copyable("skald token revoke <id>", "the command to revoke a token"),
      ] : h("p", { class: "note" }, VIEWER)),
    h("p", { class: "note" }, "Answers: 200 with the file; 401 for a missing, unknown or revoked token, or a token for another site; 404 for a file this page does not have. Nothing can be changed through the API. The API guide in Help has examples; the full reference is docs/API.md in Skald's code."),
  ];
}

export function users() {
  // With accounts, people are managed under Team; this page only points there.
  if (sessions()) return [head1("Users", "Who may look, and who may change things."), h("div", { class: "state" }, h("div", null, "People now sign in with their own accounts. See ",
    h("a", { href: "#settings/team" }, "Settings > Team"), " for members and invites, and ", h("a", { href: "#settings/account" }, "Your account"), " for your password."))];
  if (isViewer()) return [head1("Users", "Who may look, and who may change things."), h("div", { class: "state" }, h("div", null, `${VIEWER} The list of users is for admins.`))];
  return [
    head1("Users", "Who may look, and who may change things."),
    h("section", { class: "s" }, h("div", { class: "cols tops" },
      h("div", { class: "sheet" }, h("h3", null, "You"), h("p", { class: "u-me" }, ME.user ? [h("b", null, ME.user), ` (${ME.role || "admin"})`] : "One shared login, which is an admin until users are added on the server.")),
      h("div", { class: "sheet" }, h("h3", null, "Two roles"), h("dl", { class: "u-roles" },
        h("dt", null, "Admin"), h("dd", null, "sees everything; changes internal addresses and funnels; on the server, makes tokens and users"),
        h("dt", null, "Viewer"), h("dd", null, "sees everything these pages show, changes nothing"))))),
    h("section", { class: "s" }, h("h2", null, "Adding, changing and removing users"),
      h("p", { class: "sub" }, "On the server, with the tool. Each user has their own password, asked for when they are added and never shown again; every change is logged. A user the list does not name is a viewer."),
      copyable("skald user add <name> --role viewer", "the command to add a user"),
      copyable("skald user role <name> admin", "the command to change a role"),
      copyable("skald user remove <name>", "the command to remove a user"),
      copyable("skald user list", "the command to list users")),
  ];
}
