// One primary button per screen (2.41, docs/UI-RULES.md rule 1): in the accent colour, at
// the top right of the screen's head. Every other button on the screen is a plain one.
//
//   primary(words, onClick, { icon, label })  -> <button class="btn ui-primary">
//   screenHead(title, { help, action, lede }) -> the head: title, its "?", the one action,
//                                               and at most one line under it
//   primaries(root)                           -> how many primary buttons a screen shows
//                                               (the tests hold each screen to one)

import { h } from "../ui.js";

export function primary(words, onClick, { icon = "", label = null } = {}) {
  const b = h("button", { type: "button", class: "btn ui-primary", "aria-label": label },
    icon ? h("span", { class: "ui-p-ic", html: icon, "aria-hidden": "true" }) : null, words);
  if (onClick) b.addEventListener("click", onClick);
  return b;
}

export function screenHead(title, { help = null, action = null, lede = null, level = "h2" } = {}) {
  return h("div", { class: "ui-headw" },
    h("div", { class: "ui-head" }, h(level, { class: "ui-title" }, title), help, h("span", { class: "ui-grow" }), action ? h("span", { class: "ui-act" }, action) : null),
    lede ? h("p", { class: "ui-lede" }, lede) : null);
}

// Shown: not under [hidden], and not inside a closed fold (only its summary shows).
function shown(b) {
  if (b.closest?.("[hidden]")) return false;
  for (let p = b.parentNode, kid = b; p; kid = p, p = p.parentNode) {
    if (p.tagName === "DETAILS" && !p.hasAttribute("open") && kid.tagName !== "SUMMARY") return false;
  }
  return true;
}
export const primaries = (root) => [...(root?.querySelectorAll?.(".btn.primary, .btn.ui-primary") || [])].filter(shown).length;
