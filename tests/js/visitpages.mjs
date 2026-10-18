// A visit's pages in words (js/visitpages.js): pages loaded from the server and
// steps seen only in the browser, both stated, the same in every view.
//
//   node tests/js/visitpages.mjs
import assert from "node:assert/strict";

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { pagesWords, visitPages, browserSteps } = await import(new URL("visitpages.js", JS));

// The live case: 1 page loaded, /story/ and / seen in the browser.
const live = { pages: 1, in_app: 2, trail: [{ path: "/install/", page: true }, { path: "/story/", page: false }, { path: "/", page: false }] };
assert.equal(pagesWords(live), "3 pages (2 seen in the browser)");
assert.deepEqual(visitPages(live), { loaded: 1, browser: 2, all: 3 });
// No in_app count (an older journey, or the stored [path, "app"] trail): from the trail.
assert.equal(browserSteps({ pages: 1, trail: [["/a", "page"], ["/b", "app"]] }), 1);
assert.equal(pagesWords({ pages: 1, trail: [{ path: "/a", page: true }, { path: "/b", page: false }] }), "2 pages (1 seen in the browser)");
// Nothing seen in the browser: as before.
assert.equal(pagesWords({ pages: 1, in_app: 0 }), "1 page");
assert.equal(pagesWords({ pages: 1200 }), "1,200 pages");
assert.equal(pagesWords({ pages: 2, in_app: 1 }, { soFar: true }), "3 pages so far (1 seen in the browser)");
// Not known (a first touch): no figure is made up.
assert.equal(pagesWords({ pages: null }), "-");
console.log("visitpages: all passed");
