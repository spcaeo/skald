// "Organisation: <name> · Switch" at the top of every Settings › Organisation page, for a
// person in more than one organisation (settings-frame.js puts it there). The pages under it
// (Sites, People, Billing, Audit log) are the current site's organisation's; Switch opens the
// same page on the first site of another one. From GET orgs (orgs_api.py), asked once.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { sessions } from "../access.js";
import { DEMO } from "../demo.js";

let asked = null;
const orgs = () => (asked ||= call("orgs").then((r) => (r.ok ? r : null)));

/* For tests: forget the answer. */
export const forget = () => { asked = null; };

/* The words and the choices, from GET orgs: null when the reader is in one organisation. */
export function lineOf(r) {
  const list = (r?.orgs || []).filter((o) => o.state !== "archived" || o.id === r.current);
  if (list.length < 2) return null;
  const here = list.find((o) => o.id === r.current) || null;
  return { name: here ? here.name : "none (this site has no organisation)", others: list.filter((o) => o !== here && o.path) };
}

/* The line (empty until the answer, and for a person in one organisation). */
export function orgLine(route) {
  const box = h("div", { class: "org-line-top", hidden: true });
  if (!sessions() && !DEMO.on) return box;
  orgs().then((r) => {
    const got = lineOf(r);
    if (!got) return;
    const sel = h("select", { "aria-label": "Switch to another organisation" },
      h("option", { value: "" }, "Switch"), got.others.map((o) => h("option", { value: o.path }, o.name)));
    sel.addEventListener("change", () => { if (sel.value) location.assign(`../${sel.value}#${route}`); });
    box.replaceChildren(h("span", null, "Organisation: ", h("b", null, got.name)), ...(got.others.length ? [h("span", { class: "muted" }, " · "), sel] : []));
    box.hidden = false;
  });
  return box;
}
