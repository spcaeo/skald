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

async function skaldLead(ref, action, fields = {}) {
  try {
    const secret = process.env.SKALD_LEAD_SECRET || EMBEDDED_SECRET;
    if (!secret || !ref || !action) return false;
    const { email, name, ...extra } = fields || {};
    const lead = { ...extra, external_ref: String(ref), action: String(action) };
    if (email) lead.email = String(email);
    if (name) lead.name = String(name);
    if (lead.vid !== undefined && !VID.test(String(lead.vid))) delete lead.vid;
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

module.exports = { skaldLead };
