// Is each crawler who it says it is? Names are self-reported, so the server
// checks the address: against the owner's published ranges, its network, or
// reverse-then-forward DNS. Verified: the address is theirs. Not verifiable:
// the owner publishes nothing to check against. Spoofed: the address is not
// theirs - those requests are counted as bots ("claims to be ...").
// Also: browsers with warning signs (still counted as people), and link
// previews - someone pasted a link to the site in a chat.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, short, clock } from "../ui.js";
import { table } from "../table.js";
import { blist, panel, fileName } from "./common.js";

export const BADGE = { verified: "Verified", unverified: "Not verifiable", spoofed: "Spoofed" };
const METHOD = { ranges: "published address ranges", dns: "reverse and forward DNS", network: "the owner's network list", none: "nothing published" };
const SIGNS = {
  hosting_network: ["From a cloud or hosting network", "People rarely browse from a data centre; crawlers often do."],
  fan_out: ["One browser string, 10+ addresses in 10 seconds", "A crawler spread over many addresses."],
  bare_mozilla: ["The bare agent \"Mozilla/5.0\"", "No real browser sends only that."],
};

// bots.json's days (or today) inside the range.
function pick(f, r) {
  if (!f) return null;
  if (r.kind === "today") return f.today && f.today.state !== "withheld" ? [f.today] : [];
  return (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
}

export function verification(m, r) {
  const days = pick(m.x.bots, r);
  if (!days) return null;
  const v = {}, signs = {}, previews = {};
  let seen = false, seenSigns = false, seenPreviews = false;
  for (const d of days) {
    if (d.verification) seen = true;
    for (const [name, c] of Object.entries(d.verification || {})) {
      const a = v[name] || (v[name] = { group: c.group, method: c.method, verified: 0, unverified: 0, spoofed: 0 });
      for (const k of ["verified", "unverified", "spoofed"]) a[k] += c[k] || 0;
    }
    if (d.fake_browsers) seenSigns = true;
    for (const [k, c] of Object.entries(d.fake_browsers || {})) {
      const a = signs[k] || (signs[k] = { requests: 0, addresses: 0 });
      a.requests += c?.requests || 0;
      a.addresses += c?.addresses || 0;   // summed per day: an address seen on two days counts twice
    }
    if (d.link_previews) seenPreviews = true;
    for (const [app, c] of Object.entries(d.link_previews || {})) previews[app] = (previews[app] || 0) + c;
  }
  return { seen, byName: v, signs, seenSigns, previews, seenPreviews, days: days.length };
}

// The badge a crawler earns over the range: any spoofed request marks it.
export function badgeOf(c) {
  if (!c) return null;
  if (c.spoofed) return "spoofed";
  return c.verified ? "verified" : "unverified";
}
export const badge = (c) => {
  const b = badgeOf(c);
  if (!b) return h("span", { class: "muted" }, "-");
  // The real crawler and impostors using its name: say both, not "spoofed" alone.
  const words = b === "spoofed" && c.verified ? "Verified, plus impostors" : BADGE[b];
  return h("span", { class: `vb ${b}`, title: b === "spoofed" ? `${n(c.spoofed)} requests used this name from an address that is not theirs` : BADGE[b] }, words);
};

export function verifySection(m, r) {
  const v = verification(m, r);
  const out = [];
  if (!v || !v.seen) {
    out.push(h("section", { class: "s" }, h("h2", null, "Are they who they say they are?"),
      h("p", { class: "empty" }, "Crawler checks are not recorded for this range yet. A crawler's name is what it calls itself; once the server checks addresses, each one is marked verified, not verifiable or spoofed here.")));
  } else {
    const rows = Object.entries(v.byName).map(([name, c]) => ({ name, ...c, all: c.verified + c.unverified + c.spoofed, badge: badgeOf(c), __k: name }));
    const spoofed = rows.reduce((a, x) => a + x.spoofed, 0);
    const ranges = Object.entries(m.x.bots?.ranges || {});
    const stale = ranges.filter(([, x]) => !x.ok);
    out.push(h("section", { class: "s" }, h("h2", null, "Are they who they say they are?"),
      h("p", { class: "sub" }, spoofed ? `${n(spoofed)} requests used a well-known crawler's name from an address that is not theirs. They are counted as bots ("claims to be ..."), not as that crawler.`
        : "Every checked address belonged to the crawler it named."),
      table([
        { key: "name", label: "Crawler" },
        { key: "badge", label: "Check", fmt: (_, x) => badge(x), csv: (x) => x.badge, sort: (x) => ["spoofed", "unverified", "verified"].indexOf(x.badge) },
        { key: "method", label: "Checked by", fmt: (val) => METHOD[val] || val || "-" },
        { key: "verified", label: "Verified", num: true },
        { key: "unverified", label: "Not verifiable", num: true },
        { key: "spoofed", label: "Spoofed", num: true },
        { key: "all", label: "All", num: true },
      ], { caption: "Crawler verification", rows, file: fileName("crawler-verification", r), sortKey: "spoofed", limit: 12,
        note: `Verified: the address is on the owner's published list or network, or its DNS points back to the owner. Not verifiable: the owner publishes nothing to check against. Spoofed: the address is not theirs.${ranges.length
          ? ` Address lists last fetched: ${ranges.map(([k, x]) => `${k} ${x.fetched ? tzTime(x.fetched, { date: true }) : "never"}`).join(", ")}.` : ""}${stale.length ? ` Could not fetch: ${stale.map(([k, x]) => `${k}${x.error ? ` (${x.error})` : ""}`).join(", ")}.` : ""}` })));
  }
  const signRows = Object.entries(v?.signs || {}).filter(([, c]) => c.requests).map(([k, c]) => ({ k, label: SIGNS[k]?.[0] || k, why: SIGNS[k]?.[1] || "", ...c, __k: k }));
  const prev = Object.entries(v?.previews || {}).sort((a, b) => b[1] - a[1]);
  out.push(h("div", { class: "cols" },
    h("section", { class: "s" }, h("h2", null, "Browsers with warning signs"),
      h("p", { class: "sub" }, "Requests that look like a browser but carry a crawler's sign. They stay counted as people until a rule proves otherwise; one request can carry several signs."),
      v?.seenSigns ? table([{ key: "label", label: "Sign" }, { key: "requests", label: "Requests", num: true }, { key: "addresses", label: "Addresses", num: true }],
        { caption: "Browsers with warning signs", rows: signRows, file: fileName("browser-warning-signs", r), sortKey: "requests", search: false, empty: "No browser request carried a warning sign in this range.",
          note: signRows.length ? signRows.map((x) => `${x.label}: ${x.why}`).join(" ") : null })
        : h("p", { class: "empty" }, "Not recorded for this range yet.")),
    panel("Link previews", "Someone pasted a link to the site in a chat; the app fetched it to draw a preview. Counted as bots.",
      v?.seenPreviews ? blist(prev, { color: "var(--g-bots)", empty: "No link previews in this range." }) : h("p", { class: "empty" }, "Not recorded for this range yet."))));
  return h("div", null, out);
}
