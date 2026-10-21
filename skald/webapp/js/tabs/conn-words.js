// Settings > Connections: the words the page and its dialogs share. What a
// token is for, said from its scopes; the ways a site's visits can reach
// Skald; and the common problems, each with its likely cause and the fix.
// No DOM here, so tests/js/connections.mjs checks it directly.

// A token's purpose in words, from its scopes (accounts/apitokens.py SCOPES).
export function purposeOf(scopes) {
  const has = new Set((Array.isArray(scopes) ? scopes : String(scopes || "").split(/[,\s]+/)).filter(Boolean));
  const out = [];
  if (has.has("ingest")) out.push("Sending logs");
  if (has.has("read_private")) out.push("Reading figures and addresses");
  else if (has.has("read")) out.push("Reading figures");
  if (has.has("mcp")) out.push("AI assistant (MCP)");
  return out.length ? out.join(", ") : "Nothing (no scope)";
}

// How a site's visits can reach Skald. `log`: a log is sent to the ingest
// address (and the Test reads sites/status); `kit`: an install kit exists.
export const METHODS = [
  { id: "docker", title: "A Linux server with nginx or Apache, with Docker", sub: "Recommended. A small container reads the access log and sends new lines. Download a kit, run one command.", log: true, kit: true, best: true },
  { id: "systemd", title: "The same, without Docker", sub: "A small program runs as a system service (systemd). Needs Python 3.9 or newer on the server.", log: true, kit: true },
  { id: "cloudflare", title: "Cloudflare", sub: "The Skald Worker sends a record of each request Cloudflare serves. Any plan, the free one included.", log: true },
  { id: "vercel", title: "Vercel or Netlify", sub: "The platform sends its request logs to Skald (a log drain).", log: true },
  { id: "script", title: "Only the script tag", sub: "In-page events (clicks, forms, scroll) from a one-line tag. No server log, so no AI crawlers or bots.", log: false },
];
export const methodOf = (id) => METHODS.find((x) => x.id === id) || null;

// A refusal the log endpoint noted (ingest_status.py REASONS) -> the likely cause and the fix.
export const REASON_FIX = {
  no_token: "The shipper sent no token. Run install.sh again and paste the sending token.",
  bad_token: "The token is wrong or was revoked. Make a new sending token, then run install.sh again and paste it (or put it in the platform's setting).",
  wrong_site: "The token was made for another site. Make a sending token for this site.",
  not_sending: "That token cannot send logs. Make a sending token (Sending logs) for this site.",
  not_verified: "Finish step 2 of the site's set-up (prove the domain is yours). Nothing is lost: the shipper keeps the lines.",
  removed: "The site was removed. Stop the shipper (sudo bash uninstall.sh).",
  not_here: "This Skald does not process the site. Check the site name in the send address.",
  rate_limited: "Nothing to do: the shipper waits and sends the lines a little later.",
  day_full: "Nothing to do: the lines are sent after midnight UTC. Ask for a bigger daily limit if this happens every day.",
  plan_limit: "Choose a bigger plan in Settings > Billing. Nothing is lost.",
  read_only: "Settle the bill in Settings > Billing. Nothing is lost.",
  disk: "Ask whoever runs Skald's server to free disk space. Nothing is lost.",
  bad_format: "Set the site's log format to Detect it (auto) in Settings > Add or remove sites.",
  bad_batch: "Update the shipper: download the kit again and run install.sh.",
  too_large: "Update the shipper: download the kit again and run install.sh.",
  no_accounts: "Ask whoever runs Skald's server: accounts must be on for log sending.",
  off: "Ask whoever runs Skald's server to switch the log endpoint on (ingest.enabled).",
  other: "Run check.sh from the kit and send us its last block.",
};

// The common problems: what you see, why, and what to do. Also in docs/help/troubleshooting-connections.md.
export const TROUBLE = [
  ["Refused: the token is wrong or was revoked (401)", "The token was mistyped, cut short, or revoked in Your tokens.", "Make a new sending token, run sudo bash install.sh again and paste it."],
  ["Refused: the token is not for this site (403)", "The token was made for another site.", "Make a sending token from this site's own page."],
  ["Nothing received: the shipper is not running", "The container or service stopped, or install.sh did not finish.", "Run sudo bash check.sh from the kit. It says what stopped. Then run sudo bash install.sh again."],
  ["Nothing received: a firewall", "The server may not open HTTPS connections out to Skald.", "Allow outbound HTTPS (port 443) to Skald's address. check.sh tests it: a 401 without a token means the path works."],
  ["Nothing received: the wrong log file", "The shipper reads a file the website does not write to.", "check.sh shows the file and the server blocks that write to it. Run install.sh again with the right path."],
  ["Nothing received: the log is not growing", "Nobody visited yet, or the site logs somewhere else.", "Open the site in a browser, then test again. If the file still does not grow, find its access_log line."],
  ["Visits from another host name", "www and another host share one log file.", "Give www its own access_log file (README.txt says how), then run install.sh again."],
  ["Refused: too many batches (429)", "The shipper sent many batches at once, usually right after it started.", "Nothing to do. The shipper slows down and sends the rest."],
  ["Refused: the site is not verified (403)", "The site waits for proof that the domain is yours.", "Finish step 2 of the site's set-up (Settings > Add or remove sites)."],
  ["Docker is missing", "The kit with Docker needs Docker on the web server.", "Install Docker, or choose The same, without Docker, and download that kit."],
  ["The site check could not reach the site", "The site is not live yet, turns automated visitors away, or its name points to a private address, which Skald never fetches.", "Choose the way by hand in step 3: nothing else depends on the check. Press Check again once the site is live."],
];

// An answer of the read-only API, in words.
export function apiWords(status) {
  if (status === 200) return "200: it works.";
  if (status === 401) return "401: the token is wrong, revoked, or not for this site. Make a new token for reading figures.";
  if (status === 403) return "403: refused. The token may not read this.";
  if (status === 404) return "404: the file is not there yet. The figures appear after the first daily run.";
  if (status === 429) return "429: too many requests. Wait a minute and test again.";
  if (!status) return "No answer: Skald's address could not be reached from this browser.";
  return `${status}: refused.`;
}

// An answer of the MCP server, in words.
export function mcpWords(status, error = "") {
  if (status === 401) return "401: the token is wrong, revoked, or has no MCP scope. Make a new token for the AI assistant.";
  if (status === 403) return /origin/i.test(error) ? "403: this browser's address is not allowed to call MCP. The token may still be fine: try it in your assistant." : "403: refused.";
  if (status === 404) return "404: MCP is not switched on here. Ask whoever runs your Skald server (mcp.enabled).";
  if (status === 405) return "405: the request was not a POST.";
  if (!status) return "No answer: Skald's address could not be reached from this browser.";
  return `${status}: ${error || "refused"}.`;
}
