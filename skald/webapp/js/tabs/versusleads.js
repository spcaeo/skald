// Compare, leads (2.5.0): leads, demos booked and every completed action,
// A against B, in total, per source (last touch) and per landing page, from
// conversions.json's checked days - the same days the Conversions tab sums.
// Only when both periods are whole and verified: every day whole in the log
// and checked in conversions. Otherwise it says what stands in the way and
// shows no figure. Conversions do not know about page groups or filters.

import { h, n } from "../ui.js";
import { table } from "../table.js";
import { info } from "./tiles.js";
import { convFile, convDay, minRate, labelColumn, UNKNOWN, LEAD_WORDS } from "./leadfigs.js";

function daysOf(from, to) {
  const out = [];
  for (let d = new Date(`${from}T00:00:00Z`); out.length < 400; d.setUTCDate(d.getUTCDate() + 1)) {
    const iso = d.toISOString().slice(0, 10);
    if (iso > to) break;
    out.push(iso);
  }
  return out;
}

// One side's sums, or the reason it has none.
function side(f, x) {
  const fin = new Set(f.finished || ["completed", "paid"]), leads = new Set(f.lead_actions || []), demos = new Set(f.demo_actions || ["demo"]);
  const out = { leads: 0, demos: 0, all: 0, by: { source_type: {}, landing: {} }, demosBy: { source_type: {}, landing: {} } };
  const bad = [];
  for (const day of daysOf(x.from, x.to)) {
    const e = convDay(f, day);
    if (e?.state !== "ok") { bad.push([day, e?.state || "not in the file"]); continue; }
    for (const [a, per] of Object.entries(e.stages || {})) for (const [st, v] of Object.entries(per)) {
      if (!fin.has(st)) continue;
      out.all += v;
      if (leads.has(a)) out.leads += v;
      if (demos.has(a)) out.demos += v;
    }
    for (const dim of ["source_type", "landing"]) for (const [a, per] of Object.entries(e.by?.[dim] || {})) {
      if (!leads.has(a)) continue;
      for (const [k, v] of Object.entries(per)) {
        out.by[dim][k] = (out.by[dim][k] || 0) + v;
        if (demos.has(a)) out.demosBy[dim][k] = (out.demosBy[dim][k] || 0) + v;
      }
    }
  }
  return { out, bad };
}

const pct = (a, b) => (a === b ? "0%" : b ? `${a > b ? "+" : "−"}${Math.round(Math.abs((a - b) / b) * 100)}%` : a ? "new" : "-");
function delta(a, b) {
  const d = a - b;
  return h("span", { class: `vs-d ${d > 0 ? "up good" : d < 0 ? "down bad" : "flat"}` }, d ? `${d > 0 ? "+" : "−"}${n(Math.abs(d))}` : "0");
}

/* One breakdown, A against B: a label, then two groups of three - Leads
   (A, B, the change with its percentage under it) and Demos booked (the
   same). Full width; on a narrow screen the figures scroll under a label
   column that stays put. "Not recorded" reads muted and sorts last. */
function dimTable(A, B, dim, name, one, drill, file) {
  const keys = new Set([...Object.keys(A.by[dim]), ...Object.keys(B.by[dim])]);
  const rows = [...keys].map((k) => ({ k, label: k, a: A.by[dim][k] || 0, b: B.by[dim][k] || 0, da: A.demosBy[dim][k] || 0, db: B.demosBy[dim][k] || 0 }))
    .filter((x) => x.a || x.b).map((x) => ({ ...x, d: x.a - x.b, dd: x.da - x.db }))
    .sort((x, y) => (x.k === UNKNOWN) - (y.k === UNKNOWN) || y.a - x.a || y.b - x.b || x.k.localeCompare(y.k));
  const by = (f) => (x) => (x.k === UNKNOWN ? null : f(x));
  const change = (a, b) => (a === b ? delta(a, b) : h("span", null, delta(a, b), h("span", { class: "d-pct" }, pct(a, b))));
  const t = table([
    labelColumn(one, drill, dim === "landing"),
    { key: "a", label: "A", num: true, cls: "g-start", sort: by((x) => x.a), title: "Leads in A" },
    { key: "b", label: "B", num: true, sort: by((x) => x.b), title: "Leads in B" },
    { key: "d", label: "±", num: true, sort: by((x) => x.d), title: "Leads: A against B", fmt: (_, x) => change(x.a, x.b), csv: (x) => x.d },
    { key: "da", label: "A", num: true, cls: "g-start", sort: by((x) => x.da), title: "Demos booked in A" },
    { key: "db", label: "B", num: true, sort: by((x) => x.db), title: "Demos booked in B" },
    { key: "dd", label: "±", num: true, sort: by((x) => x.dd), title: "Demos booked: A against B", fmt: (_, x) => change(x.da, x.db), csv: (x) => x.dd },
  ], { caption: `Leads by ${name}, A against B`, rows, file, sortKey: "a", limit: 10, search: false, empty: "No lead in either period.",
    groups: [["", 1], ["Leads", 3], ["Demos booked", 3]] });
  t.classList.add("lead-tbl");
  return t;
}

export function leadsCompare(m, s, res) {
  const f = convFile(m);
  if (!f) return null;
  const head = h("div", { class: "card-h start" }, h("h2", null, "Leads and demos booked"),
    info(`${LEAD_WORDS} From the Conversions data, A against B. Only when both periods are whole and verified: every day whole in the visitor figures and checked in conversions.`, "Leads and demos booked"));
  const say = (text) => h("section", { class: "s" }, head, h("p", { class: "cmp-why", role: "note" }, text));
  if (s.view && s.view !== "all") return say("Not compared here: leads are counted for the whole site, not per page group. Choose All pages.");
  if (res.filtered) return say("Not compared with these filters: leads are not split by them. Clear the filters to compare leads.");
  for (const [nm, x] of [["A", res.a], ["B", res.b]]) {
    if (x.used !== x.days || (x.excluded || []).length) return say(`Not compared: ${nm} has ${n(x.days - x.used)} day${x.days - x.used === 1 ? "" : "s"} that ${x.days - x.used === 1 ? "is" : "are"} not whole and verified.`);
  }
  const a = side(f, res.a), b = side(f, res.b);
  for (const [nm, x] of [["A", a], ["B", b]]) {
    if (x.bad.length) {
      const held = x.bad.filter(([, st]) => st === "withheld").length;
      return say(`Not compared: ${n(x.bad.length)} day${x.bad.length === 1 ? "" : "s"} of ${nm} ${x.bad.length === 1 ? "has" : "have"} no checked conversions (${held ? `${n(held)} withheld, ` : ""}the rest not recorded${f.since ? `; conversions are recorded from ${f.since}` : ""}). A day not recorded is never counted as zero.`);
    }
  }
  const A = a.out, B = b.out;
  const kpi = (label, about, x, y) => h("div", { class: "vs-kpi" }, h("div", { class: "k-l" }, label, info(about, label)),
    h("div", { class: "vs-pair" }, h("span", { class: "vs-main" }, h("i", { class: "sa", "aria-hidden": "true" }), h("span", { class: "vh" }, "A "), n(x)),
      h("span", { class: "vs-other" }, "vs ", h("i", { class: "sb", "aria-hidden": "true" }), h("span", { class: "vh" }, "B "), n(y))),
    h("span", { class: "vs-d" }, delta(x, y), h("small", null, ` ${pct(x, y)}`)));
  const base = `compare-leads-${res.a.from}-to-${res.a.to}-vs-${res.b.from}-to-${res.b.to}`;
  return h("section", { class: "s vs-leads" }, head,
    h("div", { class: "vs-kpis" },
      kpi("Leads", LEAD_WORDS, A.leads, B.leads),
      kpi("Demos booked", "Demo bookings completed: Calendly, Cal.com, HubSpot meetings, the script tag and the lead database. Part of the leads.", A.demos, B.demos),
      kpi("All completed", "Every completed action: leads, payments, deals and clicks.", A.all, B.all)),
    res.a.days !== res.b.days ? h("p", { class: "note" }, "The periods have a different number of days: these are totals, not a typical day.") : null,
    h("div", { class: "sheet" }, h("h3", null, "By source (last touch)"), dimTable(A, B, "source_type", "source", "Source", "source", `${base}-sources.csv`)),
    h("div", { class: "sheet" }, h("h3", null, "By landing page"), dimTable(A, B, "landing", "landing page", "Page", "landing", `${base}-pages.csv`)),
    h("p", { class: "note" }, `Sources are the last touch: the visit the lead was sent from. The landing page is the one recorded with the lead. "Not recorded" is a lead the tool sent without it (a booking tool sends no landing page), never guessed. A change in a handful of leads says little: below ${minRate(f)} in either period, read the counts, not the percentage.`));
}
