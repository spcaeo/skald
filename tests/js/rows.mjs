// Every row about a value opens it (2.13, js/drill.js drillRow): the common table
// builders - table() and countTable() (js/table.js, js/tabs/common.js), the bar
// list blist() and the data grid (js/grid.js) - route their rows through one
// helper, so a new table gets the whole-row drill for free. The whole row is the
// target: a click anywhere on it, Enter or Space; buttons inside keep their own
// click; a row that opens something else (onRow: a visit) is left to it.
//
//   node tests/js/rows.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install, Ev } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { table } = await import(new URL("table.js", JS));
const { blist, countTable } = await import(new URL("tabs/common.js", JS));
const { drillRow, link, close } = await import(new URL("drill.js", JS));
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "traffic", name: "Traffic", tabs: [{ route: "traffic/sources", name: "Sources" }, { route: "traffic/pages", name: "Pages" }] }]);

const dd = () => new URLSearchParams(location.hash.split("?")[1] || "").get("dd");
const reset = () => { location.hash = "#traffic/sources"; history.state = null; };
const key = (el, k) => { const e = new Ev("keydown", { key: k }); e.target = el; el.dispatchEvent(e); return e; };

// ---- table(): a drill column makes every row open its value
{
  reset();
  const t = table([{ key: "source", label: "Source", drill: "source" }, { key: "n", label: "Visitors", num: true }],
    { caption: "Sources", rows: [{ source: "Search engine", n: 9 }, { source: "Email", n: 4 }, { source: "(none)", n: 2 }] });
  const rows = t.querySelectorAll("tbody tr");
  assert.equal(rows.length, 3);
  const drow = rows.filter((r) => r.classList.contains("drow"));
  assert.equal(drow.length, 2, "a folded or absent value has no detail, so its row is plain");
  assert.equal(drow[0].tabIndex, 0, "the row takes the focus");
  assert.equal(drow[0].querySelector("button.dl").tabIndex, -1, "one stop per row: the link inside leaves the tab order");
  drow[0].querySelector("td:not([class])")?.click?.();
  drow[0].children[1].click();                                   // the number's cell, not the name
  assert.equal(dd(), "source:Search engine", "a click anywhere on the row opens its value");
  assert.deepEqual(history.state, { drill: 1 }, "the step is counted in the history entry");
  reset();
  const e = key(drow[1], "Enter");
  assert.equal(dd(), "source:Email", "Enter on the row opens it");
  assert.ok(e.defaultPrevented);
  reset();
  key(drow[1], " ");
  assert.equal(dd(), "source:Email", "Space too");
  reset();
  drow[1].children[0].append(Object.assign(document.createElement("button"), { className: "x" }));
  drow[1].querySelector("button.x").click();
  assert.equal(dd(), null, "a button inside the row keeps its own click");
}

// ---- table() with fmt-drawn links (no drill key), and onRow, and rowDrill: false
{
  reset();
  const fmtLinked = table([{ key: "cc", label: "Country", fmt: (v) => link("country", v) }, { key: "n", label: "Visitors", num: true }],
    { caption: "Countries", rows: [{ cc: "CA", n: 3 }] });
  fmtLinked.querySelector("tbody tr").children[1].click();
  assert.equal(dd(), "country:CA", "a link a column draws itself is found too");
  reset();
  const opened = [];
  const visits = table([{ key: "path", label: "Page", drill: "path" }], { caption: "Visits", rows: [{ path: "/pricing/" }], onRow: (r) => opened.push(r.path) });
  const vr = visits.querySelector("tbody tr");
  assert.ok(!vr.classList.contains("drow"), "a row with its own onRow (a visit) is left to it");
  vr.click();
  assert.deepEqual(opened, ["/pricing/"]);
  key(vr, " ");
  assert.deepEqual(opened, ["/pricing/", "/pricing/"], "Space opens an onRow row too");
  const off = table([{ key: "path", label: "Page", drill: "path" }], { caption: "Off", rows: [{ path: "/a" }], rowDrill: false });
  assert.ok(!off.querySelector("tbody tr").classList.contains("drow"));
}

// ---- countTable() and blist()
{
  reset();
  const ct = countTable({ "/pricing/": 5, "/": 3 }, { caption: "Pages", drill: "path" });
  assert.equal(ct.querySelectorAll("tr.drow").length, 2);
  ct.querySelectorAll("tr.drow")[1].children[2].click();
  assert.equal(dd(), "path:/", "countTable rows open their value");
  reset();
  const bl = blist([["US", 7], ["CA", 2]], { drill: "country" });
  const lis = bl.querySelectorAll("li");
  assert.ok(lis.every((li) => li.classList.contains("drow")), "every bar-list line opens its value");
  lis[1].querySelector("span.bl-v").click();
  assert.equal(dd(), "country:CA");
  assert.equal(blist([["x", 1]]).querySelectorAll("li.drow").length, 0, "a list without a drill stays plain");
}

// ---- inside the drawer, a step narrows the trail and counts one more; close steps Back over them
{
  location.hash = "#traffic/sources?dd=source:Email"; history.state = { drill: 1 };
  const bl = blist([["US", 7]], { drill: "country", from: "drill" });
  bl.querySelector("li").children[2].click();
  assert.equal(dd(), "source:Email|country:US");
  assert.deepEqual(history.state, { drill: 2 });
  let went = 0;
  history.go = (k) => { went = k; };
  close();
  assert.equal(went, -2, "closing the drawer steps Back over both steps");
  history.state = null;
  close();
  assert.equal(dd(), null, "opened from a link (no steps counted): closing drops the trail");
}

// ---- one helper: every builder calls it (the grid draws its rows itself, in the browser)
{
  const src = (f) => readFileSync(new URL(f, JS), "utf8");
  for (const f of ["table.js", "grid.js", "tabs/common.js"]) assert.match(src(f), /drillRow\(/, `${f} routes its rows through drillRow`);
  assert.match(src("grid.js"), /else if \(opts\.rowDrill !== false\)/, "a grid without onRow gets the whole-row drill");
  const row = document.createElement("tr");
  assert.equal(drillRow(row), null, "a row with no value's link stays a plain row");
  assert.ok(!row.classList.contains("drow"));
}

// ---- the drill drawer (2.13): its visits are the period's, and a city links on like a country
{
  const { visitSpan, jumpsFor } = await import(new URL("drillview.js", JS));
  const m = { today: "2026-10-18", journey_days: 7, journeys: ["2026-10-12", "2026-10-17", "2026-10-18"].map((day) => ({ day })) };
  const today = visitSpan(m, { kind: "today" });
  assert.deepEqual(m.journeys.filter(today.has).map((j) => j.day), ["2026-10-18"], "Today: today's visits only");
  const yest = visitSpan(m, { kind: "history", first: "2026-10-17", last: "2026-10-17", length: 1 });
  assert.deepEqual(m.journeys.filter(yest.has).map((j) => j.day), ["2026-10-17"], "a past day: its visits only");
  assert.equal(yest.longer, false);
  const month = visitSpan(m, { kind: "history", first: "2026-09-18", last: "2026-10-17", length: 30 });
  assert.deepEqual(m.journeys.filter(month.has).map((j) => j.day), ["2026-10-12", "2026-10-17"], "a long period: as far back as visits are kept");
  assert.equal(month.longer, true, "and it says the period reaches past them");
  const city = jumpsFor("city", "Toronto, Ontario, CA", [["city", "Toronto, Ontario, CA"]], { visits: true }).map((j) => j.words);
  assert.ok(city.includes("Visitors tab, filtered to it") && city.some((w) => w.startsWith("Open in")), `a city links on: ${city}`);
  const go = jumpsFor("city", "Toronto, Ontario, CA", [["city", "Toronto, Ontario, CA"]]).find((j) => j.go?.tab === "traffic/visitors").go;
  assert.match(go.rules, /^all\(city:is:Toronto/, "by the advanced rules");
}

console.log("rows: all passed");
