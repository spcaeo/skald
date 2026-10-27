// The "Set up <site>" checklist (2.13; v2, 2026-10-26): for a site, what works and what is
// left - logs arriving, visits counted as people, countries, the script tag, a lead hook and
// Search Console (the last three optional), a confirmed mail recipient and the privacy choice.
//
// v2 (the owner: "this has too many buttons. I don't know where I should do, what I should
// do"): one title, one count ("2 left, 1 optional"), one button, "Finish set-up (2 left)",
// which opens one dialog that asks "Who will do it?" (setup-finish.js; setup=finish). Each open
// line is one button as a whole: the same dialog for that line only (setup=finish-<act>). Done
// lines fold into one line, "4 done ✓". The server's technical words are in each line's own
// dialog, never on the list.
//
// Two places, for owners and admins:
//   Overview              until every item that is not optional is done, or until they
//                         press "Hide on Overview" (kept in this browser, for this site)
//   Settings › To do      always (settings-todo.js, set-todo.js): the open lines among the
//                         rest of what needs the reader. Hiding it on Overview never hides it there.
// The items are worked out in js/setup-items.js from what the page has and two answers
// it already uses: GET integrations (the doctor's lines, each hook's state) and GET
// settings. A dialog closed asks both again, so a fixed line ticks itself.

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { DEMO } from "../demo.js";
import { store } from "../extras.js";
import { setupItems, setupDone, agentJobsLeft } from "../setup-items.js";
import { openLines, leftWords, finishWords, verbOf } from "../settings-todo.js";
import { ic, doneFold as uiDoneFold } from "./set-ui.js";
import { liveBadge } from "./setup-live.js";

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
    yourtools: integ.ok ? integ.yourtools || null : null,
  };
  answers.set(site, { at: Date.now(), got });
  return got;
}
/* The lines for a site, from the answers (asked again when fresh, or after 5 minutes). */
export async function checkItems(m, fresh = false) {
  try { return setupItems(m, await ask(m.site, fresh)); } catch { return setupItems(m, {}); }
}
/* The lines as the page knows them now, without asking (null when it has not asked yet). */
export const keptItems = (m) => (answers.get(m.site) ? setupItems(m, answers.get(m.site).got) : null);

/* The line a Set up dialog fixes, for a dialog opened from a link (its words for the server admin). */
export async function itemFor(m, act) {
  try { return setupItems(m, await ask(m.site)).find((i) => i.act === act) || null; } catch { return null; }
}
/* The open lines an AI agent can do (setup=all from a link), as job ids. */
export async function agentJobsFor(m) {
  try { return agentJobsLeft(setupItems(m, await ask(m.site))); } catch { return []; }
}
/* Every list on the page asks again (a dialog opened from a link closed). */
export function refreshChecklists() {
  for (const box of [...drawn]) { if (box.isConnected) box.refresh(); else drawn.delete(box); }
}

/* Finish set-up's dialog, for every open line (only "") or one. */
export async function openFinish(m, items, { only = "", onDone = refreshChecklists } = {}) {
  if (DEMO.on) return null;
  const { finishDialog } = await import("./setup-finish.js");
  return finishDialog(m.site, items, { only, onDone });
}

/* One line: its mark, title and plain sentence. An open line an admin can do is one button as
   a whole (onOpen); a done or waiting line is plain. */
export function row(i, { onOpen = null } = {}) {
  const open = onOpen && i.act && i.state !== "done";
  const kids = [h("span", { class: "su-mark", "aria-hidden": "true" }),
    h("span", { class: "su-txt" }, h("span", { class: "su-t" }, h("b", null, i.title), i.optional ? h("small", { class: "su-opt" }, "optional") : null,
      h("span", { class: "vh" }, `: ${MARK[i.state]}.`)), h("span", { class: "su-says" }, String(i.says || "").replace(/^Optional\. /, ""))),
    open ? h("span", { class: "su-go", "aria-hidden": "true" }, verbOf(i), ic("next", "ic-w su-chev")) : null];
  if (!open) return h("li", { class: `su-i su-${i.state}`, "data-item": i.id }, h("div", { class: "su-row" }, ...kids));
  const b = h("button", { type: "button", class: "su-row", "aria-label": `${verbOf(i)}: ${i.title}. ${i.says}` }, ...kids);
  b.addEventListener("click", () => onOpen(i, b));
  return h("li", { class: `su-i su-${i.state} su-open`, "data-item": i.id }, b);
}

/* The open lines, then the done ones folded into "4 done" (a check icon, no glyph). */
// ui/fold.js doneFold: "N done" with the tick; its body is the one list of the done lines.
export function doneFold(done) {
  const d = uiDoneFold(done, (_, n) => (n ? null : h("ol", { class: "su-list" }, done.map((i) => row(i)))));
  d?.classList.add("su-fold");
  return d;
}
export function lines(items, { onOpen = null } = {}) {
  const open = items.filter((i) => i.state !== "done");
  const done = items.filter((i) => i.state === "done");
  return [open.length ? h("ol", { class: "su-list" }, open.map((i) => row(i, { onOpen }))) : null,
    doneFold(done)];
}

/* The Finish set-up button, with what is left on it. */
export function finishButton(items, onClick) {
  const n = openLines(items).length;
  const b = h("button", { type: "button", class: "btn primary su-finish", hidden: !n }, finishWords(items));
  b.addEventListener("click", () => onClick(b));
  return b;
}

/* The checklist on Overview, or null. Hidden once done or when the reader hides it. Drawn at
   once from the page's own data when the answers are kept, then again when they come.
   where: "overview" (the only place since v2; Settings › To do draws its own). */
export function setupChecklist(m, { where = "overview" } = {}) {
  const always = where !== "overview";
  if (DEMO.on ? !always || !DEMO.api.setup.settings : !mayManage() || (!always && setupHidden(m.site))) return null;
  const left = h("span", { class: "su-left" });
  const hide = always ? null : h("button", { type: "button", class: "btn su-hide" }, "Hide on Overview");
  const slot = h("div", { class: "su-body" });
  let items = [];
  const finish = h("span");
  // 2.43: the site's live state beside the title (setup-live.js), the same as Settings › Sites.
  const head = h("div", { class: "su-head" }, h("h2", null, `Set up ${m.site}`), left, DEMO.on ? null : liveBadge(m.site),
    h("span", { class: "grow" }), finish, hide);
  const box = h("section", { class: `sheet su${always ? " su-always" : ""}`, "aria-label": `Set up ${m.site}` }, head, slot);
  if (hide) hide.addEventListener("click", () => { store.set(KEY(m.site), true); box.remove(); });

  const go = async (i, btn) => {
    if (DEMO.on) { btn.replaceWith(h("p", { class: "note" }, "In the demo, setting up needs a running Skald.")); return; }
    await openFinish(m, items, { only: i ? i.act : "" });
  };
  const draw = (list) => {
    items = list;
    left.textContent = leftWords(items);
    finish.replaceChildren(finishButton(items, (b) => go(null, b)));
    slot.replaceChildren(...lines(items, { onOpen: go }).filter(Boolean));
  };
  const show = (got) => {
    const list = setupItems(m, got);
    if (!always && setupDone(list)) { box.remove(); return; }
    draw(list);
    box.hidden = false;
  };
  const refresh = () => ask(m.site, true).then(show);
  box.refresh = refresh;
  drawn.add(box);
  // Hidden until the answers say something is left, so a site that is set up never flashes a list.
  const kept = answers.get(m.site);
  if (kept) {
    const list = setupItems(m, kept.got);
    if (!always && setupDone(list)) return null;
    draw(list);
  } else if (always) draw(setupItems(m, {}));
  else box.hidden = true;
  ask(m.site).then(show);
  return box;
}

/* For the To do page: a list drawn by the page that asks again when a dialog closes. */
export function watchList(el, refresh) { el.refresh = refresh; drawn.add(el); }
