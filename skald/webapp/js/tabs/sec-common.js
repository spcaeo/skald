// Security (2.21): what every tab of the section shares. Each tab answers one question
// (s-security.js); this draws its head (title, the question, an (i) with Learn more, the
// period), loads security.json once a minute and the addresses (owners and admins, the
// helper's people/security), sums the period (js/sec-data.js) and hands it to the tab.

import { h, n, short } from "../ui.js";
import * as S from "../state.js";
import { base, getJSON, rangeOf } from "../data.js";
import { DEMO } from "../demo.js";
import { time as tzTime } from "../tz.js";
import { call } from "./ipmanager.js";
import { mayFind } from "./person.js";
import { tabHead, emptyState } from "./sa-options.js";
import { periodOf, sumOf } from "../sec-data.js";
import { countryWords } from "./readers.js";

export const HELP = "#help?part=security";
export const at = (ts) => (ts ? tzTime(ts, { date: true, label: false }) : "-");
export const flagOf = (cc) => (cc ? countryWords(cc) : "Not recorded");

// What a probe looked for, in the words of security_names.CATEGORIES (the file says them too).
export const LOOKED = { injection: "Path tricks and injection", secrets: "Secret files (.env, keys)", cloud: "Cloud and deploy configs",
  wordpress: "WordPress", dumps: "Database dumps and backups", admin: "Admin panels and consoles", php: "PHP scripts", other: "Other probes" };
export const ADVICE = {
  secrets: ["Deny dotfiles and key files at the web server, then rotate any secret the file held.", "location ~ /\\. { deny all; }"],
  cloud: ["Keep deploy and cloud files out of the web root, or deny them.", "location ~* \\.(tf|tfvars|tfstate|ya?ml)$ { deny all; }"],
  dumps: ["Move backups and dumps out of the web root, or deny them.", "location ~* \\.(sql|bak|zip|tar|gz)$ { deny all; }"],
  wordpress: ["If the site is not WordPress, answer these paths with a 404.", ""],
  php: ["If the site runs no PHP, answer *.php with a 404 rather than a page.", ""],
  admin: ["Put admin panels behind a login or an address allow-list.", ""],
  injection: ["Check the page that answered: it should refuse a path or query like this.", ""],
};
export const adviceOf = (cat) => ADVICE[cat] || ["Open the path yourself and check what it returns; deny it at the web server if it is not meant to be public.", ""];

let FILE = { key: "", at: 0, p: null };
// Tests start again from nothing (tests/js/security.mjs).
export function forget() { FILE = { key: "", at: 0, p: null }; ASKED.clear(); }
export function loadFile(s) {
  const key = `${s.view || "all"}`;
  if (FILE.p && FILE.key === key && Date.now() - FILE.at < 60000) return FILE.p;
  FILE = { key, at: Date.now(), p: getJSON(`${base(s.view)}security.json`).catch(() => null) };
  return FILE.p;
}

const ASKED = new Map();
/* Who may see addresses: an owner or admin; in the demo, everyone (its addresses are the
   documentation ranges, written by tools/demo.py as an owner would see them). */
export const mayAddresses = () => mayFind() || (DEMO.on && !!DEMO.api.people["people/security"]);

/* The addresses behind the period's rows, for an owner or admin; null for anyone else. */
export function loadAddresses(first, last) {
  if (!mayAddresses()) return Promise.resolve(null);
  const url = `people/security?first=${first}&last=${last}`;
  const got = ASKED.get(url);
  if (got && Date.now() - got.at < 60000) return got.p;
  const p = call(url).catch((e) => ({ ok: false, error: String(e?.message || e) }));
  ASKED.set(url, { at: Date.now(), p });
  p.then((r) => { if (!r?.ok) ASKED.delete(url); });
  return p;
}

export const spanOf = (m, r) => (r.kind === "today" ? [m.today, m.today] : [r.first, r.last]);

/* The days of the period without figures, said once ("not recorded", never 0). */
export function missingNote(p, t) {
  if (!p.missing.length) return null;
  const words = p.missing.length <= 4 ? p.missing.map(short).join(", ") : `${p.missing.length} days`;
  return h("p", { class: "note sec-missing" }, `Not recorded: ${words}. Security is counted from 2.21 on, for days the raw log still held; those days are left out, never counted as 0.${t.days ? ` The figures cover ${t.days} day${t.days === 1 ? "" : "s"}.` : ""}`);
}

/* A tab of the section: its head, then `draw(ctx)` once security.json is in. */
export function secTab(m, s, { title, question, help, draw, period }) {
  const r = rangeOf(m, s);
  const top = tabHead(title, question, r, { help, more: HELP, period });
  const body = h("div", { class: "sec-body" }, h("p", { class: "empty" }, "Loading Security…"));
  if (s.view && s.view !== "all") {
    body.replaceChildren(emptyState("Security covers the whole site, every host: choose All pages to see it.", ["Show all pages", () => S.set({ view: "" })]));
    return [...top, body];
  }
  loadFile(s).then((f) => {
    if (!f) return body.replaceChildren(emptyState("Security is not written beside this page yet. It is counted from the next run on."));
    if (f.state === "error") return body.replaceChildren(emptyState(`security.json could not be built on the last redraw: ${f.error || "no reason given"}.`, null, { bad: true }));
    const p = periodOf(f, r);
    const t = sumOf(p.blobs);
    const parts = [draw({ f, r, p, t, m, s })].flat(Infinity).filter(Boolean);
    body.replaceChildren(...parts);
  });
  return [...top, body];
}

/* The words for addresses a reader cannot see, and why. */
export function addressWords(ans, f) {
  if (!mayAddresses()) return "Addresses show to owners and admins only.";
  if (!ans) return "";
  if (!ans.ok) return ans.error || "The addresses could not be loaded.";
  if (ans.mode === "off") return "This site does not keep addresses (Settings > Privacy), so each day's rows stand alone, without one.";
  if (ans.mode === "short") return "This site keeps addresses shortened (Settings > Privacy): each row is a network (/24 or /48), never one address.";
  if (DEMO.on) return "In the demo, the addresses are from the documentation ranges, shown as an owner sees them.";
  if (ans.kept_from && f) return `Addresses are kept from ${short(ans.kept_from)} (privacy.keep_days ${ans.keep_days}); an older row has none.`;
  return "";
}

/* "120 (2xx 3, 4xx 117)": a count and how the server answered it. */
export function answered(status) {
  const parts = ["2xx", "3xx", "4xx", "5xx"].filter((k) => status?.[k]).map((k) => `${k} ${n(status[k])}`);
  return parts.length ? parts.join(", ") : "-";
}

export function topOf(obj, k = 2) {
  const got = Object.entries(obj || {}).filter(([key]) => key !== "(all others)").sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
  return got.slice(0, k).map(([key]) => LOOKED[key] || key).join(", ") + (got.length > k ? ` +${got.length - k}` : "");
}
