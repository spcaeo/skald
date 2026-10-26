// Settings › All settings and Help & docs (2.40).
//
//   All settings   the map: what people come to Settings to do, one click each, then every
//                  page this reader may open, by group, with one line saying what it is for
//   Help & docs    the in-app guides, the public docs (each with copy and open icons), the
//                  API and MCP pages, What's new, the keyboard shortcuts, the contact page

import { h } from "../ui.js";
import * as S from "../state.js";
import { SETTINGS_GROUPS } from "../settings-menu.js";
import { TAB_ICONS } from "./icons.js";
import { head1 } from "./forms.js";
import { withUrl } from "../urlactions.js";
import { REPO } from "../build.js";
import { docsUrl } from "./settings-frame.js";
import INDEX from "../help-index.js";

const go = (route, extra = {}) => (e) => {
  if (e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  S.set({ tab: route, ...extra });
};
const hrefOf = (route, extra = "") => `#${route}${extra}`;

// What people come to Settings to do, in their words, each opening the page that does it.
const TASKS = [
  ["Set up this site", "settings/site/setup"],
  ["Connect an AI assistant (MCP)", "settings/ai/mcp"],
  ["Send a site's logs", "settings/site/collect"],
  ["Get the script tag", "settings/site/collect", "script"],
  ["Connect a form or booking tool", "settings/site/leads"],
  ["Add, pause or delete a site", "settings/org/sites"],
  ["Invite someone", "settings/org/team"],
  ["Choose what is kept about people", "settings/site/privacy"],
  ["Revoke a token", "settings/ai/tokens"],
  ["Change your password", "settings/you/account"],
];

export function homePage(m) {
  const tasks = TASKS.filter(([, r]) => S.shown(r)).map(([words, r, sub]) =>
    h("li", null, h("a", { class: "set-task", href: hrefOf(r, sub ? `?sub=${sub}` : ""), onclick: go(r, sub ? { sub } : {}) }, words)));
  const groups = SETTINGS_GROUPS.map((g) => {
    const pages = g.pages.filter((p) => S.shown(p.route));
    if (!pages.length) return null;
    return h("section", { class: "s set-group", "aria-labelledby": `set-g-${g.key}` },
      h("h2", { id: `set-g-${g.key}` }, g.key === "site" ? `${g.name}: ${m.site}` : g.name),
      h("ul", { class: "set-cards-grid" }, pages.map((p) => h("li", null,
        h("a", { class: "set-card", href: hrefOf(p.route), onclick: go(p.route) },
          h("span", { class: "set-card-i", html: TAB_ICONS[p.route] || "" }),
          h("span", { class: "set-card-t" }, h("b", null, p.name), h("span", null, p.line)))))));
  });
  return [head1("All settings", "Every settings page, grouped by what you came to do. New here? Start with the set-up checklist."),
    tasks.length ? h("section", { class: "s", "aria-label": "Common tasks" }, h("h2", null, "What do you want to do?"), h("ul", { class: "set-tasks" }, tasks)) : null,
    ...groups];
}

/* A public page: its name as a link (a new tab) with the copy and open icons, and one line. */
function online(name, url, line) {
  return h("li", { class: "set-doc" },
    withUrl(h("a", { href: url, target: "_blank", rel: "noopener" }, name), url, { label: name, cls: "ua-after" }),
    line ? h("span", { class: "set-doc-l" }, line) : null);
}

export function helpDocsPage() {
  const whatsNew = h("button", { type: "button", class: "btn" }, "What's new in this version");
  whatsNew.addEventListener("click", async () => (await import("../keys.js")).whatsNew(document.querySelector(".new-dot")));
  const shortcuts = h("button", { type: "button", class: "btn" }, "Keyboard shortcuts");
  shortcuts.addEventListener("click", async () => (await import("../keys.js")).help());
  return [head1("Help & docs", "Guides in plain words, here in the app and on the public site, and where to ask."),
    h("section", { class: "s" }, h("h2", null, "Start here"),
      h("ul", { class: "set-docs" },
        online("All the docs", docsUrl("docs/"), "every guide on the public site, the same words as in the app"),
        online("Connect an AI assistant (MCP)", docsUrl("integrations/mcp/"), "Claude, ChatGPT and other assistants"),
        online("The API", docsUrl("integrations/api/"), "every figure as JSON, for a script"),
        online("What's new", docsUrl("whats-new/"), "every release, newest first"),
        online("Contact", docsUrl("contact/"), "a question, a problem, a wish"),
        online("Skald on GitHub", REPO, "the source, releases, and issues"))),
    h("section", { class: "s" }, h("h2", null, "In this app"),
      h("div", { class: "acts" }, h("a", { class: "btn primary", href: "#help", onclick: go("help", { part: "" }) }, "Open Help"), whatsNew, shortcuts),
      h("p", { class: "note" }, "Ctrl K (Cmd K on a Mac) finds any guide, settings page or action by name: type mcp, token or retention.")),
    h("section", { class: "s" }, h("h2", null, "Every guide"),
      h("p", { class: "sub" }, "Each opens here in the app; the icons beside Online copy or open its public page."),
      h("ul", { class: "set-guides" }, INDEX.map((g) => h("li", null,
        h("a", { class: "set-guide", href: `#help?part=${g.id}`, onclick: go("help", { part: g.id }) }, h("b", null, g.title)),
        h("span", { class: "set-guide-s" }, g.summary),
        withUrl(h("a", { class: "set-guide-o", href: docsUrl(`docs/${g.id}/`), target: "_blank", rel: "noopener" }, "Online"), docsUrl(`docs/${g.id}/`), { label: `${g.title} online`, cls: "ua-after" })))))];
}
