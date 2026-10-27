// "Send this site's visits to Skald": the dialog in Settings > Data > Send logs,
// and the steps the "Add a site" wizard shares with it (site-wizard.js):
// where it runs, then for a server one command and the test (2.30); for
// Cloudflare and Vercel a sending token, install, test; for the tag install, test.
//
// Step 1 shows the site check's card (conn-detect.js) and chooses its way.
// The server way's command comes from POST <page>/sites/link {site}: Skald makes
// the sending token itself and answers {command, url, expires_at, token,
// token_id}, a one-time `curl ... | sudo bash` that works once, for 24 hours. It is
// asked for once, when the Run step is first drawn, and kept in this page's memory
// only (LINKS), like the token. Cloudflare's and Vercel's token is made with the
// tokens endpoint (team_api.py, tokens/create, scope ingest, this site only) when
// their token step is drawn, and kept in this page's memory only (FRESH), like
// tokens.js. The Test reads <page>/sites/status (connections_api.py) and polls it
// every 5 seconds for up to 2 minutes, from when the step is shown. For the script
// tag, when nothing has arrived, it also looks at the site's home page once per
// press (conn-tagcheck.js) and says what is wrong there.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { time } from "../tz.js";
import { METHODS, methodOf, wayId, REASON_FIX, TROUBLE } from "./conn-words.js";
import { wizard, codeBlock, answerBox, helpLink } from "./conn-ui.js";
import { installFor, byHandFold, downloadKit, kitOn, kitName } from "./conn-install.js";
import { shareBox } from "./conn-share.js";
import { tagCheckBox } from "./conn-tagcheck.js";
import { detectCard, recommendFor, suggestionsFor, saveFound } from "./conn-detect.js";
import { packToggle, keepKey } from "./setup-pack.js";
import { withUrl } from "../urlactions.js";

export const POLL_MS = 5000;
export const POLL_FOR_MS = 120000;

// Sending tokens made in this page, by site: {token, name, id}. Never stored anywhere else.
const FRESH = new Map();
export const freshFor = (site) => FRESH.get(site) || null;
// The server way's one-time commands made in this page, by site: {command, expires_at,
// token_id}. Never in the address, never stored anywhere else.
const LINKS = new Map();
export const linkFor = (site) => LINKS.get(site) || null;
const MAKING = new Map();      // site -> the sites/link or tokens/create on its way, asked once

const today = () => new Date().toISOString().slice(0, 10);

// What the page knows for one site: GET sites' answer (`data`) and the site.
export function sendState(site, data = {}) {
  const base = String(data.ingest_url || "").replace(/\/traffic-ingest\/?$/, "");
  const usable = base && !base.includes("<");
  const origin = usable ? base : location.origin;
  return { site, method: "", token: freshFor(site)?.token || "", tokenId: freshFor(site)?.id || "",
    base: origin, url: `${origin}/traffic-ingest/${site}`, kit: data.kit || null,
    beaconOn: data.beacon_on !== false, ingestOn: data.ingest_enabled !== false };
}

// ------------------------------------------------------------ choose how

/* The ways, as radio buttons. `rec` ({id, reason, site}, from the site check,
   conn-detect.js) marks one "Recommended for <site>" with its reason, in place
   of the general "Recommended". */
export function methodChooser(st, onPick = null, rec = null) {
  const name = `how-${Math.random().toString(36).slice(2, 8)}`;
  return h("fieldset", { class: "cn-ways" }, h("legend", { class: "vh" }, "How should Skald get this site's visits?"),
    METHODS.map((x) => {
      const radio = h("input", { type: "radio", name, value: x.id });
      radio.checked = wayId(st.method) === x.id;
      radio.addEventListener("change", () => { st.method = x.id; st.methodBy = "owner"; if (onPick) onPick(x.id); });
      const mine = rec && rec.id === x.id;
      const badge = mine ? h("em", { class: "cn-rec" }, ` Recommended for ${rec.site}`) : !rec && x.best ? h("em", null, " Recommended") : null;
      return h("label", { class: `cn-way${x.best ? " best" : ""}${mine ? " rec" : ""}` }, radio,
        h("span", null, h("b", null, x.title, badge), h("small", null, x.sub), mine && rec.reason ? h("small", { class: "cn-why" }, rec.reason) : null));
    }));
}

/* The check's way, chosen for the owner when nothing is chosen yet (or the
   last choice was the check's own). Turning "Use these" off takes it back. */
export function preselect(st, rec) {
  if (rec && (!st.method || st.methodBy === "found")) { st.method = rec.id; st.methodBy = "found"; }
  else if (!rec && st.methodBy === "found") { st.method = ""; st.methodBy = ""; }
}

export const chooseCheck = (st) => (st.method ? "" : "Choose how the visits get to Skald.");

// ----------------------------------------------------------------- token

/* Cloudflare's and Vercel's step: the sending token, made as soon as the step is shown
   (none made in this page yet); "Make another token" for a new one. */
export function tokenPanel(st, { onMade = null } = {}) {
  if (wayId(st.method) === "script") return [h("p", null, "The script tag needs no token: the page sends its events itself. Press Next.")];
  const slot = h("div");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const another = h("button", { type: "button", class: "btn" }, "Make another token");
  const show = () => {
    const got = freshFor(st.site);
    if (!got) { slot.replaceChildren(); return; }
    st.token = got.token;
    st.tokenId = got.id;
    slot.replaceChildren(h("div", { class: "state ok", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `"${got.name}". `), "Copy it now: it is shown only this once. It can only send logs for ", h("b", null, st.site), "."),
      codeBlock(got.token, "the sending token"),
      h("p", { class: "note" }, "The next step fills it in for you. Only a fingerprint of it is kept on the server."))));
  };
  const make = async () => {
    another.disabled = true;
    said.className = "msg";
    said.textContent = "Making the sending token...";
    const name = `Sending logs: ${st.site}, ${today()}`;
    if (!MAKING.has(`t:${st.site}`)) {
      MAKING.set(`t:${st.site}`, call("tokens/create", { name, sites: [st.site], scopes: ["ingest"] }).then((r) => {
        MAKING.delete(`t:${st.site}`);
        if (r.ok && r.token) { FRESH.set(st.site, { token: r.token, name, id: r.id || "" }); keepKey("token", st.site, r.token); }
        return r;
      }));
    }
    const r = await MAKING.get(`t:${st.site}`) || {};
    another.disabled = false;
    if (!r.ok || !r.token) { said.textContent = why(r, "The token was not made."); said.className = "msg err"; return; }
    said.textContent = "";
    show();
    if (st.onToken) st.onToken();       // the install kit's token choice (conn-install.js)
    if (onMade) onMade(r);
  };
  another.addEventListener("click", make);
  if (freshFor(st.site)) show(); else make();
  return [
    h("p", null, "A sending token lets the platform add log lines to this one site, and nothing else. It cannot read anything. It is in Settings > AI assistants > Tokens & links, named for this site and today."),
    said, slot, h("div", { class: "acts" }, another),
    h("p", { class: "note" }, "Already have one? Press Next: the steps show <token> where it goes."),
  ];
}

// ------------------------------------------------- the server way: one command

/* POST sites/link once per site and page (a second draw waits for the same answer). */
export function makeLink(st) {
  const key = `l:${st.site}`;
  if (!MAKING.has(key)) {
    MAKING.set(key, call("sites/link", { site: st.site }).then((r) => {
      MAKING.delete(key);
      if (r.ok && r.command) {
        LINKS.set(st.site, { command: r.command, expires_at: r.expires_at || "", token_id: r.token_id || "" });
        if (r.token) { FRESH.set(st.site, { token: r.token, name: `Sending logs: ${st.site}, ${today()}`, id: r.token_id || "" }); keepKey("token", st.site, r.token); }
      }
      return r;
    }));
  }
  return MAKING.get(key);
}

/* False when the link is past its time or the server says it was used (410 to a HEAD,
   which never uses it up); true when it cannot tell, so a network fault keeps it. */
export async function stillGood(got, ask = (url) => fetch(url, { method: "HEAD", cache: "no-store", credentials: "omit" })) {
  if (got.expires_at && Date.parse(got.expires_at) <= Date.now()) return false;
  const url = String(got.command || "").split(" ").find((x) => /\/traffic-kit\//.test(x));
  if (!url) return true;
  try { return (await ask(url)).status !== 410; } catch { return true; }
}

/* The server way's Run step: the one-time command (asked for on the first draw), one file
   with the same token, the set-up by mail, and the older ways by hand. */
export function runPanel(st, w, { onMade = null } = {}) {
  const got = linkFor(st.site);
  const slot = h("div", { class: "cn-run" });
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const again = h("button", { type: "button", class: "btn" }, got ? "Make a new command" : "Try again");
  const ask = async () => {
    again.disabled = true;
    const r = await makeLink(st);
    again.disabled = false;
    if (!r.ok || !r.command) {
      again.hidden = false;
      slot.replaceChildren(answerBox("bad", why(r, "The command was not made."), h("p", null, "Press Try again, or use the other ways below.")));
      return;
    }
    if (onMade) onMade(r);
    if (slot.isConnected !== false) w.redraw();       // drawn again with the command and its token
  };
  again.addEventListener("click", () => { LINKS.delete(st.site); slot.replaceChildren(h("p", { class: "empty" }, "Making a new command...")); ask(); });
  const fresh = freshFor(st.site);
  if (fresh) { st.token = fresh.token; st.tokenId = fresh.id; }
  const out = [h("p", null, `One command installs a small program on the web server of ${st.site}. It works with or without Docker, finds the access log by itself, and never changes nginx, Apache or the website.`), slot];
  if (!got) {
    again.hidden = true;
    slot.replaceChildren(h("p", { class: "empty" }, "Making the command..."));
    ask();
    return [...out, h("div", { class: "acts" }, again), byHandFold(st), shareFor(st)];
  }
  // A command already used (or past its 24 hours) is not shown again: a HEAD never uses it up.
  stillGood(got).then((ok) => { if (!ok && linkFor(st.site) === got) { LINKS.delete(st.site); if (slot.isConnected !== false) w.redraw(); } });
  slot.replaceChildren(codeBlock(got.command, "the install command"),
    h("p", null, `Paste it on the web server of ${st.site}. It works once, for 24 hours.`),
    h("p", { class: "note" }, `It holds this site's sending token, so send it only to the site's admin. ${st.testBelow ? "Skald tests it below by itself." : "Then press Next: the Test starts by itself."}`));
  const file = kitOn(st, "server") ? h("button", { type: "button", class: "btn" }, "Download as one file") : null;
  if (file) {
    file.addEventListener("click", async () => {
      file.disabled = true;
      const no = await downloadKit(st, "server", Boolean(st.token));
      file.disabled = false;
      said.textContent = no || `Saved, with the token in it. On the server: sudo bash ${kitName(st.site, "server")}. Send it only to the site's admin.`;
      said.className = `msg ${no ? "err" : "ok"}`;
    });
  }
  const [mail, box] = packToggle(st.site, "Email it to your server admin");
  return [...out, h("div", { class: "acts" }, file, mail, again), said, box, byHandFold(st), shareFor(st)];
}

// --------------------------------------------------------------- the Test

const lower = (s) => String(s || "").replace(/^./, (c) => c.toLowerCase());
const stampOf = (ts) => Date.parse(ts || "") || 0;
function rel(ts, now = Date.now()) {
  const sec = Math.round((now - stampOf(ts)) / 1000);
  if (!stampOf(ts) || sec < 0) return "";
  return sec < 60 ? "just now" : sec < 3600 ? `${Math.floor(sec / 60)} min ago` : sec < 86400 ? `${Math.floor(sec / 3600)} h ago` : `${Math.floor(sec / 86400)} days ago`;
}
const at = (ts) => `${time(ts, { label: false })}${rel(ts) ? ` (${rel(ts)})` : ""}`;

/* What sites/status says, in plain words: {kind: ok|wait|bad, head, fix, reason}.
   No DOM, so tests/js/connections.mjs checks it directly. */
export function verdict(r, method) {
  if (!r || !r.ok) return { kind: "bad", head: why(r || {}, "The status could not be read."), fix: "" };
  if (method === "script") {
    if (!r.beacon) return { kind: "bad", head: "The script tag is switched off on this server.", fix: "Ask whoever runs your Skald server to turn it on (SKALD_BEACON_ORIGINS, or beacon.origins in its config)." };
    if (r.beacon.events > 0) return { kind: "ok", head: `Connected: ${r.beacon.events.toLocaleString("en-GB")} events on ${r.beacon.day}, the counters last written at ${at(r.beacon.updated_at)}.`, fix: "" };
    if (r.beacon.last_open_at) return { kind: "ok", head: `Connected: a page opened with the tag at ${at(r.beacon.last_open_at)}. No event is counted yet.`, fix: "" };
    return { kind: "wait", head: "Waiting for the first event. Nothing from the tag has reached Skald yet.", fix: "Open a page of the site in a normal browser window, with Do Not Track and Global Privacy Control off. In the browser's developer tools, Network panel, a request to traffic-beacon answered 204 or 202 means the tag works; 403 means the page's host is not one of the site's host names. A request to your own site's /traffic-beacon answered 308, 404 or 405 means an older tag or script: copy the tag again from step 2." };
  }
  if (r.ingest_enabled === false) return { kind: "bad", head: "The log endpoint is switched off on this server.", fix: REASON_FIX.off, reason: "off" };
  if (r.verify && r.verify.state === "pending") return { kind: "bad", head: "The site is not verified yet, so nothing is collected for it.", fix: REASON_FIX.not_verified, reason: "not_verified" };
  const ref = r.last_refusal;
  if (ref && stampOf(ref.at) > stampOf(r.last_contact)) {
    return { kind: "bad", head: `Refused at ${time(ref.at, { label: false })}: ${lower(ref.words)}`, fix: REASON_FIX[ref.reason] || REASON_FIX.other, reason: ref.reason };
  }
  const b = r.last_batch, t = r.today;
  if (b && !b.lines && b.rejected && !(t && t.lines)) {
    return { kind: "bad", head: `Lines arrive, but none could be read: ${b.rejected.toLocaleString("en-GB")} refused at ${at(b.at)}.`, fix: REASON_FIX.bad_format, reason: "bad_format" };
  }
  if (t && t.lines > 0) return { kind: "ok", head: `Connected: ${t.lines.toLocaleString("en-GB")} lines received today, the last at ${at(b ? b.at : r.last_contact)}.`, fix: "" };
  const g = r.received;
  if (b || (g && g.batches)) return { kind: "ok", head: `Connected before: the last lines came at ${at(b ? b.at : g.last_at)}. Nothing today yet.`, fix: "Open the site in a browser, then test again." };
  return { kind: "wait", head: "Waiting for the first lines. Nothing has reached Skald yet.", fix: "" };
}

export function troubleTable() {
  return h("details", { class: "fold cn-trouble" }, h("summary", null, "Common problems, and the fix"),
    h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Common problems"),
      h("thead", null, h("tr", null, ["What you see", "Likely cause", "Fix"].map((x) => h("th", { scope: "col" }, x)))),
      h("tbody", null, TROUBLE.map(([a, b, c]) => h("tr", null, h("td", null, a), h("td", null, b), h("td", null, c)))))),
    h("p", { class: "note" }, "More in ", helpLink("troubleshooting-connections", "If a connection does not work"), "."));
}

/* The Test button and its answer. Polls every POLL_MS for POLL_FOR_MS after the
   first press, until connected; stops when the dialog is gone. auto: starts when
   drawn, with no press (the dialogs; the shared link's page waits for the press). */
export function testPanel(st, { onResult = null, statusOf = (site) => call(`sites/status?site=${encodeURIComponent(site)}`), pageCheck = tagCheckBox, auto = false, plain = false } = {}) {
  const out = h("div", { class: "cn-test-out" });
  const page = h("div", { class: "cn-test-page" });
  // plain (2.42, Add a site): the step's one main button is elsewhere; this one tests again.
  const btn = h("button", { type: "button", class: plain ? "btn" : "btn primary" }, "Test connection");
  let timer = null, until = 0, looked = false;
  const shipper = wayId(st.method) === "server";
  async function once() {
    const r = await statusOf(st.site);
    const v = verdict(r, st.method);
    const polling = Date.now() < until && v.kind !== "ok";
    const more = [];
    if (v.fix) more.push(h("p", null, v.kind === "ok" ? v.fix : ["What to do: ", v.fix]));
    // Every server way, a wizard saved before 2.30 ("docker", "systemd") too: the one command left skald-ship-check.
    if (v.kind !== "ok" && shipper) more.push(h("p", null, "On the web server, run ", h("code", null, "sudo skald-ship-check"), ": it checks each part and says what to fix (an older zip kit has ", h("code", null, "sudo bash check.sh"), " in its folder). What the shipper says: ", h("code", null, "sudo docker logs --tail 20 skald-ship"), " with Docker, or ", h("code", null, "journalctl -u skald-ship -n 20"), " without."));
    if (polling) more.push(h("p", { class: "note" }, "Checking again every 5 seconds, for up to 2 minutes."));
    if (v.kind === "wait" && !polling && until) more.push(h("p", null, "Nothing arrived in 2 minutes. Look at Common problems below, then press Test connection again."));
    out.replaceChildren(answerBox(v.kind, v.head, ...more));
    // Nothing from the tag yet: look at the page itself, once per press.
    if (st.method === "script" && v.kind === "wait" && until && !looked && pageCheck) { looked = true; page.replaceChildren(pageCheck(st.site)); }
    if (v.kind === "ok") page.replaceChildren();
    if (onResult) onResult(v, r);
    if (polling && out.isConnected !== false) timer = setTimeout(once, POLL_MS);
    else { clearTimeout(timer); timer = null; btn.disabled = false; }
    return v;
  }
  const start = () => {
    clearTimeout(timer);
    until = Date.now() + POLL_FOR_MS;
    looked = false;
    btn.disabled = true;
    once();
  };
  btn.addEventListener("click", start);
  if (auto) start();
  const tag = wayId(st.method) === "script";
  const panel = h("div", { class: "cn-test" },
    h("p", null, auto ? (tag ? "Open a page of the site with the tag. Skald is looking now, and says what it received." : "Skald is looking now: it says what it received, or why it refused it. Run the install first, if not done yet.")
      : tag ? "After a page of the site was opened with the tag, press Test connection." : "After the install, press Test connection. Skald says what it received, or why it refused it."),
    h("div", { class: "acts" }, btn), out, page);
  panel.start = start;      // the agent's watch (agent-watch.js) looks again when the agent moves on
  return panel;
}

// "Share with your developer" for the chosen way (conn-share.js).
export function shareFor(st) {
  const way = wayId(st.method);
  if (!way) return "";
  return way === "script" ? shareBox(st.site, "script") : shareBox(st.site, "send", way);
}

// ------------------------------------------------- the Connections dialog

// Step 1 of the dialog: the site check's card for this site (checked once on
// opening), and the ways with the check's one chosen.
function chooseStep(w, st, site, onWay = null) {
  const ways = h("div");
  const saved = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const keep = h("button", { type: "button", class: "btn", hidden: true }, "Save the host names and page assets to this site");
  const drawWays = () => {
    const rec = recommendFor(st);
    preselect(st, rec);
    if (onWay) onWay();
    ways.replaceChildren(methodChooser(st, () => { w.say(""); if (onWay) onWay(); }, rec));
    const got = suggestionsFor(st, site);
    keep.hidden = !(got.hosts || got.asset_prefixes);
  };
  keep.addEventListener("click", async () => {
    keep.disabled = true;
    const r = await saveFound(st, site);
    keep.disabled = false;
    saved.className = `msg ${r.ok ? "ok" : "err"}`;
    saved.textContent = r.words;
  });
  const card = detectCard(st, { address: () => site, name: site, auto: true, onFound: drawWays });
  drawWays();
  return [card, h("div", { class: "acts" }, keep), saved, h("p", null, "Where does the site run? Choose the way its visits reach Skald."), ways];
}

/* The steps after "Where it runs", for the way chosen (none yet: the server's). The
   server way has no token step: sites/link makes the token with the command. */
export function stepsAfter(st) {
  const way = wayId(st.method) || "server";
  const test = { name: "Test", draw: () => [testPanel(st, { auto: true }), troubleTable()] };
  if (way === "server") return [{ name: "Run one command", draw: (w) => runPanel(st, w) }, test];
  const install = { name: "Install", draw: () => [h("p", { class: "sub" }, `${methodOf(way)?.title || ""}. The send address: `, withUrl(h("code", null, st.url), st.url, { cls: "ua-after" })), ...installFor(way, st), shareFor(st)] };
  return methodOf(way)?.token ? [{ name: "Sending token", draw: () => tokenPanel(st) }, install, test] : [install, test];
}

export function sendDialog(site, data, { onClose = null, route = null, start = 0, wrap = null } = {}) {
  const st = sendState(site, data);
  const steps = [];
  let w = null;
  // A way chosen (or found by the check): the later steps follow it, and the bar with them.
  const fit = () => { steps.splice(1, steps.length - 1, ...stepsAfter(st)); if (w) w.drawBar(); };
  steps.push({ name: "Where it runs", draw: (wz) => chooseStep(wz, st, site, fit), check: () => chooseCheck(st) }, ...stepsAfter(st));
  w = wizard({ route, start, wrap,
    title: "Send this site's visits to Skald", subtitle: `For ${site}, when its web server is not this Skald's server.`,
    key: "conn-send", state: st, onClose, steps });
  return w;
}
