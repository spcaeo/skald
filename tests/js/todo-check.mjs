// Insights' "Check again" (2.44, js/tabs/todo-check.js, todos.js, todo-marks.js, todo-fix.js):
// the button on each to-do (owners and admins; a viewer sees the answer, not the button),
// the answer in place with its pill and words, the addresses still failing behind
// tdchk=<id> (in the address, Back closes it), "Check the next 50", a fixed to-do moved to
// Done as Fixed with no Undo, a refusal said in place, "Check all again" with its progress,
// the check after an AI agent's report beside the report, and the demo's sample answer.
//
//   node tests/js/todo-check.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });
const posted = [];
let helper = null;                 // GET settings/todos
let answers = [];                  // what POST settings/todo-check answers, in turn
globalThis.fetch = async (path, opts = {}) => {
  if (opts.method === "POST") {
    const body = JSON.parse(opts.body);
    posted.push([path, body]);
    const next = answers.shift() || { status: 200, body: { ok: true } };
    return { ok: next.status === 200, status: next.status, json: async () => structuredClone(next.body) };
  }
  if (String(path).startsWith("data/demo/")) return { ok: true, status: 200, json: async () => structuredClone(SAMPLE) };
  return { ok: true, status: 200, json: async () => structuredClone({ ok: true, ...helper }) };
};
const tick = (ms = 5) => new Promise((r) => setTimeout(r, ms));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const U = await import(new URL("urlactions.js", JS));
const { ME } = await import(new URL("access.js", JS));
const { DEMO } = await import(new URL("demo.js", JS));
const T = await import(new URL("tabs/todos.js", JS));
const M = await import(new URL("tabs/todo-marks.js", JS));
const C = await import(new URL("tabs/todo-check.js", JS));
const R = await import(new URL("tabs/todo-report.js", JS));
U.setSiteBase("example.com");
const text = (el) => el.textContent;
const go = (hash) => { history.replaceState(null, "", hash); };
const q = () => new URLSearchParams(location.hash.split("?")[1] || "");

const cols = (...c) => c.map(([key, label, kind]) => ({ key, label, ...(kind === "path" ? { path: true } : kind ? {} : { num: true }) }));
const lostTodo = { id: "lost-pages", kind: "lost", subject: null, tag: "Lost traffic", tone: "bad", title: "Send old pages somewhere useful",
  proof: "12 old page addresses answered 'not found'.", todo: "Redirect each.", check: "the not-found answers to the same addresses", figures: { paths: 12 },
  qualifies: true, columns: cols(["path", "Old address", "path"], ["people", "People"]), rows: [{ path: "/old-0/", people: 9 }], rows_total: 12,
  file: "old-pages.csv", open: { tab: "site/notfound", name: "Site > Not found" }, state: "open", marked: null, recheck: null, agent: true,
  window: { first: "2026-10-01", last: "2026-10-26", days: 26 } };
const errTodo = { ...lostTodo, id: "server-errors", kind: "errors", title: "Fix the server errors", tag: "Broken" };
const leaveTodo = { ...lostTodo, id: "leave-0a1b2c3d", kind: "leave", subject: "/landing/", title: "Make /landing/ lead somewhere", tag: "Leaving" };
const m = { x: { todos: { window: { first: "2026-10-01", last: "2026-10-26", days: 26 }, marks: true, todos: [lostTodo, errTodo, leaveTodo], withheld: [] } } };
const partly = { item: "lost-pages", at: "2026-10-27T14:32:00Z", mode: "live", verdict: "partly", words: "3 of 12 addresses still answer 404.",
  checked: 12, ok: 9, total: 12, next: null, bad: [{ path: "/old-9/", status: 404, ok: false, why: "still answers 404" },
    { path: "/old-10/", status: 301, location: "/nowhere/", ok: false, why: "answers 301 to a page that answers 404" },
    { path: "/old-11/", status: 404, ok: false, why: "still answers 404" }], bad_total: 3, by: "admin@example.com", by_who: "person" };
const SAMPLE = { ok: true, demo: true, check: { ...partly, by: "owner@example.com" } };

// ---- the key is listed and kept on Insights only
assert.ok(K.KEYS.has("tdchk") && K.KEYS.get("tdchk").kind === "tab");
assert.equal(S.hashFor({ ...S.read(), tab: "overview/insights", tdchk: "lost-pages" }), "#overview/insights?tdchk=lost-pages");
assert.equal(S.hashFor({ ...S.read(), tab: "traffic/pages", tdchk: "lost-pages" }), "#traffic/pages", "another tab starts without it");

// ---- an admin: the button on every to-do, beside Fix this
ME.mode = "sessions";
helper = { marks: {}, role: "admin", can_mark: true, mail: { ready: false, why: "x" }, team: [], checks: {}, checks_withheld: {} };
await M.loadMarks(true);
go("#overview/insights");
let box = T.todoSection(m, S.read());
const card = (b, id) => b.querySelectorAll("article.td").find((a) => a.id === `td-${id}`);
const words = (el) => el.querySelectorAll(".td-acts button").map(text);
assert.deepEqual(words(card(box, "lost-pages")), ["Fix this", "Check again", "Show the list (12)", "Mark done", "Not now"]);
assert.ok(words(card(box, "leave-0a1b2c3d")).includes("Check again"), "every to-do has it, a visits one too");
assert.equal(box.querySelectorAll(".ui-primary, .btn.primary").filter((b) => text(b) === "Check again").length, 0, "never the main button");
// Check all again: the kinds Skald can ask, never a visits to-do.
const all = box.querySelector(".td-chkall button");
assert.equal(text(all), "Check all again (2)");

// ---- pressed: POST, the answer in place, opened in the address
answers = [{ status: 200, body: { ok: true, check: partly, marks: {}, checks_withheld: {} } }];
card(box, "lost-pages").querySelectorAll("button").find((b) => text(b) === "Check again").click();
await tick();
assert.deepEqual(posted.at(-1), ["settings/todo-check", { item: "lost-pages", start: 0 }]);
assert.equal(q().get("tdchk"), "lost-pages", "the open answer is in the address");
box = T.todoSection(m, S.read());
let c = card(box, "lost-pages");
assert.ok(c.querySelector(".td-chk-box .ui-pill.warn") && text(c).includes("Partly fixed") && text(c).includes("3 of 12 addresses still answer 404."));
assert.ok(text(c).includes("by admin@example.com"));
const rows = c.querySelectorAll(".td-chk-tbl tbody tr");
assert.equal(rows.length, 3, "the addresses still failing");
assert.ok(rows[0].querySelector("a.ua-open").getAttribute("href") === "https://example.com/old-9/", "copy and open on each address");
assert.ok(rows[1].querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/nowhere/"), "where it redirects: open too");
assert.ok(rows[0].querySelector("button.ua-copy"), "what it answers: copy");
// Hide: out of the address; the answer's one line stays.
c.querySelector("a.td-chk-open").click();
assert.equal(q().get("tdchk"), null);
box = T.todoSection(m, S.read());
c = card(box, "lost-pages");
assert.ok(!c.querySelector(".td-chk-tbl") && text(c.querySelector("a.td-chk-open")) === "Show the 3 not fixed");
// A link with tdchk opens it straight away.
go("#overview/insights?tdchk=lost-pages");
box = T.todoSection(m, S.read());
assert.ok(card(box, "lost-pages").querySelector(".td-chk-tbl"));

// ---- more than 50: Check the next ...
const more = { ...partly, verdict: "more", words: "50 of 120 addresses checked: 48 fixed, 2 not yet. Check the next 50 to finish.", total: 120, checked: 50, next: 50 };
M.MARKS.checks = { "lost-pages": more };
box = T.todoSection(m, S.read());
const nxt = card(box, "lost-pages").querySelectorAll("button").find((b) => text(b) === "Check the next 50");
assert.ok(nxt, "the next page");
assert.ok(card(box, "lost-pages").querySelector(".ui-pill.info"));
answers = [{ status: 200, body: { ok: true, check: { ...more, checked: 100, next: 100 }, marks: {}, checks_withheld: {} } }];
nxt.click();
await tick();
assert.deepEqual(posted.at(-1)[1], { item: "lost-pages", start: 50 });

// ---- fixed: Skald's mark; the to-do moves to Done as Fixed, with no Undo
const fixed = { ...partly, verdict: "fixed", words: "Fixed: all 12 addresses now answer 301 to a live page.", ok: 12, bad: [], bad_total: 0 };
answers = [{ status: 200, body: { ok: true, check: fixed, checks_withheld: {},
  marks: { "lost-pages": { state: "fixed", day: "2026-10-27", at: "2026-10-27T14:40:00Z", first_day: "2026-10-27" } } } }];
box = T.todoSection(m, S.read());
card(box, "lost-pages").querySelectorAll("button").find((b) => text(b) === "Check again").click();
await tick();
box = T.todoSection(m, S.read());
c = box.querySelectorAll("article.td-done").find((a) => a.id === "td-lost-pages");
assert.ok(c, "in Done, and did it work?");
assert.equal(text(c.querySelector(".td-verdict")), "Fixed");
assert.ok(text(c).includes("Fixed: all 12 addresses now answer 301 to a live page.") && c.querySelector(".ui-pill.good"));
assert.deepEqual(words(c), ["Check again", "Show the list (12)"], "no Undo: a check made the mark, a new check undoes it");
assert.ok(!c.querySelector("a.td-chk-open"), "nothing failing: nothing to open");
// The second count disagreed: shown as done, with why.
M.MARKS.withheld = { "lost-pages": "the second count finds 11 of 12 addresses fixed" };
box = T.todoSection(m, S.read());
c = box.querySelectorAll("article.td-done").find((a) => a.id === "td-lost-pages");
assert.ok(text(c).includes("Shown as done, not fixed: the second count disagreed") && text(c.querySelector(".td-verdict")) !== "Fixed");
M.MARKS.withheld = {};

// ---- a refusal is said in place, with its copy icon
answers = [{ status: 429, body: { ok: false, error: "This to-do was checked 20 s ago. Check it again in 41 s." } }];
box = T.todoSection(m, S.read());
card(box, "server-errors").querySelectorAll("button").find((b) => text(b) === "Check again").click();
await tick();
box = T.todoSection(m, S.read());
c = card(box, "server-errors");
assert.ok(c.querySelector(".td-chk-said .ui-pill.bad") && text(c).includes("Check it again in 41 s."));
assert.ok(c.querySelector(".td-chk-said button.ua-copy"));

// ---- Check all again: each to-do Skald can ask, in turn, its progress in place
posted.length = 0;
answers = [{ status: 200, body: { ok: true, check: fixed, marks: {}, checks_withheld: {} } },
  { status: 200, body: { ok: true, check: { ...partly, item: "server-errors" }, marks: {}, checks_withheld: {} } }];
box = T.todoSection(m, S.read());
const bar = box.querySelector(".td-chkall");
bar.querySelector("button").click();
assert.ok(text(bar).includes("Checking 1 of 2: Send old pages somewhere useful"), "progress in place");
await tick(20);
assert.deepEqual(posted.map(([, b]) => b.item), ["lost-pages", "server-errors"]);
box = T.todoSection(m, S.read());
assert.ok(text(box.querySelector(".td-chkall")).includes("Checked again: 1 fixed, 1 partly fixed."), "the summary stays after the redraw");

// ---- a viewer: the answer, never the button
helper = { ...helper, role: "viewer", can_mark: false, checks: { "lost-pages": partly } };
await M.loadMarks(true);
box = T.todoSection(m, S.read());
assert.ok(!box.querySelectorAll("button").some((b) => /Check (again|all again|the next)/.test(text(b))), "no button");
assert.ok(text(card(box, "lost-pages")).includes("3 of 12 addresses still answer 404."), "the answer is shown");

// ---- next to an AI agent's report: Skald's own check, when it ran after the report
const fix = { state: "done", at: "2026-10-27T14:30:00Z", change: "", files: [], left: [], notes: "" };
const after = C.checkNote(lostTodo, fix);
assert.ok(after && text(after).startsWith("Skald checked: Partly fixed"));
assert.equal(C.checkNote(lostTodo, { ...fix, at: "2026-10-27T15:00:00Z" }), null, "a check before the report is not its check");
const li = R.reportBox(lostTodo, fix, after);
assert.ok(text(li).includes("Skald checked:"));

// ---- the demo: a sample answer, said to be one
DEMO.on = true;
C.forgetChecks();
DEMO.api.todocheck = { "lost-pages": "data/demo/todo-check-lost-pages.json" };
await M.loadMarks(true);
go("#overview/insights");
box = T.todoSection(m, S.read());
card(box, "lost-pages").querySelectorAll("button").find((b) => text(b) === "Check again").click();
await tick();
box = T.todoSection(m, S.read());
c = card(box, "lost-pages");
assert.ok(text(c).includes(C.DEMO_WORDS) && text(c).includes("3 of 12 addresses still answer 404."));
assert.ok(!c.querySelectorAll("button").some((b) => text(b).startsWith("Check the next")), "the demo has one page only");
DEMO.on = false;

console.log("todo-check: all passed");
