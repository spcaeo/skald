// "Set up with your AI agent", the Add a site wizard's steps 3 and 4 (site-wizard.js):
// "Which AI agent are you using?" as tiles, then "Send this line": the one line to
// paste into the agent, with its code hidden until "Show code". Step 5, the watch, is
// agent-watch.js; the words are agent-words.js.
//
// The line comes from POST <page>/sites/agentlink {site, leads: true}, asked for once
// per site when step 4 is first drawn after Next or a tile on step 3 (st.autoLine; a
// step 4 opened from an address asks with "Make the line" instead, because a new line
// ends the one an agent may be working from), and kept in this page's memory only (LINES),
// like conn-send.js's one-time command: never in the address, never stored anywhere
// else. "Make a new line" asks again; the server then ends the old line. The
// address keeps only link_id (link=<16 hex>), so a reload can watch the same line,
// but the line itself is not shown again after a reload. "Cancel this line" ends it at
// once (POST <page>/sites/agentcancel {site, link_id} -> {ok, state: "cancelled"}), also
// a line from before a reload, and from step 5 once its keys were taken. Under the line,
// "Is it safe to paste this into a chat?" says what the code is (open, folded on a phone).
//
// Chat-only agents (Claude.ai, ChatGPT) cannot run commands on a server: their
// step 4 is the server way's one command (conn-send.js runPanel), with one line why.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { stamp } from "../tz.js";
import { answerBox } from "./conn-ui.js";
import { runPanel } from "./conn-send.js";
import { withUrl, copyText, TIMING } from "../urlactions.js";
import { AGENTS, HAND, HAND_WORDS, SAFE, SAFE_TITLE, CANCELLED_WORDS, OLD_CANCELLED, agentOf, codeOf, masked, timeLeft, expired } from "./agent-words.js";

// The lines made in this page, by site and jobs: sites/agentlink's answer. Never stored
// anywhere else. jobs (2.39): the set-up dialogs' (agent-first.js), in the contract's order;
// none: Add a site's line, asked for as before ({site, leads: true}).
const LINES = new Map();
const keyOf = (site, jobs) => (jobs && jobs.length ? `${site}|${jobs.join(",")}` : site);
const ofSite = (site) => [...LINES.keys()].filter((k) => k === site || k.startsWith(`${site}|`));
export const lineFor = (site, jobs = null) => LINES.get(keyOf(site, jobs)) || null;
const MAKING = new Map();      // site (and jobs) -> the sites/agentlink on its way, asked once

/* POST sites/agentlink once per site, jobs and page (a second draw waits for the same answer).
   A new line ends the site's older ones on the server, so the page forgets them too. */
export function makeLine(site, jobs = null) {
  const k = keyOf(site, jobs);
  if (!MAKING.has(k)) {
    MAKING.set(k, call("sites/agentlink", jobs && jobs.length ? { site, jobs } : { site, leads: true }).then((r) => {
      MAKING.delete(k);
      if (r.ok && r.line) {
        for (const old of ofSite(site)) LINES.delete(old);
        LINES.set(k, { line: r.line, llms_url: r.llms_url || "", steps_url: r.steps_url || "", expires_at: r.expires_at || "", token_id: r.token_id || "", link_id: r.link_id || "", cancelled: r.cancelled || 0 });
      }
      return r;
    }));
  }
  return MAKING.get(k);
}
export const forgetLine = (site, jobs = null) => { LINES.delete(keyOf(site, jobs)); };
// The link ids cancelled in this page: step 4 says so instead of offering the line again.
const CANCELLED = new Set();
export const wasCancelled = (link) => CANCELLED.has(link);

/* POST sites/agentcancel: the line ends at once. {ok} or the refusal, as call() answers. */
export async function cancelLine(site, link) {
  const r = await call("sites/agentcancel", { site, link_id: link });
  if (r.ok) {
    CANCELLED.add(link);
    for (const k of ofSite(site)) if (LINES.get(k)?.link_id === link) LINES.delete(k);
  }
  return r;
}

/* A "Cancel this line" button; done(r) after the server said yes, `out` shows a refusal. */
export function cancelButton(site, link, out, done) {
  const b = h("button", { type: "button", class: "btn", "aria-label": "Cancel this line: it stops working at once" }, "Cancel this line");
  b.addEventListener("click", async () => {
    b.disabled = true;
    const r = await cancelLine(site, link);
    b.disabled = false;
    if (!r.ok) { out.replaceChildren(answerBox("bad", why(r, "The line was not cancelled."), h("p", null, "Try again in a moment."))); return; }
    done(r);
  });
  return b;
}

/* "Is it safe to paste this into a chat?": open on a wide screen, folded on a phone (the
   title stays in view). */
export function safetyBox() {
  let phone = false;
  try { phone = typeof matchMedia === "function" && matchMedia("(max-width: 600px)").matches; } catch { /* no media queries: open */ }
  return h("details", { class: "fold ag-safe", open: !phone }, h("summary", null, SAFE_TITLE),
    h("ul", null, SAFE.map((x) => h("li", null, x))));
}

const TERMINAL = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="m7 9 3 3-3 3M12.5 15H17"/></svg>';
const CHAT = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v10h-9l-5 4v-4H4z"/></svg>';
const EDITOR = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7 3 12l5 5M16 7l5 5-5 5M13.5 5l-3 14"/></svg>';
const iconFor = (a) => (a.id === "chat" ? CHAT : a.id === "cursor" ? EDITOR : TERMINAL);

export const CHOOSER_INTRO = "Skald writes one line for your agent. The agent reads the steps, installs Skald on the site, and reports back here. You watch each step.";

/* Step 3: the agents as tiles (aria-pressed shows the one chosen), and the quieter
   by-hand way below. onPick(id) with an agent's id or HAND. 2.39, the set-up dialogs'
   first step (agent-first.js): agents (the ones that run commands), hand ({title, sub},
   or null for none) and intro, their own words. */
export function agentChooser(st, onPick, { agents = AGENTS, hand: words = HAND_WORDS, intro = CHOOSER_INTRO } = {}) {
  const tiles = agents.map((a) => {
    const b = h("button", { type: "button", class: "ag-tile", "aria-pressed": st.agent === a.id ? "true" : "false", "aria-label": `${a.title}: ${a.sub}`, "data-agent": a.id },
      h("span", { class: "ag-ic", html: iconFor(a) }), h("b", null, a.title), h("small", null, a.sub));
    b.addEventListener("click", () => onPick(a.id));
    return b;
  });
  const hand = words ? h("button", { type: "button", class: "btn ag-hand", "data-agent": HAND, "aria-pressed": st.agent === HAND ? "true" : "false", "aria-label": `${words.title}. ${words.sub}` }, words.title) : null;
  if (hand) hand.addEventListener("click", () => onPick(HAND));
  return [intro ? h("p", null, intro) : null,
    h("div", { class: "ag-tiles", role: "group", "aria-label": "Your AI agent" }, tiles),
    hand ? h("div", { class: "ag-or" }, hand, h("small", null, words.sub)) : null];
}

/* The line in its box: hidden code by default, Copy with a green tick, Show code. */
function lineBox(got) {
  const code = codeOf(got);
  let shown = false;
  const text = h("code", null, masked(got.line, code));
  const copy = h("button", { type: "button", class: "btn primary ag-copy", "aria-label": "Copy the line for your agent" }, "Copy");
  const show = h("button", { type: "button", class: "btn", "aria-pressed": "false" }, "Show code");
  const said = h("span", { class: "vh", role: "status", "aria-live": "polite" });
  let timer = 0;
  copy.addEventListener("click", async () => {
    clearTimeout(timer);
    const ok = await copyText(got.line);
    copy.classList.toggle("ok", ok);
    copy.textContent = ok ? "✓ Copied" : "Copy failed: show the code, then select it";
    said.textContent = ok ? "Copied the line" : "Copy failed";
    timer = setTimeout(() => { copy.classList.remove("ok"); copy.textContent = "Copy"; said.textContent = ""; }, ok ? TIMING.tick : TIMING.failed);
  });
  show.addEventListener("click", () => {
    shown = !shown;
    text.textContent = shown ? got.line : masked(got.line, code);
    show.textContent = shown ? "Hide code" : "Show code";
    show.setAttribute("aria-pressed", shown ? "true" : "false");
  });
  return [h("div", { class: "cn-code ag-line" }, h("pre", null, text), copy, said), show];
}

/* Step 4, "Send this line" (or the one command, for a chat-only agent). onMade(r) when
   a new line or command is made: the wizard keeps its token_id and the address its link_id. */
export function linePanel(st, w, { onMade = null } = {}) {
  const a = agentOf(st.agent) || agentOf("other");
  const site = st.site;
  if (!a.shell) {
    st.send.method = "server";
    return [h("p", { class: "ag-why" }, a.where), runPanel(st.send, w, { onMade: (r) => { if (onMade) onMade({ token_id: r.token_id || "" }); } })];
  }
  const jobs = st.jobs || null;
  const got = lineFor(site, jobs);
  const slot = h("div", { class: "ag-slot" });
  const again = h("button", { type: "button", class: "btn" }, got ? "Make a new line" : "Try again");
  const ask = async () => {
    again.disabled = true;
    const r = await makeLine(site, jobs);
    again.disabled = false;
    if (!r.ok || !r.line) {
      slot.replaceChildren(answerBox("bad", why(r, "The line was not made."), h("p", null, jobs ? "Press Try again, or go Back and choose By hand." : "Press Try again, or go Back and choose No AI agent to set it up by hand.")));
      again.textContent = "Try again";
      again.hidden = false;
      return;
    }
    st.link = r.link_id || "";
    st.cancelled = false;
    if (onMade) onMade(r);
    if (slot.isConnected !== false) w.redraw();       // still on this step: drawn with the line
  };
  const fresh = () => { forgetLine(site, jobs); again.textContent = "Making a new line..."; ask(); };
  again.addEventListener("click", fresh);
  const intro = h("p", null, `${a.where} Skald's steps tell it what to do for ${site}.`);
  // Cancelled (here, or a line from before a reload): it is gone; a new one on request.
  const gone = () => { st.cancelled = true; if (again.isConnected !== false) w.redraw(); };
  if (!got) {
    if (st.link && (st.cancelled || wasCancelled(st.link))) {
      again.textContent = "Make a new line";
      return [intro, answerBox("ok", CANCELLED_WORDS, h("p", null, "Make a new line when you are ready, and send that one.")), slot, h("div", { class: "acts" }, again)];
    }
    // A line made before a reload: the address knows its link_id, but the line is not kept.
    if (st.link) {
      again.textContent = "Make a new line";
      return [intro, answerBox("warn", "This line was made before the page was reloaded, so it is not shown again.",
        h("p", null, "Already sent it to your agent? Press Next to watch it connect. If not, make a new line, or cancel this one.")), slot,
        h("div", { class: "acts" }, again, cancelButton(site, st.link, slot, gone))];
    }
    // Opened from an address: never make a line by itself, it would end the one already sent.
    if (!st.autoLine) {
      const make = h("button", { type: "button", class: "btn primary" }, "Make the line");
      // A failed request shows Try again in its place.
      make.addEventListener("click", async () => { make.disabled = true; make.textContent = "Making the line..."; st.autoLine = true; await ask(); make.hidden = true; });
      again.hidden = true;
      return [intro, h("p", null, "Press Make the line when you are ready to send it. A new line ends any older line for this site whose keys were not taken yet."),
        slot, h("div", { class: "acts" }, make, again)];
    }
    again.hidden = true;
    slot.replaceChildren(h("p", { class: "empty" }, "Making the line..."));
    ask();
    return [intro, slot, h("div", { class: "acts" }, again)];
  }
  if (expired(got.expires_at)) {
    again.textContent = "Make a new line";
    return [intro, answerBox("bad", "This line ran out.", h("p", null, "Make a new line and send that one.")), slot, h("div", { class: "acts" }, again)];
  }
  const [box, show] = lineBox(got);
  const left = timeLeft(got.expires_at);
  const llms = got.llms_url ? h("p", { class: "note" }, "What your agent reads first, the same for every site: ", withUrl(h("code", null, got.llms_url), got.llms_url, { cls: "ua-after", label: "Skald's guide for AI agents" })) : null;
  return [intro, box, h("div", { class: "acts" }, show, again, cancelButton(site, got.link_id, slot, gone)), slot,
    h("p", null, `It works once${got.expires_at ? `, until ${stamp(got.expires_at)}${left ? ` (${left})` : ""}` : ""}.`),
    got.cancelled ? h("p", { class: "note" }, OLD_CANCELLED) : null,
    safetyBox(),
    h("p", { class: "note" }, "This page never sees the keys. Press Next: Skald ticks off each step as your agent does it."),
    llms];
}
