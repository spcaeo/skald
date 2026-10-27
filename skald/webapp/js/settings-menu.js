// Settings' menu (v2, docs/plans/2026-10-26-settings-redesign.md): the menu on the left, the
// page on the right. To do first (what needs you now), then four short groups. Each page shows
// its state and its action; what it is for sits behind the "?" by its title (`about`, with its
// Help guide in the app, #help?part=<help>, and the public page, <home>/docs/<help>/). No DOM
// and no imports, so node and state.js read it.
//
//   route   settings/<group>/<page>
//   name    its name in the menu, the title and the phone's select
//   line    one short sentence under the title
//   about   the "?" note: what it is for, in a sentence or two
//   help    the in-app guide's id; docs: the public page's path when not /docs/<help>/
//   tabs    [[sub, name, help?, about?]]: in-page tabs, the address's sub= (the first when absent)

export const SETTINGS_HOME = "settings/todo";

export const SETTINGS_GROUPS = [
  { key: "site", name: "This site", pages: [
    { route: "settings/site/data", name: "Data", help: "connections",
      line: "How visits reach Skald.",
      about: "Skald counts visits from your server's log. Send the log here, add the script tag for clicks and forms, and choose what counts as a visit.",
      tabs: [["logs", "Send logs", "connections"], ["script", "Script tag & goals", "tracking-script", "The tag adds form steps, clicks and bookings. Goals are the events that count as a win."],
        ["counting", "What counts", "settings-and-retention", "Which visits count as people, and which addresses are pages."],
        ["sample", "Test a sample", "troubleshooting-connections", "Paste a few lines of a log: Skald says what it would count, and keeps nothing."]] },
    { route: "settings/site/leads", name: "Leads & tools", help: "webhooks",
      line: "Your forms, bookings and payments, and where leads go.",
      about: "Calendly, Cal.com, HubSpot, Typeform, Stripe or your own server tell Skald about each lead. Each row opens its address, secret, test event and deliveries. Send each lead out posts it to your CRM, Zapier or Slack; Search Console and Bing add the searches that bring people." },
    { route: "settings/site/details", name: "Site", help: "settings-and-retention",
      line: "Its names, page groups, time zone and logo.",
      about: "The host names Skald counts as this site, page groups (Views), the time zone of its days, its logo, and the machines that are yours.",
      tabs: [["details", "Names & time", "settings-and-retention"], ["internal", "Internal traffic", "internal-traffic", "Your office, home and test machines, so your own visits are not counted as people."]] },
    { route: "settings/site/privacy", name: "Privacy", help: "privacy",
      line: "What is kept about visitors and leads.",
      about: "Choose what Skald keeps about people (IP addresses, names, emails) and for how long, and copy the wording for your privacy notice." },
    { route: "settings/site/mail", name: "Mail & reports", help: "settings-and-retention",
      line: "Who gets the daily mail and client reports.",
      about: "The daily and weekly mail, who gets it, the mail server, and branded reports for your clients.",
      tabs: [["mail", "Mail", "settings-and-retention"], ["reports", "Client reports", "client-reports", "A branded mail with a PDF, on your schedule, from verified days only."]] },
    { route: "settings/site/alerts", name: "Alerts", help: "settings-and-retention",
      line: "Which alerts are on, and whether they are mailed.",
      about: "Switch each alert on or off for this site, and whether alerts are mailed. The alerts themselves are on Site › Alerts." },
  ] },
  { key: "ai", name: "AI", pages: [
    { route: "settings/ai/assistants", name: "AI assistants", help: "mcp", docs: "integrations/mcp/",
      line: "Ask Claude, ChatGPT and others about your traffic.",
      about: "Connect an AI assistant over MCP, or read every figure as JSON with the API. Each uses a read-only token; revoke one under Tokens & links.",
      tabs: [["mcp", "MCP", "mcp"], ["api", "API", "api", "Every figure as JSON, for a script or a spreadsheet, with a read-only token."],
        ["tokens", "Tokens & links", "api", "Every token of the organisation and every private link shared with a developer. Revoke one and whatever uses it stops at once."]] },
    { route: "settings/ai/answers", name: "AI answers", help: "ai-answers",
      line: "What AI assistants say about this site.",
      about: "Your questions, brand terms and competitors, the tracking profiles, and the assistants' API keys.",
      tabs: [["profiles", "Questions & profiles", "ai-answers"], ["keys", "API keys", "ai-answers", "The keys Skald uses to ask each assistant. An install admin adds them."]] },
  ] },
  { key: "org", name: "Organisation", pages: [
    { route: "settings/org/sites", name: "Sites", help: "connections",
      line: "Every site, its state, and its menu.",
      about: "Add a site, prove it is yours, continue a set-up, or pause, remove or delete a site from its row's menu." },
    { route: "settings/org/people", name: "People", help: "sign-in-and-team",
      line: "Who may see and change things.",
      about: "Members and their roles. Owners manage everything, admins change settings, viewers only look.",
      tabs: [["team", "Team", "sign-in-and-team"], ["security", "Sign-in rules", "sign-in-and-team", "Two-step sign-in for everyone, and how long a sign-in lasts."]] },
    { route: "settings/org/billing", name: "Billing", help: "settings-and-retention",
      line: "Your plan and how much of it is used.",
      about: "Admins can read it; only owners choose a plan or change the payment." },
    { route: "settings/org/audit", name: "Audit log", help: "settings-and-retention",
      line: "Who changed what, and when.",
      about: "Every change to settings, sites, tokens and members. Download it as CSV." },
  ] },
  { key: "you", name: "You", pages: [
    { route: "settings/you/account", name: "Your account", help: "sign-in-and-team",
      line: "Your name, password and two-step sign-in.",
      about: "Your name, password, two-step sign-in, and the browsers where you are signed in." },
  ] },
];

const TODO = { route: "settings/todo", name: "To do", help: "getting-started", group: null,
  line: "What needs you now.",
  about: "Everything that needs you, for this site and the organisation, most important first. A line goes away once Skald sees it working." };

// The pages in the menu's order (To do first), and by route.
export const SETTINGS_PAGES = [TODO, ...SETTINGS_GROUPS.flatMap((g) => g.pages.map((p) => ({ ...p, group: g.name })))];
export const pageOf = (route) => SETTINGS_PAGES.find((p) => p.route === route) || null;

// The in-page tab open: the address's sub=, when the page has it and `ok` lets it, else the
// first that `ok` lets (ok: the reader may open that tab; tabKey(route, sub) in HIDDEN).
export const tabKey = (route, sub) => `${route}#${sub}`;
export function subOf(route, sub, ok = () => true) {
  const tabs = (pageOf(route)?.tabs || []).filter(([k]) => ok(tabKey(route, k)));
  return tabs.some(([k]) => k === sub) ? sub : (tabs[0]?.[0] || "");
}
const tabOf = (route, sub) => (pageOf(route)?.tabs || []).find(([k]) => k === subOf(route, sub)) || null;
// The Help guide for a page (and its tab).
export function helpOf(route, sub = "") {
  const p = pageOf(route);
  return p ? (tabOf(route, sub)?.[2] || p.help || "") : "";
}
// What the "?" says for a page (and its tab).
export function aboutOf(route, sub = "") {
  const p = pageOf(route);
  return p ? (tabOf(route, sub)?.[3] || p.about || p.line || "") : "";
}
// The public page's path under the home address: "docs/mcp/", "integrations/mcp/".
export function docsPath(route, sub = "") {
  const p = pageOf(route);
  if (!p) return "";
  const t = tabOf(route, sub);
  if (t && t[2] && t[2] !== p.help) return `docs/${t[2]}/`;
  return p.docs || (p.help ? `docs/${p.help}/` : "docs/");
}

/* Older Settings addresses (before v2, and 2.40's) -> [new route, parameters it sets]. The old
   Connections page (#settings/api) is decided by what it opened: connectionsHome(). */
export const OLD_SETTINGS = {
  // 2.40's pages
  "settings/home": ["settings/todo"], "settings/site/setup": ["settings/todo"],
  "settings/site/collect": ["settings/site/data"],
  "settings/site/internal": ["settings/site/details", { sub: "internal" }],
  "settings/site/aianswers": ["settings/ai/answers"],
  "settings/ai/mcp": ["settings/ai/assistants"], "settings/ai/api": ["settings/ai/assistants", { sub: "api" }],
  "settings/ai/tokens": ["settings/ai/assistants", { sub: "tokens" }],
  "settings/org/team": ["settings/org/people"], "settings/org/users": ["settings/org/people"],
  "settings/org/security": ["settings/org/people", { sub: "security" }],
  "settings/help": ["help"],
  // before 2.40, and the short names
  "settings/account": ["settings/you/account"], account: ["settings/you/account"],
  "settings/team": ["settings/org/people"], team: ["settings/org/people"],
  "settings/users": ["settings/org/people"], users: ["settings/org/people"],
  "settings/tokens": ["settings/ai/assistants", { sub: "tokens" }], tokens: ["settings/ai/assistants", { sub: "tokens" }],
  "settings/mcp": ["settings/ai/assistants"], mcp: ["settings/ai/assistants"],
  "settings/sites": ["settings/site/details"], sites: ["settings/site/details"],
  "settings/internal": ["settings/site/details", { sub: "internal" }], internal: ["settings/site/details", { sub: "internal" }],
  ours: ["settings/site/details", { sub: "internal" }],
  "settings/retention": ["settings/site/privacy"], retention: ["settings/site/privacy"], "settings/privacy": ["settings/site/privacy"],
  "settings/mail": ["settings/site/mail"], mail: ["settings/site/mail"],
  "settings/reports": ["settings/site/mail", { sub: "reports" }], reports: ["settings/site/mail", { sub: "reports" }],
  "settings/integrations": ["settings/site/leads"], integrations: ["settings/site/leads"],
  "settings/aianswers": ["settings/ai/answers"],
  "settings/sitesadmin": ["settings/org/sites"],
  "settings/security": ["settings/org/people", { sub: "security" }], security: ["settings/org/people", { sub: "security" }],
  "settings/audit": ["settings/org/audit"], audit: ["settings/org/audit"],
  "settings/billing": ["settings/org/billing"], billing: ["settings/org/billing"],
};
// The old Connections page and its other names.
export const CONNECTIONS = new Set(["settings/api", "settings/connections", "connections", "api"]);
/* Where an old Connections address opens: by the dialog it named. params: URLSearchParams or null. */
export function connectionsHome(params) {
  const conn = params?.get?.("conn") || "";
  if (conn === "mcp") return ["settings/ai/assistants"];
  if (conn === "api") return ["settings/ai/assistants", { sub: "api" }];
  if (conn === "send" || conn === "sample") return ["settings/site/data"];
  return ["settings/todo"];
}
