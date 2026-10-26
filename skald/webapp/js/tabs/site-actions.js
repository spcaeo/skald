// A site's row menu (⋯) on Settings › Organisation › Sites: Pause/Resume, Remove/Restore,
// Clear data, Delete all data. Each opens a dialog that says what happens, what stays
// and how to undo it (the words: js/tabs/site-act-words.js). The dialog is in the
// address while it is open, #settings/org/sites?sact=<act>.<site> (js/routekeys.js,
// js/overlays.js), so a link opens it again. The danger actions are red and need the
// site's name typed; Clear data and Delete all data also need a box ticked. The helper
// checks the same rules (skald/site_actions_api.py).

import { h } from "../ui.js";
import { openDrawer } from "../drawer.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { input, why } from "./forms.js";
import { withCopy } from "../urlactions.js";
import * as W from "./site-act-words.js";

// The page's reload, set by sitesadmin.js, so a dialog a link opened redraws the list too.
let reloadPage = () => {};
export function setReload(fn) { reloadPage = typeof fn === "function" ? fn : () => {}; }

/* The ⋯ button and its list, for one site's row. */
export function siteMenu(site, { onDone = reloadPage } = {}) {
  const acts = W.menuFor(site, ME.role);
  if (!acts.length) return h("span");
  const list = h("div", { class: "acts site-menu", role: "menu", hidden: true, "aria-label": `Actions for ${site.name}` },
    acts.map((act) => {
      const b = h("button", { type: "button", role: "menuitem", class: `btn${W.DANGER.has(act) ? " danger" : ""}` }, W.LABEL[act]);
      b.addEventListener("click", () => { toggle(false); openAct(act, site, { onDone }); });
      return b;
    }),
    site.main ? h("p", { class: "note" }, W.MAIN_NOTE) : null);
  const more = h("button", { type: "button", class: "btn", "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": `Actions for ${site.name}`, title: "Pause, remove or delete" }, "⋯");
  function toggle(on) {
    list.hidden = !on;
    more.setAttribute("aria-expanded", on ? "true" : "false");
  }
  more.addEventListener("click", () => toggle(list.hidden));
  list.addEventListener("keydown", (e) => { if (e.key === "Escape") { toggle(false); more.focus?.(); } });
  return h("span", { class: "site-menu-wrap" }, more, list);
}

/* The address named a site's action: its dialog, or the plain line why not. */
export async function openSiteActKey(value) {
  if (!sessions()) return "Not available here.";
  const want = W.parseRoute(value);
  if (!want) return "That action is not one this page offers.";
  const r = await call("sites");
  if (!r.ok) return why(r, "The sites could not be loaded, so the dialog cannot open.");
  const site = (r.sites || []).find((s) => s.name === want.site);
  if (!site) return "That site is not one of this organisation's sites.";
  if (!W.menuFor(site, ME.role).includes(want.act)) return "Not available to your role, or not for this site now.";
  return openAct(want.act, site, { onDone: reloadPage });
}

/* The dialog for one action on one site. */
export function openAct(act, site, { onDone = reloadPage } = {}) {
  const t = W.words(act, site);
  const danger = W.DANGER.has(act);
  const said = h("p", { class: "td-said", role: "status", "aria-live": "polite" });
  const typed = W.TYPED.has(act) ? input({ name: "confirm", autocomplete: "off", placeholder: site.name, "aria-label": `Type ${site.name} to confirm` }) : null;
  const tick = W.TICKED.has(act) ? h("input", { type: "checkbox", name: "understood" }) : null;
  const go = h("button", { type: "button", class: `btn ${danger ? "danger" : "primary"}` }, t.button);
  const cancel = h("button", { type: "button", class: "btn" }, "Cancel");
  const instead = danger && W.menuFor(site, ME.role).includes("pause")
    ? h("button", { type: "button", class: "btn" }, "Pause instead") : null;
  const body = h("div", { class: `site-act site-act-${act}` },
    t.lede ? h("p", { class: "sub" }, t.lede) : null,
    t.parts.map(([head, text]) => h("div", { class: "site-act-part" }, h("h3", null, head), h("p", null, text))),
    instead ? h("div", { class: "acts" }, instead) : null,
    typed ? h("label", { class: "td-field" }, h("span", null, `Type ${site.name} to confirm`), typed) : null,
    tick ? h("label", { class: "site-act-tick" }, tick, ` ${t.tick}`) : null,
    said);
  const d = openDrawer({ title: t.title, subtitle: site.name, size: "md", key: "site-act", scope: "page", body, footer: [cancel, go],
    focus: typed || go, route: { key: "sact", value: W.routeValue(act, site.name) } });
  cancel.addEventListener("click", () => d.close());
  instead?.addEventListener("click", () => { d.close(); openAct("pause", site, { onDone }); });
  go.addEventListener("click", async () => {
    if (typed && typed.value.trim() !== site.name) { said.textContent = `Type ${site.name} exactly to confirm.`; typed.focus?.(); return; }
    if (tick && !tick.checked) { said.textContent = "Tick the box to say you understand what is deleted."; return; }
    const ask = { name: site.name };
    if (typed) ask.confirm = typed.value.trim();
    if (tick) ask.understood = true;
    go.disabled = true; cancel.disabled = true;
    said.textContent = act === "clear" || act === "delete" ? "Writing the archive, then deleting…" : "Saving…";
    const r = await call(W.API[act], ask);
    cancel.disabled = false;
    if (!r.ok) { go.disabled = false; said.replaceChildren(why(r)); said.classList.add("bad"); return; }
    said.classList.remove("bad");
    if (r.archive) said.replaceChildren(h("span", null, `${t.done} `), withCopy(h("code", null, r.archive), r.archive, { label: "the archive's path" }));
    else said.replaceChildren(act === "resume" && r.words ? r.words : t.done);
    go.remove();
    cancel.textContent = "Close";
    onDone();
  });
  return d;
}
