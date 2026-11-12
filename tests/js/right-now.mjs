// Overview's Right now card (#43, js/tabs/ov-rightnow.js): the people on the site now, the
// page each is on, New / Returning / Lead / Customer pills, time on the site, the count's age,
// the fold for the rest, and Refresh now asking the hook and then Real time again.
//
//   node tests/js/right-now.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "overview", name: "Overview", tabs: [{ route: "overview/summary", name: "Summary" }] }]);
const R = await import(new URL("tabs/ov-rightnow.js", JS));
const RT = await import(new URL("tabs/realtime.js", JS));
const hook = await import(new URL("refresh-hook.js", JS));
const UA = await import(new URL("urlactions.js", JS));
UA.setSiteBase("www.example.com");
const text = (el) => (el == null ? "" : el.textContent);

const v = (start, seq, city, trail, last, extra = {}) => ({ start, seq, country: city.slice(-2), city, device: "Desktop", source: "Search engine", via: "google.com",
  landing: trail[0], pages: trail.length, trail, last, active: "5", returning: false, days_seen: 1, first_touch: null, ...extra });
const UNTIL = "2026-11-12T11:00:00-05:00";
const A = v("2026-11-12T10:52:00-05:00", 7, "Toronto, Ontario, CA", ["/", "/features/", "/pricing/"], "2026-11-12T10:59:40-05:00",
  { returning: true, days_seen: 3, first_touch: { by: "vid", day: "2026-11-03", source: "Search engine", via: "google.com" } });
const B = v("2026-11-12T10:59:30-05:00", 9, "Austin, Texas, US", ["/blog/ai-crawlers/"], "2026-11-12T10:59:50-05:00", { via: "chatgpt.com", source: "AI assistant" });
const C = v("2026-11-12T10:20:00-05:00", 4, "London, England, GB", ["/", "/contact/"], "2026-11-12T10:40:00-05:00", { active: "30", returning: null, via: "", source: "Direct or unknown" });
const many = Array.from({ length: 5 }, (_, i) => v(`2026-11-12T10:1${i}:00-05:00`, 20 + i, "Paris, Ile-de-France, FR", ["/"], `2026-11-12T10:3${i}:00-05:00`, { active: "30" }));
const body = (doing) => ({ ok: true, people_state: "ok", people: { until: UNTIL, short: 5, minutes: 30, active: { 5: 2, 30: doing.length },
  per_minute: [{ at: "2026-11-12T10:58", under_way: 1, started: 0 }, { at: "2026-11-12T10:59", under_way: 2, started: 1 }], doing } });

// ---- the pieces
assert.equal(R.agoWords(UNTIL, Date.parse(UNTIL) + 2000), "just now");
assert.equal(R.agoWords(UNTIL, Date.parse(UNTIL) + 40000), "40 s ago");
assert.equal(R.agoWords(UNTIL, Date.parse(UNTIL) + 6 * 60000), "6 min ago");
assert.equal(R.stayWords(A), "8 min");
assert.equal(R.stayWords(B), "under a minute");
assert.equal(R.nowOn(A), "/pricing/", "the page they are on now is the last one");
assert.deepEqual(R.ordered([C, A, B]).map((x) => x.seq), [7, 9, 4], "here now first, then the rest of the 30 minutes");

// New / Returning from the visit's own label; unknown stays unknown (no pill)
let who = R.whoOf(A, []);
assert.deepEqual(who.pills.map((p) => p[1]), ["Returning"]);
assert.match(who.line, /seen on 3 of the last 30 days/);
assert.match(who.line, /first came from/);
assert.deepEqual(R.whoOf(B, []).pills.map((p) => p[1]), ["New"]);
assert.deepEqual(R.whoOf(C, []).pills, [], "returning not recorded: no pill, never New");
// Lead or Customer: #31's mark on the matching journey of the page (same day and place in it)
const journeys = [{ day: "2026-11-12", seq: 7, won: "lead" }, { day: "2026-11-12", seq: 9, won: "customer" }, { day: "2026-11-11", seq: 4, won: "lead" }];
assert.deepEqual(R.whoOf(A, journeys).pills.map((p) => p[1]), ["Returning", "Lead"]);
assert.deepEqual(R.whoOf(B, journeys).pills.map((p) => p[1]), ["New", "Customer"]);
assert.deepEqual(R.whoOf(C, journeys).pills, [], "another day's visit with the same place is not this one");

// ---- the card
location.hash = "#overview/summary";
RT._state.body = body([C, A, B, ...many]);
RT._state.at = Date.now();
let asked = 0;
hook.setRefresh(async () => { asked += 1; return { ok: true, result: "ran" }; });
const card = R.rightNow({ journeys }, S.read());
document.body.append(card);
assert.match(text(card.querySelector(".rn-big")), /^2people on your site now/);
assert.equal(text(card.querySelector(".rn-30")), "8 in the last 30 minutes");
assert.equal(card.querySelectorAll(".td-bar").length, 2);
assert.match(text(card.querySelector(".rn-clock")), /^Updated /, "how old the count is");
const rows = [...card.querySelector(".rn-list").children];
assert.equal(rows.length, R.SHOWN, "the first six open");
assert.match(text(rows[0]), /Toronto/);
assert.match(text(rows[0]), /Returning/);
assert.match(text(rows[0]), /Lead/);
assert.match(text(rows[0].querySelector(".rn-now")), /^Now on \/pricing\//);
assert.ok(rows[0].querySelector(".ua-host"), "the page has its copy and open icons");
assert.match(text(rows[0].querySelector(".rn-meta")), /8 min · 3 pages · google\.com/);
assert.match(text(rows[1]), /Customer/);
assert.match(text(rows[2].querySelector(".rn-now")), /^Last on /, "someone not active in 5 minutes says last on");
assert.match(text(card.querySelector(".rn-more summary")), /Everyone else in the last 30 minutes \(2\)/, "the rest in a fold");
// Refresh now: asks the hook once, says so
const btn = card.querySelector(".rn-refresh");
assert.match(text(btn), /Refresh now/);
btn.click();
await new Promise((ok) => setTimeout(ok, 400));
assert.equal(asked, 1, "Refresh now ran the recount");
assert.match(text(card.querySelector(".rn-said")), /Counted just now/);
assert.match(text(btn), /Refresh now/, "the button is back");
// Nobody here
RT._state.body = body([]);
const empty = R.rightNow({ journeys: [] }, S.read());
assert.match(text(empty.querySelector(".rn-list")), /Nobody has been on the site in the last 30 minutes/);
console.log("right-now: all passed");
process.exit(0);
