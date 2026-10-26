// The first-run checklist's items (2.13), worked out from what the page already
// has: the live count and the stored days (app.json), the doctor's lines and each
// hook's state (GET integrations: doctor.integration_checks, roads.hook_states)
// and the site's settings (GET settings). No DOM and no other module here, so
// tests/js/setup.mjs runs it in node. It reads; it counts nothing.
//
// "Pages opened inside the site" (id rsc) is there only when the doctor's Next.js
// line (doctor.next_pages) needs attention: the log has Next.js payloads but not
// the prefetch header. A site that is not Next.js never sees it.
//
// Each item: {id, title, optional, state, says, tech, act}
//   state  done | todo | wait (nothing to judge yet: no visitor today) | unknown
//          (the answer could not be loaded)
//   says   one plain line for the site's owner: no config keys, no server words
//   tech   the doctor's own line and fix, for the server admin (shown folded), or null
//   act    the Set up dialog that fixes it (js/tabs/setup-dialogs.js), or null

const DOC = (status, id) => (status || []).find((x) => x.id === id) || null;
const latest = (m) => {
  if (m?.live?.state === "ok" && m.live.day === m.today) return m.live.figures || null;
  const days = [...(m?.byDay?.values?.() || [])].filter((d) => d.state === "ok");
  return days.length ? days[days.length - 1] : null;
};
const someone = (f) => (f?.hits?.people || 0) > 0 || (f?.readers || 0) > 0;
// The doctor's line and fix, kept as written, for whoever runs the server.
const techOf = (d) => (d ? [`${d.part || d.id}: ${d.says}`, d.fix && d.state !== "OK" ? `Fix: ${d.fix}` : ""].filter(Boolean).join("\n") : null);
const UNKNOWN = "Could not be checked just now. Open this page again in a minute.";

// The script tag in plain words, from the doctor's line (doctor.script_tag).
function scriptWords(d) {
  const says = String(d?.says || "");
  const when = /the last event came (.+)$/.exec(says)?.[1];
  if (d?.state === "OK") return `The tag works: the last event came ${when || "lately"}.`;
  if (!d || d.state === "OFF") return "Optional. One line on your pages adds form steps, clicks and bookings.";
  if (/does not serve/.test(says)) return "The tag is switched on, but Skald's server does not hand it out yet. Your server admin can fix it.";
  if (when) return `No event from the tag since ${when}. Check that it is still on your pages.`;
  return "The tag is not sending yet. Put it on your pages, then test it.";
}

export function setupItems(m, { status = null, tools = null, settings = null, waiting = [] } = {}) {
  const f = latest(m);
  const out = [];

  // 1. The log is read: the doctor's access-log line, else a live count with requests in it.
  const logs = DOC(status, "logs");
  const read = f && (f.requests || 0) > 0;
  if (logs?.state === "OK" || (!logs && read)) out.push({ id: "logs", title: "Logs arriving", state: "done", says: "Visits are arriving: the server's log is read.", tech: null, act: null });
  else out.push({ id: "logs", title: "Logs arriving", state: "todo", says: read ? "Visits arrived before, but the server's log cannot be read now." : "No visit has reached Skald yet. Connect the site's server so its visits arrive.", tech: techOf(logs), act: "logs" });

  // 2. Page assets: the doctor's line; without it, whether any visit counted as people.
  const assets = DOC(status, "assets");
  const T2 = "Visits count as people";
  if (assets?.state === "NEEDS ATTENTION") out.push({ id: "assets", title: T2, state: "todo", says: "Visits arrive, but none counts as a person yet: tell Skald where your pages load their own files.", tech: techOf(assets), act: "assets" });
  else if (assets?.state === "OFF" && /not needed/.test(assets.says)) out.push({ id: "assets", title: T2, state: "done", says: "Nothing to set: every visit from a browser counts.", tech: null, act: null });
  else if (assets?.state === "OK" || someone(f)) out.push({ id: "assets", title: T2, state: "done", says: "Visits count as people: their browsers load your pages' own files.", tech: null, act: null });
  else if (read) out.push({ id: "assets", title: T2, state: "todo", says: "Visits arrive, but none counts as a person yet: tell Skald where your pages load their own files.", tech: null, act: "assets" });
  else out.push({ id: "assets", title: T2, state: "wait", says: "Waits for the first visitor.", tech: null, act: null });

  // 2b. Next.js: only while the log's payloads cannot be told from prefetches.
  const rsc = DOC(status, "rsc");
  if (rsc?.state === "NEEDS ATTENTION") out.push({ id: "rsc", title: "Pages opened inside the site are not counted yet", state: "todo", says: "Your site is built with Next.js. A page opened by a link inside the site sends no page request, so Skald does not count it yet. One line in the web server's log format fixes it.", tech: techOf(rsc), act: "rsc" });

  // 3. Countries: a visit with a country, or the GeoIP file to set.
  const cc = Object.keys(f?.by?.country || {}).filter((k) => k && k !== "Unknown" && !k.startsWith("("));
  if (cc.length) out.push({ id: "countries", title: "Countries shown", state: "done", says: "Visits show their country.", tech: null, act: null });
  else if (someone(f)) out.push({ id: "countries", title: "Countries shown", state: "todo", says: "Visits come without a country. A country file on Skald's server adds it.", tech: "The log carries no country, and no GeoIP country file is set (logs.country_db, or SKALD_COUNTRY_DB in Docker).", act: "countries" });
  else out.push({ id: "countries", title: "Countries shown", state: "wait", says: "Waits for the first visitor.", tech: null, act: null });

  // 4. The script tag (optional): the doctor's line.
  const script = DOC(status, "script");
  if (!status) out.push({ id: "script", title: "Script tag events", optional: true, state: "unknown", says: UNKNOWN, tech: null, act: null });
  else if (script?.state === "OK") out.push({ id: "script", title: "Script tag events", optional: true, state: "done", says: scriptWords(script), tech: null, act: null });
  else out.push({ id: "script", title: "Script tag events", optional: true, state: "todo", says: scriptWords(script), tech: script?.state === "NEEDS ATTENTION" ? techOf(script) : null, act: "script" });

  // 5. A lead hook (optional): a tool tested or receiving, and none whose last real delivery
  // was refused. roads.hook_states keeps state "received" with attention for a refusal (a
  // signature that did not match...): that hook is never done, whatever another tool says
  // (2.21: the line showed a tick above "was refused").
  const all = tools || [];
  const hurt = all.find((t) => t.attention && t.state !== "needs_secret");
  const ok = all.filter((t) => !t.attention && (t.state === "ready" || t.state === "received"));
  const lead = hurt || ok.find((t) => t.state === "received") || ok[0] || all.find((t) => t.tool === "lead");
  if (!tools) out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "unknown", says: UNKNOWN, tech: null, act: null });
  else if (hurt) out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "todo",
    says: hurt.state === "received" ? `${hurt.name}: leads are not arriving. The last one it sent was refused.` : `${hurt.name}: not working yet.`,
    tech: [`${hurt.name}: ${hurt.words}.`, hurt.fix ? `Fix: ${hurt.fix}` : ""].filter(Boolean).join("\n"), act: "lead" });
  else if (ok.length) out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "done", says: `${lead.name}: ${lead.words}.`, tech: null, act: null });
  else out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "todo", says: "Optional. Your forms or booking tool tell Skald about each lead.", tech: null, act: "lead" });

  // 6. Mail: a report on, and a recipient who confirmed.
  if (!settings) out.push({ id: "mail", title: "Mail recipient confirmed", state: "unknown", says: UNKNOWN, tech: null, act: null });
  else {
    const to = settings["mail.to"]?.value || [];
    const on = settings["mail.daily"]?.value || settings["mail.weekly"]?.value;
    const done = on && to.length && !waiting.length;
    out.push({ id: "mail", title: "Mail recipient confirmed", state: done ? "done" : "todo",
      says: done ? `The ${settings["mail.daily"]?.value ? "daily" : "weekly"} mail goes to ${to.length} confirmed recipient${to.length === 1 ? "" : "s"}.`
        : waiting.length ? `${waiting.length} recipient${waiting.length === 1 ? " has" : "s have"} not confirmed yet (the link in their mail).`
          : !to.length ? "Nobody gets the daily mail yet." : "The daily and the weekly mail are both off.",
      tech: null, act: done ? null : "mail" });
  }

  // 7. Privacy: someone chose what is kept about people (not left at the default).
  if (!settings) out.push({ id: "privacy", title: "Privacy settings chosen", state: "unknown", says: UNKNOWN, tech: null, act: null });
  else {
    const ips = settings["privacy.keep_ips"];
    // full, short or off (2.15.0); true and false from an older answer.
    const mode = ips?.value === true ? "full" : ips?.value === false || !ips?.value ? "off" : ips.value;
    const chosen = ips && ips.source && ips.source !== "default";
    out.push({ id: "privacy", title: "Privacy settings chosen", state: chosen ? "done" : "todo",
      says: chosen ? `IP addresses ${mode !== "off" ? `kept${mode === "short" ? " shortened" : ""} with each visit${settings["privacy.keep_days"]?.value ? ` for ${settings["privacy.keep_days"].value} days` : ""}` : "not kept"}.` : "Choose what is kept about visitors, then copy the wording for your privacy notice.",
      tech: null, act: chosen ? null : "privacy" });
  }

  // 8. Search Console (optional, 2.40): the site's Google property connected.
  if (!settings) out.push({ id: "search", title: "Search Console connected", optional: true, state: "unknown", says: UNKNOWN, tech: null, act: null });
  else {
    const prop = settings["search.google_property"]?.value;
    if (prop) out.push({ id: "search", title: "Search Console connected", optional: true, state: "done", says: `Google search figures come in from ${prop}.`, tech: null, act: null });
    else out.push({ id: "search", title: "Search Console connected", optional: true, state: "todo", says: "Optional. Connect Google Search Console to see the searches that bring people here.", tech: null, act: "search" });
  }
  return out;
}

// Done when every item that is not optional is done.
export const setupDone = (items) => items.every((i) => i.optional || i.state === "done");

// 2.39: the lines an AI agent can do (their act is the job's id), in the contract's order
// (docs/plans/2026-10-26-agent-everywhere.md). countries and mail stay by hand. The server's
// setup_left mirrors this.
export const AGENT_JOBS = ["logs", "script", "lead", "rsc", "assets", "privacy", "search"];
/* The open lines an agent can do, as job ids in that order: their Set up is offered. */
export const agentJobsLeft = (items) => AGENT_JOBS.filter((id) => (items || []).some((i) => i.act === id && i.state !== "done"));
