// One organisation's drawer (Settings › Organisation › Organisations, org=<id>): its tabs,
// each in the address (otab=<tab>): Overview, Sites, Members, Pending invites, Settings, Keys
// and Audit. Archive and Restore in the footer, each asking first (the owner's rule: pause,
// never delete). Members and invites: org-members.js. The helper: skald/orgs_api.py
// (orgs/show?org=<id> and its POSTs); what this reader may do comes in its `may`.

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { pill } from "./set-ui.js";
import { field, input, status, why, when } from "./forms.js";
import { copyIf, withUrl } from "../urlactions.js";
import { openDrawer } from "../drawer.js";
import { stepped } from "../overlays.js";
import { ME } from "../access.js";
import { tabStrip } from "../tabstrip.js";
import { reload as reloadPage, NOT_YOURS } from "./orgs.js";
import { members, invites } from "./org-members.js";
import { CLASS, classOf, stateOf, tabsFor, tabOf, figure, planWord, ARCHIVE, RESTORE, sitesWord, membersWord } from "./org-words.js";

/* GET orgs/show; the answer, or the plain line for a link this reader may not open. */
export async function loadOrg(id) {
  const r = await call(`orgs/show?org=${encodeURIComponent(id)}`);
  if (r.ok) return r;
  if (r.status === 404 || r.status === 403) return { ok: false, line: NOT_YOURS };
  return { ok: false, line: why(r, "That organisation could not be loaded.") };
}

/* The drawer for organisation `id`, on tab `tab` (otab=; Overview when absent or not
   this reader's). Returns the drawer, or a plain line (overlays.js says it). */
export async function openOrg(id, tab = "") {
  const r = await loadOrg(id);
  if (!r.ok) return r.line;
  const st = { id: String(id), r, tab: tabOf(tab, r.may) };
  const body = h("div", { class: "org-dw" });
  const foot = h("div", { class: "org-foot" });
  const d = openDrawer({ title: r.org.name, subtitle: subtitle(r), body, footer: foot, size: "lg", key: "org", scope: "page",
    className: "org-drawer", route: { key: "org", value: st.id } });
  st.d = d;
  st.refresh = async (again = true) => {
    if (again) {
      const fresh = await loadOrg(st.id);
      if (!fresh.ok) { body.replaceChildren(h("div", { class: "state" }, h("div", null, fresh.line))); return; }
      st.r = fresh;
      st.tab = tabOf(st.tab, fresh.may);
      d.el.querySelector?.(".dw-title")?.replaceChildren(fresh.org.name);
      d.el.querySelector?.(".dw-sub")?.replaceChildren(subtitle(fresh));
      reloadPage();
    }
    draw(st, body, foot);
  };
  draw(st, body, foot);
  if (tab && tab !== st.tab) stepped("org", st.id, { otab: "" });       // a tab not theirs: Overview
  return d;
}

const subtitle = (r) => `${stateOf(r.org.state).word} · ${classOf(r.org.privacy_class).word} · ${sitesWord((r.org.sites || []).length)} · ${membersWord(r.org.members ?? 0)}`;

function draw(st, body, foot) {
  const tabs = tabsFor(st.r.may).map(([key, name]) => ({ key, name, href: S.hashFor({ ...S.read(), org: st.id, otab: key === "overview" ? "" : key }),
    count: key === "invites" ? (st.r.invites || []).length : 0 }));
  const strip = tabStrip(tabs, st.tab, (k) => {
    st.tab = k;
    stepped("org", st.id, { otab: k === "overview" ? "" : k });
    draw(st, body, foot);
  }, { label: st.r.org.name });
  strip.root.classList.add("org-tabs");
  strip.panel.append(...[PANELS[st.tab](st)].flat().filter(Boolean));
  const note = st.r.org.state === "archived" ? h("p", { class: "ui-strip org-archived", role: "status" }, pill("off", "Archived"),
    h("span", null, ` Since ${String(st.r.org.archived_at || "").slice(0, 10)}. Its sites are paused; nothing is deleted.`)) : null;
  body.replaceChildren(...[note, strip.root].filter(Boolean));
  footer(st, foot);
}

// ---- Overview ------------------------------------------------------------------------------

function overview(st) {
  const { org, overview: ov = {} } = st.r;
  const cls = classOf(org.privacy_class), state = stateOf(org.state);
  const tile = (label, value, note = null) => h("div", { class: "ui-card org-tile" }, h("small", { class: "muted" }, label), h("b", null, value), note ? h("small", { class: "muted" }, note) : null);
  return [
    h("div", { class: "org-tiles" },
      tile("Sites", String((ov.sites ?? (org.sites || []).length))),
      tile("Members", String(ov.members ?? org.members ?? 0)),
      tile("Requests, last 7 days", figure(ov.requests_7d), ov.withheld || (ov.requests_7d == null ? "No day of these sites was counted in the 7 days before today." : "Every request, people and bots: the daily totals, checked against each day's groups.")),
      tile("Last data", ov.last_day || "Not recorded")),
    h("dl", { class: "org-facts" },
      h("dt", null, "State"), h("dd", null, pill(state.kind, state.word)),
      h("dt", null, "Privacy class"), h("dd", null, pill(cls.kind, cls.word), " ", h("small", { class: "muted" }, cls.line)),
      ...(ME.saas ? [h("dt", null, "Plan"), h("dd", null, planWord(org, true))] : []),   // hosted only
      h("dt", null, "Made"), h("dd", null, when(org.created_at, "not recorded")),
      h("dt", null, "ID"), h("dd", null, copyIf("text", String(org.id), String(org.id), { label: "the organisation's ID" })),
      h("dt", null, "Your role"), h("dd", null, st.r.role ? st.r.role.replace(/^./, (c) => c.toUpperCase()) : "Install admin (not a member)")),
  ];
}

// ---- Sites ---------------------------------------------------------------------------------

function sites(st) {
  const { sites: rows = [], may = {}, movable = [] } = st.r;
  const msg = status();
  const list = rows.length ? h("ul", { class: "org-site-list" }, rows.map((s) => {
    const href = `../${s.path}#overview`;
    const kind = s.state === "active" ? "good" : s.state === "paused" ? "warn" : "off";
    return h("li", null, withUrl(h("a", { href, title: `Open ${s.name}'s dashboard` }, s.name), href, { label: s.name }),
      " ", pill(kind, s.state.replace(/^./, (c) => c.toUpperCase())));
  })) : h("p", { class: "empty" }, "No sites yet.");
  const parts = [h("section", { class: "s" }, h("h2", null, `Sites (${rows.length})`), list)];
  if (may.move && movable.length) {
    const sel = h("select", { name: "site", "aria-label": "The site to move here" }, movable.map((m) => h("option", { value: m.name }, `${m.name} (now in ${m.org})`)));
    const go = h("button", { type: "button", class: "btn" }, "Move here");
    const cell = h("div", { class: "acts" }, sel, go);
    const ask = () => {
      const site = sel.value;
      const yes = h("button", { type: "button", class: "btn primary" }, `Yes, move ${site}`);
      const no = h("button", { type: "button", class: "btn" }, "Keep it where it is");
      cell.replaceChildren(h("span", { class: "confirm" }, `Move ${site} into ${st.r.org.name}? Its data, settings and keys move with it; its old organisation's members stop seeing it.`, yes, no));
      no.addEventListener("click", () => cell.replaceChildren(sel, go));
      yes.addEventListener("click", async () => {
        yes.disabled = no.disabled = true;
        const r = await call("orgs/move-site", { org: Number(st.id), site });
        if (!r.ok) { msg.say(why(r)); cell.replaceChildren(sel, go); return; }
        msg.say(`${site} is now in ${st.r.org.name}.${r.recredited ? ` ${r.recredited} key${r.recredited === 1 ? " is" : "s are"} now under an admin here, so they keep working.` : ""}`, true);
        st.refresh();
      });
    };
    go.addEventListener("click", ask);
    parts.push(h("section", { class: "s" }, h("h2", null, "Move a site here"), cell, msg));
  }
  if (may.add_site) {
    const add = h("button", { type: "button", class: "btn" }, "Add a site");
    add.addEventListener("click", () => addSite(st));
    parts.push(h("p", { class: "acts" }, add, h("small", { class: "muted" }, " Opens Add a site, with this organisation chosen.")));
  }
  return parts;
}

/* Add a site: the drawer closes (its Back taken), then Settings › Sites opens its wizard with
   this organisation chosen (setup=new&org=<id>). */
async function addSite(st) {
  st.d.close();
  await new Promise((done) => {
    let gone = false;
    const go = () => { if (!gone) { gone = true; done(); } };
    addEventListener("popstate", go, { once: true });
    setTimeout(go, 300);
  });
  S.set({ tab: "settings/org/sites", setup: "new", org: st.id });
}

// ---- Settings ------------------------------------------------------------------------------

function settings(st) {
  const { org, may = {}, settings: set = {} } = st.r;
  const out = [];
  // The name.
  const msg1 = status();
  const name = input({ name: "name", value: org.name, maxlength: "200", disabled: !may.rename });
  name.value = org.name;
  const save1 = h("button", { type: "submit", class: "btn", disabled: !may.rename }, "Rename");
  const f1 = h("form", { class: "org-form" }, field("Name", name, may.rename ? "" : "Only an owner or an admin renames it."), h("div", { class: "acts" }, save1), msg1);
  f1.addEventListener("submit", async (e) => {
    e.preventDefault();
    const r = await call("orgs/rename", { org: Number(st.id), name: name.value.trim() });
    if (!r.ok) { msg1.say(why(r)); return; }
    msg1.say("Renamed.", true);
    st.refresh();
  });
  out.push(h("section", { class: "s" }, h("h2", null, "Name"), f1));
  // The privacy class: an install admin's.
  const msg2 = status();
  const radios = Object.entries(CLASS).map(([k, c]) => {
    const el = h("input", { type: "radio", name: "privacy_class", value: k, checked: k === org.privacy_class, disabled: !may.privacy });
    el.checked = k === org.privacy_class;
    return h("label", { class: "org-choice" }, el, h("span", null, h("b", null, c.word), h("small", { class: "muted" }, c.line)));
  });
  const save2 = may.privacy ? h("button", { type: "submit", class: "btn" }, "Save the class") : null;
  const f2 = h("form", { class: "org-form" }, h("fieldset", { class: "org-set" }, h("legend", null, "Privacy class"), ...radios),
    st.r.install_keeps ? null : h("p", { class: "muted" }, "This install does not keep everything, so today both classes follow each site's Privacy settings."),
    may.privacy ? h("div", { class: "acts" }, save2) : h("p", { class: "muted" }, "Only an install admin changes it."), msg2);
  f2.addEventListener("submit", async (e) => {
    e.preventDefault();
    const cls = radios.map((l) => l.querySelector("input")).find((i) => i.checked)?.getAttribute("value");
    const r = await call("orgs/privacy", { org: Number(st.id), privacy_class: cls });
    if (!r.ok) { msg2.say(why(r)); return; }
    msg2.say(`Now ${classOf(r.privacy_class).word}. It applies from the next run.`, true);
    st.refresh();
  });
  out.push(h("section", { class: "s" }, h("h2", null, "Privacy class"), f2));
  // The sign-in rule (an owner's) and the daily mail's default (an admin's).
  const msg3 = status();
  const totp = h("input", { type: "checkbox", name: "require_totp", checked: !!set.require_totp, disabled: !may.settings_totp });
  const mail = h("input", { type: "checkbox", name: "mail_daily", checked: set.mail_daily !== false, disabled: !may.settings_mail });
  totp.checked = !!set.require_totp;
  mail.checked = set.mail_daily !== false;
  const save3 = h("button", { type: "submit", class: "btn", disabled: !may.settings_totp && !may.settings_mail }, "Save");
  const f3 = h("form", { class: "org-form" },
    h("label", { class: "org-check" }, totp, h("span", null, h("b", null, "Two-step sign-in is required"), h("small", { class: "muted" }, may.settings_totp ? "Members without it set it up the next time they sign in." : "Only an owner changes it."))),
    h("label", { class: "org-check" }, mail, h("span", null, h("b", null, "The daily mail is on by default"), h("small", { class: "muted" }, "For this organisation's sites that set nothing of their own."))),
    h("div", { class: "acts" }, save3), msg3);
  f3.addEventListener("submit", async (e) => {
    e.preventDefault();
    const ask = {};
    if (may.settings_totp && totp.checked !== !!set.require_totp) ask.require_totp = totp.checked;
    if (may.settings_mail && mail.checked !== (set.mail_daily !== false)) ask.mail_daily = mail.checked;
    if (!Object.keys(ask).length) { msg3.say("Nothing changed."); return; }
    const r = await call("orgs/prefs", { org: Number(st.id), ...ask });
    if (!r.ok) { msg3.say(why(r)); return; }
    st.r.settings = r.settings;
    msg3.say("Saved.", true);
  });
  out.push(h("section", { class: "s" }, h("h2", null, "Sign-in and mail"), f3));
  return out;
}

// ---- Keys ----------------------------------------------------------------------------------

function keys(st) {
  const list = st.r.keys || [];
  const msg = status();
  const by = Object.fromEntries((st.r.members || []).map((m) => [String(m.id), m.email]));
  if (!list.length) return h("section", { class: "s" }, h("h2", null, "Keys"), h("p", { class: "empty" }, "No API or MCP token yet. Make one under Settings › AI assistants › Tokens & links."));
  const rows = list.map((t) => {
    const cell = h("td", { class: "n" });
    const idle = () => {
      if (t.revoked_at) { cell.replaceChildren(h("span", { class: "muted" }, "Revoked")); return; }
      const b = h("button", { type: "button", class: "btn danger", "aria-label": `Revoke ${t.name}` }, "Revoke");
      b.addEventListener("click", () => {
        const yes = h("button", { type: "button", class: "btn danger" }, "Yes, revoke");
        const no = h("button", { type: "button", class: "btn" }, "Keep it");
        cell.replaceChildren(h("span", { class: "confirm" }, "Whatever uses it stops at once.", yes, no));
        no.addEventListener("click", idle);
        yes.addEventListener("click", async () => {
          yes.disabled = no.disabled = true;
          const r = await call("orgs/token-revoke", { org: Number(st.id), id: t.id });
          if (!r.ok) { msg.say(why(r)); idle(); return; }
          t.revoked_at = new Date().toISOString();
          msg.say(`${t.name} is revoked.`, true);
          idle();
        });
      });
      cell.replaceChildren(b);
    };
    idle();
    return h("tr", null, h("td", null, copyIf("text", t.name, t.name, { label: "the token's name", cls: "" })),
      h("td", null, (t.scopes || []).join(", ")), h("td", null, t.sites ? t.sites.join(", ") : "Every site"),
      h("td", null, by[String(t.created_by)] ? copyIf("email", by[String(t.created_by)], by[String(t.created_by)], { label: "email", cls: "" }) : String(t.created_by || "the server")),
      h("td", { class: "muted n" }, when(t.last_used)), cell);
  });
  return h("section", { class: "s" }, h("h2", null, `Keys (${list.length})`),
    h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "API and MCP tokens"),
      h("thead", null, h("tr", null, ["Name", "Scopes", "Sites", "Made by", "Last used"].map((t, i) => h("th", { scope: "col", class: i === 4 ? "n" : null }, t)),
        h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))), h("tbody", null, rows))), msg);
}

// ---- Audit ---------------------------------------------------------------------------------

function audit(st) {
  const box = h("div", null, h("p", { class: "empty" }, "Loading the audit log..."));
  call(`orgs/auditlog?org=${encodeURIComponent(st.id)}&limit=200`).then((r) => {
    if (!r.ok) { box.replaceChildren(h("p", { class: "empty" }, why(r, "The audit log could not be loaded."))); return; }
    const list = r.entries || [];
    if (!list.length) { box.replaceChildren(h("p", { class: "empty" }, "No change recorded yet.")); return; }
    box.replaceChildren(h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Audit log"),
      h("thead", null, h("tr", null, ["When", "Who", "What", "Detail"].map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", null, list.map((e) => h("tr", null, h("td", { class: "muted" }, when(e.at)),
        h("td", null, e.actor_email ? copyIf("email", e.actor_email, e.actor_email, { label: "email", cls: "" }) : String(e.actor || "")),
        h("td", null, h("code", null, e.action)),
        h("td", null, e.detail || e.target ? copyIf("text", [e.target, e.detail].filter(Boolean).join(": "), null, { label: "the detail", cls: "" }) : "")))))));
  });
  return h("section", { class: "s" }, h("h2", null, "Audit"), box);
}

const PANELS = { overview, sites, members, invites, settings, keys, audit };

// ---- the footer: Archive or Restore, asking first ------------------------------------------

function footer(st, foot) {
  const { org, may = {} } = st.r;
  if (!may.archive) { foot.replaceChildren(); return; }
  const archived = org.state === "archived";
  const t = archived ? RESTORE : ARCHIVE;
  const msg = status();
  const b = h("button", { type: "button", class: archived ? "btn" : "btn danger" }, t.button);
  b.addEventListener("click", () => {
    const yes = h("button", { type: "button", class: archived ? "btn primary" : "btn danger" }, `Yes, ${t.button.toLowerCase()}`);
    const no = h("button", { type: "button", class: "btn" }, "Keep it as it is");
    foot.replaceChildren(h("div", { class: "org-ask", role: "group", "aria-label": t.title }, h("b", null, t.title), h("p", null, t.what),
      t.undo ? h("p", { class: "muted" }, t.undo) : null, h("div", { class: "acts" }, no, yes), msg));
    no.focus?.();
    no.addEventListener("click", () => footer(st, foot));
    yes.addEventListener("click", async () => {
      yes.disabled = no.disabled = true;
      const r = await call(archived ? "orgs/restore" : "orgs/archive", { org: Number(st.id) });
      if (!r.ok) { msg.say(why(r)); yes.disabled = no.disabled = false; return; }
      await st.refresh();
    });
  });
  foot.replaceChildren(b);
}
