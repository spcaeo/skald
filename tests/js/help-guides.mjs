// Help (2.42, js/tabs/help.js and js/ui/help.js): the guides' index in a few groups, the
// search with its words in the address (hq), a guide opened at a section (hs), and every
// "Read the guide" or Help link in the app lands on a guide, and on a section, that exist.
//
//   node tests/js/help-guides.mjs
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { install } from "./dom-lite.mjs";

install();
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));
const DATA = (await import(new URL("help-data.js", JS))).default;
const H = await import(new URL("tabs/help.js", JS));
const { help } = await import(new URL("ui/help.js", JS));

const slugs = new Map(DATA.guides.map((g) => [g.id, new Set(g.blocks.filter((b) => b.t === "h2").map((b) => H.slug(b.text)))]));

// ---- the keys
for (const k of ["hs", "hq"]) assert.ok(K.KEYS.has(k) && S.KNOWN().includes(k), `${k} is a known key`);

// ---- every guide is in exactly one group, and the groups name only guides that exist
const named = H.GROUPS.flatMap(([, , ids]) => ids);
for (const id of named) assert.ok(slugs.has(id), `the group names ${id}, a guide`);
assert.equal(new Set(named).size, named.length, "no guide in two groups");
for (const g of DATA.guides) assert.ok(named.includes(g.id), `${g.id} is in a group`);
assert.ok(H.GROUPS.length <= 6, "a few groups");

// ---- every link into Help from the app's code: the guide and its section exist
function* files(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* files(p);
    else if (n.endsWith(".js") && !/^(help|about)-(data|index)\.js$/.test(n)) yield p;
  }
}
const links = [];
const root = new URL(JS).pathname;
for (const f of files(root)) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(/guide: "([^"]+)"/g)) links.push([f, m[1]]);
  for (const m of src.matchAll(/#help\?part=([a-z0-9-]+)(?:&hs=([a-z0-9-]+))?/g)) links.push([f, m[2] ? `${m[1]}#${m[2]}` : m[1]]);
  for (const m of src.matchAll(/\b(?:howTo|helpLink)\("([a-z0-9-]+)"/g)) links.push([f, m[1]]);
}
assert.ok(links.length > 20, `links found: ${links.length}`);
for (const [f, link] of links) {
  const [id, sec] = link.split("#");
  assert.ok(slugs.has(id), `${f.slice(root.length)}: "${link}" names no guide`);
  if (sec) assert.ok(slugs.get(id).has(sec), `${f.slice(root.length)}: "${link}": the guide has no section ${sec}`);
}
assert.ok(links.some(([, l]) => l === "where-visitors-come-from#the-visitor-drawer"), "the visitor drawer's ? lands on its section");
assert.ok(links.some(([, l]) => l === "getting-started#export"), "Export's ? lands on its section");

// ---- a "?" with id#section: Read the guide carries hs
const pop = help("Export", { text: "x", guide: "getting-started#export" });
assert.equal(pop.querySelector("a.ui-help-more").getAttribute("href"), "#help?part=getting-started&hs=export");
assert.equal(help("Nothing", { text: "x", guide: "no-such-guide" }).querySelector("a.ui-help-more"), null, "a guide that does not exist: no link");

// ---- the index: groups, one line per guide, the summary on hover
history.replaceState(null, "", "#help");
const draw = () => { const el = H.default({}, S.read()); document.body.replaceChildren(el); return el; };
let page = draw();
await tick(60);
const groups = page.querySelectorAll(".help-group");
assert.equal(groups.length, H.GROUPS.length);
assert.equal(page.querySelectorAll(".help-group a").length, DATA.guides.length, "one line per guide");
assert.ok(page.querySelectorAll(".help-group a").every((a) => a.getAttribute("title")), "the summary on hover");
assert.ok(!page.querySelector(".help-card"), "no wall of cards");
assert.ok(page.querySelectorAll("button.ui-help").length === 1, "the page's words behind ?");

// ---- the search: its words in the address; results with their sections
const q = page.querySelector("input.help-q");
q.value = "calendly";
q.dispatchEvent(new Event("input"));
await tick(30);
assert.equal(S.read().hq, "calendly", location.hash);
assert.ok(location.hash.includes("hq=calendly"));
const found = page.querySelectorAll(".help-found > li, .help-found li.ui-card");
assert.ok(found.length >= 1, "guides found");
const first = page.querySelector(".help-found a.help-ft");
assert.match(first.getAttribute("href"), /^#help\?part=[a-z0-9-]+(&hs=[a-z0-9-]+)?$/);
const where = page.querySelectorAll(".help-in a");
assert.ok(where.length >= 1, "Found in: the sections");
for (const a of where) {
  const [, id, sec] = /part=([a-z0-9-]+)&hs=([a-z0-9-]+)/.exec(a.getAttribute("href"));
  assert.ok(slugs.get(id).has(sec), `${id}#${sec}`);
}
// A link with hq opens the same results.
history.replaceState(null, "", "#help?hq=calendly");
page = draw();
await tick(30);
assert.equal(page.querySelector("input.help-q").value, "calendly");
assert.ok(page.querySelector(".help-found"));
q.value = "zzzz qqqq";
history.replaceState(null, "", "#help?hq=zzzz%20qqqq");
page = draw();
await tick(30);
assert.match(page.textContent, /No guide mentions "zzzz qqqq"/);

// ---- a guide at a section: the contents links carry hs, and the section has its id
history.replaceState(null, "", "#help?part=getting-started&hs=export");
page = draw();
await tick(30);
assert.ok(page.querySelector("#help-getting-started-export") || page.querySelectorAll("h2").some((x) => x.id === "help-getting-started-export"), "the section's anchor");
const toc = page.querySelector(".help-toc");
assert.ok(toc.querySelectorAll("a").some((a) => a.getAttribute("href") === "#help?part=getting-started&hs=export"), "the contents line links by hs");

console.log("help-guides: all passed");
process.exit(0);
