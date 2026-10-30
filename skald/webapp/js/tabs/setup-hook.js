// "Set up this site" > Lead hook tested: where the leads come from (each tool
// Settings > Leads & tools takes: integrations_api.py TOOLS), the secret (POST
// integrations/secret, shown once and kept in this dialog only; or the tool's
// own, POST integrations/hooks/paste), the steps for that tool with the address
// and the secret filled in (from docs/help/webhooks.md), a mail for the
// developer WITHOUT the secret, and the test (POST integrations/test) plus a
// live check (2.44: ui/live.js arrivedBox, POST sites/arrived hook:<tool>) that says by
// itself, beside the address and on the Test step, whether a real one arrived. For the
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

//
// 2.44.1 (a site's Calendly: every real booking refused while Skald's own test passed): the key
// step says the tool's own word (signing key, client secret...) and which way it goes; Calendly,
// Cal.com and Typeform ask one question first (how=: made yet? with a key of its own?); what is
// saved stays on the step (when, by whom, pasted or made) with the paste's answer; Calendly
// made without a signing key gets the two requests that make it again; the Test step says it
// proves Skald's address only, beside the last real delivery (hook-key.js, hook-key-ui.js).

import { h } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { wizard, codeBlock, steps, answerBox, helpLink } from "./conn-ui.js";
import { choices, mailButton, copyButton } from "./setup-common.js";
import { shareBox } from "./conn-share.js";
import { packToggle, keepKey, keptKey } from "./setup-pack.js";
import { leadFilePanel, wordpressPanel, bearerSteps } from "./setup-leadfile.js";
import { blockList } from "../mdview.js";
import { arrivedBox } from "../ui/live.js";
import { KEY_WORD, keyWord, noun, wayWords, howOf, asks, lastRealWords, testWords as honestTest, calendlyCreate, calendlyFindDelete, CAL_EVENTS } from "../hook-key.js";
import { keyStatus, howPicker, pasteForm, makeButton, wayNow } from "./hook-key-ui.js";

export const POLL_MS = 5000;
export const POLL_FOR_MS = 120000;
export const SECRET = "<the secret>";
/* The place the key goes in a tool's steps: "<the signing key>" for Calendly, "<the secret>" for most. */
export const placeOf = (tool) => `<the ${KEY_WORD[tool] || "secret"}>`;

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

/* The steps for one tool: {lines, code, code2}, with the address and the secret (or
   SECRET when it is not to be shown: said as the tool's own word) filled in. From
   docs/help/webhooks.md. how: Calendly's answer (make, paste, remake). */
export function hookSteps(tool, addr, secret = SECRET, how = "") {
  if (secret === SECRET) secret = placeOf(tool);
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
    case "calendly":
      if (how === "paste") return { lines: [
        "The webhook is made already, with your own signing_key: nothing more to do in Calendly.",
        `Its address must be ${addr}. If it is another, make the webhook again (the third answer in the step before).`,
        "Book a test call on your Calendly page: the next step shows it as soon as it arrives."] };
      if (how === "remake") return { lines: [
        "Calendly never shows a signing key again, and a webhook made without one sends no signature. So make it again: delete the old webhook, then make it with Skald's signing key.",
        "Find the old webhook and delete it (the first request below), then make it again (the second). Put your Calendly personal access token where you see <your-calendly-token>."],
      code: calendlyFindDelete(addr), code2: calendlyCreate(addr, secret) };
      return { lines: [
        `Calendly webhooks are made with Calendly's API, usually by a developer. Make one with the address ${addr}`,
        "Give it Skald's signing key as signing_key: Calendly signs each booking with it, and never shows it again.",
        `Events: ${CAL_EVENTS.join(", ")}.`,
        "The one request, with the address and the signing key filled in (put your Calendly personal access token where you see <your-calendly-token>):"],
      code: calendlyCreate(addr, secret) };
    case "calcom": return { lines: [
      "In Cal.com, go to Settings > Developer > Webhooks > New.", `Subscriber URL: ${addr}`,
      "Event triggers: Booking Created, Booking Cancelled, Booking Rescheduled.",
      how === "paste" ? "Secret: leave the one the webhook has (the one you pasted in Skald). Save." : `Secret: ${secret}. Save.`] };
    case "typeform": return { lines: [
      `In Typeform, open your form, then Connect > Webhooks > Add a webhook. Paste the address: ${addr}`,
      how === "paste" ? "Open the webhook's settings (Edit): its Secret must be the one you pasted in Skald. Save, and turn the webhook on."
        : `Open the webhook's settings (Edit) and paste the secret into Secret: ${secret}. Save, and turn the webhook on.`] };
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
const asText = ({ lines, code, code2 }) => [...lines.map((l, i) => `${i + 1}. ${l}`), ...(code ? ["", code] : []), ...(code2 ? ["", code2] : [])].join("\n");
// The tools that sign with a secret they make: Skald never makes or shows one.
const ownSecret = (t) => t.make === false;

/* The mail to the developer: the address and the steps, never the key. how: Calendly's answer. */
export function hookMail(site, t, how = "") {
  const k = keyWord(t);
  return ["Hello,", "", `Please connect ${t.name} to Skald for ${site}, so each lead is counted with where it came from.`, "",
    asText(hookSteps(t.tool, t.url, SECRET, how)), "",
    ownSecret(t) || how === "paste" ? `The ${k} is ${t.name}'s own: it never leaves ${t.name} and Skald.`
      : `The ${k} is not in this mail: I will give it to you separately. Keep it in the server's or the tool's settings, never in the code, a mail or a chat.`,
    "", "Thank you."].join("\n");
}

/* The tool's fields again from the server (saved_at, saved_by, since_saved...), into t. */
async function refreshTool(st, t) {
  const r = await call(`integrations?site=${encodeURIComponent(st.site)}`);
  const now = r.ok && (r.tools || []).find((x) => x.tool === t.tool);
  if (now) Object.assign(t, now, { set: !!(now.set || t.set) });   // just saved: saved, even if the list lags
}

/* Step 2, the key (its name is the tool's own word): which way it goes, the one question first
   (Calendly, Cal.com, Typeform), then that way: Skald makes it (at once, when none is saved) or
   the tool's own is pasted; what is saved stays here with the paste's answer. */
function secretPanel(st, w) {
  const t = st.tool();
  const k = keyWord(t);
  if (!t.rotatable) return [h("p", null, `Its ${k} is kept on Skald's server, so there is nothing to make here. Press Next.`)];
  const fresh = st.fresh?.tool === t.tool ? st.fresh : null;
  const asking = st.asking === t.tool;
  const { way, ask } = wayNow(t, st.how, { asking });
  const out = [h("p", { class: "hk-way" }, wayWords(t)),
    h("p", { class: "note" }, `It proves each message comes from ${ownSecret(t) || t.tool === "lead" || t.tool === "json" ? "where it says" : t.name}. Anyone with it could send fake leads, so treat it like a password.`)];
  const acts = h("div", { class: "acts" });
  const make = async () => {
    st.making = t.tool;
    acts.replaceChildren(h("p", { class: "empty" }, `Making the ${k}...`));
    const r = await call("integrations/secret", { site: st.site, tool: t.tool });
    st.making = "";
    if (!r.ok || !r.secret) { st.failed = t.tool; acts.replaceChildren(makeButton(t, make, { fresh })); w.say(why(r, `The ${k} was not made.`)); return; }
    st.fresh = { tool: t.tool, secret: r.secret, url: r.url || t.url };
    st.check = { tool: t.tool, check: r.check || null };
    st.asking = "";
    if (t.tool === "lead") keepKey("lead", st.site, r.secret);
    t.set = true;
    await refreshTool(st, t);
    w.redraw();
  };
  const paste = async (value) => {
    const r = await call("integrations/hooks/paste", { site: st.site, tool: t.tool, secret: value });
    if (!r.ok) return r;
    st.check = { tool: t.tool, check: r.check || null };
    const v = r.check?.verdict || "";
    st.asking = v === "no_match" || v === "unsigned" ? t.tool : "";
    // No signature: the webhook is made again (Calendly) or given Skald's own key (Cal.com, Typeform).
    if (v === "unsigned") { st.how = t.tool === "calendly" ? "remake" : "make"; w.keep({ how: st.how }); }
    t.set = true;
    await refreshTool(st, t);
    w.redraw();
    return r;
  };
  const pick = (id) => { st.how = id; st.asking = t.tool; w.keep({ how: id }); w.redraw(); };
  const replace = asks(t) || ownSecret(t) ? () => { st.asking = t.tool; w.redraw(); } : null;
  out.push(keyStatus(t, { fresh, check: st.check?.tool === t.tool ? st.check.check : null, onReplace: replace }));
  if (ask) out.push(howPicker(t, way, pick));
  if (way === "paste") out.push(pasteForm(t, paste));
  else if (way === "make" || way === "remake") {
    if (way === "remake") out.push(h("p", null, `Calendly never shows a ${k} again, so the webhook is made again with Skald's ${k}: make it here, and the next step has the two requests with it filled in.`));
    // None saved and none made here: made at once, with no press (once; a failure shows the button).
    if (!t.set && !fresh && st.failed !== t.tool) { if (st.making !== t.tool) make(); else acts.replaceChildren(h("p", { class: "empty" }, `Making the ${k}...`)); }
    else acts.replaceChildren(makeButton(t, make, { fresh }));
    if (t.set && !fresh) out.push(h("p", { class: "note" }, `A ${k} is saved already. Make a new one only if you lost it, or to make the webhook again.`));
    out.push(acts);
  }
  return out;
}

/* Step 4, Test: Skald's address first (what it proves, and what it does not), then whether a real
   one has come, by itself, beside the last real delivery. */
function testPanel(st) {
  const t = st.tool();
  const out = h("div", { class: "cn-test-out" });
  const test = h("button", { type: "button", class: "btn" }, "Test Skald's address");
  const last = h("p", { class: "note hk-last" }, lastRealWords(t));
  // 2.44: whether a real one arrived, said by itself (every 5 s, then 30 s) with its Test.
  const real = arrivedBox(st.site, `hook:${t.tool}`, { label: "Check for a real one", next: true, intro: "Waiting for the first real one." });
  test.addEventListener("click", async () => {
    test.disabled = true;
    const r = await call("integrations/test", { site: st.site, tool: t.tool });
    test.disabled = false;
    const [kind, head, more] = honestTest(r, t, why(r || {}, "The test could not be sent."));
    out.replaceChildren(answerBox(kind, head, more ? h("p", null, more) : null));
    if (r?.ok && r.last_real !== undefined) last.textContent = lastRealWords(t, r.last_real);
  });
  const ours = t.tool === "lead" || t.tool === "json";
  const intro = ours ? "Only a real lead from your form shows it works: this page shows it as soon as it arrives."
    : `Only a real ${noun(t.tool)} from ${t.name} shows that ${t.name} signs with the same ${keyWord(t)} as Skald: this page shows it as soon as it arrives.`;
  return h("div", { class: "cn-test" }, h("p", null, `${intro} Test Skald's address checks Skald's side only.`),
    real, h("div", { class: "acts" }, t.set ? test : null), out, last.textContent ? last : null);
}

/* Step 3, Set it up: the way's own steps with the address and the secret filled in, the
   mail and the share for a developer, and the set-up pack for someone else. */
function setUpPanel(st, w) {
  const t = st.tool();
  const site = st.site;
  const fresh = st.fresh?.tool === t.tool ? st.fresh : null;
  const addr = fresh?.url || t.url;
  const secret = fresh && !ownSecret(t) ? fresh.secret : "";
  const k = keyWord(t);
  const how = howOf(t, st.how) || wayNow(t, st.how).way;
  const shown = hookSteps(t.tool, addr, secret || SECRET, how);
  const [pack, packBody] = packToggle(site, "Send set-up to someone");
  const mail = mailButton("Send these steps to your developer", { subject: `Connect ${t.name} to Skald for ${site}`, body: hookMail(site, { ...t, url: addr }, how) });
  const theirs = ownSecret(t) || how === "paste";
  const sendOn = [h("div", { class: "acts" }, copyButton("Copy the steps", asText(shown), "the steps"), mail, pack), packBody,
    shareBox(site, "hook", t.tool),
    h("p", { class: "note" }, theirs ? "The mail holds the address and the steps." : `The mail holds the address and the steps, not the ${k}: give the ${k} separately, never by mail or chat.`)];
  const filled = h("p", null, theirs ? "The address is filled in." : secret ? `The address and the ${k} are filled in.` : `The address is filled in. Put the ${k} where you see ${placeOf(t.tool)}.`);
  // 2.44: beside the address, whether anything has arrived at it yet, by itself, with Test.
  const live = arrivedBox(site, `hook:${t.tool}`, { intro: `Waiting for ${t.name}: nothing has arrived yet.` });
  if (st.pick === "wordpress") {
    return [...wordpressPanel(site, { secret }), live, h("div", { class: "acts" }, pack), packBody, helpLink("webhooks", "WordPress forms, step by step")];
  }
  if (st.pick === "lead") {
    return [...leadFilePanel(st, { secret, onLang: () => w.redraw() }),
      h("details", { class: "fold" }, h("summary", null, "By hand: the signed request"), filled, steps(...shown.lines), shown.code ? codeBlock(shown.code, "the example") : null),
      examples(addr), live, ...sendOn, helpLink("leads-from-your-backend", "Examples in Node, Python and PHP")];
  }
  return [filled, steps(...shown.lines), shown.code ? codeBlock(shown.code, shown.code2 ? "the requests that find and delete the old webhook" : "the example") : null,
    shown.code2 ? codeBlock(shown.code2, "the request that makes the webhook") : null,
    t.tool === "json" ? h("details", { class: "fold" }, h("summary", null, "Signed instead (optional)"), steps(...signedJson(addr))) : null,
    live, ...sendOn, helpLink("webhooks", `${t.name}, step by step`)];
}

export async function hookDialog(site, { onClose = null, route = null, start = 0, wrap = null, way = "" } = {}) {
  const r = await call(`integrations?site=${encodeURIComponent(site)}`);
  const tools = r.ok ? (r.tools || []).filter((t) => WAYS[t.tool]) : [];
  // A lead secret made earlier in this page is still known (setup-pack.js keeps it).
  const kept = keptKey("lead", site);
  const st = { site, tool: null, lang: "php", fresh: kept ? { tool: "lead", secret: kept, url: tools.find((t) => t.tool === "lead")?.url || "" } : null,
    // A page's Connect names the way (way=, js/ui/connect.js); else the tool set up, else the first.
    pick: (WAYS[way] && tools.some((t) => t.tool === toolOf(way)) ? way : "") || (tools.find((t) => t.set) || tools[0])?.tool || "",
    // 2.44.1: how the tool's webhook was made (how=, the key step's question), from a link.
    how: String(S.read().how || ""), asking: "", check: null };
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
      // The step's name is the tool's own word for its key (a getter: the tool is chosen in step 1).
      { get name() { return `The ${keyWord(st.tool())}`; }, draw: (w) => secretPanel(st, w),
        check: () => {
          const t = st.tool();
          const k = keyWord(t);
          if (t.set || !t.rotatable) return "";
          const { way, ask } = wayNow(t, st.how);
          if (ask && !way) return t.tool === "calendly" ? "Say how your Calendly webhook was made first." : `Say whether ${t.name} gave you a ${k} first.`;
          return way === "paste" ? `Paste the ${k} from ${t.name} first.` : `Make the ${k} first.`;
        } },
      { name: "Set it up", draw: (w) => setUpPanel(st, w) },
      { name: "Test", draw: () => [testPanel(st)] },
    ],
  });
}
