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

import { h, toast } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { head1, field, input, status, why } from "./forms.js";
import logoCard from "./sitelogo.js";
import { mailPreview } from "./mailpreview.js";
import { fillChoice, fillNote, remember, viewsFill } from "./viewsfill.js";

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
  if (s.kind === "choice") {
    el = h("select", { id, disabled: ro }, h("option", { value: "" }, name === "mail.smtp.security" ? "from the port" : "the default"), (s.choices || []).map((c) => h("option", { value: c, selected: c === s.value }, c)));
    get = () => ((el.value || null) === (s.value || null) ? undefined : el.value || null);
  } else if (s.kind === "emails" || s.kind === "hosts" || s.kind === "prefixes") {
    const text = (s.value || []).join("\n");
    el = h("textarea", { id, rows: "3", spellcheck: "false", disabled: ro, placeholder: s.kind === "prefixes" ? "/wp-content/\n/wp-includes/" : null }, text);
    get = () => {
      const items = el.value.split(/[\s,]+/).filter(Boolean);
      if (items.join("\n") === text) return undefined;
      // An empty list of asset paths clears the row: the default (/_next/static/) applies.
      return s.kind === "prefixes" && !items.length ? null : items;
    };
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

// "At the next run this removes ..." for a smaller retention window.
async function previewWords(name, value) {
  const r = await call(`settings/retention-preview?key=${encodeURIComponent(name)}&value=${encodeURIComponent(value)}`);
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
export function card(title, sub, names, all, site, onSaved) {
  const rows = names.filter((k) => all[k]).map((k) => [k, control(k, all[k])]);
  const msg = status();
  if (saved === title) { msg.say(((title === site && fillNote()) || "Saved. It applies from the next run.") + waiting, true); saved = null; }
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
    waiting = r.mail_waiting?.length ? ` A confirm link was mailed to ${r.mail_waiting.join(", ")}; they get no reports until they confirm.` : "";
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
  return h("section", { class: "sheet acct-card" }, h("h2", null, title), sub ? h("p", { class: "sub" }, sub) : null, form, msg);
}

// The page frame: loads GET settings, draws `build(settings, redraw)`.
function page(title, lede, build) {
  if (!sessions()) return [head1(title, lede), h("div", { class: "state" }, h("div", null, BASIC))];
  const box = h("div", { class: "set-cards" }, h("p", { class: "empty" }, "Loading the settings..."));
  const draw = (r) => {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The settings could not be loaded.")))); return; }
    const redraw = (settings, got) => draw({ ...r, settings, notice: got?.notice || r.notice });
    box.replaceChildren(...[build(r.settings, redraw, r)].flat(Infinity).filter(Boolean));
  };
  call("settings").then(draw);
  return [head1(title, lede), box];
}

// "Wording for your privacy notice": the text the server made from this site's
// settings (people/notice.py), shown as it will be copied, with a Copy button.
function noticeCard(nt) {
  if (!nt || !Array.isArray(nt.items)) return null;
  const copy = h("button", { type: "button", class: "btn" }, "Copy");
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(nt.text); toast("Copied the wording"); } catch { toast("Copy is not allowed here; select the text instead"); }
  });
  return h("section", { class: "sheet acct-card notice-card" }, h("h2", null, "Wording for your privacy notice"),
    h("p", { class: "sub" }, "Made from this site's settings on this page, so it says what is kept. Save a change and it is made again. Fill in or delete the parts in [square brackets] before you use it."),
    h("p", { class: "note" }, nt.note || "A starting point, not legal advice. Your notice must match your own situation."),
    h("div", { class: "notice-text" }, h("p", null, nt.intro), h("ul", null, nt.items.map((line) => h("li", null, line)))),
    h("div", { class: "acts" }, copy));
}

export function retention(m) {
  return page("Data retention", "How long the detail is kept. Totals are kept for good.", (all, redraw, r) => [
    card("Detail kept for this site", "Days of each kind of detail. Totals, page milestones and every day's figures are kept forever and are not a setting.",
      ["report.retention_days", "report.journey_days", "visitors.repeat_days", "beacon.keep_days"], all, m.site, redraw),
    card("People", "Each visit's IP address and browser, with its pages and times, and the names and emails of leads, so a person can be looked up and followed (the search at the top). Not keeping IP addresses deletes the visits kept with them at the next nightly run; keeping them shortened shortens them then. Your privacy notice must say what you keep.",
      ["privacy.keep_ips", "privacy.keep_days", "conversions.identity"], all, m.site, redraw),
    card("Leads", "A lead is a form sent or a call booked: its name and email (when kept), where it came from, and the pages its visitor ID read. Kept for good means Skald never deletes them; a person's own request to be deleted still removes everything about them. The pages of a visitor who has not signed up yet are kept for the days below; once they sign up, their pages are kept with the lead.",
      ["conversions.retention_days", "journeys.vid_days"], all, m.site, redraw),
    noticeCard(r.notice),
    card("Backups", "Copies of the history kept on the server, for every site of the install.", ["backup.daily", "backup.weekly"], all, m.site, redraw),
  ]);
}

function testMail() {
  const to = input({ type: "email", value: ME.user || "", autocomplete: "email", maxlength: "254" });
  const send = h("button", { type: "submit", class: "btn" }, "Send test mail");
  const msg = status();
  const form = h("form", { class: "af-row", novalidate: true }, field("Send to", to), send);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    send.disabled = true;
    const r = await call("settings/test-mail", { to: to.value.trim() });
    send.disabled = false;
    msg.say(r.ok ? `Sent to ${r.to}. Check that inbox.` : why(r), r.ok);
  });
  return h("section", { class: "sheet acct-card" }, h("h2", null, "Send a test mail"), h("p", { class: "sub" }, "A short mail through the settings above. At most 3 in 10 minutes."), form, msg);
}

export function mail(m) {
  return page("Mail", "The daily and weekly mail, and how it is sent.", (all, redraw, r) => [
    card("Reports", "The daily mail goes after each morning's run; the weekly one on Mondays.", ["mail.daily", "mail.weekly", "mail.to", "mail.from_name"], all, m.site, redraw),
    card("Mail server (SMTP)", "For every site of the install. The sender address is the From of every mail. The password is write-only: this page only says whether it is set.",
      ["mail.from", "mail.smtp.host", "mail.smtp.port", "mail.smtp.security", "mail.smtp.user", "mail.smtp.password"], all, m.site, redraw),
    card("Google PageSpeed", "A free API key raises Google's daily limit for the page speed tests.", ["pagespeed.api_key"], all, m.site, redraw),
    ["owner", "admin"].includes(r.role) || r.install_admin ? testMail() : null,
    ["owner", "admin"].includes(r.role) || r.install_admin ? mailPreview() : null,
  ]);
}

export function sites(m) {
  return page("Sites", "What counts as this site, and where its log is.", (all, redraw) => [
    card(m.site, "Changes apply from the next run. Days already stored are not counted again, except a new page group's: tick the box under Views to fill its past days from the raw log.",
      ["sites.hosts", "sites.views", "sites.timezone"], all, m.site, (settings, got) => { remember(got?.views); redraw(settings, got); }),
    h("p", { class: "note" }, "Views (page groups): one per line, as name | path prefix | prefixes to leave out (separated by spaces). For example: Blog | /blog/ or Canada | /ca/ | /ca/fr/"),
    viewsFill(m),
    logoCard(m),
    card("Log file", "Where the server's access log for this site is. For install admins.", ["sites.log_dir", "sites.log_base"], all, m.site, redraw),
    card("Page assets", "A visit counts as people only when its browser also fetched one of the page's own scripts or styles. Next.js: /_next/static/ (the default). WordPress: /wp-content/ and /wp-includes/. Many other sites: /assets/ or /static/. One path per line, at most 10. Turn the rule off only when the assets come from a CDN host this log never sees. Changes apply from the next run; stored days are recounted with backfill --force on the server.",
      ["site.asset_prefixes", "site.require_rendering"], all, m.site, redraw),
    card("Script tag", "Visitor IDs: the tag keeps an anonymous random ID per browser, for journeys, abandoned forms and lead matching; your privacy notice must say so. Off, the tag still sends events but keeps no ID. Share the ID across subdomains: www. and app. see the same ID (a first-party cookie), as data-share-subdomains=\"true\" on the tag does, with the tag unchanged; browsers learn it within a day.", ["beacon.visitor_ids", "beacon.share_subdomains"], all, m.site, redraw),
    card("Goals", "The in-page events that count as this site's goals. Events shows each one per 100 visits by source, on checked days. At most 10.", ["beacon.goals"], all, m.site, redraw),
  ]);
}

export function security(m) {
  return page("Security", "Sign-in rules for everyone in the organisation.", (all, redraw, r) => [
    card("Sign-in", "Two-step sign-in: members without it set it up the next time they sign in. Session length: how long a sign-in lasts at most.",
      ["security.require_totp", "security.session_days"], all, m.site, redraw),
    r.totp_on ? null : h("p", { class: "note" }, "Turn on two-step sign-in for your own account first (Settings > Your account) before you require it."),
  ]);
}
