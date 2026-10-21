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

import { h, n, change } from "../ui.js";
import * as S from "../state.js";
import { rangeOf, previousOf } from "../data.js";
import { time as tzTime } from "../tz.js";
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
   action, the label, the stage now, the source; left-out rows only when asked for. */
export function keepRows(rows, s, r) {
  const out = listOf(s.lshow, ["out"]).length > 0;
  return (rows || []).filter((x) => {
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
export function columnsFor(names) {
  return [
    { key: "at", label: "When", type: "date", fmt: (v) => at(v) },
    ...(names ? [{ key: "name", label: "Name", fmt: dash }, { key: "email", label: "Email", fmt: dash, cls: "path nm" }] : []),
    { key: "action", label: "What", fmt: (v, x) => h("span", null, oneAction(v || ""), labelTag(x.label)), csv: (x) => `${oneAction(x.action || "")}${x.label ? ` (${x.label})` : ""}` },
    { key: "now", label: "Stage now", fmt: (_, x) => (x.left_out ? h("b", { class: "pp-bad" }, stageWords(x)) : stageWords(x)), csv: stageWords, sort: stageWords },
    { key: "tool", label: "From", fmt: (v) => toolName(v || ""), csv: (x) => toolName(x.tool || "") },
    { key: "source", label: "Source", fmt: dash },
    { key: "first_source", label: "First touch", fmt: dash },
    { key: "landing", label: "Landing page", fmt: dash, cls: "path" },
    { key: "country", label: "Country", fmt: (v) => (v ? countryWords(v) : "-"), country: (x) => x.country || "" },
  ];
}

/* A lead in the visitor drawer: its steps (every stage the tools and the lead database
   reported), its pages up to the moment (the page script's, by its visitor ID), its facts. */
export function openLead(x) {
  const facts = [["When", at(x.at)], ...(x.name || x.email ? [["Name", dash(x.name)], ["Email", dash(x.email)]] : []), ["What", h("span", null, oneAction(x.action || ""), labelTag(x.label))],
    ["Stage now", stageWords(x)], ["From", toolName(x.tool || "")], ["Source (last touch)", dash(x.source)], ["First touch", dash(x.first_source)],
    ["Campaign", dash(x.campaign)], ["Landing page", dash(x.landing)], ["Country", x.country ? countryWords(x.country) : "-"], ["Device", dash(x.device)]];
  return openVisitor({ conversion: { action: x.action, at: x.at, tool: x.tool, browser: x.browser, journey: x.journey || [], steps: x.steps || [] },
    facts: [h("dl", { class: "dw-dl" }, facts.flatMap(([t, v]) => [h("dt", null, t), h("dd", null, v)]))] });
}

// The period's days, as the figure counts them.
const daysOf = (m, r) => (r.kind === "today" ? [m.today] : r.days.map((d) => d.day));

/* The Leads figure of the period (the options that narrow it: What and Label), against the
   period before: "37 leads, 12% more than the 30 days before". */
function figureLine(m2, m, r) {
  const got = leadsOn(m2, daysOf(m, r));
  if (!got || !got.ok) return { node: null, got: null };
  const p = previousOf(m, r);
  const was = p ? leadsOn(m2, p.days.map((d) => d.day)) : null;
  const cmp = was && was.whole && got.whole ? change(got.leads, was.leads) : null;
  const vs = cmp ? (cmp[0] ? `${cmp[1]} ${cmp[0] === "▲" ? "more" : "fewer"} than the ${n(p.length)} days before (${n(was.leads)})` : `${cmp[1]} as the ${n(p.length)} days before`) : "";
  const node = h("p", { class: "sa-figure", title: "The Leads figure: forms sent and demos booked, completed, test rows never counted. The same as Overview's Leads tile." },
    h("b", null, `${n(got.leads)} lead${got.leads === 1 ? "" : "s"}`), vs ? ` · ${vs}` : "", got.demos ? ` · ${n(got.demos)} demo${got.demos === 1 ? "" : "s"} booked` : "",
    got.whole ? "" : ` · ${n(got.ok)} of ${n(got.of)} days recorded, the others not recorded (never zero)`);
  return { node, got };
}

// The source choices: the figure's own breakdown of the period (last touch), most first.
function sourceChoices(f, m, r) {
  const days = new Set(daysOf(m, r)), lead = new Set(f?.lead_actions || []), by = {};
  for (const e of f?.days || []) if (e.state === "ok" && days.has(e.day)) for (const [a, per] of Object.entries(e.by?.source_type || {})) if (lead.has(a)) for (const [k, v] of Object.entries(per)) by[k] = (by[k] || 0) + v;
  return Object.keys(by).sort((a, b) => by[b] - by[a]).map((k) => [k, k === "Unknown" ? "Not recorded" : k]);
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
  const r = rangeOf(m, s);
  const f = convFile(m);
  const view = viewOf(s.lview, VIEWS);
  const top = tabHead("Leads", "Who are my leads? One row per lead: who, what they did, and where they came from.", r,
    { help: "Every lead of the period from every road: the lead database, the booking tools, the page's script tag and your site's server, each row saying which. The count is the Leads figure, the same as Overview's.", more: HELP });
  if (!f) {
    const raw = m.x.conversions;
    return [...top, emptyState(raw?.state === "error" ? `The leads could not be built: ${raw.error || "no reason given"}.` : "No leads yet: nothing has reported a lead for this site.",
      ["Connect a source of leads", "#settings/integrations"], { bad: raw?.state === "error" })];
  }
  const g = narrowConv(f, s);
  const m2 = withFile(m, "conversions", g);
  const acts = (f.lead_actions || []).map((a) => [a, actionName(a)]);
  const labels = convLabels(f, s.lact);
  const row = optionsRow("Leads options", [
    select("What", s.lact, acts, (v) => S.set({ lact: v }), { all: "Every kind" }),
    labels.length || s.llabel ? select("Label", s.llabel, labels, (v) => S.set({ llabel: v }), { all: "Every label" }) : null,
    select("Stage now", s.lnow, [...GROUPS, ["out", "Left out"]], (v) => S.set({ lnow: v, lshow: v === "out" ? "out" : s.lshow }), { all: "Every stage", off: view === "timeline" || view === "map" ? "The figures are counted when the lead came in, not by its stage now." : "" }),
    select("Source", s.lby, sourceChoices(f, m, r), (v) => S.set({ lby: v }), { all: "Every source", off: view === "map" ? "Leads by country are not split by source." : "" }),
  ], {
    more: [toggles("Show", listOf(s.lshow, ["out"]), [["out", "Left out: test, spam and duplicates"]], (list) => S.set({ lshow: list.join(",") }))],
    end: viewSwitch("Show leads as", view, VIEWS, (k) => S.set({ lview: k === "list" ? "" : k })),
  });
  const { node: line, got } = figureLine(m2, m, r);
  const body = h("div", { class: "sa-view" });
  const out = [...top, ...row, line, body];
  if (view === "timeline") { body.append(...[timeline(m2, s, r)].flat().filter(Boolean)); return out; }
  if (view === "map") { body.append(...[map(m2, s, r)].flat().filter(Boolean)); return out; }

  body.append(h("p", { class: "empty" }, "Loading the leads…"));
  const first = r.kind === "today" ? m.today : r.first, last = r.kind === "today" ? m.today : r.last;
  fetchLeads(first, last, mayFind()).then((ans) => fill(body, () => {
    if (!ans?.ok) return h("div", { class: "state bad", role: "alert" }, h("div", null, ans?.error || "The leads could not be loaded."));
    const rows = keepRows(ans.rows, s, r);
    const counted = keepRows(ans.rows, { ...s, lnow: "", lby: "", lshow: "" }, r).length;
    const names = !!ans.names;
    const parts = [];
    if (view === "board") parts.push(board(rows, names, openLead));
    else {
      parts.push(grid({ ns: "ld", caption: "Leads", file: "leads.csv", rows, columns: columnsFor(names), sortKey: "at", dir: "desc", onRow: openLead,
        placeholder: names ? "Search names, emails, sources, pages" : "Search sources, pages, countries",
        empty: s.lnow || s.lby ? "No lead matches these options." : "No lead in this period." }));
    }
    const notes = [];
    if (got && counted !== got.leads && !s.lnow && !s.lby) notes.push(`The list holds ${n(counted)} lead${counted === 1 ? "" : "s"} as known now; the figure above counts ${n(got.leads)} (the days checked at the last redraw).`);
    if (!names) notes.push(DEMO.on ? "In the demo, names and emails are hidden: on your own install, admins and owners see them here."
      : ans.why || "Names and emails show to admins and owners, on a site that keeps them (Settings > Data retention > People).");
    parts.push(...notes.map((t) => h("p", { class: "note" }, t)));
    return parts;
  }));
  return out;
}
