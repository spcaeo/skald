// Settings › Organisation › Sites (accounts, access.mode: sessions): the
// organisation's sites, where each is defined (a config file on the server, or
// made here), and what the log endpoint has received for it. An admin adds a
// site step by step (site-wizard.js): its address, proof it is theirs, then one
// line for an AI agent and a watch as it connects, or by hand how its visits reach
// Skald, the install and a test; a set-up left half way shows
// "Finish setting up", and one that heard nothing for a day "No
// visits yet: test the connection". #settings/org/sites?setup=new|<site>&step=<n>&by=me|dev|agent&agent=<id>&link=<id>
// is the wizard open (2.21: kept while it is open, Back closes it; js/overlays.js), and ?test=<site>
// opens a site's wizard at its Test (the site picker links there). Each site's ⋯ menu
// (site-actions.js, ?sact=<act>.<site>) pauses or resumes it (owner or admin), and for
// an owner removes or restores it, clears its data, or deletes all of it, typing its
// name; removed sites are listed apart, under Removed sites. The helper behind
// <page>/sites checks role and CSRF.

import { h } from "../ui.js";
import { primary, quietLine, quietButton } from "./set-ui.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { head1, copyable, status, when, why } from "./forms.js";
import * as S from "../state.js";
import { siteWizard, STEPS } from "./site-wizard.js";
import { withCopy, withUrl } from "../urlactions.js";
import { setReload, siteMenu } from "./site-actions.js";
import { stateWords } from "./site-act-words.js";

const FORMAT_NAME = {
  auto: "Detect it", nginx_combined: "nginx (combined)", nginx_extended: "nginx (Skald's extended format)", apache_combined: "Apache (combined)",
  caddy_json: "Caddy (JSON)", cloudflare_json: "Cloudflare Logpush (JSON)", cloudfront_w3c: "CloudFront (W3C)", fastly_json: "Fastly (JSON)",
  akamai_json: "Akamai DataStream 2 (JSON)",
  vercel_json: "Vercel log drain", netlify_json: "Netlify log drain", edge_json: "Edge records (Skald Worker)",
};

// What was just made: kept in this page's memory only, so a redraw does not lose the token before it is copied.
let fresh = null;

const admin = () => ME.role === "owner" || ME.role === "admin";

function freshNote(slot) {
  if (!fresh) { slot.replaceChildren(); return; }
  const done = h("button", { type: "button", class: "btn" }, "I have copied it");
  done.addEventListener("click", () => { fresh = null; slot.replaceChildren(); });
  slot.replaceChildren(h("div", { class: "state ok acct-link", role: "status" }, h("div", null,
    h("p", null, h("strong", null, `${fresh.site}: `), "copy the token now. It is shown only this once; only a fingerprint of it is kept."),
    copyable(fresh.token, "the ingest token"),
    h("p", null, `1. On the site's server, put the token in ${fresh.token_file} (readable by root and the shipper only).`),
    h("p", null, "2. Install tools/skald-ship.py as /usr/local/bin/skald-ship and start it (docs/INGEST.md has the systemd unit):"),
    copyable(fresh.ship_command, "the shipper command"),
    fresh.tag ? h("p", null, "3. Optional, for in-page events: add this tag to the site's pages. It loads from this server and sends its events here, so the site's web server needs no change (docs/INTEGRATIONS.md).") : null,
    fresh.tag ? copyable(fresh.tag, "the script tag") : null,
    h("div", { class: "acts" }, done))));
}

// A wizard asked for by ?test=, opened once per ask.
let asked = "";
// The latest answer and its reload, for a wizard a link opens (openSiteKey).
let latest = null;

/* setup=new|<site>&step=<n>&agent=<id>&link=<id>, from a link: the Add a site wizard, for an
   owner or an admin (on Connections too: its "Set up with your AI agent" opens Connect it).
   The page's last answer, unless it does not have the site yet (one the wizard just made).
   No step in the address (the site picker's "Finish setting up"): the saved one.
   2.42: two steps (site-wizard.js); by= is who connects it, and pick asks which AI agent. */
export async function openSiteKey(value, step = 0, s = {}) {
  if (!sessions() || !admin()) return "Not available to your role.";
  const has = (d) => d?.sites && (value === "new" || d.sites.some((x) => x.name === value));
  const r = has(latest?.data) ? latest.data : await call("sites");
  if (!r.ok && !r.sites) return why(r, "The sites could not be loaded, so the wizard cannot open. Open this page again in a minute.");
  const reload = location.hash.includes("settings/org/sites") && latest?.reload || (() => {});
  if (value === "new") return r.can_add ? siteWizard({ data: r, onChange: reload, agent: s.agent || "", by: s.by || "" }) : "Adding a site is not open to this organisation now.";
  const site = (r.sites || []).find((x) => x.name === value);
  if (!site) return "That site is not one of this organisation's sites.";
  // pick: Connections' "Set up with your AI agent" asks which agent, whatever way was saved.
  const at = step || (site.setup && !site.setup.done && site.setup.step) || 1;
  return siteWizard({ data: r, name: site.name, start: Math.max(0, Math.min(STEPS, at) - 1), method: s.pick ? "" : site.setup?.method || "", verify: site.verify,
    found: site.setup?.found || null, onChange: reload, agent: s.pick ? "" : s.agent || "", link: s.link || "", by: s.pick ? "agent" : s.by || "" });
}

export default function sitesadmin(m, s = {}) {
  const title = head1("Add or remove sites", ME.org ? `The sites ${ME.org} reports on.` : "The sites this organisation reports on.");
  if (!sessions()) {
    return [title, h("div", { class: "state" }, h("div", null, "Adding sites here comes with accounts. On this server, sites are listed in the config file."))];
  }
  const box = h("div", { class: "acct" }, h("p", { class: "empty" }, "Loading the sites..."));
  const msg = status();
  const slot = h("div");
  const reload = () => call("sites").then(draw);

  let data = {};
  function draw(r) {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The sites could not be loaded.")))); return; }
    data = r;
    latest = { data: r, reload };
    setReload(reload);
    const all = r.sites || [];
    box.replaceChildren(...[table(all.filter((x) => x.status !== "removed")), removedBox(all.filter((x) => x.status === "removed")),
      pendingBox(all), addForm(r)].flat().filter(Boolean));
    openAsked(r);
  }

  // Removed sites: their data is kept; an owner restores one (or deletes its data) from its menu.
  function removedBox(list) {
    if (!list.length) return h("div");
    return h("section", { class: "s" }, h("h2", null, "Removed sites"),
      h("p", { class: "sub" }, "Nothing is collected for these sites and they are hidden from the dashboard. Their data is kept until an owner deletes it."),
      h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Removed sites"),
        h("thead", null, h("tr", null, ["Site", "Defined in", "State"].map((t) => h("th", { scope: "col" }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Actions")))),
        h("tbody", null, list.map((s) => h("tr", null, h("td", { class: "path nm" }, withCopy(h("span", null, s.name), s.name)),
          h("td", null, s.source === "dashboard" ? "these pages" : "config file"), h("td", null, stateWords(s)),
          h("td", { class: "n" }, siteMenu(s))))))));
  }

  // The wizard for a site: from its saved step, or at the Test (step 5).
  function resume(site, test = false) {
    const step = test ? STEPS : Math.max(1, Math.min(STEPS, site.setup?.step || 1));
    siteWizard({ data, name: site.name, start: step - 1, method: site.setup?.method || "", verify: site.verify, found: site.setup?.found || null, onChange: reload });
  }
  // ?test=<site>: its wizard at the Test, which then names itself (setup=<site>&step=5).
  // ?setup= is the router's (js/overlays.js -> openSiteKey).
  function openAsked(r) {
    const want = s.test ? `test:${s.test}` : "";
    if (!want || want === asked || !admin()) return;
    asked = want;
    S.set({ test: "" }, { replace: true });
    const site = (r.sites || []).find((x) => x.name === s.test);
    if (site) resume(site, true);
  }
  function setupCell(site) {
    if (!admin() || site.status !== "active") return "";
    if (site.setup && !site.setup.done) {
      const b = h("button", { type: "button", class: "btn cn-badge" }, "Finish setting up");
      b.addEventListener("click", () => resume(site));
      return b;
    }
    if (site.quiet) {
      const b = h("button", { type: "button", class: "btn cn-badge warn" }, "No visits yet: test the connection");
      b.addEventListener("click", () => resume(site, true));
      return b;
    }
    return "";
  }

  // A site waiting for its domain to be verified collects nothing (site_verify.py).
  const waiting = (s) => s.verify && s.verify.state === "pending";

  function pendingBox(list) {
    const rows = list.filter((s) => waiting(s) && s.status === "active");
    if (!rows.length) return h("div");
    return h("section", { class: "s" }, h("h2", null, "Verify your domain"),
      h("p", { class: "sub" }, "Nothing is collected for these sites until you show the domain is yours: add the DNS TXT record, or put the meta tag in the home page's <head>, then press Verify."),
      ...rows.map((s) => {
        const go = h("button", { type: "button", class: "btn primary", "aria-label": `Verify ${s.name}` }, "Verify");
        go.addEventListener("click", async () => {
          go.disabled = true;
          const r = await call("sites/verify", { name: s.name });
          go.disabled = false;
          if (!r.ok) { msg.say(why(r, "The domain could not be verified yet.")); return; }
          msg.say(`${s.name} is verified. Skald collects for it from now on.`, true);
          reload();
        });
        return h("div", { class: "sheet" }, h("p", null, h("strong", null, s.name)),
          h("p", null, `A TXT record on ${s.name}:`), copyable(s.verify.txt, "the TXT record"),
          h("p", null, `or this tag on https://${s.name}/:`), copyable(s.verify.meta, "the meta tag"),
          admin() ? h("div", { class: "acts" }, go) : h("p", { class: "note" }, "An admin presses Verify."));
      }));
  }

  function received(s) {
    const g = s.ingest;
    if (!g || !g.batches) return s.source === "dashboard" ? "nothing yet" : "";
    return `${g.accepted.toLocaleString("en-GB")} lines kept, ${g.rejected.toLocaleString("en-GB")} refused; last ${when(g.last_at)}`;
  }

  function actions(s, cell) {
    const draw1 = () => {
      const parts = [];
      if (admin() && s.status !== "removed") {
        const tok = h("button", { type: "button", class: "btn", "aria-label": `A new ingest token for ${s.name}` }, "New token");
        tok.addEventListener("click", async () => {
          tok.disabled = true;
          const r = await call("sites/token", { name: s.name });
          tok.disabled = false;
          if (!r.ok) { msg.say(why(r)); return; }
          fresh = { site: s.name, token: r.token, ship_command: r.ship_command, token_file: r.token_file };
          freshNote(slot);
          msg.say("");
        });
        parts.push(tok);
      }
      // Pause/Resume, Remove/Restore, Clear data, Delete all data (js/tabs/site-actions.js).
      parts.push(siteMenu(s));
      cell.replaceChildren(...parts);
    };
    draw1();
  }

  function table(list) {
    if (!list.length) return h("section", { class: "s" }, h("h2", null, "Sites"), h("p", { class: "empty" }, "No sites yet."));
    return h("section", { class: "s" }, h("h2", null, "Sites"),
      h("p", { class: "sub" }, "A site from the server's config file is changed there. A site made here gets its log through the shipper. Each row's menu pauses a site (nothing is deleted), removes it, or deletes its data."),
      h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Sites"),
        h("thead", null, h("tr", null, ["Site", "Defined in", "State", "Log format", "Log received"].map((t) => h("th", { scope: "col" }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Actions")))),
        h("tbody", null, list.map((s) => {
          const cell = h("td", { class: "n" });
          actions(s, cell);
          return h("tr", null, h("td", { class: "path nm" }, withUrl(h("span", null, s.name), /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(s.name || "") ? `https://${s.name}` : "", { label: s.name, cls: "ua-after" }), h("div", null, setupCell(s))), h("td", null, s.source === "dashboard" ? "these pages" : "config file"),
            h("td", null, stateWords(s, waiting(s))),
            h("td", { class: "muted" }, s.format ? FORMAT_NAME[s.format] || s.format : ""), h("td", { class: "muted" }, received(s)), cell);
        })))));
  }

  function addForm(r) {
    if (!admin()) return h("section", { class: "s" }, h("h2", null, "Add a site"), h("p", { class: "note" }, "Only an admin can add a site."));
    if (!r.can_add) return h("section", { class: "s" }, h("h2", null, "Add a site"), h("p", { class: "note" }, r.add_refused || "Adding sites is not available here."));
    // v2: the page's one primary (beside the title); several sites at once, one quiet line.
    const go = primary("Add a site", () => siteWizard({ data: r, onChange: reload }));
    // 2.40: every site its own line for its AI agent, and several new sites at once (agent-many.js).
    const lines = quietButton("Set up many sites with your AI agent", async () => (await import("./agent-many.js")).openLines());
    return [go, quietLine("Many sites at once", "One line for your AI agent sets up each of them.", lines)];
  }

  freshNote(slot);
  reload();
  return [title, slot, box, msg];
}
