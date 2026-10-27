// Settings › To do (v2, the landing page of Settings): one list of what needs this reader now,
// most important first (settings-todo.js works it out). Each row is one sentence and one
// button; the whole row is the button. At the top, "Find a setting" (the Ctrl K finder).
//
//   This site      the set-up lines still open, "Finish set-up (N left)" (setup-finish.js),
//                  done lines folded into "N done"
//   Organisation   sites waiting for proof or paused, the plan's usage, invites, old tokens
//   You            two-step sign-in off
//
// Nothing left: "Nothing needs you. Everything is set up for <site>." and what works, folded.

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { ME, sessions, isViewer } from "../access.js";
import { DEMO } from "../demo.js";
import { checkItems, keptItems, mayManage, openFinish, finishButton, row, doneFold, watchList, refreshChecklists } from "./checklist.js";
import { ic, pill } from "./set-ui.js";
import { todoItems, openLines, leftWords } from "../settings-todo.js";

const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const SEARCH = I('<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14"/>');
const LEVEL = { bad: I('<circle cx="8" cy="8" r="6"/><path d="M8 4.8v3.6M8 11h.01"/>'),
  warn: I('<path d="M8 2.2 14 13H2z"/><path d="M8 6.5v2.8M8 11.2h.01"/>'),
  info: I('<circle cx="8" cy="8" r="6"/><path d="M8 7.3v3.7M8 5h.01"/>') };
const DONE = I('<circle cx="8" cy="8" r="6.2"/><path d="M5.2 8.2 7.2 10.2 10.9 6.1"/>');

/* "Find a setting": opens the Ctrl K finder (keys.js), which searches every page and action. */
export function finder() {
  const b = h("button", { type: "button", class: "todo-find", "aria-keyshortcuts": "Control+K Meta+K" },
    h("span", { class: "todo-find-i", html: SEARCH }), h("span", null, "Find a setting"), h("kbd", null, "Ctrl K"));
  b.addEventListener("click", () => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true })));
  return b;
}

/* A row that is a link: its sign, its sentence, its one word. */
function linkRow(x) {
  const a = h("a", { class: `todo-row lv-${x.level}`, href: x.href, "aria-label": `${x.verb}: ${x.says}` },
    h("span", { class: "todo-i", html: LEVEL[x.level] }), h("span", { class: "todo-says" }, x.says), h("span", { class: "todo-go", "aria-hidden": "true" }, x.verb, ic("next", "ic-w su-chev")));
  a.addEventListener("click", (e) => {
    if (e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    const [tab, q = ""] = x.href.slice(1).split("?");
    S.set({ tab, ...Object.fromEntries(new URLSearchParams(q)) });
  });
  return h("li", null, a);
}
const card = (cls, title, ...kids) => h("section", { class: `todo-card ${cls}` }, h("h2", null, title), ...kids);

export function todoPage(m) {
  const manage = DEMO.on ? !!DEMO.api?.setup?.settings : mayManage();
  const box = h("div", { class: "todo" }, h("p", { class: "empty" }, "Looking at what needs you..."));
  let items = [];

  const site = (rows) => {
    const open = openLines(items);
    if (!manage || (!open.length && !rows.length)) return null;
    const go = (i) => openFinish(m, items, { only: i ? i.act : "", onDone: () => { refreshChecklists(); } });
    const finish = finishButton(items, () => (DEMO.on ? null : go(null)));
    finish.classList.add("set-primary");   // the page's one primary, beside the title (settings-frame.js)
    if (DEMO.on) finish.disabled = true;
    const required = items.filter((i) => !i.optional);
    const optional = items.filter((i) => i.optional && i.state !== "done");
    const done = items.filter((i) => i.state === "done");
    const onOpen = DEMO.on ? null : (i) => go(i);
    return h("section", { class: "todo-card tc-site" },
      h("div", { class: "todo-head" }, h("h2", null, m.site), pill(open.some((i) => !i.optional) ? "warn" : "good", leftWords(items)), h("span", { class: "grow" }), finish),
      h("ol", { class: "su-list" }, required.filter((i) => i.state !== "done").map((i) => row(i, { onOpen })), optional.map((i) => row(i, { onOpen }))),
      doneFold(done));
  };

  function draw(got) {
    const list = todoItems({ setup: items, manage, accounts: sessions(), totpOn: ME.totp_on !== false, saas: !!ME.saas, plan: ME.plan,
      sites: got.sites?.ok ? got.sites.sites : null, invites: got.team?.ok ? got.team.invites : null, tokens: got.tokens?.ok ? got.tokens.tokens : null });
    const org = list.filter((x) => x.scope === "org"), you = list.filter((x) => x.scope === "you");
    const needs = list.filter((x) => x.scope !== "site" || !x.optional);
    const done = items.filter((i) => i.state === "done");
    const parts = [];
    if (!needs.length) {
      parts.push(h("div", { class: "todo-clear", role: "status" }, h("span", { class: "todo-clear-i", html: DONE }),
        h("div", null, h("p", null, h("strong", null, "Nothing needs you.")),
          manage ? h("p", null, `Everything is set up for ${m.site}.`) : null,
          doneFold(done))));
      const optional = items.filter((i) => i.optional && i.state !== "done");
      if (manage && optional.length && !DEMO.on) parts.push(card("tc-site", "You can also add",
        h("ol", { class: "su-list" }, optional.map((i) => row(i, { onOpen: (x) => openFinish(m, items, { only: x.act }) })))));
    } else {
      parts.push(site(needs.filter((x) => x.scope === "site")));
      if (org.length) parts.push(card("tc-org", "Organisation", h("ul", { class: "todo-list" }, org.map(linkRow))));
      if (you.length) parts.push(card("tc-you", "You", h("ul", { class: "todo-list" }, you.map(linkRow))));
    }
    box.replaceChildren(...parts.filter(Boolean));
  }

  let last = {};
  const load = async (fresh = false) => {
    const ask = manage && !DEMO.on;
    const [setup, sites, team, tokens] = await Promise.all([manage ? checkItems(m, fresh) : [],
      ask ? call("sites") : null, ask && !isViewer() ? call("team") : null, ask ? call("tokens") : null]);
    items = setup;
    last = { sites, team, tokens };
    draw(last);
  };
  // Drawn at once from what the page already has, then again when the answers come.
  const kept = manage ? keptItems(m) : [];
  if (kept) { items = kept; draw(last); }
  watchList(box, () => load(true));
  load();
  return [finder(), box];
}
