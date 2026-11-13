// Leads › Find a person (#33): the Find a person tab became this one search box, at the right
// of the Leads head (actions on the right). An admin or an owner types an IP address, an
// email, a lead or a visitor ID; the answer opens in person.js's drawer (every visit kept,
// every lead and conversion, linked), whose search is in the address as a token (who=). The
// helper checks the role too and writes each search to the audit log (the kind of value,
// never the value). The old address (#sales/people) opens Leads with this box focused
// (lfind=1, routes.js). Everyone else, and the demo, sees no box: one door, only where it works.

import { h } from "../ui.js";
import { DEMO } from "../demo.js";
import { mayFind, openPerson, SEARCH_HINT } from "./person.js";

export function findBox(s) {
  if (DEMO.on || !mayFind()) return null;
  const field = h("input", { type: "search", class: "pp-in sa-find-in", id: "sa-find", placeholder: "Find a person", title: SEARCH_HINT, autocomplete: "off", spellcheck: "false", maxlength: "320", "aria-describedby": "sa-find-why" });
  const form = h("form", { class: "sa-find", role: "search" }, h("label", { class: "vh", for: "sa-find" }, `Find a person: ${SEARCH_HINT}`), field,
    h("span", { class: "vh", id: "sa-find-why" }, "Every visit kept with this address, every lead and conversion, linked. Each search is written to the audit log: the kind of value, never the value."),
    h("button", { type: "submit", class: "btn" }, "Find"));
  form.addEventListener("submit", (e) => { e.preventDefault(); if (field.value.trim()) openPerson(field.value); });
  // An old Find a person link (lfind=1): the box has the focus.
  if (s?.lfind) requestAnimationFrame(() => { if (field.isConnected) field.focus?.(); });
  return form;
}

/* What the demo and the other roles are told instead, once, under the list: where finding a
   person lives on an install. */
export function findNote() {
  if (DEMO.on) return "In the demo, Find a person is off: on your own install, admins and owners find one person by an IP address, an email, a lead or a visitor ID, from the box at the top of Leads.";
  if (!mayFind()) return "Only an admin or an owner can look a person up (the Find a person box at the top of Leads).";
  return "";
}
