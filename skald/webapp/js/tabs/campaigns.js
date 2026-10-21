// Campaigns and referrers: every UTM tag, the referring sites down to the
// page that linked, paid traffic by network - each with what those visits
// did: pages per visit, missing pages met, and form sends.

import { h, n } from "../ui.js";
import { table } from "../table.js";
import { blist, panel, fileName } from "./common.js";
import { link } from "../drill.js";
import { subView } from "../tablestate.js";
import { withUrl } from "../urlactions.js";

const UTM = [["utm_source", "Source"], ["utm_medium", "Medium"], ["utm_campaign", "Campaign"], ["utm_term", "Term"], ["utm_content", "Content"]];
const NONE = "(none)";

// Sum each dimension's rows by name over the range's verified days (or today).
function sum(f, r) {
  const days = r.kind === "today" ? (f.today?.state === "ok" ? [f.today] : [])
    : (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  const out = {};
  for (const d of days) {
    for (const [dim, rows] of Object.entries(d.rows || {})) {
      const into = out[dim] || (out[dim] = new Map());
      for (const x of rows) {
        const a = into.get(x.name) || { name: x.name, visits: 0, pages: 0, not_found: 0, posts: 0 };
        a.visits += x.visits || 0; a.pages += x.pages || 0; a.not_found += x.not_found || 0; a.posts += x.posts || 0;
        into.set(x.name, a);
      }
    }
  }
  return { days: days.length, dims: Object.fromEntries(Object.entries(out).map(([k, v]) => [k, [...v.values()]])) };
}

const COLS = (first, drill) => [
  { key: "name", label: first, drill },
  { key: "visits", label: "Visits", num: true },
  { key: "ppv", label: "Pages per visit", num: true, sort: (r) => (r.visits ? r.pages / r.visits : 0), fmt: (_, r) => (r.visits ? (r.pages / r.visits).toFixed(1) : "-"), csv: (r) => (r.visits ? (r.pages / r.visits).toFixed(2) : "") },
  { key: "not_found", label: "Broken links met", num: true },
  { key: "posts", label: "Form sends", num: true },
];

// Tag problems (campaigns.json days[].utm_hygiene, utm_hygiene.py): visits
// whose landing address was tagged badly, with example landing paths and
// only their utm_ tags (a click id is named by its network, never its value).
const HYGIENE = [
  ["source_no_medium", "Source tag without a medium", "utm_source with no utm_medium: analytics tools cannot tell the channel."],
  ["unknown_medium", "Medium no tool knows", "A utm_medium outside the usual channel names (cpc, email, social, referral...): it lands in an \"other\" channel."],
  ["click_id_no_tags", "Ad click id without tags", "A click id (gclid, fbclid, msclkid...) and no utm_ tag: the network is known, the campaign is not."],
  ["internal_tags", "Tags on links between our own pages", "A utm_ tag on a link from one of the site's own pages: it starts a new source in the middle of a visit. Never tag internal links."],
];

function tagProblems(m, f, r) {
  const days = r.kind === "today" ? (f.today?.state === "ok" ? [f.today] : [])
    : (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  const counted = days.filter((d) => d.utm_hygiene);
  const out = [];
  if (!counted.length) out.push(h("p", { class: "empty" }, "Tag problems are counted from this release on: no counted day in this range yet."));
  else {
    const visits = counted.reduce((a, d) => a + (d.utm_hygiene.visits || 0), 0);
    const rows = HYGIENE.map(([k, label, why]) => {
      const paths = {};
      const examples = [];
      let total = 0;
      for (const d of counted) {
        const u = d.utm_hygiene;
        total += u.counts?.[k] || 0;
        for (const [p, v] of Object.entries(u.paths?.[k] || {})) paths[p] = (paths[p] || 0) + v;
        for (const e of u.examples?.[k] || []) if (examples.length < 3 && !examples.some((x) => x.path === e.path && x.tags === e.tags)) examples.push(e);
      }
      return { k, label, why, total, paths, examples };
    });
    // Each problem: its examples (path + utm_ tags), then its largest landing paths.
    const paths = (x) => Object.entries(x.paths).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([p, v]) => [p, v]);
    out.push(h("div", { class: "cols" }, ...rows.map((x) => panel(`${x.label}: ${n(x.total)} visit${x.total === 1 ? "" : "s"}`, x.why,
      x.total ? h("div", { class: "prose" }, ...x.examples.map((e) => h("div", null, withUrl(h("code", null, `${e.path}${e.tags ? `?${e.tags}` : ""}`), e.path, { cls: "ua-after" }), e.click_id ? ` (${e.click_id} click id)` : ""))) : null,
      x.total ? blist(paths(x), { color: "var(--g-bots)", limit: 5, drill: "landing", empty: "" }) : null))),
    h("p", { class: "note" }, `Out of ${n(visits)} visits on ${n(counted.length)} counted day${counted.length === 1 ? "" : "s"}${counted.length < days.length ? ` (${n(days.length - counted.length)} day${days.length - counted.length === 1 ? "" : "s"} not counted for tags)` : ""}. A visit can show more than one problem. Examples keep the landing path and its utm_ tags only.`));
  }
  const missing = leadsOnly(m, f);
  if (missing) out.push(missing);
  return h("section", { class: "s" }, h("h3", null, "Tag problems"), ...out);
}

// Campaigns the lead store saw (leads.json, last 30 days, first or last
// touch) that no counted day of the log ever carried. Shown only when the
// lead store is set up; both lists are checked figures, read side by side.
function leadsOnly(m, f) {
  const p = m.x.leads?.available ? m.x.leads.period : null;
  if (!p) return null;
  const said = new Set([...Object.keys(p.first_touch?.utm_campaign || {}), ...Object.keys(p.last_touch?.utm_campaign || {})].filter((k) => k && k !== NONE));
  if (!said.size) return null;
  const seen = new Set();
  let folded = false;
  for (const d of [...(f.days || []).filter((x) => x.state === "ok"), ...(f.today?.state === "ok" ? [f.today] : [])]) {
    for (const x of d.rows?.utm_campaign || []) { if (x.name === "(all others)") folded = true; else seen.add(x.name); }
  }
  const never = [...said].filter((k) => !seen.has(k)).sort();
  const words = never.length ? `${never.length} campaign${never.length === 1 ? "" : "s"} in leads of the last 30 days never seen in the log: ${never.slice(0, 10).join(", ")}${never.length > 10 ? ", ..." : ""}.` : "Every campaign in leads of the last 30 days was also seen in the log.";
  return h("p", { class: "note" }, `${words} A campaign only in leads may come from a link that drops its tags on a redirect, or from an older visit on the same browser.${folded ? " Some days fold their smaller campaigns into \"(all others)\", so a campaign may be there unnamed." : ""}`);
}

export function campaigns(m, s, r) {
  const f = m.x.campaigns;
  if (!f) return h("p", { class: "empty" }, "Full UTM tags, referring pages and paid networks arrive with the next data update. The Campaigns and Referring sites lists above already show what history keeps.");
  const { days, dims } = sum(f, r);
  if (!days) return h("p", { class: "empty" }, "No verified day of campaign figures in this range yet.");
  const want = (rows) => rows.filter((x) => x.name !== NONE && (!s.campaign || x.name === s.campaign));

  // UTM table, switchable by tag.
  // The tag chosen stays in the address (utm_view=utm_medium: tablestate.js subView).
  const kept = subView("utm");
  let dim = UTM.some(([k]) => k === kept.get()) ? kept.get() : "utm_source";
  const holder = h("div");
  const seg = h("div", { class: "seg plain", role: "group", "aria-label": "UTM tag" });
  const draw = () => {
    seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === dim)));
    const label = UTM.find(([k]) => k === dim)[1];
    holder.replaceChildren(table(COLS(label, dim === "utm_campaign" ? "campaign" : undefined), { caption: `Visits by ${label.toLowerCase()}`, rows: want(dims[dim] || []), file: fileName(dim.replace("_", "-"), r), sortKey: "visits",
      empty: "No visit in this range carried this tag." }));
  };
  seg.append(...UTM.map(([k, label]) => { const b = h("button", { type: "button", "data-k": k, onclick: () => { dim = k; kept.set(k, "utm_source"); draw(); } }, label); return b; }));
  draw();

  // Referring sites, each opening to the pages on that site that linked here.
  const pages = dims.ref_page || [];
  const hosts = (dims.ref_host || []).filter((x) => x.name !== NONE && (!s.referrer || x.name === s.referrer));
  const open = new Set();
  const refHolder = h("div");
  const drawRefs = () => {
    const rows = [];
    for (const x of hosts.sort((a, b) => b.visits - a.visits)) {
      const kids = pages.filter((p) => p.name.startsWith(x.name + "/") || p.name === x.name);
      rows.push({ ...x, __k: x.name, kids });
      if (open.has(x.name)) for (const p of kids) rows.push({ ...p, __k: `${x.name}>${p.name}`, sub: true });
    }
    const cols = COLS("Referring site");
    // A referring site or its page, as the full URL that sent the visit: copy and open (urlactions.js).
    cols[0] = { key: "name", label: "Referring site", url: true, href: (row) => (/^[a-z0-9.-]+\.[a-z]{2,}(\/|$)/i.test(row.name || "") ? `https://${row.name}` : ""), fmt: (v, row) => (row.sub ? v : row.kids?.length
      ? h("span", { class: "named" }, h("button", { type: "button", class: "exp", "aria-expanded": String(open.has(v)), "aria-label": `Show the pages on ${v} that linked here`, onclick: () => { open.has(v) ? open.delete(v) : open.add(v); drawRefs(); } }, h("i", { "aria-hidden": "true" }, "›")), link("referrer", v))
      : link("referrer", v)) };
    refHolder.replaceChildren(table(cols, { caption: "Referring sites", rows, file: fileName("referrers", r), sortKey: "__none", search: true, limit: 50,
      rowClass: (row) => (row.sub ? "sub" : null), empty: "No referring site in this range." }));
  };
  drawRefs();

  const paid = want(dims.paid || []).map((x) => [x.name, x.visits]);
  const ai = want(dims.ai || []).map((x) => [x.name, x.visits]);
  return h("div", null,
    h("section", { class: "s" }, h("h3", null, "UTM tags"), h("div", { class: "camp-tools" }, seg), holder),
    h("section", { class: "s" }, h("h3", null, "Referring sites, down to the page"),
      h("p", { class: "sub" }, "Open a site to see the pages on it that sent visitors. Only the referrer's address is kept, never anything about the visitor."), refHolder),
    h("div", { class: "cols" },
      panel("Paid traffic by network", "From the ad click id on the landing address", blist(paid.sort((a, b) => b[1] - a[1]), { color: "var(--g-bots)", empty: "No paid clicks in this range." })),
      panel("Sent by an AI assistant", "Visits whose source was an assistant", blist(ai.sort((a, b) => b[1] - a[1]), { drill: "assistant", color: "var(--g-answer_engines)", empty: "No assistant sent a visitor in this range." }))),
    tagProblems(m, f, r),
    h("p", { class: "note" }, `${n(days)} verified day${days === 1 ? "" : "s"} of campaign figures. Only utm_ tags, ad click ids and ref= style parameters are kept; every other query parameter is dropped before anything is stored.`));
}
