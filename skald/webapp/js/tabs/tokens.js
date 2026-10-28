// v2: one row per token (its name, what it is for, its sites, made and last used; a pill: in use
// or never used) with Revoke on the row; "New token" is the tab's one primary and its form
// opens in a drawer (edit=token-new, set-edit.js).
//
// Settings › Tokens & links, "Your tokens" (accounts, access.mode: sessions; 2.40: also on the
// MCP page with only: "mcp", the assistants' tokens alone, with no form):
// the organisation's tokens, each said by what it is for
// (conn-words.js purposeOf), and revoked here with a confirm. The set-up
// dialogs make tokens for one task; "New token" keeps the full choice of
// sites and scopes. A new token is shown once; the server keeps
// only a fingerprint of it. A viewer is told the list is for admins. The
// helper behind <page>/tokens checks role and CSRF.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions, VIEWER } from "../access.js";
import { copyable, field, input, status, confirmIn, when, why } from "./forms.js";
import { purposeOf } from "./conn-words.js";
import { copyIf } from "../urlactions.js";
import { DEMO } from "../demo.js";
import { primary, statusRow } from "./set-ui.js";
import { editPart, openEdit } from "./set-edit.js";
import { arrivedBox } from "../ui/live.js";

const SCOPES = [
  ["read", "Reading figures", "every figure these pages show, as JSON"],
  ["read_private", "Reading visitor addresses", "also the request log and AI activity, which hold visitor addresses"],
  ["mcp", "AI assistant (MCP)", "for an AI assistant, through the MCP server"],
  ["ingest", "Sending logs", "a shipper or a platform adds log lines to the site; reads nothing"],
  // 2.39.0: the MCP tool setup_line. The server refuses it unless an owner or admin makes it, for one site, with mcp.
  ["setup", "Set-up lines (AI agent)", "can make set-up lines for an AI agent; reads nothing by itself. One site only, with AI assistant (MCP); owners and admins only"],
  // 2.44: the MCP tools add_site, site_progress, check_site, send_invites. The whole organisation, with mcp; owners and admins who see every site.
  ["add_sites", "Add sites (AI agent)", "can add sites to this organisation and watch their set-up, within the plan. Every site, with AI assistant (MCP); owners and admins only"],
];

// The token just made by hand: kept in this page's memory only, so a redraw does not lose it before it is copied.
let fresh = null;
// The page's list of every token, drawn again when a token is made in the drawer.
let reloadAll = null;

const sitesOf = (m) => {
  const names = (m.x?.sites?.sites || []).map((x) => x && x.name).filter(Boolean);
  return names.length ? [...new Set(names)] : [m.site];
};

const iconOf = (scopes) => (scopes.includes("mcp") ? "bot" : scopes.includes("ingest") ? "server" : "key");

/* New token, by hand: a name, which sites, and its scopes; the token shown once, here. */
function newToken(m) {
  const msg = status();
  const shown = h("div");
  function showFresh() {
    if (!fresh) { shown.replaceChildren(); return; }
    const done = h("button", { type: "button", class: "btn" }, "I have copied it");
    done.addEventListener("click", () => { fresh = null; shown.replaceChildren(); });
    shown.replaceChildren(h("div", { class: "state ok acct-link", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `The token "${fresh.name}". `), "Copy it now: it is shown only this once. Put it in the Authorization header as Bearer <token>."),
      copyable(fresh.token, "the new token"),
      // 2.44: whether the assistant or tool used it yet, by itself, with Test (sites/arrived token:<id>).
      fresh.id && m.site ? arrivedBox(m.site, `token:${fresh.id}`, { intro: "Waiting: nothing has used this token yet." }) : "",
      h("div", { class: "acts" }, done))));
  }
  const name = input({ name: "token-name", autocomplete: "off", maxlength: "60", placeholder: "e.g. Weekly sheet", required: true });
  const siteBoxes = sitesOf(m).map((s) => {
    const box = h("input", { type: "checkbox", value: s });
    box.checked = s === m.site;
    return h("label", { class: "chk" }, box, h("span", null, s));
  });
  const scopeBoxes = SCOPES.map(([k, label, sub]) => {
    const box = h("input", { type: "checkbox", value: k });
    box.checked = k === "read";
    return h("label", { class: "chk" }, box, h("span", null, h("b", null, label), h("small", null, sub)));
  });
  const make = h("button", { type: "submit", class: "btn primary" }, "Make token");
  // Add sites is for the whole organisation: no site list, and it works through MCP.
  const scopeBox = (k) => scopeBoxes.map((l) => l.querySelector("input")).find((b) => b.getAttribute("value") === k);
  const adds = () => scopeBox("add_sites").checked;
  const siteSet = h("fieldset", { class: "af-set" }, h("legend", null, "Sites"), siteBoxes);
  const wholeOrg = h("p", { class: "note", hidden: true }, "Every site of this organisation, and the ones it adds.");
  scopeBox("add_sites").addEventListener("change", () => {
    if (adds()) scopeBox("mcp").checked = true;
    siteSet.hidden = adds();
    wholeOrg.hidden = !adds();
  });
  const form = h("form", { class: "af-col", novalidate: true },
    field("Name", name, "What the token is for, so the list says whose it is."),
    siteSet, wholeOrg,
    h("fieldset", { class: "af-set" }, h("legend", null, "What it may do"), scopeBoxes),
    h("div", null, make));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sites = siteBoxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.getAttribute("value"));
    const scopes = scopeBoxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.getAttribute("value"));
    if (!name.value.trim()) { msg.say("Give the token a name first."); name.focus(); return; }
    if (!sites.length && !adds()) { msg.say("Choose at least one site."); return; }
    if (!scopes.length) { msg.say("Choose at least one thing it may do."); return; }
    make.disabled = true;
    const r = await call("tokens/create", { name: name.value.trim(), sites: adds() ? [] : sites, scopes });
    make.disabled = false;
    if (!r.ok || !r.token) { msg.say(why(r, "The token was not made.")); return; }
    fresh = { name: name.value.trim(), token: r.token, id: r.id };
    name.value = "";
    msg.say("");
    showFresh();
    reloadAll?.();
  });
  showFresh();
  return [h("p", { class: "note" }, "For advanced use: any sites, any mix of scopes. The set-up pages make the right token for each task and are simpler."), shown, form, msg];
}
editPart("token-new", { title: "New token", body: (m) => (DEMO.on ? "In the demo, tokens need a running Skald." : !sessions() ? "Tokens come with accounts."
  : isViewer() ? `${VIEWER} Tokens are for admins.` : newToken(m)) });

export default function tokens(m, { reloadHook = null, only = "", title = "Your tokens" } = {}) {
  if (isViewer()) return h("section", { class: "s" }, h("h2", null, title), h("p", { class: "note" }, `${VIEWER} Tokens are for admins.`));
  const list = h("div", { class: "set-list" }, h("p", { class: "empty" }, "Loading the tokens..."));
  const msg = status();
  const reload = () => call("tokens").then(draw);
  if (reloadHook) reloadHook(reload);
  if (!only) reloadAll = reload;

  function row(t, scopes) {
    const cell = h("span", { class: "tok-act" });
    const drawCell = () => {
      const rv = h("button", { type: "button", class: "btn danger", "aria-label": `Revoke the token ${t.name}` }, "Revoke");
      rv.addEventListener("click", () => confirmIn(cell, `Revoke "${t.name}"? Whatever uses it stops at once.`, "Yes, revoke", async () => {
        const res = await call("tokens/revoke", { id: t.id });
        if (res.ok) { msg.say(`Revoked "${t.name}".`, true); reload(); } else { msg.say(why(res)); drawCell(); }
      }, drawCell));
      cell.replaceChildren(rv);
    };
    drawCell();
    const sites = Array.isArray(t.sites) ? t.sites.join(", ") : t.sites || "all sites";
    return statusRow({ iconName: iconOf(scopes), title: copyIf("text", t.name || `#${t.id}`, null, { label: "token name", cls: "" }),
      line: [h("span", { class: "cn-purpose" }, purposeOf(t.scopes)), ` · ${sites} · made `, when(t.created_at, ""), t.created_by ? ` by ${t.created_by}` : "", " · last used ", when(t.last_used)],
      kind: t.last_used ? "good" : "off", word: t.last_used ? "In use" : "Never used", action: cell });
  }

  function draw(r) {
    if (!r.ok) { list.replaceChildren(h("p", { class: "empty" }, why(r, "The tokens could not be loaded."))); return; }
    const scopesOf = (t) => (Array.isArray(t.scopes) ? t.scopes : String(t.scopes || "").split(/[\s,]+/));
    const all = (r.tokens || []).filter((t) => !t.revoked_at && (!only || scopesOf(t).includes(only)));
    if (!all.length) { list.replaceChildren(h("p", { class: "empty" }, only ? "No token for an assistant yet. Connect an assistant above: it makes one." : "No tokens yet. Each set-up makes the token it needs: sending logs, an AI assistant (MCP), the API.")); return; }
    list.replaceChildren(...all.map((t) => row(t, scopesOf(t))));
  }

  reload();
  const card = (sub) => h("section", { class: "ui-card set-rows tok-rows" }, h("div", { class: "ui-card-h" }, h("h2", null, title), h("p", { class: "sub" }, sub)), list, msg);
  if (only) return card("Revoke one and that assistant stops at once. Every token is under Tokens & links.");
  return [card("Every token of this organisation, by what it is for. A token is shown once, when it is made; only a fingerprint of it is kept. Revoke one and whatever uses it stops at once."),
    primary("New token", () => openEdit("token-new", m), { iconName: "plus" })];
}
