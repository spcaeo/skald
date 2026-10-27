// "Share with your developer": a private link to one set-up task's steps for
// one site, which opens with no sign-in (share_api.py, share-page.js). Made
// and revoked by an admin (POST <page>/sites/share | sites/unshare; the list:
// GET sites/shares). The link is shown once, here. It can show its secret
// (a sending token, or a hook's secret) once: the secret is made only when
// the developer presses "Show the secret".

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why, when, confirmIn } from "./forms.js";
import { codeBlock } from "./conn-ui.js";
import { stepped } from "../overlays.js";
import { read } from "../state.js";
import { copyIf } from "../urlactions.js";
import { statusRow } from "./set-ui.js";

const TASK_WORDS = { send: "sending this site's visits", script: "the script tag", hook: "the lead hook", nextjs: "counting pages opened inside the site" };

// task: "send" (method server|cloudflare|vercel; docker|systemd before 2.30), "script", "nextjs", or "hook" (method: the tool).
// The form open is in the address as share=1 beside the dialog's key (js/overlays.js);
// the link it makes never is: it opens the steps with no sign-in.
export function shareBox(site, task, method = "") {
  const box = h("div", { class: "cn-share" });
  const open = h("button", { type: "button", class: "btn" }, "Share with your developer");
  const draw = () => box.replaceChildren(open);
  const mark = (on) => {
    const s = read();
    const fam = s.setup ? "setup" : s.conn ? "conn" : "";
    if (fam) stepped(fam, s[fam], { share: on ? "1" : "" });
  };
  open.addEventListener("click", () => {
    mark(true);
    const days = h("select", { name: "share-days", "aria-label": "The link works for" },
      [[1, "1 day"], [7, "7 days"], [30, "30 days"]].map(([v, t]) => h("option", { value: String(v), selected: v === 7 }, t)));
    days.value = "7";
    const make = h("button", { type: "button", class: "btn primary" }, "Make the link");
    const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
    make.addEventListener("click", async () => {
      make.disabled = true;
      const r = await call("sites/share", { site, task, method: method || undefined, days: Number(days.value) || 7 });
      make.disabled = false;
      if (!r.ok || !r.link) { said.textContent = why(r, "The link was not made."); said.className = "msg err"; return; }
      const revoke = h("button", { type: "button", class: "btn danger" }, "Revoke the link");
      const cell = h("span");
      const back = () => cell.replaceChildren(revoke);
      revoke.addEventListener("click", () => confirmIn(cell, "Revoke it? The page stops working at once.", "Yes, revoke", async () => {
        const res = await call("sites/unshare", { ref: r.ref });
        cell.replaceChildren(h("span", { class: res.ok ? "msg ok" : "msg err" }, res.ok ? "Revoked." : why(res)));
      }, back));
      back();
      const mail = `mailto:?subject=${encodeURIComponent(`Set-up steps for ${site}`)}&body=${encodeURIComponent(
        `Hello,\n\nThe steps for ${TASK_WORDS[task] || "the set-up"} of ${site}, with everything filled in and a Test button:\n${r.link}\n\nThe link works until ${r.expires_at}. It can show the secret once.\n`)}`;
      box.replaceChildren(h("div", { class: "state ok", role: "status" }, h("div", null,
        h("p", null, h("strong", null, "The link. "), "Copy it now: it is shown only here. It opens these steps for ", h("b", null, site), " with no sign-in, until ", when(r.expires_at, r.expires_at), "."),
        codeBlock(r.link, "the link for your developer"),
        h("p", { class: "note" }, task === "script" ? "The tag needs no secret." : task === "nextjs" ? "These steps need no secret." : "The page can show the secret once: it is made when your developer presses Show the secret. Send the link privately."),
        h("div", { class: "acts" }, h("a", { class: "btn", href: mail }, "Send it by mail"), cell))));
    });
    box.replaceChildren(h("div", { class: "cn-share-new" },
      h("p", null, `A private page with only these steps for ${site}, for someone without a sign-in. It works for:`),
      h("div", { class: "acts" }, days, make), said));
  });
  draw();
  // Opened from a link with share=1: the form, ready (the dialog draws this box afterwards).
  if (read().share === "1") queueMicrotask(() => { if (box.firstChild === open) open.click(); });
  return box;
}

// Settings > AI assistants > Tokens & links: the links made, one row each (what it is for, its
// site, when it ends, whether it was opened and its secret shown), with Revoke on the row.
export function sharesSection() {
  const list = h("div", { class: "set-list" }, h("p", { class: "empty" }, "Loading the links..."));
  const row = (s, reload) => {
    const cell = h("span", { class: "tok-act" });
    const drawCell = () => {
      const rv = h("button", { type: "button", class: "btn danger", "aria-label": `Revoke the link ${s.ref}` }, "Revoke");
      rv.addEventListener("click", () => confirmIn(cell, "Revoke this link? Its page stops working at once.", "Yes, revoke", async () => {
        const res = await call("sites/unshare", { ref: s.ref });
        if (res.ok) reload(); else drawCell();
      }, drawCell));
      cell.replaceChildren(rv);
    };
    drawCell();
    const what = TASK_WORDS[s.task] || s.task || "a set-up";
    const secret = s.task === "script" ? "" : s.revealed_at ? " · secret shown" : " · secret not shown";
    return statusRow({ iconName: "out", title: `${what[0].toUpperCase()}${what.slice(1)}${s.method ? ` (${s.method})` : ""}`,
      line: [copyIf("text", s.site || "", null, { label: "site", cls: "" }), " · ends ", when(s.expires_at), " · ", s.views ? `opened ${s.views} times, first ${when(s.viewed_at)}` : "not opened yet", secret],
      kind: s.views ? "info" : "off", word: s.views ? "Opened" : "Not opened", action: cell });
  };
  const reload = () => call("sites/shares").then((r) => {
    if (!r.ok) { list.replaceChildren(h("p", { class: "empty" }, why(r, "The links could not be loaded."))); return; }
    const live = (r.shares || []).filter((s) => s.state === "open" || s.state === "shown");
    if (!live.length) { list.replaceChildren(h("p", { class: "empty" }, "No links shared now.")); return; }
    list.replaceChildren(...live.map((s) => row(s, reload)));
  });
  reload();
  return h("section", { class: "ui-card set-rows tok-rows" }, h("div", { class: "ui-card-h" }, h("h2", null, "Shared links"),
    h("p", { class: "sub" }, "Pages made with Share with your developer. Each shows one task's steps for one site, with no sign-in, until it ends or you revoke it.")), list);
}
