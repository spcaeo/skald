// Leads & sales > Leads (2.20), the section's first tab: "Who are my leads?" One row per
// lead of the period, newest first: when, name and email (admins and owners, on a site that
// keeps them), what they did, its label, its stage now, where it came from (the lead
// database, a booking tool, the page's script tag, the site's server), the source (last and
// first touch), the landing page and the country. A row opens the visitor drawer with that
// lead's steps and pages.
//
// The rows come from the helper (people/leads, people/leadlist.py): a listing, never a
// figure. The count beside them is the Leads figure itself (leadfigs.js leadsOn, the same
// sum as Overview's Leads tile and Summary), never a count of these rows; a list that
// holds more or fewer (a lead that came in after the last redraw) says so.
//
// One options row (kept in the address): What (lact), Label (llabel), Stage now (lnow),
// Source (lby), and under More, Show left out (lshow=out: test, spam and duplicate rows,
// listed, never counted). The same rows and filters in four shapes (viewswitch.js, lview):
// List (the table), Board (by stage now), Timeline (leads per day, split by what or by
// source: the figure's own days) and Map (leads by country: the figure's own breakdown).
//
// 2.23: the options row is the only filter row (the table has no Filter button of its own);
// the top bar's Filters a lead carries (source, country, device, campaign) narrow the leads
// too; every filter on is a chip in one "Filtered by" line with Clear all (sa-filters.js);
// the count line says what is applied; a period with no lead says where the leads are
// (the last 30 days, all time), with a button to each. Leads & sales opens on 7 days.
//
// 2.25: a Reference column (the sender's own ID for the lead, with a copy icon), hidden until
// Columns shows it, searched and in the CSV either way; the lead's drawer lists every step of
// that reference and, for owners and admins, Mark as test / Not a test (leadref.js).
//
// 2.27: 7, 30 and 90 days are today so far and the whole days before it (sa-period.js): the
// list holds today's leads, marked live; the change compares the period before to this hour.
//
// 2.32.0: a sale's drawer shows its value and currency, what was refunded on it, its customer
// reference (with a copy icon) and its tags (saleFacts); the sums are on Revenue (sa-revenue.js).

import { h, n, change, short, long } from "../ui.js";
import * as S from "../state.js";
import { rangeOf, previousOf } from "../data.js";
import { time as tzTime, daysNote } from "../tz.js";
import { DEMO } from "../demo.js";
import { grid } from "../grid.js";
import { call } from "./ipmanager.js";
import { mayFind } from "./person.js";
import { openVisitor } from "./visitor.js";
import { countryWords } from "./readers.js";
import { actionName, oneAction, toolName, labelTag, leadsOn, convFile } from "./leadfigs.js";
import { narrowConv, withFile, convLabels } from "./sa-pipeline.js";
import { tabHead, optionsRow, select, toggles, listOf, emptyState } from "./sa-options.js";
import { viewSwitch, viewOf } from "../viewswitch.js";
import { board, timeline, map } from "./sa-views.js";
import { withUrl, withCopy, copyFact } from "../urlactions.js";
import { money } from "./revfigs.js";
import { LEAD_DIMS, activeFilters, filteredBy, appliedWords, figureFile, listOnly, leadsWord, CLEAR_ALL } from "./sa-filters.js";
import { refCell, afterMark } from "./leadref.js";
import { leadsRange, headWords, sentenceWords, versusLive, liveNote, csvName } from "./sa-period.js";

export const VIEWS = [["list", "List"], ["board", "Board: by stage now"], ["timeline", "Timeline: leads per day"], ["map", "Map: leads by country"]];
// A lead's stage now, in words, and the group it joins on the board and in the Stage filter.
export const NOW = { completed: "Completed", paid: "Paid", rescheduled: "Rescheduled", won: "Won", lost: "Lost", cancelled: "Cancelled", no_show: "No-show",
  spam: "Spam", duplicate: "Duplicate", test: "Test" };
export const GROUPS = [["open", "New or open"], ["won", "Won"], ["lost", "Lost"], ["cancelled", "Cancelled or no-show"]];
export const groupOf = (now) => (now === "won" ? "won" : now === "lost" ? "lost" : now === "cancelled" || now === "no_show" ? "cancelled" : "open");
const HELP = "#help?part=leads-and-conversions";
const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
const dash = (v) => (v == null || v === "" ? "-" : String(v));

// One answer per address for a minute: a redraw does not ask again.
const asked = new Map();
afterMark(() => asked.clear());       // a lead marked test (or not): ask again, the row moves
export function fetchLeads(first, last, names) {
  const url = `people/leads?first=${first}&last=${last}${names ? "&names=1" : ""}`;
  const got = asked.get(url);
  if (got && Date.now() - got.at < 60000) return got.p;
  const p = call(url).catch((e) => ({ ok: false, error: String(e?.message || e) }));
  asked.set(url, { at: Date.now(), p });
  p.then((r) => { if (!r?.ok) asked.delete(url); });
  return p;
}

/* The rows the options keep: the period (the demo's one answer covers every period), the
   action, the label, the stage now, the source, and the dashboard's own filters a lead
   carries (source, country, device, campaign: a value not recorded matches none of them);
   left-out rows only when asked for (Show left out, or Stage now: Left out; 2.23: a link
   with lnow=out alone listed nothing). */
export function keepRows(rows, s, r) {
  const out = listOf(s.lshow, ["out"]).length > 0 || s.lnow === "out";
  const dash = Object.entries(LEAD_DIMS).filter(([k]) => s[k]).map(([k, [field]]) => [field, k === "country" ? String(s[k]).toUpperCase() : s[k]]);
  return (rows || []).filter((x) => {
    for (const [field, v] of dash) if ((field === "country" ? String(x[field] || "").toUpperCase() : x[field]) !== v) return false;
    const day = String(x.at || "").slice(0, 10);
    if (day < r.first || day > r.last) return false;
    if (x.left_out && !out) return false;
    if (s.lact && x.action !== s.lact) return false;
    if (s.llabel && x.label !== s.llabel) return false;
    if (s.lnow && (x.left_out ? "out" : groupOf(x.now)) !== s.lnow) return false;
    if (s.lby && (x.source || "Unknown") !== s.lby) return false;
    return true;
  });
}

// What the row says in its Stage cell: the stage now, and "left out" when it is.
const stageWords = (x) => (x.left_out ? `${NOW[x.left_out] || x.left_out} (left out)` : NOW[x.now] || dash(x.now));

/* The list's columns: Name and Email only when the answer holds them (an admin or an owner,
   on a site that keeps them); for everyone else the columns are not there at all. */
export function columnsFor(names, today = "") {
  // Today's rows (2.27: in a period that ends today) carry the live mark: still being counted.
  const live = (v) => (today && String(v || "").slice(0, 10) === today
    ? h("span", null, at(v), h("span", { class: "live-dot", title: "Today, live: still being counted" }, h("span", { class: "vh" }, ", today, live"))) : at(v));
  return [
    { key: "at", label: "When", type: "date", fmt: live, csv: (x) => x.at || "" },
    ...(names ? [{ key: "name", label: "Name", fmt: dash }, { key: "email", label: "Email", fmt: dash, cls: "path nm" }] : []),
    { key: "action", label: "What", fmt: (v, x) => h("span", null, oneAction(v || ""), labelTag(x.label)), csv: (x) => `${oneAction(x.action || "")}${x.label ? ` (${x.label})` : ""}` },
    { key: "now", label: "Stage now", fmt: (_, x) => (x.left_out ? h("b", { class: "pp-bad" }, stageWords(x)) : stageWords(x)), csv: stageWords, sort: stageWords },
    { key: "tool", label: "From", fmt: (v) => toolName(v || ""), csv: (x) => toolName(x.tool || "") },
    // The sender's own ID for the lead (2.25: e.g. an app's account id, u-1001), to find it in its admin.
    // Hidden until Columns shows it; the search finds it either way; always in the CSV.
    // A booking tool's reference is a long address: its end shown, the whole on hover, in the copy and the CSV.
    { key: "ref", label: "Reference", hide: true, csvAlways: true,
      fmt: (v) => refCell(v, v && String(v).length > 28 ? `…${String(v).slice(-26)}` : v), csv: (x) => x.ref || "", sortable: false },
    { key: "source", label: "Source", fmt: dash },
    { key: "first_source", label: "First touch", fmt: dash },
    { key: "landing", label: "Landing page", fmt: dash, path: true },
    { key: "country", label: "Country", fmt: (v) => (v ? countryWords(v) : "-"), country: (x) => x.country || "" },
  ];
}

/* A sale's own facts (2.32.0), only those it carries: its value and currency, what was refunded
   on it, the customer reference your tool sent (an opaque ID, with its copy icon) and its tags. */
export function saleFacts(x) {
  const out = [];
  if (x.value_minor != null && x.currency) out.push(["Value", h("span", { class: "mono" }, money(x.value_minor, x.currency), ` ${x.currency}`)]);
  const back = x.refunded_currency || x.currency;
  if (x.refunded_minor != null && back) out.push(["Refunded", money(x.refunded_minor, back)]);
  if (x.customer_ref) out.push(["Customer", withCopy(h("span", { class: "mono lr-id" }, x.customer_ref), x.customer_ref, { label: `customer ${x.customer_ref}`, cls: "ua-after" })]);
  const tags = Object.entries(x.tags && typeof x.tags === "object" ? x.tags : {});
  if (tags.length) out.push(["Tags", h("span", null, tags.map(([k, v]) => withCopy(h("span", { class: "lbl-tag", title: `Tag: ${k} = ${v}` }, `${k}: ${v}`), String(v), { label: `tag ${k}`, cls: "ua-after" })))]);
  return out;
}

/* A lead in the visitor drawer: its steps (every stage the tools and the lead database
   reported), its pages up to the moment (the page script's, by its visitor ID), its facts. */
export function openLead(x) {
  const facts = [["When", at(x.at)], ...(x.name || x.email ? [["Name", dash(x.name)], ["Email", dash(x.email)]] : []), ["What", h("span", null, oneAction(x.action || ""), labelTag(x.label))],
    ...saleFacts(x), ["Stage now", stageWords(x)], ["From", toolName(x.tool || "")], ["Source (last touch)", dash(x.source)], ["First touch", dash(x.first_source)],
    ["Campaign", dash(x.campaign)], ["Landing page", x.landing ? withUrl(h("span", { class: "mono" }, x.landing), x.landing, { cls: "ua-after" }) : "-"], ["Country", x.country ? countryWords(x.country) : "-"], ["Device", dash(x.device)]];
  // In the address by its row id (lead=1287: js/overlays.js), never a name or an email.
  // id, ref and test (2.25): its reference, every step of it and Mark as test (leadref.js).
  return openVisitor({ conversion: { action: x.action, at: x.at, tool: x.tool, browser: x.browser, journey: x.journey || [], steps: x.steps || [],
    id: x.id, ref: x.ref || null, test: x.left_out === "test" },
    facts: [h("dl", { class: "dw-dl" }, facts.flatMap(([t, v]) => [h("dt", null, t), h("dd", null, copyFact(t, v))]))],
    route: x.id != null ? { key: "lead", value: String(x.id) } : null });
}

/* lead=<id>, from a link: the row in the period on screen (the same answer the list asked
   for), else the plain line. */
export async function openLeadKey(m, s, value) {
  const r = leadsRange(m, s);
  const first = r.kind === "today" ? m.today : r.first, last = r.kind === "today" ? m.today : r.last;
  const ans = await fetchLeads(first, last, mayFind());
  if (!ans?.ok) return ans?.status === 403 ? "Not available to your role." : "The leads could not be loaded just now, so that lead cannot be shown. Open this page again in a minute.";
  const x = (ans.rows || []).find((row) => String(row.id) === String(value));
  return x ? openLead(x) : "That lead is not in the period on screen. Choose a longer period, or it is no longer kept.";
}

// The source choices: the figure's own breakdown of the period (last touch), most first.
function sourceChoices(f, m, r) {
  const days = new Set(daysOf(m, r)), lead = new Set(f?.lead_actions || []), by = {};
  for (const e of f?.days || []) if (e.state === "ok" && days.has(e.day)) for (const [a, per] of Object.entries(e.by?.source_type || {})) if (lead.has(a)) for (const [k, v] of Object.entries(per)) by[k] = (by[k] || 0) + v;
  return Object.keys(by).sort((a, b) => by[b] - by[a]).map((k) => [k, k === "Unknown" ? "Not recorded" : k]);
}

/* The period's days, as the figure counts them. All time starts at the leads' own first day
   (conversions.json `since`) when the site's history began earlier: before it nothing could
   be recorded, so those days are not "not recorded" here. */
export function daysOf(m, r) {
  if (r.kind === "today") return [m.today];
  const since = r.all ? convFile(m)?.since : null;
  return r.days.map((d) => d.day).filter((d) => !since || d >= since);
}

/* The period in words, inside a sentence: "today so far", "the last 7 days", "all time". */
export function periodName(r, s, m = null) {
  if (r.kind === "today") return "today so far";
  if (r.live && m) return sentenceWords(r, m);
  if (r.all) return "all time";
  if (s.range === "yesterday") return "yesterday";
  if (r.length === 1) return long(r.first);
  return s.range && s.range !== "custom" ? `the last ${n(r.length)} days` : `${short(r.first)} to ${short(r.last)}`;
}

// "12% more than the 7 days before (30)", when both periods are whole.
function versus(fm, m, r, got) {
  const p = previousOf(m, r);
  if (!p || r.all) return "";
  const was = leadsOn(fm, p.days.map((d) => d.day));
  // None in either: nothing to compare (the empty state below says where the leads are).
  const cmp = was && was.whole && got.whole && (got.leads || was.leads) ? change(got.leads, was.leads) : null;
  if (!cmp) return "";
  return cmp[0] ? `${cmp[1]} ${cmp[0] === "▲" ? "more" : "fewer"} than the ${n(p.length)} days before (${n(was.leads)})` : `${cmp[1]} as the ${n(p.length)} days before`;
}

/* The count line. With filters the Leads figure can be split by (What, Label, one breakdown):
   the figure itself, "5 leads · filtered: Source = Search engine". With filters it cannot
   (Stage now, Show left out, two breakdowns at once): the rows listed, said as rows listed,
   beside the figure before those filters, and why. Never a figure that is not counted. */
function countLine(m, s, r, fig, list, view) {
  const words = appliedWords(list);
  const said = words ? ` · filtered: ${words}` : "";
  const TITLE = "The Leads figure: forms sent and demos booked, completed, test rows never counted. The same as Overview's Leads tile.";
  const rowsOnly = !fig.f || (view !== "timeline" && view !== "map" && listOnly(s));
  if (!rowsOnly) {
    const fm = withFile(m, "conversions", fig.f);
    const got = leadsOn(fm, daysOf(m, r));
    if (!got || !got.ok) return { node: null, got };
    const vs = r.live ? versusLive(fm, m, r, got, s, fig) : versus(fm, m, r, got);
    const node = h("p", { class: "sa-figure", title: TITLE },
      h("b", null, leadsWord(got.leads)), said, vs ? ` · ${vs}` : "", got.demos ? ` · ${n(got.demos)} demo${got.demos === 1 ? "" : "s"} booked` : "",
      got.whole ? "" : ` · ${n(got.ok)} of ${n(got.of)} days recorded, the others not recorded (never zero)`);
    return { node, got, today: r.live ? leadsOn(fm, [m.today]) : null };
  }
  // The figure before the list's own filters and the breakdowns (What and Label only).
  const base = convFile(m) ? leadsOn(withFile(m, "conversions", narrowConv(convFile(m), s)), daysOf(m, r)) : null;
  const k = h("b", null, "Counting the rows listed…");
  const node = h("p", { class: "sa-figure", title: "A count of the rows listed, not the Leads figure: the figure cannot be split by these filters." },
    k, said, base && base.ok ? ` · of ${leadsWord(base.leads)} in the period (the Leads figure, before these filters)` : "", fig.why ? `. ${fig.why}` : "");
  node.say = (rows) => { k.textContent = `${n(rows)} listed`; };
  return { node, got: null, rowsOnly: true };
}

/* The period has no lead: say so, and where the leads are (the same figure over the last 30
   days, then all time), with a button to each; none at all: "No leads yet" and the hint. */
export function emptyLeads(m, s, r, fig, list) {
  const fm = withFile(m, "conversions", fig.f);
  const count = (range) => { const w = leadsRange(m, { ...s, range }); return { w, got: leadsOn(fm, daysOf(m, w)) }; };
  const btn = (words, range) => h("button", { type: "button", class: "btn", onclick: () => S.set({ range }) }, words);
  const filtered = list.some((x) => x.applied);
  const none = filtered ? "No new leads match these filters" : "No new leads";
  const where = `${none} in ${periodName(r, s, m)}.`;
  const d30 = ["30d", "90d", "all"].includes(s.range) ? null : count("30d");
  if (d30?.got?.leads) {
    return h("div", { class: "sa-empty sa-wider", role: "status" }, h("p", null, `${where} `, h("b", null, leadsWord(d30.got.leads)), ` in ${d30.w.live ? sentenceWords(d30.w, m, true) : "the last 30 days"}.`),
      btn("Show last 30 days", "30d"), btn("All time", "all"));
  }
  const all = s.range === "all" ? null : count("all");
  if (all?.got?.leads) {
    const since = daysOf(m, all.w)[0] || all.w.first;
    return h("div", { class: "sa-empty sa-wider", role: "status" }, h("p", null, `${where} `, h("b", null, leadsWord(all.got.leads)), ` since ${long(since)}${all.w.cut ? `, in the ${n(all.w.length)} days the dashboard holds` : ""}.`),
      btn("All time", "all"));
  }
  if (filtered) return h("div", { class: "sa-empty", role: "status" }, h("p", null, `No lead matches these filters, in any period the dashboard holds.`),
    h("button", { type: "button", class: "btn", onclick: () => S.set(CLEAR_ALL) }, "Clear all filters"));
  return emptyState("No leads yet: nothing has reported a lead for this site.", ["Connect a source of leads", "#settings/integrations"]);
}

function fill(body, make) {
  let tries = 0;
  const go = () => {
    if (!body.isConnected) { if (++tries < 30) requestAnimationFrame(go); return; }
    body.replaceChildren(...[make()].flat(Infinity).filter(Boolean));
  };
  go();
}

export default function leadsTab(m, s) {
  const r = leadsRange(m, s);
  const f = convFile(m);
  const view = viewOf(s.lview, VIEWS);
  const top = tabHead("Leads", "Who are my leads? One row per lead: who, what they did, and where they came from.", r,
    { help: "Every lead of the period from every road: the lead database, the booking tools, the page's script tag and your site's server, each row saying which. The count is the Leads figure, the same as Overview's.", more: HELP,
      ...(r.live ? { period: [headWords(r, m), daysNote()].filter(Boolean).join(" · ") } : {}) });
  if (!f) {
    const raw = m.x.conversions;
    return [...top, emptyState(raw?.state === "error" ? `The leads could not be built: ${raw.error || "no reason given"}.` : "No leads yet: nothing has reported a lead for this site.",
      ["Connect a source of leads", "#settings/integrations"], { bad: raw?.state === "error" })];
  }
  const acts = (f.lead_actions || []).map((a) => [a, actionName(a)]);
  const labels = convLabels(f, s.lact);
  const notList = view === "timeline" || view === "map" ? "The figures are counted when the lead came in, not by its stage now." : "";
  const row = optionsRow("Leads options", [
    select("What", s.lact, acts, (v) => S.set({ lact: v }), { all: "Every kind" }),
    labels.length || s.llabel ? select("Label", s.llabel, labels, (v) => S.set({ llabel: v }), { all: "Every label" }) : null,
    select("Stage now", s.lnow, [...GROUPS, ["out", "Left out"]], (v) => S.set({ lnow: v, lshow: v === "out" ? "out" : s.lshow }), { all: "Every stage", off: notList }),
    select("Source", s.lby, sourceChoices(f, m, r), (v) => S.set({ lby: v }), { all: "Every source", off: view === "map" ? "Leads by country are not split by source." : "" }),
  ], {
    more: [toggles("Show", listOf(s.lshow, ["out"]), [["out", "Left out: test, spam and duplicates"]], (list) => S.set({ lshow: list.join(",") }))],
    end: viewSwitch("Show leads as", view, VIEWS, (k) => S.set({ lview: k === "list" ? "" : k })),
  });
  // Every filter on, from the row and from the top bar's Filters, in one line (sa-filters.js).
  const list = activeFilters(s, view);
  // The map counts by country: the other breakdowns are not applied there (their chips say so).
  const fig = figureFile(m, view === "map" ? { ...s, lby: "", source: "", device: "", campaign: "" } : s);
  const { node: line, got, rowsOnly, today } = countLine(m, s, r, fig, list, view);
  const body = h("div", { class: "sa-view" });
  // 2.27: under the count, today's part of the period and what is verified ("Today so far" was above).
  const live = r.live ? liveNote(m, s, r, today || (rowsOnly ? null : leadsOn(m, [m.today])), today && got ? got.leads : null) : null;
  const out = [...top, ...row, filteredBy(list), line, live, body].filter(Boolean);
  // The period has no lead (the figure says 0 on checked days): where the leads are instead.
  if (got && got.ok && !got.leads) { body.append(emptyLeads(m, s, r, fig, list)); return out; }
  const m2 = fig.f ? withFile(m, "conversions", fig.f) : m;
  if (view === "timeline" || view === "map") {
    if (!fig.f) body.append(h("p", { class: "empty" }, `${fig.why} Remove a filter to see the ${view === "map" ? "map" : "timeline"}.`));
    else body.append(...[view === "map" ? map(m2, s, r, fig) : timeline(m2, s, r, fig)].flat().filter(Boolean));
    return out;
  }

  body.append(h("p", { class: "empty" }, "Loading the leads…"));
  const first = r.kind === "today" ? m.today : r.first, last = r.kind === "today" ? m.today : r.last;
  fetchLeads(first, last, mayFind()).then((ans) => fill(body, () => {
    if (!ans?.ok) return h("div", { class: "state bad", role: "alert" }, h("div", null, ans?.error || "The leads could not be loaded."));
    const rows = keepRows(ans.rows, s, r);
    if (rowsOnly) line.say(rows.length);
    const names = !!ans.names;
    const parts = [];
    if (view === "board") parts.push(board(rows, names, openLead));
    else {
      // The table's own Filter button is not here (2.23): the options row is the filter row.
      parts.push(grid({ ns: "ld", caption: "Leads", file: csvName(r, m), rows, columns: columnsFor(names, r.live ? m.today : ""), sortKey: "at", dir: "desc", onRow: openLead, columnFilters: false,
        placeholder: names ? "Search names, emails, references, sources, pages" : "Search references, sources, pages, countries",
        empty: list.length ? "No lead matches these filters." : "No lead in this period." }));
    }
    const notes = [];
    // The rows the figure counts, as known now, against the figure of the last redraw.
    const counted = keepRows(ans.rows, { ...s, lnow: "", lshow: "" }, r).length;
    if (got && counted !== got.leads) notes.push(`The list holds ${leadsWord(counted)} as known now; the figure above counts ${n(got.leads)} (the days checked at the last redraw).`);
    if (!names) notes.push(DEMO.on ? "In the demo, names and emails are hidden: on your own install, admins and owners see them here."
      : ans.why || "Names and emails show to admins and owners, on a site that keeps them (Settings > Data retention > People).");
    parts.push(...notes.map((t) => h("p", { class: "note" }, t)));
    return parts;
  }));
  return out;
}
