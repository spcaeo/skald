// Settings › To do (v2): one list of what needs this reader now, most important first. Worked
// out from answers the page already asks for; no DOM and no imports, so node tests it.
//
//   setup     the set-up lines (setup-items.js): each open line, its own row (setup=finish-<act>)
//   sites     GET sites: a site waiting for proof that it is yours, a paused site
//   plan      /me's plan (hosted): this month's requests at 80 % or more
//   invites   GET team: invites not accepted yet
//   totp      /me: two-step sign-in off for this reader (accounts only)
//   tokens    GET tokens: tokens never used for 2 weeks after they were made, or unused for 90 days
//
// The mail line (setup-items.js "mail") already says when a recipient has not confirmed.
// Owners and admins (manage) see the site's and the organisation's rows; everyone sees their own.
//
// A row: {id, scope: site | org | you, level: bad | warn | info, says, verb, act | href, optional}
//   act   a set-up line's dialog (the Finish set-up dialog for that line), else
//   href  the page that fixes it

const DAY = 86400000;
const LEVEL = { bad: 0, warn: 1, info: 2 };
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const VERB = { assets: "Fix", rsc: "Fix", countries: "Fix", privacy: "Review" };
/* A set-up line's one word: Set up, Fix or Review. */
export const verbOf = (i) => (i.id === "logs" && /cannot be read now/.test(i.says || "") ? "Fix" : VERB[i.act] || "Set up");

/* The set-up lines still open (not done, with a dialog that does them). */
export const openLines = (items) => (items || []).filter((i) => i.act && i.state !== "done");
/* "2 left, 1 optional" (the owner, 2026-10-26: "1 of 5 left" while two were open): every open
   line counts, the optional among them named; only optional ones left: "All set, 2 optional". */
export function leftWords(items) {
  const open = openLines(items);
  const opt = open.filter((i) => i.optional).length;
  if (open.length === opt) return `All set${opt ? `, ${opt} optional` : ""}`;
  return `${open.length} left${opt ? `, ${opt} optional` : ""}`;
}
/* The one button's words: what is left, or the optional lines once the rest is done. */
export function finishWords(items) {
  const open = openLines(items);
  const req = open.filter((i) => !i.optional).length;
  return req ? `Finish set-up (${open.length} left)` : `Add the optional (${open.length})`;
}

const when = (iso) => { const t = Date.parse(iso || ""); return Number.isFinite(t) ? t : null; };

export function todoItems({ setup = [], sites = null, plan = null, invites = null, totpOn = true, accounts = false, tokens = null, manage = false, saas = false, now = Date.now() } = {}) {
  const out = [];
  if (manage) {
    for (const i of openLines(setup)) {
      const level = i.id === "logs" ? "bad" : i.optional ? "info" : "warn";
      out.push({ id: `setup-${i.id}`, scope: "site", level, says: i.says, title: i.title, verb: verbOf(i), act: i.act, optional: !!i.optional });
    }
    for (const s of sites || []) {
      if (s.status === "removed") continue;
      if (s.verify?.state === "pending" && s.status === "active")
        out.push({ id: `proof-${s.name}`, scope: "org", level: "bad", says: `${s.name} waits for proof that it is yours. Nothing is collected until then.`, verb: "Confirm", href: "#settings/org/sites" });
      else if (s.status === "paused")
        out.push({ id: `paused-${s.name}`, scope: "org", level: "warn", says: `${s.name} is paused: nothing is collected for it.`, verb: "Review", href: "#settings/org/sites" });
    }
    const u = saas ? plan?.usage : null;
    if (u && Number(u.percent) >= 80)
      out.push({ id: "usage", scope: "org", level: Number(u.percent) >= 100 ? "bad" : "warn",
        says: Number(u.percent) >= 100 ? "This month's requests are used up: new log lines are turned away." : `${u.percent}% of this month's requests are used.`,
        verb: "Review", href: "#settings/org/billing" });
    const waiting = (invites || []).length;
    if (waiting) out.push({ id: "invites", scope: "org", level: "info", says: `${plural(waiting, "invite is", "invites are")} not accepted yet.`, verb: "Review", href: "#settings/org/people" });
    const idle = (tokens || []).filter((t) => {
      if (t.revoked_at) return false;
      const used = when(t.last_used), made = when(t.created_at);
      return used != null ? now - used >= 90 * DAY : made != null && now - made >= 14 * DAY;
    }).length;
    if (idle) out.push({ id: "tokens", scope: "org", level: "info", says: `${plural(idle, "token has", "tokens have")} not been used for a long time. Revoke what you no longer use.`, verb: "Review", href: "#settings/ai/assistants?sub=tokens" });
  }
  if (accounts && !totpOn) out.push({ id: "totp", scope: "you", level: "warn", says: "Two-step sign-in is off for your account.", verb: "Set up", href: "#settings/you/account" });
  // Most important first: broken, then waiting on you, then nice to have; the site's before the organisation's.
  const SCOPE = { site: 0, org: 1, you: 2 };
  return out.map((x, i) => [x, i]).sort((a, b) => LEVEL[a[0].level] - LEVEL[b[0].level] || SCOPE[a[0].scope] - SCOPE[b[0].scope] || a[1] - b[1]).map(([x]) => x);
}
