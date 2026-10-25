// Traffic > Sources, segment "Social network" (social_networks.py): the Social media visits
// by network - X, LinkedIn, Facebook, ... - each rolling up its hosts, apps and tags
// (t.co, x.com, twitter.com and the X app are one row). Counted, never inferred; the rows
// add up to the Social media row of "Source type". Read from campaigns.json
// (../social-networks.js), never from the referring sites, which are folded and stored apart.
//
// A row opens the network's detail under the grid: how its visits were matched and the
// pages they landed on. The open network is in the address (net=x, a tab key):
//   #traffic/sources?src_seg=social&net=x
// Back closes it. Compare mode gives B and ± only when every verified day of A and B
// recorded the figure; otherwise the rows keep A's figures and a line says why.

import { h, n, share } from "../ui.js";
import * as S from "../state.js";
import { table } from "../table.js";
import { info } from "./tiles.js";
import { previousOf, coverage, chartDays } from "../data.js";
import { leadRows, compareRows } from "./tr-grid.js";
import { labelCell } from "./leadfigs.js";
import { rangeBlobs, sumNetworks, nameOf, perDay, viaWords, viaHref, method, isNetId, NAMES } from "../social-networks.js";

export const SEGMENT = { id: "social", label: "Social network", dim: "network", noLeads: "Leads are split by source type only, not by social network" };

/* A range's networks: the campaigns file, its blobs and their sums. */
export function socialOf(m, r) {
  const f = m.x?.campaigns;
  const got = rangeBlobs(f, r);
  return { f, ...got, t: sumNetworks(got.blobs) };
}
// Recorded on every verified day of the range, and adding up.
const whole = (x) => x.blobs.length > 0 && !x.missing && x.t.ok;

/* The segment's rows, beside the source types' (tr-sources.js sourceRows). */
export function socialRows(m, s, r, c) {
  const a = socialOf(m, r);
  if (!a.blobs.length || !a.t.ok) return { rows: [], a, compared: false };
  const label = (k) => nameOf(a.f, k);
  const rows = leadRows(a.t.networks, null, { dim: SEGMENT.dim, label, noLeads: SEGMENT.noLeads }).map((x) => ({ ...x, seg: SEGMENT.id }));
  // Before, Change and the trend chip: the range before, only when both are whole, verified and
  // recorded every day (the source types' rule, readers.js).
  const pr = c.ok ? null : previousOf(m, r);
  const b = pr && coverage(r).complete && coverage(pr).complete && whole(a) ? socialOf(m, pr) : null;
  const p = b && whole(b) && b.blobs.length === pr.length ? b.t.networks : null;
  const days = r.kind === "history" ? { kind: "history", days: chartDays(r) } : null;
  for (const x of rows) {
    x.before = p ? p[x.k] || 0 : null;
    x.chip = "";
    if (p && x.before === 0 && x.v > 0) x.chip = "new";
    else if (p && x.before > 0) { const pc = ((x.v || 0) - x.before) / x.before; x.chip = pc >= 0.2 ? "working" : pc <= -0.2 ? "dropped" : ""; }
    x.trend = days ? perDay(a.f, days, x.k) : null;
  }
  if (!c.ok) return { rows, a, compared: false };
  const bS = socialOf(m, c.b);
  if (!whole(a) || !whole(bS)) return { rows, a, compared: false, why: "Social networks are not compared: some days of A or B were recorded before they were counted, or do not add up." };
  return { rows: compareRows(c, rows, bS.t.networks, { dim: SEGMENT.dim, label }), a, compared: true };
}

/* A network row's label: a button that opens its detail (the whole row, drill.js drillRow). */
export function netCell(x) {
  const b = h("button", { type: "button", class: "dl", title: `Open ${x.label}: how its visitors were matched and where they landed` }, h("span", { class: "nm" }, x.label));
  b.dataset.dim = SEGMENT.dim;
  b.dataset.value = x.k;
  b.addEventListener("click", (e) => { e.stopPropagation(); S.set({ net: x.k }); });
  return h("span", { class: "cell-l", title: x.label }, b);
}

/* What the segment needs said under the grid, or null. */
export function socialNote(got) {
  const { a, why } = got || {};
  if (!a) return null;
  const parts = [];
  if (!a.blobs.length) parts.push("Social network: not recorded for this range; it is counted from this release on.");
  else if (!a.t.ok) parts.push("Social network: withheld for this range, these days' figures do not add up.");
  else if (a.missing) parts.push(`Social network: over ${n(a.blobs.length)} of ${n(a.days)} recorded days; the days before it was counted are left out.`);
  if (why) parts.push(why);
  return parts.length ? h("p", { class: "note" }, parts.join(" ")) : null;
}

const known = (f, id) => isNetId(id) && (id in (f?.social_networks?.names || NAMES));

/* The open network's detail (net=<id>), under the grid; null when none is open. */
export function networkPanel(m, s, r) {
  if (!s.net) return null;
  const a = socialOf(m, r);
  const name = known(a.f, s.net) ? nameOf(a.f, s.net) : "";
  const box = h("section", { class: "s tr-net", id: "social-network" },
    h("h2", null, `${name || "Social network"} `, info(method(a.f), "Social networks")),
    h("p", { class: "tr-goto" }, h("a", { href: S.hashFor({ ...s, net: "" }) }, h("span", { "aria-hidden": "true" }, "‹ "), "All social networks")));
  const say = (words) => { box.append(h("p", { class: "empty" }, words)); return box; };
  if (!name) return say("Not a social network Skald knows.");
  if (!a.blobs.length) return say("Not recorded for this range: social networks are counted from this release on.");
  if (!a.t.ok) return say("Withheld: these days' figures do not add up.");
  const v = a.t.networks[s.net] || 0;
  if (!v) return say(`No visitor from ${name} in this range.`);
  box.append(h("p", { class: "sub" }, `${n(v)} visitor${v === 1 ? "" : "s"} from ${name}${a.t.social >= 10 ? `, ${share(v, a.t.social)} of the ${n(a.t.social)} from social networks` : ` of ${n(a.t.social)} from social networks`}${a.missing ? `, over ${n(a.blobs.length)} of ${n(a.days)} recorded days` : ""}.`));
  const rowsOf = (obj) => Object.entries(obj || {}).filter(([, x]) => x).map(([k, x]) => ({ k, v: x }));
  const pct = { key: "share", label: "Share", num: true, sort: (x) => x.v, fmt: (_, x) => share(x.v, v) || "-", csv: (x) => (v ? (x.v / v).toFixed(4) : "") };
  const file = (what) => `social-${s.net}-${what}-${r.first}-to-${r.last}.csv`;
  box.append(h("div", { class: "cols" },
    h("div", { class: "sheet" }, h("h3", null, "How they were matched"),
      table([{ key: "k", label: "Came from", url: true, href: (x) => viaHref(x.k), fmt: (_, x) => viaWords(x.k), csv: (x) => x.k },
        { key: "v", label: "Visitors", num: true }, pct],
      { caption: `${name}: how they were matched`, rows: rowsOf(a.t.via[s.net]), file: file("hosts"), ns: "snv", tools: false, search: false, sortKey: "v", empty: "Nothing recorded." })),
    h("div", { class: "sheet" }, h("h3", null, "Where they landed"),
      table([{ key: "k", label: "Landing page", drill: "landing", fmt: (_, x) => labelCell("landing", x.k, x.k), csv: (x) => x.k },
        { key: "v", label: "Visitors", num: true }, pct],
      { caption: `${name}: landing pages`, rows: rowsOf(a.t.landings[s.net]), file: file("pages"), ns: "snl", tools: false, sortKey: "v", empty: "Nothing recorded." }))));
  box.append(h("p", { class: "note" }, `A page list keeps each day's top pages and sums the rest as "(all others)", so it adds up to ${n(v)}. ${method(a.f)}`));
  return box;
}
