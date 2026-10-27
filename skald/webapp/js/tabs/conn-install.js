// Settings > Data > Send logs, "Send this site's visits to Skald", step Install:
// the exact steps for each way, with the send address filled in, and the
// fresh sending token when there is one (else a clear <token>). Every command
// has a Copy button. For the shippers, the install kit built by the helper
// (POST <page>/sites/kit, skald/kit): for the server way (2.30) one file,
// skald-install-<site>.sh, with or without Docker; the older Docker and system
// service kits (.zip) stay under "Other ways" (byHandFold). The steps follow
// docs/INGEST.md, docs/VERCEL.md, docs/HOSTING.md, deploy/cloudflare-worker
// and deployments' ADD-A-CLIENT-SITE.md.
//
// `st`: { site, url (the send address), token (or ""), base (Skald's address), kit (GET sites' kit),
//         kitUrl (where the kit is asked for; a shared link's page has its own), tokenHint }

import { h } from "../ui.js";
import { csrfHeaders } from "./ipmanager.js";
import { DEMO } from "../demo.js";
import { codeBlock, steps, helpLink } from "./conn-ui.js";
import { read } from "../state.js";
import { stepped } from "../overlays.js";

// The send dialog tests on its next step; Add a site (2.42, st.testBelow) on the same one.
export const thenTest = (st) => (st && st.testBelow ? "check it with Test connection below." : "press Next and Test connection here.");

const TOKEN = "<token>";
const tok = (st) => st.token || TOKEN;
const host = (base) => { try { return new URL(base).host; } catch { return "<skald server>"; } };

// The file name the server gave (Content-Disposition), else `name`.
const nameFrom = (res, name) => {
  const cd = (res.headers && typeof res.headers.get === "function" && res.headers.get("Content-Disposition")) || "";
  const m = /filename="?([A-Za-z0-9._-]{1,120})"?/.exec(cd);
  return m ? m[1] : name;
};

/* A POST whose answer is a file, saved by the browser: "" when saved, else why not in
   words. Also the set-up pack (setup-pack.js) and the leads file (setup-hook.js). */
export async function postFile(path, body, name, { failed = "The file was not made" } = {}) {
  if (DEMO.on) return "The demo has no server: the file comes from a running Skald.";
  let res;
  try {
    res = await fetch(path, { method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", ...csrfHeaders() }, body: JSON.stringify(body) });
  } catch {
    return "The server could not be reached.";
  }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    return (data && data.error) || `${failed} (${res.status}).`;
  }
  try {
    const url = URL.createObjectURL(await res.blob());
    const a = h("a", { href: url, download: nameFrom(res, name), hidden: true });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch {
    return "The browser could not save the file.";
  }
  return "";
}

// The kit's file name: the server way is one installer, the by-hand kits a zip.
export const kitName = (site, method) => (method === "server" ? `skald-install-${site}.sh` : `skald-ship-${site}.zip`);

// The kit, posted for and saved as a file. The token goes in only when asked (kitBox's box).
export async function downloadKit(st, method, withToken) {
  const body = { site: st.site, method, include_token: Boolean(withToken && st.token) };
  if (body.include_token) body.token = st.token;
  return postFile(st.kitUrl || "sites/kit", body, kitName(st.site, method), { failed: "The kit was not made" });
}

// Whether this server makes the kit for a way. The server way: GET sites' kit.server
// (2.30), else either older kit (a server from before 2.30 answers only those).
export function kitOn(st, method) {
  const k = st.kit || {};
  return method === "server" ? Boolean(k.server ?? (k.docker || k.systemd)) : Boolean(k[method]);
}

// The kit's token choice (the owner, 2026-10-22): the token goes in the zip unless the box
// is unticked. Unticked, the zip holds no token anywhere and the token is shown here, to
// send separately. In the address as token=0 beside the dialog's key while unticked (the
// token itself never is); a page with no dialog key (the shared link's page) keeps it in st.
export const KIT_WORDS = {
  label: "Include the access token in the zip",
  on: "The kit is ready to run. Treat the zip like a password: send it only to the site's admin.",
  off: "The zip has no token. Send the token separately (copy it below), and the admin pastes it when the installer asks.",
  none: "This page has no token to put in the zip: a token is shown only once, when it is made. The zip holds none, and the admin pastes the token when the installer asks.",
};
const family = (s) => (s.setup ? "setup" : s.conn ? "conn" : "");
export function kitTokenOn(st) {
  const s = read();
  return family(s) ? s.token !== "0" : st.kitToken !== false;
}
export function setKitToken(st, on) {
  st.kitToken = Boolean(on);
  const s = read();
  const fam = family(s);
  if (fam) stepped(fam, s[fam], { token: on ? "" : "0" });
}

// The same choice for the server way's one file (the installer, skald-install-<site>.sh).
export const FILE_WORDS = {
  label: "Include the access token in the file",
  on: "The file is ready to run. Treat it like a password: send it only to the site's admin.",
  off: "The file has no token. Send the token separately (copy it below), and the admin pastes it when the installer asks.",
  none: "This page has no token to put in the file: a token is shown only once, when it is made. The file holds none, and the admin pastes the token when the installer asks.",
};

function kitBox(st, method) {
  if (!kitOn(st, method)) return h("p", { class: "note" }, (st.kit && st.kit.why && st.kit.why[method]) || "The kit is not available on this server. Use the steps by hand below.");
  const one = method === "server";
  const words = one ? FILE_WORDS : KIT_WORDS;
  const choice = h("div", { class: "cn-kit-token" });
  const btn = h("button", { type: "button", class: "btn primary" }, one ? "Download as one file" : "Download the install kit (.zip)");
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  let box = null;
  // Drawn again when a token is made on this page (tokenPanel calls st.onToken).
  const drawChoice = () => {
    box = null;
    if (!st.token) { choice.replaceChildren(h("p", { class: "note" }, words.none)); return; }
    const mine = h("input", { type: "checkbox", name: "kit-token" });
    mine.checked = kitTokenOn(st);
    const line = h("small");
    const apart = h("div");
    const show = () => {
      line.textContent = mine.checked ? words.on : words.off;
      apart.replaceChildren(...(mine.checked ? [] : [codeBlock(st.token, "the sending token")]));
    };
    mine.addEventListener("change", () => { setKitToken(st, mine.checked); show(); said.textContent = ""; });
    show();
    box = mine;
    choice.replaceChildren(h("label", { class: "chk" }, mine, h("span", null, h("b", null, words.label), line)), apart);
  };
  st.onToken = drawChoice;
  drawChoice();
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const withToken = Boolean(box && box.checked && st.token);
    const why = await downloadKit(st, method, withToken);
    btn.disabled = false;
    said.textContent = why || (withToken ? "Saved, with the token in it. Send it only to the site's admin." : "Saved. It holds no token: send the token separately.");
    said.className = `msg ${why ? "err" : "ok"}`;
  });
  return h("div", { class: "cn-kit" }, choice, h("div", { class: "acts" }, btn), said,
    h("p", { class: "note" }, one ? "One file. It works with or without Docker on the server, and finds the site's access log by itself."
      : "The kit holds install.sh, uninstall.sh, check.sh and README.txt. If something seems wrong later, run sudo bash check.sh first."));
}

const tokenNote = (st) => (st.token ? codeBlock(st.token, "the sending token")
  : h("p", { class: "note" }, st.tokenHint || "Make a sending token in the step before, or use one you have: put it where you see <token>."));

function docker(st) {
  const k = st.kit || {};
  const image = k.image || "<the Skald image>";
  const ship = k.ship_path || "<the shipper's path in the image>";
  return [
    h("p", null, `On the web server of ${st.site}, with sudo. It reads the access log only and never changes nginx, Apache or the website.`),
    kitBox(st, "docker"),
    steps(
      ["Copy the zip to the server and unpack it:", codeBlock(`scp skald-ship-${st.site}.zip <server>:~/\nssh <server>\nunzip skald-ship-${st.site}.zip && cd skald-ship-${st.site}`, "the copy commands")],
      ["Run the installer. It shows nginx's log files; give the access log of " + st.site + " (or www." + st.site + "). Then paste the token when it asks (unless it is in the zip):", codeBlock("sudo bash install.sh", "the install command")],
      ["Open https://" + st.site + "/ once in a browser, then " + thenTest(st)],
    ),
    h("details", { class: "fold" }, h("summary", null, "Without the kit (the same, by hand)"),
      h("p", null, "The token, then the container. Paste the token after the third line, press Enter, then Ctrl-D."), tokenNote(st),
      codeBlock([
        "sudo install -d -m 0750 -o root -g adm /srv/skald",
        "sudo install -d -m 0700 -o 10001 -g 4 /srv/skald/ship-state",
        "sudo sh -c 'umask 027; cat > /srv/skald/ship-token'",
        "sudo chgrp adm /srv/skald/ship-token",
        "sudo docker run -d --name skald-ship --restart unless-stopped --memory 128m \\",
        "  --user 10001:4 --no-healthcheck --entrypoint python3 \\",
        "  -v /var/log/nginx:/var/log/nginx:ro \\",
        "  -v /srv/skald/ship-token:/run/skald-ship/token:ro \\",
        "  -v /srv/skald/ship-state:/state \\",
        `  ${image} ${ship} \\`,
        `  --url ${st.url} \\`,
        "  --token-file /run/skald-ship/token --log /var/log/nginx/access.log \\",
        "  --state /state/state.json --from-end",
        "sudo docker logs --tail 20 skald-ship",
      ].join("\n"), "the Docker commands"),
      h("p", { class: "note" }, "Change /var/log/nginx/access.log to the site's own access log (Apache: /var/log/apache2/...).")),
  ];
}

function systemd(st) {
  return [
    h("p", null, `On the web server of ${st.site}, with sudo. Needs Python 3.9 or newer (python3 --version).`),
    kitBox(st, "systemd"),
    steps(
      ["Copy the zip to the server and unpack it:", codeBlock(`scp skald-ship-${st.site}.zip <server>:~/\nssh <server>\nunzip skald-ship-${st.site}.zip && cd skald-ship-${st.site}`, "the copy commands")],
      ["Run the installer. It asks for the access log of " + st.site + " (or www." + st.site + ") and the token (unless it is in the zip):", codeBlock("sudo bash install.sh", "the install command")],
      ["Open https://" + st.site + "/ once in a browser, then " + thenTest(st)],
    ),
    h("details", { class: "fold" }, h("summary", null, "Without the kit (the same, by hand)"),
      h("p", null, "Install the shipper (tools/skald-ship.py in Skald's code), its user and the token. Paste the token after the fourth line, press Enter, then Ctrl-D."), tokenNote(st),
      codeBlock([
        "sudo install -m 0755 skald-ship.py /usr/local/bin/skald-ship",
        "sudo useradd --system --no-create-home --shell /usr/sbin/nologin --groups adm skald-ship",
        "sudo install -d -m 0750 -o root -g skald-ship /etc/skald-ship",
        "sudo sh -c 'umask 027; cat > /etc/skald-ship/token'",
        "sudo chgrp skald-ship /etc/skald-ship/token",
      ].join("\n"), "the install commands"),
      h("p", null, "Then /etc/systemd/system/skald-ship.service:"),
      codeBlock([
        "[Unit]", "Description=Ship the access log to Skald", "After=network-online.target", "Wants=network-online.target", "",
        "[Service]", "User=skald-ship", "ExecStart=/usr/local/bin/skald-ship \\", `    --url ${st.url} \\`,
        "    --token-file /etc/skald-ship/token \\", "    --log /var/log/nginx/access.log \\",
        "    --state /var/lib/skald-ship/state.json --from-end", "Restart=always", "RestartSec=5",
        "StateDirectory=skald-ship", "StateDirectoryMode=0700", "NoNewPrivileges=true", "ProtectSystem=strict", "ProtectHome=true",
        "ReadOnlyPaths=/var/log /etc/skald-ship", "", "[Install]", "WantedBy=multi-user.target",
      ].join("\n"), "the service file"),
      codeBlock("sudo systemctl daemon-reload && sudo systemctl enable --now skald-ship\njournalctl -u skald-ship -n 20 -o cat", "the start commands")),
  ];
}

// The older ways, by hand: the Docker kit and the system service kit, each with its
// steps without the kit. Folded under the server way's one command or one file.
export function byHandFold(st) {
  return h("details", { class: "fold cn-byhand" }, h("summary", null, "Other ways: by hand with Docker / without Docker"),
    h("h4", null, "With Docker"), ...docker(st), h("h4", null, "Without Docker (a system service)"), ...systemd(st));
}

// The server way without a session (the shared link's page, share-page.js): the one
// file, then the same by hand. The dialog has the one command first (conn-send.js runPanel).
function server(st) {
  const file = kitName(st.site, "server");
  return [
    h("p", null, `On the web server of ${st.site}, with sudo. It works with or without Docker, finds the access log by itself, and never changes nginx, Apache or the website.`),
    kitBox(st, "server"),
    steps(
      ["Copy the file to the server:", codeBlock(`scp ${file} <server>:~/`, "the copy command")],
      ["Run it there:", codeBlock(`sudo bash ${file}`, "the install command")],
      ["Open https://" + st.site + "/ once in a browser, then press Test connection."],
    ),
    byHandFold(st),
  ];
}

function cloudflare(st) {
  return [
    h("p", null, "The Skald Worker passes every request on unchanged and, after the answer has gone out, sends a small record of it to Skald. Use it when Cloudflare serves the site and no server log is sent."),
    steps(
      ["Deploy the Worker: the Deploy to Cloudflare button in deploy/cloudflare-worker/README.md (in Skald's code), or by hand with Wrangler from that folder."],
      ["Set its two values. The address:", codeBlock(st.url, "the send address (SKALD_INGEST_URL)"), "and the token, as a secret named SKALD_TOKEN:", tokenNote(st)],
      ["By hand with Wrangler, the token is set with this command (it asks for the value), then deploy:", codeBlock("npx wrangler secret put SKALD_TOKEN\nnpx wrangler deploy", "the Wrangler commands")],
      ["Add the site's route: in Cloudflare, open the Worker, then Settings > Domains & Routes > Add > Route, with " + st.site + "/* (and www." + st.site + "/*)."],
      ["Open a page of the site, then " + thenTest(st)],
    ),
    h("p", { class: "note" }, "Skald reads this site's records as edge records (log format edge_json) when nothing else has arrived for it yet. If you also send the server's log, keep the format Detect it: then only Cloudflare's cache hits are counted from the Worker."),
  ];
}

function drains(st) {
  return [
    h("p", null, "Vercel (Pro or Enterprise) and Netlify (Enterprise) post their request logs to an address you give them. Nothing to install."),
    h("h4", null, "Vercel"),
    steps(
      "Team Settings > Drains > Add Drain > Logs.",
      "Projects: this site's project. Sources: static, edge and lambda. Environments: production. Sampling: 100%.",
      ["Destination, a custom endpoint:", codeBlock(`${st.url}?format=vercel`, "the Vercel address")],
      ["Format: JSON or NDJSON. Custom header:", codeBlock(`Authorization: Bearer ${tok(st)}`, "the Vercel header")],
      "Keep Team Settings > Security & Privacy > IP Address Visibility on: without the visitor's address Skald refuses the record.",
    ),
    h("h4", null, "Netlify"),
    steps(
      "The site's log drain settings, service General HTTP endpoint, log type traffic logs.",
      ["Endpoint:", codeBlock(`${st.url}?format=netlify`, "the Netlify address")],
      ["Authorization header:", codeBlock(`Bearer ${tok(st)}`, "the Netlify header")],
      "Format JSON or NDJSON. Leave \"Exclude personally identifiable information\" off.",
    ),
    h("p", null, `Then ${thenTest(st)}`),
  ];
}

// The plain tag: the page loads skald.js from Skald and posts its events there
// (beside the script), so the site's own server needs no change.
export const plainTag = (base, site) => `<script src="${base}/traffic-js/skald.js" data-site="${site}" defer></script>`;

// "Advanced: serve it from your own domain": the site's web server passes the
// two paths on to Skald (nginx, Apache, Caddy; as ADD-A-CLIENT-SITE.md 7.1),
// and the tag loads from the site itself. Optional; fewer ad blockers stop it.
export function proxyLines(base) {
  const sk = host(base);
  const up = ["  proxy_pass " + base + ";", `  proxy_set_header Host ${sk};`, "  proxy_ssl_server_name on;",
    "  proxy_set_header X-Forwarded-For $remote_addr;", '  proxy_set_header Cookie "";', '  proxy_set_header Authorization "";', "  proxy_hide_header Set-Cookie;", "}"];
  return {
    nginx: ["location = /traffic-beacon {", "  limit_except POST { deny all; }", "  access_log off;", "  client_max_body_size 4k;", ...up,
      "location ^~ /traffic-js/ {", "  limit_except GET { deny all; }", "  access_log off;", ...up].join("\n"),
    apache: ["# mod_proxy, mod_proxy_http, mod_ssl and mod_headers on; in the site's HTTPS <VirtualHost>", "SSLProxyEngine on",
      ...["/traffic-beacon", "/traffic-js/"].flatMap((p) => [`<Location "${p}">`, `  ProxyPass "${base}${p}"`, "  RequestHeader unset Cookie", "  RequestHeader unset Authorization", "  Header unset Set-Cookie", "</Location>"])].join("\n"),
    caddy: ["@skald path /traffic-beacon /traffic-js/*", "handle @skald {", `\treverse_proxy ${base} {`, `\t\theader_up Host ${sk}`, "\t\theader_up X-Forwarded-For {remote_host}",
      "\t\theader_up -Cookie", "\t\theader_up -Authorization", "\t\theader_down -Set-Cookie", "\t\ttransport http {", `\t\t\ttls_server_name ${sk}`, "\t\t}", "\t}", "}"].join("\n"),
  };
}

export function proxyFold(base, site) {
  const got = proxyLines(base);
  return h("details", { class: "fold su-tech cn-proxy" }, h("summary", null, "Advanced: serve it from your own domain"),
    h("p", null, "Optional. The tag above needs no change on your server. To serve the script and its events from your own domain instead, so fewer ad blockers stop them, your web server passes two addresses on to Skald: /traffic-js/ and /traffic-beacon."),
    steps(["nginx, in the site's HTTPS server block, then sudo nginx -t and reload:", codeBlock(got.nginx, "the nginx lines")],
      ["Apache:", codeBlock(got.apache, "the Apache lines")],
      ["Caddy, in the site's block:", codeBlock(got.caddy, "the Caddy lines")],
      "Vercel or Netlify: two rewrites, in the tracking script guide.",
      ["Then put this tag on your pages instead of the one above:", codeBlock(`<script src="/traffic-js/skald.js" data-site="${site}" defer></script>`, "the first-party tag")]),
    h("p", { class: "note" }, "Whoever runs your Skald server must then trust your server for the visitor's address (X-Forwarded-For); until then every visitor looks like your server. ", helpLink("tracking-script", "The tracking script guide"), " has the details."));
}

function script(st) {
  return [
    h("p", null, "The tag counts what a log cannot see: clicks, form steps, scroll and booking embeds. It never sees AI crawlers or bots, so a server log is still the best source."),
    steps(
      ["Put the tag in the <head> of every page:", codeBlock(plainTag(st.base, st.site), "the script tag")],
      ["Open a page of the site in a normal browser window (Do Not Track off), then " + thenTest(st)],
    ),
    h("p", { class: "note" }, `Nothing changes on your web server: the page loads the script from ${host(st.base)} and sends its events there. The page's host name must be one of the site's host names (Settings > Site).`),
    proxyFold(st.base, st.site),
  ];
}

export function installFor(method, st) {
  const fn = { server, docker, systemd, cloudflare, vercel: drains, script }[method];
  return fn ? fn(st) : [h("p", { class: "empty" }, "Choose a way first.")];
}
