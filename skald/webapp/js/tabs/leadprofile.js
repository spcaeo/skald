// A lead's profile in its drawer (#31): Leads & sales > Leads, a row opens the visitor drawer
// (sa-leads.js openLead); for owners and admins (person.js mayFind) this adds "Their profile":
// who, everything they did with its time and value, and their visits in order, each proven
// or likely (person.js profileParts). Everyone else sees the drawer as before.
//
// Asked on demand, by the lead's own reference, the same question Find a person asks
// (people?q=<reference>: written to the audit log, never the value). The drawer is already
// in the address by its row (lead=<id>), so a link opens the profile again; the reference
// itself never goes in a link. One answer per reference for 5 minutes.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { mayFind, profileParts } from "./person.js";
import { fold } from "../ui/fold.js";

const asked = new Map();
export function askPerson(ref) {
  const url = `people?q=${encodeURIComponent(ref)}`;
  const kept = asked.get(url);
  if (kept && Date.now() - kept.at < 300000) return kept.p;
  const p = call(url).catch((e) => ({ ok: false, error: String(e?.message || e) }));
  asked.set(url, { at: Date.now(), p });
  p.then((r) => { if (!r?.ok) asked.delete(url); });
  return p;
}

/* Adds the profile to an open lead drawer `d` (openDrawer's handle) for the lead row `x`.
   Kept on d.profile so a redraw of the drawer (Show all) keeps it (visitor.js draw). */
export async function leadProfile(d, x) {
  if (!d?.body || !x?.ref || !mayFind()) return null;
  const inner = h("div", { class: "lp-prof" }, h("p", { class: "empty" }, "Looking in everything kept…"));
  const box = fold("Their profile", [inner], { open: true, cls: "vz-more" });
  d.profile = box;
  d.body.append(box);
  const got = await askPerson(String(x.ref));
  if (!d.el?.isConnected) return d;
  inner.replaceChildren(...(got?.ok ? [...profileParts(got),
    h("p", { class: "note" }, "Found by the lead's reference, as Find a person finds it: written to the audit log (never the value).")]
    : [h("p", { class: "note" }, got?.status === 403 ? "Not available to your role." : got?.error || "The profile could not be read just now.")]));
  return d;
}
