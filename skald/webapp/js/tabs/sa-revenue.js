// Leads & sales > Revenue (2.32.0): "Which sources, pages and campaigns made money?" The
// sales that carried a value (Stripe's amounts, or `value` and `currency` sent with a lead
// through the lead hook, the json hook, Zapier, Make, n8n or a lead file), summed per
// currency from conversions.json's `revenue` block (revfigs.js), never converted.
//
//   one row of options     Currency (cur, when the period has more than one), Breakdown
//                          (by: source, first touch, campaign, landing page, country,
//                          device, reported by, label, tag), Tag (tag=key:value)
//   one row of numbers     net revenue, sales, refunds, new customers, renewals, revenue
//                          per visitor (net revenue over the visitors of the same days: only
//                          the days with revenue figures, never those before the first value)
//   the main table         net revenue and sales by the chosen breakdown
//   a fold of its own      lifetime value by first source (every sale kept, not the period)
//
// A tag is not crossed with the other breakdowns: with one chosen, the numbers are that
// tag's own net revenue and sales, the table lists the values of its key, and the row's (i)
// says so. A withheld day is left out of every figure and said once, in the words the
// conversions figures use; a site that never sent a value gets the how-to. Values are recorded
// from the file's revenue_since: the tab says from which day, and a day before it is not
// recorded, never zero.

import { h, n, short, pct1 } from "../ui.js";
import * as S from "../state.js";
import { rangeOf } from "../data.js";
import { table } from "../table.js";
import { label as valueLabel } from "../drill.js";
import { fixed } from "./common.js";
import { tiles } from "./tiles.js";
import { convFile, toolName, minRate } from "./leadfigs.js";
import { tabHead, optionsRow, choice, select, emptyState } from "./sa-options.js";
import { BY, byName, money, decimal, hasRevenue, firstDay, sinceHeld, revenueDays, sumRevenue, currencies, pickCurrency, tagOf, tagChoices, orphanRefunds, rowsOf, visitorsOn, perVisitor, ltvOf, ltvHeld, ltvRows } from "./revfigs.js";

export const HELP = "#help?part=revenue";
const QUESTION = "Which sources, pages and campaigns made money? Sales with a value, summed per currency, refunds taken off.";
const HEAD_HELP = "Counted from the sales that carried a value: Stripe's amounts, or value and currency sent with a lead by your site's server, the json hook (Zapier, Make, n8n) or a lead file. Each currency is summed apart and never converted. Rows marked test are never counted.";
const REFUND_WORDS = "A refund counts on the day it arrives, against its sale's own source; a later, larger total counts the difference on its own day. It counts only against a sale Skald counts, in that sale's currency, and never past the sale's value.";
const SUM_WORDS = "Each currency is summed apart: Skald never converts one into another, because an exchange rate is not something it can check.";

const bad = (words) => h("div", { class: "state bad", role: "alert" }, h("div", null, words));
const plural = (k, one, many = `${one}s`) => `${n(k)} ${k === 1 ? one : many}`;

function heldWords(list) {
  return `${list.length} day${list.length === 1 ? "" : "s"} withheld (${list.slice(0, 5).map((d) => short(d.day)).join(", ")}${list.length > 5 ? "..." : ""}): left out of every figure below, never counted as zero. Why: ${list[0].why || "the second count disagrees."}`;
}

// A breakdown's value in words: a tool by its name, a country by its name, "Unknown" as not
// recorded, a sale without a label as the label list says it.
function words(dim, k) {
  if (k === "Unknown" || k === "(none)") return "Not recorded";
  if (k === "(no label)") return "No label";
  if (dim === "tool") return toolName(k);
  if (dim === "country") return valueLabel("country", k, k);
  return k;
}

/* The numbers. t: the currency's totals; v: visitors of the same days; pick: a tag's own
   [key, value, {net_minor, sales}] when one is chosen. */
function numbers(t, cur, f, v, okCount, pick) {
  const min = minRate(f);
  if (pick) {
    const [k, val, x] = pick;
    const off = "Not split by tag: shown with Every tag.";
    return tiles([
      { label: `Net revenue, ${k} = ${val}`, value: money(x.net_minor, cur, f), info: `Net revenue of the sales tagged ${k} = ${val}: their value, less what was refunded on them. ${SUM_WORDS}`, more: HELP, line: `${cur}, tagged ${k} = ${val}` },
      { label: "Sales", value: x.sales, info: `Sales tagged ${k} = ${val}, counted once each.`, more: HELP, line: "with this tag" },
      { label: "Refunds, customers, renewals", value: null, info: off, line: off },
    ]);
  }
  const pv = perVisitor(t.net_minor, v, okCount, min);
  const pvLine = pv != null ? `${money(t.net_minor, cur, f)} over ${plural(v.visitors, "visitor")}, the same ${plural(v.days, "day")}`
    : v.days !== okCount ? "the visitors are not whole on every day of these figures" : `too few visitors to say (${n(v.visitors)}, under ${n(min)})`;
  return tiles([
    { label: "Net revenue", value: money(t.net_minor, cur, f), info: `The value of the sales, less what was refunded in the period. ${SUM_WORDS}`, more: HELP,
      line: t.refunded_minor ? `${money(t.gross_minor, cur, f)} sold, ${money(t.refunded_minor, cur, f)} refunded` : `${money(t.gross_minor, cur, f)} sold, nothing refunded` },
    { label: "Sales", value: t.sales, info: "Paid or completed sales that carried a value, each counted once (the paid step when a sale reports both).", more: HELP, line: cur },
    { label: "Refunds", value: t.refunds, info: `${REFUND_WORDS} Each refund that arrived is counted once.`, more: HELP, line: t.refunds ? `${money(t.refunded_minor, cur, f)} refunded` : "none" },
    { label: "New customers", value: t.new_customers, info: "First paid sales of a customer (by the customer reference your tool sends; a sale without one is its own customer).", more: HELP, line: "first paid sale" },
    { label: "Renewals", value: t.renewals, info: "Paid sales of a customer who had paid before: a subscription's next invoice, a second order.", more: HELP, line: "repeat paid sales" },
    { label: "Revenue per visitor", value: pv != null ? money(pv, cur, f) : null, info: `Net revenue divided by the visitors of the same verified days: two counted figures, divided, given over at least ${n(min)} visitors.`, more: HELP, line: pvLine },
  ]);
}

// The other currencies of the period, one button each: never added to the one shown.
function others(list, cur, totals, f) {
  const rest = list.filter((c) => c !== cur);
  if (!rest.length) return null;
  return h("p", { class: "note rv-others" }, "Also in this period, never added: ",
    rest.map((c, i) => [i ? ", " : "", h("button", { type: "button", class: "linkish", onclick: () => S.set({ cur: c }) }, `${money(totals[c].net_minor, c, f)} net`), ` from ${plural(totals[c].sales, "sale")}`]), ".");
}

function breakdown(t, cur, f, dim, tagKey) {
  const rows = rowsOf(t, dim, tagKey).map((x) => ({ ...x, label: dim === "tag" ? x.k : words(dim, x.k) }));
  const net = rows.reduce((a, x) => a + x.net_minor, 0);
  const sales = rows.reduce((a, x) => a + x.sales, 0);
  const min = minRate(f);
  const cols = [
    { key: "label", label: byName(dim), path: dim === "landing", href: dim === "landing" ? (x) => x.k : undefined, country: dim === "country" ? (x) => x.k : undefined,
      sort: (x) => (x.label === "Not recorded" ? null : x.label) },
    { key: "net_minor", label: `Net revenue (${cur})`, num: true, fmt: (v) => money(v, cur, f), csv: (x) => decimal(x.net_minor, cur, f) },
    { key: "sales", label: "Sales", num: true },
    { key: "share", label: "Share of net", num: true, sort: (x) => x.net_minor,
      fmt: (_, x) => (sales >= min && net > 0 && x.net_minor >= 0 ? pct1(x.net_minor, net) : ""), csv: (x) => (sales >= min && net > 0 && x.net_minor >= 0 ? (x.net_minor / net).toFixed(4) : "") },
  ];
  const what = dim === "tag" ? (tagKey ? `the tag ${tagKey}` : "tag") : byName(dim).toLowerCase();
  return h("section", { class: "s" }, h("h2", null, `Revenue by ${what}`),
    h("div", { class: "sheet" }, table(cols, { caption: `Net revenue by ${what}, ${cur}`, ns: "rev", rows, file: `revenue-by-${dim}-${cur.toLowerCase()}.csv`, search: rows.length > 12, limit: 12, sortKey: "net_minor",
      empty: dim === "tag" ? "No sale in this period carried a tag." : "None in this period." })),
    h("p", { class: "note" }, dim === "first_source" ? "First touch: where the customer's browser first came from, as the sale reported it. " : "",
      dim === "tag" ? "Tags are the labels your site's server sends with a sale (for example plan = pro). A sale with two tags counts under each. " : "",
      `Shares are given over at least ${n(min)} sales. A refund counts against the sale's own ${dim === "tag" ? "tags" : "source"}, on the day it arrived.`));
}

// Lifetime value by first source: its own window (every sale kept), folded at the bottom.
function lifetime(f, cur) {
  const l = ltvOf(f)?.[cur];
  const period = l?.first_day ? `every sale kept, since ${short(l.first_day)}` : "every sale kept";
  const why = ltvHeld(f);
  if (why != null) return fixed("Lifetime value, by first source", period, bad(`Withheld: the second count disagrees, so no lifetime figure is shown. ${why}`));
  const min = minRate(f);
  const rows = ltvRows(f, cur, min).map((x) => ({ ...x, label: words("first_source", x.k) }));
  if (!rows.length) return fixed("Lifetime value, by first source", period, h("p", { class: "empty" }, `No paying customer in ${cur} yet.`));
  const cols = [
    { key: "label", label: "First source", sort: (x) => (x.label === "Not recorded" ? null : x.label) },
    { key: "customers", label: "Customers", num: true },
    { key: "net_minor", label: `Net revenue (${cur})`, num: true, fmt: (v) => money(v, cur, f), csv: (x) => decimal(x.net_minor, cur, f) },
    { key: "avg_minor", label: "Average per customer", num: true, fmt: (v) => money(v, cur, f), csv: (x) => decimal(x.avg_minor, cur, f) },
    { key: "renewals", label: "Renewals", num: true },
    { key: "rate", label: "Repeat rate", num: true, sort: (x) => x.rate, fmt: (v, x) => (v == null ? h("span", { class: "few" }, `too few (${n(x.customers)})`) : pct1(x.repeat_customers, x.customers)),
      csv: (x) => (x.rate == null ? "" : x.rate.toFixed(4)) },
  ];
  return fixed("Lifetime value, by first source", period,
    h("p", { class: "sub" }, `Every ${cur} customer, by the first source of their first paid sale: how many, what they paid in all (refunds taken off), the average per customer, their renewals and the share who paid again.`),
    h("div", { class: "sheet" }, table(cols, { caption: `Lifetime value by first source, ${cur}`, ns: "revl", rows, file: `revenue-lifetime-${cur.toLowerCase()}.csv`, search: false, limit: 12, sortKey: "net_minor" })),
    h("p", { class: "note" }, `A customer is one customer reference your tool sends (a Stripe customer, your app's account ID); a sale without one is its own customer. Counted over every sale Skald keeps (Settings > Privacy & retention applies), not the date range above. The average and the repeat rate are worked out here from two counted figures; the repeat rate is given over at least ${n(min)} customers.`));
}

export default function revenue(m, s) {
  const r = rangeOf(m, s);
  const top = tabHead("Revenue", QUESTION, r, { help: HEAD_HELP, more: HELP });
  const f = convFile(m);
  const howTo = ["How to send value and currency", HELP];
  if (!f) {
    const raw = m.x.conversions;
    return [...top, emptyState(raw?.state === "error" ? `The revenue could not be built: ${raw.error || "no reason given"}.` : "No revenue yet: nothing has reported a sale for this site.", howTo, { bad: raw?.state === "error" })];
  }
  if (!hasRevenue(f)) {
    return [...top, emptyState("No revenue yet. Send value and currency with each sale (for example value 49.00, currency USD) through the lead hook, the json hook, Zapier, Make, n8n or a lead file, or connect Stripe: each sale then shows here, by source, page and campaign.", howTo)];
  }
  const wanted = r.kind === "today" ? [m.today] : r.days.map((d) => d.day);
  const got = revenueDays(f, wanted);
  const out = [...top];
  if (got.held.length) out.push(bad(heldWords(got.held)));
  if (!got.ok.length) {
    const since = firstDay(f);
    out.push(emptyState(`No revenue figures for ${r.kind === "today" ? "today" : "this period"}${since ? `: values are recorded from ${short(since)} on` : ""}. A day without figures is not recorded, never zero.`,
      s.range === "all" ? null : ["Show all time", () => S.set({ range: "all" })]));
    out.push(lifetimeAll(f), orphans(f));
    return out.filter(Boolean);
  }
  const totals = sumRevenue(got.ok);
  const list = currencies(totals);
  if (!list.length) {
    out.push(emptyState(`No sale with a value in this period (${plural(got.ok.length, "day")} recorded).`, s.range === "all" ? null : ["Show all time", () => S.set({ range: "all" })]));
    out.push(lifetimeAll(f), orphans(f));
    return out.filter(Boolean);
  }
  const cur = pickCurrency(list, s.cur);
  const t = totals[cur];
  const tags = tagChoices(t);
  const asked = tagOf(s.tag);
  const x = asked && asked[1] ? t.by?.tag?.[asked[0]]?.[asked[1]] : null;
  const pick = x ? [asked[0], asked[1], x] : null;
  // tag=plan, no value: every value of the tag plan, as the table (the numbers stay whole).
  const tagKey = pick ? pick[0] : asked && !asked[1] && t.by?.tag?.[asked[0]] ? asked[0] : "";
  const dim = pick || tagKey ? "tag" : BY.some(([k]) => k === s.by) ? s.by : "source";
  const notes = [SUM_WORDS,
    pick ? `Tag ${pick[0]} = ${pick[1]}: the numbers are that tag's own; refunds, customers, renewals and the other breakdowns are not split by tag, so they show with Every tag.` : tagKey ? `Tag ${tagKey}, every value: the table lists each value of it; the numbers are every sale's.` : "",
    got.missing.length ? `${plural(got.missing.length, "day")} of the period not recorded (before values were stored, or not checked yet), never zero.` : ""];
  out.push(...optionsRow("Revenue options", [
    list.length > 1 ? choice("Currency", cur, list.map((c) => [c, c, `Figures in ${c}, never converted`]), (k) => S.set({ cur: k })) : null,
    select("Breakdown", dim, BY, (v) => S.set({ by: v === "source" ? "" : v }), { all: null, off: pick || tagKey ? "With a tag chosen, the table lists the values of its key." : "" }),
    select("Tag", pick ? `${pick[0]}:${pick[1]}` : tagKey, tags, (v) => S.set({ tag: v }), { all: "Every tag", off: tags.length || s.tag ? "" : "No sale in this period carried a tag." }),
  ], { notes, help: HELP }));
  if (s.tag && !pick && !tagKey) out.push(h("p", { class: "note" }, `No ${cur} sale in this period carries the tag ${asked ? (asked[1] ? `${asked[0]} = ${asked[1]}` : asked[0]) : String(s.tag)}. `,
    h("button", { type: "button", class: "linkish", onclick: () => S.set({ tag: "" }) }, "Show every tag")));
  out.push(h("section", { class: "s" }, numbers(t, cur, f, visitorsOn(m, got.ok), got.ok.length, pick)), others(list, cur, totals, f));
  out.push(breakdown(t, cur, f, dim, tagKey));
  out.push(orphans(f));
  out.push(lifetime(f, cur));
  out.push(h("p", { class: "note" }, `${plural(got.ok.length, "day")} of ${n(wanted.length)} recorded. ${recordedFrom(f)} ${REFUND_WORDS} ${f.as_known || ""}`.replace(/\s+/g, " ").trim()));
  return out.filter(Boolean);
}

// From which day values are kept: the days before it are not recorded, never zero.
function recordedFrom(f) {
  const since = firstDay(f);
  if (since) return `Values are recorded from ${short(since)}: a day before it is not recorded, never zero.`;
  const why = sinceHeld(f);
  return why != null ? `The first day with a value is withheld: the second count disagrees. ${why}` : "";
}

// Refunds Skald keeps but counts nowhere, over every row kept: no counted sale, a value that
// could not be read, or another currency than the sale's (kept without its value).
function orphans(f) {
  const o = orphanRefunds(f);
  if (!o) return null;
  if (o.held) return h("p", { class: "note" }, `Refunds counted nowhere: withheld, the second count disagrees. ${o.held}`);
  const sums = Object.entries(o.currencies).map(([c, v]) => money(v, c, f)).join(", ");
  return h("p", { class: "note" }, `${plural(o.count, "refund")} kept but counted nowhere${sums ? ` (${sums})` : ""}, over every row kept: never taken off any figure here. A refund counts only against a sale Skald counts, with a value in that sale's currency. Listed here: a refund whose sale is a test, was removed or never came, one whose value could not be read, and one sent in another currency than its sale (kept without its value)${sums ? "; the amounts are those of the refunds kept with a value" : ""}.`);
}

// No figure in the period: the lifetime value still shows, in its first currency.
function lifetimeAll(f) {
  const cur = Object.keys(ltvOf(f) || {}).sort()[0];
  return cur || ltvHeld(f) != null ? lifetime(f, cur || "") : null;
}
