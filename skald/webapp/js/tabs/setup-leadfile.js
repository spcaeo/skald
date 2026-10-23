// "Connect your leads" > Set it up (setup-hook.js), the short ways (2.30): the site's
// own backend downloads one file for its language and adds one line; WordPress
// uploads one plugin; Zapier, Make and n8n post with an Authorization: Bearer
// header, with no signing (the "lead" and "json" hooks take it).
//
// The files come from POST <page>/integrations/leadfile {site, lang, secret?}
// (integrations_api.py): lang php, node, python or wordpress. With the secret this
// page holds, the server writes it in the file as a fallback; the environment variable
// SKALD_LEAD_SECRET (WordPress: that constant in wp-config.php) wins when set.

import { h } from "../ui.js";
import { codeBlock, steps } from "./conn-ui.js";
import { choices } from "./setup-common.js";
import { postFile } from "./conn-install.js";

export const ENV = "SKALD_LEAD_SECRET";
export const PLUGIN = "skald-leads.zip";
// Each language: its file (the server's own name, else this one), the line that loads it, the call.
export const LANGS = {
  php: { title: "PHP", file: "skald-lead.php", use: 'require_once __DIR__ . "/skald-lead.php";', call: 'skald_lead("L-1001", "demo", $email);' },
  node: { title: "Node", file: "skald-lead.cjs", use: 'const { skaldLead } = require("./skald-lead.cjs");', call: 'await skaldLead("L-1001", "demo", { email, name });' },
  python: { title: "Python", file: "skald_lead.py", use: "from skald_lead import skald_lead", call: 'skald_lead("L-1001", "demo", email)' },
};

/* The body of integrations/leadfile: the secret only when the page holds it. No DOM. */
export function leadFileBody(site, lang, secret = "") {
  const body = { site, lang };
  if (secret) body.secret = secret;
  return body;
}
export const leadLines = (lang) => `${LANGS[lang].use}\n${LANGS[lang].call}`;

// A download button and its line: the file asked for and saved, or why not.
function downloadButton(words, site, lang, secret, name, save) {
  const btn = h("button", { type: "button", class: "btn primary" }, words);
  const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const no = await save("integrations/leadfile", leadFileBody(site, lang, secret), name, { failed: "The file was not made" });
    btn.disabled = false;
    said.textContent = no || (secret ? `Saved ${name}, with the secret in it. Treat it like a password.` : `Saved ${name}. It has no secret in it.`);
    said.className = `msg ${no ? "err" : "ok"}`;
  });
  return [h("div", { class: "acts" }, btn), said];
}

/* The site's own backend: the language, its file, the one line, where the secret goes.
   st.lang is the language chosen; onLang() after a change (the step is drawn again). */
export function leadFilePanel(st, { secret = "", onLang = null, save = postFile } = {}) {
  if (!LANGS[st.lang]) st.lang = "php";
  const lang = st.lang;
  const L = LANGS[lang];
  return [
    h("p", null, "Your site's server tells Skald each time a lead is made. Which language is it written in?"),
    choices(st, "lang", Object.entries(LANGS).map(([id, x]) => ({ id, title: x.title })), "The server's language", onLang),
    ...downloadButton(`Download ${L.file}`, st.site, lang, secret, L.file, save),
    steps(
      `Put ${L.file} beside your code.`,
      ["Where a lead is made (a form sent, a sign-up), add:", codeBlock(leadLines(lang), "the lines to add"),
        h("small", null, "L-1001 is the lead's own ID in your system; demo is one of demo, signup, contact or trial.")],
      ["Where the secret goes: the environment variable ", h("code", null, ENV), " on the server.",
        secret ? codeBlock(`${ENV}=${secret}`, "the secret's setting") : h("small", null, ` Put the secret after ${ENV}=.`)],
    ),
    h("p", { class: "note" }, secret ? "The file has the secret in it too, so it works at once. The environment variable wins when it is set."
      : "The file has no secret in it: it reads SKALD_LEAD_SECRET."),
  ];
}

/* WordPress: the plugin, uploaded and activated. */
export function wordpressPanel(site, { secret = "", save = postFile } = {}) {
  return [
    h("p", null, "A small plugin sends each form entry as a lead: Contact Form 7, WPForms, Gravity Forms, Elementor Pro and Ninja Forms."),
    ...downloadButton("Download the plugin (.zip)", site, "wordpress", secret, PLUGIN, save),
    steps("In WordPress, go to Plugins > Add New > Upload Plugin.", `Choose ${PLUGIN}, press Install Now, then Activate.`,
      "That is all. Send a form on the site, then press Next to test."),
    secret ? null : h("p", { class: "note" }, "This page has no secret to put in the plugin. Add this line to wp-config.php, with the secret: ",
      h("code", null, `define('${ENV}', '<the secret>');`)),
  ];
}

/* Zapier, Make, n8n or a form plugin: {lines, code}, with the address and the secret
   (or its placeholder) filled in. No signing: the Bearer header. */
export function bearerSteps(addr, secret) {
  return { lines: [
    "Keep the secret in the tool's own secure storage, not in a plain text step.",
    `Zapier: Webhooks by Zapier > POST. Make: HTTP > Make a request. n8n: HTTP Request. Post to ${addr}`,
    `Add the header Authorization with the value Bearer ${secret}. No signing is needed.`,
    "Send the lead as JSON. Needed: external_ref (the lead's own ID) and action (demo, signup, contact or trial). Optional: vid, name and email. One message can carry one lead, a list of them, or {\"records\": [...]}, up to 100.",
    "A short test from a terminal:"],
  code: [`curl -X POST '${addr}' \\`, "  -H 'Content-Type: application/json' \\", `  -H 'Authorization: Bearer ${secret}' \\`,
    `  --data-raw '{"external_ref":"L-1001","action":"demo","email":"lead@example.com"}'`].join("\n") };
}
