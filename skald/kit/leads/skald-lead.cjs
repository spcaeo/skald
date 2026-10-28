"use strict";
/*
 * Skald lead helper for __SITE__: one file, one function (Node 18 or later).
 *
 *   const { skaldLead } = require("./skald-lead.cjs");
 *   await skaldLead(entryId, "contact", { email, name });
 *
 * From an ES module (import, "type": "module"), the same file works:
 *   import { skaldLead } from "./skald-lead.cjs";
 *
 * It tells Skald a lead was made: a signed POST to
 * __URL__
 * Call it after your form is saved. It waits at most 3 seconds, never throws,
 * and resolves true when Skald kept the lead (false otherwise: you can send
 * it again later, a repeat is never counted twice).
 *
 * __SECRET_NOTE__
 *
 * ref     your own id for the lead (the same lead always sends the same id)
 * action  a short lowercase word: "contact", "demo", "signup", "trial"
 * fields  { email, name } and any other field, such as { label: "sales",
 *         stage: "won", vid: req.cookies.skald_vid, test: true }. See README.md.
 *         ip: the visitor's address, so Skald records the lead's country
 *         (looked up, then dropped at once). Read it in the request that made
 *         the lead, from the header your host sets (README.md, "The visitor's
 *         address"):
 *           Vercel, Next.js:  request.headers.get("x-forwarded-for")
 *                             a server action: (await headers()).get("x-forwarded-for")
 *           Express:          req.ip (behind a proxy: app.set("trust proxy", true))
 *           Cloudflare:       request.headers.get("cf-connecting-ip")
 *         A list ("a, b") is read as its first address; anything that is not
 *         an IPv4 or IPv6 address is not sent.
 *         Money (Skald 2.32): { value: 49.99, currency: "USD",
 *         customer_ref: "your-customer-id", tags: { plan: "pro" } } (the
 *         amount in the currency's units; never an email as customer_ref).
 *         A refund: stage "refunded" on the sale's ref, value = the total
 *         refunded so far (no value: all of it).
 */
const crypto = require("node:crypto");

const SKALD_URL = "__URL__";
const EMBEDDED_SECRET = "__SECRET__";
const VID = /^skv_[A-Za-z0-9_-]{22}$/;
const net = require("node:net");

// The visitor's address from what was passed: the first of a list, without a port; else null.
function visitorIp(value) {
  let got = String(value ?? "").split(",")[0].trim();
  const m = /^(\d{1,3}(?:\.\d{1,3}){3}):\d{1,5}$/.exec(got) || /^\[([0-9A-Fa-f:.]+)\](?::\d{1,5})?$/.exec(got);
  if (m) got = m[1];
  return net.isIP(got) ? got : null;
}

async function skaldLead(ref, action, fields = {}) {
  try {
    const secret = process.env.SKALD_LEAD_SECRET || EMBEDDED_SECRET;
    if (!secret || !ref || !action) return false;
    const { email, name, ...extra } = fields || {};
    const lead = { ...extra, external_ref: String(ref), action: String(action) };
    if (email) lead.email = String(email);
    if (name) lead.name = String(name);
    if (lead.vid !== undefined && !VID.test(String(lead.vid))) delete lead.vid;
    if (lead.ip !== undefined) {
      const ip = visitorIp(lead.ip);
      if (ip) lead.ip = ip; else delete lead.ip;
    }
    const body = JSON.stringify(lead);
    const t = Math.floor(Date.now() / 1000);
    const sig = crypto.createHmac("sha256", secret).update(`${t}.${body}`).digest("hex");
    const res = await fetch(SKALD_URL, {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json", "User-Agent": "skald-lead-node/1",
                 "X-Skald-Signature": `t=${t},v1=${sig}` },
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

module.exports = { skaldLead, visitorIp };
