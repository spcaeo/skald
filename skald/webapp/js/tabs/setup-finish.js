// "Finish set-up" (v2): one button, one dialog that asks first "Who will do it?" (the owner,
// 2026-10-26: "When clicking one button, inside, it should ask what are you trying to do").
// It replaces the checklist's "Set up everything left with your AI agent", "Send set-up to
// someone" and each line's own Set up button. The question is the app's one who-step,
// js/ui/who.js whoDialog (docs/UI-RULES.md rule 2): Me / My developer / My AI agent, the
// choice in the address and remembered per person in this browser.
//
//   Me             the open lines, each opening its own steps (setup=<act>&by=me)
//   My developer   the set-up in one mail or one zip (setup-pack.js); a missing country
//                  file: the mail to the person who runs the Skald server
//   My AI agent    "What it does" (each open line an agent can do, ticked), then ui/who.js
//                  agentPath: the agent tiles, its line (sites/agentlink with the jobs) and
//                  its watch, in this dialog
//
// In the address: setup=finish (every open line) or setup=finish-<act> (one line, from its
// row), with by=me|dev|agent inside it, and agent=, link= once the agent path has them.
// setup=finish-tools: Leads & tools' "Connect a tool", for the lead hook and each of your own
// tools (one line each, act connect-tools; their developer mail: yourtools.js toolsMail).

import { h } from "../ui.js";
import { whoDialog, agentPath } from "../ui/who.js";
import { jobsInOrder, jobOf } from "./agent-words.js";
import { packBox } from "./setup-pack.js";
import { AGENT_JOBS } from "../setup-items.js";
import { openLines, verbOf } from "../settings-todo.js";
import { ic } from "./set-ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";

// Lines a developer (or the server admin) can do from the zip or a mail.
const TECH = ["logs", "script", "lead", "rsc", "assets", "countries"];
// only= that names several acts: Connect a tool (Leads & tools) is the lead hook and your tools.
export const GROUPS = { tools: ["lead", "connect-tools"] };
const wanted = (only, act) => !only || (GROUPS[only] ? GROUPS[only].includes(act) : act === only);

/* The dialog. items: the set-up lines (setup-items.js); only: one line's act, or "".
   onDone: a dialog it opened was closed (the lists ask again). The address's by= is read by
   the who-step itself. */
export async function finishDialog(site, items, { only = "", onDone = null } = {}) {
  let lines = openLines(items).filter((i) => wanted(only, i.act));
  // One line asked for that is done already (Data › Send logs: "Change how visits arrive").
  const first = GROUPS[only]?.[0] || only;
  if (only && !lines.length) lines = [{ id: first, act: first, title: jobOf(first)?.title || "Set it up", says: "" }];
  const jobs = jobsInOrder(lines.map((i) => i.act).filter((a) => AGENT_JOBS.includes(a)));
  const tech = lines.filter((i) => TECH.includes(i.act));
  const tools = lines.filter((i) => i.act === "connect-tools");
  const route = { key: "setup", value: only ? `finish-${only}` : "finish" };
  const title = only === "tools" ? "Connect a tool" : only && lines[0] ? lines[0].title : `Finish setting up ${site}`;
  let d = null;

  // Hand over to a line's own dialog: it opens over this one, which then goes quietly (the
  // address names the new one).
  async function handOver(act, opts, line = null) {
    const { openSetup } = await import("./setup-dialogs.js");
    await openSetup(act, site, { item: line || lines.find((i) => i.act === act) || null, onClose: onDone, ...opts });
    d?.close({ instant: true, silent: true, focusBack: false });
  }
  const lineButton = (i, n) => {
    const b = h("button", { type: "button", class: "fin-line", "data-act": i.act },
      h("span", { class: "fin-n" }, String(n + 1)), h("span", { class: "fin-t" }, h("b", null, i.title), i.says ? h("small", null, i.says) : null),
      h("span", { class: "fin-go" }, verbOf(i), ic("next", "ic-w su-chev")));
    b.addEventListener("click", () => handOver(i.act, AGENT_JOBS.includes(i.act) ? { by: "me", start: 1 } : {}, i));
    return b;
  };

  // Me: the lines in order, each opening its own steps.
  const me = () => [h("p", { class: "fin-pick" }, lines.length > 1 ? "Skald walks you through each one. Start with the first:" : "Skald walks you through it:"),
    h("div", { class: "fin-lines" }, lines.map(lineButton))];
  // My developer: the set-up pack; the missing country file is a mail to the server's admin.
  const dev = async () => {
    if (only === "countries") {
      const b = h("button", { type: "button", class: "btn" }, "Write the mail");
      b.addEventListener("click", () => handOver("countries", { start: 1 }));
      return [h("p", null, "The country file is on the server that runs Skald. Skald writes the mail for the person who runs it."), b];
    }
    if (!tools.length) return packBox(site);
    // Your own tools: what to make and where to paste it (never a key in a mail).
    const yt = await import("./yourtools.js");
    const r = await call(yt.TOOLS_PATH);
    const want = new Set(tools.map((i) => i.id.replace(/^tool-/, "")));
    const list = r.ok ? (r.tools || []).filter((t) => want.has(t.id)) : [];
    return [tech.length ? packBox(site) : null,
      list.length ? [h("p", null, `For ${list.map((t) => t.name).join(" and ")}: send them this. It says which key to make and where to paste it; it never asks for a key by mail.`),
        h("div", { class: "acts" }, yt.copyMailButton(site, list))] : h("p", { class: "msg err" }, why(r, "Your tools could not be loaded."))];
  };
  // My AI agent: what it does (when there is a choice), then the agent path.
  const picked = [...jobs];
  const agentLine = agentPath({ site, jobs: picked, route });
  const agent = async () => {
    const box = jobs.length > 1 ? h("fieldset", { class: "af-set fin-jobs" }, h("legend", null, `What it does (${jobs.length})`),
      jobs.map((id) => {
        const line = lines.find((i) => i.act === id);
        const cb = h("input", { type: "checkbox", checked: true, value: id });
        cb.addEventListener("change", () => {
          const now = jobsInOrder(cb.checked ? [...picked, id] : picked.filter((x) => x !== id));
          if (!now.length) { cb.checked = true; return; }   // at least one job
          picked.splice(0, picked.length, ...now);
          d?.who?.pick("agent");                            // its line is for these jobs
        });
        return h("label", { class: "chk" }, cb, h("span", null, line?.title || id));
      })) : null;
    return [box, await agentLine()];
  };

  const paths = {};
  if (lines.length) paths.me = me;
  if (tech.length || tools.length) paths.dev = dev;
  if (jobs.length) paths.agent = agent;
  d = await whoDialog({ title, subtitle: only ? "" : lines.map((i) => i.title).join(" · "), route, paths, drawerKey: "setup-finish",
    top: lines.length ? null : h("p", { class: "state ok" }, "Nothing is left to set up."), onClose: onDone });
  d.el?.classList?.add("fin-dw");
  return d;
}
