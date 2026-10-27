// One organisation's Members and Pending invites tabs (org-drawer.js; the helper:
// skald/orgs_api.py, orgs/member/* and orgs/invite/*). A member is named by their id
// in every request, never by their email in an address.
//
//   Members   each member's role and the sites they see (every site, or some: Change), Remove;
//             Invite someone (with the sites they will see); Transfer ownership; Leave
//   Invites   each open invite: Resend or Cancel
//
// The server keeps the rules (accounts/users.py): only an owner makes or removes an owner, an
// organisation always keeps one owner, and an owner always sees every site.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { field, input, status, why, when, copyable } from "./forms.js";
import { copyIf } from "../urlactions.js";
import { tip } from "./settings-frame.js";
import { ROLE_WORD, accessWords } from "./org-words.js";

const NO_MAIL = "Mail is not set up: pass this link on yourself. It works once, for 7 days.";

/* The roles this reader may give: an owner's only by an owner. */
const rolesFor = (may, current) => ["viewer", "admin", ...(may.owners || current === "owner" ? ["owner"] : [])];

/* Ticks for "which sites": Every site, or some of the organisation's. -> {el, value()}:
   null for every site, else the names ticked. */
function sitePicker(all, chosen, label) {
  const every = h("input", { type: "checkbox", name: "every", checked: chosen == null });
  const boxes = all.map((s) => h("input", { type: "checkbox", name: "site", value: s, checked: chosen == null || chosen.includes(s), disabled: chosen == null }));
  every.checked = chosen == null;
  boxes.forEach((b, i) => { b.checked = chosen == null || chosen.includes(all[i]); b.disabled = chosen == null; });
  every.addEventListener("change", () => boxes.forEach((b) => { b.disabled = every.checked; if (every.checked) b.checked = true; }));
  const el = h("fieldset", { class: "org-set org-sites-pick" }, h("legend", null, label),
    h("label", { class: "org-check" }, every, h("span", null, h("b", null, "Every site"), h("small", { class: "muted" }, "Sites added later too."))),
    ...all.map((s, i) => h("label", { class: "org-site-pick" }, boxes[i], ` ${s}`)));
  return { el, value: () => (every.checked ? null : boxes.filter((b) => b.checked).map((b) => b.getAttribute("value"))) };
}

export function members(st) {
  const { members: list = [], may = {}, org } = st.r;
  const all = org.sites || [];
  const msg = status();
  const linkSlot = h("div");
  const roleTip = tip("each role", h("dl", { class: "u-roles" },
    h("dt", null, "Viewer"), h("dd", null, "sees the sites they may see, changes nothing"),
    h("dt", null, "Admin"), h("dd", null, "also changes settings, members and keys"),
    h("dt", null, "Owner"), h("dd", null, "everything, on every site; an organisation always keeps one")),
  h("p", null, "Each admin or viewer sees every site, or only the sites you choose: the dashboard, the API, MCP and the mails all follow it."));
  const rows = list.map((m) => row(st, m, all, msg));
  const out = [h("section", { class: "s" }, h("h2", { class: "has-tip" }, `Members (${list.length})`, roleTip.btn),
    list.length ? h("div", { class: "scroll" }, h("table", { class: "rows-mid org-members" }, h("caption", { class: "vh" }, "Members"),
      h("thead", null, h("tr", null, [["Email"], ["Name"], ["Role"], ["Sites"], ["Last seen", "n"], ["Two-step", "c"]].map(([t, c]) => h("th", { scope: "col", class: c }, t)),
        h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))), h("tbody", null, rows))) : h("p", { class: "empty" }, "No members yet."), msg)];
  if (may.members) out.push(inviteForm(st, all, linkSlot), linkSlot);
  const yours = owners(st, list, msg);
  if (yours) out.push(yours);
  return out;
}

function row(st, m, all, msg) {
  const { may = {} } = st.r;
  const id = Number(st.id);
  const sel = h("select", { "aria-label": `Role of ${m.email}`, disabled: !may.members || m.me }, rolesFor(may, m.role).map((r) => h("option", { value: r, selected: r === m.role }, ROLE_WORD[r])));
  if (m.me) sel.title = "Your own role is changed by another owner.";
  sel.addEventListener("change", async () => {
    sel.disabled = true;
    const r = await call("orgs/member/role", { org: id, user: m.id, role: sel.value });
    sel.disabled = false;
    if (!r.ok) { msg.say(why(r)); sel.value = m.role; return; }
    msg.say(`${m.email} is now ${ROLE_WORD[sel.value]}.`, true);
    st.refresh();
  });
  // The sites they see: words, and Change for an admin (never an owner's: every site).
  const sitesCell = h("td", { class: "org-access" });
  const drawSites = () => {
    const words = h("span", null, accessWords(m.sites, m.role));
    const canChange = may.sites_access && m.role !== "owner" && !m.me && all.length > 1;
    if (!canChange) { sitesCell.replaceChildren(words); return; }
    const b = h("button", { type: "button", class: "linkish", "aria-label": `Change the sites ${m.email} sees` }, "Change");
    b.addEventListener("click", () => {
      const pick = sitePicker(all, m.sites, `Sites ${m.email} sees`);
      const save = h("button", { type: "button", class: "btn" }, "Save");
      const back = h("button", { type: "button", class: "btn" }, "Cancel");
      sitesCell.replaceChildren(pick.el, h("div", { class: "acts" }, back, save));
      back.addEventListener("click", drawSites);
      save.addEventListener("click", async () => {
        const sites = pick.value();
        if (sites && !sites.length) { msg.say("Tick at least one site, or Every site."); return; }
        const r = await call("orgs/member/sites", { org: id, user: m.id, sites });
        if (!r.ok) { msg.say(why(r)); return; }
        m.sites = r.sites;
        msg.say(`${m.email} now sees ${accessWords(r.sites, m.role).toLowerCase()}.`, true);
        drawSites();
      });
    });
    sitesCell.replaceChildren(words, " ", b);
  };
  drawSites();
  // Remove, asking first (yourself: Leave, below).
  const cell = h("td", { class: "n" });
  const idle = () => {
    if (!may.members || m.me) { cell.replaceChildren(); return; }
    const rm = h("button", { type: "button", class: "btn danger", "aria-label": `Remove ${m.email}` }, "Remove");
    rm.addEventListener("click", () => {
      const yes = h("button", { type: "button", class: "btn danger" }, "Yes, remove");
      const no = h("button", { type: "button", class: "btn" }, "Keep them");
      cell.replaceChildren(h("span", { class: "confirm" }, `Remove ${m.email}? Their sessions end at once.`, yes, no));
      no.addEventListener("click", idle);
      yes.addEventListener("click", async () => {
        yes.disabled = no.disabled = true;
        const r = await call("orgs/member/remove", { org: id, user: m.id });
        if (!r.ok) { msg.say(why(r)); idle(); return; }
        msg.say(`Removed ${m.email}.`, true);
        st.refresh();
      });
    });
    cell.replaceChildren(rm);
  };
  idle();
  const on = m.totp_on;
  return h("tr", null,
    h("td", { class: "path nm" }, copyIf("email", m.email || "", m.email, { label: "email", cls: "" }), m.me ? h("span", { class: "you" }, " (you)") : null,
      m.disabled_at ? h("small", { class: "muted" }, " (switched off)") : null),
    h("td", null, m.name ? copyIf("text", m.name, null, { label: "name", cls: "" }) : ""), h("td", null, sel), sitesCell,
    h("td", { class: "muted n" }, when(m.last_seen)),
    h("td", { class: "c" }, on == null ? h("span", { class: "muted" }, "not known") : h("span", { class: `tf ${on ? "on" : "off"}` }, on ? "On" : "Off")), cell);
}

function inviteForm(st, all, linkSlot) {
  const { may = {} } = st.r;
  const msg = status();
  const email = input({ type: "email", name: "email", autocomplete: "off", placeholder: "name@example.com" });
  const role = h("select", { name: "role" }, rolesFor(may, "").map((r) => h("option", { value: r, selected: r === "viewer" }, ROLE_WORD[r])));
  const pick = all.length > 1 ? sitePicker(all, null, "Sites they will see") : null;
  const go = h("button", { type: "submit", class: "btn" }, "Invite");
  const form = h("form", { class: "org-form org-invite", novalidate: true }, h("div", { class: "org-row" }, field("Email", email), field("Role", role)),
    pick ? pick.el : null, h("div", { class: "acts" }, go), msg);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const to = email.value.trim();
    if (!to) { msg.say("Type their email."); return; }
    const sites = role.value === "owner" || !pick ? null : pick.value();
    if (sites && !sites.length) { msg.say("Tick at least one site, or Every site."); return; }
    go.disabled = true;
    const r = await call("orgs/member/invite", { org: Number(st.id), email: to, role: role.value, sites });
    go.disabled = false;
    if (!r.ok) { msg.say(why(r)); return; }
    email.value = "";
    msg.say(r.mailed ? `Invite sent to ${to}.` : r.warning || `Invite made for ${to}.`, true);
    linkSlot.replaceChildren(r.link ? h("div", { class: "state ok", role: "status" }, h("div", null, h("p", null, h("strong", null, NO_MAIL), ` It is for ${to}.`), copyable(r.link, "the invite link"))) : "");
    const fresh = await call(`orgs/show?org=${encodeURIComponent(st.id)}`);
    if (fresh.ok) st.r.invites = fresh.invites;
  });
  return h("section", { class: "s" }, h("h2", null, "Invite someone"), form);
}

/* Transfer ownership (an owner) and Leave (a member), each asking first. */
function owners(st, list, msg) {
  const { may = {}, org } = st.r;
  const id = Number(st.id);
  const parts = [];
  if (may.transfer) {
    const others = list.filter((m) => !m.me && !m.disabled_at);
    if (others.length) {
      const sel = h("select", { "aria-label": "The new owner" }, others.map((m) => h("option", { value: String(m.id) }, m.email)));
      const go = h("button", { type: "button", class: "btn" }, "Transfer ownership");
      const cell = h("div", { class: "acts" }, sel, go);
      go.addEventListener("click", () => {
        const who = others.find((m) => String(m.id) === sel.value);
        const yes = h("button", { type: "button", class: "btn primary" }, "Yes, transfer");
        const no = h("button", { type: "button", class: "btn" }, "Keep it");
        cell.replaceChildren(h("span", { class: "confirm" }, `Make ${who.email} an owner of ${org.name}? You become an admin.`, yes, no));
        no.addEventListener("click", () => cell.replaceChildren(sel, go));
        yes.addEventListener("click", async () => {
          yes.disabled = no.disabled = true;
          const r = await call("orgs/transfer", { org: id, user: who.id });
          if (!r.ok) { msg.say(why(r)); cell.replaceChildren(sel, go); return; }
          msg.say(`${who.email} is now an owner; you are an admin.`, true);
          st.refresh();
        });
      });
      parts.push(h("div", null, h("b", null, "Transfer ownership"), h("p", { class: "muted" }, "Hand the organisation to another member. You stay, as an admin."), cell));
    }
  }
  if (may.leave) {
    const go = h("button", { type: "button", class: "btn danger" }, "Leave this organisation");
    const cell = h("div", { class: "acts" }, go);
    go.addEventListener("click", () => {
      const yes = h("button", { type: "button", class: "btn danger" }, "Yes, leave");
      const no = h("button", { type: "button", class: "btn" }, "Stay");
      cell.replaceChildren(h("span", { class: "confirm" }, `Leave ${org.name}? You stop seeing its sites at once.`, yes, no));
      no.addEventListener("click", () => cell.replaceChildren(go));
      yes.addEventListener("click", async () => {
        yes.disabled = no.disabled = true;
        const r = await call("orgs/leave", { org: id });
        if (!r.ok) { msg.say(why(r)); cell.replaceChildren(go); return; }
        st.d.close();
        location.assign("../");
      });
    });
    parts.push(h("div", null, h("b", null, "Leave"), h("p", { class: "muted" }, "The last owner cannot leave: transfer ownership first."), cell));
  }
  return parts.length ? h("section", { class: "s org-own" }, h("h2", null, "Ownership"), ...parts) : null;
}

export function invites(st) {
  const list = st.r.invites || [];
  const msg = status();
  const by = Object.fromEntries((st.r.members || []).map((m) => [String(m.id), m.email]));
  if (!list.length) return h("section", { class: "s" }, h("h2", null, "Pending invites"), h("p", { class: "empty" }, "No invite is waiting."));
  const rows = list.map((v) => {
    const cell = h("td", { class: "n" });
    const idle = () => {
      const resend = h("button", { type: "button", class: "btn", "aria-label": `Resend the invite to ${v.email}` }, "Resend");
      const cancel = h("button", { type: "button", class: "btn danger", "aria-label": `Cancel the invite to ${v.email}` }, "Cancel");
      resend.addEventListener("click", async () => {
        resend.disabled = true;
        const r = await call("orgs/invite/resend", { org: Number(st.id), email: v.email });
        resend.disabled = false;
        if (!r.ok) { msg.say(why(r)); return; }
        msg.say(r.mailed ? `Sent again to ${v.email}.` : `A new link for ${v.email}.`, true);
        if (r.link) cell.replaceChildren(copyable(r.link, "the invite link"));
      });
      cancel.addEventListener("click", () => {
        const yes = h("button", { type: "button", class: "btn danger" }, "Yes, cancel it");
        const no = h("button", { type: "button", class: "btn" }, "Keep it");
        cell.replaceChildren(h("span", { class: "confirm" }, "Its link stops working.", yes, no));
        no.addEventListener("click", idle);
        yes.addEventListener("click", async () => {
          const r = await call("orgs/invite/cancel", { org: Number(st.id), email: v.email });
          if (!r.ok) { msg.say(why(r)); idle(); return; }
          st.r.invites = list.filter((x) => x !== v);
          msg.say(`The invite to ${v.email} is cancelled.`, true);
          st.refresh(false);
        });
      });
      cell.replaceChildren(resend, cancel);
    };
    idle();
    return h("tr", null, h("td", { class: "path nm" }, copyIf("email", v.email, v.email, { label: "email", cls: "" })),
      h("td", null, ROLE_WORD[v.role] || v.role), h("td", null, accessWords(v.sites, v.role)),
      h("td", null, by[String(v.invited_by)] || String(v.invited_by || "")),
      h("td", { class: "muted n" }, v.expired ? "Expired" : String(v.expires_at || "").slice(0, 10)), cell);
  });
  return h("section", { class: "s" }, h("h2", null, `Pending invites (${list.length})`),
    h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Pending invites"),
      h("thead", null, h("tr", null, [["Email"], ["Role"], ["Sites"], ["Invited by"], ["Expires", "n"]].map(([t, c]) => h("th", { scope: "col", class: c }, t)),
        h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Actions")))), h("tbody", null, rows))), msg);
}
