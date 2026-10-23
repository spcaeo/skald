// "Send set-up to someone" (2.30): everything to set up one site, in one zip that
// Skald's server makes: START-HERE.md, CLAUDE.md and AGENTS.md for an AI agent,
// secrets.env, and a folder each for the logs, the script tag and the leads.
// Sent by Skald's server to up to 3 addresses (POST <page>/sites/packmail), or
// saved here (POST <page>/sites/pack). Shown in three places:
//
//   the Set up checklist   "Send set-up to someone" (setup=pack, setup-dialogs.js)
//   the logs wizard        the Run step's "Email it to your server admin" (conn-send.js)
//   the leads wizard       the Set it up step (setup-hook.js)
//
// The keys go in unless the box is unticked. The page passes the sending token and
// the lead secret it holds (made in this page, kept in its memory only), so the
// server does not make new ones; without them the server makes them for the zip.
// The addresses stay in the form: never in the page's address. The box open is in the
// address as pack=1 beside the dialog's key (js/overlays.js), like share=1.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why } from "./forms.js";
import { postFile } from "./conn-install.js";
import { stepped } from "../overlays.js";
import { read } from "../state.js";

export const MAX_TO = 3;
export const PACK_WORDS = {
  keys: "Include the keys (sending token and lead secret)",
  careful: "Treat the mail like a password: anyone with it can send data for this site.",
  agent: "Your client can open START-HERE.md, or give the folder to Claude Code and say: Set up Skald from CLAUDE.md.",
};
const EMAIL = /^[^\s@,;<>"]+@[^\s@,;<>"]+\.[^\s@,;<>"]+$/;
export const packName = (site) => `skald-setup-${site}.zip`;

// The keys this page made, by site: "token" (the sending token: conn-send.js) and "lead"
// (the lead hook's secret: setup-hook.js). In this page's memory only, never stored.
const KEPT = { token: new Map(), lead: new Map() };
export const keepKey = (kind, site, value) => { if (value) KEPT[kind].set(site, value); };
export const keptKey = (kind, site) => KEPT[kind].get(site) || "";

/* The body of sites/pack, or of sites/packmail when `to` is given: the keys only when
   asked for and held by the page; the note only with a mail. No DOM, for the tests. */
export function packBody(site, { keys = true, token = "", secret = "", to = null, note = "" } = {}) {
  const body = { site, include_secrets: Boolean(keys) };
  if (to) body.to = to.slice(0, MAX_TO);
  if (keys && token) body.token = token;
  if (keys && secret) body.lead_secret = secret;
  if (to && String(note || "").trim()) body.note = String(note).trim();
  return body;
}

/* The addresses typed: {to} or {error}. */
export function packTo(values) {
  const to = values.map((v) => String(v || "").trim()).filter(Boolean);
  if (!to.length) return { error: "Type at least one email address." };
  const bad = to.find((x) => !EMAIL.test(x));
  if (bad) return { error: `"${bad}" is not an email address.` };
  return { to: [...new Set(to)].slice(0, MAX_TO) };
}

const sentWords = (r) => [`Sent to ${(r.sent_to || []).join(", ") || "them"}.`,
  r.token_id ? "Skald made a new sending token for it." : "", r.lead_secret_made ? "Skald made a new lead secret for it: the old one stops working." : ""].filter(Boolean).join(" ");

/* The box. token() and secret(): what the page holds now ("" when nothing). send and
   save are the two calls, replaceable in tests. */
export function packBox(site, { token = () => keptKey("token", site), secret = () => keptKey("lead", site),
  send = (body) => call("sites/packmail", body),
  save = (body) => postFile("sites/pack", body, packName(site), { failed: "The zip was not made" }) } = {}) {
  const tos = Array.from({ length: MAX_TO }, (_, i) => input({ type: "email", name: `pack-to-${i + 1}`, autocomplete: "off", maxlength: "200",
    placeholder: i ? "another address (optional)" : "admin@example.com", "aria-label": `Email address ${i + 1}` }));
  const note = h("textarea", { name: "pack-note", rows: "3", maxlength: "1000" });
  const keys = h("input", { type: "checkbox", name: "pack-keys" });
  keys.checked = true;
  const held = h("small");
  const showHeld = () => {
    const have = [token() ? "the sending token" : "", secret() ? "the lead secret" : ""].filter(Boolean);
    held.textContent = !keys.checked ? "The zip holds no key: send them separately."
      : have.length === 2 ? `${PACK_WORDS.careful} It holds the keys this page made.`
        : `${PACK_WORDS.careful} ${have.length ? `It holds ${have[0]} this page made; ` : ""}Skald makes ${have.length ? "the other" : "the keys"} for it.`;
  };
  keys.addEventListener("change", showHeld);
  showHeld();
  const mail = h("button", { type: "button", class: "btn primary" }, "Send by email");
  const zip = h("button", { type: "button", class: "btn" }, "Download (.zip)");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const say = (text, ok) => { said.textContent = text; said.className = `msg ${ok ? "ok" : "err"}`; };
  mail.addEventListener("click", async () => {
    const got = packTo(tos.map((x) => x.value));
    if (got.error) { say(got.error, false); return; }
    mail.disabled = true;
    const r = await send(packBody(site, { keys: keys.checked, token: token(), secret: secret(), to: got.to, note: note.value }));
    mail.disabled = false;
    if (!r || !r.ok) { say(why(r || {}, "The mail was not sent."), false); return; }
    say(sentWords(r), true);
  });
  zip.addEventListener("click", async () => {
    zip.disabled = true;
    const no = await save(packBody(site, { keys: keys.checked, token: token(), secret: secret() }));
    zip.disabled = false;
    if (no) { say(no, false); return; }
    say(`Saved ${packName(site)}.${keys.checked ? " It holds the keys: send it only to the person who sets the site up." : ""}`, true);
  });
  return h("div", { class: "su-pack" },
    h("p", null, `Everything to set up ${site} in one zip: the server's logs, the script tag and the leads, each with its steps.`),
    h("fieldset", { class: "su-pack-to" }, h("legend", null, "Send it to (up to 3)"), ...tos),
    field("A note for them (optional)", note, "Put in the mail above the steps."),
    h("label", { class: "chk" }, keys, h("span", null, h("b", null, PACK_WORDS.keys), held)),
    h("div", { class: "acts" }, mail, zip), said,
    h("p", { class: "note" }, PACK_WORDS.agent));
}

/* A button that opens the box in place (pack=1 in the address while open), and opens it
   at once when the address says so. getters: as packBox's. */
export function packToggle(site, words, getters = {}) {
  const box = h("div", { class: "su-pack-w" });
  const btn = h("button", { type: "button", class: "btn", "aria-expanded": "false" }, words);
  const mark = (on) => {
    const s = read();
    const fam = s.setup ? "setup" : s.conn ? "conn" : "";
    if (fam) stepped(fam, s[fam], { pack: on ? "1" : "" });
  };
  const show = (on) => {
    btn.setAttribute("aria-expanded", on ? "true" : "false");
    box.replaceChildren(...(on ? [packBox(site, getters)] : []));
  };
  btn.addEventListener("click", () => {
    const on = !box.firstChild;
    mark(on);
    show(on);
  });
  if (read().pack === "1") show(true);
  btn.box = box;
  return [btn, box];
}
