// Settings › Organisation › Organisations: the words and the pure parts (no page, no fetch),
// shared by the page (orgs.js), its drawer (org-drawer.js, org-members.js) and the tests
// (tests/js/orgs.mjs). The helper behind it: skald/orgs_api.py.
//
//   address    #settings/org/orgs?org=<id>&otab=<tab>   one organisation's drawer and its tab
//              #settings/org/orgs?org=new                New organisation
//              orgs_q, orgs_sort                         the page's search and order
//   ids only   an organisation's id, never its name; a member by id, never an email

export const ROUTE = "settings/org/orgs";

// The privacy class (keep_everything.py, the organisation rule): set by an install admin.
export const CLASS = {
  internal: { word: "Internal", kind: "info", line: "Keep everything: when the install keeps everything, nothing on these sites is deleted by itself." },
  client: { word: "Client", kind: "warn", line: "Own retention: these sites follow their own Privacy settings, even when the install keeps everything." },
};
export const classOf = (c) => CLASS[c] || CLASS.internal;

export const STATE = {
  active: { word: "Active", kind: "good" },
  archived: { word: "Archived", kind: "off" },
};
export const stateOf = (s) => STATE[s] || STATE.active;

export const ROLE_WORD = { owner: "Owner", admin: "Admin", viewer: "Viewer" };

// The drawer's tabs, in order: [key, name, who sees it ("all" or a `may` key)].
export const OTABS = [
  ["overview", "Overview", "all"],
  ["sites", "Sites", "all"],
  ["members", "Members", "all"],
  ["invites", "Pending invites", "members"],
  ["settings", "Settings", "all"],
  ["keys", "Keys", "keys"],
  ["audit", "Audit", "audit"],
];
/* The tabs this reader may open, from the answer's `may`. */
export const tabsFor = (may = {}) => OTABS.filter(([, , who]) => who === "all" || may[who]);
/* The tab to draw: the one asked when this reader may open it, else Overview. */
export function tabOf(asked, may = {}) {
  const keys = tabsFor(may).map(([k]) => k);
  return keys.includes(asked) ? asked : "overview";
}

/* org=<value>: "new", or an organisation's id (a whole number). Anything else: null. */
export function parseKey(v) {
  const s = String(v ?? "").trim();
  if (s === "new") return "new";
  return /^[1-9][0-9]{0,9}$/.test(s) ? Number(s) : null;
}

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
export const sitesWord = (n) => plural(n, "site");
export const membersWord = (n) => plural(n, "member");

/* A card's plan: its plan's name, or "Internal" (no plan: the install's own). */
/* The organisation's plan, only where the install sells plans (`hosted`: /me's saas): its
   name, or "none" when it has none. Elsewhere there is no plan: null, and nothing is shown,
   so "Internal" or "Client" is said once, by the privacy class's pill. */
export const planWord = (card, hosted = false) => (!hosted ? null
  : card.plan ? String(card.plan).replace(/^./, (c) => c.toUpperCase()) : "none");

/* The card's one line under its name: "3 sites · 5 members", and "· Plan: Pro" when hosted. */
export function cardLine(card, hosted = false) {
  const n = (card.sites || []).length;
  const plan = planWord(card, hosted);
  return [sitesWord(n), card.members == null ? null : membersWord(card.members), plan ? `Plan: ${plan}` : null].filter(Boolean).join(" · ");
}

/* Which sites a card names, for the card: the first three, then "and N more". */
export function siteNames(sites = [], shown = 3) {
  if (!sites.length) return "No sites yet";
  const head = sites.slice(0, shown).join(", ");
  return sites.length > shown ? `${head} and ${sites.length - shown} more` : head;
}

export const SORTS = [
  ["name:asc", "Name, A to Z"],
  ["sites:desc", "Most sites first"],
  ["members:desc", "Most members first"],
  ["created:desc", "Newest first"],
  ["created:asc", "Oldest first"],
];
const SORT_KEYS = new Set(SORTS.map(([k]) => k));
export const sortOf = (v) => (SORT_KEYS.has(v) ? v : "name:asc");

/* The cards the search and the order leave, archived ones last. q matches the name, the
   short name and the sites. */
export function filterSort(cards, q = "", sort = "name:asc") {
  const want = String(q || "").trim().toLowerCase();
  const hit = (c) => !want || [c.name, c.slug, ...(c.sites || [])].some((x) => String(x || "").toLowerCase().includes(want));
  const [col, dir] = sortOf(sort).split(":");
  const val = (c) => (col === "sites" ? (c.sites || []).length : col === "members" ? c.members ?? -1
    : col === "created" ? String(c.created_at || "") : String(c.name || "").toLowerCase());
  const sign = dir === "desc" ? -1 : 1;
  return cards.filter(hit).sort((a, b) => {
    const arch = (a.state === "archived") - (b.state === "archived");
    if (arch) return arch;
    const x = val(a), y = val(b);
    return (x < y ? -1 : x > y ? 1 : 0) * sign || String(a.name).localeCompare(String(b.name));
  });
}

/* A member's sites, in words: every site, or the ones they see. */
export function accessWords(sites, role) {
  if (role === "owner" || sites == null) return "Every site";
  if (!sites.length) return "No site (theirs moved away)";
  return sites.join(", ");
}

/* The overview's figure: a number, or "Not recorded" (never 0 for a figure not kept). */
export function figure(v) {
  return v == null ? "Not recorded" : Number(v).toLocaleString("en-US");
}

// The confirm words of Archive and Restore (the owner's rule: pause, never delete).
export const ARCHIVE = {
  title: "Archive this organisation?",
  what: "Its sites stop collecting: each one is paused. Its members, settings, keys and every figure stay as they are. Nothing is deleted.",
  undo: "Restore it any time: the sites it paused collect again from the next run. Days while archived are Not recorded, never 0.",
  button: "Archive",
};
export const RESTORE = {
  title: "Restore this organisation?",
  what: "The sites archiving paused collect again from the next run. A site someone paused by hand stays paused.",
  button: "Restore",
};
