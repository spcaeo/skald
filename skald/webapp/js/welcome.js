// The welcome line over the first page a new person opens (2.44.0). The helper's /me
// answers `welcome: true` once, on that person's first load (users.take_welcome); this
// tab keeps it (sessionStorage) until they close it, so a reload does not lose it.

import { h, ICON } from "./ui.js";
import { ME } from "./access.js";

const KEY = "ti-welcome";

// The words, or null: pure, so a test can run it without a page.
export function welcomeNotice(me, kept) {
  if (!me?.welcome && kept !== "1") return null;
  const first = String(me?.name || "").trim().split(/\s+/)[0];
  return {
    title: `Welcome to Skald${first ? `, ${first}` : ""}.`,
    words: me?.org ? ` You see ${me.org}'s sites. Start with ` : " Start with ",
  };
}

function kept() {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
}

export function welcomeBanner() {
  const n = welcomeNotice(ME, kept());
  if (!n) return null;
  try { sessionStorage.setItem(KEY, "1"); } catch { /* storage blocked: shown on this load only */ }
  const box = h("div", { class: "state update-banner welcome-banner", role: "status", html: ICON.info });
  const close = h("button", { class: "update-close", type: "button", "aria-label": "Close the welcome", title: "Close",
    onclick: () => { try { sessionStorage.removeItem(KEY); } catch { /* blocked */ } ME.welcome = false; box.remove(); } }, "×");
  box.append(h("div", { class: "update-words" }, h("strong", null, n.title), n.words,
    h("a", { href: "#overview/summary" }, "Overview"), ". The ? on any page says what it shows; ",
    h("a", { href: "#help" }, "Help"), " has the guides."), close);
  return box;
}
