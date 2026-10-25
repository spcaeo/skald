// Social networks as the page reads them (skald/webapp/js/social-networks.js and
// tabs/tr-social.js): only verified days, a range that does not add up is withheld, a day
// before the feature is "not recorded" (never 0), and a network opens by its id (net=x).
//
//   node tests/js/social-networks.mjs        (tests/test_social_networks.py runs it)
//
// Example data only: hosts the networks' own, paths made up.
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const SN = await import(new URL("social-networks.js", JS));
const T = await import(new URL("tabs/tr-social.js", JS));
const { ROUTE_KEYS } = await import(new URL("routekeys.js", JS));

const blob = (o = {}) => ({ visits: 20, social: 9, networks: { x: 5, linkedin: 3, other: 1 },
  via: { x: { "t.co": 3, "x.com": 1, "(utm_source)": 1 }, linkedin: { "lnkd.in": 2, "android-app://com.linkedin.android": 1 }, other: { "(utm_source)": 1 } },
  landings: { x: { "/blog/a": 4, "/": 1 }, linkedin: { "/": 3 }, other: { "/": 1 } }, ...o });

// ---- the range: verified days only; a day not recorded is left out, never a zero
{
  const f = { days: [{ day: "2026-10-04", state: "ok", social_networks: null }, { day: "2026-10-05", state: "ok", social_networks: blob() },
    { day: "2026-10-06", state: "withheld", social_networks: blob() }], today: { state: "ok", social_networks: blob({ visits: 2, social: 1, networks: { x: 1 }, via: { x: { "t.co": 1 } }, landings: { x: { "/": 1 } } }) } };
  const got = SN.rangeBlobs(f, { kind: "history", first: "2026-10-01", last: "2026-10-31" });
  assert.equal(got.days, 2, "the withheld day is not a recorded day");
  assert.equal(got.blobs.length, 1, "the day not recorded has no blob");
  assert.equal(got.missing, 1);
  assert.equal(SN.rangeBlobs(f, { kind: "today" }).blobs[0].networks.x, 1);
  assert.equal(SN.rangeBlobs({ ...f, today: { state: "withheld", social_networks: blob() } }, { kind: "today" }).blobs.length, 0, "a withheld today shows nothing");
  assert.deepEqual(SN.rangeBlobs(null, { kind: "today" }), { blobs: [], days: 0, missing: 0, list: [] });
}

// ---- the sums: two days add up; a broken one is not ok
{
  const t = SN.sumNetworks([blob(), blob()]);
  assert.equal(t.ok, true);
  assert.deepEqual([t.visits, t.social], [40, 18]);
  assert.deepEqual(t.networks, { x: 10, linkedin: 6, other: 2 });
  assert.equal(t.via.x["t.co"], 6);
  assert.equal(t.landings.x["/blog/a"], 8);
  assert.equal(SN.sumNetworks([blob({ social: 10 })]).ok, false, "networks must add up to social");
  assert.equal(SN.sumNetworks([blob({ via: { x: { "t.co": 5 }, linkedin: { "lnkd.in": 2 }, other: { "(utm_source)": 1 } } })]).ok, false, "via must add up");
  assert.equal(SN.sumNetworks([blob({ landings: { x: { "/": 5 }, linkedin: { "/": 3 } } })]).ok, false, "every network has its pages");
  assert.equal(SN.sumNetworks([blob({ visits: 3 })]).ok, false, "social within the visits");
  assert.equal(SN.sumNetworks([]).ok, true);
}

// ---- the words
{
  assert.equal(SN.nameOf(null, "x"), "X");
  assert.equal(SN.nameOf({ social_networks: { names: { x: "X (Twitter)" } } }, "x"), "X (Twitter)");
  assert.equal(SN.nameOf(null, "hackernews"), "Hacker News");
  assert.equal(SN.viaWords("t.co"), "t.co");
  assert.equal(SN.viaWords("android-app://com.linkedin.android"), "the Android app com.linkedin.android");
  assert.equal(SN.viaWords("(utm_source)"), "a link tagged utm_source");
  assert.equal(SN.viaWords("(fbclid)"), "an ad click id (fbclid)");
  assert.equal(SN.viaHref("l.facebook.com"), "https://l.facebook.com");
  assert.equal(SN.viaHref("android-app://com.linkedin.android"), "");
  assert.equal(SN.viaHref("(utm_source)"), "");
  assert.ok(SN.isNetId("hackernews"));
  for (const bad of ["", "X", "x.com", "203.0.113.5", "a@example.com", "x;y", "abcdefghijklm"]) assert.ok(!SN.isNetId(bad), bad);
}

// ---- the address: net is a tab key of its own
{
  const k = ROUTE_KEYS.find((x) => x.key === "net");
  assert.ok(k && k.kind === "tab" && /tr-social/.test(k.owner));
}

// ---- the grid's rows and the detail, from a model
const DAYS = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06"];
function model(withBlob) {
  const days = DAYS.map((day) => ({ day, state: "ok", social_networks: withBlob(day) ? blob() : null }));
  return { firstDay: DAYS[0], byDay: new Map(DAYS.map((d) => [d, { day: d, state: "ok" }])), x: { campaigns: { days, social_networks: { names: { ...SN.NAMES } } } } };
}
const range = (first, last) => {
  const days = DAYS.filter((d) => d >= first && d <= last).map((day) => ({ day, state: "ok" }));
  return { kind: "history", first, last, length: days.length, days };
};
{
  const m = model(() => true);
  const r = range("2026-10-04", "2026-10-06");
  const got = T.socialRows(m, { net: "" }, r, { ok: false });
  assert.deepEqual(got.rows.map((x) => [x.k, x.label, x.v, x.seg]), [["x", "X", 15, "social"], ["linkedin", "LinkedIn", 9, "social"], ["other", "Social, network not named", 3, "social"]]);
  assert.equal(got.rows[0].whole, 27, "the share is over the networks' own sum");
  assert.equal(got.rows[0].before, 15, "the three days before, all recorded");
  assert.deepEqual(got.rows[0].trend.slice(-3), [5, 5, 5]);
  assert.equal(T.socialNote(got), null);
  // Days before the feature: left out and said, never zeros; no Before against them.
  const half = T.socialRows(model((d) => d >= "2026-10-05"), {}, r, { ok: false });
  assert.equal(half.rows[0].v, 10);
  assert.equal(half.rows[0].before, null);
  assert.match(T.socialNote(half).textContent, /over 2 of 3 recorded days/);
  const none = T.socialRows(model(() => false), {}, r, { ok: false });
  assert.equal(none.rows.length, 0);
  assert.match(T.socialNote(none).textContent, /not recorded for this range/);
  // A day that does not add up withholds the range.
  const bad = model(() => true);
  bad.x.campaigns.days[4].social_networks = blob({ social: 99 });
  const held = T.socialRows(bad, {}, r, { ok: false });
  assert.equal(held.rows.length, 0);
  assert.match(T.socialNote(held).textContent, /withheld/);
  // Compare: B and ± only when A and B are recorded every day.
  const c = { ok: true, b: range("2026-10-01", "2026-10-03") };
  const cmp = T.socialRows(m, {}, r, c);
  assert.equal(cmp.compared, true);
  assert.equal(cmp.rows[0].b, 15);
  const cmpHalf = T.socialRows(model((d) => d >= "2026-10-02"), {}, r, c);
  assert.equal(cmpHalf.compared, false);
  assert.equal(cmpHalf.rows[0].b, undefined, "never a B of 0 for days not recorded");
  assert.match(T.socialNote(cmpHalf).textContent, /not compared/);

  // The row's label opens the network: a button, so the whole row opens it (drill.js).
  const cell = T.netCell(got.rows[0]);
  assert.ok(cell.querySelector("button.dl"));

  // The detail: hosts with their own address, pages, and the plain lines.
  const panel = T.networkPanel(m, { tab: "traffic/sources", net: "x" }, r);
  const text = panel.textContent;
  assert.match(text, /15 visitors from X/);
  assert.match(text, /t\.co/);
  assert.match(text, /a link tagged utm_source/);
  assert.match(text, /\/blog\/a/);
  assert.match(text, /All social networks/);
  assert.equal(T.networkPanel(m, { net: "" }, r), null, "nothing open, nothing drawn");
  assert.match(T.networkPanel(m, { net: "myspace" }, r).textContent, /Not a social network Skald knows/);
  assert.match(T.networkPanel(m, { net: "tiktok" }, r).textContent, /No visitor from TikTok in this range/);
  assert.match(T.networkPanel(model(() => false), { net: "x" }, r).textContent, /Not recorded for this range/);
  assert.match(T.networkPanel(bad, { net: "x" }, r).textContent, /Withheld/);
}

console.log("social-networks: ok");
