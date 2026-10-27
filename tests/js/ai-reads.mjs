// An assistant's reads in the dashboard (skald/webapp/js/tabs/ai-reads.js): the
// owner's NotebookLM sample folds to one row "asked 2 times, with 2 files its page loaded";
// a read's files are never a row of their own; a range with a day stored before reads were
// counted says "Reads counted from", never 0; the bot drawer's "What it read" says what the
// assistant is behind "?".
//
//   node tests/js/ai-reads.mjs        (tests/test_ai_reads.py runs it)
//
// Example data only: made-up paths and figures.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const R = await import(new URL("tabs/ai-reads.js", JS));

const P = "/blog/best-online-quiz-makers";
const N = "Google-NotebookLM";
// Newest first, as requests.json and ai_activity.json list them.
const rows = [
  { name: N, at: "2026-10-27T10:00:05", path: "/_next/static/chunks/app.js", role: "file", of: P },
  { name: N, at: "2026-10-27T10:00:04", path: "/css/global-custom.css", role: "file", of: P },
  { name: N, at: "2026-10-27T10:00:02", path: P, role: "repeat", of: P },
  { name: N, at: "2026-10-27T10:00:00", path: P, role: "read", of: P },
  { name: "ChatGPT-User", at: "2026-10-27T09:00:00", path: "/pricing/", role: "read", of: "/pricing/" },
  { name: N, at: "2026-10-27T08:00:00", path: "/x.css", role: "file", of: "" },
];
const f = R.foldReads(rows);
assert.deepEqual(f.map((x) => x.row.path), [P, "/pricing/", "/x.css"]);
assert.equal(f[0].again, 1);
assert.equal(f[0].files.length, 2);
assert.equal(R.foldWords(f[0]), " · asked 2 times, with 2 files its page loaded");
assert.equal(R.foldWords(f[1]), "");
// A file whose page was not read in the list stays a row of its own; so does another
// assistant's file of the same page.
assert.equal(R.foldReads([{ ...rows[0], name: "ChatGPT-User" }, rows[3]]).length, 2);

// The range's figures: reads when every whole day has them, else where they start.
const blob = { reads: 1, requests: 4, files: 2, repeats: 1, by_name: { [N]: { reads: 1, requests: 4, files: 2, repeats: 1, files_with_page: 2 } },
  pages: { [N]: { [P]: { reads: 1, files: 2 } } } };
const m = { byDay: new Map([["2026-10-27", { day: "2026-10-27", ai_reads: blob }], ["2026-10-26", { day: "2026-10-26" }]]), today: "2026-10-28" };
const known = R.readsOf(m, { ai_reads: blob, tiers: { asked: 4 } }, { kind: "history" });
assert.deepEqual([known.known, known.reads, known.requests, known.byName[N]], [true, 1, 4, 1]);
assert.equal(R.requestsWords(known), "4 requests, 2 of them files its pages loaded");
const part = R.readsOf(m, { ai_reads: blob, unmeasured: { ai_reads: 1 }, tiers: { asked: 9 } }, { kind: "history" });
assert.deepEqual([part.known, part.from, part.requests], [false, "2026-10-27", 9]);
assert.match(R.notYet(part), /^Reads counted from /);
assert.equal(R.notYet({ from: null }), "Reads are counted from the next update");

// The drawer's section: what it is behind "?", reads first, each page with its files.
const sec = R.readsSection(m, { ai_reads: blob, tiers: { asked: 4 } }, { kind: "history" }, N);
const text = sec.textContent;
assert.match(text, /What it read/);
assert.match(text, /1reads/);
assert.match(text, /4requests/);
assert.match(text, /with 2 files/);
assert.ok(R.aboutOf(N).startsWith("Google NotebookLM fetches a page when someone adds it as a source to a notebook"));
// A crawler that is no user fetcher has no such section.
assert.equal(R.readsSection(m, { ai_reads: blob }, { kind: "history" }, "GPTBot"), null);
// Before reads were counted: said so, no figure.
const old = R.readsSection(m, { ai_reads: blob, unmeasured: { ai_reads: 1 }, tiers: { asked: 9 } }, { kind: "history" }, N).textContent;
assert.match(old, /Reads counted from/);
assert.doesNotMatch(old, /0reads/);

console.log("ai-reads: all passed");
