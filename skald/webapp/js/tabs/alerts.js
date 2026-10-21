// Alerts: what is wrong now, what was wrong recently and how long it lasted,
// and which alerts are switched on. Admins switch them here (alertswitch.js);
// thresholds stay in the config.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, duration, zoned, ICON } from "../ui.js";
import { rangeOf } from "../data.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { head, healthTabs } from "./common.js";
import { switchboard } from "./alertswitch.js";
import { subView } from "../tablestate.js";

const SEV = { high: "Urgent", medium: "Worth a look", low: "For information" };
export const CAUSE = { site_down: "Site down", logging_stopped: "Logging stopped", server_errors: "Server errors", not_found_surge: "Broken-link surge",
  crawler_burst: "Crawl burst", new_crawler: "New crawler", traffic_drop: "Traffic drop",
  ai_started_reading: "AI started reading", ai_stopped_reading: "AI stopped reading", ai_sending_people: "AI sending people",
  ai_first_citation: "First AI citation", ai_first_cited_page: "Page's first AI citation", ai_cited_visits: "Visits from AI answers", crawler_silent: "Crawler gone silent",
  security_exposure: "Possible exposure", scan_wave: "New scan wave", stack_advisory: "Advisory matches your stack" };
// The AI alerts (alerts_ai.py, alerts_history.py): the "AI" filter here, and the panel on AI & crawlers.
const isAI = (a) => String(a.cause || "").startsWith("ai_");
// All or only AI, kept in the address (alerts_view=ai: tablestate.js subView).
const ONLY = subView("alerts");
let only = "all";
// In the reader's chosen zone, with the date (alerts span days).
const when = (ts) => tzTime(ts, { date: true });
const lasted = (a) => (a.closed_at ? duration((Date.parse(a.closed_at) - Date.parse(a.opened_at)) / 1000) : null);

// An alert about a path opens the request log narrowed to it, where the lines behind it are.
function look(a) {
  if (!a.subject || !a.subject.startsWith("/")) return null;
  return h("button", { type: "button", class: "btn", onclick: () => S.set({ tab: "site/requests", path: a.subject, pathmode: "starts" }) }, `See the recent requests to ${a.subject}`);
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
  const out = [healthTabs(m, "health/alerts"), ...head("Alerts", rangeOf(m, { ...s, range: "today" }), "Problems the system watches for: the site down, server errors, a surge of broken links, logging stopped, a crawl burst, a new AI assistant, AI assistants starting or stopping reading a page, first AI citations, visits from AI answers far above or below the usual, and a crawler gone silent. An alert opens when its rule is met and closes on its own when the problem is gone.", { period: "Now, and the last 30 days · the date range above does not apply" })];
  const f = m.x.alerts;
  if (!f) return [...out, h("div", { class: "state", html: ICON.info }, h("div", null, "No alerts file beside this page yet. Alerts are checked by the server with every live run and written here; until the first check, nothing is shown, and nothing here means \"no alerts\" only once the file exists."))];
  // The master switch's banner and the switches (alertswitch.js): admins change them here.
  const board = switchboard(f, CAUSE);
  out.push(board.banner);
  only = ONLY.get() === "ai" ? "ai" : "all";
  const keep = (a) => only !== "ai" || isAI(a);
  const holder = h("div");
  const seg = h("div", { class: "seg plain", role: "group", "aria-label": "Which alerts" });
  const draw = () => {
    seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === only)));
    holder.replaceChildren(...lists(f.open || [], f.closed || []));
  };
  seg.append(...[["all", "All"], ["ai", "AI"]].map(([k, label]) => h("button", { type: "button", "data-k": k, onclick: () => { only = k; ONLY.set(k, "all"); draw(); } }, label)));
  const lists = (openAll, closedAll) => {
  const open = openAll.filter(keep).sort((a, b) => ["high", "medium", "low"].indexOf(a.severity) - ["high", "medium", "low"].indexOf(b.severity) || String(b.opened_at).localeCompare(String(a.opened_at)));
  const ai = only === "ai";
  const shown = [h("section", { class: "s" }, h("h2", null, open.length ? `${open.length} open${ai ? " (AI)" : ""}` : `Nothing open${ai ? " (AI)" : ""}`),
    h("p", { class: "sub" }, f.checked_at ? `Last checked at ${when(f.checked_at, m.today)}.` : "Not checked yet.", " ", seg),
    open.length ? h("div", { class: "al-grid" }, open.map((a) => card(a, m.today)))
      : h("div", { class: `state${f.checked_at ? " ok" : ""}`, html: f.checked_at ? ICON.check : ICON.info }, h("div", null, f.checked_at
        ? `No ${ai ? "AI " : ""}alert is open. Every rule that is switched on was checked and none is met right now.` : "The alert check has not run yet, so no alert can be open.")))];
  const closed = closedAll.filter(keep).map((a) => ({ ...a, __k: a.id, type_name: CAUSE[a.cause] || a.cause, lasted_s: a.closed_at ? (Date.parse(a.closed_at) - Date.parse(a.opened_at)) / 1000 : null }));
  shown.push(h("section", { class: "s" }, h("h2", null, "Closed recently"), h("p", { class: "sub" }, "The last 30 days, newest first."),
    table([
      { key: "opened_at", label: "Opened", type: "date", fmt: (v) => when(v, m.today), csv: (r) => r.opened_at },
      { key: "lasted_s", label: "Lasted", num: true, fmt: (_, r) => lasted(r) || "-" },
      { key: "type_name", label: "Kind" },
      { key: "title", label: "What happened" },
      { key: "detail", label: "Detail" },
    ], { caption: "Closed alerts", rows: closed, file: `alerts-closed-${m.today}.csv`, sortKey: "opened_at", dir: -1, limit: 10, empty: "No alert closed in the last 30 days." })));
  return shown;
  };
  draw();
  out.push(holder);
  out.push(h("section", { class: "s" }, h("h2", null, "Which alerts are on"),
    h("p", { class: "sub" }, "Switch each one on or off for this site (admins). Thresholds are set in the server's config file; a switch locked there says so."),
    board.list));
  return out;
}

// "AI reading changes" for the AI & crawlers tab: the AI alerts of the last 7 days, and
// whether each rule judged the last whole day or is waiting for one.
const RULE_NAME = { started_reading: "Started reading", stopped_reading: "Stopped reading", sending_people: "AI answers sending people",
  first_citation: "First citation from an assistant", first_cited_page: "A page's first citation", cited_visits: "Visits from AI answers against the usual", crawler_silent: "Crawler gone silent" };
export function aiChanges(m) {
  const f = m.x.alerts;
  const why = "Whole days only. From figures already checked twice: each assistant's requests by page, visits likely sent by an AI assistant (inferred), each page's first times, visits by source and each crawler's requests. Visits and requests are never mixed. A withheld or missing day makes a rule wait; it never fires on it.";
  const top = (...kids) => h("section", { class: "s" }, h("h2", null, "AI reading changes"), h("p", { class: "sub" }, why), ...kids);
  if (!f) return null;
  if (f.enabled === false || !f.ai) return top(h("p", { class: "empty" }, f.enabled === false ? "Alerts are switched off for this site (Site > Alerts, or the server's settings), so AI reading changes are not checked." : "Not checked yet: the first live run after an update checks the last whole day."));
  const since = Date.now() - 7 * 864e5;
  const rows = [...(f.open || []), ...(f.closed || [])].filter((a) => (isAI(a) || a.cause === "crawler_silent") && Date.parse(a.opened_at) >= since)
    .map((a) => ({ ...a, __k: a.id, kind: CAUSE[a.cause] || a.cause, state: a.closed_at ? "closed" : "open" }));
  const rules = Object.entries({ ...(f.ai.rules || {}), ...((f.history || {}).rules || {}) }).map(([k, r]) => h("li", null,
    h("b", null, RULE_NAME[k] || k), ": ",
    r.state === "off" ? "off" : r.state === "waiting" ? (r.why || `waiting for whole days (${(r.waiting_on || []).slice(0, 3).join(", ")}${(r.waiting_on || []).length > 3 ? ", ..." : ""})`) : `judged ${k in (f.ai.rules || {}) ? f.ai.day : f.history.day}`,
    r.unjudged?.length ? `; not judged for ${r.unjudged.join(", ")} (too many pages a day to tell)` : "",
    k === "sending_people" && r.assistants?.length ? `; ${r.assistants.map((x) => `${x.assistant} ${x.verdict} (${n(x.day)} against ${x.average} a day)`).join("; ")}` : "",
    k === "cited_visits" && r.verdict ? `; ${r.verdict} (${n(r.day_visits)} visits against a usual ${r.median})` : ""));
  return top(h("ul", { class: "note" }, rules),
    table([
      { key: "opened_at", label: "Opened", type: "date", fmt: (v) => when(v, m.today), csv: (r) => r.opened_at },
      { key: "kind", label: "Change" },
      { key: "title", label: "What happened" },
      { key: "detail", label: "Based on" },
      { key: "state", label: "Alert", type: "badge" },
    ], { caption: "AI reading changes, last 7 days", rows, file: `ai-reading-changes-${m.today}.csv`, sortKey: "opened_at", dir: -1, limit: 10, empty: "No assistant started or stopped reading a page in the last 7 days, and no jump or fall in visits likely sent by AI answers." }));
}
