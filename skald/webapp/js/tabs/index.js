// The tab registry: one render function per route, and the menu's icons.

import about from "./about.js";
import help from "./help.js";
import { SETTINGS_RENDER } from "./settings-pages.js";
import { framed } from "./settings-frame.js";
import { SETTINGS_PAGES } from "../settings-menu.js";
import { TAB } from "../sections.js";

// The five sections' tabs come from the registry (js/sections.js, js/tabs/s-*.js); Settings'
// pages (js/settings-menu.js, drawn by settings-pages.js inside settings-frame.js), Help and About are here.
export const TAB_RENDER = { ...Object.fromEntries(Object.entries(TAB).map(([k, t]) => [k, t.render])),
  ...Object.fromEntries(SETTINGS_PAGES.map((p) => [p.route, framed(p.route, SETTINGS_RENDER[p.route])])),
  help, about };
export { TAB_ICONS, GEAR } from "./icons.js";
