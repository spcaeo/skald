// "Set up this site" > Privacy settings chosen: the three IP choices of 2.15
// (privacy.keep_ips full | short | off), leads' names and emails
// (conversions.identity full | anonymous), saved with Settings' own save
// (POST settings/save; the IP choice is always sent, so the choice is
// recorded), then "Wording for your privacy notice" made again from the
// answer (people/notice.py, the answer's `notice`) with a Copy button.
// The words follow Settings > Privacy (prefs.js).

import { h, toast } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { wizard } from "./conn-ui.js";
import { choices } from "./setup-common.js";

export const IP_MODES = [
  { id: "full", title: "Full address", sub: "Each visit is kept with its whole IP address." },
  { id: "short", title: "Shortened (last part removed)", sub: "203.0.113.57 is kept as 203.0.113.0; an IPv6 address keeps its first 48 bits. The country and city still come from the full address. One shortened address can be several people." },
  { id: "off", title: "Don't keep", sub: "No address is kept with the visits. The visits already kept with one are deleted at the next nightly run." },
];
const IDENTITY = [
  { id: "full", title: "Keep them", sub: "Each lead's name and email are kept with its conversions, so a person can be looked up." },
  { id: "anonymous", title: "Don't keep them", sub: "Leads are counted without a name or an email." },
];
const modeOf = (v) => (v === true ? "full" : v === false ? "off" : v || "full");

export function noticeBox(nt) {
  if (!nt || !Array.isArray(nt.items)) return h("p", { class: "empty" }, "The wording could not be made here. Settings > Privacy shows it.");
  const copy = h("button", { type: "button", class: "btn" }, "Copy");
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(nt.text); toast("Copied the wording"); } catch { toast("Copy is not allowed here; select the text instead"); }
  });
  return h("section", { class: "sheet acct-card notice-card" }, h("h2", null, "Wording for your privacy notice"),
    h("p", { class: "sub" }, "Made from this site's settings, so it says what is kept. Fill in or delete the parts in [square brackets] before you use it."),
    h("p", { class: "note" }, nt.note || "A starting point, not legal advice. Your notice must match your own situation."),
    h("div", { class: "notice-text" }, h("p", null, nt.intro), h("ul", null, nt.items.map((line) => h("li", null, line)))),
    h("div", { class: "acts" }, copy));
}

export async function privacyDialog(site, { onClose = null, route = null, start = 0, wrap = null } = {}) {
  const r = await call("settings");
  const s = r.ok ? r.settings || {} : {};
  const st = { ips: modeOf(s["privacy.keep_ips"]?.value), id: s["conversions.identity"]?.value || "full", was: modeOf(s["privacy.keep_ips"]?.value), notice: r.notice || null };
  const locked = (k) => (s[k] && !s[k].editable ? s[k].reason || "You cannot change this." : "");
  return wizard({ route, start, wrap,
    title: "Choose what is kept about visitors", subtitle: `For ${site}.`, key: "setup-privacy", onClose, state: st,
    steps: [
      { name: "IP addresses",
        draw: (w) => {
          const note = h("p", { class: "note" });
          const say = () => { note.textContent = st.ips === "short" && st.was === "full" ? "The addresses already kept are shortened at the next nightly run." : st.ips === "full" && st.was === "short" ? "Only new visits are kept in full: the ones kept before stay shortened." : ""; };
          say();
          return [!r.ok ? h("p", { class: "msg err" }, why(r, "The settings could not be loaded.")) : null,
            h("p", null, "Keeping each visit's address lets an admin look a person up and follow their visits. Your privacy notice must say what you keep."),
            locked("privacy.keep_ips") ? h("p", { class: "msg err" }, locked("privacy.keep_ips")) : choices(st, "ips", IP_MODES, "Keep visitors' IP addresses", () => { say(); w.say(""); }), note];
        },
        check: () => (!r.ok ? why(r, "The settings could not be loaded.") : "") },
      { name: "Names and emails",
        draw: () => [h("p", null, "When a lead comes from a form or a booking, should Skald keep the person's name and email?"),
          locked("conversions.identity") ? h("p", { class: "msg err" }, locked("conversions.identity")) : choices(st, "id", IDENTITY, "Leads' names and emails")],
        next: async (w) => {
          const body = {};
          if (!locked("privacy.keep_ips")) body["privacy.keep_ips"] = st.ips;
          if (!locked("conversions.identity") && (st.id !== s["conversions.identity"]?.value || s["conversions.identity"]?.source === "default")) body["conversions.identity"] = st.id;
          if (!Object.keys(body).length) return true;
          const got = await call("settings/save", body);
          if (!got.ok) { w.say(why(got, "It was not saved.")); return false; }
          Object.assign(s, got.settings || {});
          st.was = st.ips;
          st.notice = got.notice || st.notice;
          return true;
        } },
      { name: "Your privacy notice",
        draw: () => [h("p", { class: "msg ok" }, "Saved. Copy this wording into your privacy notice."), noticeBox(st.notice),
          h("p", { class: "note" }, "You can change both choices later in Settings > Privacy.")] },
    ],
  });
}
