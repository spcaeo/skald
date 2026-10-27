// What each settings page draws (v2): route -> render, or {sub: render} for a page with
// in-page tabs (js/settings-menu.js lists them). settings-frame.js draws each inside the frame:
// the phone's menu, the title and its "?", the tab strip. Pages that other work owns
// (Privacy, Billing, Sites) are moved here whole.

import { users } from "./settings.js";
import { sessions } from "../access.js";
import { internalTab } from "./set-internal.js";
import team from "./team.js";
import account from "./account.js";
import { retention, mail, security } from "./prefs.js";
import auditlog from "./auditlog.js";
import billing from "./billing.js";
import sitesadmin from "./sitesadmin.js";
import { integrationsPart } from "./integrations.js";
import aiAnswersSettings from "./ai-answers-settings.js";
import reports from "./reports.js";
import { dataLogs, dataScript, dataCounting, dataSample, siteDetails } from "./set-site.js";
import { leadsPage } from "./set-leads.js";
import { mcpTab, apiTab, tokensTab } from "./set-ai.js";
import { todoPage } from "./set-todo.js";
import { alertsSettings } from "./set-alerts.js";

export const SETTINGS_RENDER = {
  "settings/todo": todoPage,
  "settings/site/data": { logs: dataLogs, script: dataScript, counting: dataCounting, sample: dataSample },
  "settings/site/leads": leadsPage,
  "settings/site/details": { details: siteDetails, internal: internalTab },
  "settings/site/privacy": retention,
  "settings/site/mail": { mail, reports },
  "settings/site/alerts": alertsSettings,
  "settings/ai/assistants": { mcp: mcpTab, api: apiTab, tokens: tokensTab },
  "settings/ai/answers": { profiles: aiAnswersSettings, keys: () => integrationsPart("aikeys") },
  "settings/org/sites": sitesadmin,
  // Team with accounts; Users on a server with one shared login.
  "settings/org/people": { team: (m, s, o) => (sessions() ? team(m, s, o) : users(m, s, o)), security },
  "settings/org/audit": auditlog,
  "settings/org/billing": billing,
  "settings/you/account": account,
};
