// robots.txt beside behaviour: for each crawler, the rule that applies to it,
// whether it may fetch the site at all, and how often it fetched a path the
// rules keep it from; then the site's robots.txt itself, group by group.
// From robots.json (the last 30 days and today). A past day is judged by
// today's robots.txt, and the section says so.

import { h, n } from "../ui.js";
import { ago } from "../tz.js";
import { table } from "../table.js";
import { fixed, notBuiltNote } from "./common.js";
import { withUrl, copyIf } from "../urlactions.js";

export const robotsOf = (m) => new Map((m.x.robots?.crawlers || []).map((c) => [c.name, c]));

// One verdict per crawler: may it fetch the site, and did it keep to the rules.
export function verdict(c) {
  if (!c) return null;
  if (!c.root_allowed) return c.disallowed ? ["bad", "Blocked, fetched anyway"] : ["off", "Blocked"];
  return c.disallowed ? ["warn", "Allowed, crossed a rule"] : ["ok", "Allowed"];
}
export function robotsBadge(c) {
  const v = verdict(c);
  if (!v) return h("span", { class: "rb none", title: "Not seen in the last 30 days" }, "-");
  return h("span", { class: `rb ${v[0]}`, title: c.disallowed ? `${n(c.disallowed)} fetches of paths robots.txt keeps it from, in 30 days` : `The robots.txt group that applies: ${c.applies}` }, v[1]);
}
export const robotsWords = (c) => verdict(c)?.[1] || "";

function rules(file) {
  const r = file.robots || {};
  if (!r.ok) return h("div", { class: "state bad" }, h("div", null, `robots.txt could not be read${r.error ? `: ${r.error}` : ""}. The verdicts above use the last copy that was.`));
  // Each line with its copy icon: the line as robots.txt has it.
  const line = (k, v) => copyIf("text", h("div", { class: "rt-l" }, h("span", { class: "rt-k" }, `${k}:`), " ", h("span", { class: "rt-v" }, v)), `${k}: ${v === "(nothing)" ? "" : v}`.trim(), { label: "line", cls: "ua-block" });
  return h("div", null,
    h("div", { class: "rt-groups" }, (r.groups || []).map((g) => h("div", { class: "rt-g" },
      (g.agents || []).map((a) => line("User-agent", a)),
      (g.allow || []).map((p) => line("Allow", p)),
      (g.disallow || []).map((p) => line("Disallow", p || "(nothing)")),
      g.crawl_delay != null ? line("Crawl-delay", String(g.crawl_delay)) : null))),
    (r.sitemaps || []).length ? h("p", { class: "note" }, "Sitemaps: ", r.sitemaps.map((u, i) => [i ? ", " : "", withUrl(h("code", null, u), u, { cls: "ua-after" })])) : null);
}

export function robotsSection(m) {
  const file = m.x.robots;
  if (!file) return notBuiltNote(m, "robots", "robots.txt beside the crawlers");
  const r = file.robots || {};
  const rows = (file.crawlers || []).map((c) => ({ ...c, verdict: robotsWords(c), today_n: c.today ? c.today.requests : null }));
  const offLimits = (c) => (c.disallowed ? h("span", { class: "rt-off" }, h("b", null, n(c.disallowed)),
    (c.disallowed_paths || []).length ? h("small", null, c.disallowed_paths.slice(0, 3).map((p) => `${p.path} (${n(p.n)})`).join(", ")) : null) : "0");
  return fixed("robots.txt", "last 30 days and today",
    h("p", { class: "sub" }, r.fetched_at ? `Read from ${r.url || "/robots.txt"} ${ago(r.fetched_at)}. ` : "",
      "Each crawler is judged by its own token against today's rules, past days included; a rule changed since then is not taken into account."),
    table([
      { key: "name", label: "Crawler", drill: "bot" },
      { key: "applies", label: "Rule that applies", fmt: (v) => h("code", null, v === "*" ? "* (everyone)" : v) },
      { key: "verdict", label: "robots.txt", type: "badge", fmt: (_, c) => robotsBadge(c) },
      { key: "requests", label: "Requests", num: true },
      { key: "disallowed", label: "Off-limits fetches", num: true, fmt: (_, c) => offLimits(c), csv: (c) => c.disallowed },
      { key: "today_n", label: "Today", num: true, fmt: (v) => (v == null ? "-" : n(v)) },
    ], { caption: "Crawlers and robots.txt", rows, file: "robots-txt-by-crawler.csv", sortKey: "requests", empty: "No crawler in the last 30 days." }),
    h("p", { class: "note" }, "To let a crawler in or keep it out, see ", h("a", { href: "#ai/rules" }, "AI & bots › Crawler rules"), "."),
    h("h3", { class: "rt-h" }, "The rules as written"),
    rules(file));
}
