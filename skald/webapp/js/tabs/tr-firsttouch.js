// Traffic > Sources: "Where returning visitors first came from" (2.12.0).
//
// Most visits say Direct: no referrer. Many are people coming back. For each
// Direct visit of the range, where the same visitor's first visit we know of
// came from (firsttouch.py: the visitor ID, else the kept address and browser,
// else the 30-day code), by source type and by referring site; and every visit
// with an earlier one known, by where it first came from. Each day's figures
// are recounted by the audit (audit_firsttouch.py); a day that disagrees is
// withheld with the rest of its figures. A day counted before first touch was,
// or with no link on, has none: left out and said.

import { h, n, pct } from "../ui.js";
import { shown } from "../labels.js";
import { blist, countTable, fileName } from "./common.js";
import { tiles } from "./tiles.js";

const NAMES = { "(none)": "No referrer", "(not kept)": "Referrer not kept (linked by the 30-day code)", "(this site)": "This site" };
const label = (k) => NAMES[k] || shown(k);
const LINK = { vid: "the visitor ID", address: "the kept address and browser", hash: "the 30-day code" };

function coverage(r, live) {
  if (live) return "";
  const ok = (r.days || []).filter((d) => d.state === "ok");
  const without = ok.filter((d) => !d.first_touch).length;
  return without ? `${n(without)} of the ${n(ok.length)} verified days of this range have no first-touch figures (counted before 2.12.0, or no link was on): left out.` : "";
}

export function firstTouch(t, r, { live = false } = {}) {
  const ft = t?.first_touch;
  const sec = h("section", { class: "s" }, h("h2", null, "Where returning visitors first came from"),
    h("p", { class: "sub" }, "A Direct visit had no referrer and no campaign tag. Many are people coming back: here is where the same visitor first came from, as far as anything kept can tell."));
  if (!ft || !ft.direct) {
    sec.append(h("p", { class: "empty" }, "Not recorded for this range: first touch is counted from 2.12.0, on days with a visitor ID, kept addresses or the 30-day code."));
    return sec;
  }
  const d = ft.direct, ret = ft.returning || {};
  const by = ft.by || {};
  const links = Object.entries(LINK).filter(([k]) => by[k]).map(([k, w]) => `${n(by[k])} by ${w}`);
  sec.append(
    tiles([
      { label: "Direct visits", value: d.visits, line: "no referrer, no campaign tag" },
      { label: "Came before", value: d.known, line: `${pct(d.known, d.visits)} of Direct: an earlier visit is known`, info: "The same visitor had an earlier visit: by its visitor ID, its kept address and browser, or the 30-day code." },
      { label: "First visit we know of", value: d.none, line: "no earlier visit found: never a guess" },
      d.off ? { label: "Could not be linked", value: d.off, line: "no visitor ID, no address kept, no 30-day code" } : null]),
    h("div", { class: "cols" },
      h("div", { class: "sheet" }, h("h3", null, "Direct visits, by where they first came from"),
        h("p", { class: "card-m" }, `the ${n(d.known)} Direct visits with an earlier visit known`),
        blist(Object.entries(d.first || {}).sort((a, b) => b[1] - a[1]), { drill: "source", label: shown, total: d.known, empty: "No Direct visit had an earlier visit known." })),
      h("div", { class: "sheet" }, h("h3", null, "Their first referring sites"),
        h("p", { class: "card-m" }, "the site or assistant that sent the first visit"),
        blist(Object.entries(d.referrer || {}).sort((a, b) => b[1] - a[1]), { label, total: d.known, empty: "None." }))),
    h("div", { class: "sheet" }, h("h3", null, "Returning visits, by where they first came from"),
      h("p", { class: "card-m" }, `every visit of the range with an earlier visit known (${n(ret.visits || 0)} of ${n(ft.visits || 0)}), whatever its own source`),
      blist(Object.entries(ret.first || {}).sort((a, b) => b[1] - a[1]), { drill: "source", label: shown, total: ret.visits, empty: "No visit had an earlier visit known." }),
      h("h4", { class: "ft-h4" }, "By their first referring site"),
      countTable(ret.referrer || {}, { caption: "Returning visits by first referrer", file: fileName("first-referrers", r), key: "First referrer", value: "Visits", label, limit: 8 })),
    h("p", { class: "note" }, [
      "The first visit we know of for the same visitor: by its visitor ID when the page script sent one, else by the same address with the same browser and system while the site keeps addresses, else by the 30-day code (that gives the day and source type, not the referrer). Nothing is guessed: no earlier visit known is \"first visit we know of\".",
      links.length ? ` Linked: ${links.join(", ")}.` : "",
      ` ${coverage(r, live)}`].join("")));
  return sec;
}
