// Security > Fake browsers and scrapers (2.21): the requests Skald already moved from people
// to bots because the "browser" never rendered the page, read faster than a person can,
// fetched robots.txt or a sitemap, or claimed a crawler's name it could not prove; grouped
// by address and network, with the pages they took. Named crawlers live on AI & bots.

import { h, n } from "../ui.js";
import { table } from "../table.js";
import { tiles } from "./tiles.js";
import { blist } from "./common.js";
import { ranked } from "../data.js";
import { emptyState } from "./sa-options.js";
import { merge, networkOf } from "../sec-data.js";
import { secTab, loadAddresses, spanOf, flagOf, at, addressWords, missingNote } from "./sec-common.js";
import { label } from "./sec-scanners.js";

export function kindWords(k) {
  if (!k) return "-";
  if (k.startsWith("claims:")) return `Claims to be ${k.slice(7)}`;
  return { not_rendered: "Never rendered the page", too_fast: "Too fast for a person", crawler_session: "Browser-like crawler (robots.txt or sitemap)" }[k] || k;
}

export default function fake(m, s) {
  return secTab(m, s, {
    title: "Fake browsers and scrapers",
    question: "Which \"browsers\" were not people, and what did they take?",
    help: "Skald counts a visit as a person only if the browser drew the page. These sent a browser's user agent but never loaded the page's files, read pages faster than anyone can, fetched robots.txt or a sitemap like a crawler, or claimed to be Googlebot (or another crawler) from an address that crawler does not use. They are counted under bots, never as visitors. Named crawlers that are what they say are on AI & bots.",
    draw: ({ f, r, p, t }) => {
      if (!t.days) return [emptyState("Not recorded for this period."), missingNote(p, t)];
      const k = t.fake.kinds;
      const claims = Object.entries(k).filter(([x]) => x.startsWith("claims:")).reduce((a, [, v]) => a + v, 0);
      const parts = [tiles([
        { label: "Fake-browser requests", value: t.fake.requests, info: "Requests filed under bots for one of the reasons below." },
        { label: "Never rendered", value: k.not_rendered || 0, info: "A browser that took pages and never loaded their scripts and styles." },
        { label: "Too fast", value: k.too_fast || 0, info: "Six pages or more inside two seconds." },
        { label: "Browser-like crawlers", value: k.crawler_session || 0, info: "A browser that fetched robots.txt or a sitemap." },
        { label: "False crawler claims", value: claims, info: "Said it was Googlebot, GPTBot... from an address that crawler does not use." },
      ])];
      parts.push(h("div", { class: "sec-two" },
        h("div", { class: "card" }, h("h2", null, "What gave them away"),
          blist(ranked(k), { color: "var(--g-bots)", total: t.fake.requests, label: kindWords, empty: "None in this period." })),
        h("div", { class: "card" }, h("h2", null, "Pages they took"),
          blist(ranked(t.fake.pages).filter(([x]) => x !== "(all others)"), { color: "var(--g-bots)", label: (x) => x, empty: "No page view." }),
          h("p", { class: "note" }, "Each day's top 10 pages, summed."))));
      const holder = h("div", null, h("p", { class: "empty" }, "Loading…"));
      parts.push(holder, h("p", { class: "note" }, "Named crawlers and assistants, checked against their owners' address lists: ", h("a", { href: "#ai/crawlers" }, "AI & bots > Crawlers"), "."), missingNote(p, t));
      const [first, last] = spanOf(m, r);
      loadAddresses(first, last).then((ans) => {
        const rows = merge(t.who, ans?.ok ? ans : null).filter((x) => x.fake_requests).map((x) => ({ ...x, net: x.ip ? networkOf(x.ip) : "" }));
        const words = addressWords(ans, f);
        holder.replaceChildren(table([
          { key: "ip", label: "Address", fmt: (v, row) => label(row), sort: (row) => row.ip || "~", csv: (row) => label(row) },
          { key: "net", label: "Network", fmt: (v, row) => v || "-", hide: !rows.some((x) => x.net) },
          { key: "country", label: "Country", fmt: (v) => flagOf(v), csv: (row) => row.country || "" },
          { key: "fake", label: "What gave it away", fmt: (v) => kindWords(v) },
          { key: "fake_requests", label: "Requests", num: true },
          { key: "pages", label: "Pages taken", fmt: (v) => Object.keys(v || {}).filter((x) => x !== "(all others)").slice(0, 3).join(", ") || "-", sort: (row) => Object.keys(row.pages || {}).length },
          { key: "last", label: "Last seen", type: "date", fmt: (v) => at(v), hide: true },
        ], { caption: "Fake browsers by address", ns: "sxf", file: "fake-browsers.csv", rows, sortKey: "fake_requests", dir: -1, limit: 15,
          empty: "No fake browser in this period." }), ...(words ? [h("p", { class: "note" }, words)] : []));
      });
      return parts;
    },
  });
}
