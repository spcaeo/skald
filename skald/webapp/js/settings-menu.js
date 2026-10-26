// Settings' menu (2.40, docs/plans/2026-10-26-settings-redesign.md): every settings page,
// grouped by what a person comes to do, with one line each, its Help guide (docs/help/<id>.md,
// in the app as #help?part=<id>), its public docs page (<home>/docs/<id>/) and the page that
// comes next. A page with in-page tabs lists them (the address's sub=<key>; the first when
// absent), each with its own guide. No DOM and no imports, so node and state.js read it.
//
//   route   the page's address, settings/<group>/<page>
//   name    its name in the menu, the palette and the title bar
//   line    what it is for, one plain line (All settings, the phone's select)
//   help    the in-app guide's id; docs: the public page's path when not /docs/<help>/
//   tabs    [[sub, name, help?]]: in-page tabs
//   next    [route, words]: the Next step card at the page's foot

export const SETTINGS_HOME = "settings/home";

export const SETTINGS_GROUPS = [
  { key: "site", name: "This site", pages: [
    { route: "settings/site/setup", name: "Set-up checklist", help: "getting-started",
      line: "What works and what is left for this site, each with a Set up button. Or hand it all to your AI agent.",
      next: ["settings/site/collect", "Collect data: send the site's logs, or add the script tag"] },
    { route: "settings/site/collect", name: "Collect data", help: "connections",
      line: "How visits reach Skald: the server's logs, the script tag, and what counts as a person or a page.",
      tabs: [["logs", "Send logs", "connections"], ["script", "Script tag & goals", "tracking-script"], ["counting", "What counts", "settings-and-retention"]],
      next: ["settings/site/leads", "Leads & integrations: connect your forms, bookings and payments"] },
    { route: "settings/site/details", name: "Site details", help: "settings-and-retention",
      line: "The site's host names, page groups, time zone and logo.",
      next: ["settings/site/collect", "Collect data: how visits reach Skald"] },
    { route: "settings/site/leads", name: "Leads & integrations", help: "webhooks",
      line: "Leads from Calendly, Cal.com, HubSpot, Typeform, Stripe or your own server; webhooks out; Search Console and Bing.",
      tabs: [["hooks", "Incoming hooks", "webhooks"], ["webhooks", "Outgoing webhooks", "webhooks"], ["search", "Search Console & Bing", "search"]],
      next: ["settings/site/privacy", "Privacy & retention: choose what is kept about people"] },
    { route: "settings/site/internal", name: "Internal traffic", help: "internal-traffic",
      line: "Your office, home and test machines, so your own visits are not counted as people.",
      next: ["settings/site/setup", "Back to the set-up checklist"] },
    { route: "settings/site/privacy", name: "Privacy & retention", help: "privacy",
      line: "What is kept about people and leads, for how long, and wording for your privacy notice.",
      next: ["settings/site/mail", "Mail & reports: choose who gets the daily mail"] },
    { route: "settings/site/mail", name: "Mail & reports", help: "settings-and-retention",
      line: "The daily and weekly mail, the mail server, and reports for your clients.",
      tabs: [["mail", "Mail", "settings-and-retention"], ["reports", "Client reports", "client-reports"]],
      next: ["settings/ai/mcp", "AI assistant (MCP): ask about this site in plain words"] },
    { route: "settings/site/aianswers", name: "AI answers", help: "ai-answers",
      line: "What AI assistants say about this site: your questions, brand terms, competitors and tracking profiles.",
      tabs: [["profiles", "Questions & profiles", "ai-answers"], ["keys", "API keys", "ai-answers"]],
      next: ["settings/site/setup", "Back to the set-up checklist"] },
  ] },
  { key: "ai", name: "AI & API", pages: [
    { route: "settings/ai/mcp", name: "AI assistant (MCP)", help: "mcp", docs: "integrations/mcp/",
      line: "Ask Claude, ChatGPT or another assistant about your traffic in plain words.",
      next: ["settings/ai/tokens", "Tokens & links: see or revoke what each assistant uses"] },
    { route: "settings/ai/api", name: "Read figures (API)", help: "api", docs: "integrations/api/",
      line: "Every figure as JSON, for a script or a spreadsheet, with a read-only token.",
      next: ["settings/ai/tokens", "Tokens & links: see or revoke your tokens"] },
    { route: "settings/ai/tokens", name: "Tokens & links", help: "api",
      line: "Every token of the organisation and the private links shared with a developer. Revoke here.",
      next: ["settings/ai/mcp", "AI assistant (MCP): connect an assistant"] },
  ] },
  { key: "org", name: "Organisation", pages: [
    { route: "settings/org/sites", name: "Sites", help: "connections",
      line: "Add a site, prove it is yours, continue a set-up, or stop a site.",
      next: ["settings/site/setup", "Set up this site: the checklist"] },
    { route: "settings/org/team", name: "Team", help: "sign-in-and-team",
      line: "Who may see the organisation's sites, and what each may change. Invite someone.",
      next: ["settings/org/security", "Sign-in rules: ask everyone for two-step sign-in"] },
    { route: "settings/org/users", name: "Users", help: "sign-in-and-team",
      line: "Who may look and who may change things, on a server with one shared login.",
      next: ["settings/org/team", "Team"] },
    { route: "settings/org/security", name: "Sign-in rules", help: "sign-in-and-team",
      line: "Two-step sign-in for everyone, and how long a sign-in lasts.",
      next: ["settings/org/audit", "Audit log: who changed what"] },
    { route: "settings/org/audit", name: "Audit log", help: "settings-and-retention",
      line: "Who changed what, and when. Download it as CSV.",
      next: ["settings/org/team", "Team: who may change things"] },
    { route: "settings/org/billing", name: "Billing & usage", help: "settings-and-retention",
      line: "The plan, how much of it is used, and payment.",
      next: ["settings/org/sites", "Sites"] },
  ] },
  { key: "you", name: "You", pages: [
    { route: "settings/you/account", name: "Your account", help: "sign-in-and-team",
      line: "Your name, password, two-step sign-in and where you are signed in.",
      next: ["settings/home", "All settings"] },
  ] },
  { key: "help", name: "Help & docs", pages: [
    { route: "settings/help", name: "Help & docs", help: "getting-started", docs: "docs/",
      line: "Every guide in the app, the public docs, the API and MCP pages, What's new, and how to reach us." },
  ] },
];

// The pages in the menu's order (All settings first), and by route.
export const SETTINGS_PAGES = [
  { route: SETTINGS_HOME, name: "All settings", help: "settings-and-retention", group: null,
    line: "Every settings page, with what each is for." },
  ...SETTINGS_GROUPS.flatMap((g) => g.pages.map((p) => ({ ...p, group: g.name }))),
];
export const pageOf = (route) => SETTINGS_PAGES.find((p) => p.route === route) || null;

// The in-page tab open: the address's sub=, when the page has it, else its first tab.
export function subOf(route, sub) {
  const tabs = pageOf(route)?.tabs || [];
  return tabs.some(([k]) => k === sub) ? sub : (tabs[0]?.[0] || "");
}
// The Help guide for a page (and its tab).
export function helpOf(route, sub = "") {
  const p = pageOf(route);
  if (!p) return "";
  const t = (p.tabs || []).find(([k]) => k === subOf(route, sub));
  return (t && t[2]) || p.help || "";
}
// The public page's path under the home address: "docs/mcp/", "integrations/mcp/".
export function docsPath(route, sub = "") {
  const p = pageOf(route);
  if (!p) return "";
  const t = (p.tabs || []).find(([k]) => k === subOf(route, sub));
  if (t && t[2] && t[2] !== p.help) return `docs/${t[2]}/`;
  return p.docs || (p.help ? `docs/${p.help}/` : "docs/");
}

/* Old Settings addresses (before 2.40) -> [new route, parameters it sets]. #settings/api (the
   old Connections page) is decided by what it opened: connectionsHome(). */
export const OLD_SETTINGS = {
  "settings/account": ["settings/you/account"], account: ["settings/you/account"],
  "settings/team": ["settings/org/team"], team: ["settings/org/team"],
  "settings/users": ["settings/org/users"], users: ["settings/org/users"],
  "settings/tokens": ["settings/ai/tokens"], tokens: ["settings/ai/tokens"],
  "settings/mcp": ["settings/ai/mcp"], mcp: ["settings/ai/mcp"],
  "settings/sites": ["settings/site/details"], sites: ["settings/site/details"],
  "settings/internal": ["settings/site/internal"], internal: ["settings/site/internal"], ours: ["settings/site/internal"],
  "settings/retention": ["settings/site/privacy"], retention: ["settings/site/privacy"], "settings/privacy": ["settings/site/privacy"],
  "settings/mail": ["settings/site/mail"], mail: ["settings/site/mail"],
  "settings/reports": ["settings/site/mail", { sub: "reports" }], reports: ["settings/site/mail", { sub: "reports" }],
  "settings/integrations": ["settings/site/leads"], integrations: ["settings/site/leads"],
  "settings/aianswers": ["settings/site/aianswers"],
  "settings/sitesadmin": ["settings/org/sites"],
  "settings/security": ["settings/org/security"], security: ["settings/org/security"],
  "settings/audit": ["settings/org/audit"], audit: ["settings/org/audit"],
  "settings/billing": ["settings/org/billing"], billing: ["settings/org/billing"],
};
// The old Connections page and its other names.
export const CONNECTIONS = new Set(["settings/api", "settings/connections", "connections", "api"]);
/* Where an old Connections address opens: by the dialog it named. params: URLSearchParams or null. */
export function connectionsHome(params) {
  const conn = params?.get?.("conn") || "";
  if (conn === "mcp") return ["settings/ai/mcp"];
  if (conn === "api") return ["settings/ai/api"];
  if (conn === "send" || conn === "sample") return ["settings/site/collect"];
  return ["settings/site/setup"];
}
