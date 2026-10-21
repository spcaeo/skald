// Security > Your stack (2.21): what serves the site, read from outside once a day
// (stack.py), and the advisories shipped with Skald that apply to it (advisories.py). A card
// per advisory that needs something done; the stack itself per host; the commands to see a
// version the server does not show, folded "For your server admin". Skald tells you what
// applies and how to fix it; it does not detect or block an exploit of these flaws.

import { h } from "../ui.js";
import { emptyState } from "./sa-options.js";
import { secTab, at } from "./sec-common.js";

export const STATE = { update_needed: ["Update needed", "bad"], no_fix: ["No official fix: upgrade the branch", "bad"],
  check_version: ["Check your version", "warn"], fixed: ["Fixed", "ok"], not_listed: ["Not listed", "ok"] };
const ACT = ["update_needed", "no_fix", "check_version"];
const NOT_SHOWN = "not shown by the server";

export const nameOf = (st, p) => st?.names?.[p] || p;
export const shown = (v) => v || NOT_SHOWN;

/* What to do for one match, in plain words. */
export function todo(m, a) {
  const fixed = Object.values(a.fixed || {}).join(", ");
  if (m.state === "update_needed") return `${a.action} The fixed release for ${m.version.split(".").slice(0, a.branch === "minor" ? 2 : 1).join(".")} is ${a.fixed[m.version.split(".").slice(0, a.branch === "minor" ? 2 : 1).join(".")]}.`;
  if (m.state === "no_fix") return `${a.no_fix_words || "This branch gets no official fix."} Move to a supported branch: fixed in ${fixed}.`;
  return `The server does not show its version. Check it on the server; the fixed releases are ${fixed}.`;
}

/* One card per advisory that applies, with every host it applies to. */
export function card(a, matches, st, item = "") {
  const worst = ACT.find((s) => matches.some((m) => m.state === s));
  const [words, tone] = STATE[worst];
  const mine = !!item && matches.some((m) => m.item === item);
  return h("article", { class: `sec-card ${tone}${mine ? " focus" : ""}`, "aria-label": a.title },
    mine ? h("p", { class: "sec-from" }, "From your alert") : null,
    h("div", { class: "sec-card-top" }, h("span", { class: `sec-pill ${tone}` }, words),
      h("span", { class: "sec-sev" }, `${a.severity.charAt(0).toUpperCase()}${a.severity.slice(1)}${a.score ? ` · ${a.score}` : ""} · ${a.published}`)),
    h("h3", null, a.title),
    h("p", null, a.summary || ""),
    h("ul", { class: "sec-hits" }, matches.map((m) => h("li", null,
      h("strong", null, `${nameOf(st, m.product)} ${shown(m.version)}`), ` on ${m.host}: `, STATE[m.state][0], ". ", todo(m, a)))),
    a.affected ? h("p", { class: "note" }, a.affected) : null,
    (a.mitigations || []).length ? h("details", { class: "sec-fold" }, h("summary", null, "Mitigations while you update"),
      h("ul", null, a.mitigations.map((x) => h("li", null, x))), a.mitigations_note ? h("p", { class: "note" }, a.mitigations_note) : null) : null,
    h("p", { class: "sec-src" }, "Source: ", (a.sources || []).map((u, i) => [i ? ", " : "", h("a", { href: u, target: "_blank", rel: "noopener" }, new URL(u).hostname)]),
      (a.cves || []).length ? ` · ${a.cves.join(", ")}` : ""));
}

export function hostsPart(st) {
  const by = new Map();
  for (const p of st.products || []) { if (!by.has(p.host)) by.set(p.host, []); by.get(p.host).push(p); }
  const logins = new Map((st.logins || []).map((x) => [x.host, x]));
  return h("div", { class: "sec-stack" }, (st.hosts || []).map((x) => {
    const items = by.get(x.host) || [];
    const login = logins.get(x.host);
    return h("div", { class: "card sec-host" },
      h("h3", null, x.host, h("span", { class: "sec-tag" }, x.role === "site" ? "the site" : "content origin")),
      x.error ? h("p", { class: "note" }, `Not read: ${x.error}`) : null,
      items.length ? h("dl", { class: "sec-dl" }, items.map((p) => [h("dt", null, nameOf(st, p.product)),
        h("dd", null, shown(p.version), h("span", { class: "sec-how" }, ` (${p.how})`))])) : x.error ? null : h("p", { class: "note" }, "Nothing the server or page names."),
      login ? h("p", { class: login.open ? "sec-login bad" : "sec-login" },
        login.open ? "Login page open to the internet: /wp-login.php answers anyone." : `Login page not open to the internet (/wp-login.php answered ${login.status}).`) : null);
  }));
}

export function adminPart(st) {
  const hidden = [...new Set((st.products || []).filter((p) => !p.version).map((p) => p.product))];
  if (!hidden.length) return null;
  return h("details", { class: "sec-fold" }, h("summary", null, "For your server admin: versions the server does not show"),
    h("p", null, "Run these on the server to see each version, then compare it with the fixed releases above:"),
    h("ul", null, hidden.map((p) => h("li", null, `${nameOf(st, p)}: `, h("code", null, st.commands?.[p] || "-")))));
}

export default function stackTab(m, s) {
  return secTab(m, s, {
    title: "Your stack",
    question: "What runs the site, and does a known flaw apply to it?",
    period: "Checked once a day",
    help: "Skald reads the site's home page once a day, from outside, like any visitor: what the server says about itself (Server, X-Powered-By) and what the page says built it. A version the server hides is not guessed. The advisories come with Skald's releases. This tells you what applies to your stack and how to fix it; Skald does not detect or block an exploit of these flaws.",
    draw: ({ f }) => {
      const st = f.stack;
      if (!st) return [emptyState("Not checked yet: Skald reads the site's stack once a day, in the morning run.")];
      const parts = [h("p", { class: "sec-asof" }, `As of ${at(st.checked_at)} · advisories list of ${st.list_updated || "-"}`)];
      const cards = (st.advisories || []).map((a) => [a, (st.matches || []).filter((x) => x.advisory === a.id && ACT.includes(x.state))])
        .filter(([, ms]) => ms.length);
      if (s.item && !(st.matches || []).some((x) => x.item === s.item && ACT.includes(x.state))) {
        parts.push(h("p", { class: "note sec-item" }, "The item in this link no longer applies: the last check no longer finds it."));
      }
      cards.sort(([, a], [, b]) => (b.some((x) => x.item === s.item) ? 1 : 0) - (a.some((x) => x.item === s.item) ? 1 : 0));
      if (cards.length) parts.push(h("div", { class: "sec-cards" }, cards.map(([a, ms]) => card(a, ms, st, s.item))));
      else parts.push(emptyState("No advisory in Skald's list applies to what the server shows."));
      parts.push(h("h2", { class: "sec-h2" }, "What serves the site"), hostsPart(st), adminPart(st),
        h("p", { class: "note" }, "This tells you what applies to your stack and how to fix it. Skald does not detect or block an exploit of these flaws."));
      return parts;
    },
  });
}
