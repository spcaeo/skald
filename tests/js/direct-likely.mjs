// "Direct, likely <reason>" as the page reads it (skald/webapp/js/direct-likely.js):
// only verified days, a range that does not add up is withheld, and every line says "likely".
//
//   node tests/js/direct-likely.mjs        (tests/test_direct_likely.py runs it)
//
// Example data only: no address, no landing query value.
import assert from "node:assert/strict";
import { REASONS, reasonLabel, rangeBlobs, sumDirect, detailLine, method, visitWords } from "../../skald/webapp/js/direct-likely.js";

const blob = (o = {}) => ({ share_window_minutes: 30, visits: 18, direct: 15, likely: 10, plain: 5,
  reasons: { checkout: 4, in_app: 2, shared: 4 },
  details: { checkout: { "(return page)": 2, PayPal: 1, Stripe: 1 }, in_app: { "Facebook app": 1, "Instagram app": 1 },
    shared: { "(more than one)": 1, "(share tag)": 1, Instagram: 1, WhatsApp: 1 } }, ...o });

// ---- the range: verified days only; a day not recorded is left out, never a zero
{
  const f = { days: [{ day: "2026-10-04", state: "ok", direct_likely: null }, { day: "2026-10-05", state: "ok", direct_likely: blob() },
    { day: "2026-10-06", state: "withheld", direct_likely: blob() }], today: { state: "ok", direct_likely: blob({ visits: 1, direct: 0, likely: 0, plain: 0, reasons: { checkout: 0, in_app: 0, shared: 0 }, details: { checkout: {}, in_app: {}, shared: {} } }) } };
  const got = rangeBlobs(f, { kind: "history", first: "2026-10-01", last: "2026-10-31" });
  assert.equal(got.days, 2, "the withheld day is not a recorded day");
  assert.equal(got.blobs.length, 1, "the day not recorded has no blob");
  assert.equal(rangeBlobs(f, { kind: "today" }).blobs[0].visits, 1);
  assert.deepEqual(rangeBlobs(null, { kind: "today" }), { blobs: [], days: 0 });
}

// ---- the sums: two days add up; a broken one is not ok
{
  const t = sumDirect([blob(), blob()]);
  assert.equal(t.ok, true);
  assert.deepEqual([t.visits, t.direct, t.likely, t.plain], [36, 30, 20, 10]);
  assert.deepEqual(t.reasons, { checkout: 8, in_app: 4, shared: 8 });
  assert.equal(t.details.checkout.Stripe, 2);
  assert.deepEqual([...t.windows], [30]);
  assert.equal(sumDirect([blob({ likely: 11 })]).ok, false, "reasons must add up to likely");
  assert.equal(sumDirect([blob({ plain: 4 })]).ok, false, "likely + plain must be direct");
  assert.equal(sumDirect([blob({ details: { checkout: {}, in_app: {}, shared: {} } })]).ok, false, "details must add up");
  assert.equal(sumDirect([]).ok, true);
}

// ---- the words: always "likely", never a fact
{
  assert.deepEqual(REASONS, ["checkout", "in_app", "shared"]);
  assert.equal(reasonLabel("in_app"), "Direct, likely in-app browser");
  assert.equal(reasonLabel("checkout"), "Direct, likely checkout or payment return");
  assert.equal(detailLine({ Stripe: 3, "(return page)": 1, PayPal: 0 }), "Stripe 3, a checkout's end page 1");
  assert.equal(visitWords({ reason: "in_app", detail: "Instagram app" }), "Direct, likely in-app browser (Instagram app)");
  assert.equal(visitWords({ reason: "shared", detail: "WhatsApp", minutes: 12 }), "Direct, likely shared link (WhatsApp fetched a preview of this page 12 min before)");
  assert.equal(visitWords({ reason: "shared", detail: "(more than one)", minutes: 0 }), "Direct, likely shared link (more than one app fetched a preview of this page in the same minute)");
  assert.equal(visitWords({ reason: "shared", detail: "(share tag)" }), "Direct, likely shared link (a share tag on the link)");
  assert.equal(visitWords(null), "");
  assert.equal(visitWords({ reason: "guess", detail: "x" }), "", "an unknown reason is not shown");
  assert.match(method({ direct_likely: { method: "Inferred, not counted. Likely, never certain." } }, new Set([30])), /Likely, never certain/);
  assert.match(method(null, new Set([30, 10])), /different preview windows \(10, 30 minutes\)/);
}

console.log("direct-likely: ok");
