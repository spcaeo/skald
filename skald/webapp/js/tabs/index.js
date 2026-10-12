// The tab registry: one render function per tab, and the rail's icons.

import overview from "./overview.js";
import insights from "./insights.js";
import broken from "./broken.js";
import live from "./live.js";
import visits from "./visits.js";
import { sources, pages, audience } from "./readers.js";
import hours from "./hours.js";
import bots from "./bots.js";
import health from "./health.js";
import ours from "./ours.js";
import requests from "./requests.js";
import leads from "./leads.js";
import conversions from "./conversions.js";
import funnels from "./funnels.js";
import speed from "./speed.js";
import { api, users } from "./settings.js";
import team from "./team.js";
import account from "./account.js";
import { retention, mail, sites, security } from "./prefs.js";
import auditlog from "./auditlog.js";
import billing from "./billing.js";
import sitesadmin from "./sitesadmin.js";
import integrations from "./integrations.js";
import versus from "./versus.js";
import crawlers from "./crawlers.js";
import events from "./events.js";
import alerts from "./alerts.js";
import quality from "./quality.js";
import about from "./about.js";
import help from "./help.js";

export const TAB_RENDER = { overview, insights, compare: versus, live, requests, visitors: visits, sources, leads, conversions, funnels, events, pages, "health/broken": broken, locations: audience, time: hours, bots, health,
  "health/alerts": alerts, "health/quality": quality, "health/speed": speed, "settings/internal": ours, "settings/crawlers": crawlers, "settings/api": api, "settings/users": users,
  "settings/team": team, "settings/account": account, "settings/retention": retention, "settings/mail": mail,
  "settings/sites": sites, "settings/sitesadmin": sitesadmin, "settings/integrations": integrations, "settings/security": security, "settings/audit": auditlog, "settings/billing": billing, help, about };

const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
export const TAB_ICONS = {
  overview: I('<rect x="2" y="9" width="3" height="5" rx="1"/><rect x="6.5" y="5" width="3" height="9" rx="1"/><rect x="11" y="2" width="3" height="12" rx="1"/>'),
  insights: I('<path d="M8 1.8l1.6 3.9 4.1.4-3.1 2.7.9 4-3.5-2.1-3.5 2.1.9-4L2.3 6.1l4.1-.4z"/>'),
  "health/broken": I('<path d="M6.5 9.5l3-3M7 4.5l1-1a2.8 2.8 0 0 1 4 4l-1 1M9 11.5l-1 1a2.8 2.8 0 0 1-4-4l1-1M2.5 2.5l2 2M13.5 13.5l-2-2"/>'),
  live: I('<circle cx="8" cy="8" r="2"/><path d="M4.5 4.5a5 5 0 0 0 0 7M11.5 4.5a5 5 0 0 1 0 7"/>'),
  visitors: I('<circle cx="3.5" cy="4" r="1.5"/><circle cx="12.5" cy="12" r="1.5"/><path d="M5 4h4.5a2.5 2.5 0 0 1 0 5h-3a2.5 2.5 0 0 0 0 5H11"/>'),
  sources: I('<path d="M2 3h4l2 5-2 5H2M14 8H9"/><path d="M11.5 5.5L14 8l-2.5 2.5"/>'),
  pages: I('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M9.5 1.8v3.5H13M6.5 8.5h4M6.5 11h4"/>'),
  locations: I('<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2.2 2 9.8 0 12M8 2c-2 2.2-2 9.8 0 12"/>'),
  time: I('<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/>'),
  bots: I('<rect x="3" y="5" width="10" height="8" rx="2"/><path d="M8 2.5V5M6 9h.01M10 9h.01M1.5 9v2M14.5 9v2"/>'),
  health: I('<path d="M1.5 8.5h3l1.5-4 3 8 1.5-4h4"/>'),
  requests: I('<path d="M2.5 3.5h11M2.5 6.5h8M2.5 9.5h11M2.5 12.5h6"/>'),
  leads: I('<path d="M2 3h12l-4.5 5.5V13l-3-1.5v-3z"/>'),
  conversions: I('<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="3"/><path d="M8 8l5-5M11 3h2v2"/>'),
  events: I('<path d="M5.5 2.5v6.2l1.6-1.3 1.3 3 1.3-.6-1.3-3 2.1-.2z"/><path d="M2.5 13.5h11"/>'),
  compare: I('<path d="M2 12.5 6 8l3 2.5L14 4"/><path d="M2 9.5 5.5 6l3 3 3-2.5 2.5 2" stroke-dasharray="1.6 1.8"/>'),
  funnels: I('<path d="M2 3.5h12M4 7h8M5.8 10.5h4.4M7.2 14h1.6"/>'),
  "health/alerts": I('<path d="M4 11.5V7a4 4 0 0 1 8 0v4.5l1.2 1.3H2.8z"/><path d="M6.6 14a1.5 1.5 0 0 0 2.8 0"/>'),
  "settings/crawlers": I('<rect x="3" y="5.5" width="10" height="7.5" rx="2"/><path d="M8 2.5v3M6 9.2h.01M10 9.2h.01M1.5 2l13 12"/>'),
  "settings/api": I('<path d="M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5"/>'),
  "settings/users": I('<circle cx="6" cy="5.5" r="2.3"/><path d="M2 13c.6-2.3 2.1-3.5 4-3.5s3.4 1.2 4 3.5M10.5 3.6a2.2 2.2 0 0 1 0 4.1M12.2 9.8c.9.6 1.5 1.7 1.8 3.2"/>'),
  "settings/team": I('<circle cx="5.5" cy="5.5" r="2"/><circle cx="11" cy="6" r="1.7"/><path d="M1.8 13c.5-2.2 1.9-3.4 3.7-3.4s3.2 1.2 3.7 3.4M9.6 9.8c1.9-.4 3.6.6 4.4 3.2"/>'),
  "settings/account": I('<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.7-2.6 2.6-4 5-4s4.3 1.4 5 4"/>'),
  "settings/retention": I('<path d="M3 4.5h10M4.5 4.5v8.5a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1V4.5M6.5 2.5h3"/><path d="M6.8 7v4.5M9.2 7v4.5"/>'),
  "settings/mail": I('<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5 8 9l5.5-4.5"/>'),
  "settings/sites": I('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 5.5h12M4 4h.01M5.5 4h.01"/>'),
  "settings/sitesadmin": I('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 5.5h12M8 7.5v4M6 9.5h4"/>'),
  "settings/integrations": I('<path d="M6 2.5v3M10 2.5v3M4.5 5.5h7v2.5a3.5 3.5 0 0 1-7 0z"/><path d="M8 11.5v2"/>'),
  "settings/security": I('<rect x="3.5" y="7" width="9" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/>'),
  "settings/audit": I('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M6.5 8h4M6.5 10.5h4M6.5 5.5h1.5"/>'),
  "settings/billing": I('<rect x="1.8" y="3.5" width="12.4" height="9" rx="1.5"/><path d="M1.8 6.5h12.4M4 10h3"/>'),
  "health/speed": I('<path d="M2.5 11.5a5.5 5.5 0 1 1 11 0"/><path d="M8 11.5l2.6-3.4"/>'),
  "health/quality": I('<path d="M8 1.8l5 2v4c0 3-2.2 5.3-5 6.4-2.8-1.1-5-3.4-5-6.4v-4z"/><path d="M5.8 8l1.6 1.6 3-3.2"/>'),
  help: I('<circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/>'),
  about: I('<path d="M3 13.5l4.5-4.5M7.5 9C9 5 11 3 13.5 2.5c-.3 3-2.3 5.6-6 6.5z"/><path d="M5 3v9"/>'),
  "settings/internal": I('<path d="M2.5 7L8 2.5 13.5 7v6.5h-11z"/><path d="M6.5 13.5V10h3v3.5"/>'),
};
export const GEAR = I('<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v1.6M8 12.6v1.6M1.8 8h1.6M12.6 8h1.6M3.6 3.6l1.1 1.1M11.3 11.3l1.1 1.1M3.6 12.4l1.1-1.1M11.3 4.7l1.1-1.1"/>');
