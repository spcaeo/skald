// Settings > Add or remove sites (accounts, access.mode: sessions): the
// organisation's sites, where each is defined (a config file on the server, or
// made here), and what the log endpoint has received for it. An admin adds a
// site: it gets a log folder and an ingest token, shown once, with the command
// that ships the server's log and the skald.js tag. An owner removes a site made
// here, typing its name: processing stops, the data stays until an install admin
// purges it on the server. The helper behind <page>/sites checks role and CSRF.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { head1, copyable, field, input, status, when, why } from "./forms.js";

const FORMAT_NAME = {
  auto: "Detect it", nginx_combined: "nginx (combined)", nginx_extended: "nginx (Skald's extended format)", apache_combined: "Apache (combined)",
  caddy_json: "Caddy (JSON)", cloudflare_json: "Cloudflare Logpush (JSON)", cloudfront_w3c: "CloudFront (W3C)", fastly_json: "Fastly (JSON)",
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
    fresh.tag ? h("p", null, "3. Optional, for in-page events: add this tag to the site's pages (docs/INTEGRATIONS.md).") : null,
    fresh.tag ? copyable(fresh.tag, "the script tag") : null,
    h("div", { class: "acts" }, done))));
}

export default function sitesadmin() {
  const title = head1("Add or remove sites", ME.org ? `The sites ${ME.org} reports on.` : "The sites this organisation reports on.");
  if (!sessions()) {
    return [title, h("div", { class: "state" }, h("div", null, "Adding sites here comes with accounts. On this server, sites are listed in the config file."))];
  }
  const box = h("div", { class: "acct" }, h("p", { class: "empty" }, "Loading the sites..."));
  const msg = status();
  const slot = h("div");
  const reload = () => call("sites").then(draw);

  function draw(r) {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The sites could not be loaded.")))); return; }
    box.replaceChildren(table(r.sites || []), pendingBox(r.sites || []), addForm(r));
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
      if (admin() && s.status === "active") {
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
      if (ME.role === "owner" && s.source === "dashboard" && s.status === "active") {
        const rm = h("button", { type: "button", class: "btn danger", "aria-label": `Remove ${s.name}` }, "Remove");
        rm.addEventListener("click", () => confirmRemove(s, cell, draw1));
        parts.push(rm);
      }
      cell.replaceChildren(...parts);
    };
    draw1();
  }

  function confirmRemove(s, cell, back) {
    const typed = input({ name: "confirm", autocomplete: "off", placeholder: s.name, "aria-label": `Type ${s.name} to confirm` });
    const yes = h("button", { type: "button", class: "btn danger" }, "Remove the site");
    const no = h("button", { type: "button", class: "btn" }, "Keep it");
    cell.replaceChildren(h("span", { class: "confirm" }, `Processing of ${s.name} stops. Its figures stay until an install admin purges them. Type its name:`, typed, yes, no));
    typed.focus();
    no.addEventListener("click", back);
    yes.addEventListener("click", async () => {
      if (typed.value.trim() !== s.name) { msg.say(`Type ${s.name} exactly to confirm.`); typed.focus(); return; }
      yes.disabled = true; no.disabled = true;
      const r = await call("sites/remove", { name: s.name, confirm: typed.value.trim() });
      if (!r.ok) { msg.say(why(r)); back(); return; }
      msg.say(`${s.name} is removed. Its data stays on the server until it is purged.`, true);
      reload();
    });
  }

  function table(list) {
    if (!list.length) return h("section", { class: "s" }, h("h2", null, "Sites"), h("p", { class: "empty" }, "No sites yet."));
    return h("section", { class: "s" }, h("h2", null, "Sites"),
      h("p", { class: "sub" }, "A site from the server's config file is changed there. A site made here gets its log through the shipper."),
      h("div", { class: "scroll" }, h("table", { class: "rows-mid" }, h("caption", { class: "vh" }, "Sites"),
        h("thead", null, h("tr", null, ["Site", "Defined in", "State", "Log format", "Log received"].map((t) => h("th", { scope: "col" }, t)), h("th", { scope: "col", class: "n" }, h("span", { class: "vh" }, "Actions")))),
        h("tbody", null, list.map((s) => {
          const cell = h("td", { class: "n" });
          actions(s, cell);
          return h("tr", null, h("td", { class: "path nm" }, s.name), h("td", null, s.source === "dashboard" ? "these pages" : "config file"),
            h("td", null, s.status === "removed" ? `removed ${when(s.removed_at, "")}` : waiting(s) ? "waiting for verification" : "active"),
            h("td", { class: "muted" }, s.format ? FORMAT_NAME[s.format] || s.format : ""), h("td", { class: "muted" }, received(s)), cell);
        })))));
  }

  function addForm(r) {
    if (!admin()) return h("section", { class: "s" }, h("h2", null, "Add a site"), h("p", { class: "note" }, "Only an admin can add a site."));
    if (!r.can_add) return h("section", { class: "s" }, h("h2", null, "Add a site"), h("p", { class: "note" }, r.add_refused || "Adding sites is not available here."));
    const host = input({ name: "host", autocomplete: "off", required: true, placeholder: "shop.example.com", maxlength: "100" });
    const zone = input({ name: "timezone", autocomplete: "off", placeholder: "UTC", maxlength: "64" });
    const fmt = h("select", { name: "format" }, (r.formats || ["auto"]).map((f) => h("option", { value: f }, FORMAT_NAME[f] || f)));
    const make = h("button", { type: "submit", class: "btn primary" }, "Add site");
    const form = h("form", { class: "af-col", novalidate: true },
      field("Host name", host, "The site's address without https://. It is also the site's name here."),
      field("Time zone", zone, "Days are counted in this zone, like Europe/London. Empty: UTC."),
      field("Log format", fmt, "The web server writing the log. Lines in another format are refused and counted."),
      h("div", null, make));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = host.value.trim().toLowerCase();
      if (!/^[a-z0-9.-]+\.[a-z0-9-]+$/.test(name)) { msg.say("Type a host name, like shop.example.com."); host.focus(); return; }
      make.disabled = true;
      const res = await call("sites/add", { host: name, timezone: zone.value.trim(), format: fmt.value });
      make.disabled = false;
      if (!res.ok || !res.token) { msg.say(why(res, "The site was not added.")); return; }
      fresh = { site: res.site, token: res.token, ship_command: res.ship_command, token_file: res.token_file, tag: res.tag };
      host.value = ""; zone.value = "";
      msg.say(`${res.site} is added. Its page is ready now (choose it in the site menu); figures appear once its log lines arrive.`, true);
      freshNote(slot);
      reload();
    });
    return h("section", { class: "s" }, h("h2", null, "Add a site"),
      h("p", { class: "sub" }, "The site's own server sends its access log here with a small program, skald-ship. Nothing is read from the site itself."),
      h("div", { class: "sheet" }, form));
  }

  freshNote(slot);
  reload();
  return [title, slot, box, msg];
}
