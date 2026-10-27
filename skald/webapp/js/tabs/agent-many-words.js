// "Lines for your sites" (2.40, agent-many.js): the words and the pure parts, no DOM, so
// tests/js/agent-many.mjs reads them in node.
//
// The owner (2026-10-26): people work on each site on its own (its own repo, its own Claude
// Code or Codex session) and give their go per site. So every site gets its OWN line with its
// OWN one-time code (POST sites/agentlink, one per site); lines for different sites never end
// each other, and ten sessions can set up ten sites at once.
//
// The address: lines=<value> (js/routekeys.js), one key for the whole view:
//   all            every site of the organisation, with its open jobs and its line
//   site.<site>    the same, with that site's line and its watch open
//   mcp.<site>     that site's "two lines" (Skald's MCP for that one session, then
//                  "Set up Skald for this site")
//   add            the box that adds several new sites at once
// A site's name is the only thing in it: never a line, a code or a token.

export const KEY = "lines";
export const VIEWS = ["all", "site", "mcp", "add"];
const SITE = /^[a-z0-9](?:[a-z0-9.-]{0,98}[a-z0-9])?$/;
export const MOST_NEW = 25;            // names the box adds at once

/* lines=<value> as {view, site}, or null when it is not one this page knows. */
export function parseLines(value) {
  const v = String(value ?? "");
  if (v === "all" || v === "add") return { view: v, site: "" };
  const dot = v.indexOf(".");
  if (dot < 0) return null;
  const view = v.slice(0, dot);
  const site = v.slice(dot + 1);
  if (!["site", "mcp"].includes(view) || !SITE.test(site)) return null;
  return { view, site };
}

/* {view, site} as the address's value; "all" for anything else. */
export function linesValue({ view = "all", site = "" } = {}) {
  if ((view === "site" || view === "mcp") && SITE.test(String(site))) return `${view}.${site}`;
  return view === "add" ? "add" : "all";
}

/* The names typed in the box: one per line, or split by spaces and commas; an address
   becomes its host (https://www.example.com/x -> www.example.com), lower case, each once.
   {names, bad: [what is not a site name], more: how many past MOST_NEW were left out}. */
export function siteNames(text) {
  const names = [];
  const bad = [];
  for (const raw of String(text || "").split(/[\s,;]+/)) {
    if (!raw) continue;
    const host = raw.trim().toLowerCase().replace(/^[a-z]+:\/\//, "").replace(/[/?#].*$/, "").replace(/:\d+$/, "").replace(/\.$/, "");
    if (!SITE.test(host) || !host.includes(".")) { bad.push(raw.slice(0, 80)); continue; }
    if (!names.includes(host)) names.push(host);
  }
  return { names: names.slice(0, MOST_NEW), bad, more: Math.max(0, names.length - MOST_NEW) };
}

// What a site's newest line is doing (agentstatus's state), in plain words.
export const LINE_STATE = {
  waiting: "Line sent: waiting for the agent to read it",
  opened: "The agent read the steps",
  keys_taken: "The agent took the keys",
  expired: "The line ran out",
  cancelled: "The line was ended",
  unknown: "",
};
/* The words for a site's line, from agentleft's `line` or agentstatus's answer. */
export function lineWords(line) {
  if (!line) return "No line yet.";
  if (line.reported_at && ["keys_taken", "opened", "waiting"].includes(line.state)) return "The agent sent its report";
  return LINE_STATE[line.state] || "No line yet.";
}
/* A line still at work: the view keeps asking how far it got. */
export const live = (line) => Boolean(line && ["waiting", "opened", "keys_taken"].includes(line.state) && !line.reported_at);

/* What is left on a site, in one plain line. */
export function leftWords(row) {
  if (!row) return "";
  if (row.pending) return "Waiting for its domain to be verified: nothing is collected until then.";
  const needed = (row.left || []).filter((x) => !x.optional);
  if (row.done && !(row.jobs || []).length) return "Everything is set up.";
  if (!needed.length) return `Everything needed is set up.${(row.jobs || []).length ? " Optional lines are left." : ""}`;
  return `${needed.length} needed line${needed.length === 1 ? "" : "s"} left: ${needed.map((x) => x.title).join(", ")}.`;
}

/* The sites "Make a line for each site" makes a line for: a job left, not waiting to be verified. */
export const lineSites = (rows) => (rows || []).filter((r) => r && !r.pending && r.status !== "removed" && (r.jobs || []).length).map((r) => r.site);

// ---- the two lines, for one site --------------------------------------------------------
export const TOKEN_NAME = (site) => `AI agent (MCP + set-up): ${site}`.slice(0, 60);
export const LINE_TWO = "Set up Skald for this site";
/* The first line for each assistant, with this site's own token in it (shown once, never
   kept by the page). Claude Code: its default scope (local) keeps the server to the folder it
   runs in, so ten sites' sessions each have their own. Codex: one server per site in
   ~/.codex/config.toml (http_headers, Codex's MCP docs), named after the site. */
export function twoLines(site, url, token) {
  const name = `skald-${String(site).replace(/\./g, "-")}`;
  return {
    claude: `claude mcp add --transport http skald ${url} --header "Authorization: Bearer ${token}"`,
    codex: `printf '\\n[mcp_servers.${name}]\\nurl = "${url}"\\nhttp_headers = { Authorization = "Bearer ${token}" }\\n' >> ~/.codex/config.toml`,
    two: LINE_TWO,
  };
}
export const TWO_SAFE = [
  "Paste line 1 into a terminal in this site's own project folder: it puts the token in your assistant's own settings. Never paste the token into a chat message.",
  "The token reads this one site's figures and can make set-up lines for it, nothing else. It sees no visitor addresses.",
  "Then type line 2 into the assistant's chat. It looks at what is left, makes this site's one-time line, and follows it.",
  "Remove the token any time in Settings › AI assistants › Tokens & links. It also stops at once if its maker is no longer an owner or admin.",
];
