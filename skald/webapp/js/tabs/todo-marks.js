// The marks on Insights' to-dos and on Not found's old addresses (2.35): "done",
// "not now", "fixed". They live in Skald's own storage (accounts.sqlite, the helper's
// settings/todos: skald/todo_api.py), never in this browser, so everyone on the
// team sees the same list. The data files (todos.json, lost_pages.json) say what the
// marks were at the last data update and carry the re-checks; this says what they are
// now, so a mark shows at once and its re-check follows on the next update.
//
//   loadMarks()            GET settings/todos once per page load: {ok, marks, can_mark, mail, team, why}
//   markItem(item, state)  POST settings/todos; the answer's marks replace ours
//   markOf(item, fileMark) the mark now: the helper's when it answered, else the file's
//   sendTodo(item, to)     POST settings/todo-send: one to-do by mail to a team member

import { call } from "./ipmanager.js";
import { sessions } from "../access.js";
import { DEMO } from "../demo.js";

// `changes`: the page changes tracked now (Traffic > Pages > a page: js/tabs/pagechange.js).
// 2.41: `fixes` the AI agent's newest report per to-do ({state, change, files, left, notes, at}),
// `server` what the site check found about the web server (Fix this > Me's lines), `line`
// the site's newest to-do line (never its code: owners and admins only).
export const MARKS = { loaded: false, ok: false, marks: {}, changes: [], can_mark: false, mail: null, team: [], why: "",
  fixes: {}, server: {}, line: null };
let pending = null;

// Why nothing can be marked here, in plain words.
export const WHY = {
  basic: "Marking needs accounts (signing in): this Skald runs without them, so the list is shown but nothing can be marked or sent.",
  demo: "In the demo, marking and sending need a running Skald.",
  viewer: "Only an owner or an admin can mark these. You are signed in as a viewer.",
};

export function loadMarks(force = false) {
  if (MARKS.loaded && !force) return Promise.resolve(MARKS);
  if (pending) return pending;
  const asked = (async () => {
    if (DEMO.on) return Object.assign(MARKS, { loaded: true, ok: false, why: WHY.demo });
    if (!sessions()) return Object.assign(MARKS, { loaded: true, ok: false, why: WHY.basic });
    const r = await call("settings/todos");
    if (!r.ok) return Object.assign(MARKS, { loaded: true, ok: false, why: r.error || "The marks could not be read." });
    return Object.assign(MARKS, { loaded: true, ok: true, marks: r.marks || {}, changes: r.changes || [], can_mark: !!r.can_mark,
      mail: r.mail || null, team: r.team || [], why: r.can_mark ? "" : WHY.viewer,
      fixes: r.fixes || {}, server: r.server || {}, line: r.line || null });
  })();
  pending = asked;
  asked.finally(() => { if (pending === asked) pending = null; });
  return asked;
}

/* The mark on an item now: {state, day} or null (open). */
export function markOf(item, fileMark = null) {
  if (MARKS.ok) {
    const m = MARKS.marks[item];
    return m && m.state !== "open" ? m : null;
  }
  return fileMark && fileMark.state !== "open" ? fileMark : null;
}

export async function markItem(item, state) {
  const r = await call("settings/todos", { item, state });
  if (r.ok && r.marks) MARKS.marks = r.marks;
  return r;
}

/* Who a to-do can be sent to, or the reason it cannot be sent: {ok, team, why}. */
export function sendable() {
  if (!MARKS.ok) return { ok: false, team: [], why: MARKS.why };
  if (!MARKS.can_mark) return { ok: false, team: [], why: "Only an owner or an admin can send a to-do." };
  if (!MARKS.mail?.ready) return { ok: false, team: [], why: MARKS.mail?.why || "No mail server is set up. An admin sets one in Settings > Mail & reports." };
  if (!MARKS.team.length) return { ok: false, team: [], why: "Nobody on this site's team has confirmed their account yet. Invite someone in Settings > Team." };
  return { ok: true, team: MARKS.team, why: "" };
}

export const sendTodo = (item, to) => call("settings/todo-send", { item, to });

// ---- 2.41: Fix this (js/tabs/todo-fix.js) -------------------------------------------
//   makeTodoLine(items)   POST settings/todo-agent {act: "make", items}: the line for the AI agent
//   lineStatus(link)      POST settings/todo-agent {act: "status", link_id}
//   cancelTodoLine(link)  POST settings/todo-agent {act: "cancel", link_id}
//   todoRows(id)          GET settings/todo-rows?item=<id>: every row (for Me's lines and the CSV)
export const makeTodoLine = (items) => call("settings/todo-agent", { act: "make", items });
export const lineStatus = (link) => call("settings/todo-agent", { act: "status", link_id: link });
export const cancelTodoLine = (link) => call("settings/todo-agent", { act: "cancel", link_id: link });
export const todoRows = (id) => call(`settings/todo-rows?item=${encodeURIComponent(id)}`);

/* The AI agent's newest report on a to-do, or null. */
export const fixOf = (id) => (MARKS.ok ? MARKS.fixes[id] || null : null);
