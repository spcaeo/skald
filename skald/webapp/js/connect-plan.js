// Connect the dots (2.43): what each page needs, what is connected, what Skald already found
// on the site, and the one way it recommends. No DOM and no other module here, so node runs
// it (tests/js/connect.mjs). The card that draws it is js/ui/connect.js; Settings › This site ›
// Leads & tools (js/tabs/set-leads.js) draws its groups, rows and Next step from it.
//
//   GROUPS                 Leads & tools' groups, in order: id, title, its one-line why, the
//                          page that shows its data and the words of the link to it
//   NEEDS                  a page's missing source: its card's title and one line, the group
//                          in Leads & tools, and the dialog Connect opens
//   STATES / stateWords    connected, waiting, failing, off: the pill's kind and words
//   rowsOf({...})          every row of Leads & tools, from GET integrations, your tools,
//                          the set-up lines and the page's own files
//   fits(row, found)       does a row that is not connected fit this site (Stripe only where
//                          Stripe was found...)? Those that do not fold under "More"
//   recommend(need, found) the way Skald recommends for this site: {words, act}
//   nextStep(rows, found)  the single most useful thing to connect, or null
//   factsOf(found)         what the site check saw, as short chips
//   partly(need, rows)     a page that is partly fed: what arrives and what is still missing
//   groupOf(cause)         the group an alert needs (sale: payments...), or ""
//
// `found` is GET integrations' found (integrations_api.found_of: the site check's server,
// platform, framework, the tools named on the home page and its forms), or null. An act is
// the address patch that opens the existing dialog: setup=lead&way=<tool>, setup=search,
// setup=script, setup=tool-<id>, setup=finish-tools, rjc=connect, tool=webhooks.

export const GROUPS = [
  { id: "leads", title: "Leads from your forms", why: "Each form sent on your site, with the visit and the source that brought it.", page: "sales/leads", see: "See leads" },
  { id: "bookings", title: "Bookings", why: "Calls booked through Calendly or Cal.com, step by step.", page: "sales/bookings", see: "See bookings" },
  { id: "payments", title: "Payments", why: "Each sale's value, so Revenue shows which sources made money.", page: "sales/revenue", see: "See revenue" },
  { id: "search", title: "Search", why: "The searches that bring people here. Only Google and Bing see them.", page: "traffic/search", see: "See searches" },
  { id: "tools", title: "Your own tools", why: "Google Analytics and your other tools' own figures, beside Skald's, never added to them.", page: "overview/summary", see: "See on Overview" },
  { id: "journeys", title: "Recorded journeys", why: "The sessions your site sends after people agree to analytics.", page: "traffic/visitors", see: "See journeys" },
  { id: "out", title: "Send each lead out", why: "Each new lead posted to your CRM, Zapier or Slack as it comes.", page: "", see: "" },
];
export const GROUP_IDS = GROUPS.map((g) => g.id);
export const groupById = (id) => GROUPS.find((g) => g.id === id) || null;

// The incoming hooks (integrations_api.TOOLS) and the group each feeds.
export const HOOK_GROUP = { lead: "leads", json: "leads", typeform: "leads", hubspot: "leads", calendly: "bookings", calcom: "bookings", stripe: "payments" };
// What each hook brings, when it is not connected (its row's one line).
const HOOK_WHY = {
  lead: "Your site's own form or backend tells Skald about each lead",
  json: "A no-code tool sends each lead",
  typeform: "Each form response, counted as a contact form",
  hubspot: "New contacts, booked meetings and won deals",
  calendly: "Bookings, cancellations and no-shows",
  calcom: "Bookings, cancellations and moved bookings",
  stripe: "Each paid Checkout, with its value",
};

// Where its leads come from, in a sentence ("Leads arrive from your server").
const HOOK_FROM = { lead: "your server", json: "Zapier, Make or n8n", typeform: "Typeform", hubspot: "HubSpot", calendly: "Calendly", calcom: "Cal.com", stripe: "Stripe" };

export const STATES = { connected: ["good", "Connected"], waiting: ["warn", "Waiting"], failing: ["bad", "Failing"], off: ["off", "Not connected"] };
export const stateWords = (st) => STATES[st] || STATES.off;
const ON = new Set(["connected", "waiting", "failing"]);
export const isOn = (row) => ON.has(row?.state);

// A page's missing source. act: the dialog Connect opens when nothing better is known.
export const NEEDS = {
  leads: { group: "leads", title: "No lead source connected yet", line: "Leads need a source: your forms, your booking tool or your site's server telling Skald about each one.", act: { setup: "lead" } },
  bookings: { group: "bookings", title: "No booking tool connected yet", line: "Calendar bookings need Calendly or Cal.com to tell Skald about each booking.", act: { setup: "lead", way: "calendly" } },
  payments: { group: "payments", title: "No payment source connected yet", line: "Revenue needs each sale's value: from Stripe, or sent with each lead.", act: { setup: "lead", way: "stripe" } },
  search: { group: "search", title: "Search Console is not connected yet", line: "Search needs Google Search Console: only Google sees what people searched for.", act: { setup: "search" } },
  tools: { group: "tools", title: "No tool of yours connected yet", line: "Google Analytics and your other tools can show their own figures here, never mixed into Skald's.", act: { setup: "finish-tools" } },
  journeys: { group: "journeys", title: "Recorded journeys are not connected yet", line: "Your site can send the sessions people agreed to, labelled as its own, never added to the log's figures.", act: { rjc: "connect" } },
  // AI answers stay off without keys (the owner's rule): their state only, never a push to connect.
  ai: { group: "", title: "AI answers are off", line: "They ask AI assistants your questions with a provider key of your own, which costs per question. Nothing is asked, and nothing costs, until a key and a profile exist.", act: null },
  script: { group: "leads", title: "The script tag is not on your pages yet", line: "Clicks, form steps and goals need the script tag on your pages. Visits and pages need nothing: they come from the log.", act: { setup: "script" } },
};

/* An incoming hook's state (integrations_api tools, roads.hook_states). */
export function hookState(t) {
  if (!t) return "off";
  if (t.problem || ["missing", "exposed"].includes(t.state) || (t.attention && t.state === "received")) return "failing";
  if (t.state === "received") return "connected";
  if (t.state === "never" || t.state === "ready") return "waiting";
  return "off";
}
/* One of your own tools (GET integrations/yourtools, or integrations' yourtools states). */
export function yourState(t) {
  const st = t?.state;
  if (!st || st === "off") return "off";
  if (st === "answering") return "connected";
  if (st === "waiting" || st === "no_key") return "waiting";
  return "failing";                             // failing, stopped, withheld
}
/* A doctor's line (integrations status) by its id, or by its part's name. */
export const lineOf = (status, id, part = "") => (status || []).find((x) => x.id === id || (part && x.part === part)) || null;
/* The script tag and recorded journeys, from their doctor's line. */
export function lineState(d) {
  if (!d || d.state === "OFF") return d && /waits|waiting|first/i.test(String(d.says || "")) ? "waiting" : "off";
  if (d.state === "OK") return "connected";
  return "failing";
}
const lastOf = (says) => /the last event came (.+)$/.exec(String(says || ""))?.[1] || "";

/* Every row of Leads & tools: {id, group, name, state, line, last, open, act}.
   open: the address patch of its details (a connected row); act: the dialog that connects it.
   integ: GET integrations; yours: GET integrations/yourtools; searchOn: Search Console connected
   (the set-up line or the page's search.json); searchSays: its one line. */
export function rowsOf({ integ = null, yours = null, searchOn = false, searchSays = "" } = {}) {
  const out = [];
  const status = integ?.status || [];
  for (const t of integ?.tools || []) {
    const st = hookState(t);
    out.push({ id: t.tool, group: HOOK_GROUP[t.tool] || "leads", name: t.name || t.tool, from: HOOK_FROM[t.tool] || t.name, state: st, last: st === "connected" ? t.last_at || "" : "",
      line: st === "off" ? HOOK_WHY[t.tool] || "" : st === "connected" ? "" : t.words || "",
      open: { tool: t.tool }, act: { setup: "lead", way: t.tool } });
  }
  const script = lineOf(status, "script", "Script tag");
  const sst = lineState(script);
  out.push({ id: "script", group: "leads", name: "Script tag on your pages", from: "the script tag", state: sst, last: lastOf(script?.says),
    line: sst === "off" ? "Counts form sends, clicks and bookings with no other code" : sst === "failing" ? String(script?.says || "") : "",
    open: { tab: "settings/site/data", sub: "script" }, act: { setup: "script" } });
  const list = (yours && yours.ok !== false && yours.tools) || null;
  const ys = list || (integ?.yourtools || []).map((t) => ({ id: t.tool, name: t.name, state: t.state, words: t.words }));
  for (const t of ys) {
    const st = yourState(t);
    out.push({ id: `your-${t.id}`, group: "tools", name: t.name, state: st, last: st === "off" ? "" : t.ago || "",
      line: st === "off" ? "Its own figures, beside Skald's" : st === "connected" ? t.counted_from || "" : t.words || "",
      open: { tool: `your-${t.id}` }, act: { setup: `tool-${t.id}` } });
  }
  out.push({ id: "search", group: "search", name: "Search Console & Bing", state: searchOn ? "connected" : "off", last: "",
    line: searchOn ? searchSays : "The searches that bring people here", open: { tool: "search" }, act: { setup: "search" } });
  const rec = lineOf(status, "journeys");
  const rst = lineState(rec);
  out.push({ id: "journeys", group: "journeys", name: "Recorded journeys", state: rec && rec.state === "OFF" ? "waiting" : rst, last: lastOf(rec?.says),
    line: !rec ? "Your site sends the sessions people agreed to" : rec.state === "OFF" ? "Connected. Waiting for the first session" : rec.state === "OK" ? "" : "Your site stopped sending its sessions",
    open: { rjc: "connect" }, act: { rjc: "connect" } });
  const hooks = integ?.webhooks || [];
  out.push({ id: "webhooks", group: "out", name: "Send each lead out", state: hooks.length ? "connected" : "off", last: "",
    line: hooks.length ? hooks.map((w) => String(w.url || "").replace(/^https?:\/\//, "").split("/")[0]).join(", ") : "To a CRM, Zapier or Slack",
    open: { tool: "webhooks" }, act: { tool: "webhooks" } });
  return out;
}

const tagsOf = (found) => (found && found.tags) || {};
const has = (found, k) => (tagsOf(found)[k] || []).length > 0;

/* Does a row that is not connected fit this site? Without a site check: the lead hook, the
   script tag, Search Console and Send each lead out. */
export function fits(row, found) {
  if (isOn(row)) return true;
  const builder = !!found?.hosted_builder;
  switch (row.id) {
    case "lead": return !builder;
    case "json": return builder;
    case "script": case "search": case "webhooks": return true;
    case "hubspot": return has(found, "hubspot");
    case "calendly": return has(found, "calendly");
    case "calcom": return has(found, "calcom");
    case "stripe": return has(found, "stripe");
    case "journeys": return found?.framework === "nextjs";
    case "your-ga4": return has(found, "ga4");
    case "your-calendly": return has(found, "calendly");
    case "your-vercel": return found?.platform === "vercel";
    default: return false;
  }
}

const label = (found) => {
  const fw = found?.framework && found.framework !== "plain" ? found.framework_label : "";
  const on = found?.platform && found.platform !== "cloudflare" ? found.platform_label : "";
  return fw && on ? `${fw} on ${on}` : fw || (on ? `on ${on}` : "");
};

/* The way Skald recommends for this site: {words, act}. */
export function recommend(need, found = null) {
  const tags = tagsOf(found);
  const fw = found?.framework || "";
  const site = label(found);
  const is = site ? `Your site is ${site}` : "";
  if (need === "leads") {
    if (found?.hosted_builder) return { words: `Your site is on ${found.platform_label}: send each form through Zapier or Make to Skald's lead hook. No code.`, act: { setup: "lead", way: "json" } };
    if (tags.hubspot?.length) return { words: "HubSpot is on your site: connect HubSpot and each new contact arrives as a lead.", act: { setup: "lead", way: "hubspot" } };
    if (fw === "wordpress") return { words: "Your site is WordPress: upload Skald's plugin and your forms (Contact Form 7, WPForms, Gravity Forms and others) send each lead. No code.", act: { setup: "lead", way: "wordpress" } };
    if (fw === "nextjs") return { words: `${is}: send leads from your form's server action with the signed lead hook.`, act: { setup: "lead", way: "lead" } };
    if (site) return { words: `${is}: send each lead from your server with the signed lead hook. One file for PHP, Node or Python.`, act: { setup: "lead", way: "lead" } };
    return { words: "Send each lead from your site's server with the signed lead hook: one file for PHP, Node or Python, or a plugin for WordPress.", act: { setup: "lead", way: "lead" } };
  }
  if (need === "bookings") {
    if (tags.calendly?.length) return { words: `Calendly is on your home page (${tags.calendly[0]}): connect Calendly and each booking shows here, step by step.`, act: { setup: "lead", way: "calendly" } };
    if (tags.calcom?.length) return { words: `Cal.com is on your home page (${tags.calcom[0]}): connect Cal.com and each booking shows here, step by step.`, act: { setup: "lead", way: "calcom" } };
    return { words: "Connect Calendly or Cal.com, whichever takes your bookings: each booking then shows here, step by step.", act: { setup: "lead", way: "calendly" } };
  }
  if (need === "payments") {
    if (tags.stripe?.length) return { words: "Stripe is on your site: connect Stripe and each paid Checkout shows here with its value.", act: { setup: "lead", way: "stripe" } };
    return { words: "Send value and currency with each sale through the lead hook, or connect Stripe if it takes your payments.", act: { setup: "lead", way: "lead" } };
  }
  if (need === "search") return { words: "Connect Google Search Console: Skald keeps a copy of Google's own figures here, never mixed with its own.", act: { setup: "search" } };
  if (need === "tools") {
    if (tags.ga4?.length) return { words: `Your site has the Google Analytics tag (${tags.ga4[0]}): connect Google Analytics to see its own figures beside Skald's.`, act: { setup: "tool-ga4" } };
    if (found?.platform === "vercel") return { words: "Your site is on Vercel: connect Vercel Web Analytics to see its own figures beside Skald's.", act: { setup: "tool-vercel" } };
    return { words: "Connect Google Analytics or another of your tools: their own figures show beside Skald's, never added.", act: { setup: "finish-tools" } };
  }
  if (need === "journeys") {
    if (fw === "nextjs") return { words: `${is}: add Skald's relay route, and your consent banner sends each session people agree to.`, act: { rjc: "connect" } };
    return { words: "Your site sends each session people agree to through a small signed relay on your server.", act: { rjc: "connect" } };
  }
  if (need === "script") {
    if (fw === "nextjs") return { words: `${is}: add the script tag to your root layout. One line, no other code.`, act: { setup: "script" } };
    if (fw === "wordpress") return { words: "Your site is WordPress: add the script tag to your theme's header, or with a header plugin.", act: { setup: "script" } };
    if (found?.hosted_builder) return { words: `Your site is on ${found.platform_label}: paste the script tag in its custom code (head) setting.`, act: { setup: "script" } };
    return { words: "Add one line, the script tag, to your pages. It counts clicks, form steps and goals with no other code.", act: { setup: "script" } };
  }
  return { words: "", act: NEEDS[need]?.act || { tab: "settings/site/leads" } };
}

/* The other ways for a need, under "Other ways": [[words, act]], the recommended one left out. */
export function otherWays(need, found = null) {
  const main = JSON.stringify(recommend(need, found).act);
  const ways = {
    leads: [["Your site's own form or backend", { setup: "lead", way: "lead" }], ["WordPress forms (a plugin, no code)", { setup: "lead", way: "wordpress" }],
      ["Zapier, Make or n8n", { setup: "lead", way: "json" }], ["Typeform", { setup: "lead", way: "typeform" }], ["HubSpot", { setup: "lead", way: "hubspot" }],
      ["The script tag (form sends, no code)", { setup: "script" }]],
    bookings: [["Calendly", { setup: "lead", way: "calendly" }], ["Cal.com", { setup: "lead", way: "calcom" }], ["HubSpot meetings", { setup: "lead", way: "hubspot" }]],
    payments: [["Stripe", { setup: "lead", way: "stripe" }], ["Value with each lead (the lead hook)", { setup: "lead", way: "lead" }], ["Zapier, Make or n8n", { setup: "lead", way: "json" }]],
    search: [["Search Console & Bing, in Leads & tools", { tool: "search" }]],
    tools: [["Google Analytics", { setup: "tool-ga4" }], ["Calendly", { setup: "tool-calendly" }], ["Vercel Web Analytics", { setup: "tool-vercel" }], ["Resend", { setup: "tool-resend" }]],
    journeys: [],
    script: [["Settings › Data › Script tag", { tab: "settings/site/data", sub: "script" }]],
  }[need] || [];
  return ways.filter(([, act]) => JSON.stringify(act) !== main);
}

/* What the site check saw, as chips: {label, value} (value: what a copy icon copies). */
export function factsOf(found) {
  if (!found) return [];
  const out = [];
  if (found.framework && found.framework !== "plain") out.push({ label: found.framework_label || found.framework });
  else if (found.framework === "plain") out.push({ label: "Plain HTML" });
  if (found.platform) out.push({ label: found.platform_label || found.platform });
  else if (found.server && found.server !== "unknown") out.push({ label: found.server_label || found.server });
  if (Number.isInteger(found.forms)) out.push({ label: found.forms ? `${found.forms} form${found.forms === 1 ? "" : "s"} on the home page` : "No form on the home page" });
  const tags = tagsOf(found);
  for (const v of tags.ga4 || []) out.push({ label: "Google Analytics", value: v });
  for (const v of tags.calendly || []) out.push({ label: "Calendly", value: v });
  for (const v of tags.calcom || []) out.push({ label: "Cal.com", value: v });
  if ((tags.stripe || []).length) out.push({ label: "Stripe" });
  if ((tags.hubspot || []).length) out.push({ label: "HubSpot" });
  return out;
}

// Recorded journeys are never the next step: they change the site's code and need its consent banner.
const NEXT_ORDER = ["leads", "bookings", "payments", "search", "tools", "script"];
const anyOn = (rows, group) => rows.some((r) => r.group === group && isOn(r));
/* The single most useful thing to connect for this site: {need, words, act, button, row?}, or null. */
export function nextStep(rows, found = null) {
  const broken = rows.find((r) => r.state === "failing");
  if (broken) return { need: broken.group, row: broken, words: `${broken.name} is not working${broken.line ? `: ${broken.line}` : ""}. Fix it so its data arrives again.`, act: broken.open, button: "Fix it" };
  const tags = tagsOf(found);
  const want = {
    leads: !anyOn(rows, "leads"),
    bookings: !anyOn(rows, "bookings") && (has(found, "calendly") || has(found, "calcom")),
    payments: !anyOn(rows, "payments") && has(found, "stripe"),
    search: !anyOn(rows, "search"),
    tools: !anyOn(rows, "tools") && (tags.ga4 || []).length > 0,
    script: !rows.some((r) => r.id === "script" && isOn(r)),
  };
  const need = NEXT_ORDER.find((k) => want[k]);
  if (!need) return null;
  const rec = recommend(need, found);
  return { need, words: rec.words, act: rec.act, button: "Connect" };
}

/* A page fed by some of its sources: what arrives, and what is still missing. need: the page's
   own need; also: the groups whose absence is worth saying on it. "" when nothing to say. */
// The page each partly line is for: the groups that feed it, the groups worth naming when they
// are missing (only those that fit the site), and its noun.
export const PARTLY = {
  leads: { feeds: ["leads", "bookings", "payments"], also: ["leads", "bookings"], words: "Leads" },
  bookings: { feeds: ["bookings"], also: ["bookings"], words: "Bookings" },
  payments: { feeds: ["payments"], also: ["payments"], words: "Payments" },
};
const NOUN = { leads: "your forms", bookings: "bookings", payments: "payments", search: "search", tools: "your own tools", journeys: "recorded journeys" };
const andList = (xs) => (xs.length > 2 ? `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}` : xs.join(" and "));
export function partly(page, rows, found = null) {
  const p = PARTLY[page];
  if (!p) return "";
  const on = rows.filter((r) => p.feeds.includes(r.group) && r.state === "connected");
  if (!on.length) return "";
  // A group is missing when nothing in it is on and one of its rows fits this site.
  const missing = p.also.filter((g) => !anyOn(rows, g) && rows.some((r) => r.group === g && fits(r, found)));
  if (!missing.length) return "";
  const gone = missing.map((g) => NOUN[g]);
  return `${p.words} arrive from ${andList([...new Set(on.map((r) => r.from || r.name))])}; ${andList(gone)} ${gone.length === 1 && gone[0] === "search" ? "is" : "are"} not connected.`;
}

// The alerts that need a source, by their cause (alerts.py), and the group that feeds them.
const CAUSE_GROUP = { sale: "payments", sale_refunded: "payments", leads_drop: "leads", bookings_drop: "bookings", tool_stopped: "tools", ga4_log_gap: "tools" };
export const groupOf = (cause) => CAUSE_GROUP[cause] || "";
/* Is a group fed by anything? From the rows (an admin), or from the page's own files (anyone):
   the tools that reported to conversions.json, search.json's engines, your tools' figures. */
export function fedFromData(group, m) {
  const conv = m?.x?.conversions;
  const tools = new Set();
  for (const d of conv?.days || []) for (const per of Object.values(d.by?.tool || {})) for (const [t, v] of Object.entries(per || {})) if (v) tools.add(t);
  for (const r of conv?.today?.rows || []) if (r.tool) tools.add(r.tool);
  // Leads: any tool, or the lead database; no conversions file at all is not known.
  if (group === "leads") return tools.size > 0 || !!(m?.x?.leads && m.x.leads.available !== false) ? true : conv ? false : null;
  if (group === "bookings") return tools.has("calendly") || tools.has("calcom");
  if (group === "payments") return tools.has("stripe") || (conv?.days || []).some((d) => d.revenue && Object.keys(d.revenue).length);
  if (group === "search") return !!(m?.x?.search?.engines?.google?.connected || m?.x?.search?.engines?.bing?.connected);
  return null;                                   // not known from the files
}
