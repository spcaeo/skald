// Settings > Users. Users are made on the server with the tool, by an admin,
// so this page shows who is signed in and the exact commands; nothing secret
// is shown. With accounts (access.mode: sessions) Users points to Team.
// (2.40: the API, MCP and tokens are Settings › AI assistants, set-ai.js.)

import { h } from "../ui.js";
import { ME, isViewer, VIEWER, sessions } from "../access.js";
import { head1, copyable } from "./forms.js";

export function users() {
  // With accounts, people are managed under Team; this page only points there.
  if (sessions()) return [head1("Users", "Who may look, and who may change things."), h("div", { class: "state" }, h("div", null, "People now sign in with their own accounts. See ",
    h("a", { href: "#settings/org/people" }, "Settings › People"), " for members and invites, and ", h("a", { href: "#settings/you/account" }, "Your account"), " for your password."))];
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
