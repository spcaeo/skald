// Settings > Reports (client_reports_api.py): branded reports an agency sends
// its clients, as a mail with a PDF attached, on their own schedule. The list
// says when each goes next, which period it will cover, who has confirmed and
// how the last send went; each has Preview, PDF, Send now, History, Edit and
// Delete. Agency branding (name, colour, logo) is the organisation's, on every
// report of every site it has. Owners and admins only.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { head1, field, input, status, when, why, confirmIn } from "./forms.js";
import { reportForm, scheduleWords, previewBox, downloadPdf } from "./reportform.js";
import { DEMO, DEMO_SAYS } from "../demo.js";

const BASIC = "Client reports come with accounts (access.mode: sessions).";
const fmtDay = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const span = (a, b) => `${fmtDay(a)} – ${fmtDay(b)}`;
let said = null;
// What a save says about the confirm links: the helper's `confirm` (client_reports_api.save).
const SAVED = {
  asked: "Saved. A confirm link was mailed to each recipient who has not confirmed; the report goes to confirmed recipients only.",
  no_mail: "Saved. No confirm link was sent: no mail server is set up (Settings > Mail). Set one up, then save the report again.",
  none: "Saved.",
};

function sendRow(x) {
  return h("tr", null, h("td", null, when(x.at)), h("td", null, x.by === "schedule" ? "The schedule" : x.by),
    h("td", null, x.first ? span(x.first, x.last) : "—"), h("td", null, x.recipients.length ? x.recipients.join(", ") : "—"),
    h("td", null, h("span", { class: `tf ${x.ok ? "on" : "off"}` }, x.ok ? "sent" : "not sent"), " ", x.detail));
}

function history(sends) {
  if (!sends.length) return h("p", { class: "empty" }, "Not sent yet.");
  return h("div", { class: "scroll" }, h("table", null, h("caption", { class: "vh" }, "Sends of this report"),
    h("thead", null, h("tr", null, ["When", "Started by", "Period", "To", "Outcome"].map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", null, sends.map(sendRow))));
}

function item(rep, r, redraw, edit) {
  const s = rep.spec;
  const msg = status();
  const extra = h("div");
  const last = rep.last_send;
  const btn = (words, fn, cls = "btn") => { const b = h("button", { type: "button", class: cls }, words); b.addEventListener("click", () => fn(b)); return b; };
  const acts = h("div", { class: "mp-row" },
    btn("Preview", async (b) => {
      b.disabled = true; msg.textContent = "Building the report…"; msg.className = "msg";
      const got = await call("settings/report-preview", { id: rep.id });
      b.disabled = false;
      if (!got.ok) { msg.say(why(got, "The preview could not be built.")); return; }
      msg.say("");
      const box = previewBox();
      box.show(got);
      extra.replaceChildren(box);
    }),
    btn("Download PDF", () => downloadPdf({ id: rep.id }, msg)),
    btn("Send now", (b) => confirmIn(b.parentElement, `Send it to ${rep.confirmed.length} confirmed recipient${rep.confirmed.length === 1 ? "" : "s"} now?`, "Send", async () => {
      const got = await call("settings/report-send", { id: rep.id });
      said = [rep.id, got.ok ? `Sent: ${got.words}.` : why(got), !!got.ok];
      redraw();
    }, redraw)),
    btn("History", async () => {
      const got = await call(`settings/report-log?id=${rep.id}`);
      extra.replaceChildren(got.ok ? history(got.sends) : h("p", { class: "note" }, why(got)));
    }),
    btn("Edit", () => edit(rep)),
    btn("Delete", (b) => confirmIn(b.parentElement, `Delete "${s.name}" and its history?`, "Delete", async () => {
      const got = await call("settings/report-delete", { id: rep.id });
      said = got.ok ? null : [rep.id, why(got), false];
      redraw();
    }, redraw), "btn danger"));
  if (said && said[0] === rep.id) { msg.say(said[1], said[2]); said = null; }
  const who = [`${rep.confirmed.length} confirmed`, rep.waiting.length ? `${rep.waiting.length} waiting for the confirm link (${rep.waiting.join(", ")})` : null].filter(Boolean).join(", ");
  return h("article", { class: "rp-item" },
    h("h3", null, s.name, s.paused ? h("span", { class: "tf off" }, "paused") : null),
    h("dl", { class: "rp-facts" },
      h("dt", null, "When"), h("dd", null, `${scheduleWords(s.schedule)} (${r.timezone})`),
      h("dt", null, "Next"), h("dd", null, rep.next ? `${when(rep.next)}, covering ${span(rep.next_first, rep.next_last)}` : "Not scheduled (paused)"),
      h("dt", null, "Period"), h("dd", null, r.periods[s.period]),
      h("dt", null, "Sections"), h("dd", null, s.sections.map((k) => r.section_words[k]).join(", ")),
      h("dt", null, "Recipients"), h("dd", null, who),
      h("dt", null, "Last send"), h("dd", null, last ? [h("span", { class: `tf ${last.ok ? "on" : "off"}` }, last.ok ? "sent" : "not sent"), ` ${when(last.at)}: ${last.detail}`] : "Not sent yet")),
    acts, msg, extra);
}

// Agency branding: the organisation's name and colour (settings/save, org rows) and logo.
function brandCard(r, redraw) {
  const b = r.branding;
  const msg = status();
  const nm = input({ value: b.agency_name || "", maxlength: "60", placeholder: "Example Agency" });
  const hex = input({ value: b.color || "", maxlength: "7", placeholder: "#0f766e", pattern: "#[0-9a-fA-F]{6}", "aria-label": "Brand colour, as #rrggbb" });
  const pick = h("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(b.color || "") ? b.color : "#17212b", "aria-label": "Pick the brand colour" });
  pick.addEventListener("input", () => { hex.value = pick.value; });
  const save = h("button", { type: "submit", class: "btn primary" }, "Save");
  const form = h("form", { class: "af-col", novalidate: true }, field("Agency name", nm, "In each report's header and as the mail's From name."),
    field("Brand colour", h("div", { class: "rp-two" }, pick, hex), "The band on top of each report. Empty: Skald's ink."), h("div", null, save));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    save.disabled = true;
    const got = await call("settings/save", { "brand.agency_name": nm.value.trim() || null, "brand.color": hex.value.trim().toLowerCase() || null });
    save.disabled = false;
    if (!got.ok) { msg.say(why(got)); return; }
    said = ["brand", "Saved.", true];
    redraw();
  });
  const file = h("input", { type: "file", accept: ".png,.jpg,.jpeg,image/png,image/jpeg" });
  file.addEventListener("change", () => {
    const f = file.files?.[0];
    if (!f) return;
    if (f.size > 256 * 1024) { msg.say("The logo is a PNG or JPEG of at most 256 KB."); return; }
    const rd = new FileReader();
    rd.onload = async () => {
      const got = await call("settings/agency-logo", { data: String(rd.result).split(",")[1] || "" });
      said = ["brand", got.ok ? "Logo saved." : why(got), !!got.ok];
      redraw();
    };
    rd.readAsDataURL(f);
  });
  const remove = h("button", { type: "button", class: "btn", disabled: !b.logo }, "Remove the logo");
  remove.addEventListener("click", async () => { const got = await call("settings/agency-logo", { data: null }); said = ["brand", got.ok ? "Logo removed." : why(got), !!got.ok]; redraw(); });
  if (said && said[0] === "brand") { msg.say(said[1], said[2]); said = null; }
  return h("section", { class: "sheet acct-card" }, h("h2", null, "Agency branding"),
    h("p", { class: "sub" }, `For every report of ${r.org}. The site's own logo (Settings > Sites) sits on the left of each report; yours on the right.`),
    form, h("div", { class: "rp-logo" }, b.logo ? h("img", { src: `settings/agency-logo?v=${Date.now()}`, alt: "The agency logo", height: "40" }) : h("p", { class: "empty" }, "No logo yet: the agency's name is shown instead."),
      field("Agency logo (PNG or JPEG, at most 256 KB)", file), remove), msg);
}

export default function reports(m) {
  const lede = "Branded reports for your clients: a mail with a PDF attached, on a schedule you set.";
  if (!sessions()) return [head1("Reports", lede), h("div", { class: "state" }, h("div", null, BASIC))];
  if (DEMO.on) return [head1("Reports", lede), h("div", { class: "state" }, h("div", null, DEMO_SAYS))];
  if (!["owner", "admin"].includes(ME.role) && !ME.install_admin) return [head1("Reports", lede), h("div", { class: "state" }, h("div", null, "Only an admin or an owner sets up client reports."))];
  const box = h("div", { class: "set-cards" }, h("p", { class: "empty" }, "Loading the reports…"));
  let editing;   // undefined: the list; null: a new report; else the report being edited
  const load = () => call("settings/reports").then(draw);
  function draw(r) {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The reports could not be loaded.")))); return; }
    const edit = (rep) => { editing = rep; draw(r); };
    const done = (saved, confirm) => { if (saved) said = [saved.id, SAVED[confirm] || SAVED.none, true]; editing = undefined; load(); };
    const add = h("button", { type: "button", class: "btn primary" }, "New report");
    add.addEventListener("click", () => edit(null));
    const list = r.reports.length ? r.reports.map((rep) => item(rep, r, load, edit)) : [h("p", { class: "empty" }, "No reports yet.")];
    box.replaceChildren(...[
      r.mail_ready ? null : h("div", { class: "state warn" }, h("div", null, "No mail server is set up yet (Settings > Mail). Reports can be made, previewed and downloaded, but not sent.")),
      editing !== undefined ? reportForm(r, editing, done)
        : h("section", { class: "sheet acct-card" }, h("h2", null, `Reports for ${m.site}`), h("p", { class: "sub" }, "Figures come from verified days only: a day that did not reconcile is listed and left out, never counted as zero."), ...list, h("div", null, add)),
      brandCard(r, load)].filter(Boolean));
  }
  load();
  return [head1("Reports", lede), box];
}
