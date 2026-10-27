// The breadcrumb line and Back (js/crumbs.js): a place is the tab and what is open in it;
// a new place adds a step, a change in place keeps it, a place already on the trail cuts the
// trail back to it, a move along a section's tabs replaces the last step; the trail keeps at
// most 12. With a browser-like history (pushState, Back, Forward and popstate): the line and
// "Back to" follow Back and Forward, a crumb goes to its exact address, each step keeps its
// scroll and Back puts it back. A copied address opened fresh starts from the address alone;
// a reload keeps the tab's trail from sessionStorage.
//
//   node tests/js/crumbs.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });

// ---- a browser's history, its popstate, its scroll and the tab's sessionStorage
const heard = {};
globalThis.addEventListener = (type, fn) => { (heard[type] ||= []).push(fn); };
const fire = (type) => (heard[type] || []).forEach((fn) => fn({ type }));
const entries = [{ state: null, hash: "" }];
let at = 0;
Object.assign(globalThis.history, {
  state: null, scrollRestoration: "auto",
  pushState(s, _, h) { entries.splice(at + 1); entries.push({ state: s, hash: h }); at += 1; this.state = s; location.hash = h; },
  replaceState(s, _, h) { entries[at] = { state: s, hash: h }; this.state = s; location.hash = h; },
  go(n) { at += n; this.state = entries[at].state; location.hash = entries[at].hash; fire("popstate"); },
  back() { this.go(-1); }, forward() { this.go(1); },
});
const session = new Map();
globalThis.sessionStorage = { getItem: (k) => session.get(k) ?? null, setItem: (k, v) => session.set(k, String(v)), removeItem: (k) => session.delete(k) };
let navigation = "navigate";
globalThis.performance = { getEntriesByType: () => [{ type: navigation }] };
globalThis.scrollY = 0;
globalThis.scrollTo = ({ top }) => { globalThis.scrollY = top; };
document.documentElement.scrollHeight = 5000;
const scroll = async (y) => { globalThis.scrollY = y; fire("scroll"); await tick(); };
const tick = (ms = 5) => new Promise((r) => setTimeout(r, ms));
const later = () => tick(1000);   // restore's retries come at 300 and 900 ms

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const C = await import(new URL("crumbs.js", JS));
const U = await import(new URL("urlactions.js", JS));
U.setSiteBase("example.com");

// ---- pure: a place, a step noted, the words
const st = (patch) => ({ ...S.read(), dd: "", page: "", todo: "", part: "", vis: "", lead: "", ...patch });
let p = C.placeOf(st({ tab: "traffic/pages", page: "/pricing/" }));
assert.deepEqual(p.parts, ["Traffic", "Pages", "/pricing/"]);
assert.equal(p.key, "traffic/pages|page=/pricing/");
assert.ok(p.item && p.section === "traffic");
p = C.placeOf(st({ tab: "traffic/sources", dd: "source:Google|country:CA", vis: "2026-10-20.14" }));
assert.equal(p.parts[0], "Traffic");
assert.equal(p.parts[2], "Source: Google");
assert.ok(p.parts[3].startsWith("Country: "), p.parts[3]);
assert.equal(p.parts[4], "A visit on 20 Oct");
assert.deepEqual(C.placeOf(st({ tab: "overview/summary" })).parts, ["Overview", "Summary"]);
assert.equal(C.placeOf(st({ tab: "overview/summary", range: "90d" })).key, C.placeOf(st({ tab: "overview/summary" })).key, "a period is a change in place");

const at_ = (patch, hash) => [C.placeOf(st(patch)), hash];
let t = [];
t = C.note(t, ...at_({ tab: "overview/summary" }, "#overview/summary"));
t = C.note(t, ...at_({ tab: "traffic/sources" }, "#traffic/sources"));
assert.equal(t.length, 2, "another section: a step down");
t = C.note(t, ...at_({ tab: "traffic/places" }, "#traffic/places"));
assert.deepEqual(t.map((x) => x.hash), ["#overview/summary", "#traffic/places"], "along a section's tabs: replaced");
t = C.note(t, ...at_({ tab: "traffic/places", dd: "country:CA" }, "#traffic/places?dd=country:CA"));
t[2].scroll = 420;
t = C.note(t, ...at_({ tab: "traffic/places", dd: "country:CA", range: "90d" }, "#traffic/places?dd=country:CA&range=90d"));
assert.equal(t.length, 3, "a period changed in place: the same step");
assert.equal(t[2].hash, "#traffic/places?dd=country:CA&range=90d", "with its new address");
assert.equal(t[2].scroll, 420, "and its scroll");
t = C.note(t, ...at_({ tab: "traffic/pages", page: "/pricing/" }, "#traffic/pages?page=%2Fpricing%2F"));
t = C.note(t, ...at_({ tab: "traffic/places", dd: "country:CA" }, "#traffic/places?dd=country:CA"));
assert.equal(t.length, 3, "a place on the trail: cut back to it");
assert.equal(t[2].scroll, 420);
for (let i = 0; i < 20; i += 1) t = C.note(t, ...at_({ tab: "traffic/pages", page: `/p${i}/` }, `#traffic/pages?page=%2Fp${i}%2F`));
assert.equal(t.length, C.MOST, "the trail keeps 12");
assert.equal(t.at(-1).parts.at(-1), "/p19/");

const words = [{ parts: ["Traffic", "Sources"] }, { parts: ["Traffic", "Sources", "Source: Google"] }, { parts: ["Traffic", "Pages", "/pricing/"] }];
assert.equal(C.crumbWords(words, 0), "Traffic › Sources");
assert.equal(C.crumbWords(words, 1), "Source: Google", "what it shares with the step before is not said again");
assert.equal(C.crumbWords(words, 2), "Pages › /pricing/");

// A copied address alone: the tab, then the item.
const fresh = C.fromUrl(st({ tab: "traffic/pages", page: "/pricing/" }), null, S.hashFor);
assert.deepEqual(fresh.map((x) => x.parts.join(" › ")), ["Traffic › Pages", "Traffic › Pages › /pricing/"]);
assert.equal(fresh[0].hash, "#traffic/pages");
assert.equal(C.fromUrl(st({ tab: "traffic/pages" }), null, S.hashFor).length, 1);

const GOOGLE = S.hashFor({ ...S.read(), tab: "traffic/sources", dd: "source:Google" });
// ---- in a tab: the line follows the history
const m = { x: {} };
let line = null;
const render = (s) => { line = C.crumbLine(m, s); document.body.replaceChildren(line); C.restore(); };
S.on(render);
const crumbs = () => C.trail().map((x, i, all) => C.crumbWords(all, i));
const back = () => line.querySelector("a.cr-back");

history.replaceState(null, "", "#overview/summary");
C.start();
assert.equal(history.scrollRestoration, "manual", "Skald puts the scroll back itself");
S.emit(true);
assert.ok(line.hidden, "one tab-level step: no line");
await scroll(300);
S.set({ tab: "traffic/sources" });
await tick();
assert.ok(!line.hidden);
assert.equal(back().textContent, "← Back to Summary");
assert.equal(back().getAttribute("href"), "#overview/summary");
S.set({ dd: "source:Google" });
await tick();
await scroll(150);
S.set({ tab: "traffic/pages", page: "/pricing/", dd: "" });
await tick();
await scroll(600);
S.set({ vis: "2026-10-20.14" });
await tick();
assert.equal(C.trail().length, 5);
assert.deepEqual(crumbs().slice(0, 4), ["Overview › Summary", "Traffic › Sources", "Source: Google", "Pages › /pricing/"]);
assert.ok(crumbs()[4].startsWith("A visit on 20 Oct"));
assert.equal(line.querySelectorAll("li").length, 0, "the line is the Back link alone (2.42), never the row of crumbs");
assert.equal(line.children.length, 1);
assert.equal(back().textContent, "← Back to /pricing/");
assert.equal(line.querySelector("a.cr-back").getAttribute("href"), "#traffic/pages?page=%2Fpricing%2F");
await scroll(80);

// Back: the page's view, its scroll put back.
history.back();
await later();
assert.equal(location.hash, "#traffic/pages?page=%2Fpricing%2F");
assert.equal(C.trail().length, 4, "cut back to the page");
assert.equal(scrollY, 600, "Back puts the page's scroll back");
history.back();
await later();
assert.equal(location.hash, GOOGLE);
assert.equal(scrollY, 150);
assert.equal(back().textContent, "← Back to Sources");
// Forward: the page again, a step down, where it was scrolled.
history.forward();
await later();
assert.equal(location.hash, "#traffic/pages?page=%2Fpricing%2F");
assert.equal(C.trail().length, 4);
assert.equal(back().textContent, "← Back to Source: Google");
assert.equal(scrollY, 600, "Forward finds the page's scroll too");

// A scroll while one is being put back is the page's, not the reader's: not saved.
history.back();
fire("scroll");
await later();
assert.equal(C.trail().at(-1).scroll, 150);

// A link to a step on the trail: a new entry, the trail cut back.
const before = at;
S.set({ tab: "overview/summary", dd: "" });
await later();
assert.equal(location.hash, "#overview/summary");
assert.equal(at, before + 1, "a link to a step on the trail pushes an entry");
assert.equal(C.trail().length, 1);
assert.ok(line.hidden);
// (The crumbs that put a step's scroll back are gone in 2.42: Back and Forward still do, above.)
history.back();
await later();
assert.equal(location.hash, GOOGLE, "Back after a crumb: where the crumb was clicked");

// "Back to": the step before, by its address.
S.set({ tab: "traffic/pages", page: "/blog/", dd: "" });
await tick();
back().dispatchEvent(new Event("click"));
await later();
assert.equal(location.hash, GOOGLE);

// ---- a reload keeps the tab's trail; a link opened fresh starts from its address
await tick(80);   // the trail is saved a moment after a visit
const kept = JSON.parse(session.get(C.STORE));
assert.ok(kept.length >= 2);
navigation = "reload";
C.start();
S.emit(true);
assert.equal(C.trail().length, kept.length, "a reload: the same trail");
navigation = "navigate";
history.replaceState(null, "", "#traffic/pages?page=%2Fpricing%2F");
C.start();
S.emit(true);
assert.deepEqual(C.trail().map((x) => x.hash), ["#traffic/pages", "#traffic/pages?page=%2Fpricing%2F"]);
assert.ok(!line.hidden);
assert.equal(back().textContent, "← Back to Pages");

console.log("crumbs: all passed");
