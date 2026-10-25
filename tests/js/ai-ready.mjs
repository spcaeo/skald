// AI readiness per page (2.35, js/ai-ready.js, js/robots-match.js, js/tabs/aiready.js): the
// six lines of a page (robots.txt, crawler errors, sitemap, Markdown copy, AI asking for a
// 404, last AI read), each good, needs attention or not known, never a guess; the block in
// a page's story with copy and open on every path and copy on every name, robots.txt line
// and status; the site's list with its filter in the address.
//
//   node tests/js/ai-ready.mjs                 (tests/test_ai_ready_js.py runs it)
//   node tests/js/ai-ready.mjs cases.json      prints robots verdicts for the Python side
//
// Example data only: made-up paths and figures, example.com.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const R = await import(new URL("robots-match.js", JS));

if (process.argv[2]) {
  // [{rules, path}] -> [{allowed, rule}]: the Python test compares them with robots_match.decide.
  const cases = JSON.parse(readFileSync(process.argv[2], "utf8"));
  process.stdout.write(JSON.stringify(cases.map((c) => R.decide(c.rules, c.path))));
  process.exit(0);
}

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
globalThis.history = { state: null, pushState(_, __, hash) { location.hash = hash; }, replaceState(_, __, hash) { location.hash = hash; }, back() {}, go() {} };
globalThis.requestAnimationFrame = (f) => f();
location.hash = "#traffic/pages?page=/guide/";

const A = await import(new URL("ai-ready.js", JS));
await import(new URL("sections.js", JS));
const { setSiteBase } = await import(new URL("urlactions.js", JS));
setSiteBase("example.com");

// ---- robots.txt matching: the longest rule, an Allow on a tie, wildcards, the end anchor
assert.deepEqual(R.decide([["disallow", "/"], ["allow", "/blog/"]], "/blog/x"), { allowed: true, rule: ["allow", "/blog/"] });
assert.equal(R.decide([["disallow", "/"], ["allow", "/blog/"]], "/about").allowed, false);
assert.equal(R.decide([["disallow", "/*.pdf$"]], "/a/b.pdf").allowed, false);
assert.equal(R.decide([["disallow", "/*.pdf$"]], "/a/b.pdfx").allowed, true);
assert.equal(R.decide([["allow", "/d/*"], ["disallow", "/d/*"]], "/d/x").allowed, true);
assert.equal(R.decide([], "/x").allowed, true);
assert.equal(R.clean("/café/%7euser/%2f"), "/caf%C3%A9/~user/%2F");

// ---- a page's six lines
const crawlers = [["GPTBot", "training"], ["OAI-SearchBot", "search"], ["ChatGPT-User", "asked"], ["ClaudeBot", "training"], ["Claude-User", "asked"],
  ["PerplexityBot", "search"], ["Perplexity-User", "asked"], ["Google-Extended", "training"], ["Applebot-Extended", "training"]];
const open = { agents: ["*"], rules: [["disallow", "/signup/"]], root: true };
const F = {
  schema_version: 1, crawlers,
  robots: { url: "https://example.com/robots.txt", fetched_at: "2026-10-06T06:00:00+00:00", ok: true, error: null, missing: false,
    crawlers: Object.fromEntries(crawlers.map(([t]) => [t, t === "GPTBot" ? { agents: ["GPTBot"], rules: [["disallow", "/private/"]], root: true }
      : t === "Google-Extended" ? { agents: ["Google-Extended"], rules: [["disallow", "/"]], root: false } : open])) },
  sitemap: { enabled: true, day: "2026-10-03", fetched_at: "2026-10-03T06:00:00+00:00", count: 3, pages: { "/": null, "/guide/": "2026-10-01", "/pricing/": null } },
  window: { days: 30, first: "2026-09-06", last: "2026-10-05", of: 2, recorded: 2, since: "2026-10-04", folded: 0 },
  pages: {
    "/guide/": { self: { "ChatGPT-User": { 301: 6 } }, slow: {}, copies: { "/guide.md": { "ChatGPT-User": { 404: 6 } } } },
    "/pricing/": { self: { ClaudeBot: { 503: 2 }, PerplexityBot: { 403: 1 } }, slow: { "Claude-User": 1 }, copies: { "/pricing.md": { GPTBot: { 200: 3, 304: 1 } } } },
    "/gone/": { self: { PerplexityBot: { 404: 2 } }, slow: {}, copies: {} },
  },
  attention: { total: 3, rows: [
    { path: "/guide/", listed: true, copy_errors: 6, copy_404: 6, not_found: 0, server_errors: 0, blocked: 0, robots: [], redirects: 6, slow: 0, by: ["ChatGPT-User"] },
    { path: "/pricing/", listed: true, copy_errors: 0, copy_404: 0, not_found: 0, server_errors: 2, blocked: 1, robots: [], redirects: 0, slow: 1, by: ["Claude-User", "ClaudeBot", "PerplexityBot"] },
    { path: "/private/x/", listed: null, copy_errors: 0, copy_404: 0, not_found: 0, server_errors: 0, blocked: 0, robots: ["GPTBot"], redirects: 0, slow: 0, by: [] },
  ] },
};
const pt = { days: [
  { day: "2026-08-20", state: "ok", fetches: { paths: { "/guide/": { "ChatGPT-User": 2 } }, folded: 0 } },
  { day: "2026-10-04", state: "ok", fetches: { paths: { "/guide": { "ChatGPT-User": 3 }, "/pricing/": { "Claude-User": 1 } }, folded: 0 } },
  { day: "2026-10-05", state: "ok", fetches: { paths: { "/guide/": { "Perplexity-User": 1 } }, folded: 0 } },
] };
const by = (lines) => Object.fromEntries(lines.map((x) => [x.id, x]));

let L = by(A.readiness(F, pt, "/guide/", "2026-10-05"));
assert.deepEqual(Object.keys(L), ["robots", "errors", "sitemap", "copy", "notfound", "read"]);
assert.equal(L.robots.state, "attention", "Google-Extended is shut out of the whole site");
assert.match(L.robots.says, /keeps Google-Extended out/);
assert.match(L.robots.action, /allow Google-Extended in robots.txt/);
assert.equal(L.robots.detail[0].rule, "Disallow: /");
assert.match(L.robots.snippet, /User-agent: Google-Extended\nAllow: \/guide\//);
// a redirect alone is said, not counted: the log does not say where it leads
assert.equal(L.errors.state, "good");
assert.match(L.errors.says, /redirected \(301\) 6 times\. The log does not say where a redirect leads/);
assert.equal(L.errors.action, undefined);
assert.equal(L.sitemap.state, "good");
assert.match(L.sitemap.says, /last changed 1 Oct/);
assert.equal(L.copy.state, "attention");
assert.equal(L.copy.says, "AI asked for the Markdown copy 6 times; it answered 404 each time.");
assert.match(L.copy.action, /Fix the 404 on the Markdown copy/);
assert.equal(L.notfound.state, "good");
assert.equal(L.read.state, "good");
assert.match(L.read.says, /last fetched it for someone on 5 Oct \(Perplexity-User 1\); 4 times in the last 30 days/);
assert.doesNotMatch(L.read.says, /30 before/, "the 30 days before are not all recorded: no figure");

L = by(A.readiness(F, pt, "/pricing/", "2026-10-05"));
assert.match(L.errors.says, /server errors \(503\) twice/);
assert.match(L.errors.says, /refused \(403\) once/);
assert.match(L.errors.says, /slow answers \(a second or more\) once/);
assert.match(L.errors.action, /Fix the server error/);
assert.equal(L.copy.state, "good");
assert.equal(L.copy.says, "AI asked for the Markdown copy 4 times; it answered 200 and 304 each time.");

L = by(A.readiness(F, pt, "/private/notes/", "2026-10-05"));
assert.match(L.robots.says, /keeps GPTBot and Google-Extended out/);
assert.equal(L.sitemap.state, "attention");
assert.equal(L.sitemap.action, "Add the page to the sitemap.");
assert.equal(L.copy.state, "unknown", "no copy asked for: Skald cannot tell");
assert.equal(L.notfound.state, "good");
assert.equal(L.read.state, "attention", "no read on the recorded days");
assert.match(L.read.says, /No assistant fetched it for someone in the last 30 days \(2 of 30 days recorded\)\./);

L = by(A.readiness(F, pt, "/gone/", "2026-10-05"));
assert.equal(L.notfound.state, "attention");
assert.match(L.notfound.says, /got 404 \(PerplexityBot 2\)/);

// a Markdown copy opened as a page is its page's
assert.equal(A.pageOf("/guide/index.md"), "/guide/");
assert.equal(A.pageOf("/Guide.MD/"), "/Guide/");

// not recorded is not known, never good: no robots.txt copy, no days of ai_status, no sitemap
const bare = { ...F, robots: { ok: false, missing: false, crawlers: null, error: "TimeoutError: timed out" }, sitemap: { enabled: true, pages: null }, window: { ...F.window, recorded: 0, since: null }, pages: {} };
L = by(A.readiness(bare, null, "/guide/", "2026-10-05"));
for (const id of ["robots", "errors", "sitemap", "copy", "notfound", "read"]) assert.equal(L[id].state, "unknown", id);
assert.match(L.robots.says, /the last try failed \(TimeoutError: timed out\)/);
// no robots.txt at all (a 404): every crawler may read it
L = by(A.readiness({ ...F, robots: { ok: false, missing: true, crawlers: null, error: "HTTPError: HTTP Error 404: Not Found" } }, pt, "/x/", "2026-10-05"));
assert.equal(L.robots.state, "good");
assert.match(L.robots.says, /answered 404/);
// days that summed addresses: "no error" is not known
L = by(A.readiness({ ...F, window: { ...F.window, folded: 1 } }, pt, "/features/", "2026-10-05"));
assert.equal(L.errors.state, "unknown");
assert.equal(L.notfound.state, "unknown");

// ---- the list's words and filter
assert.equal(A.needWords(F.attention.rows[0]), "Markdown copy: 404 6 times · redirected 6 times");
assert.equal(A.needAction(F.attention.rows[2]), "Allow GPTBot in robots.txt");
assert.deepEqual(F.attention.rows.filter(A.needKeep("errors")).map((r) => r.path), ["/pricing/"]);
assert.deepEqual(F.attention.rows.filter(A.needKeep("slow")).map((r) => r.path), ["/pricing/"]);
assert.equal(A.needAction({ ...F.attention.rows[1], server_errors: 0, blocked: 0, redirects: 4 }), "Speed the page up");
assert.deepEqual(A.wholeSite(F), ["Google-Extended"]);

// ---- drawn: the block in a page's story and the list
const tick = () => new Promise((r) => setImmediate(r));
globalThis.fetch = async (url) => ({ ok: true, status: 200, json: async () => (String(url).endsWith("ai_ready.json") ? F : null), body: { cancel() {} } });
const { readyBlock, notReadWell } = await import(new URL("tabs/aiready.js", JS));
const m = { files: ["ai_ready.json"], anchor: "2026-10-05", x: { page_trends: pt } };
const block = readyBlock(m, { view: "all", psec: "ai" }, "/guide/");
document.body.append(block);
for (let i = 0; i < 6; i++) await tick();
assert.match(block.textContent, /AI readiness/);
assert.match(block.textContent, /2 of 6 need attention/);
const links = [...block.querySelectorAll("a.ua-open")].map((a) => a.getAttribute("href"));
assert.ok(links.includes("https://example.com/guide.md"), "the copy's path has copy and open");
const copies = [...block.querySelectorAll("button.ua-copy")].map((b) => b.getAttribute("aria-label"));
assert.ok(copies.includes("Copy the name ChatGPT-User"), copies.join("|"));
assert.ok(copies.includes("Copy status 404"), "a status reason has copy");
assert.ok(copies.includes("Copy the robots.txt line"), "a robots.txt line has copy");
assert.ok(copies.includes("Copy the robots.txt lines"), "the suggested lines have copy");

location.hash = "#ai/assistants";
const list = notReadWell(m, { view: "all", arw: "" });
document.body.append(list);
for (let i = 0; i < 6; i++) await tick();
assert.match(list.textContent, /Pages AI can't read well/);
assert.match(list.textContent, /robots.txt keeps Google-Extended out of the whole site/);
const rows = [...list.querySelectorAll("tbody tr")];
assert.equal(rows.length, 3);
assert.match(rows[0].textContent, /Fix the 404 on the Markdown copy/);
assert.doesNotMatch(list.textContent, /\[object|null|undefined/, "every cell is drawn, not printed as an object");
assert.match(rows[1].textContent, /Claude-User, ClaudeBot, PerplexityBot/);
assert.ok([...rows[1].querySelectorAll("button.ua-copy")].some((b) => b.getAttribute("aria-label") === "Copy the name ClaudeBot"));
// the filter writes arw; a row opens the page's story at its AI readiness
[...list.querySelectorAll(".ar-chips button")].find((b) => b.textContent === "Errors").click();
assert.match(location.hash, /arw=errors/);
rows[1].click();
assert.match(location.hash, /^#traffic\/pages\?/);
assert.match(decodeURIComponent(location.hash), /page=\/pricing\//);
assert.match(location.hash, /psec=ai/);

console.log("ai-ready: all passed");
