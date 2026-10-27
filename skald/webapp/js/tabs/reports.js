// Settings > Mail & reports > Client reports (client_reports_api.py): branded reports an agency sends
// its clients, as a mail with a PDF attached, on their own schedule. The list
// says when each goes next, which period it will cover, who has confirmed and
// how the last send went; each has Preview, PDF, Send now, History, Edit and
// Delete. Agency branding (name, colour, logo) is the organisation's, on every
// report of every site it has. Owners and admins only.
//
// v2 (Settings v2): the reports are rows (the schedule and the next send, a pill), "New
// report" is the page's one button; each report, its form and the branding open in a drawer,
// in the address: edit=report-new, report-<id>, reportedit-<id>, branding (set-edit.js).

import { h, toast } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME, sessions } from "../access.js";
import { head1, field, input, status, when, why, confirmIn } from "./forms.js";
import { reportForm, scheduleWords, previewBox, downloadPdf } from "./reportform.js";
import { DEMO, DEMO_SAYS } from "../demo.js";
import { copyIf } from "../urlactions.js";
import { editPart, openEdit } from "./set-edit.js";
import { primary, rowsCard, statusRow, help, strip, quietLine, pill } from "./set-ui.js";

const BASIC = "Client reports come with accounts (access.mode: sessions).";
const fmtDay = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const span = (a, b) => `${fmtDay(a)} – ${fmtDay(b)}`;
// The answer drawn last (settings/reports), and the page's reload, for the drawers.
const rs = { r: null, site: "", reload: () => {} };
// What a save says about the confirm links: the helper's `confirm` (client_reports_api.save).
const SAVED = {
  asked: "Saved. A confirm link was mailed to each recipient who has not confirmed; the report goes to confirmed recipients only.",
  no_mail: "Saved. No confirm link was sent: no mail server is set up (Settings > Mail & reports). Set one up, then save the report again.",
  none: "Saved.",
};

function sendRow(x) {
  return h("tr", null, h("td", null, when(x.at)), h("td", null, x.by === "schedule" ? "The schedule" : x.by),
    h("td", null, x.first ? span(x.first, x.last) : "—"), h("td", null, x.recipients.length ? copyIf("text", x.recipients.join(", "), null, { label: "recipients", cls: "" }) : "—"),
    h("td", null, h("span", { class: `tf ${x.ok ? "on" : "off"}` }, x.ok ? "sent" : "not sent"), " ", copyIf("text", x.detail || "", null, { label: "detail" })));
}

function history(sends) {
  if (!sends.length) return h("p", { class: "empty" }, "Not sent yet.");
  return h("div", { class: "scroll" }, h("table", null, h("caption", { class: "vh" }, "Sends of this report"),
    h("thead", null, h("tr", null, ["When", "Started by", "Period", "To", "Outcome"].map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", null, sends.map(sendRow))));
}

/* One report in its drawer (edit=report-<id>): its facts, then Preview, PDF, Send now, History,
   Edit and Delete. A send or a delete says so in a toast and the list is drawn again. */
function item(rep, r, ctx) {
  const s = rep.spec;
  const msg = status();
  const extra = h("div");
  const last = rep.last_send;
  const done = (words, ok, close) => { if (ok) toast(words); else msg.say(words); rs.reload(); if (ok && close) ctx.close(); };
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
      done(got.ok ? `Sent: ${got.words}.` : why(got), !!got.ok, false);
    }, () => {})),
    btn("History", async () => {
      const got = await call(`settings/report-log?id=${rep.id}`);
      extra.replaceChildren(got.ok ? history(got.sends) : h("p", { class: "note" }, why(got)));
    }),
    btn("Edit", () => { ctx.close(); openEdit(`reportedit-${rep.id}`, { site: rs.site }); }),
    btn("Delete", (b) => confirmIn(b.parentElement, `Delete "${s.name}" and its history?`, "Delete", async () => {
      const got = await call("settings/report-delete", { id: rep.id });
      done(got.ok ? `Deleted "${s.name}".` : why(got), !!got.ok, true);
    }, () => {}), "btn danger"));
  const who = [`${rep.confirmed.length} confirmed`, rep.waiting.length ? `${rep.waiting.length} waiting for the confirm link (${rep.waiting.join(", ")})` : null].filter(Boolean).join(", ");
  const [kind, word] = stateOf(rep);
  return h("article", { class: "rp-item" },
    h("p", null, pill(kind, word)),
    h("dl", { class: "rp-facts" },
      h("dt", null, "When"), h("dd", null, `${scheduleWords(s.schedule)} (${r.timezone})`),
      h("dt", null, "Next"), h("dd", null, rep.next ? `${when(rep.next)}, covering ${span(rep.next_first, rep.next_last)}` : "Not scheduled (paused)"),
      h("dt", null, "Period"), h("dd", null, r.periods[s.period]),
      h("dt", null, "Sections"), h("dd", null, s.sections.map((k) => r.section_words[k]).join(", ")),
      h("dt", null, "Recipients"), h("dd", null, who),
      h("dt", null, "Last send"), h("dd", null, last ? [pill(last.ok ? "good" : "bad", last.ok ? "Sent" : "Not sent"), ` ${when(last.at)}: ${last.detail}`] : "Not sent yet")),
    acts, msg, extra);
}

/* A report's pill: paused, its last send failed, recipients still to confirm, or on schedule. */
function stateOf(rep) {
  if (rep.spec.paused) return ["off", "Paused"];
  if (rep.last_send && !rep.last_send.ok) return ["bad", "Last send failed"];
  if (!rep.confirmed.length) return ["warn", "No one confirmed yet"];
  return ["good", "On schedule"];
}

/* A report's row: its name, when it goes next, its pill; it opens its drawer. */
function reportRow(rep, r) {
  const [kind, word] = stateOf(rep);
  const next = rep.next ? `next ${when(rep.next)}` : "not scheduled";
  return statusRow({ iconName: "", title: rep.spec.name, line: `${scheduleWords(rep.spec.schedule)} · ${next} · ${rep.confirmed.length} confirmed`, kind, word,
    label: `${rep.spec.name}: ${word}. Open it`, onOpen: () => openEdit(`report-${rep.id}`, { site: rs.site }) });
}

// Agency branding: the organisation's name and colour (settings/save, org rows) and logo.
function brandCard(r, ctx) {
  const redraw = () => { rs.reload(); };
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
    toast("Saved.");
    redraw();
    ctx.close();
  });
  const file = h("input", { type: "file", accept: ".png,.jpg,.jpeg,image/png,image/jpeg" });
  file.addEventListener("change", () => {
    const f = file.files?.[0];
    if (!f) return;
    if (f.size > 256 * 1024) { msg.say("The logo is a PNG or JPEG of at most 256 KB."); return; }
    const rd = new FileReader();
    rd.onload = async () => {
      const got = await call("settings/agency-logo", { data: String(rd.result).split(",")[1] || "" });
      if (got.ok) { toast("Logo saved."); redraw(); ctx.close(); } else msg.say(why(got));
    };
    rd.readAsDataURL(f);
  });
  const remove = h("button", { type: "button", class: "btn", disabled: !b.logo }, "Remove the logo");
  remove.addEventListener("click", async () => { const got = await call("settings/agency-logo", { data: null }); if (got.ok) { toast("Logo removed."); redraw(); ctx.close(); } else msg.say(why(got)); });
  return h("div", { class: "acct-card set-form" },
    h("p", { class: "set-edit-sub" }, `For every report of ${r.org}. The site's own logo (Settings > Site) sits on the left of each report; yours on the right.`),
    form, h("div", { class: "rp-logo" }, b.logo ? h("img", { src: `settings/agency-logo?v=${Date.now()}`, alt: "The agency logo", height: "40" }) : h("p", { class: "empty" }, "No logo yet: the agency's name is shown instead."),
      field("Agency logo (PNG or JPEG, at most 256 KB)", file), remove), msg);
}

/* The branding as rows: the name, the colour, the logo; each opens the drawer. */
function brandRows(r, m) {
  const b = r.branding;
  const open = () => openEdit("branding", m);
  return rowsCard("Agency branding", [
    statusRow({ iconName: "", title: "Agency name", line: b.agency_name || "Not set: the site's name is shown", label: "Change the agency name", onOpen: open }),
    statusRow({ iconName: "", title: "Brand colour", line: b.color || "Skald's ink", label: "Change the brand colour", onOpen: open }),
    statusRow({ iconName: "", title: "Agency logo", line: "On the right of each report", kind: b.logo ? "good" : "off", word: b.logo ? "Set" : "Not set", label: "Change the agency logo", onOpen: open }),
  ], { help: help("Agency branding", { text: `For every report of ${r.org}: the name in each report's header and as the mail's From name, the colour of the band on top, and the logo. The site's own logo (Settings > Site) sits on the left of each report; yours on the right.` }) });
}

/* The answer for a drawer opened from a link: the page may not have loaded it yet. */
async function answer() {
  if (rs.r) return rs.r;
  const r = await call("settings/reports");
  if (r.ok) rs.r = r;
  return r;
}
const mayReport = () => sessions() && !DEMO.on && (["owner", "admin"].includes(ME.role) || ME.install_admin);
const why0 = () => (!sessions() ? BASIC : DEMO.on ? DEMO_SAYS : "Only an admin or an owner sets up client reports.");
const after = (ctx) => (saved, confirm) => { if (saved) toast(SAVED[confirm] || SAVED.none); rs.reload(); ctx.close(); };
editPart("report-new", { title: "New report", size: "lg", body: async (m, s, ctx) => {
  if (!mayReport()) return why0();
  const r = await answer();
  return r.ok ? [reportForm(r, null, after(ctx))] : why(r, "The reports could not be loaded.");
} });
editPart("reportedit-", { prefix: true, title: "Edit the report", size: "lg", body: async (m, s, ctx, id) => {
  if (!mayReport()) return why0();
  const r = await answer();
  const rep = r.ok && r.reports.find((x) => `reportedit-${x.id}` === id);
  return rep ? [reportForm(r, rep, after(ctx))] : "That report is no longer kept.";
} });
editPart("report-", { prefix: true, title: (m, id) => rs.r?.reports.find((x) => `report-${x.id}` === id)?.spec.name || "Report", size: "lg", body: async (m, s, ctx, id) => {
  if (!mayReport()) return why0();
  const r = await answer();
  const rep = r.ok && r.reports.find((x) => `report-${x.id}` === id);
  return rep ? [item(rep, r, ctx)] : "That report is no longer kept.";
} });
editPart("branding", { title: "Agency branding", body: async (m, s, ctx) => {
  if (!mayReport()) return why0();
  const r = await answer();
  return r.ok ? [brandCard(r, ctx)] : why(r, "The reports could not be loaded.");
} });

export default function reports(m) {
  const lede = "Branded reports for your clients: a mail with a PDF attached, on a schedule you set.";
  if (!mayReport()) return [head1("Reports", lede), h("div", { class: "state" }, h("div", null, why0()))];
  rs.site = m.site;
  const go = primary("New report", () => openEdit("report-new", m), { iconName: "plus" });
  const box = h("div", { class: "set-cards" }, h("p", { class: "empty" }, "Loading the reports…"));
  rs.reload = () => call("settings/reports").then(draw);
  function draw(r) {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The reports could not be loaded.")))); return; }
    rs.r = r;
    const q = help(`Reports for ${m.site}`, { text: "Figures come from verified days only: a day that did not reconcile is listed and left out, never counted as zero." });
    box.replaceChildren(...[
      r.mail_ready ? null : strip("No mail server", "Reports can be made, previewed and downloaded, but not sent until a mail server is set up (the Mail tab).", null, { kind: "warn" }),
      r.reports.length ? rowsCard(`Reports for ${m.site} (${r.reports.length})`, r.reports.map((rep) => reportRow(rep, r)), { help: q })
        : quietLine("No reports yet", "A branded mail with a PDF attached, on a schedule you set."),
      brandRows(r, m)].filter(Boolean));
  }
  rs.reload();
  return [head1("Reports", lede), go, box];
}
