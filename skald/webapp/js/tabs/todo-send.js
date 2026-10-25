// "Send to team" (2.35): one to-do by mail to a member of the site's team, with its
// list as a CSV file attached and the link that opens it in Skald. The address holds
// tdsend=<to-do id> while the dialog is open (js/overlays.js); who it goes to never goes
// in the address. The mail goes through the install's own mail server (Settings > Mail),
// sent by the helper (skald/todo_api.py); the dialog is offered only when there is
// one and a team to send to (js/tabs/todo-marks.js sendable()).

import { h } from "../ui.js";
import { openDrawer } from "../drawer.js";
import { loadMarks, sendable, sendTodo } from "./todo-marks.js";
import { withCopy } from "../urlactions.js";

export const GONE = "That to-do is not on the list now, or it is not available to you.";

/* The address named a to-do to send: the dialog, or the plain line why not. */
export async function openSendKey(id, m) {
  const t = (m?.x?.todos?.todos || []).find((x) => x.id === id);
  if (!t) return GONE;
  await loadMarks();
  const can = sendable();
  if (!can.ok) return `Send to team is not offered here: ${can.why}`;
  return sendDialog(t, can.team);
}

export function sendDialog(t, team) {
  const pick = h("select", { class: "td-to", "aria-label": "Send to" },
    h("option", { value: "" }, "Pick a team member"),
    team.map((p) => h("option", { value: String(p.id) }, `${p.email} (${p.role})`)));
  const said = h("p", { class: "td-said", role: "status", "aria-live": "polite" });
  const sendBtn = h("button", { type: "button", class: "btn primary" }, "Send");
  const body = h("div", { class: "td-send" },
    h("label", { class: "td-field" }, h("span", null, "To"), pick),
    h("h3", null, "What they get"),
    h("div", { class: "td-preview" },
      h("p", null, h("b", null, t.title)),
      h("p", null, h("b", null, "Proof: "), t.proof),
      h("p", null, h("b", null, "Do: "), t.todo),
      h("p", null, h("b", null, "Skald will check: "), t.check)),
    h("p", { class: "note" }, "Attached: ", withCopy(h("code", null, t.file), t.file), `${t.rows_total > (t.rows || []).length ? ` (the first ${t.rows.length} of ${t.rows_total} rows)` : ""}. The link opens this to-do in Skald with its list. A teammate without rights to this site sees "not available to you"; the CSV works for anyone.`),
    said);
  const cancel = h("button", { type: "button", class: "btn" }, "Cancel");
  const d = openDrawer({ title: "Send to team", subtitle: t.title, size: "md", key: "todo-send", scope: "page", body, footer: [cancel, sendBtn],
    focus: pick, route: { key: "tdsend", value: t.id } });
  cancel.addEventListener("click", () => d.close());
  sendBtn.addEventListener("click", async () => {
    if (!pick.value) { said.textContent = "Pick who it goes to first."; return; }
    sendBtn.disabled = true;
    said.textContent = "Sending…";
    const r = await sendTodo(t.id, pick.value);
    sendBtn.disabled = false;
    said.replaceChildren(r.ok ? `Sent to ${r.sent_to}, with ${r.file || "the CSV"} attached.` : withCopy(r.error || "Not sent.", r.error || "Not sent."));
    said.classList.toggle("bad", !r.ok);
  });
  return d;
}
