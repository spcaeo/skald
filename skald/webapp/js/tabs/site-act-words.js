// A site's row menu on Settings > Add or remove sites (js/tabs/site-actions.js): which
// actions a role sees for a site, and every word of each dialog, as data. No DOM, so
// node runs it (tests/js/site-actions.mjs). The server's rules are the same
// (skald/site_lifecycle.py, site_actions_api.py): Pause and Resume for an owner
// or an admin; Remove, Restore, Clear data and Delete all data for an owner only; the
// install's main site can only be paused.

// The actions, in the menu's order. Pause comes first: it is the safe one.
export const ACTS = ["pause", "resume", "remove", "restore", "clear", "delete"];
// The address holds sact=<act>.<site> while a dialog is open (js/routekeys.js).
export const API = { pause: "sites/pause", resume: "sites/resume", remove: "sites/remove", restore: "sites/restore", clear: "sites/clear", delete: "sites/purge" };
export const DANGER = new Set(["remove", "clear", "delete"]);
export const TYPED = new Set(["remove", "clear", "delete"]);
export const TICKED = new Set(["clear", "delete"]);

/* The value in the address, and back: "pause.shop.example.com" -> ["pause", "shop.example.com"]. */
export const routeValue = (act, site) => `${act}.${site}`;
export function parseRoute(value) {
  const v = String(value || "");
  const i = v.indexOf(".");
  const act = i > 0 ? v.slice(0, i) : "";
  const site = i > 0 ? v.slice(i + 1) : "";
  return ACTS.includes(act) && /^[a-z0-9.-]+\.[a-z0-9-]+$/.test(site) ? { act, site } : null;
}

/* The actions this role may take on this site now, in the menu's order. */
export function menuFor(site, role) {
  const owner = role === "owner";
  if (!(owner || role === "admin") || !site) return [];
  const removed = site.status === "removed";
  const out = [];
  if (!removed) out.push(site.status === "paused" ? "resume" : "pause");
  if (owner && !site.main) {
    out.push(removed ? "restore" : "remove");
    out.push("clear", "delete");
  }
  return out;
}

const day = (stamp) => String(stamp || "").slice(0, 10);

/* Every word of a dialog: {title, lede, parts: [[heading, text]], button, done}. */
export function words(act, site) {
  const n = site.name;
  const config = site.source === "config";
  const W = {
    pause: {
      title: `Pause ${n}`,
      lede: "The safe choice: nothing is deleted, and you can resume at any time.",
      parts: [
        ["What happens", "Skald stops collecting and counting this site. Its log endpoint asks the shipper to wait, so the shipper keeps its lines. The daily and live runs skip the site."],
        ["What stays", `Everything: its history, settings, tokens, set-up and dashboard. The site shows "Paused since" the day you paused it.`],
        ["The days while paused", "They read Not recorded, never 0. When you resume, Skald says whether the log can still fill them: a shipper keeps its lines, a log drain (Vercel, Netlify) does not."],
        ["How to undo", "Resume, from this same menu."],
      ],
      button: "Pause the site",
      done: `${n} is paused. Nothing is collected until you resume it.`,
    },
    resume: {
      title: `Resume ${n}`,
      lede: site.paused_at ? `Paused since ${day(site.paused_at)}.` : "",
      parts: [
        ["What happens", "Skald starts collecting and counting this site again, from now."],
        ["The days while paused", "They read Not recorded, never 0. After you resume, Skald says whether the log can still fill them."],
        ["How to undo", "Pause again, from this same menu."],
      ],
      button: "Resume the site",
      done: `${n} is collecting again.`,
    },
    remove: {
      title: `Remove ${n}`,
      lede: "Only want a break? Pause keeps the site on the dashboard and is undone the same way.",
      parts: [
        ["What happens", `Skald stops processing ${n} and hides it from the dashboard and the site switcher. Its log endpoint refuses new lines.`],
        ["What stays", "All of its data: history, leads, settings and tokens. Nothing is deleted."],
        ["How to undo", "Restore it from Removed sites, on this page."],
      ],
      button: "Remove the site",
      done: `${n} is removed. Its data is kept; restore it from Removed sites.`,
    },
    restore: {
      title: `Restore ${n}`,
      lede: site.removed_at ? `Removed on ${day(site.removed_at)}.` : "",
      parts: [
        ["What happens", `Skald processes ${n} again and shows it on the dashboard. Its data was kept.`],
        ["The days it was removed", "They read Not recorded, never 0."],
        ["How to undo", "Remove it again, from this same menu."],
      ],
      button: "Restore the site",
      done: `${n} is back.`,
    },
    clear: {
      title: `Clear the data of ${n}`,
      lede: "Starts counting this site afresh. Want a break instead? Pause deletes nothing.",
      parts: [
        ["What is deleted", "Its collected data: every day of history, the raw log lines Skald holds for it, its leads, sales and conversions, its AI answer runs and today's live figures."],
        ["What stays", "The site, its settings, page groups, funnels, webhooks, tokens and set-up. Collecting goes on."],
        ["Before anything is deleted", "Skald writes one archive of all of it into the install's backups folder, kept 30 days, and shows you its path."],
        ["Afterwards", "The days before today read Not recorded, never 0, and are not counted again, even if the web server's own log still holds them."],
        ["How to undo", "There is no undo button. For 30 days the archive holds a copy; an install admin can copy data back from it by hand."],
      ],
      tick: `I understand that the history, logs and leads of ${n} are deleted.`,
      button: "Clear the data",
      done: `The data of ${n} is cleared. The archive is at:`,
    },
    delete: {
      title: `Delete all data of ${n}`,
      lede: "This cannot be undone here. Want a break instead? Pause deletes nothing.",
      parts: [
        ["What is deleted", "Everything Skald keeps for this site: its day history, the raw log lines Skald holds, its leads, sales and conversions, AI answers, its settings, its tokens (they stop working at once), its dashboard folder, its logo and its set-up links."],
        ["What happens to the site", config
          ? "It is defined in the server's config file, so its entry stays there: the site becomes Removed, with no data. Restore collects it again from that day."
          : "It is gone from this organisation. Its name can be added again after 30 days."],
        ["Before anything is deleted", "Skald writes one archive of all of it into the install's backups folder, kept 30 days, and shows you its path."],
        ["How to undo", "There is no undo button. For 30 days the archive holds a copy; an install admin can copy data back from it by hand."],
      ],
      tick: `I understand that everything above is deleted and the tokens of ${n} stop working.`,
      button: "Delete all data",
      done: `All data of ${n} is deleted. The archive is at:`,
    },
  };
  return W[act];
}

/* The menu's label for each action. */
export const LABEL = { pause: "Pause", resume: "Resume", remove: "Remove", restore: "Restore", clear: "Clear data", delete: "Delete all data" };

/* The State column: "Paused since 2026-10-20" and the like. */
export function stateWords(site, waiting = false) {
  if (site.status === "removed") return `Removed${site.removed_at ? ` on ${day(site.removed_at)}` : ""}`;
  if (site.status === "paused") return `Paused since ${day(site.paused_at)}`;
  return waiting ? "waiting for verification" : "active";
}

export const MAIN_NOTE = "This is the install's main site: it can be paused here; removing it or deleting its data is done on the server.";
