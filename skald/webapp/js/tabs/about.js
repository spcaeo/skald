// About Skald: who made it and why, why the name, how it compares with the
// usual tools (compare.js), and what each tab does. The words come from the docs, built
// into about-data.js by tools/build-about.py and loaded only when this page
// opens; links to other sites open in a new tab and send no referrer.

import { h } from "../ui.js";
import * as S from "../state.js";
import { MARK } from "../mark.js";
import { BUILD, toolName, toolTagline } from "../build.js";
import { compare } from "./compare.js";
import { line, blockList } from "../mdview.js";

let DATA = null;
// Where addresses appear and what is kept: the footer's Privacy (i), and a section here.
export const PRIVACY = "Visitor IP addresses appear only on this private page: the last 6 hours of requests and today's AI activity. Stored history holds totals and 30-day one-way codes, never addresses. Raw logs stay on the server for 14 days, and one command removes an address on request.";
const PARTS = [["why", "Why we built Skald"], ["name", "Why the name"], ["compare", "How Skald compares"], ["features", "What Skald can do"]];

// ------------------------------------------------------------- words
// seg, line and blockList are mdview.js's, shared with Help.

/* Long prose as rows: each heading on the left, its text across the rest of
   the width - the page's whole width is used, and no column is left empty. */
function prose(blocks, first = "") {
  const rows = [];
  let cur = { title: first, blocks: [] };
  for (const b of blocks) {
    if (/^h[2-4]$/.test(b.t)) { if (cur.title || cur.blocks.length) rows.push(cur); cur = { title: b.text, blocks: [] }; } else cur.blocks.push(b);
  }
  if (cur.title || cur.blocks.length) rows.push(cur);
  return h("div", { class: "prose" }, rows.map((r) => h("div", { class: "prose-row" }, h("h3", null, r.title), h("div", null, blockList(r.blocks)))));
}

// --------------------------------------------------------- feature map
// The menu's groups (state.js MENU), each page with what it is for.
const FEATURES = [
  ["Home", [
    ["overview", "Visitors, pages read, visitors from AI, leads and returning visitors for any period, with the machines in their own units."],
    ["live", "Today so far, every two minutes: who is reading now and which assistants are fetching."],
    ["insights", "What changed, in plain words: working, dropped, new, gone, unusual."],
    ["compare", "Any two periods side by side, A against B: the figures, both on one chart, and what is new or gone."],
  ]],
  ["Audience", [
    ["visitors", "Each visit's pages in order, its length and where it came from."],
    ["sources", "Search, AI assistants, social, email, campaigns and referring sites."],
    ["pages", "What was read, where visits started, and each page in depth."],
    ["locations", "Countries, devices, browsers and systems."],
    ["time", "When people come, hour by hour."],
  ]],
  ["Results", [
    ["leads", "Sign-ups and demo bookings by source, first and last touch, and the funnel to them."],
    ["conversions", "Every action that counts - a demo booked, a form sent, a sign-up, a payment - from the script tag, the tools' webhooks and the lead database: started, completed, abandoned, and where they came from."],
    ["funnels", "Any series of pages, in order: how many visits went through, and where the rest left."],
    ["events", "What readers did inside the pages: buttons, forms, demo bookings, reading and copying, by page and source."],
  ]],
  ["AI & bots", [
    ["bots", "AI assistants by why they came, search engines, bots and scanners, each crawler checked against its owner's addresses."],
  ]],
  ["Site & server", [
    ["health", "Server requests, errors and how fast pages were answered."],
    ["health/alerts", "Site down, errors, a broken-link surge, a new crawler: open and closed."],
    ["health/quality", "Whether each day can be trusted, and when each job last ran."],
    ["health/speed", "How fast the top pages load and respond, for real users and in Google's lab test, phone and desktop."],
    ["health/broken", "Pages people could not find, and whether a redirect fixes them."],
    ["requests", "The last six hours, request by request, each with the rule that put it in its group."],
  ]],
  ["Settings", [
    ["settings/account", "Your name, password, two-step sign-in and where you are signed in."],
    ["settings/team", "Invite people and choose what each may do."],
    ["settings/users", "Who may look and who may change things: admins and viewers."],
    ["settings/api", "Every figure as JSON, with the dashboard login or a token; tokens for scripts, and the MCP address for AI assistants."],
    ["settings/internal", "Our own machines and the heartbeat, and the addresses that count as ours."],
    ["settings/integrations", "Webhooks from booking, form and payment tools, and the skald.js tag, for Conversions."],
    ["settings/retention", "How long each kind of record is kept."],
    ["settings/mail", "Reports, alerts and failure mail: who gets what."],
    ["settings/security", "Sign-in rules for everyone in the organisation."],
    ["settings/audit", "Who changed what, and when."],
  ]],
  ["Help", [
    ["help", "Guides in plain words: getting started, sign-in and team, internal traffic, leads and conversions, the tracking script, webhooks, funnels, the API, MCP, settings, privacy and questions."],
  ]],
];
const tabName = (k) => S.nameOf(k);
function features() {
  return h("div", { class: "fmap" }, FEATURES.map(([group, items]) => h("div", { class: "sheet card" }, h("h3", null, group),
    h("ul", null, items.filter(([tab]) => S.shown(tab)).map(([tab, what]) => h("li", null, h("a", { href: `#${tab}` }, tabName(tab)), h("span", null, what)))))));
}

// ---------------------------------------------------------------- page
function page(s) {
  const ver = BUILD ? `Version ${BUILD.version} · release ${BUILD.release} · ${BUILD.commit}` : "";
  const quote = DATA.name.find((b) => b.t === "quote" && /storyteller/i.test(b.in.map((x) => x.s ?? x.b ?? "").join("")));
  const hero = h("header", { class: "about-hero" }, h("span", { class: "about-mark", "aria-hidden": "true", html: MARK }),
    h("div", null, h("h1", { class: "about-name" }, toolName()), h("p", { class: "about-tag" }, toolTagline()),
      quote ? h("p", { class: "about-pitch" }, line(quote.in)) : null, ver ? h("p", { class: "about-ver" }, ver) : null));
  const nav = h("nav", { class: "about-nav", "aria-label": "On this page" }, PARTS.map(([k, name]) =>
    h("a", { href: `#about?part=${k}`, "aria-current": s.part === k ? "true" : null }, name)));
  const name = DATA.name.filter((b) => b !== quote);
  const out = [hero, nav,
    h("section", { class: "s about-sec", id: "about-why" }, h("h2", null, "Why we built Skald"), prose(DATA.why, "In short")),
    h("section", { class: "s about-sec", id: "about-name" }, h("h2", null, "Why the name"), prose(name, "The skalds")),
    h("section", { class: "s about-sec", id: "about-compare" }, h("h2", null, "How Skald compares"), compare(DATA.compare)),
    h("section", { class: "s about-sec", id: "about-features" }, h("h2", null, "What Skald can do"), features()),
    h("section", { class: "s about-sec", id: "about-privacy" }, h("h2", null, "Privacy"), h("p", { class: "about-privacy" }, PRIVACY))];
  requestAnimationFrame(() => { measure(); if (s.part) document.getElementById(`about-${s.part}`)?.scrollIntoView({ block: "start" }); });
  return out;
}

// The top bar's and the sub-nav's real heights, so the sub-nav, the table
// header and every anchor sit just below them at any width.
function measure() {
  const root = document.querySelector(".about");
  if (!root) return;
  const bar = document.querySelector(".bar"), sub = root.querySelector(".about-nav");
  if (bar) root.style.setProperty("--bar-h", `${getComputedStyle(bar).position === "sticky" ? bar.offsetHeight : 0}px`);
  if (sub) root.style.setProperty("--subnav-h", `${sub.offsetHeight}px`);
}
addEventListener("resize", measure);

export default function about(m, s) {
  const root = h("div", { class: "about" });
  if (DATA) root.append(...page(s).flat(Infinity).filter(Boolean));
  else {
    root.append(h("p", { class: "boot" }, "Loading…"));
    import("../about-data.js").then((mod) => { DATA = mod.default; if (root.isConnected) root.replaceChildren(...page(s).flat(Infinity).filter(Boolean)); })
      .catch((e) => root.replaceChildren(h("p", { class: "state bad" }, `The About page could not be loaded: ${e.message || e}`)));
  }
  return root;
}
