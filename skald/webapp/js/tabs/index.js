// The tab registry: one render function per route, and the menu's icons.

import { api, users } from "./settings.js";
import ours from "./ours.js";
import team from "./team.js";
import account from "./account.js";
import { retention, mail, sites, security } from "./prefs.js";
import auditlog from "./auditlog.js";
import billing from "./billing.js";
import sitesadmin from "./sitesadmin.js";
import integrations from "./integrations.js";
import aiAnswersSettings from "./ai-answers-settings.js";
import reports from "./reports.js";
import about from "./about.js";
import help from "./help.js";
import { TAB, SECTION_ICONS } from "../sections.js";

// The five sections' tabs come from the registry (js/sections.js, js/tabs/s-*.js); Settings'
// pages, Help and About are here.
export const TAB_RENDER = { ...Object.fromEntries(Object.entries(TAB).map(([k, t]) => [k, t.render])),
  "settings/internal": ours, "settings/api": api, "settings/users": users,
  "settings/team": team, "settings/account": account, "settings/retention": retention, "settings/mail": mail, "settings/reports": reports,
  "settings/sites": sites, "settings/sitesadmin": sitesadmin, "settings/integrations": integrations, "settings/aianswers": aiAnswersSettings, "settings/security": security, "settings/audit": auditlog, "settings/billing": billing, help, about };

const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const TAB_ICONS = {
  ...SECTION_ICONS,
  "settings/api": I('<path d="M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5"/>'),
  "settings/users": I('<circle cx="6" cy="5.5" r="2.3"/><path d="M2 13c.6-2.3 2.1-3.5 4-3.5s3.4 1.2 4 3.5M10.5 3.6a2.2 2.2 0 0 1 0 4.1M12.2 9.8c.9.6 1.5 1.7 1.8 3.2"/>'),
  "settings/team": I('<circle cx="5.5" cy="5.5" r="2"/><circle cx="11" cy="6" r="1.7"/><path d="M1.8 13c.5-2.2 1.9-3.4 3.7-3.4s3.2 1.2 3.7 3.4M9.6 9.8c1.9-.4 3.6.6 4.4 3.2"/>'),
  "settings/account": I('<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.7-2.6 2.6-4 5-4s4.3 1.4 5 4"/>'),
  "settings/retention": I('<path d="M3 4.5h10M4.5 4.5v8.5a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1V4.5M6.5 2.5h3"/><path d="M6.8 7v4.5M9.2 7v4.5"/>'),
  "settings/mail": I('<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5 8 9l5.5-4.5"/>'),
  "settings/reports": I('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M6.5 12v-2M8.5 12V8M10.5 12V9.5"/>'),
  "settings/sites": I('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 5.5h12M4 4h.01M5.5 4h.01"/>'),
  "settings/sitesadmin": I('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 5.5h12M8 7.5v4M6 9.5h4"/>'),
  "settings/integrations": I('<path d="M6 2.5v3M10 2.5v3M4.5 5.5h7v2.5a3.5 3.5 0 0 1-7 0z"/><path d="M8 11.5v2"/>'),
  "settings/aianswers": I('<path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z"/><path d="M5.5 7h.01M8 7h.01M10.5 7h.01"/>'),
  "settings/security": I('<rect x="3.5" y="7" width="9" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/>'),
  "settings/audit": I('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M6.5 8h4M6.5 10.5h4M6.5 5.5h1.5"/>'),
  "settings/billing": I('<rect x="1.8" y="3.5" width="12.4" height="9" rx="1.5"/><path d="M1.8 6.5h12.4M4 10h3"/>'),
  help: I('<circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/>'),
  about: I('<path d="M3 13.5l4.5-4.5M7.5 9C9 5 11 3 13.5 2.5c-.3 3-2.3 5.6-6 6.5z"/><path d="M5 3v9"/>'),
  "settings/internal": I('<path d="M2.5 7L8 2.5 13.5 7v6.5h-11z"/><path d="M6.5 13.5V10h3v3.5"/>'),
};
export const GEAR = I('<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v1.6M8 12.6v1.6M1.8 8h1.6M12.6 8h1.6M3.6 3.6l1.1 1.1M11.3 11.3l1.1 1.1M3.6 12.4l1.1-1.1M11.3 4.7l1.1-1.1"/>');
