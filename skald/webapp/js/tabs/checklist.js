// The "Set up <site>" checklist (2.13; 2.21: named for its site, and also on Settings ›
// Connections): for a site, what works and what is left - logs arriving, visits counted
// as people, countries, the script tag and a lead hook (both optional), a confirmed mail
// recipient and the privacy choice. Each open line is one plain sentence and a Set up
// button that opens a short guided dialog (js/tabs/setup-dialogs.js, loaded when first
// pressed; in the address as setup=<item>&step=<n>); the server's own technical words
// stay folded under "For your server admin". At the top, "Send set-up to someone" (2.30,
// setup=pack): the whole set-up in one zip, mailed or saved (setup-pack.js).
//
// Two places, for owners and admins:
//   Overview              until every item that is not optional is done, or until they
//                         press "Hide on Overview" (kept in this browser, for this site)
//   Settings › Connections  always, at the top: a finished list shows every tick and
//                         "All set". Hiding it on Overview never hides it here.
// The items are worked out in js/setup-items.js from what the page has and two answers
// it already uses: GET integrations (the doctor's lines, each hook's state) and GET
// settings. A dialog closed asks both again, so a fixed line ticks itself.

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { DEMO } from "../demo.js";
import { store } from "../extras.js";
import { setupItems, setupDone } from "../setup-items.js";
import { adminFold } from "./setup-common.js";

const KEY = (site) => `ti-setup-hidden:${site}`;
const MARK = { done: "Done", todo: "To do", wait: "Waiting", unknown: "Not checked" };
const answers = new Map();   // site -> {at, got}: asked again after 5 minutes, not on every redraw
const drawn = new Set();     // the lists on the page, asked again when a dialog closes

export const mayManage = () => sessions() && (["owner", "admin"].includes(ME.role) || ME.install_admin);
// Hidden on Overview only (the reader's choice, in this browser).
export const setupHidden = (site) => !!store.get(KEY(site), false);
// The palette's "Setup checklist": shown again, on Overview.
export function showSetup(site) { store.set(KEY(site), false); answers.delete(site); S.set({ tab: "overview/summary" }); }

async function ask(site, fresh = false) {
  const kept = answers.get(site);
  if (!fresh && kept && Date.now() - kept.at < 300000) return kept.got;
  const [set, integ] = await Promise.all([call("settings"), call(`integrations?site=${encodeURIComponent(site)}`)]);
  const got = {
    settings: set.ok ? set.settings : null, waiting: set.ok ? set.mail_waiting || [] : [],
    status: integ.ok ? integ.status || [] : null, tools: integ.ok ? integ.tools || [] : null,
  };
  answers.set(site, { at: Date.now(), got });
  return got;
}

/* The line a Set up dialog fixes, for a dialog opened from a link (its words for the server admin). */
export async function itemFor(m, act) {
  try { return setupItems(m, await ask(m.site)).find((i) => i.act === act) || null; } catch { return null; }
}
/* Every list on the page asks again (a dialog opened from a link closed). */
export function refreshChecklists() {
  for (const box of [...drawn]) { if (box.isConnected) box.refresh(); else drawn.delete(box); }
}

/* One line: its mark, title, the plain sentence, and for an admin with an open
   item the Set up button (and the technical words folded). */
export function row(i, { manage = false, onSetUp = null } = {}) {
  const open = manage && i.act && i.state !== "done";
  const btn = open ? h("button", { type: "button", class: "btn su-go", "aria-label": `Set up: ${i.title}` }, "Set up") : null;
  if (btn && onSetUp) btn.addEventListener("click", () => onSetUp(i, btn));
  return h("li", { class: `su-i su-${i.state}`, "data-item": i.id },
    h("span", { class: "su-mark", "aria-hidden": "true" }),
    h("div", null, h("b", null, i.title), i.optional ? h("small", { class: "su-opt" }, " optional") : null,
      h("span", { class: "vh" }, `: ${MARK[i.state]}.`), h("p", null, i.says),
      btn ? h("div", { class: "su-acts" }, btn) : null,
      open ? adminFold(i.tech) : null));
}

/* The checklist, or null. where: "overview" (hidden once done or when the reader hides it)
   or "connections" (always, ticks and all). Drawn at once from the page's own data, then
   again when the two answers come. */
export function setupChecklist(m, { where = "overview" } = {}) {
  const always = where === "connections";
  // The demo: on Connections only, from the demo's own answers; its Set up buttons say why not.
  if (DEMO.on ? !always || !DEMO.api.setup.settings : !mayManage() || (!always && setupHidden(m.site))) return null;
  const list = h("ol", { class: "su-list" });
  const left = h("span", { class: "su-left" });
  const hide = always ? null : h("button", { type: "button", class: "btn su-hide" }, "Hide on Overview");
  // 2.30: the whole set-up, mailed or saved as one zip (setup=pack, setup-dialogs.js).
  const pack = h("button", { type: "button", class: "btn primary su-pack-go" }, "Send set-up to someone");
  const head = h("div", { class: "su-head" }, h("h2", null, `Set up ${m.site}`), left, h("span", { class: "grow" }), pack,
    hide ? h("span", { class: "su-hide-w" }, hide, h("small", { class: "su-where" }, "Always in Settings › Connections")) : null);
  const box = h("section", { class: `sheet su${always ? " su-always" : ""}`, "aria-label": `Set up ${m.site}` }, head,
    h("p", { class: "sub" }, always ? "What works and what is left for this site. Set up walks you through each step; a line ticks itself once Skald sees it working."
      : "What works and what is left. Set up walks you through each step; a line ticks itself once Skald sees it working."), list);
  if (hide) hide.addEventListener("click", () => { store.set(KEY(m.site), true); box.remove(); });

  // A Set up button: its dialog, then both answers asked again when it closes.
  async function setUp(item, btn) {
    if (DEMO.on) { btn.replaceWith(h("p", { class: "note" }, "In the demo, setting up needs a running Skald.")); return; }
    btn.disabled = true;
    try {
      const { openSetup } = await import("./setup-dialogs.js");
      await openSetup(item.act, m.site, { item, onClose: () => refresh() });
    } finally { btn.disabled = false; }
  }
  pack.addEventListener("click", () => setUp({ act: "pack" }, pack));
  const draw = (items) => {
    const todo = items.filter((i) => !i.optional && i.state !== "done").length;
    left.textContent = todo ? `${todo} of ${items.filter((i) => !i.optional).length} left` : "All set";
    list.replaceChildren(...items.map((i) => row(i, { manage: true, onSetUp: setUp })));
  };
  const show = (got) => {
    const items = setupItems(m, got);
    if (!always && setupDone(items)) { box.remove(); return; }
    draw(items);
    box.hidden = false;
  };
  const refresh = () => ask(m.site, true).then(show);
  box.refresh = refresh;
  drawn.add(box);
  // On Overview, hidden until the answers say something is left, so a site that is set up
  // never flashes a list. On Connections, drawn at once from what the page has.
  const kept = answers.get(m.site);
  if (kept) {
    const items = setupItems(m, kept.got);
    if (!always && setupDone(items)) return null;
    draw(items);
  } else if (always) draw(setupItems(m, {}));
  else box.hidden = true;
  ask(m.site).then(show);
  return box;
}
