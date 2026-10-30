// Settings > Data retention, Mail, Sites and Security (accounts, access.mode:
// sessions): the settings people change from the page (settings_api.py,
// docs/SETTINGS.md). GET <page>/settings says each value, where it comes from
// and whether this reader may change it; a field they cannot change is shown
// read-only with the reason. A smaller retention window shows what it will
// remove and needs the site's name typed; removal happens at the next run.
// Secrets (the SMTP password, the PageSpeed key) are write-only: the page
// only ever says "set" or "not set". Goals (beacon.goals) are ticked from the
// events the site has counted; the others wait under "Not counted yet". Page
// assets (site.asset_prefixes, one per line) and the rendering rule decide
// which visits count as people (rendering.py). Keeping IP addresses
// (privacy.keep_ips) is a choice of three: full, shortened or not kept. Under
// it, "Wording for your privacy notice" (people/notice.py, the answer's
// `notice`) says what this site's settings keep, with a Copy button. Leads
// (2.29): conversions.retention_days is "kept for good" (0) or N days, a
// choice of two (`forever` in the answer); journeys.vid_days is the days an
// ID's pages are kept before it signs up.
//
// v2 (Settings v2): a page shows each card as rows (set-parts.js: the value in words and a
// pill); the card's form opens in its drawer, edit=<id> in the address (set-edit.js). The
// cards are PARTS below, by id. One Save per form, active once something changed.

import { h, toast } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { head1, field, input, status, why, moreOptions } from "./forms.js";
import logoCard from "./sitelogo.js";
import { mailPreview } from "./mailpreview.js";
import { fillChoice, fillNote, remember, viewsFill } from "./viewsfill.js";
import { withCopy, withUrl } from "../urlactions.js";
import { mailServerNote, waitingWords } from "../mail-ready.js";
import { isViewer } from "../access.js";
import { editPart, openEdit } from "./set-edit.js";
import { partCard } from "./set-parts.js";
import { help, primary, rowsCard, statusRow } from "./set-ui.js";

const SOURCE = { site: "set for this site", org: "set for the organisation", install: "set for the whole install", config: "from config.yml", default: "the default",
  upgrade: "kept off by the upgrade to 2.4.0; turn it on once your privacy notice says so" };
const BASIC = "These settings come with accounts. On this server they are set in config.yml by whoever runs it.";
// privacy.keep_ips (2.15.0): the three choices, each with one line.
const IP_MODES = [
  ["full", "Full address", "Each visit is kept with its whole IP address."],
  ["short", "Shortened (last part removed)", "203.0.113.57 is kept as 203.0.113.0; an IPv6 address keeps its first 48 bits. The country and city still come from the full address. One shortened address can be several people."],
  ["off", "Don't keep", "No address is kept with the visits. The visits already kept with one are deleted at the next nightly run."],
];
// A `forever` key's 0 keeps the most: a shorter window is any number after it.
const endless = (s, v) => (s.forever && v === 0 ? Infinity : v);
const keepsLess = (s, v) => typeof v === "number" && !Number.isNaN(v) && endless(s, v) < endless(s, s.value);
// A line before a number's range, for the keys that need one.
const HINTS = { "journeys.vid_days": "Days. Once they sign up, their pages are kept with the lead. " };
const IP_SWITCH = "From full to shortened, the addresses already kept are shortened at the next nightly run. From shortened to full, only new visits are kept in full: the ones kept before stay shortened.";

// One field per setting: get() is the value to save, or undefined when unchanged.
function control(name, s) {
  const ro = !s.editable;
  const note = ro ? h("small", { class: "ro-why" }, s.reason || "You cannot change this.") : h("small", null, SOURCE[s.source] || "");
  const id = `set-${name.replace(/\W/g, "-")}`;
  let el, get;
  if (s.hidden) {
    return { el: field(s.label, h("p", { class: "muted" }, "Shown to install admins only."), s.reason), get: () => undefined };
  }
  if (s.kind === "secret") {
    el = input({ type: "password", id, autocomplete: "new-password", maxlength: "500", placeholder: s.set ? "set: type to replace" : "not set", disabled: ro });
    const clear = h("label", { class: "chk chk-clear" }, h("input", { type: "checkbox", disabled: ro || !s.set }), h("span", null, "Clear it"));
    const badge = h("span", { class: `tf ${s.set ? "on" : "off"}` }, s.set ? "set" : "not set");
    get = () => (clear.querySelector("input").checked ? null : el.value ? el.value : undefined);
    return { el: field(s.label, h("div", { class: "sec-row" }, el, badge, clear), ro ? s.reason : s.env ? "The server's environment also sets it, and wins." : "Write-only: it is never shown again."), get };
  }
  if (s.kind === "bool") {
    el = h("input", { type: "checkbox", id, checked: !!s.value, disabled: ro });
    get = () => (el.checked === !!s.value ? undefined : el.checked);
    return { el: h("div", { class: "af" }, h("label", { class: "chk" }, el, h("span", null, h("b", null, s.label))), note), get };
  }
  if (s.kind === "ipmode") {
    // true and false from an older answer read as full and off.
    const was = s.value === true ? "full" : s.value === false ? "off" : s.value || "full";
    const box = h("fieldset", { class: "af-set", id }, h("legend", null, s.label),
      IP_MODES.map(([v, t, line]) => h("label", { class: "chk" }, h("input", { type: "radio", name: id, value: v, checked: v === was, disabled: ro }), h("span", null, h("b", null, t), h("small", null, line)))));
    get = () => {
      const now = [...box.querySelectorAll("input")].find((i) => i.checked)?.value;
      return !now || now === was ? undefined : now;
    };
    return { el: h("div", { class: "af" }, box, note, ro ? null : h("small", null, IP_SWITCH)), get };
  }
  if (s.kind === "int" && s.forever) {
    // Kept for good (0) or N days: two choices, the days typed beside the second.
    const good = s.value === 0;
    const days = input({ type: "number", id: `${id}-days`, value: good ? "" : s.value ?? "", min: s.lo, max: s.hi, inputmode: "numeric", disabled: ro, "aria-label": `${s.label}: days` });
    const pick = (v, on, ...words) => h("label", { class: "chk" }, h("input", { type: "radio", name: id, value: v, checked: on, disabled: ro }), h("span", null, ...words));
    const box = h("fieldset", { class: "af-set", id }, h("legend", null, s.label),
      pick("forever", good, h("b", null, "Kept for good"), h("small", null, "Skald never deletes them. A person's own request to be deleted still removes everything about them.")),
      pick("days", !good, days, h("small", null, `days (${s.lo} to ${s.hi})`)));
    days.addEventListener("focus", () => box.querySelectorAll('input[type="radio"]').forEach((r) => { r.checked = r.value === "days"; }));
    get = () => {
      const now = [...box.querySelectorAll('input[type="radio"]')].find((i) => i.checked)?.value;
      const v = now === "forever" ? 0 : days.value.trim() === "" ? undefined : Number(days.value.trim());
      return v === undefined || v === s.value ? undefined : v;
    };
    const capped = s.capped ? `Capped by your plan: ${s.hi} days at most. ` : "";
    return { el: h("div", { class: "af" }, box, ro ? note : h("small", null, `${capped}${SOURCE[s.source] || ""}`)), get, input: box };
  }
  if (s.kind === "events") {
    const was = s.value || [];
    const box = (e) => h("label", { class: "chk" }, h("input", { type: "checkbox", value: e.name, checked: was.includes(e.name), disabled: ro }), h("span", null, h("b", null, e.label), h("small", null, e.name)));
    const all = s.events || [];
    const seen = all.filter((e) => e.seen || was.includes(e.name));
    const rest = all.filter((e) => !seen.includes(e));
    el = h("fieldset", { class: "af-set", id }, h("legend", null, s.label),
      seen.length ? seen.map(box) : h("p", { class: "muted" }, "No event counted on this site yet."),
      rest.length ? h("details", null, h("summary", null, `Not counted yet (${rest.length})`), rest.map(box)) : null);
    get = () => {
      const now = [...el.querySelectorAll("input:checked")].map((c) => c.value);
      return now.join(" ") === was.join(" ") ? undefined : now;
    };
    return { el: h("div", { class: "af" }, el, note), get };
  }
  if (s.kind === "notpages") {
    // site.not_pages_off (2.35): ticked = not counted as a page (the default); the value
    // saved is the entries left unticked, counted as pages again.
    const off = s.value || [];
    const all = s.entries || [];
    el = h("fieldset", { class: "af-set", id }, h("legend", null, s.label),
      all.map((e) => h("label", { class: "chk" }, h("input", { type: "checkbox", value: e.name, checked: !off.includes(e.name), disabled: ro }),
        h("span", null, withCopy(h("b", null, e.name), e.name, { label: `entry ${e.name}` }), withCopy(h("small", null, e.reason), e.reason, { label: `why ${e.name}` })))));
    get = () => {
      const now = [...el.querySelectorAll("input")].filter((c) => !c.checked).map((c) => c.value);
      return now.join(" ") === off.join(" ") ? undefined : now;
    };
    return { el: h("div", { class: "af" }, el, note), get };
  }
  if (s.kind === "postpaths") return postPaths(s, id, ro, note);
  if (s.kind === "choice") {
    el = h("select", { id, disabled: ro }, h("option", { value: "" }, name === "mail.smtp.security" ? "from the port" : "the default"), (s.choices || []).map((c) => h("option", { value: c, selected: c === s.value }, c)));
    get = () => ((el.value || null) === (s.value || null) ? undefined : el.value || null);
  } else if (s.kind === "emails" || s.kind === "hosts" || s.kind === "prefixes" || s.kind === "pagepatterns") {
    const text = (s.value || []).join("\n");
    el = h("textarea", { id, rows: "3", spellcheck: "false", disabled: ro, placeholder: s.kind === "prefixes" ? "/wp-content/\n/wp-includes/" : s.kind === "pagepatterns" ? "/status\n/preview/*\n?preview" : null }, text);
    get = () => {
      const items = el.value.split(/[\s,]+/).filter(Boolean);
      if (items.join("\n") === text) return undefined;
      // An empty list of asset paths clears the row: the default (/_next/static/) applies.
      return (s.kind === "prefixes" || s.kind === "pagepatterns") && !items.length ? null : items;
    };
    if (s.kind === "pagepatterns" && (s.value || []).length) {
      // The saved entries, each with its icons: an exact path opens on the site; /prefix* and ?key copy only.
      const saved = h("p", { class: "note" }, "Saved: ", (s.value || []).map((v, i) => [i ? ", " : "",
        /^\/[^*?]*$/.test(v) ? withUrl(h("span", { class: "mono" }, v), v) : withCopy(h("span", { class: "mono" }, v), v, { label: `entry ${v}` })]));
      return { el: h("div", { class: "af" }, field(s.label, el, ro ? s.reason : SOURCE[s.source] || ""), saved), get, input: el };
    }
  } else if (s.kind === "views") {
    const line = (v) => [v.name, v.path_prefix || "", v.exclude_prefix || ""].join(" | ").replace(/( \| )+$/, "");
    const text = (s.value || []).map(line).join("\n");
    el = h("textarea", { id, rows: "4", spellcheck: "false", disabled: ro, placeholder: "Canada | /ca/ | /ca/fr/" }, text);
    get = () => {
      if (el.value.trim() === text.trim()) return undefined;
      return el.value.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
        const [nm, prefix = "", exclude = ""] = l.split("|").map((x) => x.trim());
        return { name: nm, path_prefix: prefix, exclude_prefix: exclude };
      });
    };
    // Under the box: fill the new groups' past days after saving (viewsfill.js).
    if (!ro) return { el: h("div", { class: "af-views" }, field(s.label, el, SOURCE[s.source] || ""), fillChoice()), get, input: el };
  } else {
    const num = s.kind === "int";
    el = input({ id, type: num ? "number" : s.kind === "email" ? "email" : "text", value: s.value ?? "", min: s.lo, max: s.hi, inputmode: num ? "numeric" : null, disabled: ro, maxlength: num ? null : "300", autocomplete: s.kind === "email" ? "off" : null });
    get = () => {
      const raw = el.value.trim();
      if (raw === String(s.value ?? "")) return undefined;
      if (!raw) return null;
      return num ? Number(raw) : raw;
    };
  }
  // A plan that keeps fewer days than the saved value: the plan's cap is what applies (saas).
  const capped = s.capped ? `Capped by your plan: ${s.hi} days at most (it was set to ${s.set_value}). ` : "";
  const hint = (HINTS[name] || "") + (s.lo != null ? `${s.lo} to ${s.hi}. ` : "") + capped;
  const src = SOURCE[s.source] || "";
  return { el: field(s.label, el, ro ? s.reason : hint && src ? `${hint}${src[0].toUpperCase()}${src.slice(1)}.` : `${hint}${src}`), get, input: el };
}

/* site.script_posts (form_names.py): POST paths the site's own pages send by themselves,
   not forms. The ones Skald suggests from the stored days, each with Add; the saved ones, each
   with Remove; one typed by hand. Nothing is applied until Save. */
function postPaths(s, id, ro, note) {
  const was = s.value || [];
  let now = [...was];
  const box = h("fieldset", { class: "af-set", id });
  const typed = input({ type: "text", placeholder: "/api/track or /ingest/*", maxlength: "100", spellcheck: "false", disabled: ro, "aria-label": "A path to add" });
  const changed = () => box.dispatchEvent(new Event("change", { bubbles: true }));
  const shown = (p) => (/^\/[^*]*$/.test(p) ? withUrl(h("span", { class: "mono" }, p), p) : withCopy(h("span", { class: "mono" }, p), p, { label: `path ${p}` }));
  const btn = (words, act) => (ro ? null : h("button", { type: "button", class: "btn", onclick: () => { act(); draw(); changed(); } }, words));
  const draw = () => {
    const sug = (s.suggested || []).filter((x) => !now.includes(x.path));
    box.replaceChildren(...[h("legend", null, s.label),
      sug.length ? h("p", null, h("b", null, "Suggested from your log")) : null,
      sug.length ? h("ul", { class: "plain" }, sug.map((x) => h("li", null, shown(x.path),
        h("small", null, ` sent by ${x.visits} of the ${x.of_posting} visits that sent a POST, of ${x.of_all} visits, on ${x.day}; like that on ${x.days} days. If it is a real form, leave it.`),
        " ", btn("Add", () => { now = [...now, x.path]; })))) : null,
      h("p", null, h("b", null, "Saved")),
      now.length ? h("ul", { class: "plain" }, now.map((p) => h("li", null, shown(p), " ", btn("Remove", () => { now = now.filter((x) => x !== p); }))))
        : h("p", { class: "muted" }, "None of your own."),
      ro ? null : h("div", { class: "af-row" }, typed, btn("Add", () => { const v = (typed.value || "").trim(); if (v && !now.includes(v)) now = [...now, v]; typed.value = ""; })),
      (s.defaults || []).length ? h("details", null, h("summary", null, `Never forms on any site (${s.defaults.length})`),
        h("p", { class: "note" }, s.defaults.map((p, i) => [i ? ", " : "", withCopy(h("span", { class: "mono" }, p), p, { label: `path ${p}` })]),
          ". A POST answered 204 with no body is never a form either.")) : null].filter(Boolean));
  };
  draw();
  const get = () => {
    const v = (typed.value || "").trim();
    const all = v && !now.includes(v) ? [...now, v] : now;
    if (all.join(" ") === was.join(" ")) return undefined;
    return all.length ? all : null;
  };
  return { el: h("div", { class: "af" }, box, note), get };
}

// "At the next run this removes ..." for a smaller retention window.
async function previewWords(name, value) {
  const r = await call(`settings/retention-preview?key=${encodeURIComponent(name)}&value=${encodeURIComponent(value)}`);
  if (r.ok && r.kept) return `${r.words} A shorter window removes nothing on this site.`;
  if (!r.ok || !r.shrinks) return "";
  if (name.startsWith("backup.")) return `${r.files} backup cop${r.files === 1 ? "y" : "ies"} will be deleted.`;
  const spool = r.files ? ` and ${r.files} beacon files` : "";
  return r.rows ? `${r.rows.toLocaleString("en-US")} stored rows over ${r.days} day${r.days === 1 ? "" : "s"} (${r.first} to ${r.last})${spool} will be removed.` : `Nothing stored is old enough to be removed now${spool}.`;
}

// "Saved" for the card just saved: the page is drawn again from the answer, so the
// words are kept here and said by the new card of the same title.
let saved = null;
let waiting = "";   // recipients that still have to confirm (mail_confirm.py)

// A card of settings with one Save button; a smaller window asks for the site's name first.
export function card(title, sub, names, all, site, onSaved, { bare = false } = {}) {
  const rows = names.filter((k) => all[k]).map((k) => [k, control(k, all[k])]);
  const msg = status();
  if (saved === title) { msg.say(((names.includes("sites.views") && fillNote()) || "Saved. It applies from the next run.") + waiting, true); saved = null; }
  const ask = h("div");
  const save = h("button", { type: "submit", class: "btn primary" }, "Save");
  const editable = rows.some(([k]) => all[k].editable && !all[k].hidden);
  for (const [k, c] of rows) {
    const s = all[k];
    if (!s.shrink || !c.input || !s.editable) continue;
    const hint = h("small", { class: "shrink", "aria-live": "polite" });
    c.el.append(hint);
    let t;
    const look = () => {
      clearTimeout(t);
      const v = s.forever ? c.get() : Number(c.input.value);
      if (!keepsLess(s, v)) { hint.textContent = ""; return; }
      t = setTimeout(async () => { hint.textContent = await previewWords(k, v); }, 350);
    };
    c.input.addEventListener("input", look);
    c.input.addEventListener("change", look);
  }
  const form = h("form", { class: "af-col", novalidate: true }, rows.map(([, c]) => c.el), editable ? h("div", null, save) : null, ask);
  // One Save, at the foot, active once something changed (UI rule 12).
  save.disabled = true;
  const changed = () => { save.disabled = false; };
  form.addEventListener("input", changed);
  form.addEventListener("change", changed);
  async function send(confirm) {
    const body = {};
    for (const [k, c] of rows) { const v = c.get(); if (v !== undefined) body[k] = v; }
    if (!Object.keys(body).length) { msg.say("Nothing changed."); return; }
    if (confirm) body.confirm = confirm;
    save.disabled = true;
    const r = await call("settings/save", body);
    save.disabled = false;
    if (r.needs_confirm) { askName(r.keys || [], body); msg.say(""); return; }
    if (!r.ok) { msg.say(why(r)); return; }
    ask.replaceChildren();
    saved = title;
    // Never "mailed" when no mail server is set (mail-ready.js): then it says the link waits for one.
    waiting = r.mail_waiting?.length ? ` ${waitingWords(r, r.mail_waiting)}` : "";
    onSaved(r.settings, r);
  }
  async function askName(keys, body) {
    const words = (await Promise.all(keys.map((k) => previewWords(k, body[k])))).filter(Boolean);
    const typed = input({ autocomplete: "off", placeholder: site, "aria-label": "The site's name" });
    const yes = h("button", { type: "button", class: "btn danger" }, "Yes, keep less");
    const no = h("button", { type: "button", class: "btn" }, "Keep it as it is");
    yes.addEventListener("click", () => send(typed.value.trim()));
    no.addEventListener("click", () => ask.replaceChildren());
    ask.replaceChildren(h("div", { class: "state warn", role: "alert" }, h("div", null,
      h("p", null, h("strong", null, "A shorter window removes stored data at the next run. "), "It cannot be brought back from the history; only a backup holds it."),
      words.map((w) => h("p", null, w)),
      field(`Type the site's name, ${site}, to confirm`, typed), h("div", { class: "acts" }, yes, no))));
    typed.focus();
  }
  form.addEventListener("submit", (e) => { e.preventDefault(); send(); });
  if (bare) return h("div", { class: "acct-card set-form" }, form, msg);
  return h("section", { class: "sheet acct-card" }, h("h2", null, title), sub ? h("p", { class: "sub" }, sub) : null, form, msg);
}

// The page drawn last: a drawer that saved draws it again, so its rows say the new values.
let repaint = () => {};

// The page frame: loads GET settings, draws `build(settings, redraw, answer)`.
function page(title, lede, build) {
  if (!sessions()) return [head1(title, lede), h("div", { class: "state" }, h("div", null, BASIC))];
  const box = h("div", { class: "set-cards" }, h("p", { class: "empty" }, "Loading the settings..."));
  let last = null;
  const draw = (r) => {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The settings could not be loaded.")))); return; }
    last = r;
    const redraw = (settings, got) => draw({ ...r, settings, notice: got?.notice || r.notice, mail_server: got?.mail_server || r.mail_server });
    box.replaceChildren(...[build(r.settings, redraw, r)].flat(Infinity).filter(Boolean));
  };
  // From a drawer's save: the answer it got (the settings, a new notice), else asked again.
  repaint = (settings, got) => (settings && last ? draw({ ...last, settings, notice: got?.notice || last.notice, mail_server: got?.mail_server || last.mail_server }) : call("settings").then(draw));
  call("settings").then(draw);
  return [head1(title, lede), box];
}

// keep_everything.py: an internal or enterprise site deletes nothing by itself. Which
// organisation rule decides it (its rule) is said too: when it keeps everything, and when a
// client organisation's site follows its own windows on an install that keeps everything.
function keptAll(r) {
  const k = r && r.keep_everything;
  if (!k) return "";
  const rule = k.rule && k.rule.words && (k.on || k.rule.class === "client") ? k.rule.words : "";
  return k.on ? [k.words, rule].filter(Boolean).join(" ") : rule;
}

// The AI assistants' API keys (Settings › AI answers › API keys, integrations.js).
export const AI_KEYS = ["ai_answers.openai_key", "ai_answers.perplexity_key", "ai_answers.gemini_key", "ai_answers.anthropic_key"];

/* Each card: its title, its settings, the line behind its "?", and what a save also does. */
export const PARTS = {
  people: { title: "People", names: ["privacy.keep_ips", "privacy.keep_days", "conversions.identity"],
    sub: (r) => (keptAll(r) ? `${keptAll(r)} ` : "") + "Each visit's IP address and browser, with its pages and times, and the names and emails of leads, so a person can be looked up and followed (the search at the top). Visits with addresses, when you set it shorter than the leads, is also the most a lead's name and email are kept: after it the lead stays, counted, without them. Not keeping IP addresses deletes the visits kept with them at the next nightly run; keeping them shortened shortens them then. Your privacy notice must say what you keep." },
  leads: { title: "Leads", names: ["conversions.retention_days", "journeys.vid_days", "conversions.click_ids"],
    sub: "A lead is a form sent or a call booked: its name and email (when kept), where it came from, and the pages its visitor ID read. Kept for good means Skald never deletes them; a person's own request to be deleted still removes everything about them. The pages of a visitor who has not signed up yet are kept for the days below; once they sign up, their pages are kept with the lead. Ad click IDs (off unless you turn them on): the ID Google, Microsoft, Meta, LinkedIn, TikTok or X adds to an ad's link (gclid, msclkid, fbclid...), kept with the lead so it can be tied to the exact ad click. Only owners and admins see them; they go with the lead, with a deletion request, after the People days when those are shorter, and all at once when you turn this off. Your privacy notice must say so." },
  detail: { title: "Detail kept for this site", names: ["report.retention_days", "report.journey_days", "visitors.repeat_days", "beacon.keep_days"],
    sub: "Days of each kind of detail. Totals, page milestones and every day's figures are kept forever and are not a setting." },
  backups: { title: "Backups", names: ["backup.daily", "backup.weekly"], sub: "Copies of the history kept on the server, for every site of the install." },
  names: { title: "Names & time", names: ["sites.hosts", "sites.views", "sites.timezone"], saved: (got) => remember(got?.views),
    sub: "Changes apply from the next run. Days already stored are not counted again, except a new page group's: tick the box under Views to fill its past days from the raw log. Views (page groups): one per line, as name | path prefix | prefixes to leave out (separated by spaces). For example: Blog | /blog/ or Canada | /ca/ | /ca/fr/" },
  logfile: { title: "Log file", names: ["sites.log_dir", "sites.log_base"], sub: "Where the server's access log for this site is. For install admins." },
  assets: { title: "Page assets", names: ["site.asset_prefixes", "site.require_rendering"],
    sub: "A visit counts as people only when its browser also fetched one of the page's own scripts or styles. Next.js: /_next/static/ (the default). WordPress: /wp-content/ and /wp-includes/. Many other sites: /assets/ or /static/. One path per line, at most 10. Turn the rule off only when the assets come from a CDN host this log never sees. Changes apply from the next run; stored days are recounted with backfill --force on the server." },
  notpages: { title: "Not pages", names: ["site.not_pages_off", "site.not_pages_extra"],
    sub: "Machine addresses that are never a person reading a page: feeds, WordPress's API, Markdown copies for AI agents. Ticked, a request for one is not a page view; it still counts as a request, in its group. Untick one this site serves as a real page. Also not pages: your own, one per line, as /path, /prefix* or ?key, at most 20. Changes apply from the next run; stored days are recounted with backfill --force on the server." },
  notforms: { title: "Not forms", names: ["site.script_posts"],
    sub: "A visit \"sent a form\" when it made a POST. Many pages also post by themselves, with nobody doing anything: an analytics or event beacon, an error report. Those are not forms: Skald's own endpoints, a POST answered 204 with no body, the well-known beacons listed below, and the paths you add here. Skald suggests a path when most page views send it (at least half of the visits that sent a POST, and a fifth of all visits, on 3 of the last 14 days); it never adds one by itself. A real contact or sign-up form stays a form. Changes apply from the next run; stored days are recounted with backfill --force on the server." },
  script: { title: "Script tag", names: ["beacon.visitor_ids", "beacon.share_subdomains"],
    sub: "Visitor IDs: the tag keeps an anonymous random ID per browser, for journeys, abandoned forms and lead matching; your privacy notice must say so. Off, the tag still sends events but keeps no ID. Share the ID across subdomains: www. and app. see the same ID (a first-party cookie), as data-share-subdomains=\"true\" on the tag does, with the tag unchanged; browsers learn it within a day." },
  goals: { title: "Goals", names: ["beacon.goals"], sub: "The in-page events that count as this site's goals. Events shows each one per 100 visits by source, on checked days. At most 10." },
  mail: { title: "The daily and weekly mail", names: ["mail.daily", "mail.weekly", "mail.marketing", "mail.to", "mail.from_name"], sub: "The daily mail goes after each morning's run; the weekly one on Mondays. The Monday marketing mail (off until you turn it on): last week's visitors, leads and sources, then each of your tools' own figures, apart." },
  smtp: { title: "Mail server (SMTP)", names: ["mail.from", "mail.smtp.host", "mail.smtp.port", "mail.smtp.security", "mail.smtp.user", "mail.smtp.password"],
    sub: "For every site of the install. The sender address is the From of every mail. The password is write-only: this page only says whether it is set." },
  pagespeed: { title: "Google PageSpeed", names: ["pagespeed.api_key"], sub: "A free API key raises Google's daily limit for the page speed tests." },
  signin: { title: "Sign-in", names: ["security.require_totp", "security.session_days"],
    sub: "Two-step sign-in: members without it set it up the next time they sign in. Session length: how long a sign-in lasts at most." },
  aikeys: { title: "Assistants' API keys", names: AI_KEYS,
    sub: "Each key lets Skald ask that assistant the tracking profiles' questions (Settings › AI answers). The questions are sent to the provider; each answer costs a few cents on your provider account. Nothing is asked until a site admin makes a profile. Write-only: the page only says set or not." },
};
const subOf = (p, r) => (typeof p.sub === "function" ? p.sub(r) : p.sub);

/* A card's form in its drawer (edit=<id>): saved, it says so there and the page's rows follow. */
async function editBody(id, m) {
  if (!sessions()) return BASIC;
  const p = PARTS[id];
  const r = await call("settings");
  if (!r.ok) return why(r, "The settings could not be loaded.");
  const slot = h("div", { class: "set-form-w" });
  const draw = (all) => slot.replaceChildren(card(p.title, null, p.names, all, m?.site || r.site || "", (settings, got) => { p.saved?.(got); draw(settings); repaint(settings, got); }, { bare: true }));
  draw(r.settings);
  const sub = subOf(p, r);
  return [sub ? h("p", { class: "set-edit-sub" }, sub) : null, slot];
}
for (const id of Object.keys(PARTS)) editPart(id, { title: PARTS[id].title, body: (m) => editBody(id, m) });

/* A card as rows, its line behind the "?" by its title. */
export function partOf(id, all, m, r = null, title = "", extra = []) {
  const p = PARTS[id];
  const t = title || p.title;
  const sub = subOf(p, r);
  return partCard(id, t, p.names, all, m, { help: sub ? help(t, { text: sub }) : null, extra });
}

// "Wording for your privacy notice": the text the server made from this site's
// settings (people/notice.py), shown as it will be copied, with a Copy button.
function noticeCard(nt) {
  if (!nt || !Array.isArray(nt.items)) return null;
  const copy = h("button", { type: "button", class: "btn" }, "Copy");
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(nt.text); toast("Copied the wording"); } catch { toast("Copy is not allowed here; select the text instead"); }
  });
  const t = "Wording for your privacy notice";
  return h("section", { class: "ui-card set-rows notice-card" },
    h("div", { class: "ui-card-h" }, h("h2", null, t), help(t, { text: "Made from this site's settings on this page, so it says what is kept. Save a change and it is made again. Fill in or delete the parts in [square brackets] before you use it." }), h("span", { class: "ui-grow" }), copy),
    h("details", { class: "fold" }, h("summary", null, "Show the wording"),
      h("p", { class: "note" }, nt.note || "A starting point, not legal advice. Your notice must match your own situation."),
      h("div", { class: "notice-text" }, h("p", null, nt.intro), h("ul", null, nt.items.map((line) => h("li", null, line))))));
}

export function retention(m) {
  return page("Data retention", "How long the detail is kept. Totals are kept for good.", (all, redraw, r) => [
    keptAll(r) ? h("div", { class: "state ok", role: "status" }, h("div", null, h("p", null, h("strong", null, keptAll(r)), " The windows below are not applied on this site: Skald deletes and clears nothing by itself. A person's own request to be deleted, run by an admin, still removes what is kept about them."))) : null,
    partOf("people", all, m, r), partOf("leads", all, m, r), noticeCard(r.notice),
    moreOptions(partOf("detail", all, m, r), partOf("backups", all, m, r)),
  ]);
}

/* Send a test mail (edit=testmail): through the settings of the Mail page. */
function testMail() {
  const to = input({ type: "email", value: ME.user || "", autocomplete: "email", maxlength: "254" });
  const send = h("button", { type: "submit", class: "btn primary" }, "Send test mail");
  const msg = status();
  const form = h("form", { class: "af-row", novalidate: true }, field("Send to", to), send);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    send.disabled = true;
    const r = await call("settings/test-mail", { to: to.value.trim() });
    send.disabled = false;
    msg.say(r.ok ? `Sent to ${r.to}. Check that inbox.` : why(r), r.ok);
  });
  return [h("p", { class: "set-edit-sub" }, "A short mail through the mail server's settings. At most 3 in 10 minutes."), form, msg];
}
const mayMail = () => sessions() && !isViewer();
editPart("testmail", { title: "Send a test mail", body: () => (mayMail() ? testMail() : "Not available to your role.") });
editPart("preview", { title: "Preview the mail", size: "lg", body: () => {
  if (!mayMail()) return "Not available to your role.";
  const box = mailPreview();
  box.querySelector("h2")?.remove();
  return [box];
} });

export function mail(m) {
  const go = mayMail() ? primary("Send a test mail", () => openEdit("testmail", m), { iconName: "mail" }) : null;
  return [go, ...page("Mail", "The daily and weekly mail, and how it is sent.", (all, redraw, r) => [
    // No mail server: one card says so above the recipients, with who will set it up.
    mailServerNote(r, { what: "the daily and weekly mail", site: m?.site || r.site || "", route: null }),
    partOf("mail", all, m, r, "", ["owner", "admin"].includes(r.role) || r.install_admin ? [statusRow({ iconName: "", title: "Preview the mail",
      line: "The daily or the weekly mail as it would go now. Nothing is sent.", label: "Preview the mail", onOpen: () => openEdit("preview", m) })] : []),
    // The mail server is the whole install's, set once: under More options, as before.
    moreOptions(partOf("smtp", all, m, r), partOf("pagespeed", all, m, r)),
  ])];
}

/* The logo (edit=logo, sitelogo.js's card in the drawer): where it comes from, on the page. */
const LOGO_FROM = { auto: "From the site (automatic)", upload: "Uploaded", letter: "A letter on a colour" };
editPart("logo", { title: "Logo", size: "lg", body: (m) => [logoCard(m)] });
function logoRow(m) {
  const row = statusRow({ iconName: "", title: "Where the logo comes from", line: "Shown on the site picker, in the menu and on the browser tab", label: "Change the logo", onOpen: () => openEdit("logo", m) });
  call("logo/state").then((r) => {
    const small = row.querySelector("small");
    if (r.ok && small && LOGO_FROM[r.source]) small.textContent = `${LOGO_FROM[r.source]}${r.editable ? "" : " · read-only"}`;
  });
  return rowsCard("Logo", [row]);
}

/* 2.40: Settings shows the site's cards in three places (settings-pages.js): "details" (host
   names, page groups, time zone, logo: Site details), "logs" (the log file: Collect data › Send
   logs), "script" (the tag's visitor IDs and the goals: Script tag & goals) and "counting" (page
   assets, not pages: What counts). "all": every card, as the page was. bare: no title (a tab). */
export function sites(m, part = "all", { bare = false } = {}) {
  const want = (k) => part === "all" || part === k;
  const framed = (title, lede, build) => (bare ? page(title, lede, build).slice(1) : page(title, lede, build));
  return framed("Sites", "What counts as this site, and where its log is.", (all, redraw, r) => [
    want("details") ? partOf("names", all, m, r, m.site) : null,
    want("details") ? logoRow(m) : null,
    want("details") ? moreOptions(viewsFill(m)) : null,
    want("logs") ? partOf("logfile", all, m, r) : null,
    want("counting") ? partOf("assets", all, m, r) : null,
    want("counting") ? partOf("notforms", all, m, r) : null,
    want("counting") ? moreOptions(partOf("notpages", all, m, r)) : null,
    want("script") ? partOf("script", all, m, r) : null,
    want("script") ? partOf("goals", all, m, r) : null,
  ]);
}

export function security(m) {
  return page("Security", "Sign-in rules for everyone in the organisation.", (all, redraw, r) => [
    partOf("signin", all, m, r),
    r.totp_on ? null : h("p", { class: "note" }, "Turn on two-step sign-in for your own account first (Settings › Your account) before you require it."),
  ]);
}
