// Change dates on Traffic > Pages (skald/webapp/js/tabs/pagestory.js): the website's
// own updated date, else the sitemap's lastmod said "from your sitemap"; the filter
// "Changed since" (chgfrom= in the address); a page only the sitemap lists.
//
//   node tests/js/page-dates.mjs        (tests/test_sitemap_lastmod.py runs it)
//
// Example data only: made-up paths.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const P = await import(new URL("tabs/pagestory.js", JS));
const { ROUTE_KEYS } = await import(new URL("routekeys.js", JS));

const row = (path, o = {}) => ({ path, title: null, locale: null, published: "2026-10-21", date_source: "first seen", first_seen: "2026-10-21",
  updated: null, updated_source: null, lastmod: null, lastmod_seen: [], days_since_publish: 4, milestones: {}, views_7d: 1, views_30d: 1, readers_30d: 1, ...o });
const idx = { meta: { source: null, generated: null, lastmod: { day: "2026-10-25", dated: 2, missing: 0, invalid: 1, future: 0 } }, pages: [
  row("/a/", { updated: "2026-10-20", updated_source: "sitemap", lastmod: "2026-10-20", lastmod_seen: [["2026-10-20", "2026-10-21"]] }),
  row("/b/", { updated: "2026-10-01", updated_source: "website", lastmod: "2026-10-24" }),
  row("/c/"),
  row("/only/", { published: null, first_seen: null, days_since_publish: null, updated: "2026-10-23", updated_source: "sitemap", lastmod: "2026-10-23" }),
] };
const m = { x: { page_index: idx }, anchor: "2026-10-24", files: ["page_index"], failed: {} };

{
  const el = P.published(m, {});
  const text = el.textContent;
  assert.match(text, /Changed since/);
  assert.match(text, /from your sitemap/);
  assert.match(text, /not seen yet/, "a page only the sitemap lists says so");
  assert.match(text, /a change date, not a publish date/);
  assert.match(text, /2 of the sitemap's pages had one on 25 Oct \(1 with a date that does not parse: left out\)/);
}
{
  const text = P.published(m, { chgfrom: "2026-10-15" }).textContent;
  assert.match(text, /\/a\//);
  assert.match(text, /\/only\//);
  assert.doesNotMatch(text, /\/b\//, "the website's own date (1 Oct) is older than the filter");
  assert.doesNotMatch(text, /\/c\//, "a page with no change date is left out by the filter");
  assert.match(P.published(m, { chgfrom: "2026-10-30" }).textContent, /No page in these dates changed since then/);
}
{
  // no change date anywhere: no column, no filter
  const bare = { ...m, x: { page_index: { meta: { source: null }, pages: [row("/c/")] } } };
  assert.doesNotMatch(P.published(bare, {}).textContent, /Changed/);
}
assert.equal(P.changedWords(idx.pages[0]), "changed 20 Oct (from your sitemap)");
assert.equal(P.changedWords(idx.pages[1]), "updated 1 Oct");
assert.equal(P.changedWords(idx.pages[2]), "");
assert.ok(ROUTE_KEYS.some((k) => k.key === "chgfrom"), "chgfrom is a known address key");
console.log("page dates: ok");
