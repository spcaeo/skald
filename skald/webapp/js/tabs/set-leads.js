// Settings › This site › Leads & tools (v2, the UX audit's mockup v-settings-after): one page,
// no tabs. What is set up, as rows with a status pill; a row opens its details in a drawer
// (tool=<id>: the address, the secret, a test event, the deliveries, Remove). A red line only
// when something is broken, with its Fix. What is not set up: one quiet line. One primary,
// "Connect a tool", asks who will do it, then which tool (the lead hook's set-up dialog).
//
//   tool=<id>        one incoming hook (site, calendly, calcom, stripe, hubspot, typeform, zapier...)
//   tool=webhooks    Send each lead out: the outgoing webhooks and Add one
//   tool=search      Search Console and Bing
//   tool=checks      every check, with the server's own words
// GET <page>/integrations (integrations_api.py) and the set-up lines (checklist.js).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { isViewer, sessions, VIEWER } from "../access.js";
import { DEMO } from "../demo.js";
import { openDrawer } from "../drawer.js";
import { field } from "./forms.js";
import { integrationsPart, integPath, setIntegSite, toolKind, codeSpans } from "./integrations.js";
import { checkItems, keptItems, openFinish, mayManage } from "./checklist.js";
import { primary, strip, statusRow, rowsCard, quietLine, quietButton } from "./set-ui.js";

const FIXED = ["webhooks", "search", "checks"];
const TITLES = { webhooks: "Send each lead out", search: "Search Console & Bing", checks: "Every check" };

/* Connect a tool: Who will do it? for the lead hook, then its dialog asks which tool. */
function connect(m) {
  return primary("Connect a tool", async () => openFinish(m, keptItems(m) || await checkItems(m), { only: "lead" }));
}

/* A drawer with one tool's details, or one of the fixed parts; its key in the address. */
export async function openTool(id, m) {
  const fixed = FIXED.includes(id);
  if (!fixed && !/^[a-z0-9_-]{1,30}$/.test(id)) return "That tool is not one Skald knows.";
  if (DEMO.on) return "In the demo, tools need a running Skald.";
  if (!sessions() || isViewer()) return "Not available to your role.";
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

export function leadsPage(m) {
  if (!DEMO.on && !sessions()) return h("div", { class: "state" }, h("div", null, "Tools are connected here with accounts. On this server, use skald hooks secret, skald doctor and docs/INTEGRATIONS.md."));
  if (!DEMO.on && isViewer()) return h("div", { class: "state" }, h("div", null, `${VIEWER} Tools are for admins.`));
  const slot = h("div", { class: "set-leads" }, h("p", { class: "empty" }, "Loading your tools..."));
  const go = DEMO.on ? null : connect(m);
  const open = (id) => async () => { const got = await openTool(id, m); if (typeof got === "string") slot.prepend(h("p", { class: "msg err" }, got)); };

  function draw(r, items) {
    if (!r.ok) { slot.replaceChildren(h("p", { class: "empty" }, "The tools could not be loaded.")); return; }
    const tools = r.tools || [];
    const on = tools.filter((t) => t.set || t.state !== "needs_secret");
    const off = tools.filter((t) => !on.includes(t));
    // The red lines: a check that needs you, a tool that is not working.
    const broken = [];
    // A tool's own check ("Hook Calendly") is its row's pill: red only when the tool is not working.
    const own = new Set(tools.map((t) => `Hook ${t.name}`));
    for (const x of (r.status || []).filter((c) => c.state === "NEEDS ATTENTION" && !own.has(c.part))) {
      const fix = x.fix ? (btn) => { btn.parentNode.insertBefore(h("span", { class: "set-fixtext" }, ...codeSpans(x.fix)), btn); btn.remove(); } : null;
      broken.push(strip("Broken", h("span", null, h("b", null, x.part), ` · ${x.says}`), fix));
    }
    for (const t of on.filter((x) => toolKind(x)[0] === "bad")) broken.push(strip("Broken", h("span", null, h("b", null, t.name), ` · ${t.words || t.problem || "not working"}`), open(t.tool)));
    const rows = on.map((t) => {
      const [kind, word] = toolKind(t);
      return statusRow({ iconName: t.tool === "site" ? "server" : "plug", title: t.name, line: t.words ? t.words.replace(/^./, (c) => c.toUpperCase()) : "", kind, word, onOpen: open(t.tool) });
    });
    const hooks = r.webhooks || [];
    const search = (items || []).find((i) => i.id === "search");
    const outRow = hooks.length
      ? statusRow({ iconName: "out", title: "Send each lead out", line: `${hooks.length} address${hooks.length === 1 ? "" : "es"}: ${hooks.map((w) => w.url.replace(/^https:\/\//, "").split("/")[0]).join(", ")}`, kind: "good", word: "On", onOpen: open("webhooks") })
      : statusRow({ iconName: "out", title: "Send each lead out", line: "To a CRM, Zapier or Slack", kind: "off", word: "Off", action: quietButton("Set up", open("webhooks")) });
    const searchRow = search && search.state === "done"
      ? statusRow({ iconName: "search", title: "Search Console & Bing", line: search.says || "", kind: "good", word: "Working", onOpen: open("search") })
      : statusRow({ iconName: "search", title: "Search Console & Bing", line: "The searches that bring people here", kind: "off", word: "Not set up",
        action: quietButton("Set up", () => (mayManage() ? openFinish(m, items || [], { only: "search" }) : open("search")())) });
    const pick = (r.sites || []).length > 1 ? h("select", { "aria-label": "Site" }, r.sites.map((x) => h("option", { value: x, selected: x === r.site }, x))) : null;
    if (pick) pick.addEventListener("change", () => { setIntegSite(pick.value); load(); });
    const checks = (r.status || []).length;
    slot.replaceChildren(
      pick ? field("Site", pick, r.install_admin ? "As an install admin you may set up any site." : "") : "",
      r.locked ? h("p", { class: "msg err" }, r.locked) : "",
      r.takes_hooks === false ? strip("Off", "This install does not report on this site yet, so its hooks are not answered.", null, { kind: "warn" }) : "",
      ...broken,
      rows.length ? rowsCard(`Connected (${rows.length})`, rows) : quietLine("Nothing connected yet", "Your forms, bookings and payments tell Skald about each lead."),
      off.length ? quietLine("Not connected", off.map((t) => t.name).join(" · "), go ? quietButton("Connect a tool", () => go.click()) : null) : "",
      h("div", { class: "set-pair" }, outRow, searchRow),
      checks ? h("p", { class: "set-foot" }, quietButton(`Every check (${checks})`, open("checks"))) : "");
  }

  function load() {
    const items = keptItems(m);
    Promise.all([call(integPath()), items ? Promise.resolve(items) : checkItems(m)]).then(([r, it]) => draw(r, it));
  }
  load();
  return [go, slot];
}
