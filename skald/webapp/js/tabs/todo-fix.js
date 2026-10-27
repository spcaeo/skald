// "Fix this" (2.41): ONE button per to-do on Overview › Insights, and "Fix all (N)" above the
// list, open the same dialog. It asks one question, "Who will do it?", and shows only the
// answer's part (the owner, 2026-10-26: one button, then "what are you trying to do?"):
//
//   My AI agent   one line to paste into Claude Code, Codex, Cursor...: the agent fetches every
//                 row from Skald itself (no CSV, no copy and paste), fixes it in the site's own
//                 code or server, asks before any server change, and reports back. Its report
//                 shows here; "done" marks the to-do done, so Skald re-checks it on the days
//                 after (it changes no figure; Undo is one click)
//   Me            the exact lines to paste for the site's web server (nginx or Apache, the site
//                 check's when known), every row (settings/todo-rows, never the browser's cut-down
//                 files), and the CSV as a small link; then Mark done
//   My developer  Send to team (todo_api.py's mail with the CSV), or the link to copy
//
// The question is the shared one (ui/who.js, 2.41): Me, My developer, My AI agent, in that
// order, the last answer remembered per person.
//
// The address: fix=1 with todo=<id> (one to-do), or fix=all; by=me|dev|agent (the answer;
// links made before said fixby=agent|me|someone, read the same, someone as dev); link=<16 hex> (the line being watched: never the line or its code, which live in
// this page's memory only, like every agent line). A line is made only on a press, never by
// opening an address: a new line ends the older one an agent may be working from.

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { openDrawer } from "../drawer.js";
import { whoStep } from "../ui/who.js";
import { stepped } from "../overlays.js";
import { stamp } from "../tz.js";
import { reportBox } from "./todo-report.js";
import { columnsOf } from "./todos.js";
import { csv, download } from "../table.js";
import { withCopy, copyText, TIMING } from "../urlactions.js";
import { answerBox } from "./conn-ui.js";
import { lineBox } from "./agent-setup.js";
import { expired, timeLeft, CANCELLED_WORDS, SAFE_TITLE } from "./agent-words.js";
import { MARKS, loadMarks, markItem, makeTodoLine, lineStatus, cancelTodoLine, todoRows, sendable, sendTodo } from "./todo-marks.js";

export const AGENT_KINDS = ["lost", "errors", "markdown", "sitemap", "leave"];
export const isAgentTodo = (t) => (t.agent ?? AGENT_KINDS.includes(t.kind));
// The answers' second lines here (ui/who.js keeps the titles: Me, My developer, My AI agent).
export const SUBS = {
  me: "The exact lines to paste for your web server, with every row.",
  dev: "Send it to your developer or a teammate, with its list.",
  agent: "Claude Code, Codex, Cursor or another that runs commands. One line to paste; it fixes it and reports back here.",
};
export const GONE = "That to-do is not on the list now, or it is not available to you.";
export const UNDO_WORDS = "Marking it done changes no figure: Skald only starts checking it, with the same measure, on every whole day after. Undo is one click.";
// "Is it safe to paste this into a chat?" for a to-do line (checked against kit/agent_todos.py).
export const SAFE = [
  "Yes. The line holds a one-time code, not a password or a key to your dashboard.",
  "Your agent swaps the code once for a report key, saved straight into a locked file on its machine. The code cannot be swapped again. Everything stops after 24 hours, or at once when you press Cancel this line.",
  "The report key can only read the addresses and counts of the to-dos in this line, for this one site, and send back what was changed. It never sees a visitor's address or email, and cannot open your dashboard or change a setting.",
  "The worst a leaked line can do is mark one of these to-dos done. That changes no figure: Skald only starts checking it. Undo is one click.",
  "Your agent is told to ask you before any change on a server, to test the server's settings before a reload, and to touch nothing the to-do does not list.",
];
const safetyBox = () => h("details", { class: "fold ag-safe" }, h("summary", null, SAFE_TITLE), h("ul", null, SAFE.map((x) => h("li", null, x))));
const POLL = { every: 5000, slowAfter: 15 * 60000, slow: 30000 };
export const setPoll = (p) => Object.assign(POLL, p);       // the tests make it quicker

// The lines made in this page, by the to-dos they carry. Never stored anywhere else.
const LINES = new Map();
const keyOf = (list) => list.map((t) => t.id).join(",");
export const forgetLines = () => LINES.clear();   // a reload, for the tests

/* ---- the server lines (closest_page.rules, the same in JS) ----------------------------- */
const SAFE_PATH = /^\/[A-Za-z0-9._~/-]*$/;
const decode = (p) => { try { return decodeURIComponent(p); } catch { return p; } };
export function rules(old, target) {
  const src = decode(String(old).split("?")[0]);
  const dst = target ? decode(String(target).split("?")[0]) : null;
  if (!SAFE_PATH.test(src) || (dst !== null && !SAFE_PATH.test(dst))) return { nginx: null, apache: null };
  if (dst) return { nginx: `location = ${src} { return 301 ${dst}; }`, apache: `Redirect 301 ${src} ${dst}` };
  return { nginx: `location = ${src} { return 410; }`, apache: `Redirect gone ${src}` };
}
export const serverOf = (srv) => (/apache|litespeed/i.test(`${srv?.server || ""}`) ? "apache" : "nginx");
const HOSTED = { vercel: "vercel.json or next.config.js", netlify: "the _redirects file", cloudflare: "Cloudflare's Redirect Rules" };

/* The lines to paste for one to-do and server: {text, count, by_hand}. */
export function linesFor(t, rows, server) {
  const out = [];
  let count = 0, byHand = 0;
  const one = (from, to, note = "") => {
    const r = rules(from, to)[server];
    if (!r) { byHand += 1; out.push(`# ${from}: write this one by hand (characters a rule cannot take as they are)`); return; }
    out.push(note ? `${r}   # ${note}` : r);
    count += 1;
  };
  if (t.kind === "lost") {
    for (const r of rows) one(r.path, r.target || null, r.target ? "" : "no live page close to it: gone only if it is");
  } else if (t.kind === "markdown") {
    out.push(server === "apache"
      ? "# One rule for every .md address (real .md files stay):\nRewriteEngine On\nRewriteCond %{REQUEST_FILENAME} !-f\nRewriteRule ^(.+)\\.md$ /$1/ [R=301,L]"
      : "# One rule for every .md address (real .md files stay):\nlocation ~ \\.md$ { try_files $uri @skald_md; }\nlocation @skald_md { rewrite ^(.+)\\.md$ $1/ permanent; }");
    out.push("# Or one line per address:");
    for (const r of rows) one(r.path, r.page || null);
    count += 1;
  } else if (t.kind === "sitemap") {
    out.push("# Change /sitemap.xml below if your sitemap is at another address.");
    for (const r of rows) one(r.path, "/sitemap.xml");
  }
  return { text: out.join("\n") + "\n", count, by_hand: byHand };
}

/* ---- opening ---------------------------------------------------------------------------- */

const todosOf = (m) => (m?.x?.todos?.todos || []).filter((t) => t && t.id);
const openOnes = (m) => todosOf(m).filter((t) => isAgentTodo(t) && !["done", "notnow"].includes((MARKS.ok ? MARKS.marks[t.id]?.state : t.state) || ""));

/* The address named the dialog: fix=1 (with todo=<id>) or fix=all. */
export async function openFixKey(v, m, s) {
  await loadMarks();
  const list = v === "all" ? openOnes(m) : todosOf(m).filter((t) => t.id === s.todo);
  if (!list.length) return v === "all" ? "Nothing is left to fix now." : GONE;
  return fixDialog(list, v === "all" ? "all" : "1", s);
}

export function fixDialog(list, value, s = S.read()) {
  const all = value === "all";
  const st = { link: /^[0-9a-f]{16}$/.test(s.link || "") ? s.link : "", made: false };
  const route = { key: "fix", value };
  const step = whoStep({ route, from: s.by || s.fixby || "", subs: SUBS,
    paths: { me: () => mePart(list), dev: () => somePart(list), agent: ({ pressed }) => agentPart(list, st, value, pressed) },
    // A line is watched only on My AI agent: the other answers take it out of the address.
    onPick: (k) => { if (k !== "agent") stepped("fix", value, { link: "" }); } });
  const body = h("div", { class: "fx" }, step.el);
  const d = openDrawer({ title: all ? `Fix all (${list.length})` : "Fix this", subtitle: all ? list.map((t) => t.title).join(" · ") : list[0].title,
    size: "md", key: "todo-fix", scope: "page", body, route });
  d.st = st;
  d.who = step;
  return d;
}

/* ---- My AI agent -------------------------------------------------------------------------- */

function agentPart(list, st, value, pressed) {
  if (!MARKS.ok) return [answerBox("warn", MARKS.why || "Lines for an AI agent need a running Skald with accounts.")];
  if (!MARKS.can_mark) return [answerBox("warn", "Only an owner or an admin can make the line for an AI agent.", h("p", null, "Ask one of them, or choose Someone else to send it."))];
  const slot = h("div", { class: "fx-line" });
  const watch = h("div", { class: "fx-watch" });
  const k = keyOf(list);
  const draw = () => {
    const got = LINES.get(k);
    if (got && !expired(got.expires_at)) {
      const [box, show] = lineBox(got);
      const left = timeLeft(got.expires_at);
      slot.replaceChildren(h("p", null, "Copy this line and paste it into your AI agent, in the site's project folder or on its server."), box,
        h("div", { class: "acts" }, show, again, cancel),
        h("p", { class: "note" }, `It works once${got.expires_at ? `, until ${stamp(got.expires_at)}${left ? ` (${left})` : ""}` : ""}. Your agent fetches every row from Skald itself: nothing to download.`));
      watchLine(list, st, watch, finished);
      return;
    }
    if (st.link && !st.made) {
      slot.replaceChildren(h("p", { class: "note" }, "This line was made before the page was reloaded, so it is not shown again. Its progress is below."), h("div", { class: "acts" }, make, cancel));
      watchLine(list, st, watch, finished);
      return;
    }
    slot.replaceChildren(h("div", { class: "acts" }, make));
  };
  const make = h("button", { type: "button", class: "btn primary" }, "Make the line");
  const again = h("button", { type: "button", class: "btn" }, "Make a new line");
  const cancel = h("button", { type: "button", class: "btn", "aria-label": "Cancel this line: it stops working at once" }, "Cancel this line");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  // Every to-do of the line reported: the line has done its work.
  const finished = () => slot.replaceChildren(h("p", { class: "note" }, "Your agent has reported every to-do in this line. The line stops by itself within 24 hours, or cancel it now."),
    h("div", { class: "acts" }, cancel));
  const ask = async () => {
    make.disabled = again.disabled = true;
    said.textContent = "Making the line…";
    const r = await makeTodoLine(value === "all" ? list.map((t) => t.id) : [list[0].id]);
    make.disabled = again.disabled = false;
    said.textContent = "";
    if (!r.ok || !r.line) { slot.replaceChildren(answerBox("bad", r.error || "The line was not made."), h("div", { class: "acts" }, make)); return; }
    LINES.set(k, r);
    st.link = r.link_id || "";
    st.made = true;
    stepped("fix", value, { link: st.link });
    draw();
  };
  make.addEventListener("click", ask);
  again.addEventListener("click", () => { LINES.delete(k); ask(); });
  cancel.addEventListener("click", async () => {
    const lid = LINES.get(k)?.link_id || st.link;
    cancel.disabled = true;
    const r = await cancelTodoLine(lid);
    cancel.disabled = false;
    if (!r.ok) { said.textContent = r.error || "The line was not cancelled."; return; }
    LINES.delete(k);
    st.link = "";
    stepped("fix", value, { link: "" });
    watch.replaceChildren();
    slot.replaceChildren(answerBox("ok", CANCELLED_WORDS), h("div", { class: "acts" }, make));
  });
  draw();
  // Chosen by a press: the line is made at once. From an address: only on Make the line.
  if (pressed && !LINES.get(k) && !st.link) ask();
  return [h("p", null, "Your agent reads Skald's steps, fetches every row, finds where your site keeps its redirects or rules, changes only what is missing, and asks you before any server change. Then it reports here."),
    slot, said, watch, safetyBox(),
    h("p", { class: "note" }, `When your agent reports a to-do done, Skald marks it done. ${UNDO_WORDS}`)];
}

function watchLine(list, st, out, finished = () => {}) {
  const started = Date.now();
  const steps = h("ol", { class: "ag-watch fx-steps", "aria-live": "polite" });
  out.replaceChildren(h("h4", null, "What your agent has done"), steps);
  const once = async () => {
    if (!out.isConnected || !st.link) return;
    const r = await lineStatus(st.link);
    if (!out.isConnected) return;
    if (r.ok) {
      const fixes = r.reports || {};
      steps.replaceChildren(
        h("li", { class: r.opened_at ? "ok" : "wait" }, h("span", { class: "cn-tick", "aria-hidden": "true" }, r.opened_at ? "✓" : "…"), r.opened_at ? "It read Skald's steps" : "Waiting for your agent to read the steps"),
        h("li", { class: r.keys_at ? "ok" : "wait" }, h("span", { class: "cn-tick", "aria-hidden": "true" }, r.keys_at ? "✓" : "…"), r.keys_at ? "It took its key, to fetch the rows" : "Waiting for it to fetch the rows"),
        ...list.map((t) => reportBox(t, fixes[t.id])));
      if (Object.keys(fixes).length && Object.keys(fixes).length !== Object.keys(st.seen || {}).length) {
        st.seen = fixes;
        loadMarks(true);
      }
      if (["cancelled", "expired"].includes(r.state)) { steps.append(h("li", { class: "bad" }, r.state === "cancelled" ? CANCELLED_WORDS : "This line ran out.")); return; }
      if (list.every((t) => fixes[t.id])) { finished(); return; }
    }
    setTimeout(once, Date.now() - started < POLL.slowAfter ? POLL.every : POLL.slow);
  };
  setTimeout(once, 0);
}

/* ---- Me ------------------------------------------------------------------------------------ */

function mePart(list) {
  return list.map((t) => meOne(t));
}

function meOne(t) {
  const box = h("section", { class: "fx-me", "aria-label": t.title }, h("h4", null, t.title), h("p", { class: "empty" }, "Reading every row…"));
  (async () => {
    const r = await todoRows(t.id);
    const full = r.ok && r.todo ? r.todo : t;
    const rows = full.rows || [];
    const parts = [h("h4", null, t.title), h("p", null, h("b", null, "Do: "), t.todo)];
    if (["lost", "markdown", "sitemap"].includes(t.kind)) {
      let server = serverOf(MARKS.server);
      const out = h("div");
      const draw = () => {
        const got = linesFor(t, rows, server);
        const sw = h("div", { class: "seg plain", role: "group", "aria-label": "Your web server" },
          ["nginx", "apache"].map((k) => h("button", { type: "button", "aria-pressed": String(k === server), onclick: () => { server = k; draw(); } }, k === "nginx" ? "nginx" : "Apache")));
        const hosted = Object.entries(HOSTED).find(([k]) => new RegExp(k, "i").test(`${MARKS.server?.platform || ""} ${MARKS.server?.server || ""}`));
        out.replaceChildren(...[sw,
          h("p", { class: "note" }, server === "nginx" ? "Paste them inside your site's server { } block (or a file it includes), run nginx -t, then reload." : "Paste them into the site's .htaccess or its Apache file, run apachectl configtest, then reload."),
          hosted ? h("p", { class: "note" }, `Your site runs on ${hosted[0]}: its redirects usually go in ${hosted[1]}. Your AI agent can write them in the right place.`) : null,
          withCopy(h("pre", { class: "fx-pre fx-lines" }, got.text), got.text, { label: "the lines", tag: "div" }),
          h("div", { class: "acts" }, copyLines(got.text), h("button", { type: "button", class: "btn", onclick: () => download(`${t.id}-${server}.conf`, got.text, "text/plain;charset=utf-8") }, `Download the lines`)),
          got.by_hand ? h("p", { class: "note" }, `${n(got.by_hand)} ${got.by_hand === 1 ? "address needs" : "addresses need"} a rule written by hand.`) : null].filter(Boolean));
      };
      draw();
      parts.push(out);
    } else {
      parts.push(h("p", { class: "note" }, t.kind === "errors" ? "Send these addresses to your developer or host: each one failed for whoever asked. Your AI agent can also find the failing route and fix it." :
        "Give each page a clear next step. Your AI agent can draft the change for you to approve."));
    }
    parts.push(h("p", { class: "note" }, `${n(full.rows_total ?? rows.length)} row${(full.rows_total ?? rows.length) === 1 ? "" : "s"}. `,
      h("a", { href: "#", class: "fx-csv", onclick: (e) => { e.preventDefault(); download(t.file || `${t.id}.csv`, csv(columnsOf(t), rows)); } }, `Download CSV`)),
      doneButton(t));
    box.replaceChildren(...parts);
  })();
  return box;
}

function copyLines(text) {
  const b = h("button", { type: "button", class: "btn primary" }, "Copy the lines");
  b.addEventListener("click", async () => {
    const ok = await copyText(text);
    b.textContent = ok ? "✓ Copied" : "Copy failed: select and copy";
    b.classList.toggle("ok", ok);
    setTimeout(() => { b.textContent = "Copy the lines"; b.classList.remove("ok"); }, ok ? TIMING.tick : TIMING.failed);
  });
  return b;
}

function doneButton(t) {
  const why = MARKS.ok && MARKS.can_mark ? "" : MARKS.why;
  const said = h("span", { class: "msg", role: "status", "aria-live": "polite" });
  const b = h("button", { type: "button", class: "btn", disabled: why ? true : null, title: why || null }, "Mark done");
  b.addEventListener("click", async () => {
    b.disabled = true;
    const r = await markItem(t.id, "done");
    said.textContent = r.ok ? "Marked done. Skald re-checks it on every whole day after." : (r.error || "Not saved.");
    if (!r.ok) b.disabled = false;
  });
  return h("p", { class: "fx-mark" }, "Done it? ", b, " ", said, h("br"), h("small", { class: "muted" }, UNDO_WORDS));
}

/* ---- Someone else ---------------------------------------------------------------------- */

function somePart(list) {
  const can = sendable();
  const linkOf = (t) => `${location.href.split("#")[0]}${S.hashFor({ ...S.read(), tab: "overview/insights", todo: t.id, fix: "", by: "", fixby: "", link: "", tdsend: "" })}`;
  const links = h("ul", { class: "fx-links" }, list.map((t) => h("li", null, `${t.title}: `, withCopy(h("span", { class: "muted" }, "copy its link"), linkOf(t), { label: `the link to "${t.title}"` }))));
  if (!can.ok) return [h("p", null, "Send them the link: it opens the to-do with its list once they sign in."), links, h("p", { class: "note" }, `Mail is not offered here: ${can.why}`)];
  const pick = h("select", { class: "td-to", "aria-label": "Send to" }, h("option", { value: "" }, "Pick a team member"),
    can.team.map((p) => h("option", { value: String(p.id) }, `${p.email} (${p.role})`)));
  const said = h("p", { class: "td-said", role: "status", "aria-live": "polite" });
  const send = h("button", { type: "button", class: "btn primary" }, list.length > 1 ? `Send all ${list.length}` : "Send");
  send.addEventListener("click", async () => {
    if (!pick.value) { said.textContent = "Pick who it goes to first."; return; }
    send.disabled = true;
    const sent = [];
    for (const t of list) {
      said.textContent = `Sending ${t.title}…`;
      const r = await sendTodo(t.id, pick.value);
      if (!r.ok) { said.replaceChildren(withCopy(r.error || "Not sent.", r.error || "Not sent.")); said.classList.add("bad"); send.disabled = false; return; }
      sent.push(r);
    }
    send.disabled = false;
    said.classList.remove("bad");
    said.textContent = `Sent to ${sent[0]?.sent_to || "them"}: ${sent.length} mail${sent.length === 1 ? "" : "s"}, each with its list as a CSV and the link to it.`;
  });
  return [h("label", { class: "td-field" }, h("span", null, "To"), pick), h("div", { class: "acts" }, send), said,
    h("p", { class: "note" }, "Each mail has the to-do, its list as a CSV and the link that opens it in Skald. A teammate without rights to this site sees \"not available to you\"."),
    h("details", { class: "fold" }, h("summary", null, "Or copy the link"), links)];
}
