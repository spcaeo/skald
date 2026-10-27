// Site › Alerts (2.41, the UX audit's task 1, docs/UI-RULES.md): what needs you, in groups.
//
//   one card per kind (alert-groups.js), the most urgent first, each with a pill and one
//   line; the first that can be fixed holds the page's one primary button, Fix
//   Fix opens "Who will do it? Me / My developer / My AI agent" (ui/who.js) with that
//   kind's steps: the same words and places the old cards linked to (the request log of
//   a path, Security › Your stack, the advice for an exposed file); My AI agent only where
//   the agent kit has the job (logging stopped: the "logs" job)
//   a kind with nothing to fix (an AI assistant stopped reading pages) shows its list
//   the method text sits behind the "?"; closed alerts and the switches are folds
//
// The address: alfix=<kind> (the dialog, by its kind: a fixed word, never an id of a
// person), by=me|dev|agent inside it. Which alerts are on is one line that links to Settings ›
// This site › Alerts (set-alerts.js); an older alerts_view=switches link opens that page (routes.js).
// The count of what needs you (alert-groups.js needsYou) is the one the Site badge and
// the bell show.

import { h, n, ICON } from "../ui.js";
import * as S from "../state.js";
import { time as tzTime } from "../tz.js";
import { table } from "../table.js";
import { withCopy } from "../urlactions.js";
import { say } from "../overlays.js";
import { CAUSE } from "./alerts.js";
import { switchboard } from "./alertswitch.js";
import { adviceOf } from "./sec-common.js";
import { groupsOf, pagesOf } from "../alert-groups.js";
import { pill } from "../ui/pill.js";
import { help } from "../ui/help.js";
import { fold } from "../ui/fold.js";
import { primary, screenHead } from "../ui/primary.js";
import { whoDialog, mePath, devPath, agentPath } from "../ui/who.js";
import { sourceLink } from "../ui/connect.js";
import { groupOf, groupById, fedFromData } from "../connect-plan.js";

export const KEY = "alfix";
const SEV = { high: ["bad", "Urgent"], medium: ["warn", "Worth a look"], low: ["info", "For information"] };
const when = (ts) => (ts ? tzTime(ts, { date: true }) : "-");
const once = (a) => !!a.closed_at && a.closed_at === a.opened_at;

// Where each kind is looked at, or fixed, in Skald: [route, words].
const PLACE = {
  site_down: ["site/health", "Site › Health"], server_errors: ["site/health", "Site › Health"], not_found_surge: ["site/notfound", "Site › Not found"],
  logging_stopped: ["settings/site/data", "Settings › Data"], crawler_burst: ["ai/crawlers", "AI & bots › Crawlers"],
  new_crawler: ["ai/crawlers", "AI & bots › Crawlers"], crawler_silent: ["ai/crawlers", "AI & bots › Crawlers"], traffic_drop: ["traffic/sources", "Traffic › Sources"],
  security_exposure: ["threats/exposed", "Security › Is anything exposed?"], scan_wave: ["threats/scanners", "Security › Who is scanning us?"],
  stack_advisory: ["threats/stack", "Security › Your stack"], sale: ["sales/revenue", "Leads & sales › Revenue"], sale_refunded: ["sales/revenue", "Leads & sales › Revenue"],
};
const placeOf = (cause) => PLACE[cause] || (String(cause).startsWith("ai_") ? ["ai/assistants", "AI & bots › Assistants"] : ["site/health", "Site › Health"]);
// Kinds someone can fix. The rest are news: their list, and the place to look.
export const FIXABLE = new Set(["site_down", "logging_stopped", "server_errors", "not_found_surge", "security_exposure", "stack_advisory"]);
// Kinds the agent kit has a job for (kit/agent_jobs.py; js/tabs/agent-words.js JOBS).
const AGENT_JOBS = { logging_stopped: ["logs"] };

// Advisories say "Advisory for <site>: <what>"; on the site's own page the site is known.
const short = (a) => String(a.title || "").replace(/^Advisory for [^:]+:\s*/, "");

/* The group's title: its one alert's, or what the alerts share, counted in words. */
export function titleOf(g) {
  const k = g.alerts.length;
  if (k === 1) return g.cause === "stack_advisory" ? `Advisory: ${short(g.alerts[0])}` : g.alerts[0].title;
  if (String(g.cause).startsWith("ai_") || g.cause === "crawler_silent") {
    const pages = pagesOf(g.alerts).length;
    const verb = { ai_stopped_reading: "AI stopped reading", ai_started_reading: "AI started reading" }[g.cause];
    const pw = `${n(pages)} page${pages === 1 ? "" : "s"}`;
    if (verb) return pages === k ? `${verb} ${pw}` : `${verb} ${pw} (${n(k)} alerts: some pages by more than one assistant)`;
  }
  const many = { stack_advisory: "security advisories match your stack", security_exposure: "possible exposures", server_errors: "pages answering with server errors",
    not_found_surge: "broken-link surges", new_crawler: "new crawlers", crawler_burst: "crawl bursts", sale: "sales", sale_refunded: "refunds" }[g.cause];
  return many ? `${n(k)} ${many}` : `${CAUSE[g.cause] || g.cause}: ${n(k)} open`;
}

/* One line under the title: what the alerts name, then since when. */
function metaOf(g) {
  const a = g.alerts;
  let what;
  if (g.cause === "stack_advisory") what = a.slice(0, 3).map(short).join(" · ");
  else if (String(g.cause).startsWith("ai_")) what = [...new Set(a.map((x) => String(x.subject || "").split(": ")[0]).filter(Boolean))].sort().join(", ");
  // One alert: the first sentence of its detail (the whole detail is in Fix).
  else what = a.length === 1 ? String(a[0].detail || "").split(/(?<=[.;])\s/)[0] : a.slice(0, 3).map((x) => x.subject || x.title).join(" · ");
  if (a.length > 3 && g.cause !== "stack_advisory" && !String(g.cause).startsWith("ai_")) what += `, and ${n(a.length - 3)} more`;
  if (a.length > 3 && g.cause === "stack_advisory") what += `, and ${n(a.length - 3)} more`;
  const since = a.map((x) => x.opened_at).filter(Boolean).sort()[0];
  return [what, since ? `open since ${when(since)}` : ""].filter(Boolean).join(" · ");
}

// ---- the Fix dialog ---------------------------------------------------------------------

const go = (route, words, patch = {}) => h("button", { type: "button", class: "btn", onclick: () => S.set({ tab: route, ...patch, [KEY]: "", by: "" }) }, `Open ${words}`);

/* Me: each alert's own steps, in the words the old cards and the Security tabs use. */
function stepsOf(g) {
  const [route, words] = placeOf(g.cause);
  return [...g.alerts.map((a) => {
    const parts = [h("h4", null, g.cause === "stack_advisory" ? short(a) : a.title)];
    if (g.cause === "security_exposure") {
      const [what, code] = adviceOf(a.data?.category);
      parts.push(h("p", null, a.detail || ""), h("p", null, h("b", null, "Do: "), what));
      if (code) parts.push(withCopy(h("pre", { class: "ui-code" }, code), code, { label: "the line for nginx", tag: "div" }),
        h("p", { class: "note" }, "For nginx: inside the site's server { } block, then nginx -t and reload."));
    } else {
      parts.push(h("p", null, a.detail || ""));
    }
    const path = a.subject && String(a.subject).startsWith("/") ? a.subject : null;
    if (path) parts.push(h("p", null, h("button", { type: "button", class: "btn", onclick: () => S.set({ tab: "site/requests", path, pathmode: "starts", [KEY]: "", by: "" }) }, `See the recent requests to ${path}`)));
    if (g.cause === "stack_advisory" && /^[a-z0-9]{1,16}$/.test(a.data?.item || "")) parts.push(h("p", null, go(route, words, { item: a.data.item })));
    return h("section", { class: "ui-card quiet ui-stack" }, parts);
  }), g.cause === "stack_advisory" ? null : h("p", null, go(route, words))];
}

/* My developer: the message to send (the alerts in plain words) and the link to this place. */
function messageOf(g, site) {
  const lines = [`Skald found this on ${site || "our site"}: ${titleOf(g)}.`, ...g.alerts.map((a) => `- ${a.title}${a.detail ? `: ${a.detail}` : ""}`)];
  if (g.cause === "security_exposure") for (const a of g.alerts) { const [what, code] = adviceOf(a.data?.category); lines.push(`What to do: ${what}${code ? ` (nginx: ${code})` : ""}`); }
  if (g.cause === "stack_advisory") lines.push("What to do: update each one to its fixed release, or move to a supported branch.");
  lines.push("Skald checks again with every live run and closes the alert by itself once it is gone.");
  return lines.join("\n");
}

export async function openFix(m, cause) {
  const g = groupsOf(m.x?.alerts?.open).find((x) => x.cause === cause);
  if (!g) return "That alert is closed now, or it is not available to you.";
  const site = m.site || "";
  const link = `${location.origin || ""}${location.pathname}${location.search || ""}${S.hashFor({ ...S.read(), tab: "site/alerts", [KEY]: cause, by: "" })}`;
  const route = { key: KEY, value: cause };
  const paths = { me: mePath(() => stepsOf(g)), dev: devPath({ site, message: messageOf(g, site), link }) };
  if (AGENT_JOBS[cause]) {
    paths.agent = agentPath({ site, jobs: AGENT_JOBS[cause], route });
    paths.dev = devPath({ site, task: "send" });
  }
  const said = "Skald checks again with every live run, within 2 minutes. The alert closes by itself once the problem is gone.";
  let d = null;
  const done = primary("I have done it", () => { d?.close(); say(said); });
  d = await whoDialog({ title: `Fix: ${titleOf(g)}`, subtitle: CAUSE[cause] || cause, route, paths, fallback: "me", footer: [done],
    top: h("p", { class: "ui-lede" }, pill(...SEV[g.severity] || SEV.low), g.alerts.length > 1 ? `${n(g.alerts.length)} alerts of this kind are open.` : "One alert of this kind is open.") });
  return d;
}
export const openFixKey = (v, m) => openFix(m, v);

// ---- the page ---------------------------------------------------------------------------

function groupCard(m, g, first) {
  const [kind, words] = SEV[g.severity] || SEV.low;
  const title = titleOf(g);
  let act = null, list = null;
  if (FIXABLE.has(g.cause)) {
    act = first ? primary("Fix", () => openFix(m, g.cause), { label: `Fix: ${title}` })
      : h("button", { type: "button", class: "btn", "aria-label": `Fix: ${title}`, onclick: () => openFix(m, g.cause) }, "Fix");
  } else if (g.alerts.length > 1) {
    const pages = String(g.cause).startsWith("ai_");
    const np = pagesOf(g.alerts).length;
    list = fold(pages ? `See the ${n(np)} page${np === 1 ? "" : "s"}` : `See the ${n(g.alerts.length)}`, () => [
      h("ul", { class: "ui-list" }, g.alerts.map((a) => h("li", null, h("b", null, a.subject || a.title), a.detail ? h("small", { class: "muted" }, ` ${a.detail.split(". From ")[0]}.`) : null))),
      h("p", null, go(...placeOf(g.cause)))]);
  } else {
    act = go(...placeOf(g.cause));
  }
  return h("article", { class: `ui-card ${kind === "bad" ? "bad" : kind === "warn" ? "warn" : ""}`.trim(), "aria-label": `${words}: ${title}`, "data-cause": g.cause },
    h("div", { class: "ui-card-h" }, pill(kind, words), h("h3", { class: "ui-grow" }, title), act),
    h("p", { class: "ui-meta" }, metaOf(g)), list);
}

const METHOD = [
  "Skald checks for the site down, server errors, a surge of broken links, logging stopped, a crawl burst, a new crawler, AI assistants starting or stopping reading a page, first AI citations, visits from AI answers far from the usual, a crawler gone silent, a possible exposure and advisories that match your stack.",
  "An alert opens when its rule is met and closes on its own when the problem is gone. AI alerts use whole days only, from figures already checked twice. Sale and refund alerts, when on, open and close at once.",
];

/* 2.43: an alert switched on whose source is not connected can never open (no sale alert
   without a payment source): one quiet line naming them, and, for an admin, the way to the
   source's group in Settings › Leads & tools. Known from the page's own files only. */
export function needsSource(m, rules) {
  const by = new Map();
  for (const r of rules || []) {
    const g = r.on ? groupOf(r.cause) : "";
    if (g && fedFromData(g, m) === false) by.set(g, [...(by.get(g) || []), CAUSE[r.cause] || r.cause]);
  }
  if (!by.size) return null;
  return h("div", { class: "ui-strip ui-conn-part al-need", role: "note" }, pill("off", "Needs a source"),
    h("span", null, [...by].map(([g, names]) => `${names.join(", ")}: ${groupById(g).title.toLowerCase()} not connected`).join(". "), ". "),
    ...[...by.keys()].map((g) => sourceLink(g, `Connect ${groupById(g).title.toLowerCase()}`)).filter(Boolean));
}

export default function alertsPage(m, s) {
  const f = m.x.alerts;
  const groups = groupsOf(f?.open);
  const need = groups.filter((g) => g.needs).length;
  const fixes = groups.filter((g) => FIXABLE.has(g.cause)).length;
  const lede = !f ? "" : need ? `${n(need)} thing${need === 1 ? " needs" : "s need"} you.${fixes ? ` ${fixes === need ? (need === 1 ? "It has" : "Each has") : `${n(fixes)} ${fixes === 1 ? "has" : "have"}`} a Fix button.` : ""}`
    : groups.length ? "Nothing needs you now." : "";
  const out = [screenHead("Alerts", { help: help("Alerts", { text: METHOD, guide: "settings-and-retention" }), lede: lede || null, level: "h1" })];
  if (!f) return [...out, h("div", { class: "state", html: ICON.info }, h("div", null, "No alerts file beside this page yet. Alerts are checked by the server with every live run; until the first check, nothing is shown, and nothing here means \"no alerts\" only once the file exists."))];
  const board = switchboard(f, CAUSE);
  out.push(board.banner);
  const firstFix = groups.find((g) => FIXABLE.has(g.cause));
  out.push(groups.length ? h("div", { class: "ui-stack si-al" }, groups.map((g) => groupCard(m, g, g === firstFix)))
    : h("div", { class: `state${f.checked_at ? " ok" : ""}`, html: f.checked_at ? ICON.check : ICON.info }, h("div", null, f.checked_at
      ? "No alert is open. Every rule that is switched on was checked and none is met right now." : "The alert check has not run yet, so no alert can be open.")));
  out.push(h("p", { class: "note" }, f.checked_at ? `Last checked at ${when(f.checked_at)}.` : "Not checked yet."));
  // Closed recently: one quiet line that opens to the table.
  const closed = (f.closed || []).map((a) => ({ ...a, __k: a.id, type_name: CAUSE[a.cause] || a.cause, lasted_s: a.closed_at && !once(a) ? (Date.parse(a.closed_at) - Date.parse(a.opened_at)) / 1000 : null }));
  out.push(closed.length ? fold(`${n(closed.length)} closed in the last 30 days`, () => table([
    { key: "opened_at", label: "Opened", type: "date", fmt: (v) => when(v), csv: (r) => r.opened_at },
    { key: "lasted_s", label: "Lasted", num: true, fmt: (v) => (v == null ? "-" : `${n(Math.round(v / 60))} min`) },
    { key: "type_name", label: "Kind" },
    { key: "title", label: "What happened" },
  ], { caption: "Closed alerts", rows: closed, file: `alerts-closed-${m.today}.csv`, sortKey: "opened_at", dir: -1, limit: 10 }))
    : h("p", { class: "note" }, "Nothing closed in the last 30 days."));
  // Which alerts are on: one line, to its settings page (Settings › This site › Alerts).
  const rules = f.rules || [];
  const on = rules.filter((r) => r.on).length;
  out.push(h("p", { class: "note al-on" }, `Which alerts are on: ${n(on)} of ${n(rules.length)}${f.enabled === false ? " (all off)" : ""}. `,
    h("a", { href: S.hashFor({ ...s, tab: "settings/site/alerts" }) }, "Change them in Settings › Alerts")));
  const starved = needsSource(m, rules);
  if (starved) out.push(starved);
  return out;
}

// For a test: the parts.
export const _parts = { stepsOf, messageOf, metaOf, placeOf };
