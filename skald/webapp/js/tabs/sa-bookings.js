// Leads & sales > Calendar bookings (2.7.0 as Bookings; renamed in 2.20, the route stays
// sales/bookings): "Who booked a call?" Calls booked through Calendly and Cal.com, and the
// payments Stripe reports where a site sends them, as those tools and the page's script tag
// reported them: every stage of one booking action, the demo funnel (opened, chose a time,
// booked, cancelled, rescheduled, no-show, won), where the booked ones came from, and the
// cancelled, removed and test ones listed in full.
//
// One file only, the tools' (conversions.json). The lead database's own "Demos
// booked" stays on Pipeline (Count from: Lead database): the two are never added.
// The figures are drawn by conversions.js over the file narrowed to the chosen
// action (as Pipeline narrows it), so each is summed by today's code.
//
// Options, kept in the address: bact (the booking action; the first is the
// file's demo action), bshow (cancelled, removed, test: the lists).

import { h, n } from "../ui.js";
import * as S from "../state.js";
import { rangeOf } from "../data.js";
import { time as tzTime } from "../tz.js";
import conversions from "./conversions.js";
import { actionName, toolName, STAGE } from "./leadfigs.js";
import { grid } from "../grid.js";
import { tabHead, optionsRow, select, toggles, listOf, foldNotes } from "./sa-options.js";
import { convList, CONV_SHOW } from "./sa-lists.js";
import { openVisitor } from "./visitor.js";
import { refCell } from "./leadref.js";
import { connectCard } from "../ui/connect.js";
import { fedFromData } from "../connect-plan.js";

// Tools that book or take payment: an action any of them reported is a booking action.
const BOOKING_TOOLS = new Set(["calendly", "calcom", "stripe"]);
// The tab keeps the parts that are about one booking action; the rest is Pipeline's or People's.
const KEEP = new Map([["Every action", "Every stage"], ["Demo funnel", "Demo funnel"], ["Where the completed ones came from", "Where the booked ones came from"]]);

// The booking actions in the file, demos first: [[action, words]].
function bookingActions(f) {
  const tools = new Map();
  const demos = f.demo_actions || ["demo"];
  for (const a of demos) tools.set(a, new Set());
  for (const d of f.days || []) {
    if (d.state !== "ok") continue;
    for (const [a, per] of Object.entries(d.by?.tool || {})) {
      const set = new Set(Object.keys(per));
      if (demos.includes(a) || [...set].some((t) => BOOKING_TOOLS.has(t))) {
        const got = tools.get(a) || new Set();
        for (const t of set) if (BOOKING_TOOLS.has(t)) got.add(t);
        tools.set(a, got);
      }
    }
  }
  return [...tools.entries()].map(([a, t]) => [a, `${actionName(a)}${t.size ? ` (${[...t].map(toolName).sort().join(", ")})` : ""}`]);
}

function narrow(f, a) {
  const pick = (o) => (o && a in o ? { [a]: o[a] } : {});
  return { ...f, days: (f.days || []).map((d) => (d.state !== "ok" ? d : { ...d, stages: pick(d.stages), abandoned: pick(d.abandoned),
    by: Object.fromEntries(Object.entries(d.by || {}).map(([dim, per]) => [dim, pick(per)])),
    visits_before: pick(d.visits_before), time_to_convert: pick(d.time_to_convert),
    assisted: d.assisted ? pick(d.assisted) : d.assisted, likely_ai: d.likely_ai ? pick(d.likely_ai) : d.likely_ai })) };
}

const titleOf = (el) => (el?.matches?.("section") ? el.querySelector(":scope > h2")?.firstChild : el?.matches?.("details") ? el.querySelector(":scope > summary")?.firstChild : null);

/* A row of today opens the visitor drawer (2.25): its reference with a copy icon, today's
   steps of that reference, and Mark as test for owners and admins (leadref.js). */
export function openStep(r, all) {
  const same = r.ref ? all.filter((x) => x.tool === r.tool && x.ref === r.ref) : [r];
  return openVisitor({ conversion: { action: r.action, at: r.at, tool: r.tool, stage: r.stage, id: r.id ?? null, ref: r.ref || null, test: !!r.test,
    steps: same.map((x) => ({ action: x.action, stage: x.stage, at: x.at, tool: x.tool, test: !!x.test })) } });
}

// Today's rows of this action, every stage, test marked: a listing, not a figure.
function today(f, a) {
  const t = f.today;
  if (!t || t.state !== "ok") return null;
  const rows = (t.rows || []).filter((r) => r.action === a);
  const at = (ts) => (ts ? tzTime(ts, { label: false }) : "-");
  const dash = (v) => (v == null || v === "" ? "-" : v);
  return h("section", { class: "s" }, h("h2", null, "Today, as it came in"),
    h("p", { class: "sub" }, `Each ${actionName(a).toLowerCase().replace(/s$/, "")} step today, newest first: started, booked, cancelled and the rest. A row marked test is kept and never counted.`),
    grid({ ns: "bt", caption: `Today's ${actionName(a).toLowerCase()}`, file: "bookings-today.csv", rows, sortKey: "at", dir: "desc",
      columns: [{ key: "at", label: "Time", type: "date", fmt: (v) => at(v) }, { key: "stage", label: "Stage", fmt: (v, r) => h("span", null, STAGE[v] || dash(v), r.test ? h("b", { class: "pp-bad" }, " test (not counted)") : null), csv: (r) => `${r.stage}${r.test ? " (test)" : ""}` },
        { key: "tool", label: "Reported by", fmt: (v) => (v ? toolName(v) : "-"), csv: (r) => r.tool }, { key: "source", label: "Source", fmt: dash }, { key: "campaign", label: "Campaign", fmt: dash },
        { key: "landing", label: "Landing", path: true, fmt: dash }, { key: "country", label: "Country", fmt: dash }, { key: "device", label: "Device", fmt: dash },
        { key: "ref", label: "Reference", hide: true, csvAlways: true, fmt: (v) => refCell(v), csv: (r) => r.ref || "", sortable: false }],
      filters: [{ key: "stage", label: "Stage", options: [...new Set(rows.map((r) => r.stage))].map((k) => [k, STAGE[k] || k]) }],
      onRow: (r) => openStep(r, t.rows || []),
      empty: "None so far today." }),
    t.tests ? h("p", { class: "note" }, `${n(t.tests)} row${t.tests === 1 ? "" : "s"} marked test today, kept apart.`) : null);
}

export default function bookings(m, s, o) {
  const f = m.x.conversions;
  const ready = f && f.available && Array.isArray(f.days);
  const acts = ready ? bookingActions(f) : [];
  const a = acts.some(([k]) => k === s.bact) ? s.bact : acts[0]?.[0];
  const m2 = Object.create(m);
  m2.x = { ...m.x, conversions: ready && a ? narrow(f, a) : f };
  let body = [conversions(m2, s, o)].flat(Infinity).filter(Boolean).filter((el) => !el.classList?.contains("head"));
  const r = rangeOf(m, s);
  const top = tabHead("Calendar bookings", "Who booked a call? Bookings made through Calendly and Cal.com, step by step, and payments Stripe reports where your site sends them.", r,
    { help: "Counted from the booking and payment tools (Calendly, Cal.com, Stripe) with the page's script tag and the lead database. The lead database's own demos booked are on Summary (Count from: Lead database), never added to these.", more: "#help?part=demo-bookings", source: "bookings" });
  // 2.43: no booking tool: what this page needs and how to connect it (js/ui/connect.js).
  if (!ready || !acts.length) return [...top, connectCard(m, "bookings", { s })];
  // Bookings only from the lead database or the script tag: one line, Calendly or Cal.com not connected.
  const noTool = fedFromData("bookings", m) ? null : connectCard(m, "bookings", { s, mode: "line", title: "No booking tool connected", line: "Calendly or Cal.com would add each booking's every step." });
  body = body.filter((el) => {
    const t = titleOf(el);
    if (!t) return !el.matches?.("section, details");
    const keep = KEEP.get(t.textContent.trim());
    if (keep) t.textContent = keep;
    return !!keep;
  });
  const show = listOf(s.bshow, CONV_SHOW.map(([k]) => k));
  const row = optionsRow("Calendar bookings options", [
    select("Booking", a || "", acts, (v) => S.set({ bact: v }), { all: null }),
  ], { more: [toggles("Show left out", show, CONV_SHOW, (list) => S.set({ bshow: list.join(",") }))] });
  const lists = show.length && a ? [convList(show, { ns: "bk", only: (x) => x === a, title: `Cancelled, removed and test: ${actionName(a).toLowerCase()}` })] : [];
  const live = r.kind === "today" && a ? today(f, a) : null;
  foldNotes(body);
  if (live) foldNotes([live]);
  return [...top, noTool, ...row, live, ...body, ...lists,
    h("p", { class: "note" }, "Time to convert, the touches and the pages seen before are on ", h("a", { href: S.hashFor({ ...s, tab: "sales/sources", lsrc: "all", lact: a || "" }) }, "Sources, counted from the tools"), ".")].filter(Boolean);
}
