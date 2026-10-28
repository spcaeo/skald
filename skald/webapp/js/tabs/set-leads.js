// Settings › This site › Leads & tools (2.43, "connect the dots"; v2 before it). The owner,
// 2026-10-27: a long list of rows did not say what to do first. Now, top to bottom:
//
//   Next step for <site>   what Skald found on the site (the set-up's own check: framework,
//                          platform, forms, Calendly, the GA4 tag...), the single most useful
//                          thing to connect (connect-plan.js nextStep) as the page's one primary,
//                          and "Connect everything left with your AI agent" (setup=finish-tools,
//                          by=agent). Nothing left: one line, and "Connect a tool" by the title.
//   the red lines          a check that needs you (the doctor's own words), with its Fix
//   groups by goal         Leads from your forms, Bookings, Payments, Search, Your own tools,
//                          Recorded journeys, Send each lead out: each a one-line why, then one
//                          row per source with its pill (Connected, Waiting, Failing, Not
//                          connected), when it last sent, and one action (its details, or
//                          Connect). A connected row links to the page that shows its data
//                          ("See leads", "See bookings"...)
//   More you can connect   the rows not connected that do not fit this site (Stripe where no
//                          Stripe was found), folded
//
// The address: lt=<group> (a data page's "Sources: Leads & tools" link) scrolls to that group
// and marks it; tool=<id> is a row's drawer, as before:
//
//   tool=<id>        one incoming hook (site, calendly, calcom, stripe, hubspot, typeform, zapier...)
//   tool=your-<id>   one of your own tools (Google Analytics...): its figures' state, its key
//                    (never shown), Sync now, Pause, Remove (yourtools.js; docs/TOOLS.md)
//   tool=webhooks    Send each lead out: the outgoing webhooks and Add one
//   tool=search      Search Console and Bing
//   tool=checks      every check, with the server's own words
// Connect writes the dialog's own key (setup=lead&way=<tool>, setup=tool-<id>, setup=search,
// setup=script, rjc=connect): each asks "Who will do it?" first. GET <page>/integrations
// (integrations_api.py, with `found`), GET integrations/yourtools and the set-up lines (checklist.js).

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions, VIEWER } from "../access.js";
import { DEMO } from "../demo.js";
import { openDrawer } from "../drawer.js";
import { ago } from "../tz.js";
import { field } from "./forms.js";
import { integrationsPart, integPath, setIntegSite, codeSpans } from "./integrations.js";
import { checkItems, keptItems, openFinish } from "./checklist.js";
import { primary, strip, quietButton, icon, ic, pill, fold, help } from "./set-ui.js";
import { primary as uiPrimary } from "../ui/primary.js";
import { TOOLS_PATH, DRAWER, toolDrawer } from "./yourtools.js";
import { GROUPS, rowsOf, fits, nextStep, stateWords, isOn } from "../connect-plan.js";
import { foundChips, go, hashOf, forgetSources } from "../ui/connect.js";

const FIXED = ["webhooks", "search", "checks"];
const TITLES = { webhooks: "Send each lead out", search: "Search Console & Bing", checks: "Every check" };
const ICONS = { leads: "plug", bookings: "plug", payments: "plug", search: "search", tools: "plug", journeys: "people", out: "out" };

/* Connect a tool: Who will do it? for the lead hook and your own tools, then which tool. */
function connect(m) {
  return primary("Connect a tool", async () => openFinish(m, keptItems(m) || await checkItems(m), { only: "tools" }));
}

/* One of your own tools' drawer (tool=your-<id>). */
async function openYours(id, m) {
  const r = await call(TOOLS_PATH);
  const t = r.ok && (r.tools || []).find((x) => x.id === id);
  if (!t) return "That tool is not one Skald knows.";
  const slot = h("div");
  const d = openDrawer({ title: t.name, size: "md", key: "tool", className: "set-dw", body: slot, route: { key: "tool", value: `${DRAWER}${id}` } });
  const draw = (tool) => slot.replaceChildren(toolDrawer(tool, m.site, { onChange: async () => {
    const again = await call(TOOLS_PATH);
    const next = again.ok && (again.tools || []).find((x) => x.id === id);
    if (next) draw(next);
  } }));
  draw(t);
  return d;
}

/* A drawer with one tool's details, or one of the fixed parts; its key in the address. */
export async function openTool(id, m) {
  const fixed = FIXED.includes(id);
  if (!fixed && !/^[a-z0-9_-]{1,30}$/.test(id)) return "That tool is not one Skald knows.";
  if (DEMO.on) return "In the demo, tools need a running Skald.";
  if (!sessions() || isViewer()) return "Not available to your role.";
  if (id.startsWith(DRAWER)) return openYours(id.slice(DRAWER.length), m);
  let title = TITLES[id] || id;
  let body;
  if (id === "search") body = [(await import("./search-connect.js")).searchBox(m.site)];
  else body = integrationsPart(fixed ? id : `tool:${id}`).filter(Boolean);
  if (!fixed) {
    const r = await call(integPath());
    const t = r.ok && (r.tools || []).find((x) => x.tool === id);
    if (!t) return "That tool is not one Skald knows.";
    title = t.name;
  }
  return openDrawer({ title, size: "md", key: "tool", className: "set-dw", body: h("div", null, body), route: { key: "tool", value: id } });
}
export const openToolKey = (v, m) => openTool(v, m);

/* When a row last sent something: a time (a hook's last delivery) or words (your tools' "2 h ago"). */
function lastWords(row) {
  if (!row.last) return "";
  const when = /^\d{4}-\d\d-\d\dT/.test(row.last) ? ago(row.last) : row.last;
  return row.group === "tools" ? `Last answer ${when}` : row.id === "journeys" ? `Last session ${when}` : `Last received ${when}`;
}

/* One row: its icon, name and line, its pill, one action, and for a connected row the page
   that shows its data. A row that is on opens its details; one that is not, Connect. */
export function ltRow(row, { onOpen, onConnect, group = null }) {
  const [kind, word] = stateWords(row.state);
  const on = isOn(row);
  const line = [lastWords(row), row.line].filter(Boolean).join(" · ");
  const kids = [h("span", { class: "ui-ic", html: icon(ICONS[row.group] || "plug") }),
    h("span", { class: "grow sr-t" }, h("b", null, row.name), line ? h("small", null, line) : null), pill(kind, word)];
  const see = on && row.state !== "failing" && group?.page ? h("a", { class: "lt-see", href: hashOf({ tab: group.page }) }, group.see) : null;
  if (!on) {
    const b = h("button", { type: "button", class: "btn lt-go", "aria-label": `Connect ${row.name}` }, "Connect");
    b.addEventListener("click", () => onConnect(row));
    return h("div", { class: "set-row lt-row", "data-row": row.id, "data-state": row.state }, ...kids, b);
  }
  const b = h("button", { type: "button", class: "set-row is-open lt-open", "aria-label": `${row.name}: ${word}. Open its details` }, ...kids, ic("more", "sr-more"));
  b.addEventListener("click", () => onOpen(row, b));
  return h("div", { class: "lt-row lt-on", "data-row": row.id, "data-state": row.state }, b, see);
}

/* A group: its title, its one-line why, its rows. */
function groupCard(g, rows, opts) {
  return h("section", { class: "ui-card set-rows lt-group", id: `lt-${g.id}`, "data-group": g.id },
    h("div", { class: "ui-card-h" }, h("h2", null, g.title)), h("p", { class: "ui-meta" }, g.why),
    h("div", { class: "set-list" }, rows.map((r) => ltRow(r, { ...opts, group: g }))));
}

/* The top: Next step for <site>. next: connect-plan.js nextStep, or null (nothing left). */
export function nextCard(site, next, found, { onNext, onAgent, agent = true, fixes = 0 } = {}) {
  const chips = foundChips(found, site);
  const done = !next;
  // 2.44: never "All connected" over a red line (the owner: a page must not contradict itself).
  const words = fixes ? `Everything that fits ${site} is connected, but ${fixes === 1 ? "one thing needs" : `${fixes} things need`} a fix: see below.`
    : `Everything that fits ${site} is connected. More you can connect is below.`;
  const btn = done ? null : uiPrimary(next.button, () => onNext(next), { icon: icon(next.button === "Fix it" ? "fix" : "plug") });
  if (btn) btn.classList.add("lt-next-go");
  const ag = !done && agent ? h("button", { type: "button", class: "btn lt-agent" }, h("span", { html: icon("bot") }), "Connect everything left with your AI agent") : null;
  if (ag) ag.addEventListener("click", onAgent);
  return h("section", { class: `ui-card lt-next${done && !fixes ? " good" : ""}`, "aria-label": `Next step for ${site}` },
    h("div", { class: "ui-card-h" }, h("h2", null, `Next step for ${site}`), done ? (fixes ? pill("warn", fixes === 1 ? "1 to fix" : `${fixes} to fix`) : pill("good", "All connected")) : null,
      help("Next step", { text: "Skald picks the one source that helps most on this site, from what it found when the site was added and what is still missing. Connect asks who will do it: you, your developer or your AI agent.", guide: "leads-and-conversions" })),
    chips,
    h("p", { class: "lt-next-w" }, done ? words : next.words),
    btn || ag ? h("div", { class: "acts lt-next-acts" }, btn, ag) : null);
}

export function leadsPage(m, s = S.read()) {
  if (!DEMO.on && !sessions()) return h("div", { class: "state" }, h("div", null, "Tools are connected here with accounts. On this server, use skald hooks secret, skald doctor and docs/INTEGRATIONS.md."));
  if (!DEMO.on && isViewer()) return h("div", { class: "state" }, h("div", null, `${VIEWER} Tools are for admins.`));
  const slot = h("div", { class: "set-leads" }, h("p", { class: "empty" }, "Loading your tools..."));
  let titled = null;                       // "Connect a tool", by the title, when nothing is next
  const say = (got) => { if (typeof got === "string") slot.prepend(h("p", { class: "msg err" }, got)); };
  const open = (id) => async () => say(await openTool(id, m));
  const opts = {
    onOpen: async (row) => {
      if (row.open.tool) return say(await openTool(row.open.tool, m));
      return go(row.open);
    },
    onConnect: (row) => go(row.act),
  };

  function draw(r, items, yours) {
    if (!r.ok) { slot.replaceChildren(h("p", { class: "empty" }, "The tools could not be loaded.")); return; }
    const search = (items || []).find((i) => i.id === "search");
    const searchOn = search?.state === "done" || !!(m.x?.search?.engines?.google?.connected || m.x?.search?.engines?.bing?.connected);
    const rows = rowsOf({ integ: r, yours, searchOn, searchSays: search?.state === "done" ? search.says : "" });
    const found = r.found || null;
    const next = DEMO.on ? null : nextStep(rows, found);
    // The red lines: a check that needs you. A row's own check (a hook's, the script tag's,
    // recorded journeys') is its row's pill instead.
    const own = new Set((r.tools || []).map((t) => `Hook ${t.name}`));
    const broken = (r.status || []).filter((c) => c.state === "NEEDS ATTENTION" && !own.has(c.part) && !["script", "journeys"].includes(c.id)).map((x) => {
      const fix = x.fix ? (btn) => { btn.parentNode.insertBefore(h("span", { class: "set-fixtext" }, ...codeSpans(x.fix)), btn); btn.remove(); } : null;
      return strip("Needs a fix", h("span", null, h("b", null, x.part), ` · ${x.says}`), fix);
    });
    const shown = rows.filter((row) => fits(row, found));
    const more = rows.filter((row) => !fits(row, found));
    const groups = GROUPS.map((g) => [g, shown.filter((row) => row.group === g.id)]).filter(([, list]) => list.length).map(([g, list]) => groupCard(g, list, opts));
    const moreBox = more.length ? fold(`More you can connect (${more.length})`, () => GROUPS.map((g) => {
      const list = more.filter((row) => row.group === g.id);
      return list.length ? h("div", { class: "lt-more-g", "data-group": g.id }, h("h3", null, g.title), h("div", { class: "set-list" }, list.map((row) => ltRow(row, { ...opts, group: g })))) : null;
    }), { cls: "lt-more", open: !!s.lt && more.some((row) => row.group === s.lt) && !shown.some((row) => row.group === s.lt) }) : null;
    const pick = (r.sites || []).length > 1 ? h("select", { "aria-label": "Site" }, r.sites.map((x) => h("option", { value: x, selected: x === r.site }, x))) : null;
    if (pick) pick.addEventListener("change", () => { setIntegSite(pick.value); forgetSources(); load(); });
    const checks = (r.status || []).length;
    const site = r.site || m.site;
    // The page's one primary: the next step's Connect, in its card; nothing next, Connect a tool by the title.
    if (next || DEMO.on) { titled?.remove(); titled = null; } else if (!titled) titled = connect(m);
    slot.replaceChildren(...[
      pick ? field("Site", pick, r.install_admin ? "As an install admin you may set up any site." : "") : null,
      r.locked ? h("p", { class: "msg err" }, r.locked) : null,
      r.takes_hooks === false ? strip("Off", "This install does not report on this site yet, so its hooks are not answered.", null, { kind: "warn" }) : null,
      titled && !titled.isConnected ? titled : null,
      DEMO.on ? null : nextCard(site, next, found, { onNext: (x) => (x.row ? opts.onOpen(x.row) : go(x.act)), onAgent: () => go({ setup: "finish-tools", by: "agent" }), fixes: broken.length }),
      ...broken, ...groups, moreBox,
      checks ? h("p", { class: "set-foot" }, quietButton(`Every check (${checks})`, open("checks"))) : null].filter(Boolean));
    // lt=<group>: scrolled to and marked (a data page's Sources link).
    const hit = s.lt && slot.querySelector(`[data-group="${s.lt}"]`);
    if (hit) {
      hit.classList.add("lt-hl");
      if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => hit.scrollIntoView?.({ block: "start", behavior: "smooth" }));
    }
  }

  function load() {
    const items = keptItems(m);
    Promise.all([call(integPath()), items ? Promise.resolve(items) : checkItems(m), call(TOOLS_PATH)]).then(([r, it, yours]) => draw(r, it, yours));
  }
  load();
  return slot;
}
