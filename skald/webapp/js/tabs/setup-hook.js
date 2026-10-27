// "Set up this site" > Lead hook tested: where the leads come from (each tool
// Settings > Leads & tools takes: integrations_api.py TOOLS), the secret (POST
// integrations/secret, shown once and kept in this dialog only; or the tool's
// own, POST integrations/hooks/paste), the steps for that tool with the address
// and the secret filled in (from docs/help/webhooks.md), a mail for the
// developer WITHOUT the secret, and the test (POST integrations/test) plus a
// live check that polls GET integrations until a real one arrives. For the
// site's own backend, the guide's body and signed examples (help-data.js,
// "Send leads from your backend") with this site's address; "Share with your
// developer" (conn-share.js) makes a private page with the same steps.
//
// 2.30, shorter: the first step says what the script tag already counts with no code;
// the secret is made as soon as its step is shown (when the tool takes one Skald makes
// and none is set); the site's own backend downloads one file per language and
// WordPress one plugin (POST integrations/leadfile {site, lang, secret?}: setup-leadfile.js);
// Zapier, Make and n8n post with an Authorization: Bearer header, no signing. The
// set-up pack (setup-pack.js) sends all of it to someone in one zip.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { input, field, why, confirmIn } from "./forms.js";
import { wizard, codeBlock, steps, answerBox, helpLink } from "./conn-ui.js";
import { adminFold, choices, mailButton, copyButton } from "./setup-common.js";
import { shareBox } from "./conn-share.js";
import { packToggle, keepKey, keptKey } from "./setup-pack.js";
import { leadFilePanel, wordpressPanel, bearerSteps } from "./setup-leadfile.js";
import { blockList } from "../mdview.js";

export const POLL_MS = 5000;
export const POLL_FOR_MS = 120000;
export const SECRET = "<the secret>";

// What the script tag counts with no code (the beacon's own events), said first.
export const NO_CODE = "Already counted with no code, when the script tag is on the site: form sends, Calendly and Cal.com bookings, phone and email clicks.";

// Each way in plain words: its title and one line. "wordpress" is a way, not a tool:
// the plugin posts to the "lead" hook (toolOf).
const WAYS = {
  lead: ["Your site's own form or backend", "Your site's server tells Skald each time a lead is made. Download one file, add one line."],
  wordpress: ["WordPress forms", "Contact Form 7, WPForms, Gravity Forms, Elementor and Ninja Forms. Upload one plugin; no code."],
  json: ["Zapier, Make or n8n", "A form plugin or a no-code tool sends each lead through Zapier, Make or n8n."],
  calendly: ["Calendly", "Bookings, cancellations and no-shows. Needs a paid Calendly plan (Standard or higher)."],
  calcom: ["Cal.com", "Bookings, cancellations and moved bookings."],
  typeform: ["Typeform", "Each form response, counted as a contact form."],
  stripe: ["Stripe", "Each paid Checkout, counted as a payment."],
  hubspot: ["HubSpot", "New contacts, booked meetings and won deals."],
};
const ORDER = ["lead", "wordpress", "json", "calendly", "calcom", "typeform", "stripe", "hubspot"];
export const toolOf = (way) => (way === "wordpress" ? "lead" : way);
// The lead hook's secret made in this page, for the set-up pack (never stored).
export const leadSecretFor = (site) => keptKey("lead", site);

/* The steps for one tool: {lines, code}, with the address and the secret (or
   SECRET when it is not to be shown) filled in. From docs/help/webhooks.md. */
export function hookSteps(tool, addr, secret = SECRET) {
  switch (tool) {
    case "lead": return { lines: [
      "Keep the secret in the server's settings, never in the code.",
      `For each new lead, send a POST with a JSON body to ${addr}`,
      "Sign it with the header X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of \"<t>.<raw body>\">, keyed with the secret. A time more than 5 minutes off is refused.",
      "Needed fields: external_ref (the lead's own ID) and action (demo, signup, contact or trial). Optional: vid (the visitor ID the page had), name and email.",
      "A short test from a terminal:"],
    code: [`BODY='{"external_ref":"L-1001","action":"demo"}'`, "T=$(date +%s)",
      `SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "${secret}" -hex | sed 's/^.* //')`,
      `curl -X POST '${addr}' \\`, `  -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY"`].join("\n") };
    case "json": return bearerSteps(addr, secret);
    case "calendly": return { lines: [
      `Make a webhook subscription in Calendly with the address ${addr}. Calendly has no screen for it: it is made through Calendly's API, usually by a developer.`,
      "Use the secret as the subscription's signing key.",
      "Choose these events: invitee.created, invitee.canceled, invitee_no_show.created.",
      "A developer can make it with one request:"],
    code: ["curl -X POST https://api.calendly.com/webhook_subscriptions \\", "  -H \"Authorization: Bearer <your-calendly-token>\" \\", "  -H \"Content-Type: application/json\" \\",
      `  -d '{"url": "${addr}",`, "       \"events\": [\"invitee.created\", \"invitee.canceled\", \"invitee_no_show.created\"],",
      "       \"organization\": \"https://api.calendly.com/organizations/<your-organization-id>\",", `       "scope": "organization", "signing_key": "${secret}"}'`].join("\n") };
    case "calcom": return { lines: [
      "In Cal.com, go to Settings > Developer > Webhooks > New.", `Subscriber URL: ${addr}`,
      "Event triggers: Booking Created, Booking Cancelled, Booking Rescheduled.", `Secret: ${secret}. Save.`] };
    case "typeform": return { lines: [
      `In Typeform, open your form, then Connect > Webhooks > Add a webhook. Paste the address: ${addr}`,
      `Open the webhook's settings (Edit) and paste the secret into Secret: ${secret}. Save, and turn the webhook on.`] };
    case "stripe": return { lines: [
      "In Stripe, go to Developers > Webhooks > Add endpoint.", `Endpoint URL: ${addr}`,
      "Events: checkout.session.completed and checkout.session.async_payment_succeeded.",
      "Save, then reveal the endpoint's Signing secret (it starts with whsec_) and paste it in Skald, in the step before."] };
    case "hubspot": return { lines: [
      "In your HubSpot app, open Auth and copy the Client secret. Paste it in Skald, in the step before.",
      `In your HubSpot app, open Webhooks and set the Target URL to ${addr}`,
      "Subscribe to contact.creation, to object.creation for meetings, and to deal.propertyChange for dealstage."] };
    default: return { lines: [`Send each lead to ${addr}`] };
  }
}
// The signed way for Zapier and Make (before 2.30 the only one), folded under the Bearer header.
const signedJson = (addr) => [
  "Keep the secret in the tool's own secure storage, not in a plain text step.",
  `Zapier: add a "Code by Zapier" step that signs the body and posts it to ${addr}`,
  `Make: use the HTTP module to post to ${addr} with the header X-Skald-Signature set to t={{timestamp}},v1={{sha256(timestamp + "." + body; "hex"; secret)}}, using the secret.`,
  "One message can carry one lead, a list of them, or {\"records\": [...]}, up to 100."];

// The guide's parts 2 and 3 (the body; sign it and send it), its example address
// replaced with this hook's, as the shared page shows them (share-page.js).
const GUIDE_URL = "https://stats.example.com/traffic-hooks/example.com/lead";
export async function guideParts(url) {
  let data = null;
  try { data = (await import("../help-data.js")).default; } catch { return []; }
  const g = (data.guides || []).find((x) => x.id === "leads-from-your-backend");
  const out = [];
  let on = false;
  for (const b of g?.blocks || []) {
    if (b.t === "h2") on = /^(2|3)\./.test(b.text || "");
    if (!on) continue;
    if (b.t === "pre") out.push(codeBlock(String(b.text).split(GUIDE_URL).join(url), "the example"));
    else out.push(...[].concat(blockList([b])));
  }
  return out;
}
function examples(url) {
  const box = h("div", null, h("p", { class: "empty" }, "Loading the examples..."));
  guideParts(url).then((parts) => box.replaceChildren(...(parts.length ? parts : [helpLink("leads-from-your-backend", "The examples are in the guide")])));
  return h("details", { class: "fold" }, h("summary", null, "The body, and examples in curl, Node, Python and PHP"), box);
}
const asText =({ lines, code }) => [...lines.map((l, i) => `${i + 1}. ${l}`), ...(code ? ["", code] : [])].join("\n");
// The tools that sign with a secret they make: Skald never makes or shows one.
const ownSecret = (t) => t.make === false;

/* The mail to the developer: the address and the steps, never the secret. */
export function hookMail(site, t) {
  return ["Hello,", "", `Please connect ${t.name} to Skald for ${site}, so each lead is counted with where it came from.`, "",
    asText(hookSteps(t.tool, t.url, SECRET)), "",
    ownSecret(t) ? `The secret is ${t.name}'s own: it never leaves ${t.name} and Skald.`
      : "The secret is not in this mail: I will give it to you separately. Keep it in the server's or the tool's settings, never in the code, a mail or a chat.",
    "", "Thank you."].join("\n");
}

const testWords = (r) => {
  if (!r.ok) return ["bad", why(r, "The test could not be sent.")];
  const a = r.answer || {};
  if (r.status !== 200) return ["bad", `The test was refused (${r.status}): ${a.error || "refused"}.`];
  return ["ok", `The test was signed, received and read. A real one would keep ${a.would_keep ?? a.records ?? 0} of ${a.records ?? 0}. Nothing was kept.`];
};

function secretPanel(st, w) {
  const t = st.tool();
  if (!t.rotatable) return [h("p", null, "Its secret is kept on Skald's server, so there is nothing to make here. Press Next.")];
  const out = [h("p", null, "The secret proves each message comes from you. Anyone with it could send fake leads, so treat it like a password.")];
  const fresh = st.fresh?.tool === t.tool ? st.fresh : null;
  if (!ownSecret(t)) {
    const acts = h("div", { class: "acts" });
    const make = async () => {
      st.making = t.tool;
      acts.replaceChildren(h("p", { class: "empty" }, "Making the secret..."));
      const r = await call("integrations/secret", { site: st.site, tool: t.tool });
      st.making = "";
      if (!r.ok || !r.secret) { st.failed = t.tool; draw(); w.say(why(r, "The secret was not made.")); return; }
      st.fresh = { tool: t.tool, secret: r.secret, url: r.url || t.url };
      if (t.tool === "lead") keepKey("lead", st.site, r.secret);
      t.set = true;
      w.redraw();
    };
    function draw() {
      const btn = h("button", { type: "button", class: "btn primary" }, t.set ? "Make a new secret" : "Make the secret");
      btn.addEventListener("click", () => {
        if (!t.set || fresh) { btn.disabled = true; make(); return; }
        confirmIn(acts, "Make a new secret? The old one stops working at once.", "Yes, make a new one", make, draw);
      });
      acts.replaceChildren(btn);
    }
    // None set and none made here: made at once, with no press (once; a failure shows the button).
    if (!t.set && !fresh && st.failed !== t.tool) { if (st.making !== t.tool) make(); else acts.replaceChildren(h("p", { class: "empty" }, "Making the secret...")); }
    else draw();
    if (t.set && !fresh) out.push(h("p", { class: "note" }, "This hook has a secret already. Make a new one only if you lost it."));
    out.push(acts);
  }
  if (fresh) {
    out.push(h("div", { class: "state ok", role: "status" }, h("div", null,
      h("p", null, h("strong", null, "The secret. "), "Copy it now: it is shown only this once, and the next step fills it in."),
      codeBlock(fresh.secret, "the secret"))));
  }
  if (t.paste) {
    const box = input({ type: "password", autocomplete: "off", maxlength: "500", placeholder: t.set ? "set: paste to replace" : "not set" });
    const save = h("button", { type: "button", class: "btn" }, "Save secret");
    const said = h("p", { class: "msg", role: "status", "aria-live": "polite" });
    save.addEventListener("click", async () => {
      if (!box.value.trim()) { said.textContent = `Paste the signing secret from ${t.secret_from || t.name} first.`; said.className = "msg err"; return; }
      save.disabled = true;
      const r = await call("integrations/hooks/paste", { site: st.site, tool: t.tool, secret: box.value });
      save.disabled = false;
      if (!r.ok) { said.textContent = why(r, "It was not saved."); said.className = "msg err"; return; }
      box.value = "";
      t.set = true;
      said.textContent = "Saved. It is not shown again.";
      said.className = "msg ok";
    });
    out.push(h("div", { class: "af-row" }, field(ownSecret(t) ? `Paste the signing secret from ${t.secret_from || t.name}` : `Or paste the signing secret ${t.name} gave you`, box,
      ownSecret(t) ? `${t.name} makes its own secret; Skald cannot make one for it.` : "Only if the tool made its own."), save), said);
  }
  return out;
}

function testPanel(st) {
  const t = st.tool();
  const out = h("div", { class: "cn-test-out" });
  const test = h("button", { type: "button", class: "btn primary" }, "Send a test lead");
  const live = h("button", { type: "button", class: "btn" }, "Wait for a real one");
  test.addEventListener("click", async () => {
    test.disabled = true;
    const r = await call("integrations/test", { site: st.site, tool: t.tool });
    test.disabled = false;
    const [kind, head] = testWords(r);
    out.replaceChildren(answerBox(kind, head, kind === "ok" ? h("p", null, "Skald's side works. Now send a real lead from your form or tool, and press Wait for a real one.") : null));
  });
  let timer = null, until = 0;
  async function once() {
    const r = await call(`integrations?site=${encodeURIComponent(st.site)}`);
    const now = r.ok ? (r.tools || []).find((x) => x.tool === t.tool) : null;
    const polling = Date.now() < until;
    if (now?.state === "received" && !now.attention) {
      out.replaceChildren(answerBox("ok", `Connected: ${now.name}, ${now.words}.`));
    } else if (now?.attention) {
      out.replaceChildren(answerBox("bad", `${now.name}: ${now.words}.`, adminFold(now.fix || null)));
    } else {
      out.replaceChildren(answerBox("wait", "Waiting for the first real one. Nothing real has arrived yet.",
        polling ? h("p", { class: "note" }, "Checking again every 5 seconds, for up to 2 minutes.") : h("p", null, "Nothing arrived in 2 minutes. Check the address and the secret in the tool, then try again.")));
      if (polling && out.isConnected !== false) { timer = setTimeout(once, POLL_MS); return; }
    }
    clearTimeout(timer);
    live.disabled = false;
  }
  live.addEventListener("click", () => { clearTimeout(timer); until = Date.now() + POLL_FOR_MS; live.disabled = true; once(); });
  return h("div", { class: "cn-test" }, h("p", null, "Send a test lead first: Skald signs a sample, reads it and keeps nothing (it is marked as a test). Then send a real lead and wait for it here."),
    h("div", { class: "acts" }, t.set ? test : null, live), out);
}

/* Step 3, Set it up: the way's own steps with the address and the secret filled in, the
   mail and the share for a developer, and the set-up pack for someone else. */
function setUpPanel(st, w) {
  const t = st.tool();
  const site = st.site;
  const fresh = st.fresh?.tool === t.tool ? st.fresh : null;
  const addr = fresh?.url || t.url;
  const secret = fresh && !ownSecret(t) ? fresh.secret : "";
  const shown = hookSteps(t.tool, addr, secret || SECRET);
  const [pack, packBody] = packToggle(site, "Send set-up to someone");
  const mail = mailButton("Send these steps to your developer", { subject: `Connect ${t.name} to Skald for ${site}`, body: hookMail(site, { ...t, url: addr }) });
  const sendOn = [h("div", { class: "acts" }, copyButton("Copy the steps", asText(shown), "the steps"), mail, pack), packBody,
    shareBox(site, "hook", t.tool),
    h("p", { class: "note" }, ownSecret(t) ? "The mail holds the address and the steps." : "The mail holds the address and the steps, not the secret: give the secret separately, never by mail or chat.")];
  const filled = h("p", null, secret ? "The address and the secret are filled in." : `The address is filled in. Put the secret where you see ${SECRET}.`);
  if (st.pick === "wordpress") {
    return [...wordpressPanel(site, { secret }), h("div", { class: "acts" }, pack), packBody, helpLink("webhooks", "WordPress forms, step by step")];
  }
  if (st.pick === "lead") {
    return [...leadFilePanel(st, { secret, onLang: () => w.redraw() }),
      h("details", { class: "fold" }, h("summary", null, "By hand: the signed request"), filled, steps(...shown.lines), shown.code ? codeBlock(shown.code, "the example") : null),
      examples(addr), ...sendOn, helpLink("leads-from-your-backend", "Examples in Node, Python and PHP")];
  }
  return [filled, steps(...shown.lines), shown.code ? codeBlock(shown.code, "the example") : null,
    t.tool === "json" ? h("details", { class: "fold" }, h("summary", null, "Signed instead (optional)"), steps(...signedJson(addr))) : null,
    ...sendOn, helpLink("webhooks", `${t.name}, step by step`)];
}

export async function hookDialog(site, { onClose = null, route = null, start = 0, wrap = null, way = "" } = {}) {
  const r = await call(`integrations?site=${encodeURIComponent(site)}`);
  const tools = r.ok ? (r.tools || []).filter((t) => WAYS[t.tool]) : [];
  // A lead secret made earlier in this page is still known (setup-pack.js keeps it).
  const kept = keptKey("lead", site);
  const st = { site, tool: null, lang: "php", fresh: kept ? { tool: "lead", secret: kept, url: tools.find((t) => t.tool === "lead")?.url || "" } : null,
    // A page's Connect names the way (way=, js/ui/connect.js); else the tool set up, else the first.
    pick: (WAYS[way] && tools.some((t) => t.tool === toolOf(way)) ? way : "") || (tools.find((t) => t.set) || tools[0])?.tool || "" };
  st.tool = () => tools.find((t) => t.tool === toolOf(st.pick)) || tools[0];
  // The ways offered: each tool the server takes, and WordPress when it takes "lead".
  const ways = ORDER.filter((id) => tools.some((t) => t.tool === toolOf(id)));
  if (!tools.length) {
    return wizard({ route, start, wrap, title: "Connect your leads", subtitle: `For ${site}. Optional.`, key: "setup-lead", onClose,
      steps: [{ name: "Not available", draw: () => [h("p", { class: "msg err" }, why(r, "The hooks could not be loaded."))] }] });
  }
  return wizard({ route, start, wrap,
    title: "Connect your leads", subtitle: `For ${site}. Optional.`, key: "setup-lead", onClose, state: st,
    steps: [
      { name: "Where leads come from",
        draw: (w) => [h("div", { class: "state ok su-nocode", role: "note" }, h("div", null, h("p", null, NO_CODE))),
          h("p", null, "Where else are your leads made? Skald then counts each one with the visit and the source that brought it."),
          r.locked ? h("p", { class: "msg err" }, r.locked) : null,
          r.takes_hooks === false ? h("p", { class: "msg err" }, "This Skald does not report on this site yet, so its hooks are not answered.") : null,
          choices(st, "pick", ways.map((id) => { const t = tools.find((x) => x.tool === toolOf(id)); return { id, title: WAYS[id][0], sub: `${WAYS[id][1]} Now: ${t.words}.` }; }),
            "Where do your leads come from?", () => w.say("")),
          helpLink("webhooks", "Each tool, step by step")],
        check: () => (st.pick ? "" : "Choose where your leads come from.") },
      { name: "The secret", draw: (w) => secretPanel(st, w),
        check: () => { const t = st.tool(); return t.set || !t.rotatable ? "" : ownSecret(t) ? `Paste the signing secret from ${t.name} first.` : "Make the secret first."; } },
      { name: "Set it up", draw: (w) => setUpPanel(st, w) },
      { name: "Test", draw: () => [testPanel(st)] },
    ],
  });
}
