// #32: one period rule on every Leads & sales tab, today included, and leads only.
//
// The owner, 11 Nov: the same click showed different counts. On "7 days" Leads counted today
// and the 6 days before, Summary, Sources and the rest 7 whole days up to yesterday. Now every
// tab asks js/tabs/sa-period.js salesRange for its period (a source check below holds every tab
// to it), today's part is marked live, Summary's Leads tile and the Leads tab count the same
// leads (the lead actions of conversions.json only, never a click, a payment or a site's own
// action), and the period's figure is checked against conversions.json today.periods (its
// second count: audit_conversions_leads.check_periods): a figure that does not match is withheld.
//
//   node tests/js/sales-period.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { setContext } = await import(new URL("tabs/common.js", JS));
const { leadsOn } = await import(new URL("tabs/leadfigs.js", JS));
const { ME } = await import(new URL("access.js", JS));
const P = await import(new URL("tabs/sa-period.js", JS));
const PL = await import(new URL("tabs/sa-pipeline.js", JS));
const sales = (await import(new URL("tabs/s-sales.js", JS))).default;
const TAB = Object.fromEntries(sales.map(([k, , render]) => [k, render]));

const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const tick = () => new Promise((r) => setTimeout(r, 5));
const go = (hash) => { location.hash = hash; return S.read(); };

// ---- the fixture: 1 Oct to today (22 Oct). Leads on 10 Oct (2), 16 Oct (1) and today (2), and
// rows of other kinds every day: button clicks, a payment, an app's own runs. Never leads.
const TODAY = "2026-10-22";
const iso = (k) => new Date(Date.UTC(2026, 9, 1) + k * 864e5).toISOString().slice(0, 10);   // iso(0) = 1 Oct
const byDay = new Map();
for (let i = 0; i < 21; i += 1) byDay.set(iso(i), { day: iso(i), state: "ok", readers: 10 });    // to 21 Oct
const other = { cta: { completed: 9 }, paid: { completed: 1 }, xray: { completed: 4 } };
const LEADS = { "2026-10-10": { signup: { completed: 2 } }, "2026-10-16": { contact: { completed: 1, started: 3 } }, [TODAY]: { signup: { completed: 1 }, demo: { completed: 1, started: 2 } } };
const days = [];
for (let i = 0; i <= 21; i += 1) {
  const d = iso(i), mine = LEADS[d] || {};
  const stages = { ...other, ...mine };
  const tool = Object.fromEntries(Object.keys(stages).map((a) => [a, { lead: (stages[a].completed || 0) }]));
  days.push({ day: d, state: "ok", stages, abandoned: {}, labels: {}, labels_abandoned: {},
    by: { source_type: Object.fromEntries(Object.entries(stages).map(([a, st]) => [a, { "Search engine": st.completed || 0 }])), tool },
    visits_before: {}, time_to_convert: {}, assisted: null, likely_ai: {} });
}
const sum = (first, last) => days.filter((d) => d.day >= first && d.day <= last)
  .reduce((x, d) => x + ["signup", "contact", "demo"].reduce((y, a) => y + (d.stages[a]?.completed || 0), 0), 0);
const periods = [7, 30, 90].map((k) => {
  const first = new Date(Date.parse(`${TODAY}T00:00:00Z`) - (k - 1) * 864e5).toISOString().slice(0, 10);
  return { back: k, first, last: TODAY, state: k === 7 ? "ok" : "partial", leads: sum(first, TODAY), actions: {}, days_ok: Math.min(k, 22) };
});
const f = { available: true, since: "2026-10-01", finished: ["completed", "paid"], lead_actions: ["contact", "signup", "waitlist", "trial", "demo"], demo_actions: ["demo"], min_rate: 10, abandon_hours: 24,
  dims: ["source_type", "tool"], days, timeline: [], pages_before: null, period: { first: "2026-09-23", last: TODAY },
  today: { day: TODAY, state: "ok", total: 2, tests: 0, rows: [], periods } };
const m = { site: "example.com", today: TODAY, anchor: "2026-10-21", firstDay: "2026-10-01", byDay, views: [], journeys: [], options: {}, days: [...byDay.values()], x: { conversions: f, events: null, funnels: null } };

// ---- 1. the rule, choice by choice
{
  const r7 = P.salesRange(m, { range: "7d" });
  assert.deepEqual([r7.first, r7.last, r7.length, r7.live], ["2026-10-16", TODAY, 7, true], "7 days: today and the 6 before");
  assert.deepEqual(P.periodDays(m, r7), ["2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", TODAY]);
  assert.equal(P.salesRange(m, { range: "30d" }).first, "2026-09-23");
  assert.equal(P.salesRange(m, { range: "90d" }).length, 90);
  const all = P.salesRange(m, { range: "all" });
  assert.deepEqual([all.first, all.last, all.live, all.all], ["2026-10-01", TODAY, true, true], "All time: to today");
  assert.deepEqual([P.salesRange(m, { range: "today" }).kind, P.salesRange(m, { range: "today" }).first], ["today", TODAY]);
  const y = P.salesRange(m, { range: "yesterday" });
  assert.deepEqual([y.first, y.last, !!y.live], ["2026-10-21", "2026-10-21", false], "Yesterday: one whole day");
  const c1 = P.salesRange(m, { range: "custom", from: "2026-10-05", to: "2026-10-08" });
  assert.deepEqual([c1.first, c1.last, !!c1.live], ["2026-10-05", "2026-10-08", false], "a custom period before today: as chosen");
  const c2 = P.salesRange(m, { range: "custom", from: "2026-10-18", to: "2026-10-25" });
  assert.deepEqual([c2.first, c2.last, c2.live], ["2026-10-18", TODAY, true], "a custom period that reaches today ends today");
  assert.equal(P.salesLive({ range: "7d" }), true);
  assert.equal(P.salesLive({ range: "yesterday" }), false);
  assert.equal(P.periodBefore(m, r7), null, "a live period has no whole period before it: versusLive compares it to this hour");
  assert.deepEqual([P.periodBefore(m, y).first, P.periodBefore(m, y).last], ["2026-10-20", "2026-10-20"]);
  // Include today (inc=1) belongs to Overview and Pages: it never changes a Leads & sales period.
  assert.deepEqual(P.salesRange(m, { range: "yesterday", inc: "1", tab: "sales/summary" }), y);
}

// ---- 2. leads only: other kinds of row are never counted
{
  const g = PL.leadsOnly(f);
  assert.deepEqual(Object.keys(g.days[0].stages).sort(), [], "1 Oct: clicks, a payment and runs only: no lead");
  assert.deepEqual(Object.keys(g.days.at(-1).stages).sort(), ["demo", "signup"]);
  assert.deepEqual(Object.keys(g.days.at(-1).by.source_type).sort(), ["demo", "signup"], "the breakdowns too");
  assert.deepEqual(PL.convActions(f).map(([a]) => a).sort(), ["contact", "demo", "signup"], "What lists kinds of lead only");
  assert.equal(PL.leadsOnly(null), null);
}

// ---- 3. the same click, the same count, on every tab: 7 days
ME.role = "viewer";
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true, names: false, rows: [] }) });
async function draw(tab, hash) {
  const s = go(hash);
  setContext(m, s);
  document.body.replaceChildren();
  document.body.append(...flat(TAB[tab](m, s, {})));
  for (let i = 0; i < 6; i += 1) await tick();
  return document.body;
}
const want = sum("2026-10-16", TODAY);
assert.equal(want, 3, "16 Oct's contact form and today's two");
{
  const words = "Last 7 days: Fri 16 Oct to Thu 22 Oct (today, so far)";
  const leads = await draw("leads", "#sales/leads");
  assert.equal(text(leads.querySelector(".period")), words, "Leads names the days");
  assert.match(text(leads.querySelector(".sa-figure")), /^3 leads/, "Leads: 3, today's included");
  const summary = await draw("summary", "#sales/summary");
  assert.equal(text(summary.querySelector(".period")), words, "Summary names the same days");
  const tile = summary.querySelectorAll(".tile").find((t) => text(t).startsWith("Leads"));
  assert.equal(text(tile.querySelector(".t-v")), "3", "Summary's Leads tile: the same 3");
  assert.equal(leadsOn(m, P.periodDays(m, P.salesRange(m, { range: "7d" }))).leads, 3, "the one sum both read");
  assert.ok(summary.querySelector(".sa-live"), "today's part marked live on Summary too");
  const each = summary.querySelectorAll("h2").find((x) => text(x).startsWith("Each kind of lead"));
  const rows = each.parentNode.querySelectorAll("tr").map(text);
  assert.ok(!rows.some((t) => /^(Button clicks|Payments|Xray)/.test(t)), `leads only in the table: ${rows.join(" | ")}`);
  const revenue = await draw("revenue", "#sales/revenue");
  assert.equal(text(revenue.querySelector(".period")), words, "Revenue names the same days");
  // 30 days: the same on every tab again.
  // (draw() reuses the page: each is read before the next is drawn.)
  const l30 = await draw("leads", "#sales/leads?range=30d");
  assert.match(text(l30.querySelector(".sa-figure")), new RegExp(`^${sum("2026-09-23", TODAY)} leads`));
  const s30 = await draw("summary", "#sales/summary?range=30d");
  assert.equal(text(s30.querySelectorAll(".tile").find((t) => text(t).startsWith("Leads")).querySelector(".t-v")), String(sum("2026-09-23", TODAY)));
}
{
  // Funnels counts the visits of the same days: today's journeys are in its 7 days.
  const journeys = [{ day: TODAY, source: "Search engine", pages: ["/", "/pricing/"], paths: ["/", "/pricing/"] }, { day: "2026-10-15", source: "Direct", pages: ["/"], paths: ["/"] }];
  const r = P.salesRange(m, { range: "7d" });
  const inRange = journeys.filter((j) => j.day >= r.first && j.day <= r.last);
  assert.deepEqual(inRange.map((j) => j.day), [TODAY], "the funnel's 7 days hold today's visits, not 15 Oct's");
}

// ---- 4. the period's figure against its second count (today.periods)
{
  const r7 = P.salesRange(m, { range: "7d" });
  const got = leadsOn(m, P.periodDays(m, r7));
  assert.deepEqual(P.periodCheck(m, r7, got), { ok: true, checked: true }, "the file's 7 days agree");
  const r30 = P.salesRange(m, { range: "30d" });
  assert.equal(P.periodCheck(m, r30, leadsOn(m, P.periodDays(m, r30))).checked, undefined, "a partial period is not checked");
  const bad = { ...m, x: { ...m.x, conversions: { ...f, today: { ...f.today, periods: [{ ...periods[0], leads: 4 }, ...periods.slice(1)] } } } };
  const no = P.periodCheck(bad, r7, leadsOn(bad, P.periodDays(bad, r7)));
  assert.equal(no.ok, false);
  assert.match(no.why, /do not reconcile: 3 summed day by day, 4 counted for the whole period/);
  // Withheld on the page: Summary's tile has no number, Leads says why.
  const s = go("#sales/summary");
  setContext(bad, s);
  const out = flat(TAB.summary(bad, s, {}));
  const tile = out.flatMap((el) => (el.querySelectorAll ? el.querySelectorAll(".tile") : [])).find((t) => text(t).startsWith("Leads"));
  assert.equal(text(tile.querySelector(".t-v")), "-", "Summary: no figure");
  assert.match(text(tile), /withheld/);
  const s2 = go("#sales/leads");
  setContext(bad, s2);
  const out2 = flat(TAB.leads(bad, s2, {}));
  assert.ok(out2.some((el) => el.matches?.(".state.bad") && /do not reconcile/.test(text(el))), "Leads: withheld, with why");
  // One kind: checked by the file's own count of that kind.
  const byKind = { ...m, x: { ...m.x, conversions: { ...f, today: { ...f.today, periods: [{ ...periods[0], actions: { contact: 1, signup: 1, demo: 1 } }] } } } };
  const g = PL.narrowConv(PL.leadsOnly(f), { lact: "signup" });
  const mk = { ...byKind, x: { ...byKind.x, conversions: { ...byKind.x.conversions, days: g.days } } };
  assert.equal(P.periodCheck(mk, r7, leadsOn(mk, P.periodDays(mk, r7)), { lact: "signup" }).ok, true, "1 sign-up: agrees");
}

// ---- 5. the source check: no Leads & sales tab builds its own period
{
  const read = (rel) => readFileSync(new URL(rel, JS), "utf8");
  const TABS = { "tabs/sa-leads.js": "sales/leads", "tabs/sa-pipeline.js": "sales/summary", "tabs/sa-revenue.js": "sales/revenue", "tabs/funnels.js": "sales/funnels" };
  // Each tab module the section registers, and the renderers and parts they draw with.
  const PARTS = ["tabs/conversions.js", "tabs/sa-steps.js", "tabs/sa-views.js", "tabs/sa-filters.js", "tabs/sa-options.js", "tabs/sa-find.js", "tabs/sa-rate.js", "tabs/funnelhistory.js", "tabs/funnel-leads.js"];
  const src = read("tabs/s-sales.js");
  for (const [file, route] of Object.entries(TABS)) {
    const mod = file.replace("tabs/", "./");
    assert.ok(src.includes(`from "${mod}"`), `${route} is drawn by ${file}`);
    assert.match(read(file), /from "\.\/sa-period\.js"/, `${file} takes its period from sa-period.js`);
    assert.match(read(file), /salesRange\(m, s\)/, `${file} asks salesRange for it`);
  }
  const BUILDS = /\b(rangeOf|previousOf|withToday|allTime|daysBetween)\s*\(|addDays\(\s*m\.today|from "\.\.\/period-dates\.js"/;
  for (const file of [...Object.keys(TABS), ...PARTS]) {
    const body = read(file).replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
    assert.doesNotMatch(body, BUILDS, `${file} builds no period of its own`);
    assert.doesNotMatch(body, /import\s*\{[^}]*\b(rangeOf|previousOf)\b[^}]*\}\s*from "\.\.\/data\.js"/, `${file} imports no period from data.js`);
  }
  // Only sa-period.js builds it, and only from data.js's own days.
  assert.match(read("tabs/sa-period.js"), /export function salesRange\(m, s\)/);
  // Every tab of the section is one of the four: a new tab must be added to this check.
  assert.deepEqual(sales.map(([k]) => `sales/${k}`).sort(), Object.values(TABS).sort());
}

console.log("sales-period: all passed");
