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

const TASK_WORDS = { send: "sending this site's visits", script: "the script tag", hook: "the lead hook", nextjs: "counting pages opened inside the site" };

// task: "send" (method docker|systemd|cloudflare|vercel), "script", "nextjs", or "hook" (method: the tool).
export function shareBox(site, task, method = "") {
  const box = h("div", { class: "cn-share" });
  const open = h("button", { type: "button", class: "btn" }, "Share with your developer");
  const draw = () => box.replaceChildren(open);
  open.addEventListener("click", () => {
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
  return box;
}

// Settings > Connections: the links made, and Revoke.
export function sharesSection() {
  const list = h("div", null, h("p", { class: "empty" }, "Loading the links..."));
  const reload = () => call("sites/shares").then((r) => {
    if (!r.ok) { list.replaceChildren(h("p", { class: "empty" }, why(r, "The links could not be loaded."))); return; }
    const live = (r.shares || []).filter((s) => s.state === "open" || s.state === "shown");
    if (!live.length) { list.replaceChildren(h("p", { class: "empty" }, "No links shared now.")); return; }
    list.replaceChildren(h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Shared links"),
      h("thead", null, h("tr", null, ["For", "Site", "Ends", "Opened", "Secret"].map((t) => h("th", { scope: "col" }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))),
      h("tbody", null, live.map((s) => {
        const cell = h("td", { class: "n" });
        const drawCell = () => {
          const rv = h("button", { type: "button", class: "btn danger", "aria-label": `Revoke the link ${s.ref}` }, "Revoke");
          rv.addEventListener("click", () => confirmIn(cell, "Revoke this link? Its page stops working at once.", "Yes, revoke", async () => {
            const res = await call("sites/unshare", { ref: s.ref });
            if (res.ok) reload(); else drawCell();
          }, drawCell));
          cell.replaceChildren(rv);
        };
        drawCell();
        return h("tr", null, h("td", null, TASK_WORDS[s.task] || s.task, s.method ? ` (${s.method})` : ""), h("td", { class: "path nm" }, s.site),
          h("td", { class: "muted" }, when(s.expires_at)), h("td", { class: "muted" }, s.views ? `${s.views} times, first ${when(s.viewed_at)}` : "not yet"),
          h("td", { class: "muted" }, s.task === "script" ? "none" : s.revealed_at ? "shown" : "not shown"), cell);
      })))));
  });
  reload();
  return h("section", { class: "s" }, h("h2", null, "Shared links"),
    h("p", { class: "sub" }, "Pages made with Share with your developer. Each shows one task's steps for one site, with no sign-in, until it ends or you revoke it."), list);
}
