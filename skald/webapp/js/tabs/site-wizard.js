// "Add a site" (Settings > Sites, and "+ Add a site" in the site picker), in two steps
// (2.42, the UX audit's task 10; before: five steps and 11 presses):
//
//   1 Your site     the address; Skald looks at the site while you type and says what it found
//                   in one line ("Runs on nginx · suggested: one command on the server"), and
//                   the time zone of your other sites (Change to type another); then "Who will
//                   connect it? Me / My developer / My AI agent" (ui/who.js, the last answer kept)
//   (Prove it's yours, only when this server asks for proof and the site is not verified)
//   2 Connect it    only the path chosen:
//                     Me        the way Skald found (Another way: the choices), its install (one
//                               command for a server), and Skald waits for the first lines
//                     My developer  a private link with the steps (conn-share.js), and the wait
//                     My AI agent   which agent, its line, and the watch under it: Skald ticks
//                               each step by itself (agent-setup.js, agent-watch.js)
//
// In the address: setup=new, then setup=<site> once step 1 made it, with step=<n> (its place in
// the bar), by=me|dev|agent, agent=<id> and link=<link id> (the line being watched, never the
// line or its code). A reload at any step comes back there. Older links still open: agent=hand
// is by=me, an agent's id is by=agent, and step=3, 4 or 5 is Connect it.
//
// The progress is kept on the server per site (POST <page>/sites/setup, accounts/site_setup.py)
// on its own scale of five: 1 the site, 2 the proof, 3 connecting, 4 a line or command made,
// 5 done; with the way ("agent" on the AI agent's way; a chat-only agent runs the server way's
// command, so "server") and the sending token's id (never the token). Closing loses nothing:
// the site's row offers "Finish setting up".
//
// 2.43: step 1 first asks which organisation and who will use it (site-wizard-org.js; org= and
// ppl= in the address); sites/add makes a new organisation with the site and keeps the people in
// its set-up row, invited once the first data arrives. Connect it (My AI agent, My developer)
// (every path) shows the live progress with Check now (setup-live.js); a set-up that is done, also opened from
// an old link, shows the done state and Close, never "Finish later".

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why } from "./forms.js";
import { wizard, codeBlock, answerBox, helpLink } from "./conn-ui.js";
import { sendState, methodChooser, tokenPanel, runPanel, troubleTable, preselect, shipperHelp } from "./conn-send.js";
import { detectCard, recommendFor, suggestionsFor, DETECT_WAIT_MS } from "./conn-detect.js";
import { installFor } from "./conn-install.js";
import { methodOf, wayId } from "./conn-words.js";
import { withUrl } from "../urlactions.js";
import { HAND, agentOf, agentKey, isLinkId } from "./agent-words.js";
import { agentChooser, linePanel, lineFor, wasCancelled } from "./agent-setup.js";
import { watchPanel } from "./agent-watch.js";
import { whoStep, WHO } from "../ui/who.js";
import { pill } from "../ui/pill.js";
import { fold } from "../ui/fold.js";
import { siteZone } from "../tz.js";
import { whoState, whoPart, whoBody, whoCheck } from "./site-wizard-org.js";
import { livePanel } from "./setup-live.js";
import { tagCheckBox } from "./conn-tagcheck.js";

export const STEPS = 5;           // the server's scale (accounts/site_setup.py STEPS)
const NAME = /^(?=.{3,100}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$/;
const BAD = "That is not a site's address. Type it like www.example.com.";

/* "https://WWW.Example.com/pricing" -> {name: "www.example.com"}, as the server
   makes it (saas/signups.py clean_host, accounts/site_configs.py clean_name). */
export function siteFrom(raw) {
  const typed = String(raw || "").trim().toLowerCase();
  if (!typed) return { error: "Type the site's address, like www.example.com." };
  if (/\s/.test(typed)) return { error: "An address has no spaces. Type it like www.example.com." };
  let host = "";
  try { host = new URL(`https://${typed.replace(/^[a-z][a-z0-9+.-]*:\/\//, "").replace(/^\/\//, "")}`).hostname; } catch { return { error: BAD }; }
  host = host.replace(/\.$/, "");
  if (!NAME.test(host) || /^[\d.]+$/.test(host)) return { error: BAD };
  return { name: host };
}

/* Who connects it, from the address and the saved progress: by= first, then the older
   agent= (hand is Me), then the saved way ("agent" is My AI agent, any other way is Me). */
export function byFrom({ by = "", agent = "", method = "" } = {}) {
  if (WHO.includes(by)) return by;
  const a = agentKey(agent);
  if (a === HAND) return "me";
  if (a) return "agent";
  if (method === "agent") return "agent";
  return method ? "me" : "";
}

// sites/setup, quietly: the wizard goes on even if a save fails, and says so.
async function save(w, body) {
  if (!w.state.site) return;
  const r = await call("sites/setup", { name: w.state.site, ...body });
  if (!r.ok) w.say(`Your progress was not saved: ${why(r)}`);
}

// The found facts as the progress keeps them, with the toggle.
const kept = (st) => ({ ...st.found, use: st.useFound !== false });

/* What Skald found, in one line: the server, and the way it suggests. */
export function foundWords(f) {
  if (!f) return "";
  if (!f.reachable) return `Skald could not reach ${f.site} from here: choose the way by hand.`;
  const server = f.server && f.server !== "unknown" ? `Runs on ${f.server_label || f.server}` : "Server not told";
  const platform = f.platform_label ? ` behind ${f.platform_label}` : "";
  const way = SHORT[wayId(f.recommended_method)];
  return `${server}${platform}${way ? ` · suggested: ${way}` : ""}`;
}
const SHORT = { server: "one command on the server", cloudflare: "the Cloudflare Worker", vercel: "a log drain from Vercel or Netlify", script: "the script tag only" };

// The time zone: the one of the site open here (your other sites), the browser's when none.
function zoneOf(st) {
  if (st.zone) return st.zone;
  let z = siteZone();
  if (!z || z === "UTC") { try { z = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { z = "UTC"; } }
  return z;
}

function stepSite(w, data) {
  const st = w.state;
  const sum = h("span", { class: "sw-found-w" });
  const mark = h("span");
  const line = h("p", { class: "sw-found", "aria-live": "polite" }, mark, sum);
  const show = (f, looking = "") => {
    sum.textContent = looking ? `Looking at ${looking}...` : foundWords(f);
    mark.replaceChildren(looking || !f ? "" : f.reachable ? pill("good", "found") : pill("warn", "not reached"));
    line.hidden = !looking && !f;
  };
  const onFound = (f, why2) => { show(f); if (why2 === "toggle" && f && st.site) save(w, { found: kept(st) }); };
  const who = whoStep({
    route: w.route, from: st.by, fallback: "me", question: "Who will connect it?",
    paths: { me: () => null, dev: () => null, agent: () => null },
    subs: { me: "I install it: Skald gives the steps and waits for the first visits.", dev: "Skald makes a private link with the steps to send them.", agent: "One line for Claude Code, Codex or Cursor. You watch it work." },
    onPick: (k) => { st.by = k; w.say(""); },
  });
  st.by = who.choice();
  if (st.by) w.keep({ by: st.by });          // the answer shown is the one in the address
  if (st.site) {
    const card = detectCard(st, { address: () => st.site, name: st.site, auto: !st.found, onFound });
    show(st.found);
    return [h("p", null, "The site: ", h("strong", null, st.site), "."), line, fold("What Skald found", [card]), who.el];
  }
  if (data.can_add === false) return [answerBox("bad", data.add_refused || "Adding sites is not available here.")];
  const addr = input({ name: "site-address", autocomplete: "off", inputmode: "url", maxlength: "200", placeholder: "www.example.com" });
  addr.value = st.typed || "";
  const card = detectCard(st, { address: () => siteFrom(addr.value).name || "", onFound });
  let timer = null;
  const say = () => {
    st.typed = addr.value;
    const got = siteFrom(addr.value);
    clearTimeout(timer);
    if (!got.name) { show(null); if (addr.value.trim() && got.error) { sum.textContent = got.error; line.hidden = false; } return; }
    if (got.name === st.found?.site) { show(st.found); return; }
    show(null, got.name);
    timer = setTimeout(async () => { const f = await card.run(); if (!f) show(null); }, DETECT_WAIT_MS);
  };
  addr.addEventListener("input", say);
  // The time zone: your other sites' (one line), Change to type another.
  const zone = input({ name: "timezone", autocomplete: "off", maxlength: "64", "aria-label": "Time zone" });
  zone.value = zoneOf(st);
  st.zone = zone.value;
  zone.addEventListener("input", () => { st.zone = zone.value; });
  const zoneBox = h("div", { class: "sw-zone-in", hidden: true }, field("Time zone", zone, "Days are counted in this zone, like Europe/London."));
  const change = h("button", { type: "button", class: "btn link", "aria-expanded": "false" }, "Change");
  change.addEventListener("click", () => { zoneBox.hidden = false; change.hidden = true; zone.focus?.(); });
  const zoneLine = h("p", { class: "sw-zone" }, h("span", null, "Time zone: "), h("b", null, zone.value), " ", change);
  say();
  return [field("Site address", addr), line, zoneLine, zoneBox, fold("What Skald found", [card]),
    whoPart(st.who, (p) => w.keep(p)), who.el];
}

function siteCheck(w) {
  const st = w.state;
  if (!st.site) {
    const got = siteFrom(st.typed);
    if (got.error) return got.error;
    const org = whoCheck(st.who);
    if (org) return org;
  }
  return st.by ? "" : "Choose who will connect it.";
}

async function makeSite(w) {
  const st = w.state;
  if (!st.site) {
    const got = siteFrom(st.typed);
    if (got.error) { w.say(got.error); return false; }
    const r = await call("sites/add", { host: got.name, timezone: String(st.zone || "").trim(), format: "auto", token: false, ...suggestionsFor(st, got.name), ...whoBody(st.who) });
    if (!r.ok) { w.say(why(r, "The site was not added.")); return false; }
    st.site = r.site;
    w.rename(r.site);         // setup=new becomes setup=<site>: a reload finds the site
    st.verify = r.verify || null;
    st.org = r.org || null;           // 2.43: where it went (a new organisation, or another of yours)
    Object.assign(st.send, sendState(r.site, st.data));
    if (st.found && st.found.site !== r.site) st.found = null;     // a check of another address
    if (st.onChange) st.onChange();
  }
  st.fit();
  if (st.by !== "agent") preselect(st.send, recommendFor(st));      // the found way, saved with the progress
  const proof = needsProof(st);
  await save(w, { step: proof ? 2 : 3, ...(proof ? {} : { method: methodNow(st) }), ...(st.found ? { found: kept(st) } : {}) });
  return true;
}

const needsProof = (st) => !!st.verify && st.verify.state !== "verified";
// The way saved with the progress: the agent's ("server" for a chat-only one), else the one chosen.
const methodNow = (st) => (st.by === "agent" ? (agentOf(st.agent)?.shell === false ? "server" : "agent") : wayId(st.send.method) || "");

function stepProve(w) {
  const st = w.state;
  const v = st.verify;
  if (!v || v.state === "verified") return [answerBox("ok", `${st.site} is verified.`, h("p", null, "Press Next."))];
  const out = h("div");
  const btn = h("button", { type: "button", class: "btn" }, "Check now");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const r = await call("sites/verify", { name: st.site });
    btn.disabled = false;
    if (!r.ok) { out.replaceChildren(answerBox("bad", why(r, "Not found yet."), h("p", null, "A new DNS record can take a few minutes to show. Try again soon."))); return; }
    st.verify = { state: "verified" };
    out.replaceChildren(answerBox("ok", `${st.site} is verified. Skald collects for it from now on.`));
    await save(w, { step: 3 });
  });
  return [h("p", null, "Show that the domain is yours. Nothing is collected for the site until then. Do one of these:"),
    h("p", null, h("b", null, "A DNS TXT record"), ` on ${st.site}:`), codeBlock(v.txt, "the TXT record"),
    h("p", null, h("b", null, "Or this tag"), ` in the <head> of https://${st.site}/:`), codeBlock(v.meta, "the meta tag"),
    h("div", { class: "acts" }, btn), out,
    h("p", { class: "note" }, "You can go on and install now; the check can wait. Lines sent before it are refused and sent again by the shipper later.")];
}

// ---------------------------------------------------------------- Connect it

const WHO_TITLE = { me: "Me", dev: "My developer", agent: "My AI agent" };

function connect(w) {
  const st = w.state;
  const back = h("button", { type: "button", class: "btn link" }, "Change");
  back.addEventListener("click", () => w.go(0));
  const who = h("p", { class: "sw-who" }, h("span", null, "Who connects it: "), h("b", null, WHO_TITLE[st.by] || "Me"), " ", back);
  if (st.done) { w.setDone("Close"); return [live(w)]; }
  const part = st.by === "agent" ? agentPart(w) : st.by === "dev" ? devPart(w) : mePart(w);
  // Every path ends with the live progress, once (waitPart places it; the agent's watch does not).
  // Me too: the 24-hour mail's link lands here, and its "Send the invites now" is in the panel.
  const out = [who, ...part];
  return out.includes(st.livePanel?.el) ? out : [...out, live(w)];
}

// 2.43: the live checklist (setup-live.js), kept across redraws of the step; done says Close.
function live(w) {
  const st = w.state;
  if (!st.livePanel || st.livePanel.site !== st.site || st.livePanel.link !== st.link) {
    // Done: the step shows only the done state (one "Open the dashboard"), and the button says Close.
    // The first data in: the set-up is saved done, as the old Test connection did (2.42), so the
    // view turns done at once (older set-ups too, which the server's own tick leaves alone).
    const onState = (r) => {
      if (st.liveHelp) st.liveHelp.hidden = r.state !== "waiting";
      if (r.state !== "receiving" || st.marking) return;
      st.marking = true;
      save(w, { step: STEPS, done: true }).then(() => st.livePanel?.el.refresh());
    };
    // Check now, nothing yet: the way's own help (the shipper's check, or the home page's tag).
    const more = () => {
      const way = wayId(st.send?.method);
      return way === "server" ? shipperHelp() : way === "script" ? tagCheckBox(st.site) : null;
    };
    const el = livePanel(st.site, { link: st.link, onState, more, onDone: () => { st.done = true; w.setDone("Close"); w.redraw(); } });
    st.livePanel = { site: st.site, link: st.link, el };
  }
  return st.livePanel.el;
}

// The wait for the first lines (Me, My developer and a chat-only agent's command): the live
// progress alone (2.43), the one source of truth with the one check, Check now. The old "Skald
// waits for the first visits" block and its Test connection are gone from Add a site.
function waitPart(w) {
  const st = w.state;
  // The common problems only while nothing has arrived (the live progress hides them after).
  const help = fold("Not connected yet?", () => [troubleTable(), h("p", { class: "note" }, "Or finish later: the site's row says how far it got, and ", helpLink("troubleshooting-connections", "the troubleshooting guide"), " has the common fixes.")]);
  const state = st.livePanel?.el.state()?.state;
  help.hidden = !!state && state !== "waiting";
  st.liveHelp = help;
  return [live(w), help];
}

function mePart(w) {
  const st = w.state;
  const send = st.send;
  send.testBelow = true;           // the install's words: the live progress is below, on this step
  const rec = recommendFor(st);
  preselect(send, rec);
  const way = wayId(send.method);
  if (!way || st.chooseWay) {
    const lost = st.found && !st.found.reachable ? h("p", { class: "note" }, `Skald could not reach ${st.found.site} to suggest a way.`) : null;
    return [h("p", null, "Where does the site run? Choose the way its visits reach Skald."), lost,
      methodChooser(send, () => { st.chooseWay = false; w.say(""); save(w, { step: 3, method: send.method }); w.redraw(); }, rec)].filter(Boolean);
  }
  const other = h("button", { type: "button", class: "btn link" }, "Another way");
  other.addEventListener("click", () => { st.chooseWay = true; w.redraw(); });
  const head = h("p", { class: "sw-way" }, h("b", null, methodOf(way)?.title || way), rec?.id === way ? " " : "", rec?.id === way ? pill("good", "found") : "", " ", other);
  const install = way === "server" ? [runPanel(send, w, { onMade: (r) => save(w, { step: 4, method: way, token_id: r.token_id || "" }) })]
    : [h("p", { class: "sub" }, "The send address: ", withUrl(h("code", null, send.url), send.url, { cls: "ua-after" })),
      ...(methodOf(way)?.token ? tokenPanel(send, { onMade: (r) => save(w, { step: 4, method: way, token_id: r.id || "" }) }) : []),
      ...installFor(way, send)];
  return [head, ...install, ...waitPart(w)];
}

function devPart(w) {
  const st = w.state;
  const rec = recommendFor(st);
  preselect(st.send, rec);
  const way = wayId(st.send.method) || "server";
  return [h("p", null, `Skald makes a private page with the steps for ${st.site}, filled in, with a Test button. Send its link to whoever runs the site's server or host.`),
    shareLink(st.site, way), ...waitPart(w)];
}

// conn-share.js's box, loaded when drawn (it reads the address for share=1).
function shareLink(site, way) {
  const slot = h("div");
  import("./conn-share.js").then(({ shareBox }) => slot.replaceChildren(way === "script" ? shareBox(site, "script") : shareBox(site, "send", way)));
  return slot;
}

function agentPart(w) {
  const st = w.state;
  const a = agentOf(st.agent);
  if (!a || st.agent === HAND) {
    return agentChooser(st, async (id) => {
      if (id === HAND) { st.by = "me"; st.agent = ""; w.keep({ by: "me", agent: "" }); w.redraw(); return; }
      st.agent = id;
      st.autoLine = true;       // chosen here: the line may be made at once
      w.keep({ agent: id });
      w.say("");
      await save(w, { step: 4, method: methodNow(st) });
      w.redraw();
    // No "Me" here: who connects it is asked once, in step 1 (ui/who.js); Change goes back there.
    }, { hand: null });
  }
  const other = h("button", { type: "button", class: "btn link" }, "Another agent");
  other.addEventListener("click", () => { st.agent = ""; st.link = ""; w.keep({ agent: "", link: "" }); w.redraw(); });
  const head = h("p", { class: "sw-way" }, h("b", null, a.title), " ", other);
  const line = () => [linePanel(st, w, { below: true, onMade: (r) => {
    if (r.link_id) w.keep({ link: r.link_id });
    save(w, { step: 4, method: methodNow(st), token_id: r.token_id || "" });
  } })].flat();
  if (a.shell === false) return [head, ...line(), ...waitPart(w)];
  // The line made on this page is the one watched (Another agent keeps it).
  const made = lineFor(st.site, st.jobs || null);
  if (made?.link_id && !st.cancelled && st.link !== made.link_id) { st.link = made.link_id; w.keep({ link: st.link }); }
  const watching = st.link && !st.cancelled && !wasCancelled(st.link);
  // heard: the live progress is the one check; the watch ticks its log line from it.
  const heard = () => ["receiving", "done"].includes(st.livePanel?.el.state()?.state);
  const watch = (cancel) => watchPanel(st, { cancel, heard, again: () => st.livePanel?.el.refresh(), onDone: () => save(w, { step: STEPS, done: true }).then(() => st.livePanel?.el.refresh()) });
  if (!watching) return [head, ...line()];
  // A line from before a reload is not shown again: the watch (with its Cancel), and a new line on request.
  if (!made) {
    const fresh = h("button", { type: "button", class: "btn" }, "Make a new line");
    fresh.addEventListener("click", () => { st.link = ""; st.autoLine = true; w.keep({ link: "" }); w.redraw(); });
    return [head, h("p", { class: "sw-sent" }, "The line was made before this page was reloaded, so it is not shown again. Skald keeps watching it. ", fresh), watch(true)];
  }
  return [head, ...line(), h("h4", null, "Skald watches your agent"), watch(false)];
}

// ---------------------------------------------------------------- the wizard

/* In the address as setup=new or setup=<site> (js/overlays.js; Settings > Sites: tabs/sitesadmin.js
   openSiteKey reopens it from a link). start: on the server's scale, from 0 (0 the site, 1 the
   proof, 2 to 4 connecting). by: the address's (or worked out by byFrom); agent: an agent's id or
   hand; link: the line the watch follows. */
export function siteWizard({ data = {}, name = null, start = 0, method = "", verify = null, found = null, onChange = null, agent = "", link = "", by = "", org = "", ppl = "", sees = "", done = false } = {}) {
  const send = sendState(name || "", data);
  const a = agentKey(agent);
  const who = byFrom({ by, agent, method });
  send.method = who === "agent" ? (agentOf(a)?.shell === false ? "server" : "") : wayId(method === "agent" ? "" : method);
  const state = { site: name, verify, data, send, onChange, typed: "", zone: "", found: found || null, useFound: found ? found.use !== false : true,
    by: who, agent: a && a !== HAND ? a : "", link: isLinkId(link) ? link : "", who: whoState({ org, ppl, sees }), done: !!done };
  const site = { name: "Your site", draw: (wz) => stepSite(wz, data), check: siteCheck, next: makeSite };
  const prove = { name: "Prove it's yours", draw: stepProve, next: async (wz) => { await save(wz, { step: 3, method: methodNow(wz.state) }); return true; } };
  const conn = { name: "Connect it", draw: connect };
  const steps = [];
  let w = null;
  state.fit = () => { steps.splice(0, steps.length, site, ...(state.site && needsProof(state) ? [prove] : []), conn); if (w) w.drawBar(); };
  state.fit();
  // The server's scale to a place in the bar: the proof only when it is a step; 2 to 4 are Connect it.
  const at = done ? steps.length - 1 : start <= 0 ? 0 : start === 1 && steps.includes(prove) ? 1 : steps.length - 1;
  const route = { key: "setup", value: name || "new" };
  w = wizard({
    title: name ? `Set up ${name}` : "Add a site", subtitle: "Two short steps. You can close this and continue later: nothing is lost.",
    key: "site-wizard", state, start: at, done: done ? "Close" : "Finish later", route,
    onClose: () => { if (onChange) onChange(); },
    steps,
  });
  // The answers stay in the address (the wizard writes its step itself).
  w.keep({ by: state.by, agent: state.agent, link: state.link });
  return w;
}
