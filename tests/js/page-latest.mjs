// The page story's latest crawl (#44) and time on page from the log (#46)
// (skald/webapp/js/tabs/pagestory.js): latestCrawls, timeOnPageWords.
//
//   node tests/js/page-latest.mjs        (tests/test_page_latest_time.py runs it)
//
// Example data only: made-up times.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const P = await import(new URL("tabs/pagestory.js", JS));

{
  const el = P.latestCrawls({ milestones: { googlebot_latest: { at: "2026-11-11T08:00:00+00:00", status: 200 }, bingbot_latest: null } });
  const text = el.textContent;
  assert.match(text, /Latest crawl/);
  assert.match(text, /Googlebot last fetched it/);
  assert.match(text, /status 200/);
  assert.match(text, /Bingbot has not fetched it since the logs began/, "never fetched is said, never a 0");
}
// An older server sends no latest fetch: nothing is shown.
assert.equal(P.latestCrawls({ milestones: { googlebot: { at: "2026-11-01T08:00:00+00:00" } } }), null);
assert.equal(P.latestCrawls({ local: true }), null);

assert.equal(P.timeOnPageWords(null), "");
assert.equal(P.timeOnPageWords({ median_s: 42, measured: 120, not_measured_last_page: 30, min_measured: 5 }),
  "Time on page: 42 s typical (median) over 120 views measured, from your server log; 30 views were the visit's last page, so not measured.");
assert.equal(P.timeOnPageWords({ median_s: null, measured: 2, not_measured_last_page: 1, min_measured: 5 }),
  "Time on page: not shown, 2 views measured (fewer than 5); 1 view was the visit's last page, so not measured.");
console.log("page latest: ok");
