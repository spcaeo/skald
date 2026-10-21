// Leads & sales > Find a person (2.7.0 as People; 2.20 keeps only the search): find one
// person. The people who converted lately are on Leads now, one row per lead (sa-leads.js).
//   * Find a person (admins and owners): an IP address, an email, a lead or a
//     visitor ID; the answer opens in person.js's drawer (every visit kept,
//     every lead and conversion, linked). The helper checks the role too and
//     writes each search to the audit log (the kind of value, never the value).
// Listings, never figures. What the figures leave out is listed on Leads (Show left out)
// and Calendar bookings; this tab links to them.

import { h } from "../ui.js";
import * as S from "../state.js";
import { rangeOf } from "../data.js";
import { DEMO, DEMO_SAYS } from "../demo.js";
import { mayFind, openPerson, SEARCH_HINT } from "./person.js";
import { tabHead } from "./sa-options.js";

function search() {
  // The demo has no helper to ask: the search needs a running install.
  if (DEMO.on) {
    return h("section", { class: "s" },
      h("div", { class: "state" }, h("div", null, h("strong", null, `${DEMO_SAYS} `), "On your own install, admins and owners find one person here by an IP address, an email, a lead or a visitor ID: every visit kept, every lead and conversion, linked.")));
  }
  if (!mayFind()) {
    return h("section", { class: "s" },
      h("div", { class: "state" }, h("div", null, "Only an admin or an owner can look a person up. Ask one of them: the search shows every visit kept, every lead and conversion, linked.")));
  }
  const field = h("input", { type: "search", class: "pp-in sa-find-in", id: "sa-find", placeholder: SEARCH_HINT, autocomplete: "off", spellcheck: "false", maxlength: "320" });
  const form = h("form", { class: "sa-find", role: "search" }, h("label", { class: "vh", for: "sa-find" }, `Find a person: ${SEARCH_HINT}`), field,
    h("button", { type: "submit", class: "btn primary" }, "Find"));
  form.addEventListener("submit", (e) => { e.preventDefault(); if (field.value.trim()) openPerson(field.value); });
  return h("section", { class: "s" },
    h("p", { class: "sub" }, "Every visit kept with the address, the last 6 hours of requests, every lead (spam, duplicates and test too) and every conversion, linked: each address, email or ID in the answer opens that person in turn."),
    form, h("p", { class: "note" }, "Each search is written to the audit log: the kind of value, never the value. The same search is in the top bar (Ctrl K, then Find a person)."));
}

export default function people(m, s) {
  const link = (words, patch) => h("a", { href: S.hashFor({ ...s, ...patch }) }, words);
  return [...tabHead("Find a person", "Who is this? Everything kept about one address, email, lead or visitor, linked.", rangeOf(m, s), { period: "Everything kept" }),
    search(),
    h("p", { class: "note" }, "Every lead of a period, with names and emails for admins and owners, is on ",
      link("Leads", { tab: "sales/leads" }), "; the test, spam and duplicate ones too (",
      link("Show left out", { tab: "sales/leads", lshow: "out" }), ").")];
}
