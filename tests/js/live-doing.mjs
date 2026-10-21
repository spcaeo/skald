// Overview > Summary, Live (2.20, js/tabs/ov-doing.js): "What visitors are doing now". The
// newest visitors' paths (folded in the middle when long, the page they are on now marked),
// the pages read in the last 30 minutes beside them, the live diff (a new visitor slides in, a
// visitor who moved gets the new page), the drill-down narrowing the list (dd=country:CA) and
// the line that says a filter cannot apply. dom-lite throws on a null child.
//
//   node tests/js/live-doing.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "overview", name: "Overview", tabs: [{ route: "overview/summary", name: "Summary" }] }]);
const D = await import(new URL("tabs/ov-doing.js", JS));
const { mapRows } = await import(new URL("tabs/ov-today-cards.js", JS));
const text = (el) => (el == null ? "" : el.textContent);

const v = (start, country, city, trail, last, extra = {}) => ({ start, seq: Number(start.slice(-2)), country, city, device: "Desktop", source: "Search engine", via: "google.com",
  landing: trail[0], pages: trail.length, trail, last, active: "5", ...extra });
const UNTIL = "2026-10-21T11:00:00-04:00";
const A = v("2026-10-21T10:50", "CA", "Toronto, Ontario, CA", ["/", "/pricing/", "/book-a-demo/"], "2026-10-21T10:59:40-04:00");
const B1 = v("2026-10-21T10:41", "US", "Austin, Texas, US", ["/", "/features/", "/pricing/", "/blog/", "/signup/", "/contact/"], "2026-10-21T10:58:00-04:00");
const C = v("2026-10-21T10:30", "GB", "", ["/blog/ai-crawlers-explained/"], "2026-10-21T10:40:00-04:00", { active: "30", via: "", source: "Direct or unknown" });
const body = (doing) => ({ people_state: "ok", people: { until: UNTIL, doing, pages: { "/pricing/": 4, "/": 3, "/a/very/long/path/that/goes/on/and/on/and/on/and/on/for/ever/": 1 }, page_views: 8 } });

// ---- folding and cutting
assert.deepEqual(D.folded(["/", "/a", "/b"]), ["/", "/a", "/b"]);
assert.deepEqual(D.folded(["/", "/a", "/b", "/c", "/d", "/e"]), ["/", "…", "/d", "/e"], "a long path folds in the middle");
assert.ok(D.middle("/a/very/long/path/that/goes/on/and/on/and/on/and/on/for/ever/").includes("…"));
assert.ok(D.middle("/a/very/long/path/that/goes/on/and/on/and/on/and/on/for/ever/").endsWith("ever/"), "the end of a path stays");

// ---- the rows
location.hash = "#overview/summary";
const card = D.doingCard({ journeys: [] }, { pause() {} }, false);
document.body.append(card.el);
card.draw(body([A, B1, C]));
let rows = card.el.querySelectorAll(".td-paths li");
assert.equal(rows.length, 3);
assert.match(text(rows[0]), /Toronto/);
assert.equal(rows[0].querySelector(".td-st.now").textContent, "/book-a-demo/", "the page they are on now");
assert.match(text(rows[0].querySelector(".td-pnow")), /now on \/book-a-demo\/ · 20 s ago/);
assert.equal(rows[1].querySelectorAll(".td-st").map((x) => x.textContent).join(" "), "/ … /signup/ /contact/", "folded in the middle");
assert.equal(rows[1].querySelector(".td-steps").getAttribute("title"), B1.trail.join(" → "), "the whole path in its tooltip");
assert.match(text(card.el.querySelector(".td-pg")), /Pages read in the last 30 minutes8 page views by visitors/);

// ---- live: a visitor who moved gets the new page; a new one slides in at the top; at most 5
const A2 = { ...A, trail: [...A.trail, "/thanks/"], pages: 4, last: "2026-10-21T11:00:00-04:00" };
const N = v("2026-10-21T10:59", "DE", "Munich, Bavaria, DE", ["/"], "2026-10-21T11:00:00-04:00");
card.draw(body([N, A2, B1, C, v("2026-10-21T10:10", "FR", "", ["/"], "2026-10-21T10:35:00-04:00"), v("2026-10-21T10:05", "ES", "", ["/"], "2026-10-21T10:34:00-04:00")]));
rows = card.el.querySelectorAll(".td-paths li").filter((li) => !li.classList.contains("td-out"));
assert.equal(rows.length, D.SHOWN, "the five newest");
assert.equal(rows[0].dataset.k, D.keyOf(N));
assert.ok(rows[0].classList.contains("td-in"), "a new visitor slides in");
assert.ok(rows[1].querySelector(".td-st.now.td-step-new"), "the new page is appended with its animation");
assert.equal(rows[1].querySelector(".td-st.now").textContent, "/thanks/");

// ---- a page on the right narrows the list to the visitors who read it
card.el.querySelectorAll(".td-pgr .td-path").find((b) => b.textContent === "/pricing/").click();
rows = card.el.querySelectorAll(".td-paths li").filter((li) => !li.classList.contains("td-out"));
assert.ok(rows.every((li) => /\/pricing\//.test(li.querySelector(".td-steps").getAttribute("title"))), "only who read /pricing/");
assert.match(text(card.el.querySelector(".td-pick")), /Read \/pricing\//);
card.el.querySelector(".td-pick button").click();

// ---- the drill-down: dd=country:CA shows only the Canadian visitors, and says so
location.hash = "#overview/summary?dd=country%3ACA";
const ca = D.doingCard({ journeys: [] }, { pause() {} }, false);
ca.draw(body([N, A2, B1, C]));
rows = ca.el.querySelectorAll(".td-paths li");
assert.equal(rows.length, 1);
assert.match(text(rows[0]), /Toronto/);
assert.match(text(ca.el.querySelector(".td-note")), /Only the visitors matching .*CAN: 1 shown\./, "the total is the rows shown");
assert.match(text(ca.el.querySelector(".td-pg")), /not split by the filter/);
const map = mapRows({ countries: { CA: { visits: 3, active: 1 }, US: { visits: 9, active: 2 } }, cities: { "Toronto, Ontario, CA": { visits: 2, active: 1 }, "Austin, Texas, US": { visits: 4, active: 1 } } }, S.read().dd ? [["country", "CA"]] : []);
assert.deepEqual(Object.keys(map.countries), ["CA"], "the map keeps that country");
assert.deepEqual(Object.keys(map.cities), ["Toronto, Ontario, CA"]);

// ---- a kind the live rows do not carry: one quiet line, everyone shown
location.hash = "#overview/summary?dd=campaign%3Afall-launch";
const camp = D.doingCard({ journeys: [] }, { pause() {} }, false);
camp.draw(body([N, A2, B1]));
assert.equal(camp.el.querySelectorAll(".td-paths li").length, 3);
assert.equal(text(camp.el.querySelector(".td-note")), "Live list shows every visitor: this filter can't apply to it.");

// ---- nobody active, and no answer yet: one line each
location.hash = "#overview/summary";
const none = D.doingCard({ journeys: [] }, { pause() {} }, false);
none.draw(body([]));
assert.match(text(none.el.querySelector(".td-paths")), /Nobody has been on the site in the last 30 minutes/);
none.draw(null);
assert.match(text(none.el.querySelector(".td-paths")), /appear with the next live count/);
console.log("live-doing: all passed");
