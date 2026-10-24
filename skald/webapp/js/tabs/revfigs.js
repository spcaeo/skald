// Revenue (2.32.0): the sums the Revenue tab shows, from conversions.json's `revenue` block
// per day and its `ltv` (DATA-CONTRACT-CONVERSIONS.md). No DOM here, so node tests it
// (tests/js/revenue.mjs). The rules:
//
//   * money is summed per currency, never converted: an exchange rate is a figure Skald
//     cannot prove, so EUR and USD are two sets of figures, side by side
//   * amounts arrive in minor units (cents); the decimals of each currency come from the
//     file (`currencies`, {currency: decimals}, the table the counting used), and are shown
//     with Intl.NumberFormat in that currency
//   * only "ok" days that carry a `revenue` block are summed (checked by the second count;
//     `{}` is a known none); a withheld day, or a withheld block, is named and left out,
//     never zero; an ok day without a block, or before `revenue_since` (the first day a
//     value was kept), is not recorded
//   * revenue per visitor is net revenue over the visitors of the same verified days: two
//     counted figures, divided; given over at least min_rate visitors
//
// Every other module that shows money imports from here.

const LOCALE = "en-US";
// The file's `currencies` table wins. This copy of the server's (conversions DECIMALS) is
// only for an amount whose currency the file does not list: a lead's drawer, or a refund
// without a counted sale.
const ZERO = new Set(["BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF"]);
const THREE = new Set(["BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"]);
const FOUR = new Set(["CLF", "UYW"]);

// The breakdowns of the `by` block, in the order the options list them.
export const BY = [["source", "Source (last touch)"], ["first_source", "First touch"], ["campaign", "Campaign"], ["landing", "Landing page"],
  ["country", "Country"], ["device", "Device"], ["tool", "Reported by"], ["label", "Label"], ["tag", "Tag"]];
export const byName = (k) => (BY.find(([x]) => x === k) || [null, k])[1];

export const isCurrency = (c) => /^[A-Z]{3}$/.test(String(c || ""));

/* The decimals of a currency: the file's table, else ISO 4217's. */
export function decimalsOf(f, cur) {
  const d = f?.currencies?.[cur];
  if (Number.isInteger(d) && d >= 0 && d <= 4) return d;
  return ZERO.has(cur) ? 0 : THREE.has(cur) ? 3 : FOUR.has(cur) ? 4 : 2;
}

const formats = new Map();
function formatter(cur, d) {
  const k = `${cur}:${d}`;
  if (!formats.has(k)) {
    let fmt;
    try { fmt = new Intl.NumberFormat(LOCALE, { style: "currency", currency: cur, minimumFractionDigits: d, maximumFractionDigits: d }); } catch { fmt = null; }
    formats.set(k, fmt);
  }
  return formats.get(k);
}

/* Minor units as money: money(4900, "USD", f) -> "$49.00"; money(1200, "JPY") -> "¥1,200".
   null (not recorded) is "-", never "$0.00". */
export function money(minor, cur, f = null) {
  if (minor == null || !Number.isFinite(minor) || !isCurrency(cur)) return "-";
  const d = decimalsOf(f, cur);
  const fmt = formatter(cur, d);
  const v = minor / 10 ** d;
  return fmt ? fmt.format(v) : `${v.toFixed(d)} ${cur}`;
}

/* The same amount as a plain decimal for a CSV: "49.00". */
export function decimal(minor, cur, f = null) {
  if (minor == null || !Number.isFinite(minor)) return "";
  const d = decimalsOf(f, cur);
  return (minor / 10 ** d).toFixed(d);
}

const held = (b) => !!b && !Array.isArray(b) && b.state === "withheld";
// Whether the site has any counted value: `currencies` is null until one is kept.
export function hasRevenue(f) {
  return !!f && Array.isArray(f.days) && !!f.currencies && typeof f.currencies === "object" && Object.keys(f.currencies).length > 0;
}

/* The first day a value was kept (the file's `revenue_since`): revenue is recorded from it on.
   null: no value yet, or withheld (sinceHeld says why). */
export function firstDay(f) {
  const d = f?.revenue_since;
  return typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null;
}
export const sinceHeld = (f) => (held(f?.revenue_since) ? f.revenue_since.why || "" : null);

/* The days asked for, as the revenue figures see them:
     ok       [{day, revenue}]  checked days with a revenue block ({} when no sale)
     held     [{day, why}]      the day, or its revenue block, withheld by the second count
     missing  [day]             not in the file, without a block, before the first value, or
                                not checked */
export function revenueDays(f, wanted) {
  const at = new Map((f?.days || []).map((d) => [d.day, d]));
  const since = firstDay(f);
  const out = { ok: [], held: [], missing: [] };
  for (const day of wanted) {
    const e = at.get(day);
    if (since && day < since && e?.state !== "withheld") out.missing.push(day);
    else if (e?.state === "withheld") out.held.push({ day, why: e.why || "" });
    else if (e?.state === "ok" && held(e.revenue)) out.held.push({ day, why: e.revenue.why || "" });
    else if (e?.state === "ok" && e.revenue && typeof e.revenue === "object" && !Array.isArray(e.revenue)) out.ok.push({ day, revenue: e.revenue });
    else out.missing.push(day);
  }
  return out;
}

const KEYS = ["gross_minor", "refunded_minor", "net_minor", "sales", "refunds", "new_customers", "renewals"];

function addBy(into, by) {
  for (const [dim, per] of Object.entries(by || {})) {
    into[dim] = into[dim] || {};
    if (dim === "tag") {
      for (const [k, vals] of Object.entries(per || {})) {
        into.tag[k] = into.tag[k] || {};
        for (const [v, x] of Object.entries(vals || {})) addPair(into.tag[k], v, x);
      }
    } else for (const [name, x] of Object.entries(per || {})) addPair(into[dim], name, x);
  }
}
function addPair(into, name, x) {
  const e = into[name] || (into[name] = { net_minor: 0, sales: 0 });
  e.net_minor += x?.net_minor || 0;
  e.sales += x?.sales || 0;
}

/* The ok days' figures per currency: {CUR: {gross_minor, ..., renewals, by}}. */
export function sumRevenue(okDays) {
  const out = {};
  for (const { revenue } of okDays) {
    for (const [cur, x] of Object.entries(revenue || {})) {
      if (!isCurrency(cur) || !x || typeof x !== "object") continue;
      const t = out[cur] || (out[cur] = { ...Object.fromEntries(KEYS.map((k) => [k, 0])), by: {} });
      for (const k of KEYS) t[k] += x[k] || 0;
      addBy(t.by, x.by);
    }
  }
  return out;
}

/* The currencies, most net revenue first (then by sales, then A to Z). */
export function currencies(totals) {
  return Object.keys(totals).sort((a, b) => totals[b].net_minor - totals[a].net_minor || totals[b].sales - totals[a].sales || a.localeCompare(b));
}

/* The currency shown: the one in the address when the period has it, else the first. */
export function pickCurrency(list, asked) {
  const want = String(asked || "").toUpperCase();
  return list.includes(want) ? want : list[0] || null;
}

/* tag=plan:pro in the address -> ["plan", "pro"]; tag=plan -> ["plan", ""]; else null. */
export function tagOf(v) {
  const m = /^([a-z0-9_]{1,24})(?::([a-z0-9_.-]{1,40}))?$/.exec(String(v || ""));
  return m ? [m[1], m[2] || ""] : null;
}

/* The tag choices of a currency's period: each key ("plan", every value of it), then each
   pair ([["plan:pro", "plan = pro"], ...]), most net first. */
export function tagChoices(t) {
  const keys = [], out = [];
  for (const [k, vals] of Object.entries(t?.by?.tag || {})) {
    keys.push([k, `${k}: every value`, Object.values(vals).reduce((a, x) => a + (x.net_minor || 0), 0)]);
    for (const [v, x] of Object.entries(vals)) out.push([`${k}:${v}`, `${k} = ${v}`, x.net_minor]);
  }
  const order = (a, b) => b[2] - a[2] || a[0].localeCompare(b[0]);
  return [...keys.sort(order), ...out.sort(order)].map(([k, w]) => [k, w]);
}

/* Refunds stored but counted nowhere (`refunds_without_sale`, every row kept): no counted
   sale, a value that could not be read, or another currency than the sale's. {count, currencies} | {held: why} (the block, or `withheld`, says so) | null. */
export function orphanRefunds(f) {
  const r = f?.refunds_without_sale;
  const why = f?.withheld?.refunds_without_sale || (held(r) ? r.why || "" : null);
  if (why != null) return { held: String(why) };
  return r && r.count > 0 ? { count: r.count, currencies: r.currencies || {} } : null;
}

/* One breakdown's rows: [{k, net_minor, sales}], most net first. by=tag: one row per
   key = value (only the chosen key's, when one is chosen). */
export function rowsOf(t, dim, tagKey = "") {
  const per = t?.by?.[dim] || {};
  const rows = [];
  if (dim === "tag") {
    for (const [k, vals] of Object.entries(per)) if (!tagKey || k === tagKey) for (const [v, x] of Object.entries(vals)) rows.push({ k: `${k} = ${v}`, key: k, value: v, net_minor: x.net_minor, sales: x.sales });
  } else for (const [k, x] of Object.entries(per)) rows.push({ k, net_minor: x.net_minor, sales: x.sales });
  return rows.sort((a, b) => b.net_minor - a.net_minor || b.sales - a.sales || a.k.localeCompare(b.k));
}

/* Visitors of the same verified days (the log's own figure, m.byDay readers on "ok" days):
   {visitors, days} over the revenue's ok days that are also whole in the log. */
export function visitorsOn(m, okDays) {
  let visitors = 0, days = 0;
  for (const { day } of okDays) {
    const e = m?.byDay?.get?.(day);
    if (e?.state === "ok" && typeof e.readers === "number") { visitors += e.readers; days += 1; }
  }
  return { visitors, days };
}

/* Revenue per visitor in minor units (rounded), or null under `min` visitors or when not every
   ok day has its visitors (then the two figures would not cover the same days). */
export function perVisitor(net, v, okCount, min = 10) {
  if (!v || v.days !== okCount || v.visitors < min) return null;
  return Math.round(net / v.visitors);
}

/* The lifetime figures per currency ({CUR: {customers, net_minor, renewals, repeat_customers,
   first_day, by_first_source}}), or null: none, or withheld (ltvHeld says why). */
export function ltvOf(f) {
  const l = f?.ltv;
  return l && !held(l) && l.currencies && typeof l.currencies === "object" ? l.currencies : null;
}
export const ltvHeld = (f) => (held(f?.ltv) ? f.ltv.why || "" : null);

/* Lifetime value by first source, for one currency: rows [{k, customers, net_minor, avg_minor,
   renewals, repeat_customers, rate}], rate (repeat customers / customers) only over `min`. */
export function ltvRows(f, cur, min = 10) {
  const l = ltvOf(f)?.[cur];
  if (!l) return [];
  return Object.entries(l.by_first_source || {}).map(([k, x]) => ({ k, customers: x.customers || 0, net_minor: x.net_minor || 0,
    avg_minor: x.customers ? Math.round((x.net_minor || 0) / x.customers) : null, renewals: x.renewals || 0, repeat_customers: x.repeat_customers || 0,
    rate: (x.customers || 0) >= min ? (x.repeat_customers || 0) / x.customers : null }))
    .sort((a, b) => b.net_minor - a.net_minor || b.customers - a.customers || a.k.localeCompare(b.k));
}
