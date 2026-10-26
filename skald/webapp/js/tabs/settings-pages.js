// What each settings page draws (2.40): route -> render, or {sub: render} for a page with
// in-page tabs (js/settings-menu.js lists them). settings-frame.js draws each inside the frame:
// the phone's menu, Help · Docs, the tab strip, Next step. Pages that other work owns
// (Privacy & retention, Billing & usage, Sites) are moved here whole.

import { users } from "./settings.js";
import ours from "./ours.js";
import team from "./team.js";
import account from "./account.js";
import { retention, mail, security } from "./prefs.js";
import auditlog from "./auditlog.js";
import billing from "./billing.js";
import sitesadmin from "./sitesadmin.js";
import { integrationsPart } from "./integrations.js";
import aiAnswersSettings from "./ai-answers-settings.js";
import reports from "./reports.js";
import { setupPage, collectLogs, collectScript, collectCounting, siteDetails } from "./set-site.js";
import { mcpPage, apiPage, tokensPage } from "./set-ai.js";
import { homePage, helpDocsPage } from "./set-home.js";

export const SETTINGS_RENDER = {
  "settings/home": homePage,
  "settings/site/setup": setupPage,
  "settings/site/collect": { logs: collectLogs, script: collectScript, counting: collectCounting },
  "settings/site/details": siteDetails,
  "settings/site/leads": { hooks: () => integrationsPart("hooks"), webhooks: () => integrationsPart("webhooks"), search: () => integrationsPart("search") },
  "settings/site/internal": ours,
  "settings/site/privacy": retention,
  "settings/site/mail": { mail, reports },
  "settings/site/aianswers": { profiles: aiAnswersSettings, keys: () => integrationsPart("aikeys") },
  "settings/ai/mcp": mcpPage,
  "settings/ai/api": apiPage,
  "settings/ai/tokens": tokensPage,
  "settings/org/sites": sitesadmin,
  "settings/org/team": team,
  "settings/org/users": users,
  "settings/org/security": security,
  "settings/org/audit": auditlog,
  "settings/org/billing": billing,
  "settings/you/account": account,
  "settings/help": helpDocsPage,
};
