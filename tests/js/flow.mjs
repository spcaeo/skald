// Visitor flow (skald/webapp/js/flow.js): it adds up, and it says the
// same as the tables beside it.
//
//   node tests/js/flow.mjs [path/to/app.json]
//
// Without a file: small hand-made journeys. With one (tests/test_demo.py passes
// the demo's): the flow of the range's kept journeys against "Where visits
// started" (by.landing), "Common next steps" (visit.steps, less the reloads),
// "Where visits ended" (visit.exits) and the sources (by.source), summed over the
// same verified days. Example data only: example.com paths, no addresses.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { flowOf, funnelFlowOf, check, ledger, keptFor, pagesOf, OTHER } from "../../skald/webapp/js/flow.js";

const j = (source, ...trail) => ({ source, via: "", trail: trail.map((p) => ({ path: p, page: true })) });

// ---- by hand
{
  const js = [j("Search engine", "/", "/pricing/", "/signup/"), j("Direct", "/"), j("Direct", "/", "/", "/pricing/"),
    j("Email", "/blog/a", "/pricing/", "/", "/features/", "/signup/", "/x/")];
  assert.deepEqual(pagesOf(js[2]), ["/", "/pricing/"], "a reload is one step");
  const f = flowOf(js, { depth: 4, top: 7 });
  assert.deepEqual(check(f), []);
  assert.equal(f.total, 4);
  const node = (col, key) => f.columns.flatMap((c) => c.nodes).find((nd) => nd.col === col && nd.key === key);
  assert.equal(node(1, "/").value, 3);
  assert.equal(node(2, "left1").value, 1, "a one-page visit leaves after 1 page");
  assert.equal(node(5, "more").value, 1, "a visit longer than the columns goes on");
  assert.equal(node(4, "left3").value, 1);
  assert.deepEqual(node(1, "/blog/a").drill, ["landing", "/blog/a"]);
  assert.deepEqual(node(2, "/pricing/").drill, ["path", "/pricing/"]);
  // Folding keeps every column whole.
  const tight = flowOf(js, { depth: 4, top: 1 });   // as dimensions.fold: top - 1 kept, the rest one row
  assert.deepEqual(check(tight), []);
  assert.equal(tight.columns[1].nodes.find((nd) => nd.key === OTHER).value, 4);
  const l = ledger(js);
  assert.deepEqual(l.landing, { "/": 3, "/blog/a": 1 });
  assert.deepEqual(l.exits, { "/signup/": 1, "/": 1, "/pricing/": 1, "/x/": 1 });
  assert.equal(l.moves["/ → /pricing/"], 2);
  assert.equal(l.moves["/ → /"], undefined);
  // By who sent them: the assistant or site, else the source type.
  const v = flowOf([{ ...j("AI assistant", "/"), via: "ChatGPT" }, { ...j("Other website", "/"), via: "example.org" }, j("Direct", "/")], { start: "via" });
  assert.deepEqual(v.columns[0].nodes.map((nd) => nd.drill).sort(), [["assistant", "ChatGPT"], ["referrer", "example.org"], ["source", "Direct"]].sort());
  // A funnel: the steps reached, and those that left between them.
  const ff = funnelFlowOf([{ j: js[0], r: 3 }, { j: js[1], r: 1 }, { j: js[2], r: 2 }, { j: js[3], r: 0 }], ["Any", "/pricing/", "/signup/"]);
  assert.deepEqual(check(ff), []);
  assert.equal(ff.total, 3, "a visit that never met step 1 is not in the funnel");
  assert.deepEqual(ff.columns.slice(1).map((c) => c.nodes.map((nd) => [nd.label, nd.value])),
    [[["Any", 3]], [["/pricing/", 2], ["Left after step 1", 1]], [["/signup/", 1], ["Left after step 2", 1]]]);
}

// ---- against the tables, on a built page's app.json
const file = process.argv[2];
if (file) {
  const m = JSON.parse(readFileSync(file, "utf8"));
  m.byDay = new Map(m.days.map((d) => [d.day, d]));
  const ok = m.days.filter((d) => d.state === "ok");
  assert.ok(ok.length, "the page has verified days");
  const r = { kind: "history", first: ok[0].day, last: ok[ok.length - 1].day, days: m.days.filter((d) => d.day >= ok[0].day && d.day <= ok[ok.length - 1].day) };
  const kept = keptFor(m, r);
  assert.ok(kept.days.length && kept.journeys.length, "some days have their journeys kept");
  const days = kept.days.map((d) => m.byDay.get(d));
  const sum = (get) => { const o = {}; for (const d of days) for (const [k, v] of Object.entries(get(d) || {})) o[k] = (o[k] || 0) + v; return o; };
  const total = (o) => Object.values(o).reduce((a, b) => a + b, 0);
  const sansFold = (o) => Object.fromEntries(Object.entries(o).filter(([k]) => k !== "(all others)"));
  const landing = sum((d) => d.by?.landing), source = sum((d) => d.by?.source);
  const exits = sum((d) => d.visit?.exits);
  const steps = Object.fromEntries(Object.entries(sum((d) => d.visit?.steps)).filter(([k]) => { const [a, b] = k.split(" → "); return a !== b; }));
  const l = ledger(kept.journeys);
  assert.equal(l.visits, days.reduce((a, d) => a + d.readers, 0), "the flow's visits are the visitors of its days");
  assert.equal(l.visits, total(landing), "Where visits started adds up to the same visits");
  assert.equal(total(l.exits), total(exits), "Where visits ended adds up to the same visits");
  // A label the tables kept whole is the same in both; a busy day may fold its tail, so totals then.
  const folded = (o) => "(all others)" in o;
  if (!folded(landing)) assert.deepEqual(l.landing, landing, "first page column = Where visits started");
  if (!folded(source)) assert.deepEqual(l.starts, source, "source column = visits by source");
  if (!folded(exits)) assert.deepEqual(l.exits, exits, "pages before each Left = Where visits ended");
  if (!folded(steps)) assert.deepEqual(l.moves, steps, "moves = Common next steps, less reloads");
  else for (const [k, v] of Object.entries(sansFold(steps))) assert.ok((l.moves[k] || 0) >= v, `${k}`);
  for (const start of ["source", "via"]) for (const depth of [3, 4, 5]) {
    const f = flowOf(kept.journeys, { depth, top: 7, start });
    assert.deepEqual(check(f), [], `the drawn flow adds up (${start}, ${depth} pages)`);
    assert.equal(f.columns[1].nodes.reduce((a, nd) => a + nd.value, 0), l.visits);
  }
  // Narrowed to one country, as the drill drawer does: it still adds up, and its first column is its landings.
  const top = Object.entries(sum((d) => d.by?.country)).sort((a, b) => b[1] - a[1])[0][0];
  const one = kept.journeys.filter((x) => x.country === top);
  const f = flowOf(one);
  assert.deepEqual(check(f), []);
  assert.equal(f.total, one.length);
  console.log(`flow: ${l.visits} visits on ${kept.days.length} days reconcile with the tables; ${top}: ${one.length}`);
}
console.log("flow: all passed");
