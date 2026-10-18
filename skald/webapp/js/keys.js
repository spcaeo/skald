// Keyboard: "/" to search, "g" then a letter to switch tabs, "?" for the
// list, Ctrl or Cmd + K for the command palette. And the "What's new" note.
// Keys are ignored while typing in a field, so they never eat a letter.

import { h } from "./ui.js";
import * as S from "./state.js";
import { store, savedViews } from "./extras.js";
import { toolName } from "./build.js";
import GUIDES from "./help-index.js";
import { openDrawer } from "./drawer.js";
import { find, score, targetOf, personLike } from "./finder.js";

// The letters stay what they were before the five sections (2.7.0), each on the tab that
// holds its old page now; "," opens Settings.
export const GO = {
  o: "overview/summary", i: "overview/insights", l: "live", c: "compare",  // routes.js: the global Live and Compare modes
  v: "traffic/visitors", s: "traffic/sources", p: "traffic/pages", d: "traffic/places", t: "traffic/time",
  e: "sales/pipeline", x: "sales/bookings", f: "sales/funnels", n: "sales/events",
  b: "ai/assistants",
  h: "site/health", a: "site/alerts", r: "site/requests", k: "site/notfound", w: "site/speed", q: "site/quality",
  u: "settings/internal", ",": "settings",
};
const tabName = (k) => S.nameOf(k);
const keyOf = (tab) => Object.keys(GO).find((x) => GO[x] === tab);

// What this release added, shown once in the rail until opened. Newest first;
// a third value names the Help guide (docs/help) the line links to.
const NEW = {
  id: "2026-10-18-2.13.0",
  items: [
    ["Overview, today", "today's Summary in Live mode: visitors now, arrivals minute by minute, and each tile against yesterday at this hour.", "real-time"],
    ["Visitors", "a new Traffic > Visitors: the flow, each visit with its city and where the visitor first came from, and real new and returning figures.", "getting-started"],
    ["Visitors cards", "New and returning, and How engaged, follow your filters when every kept visit checks out against the day's own figures; otherwise they say they cover all visits.", "getting-started"],
    ["Filters", "build rules with AND, OR and groups on any field a visit carries; save them as views, rename them or copy a link.", "getting-started"],
    ["Every table", "sort any column, filter columns, choose columns, and export just what you see.", "getting-started"],
    ["Search", "Google Search Console's and Bing's own queries, pages, clicks, impressions and position, under Traffic > Search; they sync every 6 hours.", "search"],
    ["Connect search", "connect Search Console and Bing from Settings > Integrations, no shell; a cross-check puts Google's clicks beside Skald's own visits."],
    ["Client reports", "branded reports for your clients, a mail with a PDF, weekly or monthly, from verified days only. Settings > Reports.", "client-reports"],
    ["Retention", "of the visitors first seen in a week, how many came back in each week after. Traffic > Retention.", "retention"],
    ["Crawl health", "which of your sitemap's pages Google, Bing and each AI crawler fetch, which they never do, and their errors. AI & bots > Crawl health.", "crawl-health"],
    ["First touch", "where a returning visitor first came from, under each Direct visit and on Sources; one visitor drawer with an animated journey.", "where-visitors-come-from"],
    ["Cities", "each visit's city from a free city file, a Cities table on Places & devices, and city dots on the live map.", "getting-started"],
    ["Search the dashboard", "the magnifier (Ctrl K) finds pages, countries, sources, assistants and crawlers in the period, and opens them.", "getting-started"],
    ["Whole rows", "every row opens its detail, not only its name; Insights shows the five biggest first."],
    ["Countries", "shown as a flag and a three-letter code everywhere; the full name on hover and in the CSV."],
    ["Honest counts", "places that show the same figure agree; something never set up says so instead of 0; a tab with its own period says which."],
    ["Too fast to be a person", "a visit that opens 6 or more pages within 2 seconds counts as a bot; a visit says \"3 pages (2 seen in the browser)\"."],
    ["Set up this site", "a checklist for owners and admins on a new site's Overview; Settings > Mail can preview the daily and weekly mail."],
    ["Alerts", "switch alerts, their mail and each rule on or off on Site > Alerts."],
    ["Fixes", "one Leads figure in the mails, reports and Overview; drill panels follow the period; phone tables stay in the page; and more in the changelog."],
  ],
  // The earlier releases' notes, folded under the new ones.
  earlier: [
    // 2.11.0-2.12.0
    ["Visitor flow", "see how visits moved, from where they came to each page and out; on Visitors, every drill-down and Funnels.", "visitor-flow"],
    ["Internal traffic", "pause, edit or delete an address on your own-traffic list; nothing is lost, past days keep their figures."],
    ["Real time", "who is on your site now: active visitors, minute by minute, a world map, the pages being read and the AI and crawlers now. Overview > Real time.", "real-time"],
    ["Alerts in Slack", "any alert can go to Slack or another tool: add a webhook for alert.opened in Settings > Integrations.", "webhooks"],
    ["AI alerts", "the first visit from an AI answer, a page's first, visits from AI answers against the usual for that weekday, and a crawler gone silent.", "faq"],
    ["Clearer words", "a visit with no referrer and no campaign tag reads \"Direct\"; a value the log did not have reads \"Not recorded\"."],
    // 2.10.0-2.10.1
    ["Today, live", "the dashboard now opens on Today with live figures on every page; pick another period any time."],
    ["Forms", "a visit is no longer marked \"form sent\" because the script tag reported an event."],
    ["Bots", "about 60 more crawlers, AI agents and monitors recognised; phone browsers that look like bots stay people."],
    ["Returning readers", "a returning visitor whose browser has your site's files cached now counts as a reader when your pages have the script tag."],
    ["Crawler cost", "what each crawler costs your server: requests, data sent, response time, errors and re-crawls. Open one for its detail by day.", "ai-and-bots"],
    ["Client sites", "page assets and the visitor IDs switch per site in Settings > Sites; settings and site commands from the shell."],
    ["Google AI Mode", "a visit from Google's AI Mode reads \"google.com (AI Mode)\" under Search engine.", "faq"],
    ["What they fetch", "AI fetches by what they ask for: pages, llms.txt, Markdown, robots.txt, sitemaps.", "faq"],
    ["What the AI read", "the pages an assistant fetched just before it sent a visitor, in the visit and per assistant.", "faq"],
    // 2.9.0
    ["Script tag", "every site of your Skald can use the script tag now, not only the first. Each site's events go to that site."],
    ["Visitor IDs", "can be on for one site and off for another."],
    ["Google Ads on iPhone", "a lead from a Google Ads click on iOS (gbraid, wbraid) counts as paid search."],
    // 2.8.0-2.8.1
    ["Pages", "calls to a site's own API (/api/...) are no longer counted as pages or as steps between pages."],
    ["Countries", "a log with no country of its own (Caddy, a plain log) gets one from a GeoIP file your server admin sets. DB-IP's free file works.", "faq"],
    ["Caddy", "sites with a Caddy log no longer fail the daily check, so their days are stored."],
    ["More readers", "sites added from the dashboard no longer wait for the first site's files, so returning readers count as people again."],
    ["Cached pages", "a page shown from the browser's cache counts as a page view and keeps the visit's source."],
    ["Sources", "ChatGPT, Claude and other assistant phone apps count as AI; YouTube, WhatsApp and Telegram apps are social; utm_source decides before utm_medium; more ad click ids."],
    ["Our own traffic", "Skald's own robots.txt check is no longer counted as a bot."],
    // 2.7.0-2.7.1
    ["GitHub", "Skald's home on GitHub is linked from About, the footer and the account menu: star it, see releases, report a problem."],
    ["Five sections", "Overview, Traffic, Leads & sales, AI & bots and Site, with tabs inside. Old links still work.", "getting-started"],
    ["Live and Compare", "two switches in the top bar that work on every page.", "getting-started"],
    ["One place each", "landing pages, sources and countries each live in one place now.", "getting-started"],
    ["Leads & sales", "one row of options: count from, source, action, stage, show left out.", "leads-and-conversions"],
    ["Grids", "search, filter and sort long lists; the view is kept in the address to share.", "getting-started"],
    // 2.6.0-2.6.1
    ["Site logos", "each site shows its own logo in the menu, the switcher and the browser tab.", "settings-and-retention"],
    ["Choose a site", "after sign-in, a card per site with today's visitors, leads and demos booked."],
    ["Logo settings", "Settings > Sites > Logo: from the site, upload your own, or a letter on a colour.", "settings-and-retention"],
    // 2.5.0-2.5.2
    ["Spam caught sooner", "a lead your team marks spam leaves the figures within two minutes, not at the next daily run.", "leads-and-conversions"],
    ["Fixes", "lead tiles show 0, not a dash, when every lead was spam or test; Live no longer shows a date range; the top bar never overlaps."],
    ["Leads everywhere", "leads and demos booked on Overview, Sources, Pages, Locations, Insights and Compare, each counted twice.", "leads-and-conversions"],
    ["Live", "today's leads and bookings as they arrive, with source, page and country.", "leads-and-conversions"],
    ["Doctor", "names the step a daily run stopped at, and why."],
    // 2.4.0-2.4.1
    ["Find a person", "on narrower screens the search is an icon in the top bar, so nothing overlaps.", "privacy"],
    ["Person search", "find anyone by IP, email or lead (admins): every visit, page, lead and booking, across days.", "privacy"],
    ["Nothing hidden", "spam, duplicate and test leads, and cancelled, removed and test conversions, are listed with their rows.", "leads-and-conversions"],
    ["Doctor", "skald doctor and Settings > Integrations say what works, what is missing, and the exact fix.", "pick-your-road"],
    ["Calendly", "keep only your own event types when one Calendly account books for several businesses.", "demo-bookings"],
    ["Guides", "pick your road, leads from your backend in 5 minutes, demo bookings, Docker first install.", "pick-your-road"],
    // 2.3.0
    ["Flags", "a flag beside every country, everywhere in the dashboard, the plain page and the mails."],
    ["Visits", "coming back from ChatGPT, Perplexity, a search or a campaign link starts a new visit, so the assistant or campaign that brought someone back is shown as its source.", "getting-started"],
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
    ["Tag problems", "campaign links with a missing or unrecognised tag, on Sources."],
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
    ["Time zone", "times show in the site's zone by default; choose your own zone or UTC instead. Days are still counted midnight to midnight in the site's zone."],
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
        const rows = Object.entries(GO).filter(([, tab]) => keys.includes(tab) && (tab === "settings" || S.shown(tab)));
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

/* The command palette, and the search behind the top bar's magnifier. actions:
   [{label, hint, run}] from main.js (theme, refresh...); the tabs, ranges and saved
   views are added here. finds(): what it searches in the figures (main.js, finder.js):
   {entries, earlier, period, person(q) or null}. A typed word finds the commands
   first, then the pages, countries, sources, referring sites, campaigns, assistants
   and crawlers seen in the period (each opens its tab with its detail), then, for an
   admin, a person by IP address, email or lead. */
export function palette(actions = [], finds = null) {
  const cmds = [
    // Every section, then every page this reader may open, in the menu's order, with its section or group beside it.
    ...S.SECTIONS.map((x) => ({ label: `Go to ${x.name}`, group: "Section", hint: "", run: () => S.set({ tab: x.key }) })),
    ...S.TABS.filter(([k]) => S.shown(k)).map(([k, name]) => ({ label: `Go to ${name}`, group: S.inSettings(k) ? `Settings, ${S.groupOf(k)}` : S.groupOf(k), hint: keyOf(k) ? `g ${keyOf(k)}` : "", run: () => S.set({ tab: k }) })),
    ...S.RANGES.filter(([k]) => k !== "custom").map(([k, name]) => ({ label: `Range: ${name}`, hint: "", run: () => S.set({ range: k }) })),
    // Every Help guide by its name: "Help: Webhooks".
    ...GUIDES.map((g) => ({ label: `Help: ${g.title}`, group: "Help", hint: "", run: () => S.set({ tab: "help", part: g.id }) })),
    ...savedViews().map((v) => ({ label: `Saved view: ${v.name}`, hint: "", run: () => { location.hash = v.hash; } })),
    ...actions,
  ];
  const data = finds ? finds() : null;
  const input = h("input", { type: "text", class: "pal-in", placeholder: data ? "Search pages, sources, countries… or a tab or an action" : "Type a tab, a range, a saved view or an action",
    "aria-label": "Search or command", role: "combobox", "aria-expanded": "true", "aria-controls": "pal-list", autocomplete: "off", spellcheck: "false" });
  const list = h("ul", { class: "pal-list", id: "pal-list", role: "listbox", "aria-label": "Results" });
  // A found name: its words, its kind and period beside them; it opens its tab with its detail.
  // Two steps in the history, the tab then its detail (one drill step): closing the
  // drawer leaves the tab open, and Back then returns to where the search began.
  const open = (e) => { const t = targetOf(e); S.set({ tab: t.tab }); S.set({ dd: t.dd }, { mark: { drill: 1 } }); };
  // A country or a city is said in full already ("🇨🇦 CAN · Canada"): its stored code is not repeated.
  const named = (e, when) => ({ label: e.words, value: e.words !== e.value && e.dim !== "country" && e.dim !== "city" ? e.value : "", group: `${e.group} · ${when}`, hint: "", found: true, path: e.dim === "path", run: () => open(e) });
  let shown = cmds, at = 0;
  const draw = () => {
    const q = input.value.trim().toLowerCase();
    if (!q) shown = cmds;
    else {
      const ranked = cmds.map((c) => [score(`${c.label} ${c.group || ""}`, q), c]).filter(([r]) => r != null);
      // Commands keep their menu order, the closest first; at most 8, so the figures show too.
      shown = ranked.sort((a, b) => a[0] - b[0]).slice(0, 8).map(([, c]) => c);
      if (data) {
        let got = find(data.entries, q, 30).map((e) => named(e, data.period));
        // Nothing in the period: the days kept before it, said so.
        if (!got.length && data.earlier) got = find(data.earlier(), q, 15).map((e) => named(e, "earlier days, not this period"));
        const person = personLike(q) && data.person ? [{ label: `Find a person: ${input.value.trim()}`, group: "People · every visit kept", hint: "", run: () => data.person(input.value.trim()) }] : [];
        shown = [...person, ...shown, ...got];
      }
    }
    at = Math.min(at, Math.max(0, shown.length - 1));
    list.replaceChildren(...shown.map((c, i) => h("li", { role: "option", id: `pal-${i}`, class: c.found ? `pal-found${c.path ? " pal-path" : ""}` : null, "aria-selected": String(i === at), onclick: () => go(i) },
      h("span", null, c.label, c.value ? h("small", { class: "pal-v" }, c.value) : null, c.group ? h("small", { class: "pal-g" }, c.group) : null), c.hint ? h("kbd", null, c.hint) : null)));
    if (!shown.length) list.append(h("li", { class: "empty" }, data ? `Nothing matches. Pages, sources, countries, campaigns, assistants and crawlers are searched in ${data.period}.` : "Nothing matches."));
    input.setAttribute("aria-activedescendant", shown.length ? `pal-${at}` : "");
    list.children[at]?.scrollIntoView({ block: "nearest" });
  };
  const dlg = modal(data ? "Search, go to, or do" : "Go to, or do", h("div", null, input, list));
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

export function keys(actions, finds = null) {
  let pending = 0;
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      palette(actions(), finds);
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
      if (field) { field.focus(); field.select?.(); } else palette(actions(), finds);
    }
  });
}
