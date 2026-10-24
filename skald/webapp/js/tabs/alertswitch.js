// Site > Alerts: the switches (2.13.0). With accounts (access.mode: sessions) an
// admin turns alerts, their mail and each rule on or off here: the settings_store
// keys alerts.enabled, alerts.mail and alerts.<rule> (the names in config.yml's
// `alerts` section; alerts.json gives each rule's key as `setting`), saved for this
// site through settings/save, audited there, and used from the next live run.
// A key config.yml locks (settings.locked) stays read-only with the reason; a
// viewer sees the switches disabled with theirs. Without accounts, and in the
// demo, the switches show alerts.json's state and say where it is set.
//
// The sale alerts (alerts_sales.py) also have alerts.sale_minimum: the least amount per
// currency that alerts ("USD 100, EUR 90.50"; empty: any amount), edited in the row under
// the sale switch, on this same tab (#site/alerts).
//
//   switchboard(f, CAUSE) -> {banner, list}: two elements that fill themselves
//   once the settings have loaded, and redraw after every save.

import { h, ICON } from "../ui.js";
import { call } from "./ipmanager.js";
import { sessions } from "../access.js";
import { DEMO } from "../demo.js";

const NEXT = "Saved. It applies from the next live run, within 2 minutes.";
// The settings keys (config.yml's alerts section), never shown as words.
const MASTER = `alerts.${"enabled"}`, MAIL = `alerts.${"mail"}`, LEAST = `alerts.${"sale_minimum"}`;
const BASIC = "Set in the server's config file (the alerts section). With accounts, an admin switches them here.";
const IN_DEMO = "In the demo, switching alerts on or off needs a running Skald.";

export function switchboard(f, CAUSE) {
  const banner = h("div", { class: "al-banner" });
  const list = h("div", { class: "al-switches" });
  const said = h("p", { class: "note al-said", role: "status", "aria-live": "polite" });
  let all = null;             // GET settings' `settings`, once loaded
  let busy = false;

  // A key's state: {on, may, why}; before the settings load (or without them), alerts.json's.
  const of = (key, fallback) => {
    const s = all?.[key];
    if (!s) return { on: !!fallback, may: false, why: DEMO.on ? IN_DEMO : sessions() ? "" : BASIC };
    return { on: !!s.value, may: !!s.editable, why: s.editable ? "" : s.reason || "", locked: !!s.locked };
  };

  async function flip(key, on) {
    if (busy) return;
    busy = true;
    said.textContent = "";
    const r = await call("settings/save", { [key]: on });
    busy = false;
    if (r.ok && r.settings) { all = r.settings; draw(); said.textContent = NEXT; return; }
    said.textContent = r.error || "Not saved.";
  }

  function toggle(key, st, label) {
    return h("button", { type: "button", role: "switch", class: `onoff al-sw${st.on ? " on" : ""}`, "aria-checked": String(st.on),
      "aria-label": `${label}: ${st.on ? "on" : "off"}`, disabled: !st.may, title: st.may ? `Switch ${st.on ? "off" : "on"}` : st.why || null,
      onclick: () => flip(key, !st.on) }, st.on ? "On" : "Off");
  }

  function draw() {
    const master = of(MASTER, f.enabled !== false);
    const mail = of(MAIL, f.mail_on ?? f.mail !== false);
    // The banner: off says so, and offers the switch to whoever may use it.
    if (!master.on) {
      const words = master.may ? "Alerts are off for this site, so nothing is being checked."
        : master.locked ? "Alerts are switched off in the server's settings (locked there), so nothing is being checked. Your server admin can switch them on."
          : all ? "Alerts are off for this site, so nothing is being checked. An admin can turn them on here."
            : "Alerts are switched off in the server's settings, so nothing is being checked. Your server admin can switch them on, to have them checked with every live run.";
      banner.replaceChildren(h("div", { class: "state bad", role: "note", html: ICON.info }, h("div", null, words, " ",
        master.may ? h("button", { type: "button", class: "btn primary", onclick: () => flip(MASTER, true) }, "Turn alerts on") : null)));
    } else if (!mail.on || (f.mail === false && f.checked_at && f.enabled !== false)) {
      banner.replaceChildren(h("p", { class: "cmp-why" }, `Alerts are checked and shown here, but not mailed${mail.on ? "" : " (Mail alerts is off)"}.`));
    } else banner.replaceChildren();
    const row = (key, st, name, sub, ch) => h("li", null, toggle(key, st, name),
      h("div", null, h("b", null, name), h("small", null, sub), !st.may && st.why && all ? h("small", { class: "al-why" }, st.why) : null),
      h("span", { class: "al-ch" }, ch));
    const rules = (f.rules || []).flatMap((t) => {
      const st = t.setting ? of(t.setting, t.on) : { on: !!t.on, may: false, why: BASIC };
      const watched = st.on && master.on;
      const one = row(t.setting, st, CAUSE[t.cause] || t.cause, t.threshold || "", watched ? (mail.on ? "mailed" : "shown here only") : "not watched");
      return t.cause === "sale" && all?.[LEAST] ? [one, least()] : [one];
    });
    list.replaceChildren(...[
      h("ul", { class: "al-types" },
        row(MASTER, master, "All alerts", "the switch for every rule below", master.on ? "checked every live run" : "nothing checked"),
        row(MAIL, mail, "Mail alerts", "to the site's confirmed recipients; off: shown here only", mail.on ? "mailed" : "not mailed"),
        rules),
      (f.rules || []).length ? null : h("p", { class: "empty" }, "No alert types are listed."),
      !all ? h("p", { class: "note" }, DEMO.on ? IN_DEMO : sessions() ? "Loading who may change these..." : BASIC) : null,
      said].filter(Boolean));
  }

  // The sale alerts' minimum per currency: one line of text, saved on its own.
  function least() {
    const s = all[LEAST];
    const may = !!s.editable;
    const input = h("input", { type: "text", class: "al-least", value: s.value || "", placeholder: "any amount, or e.g. USD 100, EUR 90.50",
      "aria-label": "Sale alert minimum per currency", disabled: !may, maxlength: "200" });
    const save = async () => {
      if (busy) return;
      busy = true;
      said.textContent = "";
      const r = await call("settings/save", { [LEAST]: input.value.trim() || null });
      busy = false;
      if (r.ok && r.settings) { all = r.settings; draw(); said.textContent = NEXT; return; }
      said.textContent = r.error || "Not saved.";
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); save(); } });
    return h("li", { class: "al-least-row" }, h("span"),
      h("div", null, h("b", null, "Sale alert minimum"),
        h("small", null, "Per currency: a sale under it does not alert, nor does a refund on it; a currency not listed alerts at any amount. Currencies are never converted."),
        h("span", { class: "al-least-edit" }, input, may ? h("button", { type: "button", class: "btn", onclick: save }, "Save minimum") : null),
        !may && s.reason ? h("small", { class: "al-why" }, s.reason) : null),
      h("span", { class: "al-ch" }, s.value ? "set" : "any amount"));
  }

  draw();
  if (sessions() && !DEMO.on) call("settings").then((r) => { if (r.ok && r.settings) all = r.settings; else said.textContent = r.error || ""; draw(); });
  return { banner, list };
}
