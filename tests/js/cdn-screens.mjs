// SKALD-17 (20, 21, 22, 23): the screens on a site whose log holds a CDN's addresses.
//   Data quality: a day with half its lines or more from a CDN edge is worth a look, and says why.
//   Block list: never a CDN edge (counted apart); a period mostly through a CDN has nothing to block.
//   Crawler check: "Can't check (CDN)", which never hides an impostor nor beats a verified address.
//   Scanners: a CDN edge's row says so.
//
//   node tests/js/cdn-screens.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const Q = await import(new URL("tabs/quality.js", JS));
const D = await import(new URL("sec-data.js", JS));
const V = await import(new URL("tabs/botverify.js", JS));
const SC = await import(new URL("tabs/sec-scanners.js", JS));

// ---- Data quality (SKALD-23)
const day = { day: "2026-11-17", state: "ok", verify: "ok", lines: 1000, unparsed: 0, audit: { state: "match" } };
let [g, why] = Q.grade({ ...day, cdn_lines: 985 });
assert.equal(g, "amber");
assert.match(why[0], /^98\.5% of lines carry a CDN's address, not the visitor's: cities, crawler checks, scanners and the block list are not reliable$/);
assert.deepEqual(Q.grade({ ...day, cdn_lines: 400 }), ["green", []], "under half: nothing to say");
assert.deepEqual(Q.grade({ ...day, cdn_lines: null }), ["green", []], "not recorded: nothing to say");
assert.equal(Q.cdnShare({ lines: 0, cdn_lines: 0 }), null);

// ---- Block list (SKALD-20)
const row = (ip, probes, cdn = null) => ({ ip, probes, requests: probes, injection: 0, login: 0, burst: 0, days: ["2026-11-17"], country: "FR", hosting: false, cdn });
const merged = [row("198.51.100.7", 40, "Cloudflare"), row("198.51.100.9", 30, "Cloudflare"),
  row("203.0.113.5", 5), row("203.0.113.6", 4)];
let list = D.blockList(merged, "full");
assert.deepEqual(list.addresses.map((x) => x.ip), ["203.0.113.5", "203.0.113.6"], "never a CDN edge");
assert.deepEqual(list.networks.map((x) => x.cidr), ["203.0.113.0/24"], "nor its network");
assert.deepEqual(list.left, { addresses: 2, probes: 70 });
assert.ok(!D.nginx(list, {}).includes("198.51.100."), "no deny line for a CDN edge");
list = D.blockList(merged, "short");
assert.ok(!list.networks.some((x) => x.cidr.startsWith("198.51.100.")));
assert.equal(D.mostlyCdn({ probes: 100, cdnProbes: 100, cdn: 70 }), true);
assert.equal(D.mostlyCdn({ probes: 100, cdnProbes: 100, cdn: 20 }), false);
assert.equal(D.mostlyCdn({ probes: 100, cdnProbes: 0, cdn: null }), false, "not recorded: no claim");
const t = D.sumOf([["2026-11-16", { probes: 10, cdn: 7 }], ["2026-11-17", { probes: 5, cdn: 1 }]]);
assert.equal(t.cdn, 8);
// A month of days stored before SKALD-22 does not dilute the share of the days that counted it.
const mixed = D.sumOf([["2026-10-20", { probes: 500 }], ["2026-11-17", { probes: 10, cdn: 9 }]]);
assert.equal(D.mostlyCdn(mixed), true);
// The server marks a CDN edge by today's list (people/security `cdn`), on any day's row.
const old = D.merge([{ day: "2026-10-20", seq: 0, probes: 30, requests: 30, kinds: ["scanner"], country: "FR" }],
  { ok: true, mode: "full", rows: [{ day: "2026-10-20", seq: 0, ip: "198.51.100.7", user_agent: "curl/8", cdn: "Cloudflare" }] });
assert.equal(old[0].cdn, "Cloudflare");
assert.deepEqual(D.blockList(old, "full").addresses, [], "an old day's CDN edge is not offered either");
assert.equal(D.sumOf([["2026-11-16", { probes: 10 }]]).cdn, null, "days before SKALD-22: not recorded");

// ---- Crawler check (SKALD-21)
assert.equal(V.badgeOf({ verified: 0, unverified: 0, spoofed: 0, cdn: 152 }), "cdn");
assert.equal(V.badgeOf({ verified: 27, unverified: 0, spoofed: 0, cdn: 152 }), "verified");
assert.equal(V.badgeOf({ verified: 0, unverified: 0, spoofed: 3, cdn: 152 }), "spoofed", "an impostor is still said");
assert.equal(V.BADGE.cdn, "Can't check (CDN)");

// ---- Scanners (SKALD-22)
assert.equal(SC.label({ ip: "198.51.100.7", cdn: "Cloudflare", days: [], refs: [] }), "198.51.100.7 (Cloudflare edge)");
assert.equal(SC.label({ ip: "203.0.113.5", cdn: "", days: [], refs: [] }), "203.0.113.5");

console.log("cdn-screens: all passed");
process.exit(0);
