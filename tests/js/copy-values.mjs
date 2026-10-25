// Copy on every value someone may paste elsewhere (2.35, the owner's rule of 2026-10-25):
// a URL or a site path gets copy and open (js/urlactions.js withUrl), an IP address, a user
// agent, an email, a name, a crawler, a search term, a campaign, a reference or a reason
// gets the copy icon alone (copyCell, copyIf, copyFact), the same look and the same tick.
// Labels, numbers and blanks get none. The main tables and drawers are drawn here with
// sample data, and the test fails when a known kind is drawn without its icons; the code
// is read so a raw address, email or user agent in a cell or a fact cannot come back.
//
//   node tests/js/copy-values.mjs
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const U = await import(new URL("urlactions.js", JS));
const { table } = await import(new URL("table.js", JS));
const { blist } = await import(new URL("tabs/common.js", JS));
const { ME } = await import(new URL("access.js", JS));
U.setSiteBase("example.com");
const copied = [];
Object.defineProperty(globalThis.navigator, "clipboard", { configurable: true, value: { writeText: async (t) => { copied.push(t); } } });
const tick = () => new Promise((r) => setImmediate(r));

const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15";
// What a node holds: copy-only, copy and open, or nothing.
const icons = (el) => {
  const copy = el.querySelectorAll ? el.querySelectorAll("button.ua-copy").length : 0;
  const open = el.querySelectorAll ? el.querySelectorAll("a.ua-open").length : 0;
  return open ? "copy+open" : copy ? "copy" : "none";
};
const copyOf = (el) => el.querySelector("button.ua-copy")?.getAttribute("title")?.replace(/^Copy /, "");

// ---- the column kinds: by key, by label, by a drilled value; numbers and dates never
const kindOf = U.copyKind;
assert.equal(kindOf({ key: "ip", label: "From" }), "ip");
assert.equal(kindOf({ key: "who", label: "Address" }), "ip");
assert.equal(kindOf({ key: "agent", label: "User agent" }), "ua");
assert.equal(kindOf({ key: "email", label: "Contact" }), "email");
for (const label of ["Name", "Crawler", "Assistant", "Query", "Search term", "Campaign", "Reference", "Visitor ID", "Network", "Host", "Why", "Competitor", "Question"]) assert.equal(kindOf({ key: "x", label }), "text", label);
for (const drill of ["bot", "referrer", "campaign", "assistant"]) assert.equal(kindOf({ key: "k", label: "Thing", drill }), "text", drill);
assert.equal(kindOf({ key: "k", label: "Thing", drill: "ip" }), "ip");
for (const c of [{ key: "v", label: "Visits", num: true }, { key: "at", label: "Name", type: "date" }, { key: "path", label: "Name", path: true },
  { key: "k", label: "Source", drill: "source" }, { key: "k", label: "Country" }, { key: "ip", label: "Address", copy: false }]) assert.equal(kindOf(c), null, JSON.stringify(c));
assert.equal(kindOf({ key: "k", label: "Device", copy: true }), "text");

// ---- a table of every kind: the right icons on each cell, none on a blank or a number
{
  const cols = [
    { key: "ip", label: "Address" }, { key: "agent", label: "User agent", fmt: (v) => String(v).slice(0, 20) }, { key: "email", label: "Email" },
    { key: "path", label: "Page", path: true }, { key: "url", label: "Cited", url: true }, { key: "bot", label: "Crawler", drill: "bot" },
    { key: "q", label: "Query" }, { key: "src", label: "Source" }, { key: "n", label: "Visits", num: true },
  ];
  const rows = [
    { ip: "192.0.2.10", agent: UA, email: "ana@example.com", path: "/pricing/", url: "https://news.example.org/a", bot: "ChatGPT-User", q: "server log analytics", src: "Search engine", n: 4 },
    { ip: "(removed)", agent: "", email: "-", path: "(all others)", url: "", bot: "", q: "-", src: "Direct", n: 1 },
  ];
  const t = table(cols, { caption: "Kinds", rows, ns: false, sortKey: "n" });
  const [full, blank] = t.querySelectorAll("tbody tr");
  const want = ["copy", "copy", "copy", "copy+open", "copy+open", "copy", "copy", "none", "none"];
  assert.deepEqual(full.children.map(icons), want, "each kind its icons");
  assert.deepEqual(blank.children.map(icons), want.map(() => "none"), "a blank, a removed address or a folded row: none");
  // The copy writes the whole value: the full user agent behind a shortened cell, the address, the words shown.
  assert.equal(copyOf(full.children[0]), "192.0.2.10");
  assert.equal(copyOf(full.children[1]), UA, "the full user agent, not the shortened cell");
  assert.equal(copyOf(full.children[2]), "ana@example.com");
  assert.equal(copyOf(full.children[3]), "https://example.com/pricing/");
  assert.equal(copyOf(full.children[5]), "ChatGPT-User", "a drilled crawler: its own name, not its link's words");
  assert.equal(copyOf(full.children[6]), "server log analytics");
  // Pressing it copies and ticks, and the row's own click never hears it.
  let rowClicks = 0;
  full.addEventListener("click", () => { rowClicks += 1; });
  full.children[0].querySelector("button.ua-copy").click();
  await tick();
  assert.deepEqual(copied, ["192.0.2.10"]);
  assert.ok(full.children[0].querySelector(".ua").classList.contains("ua-ok"), "the green tick");
  assert.equal(rowClicks, 0);
  // Keyboard and screen reader: a real button with its label.
  const b = full.children[1].querySelector("button.ua-copy");
  assert.equal(b.getAttribute("type"), "button");
  assert.match(b.getAttribute("aria-label"), /^Copy user agent Mozilla\/5\.0/);
  // An address that is not one (a "Not shown" line) gets none; an email column of names gets none.
  const odd = table([{ key: "ip", label: "Address" }, { key: "email", label: "Email" }], { caption: "Odd", rows: [{ ip: "Not shown (12 Oct #3)", email: "Ana" }], ns: false });
  assert.deepEqual(odd.querySelector("tbody tr").children.map(icons), ["none", "none"]);
}

// ---- bar lists: a drilled referrer, an address or a list of user agents
{
  const ul = blist([["news.example.org", 9], ["(none)", 2]], { drill: "referrer" });
  assert.deepEqual(ul.querySelectorAll("li").map(icons), ["copy", "none"]);
  const uas = blist([[UA, 5]], { copy: "ua" });
  assert.equal(copyOf(uas.querySelector("li")), UA);
  const src = blist([["Search engine", 5]], { drill: "source" });
  assert.equal(icons(src), "none", "a source type is a label");
}

// ---- drawers and screens, drawn with sample data
ME.role = "owner";
{
  // Find a person: every address, email, visitor ID and lead it linked.
  const { personParts } = await import(new URL("tabs/person.js", JS));
  const got = { query: { kind: "ip", value: "192.0.2.10" }, keys: { ips: ["192.0.2.10"], emails: ["ana@example.com"], vids: ["v-1a2b3c"], leads: ["14"] }, kept: { keep_ips: true, ip_mode: "full", keep_days: 30, identity: "full" },
    visits: [], requests: [{ at: "2026-10-24T10:00:00Z", method: "GET", path: "/pricing/", status: 200, group: "people" }],
    leads: [{ id: 14, created_at: "2026-10-24T10:02:00Z", type: "demo", status: "new", page: "/demo/", first_source: "Search engine", last_source: "Direct", email: "ana@example.com", name: "Ana Example" }],
    candidates: [{ lead: 14, ip: "192.0.2.10", start: "2026-10-24T10:00:00Z", landing: "/pricing/" }],
    conversions: [{ id: 3, at: "2026-10-24T10:02:00Z", action: "demo", stage: "completed", tool: "lead", source_type: "Direct", landing: "/demo/", external_ref: "u-1001", vid: "v-1a2b3c", email: "ana@example.com" }],
    removed: [], journeys: [{ at: "2026-10-24T10:00:00Z", path: "/pricing/", source_type: "Direct" }] };
  const box = document.createElement("div");
  box.append(...personParts(got));
  const linked = box.querySelector("dl.dw-dl");
  assert.deepEqual(linked.querySelectorAll("dd").map(icons), ["copy", "copy", "copy", "copy"], "Linked: addresses, emails, visitor IDs, leads");
  const copiedWords = box.querySelectorAll("button.ua-copy").map((x) => x.getAttribute("title"));
  for (const v of ["192.0.2.10", "ana@example.com", "v-1a2b3c", "u-1001", "Ana Example"]) assert.ok(copiedWords.includes(`Copy ${v}`), `${v} has its copy icon`);
  assert.ok(box.querySelectorAll("a.ua-open").map((a) => a.getAttribute("href")).includes("https://example.com/demo/"), "a lead's page opens");
  assert.equal(box.querySelectorAll(".ua-host .ua-host").length, 0, "never two icons on one value");
}
{
  // Security > Scanners: the address and the user agent in the table.
  const { rowsTable } = await import(new URL("tabs/sec-scanners.js", JS));
  const t = rowsTable([{ ip: "198.51.100.7", agent: UA, country: "CA", first: "2026-10-24T01:00:00Z", last: "2026-10-24T02:00:00Z", requests: 40, probes: 12, categories: { wp: 12 }, status: { "4xx": 40 }, days: ["2026-10-24"], refs: ["2026-10-24#1"] }], {}, {});
  const heads = t.querySelectorAll("thead th").map((x) => x.textContent);
  const cells = t.querySelector("tbody tr").children;
  const at = (name) => cells[heads.findIndex((x) => x.startsWith(name))];
  assert.equal(copyOf(at("Address")), "198.51.100.7");
}
{
  // Leads > List: name and email.
  const { columnsFor } = await import(new URL("tabs/sa-leads.js", JS));
  const t = table(columnsFor(true), { caption: "Leads", rows: [{ at: "2026-10-24T10:02:00Z", name: "Ana Example", email: "ana@example.com", action: "demo", now: "new", tool: "lead", source: "Direct", first_source: "Direct", landing: "/demo/", country: "CA" }], ns: false });
  const words = t.querySelectorAll("button.ua-copy").map((x) => x.getAttribute("title"));
  assert.ok(words.includes("Copy Ana Example") && words.includes("Copy ana@example.com"), words.join(" | "));
  assert.ok(t.querySelectorAll("a.ua-open").length, "the landing page opens");
}
{
  // The visit's own facts (the visitor drawer): its referrer, campaign, tags and search words.
  const { visitFacts } = await import(new URL("tabs/visitlist.js", JS));
  const box = document.createElement("div");
  box.append(...visitFacts({ country: "CA", device: "Desktop", browser: "Safari", os: "macOS", source: "Referral", via: "news.example.org", ref_page: "news.example.org/a/", campaign: "autumn", utm: { source: "news" }, search_terms: "log analytics", exit: "/thanks/", trail: [] }));
  const facts = Object.fromEntries(box.querySelectorAll("dt").map((dt, i) => [dt.textContent, box.querySelectorAll("dd")[i]]));
  assert.equal(icons(facts["Came from"]), "copy");
  assert.equal(icons(facts["Referring page"]), "copy+open");
  assert.equal(icons(facts.Campaign), "copy");
  assert.equal(icons(facts.Tags), "copy");
  assert.equal(icons(facts["Searched for"]), "copy");
  assert.equal(icons(facts["Ended on"]), "copy+open");
  assert.equal(icons(facts.Country), "none", "a country is a label");
}

// ---- the code: no address, email or user agent drawn raw in a cell or a fact, and no second copy helper
const files = [...readdirSync(new URL("tabs/", JS)).map((f) => `tabs/${f}`), ...readdirSync(JS)].filter((f) => f.endsWith(".js"));
const RAW = /h\("(td|dd)", (null|\{[^}]*\}), [a-z]+\.(ip|email|agent|user_agent)( \|\||\)|,)/;
// Buttons that copy a whole block (a snippet, the steps, a mail) are labelled buttons of their own.
const BLOCK_COPY = new Set(["urlactions.js", "extras.js", "tabs/setup-common.js", "tabs/conn-ui.js", "tabs/crawlers.js", "tabs/account.js", "tabs/setup-privacy.js", "tabs/forms.js", "tabs/agent-setup.js", "tabs/prefs.js", "tabs/search-connect.js"]);
for (const f of files) {
  const src = readFileSync(new URL(f, JS), "utf8");
  for (const line of src.split("\n")) assert.ok(!RAW.test(line), `${f}: a raw value without its copy icon: ${line.trim().slice(0, 140)}`);
  if (!BLOCK_COPY.has(f)) assert.ok(!/clipboard\.writeText/.test(src), `${f}: copies by itself; use withCopy/copyIf from urlactions.js`);
}
// The table builders hand every cell to copyCell, the bar list to copyIf.
for (const [f, re] of [["table.js", /copyCell\(c, r, shown\)/], ["grid.js", /copyCell\(c, r, cell\(c, r\)/], ["tabs/common.js", /copyIf\(kind, lab/]]) assert.match(readFileSync(new URL(f, JS), "utf8"), re, f);
console.log("copy-values: all passed");
