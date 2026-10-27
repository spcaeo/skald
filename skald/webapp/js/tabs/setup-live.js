// A set-up's live progress (2.43): the owner added fieldcamp.ai, gave the agent line to its
// developer, and the agent did it all, but his open wizard said only "Finish later". Now Add a
// site's "Connect it" (My AI agent and My developer), and a done set-up opened from a link,
// show a short checklist that ticks itself, each line with its time:
//
//   Your agent opened the line · Keys made and taken · Data road set up: Vercel log drain ·
//   First data received (N in the last 15 min, newest 13:28) · Domain verified · Set-up done ·
//   Invites (who, once the first data arrives)
//
// It asks POST <page>/sites/live {site, link_id} every 5 s, every 30 s after 2 minutes, and
// not while the tab is hidden or once the panel left the page (setup-live-words.js POLL).
// "Check now" asks POST sites/check at once and says plainly what is missing. Done: a green
// "Receiving data", the primary "Open the dashboard", "Invite the people who will use it", and
// the invites' line (with "Send the invites now" while they wait). The server's side:
// skald/setup_live.py.
//
// It is the step's one source of truth (the coordinator, 2.43): it replaced the old "Skald
// waits for the first visits" block and its Test connection on every path, so the screen never
// says "receiving" and "nothing has reached Skald" at once. What that block had and this lacked
// is here: the plain reason Skald refused what was sent (shown without a press, from the view's
// `refused`), and, in Check now's answer, the way's own help (more(check): the shipper's check
// command, or the home page's tag).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { time } from "../tz.js";
import { answerBox } from "./conn-ui.js";
import { pill } from "../ui/pill.js";
import { fold } from "../ui/fold.js";
import { itemsOf, pillOf, doneWords, delay, checkKind } from "./setup-live-words.js";

const TICK = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8.5l3 3 7-7"/></svg>';
const DOT = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="3.2"/></svg>';

const liveOf = (site, link) => call("sites/live", { site, ...(link ? { link_id: link } : {}) });
const checkOf = (site, link) => call("sites/check", { site, ...(link ? { link_id: link } : {}) });
const sendOf = (site) => call("sites/sendinvites", { site });

function itemEl(x) {
  return h("li", { class: x.done ? "ok" : "wait", "data-id": x.id },
    h("span", { class: "sl-ic", html: x.done ? TICK : DOT, "aria-hidden": "true" }),
    h("span", { class: "sl-w" }, x.words, x.more ? h("small", null, ` · ${x.more}`) : null),
    h("span", { class: "sl-at" }, x.done && x.at ? time(x.at, { label: false }) : ""),
    h("span", { class: "vh" }, x.done ? " (done)" : " (waiting)"));
}

/* The panel. onDone(live) once the set-up reads done; onState(live) after each answer.
   ask: {live, check, send} replace the calls (the tests). */
export function livePanel(site, { link = "", onDone = null, onState = null, more = null, ask = {} } = {}) {
  const get = ask.live || liveOf, check = ask.check || checkOf, send = ask.send || sendOf;
  const mark = h("span", { class: "sl-pill" });
  const checkBtn = h("button", { type: "button", class: "btn" }, "Check now");
  const list = h("ol", { class: "sl-list", "aria-label": "What has happened so far", "aria-live": "polite" });
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const checkOut = h("div", { class: "sl-check" });
  const doneBox = h("div", { class: "sl-done" });
  const peopleBox = h("div", { class: "sl-people" });
  const refusedBox = h("div", { class: "sl-refused" });
  const root = h("section", { class: "sl", "aria-label": `Live progress of ${site}` },
    h("div", { class: "sl-head" }, h("h4", null, "Live progress"), mark, h("span", { class: "grow" }), checkBtn),
    doneBox, list, refusedBox, peopleBox, said, checkOut);
  let live = null;
  let doneSeen = false;
  let timer = 0;
  const started = Date.now();

  function draw(r) {
    live = r;
    list.replaceChildren(...itemsOf(r).map(itemEl));
    const p = pillOf(r);
    mark.replaceChildren(p ? pill(p[0], p[1]) : "");
    root.dataset.state = r.state || "";
    if (r.state === "done") drawDone(r);
    else doneBox.replaceChildren();
    drawRefused(r);
    drawPeople(r);
    if (onState) onState(r);
    if (r.state === "done" && !doneSeen) { doneSeen = true; if (onDone) onDone(r); }
  }

  function drawDone(r) {
    const w = doneWords(r, site);
    const open = h("a", { class: "btn primary", href: `/traffic/${site}/#overview/summary` }, "Open the dashboard");
    const invite = h("a", { class: "btn", href: `/traffic/${site}/#settings/org/people` }, "Invite the people who will use it");
    doneBox.replaceChildren(answerBox("ok", r.recent ? "Receiving data" : "Set up", h("p", null, w.head),
      h("div", { class: "acts" }, open, invite)));
  }

  // The plain reason the last lines were refused, while it is newer than the data kept.
  function drawRefused(r) {
    const x = r.refused;
    refusedBox.replaceChildren(...(x ? [answerBox("bad", "Skald refused what was sent.", h("p", null, x.words),
      x.at ? h("p", { class: "note" }, `At ${time(x.at, { label: false })}. Fix it, send again, then press Check now.`) : null)] : []));
  }

  // Who gets an invite, and "Send the invites now" while they wait: before the data too (the
  // 24-hour mail sends the maker here), once sent the words of what was sent.
  function drawPeople(r) {
    const w = doneWords(r, site);
    let now = null;
    if (r.people && !r.invites_at) {
      now = h("button", { type: "button", class: "btn" }, "Send the invites now");
      now.addEventListener("click", async () => {
        now.disabled = true;
        const got = await send(site);
        if (!got?.ok) { now.disabled = false; said.textContent = why(got || {}, "The invites were not sent."); return; }
        said.textContent = got.invites?.words || "Sent.";
        once();
      });
    }
    const words = r.state !== "done" && r.people && !r.invites_at
      ? `${w.people.replace(/\.$/, "")}: it is sent as soon as the first data arrives.` : w.people;
    peopleBox.replaceChildren(...(words ? [h("p", null, words, now ? " " : "", now || "")] : []));
  }

  async function once() {
    clearTimeout(timer);
    if (root.isConnected === false) return;                  // the step or the dialog closed: stop
    if (typeof document !== "undefined" && document.hidden) return;   // asked again when shown
    const r = await Promise.resolve(get(site, link)).catch(() => null);
    if (root.isConnected === false) return;
    if (r && (r.status === 401 || r.status === 403 || r.status === 402)) {
      said.textContent = `${why(r, "Skald refused to show the progress.")} Sign in again, then reload this page.`;
      return;
    }
    if (!r || !r.ok) said.textContent = `${why(r || {}, "The progress could not be read.")} Trying again.`;
    else if (r.live) { said.textContent = ""; draw(r.live); }
    timer = setTimeout(once, delay(Date.now() - started));
  }

  checkBtn.addEventListener("click", async () => {
    checkBtn.disabled = true;
    checkOut.replaceChildren(h("p", { class: "empty" }, "Checking..."));
    const r = await Promise.resolve(check(site, link)).catch(() => null);
    checkBtn.disabled = false;
    if (!r || !r.ok) { checkOut.replaceChildren(answerBox("bad", why(r || {}, "The check could not run."), h("p", null, "Try again in a minute."))); return; }
    const c = r.check || {};
    checkOut.replaceChildren(answerBox(checkKind(c.verdict), c.head || "Checked.", c.says ? h("p", null, c.says) : null,
      c.fix ? h("p", null, c.fix) : null, ...(more && c.verdict !== "ok" ? [more(c)].flat().filter(Boolean) : []),
      c.tech ? fold("Technical details", [h("pre", { class: "sl-tech" }, c.tech)]) : null));
    if (r.live) draw(r.live);
  });

  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("visibilitychange", () => { if (!document.hidden && root.isConnected !== false) once(); });
  }
  root.refresh = once;
  root.state = () => live;
  setTimeout(once, 0);
  return root;
}

/* The pill for a site's row (Settings › Sites) or Overview's "Set up <site>", from one row
   of sites/live {all: true}; null when it says nothing. */
export function livePill(row) {
  const p = pillOf(row);
  return p ? pill(p[0], p[1]) : null;
}

/* Overview's "Set up <site>" (checklist.js): the same live state in one line, a pill and the
   lines of the last 15 minutes, asked while the set-up waits (every 5 s, then 30 s). */
export function liveBadge(site, { ask = () => call("sites/live", { site }) } = {}) {
  const el = h("span", { class: "sl-badge", "aria-live": "polite" });
  const started = Date.now();
  async function once() {
    if (el.isConnected === false) return;                    // left the page: stop
    if (typeof document !== "undefined" && document.hidden) { setTimeout(once, 30000); return; }
    const r = await Promise.resolve(ask()).catch(() => null);
    if (!r?.ok) return;                                   // no right, no helper: say nothing
    el.dataset.seen = "1";
    const v = r.live || {};
    const p = pillOf(v);
    el.replaceChildren(...(p ? [pill(p[0], p[1])] : []),
      v.recent ? h("small", null, ` ${Number(v.recent).toLocaleString("en-GB")} in the last 15 min`) : "");
    if (v.state === "waiting" || v.state === "receiving") setTimeout(once, delay(Date.now() - started));
  }
  setTimeout(once, 0);
  return el;
}

/* Every site's live state, asked every 5 s then 30 s while `el` is on the page. */
export function watchSites(el, onRows, { ask = () => call("sites/live", { all: true }) } = {}) {
  const started = Date.now();
  let timer = 0;
  async function once() {
    clearTimeout(timer);
    if (el.isConnected === false) return;
    if (typeof document !== "undefined" && document.hidden) { timer = setTimeout(once, 30000); return; }
    const r = await Promise.resolve(ask()).catch(() => null);
    if (el.isConnected === false) return;
    if (r?.ok) onRows(r.sites || {});
    else if (r && [401, 402, 403, 404].includes(r.status)) return;
    // Nothing left to wait for: no set-up still waiting, so ask again only slowly.
    const waiting = r?.ok && Object.values(r.sites || {}).some((x) => x.setup && x.state !== "done");
    timer = setTimeout(once, waiting ? delay(Date.now() - started) : 60000);
  }
  setTimeout(once, 0);
  return { stop: () => clearTimeout(timer), now: once };
}
