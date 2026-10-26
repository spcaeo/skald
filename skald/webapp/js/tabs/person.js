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
// Listings, never figures: nothing here is summed into a count. A site that
// keeps addresses shortened (privacy.keep_ips: short) finds a full address's
// visits under its shortened form (query.short), and says it can be several people.

import { h, n } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { openDrawer } from "../drawer.js";
import { call } from "./ipmanager.js";
import { ME } from "../access.js";
import { openVisitor } from "./visitor.js";
import { labelTag } from "./leadfigs.js";
import { withUrl, copyIf } from "../urlactions.js";
import { refBlock, refCell, byRef, markButton, mayMark } from "./leadref.js";

export const SEARCH_HINT = "IP address, email, lead or visitor ID";
export const mayFind = () => ["owner", "admin"].includes(ME.role);
const STAGE = { started: "started", completed: "completed", paid: "paid", cancelled: "cancelled", rescheduled: "rescheduled", no_show: "no-show", won: "won", lost: "lost" };
const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
const dash = (v) => (v == null || v === "" ? "-" : String(v));
const sec = (title, ...kids) => h("section", { class: "dw-sec" }, h("h3", null, title), ...kids);
const empty = (words) => h("p", { class: "empty" }, words);

function grid(caption, heads, rows) {
  return h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, caption),
    h("thead", null, h("tr", null, heads.map((x) => h("th", { scope: "col" }, x)))),
    h("tbody", null, rows.map((r) => h("tr", null, r.map((c) => h("td", null, c)))))));
}

// A key that opens its own person: an address, an email, a visitor ID, a lead; with its
// copy icon (copy: false where the caller adds its own, a reference's refCell).
function key(value, label = value, copy = true) {
  if (!value || value === "(removed)") return value === "(removed)" ? "removed on request" : "-";
  const el = mayFind() ? h("button", { type: "button", class: "pp-link", title: `Find ${value}`, onclick: () => openPerson(value) }, label) : label;
  return copy ? copyIf("text", el, String(value)) : el;
}
const text = (v) => copyIf("text", dash(v));

function leadsPart(rows) {
  if (!rows.length) return empty("No lead in the lead database.");
  return grid("Leads", ["Made", "Lead", "Type", "Status", "Page", "First touch", "Last touch", "Email", "Name"], rows.map((r) => [
    at(r.created_at), key(String(r.id), `#${r.id}`), dash(r.type),
    r.left_out ? h("b", { class: "pp-bad" }, `${r.test ? "test" : r.status} (left out)`) : dash(r.status),
    withUrl(h("span", { class: "mono" }, dash(r.page)), r.page, { cls: "ua-after" }), dash(r.first_source), dash(r.last_source), r.email ? key(r.email) : "-", text(r.name)]));
}

/* marks: a Test column with Mark as test / Not a test on each row (owners and admins; the
   Conversions lists). Each reference has its copy icon (2.25, leadref.js). */
function conversionsPart(rows, { marks = false } = {}) {
  if (!rows.length) return empty("No conversion.");
  const withMarks = marks && mayMark();
  return grid("Conversions", ["When", "Action", "Stage", "Reported by", "Source", "Landing", "Lead or reference", "Visitor ID", "Email", ...(withMarks ? ["Test"] : [])], rows.map((r) => [
    at(r.at), [dash(r.action), labelTag(r.label)], [STAGE[r.stage] || r.stage, r.test ? h("b", { class: "pp-bad" }, " test (not counted)") : null],
    dash(r.tool), dash(r.source_type), withUrl(h("span", { class: "mono" }, dash(r.landing)), r.landing), refCell(r.external_ref, key(r.external_ref, r.external_ref, false)), key(r.vid), r.email ? key(r.email) : "-",
    ...(withMarks ? [markButton({ id: r.id, ref: r.external_ref, tool: r.tool, test: !!r.test }, { compact: true }) || "-"] : [])]));
}

function removedPart(rows) {
  return grid("Removed conversions", ["Removed", "Why", "Was", "Lead or reference"], rows.map((r) => [
    at(r.removed_at), text(r.why), [`${dash(r.action)} ${STAGE[r.stage] || dash(r.stage)} at ${at(r.at)}`, labelTag(r.row?.label)], key(r.external_ref)]));
}

/* A person (people?q=) opens in the visitor drawer (visitor.js), the same
   layout as every visit; these are the parts only a search has: what it
   linked, the last 6 hours of requests, the lead database's rows, the visits
   at a lead's time, every conversion, the removed rows and the visitor IDs'
   pages. */
export function personParts(got) {
  const k = got.keys || {};
  const linked = h("dl", { class: "dw-dl" }, [["IP addresses", k.ips], ["Emails", k.emails], ["Visitor IDs", k.vids], ["Leads and references", k.leads]]
    .flatMap(([t, list]) => [h("dt", null, t), h("dd", null, (list || []).length ? (list || []).map((v) => h("span", { class: "pp-key" }, key(v))) : "-")]));
  const cand = got.candidates || [];
  const noVisits = !got.visits.length ? empty(got.query.kind !== "ip"
    ? "No visit is shown: the search was not for an IP address. Open an address under Linked (or under the visits that sent a form at a lead's time) to see its visits."
    : got.kept?.keep_ips ? "No visit kept for this address." : "This site keeps no IP addresses with its visits (Settings > Privacy & retention > People): only the last 6 hours of requests below show them.") : null;
  const short = got.query.short ? h("p", { class: "note" }, `This site keeps addresses shortened, with the last part removed: ${got.query.value} is kept as ${got.query.short}. A shortened address can be several people, so the visits below may not all be one person's.`) : null;
  const mode = got.kept?.ip_mode || (got.kept?.keep_ips ? "full" : "off");
  const addresses = mode === "off" ? "not kept" : `${mode === "short" ? "shortened, " : ""}for ${got.kept.keep_days} days`;
  return [
    short,
    noVisits,
    sec("Linked", linked, h("p", { class: "note" }, `Kept: addresses ${addresses}; names and emails ${got.kept?.identity === "full" ? "kept" : "not kept"}.`)),
    got.requests.length ? sec("Requests in the last 6 hours", grid("Requests", ["Time", "Request", "Status", "Group"], got.requests.map((r) => [at(r.at), withUrl(h("span", { class: "mono" }, `${r.method} ${r.path}`), r.path, { label: r.path }), String(r.status), dash(r.group)]))) : null,
    sec("Leads", leadsPart(got.leads)),
    cand.length ? sec("Leads and the visits that sent a form at their time", h("p", { class: "note" }, "Matched by time only: a form sent from 2 minutes before the lead to 30 seconds after. Likely the same person, never certain: the lead database keeps no address."),
      grid("Visits at a lead's time", ["Lead", "IP address", "Started", "Landing"], cand.map((c) => [key(c.lead, `#${c.lead}`), key(c.ip), at(c.start), withUrl(h("span", { class: "mono" }, dash(c.landing)), c.landing)]))) : null,
    sec("Conversions", conversionsPart(got.conversions)),
    // Each reference: its copy icon, every step, Mark as test (2.25, leadref.js).
    ...byRef(got.conversions).map((x) => refBlock(x)),
    got.removed.length ? sec("Removed by a sync", removedPart(got.removed)) : null,
    got.journeys.length ? sec("Pages seen by its visitor IDs", grid("Pages", ["When", "Page", "Source"], got.journeys.map((j) => [at(j.at), withUrl(h("span", { class: "mono" }, j.path), j.path), dash(j.source_type)]))) : null,
  ].filter(Boolean);
}

/* Find a person: the visitor drawer, by an address, email, visitor ID or lead. */
export function openPerson(q) {
  q = String(q || "").trim();
  if (!q) return openSearch();
  return openVisitor({ q });
}

// The search itself, for the palette and a phone: a drawer with one field.
export function openSearch() {
  const field = h("input", { type: "search", class: "pp-in", placeholder: SEARCH_HINT, "aria-label": `Find a person: ${SEARCH_HINT}`, autocomplete: "off", spellcheck: "false", maxlength: "320" });
  const form = h("form", { class: "af-row" }, field, h("button", { type: "submit", class: "btn primary" }, "Find"));
  form.addEventListener("submit", (e) => { e.preventDefault(); if (field.value.trim()) openPerson(field.value); });
  return openDrawer({ title: "Find a person", subtitle: SEARCH_HINT, size: "md", key: "person", focus: field, route: { key: "dlg", value: "find" },
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
  const d = openDrawer({ title: "Left out of the figures", subtitle: "Spam, duplicates and test", key: "left-out", scope: "page", body: h("p", { class: "empty" }, "Loading…"),
    route: { key: "list", value: "leftout" } });
  const got = await call("people/left-out");
  if (!d.el.isConnected) return d;
  if (!got.ok) { d.body.replaceChildren(h("div", { class: "state bad" }, h("div", null, got.error || "The list could not be loaded."))); return d; }
  d.body.replaceChildren(
    sec(`Leads (${n(got.leads.length)})`, got.leads.length ? leadsPart(got.leads) : empty("No spam, duplicate or test lead.")),
    sec(`Conversions marked test (${n(got.conversions.length)})`, got.conversions.length ? conversionsPart(got.conversions, { marks: true }) : empty("No conversion is marked test.")),
    h("p", { class: "note" }, `A lead is left out when your team marked it spam or duplicate in the lead database, or it is marked test. A conversion is marked test by an owner or admin (Mark as test in its drawer), by your site's server (leads/test) or on the server (skald conversions mark-test). Both are kept and listed here, never counted.${got.private ? "" : " Emails and names show to admins and owners only."}`));
}

// The Conversions page's lists: cancelled, removed and test conversions, with row and journey.
const LISTS = { cancelled: "Cancelled and no-show", removed: "Removed by a sync", test: "Marked test" };
export async function openConversionList(kind) {
  const d = openDrawer({ title: `Conversions: ${LISTS[kind] || kind}`, key: "conv-list", scope: "page", body: h("p", { class: "empty" }, "Loading…"),
    route: { key: "list", value: `conv-${kind}` } });
  const got = await call(`people/conversions?kind=${encodeURIComponent(kind)}`);
  if (!d.el.isConnected) return d;
  if (!got.ok) { d.body.replaceChildren(h("div", { class: "state bad" }, h("div", null, got.error || "The list could not be loaded."))); return d; }
  const rows = got.rows || [];
  const tabs = h("div", { class: "acts", role: "group", "aria-label": "Which conversions" }, Object.entries(LISTS).map(([k, t]) =>
    h("button", { type: "button", class: `btn${k === kind ? " primary" : ""}`, "aria-pressed": String(k === kind), onclick: () => openConversionList(k) }, t)));
  const words = { cancelled: "Cancelled bookings and no-shows, as the booking tool reported them. They are counted under their own stage, never as completed.",
    removed: "Rows a lead-database sync took away (the lead was deleted, marked spam or duplicate, or changed), kept whole with when and why. Only a deletion request (skald forget) deletes for good.",
    test: "Conversions marked test (Mark as test in a drawer, your site's server, or the server's command line): kept, never counted." }[kind];
  const list = kind === "removed" ? (rows.length ? removedPart(rows) : empty("Nothing was removed."))
    : rows.length ? conversionsPart(rows, { marks: true }) : empty("None.");
  const journeys = rows.filter((r) => (r.journey || []).length).map((r) => h("details", null, h("summary", null, `${dash(r.action || r.row?.action)} at ${at(r.at)}: ${r.journey.length} page${r.journey.length === 1 ? "" : "s"} before`),
    h("ol", { class: "pp-trail" }, r.journey.map((j) => h("li", null, at(j.at), " ", withUrl(h("span", { class: "mono" }, j.path), j.path, { cls: "ua-after" }))))));
  d.body.replaceChildren(...[tabs, h("p", { class: "note" }, words), list, journeys.length ? sec("Journeys", ...journeys) : null].filter(Boolean));
  return d;
}

/* list=leftout | conv-<kind>, from a link. */
export function openListKey(value) {
  if (value === "leftout") return openLeftOut();
  const kind = String(value).replace(/^conv-/, "");
  return LISTS[kind] ? openConversionList(kind) : "That list is not in this version of the page.";
}
