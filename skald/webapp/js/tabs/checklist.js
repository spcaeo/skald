// The first-run checklist on Overview (2.13): for a new site, what works and what
// is left - logs arriving, visits counted as people, countries, the script tag and
// a lead hook (both optional), a confirmed mail recipient and the privacy choice.
// Each open line is one plain sentence and a Set up button that opens a short
// guided dialog (js/tabs/setup-dialogs.js, loaded when first pressed); the
// server's own technical words stay folded under "For your server admin".
// Shown to owners and admins until every item that is not optional is done, or
// until they hide it for this site (kept in this browser). The items are worked
// out in js/setup-items.js from what the page has and two answers it already
// uses: GET integrations (the doctor's lines, each hook's state) and GET
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

const mayManage = () => sessions() && (["owner", "admin"].includes(ME.role) || ME.install_admin);
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

/* The checklist for Overview, or null. Drawn at once from the page's own data, then
   again when the two answers come (or left out when they say everything is done). */
export function setupChecklist(m) {
  if (DEMO.on || !mayManage() || setupHidden(m.site)) return null;
  const list = h("ol", { class: "su-list" });
  const left = h("span", { class: "su-left" });
  const hide = h("button", { type: "button", class: "btn su-hide" }, "Hide this list");
  const box = h("section", { class: "sheet su", "aria-label": "Set up this site" },
    h("div", { class: "su-head" }, h("h2", null, "Set up this site"), left, h("span", { class: "grow" }), hide),
    h("p", { class: "sub" }, "What works and what is left. Set up walks you through each step; a line ticks itself once Skald sees it working."), list);
  hide.addEventListener("click", () => { store.set(KEY(m.site), true); box.remove(); });

  // A Set up button: its dialog, then both answers asked again when it closes.
  async function setUp(item, btn) {
    btn.disabled = true;
    try {
      const { openSetup } = await import("./setup-dialogs.js");
      await openSetup(item.act, m.site, { item, onClose: () => refresh() });
    } finally { btn.disabled = false; }
  }
  const draw = (items) => {
    const todo = items.filter((i) => !i.optional && i.state !== "done").length;
    left.textContent = todo ? `${todo} of ${items.filter((i) => !i.optional).length} left` : "All set";
    list.replaceChildren(...items.map((i) => row(i, { manage: true, onSetUp: setUp })));
  };
  const show = (got) => {
    const items = setupItems(m, got);
    if (setupDone(items)) { box.remove(); return; }
    draw(items);
    box.hidden = false;
  };
  const refresh = () => ask(m.site, true).then(show);
  box.refresh = refresh;
  // Hidden until the answers say something is left, so a site that is set up never flashes a list.
  const kept = answers.get(m.site);
  if (kept) {
    const items = setupItems(m, kept.got);
    if (setupDone(items)) return null;
    draw(items);
  } else box.hidden = true;
  ask(m.site).then(show);
  return box;
}
