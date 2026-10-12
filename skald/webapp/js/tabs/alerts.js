// Alerts: what is wrong now, what was wrong recently and how long it lasted,
// and which alerts are switched on. Read-only: alerts are set in the config.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, duration, zoned, ICON } from "../ui.js";
import { rangeOf } from "../data.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { head, healthTabs } from "./common.js";

const SEV = { high: "Urgent", medium: "Worth a look", low: "For information" };
export const CAUSE = { site_down: "Site down", logging_stopped: "Logging stopped", server_errors: "Server errors", not_found_surge: "Broken-link surge",
  crawler_burst: "Crawl burst", new_crawler: "New crawler", traffic_drop: "Traffic drop" };
// In the reader's chosen zone, with the date (alerts span days).
const when = (ts) => tzTime(ts, { date: true });
const lasted = (a) => (a.closed_at ? duration((Date.parse(a.closed_at) - Date.parse(a.opened_at)) / 1000) : null);

// An alert about a path opens the request log narrowed to it, where the lines behind it are.
function look(a) {
  if (!a.subject || !a.subject.startsWith("/")) return null;
  return h("button", { type: "button", class: "btn", onclick: () => S.set({ tab: "requests", path: a.subject, pathmode: "starts" }) }, `See the recent requests to ${a.subject}`);
}

function card(a, today) {
  return h("article", { class: `al sev-${a.severity || "low"}`, "aria-label": `${SEV[a.severity] || "Alert"}: ${a.title}` },
    h("div", { class: "al-top" }, h("span", { class: "al-sev" }, SEV[a.severity] || a.severity || "Alert"), h("span", { class: "al-type" }, CAUSE[a.cause] || a.cause)),
    h("h3", { class: "al-title" }, a.title),
    a.detail ? h("p", { class: "al-cause" }, a.detail) : null,
    h("p", { class: "al-meta" }, `Open since ${when(a.opened_at, today)}`, a.last_seen_at ? `, last seen ${when(a.last_seen_at, today)}` : "",
      a.mailed ? `. Mailed ${a.mailed === 1 ? "once" : `${n(a.mailed)} times`}` : ". Not mailed", a.repeats ? `; found again ${n(a.repeats)} times since (in the daily digest)` : "", "."),
    look(a));
}

export default function alerts(m, s) {
  const out = [healthTabs(m, "health/alerts"), ...head("Alerts", rangeOf(m, { ...s, range: "today" }), "Problems the system watches for: the site down, server errors, a surge of broken links, logging stopped, a crawl burst, a new AI assistant. An alert opens when its rule is met and closes on its own when the problem is gone.", { period: "Now, and the last 30 days · the date range above does not apply" })];
  const f = m.x.alerts;
  if (!f) return [...out, h("div", { class: "state", html: ICON.info }, h("div", null, "No alerts file beside this page yet. Alerts are checked by the server with every live run and written here; until the first check, nothing is shown, and nothing here means \"no alerts\" only once the file exists."))];
  const rules = f.rules || [];
  if (f.enabled === false) out.push(h("div", { class: "state bad", role: "note", html: ICON.info }, h("div", null, "Alerts are switched off in the server's config, so nothing is being checked. Switch on alerts.enabled to have them checked with every live run.")));
  else if (f.mail === false) out.push(h("p", { class: "cmp-why" }, "Alerts are checked and shown here, but not mailed (alerts.mail is off)."));
  const open = (f.open || []).slice().sort((a, b) => ["high", "medium", "low"].indexOf(a.severity) - ["high", "medium", "low"].indexOf(b.severity) || String(b.opened_at).localeCompare(String(a.opened_at)));
  out.push(h("section", { class: "s" }, h("h2", null, open.length ? `${open.length} open` : "Nothing open"),
    h("p", { class: "sub" }, f.checked_at ? `Last checked at ${when(f.checked_at, m.today)}.` : "Not checked yet."),
    open.length ? h("div", { class: "al-grid" }, open.map((a) => card(a, m.today)))
      : h("div", { class: `state${f.checked_at ? " ok" : ""}`, html: f.checked_at ? ICON.check : ICON.info }, h("div", null, f.checked_at
        ? "No alert is open. Every rule that is switched on was checked and none is met right now." : "The alert check has not run yet, so no alert can be open."))));
  const closed = (f.closed || []).map((a) => ({ ...a, __k: a.id, type_name: CAUSE[a.cause] || a.cause, lasted_s: a.closed_at ? (Date.parse(a.closed_at) - Date.parse(a.opened_at)) / 1000 : null }));
  out.push(h("section", { class: "s" }, h("h2", null, "Closed recently"), h("p", { class: "sub" }, "The last 30 days, newest first."),
    table([
      { key: "opened_at", label: "Opened", fmt: (v) => when(v, m.today), csv: (r) => r.opened_at },
      { key: "lasted_s", label: "Lasted", num: true, fmt: (_, r) => lasted(r) || "-" },
      { key: "type_name", label: "Kind" },
      { key: "title", label: "What happened" },
      { key: "detail", label: "Detail" },
    ], { caption: "Closed alerts", rows: closed, file: `alerts-closed-${m.today}.csv`, sortKey: "opened_at", dir: -1, limit: 10, empty: "No alert closed in the last 30 days." })));
  out.push(h("section", { class: "s" }, h("h2", null, "Which alerts are on"), h("p", { class: "sub" }, "Set in the server's config file; shown here so you know what is being watched."),
    h("ul", { class: "al-types" }, rules.map((t) => h("li", null,
      h("span", { class: `onoff${t.on && f.enabled !== false ? " on" : ""}` }, t.on && f.enabled !== false ? "On" : "Off"),
      h("div", null, h("b", null, CAUSE[t.cause] || t.cause), h("small", null, t.threshold || "")),
      h("span", { class: "al-ch" }, t.on && f.enabled !== false ? (f.mail === false ? "shown here only" : "mailed") : "not watched")))),
    rules.length ? null : h("p", { class: "empty" }, "No alert types are listed.")));
  return out;
}
