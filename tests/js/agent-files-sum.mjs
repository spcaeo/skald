// SKALD-56: Traffic › Agent files, the range sums (js/tabs/agent-files-sum.js), against
// agent_files.json shaped as agent_files.py builds it (no DOM):
//  - only ok days are summed; a day without the figure is unrecorded, never zero
//  - kinds, who and names add up over the days; one kind narrows names and files
//  - files only from the days that kept them (filesDays); the rest per kind summed
//  - today alone; a range that ends today (inc) takes today's blob too
//  - answers(): ok (2xx, 304), moved (3xx), failed (4xx, 5xx); attention() lists
//    failed files first
//
//   node tests/js/agent-files-sum.mjs
import assert from "node:assert/strict";
import { sumRange, answers, attention, aiOf, daysOf } from "../../skald/webapp/js/tabs/agent-files-sum.js";

const day1 = {
  kinds: { markdown: { requests: 3, status: { "2xx": 2, "4xx": 1 }, who: { ai_asked: 1, bots: 2 } },
    llms_txt: { requests: 1, status: { "2xx": 1 }, who: { search_engines: 1 } } },
  names: { ai_asked: { "ChatGPT-User": { markdown: 1 } }, bots: { RiverBot: { markdown: 2 } },
    search_engines: { Googlebot: { llms_txt: 1 } } },
  files: { "/a.md": { kind: "markdown", requests: 2, status: { "200": 2 }, who: { ai_asked: 1, bots: 1 }, names: { "ChatGPT-User": 1, RiverBot: 1 }, last: "2026-11-20T10:00:00Z" },
    "/b.md": { kind: "markdown", requests: 1, status: { "404": 1 }, who: { bots: 1 }, names: { RiverBot: 1 }, last: "2026-11-20T11:00:00Z" },
    "/llms.txt": { kind: "llms_txt", requests: 1, status: { "200": 1 }, who: { search_engines: 1 }, names: { Googlebot: 1 }, last: "2026-11-20T09:00:00Z" } },
  rest: {},
};
const day2 = {
  kinds: { markdown: { requests: 2, status: { "2xx": 1, "3xx": 1 }, who: { ai_training: 2 } } },
  names: { ai_training: { GPTBot: { markdown: 2 } } },
  files: { "/a.md": { kind: "markdown", requests: 1, status: { "200": 1 }, who: { ai_training: 1 }, names: { GPTBot: 1 }, last: "2026-11-21T08:00:00Z" },
    "/c.md": { kind: "markdown", requests: 0, status: {}, who: {}, names: {}, last: null } },
  rest: { markdown: { files: 1, requests: 1 } },
};
const old = { kinds: { markdown: { requests: 5, status: { "2xx": 5 }, who: { bots: 5 } } }, names: { bots: { X: { markdown: 5 } } } };   // no files: older than 30 days
const file = {
  days: [
    { day: "2026-11-18", state: "ok" },                                   // counted before the kind: unrecorded
    { day: "2026-11-19", state: "ok", files: old },
    { day: "2026-11-20", state: "ok", files: day1 },
    { day: "2026-11-21", state: "ok", files: day2 },
    { day: "2026-11-22", state: "withheld" },
  ],
  today: { day: "2026-11-23", state: "ok", files: { kinds: { okf: { requests: 4, status: { "2xx": 4 }, who: { ai_training: 4 } } }, names: {}, files: {}, rest: {} } },
};
const R = { kind: "history", first: "2026-11-18", last: "2026-11-22", length: 5 };

let got = sumRange(file, R);
assert.equal(got.days, 3);
assert.equal(got.unrecorded, 1);
assert.equal(got.filesDays, 2);
assert.equal(got.total, 11);
assert.deepEqual(got.kinds.markdown.who, { ai_asked: 1, bots: 7, ai_training: 2 });
assert.deepEqual(got.kinds.markdown.status, { "2xx": 8, "4xx": 1, "3xx": 1 });
assert.equal(got.names[0].name, "X");
assert.equal(got.names.find((x) => x.name === "RiverBot").requests, 2);
const a = got.files.find((x) => x.path === "/a.md");
assert.equal(a.requests, 3);
assert.deepEqual(a.who, { ai_asked: 1, bots: 1, ai_training: 1 });
assert.equal(a.last, "2026-11-21T08:00:00Z");
assert.deepEqual(a.days, [["2026-11-20", 2], ["2026-11-21", 1]]);
assert.deepEqual(got.rest, { markdown: { files: 1, requests: 1 } });
assert.deepEqual(got.series.get("2026-11-20"), { ai_asked: 1, bots: 2, search_engines: 1 });

got = sumRange(file, R, "llms_txt");
assert.equal(got.shown, 1);
assert.equal(got.total, 11);
assert.deepEqual(got.files.map((x) => x.path), ["/llms.txt"]);
assert.deepEqual(got.names.map((x) => x.name), ["Googlebot"]);
assert.deepEqual(got.rest, {});
assert.deepEqual(got.series.get("2026-11-21"), {});

got = sumRange(file, { kind: "today" });
assert.equal(got.total, 4);
assert.equal(daysOf(file, { ...R, last: "2026-11-23", inc: true }).used.length, 4);
assert.equal(sumRange(null, R).days, 0);

assert.deepEqual(answers({ "200": 2, "304": 1, "301": 3, "404": 1, "503": 2 }), { ok: 3, moved: 3, failed: 3 });
const list = attention([{ path: "/x.md", status: { "301": 5 }, requests: 5 }, { path: "/y.md", status: { "404": 1 }, requests: 1 }, { path: "/z.md", status: { "200": 9 }, requests: 9 }]);
assert.deepEqual(list.map((x) => x.path), ["/y.md", "/x.md"]);
assert.equal(aiOf({ ai_asked: 2, ai_training: 3, bots: 9 }), 5);
console.log("ok");
