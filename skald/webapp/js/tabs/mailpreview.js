// Settings > Mail & reports > Preview (2.13): the daily or the weekly mail as this site
// would send it now, drawn in a frame. GET settings/mail-preview?kind= builds it
// with the real mail code from the verified history (mail_preview.py) and sends
// nothing. The frame is sandboxed with nothing allowed: the mail runs no script
// and cannot reach the page around it.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { status, why } from "./forms.js";

export function mailPreview() {
  const msg = status();
  const frame = h("iframe", { class: "mp-frame", title: "The mail as it would go", sandbox: "", referrerpolicy: "no-referrer", hidden: true });
  const subject = h("p", { class: "mp-subject", hidden: true });
  const show = async (kind, btn) => {
    btns.forEach((b) => { b.disabled = true; b.setAttribute("aria-pressed", String(b === btn)); });
    msg.textContent = "Building the mail…"; msg.className = "msg";
    const r = await call(`settings/mail-preview?kind=${kind}`);
    btns.forEach((b) => { b.disabled = false; });
    if (!r.ok) { msg.say(why(r, "The preview could not be built.")); frame.hidden = subject.hidden = true; return; }
    msg.say("");
    subject.replaceChildren(h("b", null, "Subject: "), r.subject);
    frame.srcdoc = r.html;   // srcdoc in a sandbox with no permissions: shown, never run
    frame.hidden = subject.hidden = false;
  };
  const btns = [["daily", "Preview the daily mail"], ["weekly", "Preview the weekly mail"]].map(([k, words]) => {
    const b = h("button", { type: "button", class: "btn", "aria-pressed": "false" }, words);
    b.addEventListener("click", () => show(k, b));
    return b;
  });
  return h("section", { class: "sheet acct-card" }, h("h2", null, "Preview the mail"),
    h("p", { class: "sub" }, "The daily or weekly mail exactly as this site would send it now, from the same verified days. Nothing is sent; no mail server is needed."),
    h("div", { class: "mp-row" }, btns), msg, subject, frame);
}
