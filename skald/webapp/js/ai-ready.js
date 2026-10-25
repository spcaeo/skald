// AI readiness of one page (2.35): can AI read it well? Six lines, each a state, the
// evidence in one short line and what to do, from ai_ready.json (ai_ready.py:
// robots.txt, the sitemap, what AI got back by address) and page_trends.json (L1, the
// assistants' fetches by page). Nothing is counted here and nothing is guessed: a figure
// that was not recorded says "Not known", never 0.
//
//   readiness(F, pt, path, anchor) -> [{id, title, state, says, detail, action, snippet}]
//   needWords(row)                 -> the words of a "Pages AI can't read well" row
//
// States: "good", "attention" (needs attention), "unknown" (not known). Pure: no DOM, so
// node tests it (tests/js/ai-ready.mjs).

import { decide } from "./robots-match.js";
import { pageKey, OTHER } from "./page-figs.js";
import { addDays } from "./ui.js";

export const STATE_WORDS = { good: "Good", attention: "Needs attention", unknown: "Not known" };
export const ROLE = { training: "trains AI models", search: "AI search", asked: "fetches for a person's question" };
const COPY_ENDS = [".markdown", ".mdx", ".md"];

const fmt = (x) => Number(x || 0).toLocaleString("en-US");
const times = (k) => (k === 1 ? "once" : k === 2 ? "twice" : `${fmt(k)} times`);
const ok = (code) => code.startsWith("2") || code === "304";
const listWords = (xs) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
const dayWords = (d) => { const t = new Date(`${d}T12:00:00Z`); return Number.isNaN(+t) ? String(d) : t.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }); };

/* The page a path is: a Markdown copy is its page's (ai_ready.py copy_of). */
export function pageOf(path) {
  const cut = String(path || "").split("?")[0].split("#")[0];
  let bare = cut.replace(/\/+$/, "");
  const low = bare.replace(/[A-Z]/g, (c) => c.toLowerCase());
  const end = COPY_ENDS.find((e) => low.endsWith(e));
  if (!end) return pageKey(cut);
  bare = bare.slice(0, -end.length);
  if (bare.replace(/[A-Z]/g, (c) => c.toLowerCase()).endsWith("/index")) bare = bare.slice(0, -"index".length);
  return pageKey(bare || "/");
}

/* {code: n} and {name: n} of a {name: {code: n}} map, for the codes `test` keeps. */
function tally(per, test) {
  const codes = {}, names = {};
  let total = 0;
  for (const [name, got] of Object.entries(per || {})) {
    for (const [code, k] of Object.entries(got || {})) {
      if (!test(String(code))) continue;
      codes[code] = (codes[code] || 0) + k; names[name] = (names[name] || 0) + k; total += k;
    }
  }
  return { total, codes, names };
}
const ranked = (o) => Object.entries(o || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
export const byWords = (o) => ranked(o).map(([k, v]) => `${k} ${fmt(v)}`).join(", ");
const codeWords = (o) => listWords(ranked(o).map(([c]) => c));

function windowWords(w) {
  return `the last ${w.days} days (${w.recorded === w.of ? `${fmt(w.of)} recorded` : `${fmt(w.recorded)} of ${fmt(w.of)} days recorded`})`;
}
const NOT_YET = "Not recorded yet: what AI gets back is kept from the next collected day on.";
const folded = (w) => `On ${fmt(w.folded)} ${w.folded === 1 ? "day" : "days"} more addresses had such answers than Skald keeps (1,000 a day), so this page may be among the ones summed.`;

// ---------------------------------------------------------------- the six lines
function robotsLine(F, path) {
  const r = F.robots || {};
  const title = "robots.txt";
  if (r.missing) {
    const code = String(r.error || "").match(/HTTP Error (\d{3})/)?.[1];
    return { id: "robots", title, state: "good", says: `The site has no robots.txt (it answered ${code || "an error"} when Skald asked), so every crawler may read this page.` };
  }
  if (!r.crawlers) {
    return { id: "robots", title, state: "unknown", says: `Skald has no copy of the site's robots.txt${r.error ? `: the last try failed (${r.error})` : " yet"}.`,
      action: "Make sure /robots.txt answers: Skald reads it every hour." };
  }
  const tokens = (F.crawlers || []).map(([t, what]) => [t, what]);
  const shut = [];
  for (const [token, what] of tokens) {
    const c = r.crawlers[token];
    if (!c) continue;
    const got = decide(c.rules, path);
    if (!got.allowed) shut.push({ token, what, rule: got.rule, agents: c.agents, whole: !c.root });
  }
  const read = r.fetched_at ? `robots.txt as Skald read it on ${dayWords(r.fetched_at.slice(0, 10))}` : "robots.txt as Skald keeps it";
  if (!shut.length) return { id: "robots", title, state: "good", says: `All ${tokens.length} main AI crawlers may read it (${read}).` };
  const names = shut.map((x) => x.token);
  return { id: "robots", title, state: "attention", says: `robots.txt keeps ${listWords(names)} out of this page (${read}).`,
    detail: shut.map((x) => ({ name: x.token, role: ROLE[x.what] || "", rule: x.rule ? `${x.rule[0] === "allow" ? "Allow" : "Disallow"}: ${x.rule[1]}` : "", group: `User-agent: ${x.agents.join(", ") || "*"}`, whole: x.whole })),
    action: `If you want them to read it, allow ${listWords(names)} in robots.txt.`,
    snippet: shut.map((x) => `User-agent: ${x.token}\nAllow: ${String(path || "/").split("?")[0]}`).join("\n\n") };
}

function errorsLine(F, facts) {
  const w = F.window || {}, title = "Crawler errors";
  if (!w.recorded) return { id: "errors", title, state: "unknown", says: NOT_YET };
  const own = facts?.self || {};
  const s5 = tally(own, (c) => c.startsWith("5"));
  const s4 = tally(own, (c) => c.startsWith("4") && c !== "404" && c !== "410");
  const s3 = tally(own, (c) => c.startsWith("3") && c !== "304");
  const slow = Object.values(facts?.slow || {}).reduce((a, k) => a + k, 0);
  const parts = [];
  if (s5.total) parts.push({ what: `server errors (${codeWords(s5.codes)}) ${times(s5.total)}`, by: s5.names, codes: s5.codes });
  if (s4.total) parts.push({ what: `refused (${codeWords(s4.codes)}) ${times(s4.total)}`, by: s4.names, codes: s4.codes });
  if (slow) parts.push({ what: `slow answers (a second or more) ${times(slow)}`, by: facts.slow, codes: {} });
  // A redirect is said, not counted against the page: the log does not say where it leads,
  // and a site may send AI to the page's Markdown copy on purpose (that copy's own line says
  // whether it answers).
  const moved = s3.total ? { what: `redirected (${codeWords(s3.codes)}) ${times(s3.total)}`, by: s3.names, codes: s3.codes } : null;
  const where = "The log does not say where a redirect leads, so it is not counted as a problem.";
  if (!parts.length) {
    if (moved) return { id: "errors", title, state: "good", says: `No error or slow answer to AI on this page in ${windowWords(w)}; it was ${moved.what}. ${where}`, detail: [moved] };
    if (w.folded) return { id: "errors", title, state: "unknown", says: `No error or slow answer recorded for this page in ${windowWords(w)}. ${folded(w)}` };
    return { id: "errors", title, state: "good", says: `No error, redirect or slow answer to AI on this page in ${windowWords(w)}.` };
  }
  const action = s5.total ? "Fix the server error AI crawlers get on this page."
    : s4.total ? "Let AI crawlers through: the server or a firewall refuses them on this page."
      : "Speed the page up: crawlers give up on slow pages.";
  const all = moved ? [...parts, moved] : parts;
  return { id: "errors", title, state: "attention", says: `In ${windowWords(w)} AI got ${listWords(all.map((p) => p.what))}.`, detail: all, action };
}

function sitemapLine(F, key) {
  const sm = F.sitemap || {}, title = "In the sitemap";
  if (!sm.enabled) return { id: "sitemap", title, state: "unknown", says: "Skald does not read this site's sitemap (crawl_health.sitemap is off)." };
  if (!sm.pages) return { id: "sitemap", title, state: "unknown", says: "Skald has no copy of the site's sitemap yet.", action: "Name the sitemap in robots.txt (Sitemap: https://…/sitemap.xml), or under crawl_health.sitemaps." };
  const read = sm.day ? `read ${dayWords(sm.day)}, ${fmt(sm.count)} pages` : `${fmt(sm.count)} pages`;
  if (!(key in sm.pages)) return { id: "sitemap", title, state: "attention", says: `Not in your sitemap (${read}).`, action: "Add the page to the sitemap." };
  const lm = sm.pages[key];
  return { id: "sitemap", title, state: "good", says: lm ? `In your sitemap, last changed ${dayWords(lm)} (its lastmod).` : `In your sitemap (${read}), without a last-changed date (lastmod).` };
}

function copyLine(F, facts) {
  const w = F.window || {}, title = "Markdown copy";
  if (!w.recorded) return { id: "copy", title, state: "unknown", says: NOT_YET };
  const copies = facts?.copies || {};
  if (!Object.keys(copies).length) {
    return { id: "copy", title, state: "unknown", says: `AI did not ask for a Markdown copy of this page in ${windowWords(w)}, so Skald cannot tell whether one exists.` };
  }
  const all = { total: 0, codes: {}, names: {} }, bad = { total: 0, codes: {}, names: {} };
  const detail = [];
  for (const [p, per] of Object.entries(copies)) {
    const a = tally(per, () => true), b = tally(per, (c) => !ok(c));
    for (const [x, y] of [[all, a], [bad, b]]) {
      x.total += y.total;
      for (const [k, v] of Object.entries(y.codes)) x.codes[k] = (x.codes[k] || 0) + v;
      for (const [k, v] of Object.entries(y.names)) x.names[k] = (x.names[k] || 0) + v;
    }
    detail.push({ path: p, total: a.total, codes: a.codes, by: a.names });
  }
  detail.sort((x, y) => y.total - x.total || x.path.localeCompare(y.path));
  const asked = `AI asked for the Markdown copy ${times(all.total)}`;
  if (!bad.total) return { id: "copy", title, state: "good", says: `${asked}; it answered ${codeWords(all.codes)}${all.total > 1 ? " each time" : ""}.`, detail };
  const one = Object.keys(bad.codes).length === 1 ? Object.keys(bad.codes)[0] : null;
  const says = bad.total === all.total && one ? `${asked}; it answered ${one}${all.total > 1 ? " each time" : ""}.`
    : `${asked}; ${times(bad.total)} it answered ${codeWords(bad.codes)}.`;
  const nf = (bad.codes["404"] || 0) + (bad.codes["410"] || 0);
  const action = nf ? `Fix the ${bad.codes["404"] ? "404" : "410"} on the Markdown copy, or stop sending AI to it (a plugin or a redirect may point AI there).`
    : Object.keys(bad.codes).some((c) => c.startsWith("5")) ? "Fix the server error on the Markdown copy." : "Make the Markdown copy answer 200.";
  return { id: "copy", title, state: "attention", says, detail, action };
}

function notFoundLine(F, facts) {
  const w = F.window || {}, title = "AI asking for a 404";
  if (!w.recorded) return { id: "notfound", title, state: "unknown", says: NOT_YET };
  const nf = tally(facts?.self, (c) => c === "404" || c === "410");
  if (!nf.total) {
    if (w.folded) return { id: "notfound", title, state: "unknown", says: `No 404 recorded for this page in ${windowWords(w)}. ${folded(w)}` };
    return { id: "notfound", title, state: "good", says: `No AI request for this page got a 404 in ${windowWords(w)}.` };
  }
  return { id: "notfound", title, state: "attention", says: `AI asked for this page ${times(nf.total)} and got ${codeWords(nf.codes)} (${byWords(nf.names)}).`,
    detail: [{ what: "not found", by: nf.names, codes: nf.codes }], action: "Bring the page back, or redirect its address to the page that replaced it." };
}

/* The assistants' fetches of one page by day, from page_trends.json (L1). */
function reads(pt, key) {
  const per = new Map();
  for (const d of pt.days || []) {
    if ((d.state !== "ok" && d.state !== "partial") || !d.fetches) continue;
    const got = { n: 0, who: {} };
    for (const [p, w] of Object.entries(d.fetches.paths || {})) {
      if (p === OTHER || pageKey(p) !== key) continue;
      for (const [who, k] of Object.entries(w)) { got.n += k; got.who[who] = (got.who[who] || 0) + k; }
    }
    per.set(d.day, { ...got, folded: !!d.fetches.folded });
  }
  return per;
}

function readLine(pt, key, anchor) {
  const title = "Last AI read";
  if (!pt) return { id: "read", title, state: "unknown", says: "Not recorded yet: the assistants' reads by page come with the next redraw." };
  if (pt.whole_site_only) return { id: "read", title, state: "unknown", says: "Counted for the whole site only: choose All pages." };
  const per = reads(pt, key);
  const sum = (from, to) => { let n = 0, days = 0, all = 0; for (let d = from; d <= to; d = addDays(d, 1)) { all += 1; const x = per.get(d); if (x) { n += x.n; days += 1; } } return { n, days, all }; };
  const now = sum(addDays(anchor, -29), anchor), before = sum(addDays(anchor, -59), addDays(anchor, -30));
  const last = [...per.entries()].filter(([, x]) => x.n).sort((a, b) => (a[0] < b[0] ? 1 : -1))[0];
  if (!now.days && !last) return { id: "read", title, state: "unknown", says: "The assistants' reads by page are not recorded for the last 30 days." };
  const cover = now.days < now.all ? ` (${fmt(now.days)} of ${fmt(now.all)} days recorded)` : "";
  const was = before.days === before.all ? `, ${fmt(before.n)} in the 30 before` : "";
  if (now.n) {
    const who = byWords(last[1].who);
    return { id: "read", title, state: "good", says: `An assistant last fetched it for someone on ${dayWords(last[0])} (${who}); ${times(now.n)} in the last 30 days${cover}${was}.`,
      detail: [{ what: "trend", now: now.n, before: before.days === before.all ? before.n : null }] };
  }
  return { id: "read", title, state: "attention",
    says: last ? `No assistant fetched it for someone in the last 30 days${cover}; the last time was ${dayWords(last[0])}.` : `No assistant fetched it for someone in the last 30 days${cover}.`,
    action: "Make sure the lines above are good, and link to it from pages AI already reads." };
}

export function readiness(F, pt, path, anchor) {
  const key = pageOf(path);
  const facts = F?.pages?.[key] || null;
  const own = String(path || "/").split("?")[0];
  return [robotsLine(F, own), errorsLine(F, facts), sitemapLine(F, key), copyLine(F, facts), notFoundLine(F, facts), readLine(pt, key, anchor)];
}

// ------------------------------------------------------- the site's list
export const NEED_FILTERS = [["", "All"], ["copy", "Markdown copy"], ["404", "404"], ["errors", "Errors"], ["robots", "robots.txt"], ["slow", "Slow"]];
export const needKeep = (want) => (r) => !want || (want === "copy" ? r.copy_errors > 0 : want === "404" ? r.not_found > 0
  : want === "errors" ? r.server_errors + r.blocked > 0 : want === "robots" ? r.robots.length > 0 : want === "slow" ? r.slow > 0 : true);

export function needWords(r) {
  const out = [];
  if (r.copy_errors) out.push(r.copy_404 === r.copy_errors ? `Markdown copy: 404 ${times(r.copy_errors)}` : `Markdown copy: errors ${times(r.copy_errors)}`);
  if (r.not_found) out.push(`the page: 404 ${times(r.not_found)}`);
  if (r.server_errors) out.push(`server errors ${times(r.server_errors)}`);
  if (r.blocked) out.push(`refused ${times(r.blocked)}`);
  if (r.robots.length) out.push(`robots.txt shuts out ${listWords(r.robots)}`);
  if (r.slow) out.push(`slow ${times(r.slow)}`);
  if (r.redirects) out.push(`redirected ${times(r.redirects)}`);
  return out.join(" · ");
}

export function needAction(r) {
  if (r.copy_errors) return r.copy_404 ? "Fix the 404 on the Markdown copy" : "Fix the Markdown copy";
  if (r.not_found) return "Bring the page back or redirect it";
  if (r.server_errors) return "Fix the server error";
  if (r.blocked) return "Let AI crawlers through";
  if (r.robots.length) return `Allow ${listWords(r.robots)} in robots.txt`;
  return "Speed the page up";
}

/* The crawlers robots.txt shuts out of the whole site: said once, above the list. */
export function wholeSite(F) {
  const c = F?.robots?.crawlers;
  if (!c) return [];
  return (F.crawlers || []).map(([t]) => t).filter((t) => c[t] && !c[t].root);
}
