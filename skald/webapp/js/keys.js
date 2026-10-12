// Keyboard: "/" to search, "g" then a letter to switch tabs, "?" for the
// list, Ctrl or Cmd + K for the command palette. And the "What's new" note.
// Keys are ignored while typing in a field, so they never eat a letter.

import { h } from "./ui.js";
import * as S from "./state.js";
import { store, savedViews } from "./extras.js";
import { toolName } from "./build.js";
import GUIDES from "./help-index.js";
import { openDrawer } from "./drawer.js";

// The letters stay what they were when the menu was regrouped; "," opens Settings.
export const GO = {
  o: "overview", l: "live", i: "insights", c: "compare",
  v: "visitors", s: "sources", p: "pages", d: "locations", t: "time",
  e: "leads", x: "conversions", f: "funnels", n: "events",
  b: "bots",
  h: "health", a: "health/alerts", q: "health/quality", w: "health/speed", k: "health/broken", r: "requests",
  u: "settings/internal", ",": "settings",
};
const tabName = (k) => (k === "settings" ? "Settings" : (S.TABS.find(([x]) => x === k) || [null, k])[1]);
const keyOf = (tab) => Object.keys(GO).find((x) => GO[x] === tab);

// What this release added, shown once in the rail until opened. Newest first;
// a third value names the Help guide (docs/help) the line links to.
const NEW = {
  id: "2026-10-12f",
  items: [
    ["Flags", "a flag beside every country, everywhere in the dashboard, the plain page and the mails."],
    ["Visits", "coming back from ChatGPT, Perplexity, a search or a campaign link starts a new visit, so the assistant or campaign that brought someone back is shown as its source.", "getting-started"],
  ],
  // The earlier releases' notes, folded under the new ones.
  earlier: [
    // 2.2.1-2.2.3
    ["Abandoned", "a demo or form started and finished later by the same person, from another session or device, now counts as finished, not abandoned.", "leads-and-conversions"],
    ["Privacy", "with visitor IDs off, no visitor ID is kept from any source: the script tag, a webhook, or your lead database.", "privacy"],
    ["Webhooks", "Calendly, Stripe, HubSpot and the lead hook reach Skald on every install, with or without the tracking script. Before, they could fail until the script was switched on.", "webhooks"],
    ["Dashboard", "every install opens the full dashboard (menu, tabs, drawers), not the plain page.", "getting-started"],
    // 2.2.0
    ["New releases", "owners and admins see a line when a newer Skald is out, red for a security release; your server admin upgrades with one command, with a backup and a rollback.", "faq"],
    ["llms.txt", "Settings > AI crawlers suggests an llms.txt from the pages people and AI assistants read most. Copy or download it; Skald never writes to your site.", "settings-and-retention"],
    ["AI alerts", "an alert when an assistant starts or stops reading a page, or visits likely sent by AI jump or vanish. The AI filter on Alerts and AI reading changes on AI & crawlers.", "faq"],
    ["Cloudflare", "the Skald Worker now deploys with one button.", "faq"],
    ["Live demo", "the whole dashboard with sample data, no sign-up, at spcaeo.github.io/skald.", "getting-started"],
    ["Faster", "the live run and the dashboards take a third less time, a page's story less than half. No figure changed."],
    // 2.1.0
    ["Likely from AI", "a direct visit that lands on a page ChatGPT, Perplexity or another assistant fetched minutes before is shown as likely sent by it: on Sources, AI & crawlers, Leads, Conversions and a visitor's details. An estimate, marked \"likely\" with an (i), never added to any count.", "leads-and-conversions"],
    ["Cloudflare Worker", "a site behind Cloudflare on any plan can send each request to Skald, so pages served from Cloudflare's cache are counted too, and none twice.", "faq"],
    ["Vercel", "a step-by-step guide for a site on Vercel: where Skald runs, the log drain, and what each Vercel plan lets Skald see.", "getting-started"],
    // 2.0.0
    ["Help", "guides in plain words for every part, step by step: getting started, sign-in and team, internal traffic, leads and conversions, the tracking script, webhooks, funnels and goals, the API, MCP, settings, privacy, and questions. In Settings > Help, the round You button, the footer, Ctrl K (Help: …) and the ? list. Pages with a setup step link to their guide.", "getting-started"],
    ["Sign-in", "Show or hide a password as you type it, and Keep me signed in on a computer you trust.", "sign-in-and-team"],
    ["Footer", "Live · version · released, in your time zone and the site's; how fresh the figures are beside it. Theme and What's new sit in the sidebar's foot."],
    ["Menu", "grouped by what you came for: Home, Audience, Results, AI & bots, Site & server. Settings has its own menu (the gear): You, Team & access, This site, Organisation, Help. Old links still open the right page."],
    ["Settings", "your account, team, sites, internal traffic, AI crawlers, data retention, mail, integrations, security and the audit log, changed here instead of on the server.", "settings-and-retention"],
    ["Internal traffic", "Add my current address, or an address or range with a label, so your team's visits are not counted as visitors.", "internal-traffic"],
    ["Conversions", "bookings, forms and payments: started, completed and abandoned, where they came from, first, last and assisted touch, and time to convert.", "leads-and-conversions"],
    ["Webhooks", "Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier or Make, and your own site send signed events; a test button; webhooks out to your CRM or Slack.", "webhooks"],
    ["Tracking script", "skald.js: one line in your pages for clicks, form steps and bookings; consent mode, other domains, and the visitor ID on Calendly links.", "tracking-script"],
    ["API & tokens", "tokens with scopes, made and revoked in Settings; the MCP address to copy.", "api"],
    ["MCP", "ask Claude, ChatGPT or another assistant about your traffic in plain words. Read-only.", "mcp"],
    ["Yesterday", "a period of its own in the top bar."],
    ["Funnel history", "a saved funnel is counted every day, by source and device, with drop-off and time to go through.", "funnels-and-goals"],
    ["Goals", "chosen events per 100 visits, by source, on Events.", "funnels-and-goals"],
    ["Engagement", "pages per visit, one-page visits and visit length by source and device, and returning visitors by source, on Visitors."],
    ["Tag problems", "campaign links with a missing or unknown tag, on Sources."],
    ["Exit rate", "how many of a page's visits left from it, on each page in Pages."],
    ["Leads", "lead quality by source, and time from first visit to lead.", "leads-and-conversions"],
    ["Failure mail", "a failed morning run sends one short mail."],
    // before 2.0.0
    ["Events", "under Results: what readers did inside the pages, from the site's own beacon: button clicks, sign-up and demo steps, links out, reading three quarters, copying text, by page and by source. Funnels can end with event steps, and each page's story shows its events."],
    ["Broken links", "now under Site health, beside Alerts, Data quality and Page speed. Old links still open it."],
    ["Compare", "after Insights: any two periods side by side, A against B, with presets or a calendar, up to 12 months. The figures with their change, both periods on one chart, and tables of pages, sources, AI assistants, countries, devices, browsers, systems and campaigns with what is new or gone. The link keeps it all."],
    ["Page story", "select any page in Pages: when it was published, the first crawl, the first AI fetch, the first person and the first lead, every day since, and where its readers came from. Compare this page puts its last week against its first."],
    ["Published between", "Pages lists the pages published in any dates, this month or last, with their first crawl and first visitor."],
    ["Funnels", "under Results: choose pages in order, and from which source; see how many visits went through, where the rest left, and open each step's visits. Save a funnel to come back to it."],
    ["Leads by touch", "every source, assistant, campaign and landing page shows its first touch and its last touch side by side."],
    ["robots.txt", "AI & crawlers shows, for each crawler, whether the site's robots.txt lets it in and how often it fetched a page the rules keep it from, and the rules as written."],
    ["Page speed", "under Site health: the top pages' Core Web Vitals and Google's score, phone and desktop, the 30-day trend, and the server's own answer time."],
    ["Sites", "the switcher under the name lists every site this server reads."],
    ["API and users", "in Settings: every figure as JSON for a script, and who may look and who may change things."],
    ["About Skald", "why we built it, why the name, how it compares with the usual tools, and what each tab does: from the logo, the sidebar or the footer."],
    ["Navigation", "sections in groups; press [ or the button at the foot of the sidebar to shrink it to icons; on a phone, the sections open from the menu button and the bottom bar."],
    ["Skald", "the tool has its name and mark: Skald, every visit, truly told. The version and release are at the foot of every page."],
    ["Time zone", "the top bar shows times in your own zone, the site's or UTC. Days are still counted midnight to midnight in the site's zone."],
    ["Live", "people first, the machines in their own units, the latest visits and AI activity side by side, and today's top lists."],
    ["One period", "every tab's figures follow the date range; a part kept for a fixed period of its own is folded at the bottom and says so."],
    ["Drill-down", "select any country, page, source, assistant, campaign, referrer, device, browser, system, hour, address or bot to see its trend, the visits and the requests behind it; keep selecting to narrow. Back and the trail at the top step out again, and the address bar keeps every step."],
    ["Export and reports", "Export in the top bar: every table on the tab as a ZIP of CSV files, the tab as JSON, a printable report, and a report builder for several tabs at once. Choose Save as PDF in the print dialog to keep a PDF."],
    ["Icons", "small marks beside assistants, crawlers, search engines, social networks, browsers, systems, devices, sources and kinds of page, and referring sites' own icons where the server has them."],
    ["Requests", "the last few hours of the request log, every line: who, what, and the rule that decided its group, with quick toggles, search and a detail panel."],
    ["Leads", "leads per day by kind, where they first came from, and a funnel from visitors to demos booked."],
    ["Alerts", "a bell in the top bar and a tab listing open and closed alerts, and which alerts are on."],
    ["Data quality", "per day: lines read, unreadable and duplicate lines, silent stretches, the audit, and when each job last ran."],
    ["Markers", "website releases, deploys, counting changes and internal-address changes on every day chart."],
    ["Compare", "the previous period beside each headline figure and as a dashed line on the charts, when both periods are whole."],
    ["Bots", "verified, not verifiable and spoofed crawlers, browsers with warning signs, and link previews from chats."],
    ["Saved views and shortcuts", "save the filters on screen under a name; press ? for the keyboard shortcuts."],
  ],
};

function modal(title, body, { wide = false } = {}) {
  document.querySelectorAll("dialog.modal").forEach((d) => d.remove());
  const dlg = h("dialog", { class: `modal${wide ? " wide" : ""}`, "aria-labelledby": "modal-title" });
  const close = h("button", { type: "button", class: "btn", onclick: () => dlg.close() }, "Close");
  dlg.append(h("div", { class: "modal-head" }, h("h2", { id: "modal-title" }, title), close), h("div", { class: "modal-body" }, body));
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}

// Shortcuts and What's new open in the drawer (drawer.js); the palette stays a small centred box.
let sheet = null;
const drawer = (title, subtitle, body, className) => { sheet = openDrawer({ title, subtitle, body, size: "md", className, key: "keys" }); };
const closeModal = () => { document.querySelectorAll("dialog.modal").forEach((d) => d.close()); sheet?.close({ focusBack: false }); };

export function help() {
  const row = (keys, what) => h("tr", null, h("td", null, keys.map((k) => h("kbd", null, k))), h("td", null, what));
  const sec = (title, ...kids) => h("section", { class: "dw-sec" }, h("h3", null, title), ...kids);
  drawer(`${toolName()} keyboard shortcuts`, "Keys work anywhere except while you type in a field.", [h("div", { class: "dw-cols" },
    sec("Anywhere", h("table", { class: "keys" }, h("tbody", null,
      row(["/"], "Search: the list on this tab"),
      row(["Ctrl", "K"], "Command palette: go anywhere, run anything (Cmd K on a Mac)"),
      row(["?"], "This list"),
      row(["["], "Sidebar: shrink to icons, or open it again"),
      row(["Esc"], "Close a panel or a menu"),
      row(["Enter"], "On a value, a bar or an hour: open its detail"),
      row(["↑", "↓"], "Next or previous section, when the menu has focus")))),
    sec("Go to a section: press g, then",
      // In the menu's groups, so the letters read like the sidebar.
      h("div", { class: "keys-groups" }, [...S.MENU, ["Settings", ["settings", "settings/internal"]]].map(([group, keys]) => {
        const rows = Object.entries(GO).filter(([, tab]) => keys.includes(tab.split("/")[0] === "health" ? "health" : tab) && (tab === "settings" || S.shown(tab)));
        return rows.length ? h("div", { class: "keys-g" }, h("h4", null, group), h("table", { class: "keys" }, h("tbody", null, rows.map(([k, tab]) => row(["g", k], tabName(tab)))))) : null;
      })))),
    // The guides, one click away: the drawer closes as a link is followed.
    sec("Help guides",
      h("ul", { class: "keys-help" }, h("li", null, h("a", { href: "#help", onclick: closeModal }, "All guides")),
        GUIDES.map((g) => h("li", null, h("a", { href: `#help?part=${g.id}`, onclick: closeModal }, g.title)))))], "dw-keys");
}

export function whatsNew(dot) {
  store.set("ti-seen-new", NEW.id);
  if (dot) dot.hidden = true;
  drawer(`What's new in ${toolName()}`, "A tab whose data is not written yet says so and why; nothing is shown as zero.", [
    h("ul", { class: "dw-news" }, NEW.items.map(([name, what, guide]) => h("li", null, h("b", null, name), " ", what,
      guide ? [" ", h("a", { href: `#help?part=${guide}`, onclick: closeModal }, "Read the guide")] : null))),
    h("details", { class: "news-old" }, h("summary", null, "Earlier changes"),
      h("ul", { class: "dw-news" }, NEW.earlier.map(([name, what]) => h("li", null, h("b", null, name), " ", what))))], "dw-new");
}
export const newUnseen = () => store.get("ti-seen-new", "") !== NEW.id;

/* The command palette. actions: [{label, hint, run}] from main.js (theme,
   refresh...); the tabs, ranges and saved views are added here. */
export function palette(actions = []) {
  const cmds = [
    // Every page this reader may open, in the menu's order, with its group beside it.
    ...S.TABS.filter(([k]) => S.shown(k)).map(([k, name]) => ({ label: `Go to ${name}`, group: S.inSettings(k) ? `Settings, ${S.groupOf(k)}` : S.groupOf(k), hint: keyOf(k) ? `g ${keyOf(k)}` : "", run: () => S.set({ tab: k }) })),
    ...S.RANGES.filter(([k]) => k !== "custom").map(([k, name]) => ({ label: `Range: ${name}`, hint: "", run: () => S.set({ range: k }) })),
    // Every Help guide by its name: "Help: Webhooks".
    ...GUIDES.map((g) => ({ label: `Help: ${g.title}`, group: "Help", hint: "", run: () => S.set({ tab: "help", part: g.id }) })),
    ...savedViews().map((v) => ({ label: `Saved view: ${v.name}`, hint: "", run: () => { location.hash = v.hash; } })),
    ...actions,
  ];
  const input = h("input", { type: "text", class: "pal-in", placeholder: "Type a tab, a range, a saved view or an action", "aria-label": "Command",
    role: "combobox", "aria-expanded": "true", "aria-controls": "pal-list", autocomplete: "off", spellcheck: "false" });
  const list = h("ul", { class: "pal-list", id: "pal-list", role: "listbox", "aria-label": "Commands" });
  let shown = cmds, at = 0;
  const draw = () => {
    const q = input.value.trim().toLowerCase();
    shown = q ? cmds.filter((c) => q.split(/\s+/).every((w) => `${c.label} ${c.group || ""}`.toLowerCase().includes(w))) : cmds;
    at = Math.min(at, Math.max(0, shown.length - 1));
    list.replaceChildren(...shown.map((c, i) => h("li", { role: "option", id: `pal-${i}`, "aria-selected": String(i === at), onclick: () => go(i) },
      h("span", null, c.label, c.group ? h("small", { class: "pal-g" }, c.group) : null), c.hint ? h("kbd", null, c.hint) : null)));
    if (!shown.length) list.append(h("li", { class: "empty" }, "Nothing matches."));
    input.setAttribute("aria-activedescendant", shown.length ? `pal-${at}` : "");
    list.children[at]?.scrollIntoView({ block: "nearest" });
  };
  const dlg = modal("Go to, or do", h("div", null, input, list));
  dlg.classList.add("pal");
  const go = (i) => { const c = shown[i]; if (!c) return; dlg.close(); c.run(); };
  input.addEventListener("input", () => { at = 0; draw(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); at = (at + 1) % Math.max(1, shown.length); draw(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); at = (at - 1 + shown.length) % Math.max(1, shown.length); draw(); }
    else if (e.key === "Enter") { e.preventDefault(); go(at); }
  });
  draw();
  input.focus();
}

const typing = (el) => el && (el.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName));

export function keys(actions) {
  let pending = 0;
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      palette(actions());
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target) || document.querySelector("dialog[open]")) return;
    if (pending && Date.now() - pending < 1500 && GO[e.key.toLowerCase()]) {
      pending = 0;
      e.preventDefault();
      S.set({ tab: GO[e.key.toLowerCase()] });
      return;
    }
    pending = 0;
    if (e.key === "g") { pending = Date.now(); return; }
    if (e.key === "?") { e.preventDefault(); help(); return; }
    if (e.key === "/") {
      const field = document.querySelector('#panel input[type="search"], #panel .rq-search');
      e.preventDefault();
      if (field) { field.focus(); field.select?.(); } else palette(actions());
    }
  });
}
