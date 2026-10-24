// "Set up with your AI agent" (the Add a site wizard, steps 3 to 5): the agents to
// choose from, where each one pastes the line, the code hidden in the line, the
// agent's report in plain words, and the checklist of what has happened so far.
// No DOM here, so tests/js/agent-setup.mjs reads it directly.
//
// The line comes from POST <page>/sites/agentlink {site, leads} (kit_api.py):
// {line, llms_url, steps_url, expires_at, token_id, link_id, cancelled}. A site has one
// live line: a new one ends the older ones whose keys were not taken (`cancelled`). It holds a one-time
// code that the agent swaps once for the keys, by curl, into a file on the server.
// The code is never in the address, never kept, never logged; link_id (16 hex, a
// hash of the code) is the only thing the address holds, so a reload at step 5 can
// still watch the same line (POST <page>/sites/agentstatus {site, link_id}).

// shell: the agent can run commands in the site's project or on its server; the
// chat-only ones get the one-command install instead (conn-send.js runPanel).
export const AGENTS = [
  { id: "claude-code", title: "Claude Code", sub: "In a terminal", shell: true,
    where: "Paste it into Claude Code, in a terminal in the site's project folder, or on the site's server." },
  { id: "codex", title: "Codex", sub: "In a terminal", shell: true,
    where: "Paste it into Codex, in a terminal in the site's project folder, or on the site's server." },
  { id: "cursor", title: "Cursor", sub: "In the editor", shell: true,
    where: "Open the site's project in Cursor, and paste it into the chat in Agent mode." },
  { id: "chat", title: "Claude.ai or ChatGPT", sub: "Chat only", shell: false,
    where: "A chat in the browser cannot run commands on your server. So here is one command to paste on the server yourself." },
  { id: "other", title: "Another agent", sub: "One that can run shell commands", shell: true,
    where: "Paste it into your agent, in the site's project folder or on its server. It needs to run shell commands there." },
];
// The quieter way out: today's steps (How visits reach Skald, Install, Test and finish).
export const HAND = "hand";
export const HAND_WORDS = { title: "No AI agent: set it up by hand", sub: "Choose how the visits reach Skald, then install." };

// "Is it safe to paste this into a chat?", under the line (the owner's words, 2026-10-24,
// checked against the code). The tokens are on Settings > Connections, under Your tokens.
export const TOKENS_AT = "Settings > Connections > Your tokens";
export const SAFE_TITLE = "Is it safe to paste this into a chat?";
export const SAFE = [
  "Yes. The line holds a one-time code, not a password or a key.",
  "The keys come out once. When your agent takes them, the code can never give them again. A code nobody uses stops after 24 hours.",
  "Your agent is told to save the keys straight into a locked file and never show them in the chat. Skald gives them only to a command-line download such as curl, and turns away web readers and fetch tools, which could pass them into a chat.",
  "The keys work for this one site only. The sending key can only send log lines. The lead secret sends leads and can read back this site's lead list (reference, stage, time), never names, emails, addresses or visitor IDs. Neither can open your dashboard or see your visitors.",
  "Skald keeps only a scrambled copy of the code (a hash), never the code itself, and never writes it to a log.",
  "Until the keys are taken, treat the line like a house key: paste it only into your own agent. Changed your mind? Press Cancel this line and it stops at once. A new line also cancels an older one whose keys were not taken yet.",
  `If your site already has a lead secret, the agent gets that same one (unless your Skald keeps it in the server's settings; then the keys hold none). After the set-up you can remove the agent's sending key ("AI agent set-up") in ${TOKENS_AT}, and make a new lead secret in Settings > Integrations.`,
];
export const CANCELLED_WORDS = "Cancelled. This line no longer works.";
export const OLD_CANCELLED = "The old line was cancelled.";
/* Step 5, once the keys are taken: [the headline, what to do if it was not your agent]. */
export const keysWords = (at) => [`Your agent took the keys at ${at}. The code is used up: it cannot give the keys again.`,
  `Didn't your agent do this? Cancel the line, remove the key in ${TOKENS_AT}, and make a new line.`];

export const agentOf = (id) => AGENTS.find((a) => a.id === id) || null;
export const isAgent = (id) => Boolean(agentOf(id));
// The ids the address may hold: an agent's, or hand.
export const agentKey = (id) => (id === HAND || isAgent(id) ? id : "");
export const isLinkId = (v) => /^[0-9a-f]{16}$/.test(String(v || ""));

/* The code in an answer: the part of steps_url between /traffic-kit/ and /steps,
   else the word after "use code" in the line. "" when neither has one. */
export function codeOf(answer) {
  const a = answer || {};
  const m = /\/traffic-kit\/([A-Za-z0-9_-]{16,})\/steps\b/.exec(String(a.steps_url || ""));
  if (m) return m[1];
  const w = /\buse code ([A-Za-z0-9_-]{16,})/.exec(String(a.line || ""));
  return w ? w[1] : "";
}

export const HIDDEN = "••••••••••••";
/* The line with its code hidden, as shown before "Show code". */
export function masked(line, code) {
  const text = String(line || "");
  return code ? text.split(code).join(HIDDEN) : text;
}

/* "for 23 more hours", "for 40 more minutes", or "" once it ran out. */
export function timeLeft(expires, now = Date.now()) {
  const left = (Date.parse(expires || "") || 0) - now;
  if (left <= 0) return "";
  const min = Math.round(left / 60000);
  if (min < 60) return `for ${Math.max(1, min)} more minute${min === 1 ? "" : "s"}`;
  const hours = Math.round(min / 60);
  return `for ${hours} more hour${hours === 1 ? "" : "s"}`;
}
export const expired = (expires, now = Date.now()) => Boolean(expires) && (Date.parse(expires) || 0) <= now;

export const PRIVACY_AT = "Set this in Settings > Data retention > People.";
export const REPORT_NOTE = "Sent by your agent. Check it before you use it.";
const list = (x) => (Array.isArray(x) ? x.map((v) => String(v)).filter(Boolean) : []);
const text = (x) => (x == null ? "" : String(x).trim());

/* The agent's report as lines: [{name, value, kind}] in the order a person reads
   them. kind: "list" (value is an array), "url" (value is a URL), "warn" (left for
   you), "noted" ([words, a small note under them]), else plain words. A field the report leaves out is left out here. */
export function reportLines(report) {
  const r = report || {};
  const out = [];
  const add = (name, value, kind = "") => { if (Array.isArray(value) ? value.length : value) out.push({ name, value, kind }); };
  add("Hosting", text(r.hosting));
  add("Web server", text(r.server));
  add("Access log", text(r.log_path));
  add("Built with", text(r.framework));
  add("Page assets", list(r.asset_paths).join(", "));
  if (text(r.script_tag)) add("Script tag", `added in ${text(r.script_tag)}`);
  const leads = (Array.isArray(r.leads) ? r.leads : []).filter((l) => l && (l.tool || l.file))
    .map((l) => [text(l.tool), text(l.file) ? `in ${text(l.file)}` : ""].filter(Boolean).join(" "));
  add("Leads", leads, "list");
  // The agent only reports the owner's choice; it is set on Settings > Data retention > People.
  const p = r.privacy;
  if (p && typeof p === "object") {
    const days = Number.isInteger(p.days) && p.days > 0 ? `for ${p.days} days` : "with no end date";
    const keep = p.keep_ips === true ? `Keep IP addresses ${days}` : p.keep_ips === false ? "Keep no IP addresses" : "";
    if (keep) add("Privacy", [keep, PRIVACY_AT], "noted");
    if (/^https?:\/\/\S+$/.test(text(p.notice_url))) add("Privacy notice", text(p.notice_url), "url");
  }
  if (r.nextjs_log_field === true) add("Next.js", "the log field for pages opened inside the site was added");
  else if (r.nextjs_log_field === false) add("Next.js", "the log field was not added");
  add("Files changed", list(r.changed_files), "list");
  add("Left for you", list(r.left_for_user), "warn");
  add("Notes", text(r.notes));
  return out;
}

/* The asset paths to offer with "Use these": the report's, when they differ from the
   site's own (site.asset_prefixes), at most ASSETS_MAX (the setting's limit). [] when
   there is nothing to change. */
export const ASSETS_MAX = 10;
export function newAssets(report, current) {
  const got = list(report?.asset_paths).filter((p) => p.startsWith("/")).slice(0, ASSETS_MAX);
  if (!got.length) return [];
  const now = list(current);
  const same = got.length === now.length && got.every((p) => now.includes(p));
  return same ? [] : got;
}

/* The checklist on "Watch it connect": [{id, done, words, at}], from agentstatus's
   answer and what the page saw itself (seen: {lines, tag, lead}, each true, false
   for a problem, null when the check could not tell, or undefined while waiting). The script tag and the test lead
   are only on it when the agent's report says it added them. */
export function watchItems(status, seen = {}) {
  const s = status || {};
  const report = s.report || null;
  const items = [
    { id: "opened", done: Boolean(s.opened_at), at: s.opened_at || "", words: s.opened_at ? "Your agent read the steps" : "Waiting for your agent to read the steps" },
    { id: "keys", done: Boolean(s.keys_at), at: s.keys_at || "", words: s.keys_at ? "It took the keys, once" : "Waiting for it to take the keys" },
    { id: "report", done: Boolean(s.reported_at), at: s.reported_at || "", words: s.reported_at ? "It sent its report" : "Waiting for its report" },
    { id: "lines", done: seen.lines === true, at: "", words: seen.lines === true ? "The first log lines arrived" : "Waiting for the first log lines" },
  ];
  if (text(report?.script_tag)) {
    items.push({ id: "tag", done: seen.tag === true, bad: seen.tag === false, at: "",
      words: seen.tag === true ? "The script tag is on the home page" : seen.tag === false ? "The script tag is not working yet"
        : seen.tag === null ? "Skald could not look for the script tag just now" : "Looking for the script tag on the home page" });
  }
  if (Array.isArray(report?.leads) && report.leads.length) {
    items.push({ id: "lead", done: seen.lead === true, at: "", words: seen.lead === true ? "A test lead arrived" : "Waiting for a test lead" });
  }
  return items;
}

/* What agentstatus's state means when it stops the watch: words, or "" to go on. */
export function stopWords(status) {
  const s = status || {};
  if (s.state === "expired" && !s.keys_at) return "The line ran out before your agent took the keys. Go Back and make a new line.";
  if (s.state === "expired" && !s.reported_at) return "The line ran out before your agent sent its report. The log test below still shows whether visits arrive.";
  if (s.state === "cancelled") return "This line was ended: a newer line replaced it, or it was cancelled. Go Back to send the newest line.";
  if (s.state === "unknown") return "Skald does not know this line any more. Go Back and make a new line.";
  return "";
}
