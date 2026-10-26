// What the agent recommends (2.39), on the watch step (agent-watch.js): the report's page
// assets and privacy answers, in plain words, each with Apply. Apply makes the same save
// as the by-hand dialog (POST settings/save): page assets as "Count visits as people"
// (setup-dialogs.js assetsDialog: site.asset_prefixes, and site.require_rendering back on
// when it was off), IP addresses as "Choose what is kept" (setup-privacy.js:
// privacy.keep_ips; the report's days as privacy.keep_days). Nothing is applied without the
// press: a leaked code must never change what Skald keeps. The settings are the report's
// site's own (GET <that site's page>/settings), so a new site's are not the page's.
// 2.40: a Search Console property is "Connect it" (POST integrations/search/connect, as
// Settings > Leads & integrations > Search Console & Bing does, with all 16 months of history).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { withCopy } from "../urlactions.js";
import { noticeBox } from "./setup-privacy.js";
import { newAssets, ASSETS_MAX } from "./agent-words.js";

// The page's own site (/traffic/<site>/...): a call for another site goes to that site's page.
const pageSite = () => { try { return decodeURIComponent((location.pathname.match(/^\/traffic\/([^/]+)\//) || [])[1] || ""); } catch { return ""; } };
export const siteCall = (site, path, body) => call(site && pageSite() && site !== pageSite() ? `/traffic/${encodeURIComponent(site)}/${path}` : path, body);

/* The page-assets save a report suggests, or null: nothing new, or not editable here. */
export function assetsSave(report, settings) {
  const cur = settings?.["site.asset_prefixes"];
  if (!cur || cur.editable === false) return null;
  const paths = newAssets(report, cur.value);
  if (!paths.length) return null;
  return { "site.asset_prefixes": paths, ...(settings["site.require_rendering"]?.value === false ? { "site.require_rendering": true } : {}) };
}

// full, short or off (2.15.0); true and false from an older answer.
const modeOf = (v) => (v === true ? "full" : v === false || !v ? "off" : v);
const MODE_WORDS = { full: "full IP addresses are kept", short: "shortened IP addresses are kept", off: "no IP address is kept" };

/* The privacy save a report suggests, or null. Kept or not is the report's choice (true:
   keep them in full; a site that keeps them shortened keeps doing so); the IP choice is
   sent while it is still the default, so it counts as chosen, as the by-hand dialog does. */
export function privacySave(privacy, settings) {
  const p = privacy || {};
  const ips = settings?.["privacy.keep_ips"];
  if (typeof p.keep_ips !== "boolean" || !ips || ips.editable === false) return null;
  const now = modeOf(ips.value);
  const body = {};
  if ((now !== "off") !== p.keep_ips || !ips.source || ips.source === "default") body["privacy.keep_ips"] = p.keep_ips ? (now === "off" ? "full" : now) : "off";
  const days = settings["privacy.keep_days"];
  if (p.keep_ips && Number.isInteger(p.days) && p.days >= 1 && p.days <= 3650 && days && days.editable !== false && days.value !== p.days) body["privacy.keep_days"] = p.days;
  return Object.keys(body).length ? body : null;
}

/* The Search Console connect a report suggests, or null: none, or the one connected already. */
export function searchSave(report, settings) {
  const prop = String(report?.search?.google_property || "").trim();
  if (!prop || !settings) return null;
  if (settings["search.google_property"]?.value === prop) return null;
  return { engine: "google", source: prop, backfill_months: 16 };
}

/* One recommendation: its words, Apply, and what the save said. after(r): nodes shown once saved.
   path: the save (settings/save, or integrations/search/connect with the site). */
function rec(site, { kind, head, says, body, done, after = null, path = "settings/save" }) {
  const btn = h("button", { type: "button", class: "btn primary", "aria-label": `Apply: ${head}` }, "Apply");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  const more = h("div");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const r = await siteCall(site, path, body);
    btn.disabled = false;
    said.className = `msg ${r.ok ? "ok" : "err"}`;
    said.textContent = r.ok ? done : why(r, "It was not saved.");
    if (!r.ok) return;
    btn.hidden = true;
    if (after) more.replaceChildren(...[].concat(after(r) || []));
  });
  return h("div", { class: "ag-rec", "data-rec": kind }, h("p", null, h("b", null, head)), ...says, h("div", { class: "acts" }, btn), said, more);
}

/* The recommendations box for a report: empty when it suggests nothing new. */
export function recsBox(report, site) {
  const box = h("div", { class: "ag-recs-w" });
  const r = report || {};
  if (!r.asset_paths?.length && typeof r.privacy?.keep_ips !== "boolean" && !r.search?.google_property) return box;
  siteCall(site, "settings").then((now) => {
    if (!now.ok || !now.settings) return;
    const s = now.settings;
    const recs = [];
    const assets = assetsSave(r, s);
    if (assets) {
      const paths = assets["site.asset_prefixes"];
      const cur = s["site.asset_prefixes"]?.value || [];
      const many = r.asset_paths.length > ASSETS_MAX ? ` Skald keeps at most ${ASSETS_MAX}: these are the first ${ASSETS_MAX}.` : "";
      recs.push(rec(site, { kind: "assets", head: "Count visits as people with these page assets", body: assets,
        says: [h("p", null, "The pages load their own files from:"),
          h("ul", { class: "ag-paths" }, paths.map((p) => h("li", null, withCopy(h("code", null, p), p, { cls: "ua-after", label: `the folder ${p}` })))),
          h("p", { class: "note" }, `The agent found other page assets than ${site} has now (${cur.join(", ") || "none"}).${many}`)],
        done: `Saved: ${site} counts pages that load ${paths.join(", ")}.` }));
    }
    const privacy = privacySave(r.privacy, s);
    if (privacy) {
      const keep = r.privacy.keep_ips;
      const days = privacy["privacy.keep_days"] || (keep && Number.isInteger(r.privacy.days) && r.privacy.days > 0 ? r.privacy.days : 0);
      const ips = s["privacy.keep_ips"];
      recs.push(rec(site, { kind: "privacy", head: keep ? `Keep visitors' IP addresses${days ? ` for ${days} days` : ""}` : "Keep no IP addresses", body: privacy,
        says: [h("p", null, "Your agent read the site's privacy notice and suggests this."),
          h("p", { class: "note" }, `Now: ${MODE_WORDS[modeOf(ips.value)]}${!ips.source || ips.source === "default" ? " (not chosen yet)" : ""}.`)],
        done: "Saved. Copy this wording into your privacy notice.", after: (got) => (got.notice ? [noticeBox(got.notice)] : []) }));
    }
    const search = searchSave(r, s);
    if (search) {
      recs.push(rec(site, { kind: "search", head: `Connect Google Search Console: ${search.source}`, body: { site, ...search }, path: "integrations/search/connect",
        says: [h("p", null, "Your agent found the site's Search Console property."),
          h("p", { class: "note" }, r.search.robot_added === true ? "It says Skald's robot address was added as a user there." : "Add Skald's robot address as a Restricted user there first (Settings > Leads & integrations > Search Console & Bing shows it), or the connect is refused.")],
        done: "Connected. Skald syncs its figures in the background: the last 16 months first." }));
    }
    if (!recs.length) return;
    box.replaceChildren(h("section", { class: "ag-recs", "aria-label": "What your agent recommends" }, h("h4", null, "What your agent recommends"),
      h("p", { class: "note" }, "Skald changes nothing until you press Apply."), ...recs));
  });
  return box;
}
