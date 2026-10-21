// "Send this site's visits to Skald": the dialog in Settings > Connections,
// and the steps the "Add a site" wizard shares with it (site-wizard.js):
// choose how, a sending token, install, test.
//
// The sending token is made with the tokens endpoint (team_api.py,
// tokens/create, scope ingest, this site only) and kept in this page's memory
// only, like tokens.js. The Test reads <page>/sites/status (connections_api.py)
// and polls it every 5 seconds for up to 2 minutes after the first press.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why } from "./forms.js";
import { time } from "../tz.js";
import { METHODS, methodOf, REASON_FIX, TROUBLE } from "./conn-words.js";
import { wizard, codeBlock, answerBox, helpLink } from "./conn-ui.js";
import { installFor } from "./conn-install.js";
import { shareBox } from "./conn-share.js";

export const POLL_MS = 5000;
export const POLL_FOR_MS = 120000;

// Sending tokens made in this page, by site: {token, name, id}. Never stored anywhere else.
const FRESH = new Map();
export const freshFor = (site) => FRESH.get(site) || null;

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

export function methodChooser(st, onPick = null) {
  const name = `how-${Math.random().toString(36).slice(2, 8)}`;
  return h("fieldset", { class: "cn-ways" }, h("legend", { class: "vh" }, "How should Skald get this site's visits?"),
    METHODS.map((x) => {
      const radio = h("input", { type: "radio", name, value: x.id });
      radio.checked = st.method === x.id;
      radio.addEventListener("change", () => { st.method = x.id; if (onPick) onPick(x.id); });
      return h("label", { class: `cn-way${x.best ? " best" : ""}` }, radio,
        h("span", null, h("b", null, x.title, x.best ? h("em", null, " Recommended") : null), h("small", null, x.sub)));
    }));
}

export const chooseCheck = (st) => (st.method ? "" : "Choose how the visits get to Skald.");

// ----------------------------------------------------------------- token

export function tokenPanel(st, { onMade = null } = {}) {
  if (st.method === "script") return [h("p", null, "The script tag needs no token: the page sends its events itself. Press Next.")];
  const slot = h("div");
  const name = input({ name: "token-name", autocomplete: "off", maxlength: "60" });
  name.value = `Sending logs: ${st.site}, ${today()}`;
  const make = h("button", { type: "button", class: "btn primary" }, "Make a sending token");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const show = () => {
    const got = freshFor(st.site);
    if (!got) { slot.replaceChildren(); return; }
    slot.replaceChildren(h("div", { class: "state ok", role: "status" }, h("div", null,
      h("p", null, h("strong", null, `"${got.name}". `), "Copy it now: it is shown only this once. It can only send logs for ", h("b", null, st.site), "."),
      codeBlock(got.token, "the sending token"),
      h("p", { class: "note" }, "The next step fills it in for you. Only a fingerprint of it is kept on the server."))));
  };
  make.addEventListener("click", async () => {
    const words = name.value.trim();
    if (!words) { said.textContent = "Give the token a name first."; said.className = "msg err"; return; }
    make.disabled = true;
    const r = await call("tokens/create", { name: words, sites: [st.site], scopes: ["ingest"] });
    make.disabled = false;
    if (!r.ok || !r.token) { said.textContent = why(r, "The token was not made."); said.className = "msg err"; return; }
    FRESH.set(st.site, { token: r.token, name: words, id: r.id || "" });
    st.token = r.token;
    st.tokenId = r.id || "";
    said.textContent = "";
    show();
    if (onMade) onMade(r);
  });
  show();
  return [
    h("p", null, "A sending token lets the shipper or the platform add log lines to this one site, and nothing else. It cannot read anything."),
    field("Name", name, "What it is for, so Your tokens says whose it is. You can change it."),
    h("div", { class: "acts" }, make), said, slot,
    h("p", { class: "note" }, "Already have one? Press Next: the steps show <token> where it goes."),
  ];
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
    return { kind: "wait", head: "Waiting for the first event. Nothing from the tag has reached Skald yet.", fix: "Open a page of the site in a normal browser window, with Do Not Track and Global Privacy Control off. In the browser's developer tools, Network panel, a request to /traffic-beacon answered 204 or 202 means the tag works; 403 means the page's host is not one of the site's host names; 404 means the two addresses are not passed on to Skald." };
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
   first press, until connected; stops when the dialog is gone. */
export function testPanel(st, { onResult = null, statusOf = (site) => call(`sites/status?site=${encodeURIComponent(site)}`) } = {}) {
  const out = h("div", { class: "cn-test-out" });
  const btn = h("button", { type: "button", class: "btn primary" }, "Test connection");
  let timer = null, until = 0;
  const shipper = st.method === "docker" || st.method === "systemd";
  async function once() {
    const r = await statusOf(st.site);
    const v = verdict(r, st.method);
    const polling = Date.now() < until && v.kind !== "ok";
    const more = [];
    if (v.fix) more.push(h("p", null, v.kind === "ok" ? v.fix : ["What to do: ", v.fix]));
    if (v.kind !== "ok" && shipper) more.push(h("p", null, "On the web server, run check.sh from the kit: ", h("code", null, "sudo bash check.sh"), ". It checks each part and says what to fix."));
    if (polling) more.push(h("p", { class: "note" }, "Checking again every 5 seconds, for up to 2 minutes."));
    if (v.kind === "wait" && !polling && until) more.push(h("p", null, "Nothing arrived in 2 minutes. Look at Common problems below, then press Test connection again."));
    out.replaceChildren(answerBox(v.kind, v.head, ...more));
    if (onResult) onResult(v, r);
    if (polling && out.isConnected !== false) timer = setTimeout(once, POLL_MS);
    else { clearTimeout(timer); timer = null; btn.disabled = false; }
    return v;
  }
  btn.addEventListener("click", () => {
    clearTimeout(timer);
    until = Date.now() + POLL_FOR_MS;
    btn.disabled = true;
    once();
  });
  return h("div", { class: "cn-test" },
    h("p", null, st.method === "script" ? "After a page of the site was opened with the tag, press Test connection." : "After the install, press Test connection. Skald says what it received, or why it refused it."),
    h("div", { class: "acts" }, btn), out);
}

// "Share with your developer" for the chosen way (conn-share.js).
export function shareFor(st) {
  if (!st.method) return "";
  return st.method === "script" ? shareBox(st.site, "script") : shareBox(st.site, "send", st.method === "vercel" ? "vercel" : st.method);
}

// ------------------------------------------------- the Connections dialog

export function sendDialog(site, data, { onClose = null } = {}) {
  const st = sendState(site, data);
  return wizard({
    title: "Send this site's visits to Skald", subtitle: `For ${site}, when its web server is not this Skald's server.`,
    key: "conn-send", state: st, onClose,
    steps: [
      { name: "Choose how", draw: (w) => [h("p", null, "Where does the site run? Choose the way its visits reach Skald."), methodChooser(st, () => w.say(""))], check: () => chooseCheck(st) },
      { name: "Sending token", draw: () => tokenPanel(st) },
      { name: "Install", draw: () => [h("p", { class: "sub" }, `${methodOf(st.method)?.title || ""}. The send address: `, h("code", null, st.url)), ...installFor(st.method, st), shareFor(st)] },
      { name: "Test", draw: () => [testPanel(st), troubleTable()] },
    ],
  });
}
