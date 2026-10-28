// A hook's key, in plain words (no DOM, so node runs it: tests/js/hook-key.mjs). The pieces that
// draw it are js/tabs/hook-key-ui.js; Leads & tools' drawer (tabs/integrations.js) and the
// set-up dialog (tabs/setup-hook.js) use both.
//
// Found on a site's Calendly (2026-10-28): the page said "secret" where Calendly says "signing
// key", so it took ten minutes to see which way the key goes; once saved, the screen said
// nothing about it; Skald's own test passed (it signs its own sample with the key it holds, so
// it proves only Skald's address) while every real booking was refused. Now:
//
//   keyWord(t)             the tool's own word: the server's key_word, else KEY_WORD
//   wayWords(t)            which way the key goes, said once
//   howQuestion(t)         the one question first, for a tool that takes either key (Calendly,
//                          Cal.com, Typeform): {question, choices}; how= in the address
//   savedWords(t)          "Signing key saved 28 Oct 10:16 by Ann (pasted)", from saved_at,
//                          saved_by, saved_how; "saved" without a time when not known
//   checkWords(check, t)   a paste's or a make's answer (check.verdict) in plain words
//   lastRealWords(t)       the last real delivery (last_real): accepted, refused and why, none
//   realState(t)           good, bad or wait from since_saved (good only after a real delivery
//                          was accepted since the key was saved); null from an older server
//   testWords(r, t)        Test Skald's address: what it proves, and what it does not
//
// A field the server does not send (an older Skald) is unknown: nothing is said about it.

import { time, when } from "./tz.js";

export const KEY_WORD = { calendly: "signing key", calcom: "secret", typeform: "secret", stripe: "signing secret",
  hubspot: "client secret", lead: "secret", json: "secret" };
export const keyWord = (t) => (t && t.key_word) || KEY_WORD[t?.tool] || "secret";
export const cap = (s) => String(s || "").replace(/^./, (c) => c.toUpperCase());

// What each tool sends: one and many.
const NOUN = { calendly: ["booking", "bookings"], calcom: ["booking", "bookings"], typeform: ["response", "responses"],
  stripe: ["payment", "payments"], hubspot: ["delivery", "deliveries"], lead: ["lead", "leads"], json: ["lead", "leads"] };
export const noun = (tool, n = 1) => (NOUN[tool] || ["delivery", "deliveries"])[n === 1 ? 0 : 1];

// The tools that take either key: one Skald makes, or the tool's own, pasted.
export const EITHER = new Set(["calendly", "calcom", "typeform"]);
export const asks = (t) => !!t && EITHER.has(t.tool) && t.rotatable !== false;
export const HOWS = ["make", "paste", "remake"];
/* The address's how=, when it is an answer this tool's question has; else "". */
export function howOf(t, value) {
  const q = howQuestion(t);
  return q && q.choices.some((c) => c.id === value) ? value : "";
}

/* Which way the key goes, once, in plain words. */
export function wayWords(t) {
  if (!t) return "";
  const k = keyWord(t), name = t.name || t.tool;
  if (t.make === false) return `${name} makes the ${k}; you paste it here once. ${name} signs each ${noun(t.tool)} with it, and Skald checks it.`;
  if (t.tool === "lead") return `Skald makes the ${k}; your site's server signs each lead with it.`;
  if (t.tool === "json") return `Skald makes the ${k}; Zapier, Make or n8n sends it with each lead.`;
  return `Skald gives ${name} a ${k}; ${name} signs each ${noun(t.tool)} with it.`;
}

/* The one question first, for a tool that takes either key: {question, choices[{id, title, sub}]}, or null. */
export function howQuestion(t) {
  if (!asks(t)) return null;
  const k = keyWord(t), name = t.name || t.tool;
  if (t.tool === "calendly") {
    return { question: "How was your Calendly webhook made?", choices: [
      { id: "make", title: "Not made yet", sub: "Skald makes the signing key. The steps and the one API request have it filled in." },
      { id: "paste", title: "Made with an API request that had a signing_key", sub: "Paste that value here." },
      { id: "remake", title: "Made without a signing key, or not sure", sub: "Calendly never shows a signing key again, so the webhook is made again with Skald's key." }] };
  }
  return { question: `Has ${name} given you a ${k}?`, choices: [
    { id: "make", title: "No", sub: `Skald makes the ${k}; you paste it into ${name}.` },
    { id: "paste", title: `Yes, ${name} gave me one`, sub: `Paste it here.` }] };
}

// "10:13" today, "27 Oct 10:13" another day, in the zone the page uses (tz.js).
export function at(iso, now = Date.now()) {
  const w = when(iso);
  if (!w) return "";
  const today = when(now);
  return time(iso, { label: false, date: !today || today.day !== w.day });
}

/* "Signing key saved 28 Oct 10:16 by Ann Example (pasted)"; null when none is saved. */
export function savedWords(t) {
  if (!t || !t.set) return null;
  const k = cap(keyWord(t));
  if (t.where === "env") return `${k} kept in the server's environment${t.env ? ` (${t.env})` : ""}.`;
  const on = t.saved_at ? when(t.saved_at) : null;
  const how = t.saved_how === "made by Skald" || t.saved_how === "pasted" ? ` (${t.saved_how})` : "";
  return `${k} saved${on ? ` ${time(t.saved_at, { label: false, date: true })}` : ""}${t.saved_by ? ` by ${t.saved_by}` : ""}${how}.`;
}

// What to copy instead, when a pasted key does not match.
const RIGHT_ONE = {
  calendly: "Copy the signing_key from the request that made the webhook, not your Calendly token or the webhook address.",
  calcom: "Copy the secret from the webhook in Cal.com (Settings > Developer > Webhooks), not an API key.",
  typeform: "Copy the secret from the webhook's settings in Typeform (Connect > Webhooks > Edit), not your Typeform token.",
  stripe: "Copy this endpoint's signing secret in Stripe (Developers > Webhooks, it starts with whsec_), not an API key.",
  hubspot: "Copy the client secret from your HubSpot app's Auth page, not the app ID or an access token.",
};
const time0 = (x) => (typeof x === "string" && when(x) ? x : null);

/* A paste's or a make's answer: {kind: good|bad|warn|info, words}, or null (no check: an older server). */
export function checkWords(check, t, now = Date.now()) {
  if (!check || !check.verdict || !t) return null;
  const name = t.name || t.tool, k = keyWord(t);
  if (check.verdict === "matches") {
    const seen = time0(check.matched) || t.last_real?.at || null;
    const taken = Number(check.taken || 0);
    return { kind: "good", words: `It matches ${name}'s ${noun(t.tool)}${seen ? ` from ${at(seen, now)}` : ""}.${taken ? ` ${taken.toLocaleString("en-GB")} ${noun(t.tool, taken)} taken in.` : ""}` };
  }
  if (check.verdict === "no_match") {
    const last = time0(check.refused_last_at);
    return { kind: "bad", words: `This is not the key ${name} signs with: ${name}'s ${last ? `delivery at ${at(last, now)}` : "last delivery"} still does not match. ${RIGHT_ONE[t.tool] || `Copy the ${k} ${name} gave you.`}` };
  }
  if (check.verdict === "unsigned") {
    return { kind: "bad", words: `${name} sends no signature: the webhook was made without a ${k}. Make it again with Skald's key (steps below).` };
  }
  if (check.verdict === "none_held") return { kind: "info", words: `Saved. Skald checks it against ${name}'s next ${noun(t.tool)}.` };
  return null;
}

/* The last real delivery, in one line; "" when the server does not say (an older Skald). */
export function lastRealWords(t, last = t?.last_real, now = Date.now()) {
  if (!t || last === undefined) return "";
  const what = `Last real ${noun(t.tool)}`;
  if (!last) return `${what}: none yet.`;
  const k = keyWord(t), hm = last.at ? ` at ${at(last.at, now)}` : "";
  if (last.outcome === "accepted" || last.outcome === "accepted_held") return `${what}: accepted${hm}.`;
  if (last.outcome === "bad_signature") return `${what}: refused${hm}, the ${k} does not match.`;
  if (last.outcome === "unsigned") return `${what}: refused${hm}, it had no signature.`;
  return last.words ? `${what}${hm}: ${String(last.words).replace(/\.+$/, "")}.` : "";
}

/* good, bad or wait, from since_saved; null when the server does not say. Good only after a real
   delivery was accepted since the key was saved; bad when only refused or unsigned ones came. */
export function realState(t) {
  const s = t?.since_saved;
  if (!s || typeof s !== "object") return null;
  if (Number(s.accepted || 0) > 0) return "good";
  if (Number(s.refused || 0) > 0 || Number(s.unsigned || 0) > 0) return "bad";
  return "wait";
}
/* What the real deliveries since the key was saved say: unsigned (no signature), no_match, or "". */
export function realTrouble(t) {
  if (realState(t) !== "bad") return "";
  return Number(t.since_saved.unsigned || 0) > 0 && !Number(t.since_saved.refused || 0) ? "unsigned" : "no_match";
}

/* Test Skald's address: [kind, head, more]. It proves the address, never the tool's key. */
export function testWords(r, t, fallback = "The test could not be sent.") {
  const name = t?.name || t?.tool || "the tool";
  if (!r || !r.ok) return ["bad", (r && (r.error || (r.missing ? "The server does not offer this yet." : ""))) || fallback, ""];
  const a = r.answer || {};
  if (r.status !== 200) return ["bad", `Skald's address refused the test (${r.status}): ${a.error || "refused"}.`, ""];
  const head = t && t.tool !== "lead" && t.tool !== "json"
    ? `Skald's address answers. This does not check ${name}'s ${keyWord(t)}: only a real ${noun(t.tool)} does.`
    : `Skald's address answers. This does not check your ${t?.tool === "json" ? "tool" : "server"}: only a real lead does.`;
  const kept = a.would_keep ?? a.records ?? 0;
  return ["ok", head, `The sample was signed, read and not kept; a real one would keep ${kept} of ${a.records ?? 0}.`];
}

// ---- Calendly: its webhooks are made with Calendly's API, usually by a developer -------------
export const CAL_TOKEN = "<your-calendly-token>";
export const CAL_ORG = "<your-organization-uri>";
const AUTH = `  -H "Authorization: Bearer ${CAL_TOKEN}"`;
export const CAL_EVENTS = ["invitee.created", "invitee.canceled", "invitee_no_show.created"];
/* The one request that makes the webhook, with the address and the signing key filled in. */
export function calendlyCreate(addr, key) {
  return ["curl -X POST https://api.calendly.com/webhook_subscriptions \\", `${AUTH} \\`, "  -H \"Content-Type: application/json\" \\",
    `  -d '{"url": "${addr}",`, `       "events": [${CAL_EVENTS.map((e) => `"${e}"`).join(", ")}],`,
    `       "organization": "${CAL_ORG}",`, `       "scope": "organization", "signing_key": "${key}"}'`].join("\n");
}
/* Find the old webhook, then delete it: the organisation, the list, the delete. */
export function calendlyFindDelete(addr) {
  return ["# Your organisation's URI is its current_organization:", "curl -sS https://api.calendly.com/users/me \\", AUTH, "",
    `# The webhooks: the old one has "callback_url": "${addr}"`,
    `curl -sS "https://api.calendly.com/webhook_subscriptions?organization=${CAL_ORG}&scope=organization" \\`, AUTH, "",
    "# Delete the old one, by its uri:", "curl -X DELETE \"<the old webhook's uri>\" \\", AUTH].join("\n");
}
