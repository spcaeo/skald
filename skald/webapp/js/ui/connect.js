// "Not connected yet" (2.43, docs/UI-RULES.md): one card for every page that is empty because a
// source is missing, instead of an empty table. The owner, 2026-10-27, on kiwiform.com's empty
// Leads page: "we should dynamically show option or way to do that ... and connect all such dots".
//
//   connectCard(m, need, { mode })  need: leads, bookings, payments, search, tools, journeys,
//                                   script (js/connect-plan.js NEEDS). mode:
//     page   the page is empty: what it needs (one line), what Skald already found on the site
//            (the site check's framework, platform, forms and tools), the way it recommends,
//            one primary "Connect" and a quiet "Other ways" fold
//     line   a part of a page: one quiet line with a plain Connect
//     plain  the state only, no push (AI answers, off without keys by the owner's rule)
//   partlyLine(m, page)             a page fed by some of its sources: what is still missing
//   sourceLink(group)               the page's way back to its source's group in Leads & tools
//                                   (#settings/site/leads?lt=<group>), for whoever may connect
//   sourcesFor(site)                GET integrations and your tools, asked once a minute
//
// Connect opens the existing dialog through the address (setup=lead&way=<tool>, setup=search,
// setup=script, setup=tool-<id>, setup=finish-tools, rjc=connect): each asks "Who will do it?"
// (ui/who.js) first. A viewer, or a member who may not connect, reads "Ask an admin to connect
// it" with the dialog's address and its copy and open icons. Nothing new is fetched from the site:
// what was found comes from the set-up's own check (integrations_api.found_of).

import { h } from "../ui.js";
import * as S from "../state.js";
import { OVERLAY } from "../routekeys.js";
import { ME, sessions } from "../access.js";
import { DEMO } from "../demo.js";
import { call } from "../tabs/ipmanager.js";
import { primary } from "./primary.js";
import { help } from "./help.js";
import { fold } from "./fold.js";
import { pill } from "./pill.js";
import { withUrl, withCopy } from "../urlactions.js";
import { NEEDS, groupById, rowsOf, recommend, otherWays, factsOf, partly, PARTLY } from "../connect-plan.js";

const GUIDE = { leads: "leads-and-conversions", bookings: "demo-bookings", payments: "revenue", search: "search", tools: "your-tools",
  journeys: "recorded-journeys", script: "tracking-script" };
const PLUG = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2.5v3M10 2.5v3M4.5 5.5h7v2.5a3.5 3.5 0 0 1-7 0z"/><path d="M8 11.5v2"/></svg>';
const LEADS_TOOLS = "settings/site/leads";

/* May this reader connect a source here (an owner, an admin, an install admin, with accounts)? */
export const mayConnect = () => !DEMO.on && sessions() && (["owner", "admin"].includes(ME.role) || !!ME.install_admin);

/* The address of a dialog (or a move), from the page open now: what an admin opens. */
export function hashOf(patch, s = S.read()) {
  return S.hashFor({ ...s, ...(patch.tab ? Object.fromEntries(OVERLAY.map((k) => [k, ""])) : {}), ...patch });
}
export function linkFor(patch, s = S.read()) {
  const loc = typeof location !== "undefined" ? location : { origin: "", pathname: "" };
  return `${loc.origin || ""}${loc.pathname || ""}${hashOf(patch, s)}`;
}
/* Open what an act names: the dialog over this page (Back closes it), or another page. */
export function go(patch) {
  const ov = Object.keys(patch).find((k) => OVERLAY.includes(k));
  if (patch.tab) S.set(patch);
  else S.set(patch, ov ? { mark: { ov } } : {});
}

// ---- what the server knows: GET integrations (with `found`) and your own tools ------------
const asked = new Map();      // site -> {at, p}
export function sourcesFor(site) {
  if (!mayConnect()) return Promise.resolve(null);
  const kept = asked.get(site);
  if (kept && Date.now() - kept.at < 60000) return kept.p;
  const p = Promise.all([call(`integrations?site=${encodeURIComponent(site)}`), call("integrations/yourtools")])
    .then(([integ, yours]) => (integ && integ.ok ? { integ, yours: yours && yours.ok ? yours : null, found: integ.found || null } : null))
    .catch(() => null);
  asked.set(site, { at: Date.now(), p });
  return p;
}
export const forgetSources = () => asked.clear();
const searchOf = (m) => !!(m?.x?.search?.engines?.google?.connected || m?.x?.search?.engines?.bing?.connected);
export const rowsFrom = (got, m) => rowsOf({ integ: got?.integ, yours: got?.yours, searchOn: searchOf(m) });

// ---- the pieces --------------------------------------------------------------------------
/* What Skald found on the site: chips, a copy icon on each value (a tag's ID, a booking link). */
export function foundChips(found, site) {
  const facts = factsOf(found);
  if (!facts.length) return null;
  return h("div", { class: "ui-conn-found" }, h("span", { class: "ui-conn-k" }, `Skald found on ${site}`),
    h("span", { class: "ui-conn-chips" }, facts.map((f) => (f.value
      ? withCopy(h("span", { class: "ui-chip" }, `${f.label}: `, h("code", null, f.value)), f.value, { label: `${f.label} ${f.value}` })
      : h("span", { class: "ui-chip" }, f.label)))));
}

/* Ask an admin: the dialog's address, with its copy and open icons. */
function askAdmin(patch, s) {
  const link = linkFor(patch, s);
  return h("div", { class: "ui-conn-ask" }, h("p", null, h("b", null, "Ask an admin to connect it. "), "Send them this link: it opens the set-up for this page."),
    withUrl(h("code", { class: "ui-conn-link" }, link), link, { label: "the set-up link" }));
}

function others(need, found, s) {
  const ways = otherWays(need, found);
  const group = NEEDS[need]?.group;
  const items = ways.map(([words, act]) => {
    const b = h("button", { type: "button", class: "linkish" }, words);
    b.addEventListener("click", () => go(act));
    return h("li", null, b);
  });
  items.push(h("li", null, h("a", { href: hashOf({ tab: LEADS_TOOLS, lt: group || "" }, s) }, "Every source, in Settings › Leads & tools")));
  return fold("Other ways", () => h("ul", { class: "ui-conn-ways" }, items), { cls: "ui-conn-other" });
}

/* The card. m: the page's model (m.site); need: a NEEDS key. */
export function connectCard(m, need, { mode = "page", s = null, title = null, line = null, plainExtra = null } = {}) {
  const st = s || S.read();
  const n = NEEDS[need];
  if (!n) return null;
  const head = title || n.title;
  const words = line || n.line;
  const q = help(head, { guide: GUIDE[need] || "" });
  let act = recommend(need, null).act;
  if (mode === "plain") {
    return h("section", { class: "ui-card quiet ui-conn ui-conn-plain", role: "status", "data-need": need },
      h("div", { class: "ui-card-h" }, h("span", { class: "ui-ic", html: PLUG }), h("h2", null, head), pill("off", "Off"), q),
      h("p", { class: "ui-meta" }, words), plainExtra);
  }
  if (mode === "line") {
    const tail = mayConnect() ? h("button", { type: "button", class: "btn" }, "Connect")
      : DEMO.on ? null : withCopy(h("small", { class: "muted" }, "Ask an admin to connect it"), linkFor(act, st), { label: "the set-up link" });
    if (tail?.tagName === "BUTTON") tail.addEventListener("click", () => go(act));
    const box = h("div", { class: "ui-card quiet ui-conn-line", role: "status", "data-need": need },
      h("span", { class: "ui-ic", html: PLUG }), h("span", { class: "ui-grow" }, h("b", null, head), " ", h("span", { class: "muted" }, words)), q, tail);
    if (mayConnect()) sourcesFor(m.site).then((got) => { if (got) act = recommend(need, got.found).act; });
    return box;
  }
  // page
  const box = h("section", { class: "ui-card ui-conn", role: "status", "data-need": need },
    h("div", { class: "ui-card-h" }, h("span", { class: "ui-ic", html: PLUG }), h("h2", null, head), q),
    h("p", { class: "ui-meta ui-conn-need" }, words));
  if (DEMO.on) { box.append(h("p", { class: "note" }, "In the demo, connecting a source needs a running Skald.")); return box; }
  if (!mayConnect()) { box.classList.add("quiet"); box.append(askAdmin(act, st)); return box; }
  const found = h("div", { class: "ui-conn-slot" });
  const rec = h("p", { class: "ui-conn-rec" }, h("span", { class: "ui-conn-k" }, "Recommended"), h("span", null, recommend(need, null).words));
  const btn = primary("Connect", () => go(act), { icon: PLUG });
  btn.classList.add("ui-conn-go");
  const other = h("div", { class: "ui-conn-o" }, others(need, null, st));
  box.append(found, rec, h("div", { class: "ui-conn-acts" }, btn), other);
  sourcesFor(m.site).then((got) => {
    if (!got) return;
    const r = recommend(need, got.found);
    act = r.act;
    rec.lastChild.textContent = r.words;
    found.replaceChildren(...[foundChips(got.found, m.site)].filter(Boolean));
    other.replaceChildren(others(need, got.found, st));
  });
  return box;
}

/* A page fed by some of its sources: one quiet strip, what is missing and its Connect. Admins
   only (they can act on it); null when there is nothing to say, filled when the answer comes. */
export function partlyLine(m, page) {
  if (!mayConnect() || !PARTLY[page]) return null;
  const box = h("div", { class: "ui-strip ui-conn-part", role: "status", hidden: true });
  sourcesFor(m.site).then((got) => {
    if (!got) return;
    const rows = rowsFrom(got, m);
    const words = partly(page, rows, got.found);
    if (!words) return;
    const need = PARTLY[page].also.find((g) => words.includes(g === "leads" ? "your forms" : g)) || page;
    const act = recommend(need, got.found).act;
    const b = h("button", { type: "button", class: "btn" }, "Connect");
    b.addEventListener("click", () => go(act));
    box.replaceChildren(pill("warn", "Partly connected"), h("span", { class: "ui-grow" }, words), b,
      h("a", { href: hashOf({ tab: LEADS_TOOLS, lt: NEEDS[need]?.group || page }) }, "Leads & tools"));
    box.hidden = false;
  });
  return box;
}

/* The way back from a data page to its source's group in Leads & tools. */
export function sourceLink(group, words = "Sources: Leads & tools") {
  if (!mayConnect() || !groupById(group)) return null;
  return h("a", { class: "ui-conn-src", href: hashOf({ tab: LEADS_TOOLS, lt: group }) }, words);
}
