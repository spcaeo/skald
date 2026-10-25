// "Did my change work?" (js/tabs/pagechange.js): the tracker on a page's view, drawn from
// page_changes.json; the marks from the helper (a mark made since the last update waits for
// it, one stopped is gone); the words for before, after, the change and the verdict; too
// early with the day the verdict comes; unequal coverage said; leads not recorded said;
// the hint from the sitemap's date; the address keys (pchg, pcm, pcd, pck); the Mark a
// change dialog's POST; Insights' list; and the copy rule (every path copy + open, the
// note copy).
//
//   node tests/js/pagechange.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } });
const posted = [];
let helper = null;
globalThis.fetch = async (path, opts = {}) => {
  if (opts.method === "POST") {
    const body = JSON.parse(opts.body);
    posted.push([path, body]);
    const id = "c0000ffff";
    helper.changes = [{ id, path: body.item.slice(5), day: body.day, kind: body.kind, note: body.note, at: "2026-10-25T10:00:00Z" }, ...helper.changes];
    return { ok: true, status: 200, json: async () => ({ ok: true, id, day: body.day, changes: helper.changes }) };
  }
  if (!helper) return { ok: false, status: 404, json: async () => ({ ok: false, error: "not found" }) };
  return { ok: true, status: 200, json: async () => structuredClone({ ok: true, ...helper }) };
};
const tick = (ms = 5) => new Promise((r) => setTimeout(r, ms));
const text = (el) => el.textContent;
const go = (hash) => { history.replaceState(null, "", hash); };

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const U = await import(new URL("urlactions.js", JS));
const { ME } = await import(new URL("access.js", JS));
const P = await import(new URL("tabs/pagechange.js", JS));
const M = await import(new URL("tabs/todo-marks.js", JS));
U.setSiteBase("example.com");

// ---- a page_changes.json as page_changes.py writes it
const side = (days, total, at_least = false) => ({ days, total, per_day: days ? Math.round((total / days) * 1e4) / 1e4 : null, at_least });
const ready = { id: "c1a2b3c4d", path: "/pricing/", day: "2026-10-04", kind: "title", note: "New title and FAQ", at: "2026-10-04T09:00:00Z", first_at: "2026-10-04T09:00:00Z",
  days_after: 20, status: "ready", verdict_on: "2026-10-19", complete: false,
  before: { first: "2026-09-14", last: "2026-10-03", days: 20, whole: 19 }, after: { first: "2026-10-05", last: "2026-10-24", days: 20, whole: 20 },
  // The chart (charts.js lines) needs a real SVG parser; the browser check covers it, so the
  // cards here carry no days.
  days: [], leads_why: "no conversions are recorded for this site",
  figures: [
    { key: "visits", better: "up", before: side(19, 50), after: side(20, 170), unequal: true, change: { per_day: 5.8684, pct: 223 }, verdict: "up" },
    { key: "leads", better: "up", before: { days: 0, total: null, per_day: null, at_least: false }, after: { days: 0, total: null, per_day: null, at_least: false }, unequal: false, change: null, verdict: "not_recorded" },
    { key: "search", better: "up", before: side(19, 19), after: side(20, 20), unequal: true, change: { per_day: 0, pct: 0 }, verdict: "no_clear_change" },
    { key: "ai", better: "up", before: side(19, 0), after: side(20, 0), unequal: true, change: { per_day: 0, pct: null }, verdict: "too_few" },
    { key: "reads", better: "up", before: side(19, 38), after: side(20, 40), unequal: true, change: { per_day: 0.0, pct: 0 }, verdict: "no_clear_change" },
    { key: "left", better: "down", before: { days: 19, visits: 50, one_page: 40, share: 0.8, at_least: false }, after: { days: 20, visits: 170, one_page: 34, share: 0.2, at_least: false }, unequal: true, change: { points: -60 }, verdict: "down" },
  ] };
const early = { ...ready, id: "c9e8d7c6b", path: "/blog/launch/", day: "2026-10-18", kind: "content", note: "", days_after: 6, status: "too_early", verdict_on: "2026-11-02",
  figures: ready.figures.map((f) => ({ ...f, verdict: "too_early" })) };
const file = { min_days: 14, max_days: 28, marks: true, changes: [ready, early], withheld: [{ id: "c00000001", path: "/pricing/", day: "2026-09-01", why: ["visits shown 4, history gives 3"] }] };
const m = { today: "2026-10-25", anchor: "2026-10-24", x: { page_changes: file,
  page_index: { pages: [{ path: "/pricing/", updated: "2026-10-21", updated_source: "sitemap" }, { path: "/blog/launch/", updated: "2026-10-18", updated_source: "sitemap" }] } } };

// ---- the keys: listed, kept on their own tab, the dialog's day and kind inside it
for (const k of ["pchg", "pcm", "pcd", "pck"]) assert.ok(K.KEYS.has(k), `${k} in routekeys.js`);
assert.equal(K.KEYS.get("pcm").kind, "overlay");
assert.ok(K.INSIDE.includes("pcd") && K.INSIDE.includes("pck") && K.OPENERS.includes("pcm") && !K.OPENERS.includes("pcd"));
for (const k of S.KNOWN()) assert.ok(K.KEYS.has(k), `${k} is listed`);
assert.equal(S.hashFor({ ...S.read(), tab: "traffic/pages", page: "/pricing/", pchg: ready.id }), "#traffic/pages?page=%2Fpricing%2F&pchg=c1a2b3c4d");
assert.equal(S.hashFor({ ...S.read(), tab: "traffic/visitors", pchg: ready.id }), "#traffic/visitors", "another tab starts without it");

// ---- words
const f = (k, c = ready) => c.figures.find((x) => x.key === k);
assert.equal(P.sideWords(f("visits"), "before"), "2.6");
assert.equal(P.sideDetail(f("visits"), "before"), "50 in 19 days");
assert.equal(P.sideWords(f("visits"), "after"), "8.5");
assert.equal(P.changeWords(f("visits")), "+223%");
assert.equal(P.changeWords(f("left")), "−60.0 points");
assert.equal(P.sideWords(f("left"), "before"), "80.0%");
assert.equal(P.sideWords(f("leads"), "before"), "not recorded", "never 0");
assert.equal(P.tone(f("visits")), "better");
assert.equal(P.tone(f("left")), "better", "fewer leaving at once is better");
assert.equal(P.tone({ ...f("visits"), verdict: "down" }), "worse");
assert.ok(P.statusWords({ ...early, min_days: 14 }).startsWith("Too early to tell: 6 of 14 whole days so far. The verdict comes on 2 Nov."));
assert.ok(P.statusWords(ready).startsWith("20 whole days after the change (5 Oct to 24 Oct) against the 20 before it (14 Sep to 3 Oct)"));
assert.ok(P.statusWords({ ...ready, pending: true }).startsWith("Marked. Skald counts it on the next data update"));
const notes = P.coverageNotes(ready);
assert.ok(notes[0].startsWith("Compared per day: visits that started here on 19 days before, 20 after"), notes[0]);
assert.ok(notes.some((x) => x === "Leads: not recorded (no conversions are recorded for this site)."));

// ---- without accounts: the file's changes, nothing to mark, and why
ME.mode = "basic";
go("#traffic/pages?page=%2Fpricing%2F");
let box = P.changeTracker(m, S.read());
document.body.replaceChildren(box);
await tick();
assert.equal(box.querySelectorAll("article.pc-card").length, 1, "this page's change only");
assert.ok(text(box).includes("Changed 4 Oct: New title"));
const tbl = box.querySelector(".pc-tbl");
assert.ok(text(tbl).includes("Visits that started here") && text(tbl).includes("+223%") && text(tbl).includes("Up"));
assert.ok(text(tbl).includes("Left at once") && text(tbl).includes("−60.0 points") && text(tbl).includes("Down"));
assert.ok(tbl.querySelector(".pc-better"), "a better figure is toned");
assert.ok(text(box).includes("The change on 1 Sep is left out: the second count disagreed."), "a withheld change is named");
const markBtn = box.querySelectorAll("button").find((b) => text(b) === "+ Mark a change");
assert.ok(markBtn.hasAttribute("disabled") && markBtn.title === M.WHY.basic, "says why");
assert.ok(text(box).includes(M.WHY.basic));
const note = box.querySelector(".pc-note");
assert.ok(note.querySelector("button.ua-copy") && !note.querySelector("a.ua-open"), "the note: copy alone");
// The sitemap's date with no change tracked on it: a hint to track it.
assert.ok(text(box).includes("Your sitemap says this page changed on Wed 21 Oct 2026."));
assert.deepEqual(P.suggestion(m, "/blog/launch/", [early]), null, "a day already tracked: no hint");
box.querySelectorAll("button").find((b) => text(b) === "Track that change?").click();
let q = new URLSearchParams(location.hash.split("?")[1]);
assert.deepEqual([q.get("pcm"), q.get("pcd"), q.get("pck"), q.get("page")], ["new", "2026-10-21", "content", "/pricing/"]);
assert.equal(history.state?.ov, "pcm", "the dialog's entry: Back closes it");

// Too early, on its own page.
go("#traffic/pages?page=%2Fblog%2Flaunch%2F");
box = P.changeTracker(m, S.read());
assert.ok(text(box).includes("Too early to tell: 6 of 14 whole days so far. The verdict comes on 2 Nov."));
assert.ok(box.querySelector(".v-too_early"));

// A change the address names that is not tracked here.
go("#traffic/pages?page=%2Fblog%2Flaunch%2F&pchg=c1a2b3c4d");
box = P.changeTracker(m, S.read());
assert.ok(text(box).includes("That change is not tracked now"));

// A page group: the whole site's.
box = P.changeTracker({ ...m, x: { page_changes: { whole_site_only: true } } }, S.read());
assert.ok(text(box).includes("Tracked changes are the whole site's"));

// ---- with accounts, an admin: the helper's marks win; a new mark waits for the update
ME.mode = "sessions";
helper = { marks: {}, changes: [{ id: ready.id, path: "/pricing/", day: "2026-10-04", kind: "content", note: "Edited since" }, { id: "c7777aaaa", path: "/pricing/", day: "2026-10-23", kind: "redirect", note: "" }],
  role: "admin", can_mark: true, mail: { ready: false, why: "" }, team: [] };
await M.loadMarks(true);
const list = P.changesOf(m, "/pricing/");
assert.deepEqual(list.map((c) => [c.id, !!c.pending]), [[ready.id, false], ["c7777aaaa", true]], "file figures for a known mark, pending for a new one");
assert.equal(list[0].kind, "content", "the mark's words are the helper's");
assert.ok(!P.merged(m).some((c) => c.id === early.id), "stopped since the update: gone");
go("#traffic/pages?page=%2Fpricing%2F");
box = P.changeTracker(m, S.read());
document.body.replaceChildren(box);
await tick();
assert.equal(box.querySelectorAll("article.pc-card").length, 2);
assert.ok(text(box).includes("Waiting for the next update"));
assert.ok(!box.querySelectorAll("button").find((b) => text(b) === "+ Mark a change").hasAttribute("disabled"));

// ---- the dialog: its day and kind in the address, the note never
const HTMLDialog = { open: false, showModal() { this.open = true; }, close() { this.open = false; } };
const realCreate = document.createElement;
document.createElement = (t) => { const el = realCreate(t); if (t === "dialog") Object.assign(el, HTMLDialog); return el; };
go("#traffic/pages?page=%2Fpricing%2F&pcm=new&pcd=2026-10-21&pck=title");
assert.equal(await P.openMarkKey("new", m, { ...S.read(), tab: "traffic/visitors" }), "Open a page in Traffic › Pages first, then mark its change.");
const d = await P.openMarkKey("new", m, S.read());
assert.ok(d && d.el, "opened");
const dateIn = d.el.querySelector('input[type="date"]');
assert.equal(dateIn.getAttribute("value"), "2026-10-21");
assert.equal(dateIn.getAttribute("max"), "2026-10-25", "no day after today");
dateIn.value = dateIn.getAttribute("value");   // a browser's input reads its value attribute; dom-lite's does not
assert.ok(d.el.querySelector(".r2-chip.on") && text(d.el.querySelector(".r2-chip.on")) === "New title");
assert.ok(d.el.querySelector(".td-field .ua-host a.ua-open").getAttribute("href") === "https://example.com/pricing/", "the page: copy + open");
d.el.querySelectorAll("button").find((b) => text(b) === "Redirect").click();
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("pck"), "redirect", "a pick replaces the entry's kind");
d.el.querySelector('input[type="text"]').value = "Old pricing page now redirects here";
d.el.querySelectorAll("button").find((b) => text(b) === "Save change").click();
await tick();
assert.deepEqual(posted.at(-1), ["settings/todos", { item: "page:/pricing/", state: "changed", day: "2026-10-21", kind: "redirect", note: "Old pricing page now redirects here" }]);
q = new URLSearchParams(location.hash.split("?")[1]);
assert.equal(q.get("pchg"), "c0000ffff", "the new change is open");
assert.ok(!q.get("pcm") && !q.get("pcd") && !q.get("pck") && !/redirects/.test(location.hash), "dialog keys gone; the note never in the address");
assert.equal(M.MARKS.changes[0].id, "c0000ffff");
document.createElement = realCreate;

// ---- Copy link: the change's own address
assert.ok(P.linkTo(ready).endsWith("#traffic/pages?page=%2Fpricing%2F&pchg=c1a2b3c4d"));

// ---- Insights' list: one row a change, the page with copy + open, the row opens it
go("#overview/insights");
const parts = P.trackedList(m, S.read());
const el = document.createElement("div");
el.append(...parts);
assert.ok(text(el).includes("Pages you changed: did it work?"));
const rows = el.querySelectorAll("tbody tr");
assert.equal(rows.length, 3);
assert.ok(el.querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/pricing/"));
assert.ok(text(el).includes("Up") && text(el).includes("Waiting for the next update"));
rows.find((r) => text(r).includes("4 Oct")).click();
q = new URLSearchParams(location.hash.split("?")[1]);
assert.equal(location.hash.split("?")[0], "#traffic/pages");
assert.deepEqual([q.get("page"), q.get("pchg")], ["/pricing/", ready.id]);

console.log("pagechange: all passed");
