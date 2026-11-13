// #33: Leads & sales went from eight tabs to four (Leads, Summary, Revenue, Funnels). Every old
// address still opens the same view (js/routes.js, js/state.js): Sources is Summary's "Where
// they came from" fold, open; Calendar bookings is Leads with What: Demos (or the booking it
// named), its left-out rows when a list was asked for; Events is Traffic › Events; Find a
// person is Leads with its search box focused. #32: Summary's "Count from" and Status are gone,
// so an old link that carries them opens Summary itself. The new address takes the old one's
// place (replaceState), so Back never lands on the old one and loops; Back and Forward work
// between the new ones.
//
//   node tests/js/sales-routes.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
// A history that keeps its entries, so Back is Back.
const H = { stack: [{ state: null, hash: "" }], at: 0 };
globalThis.history = {
  get state() { return H.stack[H.at].state; },
  pushState(state, _, hash) { H.stack.splice(H.at + 1); H.stack.push({ state, hash }); H.at += 1; location.hash = hash; },
  replaceState(state, _, hash) { H.stack[H.at] = { state, hash }; location.hash = hash; },
  back() { if (H.at > 0) { H.at -= 1; location.hash = H.stack[H.at].hash; } },
  forward() { if (H.at < H.stack.length - 1) { H.at += 1; location.hash = H.stack[H.at].hash; } },
  go() {},
};
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const K = await import(new URL("routekeys.js", JS));

const split = (h) => { const [route, q = ""] = h.replace(/^#/, "").split("?"); return [route, Object.fromEntries(new URLSearchParams(q))]; };
// Open an old address the way a browser does: it lands, the app reads it and writes the new one.
function open(hash) {
  history.pushState(null, "", hash);
  S.emit(true);
  return split(location.hash);
}

// ---- the four tabs, in order; the moved ones are gone from the section, Events is on Traffic
const SALES = S.SECTIONS.find((x) => x.key === "sales").tabs.map(([k]) => k);
assert.deepEqual(SALES, ["sales/leads", "sales/summary", "sales/revenue", "sales/funnels"]);
assert.ok(S.SECTIONS.find((x) => x.key === "traffic").tabs.some(([k, name]) => k === "traffic/events" && name === "Events"), "Events is under Traffic");

// ---- every old address opens its new view, with its own keys
const TABLE = [
  ["#sales/sources", "sales/summary", { lpart: "sources" }],
  ["#sales/sources?lact=signup&llabel=sales", "sales/summary", { lpart: "sources", lact: "signup", llabel: "sales" }],
  ["#sales/sources?lsrc=db&lstage=won", "sales/summary", { lpart: "sources" }],
  ["#sales/bookings", "sales/leads", { lact: "demo" }],
  ["#sales/bookings?bact=paid", "sales/leads", { lact: "paid" }],
  ["#sales/bookings?bact=demo&bshow=cancelled,test", "sales/leads", { lact: "demo", lshow: "out" }],
  ["#sales/bookings?range=30d", "sales/leads", { lact: "demo", range: "30d" }],
  ["#sales/events", "traffic/events", {}],
  ["#sales/events?range=7d&path=%2Fpricing%2F", "traffic/events", { range: "7d", path: "/pricing/" }],
  ["#events", "traffic/events", {}],
  ["#sales/people", "sales/leads", { lfind: "1" }],
  ["#leads", "sales/summary", {}],
  ["#conversions", "sales/summary", {}],
  ["#sales/summary?lsrc=all&lact=demo", "sales/summary", { lact: "demo" }],
  ["#sales/summary?lsrc=db", "sales/summary", {}],
  ["#sales/pipeline?lsrc=all&lact=demo&llabel=sales", "sales/summary", { lact: "demo", llabel: "sales" }],
  ["#sales/pipeline", "sales/summary", {}],
  ["#sales", "sales/leads", {}],
  // The four keep their own addresses as they are.
  ["#sales/leads?lact=signup&lview=board", "sales/leads", { lact: "signup", lview: "board" }],
  ["#sales/summary?lpart=sources", "sales/summary", { lpart: "sources" }],
  ["#sales/revenue?rby=campaign&cur=USD", "sales/revenue", { rby: "campaign", cur: "USD" }],
  ["#sales/revenue?by=campaign", "sales/revenue", { rby: "campaign" }],
  ["#sales/funnels?fn=%2F%3E%2Fpricing%2F&fsrc=Email", "sales/funnels", { fn: "/>/pricing/", fsrc: "Email" }],
];
for (const [old, route, params] of TABLE) {
  const [got, q] = open(old);
  assert.deepEqual([got, q], [route, params], `${old} opens ${route} ${JSON.stringify(params)}: got ${location.hash}`);
  assert.equal(S.read().tab, route);
}

// ---- the new address takes the old one's place: Back goes to the page before, never the old one
location.hash = "";
H.stack = [{ state: null, hash: "#overview/summary" }]; H.at = 0;
location.hash = "#overview/summary";
open("#sales/bookings?bact=demo");
assert.equal(H.stack.length, 2, "one entry for the old address, rewritten in place");
assert.equal(H.stack[1].hash, "#sales/leads?lact=demo");
S.set({ tab: "sales/summary" });
assert.equal(location.hash, "#sales/summary?lact=demo", "What: Demos rides along: Summary keeps it too");
history.back(); S.emit();
assert.equal(location.hash, "#sales/leads?lact=demo", "Back: the bookings view, at its new address");
history.back(); S.emit();
assert.equal(location.hash, "#overview/summary", "Back again: where the reader came from, not the old address");
history.forward(); S.emit();
assert.equal(location.hash, "#sales/leads?lact=demo", "Forward works too");

// ---- the keys: the new ones are listed, the gone ones are not read any more
for (const k of ["lpart", "lfind"]) assert.ok(K.KEYS.has(k), `${k} is in js/routekeys.js`);
for (const k of ["lsrc", "lstage", "bact", "bshow"]) assert.ok(!S.KNOWN().includes(k), `${k} is no longer read`);
for (const k of S.KNOWN()) assert.ok(K.KEYS.has(k), `${k} is listed in js/routekeys.js`);

// ---- links drawn to the old routes still land: the shortcuts and the set-up card's "See bookings"
assert.equal(S.route("sales/bookings").tab, "sales/leads");
assert.equal(S.nameOf("sales/events"), "Events");
assert.equal(S.nameOf("sales/sources"), "Summary");
assert.equal(S.nameOf("sales/people"), "Leads");

// ---- no compare by default on Leads & sales: every period there holds today (#32)
for (const tab of SALES) {
  open(`#${tab}?range=30d`);
  assert.equal(S.read().cmp, "", `${tab}: no compare by default`);
}
open("#traffic/sources?range=30d");
assert.equal(S.read().cmp, "prev", "Traffic keeps its default compare");

console.log("sales-routes: all passed");
