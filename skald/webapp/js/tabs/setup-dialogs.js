// The "Set up this site" checklist's Set up buttons (checklist.js): one short
// guided dialog per open line, in the same wizard as Settings > Connections
// (conn-ui.js). This file opens the right one, and holds the three small ones:
//
//   logs       Settings > Connections' "Send this site's visits" (conn-send.js),
//              with GET sites' answer
//   assets     where the pages load their own files: GET settings, then
//              POST settings/save site.asset_prefixes (or site.require_rendering)
//   countries  a country file on the server: what it adds, and a mail to the
//              server admin (nothing to save here)
//   pack       "Send set-up to someone" at the top of the checklist (2.30): the
//              whole set-up in one zip, mailed or saved (setup-pack.js)
//
// The others: setup-tag.js (the script tag), setup-hook.js (a lead hook),
// setup-mail.js (the daily and weekly mail), setup-privacy.js (what is kept),
// setup-nextjs.js (rsc: the log_format line that counts pages opened inside a
// Next.js site).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { wizard, helpLink } from "./conn-ui.js";
import { DEMO } from "../demo.js";
import { ME, sessions } from "../access.js";
import { sendDialog } from "./conn-send.js";
import { adminFold, choices, loading, mailButton, copyButton } from "./setup-common.js";
import { tagDialog } from "./setup-tag.js";
import { hookDialog } from "./setup-hook.js";
import { mailDialog } from "./setup-mail.js";
import { privacyDialog } from "./setup-privacy.js";
import { nextDialog } from "./setup-nextjs.js";
import { packBox } from "./setup-pack.js";

// Each dialog is in the address as setup=<act>&step=<n> (js/overlays.js); start: a link's step, 0 first.
export const ACTS = ["logs", "assets", "rsc", "countries", "script", "lead", "mail", "privacy", "pack"];
export async function openSetup(act, site, { item = null, onClose = null, start = 0 } = {}) {
  const opts = { item, onClose, route: { key: "setup", value: act }, start };
  if (act === "logs") {
    const r = await call("sites");
    return sendDialog(site, r.ok ? r : {}, opts);
  }
  if (act === "assets") return assetsDialog(site, opts);
  if (act === "rsc") return nextDialog(site, opts);
  if (act === "countries") return countriesDialog(site, opts);
  if (act === "script") return tagDialog(site, opts);
  if (act === "lead") return hookDialog(site, opts);
  if (act === "mail") return mailDialog(site, opts);
  if (act === "privacy") return privacyDialog(site, opts);
  if (act === "pack") return packDialog(site, opts);
  return null;
}

// "Send set-up to someone": the box alone, with the keys this page made (setup-pack.js).
export function packDialog(site, { onClose = null, route = null, start = 0 } = {}) {
  return wizard({ route, start,
    title: "Send set-up to someone", subtitle: `For ${site}. Logs, the script tag and leads, in one zip.`, key: "setup-pack", onClose, done: "Close",
    steps: [{ name: "Send or download", draw: () => [packBox(site)] }] });
}

/* setup=<act>&step=<n>, from a link: the dialog at that step for an owner or an admin;
   the line, for anyone else. The checklists on the page ask again when it closes. */
export async function openSetupKey(act, m, step = 1) {
  if (!ACTS.includes(act)) return "That set-up step is not in this version of the page.";
  if (DEMO.on) return "Setting up needs a running Skald: not available in the demo.";
  if (!sessions() || !(["owner", "admin"].includes(ME.role) || ME.install_admin)) return "Not available to your role.";
  const { itemFor, refreshChecklists } = await import("./checklist.js");
  const item = await itemFor(m, act);
  return openSetup(act, m.site, { item, start: Math.max(0, step - 1), onClose: refreshChecklists });
}

// ------------------------------------------------- visits count as people

const BUILT = [
  { id: "next", title: "Next.js", sub: "Its pages load their files from /_next/static/.", paths: ["/_next/static/"] },
  { id: "wordpress", title: "WordPress", sub: "Its pages load their files from /wp-content/ and /wp-includes/.", paths: ["/wp-content/", "/wp-includes/"] },
  { id: "other", title: "Something else", sub: "Type the folders its pages load their scripts and styles from. Many sites use /assets/ or /static/." },
  { id: "cdn", title: "Its scripts and styles come from another address (a CDN)", sub: "Then this server's log never sees them, so every browser visit is counted instead." },
];
const pathsOf = (text) => String(text || "").split(/[\s,]+/).filter((p) => p.startsWith("/"));

export function assetsDialog(site, { item = null, onClose = null, route = null, start = 0 } = {}) {
  const st = { kind: "", custom: "/assets/\n/static/", r: null };
  const load = () => (st.r ? Promise.resolve(st.r) : call("settings").then((r) => { st.r = r; return r; }));
  const box = (w) => {
    const area = h("textarea", { rows: "3", spellcheck: "false", "aria-label": "The folders, one per line" });
    area.value = st.custom;
    area.addEventListener("input", () => { st.custom = area.value; });
    const other = h("div", { hidden: st.kind !== "other" }, area, h("p", { class: "note" }, "One folder per line, at most 10. Each starts with /."));
    return [choices(st, "kind", BUILT, "What is the site built with?", (id) => { other.hidden = id !== "other"; w.say(""); }), other];
  };
  return wizard({ route, start,
    title: "Count visits as people", subtitle: `For ${site}.`, key: "setup-assets", onClose, state: st,
    steps: [
      { name: "What the site is built with",
        draw: (w) => [h("p", null, "A visit counts as a person only when the browser also loads the page's own scripts or styles. Robots skip them. Tell Skald where your pages keep those files."),
          loading("Loading the site's settings...", load, (r) => {
            const s = r.ok ? r.settings?.["site.asset_prefixes"] : null;
            if (!r.ok) return h("p", { class: "msg err" }, why(r, "The settings could not be loaded."));
            if (s && !s.editable) return h("p", { class: "msg err" }, s.reason || "You cannot change this.");
            return [s?.value?.length ? h("p", { class: "note" }, `Now: ${s.value.join(", ")}.`) : null, ...box(w)];
          })],
        check: () => (!st.kind ? "Choose what the site is built with." : st.kind === "other" && !pathsOf(st.custom).length ? "Type at least one folder, starting with /." : ""),
        next: async (w) => {
          const was = st.r?.settings?.["site.require_rendering"]?.value;
          const body = st.kind === "cdn" ? { "site.require_rendering": false }
            : { "site.asset_prefixes": st.kind === "other" ? pathsOf(st.custom).slice(0, 10) : BUILT.find((b) => b.id === st.kind).paths, ...(was === false ? { "site.require_rendering": true } : {}) };
          const r = await call("settings/save", body);
          if (!r.ok) { w.say(why(r, "It was not saved.")); return false; }
          st.r = { ...st.r, settings: r.settings };
          return true;
        } },
      { name: "Done",
        draw: () => [h("div", { class: "state ok", role: "status" }, h("div", null, h("p", null, h("strong", null, "Saved. "), "It applies from the next daily run, each morning. This line ticks itself once the server sees browsers load those files."))),
          h("p", { class: "note" }, "You can change it later in Settings > Sites > Page assets."),
          adminFold([...(item?.tech ? [h("p", null, item.tech)] : []), h("p", null, "Days already stored are not counted again. To recount them, run backfill --force on the server.")])] },
    ],
  });
}

// ---------------------------------------------------------- countries

function countryMail(site) {
  return ["Hello,", "",
    `Skald shows no country for the visits of ${site}: the server's access log carries none.`,
    "Could you give Skald a GeoIP country file? DB-IP's free country file works.",
    "- Docker: keep the file on the host (for example in /usr/share/GeoIP) and add -v /usr/share/GeoIP:/geoip:ro -e SKALD_COUNTRY_DB=/geoip/dbip-country-lite.mmdb",
    "- Without Docker: set logs.country_db in Skald's config to the file's path.",
    "Refresh the file once a month. Skald reads the new file by itself, with no restart.",
    "", "Thank you."].join("\n");
}

export function countriesDialog(site, { item = null, onClose = null, route = null, start = 0 } = {}) {
  return wizard({ route, start,
    title: "Show each visit's country", subtitle: `For ${site}.`, key: "setup-countries", onClose,
    steps: [
      { name: "What it adds",
        draw: () => [h("p", null, "Each visit's country, on Traffic, on Overview and in the mails."),
          h("p", null, "Your server's log does not carry a country. A free country file on Skald's server adds it. Skald never guesses: without the file, the country stays Not recorded."),
          h("p", { class: "note" }, "Only the person who runs your Skald server can add the file. The next step writes the mail for them."),
          helpLink("faq", "Why do my countries say Not recorded?")] },
      { name: "Ask your server admin",
        draw: () => [h("p", null, "Send them this. Nothing else is needed from you."),
          h("div", { class: "acts" }, mailButton("Send this to your server admin", { subject: `Countries for ${site} in Skald`, body: countryMail(site) }), copyButton("Copy the text", countryMail(site), "the text")),
          adminFold(item?.tech || null)] },
    ],
  });
}
