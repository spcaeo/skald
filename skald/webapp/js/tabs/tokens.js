// Settings > Connections, "Your tokens" (accounts, access.mode: sessions):
// the organisation's tokens in one table, each said by what it is for
// (conn-words.js purposeOf), and revoked here with a confirm. The dialogs
// above make tokens for one task; "Make a token by hand" keeps the full
// choice of sites and scopes. A new token is shown once; the server keeps
// only a fingerprint of it. A viewer is told the list is for admins. The
// helper behind <page>/tokens checks role and CSRF.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { isViewer, VIEWER } from "../access.js";
import { copyable, field, input, status, confirmIn, when, why } from "./forms.js";
import { purposeOf } from "./conn-words.js";
import { copyIf } from "../urlactions.js";

const SCOPES = [
  ["read", "Reading figures", "every figure these pages show, as JSON"],
  ["read_private", "Reading visitor addresses", "also the request log and AI activity, which hold visitor addresses"],
  ["mcp", "AI assistant (MCP)", "for an AI assistant, through the MCP server"],
  ["ingest", "Sending logs", "a shipper or a platform adds log lines to the site; reads nothing"],
  // 2.39.0: the MCP tool setup_line. The server refuses it unless an owner or admin makes it, for one site, with mcp.
  ["setup", "Set-up lines (AI agent)", "can make set-up lines for an AI agent; reads nothing by itself. One site only, with AI assistant (MCP); owners and admins only"],
];

// The token just made by hand: kept in this page's memory only, so a redraw does not lose it before it is copied.
let fresh = null;

const sitesOf = (m) => {
  const names = (m.x?.sites?.sites || []).map((x) => x && x.name).filter(Boolean);
  return names.length ? [...new Set(names)] : [m.site];
};

export default function tokens(m, { reloadHook = null } = {}) {
  if (isViewer()) return h("section", { class: "s" }, h("h2", null, "Your tokens"), h("p", { class: "note" }, `${VIEWER} Tokens are for admins.`));
  const list = h("div", null, h("p", { class: "empty" }, "Loading the tokens..."));
  const msg = status();
  const shown = h("div");
  const reload = () => call("tokens").then(draw);
  if (reloadHook) reloadHook(reload);

  function showFresh() {
    if (!fresh) { shown.replaceChildren(); return; }
    const done = h("button", { type: "button", class: "btn" }, "I have copied it");
    done.addEventListener("click", () => { fresh = null; shown.replaceChildren(); });
    shown.replaceChildren(h("div", { class: "state ok acct-link", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `The token "${fresh.name}". `), "Copy it now: it is shown only this once. Put it in the Authorization header as Bearer <token>."),
      copyable(fresh.token, "the new token"), h("div", { class: "acts" }, done))));
  }

  function draw(r) {
    if (!r.ok) { list.replaceChildren(h("p", { class: "empty" }, why(r, "The tokens could not be loaded."))); return; }
    const all = (r.tokens || []).filter((t) => !t.revoked_at);
    if (!all.length) { list.replaceChildren(h("p", { class: "empty" }, "No tokens yet. The cards above make one for each task.")); return; }
    list.replaceChildren(h("div", { class: "scroll" }, h("table", { class: "rows-mid cn-tokens" }, h("caption", { class: "vh" }, "Your tokens"),
      h("thead", null, h("tr", null, [["Name"], ["What it is for"], ["Sites"], ["Made", "n"], ["Last used", "n"]].map(([t, cls]) => h("th", { scope: "col", class: cls }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))),
      h("tbody", null, all.map((t) => {
        const cell = h("td", { class: "n" });
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
        return h("tr", null, h("td", null, copyIf("text", t.name || `#${t.id}`, null, { label: "token name", cls: "" })), h("td", { class: "cn-purpose" }, purposeOf(t.scopes)), h("td", { class: "path nm" }, sites),
          h("td", { class: "muted n" }, when(t.created_at, ""), t.created_by ? ` by ${t.created_by}` : ""), h("td", { class: "muted n" }, when(t.last_used)), cell);
      })))));
  }

  // By hand: a name, which sites, and its scopes.
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
  const form = h("form", { class: "af-col", novalidate: true },
    field("Name", name, "What the token is for, so the list says whose it is."),
    h("fieldset", { class: "af-set" }, h("legend", null, "Sites"), siteBoxes),
    h("fieldset", { class: "af-set" }, h("legend", null, "What it may do"), scopeBoxes),
    h("div", null, make));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sites = siteBoxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.getAttribute("value"));
    const scopes = scopeBoxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.getAttribute("value"));
    if (!name.value.trim()) { msg.say("Give the token a name first."); name.focus(); return; }
    if (!sites.length) { msg.say("Choose at least one site."); return; }
    if (!scopes.length) { msg.say("Choose at least one thing it may do."); return; }
    make.disabled = true;
    const r = await call("tokens/create", { name: name.value.trim(), sites, scopes });
    make.disabled = false;
    if (!r.ok || !r.token) { msg.say(why(r, "The token was not made.")); return; }
    fresh = { name: name.value.trim(), token: r.token };
    name.value = "";
    msg.say("");
    showFresh();
    reload();
  });

  showFresh();
  reload();
  return h("section", { class: "s" }, h("h2", null, "Your tokens"),
    h("p", { class: "sub" }, "Every token of this organisation, by what it is for. A token is shown once, when it is made; only a fingerprint of it is kept. Revoke one and whatever uses it stops at once."),
    shown, list, msg,
    h("details", { class: "fold" }, h("summary", null, "Make a token by hand"),
      h("p", { class: "sub" }, "For advanced use: any sites, any mix of scopes. The cards above are simpler."), form));
}
