// Security > Who is scanning us? (2.21): one row per scanner (address and user agent) for the
// period, with what it looked for and what the server answered, and the probes per day.
// Addresses come from the helper (owners and admins, on a site that keeps them); without
// them each day's rows stand alone. A row opens its detail, with its request list (Site >
// Requests, filtered to the address) for the hours the raw log still holds.
//
//   sxc   Looked for: one category ("" every)
//   sxk   Show: "" scanners, "all" every suspect (attackers and fake browsers too)

import { h, n, short } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { columns } from "../charts.js";
import { openDrawer } from "../drawer.js";
import { tokenFor } from "../routemask.js";
import { tiles } from "./tiles.js";
import { blist } from "./common.js";
import { ranked } from "../data.js";
import { optionsRow, select, choice, emptyState } from "./sa-options.js";
import { merge } from "../sec-data.js";
import { secTab, loadAddresses, addressWords, spanOf, at, flagOf, answered, topOf, LOOKED, missingNote } from "./sec-common.js";

const HELP_TEXT = "A scanner is an address and user agent that asked for at least one path no real site serves (.env, wp-login.php, phpinfo.php...) or sent an attack string. All its requests of the day are on its row. Scanners and addresses are counted per day: one that came back on three days is three. A forged referrer: it claimed to come from one of the site's own pages (or a subdomain) but never loaded the site's files. Sent to the bare IP: it asked the server's address, not the site's name, which only scanners do.";

export const label = (r) => (r.ip ? r.ip : r.removed ? "(removed)" : `Not shown (${short(r.days[0])} #${r.refs[0].split("#")[1]})`);
const agentShort = (ua) => (ua ? String(ua).slice(0, 60) + (String(ua).length > 60 ? "…" : "") : "-");

export function flags(r) {
  const out = [];
  if (r.forged) out.push("Forged referrer");
  if (r.bare_ip) out.push("Sent to the bare IP");
  if (r.hosting) out.push("Hosting network");
  return out;
}

// A row's key in the address (scan=<day>.<seq>): its first day's row, never its address.
export const keyOf = (r) => String(r.refs?.[0] || "").replace("#", ".");

export function detail(r, f) {
  const hours = f?.requests_hours || 6;
  const fold = (r.paths || {})["(all others)"] || 0;
  const lines = Object.entries(r.paths || {}).filter(([p]) => p !== "(all others)").sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .map(([p, c]) => h("li", null, h("code", null, p), ` ${n(c)}`));
  if (fold) lines.push(h("li", { class: "note" }, `and ${n(fold)} more probes of other paths`));
  const body = h("div", { class: "sec-detail" },
    h("dl", { class: "sec-dl" },
      h("dt", null, "Address"), h("dd", null, label(r)),
      h("dt", null, "User agent"), h("dd", null, r.agent || (r.ip ? "(none)" : "-")),
      h("dt", null, "Country"), h("dd", null, flagOf(r.country)),
      h("dt", null, "Network"), h("dd", null, r.hosting == null ? "Not known (no hosting list)" : r.hosting ? "A hosting or cloud network" : "Not a listed hosting network"),
      h("dt", null, "Seen"), h("dd", null, `${at(r.first)} to ${at(r.last)}, on ${r.days.length} day${r.days.length === 1 ? "" : "s"}`),
      h("dt", null, "Requests"), h("dd", null, `${n(r.requests)}, of which ${n(r.probes)} probes`),
      h("dt", null, "Answered"), h("dd", null, answered(r.status)),
      h("dt", null, "Looked for"), h("dd", null, Object.entries(r.categories).map(([k, v]) => `${LOOKED[k] || k} ${n(v)}`).join(", ") || "-"),
      h("dt", null, "Signs"), h("dd", null, flags(r).join(", ") || "None")),
    lines.length ? [h("h3", null, "Paths it asked for (its top 5 of each day, summed)"), h("ul", { class: "sec-paths" }, lines)] : null,
    r.ip && !r.ip.endsWith(".0") && !r.ip.endsWith("::")
      ? h("p", null, h("a", { class: "btn", href: `#site/requests?ip=${encodeURIComponent(tokenFor(r.ip))}` }, "Open its requests"),
        ` The request list holds the last ${hours} hours of the raw log; older lines of this address have expired from it, and only the figures above remain.`)
      : h("p", { class: "note" }, r.ip ? "A shortened address is a network: the request list cannot be filtered to it." : "Without its address the request list cannot be filtered to it."));
  openDrawer({ title: label(r), subtitle: "Scanner detail", body, size: "md", route: keyOf(r) ? { key: "scan", value: keyOf(r) } : null });
}

export function rowsTable(rows, f, s) {
  return table([
    { key: "ip", label: "Address", fmt: (v, r) => label(r), sort: (r) => r.ip || "~", csv: (r) => label(r) },
    { key: "agent", label: "User agent", fmt: (v) => agentShort(v), hide: true },
    { key: "country", label: "Country", fmt: (v) => flagOf(v), csv: (r) => r.country || "" },
    { key: "first", label: "First seen", type: "date", fmt: (v) => at(v) },
    { key: "last", label: "Last seen", type: "date", fmt: (v) => at(v), hide: true },
    { key: "requests", label: "Requests", num: true },
    { key: "probes", label: "Probes", num: true },
    { key: "categories", label: "Looked for", fmt: (v) => topOf(v), sort: (r) => topOf(r.categories), csv: (r) => topOf(r.categories, 9) },
    { key: "status", label: "Answered", fmt: (v) => answered(v), sort: (r) => r.status?.["2xx"] || 0 },
    { key: "flags", label: "Signs", fmt: (v, r) => flags(r).join(", ") || "-", sort: (r) => flags(r).length },
  ], { caption: "Scanners", ns: "sxs", file: "scanners.csv", rows, sortKey: "probes", dir: -1, limit: 20, onRow: (r) => detail(r, f),
    placeholder: "Search addresses, countries, what they looked for",
    empty: s.sxc ? "No scanner looked for that in this period." : "No scanner in this period." });
}

export default function scanners(m, s) {
  return secTab(m, s, {
    title: "Who is scanning us?",
    question: "Which addresses probed the site for files and panels it does not have, and what did the server answer?",
    help: HELP_TEXT,
    draw: ({ f, r, p, t }) => {
      if (!t.days) return [emptyState("Not recorded for this period."), missingNote(p, t)];
      const parts = [tiles([
        { label: "Scanner probes", value: t.probes, info: "Requests for paths no real site serves, or with an attack string in the query." },
        { label: "Scanners", value: t.scanners, info: "Address and user agent pairs with at least one probe, counted per day." },
        { label: "Addresses", value: t.addresses, info: "Distinct addresses among them, counted per day." },
        { label: "Sent to the bare IP", value: t.bare_ip, info: "Probes that asked the server's address instead of the site's name." },
        { label: "Forged referrers", value: t.forged, info: "Suspects that claimed to come from the site's own pages but never loaded its files." },
        t.hosting != null ? { label: "From hosting networks", value: t.hosting, info: "Probes from cloud and hosting networks (the list Skald keeps for crawler checks)." } : null,
      ])];
      const days = (r.kind === "today" ? [{ day: m.today, state: "ok" }] : r.days || []).map((d) => {
        const got = t.perDay.find((x) => x.day === d.day);
        return { ...d, state: got ? "ok" : d.state === "before" ? "before" : "missing", probes: got?.probes || 0, scanners: got?.scanners || 0 };
      });
      if (days.length > 1) parts.push(h("div", { class: "card sec-chart" }, h("h2", null, "Probes per day"),
        columns(days, [{ name: "Probes", color: "var(--bad)", get: (d) => d.probes }], { label: "Scanner probes per day", H: 160, unit: "probes" })));
      const cats = Object.keys(t.categories).sort((a, b) => t.categories[b] - t.categories[a]);
      parts.push(...optionsRow("Scanner options", [
        select("Looked for", s.sxc, cats.map((k) => [k, LOOKED[k] || k]), (v) => S.set({ sxc: v }), { all: "Anything" }),
        choice("Show", s.sxk || "", [["", "Scanners"], ["all", "Every suspect"]], (v) => S.set({ sxk: v })),
      ], { notes: [HELP_TEXT] }));
      parts.push(h("div", { class: "card sec-cats" }, h("h2", null, "What they looked for"),
        blist(ranked(t.categories), { color: "var(--bad)", total: t.probes, label: (k) => LOOKED[k] || k, limit: 8, empty: "No probe." })));
      const holder = h("div", { class: "sec-who" }, h("p", { class: "empty" }, "Loading the scanners…"));
      parts.push(holder, missingNote(p, t));
      const [first, last] = spanOf(m, r);
      loadAddresses(first, last).then((ans) => {
        let rows = merge(t.who, ans?.ok ? ans : null);
        if (s.sxk !== "all") rows = rows.filter((x) => x.probes);
        if (s.sxc) rows = rows.filter((x) => x.categories[s.sxc]);
        const words = addressWords(ans, f);
        const older = t.days > t.whoDays ? `Rows are kept in this page for the last ${f.who_days} days; the totals above cover every day.` : "";
        // A link with scan= opens that row's detail once the rows are here (overlays.js leaves it to this tab).
        const want = S.read().scan;
        if (want) {
          const hit = rows.find((x) => keyOf(x) === want);
          if (hit) detail(hit, f);
          else import("../overlays.js").then((o) => o.missing("scan", "That scanner is not in the period on screen, or its row is no longer kept. Choose a longer period."));
        }
        holder.replaceChildren(rowsTable(rows, f, s), ...[words, older, t.whoFolded ? `${n(t.whoFolded)} more suspects are in the totals but not listed (each day lists its worst 300).` : ""]
          .filter(Boolean).map((w) => h("p", { class: "note" }, w)));
      });
      return parts;
    },
  });
}
