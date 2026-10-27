// Settings › This site › Alerts (v2): which alerts are on for this site, and whether they are
// mailed. Site › Alerts keeps the alerts themselves and links here in one line; an older link
// to its switches (alerts_view=switches) opens this page (routes.js). Thresholds are the
// server's; each rule's sits behind its "?".
//
//   the state line   on: how many rules are checked, and mailed or not; off: how many will run
//                    once alerts are on (never an "on" count that is not true)
//   one primary      Turn alerts on, by the title, only while alerts are off and this person
//                    may switch them (the frame lifts .set-primary; it leaves once they are on)
//   All alerts, Mail alerts   the two switches above the rest
//   the rules        in folds by area, each "N of M on"; a rule is one line: name, "?", switch
//   Sale minimum     a row under the sale rules; its form in a drawer (edit=alertmin)

import { h, n } from "../ui.js";
import { CAUSE } from "./alerts.js";
import { alertState, MASTER, MAIL, LEAST, BASIC, IN_DEMO } from "./alertswitch.js";
import { help, fold, pill, primary, quietLine, strip, rowsCard, statusRow } from "./set-ui.js";
import { editPart, openEdit } from "./set-edit.js";
import { call } from "./ipmanager.js";
import { sessions } from "../access.js";
import { DEMO } from "../demo.js";

export const ROUTE = "settings/site/alerts";

// The areas, in this order; a cause not named here goes to Crawlers & AI (ai_*) or Other.
export const AREAS = [
  ["Site health", ["site_down", "logging_stopped", "server_errors", "not_found_surge"]],
  ["Traffic", ["traffic_drop", "ai_sending_people", "ai_cited_visits", "ai_first_citation", "ai_first_cited_page"]],
  ["Crawlers & AI", ["crawler_burst", "new_crawler", "crawler_silent", "ai_started_reading", "ai_stopped_reading"]],
  ["Security", ["security_exposure", "scan_wave", "stack_advisory"]],
  ["Sales", ["sale", "sale_refunded"]],
  ["Marketing", ["tool_stopped", "leads_drop", "bookings_drop", "ga4_log_gap"]],
];
export function areaOf(cause) {
  const hit = AREAS.find(([, causes]) => causes.includes(cause));
  return hit ? hit[0] : String(cause).startsWith("ai_") ? "Crawlers & AI" : "Other";
}

const MASTER_ABOUT = "The switch for every rule below. Off: nothing is checked, and no alert opens or is mailed. A rule that is on runs only while this is on.";
const MAIL_ABOUT = "On: each new alert is mailed to the site's confirmed recipients. Off: alerts are still checked and shown on Site › Alerts, but not mailed.";
const LOCKED = "Locked in the server's config file";

let repaint = null;   // the page open now: redrawn after the minimum's drawer saves

editPart("alertmin", { title: "Sale alert minimum", body: async (m, s, ctx) => {
  if (DEMO.on) return IN_DEMO;
  if (!sessions()) return BASIC;
  const r = await call("settings");
  const k = r.ok && r.settings?.[LEAST];
  if (!k) return r.error || "Not available here.";
  const input = h("input", { type: "text", class: "al-least", value: k.value || "", placeholder: "any amount, or e.g. USD 100, EUR 90.50",
    "aria-label": "Sale alert minimum per currency", disabled: !k.editable, maxlength: "200" });
  const said = h("p", { class: "note", role: "status", "aria-live": "polite" });
  const save = h("button", { type: "button", class: "btn primary", disabled: true }, "Save");
  input.addEventListener("input", () => { save.disabled = !k.editable; });
  save.addEventListener("click", async () => {
    save.disabled = true;
    const got = await call("settings/save", { [LEAST]: input.value.trim() || null });
    if (got.ok) { ctx.close(); repaint?.(); return; }
    said.textContent = got.error || "Not saved.";
    save.disabled = false;
  });
  return [h("p", null, "Per currency: a sale under it does not alert, nor does a refund on it; a currency not listed alerts at any amount. Currencies are never converted."),
    h("label", { class: "af-col" }, h("span", null, "The least amount per currency"), input),
    !k.editable && k.reason ? h("p", { class: "note" }, k.reason) : null,
    h("div", { class: "set-actions" }, save), said].filter(Boolean);
} });

export function alertsSettings(m) {
  const f = m.x?.alerts;
  if (!f) return quietLine("No alerts file yet", "Alerts are checked by the server with every live run. Once the first check has run, the switches show here.");
  const root = h("div", { class: "set-alerts" });
  const opened = new Set();            // the folds open now, kept across a redraw
  let go = null;                       // Turn alerts on, while alerts are off
  const st = alertState(f, () => draw());
  repaint = () => st.start();

  const toggle = (key, s, name) => h("button", { type: "button", role: "switch", class: `onoff al-sw${s.on ? " on" : ""}`, "aria-checked": String(s.on),
    "aria-label": `${name}: ${s.on ? "on" : "off"}`, disabled: !s.may, title: s.may ? `Switch ${s.on ? "off" : "on"}` : s.why || null,
    onclick: () => st.flip(key, !s.on) }, s.on ? "On" : "Off");
  // One line: the name, its "?", the switch. A locked key says so under the name.
  const line = (key, s, name, about) => h("div", { class: "set-row al-row" },
    h("span", { class: "grow sr-t" }, h("span", { class: "al-name" }, h("b", null, name), about ? help(name, { text: about }) : null),
      s.locked ? h("small", null, LOCKED) : null),
    toggle(key, s, name));

  function draw() {
    const all = st.all();
    const master = st.master();
    const mail = st.mail();
    const rules = (f.rules || []).map((t) => ({ t, s: st.rule(t) }));
    const on = rules.filter((x) => x.s.on).length;
    const rulesWord = (k) => `${n(k)} rule${k === 1 ? "" : "s"}`;
    const ofAll = `${n(on)} of ${n(rules.length)} rule${rules.length === 1 ? "" : "s"}`;
    // The one primary: only while off, only for whoever may switch it.
    if (!master.on && master.may) {
      if (!go) go = primary("Turn alerts on", () => st.flip(MASTER, true), { iconName: "check" });
    } else if (go) { go.remove(); go = null; }
    const state = master.on
      ? strip("On", `${ofAll} ${on === 1 ? "is" : "are"} checked with every live run, ${mail.on ? "and mailed to the site's confirmed recipients" : "and shown on Site › Alerts, not mailed"}.`, null, { kind: "good" })
      : strip("Off", `Alerts are off, so nothing is checked. ${on ? `${rulesWord(on)} will run when ${master.may ? "you turn them on" : "they are turned on"}.` : "No rule is switched on either."}${!master.may && all ? ` ${master.locked ? "They are switched off in the server's config file: your server admin can switch them on." : master.why}` : ""}`, null, { kind: "off" });
    const none = all && ![master, mail, ...rules.map((x) => x.s)].some((s) => s.may);
    const why = !all ? (DEMO.on ? IN_DEMO : sessions() ? (st.loaded ? "" : "Loading who may change these…") : BASIC)
      : none && master.why && master.on ? master.why : "";
    const top = rowsCard("Checking and mail", [line(MASTER, master, "All alerts", MASTER_ABOUT), line(MAIL, mail, "Mail alerts", MAIL_ABOUT)]);
    const areas = [...AREAS.map(([a]) => a), "Other"].map((a) => {
      const mine = rules.filter((x) => areaOf(x.t.cause) === a);
      if (!mine.length) return null;
      const k = mine.filter((x) => x.s.on).length;
      const word = master.on ? `${k} of ${mine.length} on` : `${k} of ${mine.length} will run`;
      const kind = !master.on || !k ? "off" : k === mine.length ? "good" : "info";
      const body = () => h("div", { class: "set-list" }, mine.flatMap(({ t, s }) => {
        const one = line(t.setting, s, CAUSE[t.cause] || t.cause, t.threshold || "");
        if (t.cause !== "sale" || !all?.[LEAST]) return [one];
        const v = all[LEAST].value;
        return [one, statusRow({ iconName: "", title: "Sale alert minimum", line: v || "Any amount", label: "Change the sale alert minimum", onOpen: () => openEdit("alertmin", m) })];
      }));
      const d = fold(h("span", { class: "al-area" }, h("b", null, a), pill(kind, word)), body, { open: opened.has(a), cls: "al-fold" });
      d.addEventListener("toggle", () => { if (d.open || d.hasAttribute?.("open")) opened.add(a); else opened.delete(a); });
      return d;
    }).filter(Boolean);
    // The primary goes in once; the frame then lifts it beside the title (out of root).
    root.replaceChildren(...[go && !go.parentNode ? go : null, state, why ? h("p", { class: "note" }, why) : null, top,
      rules.length ? h("section", { class: "ui-card set-rows al-areas" }, h("div", { class: "ui-card-h" }, h("h2", null, "The rules")), ...areas)
        : h("p", { class: "empty" }, "No alert types are listed."),
      st.said ? h("p", { class: "note al-said", role: "status", "aria-live": "polite" }, st.said) : null].filter(Boolean));
  }

  draw();
  st.start();
  return root;
}
