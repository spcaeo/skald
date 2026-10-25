// Insights' to-dos and Not found's lost pages (2.35, js/tabs/todos.js, todo-marks.js,
// todo-send.js, nf-lost.js): the to-dos drawn from todos.json, "Show the list" kept in
// the address (todo=<id>), Copy link with its green tick, the CSV's words, the marks
// from the helper (none without accounts, said why), Send to team only with a mail
// server and a team, a to-do the address names that is not on the list; the lost
// pages' three tabs (nfk) and the server switch (nfsrv); and the owner's copy rule:
// every path gets copy + open, every line to paste and every word value the copy icon.
//
//   node tests/js/todos.mjs
import assert from "node:assert/strict";
import { mock } from "node:test";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });
const copied = [];
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async (t) => { copied.push(t); } } });
const posted = [];
let helper = null;            // what the helper answers to GET settings/todos (null: 404)
globalThis.fetch = async (path, opts = {}) => {
  if (opts.method === "POST") {
    const body = JSON.parse(opts.body);
    posted.push([path, body]);
    if (path === "settings/todos") {
      helper.marks = { ...helper.marks, [body.item]: { state: body.state, day: "2026-10-25", at: "2026-10-25T10:00:00Z", first_day: "2026-10-25" } };
      return { ok: true, status: 200, json: async () => ({ ok: true, marks: helper.marks }) };
    }
    return { ok: true, status: 200, json: async () => ({ ok: true, sent_to: "dev@example.com", file: "old-pages.csv" }) };
  }
  if (!helper) return { ok: false, status: 404, json: async () => ({ ok: false, error: "not found" }) };
  return { ok: true, status: 200, json: async () => structuredClone({ ok: true, ...helper }) };
};
const tick = (ms = 5) => new Promise((r) => setTimeout(r, ms));

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const U = await import(new URL("urlactions.js", JS));
const { ME } = await import(new URL("access.js", JS));
const T = await import(new URL("tabs/todos.js", JS));
const M = await import(new URL("tabs/todo-marks.js", JS));
const SEND = await import(new URL("tabs/todo-send.js", JS));
const L = await import(new URL("tabs/nf-lost.js", JS));
U.setSiteBase("example.com");
const text = (el) => el.textContent;
const go = (hash) => { history.replaceState(null, "", hash); };

// ---- a todos.json and a lost_pages.json as the data layer writes them
const cols = (...c) => c.map(([key, label, kind]) => ({ key, label, ...(kind === "path" ? { path: true } : kind ? {} : { num: true }) }));
const lostTodo = { id: "lost-pages", kind: "lost", subject: null, tag: "Lost traffic", tone: "bad", title: "Send old pages somewhere useful",
  proof: "2 old page addresses answered 'not found' from 1 Oct to 30 Oct: people asked 9 times, search engines 4 times, AI 2 times.",
  todo: "Redirect each to the closest live page.", check: "the not-found answers to the same addresses", figures: { paths: 2 }, qualifies: true,
  columns: cols(["path", "Old address", "path"], ["people", "People"], ["target", "Closest live page", "path"], ["match", "How close", "text"]),
  rows: [{ path: "/old-pricing/", people: 7, target: "/pricing/", match: "likely" }, { path: "/gone/", people: 2, target: null, match: null }],
  rows_total: 2, file: "old-pages.csv", open: { tab: "site/notfound", nfk: "lost", name: "Site > Not found" }, state: "open", marked: null, recheck: null,
  window: { first: "2026-10-01", last: "2026-10-30", days: 30 } };
const leaveTodo = { ...lostTodo, id: "leave-0a1b2c3d", kind: "leave", subject: "/our-focus/", tag: "Leaving", tone: "warn", title: "Make /our-focus/ lead somewhere",
  columns: cols(["source", "Came from", "text"], ["visits", "Visits"]), rows: [{ source: "google", visits: 18 }], file: "landing-visits.csv",
  open: { tab: "traffic/pages", page: "/our-focus/", name: "Traffic > Pages" } };
const doneTodo = { ...lostTodo, id: "server-errors", kind: "errors", title: "Fix the server errors", tag: "Broken", state: "done",
  marked: { state: "done", day: "2026-10-20", first_day: "2026-10-20" }, columns: cols(["path", "Address", "path"], ["errors", "Server errors"]),
  rows: [{ path: "/wp-json/", errors: 18 }], file: "server-errors.csv", open: { tab: "site/health", name: "Site > Health" },
  recheck: { verdict: "fixed", words: "Fixed: 0 server errors since 20 Oct.", days: 4 } };
const todos = { window: { first: "2026-10-01", last: "2026-10-30", days: 30, of: 30 }, marks: true, todos: [lostTodo, leaveTodo, doneTodo],
  withheld: [{ id: "ai-markdown", title: "Give AI the Markdown copies it asks for", why: "ai-markdown: pages 3 against 2" }] };
const lost = { window: { first: "2026-10-01", last: "2026-10-30", days: 30, of: 30 }, marks: true,
  totals: { paths: 2, people: 9, search: 4, ai: 2, md_paths: 2, md_live: 1, md_asks: 6, md_live_asks: 5 },
  lost: [{ path: "/old-pricing/", people: 7, search: 3, ai: 1, target: "/pricing/", match: "likely", marked: null,
    nginx: "location = /old-pricing/ { return 301 /pricing/; }", apache: "Redirect 301 /old-pricing/ /pricing/",
    gone: { nginx: "location = /old-pricing/ { return 410; }", apache: "Redirect gone /old-pricing/" } },
  { path: "/gone/", people: 2, search: 1, ai: 1, target: null, match: null, marked: "2026-10-24",
    nginx: "location = /gone/ { return 410; }", apache: "Redirect gone /gone/", gone: null }],
  markdown: { live: [{ path: "/pricing.md", ai: 5, page: "/pricing/", nginx: "location = /pricing.md { return 301 /pricing/; }", apache: "Redirect 301 /pricing.md /pricing/" }],
    other: [{ path: "/old.md", ai: 1, page: null, nginx: "location = /old.md { return 410; }", apache: "Redirect gone /old.md" }] },
  fixed: [{ path: "/gone/", marked_day: "2026-10-24", days: 1, people: 0, search: 0, ai: 0, bots: 0, served: 0, verdict: "fixed", today: null }],
  withheld: [] };
const m = { x: { todos, lost_pages: lost } };

// ---- the address keys are listed, and kept on their own tab only
for (const k of ["todo", "nfk", "nfsrv", "tdsend"]) assert.ok(K.KEYS.has(k), `${k} in routekeys.js`);
assert.equal(K.KEYS.get("tdsend").kind, "overlay");
for (const k of S.KNOWN()) assert.ok(K.KEYS.has(k), `${k} is listed`);
assert.equal(S.hashFor({ ...S.read(), tab: "overview/insights", todo: "lost-pages" }), "#overview/insights?todo=lost-pages");
assert.equal(S.hashFor({ ...S.read(), tab: "site/notfound", nfk: "md", nfsrv: "apache" }), "#site/notfound?nfk=md&nfsrv=apache");
assert.equal(S.hashFor({ ...S.read(), tab: "traffic/pages", todo: "lost-pages", nfk: "md" }), "#traffic/pages", "another tab starts without them");

// ---- without accounts: the list, nothing to mark, no Send to team, and why
ME.mode = "basic";
go("#overview/insights");
let box = T.todoSection(m, S.read());
await tick();
assert.equal(box.querySelectorAll("article.td").length, 3, "two open, one done");
assert.ok(text(box).includes("To do now") && text(box).includes("Send old pages somewhere useful"));
assert.ok(text(box).includes(M.WHY.basic), "says why nothing can be marked");
const markBtn = box.querySelectorAll("button").find((b) => text(b) === "Mark done");
assert.ok(markBtn.hasAttribute("disabled") && markBtn.title === M.WHY.basic);
assert.ok(!box.querySelectorAll("button").some((b) => text(b) === "Send to team"), "no mail, no team: not offered");
assert.ok(text(box).includes("left out: the second count disagreed"), "a withheld to-do is named");
assert.ok(box.querySelector(".note .ua-host button.ua-copy"), "its reason has the copy icon");
// A page to-do: its page with copy and open.
const sub = box.querySelector("p.td-sub");
assert.ok(sub.querySelector("button.ua-copy") && sub.querySelector("a.ua-open").getAttribute("href") === "https://example.com/our-focus/");
// Done, and did it work? with the re-check's own words.
const done = box.querySelector("article.td-done");
assert.ok(text(done).includes("Fixed: 0 server errors since 20 Oct.") && done.querySelector(".v-fixed"));

// ---- Show the list: the address keeps it; the rows' paths get copy + open, words copy alone
const show = box.querySelectorAll("button").find((b) => text(b).startsWith("Show the list (2)"));
show.click();
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("todo"), "lost-pages");
box = T.todoSection(m, S.read());
await tick();
const card = box.querySelector("article.td-on");
assert.ok(card && text(card).includes("Hide the list"));
const listed = card.querySelector(".td-list");
assert.ok(listed.querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/old-pricing/"), "old address: open");
assert.ok(listed.querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/pricing/"), "closest page: open");
assert.ok(text(listed).includes("Same topic") && text(listed).includes("none close"));
go("#overview/insights?todo=leave-0a1b2c3d");
box = T.todoSection(m, S.read());
const words = box.querySelector("article.td-on .td-list");
assert.ok(words.querySelector(".ua-host button.ua-copy") && !words.querySelector("a.ua-open"), "a source: copy only");

// ---- the CSV says the words, not the codes
const { csv } = await import(new URL("table.js", JS));
const written = csv(T.columnsOf(lostTodo), lostTodo.rows);
assert.ok(written.startsWith("Old address,People,Closest live page,How close"));
assert.ok(written.includes("/old-pricing/,7,/pricing/,Same topic") && written.includes("/gone/,2,,No good match"));

// ---- Copy link: this to-do's address, a green tick for 1.5 s
mock.timers.enable({ apis: ["setTimeout"] });
const copyLink = box.querySelectorAll("button.td-copy")[0];
copyLink.click();
await Promise.resolve(); await Promise.resolve();
assert.ok(copied.at(-1).endsWith("#overview/insights?todo=lost-pages") && copied.at(-1).startsWith("https://app.example.com/traffic/example.com/"), copied.at(-1));
assert.ok(copyLink.classList.contains("ok") && text(copyLink).includes("Copied"));
mock.timers.tick(U.TIMING.tick);
assert.ok(!copyLink.classList.contains("ok") && text(copyLink) === "Copy link");
mock.timers.reset();

// ---- a to-do the address names that is not on the list
go("#overview/insights?todo=sitemap");
box = T.todoSection(m, S.read());
assert.ok(text(box).includes("That to-do is not on the list now"));
assert.equal(await SEND.openSendKey("sitemap", m), SEND.GONE);
assert.ok((await SEND.openSendKey("lost-pages", m)).startsWith("Send to team is not offered here"), "no accounts: the reason");

// ---- with accounts, an admin, a mail server and a team: marks and Send to team
ME.mode = "sessions";
helper = { marks: {}, role: "admin", can_mark: true, mail: { ready: true, why: "" }, team: [{ id: 2, email: "dev@example.com", role: "viewer" }] };
await M.loadMarks(true);
go("#overview/insights");
box = T.todoSection(m, S.read());
assert.ok(box.querySelectorAll("button").some((b) => text(b) === "Send to team"), "offered");
assert.ok(!box.querySelector("article.td-done"), "the helper's marks win: the done to-do is open again");
const doIt = box.querySelectorAll("button").find((b) => text(b) === "Mark done" && !b.hasAttribute("disabled"));
doIt.click();
await tick();
assert.deepEqual(posted.at(-1), ["settings/todos", { item: "lost-pages", state: "done" }]);
assert.ok(text(box.querySelector("article.td-done")).includes("re-checks it on the next data update"), "moved to done, waiting for the re-check");
const notNow = box.querySelectorAll("button").find((b) => text(b) === "Not now" && !b.hasAttribute("disabled"));
notNow.click();
await tick();
assert.ok(text(box).includes("Not now (1)"));
// Send to team: the dialog writes tdsend; who it goes to never goes in the address.
box.querySelectorAll("button").find((b) => text(b) === "Send to team")?.click();
assert.ok(/[?&]tdsend=/.test(location.hash));
const HTMLDialog = { open: false, showModal() { this.open = true; }, close() { this.open = false; } };
const realCreate = document.createElement;
document.createElement = (t) => { const el = realCreate(t); if (t === "dialog") Object.assign(el, HTMLDialog); return el; };
const d = await SEND.openSendKey("server-errors", m);
assert.ok(d && d.el, "the dialog opened");
assert.ok(text(d.el).includes("A teammate without rights to this site sees \"not available to you\""));
d.el.querySelector("select").value = "2";
d.el.querySelectorAll("button").find((b) => text(b) === "Send").click();
await tick();
assert.deepEqual(posted.at(-1), ["settings/todo-send", { item: "server-errors", to: "2" }]);
assert.ok(text(d.el).includes("Sent to dev@example.com"));
assert.ok(!/example\.com%40|dev%40|@/.test(location.hash), "no email in the address");
d.close({ instant: true });
document.createElement = realCreate;

// ---- Not found: the lost pages, their three tabs and the server switch
go("#site/notfound");
let lp = L.lostPages(m, S.read());
await tick();
assert.ok(text(lp).includes("Old addresses still asked for") && text(lp).includes("People asked"));
const rowsOf = (el) => el.querySelectorAll("tbody tr");
assert.equal(rowsOf(lp).length, 2);
const first = rowsOf(lp)[0];
assert.ok(first.querySelectorAll("a.ua-open").length >= 2, "old address and closest page: copy + open");
const lineCells = first.querySelectorAll("code.lp-line");
assert.equal(text(lineCells[0]), "location = /old-pricing/ { return 301 /pricing/; }");
assert.equal(text(lineCells[1]), "location = /old-pricing/ { return 410; }", "or gone");
for (const c of lineCells) assert.ok(c.parentNode.classList.contains("ua-host") && c.parentNode.querySelector("button.ua-copy") && !c.parentNode.querySelector("a.ua-open"), "a line: copy alone");
// The marks: a row marked fixed says so; another can be marked.
assert.ok(text(rowsOf(lp)[1]).includes("Marked fixed 24 Oct") || text(lp).includes("Mark fixed"));
first.querySelectorAll("button").find((b) => text(b) === "Mark fixed").click();
await tick();
assert.deepEqual(posted.at(-1), ["settings/todos", { item: "path:/old-pricing/", state: "fixed" }]);
// Apache.
lp.querySelectorAll("button").find((b) => text(b) === "Apache").click();
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("nfsrv"), "apache");
lp = L.lostPages(m, S.read());
assert.equal(text(rowsOf(lp)[0].querySelector("code.lp-line")), "Redirect 301 /old-pricing/ /pricing/");
assert.ok(L.redirectMap(lost.lost, "apache").includes("Redirect gone /gone/   # no live page close to it"));
assert.ok(L.redirectMap(lost.lost, "nginx").includes("location = /old-pricing/ { return 301 /pricing/; }"));
// AI asks for Markdown.
lp.querySelectorAll("button").find((b) => text(b) === "AI asks for Markdown").click();
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("nfk"), "md");
lp = L.lostPages(m, S.read());
assert.ok(text(lp).includes("asked for .md versions of 1 live page, 5 times"));
assert.ok(lp.querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/pricing.md"));
// After the fix.
go("#site/notfound?nfk=fixed");
lp = L.lostPages(m, S.read());
assert.ok(text(lp).includes("After the fix") && rowsOf(lp).length >= 1);
assert.ok(rowsOf(lp).some((r) => text(r).includes("/old-pricing/") && text(r).includes("Waiting")), "marked since the update: waiting");
// Withheld: no figure at all.
const held = L.lostPages({ x: { lost_pages: { ...lost, totals: null, lost: null, markdown: null, withheld: ["lost: people 9 against 8"] } } }, S.read());
assert.ok(text(held).includes("Withheld") && !held.querySelector(".tiles"));
assert.equal(L.lostPages({ x: {} }, S.read()), null, "no file: nothing drawn here");
console.log("todos: all passed");
