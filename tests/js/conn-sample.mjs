// Settings > Connections' "Test a sample" (js/tabs/conn-sample.js), drawn in node from a
// real dry run (tests/test_try_log.py writes try_log.dry_run's report to SAMPLE_JSON):
// the formats match try_log.FORMATS, the dialog is in the address (conn=sample, step,
// lfmt; never the pasted lines), Next posts the lines once and draws the report: the
// format, the reasons by line number, the hosts and paths with their copy and open
// icons, the five groups and their sum.
//
//   SAMPLE_JSON=report.json node tests/js/conn-sample.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
const given = JSON.parse(readFileSync(process.env.SAMPLE_JSON, "utf8"));
const SITE = "example.com";
Object.assign(globalThis.location, { origin: "https://www.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };

const posted = [];
globalThis.fetch = async (path, opts = {}) => {
  const body = opts.body ? JSON.parse(opts.body) : null;
  if (opts.method === "POST") posted.push([path, body]);
  const answer = (data, status = 200) => ({ ok: status < 300, status, json: async () => data, headers: { get: () => null } });
  if (path === "sites/trylog") return answer({ ok: true, report: given.report });
  return answer({ ok: false, error: "not found" }, 404);
};
const tick = (ms = 15) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const sample = await import(new URL("tabs/conn-sample.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
const { setSiteBase } = await import(new URL("urlactions.js", JS));
setSiteBase(SITE);

assert.deepEqual(sample.FORMATS, given.formats, "the same readers as try_log.FORMATS");
assert.equal(sample.MAX_LINES, given.web_lines);
assert.equal(sample.MAX_BYTES, given.web_bytes);
for (const f of sample.FORMATS) assert.ok(sample.FORMAT_NAMES[f], `a name for ${f}`);
assert.deepEqual(sample.measure("a\n\nb\n"), { lines: 2, bytes: 5, over: false });

const button = (root, text) => root.querySelectorAll("button").find((b) => b.textContent.trim() === text);
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();

history.replaceState(null, "", `#${readState().tab}`);
sample.sampleDialog(SITE, {}, { route: { key: "conn", value: "sample" } });
await tick();
let d = dialog();
assert.ok(d && d.textContent.includes("Step 1 of 2: Paste some lines of the log"), "step 1");
assert.equal(readState().conn, "sample", location.hash);
assert.equal(readState().step, "1", location.hash);
// Next with nothing pasted: refused in words, nothing sent.
button(d, "Next").click(); await tick();
assert.ok(d.textContent.includes("Paste some lines of the log first."));
assert.equal(posted.length, 0);
// The reader: in the address.
const sel = d.querySelector("select");
sel.value = "caddy_json";
sel.dispatchEvent(new Event("change"));
assert.equal(readState().lfmt, "caddy_json", location.hash);
sel.value = "auto";
sel.dispatchEvent(new Event("change"));
assert.equal(readState().lfmt || "", "", location.hash);
// Paste and test.
const LINE = '2026-10-06T10:00:00+00:00 192.0.2.10 example.com "GET / HTTP/2.0" 200 5 "-" "Mozilla/5.0"';
const box = d.querySelector("textarea");
box.value = `${LINE}\n${LINE}\n`;
box.dispatchEvent(new Event("input"));
assert.ok(d.textContent.includes("2 lines."), "the count");
button(d, "Next").click(); await tick(30);
assert.deepEqual(posted[0], ["sites/trylog", { site: SITE, text: `${LINE}\n${LINE}\n`, format: "auto" }]);
assert.ok(!location.hash.includes("192.0.2.10") && !location.hash.includes("GET"), "the lines never go in the address");
assert.equal(readState().step, "2", location.hash);
d = dialog();
const text = d.textContent;
const r = given.report;
for (const t of ["Step 2 of 2: What Skald would count", r.headline, "nginx_extended", `${r.lines} lines: ${r.read} read, ${r.unread} could not be read`,
  "Real people", "Answer engines", "Search engines", "Bots and scanners", "Our own traffic", "adds up", "/pricing/", "try-log"]) assert.ok(text.includes(t), t);
assert.ok(text.includes(`(line ${r.reasons[0].examples.join(", ")})`), "the reason's line numbers");
// Copy and open: a page path has both icons, a host, the format and a reason the copy icon alone.
const page = d.querySelectorAll(".ts-pages li")[0];
assert.ok(page.querySelector(".ua-open") && page.querySelector(".ua-copy"), "the path: copy and open");
assert.ok(page.querySelector(".ua-open").getAttribute("href") === `https://${SITE}/pricing/`);
const host = d.querySelectorAll(".ts-hosts li")[0];
assert.ok(host.querySelector(".ua-copy") && !host.querySelector(".ua-open"), "the host: copy only");
assert.ok(d.querySelectorAll(".ts-why li")[0].querySelector(".ua-copy"), "the reason: copy");
const rows = d.querySelectorAll(".ts-groups tbody tr");
assert.equal(rows.length, 5);
// Close: the keys leave the address.
button(d, "Close").click(); await tick();
assert.ok(!readState().conn && !readState().lfmt, location.hash);

// No report (a link at step 2, or a reload): the report step says so.
const empty = sample.reportView(null, SITE);
assert.equal(empty.length, 1);
console.log("conn-sample: all passed");
