// Security > Block list (2.21): the worst addresses and networks of the period, ranked by
// probes, then attack attempts, to export as nginx deny lines, a Cloudflare IP list CSV or a
// plain list (fail2ban, ipset). Owners and admins only, and only what the site keeps
// (privacy.keep_ips): full addresses and their networks; with "short", networks only; with
// "off", nothing. Review before blocking: a shared address or a CDN can carry real visitors.

import { h, n } from "../ui.js";
import { table, download } from "../table.js";
import { emptyState } from "./sa-options.js";
import { merge, blockList, nginx, cloudflare, plain } from "../sec-data.js";
import { secTab, mayAddresses, loadAddresses, spanOf, flagOf, addressWords, missingNote } from "./sec-common.js";

const REVIEW = "Review before you block. A shared address (an office, a mobile network, a VPN) or a CDN can carry real visitors too, and a scanner moves on to a new address within days. Blocking at the web server or at Cloudflare stops the requests; it does not fix a file that answered when it should not (Is anything exposed?).";

export default function block(m, s) {
  return secTab(m, s, {
    title: "Block list",
    question: "Which addresses and networks should we block, and how?",
    help: REVIEW,
    draw: ({ f, r, p, t }) => {
      if (!t.days) return [emptyState("Not recorded for this period."), missingNote(p, t)];
      if (!mayAddresses()) return [emptyState("Only owners and admins see addresses, so only they see the block list."), missingNote(p, t)];
      const holder = h("div", null, h("p", { class: "empty" }, "Loading the addresses…"));
      const [first, last] = spanOf(m, r);
      loadAddresses(first, last).then((ans) => {
        if (!ans?.ok) return holder.replaceChildren(emptyState(ans?.error || "The addresses could not be loaded.", null, { bad: true }));
        if (ans.mode === "off") return holder.replaceChildren(emptyState("This site does not keep addresses, so there is nothing to block by address. Settings > Privacy & retention.", ["Open Privacy & retention", "#settings/site/privacy"]));
        const list = blockList(merge(t.who, ans), ans.mode);
        const site = m.site || "";
        const meta = { site, first, last };
        const stem = `skald-block-list-${first}-to-${last}`;
        const buttons = h("div", { class: "sec-exports", role: "group", "aria-label": "Export the block list" },
          h("button", { type: "button", class: "btn", onclick: () => download(`${stem}.nginx.conf`, nginx(list, meta), "text/plain;charset=utf-8") }, "nginx deny lines"),
          h("button", { type: "button", class: "btn", onclick: () => download(`${stem}.cloudflare.csv`, cloudflare(list)) }, "Cloudflare IP list (CSV)"),
          h("button", { type: "button", class: "btn", onclick: () => download(`${stem}.txt`, plain(list), "text/plain;charset=utf-8") }, "Plain list"));
        const out = [h("div", { class: "sec-review", role: "note" }, h("strong", null, "Review before blocking. "), REVIEW.replace(/^Review before you block\. /, "")), buttons];
        if (list.networks.length) out.push(h("h2", { class: "sec-h2" }, ans.mode === "short" ? "Networks (this site keeps addresses shortened)" : "Networks with two or more of them"),
          table([
            { key: "cidr", label: "Network" },
            { key: "addresses", label: "Addresses", num: true },
            { key: "probes", label: "Probes", num: true },
            { key: "attacks", label: "Attack attempts", num: true },
            { key: "requests", label: "Requests", num: true, hide: true },
          ], { caption: "Networks to block", ns: "sxn", file: "block-networks.csv", rows: list.networks, sortKey: "probes", dir: -1, limit: 15, search: false }));
        if (list.addresses.length) out.push(h("h2", { class: "sec-h2" }, "Addresses"), table([
          { key: "ip", label: "Address" },
          { key: "country", label: "Country", fmt: (v) => flagOf(v), csv: (row) => row.country || "" },
          { key: "hosting", label: "Hosting network", fmt: (v) => (v == null ? "Not known" : v ? "Yes" : "No") },
          { key: "probes", label: "Probes", num: true },
          { key: "attacks", label: "Attack attempts", num: true },
          { key: "days", label: "Days seen", num: true },
          { key: "requests", label: "Requests", num: true, hide: true },
        ], { caption: "Addresses to block", ns: "sxd", file: "block-addresses.csv", rows: list.addresses, sortKey: "probes", dir: -1, limit: 20 }));
        if (!list.networks.length && !list.addresses.length) out.push(emptyState("No scanner or attacker with a kept address in this period."));
        const words = addressWords(ans, f);
        out.push(h("p", { class: "note" }, `${n(list.addresses.length)} address${list.addresses.length === 1 ? "" : "es"} and ${n(list.networks.length)} network${list.networks.length === 1 ? "" : "s"}, ranked by probes, then attack attempts. The exports hold every row, networks first.${words ? ` ${words}` : ""}`), missingNote(p, t));
        holder.replaceChildren(...out.filter(Boolean));
      });
      return [holder];
    },
  });
}
