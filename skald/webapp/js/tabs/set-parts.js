// Settings v2: a card of settings (GET <page>/settings, prefs.js) as rows: each setting's
// name, its value in words and where it comes from, a pill for what is on or off, set or
// not. A row opens the card's form in its drawer (edit=<id>, set-edit.js). No form on the
// page itself: the page answers "what is set", the drawer changes it.

import { rowsCard, statusRow } from "./set-ui.js";
import { openEdit } from "./set-edit.js";

const FROM = { site: "this site", org: "the organisation", install: "the whole install", config: "config.yml", default: "the default", upgrade: "kept off by the upgrade to 2.4.0" };
const IP = { full: "Full address", short: "Shortened (last part removed)", off: "Not kept" };
const DAYS = /days|retention/;
const list = (v, none) => (Array.isArray(v) && v.length ? v.join(", ") : none);

/* One setting's value: { text, kind, word } (a pill only for on/off and set/not set). */
export function valueOf(name, s) {
  if (!s) return { text: "" };
  if (s.hidden) return { text: "Shown to install admins only" };
  const v = s.value;
  switch (s.kind) {
    case "secret": return s.set ? { text: s.env ? "The server's environment also sets it" : "", kind: "good", word: "Set" } : { text: "", kind: "off", word: "Not set" };
    case "bool": return v ? { text: "", kind: "good", word: "On" } : { text: "", kind: "off", word: "Off" };
    case "ipmode": return { text: IP[v === true ? "full" : v === false ? "off" : v || "full"] || String(v) };
    case "events": return { text: list(v, "No goal chosen") };
    case "notpages": {
      const all = (s.entries || []).length, back = (v || []).length;
      return { text: back ? `${all - back} of ${all} left out of pages` : `All ${all} left out of pages` };
    }
    case "views": return { text: list((v || []).map((x) => x.name), "No page group") };
    case "emails": case "hosts": case "prefixes": case "pagepatterns": return { text: list(v, "None") };
    case "postpaths": {
      // site.script_posts (form_names.py): the site's own list; a suggestion waiting is said on the row.
      const k = (s.suggested || []).length;
      return { text: [list(v, "None of your own"), k ? `${k} suggested` : ""].filter(Boolean).join(" · "), kind: k ? "warn" : undefined, word: k ? "Suggested" : undefined };
    }
    case "choice": return { text: v || (name === "mail.smtp.security" ? "From the port" : "The default") };
    case "int":
      if (s.forever && v === 0) return { text: "Kept for good" };
      return { text: v == null || v === "" ? "Not set" : `${v}${DAYS.test(name) ? " days" : ""}` };
    default: return { text: v == null || v === "" ? "Not set" : String(v) };
  }
}

/* The row of one setting: its name, value and source; it opens the card's drawer. */
function settingRow(id, name, s, m) {
  const v = valueOf(name, s);
  const from = s.hidden ? "" : !s.editable ? "read-only" : FROM[s.source] || "";
  const line = [v.text, from].filter(Boolean).join(" · ");
  return statusRow({ iconName: "", title: s.label, line, kind: v.kind, word: v.word, label: `${s.label}: ${v.word || v.text}. Change it`, onOpen: () => openEdit(id, m) });
}

/* A card of settings as rows; null when the answer holds none of them. */
export function partCard(id, title, names, all, m, { help = null, extra = [] } = {}) {
  const have = names.filter((k) => all[k]);
  if (!have.length) return null;
  // Nothing here this reader may change (the whole install's, or a viewer): one line, not a row
  // each; the drawer shows each value and why.
  const fixed = have.every((k) => all[k].hidden || !all[k].editable);
  const why = have.map((k) => all[k].reason).find(Boolean) || "You cannot change these here.";
  const rows = fixed ? [statusRow({ iconName: "", title: `${have.length} setting${have.length === 1 ? "" : "s"}`, line: why,
    kind: "off", word: "Read-only", label: `${title}: read-only. See the settings`, onOpen: () => openEdit(id, m) })] : have.map((k) => settingRow(id, k, all[k], m));
  const c = rowsCard(title, [...rows, ...extra], { help });
  c.setAttribute("data-part", id);
  return c;
}
