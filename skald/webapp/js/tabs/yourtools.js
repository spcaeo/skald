// From your tools (docs/TOOLS.md): the figures a person's OWN tools give (Google Analytics...),
// with their own keys, kept apart from Skald's own counts. This file holds the parts of it the
// pages share:
//
//   toolRows(r, open)       Settings › Leads & tools: one row per tool, its pill and last answer
//   toolDrawer(t, site)     the drawer of one tool (tool=your-<id> in the address): its state,
//                           "Counted from", the key (where it lives and whose it is, never the
//                           key), the options, Paste a new key, Sync now; one primary (the
//                           key pasted, else Save when an option changed, else Sync now),
//                           and Pause and Remove the key in a quieter row under it
//   toolsDialog(site, ...)  Connect <tool> (setup=tool-<id>): Who will do it? (agent-first.js,
//                           job connect-tools), then for Me: what Skald needs, paste, done
//   toolsMail(tools)        My developer: what to make, with which permission, and where to
//                           paste it (never a key in a mail)
//
// GET integrations/yourtools (admins: every tool, with what it needs); POST .../key, set,
// pause, remove, sync (yourtools/api.py). Each value shown has its copy icon (urlactions.js).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why, field } from "./forms.js";
import { wizard } from "./conn-ui.js";
import { pill } from "../ui/pill.js";
import { help } from "../ui/help.js";
import { statusRow } from "./set-ui.js";
import { withCopy } from "../urlactions.js";
import { loading, copyButton, numbered } from "./setup-common.js";

export const TOOLS_PATH = "integrations/yourtools";
export const DRAWER = "your-";                   // tool=your-<id>: one of your tools' drawer
export const SETUP = "tool-";                    // setup=tool-<id>: Connect <tool>

const num = (v) => (v == null ? "Not given" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 }));

/* The row of one tool on Leads & tools: its name, its words and last answer, its pill. */
export function toolRow(t, onOpen) {
  const line = t.state === "off" ? t.words : `${t.words} · last answer ${t.ago}`;
  return statusRow({ iconName: "plug", title: t.name, line: `${line}. ${t.counted_from}`, kind: t.pill, word: t.words, onOpen });
}

/* The rows of the tools that are on (any state but off), and the names of the others. */
export function toolRows(r, open) {
  const tools = (r && r.ok && r.tools) || [];
  const on = tools.filter((t) => t.state !== "off");
  return { rows: on.map((t) => toolRow(t, open(`${DRAWER}${t.id}`))), off: tools.filter((t) => t.state === "off") };
}

const post = (act, site, body) => call(`${TOOLS_PATH}/${act}`, { site, ...body });

function optionFields(t, st) {
  return Object.entries(t.option_specs || {}).map(([k, o]) => {
    const value = String(st[k] ?? (t.options || {})[k] ?? (t.suggest || {})[k] ?? "");
    const input = h("input", { type: "text", spellcheck: "false", autocomplete: "off", value, placeholder: o.example || "" });
    input.addEventListener("input", () => { st[k] = String(input.value || "").trim(); });
    st[k] = value.trim();
    const hint = [(t.suggest || {})[k] && !(t.options || {})[k] ? "Skald found this on your site's pages." : "", o.words].filter(Boolean).join(" ");
    return field(o.label + (o.required ? "" : " (optional)"), input, hint);
  });
}

function keyBox(t, st) {
  const area = h("textarea", { rows: "4", spellcheck: "false", autocomplete: "off", "aria-label": `The ${t.name} key`, placeholder: t.shares_key ? "Paste the key, or leave it empty to use Skald's Google key" : "Paste the key" });
  area.addEventListener("input", () => { st.key = area.value; });
  return h("div", null, field(`Its key: ${t.key_words}`, area, `It needs: ${t.permission}. Skald keeps it on its server, never shows it again, and only reads with it.`));
}

/* What Skald needs from the person, in plain steps: where to make the key, its permission. */
function needs(t) {
  return [h("p", null, `Skald reads your ${t.name} figures with your own key, read-only, and shows them in their own area, labelled "${t.counted_from}". They are never added to Skald's own counts.`),
    h("ol", { class: "steps" }, h("li", null, `Make the key: ${t.make_key}.`), h("li", null, `The permission it needs: ${t.permission}.`), h("li", null, "Paste it on the next step.")),
    Object.keys(t.suggest || {}).length ? h("p", { class: "note" }, "Found on your site's home page: ", ...Object.entries(t.suggest).map(([k, v]) => withCopy(h("code", null, v), v, { label: k })),
      t.suggest.measurement_id ? ". That is the tag's measurement ID, which shows the stream your site sends to; the property ID is other digits." : "") : null];
}

const when = (t) => (t ? String(t).replace("T", " ").slice(0, 16) : "");

/* What the tool's answer names (admins only, as the People settings keep it): one line each,
   its time, what, state, and the name and email with their copy icons. */
export function peopleList(t) {
  const people = (t.more && t.more.people) || [];
  if (!people.length) return null;
  const item = (p) => h("li", { class: "yt-person" },
    h("small", null, when(p.when)), " ", h("b", null, p.what || ""), p.state ? [" ", pill(p.state === "no-show" || p.state === "bounced" || p.state === "canceled" ? "warn" : "info", p.state)] : null,
    p.name ? [" ", withCopy(h("span", null, p.name), p.name, { label: "the name" })] : null,
    p.email ? [" ", withCopy(h("code", null, p.email), p.email, { label: "the email" })] : null);
  return [h("h3", null, "Most recent"), h("ul", { class: "yt-people" }, people.map(item))];
}

/* The tool's own notes (where its figures come from) and the lines Skald worked out. */
export function toolNotes(t) {
  const lines = [...(t.notes || []), ...((t.more && t.more.lines) || [])];
  return lines.map((line) => h("p", { class: "note yt-note" }, line));
}

/* The drawer of one tool: its state and figures' freshness, then what an admin may change. */
export function toolDrawer(t, site, { onChange = null } = {}) {
  const st = {};
  const msg = h("p", { class: "msg", role: "status" });
  const say = (text, ok = false) => { msg.className = `msg ${ok ? "ok" : "err"}`; msg.textContent = text; };
  let refresh = () => {};
  const act = (words, run) => {
    const b = h("button", { type: "button", class: "btn" }, words);
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        const r = await run();
        if (r && !r.ok) say(why(r, "It did not work."));
        else { say("Done.", true); onChange?.(); }
      } finally { b.disabled = false; refresh(); }
    });
    return b;
  };
  const key = t.key || {};
  const where = key.where === "file" ? "on Skald's server (secrets.json)" : key.where === "search console key" ? "the same Google key as Search Console" : key.where ? `in the server's environment (${key.where.replace(/^env /, "")})` : "";
  const status = h("div", { class: "yt-state" }, pill(t.pill, t.words), h("span", null, ` Last answer: ${t.ago}.`), t.error ? h("p", { class: "msg err" }, withCopy(h("span", null, t.error), t.error, { label: "the error" })) : null,
    t.withheld ? h("p", { class: "msg err" }, t.withheld) : null);
  const period = t.period ? h("p", { class: "note" }, `${t.counted_from}, over its own ${t.period.start} to ${t.period.end}${t.period.note ? ` (${t.period.note})` : ""}.`) : h("p", { class: "note" }, t.counted_from);
  const keyLine = key.set ? h("p", null, "Key: ", h("b", null, "kept "), where, key.who ? [" · ", withCopy(h("code", null, key.who), key.who, { label: "whose key it is" })] : null)
    : h("p", null, "Key: ", h("b", null, key.problem || "none yet"));
  const opts = optionFields(t, st);
  const save = opts.length ? act("Save", () => post("set", site, { tool: t.id, options: { ...st, key: undefined } })) : null;
  const paste = keyBox(t, st);
  const replace = h("input", { type: "checkbox" });
  const send = act(key.set ? "Replace the key" : "Keep the key", () => {
    if (!st.key && !t.shares_key) return Promise.resolve({ ok: false, error: "Paste the key first." });
    const options = Object.fromEntries(Object.keys(t.option_specs || {}).map((k) => [k, st[k]]));
    if (!st.key && t.shares_key) return post("set", site, { tool: t.id, options: { ...options, key: t.shares_key } });
    return post("key", site, { tool: t.id, key: st.key, options, replace: key.set ? replace.checked : false });
  });
  const on = t.state !== "off";
  const sync = on ? act("Sync now", () => post("sync", site, { tool: t.id })) : null;
  const editable = !t.in_env;
  // One primary (docs/UI-RULES.md rules 1 and 12): the key pasted, else the options changed
  // (Save, active only then), else a tool with no key yet (Keep the key), else Sync now.
  const first = Object.fromEntries(Object.keys(t.option_specs || {}).map((k) => [k, st[k]]));
  refresh = () => {
    const changed = Object.keys(first).some((k) => st[k] !== first[k]);
    const pasted = !!String(st.key || "").trim();
    const main = !editable ? sync : pasted ? send : changed && save ? save : !key.set ? send : sync;
    if (save) save.disabled = !changed;
    if (key.set) send.disabled = !pasted;
    for (const b of [save, send, sync]) if (b) b.className = b === main ? "btn ui-primary" : "btn";
  };
  refresh();
  // Pause and Remove the key: a quieter row of their own, under the main actions.
  const quiet = [on ? act("Pause", () => post("pause", site, { tool: t.id })) : null,
    key.where === "file" ? act("Remove the key", () => post("remove", site, { tool: t.id })) : null].filter(Boolean);
  for (const b of quiet) b.className = "btn yt-quiet-btn";
  const box = h("div", { class: "yt-dw" }, status, period, ...toolNotes(t), peopleList(t),
    h("h3", null, "The key"), keyLine,
    editable ? [...opts, save, paste,
      key.set ? h("label", { class: "chk" }, replace, h("span", null, "Replace the key Skald keeps now")) : null, send]
      : h("p", { class: "note" }, "This key is set in the server's environment: only whoever runs Skald can change it."),
    msg,
    sync ? h("div", { class: "acts yt-main" }, sync) : null,
    quiet.length ? h("div", { class: "acts yt-quiet" }, ...quiet,
      h("small", { class: "muted" }, key.where === "file" ? "Pause stops the asking and keeps the key and the figures. Remove the key also pauses it; the figures kept stay."
        : "Pause stops the asking and keeps the figures.")) : null,
    help(`${t.name} figures`, { guide: "your-tools" }));
  box.addEventListener("input", refresh);
  box.addEventListener("change", refresh);
  return box;
}

/* My developer: what to make and where it goes, one tool per paragraph. Never a key in it. */
export function toolsMail(site, tools) {
  return [`Hello,`, "", `Could you connect ${tools.map((t) => t.name).join(" and ")} to Skald for ${site}? Skald shows their figures beside its own, read-only.`, "",
    numbered(tools.flatMap((t) => [`${t.name}: make ${t.key_words} (${t.make_key}). It needs: ${t.permission}.`])),
    "", "Then paste each key in Skald: Settings > This site > Leads & tools > Connect a tool > Me. If you have no Skald account, ask me for an admin invite, or run the AI agent line I can make for you there.",
    "Please never send a key by mail or chat.", "", "Thank you."].join("\n");
}

/* Connect <tool>: Me's steps, after the who-step (wrap). tool: its id (setup=tool-<id>). */
export function toolsDialog(site, { tool = "", onClose = null, route = null, start = 0, wrap = null } = {}) {
  const st = { r: null };
  const load = () => (st.r ? Promise.resolve(st.r) : call(TOOLS_PATH).then((r) => { st.r = r; return r; }));
  const pick = (r) => (r.tools || []).find((t) => t.id === tool) || (r.tools || []).find((t) => t.state === "off") || (r.tools || [])[0];
  const steps = [
    { name: "What Skald needs",
      draw: () => [loading("Loading your tools...", load, (r) => (!r.ok ? h("p", { class: "msg err" }, why(r, "Your tools could not be loaded.")) : pick(r) ? needs(pick(r)) : h("p", { class: "empty" }, "No tool can be connected in this version.")))] },
    { name: "Paste the key",
      draw: (w) => [loading("Loading...", load, (r) => {
        const t = r.ok && pick(r);
        if (!t) return null;
        w.state.tool = t;
        w.state.keyBox = { ...w.state.keyBox };
        return [...optionFields(t, w.state.keyBox), keyBox(t, w.state.keyBox)];
      })],
      check: (w) => (!w.state.tool ? "Wait for your tools to load." : !w.state.keyBox?.key && !w.state.tool.shares_key ? "Paste the key." : ""),
      next: async (w) => {
        const t = w.state.tool;
        const { key = "", ...options } = w.state.keyBox || {};
        const r = key ? await post("key", site, { tool: t.id, key, options }) : await post("set", site, { tool: t.id, options: { ...options, key: t.shares_key } });
        if (!r.ok) { w.say(why(r, "It was not kept.")); return false; }
        st.done = r;
        return true;
      } },
    { name: "Done",
      draw: (w) => [h("div", { class: "state ok", role: "status" }, h("div", null, h("p", null, h("strong", null, "Connected. "),
        `Skald asks ${w.state.tool?.name || "the tool"} within the next minutes, then every few hours. Its figures show on Overview, under "From your tools".`))),
      st.done?.who ? h("p", { class: "note" }, "The key Skald keeps: ", withCopy(h("code", null, st.done.who), st.done.who, { label: "whose key it is" })) : null,
      h("p", { class: "note" }, "Change or pause it in Settings › Leads & tools.")] },
  ];
  return wizard({ route, start, wrap, done: "Close", title: "Connect a tool", subtitle: `For ${site}.`, key: "setup-tools", onClose, state: {}, steps });
}

export const copyMailButton = (site, tools) => copyButton("Copy the message", toolsMail(site, tools), "the message");
