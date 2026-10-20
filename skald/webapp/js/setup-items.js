// The first-run checklist's items (2.13), worked out from what the page already
// has: the live count and the stored days (app.json), the doctor's lines and each
// hook's state (GET integrations: doctor.integration_checks, roads.hook_states)
// and the site's settings (GET settings). No DOM and no other module here, so
// tests/js/setup.mjs runs it in node. It reads; it counts nothing.
//
// Each item: {id, title, optional, state, says, fix: [words, href] | null}
//   state  done | todo | wait (nothing to judge yet: no visitor today) | unknown
//          (the answer needs a page this reader cannot load)

// The doctor says "requests for /x/ seen in the log": a sentence here.
const said = (t) => { const s = String(t || "").trim(); return s ? `${s[0].toUpperCase()}${s.slice(1)}${/[.!?]$/.test(s) ? "" : "."}` : s; };
const DOC = (status, id) => (status || []).find((x) => x.id === id) || null;
const latest = (m) => {
  if (m?.live?.state === "ok" && m.live.day === m.today) return m.live.figures || null;
  const days = [...(m?.byDay?.values?.() || [])].filter((d) => d.state === "ok");
  return days.length ? days[days.length - 1] : null;
};
const someone = (f) => (f?.hits?.people || 0) > 0 || (f?.readers || 0) > 0;

export function setupItems(m, { status = null, tools = null, settings = null, waiting = [] } = {}) {
  const f = latest(m);
  const out = [];

  // 1. The log is read: the doctor's access-log line, else a live count with requests in it.
  const logs = DOC(status, "logs");
  if (logs) out.push({ id: "logs", title: "Logs arriving", state: logs.state === "OK" ? "done" : "todo", says: said(logs.says), fix: logs.state === "OK" ? null : [logs.fix || "Check the log file", "#settings/sites"] });
  else if (f && (f.requests || 0) > 0) out.push({ id: "logs", title: "Logs arriving", state: "done", says: "The server's access log is being read.", fix: null });
  else out.push({ id: "logs", title: "Logs arriving", state: "todo", says: "No request read yet today.", fix: ["Where the log is: Settings > Sites > Log file", "#settings/sites"] });

  // 2. Page assets: the doctor's line; without it, whether any visit counted as people.
  const assets = DOC(status, "assets");
  if (assets) out.push({ id: "assets", title: "Pages render (page assets)", state: assets.state === "NEEDS ATTENTION" ? "todo" : "done", says: said(assets.says), fix: assets.state === "NEEDS ATTENTION" ? [assets.fix || "Set the page assets", "#settings/sites"] : null });
  else if (someone(f)) out.push({ id: "assets", title: "Pages render (page assets)", state: "done", says: "Visits are counted as people: their browsers fetched the pages' own files.", fix: null });
  else if (f && (f.requests || 0) > 0) out.push({ id: "assets", title: "Pages render (page assets)", state: "todo", says: "Requests arrive, but no visit counted as people: no browser fetched the page assets Skald looks for.", fix: ["Set the page assets: Settings > Sites > Page assets", "#settings/sites"] });
  else out.push({ id: "assets", title: "Pages render (page assets)", state: "wait", says: "Waits for the first visitor.", fix: null });

  // 3. Countries: a visit with a country, or the GeoIP file to set.
  const cc = Object.keys(f?.by?.country || {}).filter((k) => k && k !== "Unknown" && !k.startsWith("("));
  if (cc.length) out.push({ id: "countries", title: "Countries on", state: "done", says: "Visits carry a country.", fix: null });
  else if (someone(f)) out.push({ id: "countries", title: "Countries on", state: "todo", says: "Visits come with no country: this log has none, and no GeoIP file is set.", fix: ["How to set a GeoIP country file", "#help?part=faq"] });
  else out.push({ id: "countries", title: "Countries on", state: "wait", says: "Waits for the first visitor.", fix: null });

  // 4. The script tag (optional): the doctor's line.
  const script = DOC(status, "script");
  if (!status) out.push({ id: "script", title: "Script tag events", optional: true, state: "unknown", says: "An admin sees this in Settings > Integrations.", fix: null });
  else if (script?.state === "OK") out.push({ id: "script", title: "Script tag events", optional: true, state: "done", says: said(script.says), fix: null });
  else out.push({ id: "script", title: "Script tag events", optional: true, state: "todo", says: script ? said(script.says) : "Not set up.", fix: [script?.state === "OFF" ? "Add the script tag (optional)" : script?.fix || "Check the script tag", "#settings/integrations"] });

  // 5. The lead hook (optional): tested or receiving.
  const lead = (tools || []).find((t) => t.tool === "lead");
  if (!tools) out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "unknown", says: "An admin sees this in Settings > Integrations.", fix: null });
  else if (lead && (lead.state === "ready" || lead.state === "received")) out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "done", says: `Lead hook: ${lead.words}.`, fix: null });
  else out.push({ id: "lead", title: "Lead hook tested", optional: true, state: "todo", says: lead ? `Lead hook: ${lead.words}.` : "Not set up.", fix: ["Make its secret and send a test: Settings > Integrations", "#settings/integrations"] });

  // 6. Mail: a report on, and a recipient who confirmed.
  if (!settings) out.push({ id: "mail", title: "Mail recipient confirmed", state: "unknown", says: "An admin sees this in Settings > Mail.", fix: null });
  else {
    const to = settings["mail.to"]?.value || [];
    const on = settings["mail.daily"]?.value || settings["mail.weekly"]?.value;
    const ok = on && to.length && !waiting.length;
    out.push({ id: "mail", title: "Mail recipient confirmed", state: ok ? "done" : "todo",
      says: ok ? `The ${settings["mail.daily"]?.value ? "daily" : "weekly"} mail goes to ${to.length} confirmed recipient${to.length === 1 ? "" : "s"}.`
        : waiting.length ? `${waiting.length} recipient${waiting.length === 1 ? " has" : "s have"} not confirmed yet (the link in their mail).`
          : !to.length ? "No recipient yet." : "The daily and the weekly mail are both off.",
      fix: ok ? null : ["Settings > Mail", "#settings/mail"] });
  }

  // 7. Privacy: someone chose what is kept about people (not left at the default).
  if (!settings) out.push({ id: "privacy", title: "Privacy settings chosen", state: "unknown", says: "An admin sees this in Settings > Data retention.", fix: null });
  else {
    const ips = settings["privacy.keep_ips"];
    // full, short or off (2.15.0); true and false from an older answer.
    const mode = ips?.value === true ? "full" : ips?.value === false || !ips?.value ? "off" : ips.value;
    const chosen = ips && ips.source && ips.source !== "default";
    out.push({ id: "privacy", title: "Privacy settings chosen", state: chosen ? "done" : "todo",
      says: chosen ? `IP addresses ${mode !== "off" ? `kept${mode === "short" ? " shortened" : ""} with each visit${settings["privacy.keep_days"]?.value ? ` for ${settings["privacy.keep_days"].value} days` : ""}` : "not kept"}.` : "The defaults apply: choose what is kept about people, and say so in your privacy notice.",
      fix: chosen ? null : ["Settings > Data retention > People", "#settings/retention"] });
  }
  return out;
}

// Done when every item that is not optional is done.
export const setupDone = (items) => items.every((i) => i.optional || i.state === "done");
