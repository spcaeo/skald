// What is open over a tab lives in the address too (2.21): the visitor drawer, a
// lead, a request's detail, a Set up dialog and its step, the app's dialogs. The
// keys and what each means: js/routekeys.js (kind "overlay").
//
//   opening    the drawer is drawn at once, then its key is written: one new history
//              entry, so Back closes it before it leaves the page
//   a step     replaces the entry (Back does not walk the steps)
//   closing    removes the key: Back over the entry the opening made, else a replace
//   a link     main.js draws the tab, then sync() opens what the address names; a key
//              that names something this reader may not see, or that is no longer
//              kept, opens the page with one plain line instead (missing())
//
// A drawer joins in with openDrawer({ route: { key, value } }) (drawer.js): it calls
// opened() when drawn and closed() when the reader closes it. sync() closes what
// the address no longer names (Back) and opens what it names (a link, a reload, a
// redraw that closed the page's drawers). Restoring each kind is below (RESTORE);
// each module opens its own drawer, so the same code runs for a click and a link.

import * as S from "./state.js";
import { h } from "./ui.js";
import { OPENERS, INSIDE, hasToken, TOKEN } from "./routekeys.js";
import { valueOf } from "./routemask.js";

const open = new Map();        // family -> {value, close(), isOpen()}
const pending = new Set();     // "family=value" being restored (answers on the way)
const STEPPED = new Set(["setup", "conn"]);
// The keys inside a stepped dialog (its step, the share form, the kit's token choice) leave with it.
const INSIDE_OFF = Object.fromEntries(INSIDE.map((k) => [k, ""]));
const extra = {};              // restorers main.js adds (the report builder needs its loader)

/* A drawer opened for a key: tracked, and its key written (a new entry, or a replace
   when the same kind was already open). handle: {close(), isOpen()}. */
export function opened(family, value, handle, { step = null } = {}) {
  value = String(value);
  open.set(family, { value, ...handle });
  const s = S.read();
  const patch = {};
  if (s[family] !== value) patch[family] = value;
  if (step != null && STEPPED.has(family) && s.step !== String(step)) patch.step = String(step);
  if (!Object.keys(patch).length) return;
  const had = !!s[family];
  S.set(patch, had ? { replace: true } : { mark: { ov: family } });
}

/* The reader closed it: forget it and take its key away. */
export function closed(family, value) {
  const cur = open.get(family);
  if (!cur || cur.value !== String(value)) return;
  open.delete(family);
  const s = S.read();
  if (s[family] !== String(value)) return;
  // The key leaves the address at once (so a move the drawer makes next does not carry it),
  // then, once this click is done, Back over the entry the opening made. A link in the
  // drawer that moved the page on (help, another tab) keeps its move.
  const pushed = history.state?.ov === family;
  S.set({ [family]: "", ...(STEPPED.has(family) ? INSIDE_OFF : {}) }, { replace: true });
  if (pushed) {
    const here = location.hash;
    setTimeout(() => { if (location.hash === here && history.state?.ov === family) history.back(); }, 0);
  }
}

/* A step of the dialog open, or a part inside it (share), in place: no new entry. */
export function stepped(family, value, patch) {
  const s = S.read();
  if (s[family] !== String(value)) return;
  const next = Object.fromEntries(Object.entries(patch).map(([k, v]) => [k, v == null ? "" : String(v)]));
  if (Object.entries(next).every(([k, v]) => (s[k] || "") === v)) return;
  S.set(next, { replace: true });
}

/* What the open dialog names changed (Add a site: setup=new, then setup=<site> once the
   site is made): the same entry, the new value, in place. */
export function renamed(family, from, to) {
  const cur = open.get(family);
  if (!cur || cur.value !== String(from)) return;
  cur.value = String(to);
  if (S.read()[family] === String(from)) S.set({ [family]: String(to) }, { replace: true });
}

export const isOpen = (family) => !!open.get(family)?.isOpen?.();
export const openValue = (family) => open.get(family)?.value ?? null;

/* One plain line at the top of the page, for a link to something not shown here. */
export function say(words) {
  const panel = document.getElementById("panel");
  if (!panel) return null;
  panel.querySelector?.(".route-miss")?.remove();
  const x = h("button", { type: "button", class: "btn icon route-miss-x", "aria-label": "Close this note" }, "×");
  const line = h("div", { class: "state route-miss", role: "status" }, h("div", null, words), x);
  x.addEventListener("click", () => line.remove());
  panel.prepend(line);
  return line;
}
/* The key named something not shown here: the line, and the key taken away. */
export function missing(family, words) {
  open.delete(family);
  const s = S.read();
  if (s[family]) S.set({ [family]: "", ...(STEPPED.has(family) ? INSIDE_OFF : {}) }, { replace: true });
  return say(words);
}

// Words for the lines (the owner's rule: plain, never an error, never "unknown").
export const ROLE = "Not available to your role.";
export const ELSEWHERE = "That link was made in another browser: addresses, emails and person searches never go in a link, so only the browser that made it can open it. Open it again from the list.";
const isTokenLeft = (v) => hasToken(v) && String(v).replace(TOKEN, (t) => (valueOf(t) == null ? "" : t)) !== String(v);

// ---- restoring each kind from the address -----------------------------------------
// fn(value, model, state) -> a drawer (opened), a string (the plain line), or null (left alone).
const RESTORE = {
  vis: async (v, m) => (await import("./tabs/visitor.js")).openVisitKey(m, v),
  who: async (v) => (await import("./tabs/visitor.js")).openWhoKey(v),
  lead: async (v, m, s) => (await import("./tabs/sa-leads.js")).openLeadKey(m, s, v),
  conv: async (v) => (await import("./tabs/sa-lists.js")).openConvKey(v),
  req: async (v, m, s) => (await import("./tabs/si-requests.js")).openRequestKey(m, s, v),
  cohort: async (v, m, s) => (await import("./tabs/tr-retention.js")).openCohortKey(m, s, v),
  sq: async (v, m, s) => (await import("./tabs/tr-search.js")).openSearchKey(m, s, v),
  list: async (v) => (await import("./tabs/person.js")).openListKey(v),
  scan: async () => null,   // Security's scanner rows load with the tab, which opens it (sec-scanners.js)
  ans: async (v) => (/^[A-Za-z0-9_-]{1,40}$/.test(v) ? (await import("./tabs/ai-answers.js")).openAnswer(v) : "That answer is not one Skald keeps."),
  // A site's name (it has a dot; the set-up dialogs' names never do) is its Add a site wizard
  // on any tab: Connections' "Set up with your AI agent" opens it there.
  setup: async (v, m, s) => (s.tab === "settings/sitesadmin" || v.includes(".") ? (await import("./tabs/sitesadmin.js")).openSiteKey(v, Number(s.step) || 1, s)
    : (await import("./tabs/setup-dialogs.js")).openSetupKey(v, m, Number(s.step) || 1, s.share === "1")),
  conn: async (v, m, s) => (await import("./tabs/connections.js")).openConnKey(v, m, Number(s.step) || 1, s.share === "1"),
  dlg: async (v, m, s) => {
    if (extra[`dlg:${v}`]) return extra[`dlg:${v}`](m, s);
    if (v === "keys") return (await import("./keys.js")).help();
    if (v === "new") return (await import("./keys.js")).whatsNew();
    if (v === "views") return (await import("./extras.js")).savedDialog();
    if (v === "find") { const p = await import("./tabs/person.js"); return p.mayFind() ? p.openSearch() : ROLE; }
    return "That dialog is not in this version of the page.";
  },
};
/* main.js adds what needs its own loader: addRestorer("dlg:report", (m, s) => ...). */
export function addRestorer(name, fn) { extra[name] = fn; }

/* Make what is open match the address: close what it no longer names, open what it names. */
export async function sync(m, s) {
  // An address or an email from a link made elsewhere: say so, and drop it.
  if (s.ip && isTokenLeft(s.ip)) { say(ELSEWHERE); S.set({ ip: "" }, { replace: true }); return; }
  if (s.dd && isTokenLeft(s.dd)) {
    const kept = s.dd.split("|").filter((part) => !isTokenLeft(part)).join("|");
    say(ELSEWHERE);
    S.set({ dd: kept }, { replace: true });
    return;
  }
  for (const family of OPENERS) {
    const want = s[family] || "";
    const cur = open.get(family);
    if (cur && cur.value !== want) {
      open.delete(family);
      if (cur.isOpen()) cur.close();
    }
    if (!want) continue;
    if (cur && cur.value === want && cur.isOpen()) continue;
    const tag = `${family}=${want}`;
    if (pending.has(tag) || !RESTORE[family]) continue;
    pending.add(tag);
    try {
      const got = await RESTORE[family](want, m, s);
      if (typeof got === "string") missing(family, got);
    } catch (e) {
      missing(family, "That part could not be opened from the link. The page is as it was.");
      if (typeof console !== "undefined") console.warn(`route ${tag}:`, e);
    } finally { pending.delete(tag); }
  }
}
