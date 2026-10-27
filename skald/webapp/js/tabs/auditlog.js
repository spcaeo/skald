// Settings > Audit log (accounts, access.mode: sessions): who changed what,
// and when - settings, the team, tokens, sign-ins that failed - newest first,
// filtered by action, and as a CSV file. For admins; install admins see every
// organisation's rows. GET <page>/settings/audit (settings_api.py).
//
// v2: one row per change (who, the action as a pill, what, when, the detail), the first 50
// then Show all; Download CSV is the page's one primary.

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions, VIEWER } from "../access.js";
import { head1, field, when, why, showFirst } from "./forms.js";
import { copyIf } from "../urlactions.js";
import { primary, statusRow } from "./set-ui.js";

const csvFor = (action) => `settings/audit?format=csv${action ? `&action=${encodeURIComponent(action)}` : ""}`;

function entry(e) {
  const what = e.target ? copyIf("text", e.target, null, { label: "target", cls: "" }) : null;
  const detail = e.detail ? copyIf("text", e.detail, null, { label: "detail", cls: "" }) : null;
  return statusRow({ iconName: "person", title: copyIf("text", e.actor_email || e.actor || "unknown", null, { label: "who", cls: "" }),
    line: [what, what ? " · " : "", when(e.at, ""), detail ? " · " : "", detail], kind: "info", word: e.action || "" });
}

export default function auditlog(m, s = {}) {
  const title = head1("Audit log", "Who changed what, and when.");
  if (!sessions()) return [title, h("div", { class: "state" }, h("div", null, "The audit log comes with accounts. On this server, changes are written to the server's logs."))];
  if (isViewer()) return [title, h("div", { class: "state" }, h("div", null, `${VIEWER} The audit log is for admins.`))];
  const pick = h("select", { "aria-label": "Show one kind of change" }, h("option", { value: "" }, "Every action"));
  let href = csvFor("");
  const csv = primary("Download CSV", () => {
    const a = h("a", { href, download: "" });
    document.body.append(a);
    a.click();
    a.remove();
  }, { iconName: "out" });
  const list = h("div", null, h("p", { class: "empty" }, "Loading the log..."));
  let actions = null;

  // The action shown is in the address (aact=), so a link opens the same list.
  const want = String(s.aact || "");
  async function load() {
    const action = want;
    href = csvFor(action);
    csv.dataset.href = href;
    const r = await call(`settings/audit?limit=500${action ? `&action=${encodeURIComponent(action)}` : ""}`);
    if (!r.ok) { list.replaceChildren(h("p", { class: "empty" }, why(r, "The log could not be loaded."))); return; }
    if (!actions) {
      actions = r.actions || [];
      pick.append(...actions.map((a) => h("option", { value: a, selected: a === want || null }, a)));
      pick.value = want;
    }
    const rows = (r.entries || []).map(entry);
    if (!rows.length) { list.replaceChildren(h("p", { class: "empty" }, "Nothing logged yet.")); return; }
    list.replaceChildren(
      r.all_orgs ? h("p", { class: "note" }, "As an install admin you see every organisation's rows.") : "",
      h("section", { class: "ui-card set-rows aud-rows" }, h("div", { class: "ui-card-h" }, h("h2", null, "Changes")), h("div", { class: "set-list" }, rows), showFirst(rows, 50)),
      h("p", { class: "note" }, `${rows.length} row${rows.length === 1 ? "" : "s"}, newest first${rows.length >= 500 ? "; the CSV has more" : ""}.`));
  }
  pick.addEventListener("change", () => S.set({ aact: pick.value }));
  load();
  return [title, csv, h("div", { class: "af-row aud-bar" }, field("Action", pick)), list];
}
