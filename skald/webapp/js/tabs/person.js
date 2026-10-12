// People (2.4.0): one search for an IP address, an email, a visitor ID or a
// lead's id, and the person it finds in a drawer - every visit kept with the
// address (time, source, referrer, landing, pages in order, country, device),
// the last 6 hours of requests, the leads (spam, duplicates and test too) and
// every conversion (test, cancelled and removed too), linked: each address,
// email, visitor ID and lead in it opens that person in turn. And the lists
// of what the figures leave out: the Leads page's spam, duplicates and test
// leads, the Conversions page's cancelled, removed and test conversions.
//
// The helper answers <page>/people?q= for admins and owners only, and writes
// each search to the audit log (never the value). The two lists are for every
// member; names, emails and visitor IDs in them only for admins and owners.
// Listings, never figures: nothing here is summed into a count.

import { h, n } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { openDrawer } from "../drawer.js";
import { call } from "./ipmanager.js";
import { ME } from "../access.js";
import { withFlag, country } from "./readers.js";
import { copyButton } from "./reqdetail.js";

export const SEARCH_HINT = "IP address, email, lead or visitor ID";
export const mayFind = () => ["owner", "admin"].includes(ME.role);
const STAGE = { started: "started", completed: "completed", paid: "paid", cancelled: "cancelled", rescheduled: "rescheduled", no_show: "no-show", won: "won", lost: "lost" };
const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
const dash = (v) => (v == null || v === "" ? "-" : String(v));
const sec = (title, ...kids) => h("section", { class: "dw-sec" }, h("h3", null, title), ...kids);
const empty = (words) => h("p", { class: "empty" }, words);
const dur = (s) => (s == null ? "-" : s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`);

function grid(caption, heads, rows) {
  return h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, caption),
    h("thead", null, h("tr", null, heads.map((x) => h("th", { scope: "col" }, x)))),
    h("tbody", null, rows.map((r) => h("tr", null, r.map((c) => h("td", null, c)))))));
}

// A key that opens its own person: an address, an email, a visitor ID, a lead.
function key(value, label = value) {
  if (!value || value === "(removed)") return value === "(removed)" ? "removed on request" : "-";
  if (!mayFind()) return label;
  return h("button", { type: "button", class: "pp-link", title: `Find ${value}`, onclick: () => openPerson(value) }, label);
}

function trail(v) {
  return h("ol", { class: "pp-trail" }, (v.trail || []).map(([path, how, s]) => h("li", null, h("span", { class: "mono" }, path),
    how === "app" ? h("small", null, " (in-app)") : null, s ? h("small", null, ` +${dur(s)}`) : null)));
}

function visitsPart(got) {
  const held = got.withheld || {};
  if (!got.visits.length) {
    if (got.query.kind !== "ip") return empty("No visit is shown: the search was not for an IP address. Open an address under Linked (or under the visits that sent a form at a lead's time) to see its visits.");
    return empty(got.kept?.keep_ips ? "No visit kept for this address." : "This site keeps no IP addresses with its visits (Settings > Data retention > People): only the last 6 hours of requests below show them.");
  }
  return grid("Visits", ["Started", "Source", "Referrer", "Landing", "Pages in order", "Country", "Device", "Took"], got.visits.map((v) => [
    h("span", null, at(v.start), held[v.day] ? h("small", { class: "pp-bad", title: "This day's figures did not reconcile: it is withheld from every total." }, " withheld day") : null),
    [v.source || "-", v.via ? h("small", null, ` ${v.via}`) : null], h("span", { class: "mono" }, dash(v.referrer)), h("span", { class: "mono" }, dash(v.landing)),
    trail(v), v.country ? withFlag(v.country, country(v.country)) : "-", [dash(v.device), v.browser ? h("small", null, ` ${v.browser} on ${v.os || "?"}`) : null], dur(v.seconds)]));
}

function leadsPart(rows) {
  if (!rows.length) return empty("No lead in the lead database.");
  return grid("Leads", ["Made", "Lead", "Type", "Status", "Page", "First touch", "Last touch", "Email", "Name"], rows.map((r) => [
    at(r.created_at), key(String(r.id), `#${r.id}`), dash(r.type),
    r.left_out ? h("b", { class: "pp-bad" }, `${r.test ? "test" : r.status} (left out)`) : dash(r.status),
    h("span", { class: "mono" }, dash(r.page)), dash(r.first_source), dash(r.last_source), r.email ? key(r.email) : "-", dash(r.name)]));
}

function conversionsPart(rows) {
  if (!rows.length) return empty("No conversion.");
  return grid("Conversions", ["When", "Action", "Stage", "Reported by", "Source", "Landing", "Lead or reference", "Visitor ID", "Email"], rows.map((r) => [
    at(r.at), dash(r.action), [STAGE[r.stage] || r.stage, r.test ? h("b", { class: "pp-bad" }, " test (not counted)") : null],
    dash(r.tool), dash(r.source_type), h("span", { class: "mono" }, dash(r.landing)), key(r.external_ref), key(r.vid), r.email ? key(r.email) : "-"]));
}

function removedPart(rows) {
  return grid("Removed conversions", ["Removed", "Why", "Was", "Lead or reference"], rows.map((r) => [
    at(r.removed_at), dash(r.why), `${dash(r.action)} ${STAGE[r.stage] || dash(r.stage)} at ${at(r.at)}`, key(r.external_ref)]));
}

export async function openPerson(q) {
  q = String(q || "").trim();
  if (!q) return openSearch();
  const d = openDrawer({ title: q, subtitle: "Looking…", key: "person", scope: "app", body: h("p", { class: "empty" }, "Looking in everything kept…") });
  const got = await call(`people?q=${encodeURIComponent(q)}`);
  if (!d.el.isConnected) return;
  if (!got.ok) { d.body.replaceChildren(h("div", { class: "state bad", role: "alert" }, h("div", null, got.error || "The search could not run."))); return; }
  const k = got.keys || {};
  const kinds = { ip: "IP address", email: "Email", vid: "Visitor ID", lead: "Lead" };
  d.el.querySelector(".dw-sub").textContent = `${kinds[got.query.kind]}: ${got.visits.length} visit${got.visits.length === 1 ? "" : "s"}, ${got.leads.length} lead${got.leads.length === 1 ? "" : "s"}, ${got.conversions.length} conversion${got.conversions.length === 1 ? "" : "s"}`;
  const linked = h("dl", { class: "dw-dl" }, [["IP addresses", k.ips], ["Emails", k.emails], ["Visitor IDs", k.vids], ["Leads and references", k.leads]]
    .flatMap(([t, list]) => [h("dt", null, t), h("dd", null, (list || []).length ? (list || []).map((v) => h("span", { class: "pp-key" }, key(v), " ", copyButton(v, "value"))) : "-")]));
  const cand = got.candidates || [];
  d.body.replaceChildren(...[
    sec("Linked", linked, h("p", { class: "note" }, `Kept: addresses ${got.kept?.keep_ips ? `for ${got.kept.keep_days} days` : "not kept"}; names and emails ${got.kept?.identity === "full" ? "kept" : "not kept"}.`)),
    sec("Visits", visitsPart(got)),
    got.requests.length ? sec("Requests in the last 6 hours", grid("Requests", ["Time", "Request", "Status", "Group"], got.requests.map((r) => [at(r.at), h("span", { class: "mono" }, `${r.method} ${r.path}`), String(r.status), dash(r.group)]))) : null,
    sec("Leads", leadsPart(got.leads)),
    cand.length ? sec("Leads and the visits that sent a form at their time", h("p", { class: "note" }, "Matched by time only: a form sent from 2 minutes before the lead to 30 seconds after. Likely the same person, never certain: the lead database keeps no address."),
      grid("Visits at a lead's time", ["Lead", "IP address", "Started", "Landing"], cand.map((c) => [key(c.lead, `#${c.lead}`), key(c.ip), at(c.start), h("span", { class: "mono" }, dash(c.landing))]))) : null,
    sec("Conversions", conversionsPart(got.conversions)),
    got.removed.length ? sec("Removed by a sync", removedPart(got.removed)) : null,
    got.journeys.length ? sec("Pages seen by its visitor IDs", grid("Pages", ["When", "Page", "Source"], got.journeys.map((j) => [at(j.at), h("span", { class: "mono" }, j.path), dash(j.source_type)]))) : null,
    h("p", { class: "note" }, "This search was written to the audit log (what kind of value, never the value). Deleting a person: skald forget on the server.")].filter(Boolean));
}

// The search itself, for the palette and a phone: a drawer with one field.
export function openSearch() {
  const field = h("input", { type: "search", class: "pp-in", placeholder: SEARCH_HINT, "aria-label": `Find a person: ${SEARCH_HINT}`, autocomplete: "off", spellcheck: "false", maxlength: "320" });
  const form = h("form", { class: "af-row" }, field, h("button", { type: "submit", class: "btn primary" }, "Find"));
  form.addEventListener("submit", (e) => { e.preventDefault(); if (field.value.trim()) openPerson(field.value); });
  openDrawer({ title: "Find a person", subtitle: SEARCH_HINT, size: "md", key: "person", focus: field,
    body: [form, h("p", { class: "note" }, mayFind() ? "Every visit kept, every lead and conversion, linked. Each search is written to the audit log." : "Only an admin or an owner can look a person up.")] });
}

const FIND_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="7" cy="7" r="4.6"/><path d="M10.4 10.4l3.4 3.4"/></svg>';

// The top bar's search (admins and owners): a box on wide screens (1600 px and
// up), an icon button that opens the same search below that, so the bar never
// overflows. Returns a list: [] for everyone else.
export function searchBox() {
  if (!mayFind()) return [];
  const btn = h("button", { type: "button", class: "btn icon pp-btn", html: FIND_ICON, "aria-label": `Find a person: ${SEARCH_HINT}`, title: `Find a person: ${SEARCH_HINT}`, onclick: openSearch });
  const field = h("input", { type: "search", class: "pp-in", placeholder: "Find a person", title: SEARCH_HINT, "aria-label": `Find a person: ${SEARCH_HINT}`, autocomplete: "off", spellcheck: "false", maxlength: "320" });
  const form = h("form", { class: "ctl pp-bar", role: "search" }, field);
  form.addEventListener("submit", (e) => { e.preventDefault(); if (field.value.trim()) openPerson(field.value); });
  return [form, btn];
}

// The Leads page's "Left out" line: spam, duplicates and test leads, and test conversions.
export async function openLeftOut() {
  const d = openDrawer({ title: "Left out of the figures", subtitle: "Spam, duplicates and test", key: "left-out", scope: "page", body: h("p", { class: "empty" }, "Loading…") });
  const got = await call("people/left-out");
  if (!d.el.isConnected) return;
  if (!got.ok) { d.body.replaceChildren(h("div", { class: "state bad" }, h("div", null, got.error || "The list could not be loaded."))); return; }
  d.body.replaceChildren(
    sec(`Leads (${n(got.leads.length)})`, got.leads.length ? leadsPart(got.leads) : empty("No spam, duplicate or test lead.")),
    sec(`Conversions marked test (${n(got.conversions.length)})`, got.conversions.length ? conversionsPart(got.conversions) : empty("No conversion is marked test.")),
    h("p", { class: "note" }, `A lead is left out when your team marked it spam or duplicate in the lead database, or it is marked test. A conversion is marked test on the server (skald conversions mark-test). Both are kept and listed here, never counted.${got.private ? "" : " Emails and names show to admins and owners only."}`));
}

// The Conversions page's lists: cancelled, removed and test conversions, with row and journey.
const LISTS = { cancelled: "Cancelled and no-show", removed: "Removed by a sync", test: "Marked test" };
export async function openConversionList(kind) {
  const d = openDrawer({ title: `Conversions: ${LISTS[kind] || kind}`, key: "conv-list", scope: "page", body: h("p", { class: "empty" }, "Loading…") });
  const got = await call(`people/conversions?kind=${encodeURIComponent(kind)}`);
  if (!d.el.isConnected) return;
  if (!got.ok) { d.body.replaceChildren(h("div", { class: "state bad" }, h("div", null, got.error || "The list could not be loaded."))); return; }
  const rows = got.rows || [];
  const tabs = h("div", { class: "acts", role: "group", "aria-label": "Which conversions" }, Object.entries(LISTS).map(([k, t]) =>
    h("button", { type: "button", class: `btn${k === kind ? " primary" : ""}`, "aria-pressed": String(k === kind), onclick: () => openConversionList(k) }, t)));
  const words = { cancelled: "Cancelled bookings and no-shows, as the booking tool reported them. They are counted under their own stage, never as completed.",
    removed: "Rows a lead-database sync took away (the lead was deleted, marked spam or duplicate, or changed), kept whole with when and why. Only a deletion request (skald forget) deletes for good.",
    test: "Conversions marked test on the server: kept, never counted." }[kind];
  const list = kind === "removed" ? (rows.length ? removedPart(rows) : empty("Nothing was removed."))
    : rows.length ? conversionsPart(rows) : empty("None.");
  const journeys = rows.filter((r) => (r.journey || []).length).map((r) => h("details", null, h("summary", null, `${dash(r.action || r.row?.action)} at ${at(r.at)}: ${r.journey.length} page${r.journey.length === 1 ? "" : "s"} before`),
    h("ol", { class: "pp-trail" }, r.journey.map((j) => h("li", null, at(j.at), " ", h("span", { class: "mono" }, j.path))))));
  d.body.replaceChildren(...[tabs, h("p", { class: "note" }, words), list, journeys.length ? sec("Journeys", ...journeys) : null].filter(Boolean));
}
