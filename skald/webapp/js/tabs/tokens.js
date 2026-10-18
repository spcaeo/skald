// Settings > API, with accounts (access.mode: sessions): the organisation's
// API tokens, made, listed and revoked here by an admin. A new token is shown
// once; the server keeps only a fingerprint of it. A viewer is told the list
// is for admins. The helper behind <page>/tokens checks role and CSRF.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { isViewer, VIEWER } from "../access.js";
import { copyable, field, input, status, confirmIn, when, why } from "./forms.js";
import { howTo } from "./help.js";

const SCOPES = [
  ["read", "Read", "every figure these pages show, as JSON"],
  ["read_private", "Read private files", "also the request log and AI activity, which hold visitor addresses"],
  ["mcp", "MCP", "for an AI assistant, through the MCP server"],
];

// The token just made: kept in this page's memory only, so a redraw does not lose it before it is copied.
let fresh = null;

const sitesOf = (m) => {
  const names = (m.x?.sites?.sites || []).map((x) => x && x.name).filter(Boolean);
  return names.length ? [...new Set(names)] : [m.site];
};

export default function tokens(m) {
  if (isViewer()) return h("section", { class: "s" }, h("h2", null, "Tokens"), h("p", { class: "note" }, `${VIEWER} Tokens are for admins.`));
  const list = h("div", null, h("p", { class: "empty" }, "Loading the tokens..."));
  const msg = status();
  const shown = h("div");
  const reload = () => call("tokens").then(draw);

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
    if (!all.length) { list.replaceChildren(h("p", { class: "empty" }, "No tokens yet.")); return; }
    list.replaceChildren(h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "API tokens"),
      h("thead", null, h("tr", null, [["Name"], ["Sites"], ["Scopes"], ["Made", "n"], ["Last used", "n"]].map(([t, cls]) => h("th", { scope: "col", class: cls }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Action")))),
      h("tbody", null, all.map((t) => {
        const cell = h("td", { class: "n" });
        const drawCell = () => {
          const rv = h("button", { type: "button", class: "btn danger", "aria-label": `Revoke the token ${t.name}` }, "Revoke");
          rv.addEventListener("click", () => confirmIn(cell, `Revoke "${t.name}"? Scripts using it stop at once.`, "Yes, revoke", async () => {
            const res = await call("tokens/revoke", { id: t.id });
            if (res.ok) { msg.say(`Revoked "${t.name}".`, true); reload(); } else { msg.say(why(res)); drawCell(); }
          }, drawCell));
          cell.replaceChildren(rv);
        };
        drawCell();
        const sites = Array.isArray(t.sites) ? t.sites.join(", ") : t.sites || "all sites";
        const scopes = (Array.isArray(t.scopes) ? t.scopes : String(t.scopes || "").split(/[,\s]+/)).filter(Boolean);
        return h("tr", null, h("td", null, t.name || `#${t.id}`), h("td", { class: "path nm" }, sites),
          h("td", null, scopes.join(", ") || "read", t.private ? h("span", { class: "muted" }, " (private)") : null),
          h("td", { class: "muted n" }, when(t.created_at, ""), t.created_by ? ` by ${t.created_by}` : ""), h("td", { class: "muted n" }, when(t.last_used)), cell);
      })))));
  }

  // The form: a name, which sites, private or not, and its scopes.
  const name = input({ name: "token-name", autocomplete: "off", maxlength: "60", placeholder: "e.g. Weekly sheet", required: true });
  const siteBoxes = sitesOf(m).map((s) => h("label", { class: "chk" }, h("input", { type: "checkbox", value: s, checked: s === m.site }), h("span", null, s)));
  const priv = h("input", { type: "checkbox", name: "private" });
  const scopeBoxes = SCOPES.map(([k, label, sub]) => h("label", { class: "chk" }, h("input", { type: "checkbox", value: k, checked: k === "read" }), h("span", null, h("b", null, label), h("small", null, sub))));
  const make = h("button", { type: "submit", class: "btn primary" }, "Make token");
  const form = h("form", { class: "af-col", novalidate: true },
    field("Name", name, "What the token is for, so the list says whose it is."),
    h("fieldset", { class: "af-set" }, h("legend", null, "Sites it may read"), siteBoxes),
    h("fieldset", { class: "af-set" }, h("legend", null, "Scopes"), scopeBoxes),
    h("label", { class: "chk" }, priv, h("span", null, h("b", null, "Private"), h("small", null, "may read files with visitor addresses; leave off unless a script needs them"))),
    h("div", null, make));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sites = siteBoxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.value);
    const scopes = scopeBoxes.map((l) => l.querySelector("input")).filter((c) => c.checked).map((c) => c.value);
    if (!name.value.trim()) { msg.say("Give the token a name first."); name.focus(); return; }
    if (!sites.length) { msg.say("Choose at least one site."); return; }
    if (!scopes.length) { msg.say("Choose at least one scope."); return; }
    make.disabled = true;
    const r = await call("tokens/create", { name: name.value.trim(), sites, private: priv.checked, scopes });
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
  return h("section", { class: "s" }, h("h2", null, "Tokens"),
    h("p", { class: "sub" }, "For a script or an AI assistant: no password, a token in the Authorization header. A token is shown once, when it is made; only a fingerprint of it is kept."),
    howTo("mcp", "How do I make a token for Claude or ChatGPT and connect it?"),
    shown, list, h("div", { class: "sheet tok-new" }, h("h3", null, "Make a token"), form), msg);
}
