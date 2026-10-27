// The menu's icons (v2; 2.40: apart from index.js, so a settings page may use them without a
// circular import): the sections', each settings page's, Help's and About's.

import { SECTION_ICONS } from "../sections.js";


const I = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const HELP = I('<circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 1 1 2.4 1.7c-.5.2-.7.6-.7 1.1v.4M8 11.3h.01"/>');
export const TAB_ICONS = {
  ...SECTION_ICONS,
  "settings/todo": I('<rect x="2.5" y="2" width="11" height="12.5" rx="1.8"/><path d="M5 6l1.2 1.2L8.5 5M5 10.5l1.2 1.2 2.3-2.2M10 6.3h1.5M10 10.8h1.5"/>'),
  "settings/site/data": I('<path d="M8 2v7.5M5 6.8 8 9.8l3-3"/><path d="M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2"/>'),
  "settings/site/details": I('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 5.5h12M4 4h.01M5.5 4h.01"/>'),
  "settings/site/leads": I('<path d="M6 2.5v3M10 2.5v3M4.5 5.5h7v2.5a3.5 3.5 0 0 1-7 0z"/><path d="M8 11.5v2"/>'),
  "settings/site/privacy": I('<path d="M8 1.8 13 3.8v4c0 3-2.2 5.3-5 6.4-2.8-1.1-5-3.4-5-6.4v-4z"/><path d="M6 8l1.5 1.5L10.3 6.6"/>'),
  "settings/site/alerts": I('<path d="M4 11V7.5a4 4 0 0 1 8 0V11l1.2 1.5H2.8z"/><path d="M6.7 14a1.4 1.4 0 0 0 2.6 0"/>'),
  "settings/site/mail": I('<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5 8 9l5.5-4.5"/>'),
  "settings/ai/answers": I('<path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z"/><path d="M5.5 7h.01M8 7h.01M10.5 7h.01"/>'),
  "settings/ai/assistants": I('<path d="M2.5 3h11v7.5h-6l-3 2.5v-2.5h-2z"/><path d="M8 4.8l.7 1.7 1.7.7-1.7.7L8 9.6l-.7-1.7-1.7-.7 1.7-.7z"/>'),
  "settings/org/sites": I('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 5.5h12M8 7.5v4M6 9.5h4"/>'),
  "settings/org/people": I('<circle cx="5.5" cy="5.5" r="2"/><circle cx="11" cy="6" r="1.7"/><path d="M1.8 13c.5-2.2 1.9-3.4 3.7-3.4s3.2 1.2 3.7 3.4M9.6 9.8c1.9-.4 3.6.6 4.4 3.2"/>'),
  "settings/org/audit": I('<path d="M4 1.8h5.5L13 5.3v8.9H4z"/><path d="M6.5 8h4M6.5 10.5h4M6.5 5.5h1.5"/>'),
  "settings/org/billing": I('<rect x="1.8" y="3.5" width="12.4" height="9" rx="1.5"/><path d="M1.8 6.5h12.4M4 10h3"/>'),
  "settings/you/account": I('<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.7-2.6 2.6-4 5-4s4.3 1.4 5 4"/>'),
  help: HELP,
  about: I('<path d="M3 13.5l4.5-4.5M7.5 9C9 5 11 3 13.5 2.5c-.3 3-2.3 5.6-6 6.5z"/><path d="M5 3v9"/>'),
};
export const GEAR = I('<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v1.6M8 12.6v1.6M1.8 8h1.6M12.6 8h1.6M3.6 3.6l1.1 1.1M11.3 11.3l1.1 1.1M3.6 12.4l1.1-1.1M11.3 4.7l1.1-1.1"/>');
