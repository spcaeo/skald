// Add a site's two first questions (2.43; the owner: "the organisation and the people are
// chosen when the site is added, so the line does everything on its own"):
//
//   Organisation     This organisation (<name>) · Another of mine (a list) · A new one (a name,
//                    and "Their data: Internal, keep everything" or "A client: their own
//                    privacy settings apply")
//   Who will use it  this organisation's members (ticked, and already in, when the site stays
//                    here), new addresses each viewer or admin (owner only for a new
//                    organisation), or No one else; then "Sees: this site only / every site"
//                    (their site access: this site only by default, every site in a new
//                    organisation)
//
// In the address: org=same|<id>|new, ppl=<user id>.<user id> (members ticked for another
// organisation) and sees=site|all (when chosen). Settings › Organisations' Add a site opens it
// with org=<id>: one of the person's other organisations is "Another of mine", chosen; this one
// is "This organisation". Never an email or a name: a typed address and a new organisation's name stay
// in this page until Next, then in the site's set-up row (setup_people.py). GET
// sites/whoopts answers the organisations and the members.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input } from "./forms.js";
import { withCopy } from "../urlactions.js";
import { ME } from "../access.js";
import { orgFrom, pplFrom, pplValue, addBody } from "./setup-live-words.js";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* The answers kept in the wizard's state, from the address. */
export function whoState(s = {}) {
  return { org: orgFrom(s.org), other: /^\d+$/.test(String(s.org || "")) ? String(s.org) : "", name: "", privacy: "internal",
    ticked: new Set(pplFrom(s.ppl)), emails: [], none: false, sees: seesFrom(s.sees), opts: null };
}
const seesFrom = (v) => (v === "site" || v === "all" ? v : "");
/* What the people see: as chosen, else this site only, or every site in a new organisation. */
export const seesOf = (o) => o.sees || (o.org === "new" ? "all" : "site");

/* What sites/add gets, and why Next is refused ("" when it is not). */
export function whoBody(o) {
  const choice = o.org === "other" ? o.other : o.org;
  const sees = seesOf(o);
  const people = o.none ? [] : [...(choice !== "same" ? [...o.ticked].map((id) => ({ user: id, role: "viewer" })) : []), ...o.emails]
    .map((p) => ({ ...p, sees }));
  return addBody({ org: choice, name: o.name, privacy: o.privacy, people });
}
export function whoCheck(o) {
  if (o.org === "new" && !String(o.name || "").trim()) return "Name the new organisation.";
  if (o.org === "other" && !o.other) return "Choose which of your organisations.";
  return "";
}

/* The two questions, for step 1 of a new site. keep(patch): writes the address. */
export function whoPart(o, keep, redraw) {
  const box = h("div", { class: "sw-org" });
  const draw = () => box.replaceChildren(...parts());
  if (!o.opts) {
    o.opts = { loading: true };
    call("sites/whoopts").then((r) => {
      o.opts = r.ok ? r : { orgs: [], members: [], org: { name: ME.org || "this organisation" }, may_make: false };
      if (o.org !== "same" && o.org !== "new" && o.org !== "other") {          // an id from the address
        if (o.opts.orgs.some((x) => String(x.id) === o.org)) { o.other = o.org; o.org = "other"; } else o.org = "same";
      }
      draw();
      if (redraw) redraw();
    });
  }
  const write = () => keep({ org: o.org === "other" ? o.other || "same" : o.org, ppl: o.org === "same" ? "" : pplValue([...o.ticked]), sees: o.sees });

  function radio(value, words, more = null) {
    const r = h("input", { type: "radio", name: "sw-org", value, checked: o.org === value || null });
    r.addEventListener("change", () => { o.org = value; write(); draw(); });
    return h("div", { class: "sw-org-o" }, h("label", null, r, ` ${words}`), o.org === value ? more : null);
  }

  function parts() {
    const opts = o.opts || {};
    if (opts.loading) return [h("p", { class: "empty" }, "Loading your organisations...")];
    const here = opts.org?.name || ME.org || "this organisation";
    const others = opts.orgs || [];
    const pick = h("select", { "aria-label": "Which of your organisations" }, h("option", { value: "" }, "Choose one"),
      others.map((x) => h("option", { value: String(x.id), selected: String(x.id) === o.other || null }, `${x.name} (${x.sites} site${x.sites === 1 ? "" : "s"})`)));
    pick.addEventListener("change", () => { o.other = pick.value; write(); });
    const name = input({ name: "org-name", maxlength: "100", placeholder: "Their company's name", "aria-label": "The new organisation's name" });
    name.value = o.name;
    name.addEventListener("input", () => { o.name = name.value; });
    const data = ["internal", "client"].map((v) => {
      const r = h("input", { type: "radio", name: "sw-privacy", value: v, checked: o.privacy === v || null });
      r.addEventListener("change", () => { o.privacy = v; });
      return h("label", null, r, v === "internal" ? " Internal, keep everything" : " A client: their own privacy settings apply");
    });
    const orgQ = h("fieldset", { class: "sw-q" }, h("legend", null, "Organisation"),
      radio("same", `This organisation (${here})`),
      others.length ? radio("other", "Another of mine", pick) : null,
      opts.may_make !== false ? radio("new", "A new one", h("div", { class: "sw-org-new" }, name,
        h("div", { class: "sw-org-data", role: "group", "aria-label": "Their data" }, h("span", null, "Their data:"), data))) : null);
    return [orgQ, peopleQ(opts)];
  }

  function peopleQ(opts) {
    const same = o.org === "same";
    const roles = ["viewer", "admin", ...(o.org === "new" ? ["owner"] : [])];
    const members = (opts.members || []).filter((m) => String(m.id) !== String(ME.user_id ?? "") && m.email !== ME.user);
    const rows = members.map((m) => {
      const tick = h("input", { type: "checkbox", checked: (same && !m.limited) || o.ticked.has(m.id) || null, disabled: same || o.none || null });
      tick.addEventListener("change", () => { if (tick.checked) o.ticked.add(m.id); else o.ticked.delete(m.id); write(); draw(); });
      return h("li", null, h("label", null, tick, ` ${m.name || m.email} `), withCopy(h("small", null, m.email), m.email, { label: "the address" }), " ", h("small", { class: "muted" }, same && m.limited ? `${m.role}, some sites only` : m.role));
    });
    const limited = same && members.some((m) => m.limited);
    const email = input({ name: "invite-email", type: "email", autocomplete: "off", placeholder: "name@example.com", "aria-label": "A new person's email" });
    const role = h("select", { "aria-label": "Their role" }, roles.map((r) => h("option", { value: r }, r)));
    const add = h("button", { type: "button", class: "btn" }, "Add");
    const said = h("small", { class: "msg", role: "status" });
    add.addEventListener("click", () => {
      const v = email.value.trim().toLowerCase();
      if (!EMAIL.test(v)) { said.textContent = "Type an email, like name@example.com."; return; }
      if (!o.emails.some((x) => x.email === v)) o.emails.push({ email: v, role: role.value });
      o.none = false;
      draw();
    });
    const added = o.emails.map((x, i) => {
      const rm = h("button", { type: "button", class: "btn link", "aria-label": `Take ${x.email} off` }, "Take off");
      rm.addEventListener("click", () => { o.emails.splice(i, 1); draw(); });
      return h("li", null, withCopy(h("span", null, x.email), x.email, { label: "the address" }), " ", h("small", { class: "muted" }, x.role), " ", rm);
    });
    const none = h("input", { type: "checkbox", checked: o.none || null });
    none.addEventListener("change", () => { o.none = none.checked; if (o.none) { o.emails = []; o.ticked.clear(); write(); } draw(); });
    return h("fieldset", { class: "sw-q" }, h("legend", null, "Who will use it"),
      rows.length ? h("ul", { class: "sw-people" }, rows) : null,
      same && rows.length ? h("small", { class: "note" }, limited ? "The rest see every site of this organisation already. Those on some sites only will not see this one: give it to them in Settings › Organisations."
        : "They see every site of this organisation already.") : null,
      h("ul", { class: "sw-people" }, added),
      h("div", { class: "sw-add" }, email, role, add, said),
      h("label", { class: "sw-none" }, none, " No one else"),
      seesLine(same),
      h("small", { class: "note" }, "Each gets an invite as soon as the first data arrives."));
  }

  /* One line, once someone will be invited: their site access in the organisation. */
  function seesLine(same) {
    if (o.none || !(o.emails.length || (!same && o.ticked.size))) return null;
    const now = seesOf(o);
    const pick = (v, words) => {
      const r = h("input", { type: "radio", name: "sw-sees", value: v, checked: now === v || null });
      r.addEventListener("change", () => { o.sees = v; write(); });
      return h("label", null, r, ` ${words}`);
    };
    return h("div", { class: "sw-sees", role: "group", "aria-label": "What they see" }, h("span", null, "Sees:"),
      pick("site", "this site only"), pick("all", "every site"));
  }

  draw();
  return box;
}
