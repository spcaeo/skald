// SKALD-63: a page group's Compare is the group's own. The page asked the helper at the
// site's address (api/compare), so the server, which reads the group from the path
// (/traffic/<site>/<group>/api/compare), answered for the whole site; and the page's own
// cube, kept once for the page's life, answered for every group.
//
//   node tests/js/compare-group.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { getJSON } = await import(new URL("data.js", JS));
const { setDemo, DEMO } = await import(new URL("demo.js", JS));
const { answer } = await import(new URL("tabs/versus.js", JS));

const asked = [];
globalThis.fetch = async (url) => {
  asked.push(String(url));
  return { status: 404, ok: false, body: { cancel() {} }, headers: { get: () => "" }, json: async () => null };
};
const go = (hash) => { location.hash = hash; return S.read(); };
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));
const day = (d) => ({ day: d, state: "ok", readers: 1, by: { country: { US: 1 } } });
const days = ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25"].map(day);
const m = { site: "example.com", today: "2026-11-26", anchor: "2026-11-25", firstDay: "2026-11-01", byDay: new Map(days.map((d) => [d.day, d])),
  files: ["page_index", "cube"], x: {}, journeys: [] };

// ---- 1. the group's own address, and its own cube when the server does not answer
const A = { first: "2026-11-23", last: "2026-11-25" }, B = { first: "2026-11-20", last: "2026-11-22" };
const blog = await answer(m, go("#compare?view=blog&country=US"), A, B);
assert.equal(blog.local, true, "the server did not answer: the page works it out");
assert.ok(asked[0].startsWith("blog/api/compare?"), `the group's address: ${asked[0]}`);
assert.ok(asked.includes("blog/data/cube.json"), `the group's cube: ${asked.join(" ")}`);
asked.length = 0;
await answer(m, go("#compare?country=US"), A, B);
assert.ok(asked[0].startsWith("api/compare?"), `the whole site's address: ${asked[0]}`);
assert.ok(asked.includes("data/cube.json"), "the whole site's own cube, not the group's");

// ---- 2. the demo never asks the helper, a page group's address included
asked.length = 0;
setDemo({ api: { compare: {} } });
assert.ok(DEMO.on);
assert.equal(await getJSON("blog/api/compare?a=2026-11-01..2026-11-07&b=2026-10-25..2026-10-31", true), null);
assert.equal(await getJSON("api/compare?a=2026-11-01..2026-11-07&b=2026-10-25..2026-10-31", true), null);
assert.deepEqual(asked, [], "nothing fetched");

console.log("compare-group: all passed");
