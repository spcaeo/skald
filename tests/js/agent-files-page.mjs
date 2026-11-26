// SKALD-65: Traffic › Agent files drawn section-wise (js/tabs/tr-agentfiles.js and
// agent-files-kind.js), against agent_files.json shaped as agent_files.py builds it:
//  - one section per kind someone fetched, in the owner's order (Markdown copies,
//    llms.txt, Sitemaps, robots.txt, agent cards, OKF bundle); none for a kind nobody asked for
//  - each section's figures are its kind's; Needs a look holds only its own kind's files
//  - every file's address has Copy and Open; Copy writes the full address, not the path
//  - robots.txt is one line and a note when it needs a look
//  - the cards jump to their sections and say how many need a look; no chips
//  - Who fetches them (all agent files) at the bottom, above How Skald counts this
//
//   node tests/js/agent-files-page.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const C = await import(new URL("tabs/common.js", JS));
const { setSiteBase, shownWords } = await import(new URL("urlactions.js", JS));
const agentFiles = (await import(new URL("tabs/tr-agentfiles.js", JS))).default;
const K = await import(new URL("tabs/agent-files-kind.js", JS));

const TODAY = "2026-11-26";
const f1 = (kind, requests, status, who, names, last) => ({ kind, requests, status, who, names, last });
const blob = {
  kinds: {
    markdown: { requests: 20, status: { "2xx": 13, "3xx": 5, "4xx": 2 }, who: { ai_asked: 2, bots: 17, people: 1 } },
    llms_txt: { requests: 7, status: { "2xx": 4, "3xx": 1, "4xx": 2 }, who: { bots: 7 } },
    sitemap: { requests: 30, status: { "2xx": 25, "3xx": 4, "4xx": 1 }, who: { search_engines: 6, bots: 24 } },
    robots_txt: { requests: 62, status: { "2xx": 38, "3xx": 24 }, who: { ai_training: 3, search_engines: 13, bots: 46 } },
    agent_card: { requests: 3, status: { "4xx": 3 }, who: { bots: 3 } },
  },
  names: {
    bots: { PetalBot: { markdown: 9, sitemap: 4 }, scanner: { llms_txt: 4, sitemap: 20, robots_txt: 6, markdown: 8, agent_card: 3 }, curl: { llms_txt: 3, robots_txt: 40 } },
    search_engines: { bingbot: { sitemap: 6, robots_txt: 13 } },
    ai_training: { GPTBot: { robots_txt: 3 } },
    ai_asked: { "ChatGPT-User": { markdown: 2 } },
    people: { "(all others)": { markdown: 1 } },
  },
  files: {
    "/CHANGELOG.md": f1("markdown", 5, { "301": 3, "404": 2 }, { bots: 4, people: 1 }, { scanner: 4 }, "2026-11-26T09:00:00Z"),
    "/pricing.md": f1("markdown", 9, { "200": 9 }, { ai_asked: 2, bots: 7 }, { PetalBot: 7, "ChatGPT-User": 2 }, "2026-11-26T08:00:00Z"),
    "/blog/old-post.md": f1("markdown", 6, { "200": 4, "301": 2 }, { bots: 6 }, { PetalBot: 2, scanner: 4 }, "2026-11-26T07:00:00Z"),
    "/llms.txt": f1("llms_txt", 5, { "200": 4, "301": 1 }, { bots: 5 }, { scanner: 2, curl: 3 }, "2026-11-26T06:00:00Z"),
    "/llms-full.txt": f1("llms_txt", 2, { "404": 2 }, { bots: 2 }, { scanner: 2 }, "2026-11-26T05:00:00Z"),
    "/sitemap.xml": f1("sitemap", 20, { "200": 16, "301": 4 }, { search_engines: 6, bots: 14 }, { scanner: 14, bingbot: 6 }, "2026-11-26T04:00:00Z"),
    "/blog/sitemap.xml": f1("sitemap", 1, { "404": 1 }, { bots: 1 }, { scanner: 1 }, "2026-11-26T03:00:00Z"),
    "/sitemap-page.xml": f1("sitemap", 9, { "200": 9 }, { bots: 9 }, { PetalBot: 4, scanner: 5 }, "2026-11-26T02:00:00Z"),
    "/robots.txt": f1("robots_txt", 62, { "200": 38, "301": 24 }, { ai_training: 3, search_engines: 13, bots: 46 }, { curl: 40, bingbot: 13 }, "2026-11-26T09:30:00Z"),
    "/.well-known/agent-card.json": f1("agent_card", 2, { "404": 2 }, { bots: 2 }, { scanner: 2 }, "2026-11-26T01:00:00Z"),
    "/.well-known/mcp.json": f1("agent_card", 1, { "404": 1 }, { bots: 1 }, { scanner: 1 }, "2026-11-26T01:10:00Z"),
  },
  rest: {},
};
const agentFile = { days: [], today: { day: TODAY, state: "ok", files: blob } };
globalThis.fetch = async (url) => (String(url).endsWith("agent_files.json")
  ? { status: 200, ok: true, headers: { get: () => "application/json" }, json: async () => agentFile }
  : { status: 404, ok: false, body: { cancel() {} }, headers: { get: () => "" }, json: async () => null });

const m = { site: "www.example.com", today: TODAY, anchor: "2026-11-25", firstDay: "2026-11-01", byDay: new Map(), views: [], journeys: [],
  options: {}, days: [], live: { day: TODAY, state: "ok" }, files: ["app.json", "agent_files.json"] };
location.hash = "#traffic/agentfiles?range=today";
const s = S.read();
C.setContext(m, s);
setSiteBase(m.site);

const page = document.createElement("div");
page.append(...agentFiles(m, s).filter(Boolean));
document.body.append(page);
for (let i = 0; i < 20 && page.querySelectorAll(".af-sec").length === 0; i += 1) await new Promise((r) => setTimeout(r, 5));
const all = (root, sel) => root.querySelectorAll(sel);
const sec = (k) => all(page, ".af-sec").find((x) => x.getAttribute("data-kind") === k);
const heads = (root) => all(root, "th").map((x) => x.textContent.replace(/[↕↑↓▲▼]/g, "").trim());

// ---- 1. one section per kind fetched, in the owner's order; none for the OKF bundle
{
  const kinds = all(page, ".af-sec").map((x) => x.getAttribute("data-kind"));
  assert.deepEqual(kinds, ["markdown", "llms_txt", "sitemap", "robots_txt", "agent_card"], "Markdown, llms.txt, Sitemaps, robots.txt, agent cards; no OKF (nobody asked)");
  assert.deepEqual(K.SECTION_ORDER, ["markdown", "llms_txt", "sitemap", "robots_txt", "agent_card", "okf"]);
  assert.equal(sec("markdown").getAttribute("id"), "af-markdown");
  assert.equal(all(page, ".af-chip").length + all(page, ".af-chips").length, 0, "the chips are gone");
  assert.match(sec("markdown").querySelector("h2").textContent, /^Markdown copies$/);
}

// ---- 2. a section's head is its kind's figures
{
  const facts = (k) => all(sec(k), ".af-hf").map((x) => x.textContent);
  assert.deepEqual(facts("markdown"), ["20requests", "10%from AI", "3files listed", "2need a look"]);
  assert.deepEqual(facts("llms_txt"), ["7requests", "0%from AI", "2files listed", "2need a look"]);
  assert.deepEqual(facts("sitemap"), ["30requests", "0%from AI", "3files listed", "2need a look"]);
  assert.deepEqual(facts("robots_txt"), ["62requests", "5%from AI", "1file listed", "1needs a look"]);
  // Who asked: the kind's own names, busiest first; a folded row is not a name.
  const busy = all(sec("sitemap"), ".af-busy li").map((x) => shownWords(x));
  assert.deepEqual(busy, ["scanner 20", "bingbot 6", "PetalBot 4"]);
  assert.ok(!all(sec("markdown"), ".af-busy li").some((x) => /all others/.test(x.textContent)));
}

// ---- 3. Needs a look: only the section's own kind, without a Kind column
{
  const lookRows = (k) => { const p = sec(k).querySelector(".af-look"); return p ? all(p, "td code.af-path").map((x) => x.textContent) : []; };
  assert.deepEqual(lookRows("markdown"), ["/CHANGELOG.md", "/blog/old-post.md"]);
  assert.deepEqual(lookRows("sitemap"), ["/blog/sitemap.xml", "/sitemap.xml"]);
  assert.deepEqual(lookRows("llms_txt"), ["/llms-full.txt", "/llms.txt"]);
  assert.deepEqual(lookRows("agent_card"), ["/.well-known/agent-card.json", "/.well-known/mcp.json"]);
  assert.equal(sec("robots_txt").querySelector(".af-look"), null, "robots.txt says it in a note");
  const th = heads(sec("markdown").querySelector(".af-look"));
  assert.deepEqual(th.slice(0, 4), ["File", "Answered", "Asked by", "What to do"]);
  assert.match(sec("llms_txt").querySelector(".af-look").textContent, /Agents ask for it and the site has none/);
  assert.equal(sec("agent_card").querySelector(".af-files table tbody tr td code")?.textContent, "/.well-known/agent-card.json");
}

// ---- 4. Files: no Kind column; Copy of for Markdown copies only
{
  assert.ok(heads(sec("markdown").querySelector(".af-files")).includes("Copy of"));
  assert.ok(!heads(sec("markdown").querySelector(".af-files")).includes("Kind"));
  assert.ok(!heads(sec("sitemap").querySelector(".af-files")).includes("Copy of"));
  const order = all(sec("markdown").querySelector(".af-files"), "td code.af-path").map((x) => x.textContent);
  assert.deepEqual(order, ["/pricing.md", "/blog/old-post.md", "/CHANGELOG.md"], "busiest first");
  assert.ok(all(sec("markdown").querySelector(".af-files"), "tr.go").length >= 3, "a row opens the file's drawer");
}

// ---- 5. every file's address: Copy and Open, Copy writing the full address
{
  for (const k of ["markdown", "llms_txt", "sitemap", "agent_card"]) {
    for (const part of all(sec(k), ".af-part").filter((p) => p.querySelector("table"))) {
      for (const code of all(part, "td code.af-path")) {
        const host = code.parentNode.querySelector(".ua") ? code.parentNode : code.parentNode.parentNode;
        const copy = host.querySelector(".ua-copy"), open = host.querySelector(".ua-open");
        assert.ok(copy && open, `${code.textContent}: Copy and Open`);
        assert.equal(copy.getAttribute("title"), `Copy https://www.example.com${code.textContent}`);
        assert.equal(open.getAttribute("href"), `https://www.example.com${code.textContent}`);
        assert.equal(open.getAttribute("target"), "_blank");
      }
    }
  }
  const one = sec("robots_txt").querySelector(".af-one");
  assert.equal(one.querySelector(".ua-copy").getAttribute("title"), "Copy https://www.example.com/robots.txt");
  assert.equal(one.querySelector(".ua-open").getAttribute("href"), "https://www.example.com/robots.txt");
}

// ---- 6. robots.txt: one line and its note
{
  const r = sec("robots_txt");
  assert.equal(r.querySelector("table"), null, "no table for one file");
  assert.match(r.querySelector(".af-one").textContent, /Requests62/);
  assert.match(r.querySelector(".af-one").textContent, /38 ok · 24 moved/);
  assert.match(r.querySelector(".af-note").textContent, /^Needs a look: 301 × 24\. It sends agents elsewhere\./);
  assert.match(r.querySelector(".af-note").textContent, /Asked by AI crawlers 3, Search engines 13, Other bots and tools 46\./);
  assert.equal(r.querySelector(".af-one").getAttribute("role"), null, "no button around Copy and Open");
  assert.match(r.querySelector("button.linkish").textContent, /Its days, answers and who fetched it/);
}

// ---- 7. the cards: one per kind, each jumping to its section, with what needs a look
{
  const jumps = all(page, "button.af-jump");
  assert.deepEqual(jumps.map((b) => b.getAttribute("data-jump")), ["markdown", "llms_txt", "sitemap", "robots_txt", "agent_card"]);
  assert.ok(jumps.every((b) => b.childNodes.every((c) => c.tagName === "SPAN" || c.tagName === "span")), "only spans inside a button");
  const words = all(page, ".kpi").map((x) => x.querySelector(".k-l").textContent);
  assert.deepEqual(words, ["All agent files", "Markdown copies", "llms.txt", "Sitemaps", "robots.txt", "Agent cards"], "robots.txt and sitemaps apart; no OKF card");
  const warn = all(page, ".kpi").map((x) => x.querySelector(".af-kw")?.textContent || "");
  assert.deepEqual(warn, ["9 need a look", "2 need a look", "2 need a look", "2 need a look", "1 needs a look", "2 need a look"]);
  let went = null, focused = null;
  const target = sec("sitemap");
  target.scrollIntoView = (o) => { went = o; };
  target.querySelector("h2").focus = (o) => { focused = o; };
  assert.equal(target.querySelector("h2").getAttribute("tabindex"), "-1");
  const getById = document.getElementById;
  document.getElementById = (id) => (id === "af-sitemap" ? target : null);
  jumps[2].dispatchEvent(new Event("click"));
  document.getElementById = getById;
  assert.deepEqual(went, { behavior: "smooth", block: "start" }, "the Sitemaps card scrolls to its section");
  assert.deepEqual(focused, { preventScroll: true }, "and the keyboard carries on from its heading");
}

// ---- 8. Who fetches them at the bottom, above How Skald counts this
{
  const blocks = page.querySelector(".af").childNodes.filter((x) => x.tagName);
  const names = blocks.map((x) => (x.classList?.contains("af-sec") ? `sec:${x.getAttribute("data-kind")}` : x.querySelector?.("h2")?.textContent || (x.querySelector?.(".kpis") ? "cards" : x.className)));
  assert.deepEqual(names, ["cards", "sec:markdown", "sec:llms_txt", "sec:sitemap", "sec:robots_txt", "sec:agent_card", "Who fetches them: all agent files", "How Skald counts this"]);
  const who = blocks[6];
  assert.deepEqual(heads(who).slice(0, 2), ["Name", "Who"]);
  assert.ok(heads(who).includes("robots.txt") && heads(who).includes("Sitemaps"), "a column per kind, as before");
}

// ---- 9. a range nobody fetched anything in says so: no sections, no jumps
{
  const empty = { days: [], today: { day: TODAY, state: "ok", files: { kinds: {}, names: {}, files: {}, rest: {} } } };
  const was = globalThis.fetch;
  globalThis.fetch = async () => ({ status: 200, ok: true, headers: { get: () => "application/json" }, json: async () => empty });
  const other = document.createElement("div");
  other.append(...agentFiles(m, { ...s, view: "quiet" }).filter(Boolean));
  for (let i = 0; i < 20 && !/Nobody fetched/.test(other.textContent); i += 1) await new Promise((r) => setTimeout(r, 5));
  globalThis.fetch = was;
  assert.equal(all(other, ".af-sec").length, 0);
  assert.equal(all(other, "button.af-jump").length, 0);
  assert.match(other.textContent, /Nobody fetched these files in this range\./);
}

// ---- 10. ranges where files are not all listed, odd paths, two robots.txt spellings, OKF
async function render(file, view, range = "today") {
  const was = globalThis.fetch;
  globalThis.fetch = async () => ({ status: 200, ok: true, headers: { get: () => "application/json" }, json: async () => file });
  const el = document.createElement("div");
  el.append(...agentFiles(m, { ...s, view, range }).filter(Boolean));
  for (let i = 0; i < 30 && !el.querySelector(".af-sec, .empty:not(:first-child)") && !/Nobody fetched|No whole/.test(el.textContent); i += 1) await new Promise((r) => setTimeout(r, 5));
  globalThis.fetch = was;
  return el;
}
const secIn = (el, k) => all(el, ".af-sec").find((x) => x.getAttribute("data-kind") === k);
{
  // a. An absolute-form target from the log ("GET http://other.example/llms.txt") and a
  //    "//host" one: listed, but no Copy or Open (the link would leave the site).
  const odd = { kinds: { llms_txt: { requests: 3, status: { "2xx": 3 }, who: { bots: 3 } } }, names: { bots: { curl: { llms_txt: 3 } } },
    files: { "http://other.example/llms.txt": f1("llms_txt", 1, { "200": 1 }, { bots: 1 }, { curl: 1 }, null),
      "//other.example/llms.txt": f1("llms_txt", 1, { "200": 1 }, { bots: 1 }, { curl: 1 }, null),
      "/llms.txt": f1("llms_txt", 1, { "200": 1 }, { bots: 1 }, { curl: 1 }, null) }, rest: {} };
  const el = await render({ days: [], today: { day: TODAY, state: "ok", files: odd } }, "odd");
  const rows = all(secIn(el, "llms_txt").querySelector(".af-files"), "tbody tr");
  const opens = rows.map((tr) => [tr.querySelector("code").textContent, tr.querySelector(".ua-open")?.getAttribute("href") || null]);
  assert.deepEqual(opens.sort(), [["/llms.txt", "https://www.example.com/llms.txt"], ["//other.example/llms.txt", null], ["http://other.example/llms.txt", null]].sort());
  assert.equal(K.sitePath("http://other.example/x"), null);
  assert.equal(K.sitePath("/\\other.example"), null);
  assert.equal(K.sitePath("/robots.txt"), "/robots.txt");
}
{
  // b. 40 days: the older days kept no files. Requests cover every day; the files, their
  //    answers and what needs a look cover the listed days and say so. robots.txt is no
  //    longer one line (its answers would cover fewer days than its requests), and the
  //    kind's "3xx" bucket (304s) raises no look.
  const day = (d, files) => ({ day: d, state: "ok", files });
  const oldBlob = { kinds: { robots_txt: { requests: 15, status: { "2xx": 10, "3xx": 5 }, who: { search_engines: 15 } },
    llms_txt: { requests: 4, status: { "4xx": 4 }, who: { bots: 4 } } }, names: { search_engines: { Googlebot: { robots_txt: 15 } }, bots: { curl: { llms_txt: 4 } } } };
  const newBlob = { kinds: { robots_txt: { requests: 2, status: { "2xx": 2 }, who: { search_engines: 2 } } }, names: { search_engines: { Googlebot: { robots_txt: 2 } } },
    files: { "/robots.txt": f1("robots_txt", 2, { "200": 2 }, { search_engines: 2 }, { Googlebot: 2 }, "2026-11-25T10:00:00Z") }, rest: {} };
  const file = { days: [day("2026-10-01", oldBlob), day("2026-11-25", newBlob)], today: null };
  const el = await render(file, "long", "90d");
  const robots = secIn(el, "robots_txt");
  assert.equal(robots.querySelector(".af-one"), null, "requests and answers over different days: the tables");
  assert.deepEqual(all(robots, ".af-hf").map((x) => x.textContent), ["17requests", "0%from AI", "1file listed"], "no look from the 304s in the bucket");
  assert.match(robots.querySelector(".af-files").textContent, /listed for 1 day of the 2 days counted, and so are their answers and what needs a look/);
  const llms = secIn(el, "llms_txt");
  assert.deepEqual(all(llms, ".af-hf").map((x) => x.textContent), ["4requests", "0%from AI", "-files listed"], "no file kept: not listed, never 0");
  assert.match(llms.querySelector(".af-files h3").textContent, /not listed/);
  assert.match(llms.querySelector(".af-files").textContent, /Files are listed for the last 30 days only\./);
}
{
  // c. Two spellings of robots.txt (file keys keep case and the slash): both shown, in a table.
  const two = { kinds: { robots_txt: { requests: 7, status: { "2xx": 5, "4xx": 2 }, who: { bots: 7 } } }, names: { bots: { curl: { robots_txt: 7 } } },
    files: { "/robots.txt": f1("robots_txt", 5, { "200": 5 }, { bots: 5 }, { curl: 5 }, null), "/robots.txt/": f1("robots_txt", 2, { "404": 2 }, { bots: 2 }, { curl: 2 }, null) }, rest: {} };
  const el = await render({ days: [], today: { day: TODAY, state: "ok", files: two } }, "two");
  const robots = secIn(el, "robots_txt");
  assert.equal(robots.querySelector(".af-one"), null);
  assert.deepEqual(all(robots.querySelector(".af-look"), "td code.af-path").map((x) => x.textContent), ["/robots.txt/"]);
  assert.equal(all(el, ".kpi").find((x) => x.querySelector(".k-l").textContent === "robots.txt").querySelector(".af-kw").textContent, "1 needs a look");
}
{
  // d. Only beyond the busiest 50: requests, no file listed: "not listed", never a plain 0.
  const rest = { kinds: { sitemap: { requests: 3, status: { "2xx": 3 }, who: { bots: 3 } } }, names: { bots: { curl: { sitemap: 3 } } }, files: {}, rest: { sitemap: { files: 2, requests: 3 } } };
  const el = await render({ days: [], today: { day: TODAY, state: "ok", files: rest } }, "rest");
  assert.deepEqual(all(secIn(el, "sitemap"), ".af-hf").map((x) => x.textContent), ["3requests", "0%from AI", "-files listed"]);
  assert.match(secIn(el, "sitemap").textContent, /Beyond each day's 50 busiest files: 3 more requests \(2 files, counted per day\)/);
}
{
  // e. The OKF bundle when someone fetched it: the last card and the last section.
  const okf = { kinds: { okf: { requests: 2, status: { "2xx": 2 }, who: { bots: 2 } }, markdown: { requests: 1, status: { "2xx": 1 }, who: { bots: 1 } } },
    names: { bots: { curl: { okf: 2, markdown: 1 } } },
    files: { "/okf/index.md": f1("okf", 2, { "200": 2 }, { bots: 2 }, { curl: 2 }, null), "/a.md": f1("markdown", 1, { "200": 1 }, { bots: 1 }, { curl: 1 }, null) }, rest: {} };
  const el = await render({ days: [], today: { day: TODAY, state: "ok", files: okf } }, "okf");
  assert.deepEqual(all(el, ".af-sec").map((x) => x.getAttribute("data-kind")), ["markdown", "okf"]);
  assert.equal(all(el, ".kpi").at(-1).querySelector(".k-l").textContent, "OKF bundle");
  assert.ok(!heads(secIn(el, "okf").querySelector(".af-files")).includes("Copy of"), "an OKF file is not a page's copy");
}

console.log("agent-files-page: all passed");
