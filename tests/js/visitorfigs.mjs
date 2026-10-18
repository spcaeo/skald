// Traffic > Visitors' two cards (js/visitorfigs.js): new and returning visits, and
// how engaged visits were. Every figure adds up to the days' readers or is withheld;
// a day without the figure is left out and named, never read as zero.
//
//   node tests/js/visitorfigs.mjs [app.json overview.json]
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { newReturning, engagement, median, narrowed, narrowedLists, foldedMatch, OTHER, ARROW, bucket, PAGE_BINS, SEC_BINS } = await import(new URL("visitorfigs.js", JS));

const day = (d, readers, ret, visit, state = "ok") => ({ day: d, state, readers, returning: ret, visit });

// New and returning: per day and in all, new = readers - returning.
const a = newReturning([
  day("2026-10-10", 80, { readers: 80, returning: 20 }),
  day("2026-10-11", 50, { readers: 50, returning: 5 }),
  day("2026-10-12", 0, null, null, "missing"),
]);
assert.equal(a.state, "ok");
assert.deepEqual([a.visits, a.fresh, a.returning], [130, 105, 25]);
assert.deepEqual(a.days.map((x) => [x.day, x.fresh, x.returning]), [["2026-10-10", 60, 20], ["2026-10-11", 45, 5]]);
assert.deepEqual(a.left, []);

// A verified day counted before returning visitors were: left out and named, not zero.
const b = newReturning([day("2026-10-10", 80, { readers: 80, returning: 20 }), day("2026-10-09", 40, null)]);
assert.equal(b.state, "ok");
assert.equal(b.visits, 80);
assert.deepEqual(b.left, ["2026-10-09"]);

// A day whose returning blob does not cover its readers: the whole figure is withheld.
const c = newReturning([day("2026-10-10", 80, { readers: 79, returning: 20 }), day("2026-10-11", 50, { readers: 50, returning: 5 })]);
assert.equal(c.state, "withheld");
assert.deepEqual(c.off, [{ day: "2026-10-10", readers: 80, counted: 79, returning: 20 }]);
assert.equal(newReturning([day("2026-10-10", 5, { readers: 5, returning: 6 })]).state, "withheld");

// Nothing recorded: none (days exist) or empty (no verified day); never a zero.
assert.equal(newReturning([day("2026-10-10", 80, null)]).state, "none");
assert.equal(newReturning([]).state, "empty");

// Engagement: both histograms add up to the readers, every value in one bin.
const v1 = { pages: { 1: 6, 2: 3, 7: 1 }, seconds: { 0: 5, 45: 3, 700: 2 } };
const e = engagement([day("2026-10-10", 10, null, v1)]);
assert.equal(e.state, "ok");
assert.deepEqual(e.pages.map((x) => x.value), [6, 3, 0, 0, 1]);
assert.deepEqual(e.seconds.map((x) => x.value), [5, 0, 3, 0, 0, 2]);
assert.equal(e.pages.length, PAGE_BINS.length);
assert.equal(e.seconds.length, SEC_BINS.length);
assert.deepEqual([e.medianPages, e.medianSeconds, e.onePage], [1, 0, 6]);
// A histogram that does not add up to the readers: withheld.
assert.equal(engagement([day("2026-10-10", 11, null, v1)]).state, "withheld");
// A page count outside every bin (0) cannot be drawn: withheld, not dropped.
assert.equal(engagement([day("2026-10-10", 11, null, { pages: { ...v1.pages, 0: 1 }, seconds: { ...v1.seconds, 3: 1 } })]).state, "withheld");
assert.deepEqual(engagement([day("2026-10-10", 10, null, null)]).left, ["2026-10-10"]);
assert.equal(median({ 1: 1, 2: 1 }), 1);
assert.equal(median({}), null);

// Narrowed by the filters (2.13): the days rebuilt from the kept visits, only when every
// day's kept visits are exactly its figures; seconds bucketed as visits.py does.
assert.deepEqual([0, 59, 61, 599, 600, 659, 3599, 3600, 4199].map(bucket), [0, 59, 60, 590, 600, 600, 3540, 3600, 3600]);
const J = (d, country, ret, pages, seconds) => ({ day: d, country, returning: ret, pages, seconds });
const js = [J("2026-10-10", "CA", true, 1, 5), J("2026-10-10", "US", false, 2, 75), J("2026-10-10", "CA", false, 1, 0),
  J("2026-10-11", "US", false, 3, 610)];
const dd = [day("2026-10-10", 3, { readers: 3, returning: 1 }, { pages: { 1: 2, 2: 1 }, seconds: { 0: 1, 5: 1, 70: 1 } }),
  day("2026-10-11", 1, { readers: 1, returning: 0 }, { pages: { 3: 1 }, seconds: { 600: 1 } })];
const ca = narrowed(dd, js, (j) => j.country === "CA");
assert.equal(ca.state, "ok");
assert.deepEqual([ca.whole, ca.kept], [4, 2]);
assert.deepEqual(ca.days.map((x) => [x.day, x.readers, x.returning.returning]), [["2026-10-10", 2, 1], ["2026-10-11", 0, 0]]);
const caNr = newReturning(ca.days);
assert.deepEqual([caNr.visits, caNr.fresh, caNr.returning], [2, 1, 1]);
assert.equal(engagement(ca.days).state, "ok");
assert.deepEqual(engagement(ca.days).pages.map((x) => x.value), [2, 0, 0, 0, 0]);
// Keeping everything gives back the days' own figures.
const everyone = narrowed(dd, js, () => true);
assert.deepEqual(newReturning(everyone.days), newReturning(dd));
assert.deepEqual(engagement(everyone.days), engagement(dd));
// A day with no kept visits (older than the keeping), or kept visits that are not its figures: unchecked.
assert.deepEqual(narrowed([...dd, day("2026-10-01", 9, null, null)], js, () => true).off, [{ day: "2026-10-01", why: "none" }]);
assert.equal(narrowed(dd, js.slice(1), () => true).off[0].why, "count");
assert.equal(narrowed(dd, js.map((j, i) => (i === 1 ? { ...j, returning: true } : j)), () => true).off[0].why, "returning");
assert.equal(narrowed(dd, js.map((j, i) => (i === 1 ? { ...j, seconds: 95 } : j)), () => true).off[0].why, "lengths");
assert.equal(narrowed([], js, () => true).state, "empty");

// Where visits ended and Common next steps, narrowed (2.13): from the kept visits' exits and
// trails, only when each day's kept visits give back its stored (folded) lists.
const T = (day, country, trail) => ({ day, country, exit: trail[trail.length - 1], trail: trail.map((path) => ({ path })) });
const tj = [T("2026-10-10", "CA", ["/", "/pricing/"]), T("2026-10-10", "US", ["/pricing/"]), T("2026-10-10", "CA", ["/blog/"])];
const lday = [day("2026-10-10", 3, null, { exits: { "/pricing/": 2, [OTHER]: 1 }, steps: { ["/" + ARROW + "/pricing/"]: 1 } })];
const lca = narrowedLists(lday, tj, (j) => j.country === "CA");
assert.equal(lca.state, "ok");
assert.deepEqual(lca.exits, { "/pricing/": 1, "/blog/": 1 });
assert.deepEqual(lca.steps, { ["/" + ARROW + "/pricing/"]: 1 });
assert.deepEqual([lca.kept, lca.whole], [2, 3]);
assert.equal(foldedMatch({ a: 2, b: 1, c: 1 }, { a: 2, [OTHER]: 2 }), true, "the folded rest is a sum");
assert.equal(foldedMatch({ a: 2, b: 1 }, { a: 2, [OTHER]: 2 }), false);
assert.equal(narrowedLists(lday, tj.slice(1), () => true).off[0].why, "count");
assert.equal(narrowedLists([day("2026-10-10", 3, null, { exits: { "/pricing/": 3 }, steps: {} })], tj, () => true).off[0].why, "lists");

// On a real build (the demo): every verified day of the files reconciles.
const [appFile, overviewFile] = process.argv.slice(2);
if (appFile) {
  const app = JSON.parse(readFileSync(appFile, "utf8"));
  const ov = overviewFile ? JSON.parse(readFileSync(overviewFile, "utf8")) : { days: [] };
  const ret = new Map(ov.days.map((d) => [d.day, d.returning]));
  const days = app.days.map((d) => ({ ...d, returning: ret.get(d.day) || null }));
  const nr = newReturning(days);
  assert.equal(nr.state, "ok", `new and returning on the build: ${JSON.stringify(nr.off || nr.state)}`);
  const en = engagement(days);
  assert.equal(en.state, "ok", "engagement on the build adds up");
  // The kept visits are exactly their days' figures, so the filtered cards can be drawn.
  const kept = new Set((app.journeys || []).map((j) => j.day));
  const inKept = days.filter((d) => kept.has(d.day) && d.state === "ok");
  assert.ok(inKept.length, "the build keeps visits for some verified days");
  const all = narrowed(inKept, app.journeys, () => true);
  assert.equal(all.state, "ok", `kept visits against their days: ${JSON.stringify(all.off)}`);
  assert.deepEqual(newReturning(all.days), newReturning(inKept));
  assert.deepEqual(engagement(all.days), engagement(inKept));
  const lists = narrowedLists(inKept, app.journeys, () => true);
  assert.equal(lists.state, "ok", `kept visits against their days' exits and steps: ${JSON.stringify(lists.off)}`);
  const live = app.live?.figures;
  if (live?.returning) assert.equal(newReturning([{ day: app.today, state: "ok", ...live }]).state, "ok", "today's live figures add up");
}
console.log("visitorfigs: all passed");
