// Leads & sales > Revenue (2.32.0, js/tabs/sa-revenue.js, js/tabs/revfigs.js): money per
// currency from conversions.json's `revenue` days, never converted; minor units by the
// file's decimals table; withheld days left out and said in the conversions' words; the
// currency, the breakdown and a tag in the address; copy and open on landing pages; the
// how-to when the site never sent a value; and the lead drawer's value, refund, customer
// reference and tags. Sample data only (example.com).
//
//   node tests/js/revenue.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const R = await import(new URL("tabs/revfigs.js", JS));
const revenue = (await import(new URL("tabs/sa-revenue.js", JS))).default;
const { saleFacts } = await import(new URL("tabs/sa-leads.js", JS));
const { setSiteBase } = await import(new URL("urlactions.js", JS));
const K = await import(new URL("routekeys.js", JS));
const sales = (await import(new URL("tabs/s-sales.js", JS))).default;
const flat = (out) => [out].flat(Infinity).filter(Boolean);
const text = (out) => flat(out).map((el) => (typeof el === "string" ? el : el.textContent)).join(" ");
const all = (out, sel) => flat(out).flatMap((el) => (el.querySelectorAll ? [...(el.matches?.(sel) ? [el] : []), ...el.querySelectorAll(sel)] : []));

// ---- money: minor units, the file's decimals, Intl in the currency; unknown is "-"
const F0 = { currencies: { USD: 2, EUR: 2, JPY: 0, KWD: 3 } };
assert.equal(R.money(4900, "USD", F0), "$49.00");
assert.equal(R.money(123456, "EUR", F0), "€1,234.56");
assert.equal(R.money(1200, "JPY", F0), "¥1,200", "a zero-decimal currency: 1200 minor units are 1200 yen");
assert.equal(R.money(1234, "KWD", F0).replace(/\s/g, " "), "KWD 1.234", "three decimals");
assert.equal(R.money(-500, "USD", F0), "-$5.00", "a period with more refunded than sold is negative, not hidden");
assert.equal(R.money(null, "USD"), "-", "not recorded is a dash, never $0.00");
assert.equal(R.money(100, "usd"), "-", "not a currency code: no amount");
assert.equal(R.decimalsOf({}, "JPY"), 0, "without the file's table: the server's copy");
assert.equal(R.decimalsOf({}, "MGA"), 0, "MGA as the server counts it");
assert.equal(R.decimalsOf({}, "CLF"), 4);
assert.equal(R.decimalsOf({ currencies: { MGA: 0 } }, "MGA"), 0);
assert.equal(R.decimalsOf({ currencies: { HUF: 2 } }, "HUF"), 2, "the file's table wins");
assert.equal(R.decimal(4900, "USD", F0), "49.00");
assert.equal(R.decimal(1200, "JPY", F0), "1200");

// ---- the days: ok with a revenue block ({} a known none); withheld (the day or its block); not recorded
const usd = (o) => ({ gross_minor: 0, refunded_minor: 0, net_minor: 0, sales: 0, refunds: 0, new_customers: 0, renewals: 0, by: {}, ...o });
const f = {
  available: true, finished: ["completed", "paid"], lead_actions: ["signup", "demo"], min_rate: 10, since: "2026-10-01",
  currencies: { USD: 2, EUR: 2 }, revenue_since: "2026-10-15",
  refunds_without_sale: { count: 1, currencies: { EUR: 1000 } },
  days: [
    { day: "2026-10-14", state: "ok", stages: {} },
    { day: "2026-10-15", state: "ok", stages: {}, revenue: {
      USD: usd({ gross_minor: 9800, net_minor: 9800, sales: 2, new_customers: 2, by: { source: { "Search engine": { net_minor: 4900, sales: 1 }, Direct: { net_minor: 4900, sales: 1 } },
        landing: { "/pricing/": { net_minor: 9800, sales: 2 } }, tag: { plan: { pro: { net_minor: 4900, sales: 1 }, team: { net_minor: 4900, sales: 1 } } } } }),
      EUR: usd({ gross_minor: 3900, net_minor: 3900, sales: 1, new_customers: 1, by: { source: { "AI assistant": { net_minor: 3900, sales: 1 } } } }) } },
    { day: "2026-10-16", state: "ok", stages: {}, revenue: {
      USD: usd({ gross_minor: 4900, refunded_minor: 2000, net_minor: 2900, sales: 1, refunds: 1, renewals: 1, by: { source: { "Search engine": { net_minor: 2900, sales: 1 } },
        landing: { "/pricing/": { net_minor: 2900, sales: 1 } }, tag: { plan: { pro: { net_minor: 2900, sales: 1 } } } } }) } },
    { day: "2026-10-17", state: "withheld", why: "the second count found 3 sales, the first 2" },
    { day: "2026-10-18", state: "ok", stages: {}, revenue: { state: "withheld", why: "the spool's sum is 49.00 USD more" } },
    { day: "2026-10-19", state: "ok", stages: {}, revenue: {} },
    { day: "2026-10-20", state: "ok", stages: {} },
  ],
  ltv: { window: "every row kept", currencies: { USD: { first_day: "2026-10-15", customers: 2, net_minor: 12700, renewals: 1, repeat_customers: 1,
    by_first_source: { "Search engine": { customers: 1, net_minor: 7800, renewals: 1, repeat_customers: 1 }, Unknown: { customers: 1, net_minor: 4900, renewals: 0, repeat_customers: 0 } } } } },
};
const days = ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21"];
const got = R.revenueDays(f, days);
assert.deepEqual(got.ok.map((d) => d.day), ["2026-10-15", "2026-10-16", "2026-10-19"], "a checked day with an empty block is a day with no sale");
assert.deepEqual(got.held.map((d) => d.day), ["2026-10-17", "2026-10-18"], "a withheld day and a withheld revenue block");
assert.deepEqual(got.missing, ["2026-10-14", "2026-10-20", "2026-10-21"], "an ok day without a block, and not in the file: not recorded");
assert.ok(R.hasRevenue(f));
assert.ok(!R.hasRevenue({ available: true, currencies: null, days: [{ day: "2026-10-15", state: "ok", stages: {} }] }), "never a value (currencies null): no revenue at all");
assert.equal(R.firstDay(f), "2026-10-15", "values recorded from the first sale's day");
assert.equal(R.firstDay({ ...f, revenue_since: "2026-10-13" }), "2026-10-13", "the file's revenue_since, not the lifetime's first sale");
assert.equal(R.firstDay({ ...f, revenue_since: { state: "withheld", why: "the spool's first value is later" } }), null, "withheld: no day");
assert.equal(R.sinceHeld({ ...f, revenue_since: { state: "withheld", why: "the spool's first value is later" } }), "the spool's first value is later");
assert.equal(R.sinceHeld(f), null);
assert.deepEqual(R.revenueDays({ ...f, days: [{ day: "2026-10-14", state: "ok", stages: {}, revenue: {} }] }, ["2026-10-14"]).missing, ["2026-10-14"],
  "a day before the first value is not recorded, even with an empty block");

// ---- sums per currency, never added across
const t = R.sumRevenue(got.ok);
assert.deepEqual(Object.keys(t).sort(), ["EUR", "USD"]);
assert.equal(t.USD.gross_minor, 14700);
assert.equal(t.USD.refunded_minor, 2000);
assert.equal(t.USD.net_minor, 12700, "net is gross less refunded");
assert.equal(t.USD.sales, 3);
assert.equal(t.USD.refunds, 1);
assert.equal(t.USD.renewals, 1);
assert.equal(t.EUR.net_minor, 3900, "EUR apart");
assert.deepEqual(t.USD.by.source["Search engine"], { net_minor: 7800, sales: 2 });
assert.deepEqual(t.USD.by.tag.plan.pro, { net_minor: 7800, sales: 2 });
assert.deepEqual(R.currencies(t), ["USD", "EUR"], "most net first");
assert.equal(R.pickCurrency(["USD", "EUR"], "eur"), "EUR");
assert.equal(R.pickCurrency(["USD", "EUR"], "GBP"), "USD", "a currency the period does not have: the first");
assert.deepEqual(R.rowsOf(t.USD, "source").map((x) => x.k), ["Search engine", "Direct"]);
assert.deepEqual(R.rowsOf(t.USD, "tag").map((x) => x.k), ["plan = pro", "plan = team"]);
assert.deepEqual(R.tagChoices(t.USD).map(([k]) => k), ["plan", "plan:pro", "plan:team"], "each key (every value), then each pair");
assert.deepEqual(R.tagOf("plan:pro"), ["plan", "pro"]);
assert.deepEqual(R.tagOf("plan"), ["plan", ""]);
assert.equal(R.tagOf("Plan:Pro"), null, "tags are lower-case tokens");
assert.equal(R.tagOf("x@example.com"), null);

// ---- revenue per visitor: two counted figures over the same days, given over min_rate
const byDay = new Map([["2026-10-14", { day: "2026-10-14", state: "ok", readers: 1000 }], ["2026-10-15", { day: "2026-10-15", state: "ok", readers: 200 }], ["2026-10-16", { day: "2026-10-16", state: "ok", readers: 100 }], ["2026-10-19", { day: "2026-10-19", state: "ok", readers: 50 }]]);
const v = R.visitorsOn({ byDay }, got.ok);
assert.deepEqual(v, { visitors: 350, days: 3 });
assert.equal(R.perVisitor(12700, v, 3), 36, "12700 cents over 350 visitors");
assert.equal(R.perVisitor(12700, { visitors: 350, days: 2 }, 3), null, "a day without whole visitors: none, never a guess");
assert.equal(R.perVisitor(12700, { visitors: 9, days: 3 }, 3), null, "under min_rate visitors: none");

// ---- lifetime value by first source
const lt = R.ltvRows(f, "USD", 10);
assert.deepEqual(lt.map((x) => [x.k, x.customers, x.avg_minor]), [["Search engine", 1, 7800], ["Unknown", 1, 4900]]);
assert.deepEqual(R.ltvRows({ ...f, ltv: { state: "withheld", why: "the spool disagrees" } }, "USD"), [], "withheld lifetime: no rows");
assert.equal(R.ltvHeld({ ltv: { state: "withheld", why: "the spool disagrees" } }), "the spool disagrees");
assert.equal(lt[0].rate, null, "a repeat rate over fewer than min_rate customers is not given");
assert.deepEqual(R.ltvRows(f, "EUR"), []);

// ---- the tab: registered with its keys
const row = sales.find((x) => x[0] === "revenue");
assert.ok(row, "Leads & sales has a Revenue tab");
assert.deepEqual(row[3].keep, ["cur", "rby", "tag"]);
for (const k of ["cur", "rby", "tag"]) assert.equal(K.KEYS.get(k)?.owner, "tabs/sa-revenue.js", `${k} is in the route registry`);

setSiteBase("example.com");
const m = { today: "2026-10-21", anchor: "2026-10-20", firstDay: "2026-08-01", byDay, x: { conversions: f }, days: [] };
const s0 = { ...S.read(), tab: "sales/revenue", range: "custom", from: "2026-10-14", to: "2026-10-20" };
const draw = (patch = {}) => flat(revenue(m, { ...s0, ...patch }));
{
  const out = draw();
  const words = text(out);
  assert.match(words, /2 days withheld \(17 Oct, 18 Oct\): left out of every figure below, never counted as zero\. Why: the second count found 3 sales, the first 2/, "the conversions' own words");
  assert.match(words, /\$127\.00/, "net revenue in USD");
  assert.match(words, /\$147\.00 sold, \$20\.00 refunded/);
  assert.match(words, /\$0\.36/, "revenue per visitor: only the days with figures (the 14th, before the first value, and its 1,000 visitors are left out)");
  assert.match(words, /Values are recorded from 15 Oct/, "the tab says from which day");
  assert.match(words, /Also in this period, never added: €39\.00 net from 1 sale/, "the other currency apart");
  assert.ok(!/166\.00|€166|\$166/.test(words), "never USD and EUR added together");
  assert.match(words, /Revenue by source \(last touch\)/);
  assert.match(words, /Lifetime value, by first source/);
  assert.ok(all(out, '[aria-label="Currency"], .sa-seg').length, "a currency switch when there are two");
  assert.match(words, /a later, larger total counts the difference on its own day/, "the refund rule, said");
  assert.match(words, /1 refund kept but counted nowhere \(€10\.00\), over every row kept: never taken off any figure here/);
  assert.equal(words.split("Values are recorded from").length, 2, "said once");
  assert.ok(!/undefined|null|NaN/.test(words), `nothing undefined printed: ${words.match(/.{30}(undefined|null|NaN).{30}/)?.[0]}`);
}
{
  const words = text(draw({ cur: "EUR" }));
  assert.match(words, /€39\.00/);
  assert.match(words, /Also in this period, never added: \$127\.00 net from 3 sales/);
}
{
  // Landing pages: each path draws copy and open at its end (urlactions.js).
  const out = draw({ rby: "landing" });
  assert.match(text(out), /Revenue by landing page/);
  const opens = all(out, "a.ua-open").map((a) => a.getAttribute("href"));
  assert.ok(opens.includes("https://example.com/pricing/"), `a landing page opens on its site: ${opens}`);
  assert.ok(all(out, "button.ua-copy").length >= 1, "and has its copy icon");
}
{
  // One tag: the numbers are that tag's own; the table lists its key's values.
  const words = text(draw({ tag: "plan:pro" }));
  assert.match(words, /Net revenue, plan = pro/);
  assert.match(words, /\$78\.00/);
  assert.match(words, /Revenue by the tag plan/);
  assert.match(words, /not split by tag/i);
  // tag=plan, no value: every value of the tag, as the table; the numbers stay whole.
  const every = text(draw({ tag: "plan" }));
  assert.match(every, /Revenue by the tag plan/);
  assert.match(every, /Tag plan, every value/);
  assert.match(every, /\$127\.00/, "the numbers are every sale's");
  assert.match(text(draw({ tag: "seats" })), /No USD sale in this period carries the tag seats\./, "a key no sale has: said plainly");
  const none = text(draw({ tag: "plan:enterprise" }));
  assert.match(none, /No USD sale in this period carries the tag plan = enterprise/);
}
{
  // A site that never sent a value: the how-to, linking the help part.
  const out = flat(revenue({ ...m, x: { conversions: { available: true, days: [{ day: "2026-10-15", state: "ok", stages: {} }] } } }, s0));
  assert.match(text(out), /No revenue yet\. Send value and currency with each sale/);
  assert.ok(all(out, 'a[href="#help?part=revenue"]').length, "the empty state links the help part");
  // No conversions file at all: the same plain words.
  assert.match(text(flat(revenue({ ...m, x: {} }, s0))), /No revenue yet/);
}
{
  // A period of only not-recorded days.
  const words = text(draw({ from: "2026-10-01", to: "2026-10-14" }));
  assert.match(words, /No revenue figures for this period: values are recorded from 15 Oct on/);
}

assert.match(text(flat(revenue({ ...m, x: { conversions: { ...f, refunds_without_sale: null, withheld: { refunds_without_sale: "the spool holds 2" } } } }, s0))),
  /Refunds counted nowhere: withheld, the second count disagrees\. the spool holds 2/);
assert.match(text(flat(revenue({ ...m, x: { conversions: { ...f, revenue_since: { state: "withheld", why: "the spool's first value is later" } } } }, s0))),
  /The first day with a value is withheld: the second count disagrees\. the spool's first value is later/);
assert.match(text(flat(revenue(m, s0))), /1 refund kept but counted nowhere \(€10\.00\).*whose value could not be read.*in another currency than its sale/,
  "every refund kept and not counted is listed, in words that say which");
assert.equal(R.orphanRefunds({ ...f, refunds_without_sale: { count: 0, currencies: {} } }), null, "none: no line");
assert.deepEqual(R.orphanRefunds({ ...f, refunds_without_sale: { state: "withheld", why: "the spool holds 2" } }), { held: "the spool holds 2" }, "the block itself withheld");

// ---- every state in the address, on this tab only
location.hash = "#sales/revenue?range=30d";
S.set({ cur: "EUR" });
S.set({ rby: "campaign" });
S.set({ tag: "plan:pro" });
const q = new URLSearchParams(location.hash.split("?")[1]);
assert.equal(q.get("cur"), "EUR");
assert.equal(q.get("rby"), "campaign");
assert.equal(q.get("tag"), "plan:pro");
const back = S.read();
assert.deepEqual([back.cur, back.rby, back.tag], ["EUR", "campaign", "plan:pro"], "a link or a reload brings them back");
assert.ok(!S.hashFor({ ...back, tab: "sales/leads" }).includes("cur="), "another tab starts without them");
for (const k of ["cur", "rby", "tag"]) assert.ok(!K.isPersonal(q.get(k)), "no address or email in them");

// ---- the lead drawer's sale facts
{
  const facts = saleFacts({ value_minor: 4900, currency: "USD", refunded_minor: 2000, customer_ref: "cus_demo_0001", tags: { plan: "pro", seats: "5" } });
  const w = facts.map(([k, x]) => `${k}: ${typeof x === "string" ? x : x.textContent}`).join(" | ");
  assert.match(w, /Value: \$49\.00 USD/);
  assert.match(w, /Refunded: \$20\.00/);
  assert.match(w, /Customer: cus_demo_0001/);
  assert.match(w, /Tags: plan: proseats: 5/);
  assert.deepEqual(saleFacts({ value_minor: null, currency: null, customer_ref: null, tags: null }), [], "a lead without a value: nothing added");
}

console.log("revenue: all passed");
