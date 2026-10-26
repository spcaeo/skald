// Settings > Team (accounts, access.mode: sessions): who belongs to this
// organisation, with which role, and the invites still open. An admin changes
// roles, removes members and sends, resends or cancels invites; a viewer sees
// the same lists with every control disabled. The helper behind <page>/team
// checks the session, the role and the CSRF value; every change is audited.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, isViewer, lockForViewer, sessions, VIEWER } from "../access.js";
import { head1, copyable, field, input, status, confirmIn, when, why, ROLE_NAME } from "./forms.js";
import { copyIf } from "../urlactions.js";

const NO_MAIL = "Mail is not set up; send this link yourself.";

// The roles this reader may hand out: only an owner makes another owner.
const roles = (current) => ["viewer", "admin", ...(ME.role === "owner" || current === "owner" ? ["owner"] : [])];

function roleSelect(value, label, onPick) {
  const sel = h("select", { "aria-label": label }, roles(value).map((r) => h("option", { value: r, selected: r === value }, ROLE_NAME[r])));
  sel.addEventListener("change", () => onPick(sel));
  return sel;
}

// The link to pass on by hand, when the server cannot mail it. It stays on screen
// (in this page's memory only) across a redraw of the tab, until put away.
let shownLink = null;
function linkNote(slot) {
  if (!shownLink) { slot.replaceChildren(); return; }
  const { link, who } = shownLink;
  const done = h("button", { type: "button", class: "btn" }, "Done");
  done.addEventListener("click", () => { shownLink = null; slot.replaceChildren(); });
  slot.replaceChildren(h("div", { class: "state ok acct-link", role: "status" },
    h("div", null, h("p", null, h("strong", null, NO_MAIL), ` It is for ${who} and works once.`), copyable(link, "the invite link"), h("div", { class: "acts" }, done))));
}

export default function team() {
  // 2.38.0: the organisation in the title, since a person in two sees a different team per site.
  const title = head1(ME.org ? `Team of ${ME.org}` : "Team", ME.org ? `Who may see ${ME.org}'s sites, and what they may change.` : "Who may see these sites, and what they may change.");
  if (!sessions()) {
    return [title, h("div", { class: "state" }, h("div", null, "Team comes with accounts. This server uses one shared login; users are listed under ",
      h("a", { href: "#settings/org/users" }, "Settings › Users"), "."))];
  }
  const box = h("div", { class: "acct" }, h("p", { class: "empty" }, "Loading the team..."));
  const msg = status();
  const linkSlot = h("div");
  const reload = () => call("team").then(draw);

  function draw(r) {
    if (!r.ok) {
      box.replaceChildren(h("div", { class: "state" }, h("div", null, isViewer() ? `${VIEWER} The team list is for admins.` : why(r, "The team could not be loaded."))));
      return;
    }
    box.replaceChildren(...[scope(r.sites || [], r.others || []), members(r.members || []), invites(r.invites || []), inviteForm()].filter(Boolean));
    lockForViewer(box);
  }

  // Which sites this team sees, and the reader's other organisations: each opens its own team.
  function scope(sites, others) {
    if (!sites.length && !others.length) return null;
    const seen = sites.length === 1 ? ["These people see ", h("b", null, sites[0]), " only."]
      : sites.length ? [`These people see these ${sites.length} sites: `, sites.join(", "), "."] : [];
    const also = others.length ? h("p", { class: "sub" }, "You are also in ", others.flatMap((o, i) => [i ? ", " : "",
      h("a", { href: `../${o.path}#settings/org/team` }, `${o.org} (${o.sites} site${o.sites === 1 ? "" : "s"})`)]),
      ". Each organisation has its own team.") : null;
    return h("section", { class: "s team-scope" }, seen.length ? h("p", null, ...seen) : null, also);
  }

  function members(list) {
    if (!list.length) return h("section", { class: "s" }, h("h2", null, "Members"), h("p", { class: "empty" }, "No members yet."));
    const rows = list.map((m) => {
      const me = m.email === ME.user;
      const sel = roleSelect(m.role, `Role of ${m.email}`, async (s) => {
        s.disabled = true;
        const r = await call("team/role", { email: m.email, role: s.value });
        s.disabled = false;
        if (r.ok) { msg.say(`${m.email} is now ${ROLE_NAME[s.value] || s.value}.`, true); m.role = s.value; } else { msg.say(why(r)); s.value = m.role; }
      });
      if (me) { sel.disabled = true; sel.title = "You cannot change your own role."; }
      const cell = h("td", { class: "n" });
      const drawCell = () => {
        const rm = h("button", { type: "button", class: "btn danger", "aria-label": `Remove ${m.email}`, disabled: me, title: me ? "You cannot remove yourself." : null }, "Remove");
        rm.addEventListener("click", () => confirmIn(cell, `Remove ${m.email}? Their sessions end at once.`, "Yes, remove", async () => {
          const r = await call("team/remove", { email: m.email });
          if (r.ok) { msg.say(`Removed ${m.email}.`, true); reload(); } else { msg.say(why(r)); drawCell(); }
        }, drawCell));
        cell.replaceChildren(rm);
        if (isViewer()) lockForViewer(cell);
      };
      drawCell();
      const on = m.totp_on ?? m.two_step;
      return h("tr", null, h("td", { class: "path nm" }, copyIf("email", m.email || "", m.email, { label: "email", cls: "" }), me ? h("span", { class: "you" }, " (you)") : null), h("td", null, copyIf("text", m.name || "", null, { label: "name", cls: "" })),
        h("td", null, sel), h("td", { class: "muted n" }, when(m.last_seen ?? m.last_sign_in)),
        h("td", { class: "c" }, on == null ? h("span", { class: "muted" }, "not known") : h("span", { class: `tf ${on ? "on" : "off"}` }, on ? "On" : "Off")), cell);
    });
    return h("section", { class: "s" }, h("h2", null, "Members"), h("p", { class: "sub" }, `${list.length} member${list.length === 1 ? "" : "s"}. Removing a member ends their sessions for this organisation at once.`),
      h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Members"),
        h("thead", null, h("tr", null, [["Email"], ["Name"], ["Role"], ["Last seen", "n"], ["Two-step sign-in", "c"]].map(([t, cls]) => h("th", { scope: "col", class: cls }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))),
        h("tbody", null, rows))));
  }

  function invites(list) {
    const body = !list.length ? h("p", { class: "empty" }, "No invites waiting.") : h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Pending invites"),
      h("thead", null, h("tr", null, [["Email"], ["Role"], ["Invited by"], ["Expires", "n"]].map(([t, cls]) => h("th", { scope: "col", class: cls }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Actions")))),
      h("tbody", null, list.map((v) => {
        const cell = h("td", { class: "n" });
        const drawCell = () => {
          const resend = h("button", { type: "button", class: "btn", "aria-label": `Resend the invite to ${v.email}` }, "Resend");
          const cancel = h("button", { type: "button", class: "btn danger", "aria-label": `Cancel the invite to ${v.email}` }, "Cancel");
          resend.addEventListener("click", async () => {
            resend.disabled = true;
            const r = await call("team/resend", { email: v.email });
            resend.disabled = false;
            if (!r.ok) { msg.say(why(r)); return; }
            if (r.link) { shownLink = { link: r.link, who: v.email }; linkNote(linkSlot); msg.say(""); } else msg.say(`Sent the invite to ${v.email} again.`, true);
          });
          cancel.addEventListener("click", () => confirmIn(cell, `Cancel the invite to ${v.email}?`, "Yes, cancel it", async () => {
            const r = await call("team/cancel", { email: v.email });
            if (r.ok) { msg.say(`Cancelled the invite to ${v.email}.`, true); reload(); } else { msg.say(why(r)); drawCell(); }
          }, drawCell));
          cell.replaceChildren(h("span", { class: "acts" }, resend, cancel));
          if (isViewer()) lockForViewer(cell);
        };
        drawCell();
        return h("tr", null, h("td", { class: "path nm" }, copyIf("email", v.email || "", v.email, { label: "email", cls: "" })), h("td", null, ROLE_NAME[v.role] || v.role || ""),
          h("td", { class: "muted" }, copyIf("text", v.invited_by || "", null, { label: "invited by", cls: "" })), h("td", { class: "muted n" }, when(v.expires_at, "")), cell);
      }))));
    return h("section", { class: "s" }, h("h2", null, "Pending invites"), h("p", { class: "sub" }, "An invite link works for 7 days, once."), body);
  }

  function inviteForm() {
    const email = input({ type: "email", name: "email", autocomplete: "off", required: true, placeholder: "name@example.com", maxlength: "254" });
    const role = h("select", { name: "role" }, roles("viewer").map((r) => h("option", { value: r }, ROLE_NAME[r])));
    const send = h("button", { type: "submit", class: "btn primary" }, "Send invite");
    const form = h("form", { class: "af-row", novalidate: true }, field("Email", email), field("Role", role), send);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const addr = email.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(addr)) { msg.say("Type a whole email address, like name@example.com."); email.focus(); return; }
      send.disabled = true;
      const r = await call("team/invite", { email: addr, role: role.value });
      send.disabled = false;
      if (!r.ok) { msg.say(why(r)); return; }
      email.value = "";
      shownLink = r.link ? { link: r.link, who: addr } : null;
      linkNote(linkSlot);
      msg.say(r.link ? `Invite made for ${addr}.` : `Invite sent to ${addr}.`, true);
      reload();
    });
    return h("section", { class: "s" }, h("h2", null, "Invite someone"),
      h("p", { class: "sub" }, "They get a mail with a link to pick a name and a password, or to join with the account they already have."),
      h("div", { class: "sheet" }, form),
      h("dl", { class: "u-roles" },
        h("dt", null, "Viewer"), h("dd", null, "sees everything these pages show, changes nothing"),
        h("dt", null, "Admin"), h("dd", null, "also changes settings, the team and tokens (saved funnels and internal addresses apply to every site: install admins only)"),
        h("dt", null, "Owner"), h("dd", null, "everything; an organisation always keeps at least one")));
  }

  linkNote(linkSlot);
  reload();
  return [title, box, linkSlot, msg];
}
