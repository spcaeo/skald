// Security > Alerts (2.21): what Skald tells you about, and how. The security rules
// (alerts_security.py): a possible exposure and an advisory that matches the stack (on with
// the site's alerts) and a new scan wave (off until switched on), their state, and the open
// and recent security alerts from alerts.json; the switches are on Site > Alerts. Then "Your
// security alerts": each person's own mail (security_notify.py), on or off, in the daily
// summary (summary_mail.py: one mail a day for all their sites, the default) or right away
// (one mail per run with everything due), and, for owners and admins, a test send
// (settings/security-*).

import { h, toast } from "../ui.js";
import { table } from "../table.js";
import { DEMO, DEMO_SAYS } from "../demo.js";
import { sessions } from "../access.js";
import { call } from "./ipmanager.js";
import { mayFind } from "./person.js";
import { emptyState, choice } from "./sa-options.js";
import { secTab, at } from "./sec-common.js";

const NAME = { security_exposure: "Possible exposure", scan_wave: "New scan wave", stack_advisory: "Advisory matches your stack" };
const SEC = (a) => a.cause in NAME;

export function ruleRows(f, al) {
  const on = !!al?.enabled;
  return (f.alerts || []).map((r) => ({ ...r, name: NAME[r.cause] || r.cause,
    state: !on ? "Off: alerts are off for this site" : r.on ? (al?.mail ? "On: shown and mailed" : "On: shown here (not mailed)") : "Off" }));
}

/* Your own security alerts for this site: on or off, in the daily summary or right away. */
const summaryLabel = (t) => (t && t !== "off" ? `In the daily summary (${t})` : "In the daily summary");
const summaryWords = (t) => (t === "off"
  ? "The daily summary is off on this server, so only Right away sends anything."
  : `The daily summary is one mail a day at ${t || "01:00"} for all your sites (security items, to-dos and set-up problems), and none when nothing is open.`);

export function mine() {
  const box = h("div", { class: "card sec-mine" }, h("h2", null, "Your security alerts"), h("p", { class: "empty" }, "Loading…"));
  if (DEMO.on) { box.replaceChildren(h("h2", null, "Your security alerts"), h("p", { class: "note" }, DEMO_SAYS)); return box; }
  if (!sessions()) { box.replaceChildren(h("h2", null, "Your security alerts"), h("p", { class: "note" }, "Each person's own security mail needs sign-in with accounts (access.mode: sessions). The site's alert mail above still works.")); return box; }
  const said = h("p", { class: "note", role: "status", "aria-live": "polite" });
  const draw = (p) => {
    const save = (patch) => call("settings/security-prefs", { alerts: p.alerts, mode: p.mode, ...patch })
      .then((r) => { if (r.ok) { draw(r); said.textContent = "Saved."; } else said.textContent = r.error || "Not saved."; });
    box.replaceChildren(...[h("h2", null, "Your security alerts"),
      h("p", { class: "note" }, `Mail to ${p.email} when Skald finds a possible exposure or an advisory that matches this site's stack. ${summaryWords(p.summary_at)} Right away: one mail per run with everything due on your sites, never one per item. Each item comes once, then a reminder while it stays open.${p.default ? " This is the default for your role; choose to keep it." : ""}`),
      h("div", { class: "sa-opts" },
        choice("Security alerts", p.alerts ? "on" : "off", [["on", "On"], ["off", "Off"]], (v) => save({ alerts: v === "on" })),
        choice("When", p.mode, [["daily", summaryLabel(p.summary_at)], ["now", "Right away"]], (v) => save({ mode: v }))),
      mayFind() ? h("p", null, h("button", { type: "button", class: "btn", onclick: () => call("settings/security-test", {}).then((r) => toast(r.ok ? `A test alert went to ${r.sent_to}.` : r.error || "Not sent.")) }, "Send a test security alert")) : null,
      (p.open || []).length ? h("p", { class: "note" }, `Open now: ${p.open.length} item${p.open.length === 1 ? "" : "s"}.`) : null,
      said].filter(Boolean));
  };
  call("settings/security-prefs").then((r) => (r.ok ? draw(r) : box.replaceChildren(h("h2", null, "Your security alerts"), h("p", { class: "note" }, r.error || "Not available."))));
  return box;
}

export default function alerts(m, s) {
  return secTab(m, s, {
    title: "Security alerts",
    question: "What will Skald tell us about, and how?",
    period: "Rules now · alerts of the last 30 days",
    help: "A possible exposure opens an alert at once, from the live count every 2 minutes and from the last whole day, one per host and path; an advisory that matches the site's stack after the daily check. Both go to the dashboard, the site's alert mail and its webhooks (Slack too). A new scan wave compares the last whole day's probes with the usual day. Each person on the team can also choose their own mail below.",
    draw: ({ f }) => {
      const al = m.x?.alerts || null;
      const parts = [];
      if (!al?.enabled) parts.push(emptyState("Alerts are off for this site: nothing is checked or sent.", ["Turn alerts on", "#site/alerts"]));
      parts.push(table([
        { key: "name", label: "Alert" },
        { key: "threshold", label: "When it opens" },
        { key: "state", label: "Now" },
      ], { caption: "Security alert rules", ns: "sxr", rows: ruleRows(f, al), search: false, tools: false, limit: 5 }));
      parts.push(mine());
      const rows = [...(al?.open || []), ...(al?.closed || [])].filter(SEC).map((a) => ({ ...a, name: NAME[a.cause] || a.cause, open: a.closed_at ? "Closed" : "Open" }));
      parts.push(h("h2", { class: "sec-h2" }, "Security alerts, last 30 days"), table([
        { key: "opened_at", label: "Opened", type: "date", fmt: (v) => at(v) },
        { key: "name", label: "Alert" },
        { key: "title", label: "What" },
        { key: "open", label: "State" },
        { key: "mailed", label: "Mailed", num: true, hide: true },
      ], { caption: "Security alerts", ns: "sxo", file: "security-alerts.csv", rows, sortKey: "opened_at", dir: -1, limit: 12,
        empty: "No security alert in the last 30 days." }));
      parts.push(h("p", { class: "note" }, "Switch each rule on or off, and the mail, on ", h("a", { href: "#site/alerts" }, "Site > Alerts"), ". Slack and other webhooks: Settings > Leads & integrations > Outgoing webhooks (the event alert.opened)."));
      return parts;
    },
  });
}
