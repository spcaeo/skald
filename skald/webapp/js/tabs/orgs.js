// Settings › Organisation › Organisations (accounts, access.mode: sessions; the helper:
// skald/orgs_api.py). An install admin sees every organisation; anyone else the ones
// they belong to. Each is a card: its name, state and privacy class, its sites and members,
// its plan (hosted installs only) and when it was made. A card opens its drawer
// (org-drawer.js, org=<id>); the one primary button, New organisation, is an install admin's (org=new).
//
// The address holds every state (docs/ROUTES.md): org=<id>&otab=<tab> for the drawer and its
// tab, org=new for New organisation, orgs_q and orgs_sort for the search and the order.
// Ids only: an organisation by its id, a member by theirs; never a name or an email.

import { h } from "../ui.js";
import * as S from "../state.js";
import { HASH, writeKeys } from "../tablestate.js";
import { call } from "./ipmanager.js";
import { primary, pill, icon } from "./set-ui.js";
import { field, input, status, why, copyable } from "./forms.js";
import { openDrawer } from "../drawer.js";
import { ROLE } from "../overlays.js";
import { DEMO } from "../demo.js";
import { sessions, ME } from "../access.js";
import { CLASS, classOf, stateOf, cardLine, siteNames, filterSort, SORTS, sortOf, parseKey, ROLE_WORD } from "./org-words.js";

export const NOT_YOURS = "That organisation is not available to you.";
const NONE = "That organisation is not one Skald keeps here.";

let last = null;              // the last answer of GET orgs: the cards, and who reads them
let redraw = null;            // the page's own redraw, after a change in a drawer

/* GET orgs, once per draw; the drawers ask again after a change (reload()). */
export async function loadOrgs() {
  const r = await call("orgs");
  if (r.ok) last = r;
  return r;
}
export const reload = () => (redraw ? redraw() : loadOrgs());

export default function orgs() {
  if (!sessions() && !DEMO.on) {
    return [h("div", { class: "state" }, h("div", null, "Organisations come with accounts. This server uses one shared login."))];
  }
  const p = HASH.read();
  let q = p.get("orgs_q") || "";
  let sort = sortOf(p.get("orgs_sort"));
  const list = h("div", { class: "org-list", "aria-live": "polite" }, h("p", { class: "empty" }, "Loading the organisations..."));
  const slot = h("span");
  const search = input({ type: "search", name: "orgs_q", value: q, placeholder: "Search by name or site", "aria-label": "Search the organisations" });
  search.value = q;
  const order = h("select", { name: "orgs_sort", "aria-label": "Order" }, SORTS.map(([k, w]) => h("option", { value: k, selected: k === sort }, w)));
  order.value = sort;
  search.addEventListener("input", () => { q = search.value; writeKeys({ orgs_q: q.trim() }); drawList(); });
  order.addEventListener("change", () => { sort = sortOf(order.value); writeKeys({ orgs_sort: sort === "name:asc" ? "" : sort }); drawList(); });
  const tools = h("div", { class: "org-tools" }, h("span", { class: "org-search" }, h("span", { class: "org-search-ic", html: icon("search") }), search), order);

  function drawList() {
    if (!last) return;
    const cards = filterSort(last.orgs || [], q, sort);
    if (!(last.orgs || []).length) { list.replaceChildren(h("p", { class: "empty" }, "No organisation yet.")); return; }
    if (!cards.length) { list.replaceChildren(h("p", { class: "empty" }, `No organisation matches "${q.trim()}".`)); return; }
    list.replaceChildren(...cards.map((c) => card(c, last.current)));
  }
  async function draw() {
    const r = await loadOrgs();
    if (!r.ok) { list.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The organisations could not be loaded.")))); return; }
    slot.replaceChildren(r.can_create ? primary("New organisation", () => openNew()) : "");
    drawList();
  }
  redraw = draw;
  draw();
  return [slot, tools, list];
}

/* One organisation's card: the whole card opens its drawer. */
function card(c, current) {
  const cls = classOf(c.privacy_class), st = stateOf(c.state);
  const b = h("button", { type: "button", class: `ui-card org-card${c.state === "archived" ? " is-archived" : ""}`, "data-org": String(c.id),
    "aria-label": `${c.name}: ${st.word}, ${cls.word}. Open its details` },
  h("span", { class: "org-card-h" }, h("span", { class: "ui-ic", html: icon("people") }), h("b", { class: "org-name" }, c.name),
    c.id === current ? h("span", { class: "org-here" }, "This site's") : null),
  h("span", { class: "org-pills" }, pill(st.kind, st.word), pill(cls.kind, cls.word), c.role ? h("span", { class: "org-role muted" }, `You: ${ROLE_WORD[c.role] || c.role}`) : null),
  h("span", { class: "org-line" }, cardLine(c, ME.saas)),
  h("span", { class: "org-sites muted" }, siteNames(c.sites || [])),
  h("small", { class: "muted" }, `Made ${String(c.created_at || "").slice(0, 10) || "on a day not recorded"}`));
  b.addEventListener("click", async () => { const { openOrg } = await import("./org-drawer.js"); openOrg(c.id); });
  return b;
}

// ---- New organisation (org=new): an install admin's ------------------------------------

/* Every site of the install the reader can move in: the sites of every card. */
const allSites = () => (last?.orgs || []).flatMap((c) => (c.sites || []).map((s) => ({ name: s, org: c.name })));

export function openNew() {
  const msg = status();
  const name = input({ name: "name", maxlength: "200", autocomplete: "off", required: true });
  const radio = (group, value, words, line, checked) => {
    const el = h("input", { type: "radio", name: group, value, checked });
    el.checked = checked;
    return h("label", { class: "org-choice" }, el, h("span", null, h("b", null, words), h("small", { class: "muted" }, line)));
  };
  const klass = h("fieldset", { class: "org-set" }, h("legend", null, "Privacy class"),
    radio("privacy_class", "internal", CLASS.internal.word, CLASS.internal.line, true),
    radio("privacy_class", "client", CLASS.client.word, CLASS.client.line, false));
  const email = input({ type: "email", name: "owner_email", autocomplete: "off", placeholder: "name@example.com", "aria-label": "The first owner's email" });
  const owner = h("fieldset", { class: "org-set" }, h("legend", null, "First owner"),
    radio("owner", "me", "You", "You are its first owner, and can move sites in now.", true),
    radio("owner", "other", "Someone else", "They get an invite by mail, or a link to pass on. Move sites in once they have joined.", false), email);
  const sites = allSites();
  const boxes = sites.map((s) => h("label", { class: "org-site-pick" }, h("input", { type: "checkbox", name: "site", value: s.name }), ` ${s.name} `, h("small", { class: "muted" }, `(now in ${s.org})`)));
  const move = sites.length ? h("fieldset", { class: "org-set" }, h("legend", null, "Sites to move in (optional)"), ...boxes,
    h("small", { class: "muted" }, "A moved site keeps its data, settings and keys.")) : null;
  const go = h("button", { type: "submit", class: "btn primary" }, "Make the organisation");
  const form = h("form", { class: "org-form", novalidate: true }, field("Name", name), klass, owner, move, h("div", { class: "acts" }, go), msg);
  const done = h("div");
  const body = h("div", null, form, done);
  const d = openDrawer({ title: "New organisation", subtitle: "Its name, its privacy class and its first owner.", body, size: "md",
    key: "org", scope: "page", route: { key: "org", value: "new" } });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const ins = [...form.querySelectorAll("input")];
    const picked = (group) => ins.filter((i) => i.getAttribute("name") === group && i.checked).map((i) => i.getAttribute("value"));
    const who = picked("owner")[0];
    const body2 = { name: name.value.trim(), privacy_class: picked("privacy_class")[0] || "internal",
      owner: who === "other" ? email.value.trim() : "me", sites: picked("site") };
    if (!body2.name) { msg.say("Type a name."); return; }
    if (who === "other" && !body2.owner) { msg.say("Type the first owner's email."); return; }
    go.disabled = true;
    const r = await call("orgs/create", body2);
    go.disabled = false;
    if (!r.ok) { msg.say(why(r, "The organisation could not be made.")); return; }
    form.hidden = true;
    const open = h("button", { type: "button", class: "btn primary" }, "Open it");
    open.addEventListener("click", async () => { const { openOrg } = await import("./org-drawer.js"); openOrg(r.org.id); });
    done.replaceChildren(h("div", { class: "state ok", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `${r.org.name} is made.`), r.link ? " Mail is not set up: pass this link to its first owner. It works once." : r.mailed ? " Its first owner has an invite by mail." : ""),
      r.link ? copyable(r.link, "the invite link") : null, h("div", { class: "acts" }, open))));
    reload();
  });
  name.focus?.();
  return d;
}

// ---- the address -------------------------------------------------------------------------

/* org=<value> from a link or a reload (overlays.js RESTORE): the drawer, or one plain line. */
export async function openOrgKey(v, m, s) {
  const key = parseKey(v);
  if (key == null) return NONE;
  if (key === "new") {
    const r = last || await loadOrgs();
    if (!r.ok) return why(r, NONE);
    return r.can_create ? openNew() : ROLE;
  }
  const { openOrg } = await import("./org-drawer.js");
  return openOrg(key, s?.otab || "");
}
