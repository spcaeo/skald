// How a stored label is shown. History keeps the names it was written with
// ("Direct or unknown", "Unknown"): the store, the journeys, the conversions and
// the audit compare them, so they never change. A person reads the words below.
// The same table is in skald/labels.py, for mails, CSV files and MCP answers.
//
//   shown("Direct or unknown") -> "Direct"     stored("Direct") -> "Direct or unknown"
//
// ui.js h() passes every text it draws through shown(), so a label drawn
// anywhere is said this way; table.js and report.js do the same for exports.
// Filters, drills and links keep the stored value.

export const SHOWN = {
  "Direct or unknown": "Direct",
  "direct or unknown": "direct",
  Unknown: "Not recorded",
  unknown: "not recorded",
  "(unknown)": "(not recorded)",
};
const STORED = Object.fromEntries(Object.entries(SHOWN).map(([k, v]) => [v, k]));

export const shown = (v) => (typeof v === "string" && Object.hasOwn(SHOWN, v) ? SHOWN[v] : v);
// A sentence that names a source inside it ("from Direct or unknown: 3 pages") says it the same way.
export const shownText = (s) => (Object.hasOwn(SHOWN, s) ? SHOWN[s] : s.includes("irect or unknown") ? s.replace(/\b([Dd])irect or unknown\b/g, "$1irect") : s);
// Back from the words to the stored name, for a value typed or picked by its words.
export const stored = (v) => (typeof v === "string" && Object.hasOwn(STORED, v) ? STORED[v] : v);

// An AI assistant by the name a person knows it by ("ChatGPT", not chatgpt.com). The
// same table is visits.ASSISTANTS in Python. Bot names (ChatGPT-User, GPTBot) stay:
// they name one fetcher or crawler, not the assistant.
export const ASSISTANTS = {
  "chatgpt.com": "ChatGPT", "perplexity.ai": "Perplexity", "claude.ai": "Claude",
  "gemini.google.com": "Gemini", "copilot.microsoft.com": "Copilot",
  "you.com": "You.com", "phind.com": "Phind", "poe.com": "Poe", "mistral.ai": "Mistral",
  "meta.ai": "Meta AI", "deepseek.com": "DeepSeek", "grok.com": "Grok",
};
export const assistantName = (v) => (typeof v === "string" && Object.hasOwn(ASSISTANTS, v) ? ASSISTANTS[v] : shown(v));

// The user fetchers (ChatGPT-User, Google-NotebookLM, Amzn-User...): a bot name, lower case, to
// the assistant it fetches for. The same table is classify.AI_FETCHER_OWNERS in Python, which
// files a fetch under its assistant; tests/test_fetcher_names.py holds the two to each other.
export const FETCHERS = {
  "chatgpt-user": "chatgpt.com", "claude-user": "claude.ai",
  "perplexity-user": "perplexity.ai", "gemini-user": "gemini.google.com",
  "bingpreview": "copilot.microsoft.com", "mistralai-user": "mistral.ai",
  "meta-externalfetcher": "meta.ai",
  "claude-web": "claude.ai", "google-agent": "gemini.google.com",
  "googleagent-mariner": "gemini.google.com",
  "google-gemininotebook": "gemini.google.com",
  "google-notebooklm": "gemini.google.com", "amzn-user": "alexa.amazon.com",
};
// The assistant a user fetcher reads for, by the name a person knows it by, or null for any
// other bot: "ChatGPT-User" -> "ChatGPT", "Google-NotebookLM" -> "Gemini".
export const fetcherOf = (v) => {
  const low = typeof v === "string" ? v.toLowerCase() : "";
  return Object.hasOwn(FETCHERS, low) ? assistantName(FETCHERS[low]) : null;
};

// An object's keys (and its nested objects' keys) as shown: for JSON a person reads.
export function shownKeys(o) {
  if (Array.isArray(o)) return o.map(shownKeys);
  if (!o || typeof o !== "object") return shown(o);
  return Object.fromEntries(Object.entries(o).map(([k, v]) => [shown(k), shownKeys(v)]));
}
