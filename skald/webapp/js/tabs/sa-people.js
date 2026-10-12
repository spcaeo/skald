// Leads & sales > People (2.7.0): find one person, and the people who converted
// lately.
//   * Find a person (admins and owners): an IP address, an email, a lead or a
//     visitor ID; the answer opens in person.js's drawer (every visit kept,
//     every lead and conversion, linked). The helper checks the role too and
//     writes each search to the audit log (the kind of value, never the value).
//   * Recent people: conversions.json's latest conversions (its own last 30
//     days), each one browser or one lead, with no name, email or visitor ID; a
//     row opens its visits by day and its steps. A browser is not a person.
// Listings, never figures. The lists of what the figures leave out sit beside
// their figures (Pipeline and Bookings, "Show"); this tab links to them.

import { h, n, short } from "../ui.js";
import * as S from "../state.js";
import { time as tzTime } from "../tz.js";
import { openDrawer } from "../drawer.js";
import { DEMO, DEMO_SAYS } from "../demo.js";
import { grid } from "../grid.js";
import { mayFind, openPerson, SEARCH_HINT } from "./person.js";
import { withFlag } from "./readers.js";
import { actionName, toolName, STAGE } from "./leadfigs.js";

const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
const dash = (v) => (v == null || v === "" ? "-" : String(v));

function search() {
  // The demo has no helper to ask: the search needs a running install.
  if (DEMO.on) {
    return h("section", { class: "s" }, h("h2", null, "Find a person"),
      h("div", { class: "state" }, h("div", null, h("strong", null, `${DEMO_SAYS} `), "On your own install, admins and owners find one person here by an IP address, an email, a lead or a visitor ID: every visit kept, every lead and conversion, linked.")));
  }
  if (!mayFind()) {
    return h("section", { class: "s" }, h("h2", null, "Find a person"),
      h("div", { class: "state" }, h("div", null, "Only an admin or an owner can look a person up. Ask one of them: the search shows every visit kept, every lead and conversion, linked.")));
  }
  const field = h("input", { type: "search", class: "pp-in sa-find-in", id: "sa-find", placeholder: SEARCH_HINT, autocomplete: "off", spellcheck: "false", maxlength: "320" });
  const form = h("form", { class: "sa-find", role: "search" }, h("label", { class: "vh", for: "sa-find" }, `Find a person: ${SEARCH_HINT}`), field,
    h("button", { type: "submit", class: "btn primary" }, "Find"));
  form.addEventListener("submit", (e) => { e.preventDefault(); if (field.value.trim()) openPerson(field.value); });
  return h("section", { class: "s" }, h("h2", null, "Find a person"),
    h("p", { class: "sub" }, "Every visit kept with the address, the last 6 hours of requests, every lead (spam, duplicates and test too) and every conversion, linked: each address, email or ID in the answer opens that person in turn."),
    form, h("p", { class: "note" }, "Each search is written to the audit log: the kind of value, never the value. The same search is in the top bar (Ctrl K, then Find a person)."));
}

// One conversion's story: its visits by day and its steps, as the tools and the page saw them.
function story(x) {
  const first = x.visits?.[0]?.day;
  const dayN = (d) => (first ? Math.round((Date.parse(`${d}T00:00:00Z`) - Date.parse(`${first}T00:00:00Z`)) / 864e5) + 1 : 1);
  const facts = [["Converted", `${actionName(x.action)}, ${at(x.at)}`], ["Reported by", toolName(x.tool)], ["Converted from", dash(x.source)], ["First came from", dash(x.first_source)],
    ["Campaign", dash(x.campaign)], ["Landed on", dash(x.landing)], ["Country", x.country ? withFlag(x.country) : "-"], ["Device", dash(x.device)],
    ["Visits before", x.visits_before == null ? "-" : n(x.visits_before)]];
  openDrawer({ title: `${actionName(x.action)}, ${at(x.at)}`, subtitle: x.browser ? "One browser (not a person: one person on two devices is two browsers)" : "One lead without a browser", key: "sa-story", scope: "page", size: "md",
    body: [h("dl", { class: "dw-dl" }, facts.flatMap(([t, v]) => [h("dt", null, t), h("dd", null, v)])),
      h("section", { class: "dw-sec" }, h("h3", null, "Visits"), (x.visits || []).length
        ? h("ul", { class: "conv-tl-visits" }, x.visits.map((v) => h("li", null, h("strong", null, `Day ${dayN(v.day)} (${short(v.day)}), ${v.source || "source unknown"}: `), (v.paths || []).join(", "))))
        : h("p", { class: "note" }, "No journey: this conversion carries no visitor ID.")),
      h("section", { class: "dw-sec" }, h("h3", null, "Steps"), h("ol", { class: "pp-trail" }, (x.steps || []).map((st) =>
        h("li", null, `${at(st.at)} `, h("b", null, `${actionName(st.action)} ${STAGE[st.stage] || st.stage}`), ` (${toolName(st.tool)})`))))] });
}

function recent(m) {
  const f = m.x.conversions;
  const period = f?.period ? `${short(f.period.first)} to ${short(f.period.last)}` : "the last 30 days";
  const head = h("h2", null, "Recent people ", h("small", { class: "note" }, `${period} · its own period`));
  if (!f || !f.available) return h("section", { class: "s" }, head, h("p", { class: "empty" }, "No conversions file yet: the people who converted show here once a source of conversions is on (Settings > Integrations)."));
  const rows = (f.timeline || []).map((x) => ({ ...x, visits_n: (x.visits || []).length }));
  return h("section", { class: "s" }, head,
    h("p", { class: "sub" }, "The latest conversions, newest first: each one browser, or one lead without a browser. No name, email or visitor ID here; a row opens its visits and steps."),
    grid({ ns: "pp", caption: "Recent people", file: "recent-conversions.csv", rows, sortKey: "at", dir: "desc", onRow: story,
      columns: [{ key: "at", label: "When", fmt: (v) => at(v) }, { key: "action", label: "Action", fmt: (v) => actionName(v || ""), csv: (r) => r.action },
        { key: "tool", label: "Reported by", fmt: (v) => toolName(v), csv: (r) => r.tool }, { key: "source", label: "Converted from", fmt: dash }, { key: "first_source", label: "First came from", fmt: dash },
        { key: "landing", label: "Landed on", fmt: dash }, { key: "country", label: "Country", fmt: (v) => (v ? withFlag(v) : "-"), csv: (r) => r.country || "" },
        { key: "visits_n", label: "Days with visits", num: true }],
      filters: [{ key: "action", label: "Action", options: [...new Set(rows.map((r) => r.action))].map((k) => [k, actionName(k)]) },
        { key: "tool", label: "Reported by", options: [...new Set(rows.map((r) => r.tool))].map((k) => [k, toolName(k)]) }],
      empty: "No completed conversion in this period." }));
}

export default function people(m, s) {
  const link = (words, patch) => h("a", { href: S.hashFor({ ...s, ...patch }) }, words);
  return [h("div", { class: "head" }, h("h1", null, "People")),
    search(), recent(m),
    h("p", { class: "note" }, "What the figures leave out is listed beside them: ",
      link("spam, duplicate and test leads", { tab: "sales/pipeline", lsrc: "db", lshow: "spam,duplicate,test" }), " (Pipeline, from the lead database); ",
      link("cancelled, removed and test conversions", { tab: "sales/pipeline", lsrc: "all", lshow: "cancelled,removed,test" }), " (Pipeline, from the tools, or Bookings).")];
}
