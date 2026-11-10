// Insights' cards and Not found's lost pages (2.35; #5, #6: only open problems; js/tabs/todos.js,
// todo-words.js, todo-marks.js, todo-send.js, nf-lost.js): the cards drawn from todos.json, three
// plain lines each with no counts, its pill, Fix this and Open; every open leaving page in one card
// (todo=leave); a failed fix (the log's re-check, not the live check) under "Fixes that failed";
// one link to the fixes being checked (show=checking); "Nothing to fix right now."; Open kept in
// the address (todo=<id>) with the list and the marks (none without accounts, said why); Copy
// link with its green tick, the CSV's words, Send to team only with a mail server and a team, a
// to-do the address names that is not on the list; the lost pages' three tabs (nfk) and the
// server switch (nfsrv); and the owner's copy rule: every path gets copy + open, every line to
// paste and every word value the copy icon.
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

// ---- #5, #6: only open problems. Without accounts: the cards, three plain lines each,
// its pill, Fix this and Open; a withheld to-do named; the done one (passed) behind one link
const W = await import(new URL("tabs/todo-words.js", JS));
ME.mode = "basic";
go("#overview/insights");
let box = T.todoSection(m, S.read());
await tick();
const cards = () => box.querySelectorAll("article.td");
const cardOf = (id) => cards().find((a) => a.id === `td-${id}`);
assert.deepEqual(cards().map((a) => a.id), ["td-lost-pages", "td-leave"], "two open problems; the passed fix is not a card");
assert.ok(text(box).includes("To do this week") && !text(box).includes("Fixes that failed"));
const lostCard = cardOf("lost-pages");
assert.equal(text(lostCard.querySelector("h3")), "Old pages answer \"Page not found\"");
assert.ok(text(lostCard).includes("Do: Redirect each to the closest live page, or answer 410 gone."));
assert.equal(text(lostCard.querySelector(".td-tag")), "Needs fixing");
assert.ok(!/\d/.test(text(lostCard).replace("410", "")), "no counts, percentages or dates on the card");
assert.equal(text(cardOf("leave").querySelector("h3")), "1 page loses its readers");
const btnWords = (el) => el.querySelectorAll(".td-acts")[0].querySelectorAll("button").map(text);
assert.deepEqual(btnWords(lostCard), ["Fix this", "Open"], "one main button and Open, nothing else");
for (const gone of ["Download CSV", "Copy link", "Send to team", "Fix all", "Mark done", "Show the list", "Proof"]) assert.ok(!text(box).includes(gone), `${gone}: not on the overview`);
assert.ok(text(box).includes("left out: the second count disagreed"), "a withheld to-do is named");
assert.ok(box.querySelector(".note .ua-host button.ua-copy"), "its reason has the copy icon");
const link = box.querySelector(".td-checking a");
assert.equal(text(link), "1 fix passed");
link.click();
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("show"), "checking");
assert.equal(S.hashFor({ ...S.read(), tab: "overview/insights" }), "#overview/insights?show=checking", "kept in the address");
box = T.todoSection(m, S.read());
const passed = cardOf("server-errors");
assert.ok(passed && text(passed.querySelector(".td-verdict.v-fixed")) === "Passed" && text(passed).includes("Server errors: your fix worked"));
assert.deepEqual(btnWords(passed), ["Open"], "nothing to fix: no Fix this");
assert.ok(text(box).includes("Back to the open problems"));
go("#overview/insights");

// ---- Open: the address keeps it; the to-do's own table, its smaller actions and its tab;
// the rows' paths get copy + open, words copy alone
box = T.todoSection(m, S.read());
cardOf("lost-pages").querySelectorAll("button").find((b) => text(b) === "Open").click();
assert.equal(new URLSearchParams(location.hash.split("?")[1]).get("todo"), "lost-pages");
box = T.todoSection(m, S.read());
await tick();
const card = box.querySelector("article.td-on");
assert.ok(card && btnWords(card).includes("Close"));
assert.deepEqual(card.querySelectorAll(".td-more button").map(text), ["Mark done", "Not now"], "no accounts: no Check again (todo-check.mjs has it)");
const markBtn = card.querySelectorAll("button").find((b) => text(b) === "Mark done");
assert.ok(markBtn.hasAttribute("disabled") && markBtn.title === M.WHY.basic, "without accounts: says why on the button");
assert.ok(card.querySelector("a.td-open") && text(card.querySelector("a.td-open")).startsWith("See it in "), "where it shows: a quiet link");
const listed = card.querySelector(".td-list");
assert.ok(listed.querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/old-pricing/"), "old address: open");
assert.ok(listed.querySelectorAll("a.ua-open").some((a) => a.getAttribute("href") === "https://example.com/pricing/"), "closest page: open");
assert.ok(text(listed).includes("Same topic") && text(listed).includes("none close"));
// Every open leaving page in one card: todo=leave, or a page's own id from a mail's link.
for (const id of ["leave", "leave-0a1b2c3d"]) {
  go(`#overview/insights?todo=${id}`);
  box = T.todoSection(m, S.read());
  const on = box.querySelector("article.td-on");
  assert.equal(on && on.id, "td-leave", id);
  assert.ok(on.querySelector(".td-list a.ua-open").getAttribute("href") === "https://example.com/our-focus/", "the page: copy and open");
  assert.ok(on.querySelector(".td-list a.td-open"), "each page's figures: its tab");
}

// ---- the words: one map, from the to-do's own fields; a number only where it is the message
{
  const failedSitemap = { id: "sitemap", kind: "sitemap", figures: { paths: 3 }, rows: [], recheck: { verdict: "not_yet", still: [["/news_sitemap.xml", 8]], still_total: 1 } };
  assert.deepEqual(W.cardWords([failedSitemap], "failed"), { title: "1 of 3 sitemaps is still missing",
    why: "Crawlers keep asking for /news_sitemap.xml and find nothing.", act: "Publish it, or redirect it to your sitemap." });
  const failedLost = { ...lostTodo, recheck: { verdict: "not_yet", still: [["/old-pricing/", 6], ["/gone/", 1]], still_total: 2 } };
  assert.equal(W.cardWords([failedLost], "failed").act, "Redirect /old-pricing/ to /pricing/ first: it is asked for most since your fix.");
  assert.equal(W.cardWords([{ ...failedLost, recheck: { still: [["/gone/", 1]], still_total: 1 } }], "failed").title, "An old page still answers \"Page not found\"");
  const leaves = [1, 2, 3].map((i) => ({ ...leaveTodo, id: `leave-${i}`, rows: [{ source: "Search engine", visits: 9 }, { source: "Direct or unknown", visits: 3 }] }));
  assert.deepEqual(W.cardWords(leaves, "open"), { title: "3 pages lose their readers", why: "People land here from search and leave without a next step.", act: "Add a clear next step on each page." });
  assert.equal(W.cardWords([leaveTodo], "open").why, "People land here and leave without a next step.", "not from search: not said");
  assert.equal(W.cardWords([doneTodo], "checking").title, "Server errors: checking your fix");
  for (const st of ["open", "failed", "checking", "passed"]) {
    for (const t of [lostTodo, doneTodo, failedSitemap, { ...lostTodo, kind: "markdown" }]) {
      const w = W.cardWords([t], st);
      assert.ok(w.title && w.why && w.act, `${t.kind} ${st}: three lines`);
    }
  }
  // The status: the log's re-check decides, even after a passing live check (state fixed).
  const fixedMark = { state: "fixed", day: "2026-11-02" };
  const sm = { ...failedSitemap, state: "fixed", marked: fixedMark, status: "failed" };
  assert.equal(T.statusOf(sm, fixedMark), "failed");
  assert.equal(T.statusOf({ ...sm, status: undefined }, fixedMark), "failed", "from the verdict when the file has no status");
  assert.equal(T.statusOf(sm, { state: "done", day: "2026-11-09" }), "checking", "a mark made since the update: checking");
  assert.equal(T.statusOf(lostTodo, null), "open");
  assert.equal(T.statusOf(lostTodo, { state: "notnow", day: "2026-11-09" }), "notnow");
  // A failed fix is a card under "Fixes that failed" with its still-failing list.
  const fm = { x: { todos: { ...todos, withheld: [], todos: [sm] } } };
  go("#overview/insights");
  box = T.todoSection(fm, S.read());
  assert.ok(text(box).includes("Fixes that failed") && text(cardOf("sitemap").querySelector(".td-verdict")) === "Failed");
  assert.equal(text(cardOf("sitemap").querySelector("h3")), "1 of 3 sitemaps is still missing");
  go("#overview/insights?todo=sitemap");
  box = T.todoSection({ x: { todos: { ...todos, withheld: [], todos: [{ ...sm, columns: [], file: "sitemap-asks.csv", open: { tab: "site/notfound", name: "Site > Not found" } }] } } }, S.read());
  assert.ok(text(box.querySelector("article.td-on .td-list")).includes("/news_sitemap.xml"), "Open: the addresses still failing");
  // Nothing open: one line.
  go("#overview/insights");
  box = T.todoSection({ x: { todos: { ...todos, withheld: [], todos: [doneTodo] } } }, S.read());
  assert.ok(text(box).includes("Nothing to fix right now.") && !box.querySelector("article.td"));
}

// ---- the CSV says the words, not the codes
const { csv } = await import(new URL("table.js", JS));
const written = csv(T.columnsOf(lostTodo), lostTodo.rows);
assert.ok(written.startsWith("Old address,People,Closest live page,How close"));
assert.ok(written.includes("/old-pricing/,7,/pricing/,Same topic") && written.includes("/gone/,2,,No good match"));

// ---- 2.41, one button: Fix this; the link is the copy icon beside the title (green tick for 1.5 s)
go("#overview/insights");
box = T.todoSection(m, S.read());
mock.timers.enable({ apis: ["setTimeout"] });
const copyLink = cardOf("lost-pages").querySelector(".td-title button.ua-copy");
assert.equal(copyLink.getAttribute("aria-label"), 'Copy the link to "Old pages answer "Page not found""');
copyLink.click();
await Promise.resolve(); await Promise.resolve();
assert.ok(copied.at(-1).endsWith("#overview/insights?todo=lost-pages") && copied.at(-1).startsWith("https://app.example.com/traffic/example.com/"), copied.at(-1));
assert.ok(cardOf("lost-pages").querySelector(".td-title .ua").classList.contains("ua-ok"), "the green tick");
mock.timers.tick(U.TIMING.tick);
assert.ok(!cardOf("lost-pages").querySelector(".td-title .ua").classList.contains("ua-ok"));
mock.timers.reset();
cardOf("lost-pages").querySelectorAll("button").find((b) => text(b) === "Fix this").click();
let q = new URLSearchParams(location.hash.split("?")[1]);
assert.deepEqual([q.get("todo"), q.get("fix")], ["lost-pages", "1"]);
go("#overview/insights");
cardOf("leave").querySelectorAll("button").find((b) => text(b) === "Fix this").click();
q = new URLSearchParams(location.hash.split("?")[1]);
assert.deepEqual([q.get("todo"), q.get("fix")], ["leave", "1"], "the leaving pages' card: all of them");
// New to-dos (first_seen in the window's last 7 days): still worked out for the mail and the agent.
assert.deepEqual(T.newOnes([{ id: "a", first_seen: "2026-10-24" }, { id: "b", first_seen: "2026-10-23" }, { id: "c" }], { last: "2026-10-30" }).map((t) => t.id), ["a"]);
go("#overview/insights");

// ---- Me's lines: the same rules as closest_page.rules
const FX = await import(new URL("tabs/todo-fix.js", JS));
assert.deepEqual(FX.rules("/old-pricing/", "/pricing/"), { nginx: "location = /old-pricing/ { return 301 /pricing/; }", apache: "Redirect 301 /old-pricing/ /pricing/" });
assert.deepEqual(FX.rules("/gone/", null), { nginx: "location = /gone/ { return 410; }", apache: "Redirect gone /gone/" });
assert.deepEqual(FX.rules("/caf%C3%A9 x/", "/"), { nginx: null, apache: null }, "a space: written by hand");
assert.deepEqual(FX.rules("/a/?utm=1", "/b/"), FX.rules("/a/", "/b/"), "the query is not part of the rule");
assert.equal(FX.serverOf({ server: "Apache/2.4" }), "apache");
assert.equal(FX.serverOf({ server: "LiteSpeed" }), "apache");
assert.equal(FX.serverOf({}), "nginx");
const lines = FX.linesFor(lostTodo, lostTodo.rows, "nginx");
assert.ok(lines.text.includes("location = /old-pricing/ { return 301 /pricing/; }") && lines.text.includes("location = /gone/ { return 410; }   # no live page close to it"));
assert.equal(lines.count, 2);
assert.ok(FX.linesFor({ kind: "markdown" }, [{ path: "/pricing.md", page: "/pricing/" }], "apache").text.includes("RewriteCond %{REQUEST_FILENAME} !-f"));

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
assert.ok(!box.querySelectorAll("button").some((b) => text(b) === "Send to team"), "inside Fix this, not on the card");
assert.equal(text(cardOf("server-errors").querySelector(".td-tag")), "Needs fixing", "the helper's marks win: the done to-do is open again");

// ---- 2.41: Fix this, "Who will do it?" (js/tabs/todo-fix.js): every choice in the address,
// the line and its code never; a reload watches the same line; closing takes it all away.
{
  const CODE = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd";
  const LINK = "0f3a9c2e7b1d4a58";
  const fullRows = [...lostTodo.rows, { path: "/older/", people: 1, target: "/new/", match: "exact" }];
  let reports = {};
  const base = globalThis.fetch;
  globalThis.fetch = async (path, opts = {}) => {
    const body = opts.body ? JSON.parse(opts.body) : null;
    if (path === "settings/todo-agent") {
      posted.push([path, body]);
      if (body.act === "make") return { ok: true, status: 200, json: async () => ({ ok: true, line: `fix the Skald to-do "${lostTodo.title}" for example.com — read https://app.example.com/traffic-kit/llms.txt and use code ${CODE} (works once, 24 hours)`,
        steps_url: `https://app.example.com/traffic-kit/${CODE}/steps`, link_id: LINK, expires_at: new Date(Date.now() + 864e5).toISOString(), todos: body.items }) };
      if (body.act === "status") return { ok: true, status: 200, json: async () => ({ ok: true, state: "opened", opened_at: "2026-10-26T10:00:00Z", keys_at: "2026-10-26T10:00:05Z", reports }) };
      return { ok: true, status: 200, json: async () => ({ ok: true, state: "cancelled" }) };
    }
    if (String(path).startsWith("settings/todo-rows")) {
      posted.push([path, null]);
      return { ok: true, status: 200, json: async () => ({ ok: true, todo: { ...lostTodo, rows: fullRows, rows_total: 3 } }) };
    }
    return base(path, opts);
  };
  FX.setPoll({ every: 5, slow: 5 });
  const realCreate = document.createElement;
  document.createElement = (t) => { const el = realCreate(t); if (t === "dialog") Object.assign(el, { open: false, showModal() { this.open = true; }, close() { this.open = false; } }); return el; };
  const qs = () => new URLSearchParams(location.hash.split("?")[1]);
  const tile = (d, who) => d.el.querySelectorAll("button.ui-who-c").find((b) => b.dataset.who === who);

  // A to-do the address names that is not on the list.
  go("#overview/insights?todo=sitemap&fix=1");
  assert.equal(await FX.openFixKey("1", m, S.read()), FX.GONE);

  // Fix this: the shared question (ui/who.js), three answers in the approved order, nothing chosen yet.
  go("#overview/insights?todo=lost-pages");
  let d = FX.fixDialog([lostTodo], "1");
  assert.equal(qs().get("fix"), "1");
  assert.ok(text(d.el).includes("Who will do it?"));
  assert.deepEqual(d.el.querySelectorAll("button.ui-who-c").map((b) => b.querySelector("b").textContent), ["Me", "My developer", "My AI agent"]);
  assert.equal(d.el.querySelectorAll('.ui-who-c[aria-checked="true"]').length, 0);

  // Me: every row from Skald (not the browser's cut-down file), the server's lines, the CSV as a link.
  tile(d, "me").click();
  assert.equal(qs().get("by"), "me");
  await tick();
  assert.ok(posted.some(([p]) => p === "settings/todo-rows?item=lost-pages"), "every row asked for");
  const pre = d.el.querySelector("pre.fx-lines");
  assert.ok(text(pre).includes("location = /older/ { return 301 /new/; }"), "the row the browser file did not have");
  assert.ok(pre.parentNode.querySelector("button.ua-copy"), "the lines: copy icon");
  assert.ok(d.el.querySelectorAll("button").some((b) => text(b) === "Copy the lines"));
  assert.ok(d.el.querySelector("a.fx-csv") && text(d.el.querySelector("a.fx-csv")) === "Download CSV", "the CSV: a small link");
  assert.ok(text(d.el).includes("3 rows"));
  d.el.querySelectorAll(".fx-me .seg button").find((b) => text(b) === "Apache").click();
  assert.ok(text(d.el.querySelector("pre.fx-lines")).includes("Redirect 301 /older/ /new/"));
  assert.ok(text(d.el).includes(FX.UNDO_WORDS), "marking done changes no figure: said");

  // My developer: Send to team inside the same dialog.
  tile(d, "dev").click();
  assert.equal(qs().get("by"), "dev");
  await d.who.ready;
  d.el.querySelector("select.td-to").value = "2";
  d.el.querySelectorAll("button").find((b) => text(b) === "Send").click();
  await tick();
  assert.deepEqual(posted.at(-1), ["settings/todo-send", { item: "lost-pages", to: "2" }]);

  // My AI agent: pressed, the line is made at once; the address gets its link id, never the code.
  tile(d, "agent").click();
  await tick();
  assert.deepEqual(posted.filter(([p, b]) => p === "settings/todo-agent" && b.act === "make").at(-1)[1], { act: "make", items: ["lost-pages"] });
  assert.equal(qs().get("by"), "agent");
  assert.equal(qs().get("link"), LINK);
  assert.ok(!location.hash.includes(CODE), "the code is never in the address");
  assert.ok(!text(d.el.querySelector(".ag-line pre")).includes(CODE), "the code is hidden until Show code");
  d.el.querySelectorAll("button").find((b) => text(b) === "Copy").click();
  await tick();
  assert.ok(copied.at(-1).includes(`use code ${CODE}`) && copied.at(-1).startsWith('fix the Skald to-do "Send old pages somewhere useful" for example.com'));
  assert.ok(text(d.el).includes("Is it safe to paste this into a chat?") && text(d.el).includes("The worst a leaked line can do is mark one of these to-dos done"));
  // The watch: the agent's report shows, with the exact change and the rows it left.
  reports = { "lost-pages": { state: "done", at: "2026-10-26T10:05:00Z", change: "location = /old-pricing/ { return 301 /pricing/; }", files: ["deploy/nginx/site.conf"],
    left: [{ row: "/gone/", why: "no live page close to it; asked before a 410" }], notes: "Tested with nginx -t and reloaded after your yes.", link_id: LINK } };
  await tick(40);
  const watch = d.el.querySelector(".fx-watch");
  assert.ok(text(watch).includes("It read Skald's steps") && text(watch).includes("Send old pages somewhere useful: Done"), text(watch));
  assert.ok(watch.querySelector(".fx-change pre") && text(watch.querySelector(".fx-change pre")).includes("return 301 /pricing/"));
  assert.ok(watch.querySelector(".fx-change button.ua-copy"), "the change: copy icon");
  assert.ok(text(watch).includes("Left for you (1)") && text(watch).includes("/gone/"));
  const polls = posted.filter(([p, b]) => p === "settings/todo-agent" && b.act === "status").length;
  await tick(40);
  assert.equal(posted.filter(([p, b]) => p === "settings/todo-agent" && b.act === "status").length, polls, "every to-do reported: the watch stops");
  d.close({ instant: true });
  await tick();
  assert.ok(!qs().get("fix") && !qs().get("by") && !qs().get("fixby") && !qs().get("link"), "closed: the choice leaves the address");

  // A reload (or a link in a mail made before 2.41) with fixby=agent&link=…: no new line, the same line watched.
  FX.forgetLines();
  go(`#overview/insights?todo=lost-pages&fix=1&fixby=agent&link=${LINK}`);
  const makes = posted.filter(([p, b]) => p === "settings/todo-agent" && b.act === "make").length;
  d = await FX.openFixKey("1", m, S.read());
  await tick(20);
  assert.equal(posted.filter(([p, b]) => p === "settings/todo-agent" && b.act === "make").length, makes, "an address never makes a line");
  assert.equal(tile(d, "agent").getAttribute("aria-checked"), "true");
  assert.ok(text(d.el).includes("reported every to-do in this line") && text(d.el).includes("Send old pages somewhere useful: Done"), "all reported: said, no Make the line");
  assert.ok(!d.el.querySelectorAll("button").some((b) => text(b) === "Make the line"));
  // Cancel this line: it stops, and the link leaves the address.
  d.el.querySelectorAll("button").find((b) => text(b) === "Cancel this line").click();
  await tick();
  assert.deepEqual(posted.at(-1), ["settings/todo-agent", { act: "cancel", link_id: LINK }]);
  assert.ok(!qs().get("link") && text(d.el).includes("Cancelled. This line no longer works."));
  d.close({ instant: true });

  // The older someone (links made before 2.41) opens My developer.
  go("#overview/insights?todo=lost-pages&fix=1&fixby=someone");
  d = await FX.openFixKey("1", m, S.read());
  assert.equal(tile(d, "dev").getAttribute("aria-checked"), "true");
  d.close({ instant: true });

  // The leaving pages' card: Fix this for all of them (todo=leave).
  go("#overview/insights?todo=leave&fix=1");
  d = await FX.openFixKey("1", m, S.read());
  assert.ok(text(d.el).includes("Make /our-focus/ lead somewhere"), "the leaving pages, named");
  d.close({ instant: true });

  // Fix all (N): one line for every open to-do an agent can fix.
  go("#overview/insights");
  d = await FX.openFixKey("all", m, { ...S.read(), fixby: "agent" });
  await tick();
  assert.ok(text(d.el.querySelector(".dw-title")).includes("Fix all (3)"), "the helper's marks: the errors to-do is open again");
  assert.ok(!posted.slice(-3).some(([p, b]) => p === "settings/todo-agent" && b.act === "make"), "from an address: only on Make the line");
  d.el.querySelectorAll("button").find((b) => text(b) === "Make the line").click();
  await tick();
  assert.deepEqual(posted.filter(([p, b]) => p === "settings/todo-agent" && b.act === "make").at(-1)[1], { act: "make", items: ["lost-pages", "leave-0a1b2c3d", "server-errors"] });
  d.close({ instant: true });

  // A viewer: no line, said why.
  helper.can_mark = false;
  await M.loadMarks(true);
  go("#overview/insights?todo=lost-pages");
  d = FX.fixDialog([lostTodo], "1", { ...S.read(), fixby: "agent" });
  await d.who.ready;
  assert.ok(text(d.el).includes("Only an owner or an admin can make the line for an AI agent."));
  d.close({ instant: true });
  helper.can_mark = true;

  // The agent's report on the card, beside its marks (settings/todos' fixes).
  helper.fixes = { "lost-pages": reports["lost-pages"] };
  await M.loadMarks(true);
  go("#overview/insights");
  box = T.todoSection(m, S.read());
  const note = box.querySelectorAll("article.td").find((a) => a.id === "td-lost-pages").querySelector(".fx-card");
  assert.ok(note && text(note).includes("Your AI agent: Done") && text(note).includes("Tested with nginx -t"));
  delete helper.fixes;
  document.createElement = realCreate;
  globalThis.fetch = base;
}

// Open's smaller actions: Mark done moves the card to the fixes being checked; Not now folds it.
go("#overview/insights?todo=lost-pages");
box = T.todoSection(m, S.read());
const doIt = box.querySelectorAll(".td-more button").find((b) => text(b) === "Mark done" && !b.hasAttribute("disabled"));
doIt.click();
await tick();
assert.deepEqual(posted.at(-1), ["settings/todos", { item: "lost-pages", state: "done" }]);
assert.ok(!cardOf("lost-pages") && text(box.querySelector(".td-checking a")) === "1 fix being checked", "marked: out of the problems, being checked");
go("#overview/insights?show=checking");
box = T.todoSection(m, S.read());
assert.ok(text(cardOf("lost-pages")).includes("Old pages: checking your fix") && text(cardOf("lost-pages").querySelector(".td-verdict")) === "Checking");
go("#overview/insights?todo=server-errors");
box = T.todoSection(m, S.read());
const notNow = box.querySelectorAll(".td-more button").find((b) => text(b) === "Not now" && !b.hasAttribute("disabled"));
notNow.click();
await tick();
assert.ok(text(box).includes("Not now (1)"));
// Send to team: an older link with tdsend still opens it; who it goes to never goes in the address.
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
