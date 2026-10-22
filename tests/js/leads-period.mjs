// Leads & sales opens on 7 days, All time, the empty state that says where the leads are,
// and one filter system on Leads (2.23; js/state.js SECTION_RANGE, js/data.js allTime,
// js/tabs/sa-leads.js, js/tabs/sa-filters.js).
//
// The owner, live, 2026-10-22: #sales/leads said "0 leads · No lead in this period" while the
// site had 5 signups on 20 and 21 Oct; the page had opened on Today, carried from Overview.
//
//   node tests/js/leads-period.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { rangeOf, allTime } = await import(new URL("data.js", JS));
const { periodWords, rangeWords, setContext } = await import(new URL("tabs/common.js", JS));
const { leadsOn } = await import(new URL("tabs/leadfigs.js", JS));
const { ME } = await import(new URL("access.js", JS));
const L = await import(new URL("tabs/sa-leads.js", JS));
const F = await import(new URL("tabs/sa-filters.js", JS));
const { timeline, map } = await import(new URL("tabs/sa-views.js", JS));

const go = (hash) => { location.hash = hash; return S.read(); };
const qOf = () => new URLSearchParams(location.hash.split("?")[1] || "");
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const tick = () => new Promise((r) => setTimeout(r, 5));

// ---- 1. the period a section opens on
const SALES = S.SECTIONS.find((x) => x.key === "sales").tabs.map(([k]) => k);
assert.deepEqual(SALES, ["sales/leads", "sales/summary", "sales/sources", "sales/bookings", "sales/funnels", "sales/events", "sales/people"]);
for (const tab of SALES) assert.equal(go(`#${tab}`).range, "7d", `${tab} with no range opens on 7 days`);
assert.equal(go("#sales").range, "7d", "the bare section too");
for (const tab of ["overview/summary", "traffic/sources", "ai/assistants", "site/health"]) assert.equal(go(`#${tab}`).range, "today", `${tab} keeps Today`);
assert.equal(go("#sales/leads?range=today").range, "today", "an explicit range always wins");
assert.equal(go("#sales/leads?range=30d").range, "30d");
assert.equal(go("#sales/leads?range=nonsense").range, "7d", "a range not known: the section's own");
assert.equal(go("#sales/leads?range=custom&from=bad").range, "7d", "a custom period without its days: the section's own");
// Overview (Today) into Leads & sales: 7 days, not Today; the address names no range.
go("#overview/summary");
S.set({ tab: "sales/leads" });
assert.equal(S.read().range, "7d", "Overview's Today is not carried into Leads & sales");
assert.ok(!qOf().has("range"), `no range written: ${location.hash}`);
// The links drawn to another section say the same (the menu, the tab strip: hashFor).
go("#overview/summary");
assert.ok(!S.hashFor({ ...S.read(), tab: "sales/leads" }).includes("range="), "a link from Overview to Leads carries no Today");
go("#sales/leads");
assert.ok(!S.hashFor({ ...S.read(), tab: "overview/summary" }).includes("range="), "a link from Leads to Overview carries no 7 days");
// A period picked inside Leads & sales is written, and stays while the reader does.
go("#sales/leads");
S.set({ range: "30d" });
assert.equal(qOf().get("range"), "30d", "a period picked is written to the address");
S.set({ tab: "sales/summary" });
assert.equal(S.read().range, "30d", "and stays from tab to tab inside the section");
S.set({ range: "today" });
assert.equal(qOf().get("range"), "today", "Today picked in Leads & sales is written (it is not this section's default)");
S.set({ tab: "sales/bookings" });
assert.equal(S.read().range, "today", "and stays");
S.set({ tab: "overview/summary" });
assert.equal(S.read().range, "today", "a period picked is carried to another section");
S.set({ range: "today" });
assert.ok(!qOf().has("range"), "Today picked on Overview is Overview's own default: no key");
S.set({ tab: "sales/leads" });
assert.equal(S.read().range, "7d", "so Live on Overview is not carried into Leads & sales (the owner's case)");
S.set({ tab: "overview/summary" });
S.set({ range: "7d" });
assert.equal(qOf().get("range"), "7d", "7 days picked on Overview is written there");
S.set({ tab: "sales/leads" });
assert.equal(S.read().range, "7d");
assert.equal(qOf().get("range"), "7d", "7 days named on Overview stays named in Leads & sales");
S.set({ tab: "ai/assistants" });
assert.equal(S.read().range, "7d", "and on into the next section");
go("#site/health?range=yesterday");
S.set({ tab: "sales/summary" });
S.set({ tab: "traffic/sources" });
assert.equal(S.read().range, "yesterday", "a named period passes through Leads & sales unchanged");
go("#overview/summary?range=90d");
S.set({ tab: "sales/sources" });
assert.equal(S.read().range, "90d", "a period the reader chose on Overview is carried, as before");
// Live mode on Leads & sales: Today, written; off again: back to the period before.
go("#sales/leads");
S.set({ range: "today", cmp: "" });
assert.equal(qOf().get("range"), "today");

// ---- 2. every new key round-trips through the address
for (const hash of ["#sales/leads?range=all", "#overview/summary?range=all", "#traffic/sources?range=all&country=CA",
  "#sales/leads?range=all&lact=signup&llabel=sales&lnow=won&lby=Search+engine&lshow=out&lview=board&country=US&source=Search+engine&device=Mobile&campaign=google+%2F+cpc+%2F+fall-launch",
  "#sales/leads?lview=timeline&lsplit=source&device=Desktop", "#sales/leads?range=today&lnow=out&lshow=out"]) {
  location.hash = hash;
  const back = S.hashFor(S.read());
  const a = new URLSearchParams(hash.split("?")[1]), b = new URLSearchParams(back.split("?")[1] || "");
  assert.deepEqual([...b].sort(), [...a].sort(), `${hash} comes back as ${back}`);
}
assert.ok(S.RANGES.some(([k, w]) => k === "all" && w === "All time"), "All time is a period of the shared control");

// ---- 3. All time: from the first day this site has data, from the same days as every range
const day = (d) => new Date(Date.UTC(2026, 8, 1) + d * 864e5).toISOString().slice(0, 10);   // day(0) = 2026-09-01
const byDay = new Map();
for (let i = 0; i <= 50; i += 1) byDay.set(day(i), { day: day(i), state: "ok" });                // 2026-09-01 .. 2026-10-21
const fin = (n) => ({ completed: n });
const cday = (d, stages = {}, by = {}) => ({ day: d, state: "ok", stages, by: { source_type: {}, country: {}, device: {}, campaign: {}, ...by } });
// Leads: 5 Sep (contact, Search engine, GB), 10 Oct (signup, Search engine, US, Mobile), 12 Oct (demo, Direct, CA, Desktop).
const LEADS = { [day(4)]: cday(day(4), { contact: fin(1) }, { source_type: { contact: { "Search engine": 1 } }, country: { contact: { GB: 1 } }, device: { contact: { Unknown: 1 } }, campaign: { contact: { Unknown: 1 } } }),
  "2026-10-10": cday("2026-10-10", { signup: fin(1) }, { source_type: { signup: { "Search engine": 1 } }, country: { signup: { US: 1 } }, device: { signup: { Mobile: 1 } }, campaign: { signup: { "google / cpc / fall-launch": 1 } } }),
  "2026-10-12": cday("2026-10-12", { demo: { completed: 1, won: 1 } }, { source_type: { demo: { "Direct or unknown": 1 } }, country: { demo: { CA: 1 } }, device: { demo: { Desktop: 1 } }, campaign: { demo: { "(no campaign tag)": 1 } } }) };
const cdays = [];
for (let i = 0; i <= 51; i += 1) cdays.push(LEADS[day(i)] || cday(day(i)));                   // to today, 2026-10-22
const f = { available: true, since: "2026-09-01", finished: ["completed", "paid"], lead_actions: ["contact", "signup", "demo"], demo_actions: ["demo"], min_rate: 10, days: cdays };
const m = { site: "example.com", today: "2026-10-22", anchor: "2026-10-21", firstDay: "2026-09-01", byDay, views: [], x: { conversions: f }, journeys: [] };
setContext(m, S.read());
{
  const r = rangeOf(m, { range: "all" });
  assert.equal(r.first, "2026-09-01");
  assert.equal(r.last, "2026-10-21", "to the last whole day, as every other preset");
  assert.equal(r.length, 51);
  assert.equal(r.days.length, 51);
  assert.ok(r.all && !r.cut);
  assert.equal(rangeWords(r), "All time: since Tue 1 Sep 2026, 51 days");
  setContext(m, { range: "all", view: "all" });
  assert.match(periodWords(r, { complete: true, ok: 51 }), /^All time: since Tue 1 Sep 2026, 51 days · every day whole and verified/);
  // The leads' first day earlier than history's: All time starts there.
  const r2 = allTime({ ...m, firstDay: "2026-09-10", x: { conversions: { ...f, since: "2026-09-01" } } });
  assert.equal(r2.first, "2026-09-01", "the earliest of history's first day and the leads' first day");
  // Data that begins before the days the page holds: said plainly, never summed as if all.
  const r3 = allTime({ ...m, firstDay: "2025-01-04" });
  assert.equal(r3.first, "2026-09-01", "starts at the first day the page holds");
  assert.equal(r3.cut, "2025-01-04");
  assert.equal(rangeWords(r3), "All time held here: the last 51 days, since Tue 1 Sep 2026 (this site's data begins Sat 4 Jan 2025; the dashboard holds 51 days)");
}

// ---- 4. the Leads tab: the empty state with real counts, the chips, the count line, each filter
const ROWS = [
  { id: 1, at: `${day(4)}T10:00:00-04:00`, action: "contact", now: "completed", tool: "site", source: "Search engine", country: "GB", device: null, campaign: null, left_out: null },
  { id: 2, at: "2026-10-10T09:00:00-04:00", action: "signup", now: "completed", tool: "site", source: "Search engine", country: "US", device: "Mobile", campaign: "google / cpc / fall-launch", left_out: null, label: "sales" },
  { id: 3, at: "2026-10-12T08:00:00-04:00", action: "demo", now: "won", tool: "calendly", source: "Direct or unknown", country: "CA", device: "Desktop", campaign: "(no campaign tag)", left_out: null },
  { id: 4, at: "2026-10-12T08:30:00-04:00", action: "contact", now: "spam", tool: "site", source: null, country: null, device: null, campaign: null, left_out: "spam" },
];
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true, names: false, why: "Names and emails show to admins and owners.", rows: ROWS }) });
ME.role = "viewer";
async function draw(hash) {
  location.hash = hash;
  const s = S.read();
  setContext(m, s);
  document.body.replaceChildren();
  const out = flat(L.default(m, s));
  document.body.append(...out);
  for (let i = 0; i < 10; i += 1) await tick();
  return document.body;
}
const lineOf = (el) => text(el.querySelector(".sa-figure"));
// The Leads figure, counted here on its own: completed and paid rows of the lead actions, over the days.
const figure = (first, last, keep = () => true) => cdays.filter((d) => d.day >= first && d.day <= last)
  .reduce((x, d) => x + Object.entries(d.stages).filter(([a]) => keep(a, d)).reduce((y, [, st]) => y + (st.completed || 0) + (st.paid || 0), 0), 0);
{
  // 7 days (15 to 21 Oct) hold no lead; the last 30 days (22 Sep to 21 Oct) hold two.
  const el = await draw("#sales/leads");
  const empty = el.querySelector(".sa-wider");
  assert.ok(empty, "the smart empty state");
  const n30 = figure("2026-09-22", "2026-10-21");
  assert.equal(n30, 2);
  assert.equal(leadsOn(m, rangeOf(m, { range: "30d" }).days.map((d) => d.day)).leads, n30, "the same figure as the 30-day period's");
  assert.equal(text(empty.querySelector("p")), `No new leads in the last 7 days. ${n30} leads in the last 30 days.`);
  const btns = empty.querySelectorAll("button");
  assert.deepEqual(btns.map(text), ["Show last 30 days", "All time"]);
  assert.match(lineOf(el), /^0 leads/, "the count line says 0, the figure");
  btns[0].click();
  assert.equal(qOf().get("range"), "30d", "the button shows the last 30 days");
  await draw("#sales/leads");
  el.querySelector(".sa-wider").querySelectorAll("button")[1].click();
  assert.equal(qOf().get("range"), "all", "and All time");
}
{
  // Today has none either: the owner's case.
  const el = await draw("#sales/leads?range=today");
  assert.equal(text(el.querySelector(".sa-wider p")), "No new leads in today so far. 2 leads in the last 30 days.");
}
{
  // The last 30 days hold none with this filter: all time does (one contact form, 5 Sep).
  const el = await draw("#sales/leads?lact=contact");
  const all = figure("2026-09-01", "2026-10-21", (a) => a === "contact");
  assert.equal(all, 1);
  assert.equal(text(el.querySelector(".sa-wider p")), `No new leads match these filters in the last 7 days. ${all} lead since Tue 1 Sep 2026.`);
  assert.deepEqual(el.querySelector(".sa-wider").querySelectorAll("button").map(text), ["All time"]);
}
{
  // None at all: "No leads yet" and the hint, as before.
  const none = { ...m, x: { conversions: { ...f, days: cdays.map((d) => cday(d.day)) } } };
  location.hash = "#sales/leads";
  const out = flat(L.default(none, S.read()));
  const t = out.map(text).join(" ");
  assert.match(t, /No leads yet: nothing has reported a lead for this site\./);
  assert.match(t, /Connect a source of leads/);
  // With a filter on and nothing anywhere: say so, and offer to clear.
  location.hash = "#sales/leads?lby=Email";
  const t2 = flat(L.default(m, S.read())).map(text).join(" ");
  assert.match(t2, /No lead matches these filters, in any period the dashboard holds\./);
}
{
  // All time: the period line, the figure, the list.
  const el = await draw("#sales/leads?range=all");
  assert.match(text(el.querySelector(".period")), /^All time: since Tue 1 Sep 2026, 51 days/);
  assert.match(lineOf(el), /^3 leads/, "all time's Leads figure");
  assert.equal(el.querySelector(".sk-grid").filtered().length, 3, "the list: every lead of all time, left out hidden");
  assert.ok(!el.querySelector(".sa-filtered"), "no filter on: no Filtered by line");
  const tools = el.querySelectorAll(".tt-btn").map(text);
  assert.ok(tools.length && !tools.some((t) => /Filter/.test(t)), `the table has no Filter button of its own on Leads (${tools.join(", ")})`);
}
{
  // One filter row: chips from the row and from the top bar's Filters, Clear all, the count line.
  const el = await draw("#sales/leads?range=all&lby=Search+engine&country=US");
  const chips = el.querySelector(".sa-filtered");
  assert.ok(chips, "one Filtered by line");
  const said = chips.querySelectorAll(".chip").map((c) => text(c).replace("×", "").trim());
  assert.equal(said[0], "Source = Search engine", "the row's Source");
  assert.match(said[1], /^Country = (\S+ )?United States$/, `the top bar's country, applied: ${said[1]}`);
  assert.ok(!chips.querySelector(".chip.off"), "both applied");
  assert.ok(chips.querySelectorAll(".chip")[1].className.includes("glob"), "the dashboard filter's chip is marked as such");
  // Two breakdowns at once: the figure cannot cross them, so the rows listed are counted, said as such.
  assert.match(lineOf(el), /^1 listed · filtered: Source = Search engine · Country = .*of 3 leads in the period \(the Leads figure, before these filters\)\. The Leads figure keeps each breakdown on its own/);
  chips.querySelector(".sa-clear").click();
  for (const k of ["lby", "country", "lact", "llabel", "lnow", "lshow", "source", "device", "campaign", "rules"]) assert.ok(!qOf().has(k), `Clear all takes ${k} away: ${location.hash}`);
  assert.equal(qOf().get("range"), "all", "and keeps the period");
}
{
  // One chip removed on its own.
  const el = await draw("#sales/leads?range=all&lby=Search+engine&lact=signup");
  const chip = el.querySelector(".sa-filtered").querySelectorAll(".chip").find((c) => /Source/.test(text(c)));
  chip.querySelector("button").click();
  assert.ok(!qOf().has("lby") && qOf().get("lact") === "signup", `only that filter goes: ${location.hash}`);
}
{
  // The count line names what is applied, with the figure narrowed the same way.
  const el = await draw("#sales/leads?range=all&lby=Search+engine");
  const n = figure("2026-09-01", "2026-10-21", (a, d) => d.by.source_type[a]?.["Search engine"]);
  assert.equal(n, 2);
  assert.match(lineOf(el), new RegExp(`^${n} leads · filtered: Source = Search engine`));
  const el2 = await draw("#sales/leads?range=all&country=CA");
  assert.match(lineOf(el2), /^1 lead · filtered: Country = /, "the dashboard's country narrows the figure: by.country");
  const el3 = await draw("#sales/leads?range=all&device=Mobile");
  assert.match(lineOf(el3), /^1 lead · filtered: Device = Mobile/);
  // A dashboard filter a lead does not carry: a greyed chip with the reason, never ignored silently.
  const el4 = await draw("#sales/leads?range=all&browser=Chrome");
  const off = el4.querySelector(".sa-filtered .chip.off");
  assert.ok(off, "greyed");
  assert.match(off.getAttribute("title"), /Not applied to leads/);
  assert.match(lineOf(el4), /^3 leads/, "and the figure is the whole of it");
}

// ---- 5. each filter against the rows (keepRows), the figure (figureFile) and the views
const R = rangeOf(m, { range: "all" });
const ids = (s) => L.keepRows(ROWS, s, R).map((x) => x.id);
assert.deepEqual(ids({}), [1, 2, 3], "every lead; left out hidden");
assert.deepEqual(ids({ lact: "signup" }), [2], "What");
assert.deepEqual(ids({ llabel: "sales" }), [2], "Label");
assert.deepEqual(ids({ lnow: "won" }), [3], "Stage now");
assert.deepEqual(ids({ lnow: "open" }), [1, 2]);
assert.deepEqual(ids({ lnow: "out" }), [4], "Stage now: Left out lists the left-out rows, even without lshow (was: nothing)");
assert.deepEqual(ids({ lby: "Search engine" }), [1, 2], "Source");
assert.deepEqual(ids({ lby: "Unknown", lshow: "out" }), [4], "Source: Not recorded");
assert.deepEqual(ids({ lshow: "out" }), [1, 2, 3, 4], "Show left out");
assert.deepEqual(ids({ country: "US" }), [2], "the dashboard's country");
assert.deepEqual(ids({ country: "ca" }), [3], "a country code in any case");
assert.deepEqual(ids({ source: "Direct or unknown" }), [3], "the dashboard's source");
assert.deepEqual(ids({ device: "Mobile" }), [2], "the dashboard's device; a device not recorded matches none");
assert.deepEqual(ids({ campaign: "google / cpc / fall-launch" }), [2], "the dashboard's campaign");
assert.deepEqual(ids({ country: "US", lby: "Direct or unknown" }), [], "filters together: all of them");
{
  const sum = (fig, first = "2026-09-01", last = "2026-10-21") => leadsOn({ x: { conversions: fig.f } }, cdays.filter((d) => d.day >= first && d.day <= last).map((d) => d.day)).leads;
  assert.equal(sum(F.figureFile(m, { lact: "signup" })), 1, "What narrows the figure");
  assert.equal(sum(F.figureFile(m, { lby: "Search engine" })), 2, "Source narrows the figure (was: the figure stayed whole while the list narrowed)");
  assert.equal(sum(F.figureFile(m, { lby: "Search engine", lact: "contact" })), 1, "What and Source together");
  assert.equal(sum(F.figureFile(m, { country: "GB" })), 1);
  assert.equal(sum(F.figureFile(m, { campaign: "(no campaign tag)" })), 1);
  assert.equal(sum(F.figureFile(m, { source: "Search engine", lby: "Search engine" })), 2, "the same source twice is one breakdown");
  assert.equal(F.figureFile(m, { lby: "Search engine", country: "US" }).f, null, "two breakdowns are never crossed");
  assert.equal(F.figureFile(m, { llabel: "sales", country: "US" }).f, null, "nor a label and a breakdown");
  // The figure and the rows agree, filter by filter.
  for (const s of [{}, { lact: "signup" }, { lby: "Search engine" }, { country: "CA" }, { device: "Mobile" }, { campaign: "google / cpc / fall-launch" }]) {
    assert.equal(sum(F.figureFile(m, s)), L.keepRows(ROWS, s, R).length, `figure and list agree for ${JSON.stringify(s)}`);
  }
  // The timeline draws the narrowed figure; by source with a country on, it says why not.
  const fig = F.figureFile(m, { country: "US" });
  const t = flat(timeline({ ...m, x: { conversions: fig.f } }, { lsplit: "source", country: "US" }, rangeOf(m, { range: "30d" }), fig)).map(text).join(" ");
  assert.match(t, /Leads per day by source cannot be shown with this filter on/);
  const t2 = flat(timeline({ ...m, x: { conversions: fig.f } }, { country: "US" }, rangeOf(m, { range: "30d" }), fig)).map(text).join(" ");
  assert.match(t2, /Leads per day/);
  // The map with a label: said, never an empty map.
  assert.match(text(map(m, { llabel: "sales" }, R)), /Leads by country are not split by label/);
}
{
  // The views keep working with the new period and filters.
  for (const v of ["board", "timeline", "map"]) {
    const el = await draw(`#sales/leads?range=all&lview=${v}&lby=Search+engine`);
    assert.ok(el.querySelector(".sa-view").childNodes.length, `${v} draws`);
    assert.match(lineOf(el), /^2 leads · filtered: Source = Search engine|^3 leads/, `${v}: the count line`);
  }
  const el = await draw("#sales/leads?range=all&lview=board&lnow=won");
  assert.match(text(el.querySelector(".bd")), /Demo/);
  const tl = await draw("#sales/leads?range=all&lview=timeline&lnow=won");
  assert.ok(tl.querySelector(".sa-filtered .chip.off"), "Stage now greyed on the timeline, with why");
}
{
  // Today so far, beside a period of whole days: the live Leads figure, never in the period's own.
  const { todayNote, tabHead } = await import(new URL("tabs/sa-options.js", JS));
  const R7 = rangeOf(m, { range: "7d" });
  assert.equal(todayNote(m, { tab: "sales/leads" }, R7), null, "no lead today: no line");
  const todays = cdays.map((d) => (d.day === "2026-10-22" ? cday(d.day, { signup: fin(2), demo: { completed: 1 }, contact: { started: 4 } }) : d));
  const mt = { ...m, x: { conversions: { ...f, days: todays } } };
  const live = leadsOn(mt, ["2026-10-22"]).leads;
  assert.equal(live, 3, "the live Leads figure: finished rows of the lead actions today");
  setContext(mt, { ...S.read(), tab: "sales/leads" });
  location.hash = "#sales/leads";
  document.body.replaceChildren();
  const out = flat(L.default(mt, S.read()));
  document.body.append(...out);
  const line = document.body.querySelector(".sa-today");
  assert.ok(line, "the line on Leads, 7 days");
  assert.equal(text(line).replace(/\s+/g, " ").trim(), `Today so far: ${live} new leads Show today (live) →`);
  assert.match(text(document.body.querySelector(".sa-figure")), /^0 leads/, "and not added to the period's figure (7 days, whole days only)");
  line.querySelector("button").click();
  assert.equal(qOf().get("range"), "today", "the button shows today, live");
  assert.equal(todayNote(mt, { tab: "sales/leads" }, rangeOf(mt, { range: "today" })), null, "no line on Today itself");
  assert.ok(todayNote(mt, { tab: "sales/leads" }, rangeOf(mt, { range: "all" })), "All time (whole days) has it too");
  // Every Leads & sales tab with a period draws it through tabHead; Find a person and Security do not.
  setContext(mt, { tab: "sales/summary" });
  assert.ok(flat(tabHead("Summary", "q", R7)).some((el) => (el.className || "").includes("sa-today")), "Summary");
  assert.ok(!flat(tabHead("Find a person", "q", R7, { period: "Everything kept" })).some((el) => (el.className || "").includes("sa-today")), "Find a person: no");
  setContext(mt, { tab: "threats/overview" });
  assert.ok(!flat(tabHead("Security", "q", R7)).some((el) => (el.className || "").includes("sa-today")), "Security: no");
  for (const [mod, tab] of [["tabs/funnels.js", "sales/funnels"], ["tabs/events.js", "sales/events"]]) {
    const draw2 = (await import(new URL(mod, JS))).default;
    setContext(mt, { ...S.read(), tab });
    const got = flat(draw2({ ...mt, x: { ...mt.x, events: null, funnels: null }, journeys: [] }, { ...go(`#${tab}`), tab }));
    assert.ok(got.some((el) => (el.className || "").includes("sa-today")), `${tab} has the line`);
  }
  setContext(m, S.read());
}
{
  // The top bar's chips: a single filter a tab applies is not greyed (2.23 fix: the lookup
  // compared a re-tidied copy by identity, so every such chip said "not on this tab").
  const { applies, filterChips } = await import(new URL("filterpanel.js", JS));
  const { fromState } = await import(new URL("rules.js", JS));
  const s = { ...go("#traffic/places?country=US&browser=Chrome"), tab: "traffic/places" };
  const tree = fromState(s);
  assert.equal(applies(s, tree.items[0], tree), true, "Places & devices applies the country filter");
  const s2 = { ...go("#traffic/sources?country=US&source=Search+engine") };
  const t2 = fromState(s2);
  assert.deepEqual(t2.items.map((x) => applies(s2, x, t2)), [false, true], "Sources applies the source filter, not the country");
  const chips = filterChips(m, s2);
  assert.equal(chips.querySelectorAll(".chip.off").length, 1, "one greyed chip, not two");
}
console.log("leads-period: all passed");
