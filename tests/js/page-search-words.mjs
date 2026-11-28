// Finding a page by its full address or its title (SKALD-70, js/search-words.js and the
// titles in js/page-dates.js): an address on the site is also looked for as its path (with
// or without www., with or without the scheme), a #fragment is dropped, a ?query is kept
// for rows that show queries; another site's address stays plain text. A page's title sits
// under its path in the Pages tables, so the search finds it; the hint says what it finds.
//
//   node tests/js/page-search-words.mjs      (tests/test_page_search_js.py runs it)
//
// Example data only: example.com, made-up paths and titles.
import assert from "node:assert/strict";
import { install, Ev } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const W = await import(new URL("search-words.js", JS));
const D = await import(new URL("page-dates.js", JS));
const { table } = await import(new URL("table.js", JS));
const { h } = await import(new URL("ui.js", JS));
const S = await import(new URL("state.js", JS));
S.addSections([{ key: "traffic", name: "Traffic", tabs: [{ route: "traffic/pages", name: "Pages" }] }]);
location.hash = "#traffic/pages";

W.setSearchHosts("www.example.com", ["www.example.com", "example.com"]);
const row = "/data-migration/export-salesforce-data/ 12".toLowerCase();
const finds = (q, text = row) => W.searchTest(q)(text);

// ---- addresses on this site
for (const q of ["https://www.example.com/data-migration/export-salesforce-data/",
  "http://example.com/data-migration/export-salesforce-data/",
  "www.example.com/data-migration/export-salesforce-data/",
  "HTTPS://WWW.EXAMPLE.COM/data-migration/export-salesforce-data/#every-method",
  "data-migration/export-salesforce-data/"]) assert.ok(finds(q), q);
assert.deepEqual(W.searchWords("https://www.example.com/a/#x"), { raw: "https://www.example.com/a/#x", path: "/a/", bare: "/a/" });
assert.deepEqual(W.searchWords("https://example.com"), { raw: "https://example.com", path: "/", bare: "/" });
assert.deepEqual(W.searchWords("www.example.com"), { raw: "www.example.com", path: null, bare: null }, "a bare host is plain text");
assert.equal(W.searchTest("   "), null);

// ---- a pasted address names one page: its path starts a cell, never sits inside another
assert.equal(finds("https://www.example.com/data-migration/export-salesforce-data/", "/en-us/data-migration/export-salesforce-data/ 5"), false);
assert.ok(finds("data-migration/export-salesforce-data/", "/en-us/data-migration/export-salesforce-data/ 5"), "typed words still match anywhere");
assert.ok(finds("https://www.example.com/b/", "x\u0001/b/ how to\u00013"), "any cell of a row joined by SEP");

// ---- the home page: only its own row, never every row
assert.equal(finds("https://www.example.com/", "/blog/\u00014"), false, "the home address is not every page");
assert.ok(finds("https://example.com", "/\u00019"), "the home row");
assert.ok(finds("https://example.com/?utm_source=x", "/\u00019"), "the home row, with a pasted query");
// ---- one page, two spellings: /pricing/ finds /pricing
assert.ok(finds("https://www.example.com/pricing/", "/pricing\u00013"));
assert.equal(finds("https://www.example.com/pricing/", "/pricing-plans/\u00013"), false);
// ---- a title with a question mark does not hide its row from a pasted ?utm address
assert.ok(finds("https://www.example.com/what-is-x/?utm_source=news", "/what-is-x/\u0001what is x?\u00015"));

// ---- another site's address is plain text
assert.equal(finds("https://other.example.net/data-migration/export-salesforce-data/"), false);
assert.ok(finds("https://other.example.net/x/", "referrer https://other.example.net/x/ 3"), "it still finds a cell that shows it");

// ---- ?query: kept where rows show queries
assert.ok(finds("https://www.example.com/a/?ref=1", "/a/ 4"), "a row without queries: the path");
assert.ok(finds("https://www.example.com/a/?ref=1", "/a/?ref=1 4"), "the same query");
assert.equal(finds("https://www.example.com/a/?ref=1", "/a/?ref=2 4"), false, "another query");

// ---- titles: under the path, searched, and the hint
D.setTitles({ pages: [{ path: "/data-migration/export-salesforce-data/", title: "How to Export Data from Salesforce (2026): Every Method" }, { path: "/b/", title: null }] });
assert.equal(D.titleOf("/data-migration/export-salesforce-data"), "How to Export Data from Salesforce (2026): Every Method", "either spelling");
assert.equal(D.searchHint(), "Search by path, address or title");
const rows = [{ path: "/data-migration/export-salesforce-data/", v: 12 }, { path: "/en-us/data-migration/export-salesforce-data/", v: 5 }, { path: "/b/", v: 3 }, { path: "/c/?ref=1", v: 1 }];
const cols = [{ key: "path", label: "Page", path: true, fmt: (v) => D.titled(v), find: (r) => D.titleFind(r.path) }, { key: "v", label: "Visitors", num: true }];
const t = table(cols, { caption: "Pages", rows, ns: false, placeholder: D.searchHint() });
const q = t.querySelector(".tbl-tools input");
assert.equal(q.getAttribute("placeholder"), "Search by path, address or title");
const search = async (text) => { q.value = text; q.dispatchEvent(new Ev("input")); await new Promise((r) => setTimeout(r, 250)); return t.querySelectorAll("tbody tr").map((tr) => tr.children[0].textContent); };
assert.equal((await search("data-migration/export-salesforce-data/")).length, 2, "typed path: both spellings, as before");
for (const text of ["How to Export Data from Salesforce (2026): Every Method",
  "https://www.example.com/data-migration/export-salesforce-data/"]) {
  const got = await search(text);
  assert.equal(got.length, 1, text);
  assert.match(got[0], /^\/data-migration\/export-salesforce-data\//, text);
}
assert.deepEqual(await search("https://other.example.net/b/"), ["No row matches the search."], "another site's address finds nothing here");
assert.equal((await search("https://example.com/c/")).length, 1, "a row with a query, found by its path");
// The title is drawn from data-title: the cell's words (column filters, CSV) stay its path.
const titledCell = D.titled("/data-migration/export-salesforce-data/");
assert.equal(titledCell.textContent, "/data-migration/export-salesforce-data/");
assert.equal(titledCell.getAttribute("data-title"), "How to Export Data from Salesforce (2026): Every Method");

// ---- a site with no titles: the cells as they were, and the other hint
D.setTitles({ pages: [{ path: "/a/" }] });
assert.equal(D.hasTitles(), false);
assert.equal(D.searchHint(), "Search by path or address");
assert.equal(D.titled("/a/"), "/a/", "no title: the cell as given");
const cell = h("span", null, "/a/");
assert.equal(D.titled("/a/", cell), cell);

console.log("page search: all passed");
