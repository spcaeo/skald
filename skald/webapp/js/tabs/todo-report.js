// An AI agent's report on one to-do (2.41): what it did, the exact change it made (with the
// copy icon), the files, and the rows it left for you with why. Shown in Fix this's watch
// (todo-fix.js) and on the to-do itself (todos.js), from settings/todos' `fixes` and
// settings/todo-agent's `reports` (todo_marks.keep_fix). Light: no other tab's module.

import { h } from "../ui.js";
import { time } from "../tz.js";
import { withCopy } from "../urlactions.js";

export const STATE_WORDS = { done: "Done", partly: "Partly done", left: "Left for you" };

/* The report's body: notes, files, the change (folded), the rows left (folded). */
export function reportParts(fix) {
  return [
    fix.notes ? h("p", null, withCopy(fix.notes, fix.notes)) : null,
    fix.files?.length ? h("p", { class: "note" }, "Files: ", fix.files.map((f, i) => [i ? ", " : "", withCopy(h("code", null, f), f)])) : null,
    fix.change ? h("details", { class: "fold fx-change" }, h("summary", null, "The change it made"),
      withCopy(h("pre", { class: "fx-pre" }, fix.change), fix.change, { label: "the change", tag: "div" })) : null,
    fix.left?.length ? h("details", { class: "fold" }, h("summary", null, `Left for you (${fix.left.length})`),
      h("ul", { class: "fx-left" }, fix.left.slice(0, 200).map((x) => h("li", null, withCopy(h("code", null, x.row), x.row), x.why ? ` ${x.why}` : "")))) : null];
}

/* One line of the watch: waiting, or the report. */
export function reportBox(t, fix) {
  if (!fix) return h("li", { class: "wait" }, h("span", { class: "cn-tick", "aria-hidden": "true" }, "…"), `${t.title}: waiting for the agent's report`);
  return h("li", { class: fix.state === "done" ? "ok" : "warn" },
    h("span", { class: "cn-tick", "aria-hidden": "true" }, fix.state === "done" ? "✓" : "!"),
    h("div", { class: "fx-rep" },
      h("p", null, h("b", null, `${t.title}: ${STATE_WORDS[fix.state] || fix.state}`), fix.at ? h("small", null, ` at ${time(fix.at, { label: false })}`) : null),
      ...reportParts(fix)));
}

/* On a to-do's card: "Your AI agent: Done at 10:42", and the same parts. */
export function agentNote(fix) {
  if (!fix) return null;
  const who = String(fix.by || "").startsWith("mcp:") ? "Your AI assistant (MCP)" : "Your AI agent";
  return h("div", { class: `fx-card fx-${fix.state}` },
    h("p", null, h("b", null, `${who}: ${STATE_WORDS[fix.state] || fix.state}`), fix.at ? h("small", { class: "muted" }, ` ${time(fix.at, { label: false, date: true })}`) : null),
    ...reportParts(fix));
}
