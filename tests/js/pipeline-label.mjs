// A lead's label (2.18) on the page: the small tag (leadfigs.js labelTag) in the lists
// that show conversions, and Pipeline's Label option in the Tools view (sa-pipeline.js):
// its choices from the file's checked days, Every action narrowed to that label's own
// rows (the file's `labels`, counted again by the second count), the parts not split by
// label left off with a note, and the label kept in the address. dom-lite throws on a
// null child, so a row without a label must append nothing.
//
//   node tests/js/pipeline-label.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { labelTag, actionWithLabel } = await import(new URL("tabs/leadfigs.js", JS));
const { convRow } = await import(new URL("tabs/sa-lists.js", JS));
const P = await import(new URL("tabs/sa-pipeline.js", JS));
const pipeline = P.default;
const text = (el) => (el == null ? "" : typeof el === "string" ? el : el.textContent);

// ---- the tag
assert.equal(labelTag(null), null);
assert.equal(labelTag(""), null);
{
  const t = labelTag("sales");
  assert.equal(t.className, "lbl-tag");
  assert.equal(t.textContent, "sales");
  assert.equal(t.getAttribute("title"), "Label: sales");
  assert.equal(actionWithLabel("contact", null).childNodes.length, 1, "no label: nothing appended");
  const both = actionWithLabel("contact", "support");
  assert.equal(both.childNodes.length, 2);
  assert.equal(both.textContent, "Contact formssupport");
}

// ---- a list row keeps its label, a removed row its kept row's
assert.equal(convRow("test", { action: "contact", label: "sales" }).label, "sales");
assert.equal(convRow("cancelled", { action: "demo" }).label, null);
assert.equal(convRow("removed", { external_ref: "L-1", row: { action: "contact", label: "partnership" } }).label, "partnership");

// ---- the file: two checked days, one withheld
const day = (d, stages, labels, gone = {}, labelsGone = {}) => ({ day: d, state: "ok", stages, abandoned: gone, labels, labels_abandoned: labelsGone,
  by: { source_type: { contact: { Search: 3 } } }, visits_before: { contact: { 0: 3 } }, time_to_convert: { contact: { unknown: 3 } }, assisted: null, likely_ai: {} });
const f = {
  available: true, finished: ["completed", "paid"], min_rate: 10, abandon_hours: 24, dims: ["source_type"], since: "2026-10-01",
  period: { first: "2026-10-01", last: "2026-10-20" }, timeline: [], pages_before: null,
  days: [
    day("2026-10-19", { contact: { completed: 3, started: 2 }, demo: { completed: 1 } },
      { contact: { sales: { completed: 2, started: 1 }, support: { completed: 1 } } }, { contact: 1 }, { contact: { sales: 1 } }),
    day("2026-10-20", { contact: { completed: 2 } }, { contact: { sales: { completed: 1 } }, demo: { partnership: { completed: 1 } } }),
    { day: "2026-10-18", state: "withheld", why: "the second count disagrees" },
  ],
};

assert.deepEqual(P.convLabels(f), [["sales", "sales"], ["partnership", "partnership"], ["support", "support"]], "most rows first, then by name");
assert.deepEqual(P.convLabels(f, "demo"), [["partnership", "partnership"]], "the chosen action's labels only");
assert.deepEqual(P.convLabels({ days: [] }), []);

{
  const g = P.narrowConv(f, { llabel: "sales" });
  assert.deepEqual(g.days[0].stages, { contact: { completed: 2, started: 1 } });
  assert.deepEqual(g.days[0].abandoned, { contact: 1 });
  assert.deepEqual(g.days[1].stages, { contact: { completed: 1 } }, "an action without the label is left out");
  assert.deepEqual(g.days[0].by, { source_type: {} }, "not split by label: emptied, never another label's figure");
  assert.equal(g.days[2].state, "withheld", "a withheld day stays withheld");
  const both = P.narrowConv(f, { lact: "demo", llabel: "partnership" });
  assert.deepEqual(both.days[1].stages, { demo: { completed: 1 } });
  assert.deepEqual(both.days[0].stages, {});
  assert.equal(P.narrowConv(f, {}), f, "nothing chosen: the file itself");
}

// ---- the tab, counting from the tools, narrowed to one label
const m = { today: "2026-10-20", anchor: "2026-10-20", byDay: new Map(), x: { conversions: f, events: null }, options: {}, days: [] };
const s = { tab: "sales/pipeline", lsrc: "all", llabel: "sales", lact: "", lshow: "", range: "custom", from: "2026-10-19", to: "2026-10-20" };
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const find = (nodes, pred) => { for (const el of nodes) { const got = walk(el, pred); if (got) return got; } return null; };
function walk(el, pred) {
  if (!el || typeof el !== "object") return null;
  if (pred(el)) return el;
  for (const k of el.childNodes || []) { const got = walk(k, pred); if (got) return got; }
  return null;
}
{
  const out = flat(pipeline(m, s, {}));
  const label = find(out, (el) => el.tagName === "SELECT" && el.parentNode && text(el.parentNode).startsWith("Label"))
    || find(out, (el) => (el.tagName || "").toLowerCase() === "select" && text(el.parentNode).startsWith("Label"));
  assert.ok(label, "a Label option in the Tools view");
  assert.ok(!label.hasAttribute("disabled"), "labels to choose: not greyed");
  const words = out.map(text).join(" ");
  assert.match(words, /Label “sales”: Every action counts only the leads/);
  assert.match(words, /not split by label/);
  const h2 = (t) => find(out, (el) => (el.tagName || "").toLowerCase() === "h2" && text(el).startsWith(t));
  assert.ok(h2("Every action"), "Every action is shown");
  const every = text(h2("Every action").parentNode);
  assert.match(every, /Contact forms/);
  assert.doesNotMatch(every, /Demos/, "demo has no row labelled sales");
  assert.equal(h2("Where the completed ones came from"), null, "a part not split by label is left off");
  assert.equal(h2("Time to convert"), null);
  assert.doesNotMatch(words, /Leads: \d/, "Overview's total is not a label's figure: left out");
}
{
  // The lead database's view: Label greyed, with the reason.
  const db = { ...m, x: { ...m.x, leads: { available: true, types: ["contact"], days: [] } } };
  const out = flat(pipeline(db, { ...s, lsrc: "db" }, {}));
  const opt = find(out, (el) => (el.className || "").includes("sa-opt") && text(el).startsWith("Label"));
  assert.ok(opt && opt.className.includes("off"), "greyed in the lead database's view");
  assert.match(text(opt), /keeps no label/);
}
console.log("pipeline-label: all passed");
