// Settings > Audit log (accounts, access.mode: sessions): who changed what,
// and when - settings, the team, tokens, sign-ins that failed - newest first,
// filtered by action, and as a CSV file. For admins; install admins see every
// organisation's rows. GET <page>/settings/audit (settings_api.py).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions, VIEWER } from "../access.js";
import { head1, field, when, why } from "./forms.js";

export default function auditlog() {
  const title = head1("Audit log", "Who changed what, and when.");
  if (!sessions()) return [title, h("div", { class: "state" }, h("div", null, "The audit log comes with accounts. On this server, changes are written to the server's logs."))];
  if (isViewer()) return [title, h("div", { class: "state" }, h("div", null, `${VIEWER} The audit log is for admins.`))];
  const pick = h("select", { "aria-label": "Show one kind of change" }, h("option", { value: "" }, "Every action"));
  const csv = h("a", { class: "btn", href: "settings/audit?format=csv", download: "" }, "Download CSV");
  const list = h("div", null, h("p", { class: "empty" }, "Loading the log..."));
  let actions = null;

  async function load() {
    const action = pick.value;
    csv.href = `settings/audit?format=csv${action ? `&action=${encodeURIComponent(action)}` : ""}`;
    const r = await call(`settings/audit?limit=500${action ? `&action=${encodeURIComponent(action)}` : ""}`);
    if (!r.ok) { list.replaceChildren(h("p", { class: "empty" }, why(r, "The log could not be loaded."))); return; }
    if (!actions) {
      actions = r.actions || [];
      pick.append(...actions.map((a) => h("option", { value: a }, a)));
    }
    const rows = r.entries || [];
    if (!rows.length) { list.replaceChildren(h("p", { class: "empty" }, "Nothing logged yet.")); return; }
    list.replaceChildren(
      r.all_orgs ? h("p", { class: "note" }, "As an install admin you see every organisation's rows.") : "",
      h("div", { class: "scroll" }, h("table", null, h("caption", { class: "vh" }, "Audit log"),
        h("thead", null, h("tr", null, ["When", "Who", "Action", "What", "Detail"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", null, rows.map((e) => h("tr", null, h("td", { class: "muted" }, when(e.at, "")), h("td", null, e.actor_email || e.actor),
          h("td", null, e.action), h("td", { class: "path nm" }, e.target || ""), h("td", { class: "muted" }, e.detail || "")))))),
      h("p", { class: "note" }, `${rows.length} row${rows.length === 1 ? "" : "s"}, newest first${rows.length >= 500 ? "; the CSV has more" : ""}.`));
  }
  pick.addEventListener("change", load);
  load();
  return [title, h("section", { class: "s" }, h("div", { class: "af-row" }, field("Action", pick), csv), list)];
}
