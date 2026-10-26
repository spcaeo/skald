// Settings > Mail & reports > Client reports: one client report's settings (client_reports.py): name,
// recipients, when it goes (weekly on a weekday, monthly on a day, or every N
// days from a date, at a time in the site's zone), the period, the sections,
// notes and footer. Save, or look first: Preview draws the mail in a sandboxed
// frame and PDF downloads the attachment, both from the unsaved settings and
// the verified history, sending nothing.

import { h } from "../ui.js";
import { call, csrfHeaders } from "./ipmanager.js";
import { field, input, status, why } from "./forms.js";
import { DEMO, DEMO_SAYS } from "../demo.js";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const today = () => new Date().toISOString().slice(0, 10);

export function scheduleWords(s) {
  const at = ` at ${s.at}`;
  if (s.kind === "weekly") return `Every ${WEEKDAYS[s.weekday]}${at}`;
  if (s.kind === "monthly") return `Monthly on day ${s.day}${s.day > 28 ? " (or the month's last day)" : ""}${at}`;
  return `Every ${s.every} day${s.every === 1 ? "" : "s"} from ${s.start}${at}`;
}

const select = (attrs, options, value) => h("select", attrs, options.map(([v, t]) => h("option", { value: v, selected: String(v) === String(value) }, t)));

// The preview: the subject, the days the figures leave out, and the mail in a frame
// that runs nothing (srcdoc in a sandbox with no permissions).
export function previewBox() {
  const subject = h("p", { class: "mp-subject" });
  const notes = h("ul", { class: "rp-cover" });
  const frame = h("iframe", { class: "mp-frame", title: "The report as it would be mailed", sandbox: "", referrerpolicy: "no-referrer" });
  const box = h("div", { class: "rp-preview", hidden: true }, subject, notes, frame);
  box.show = (r) => {
    subject.replaceChildren(h("b", null, "Subject: "), r.subject);
    notes.replaceChildren(...(r.coverage || []).map((l) => h("li", null, l)),
      ...(r.waiting?.length ? [h("li", null, `Not confirmed yet, so not mailed: ${r.waiting.join(", ")}.`)] : []));
    frame.srcdoc = r.html;
    box.hidden = false;
  };
  return box;
}

// POST settings/report-pdf and save the file it answers.
export async function downloadPdf(body, msg) {
  if (DEMO.on) { msg.say(DEMO_SAYS); return; }
  msg.textContent = "Making the PDF…"; msg.className = "msg";
  let res;
  try {
    res = await fetch("settings/report-pdf", { method: "POST", credentials: "same-origin", cache: "no-store", headers: { "Content-Type": "application/json", ...csrfHeaders() }, body: JSON.stringify(body) });
  } catch { msg.say("The server could not be reached."); return; }
  if (!res.ok || res.headers.get("Content-Type") !== "application/pdf") {
    let r = {};
    try { r = await res.json(); } catch { /* not JSON */ }
    msg.say(why({ ok: false, ...r }, `The PDF could not be made (${res.status}).`));
    return;
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "report.pdf";
  const url = URL.createObjectURL(await res.blob());
  const a = h("a", { href: url, download: name, hidden: true });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  msg.say(`Downloaded ${name}.`, true);
}

// The form. `r`: GET settings/reports' answer; `report`: the one edited, or null for a new one.
export function reportForm(r, report, done) {
  const s = report?.spec || { name: "", recipients: [], schedule: { kind: "monthly", day: 1, at: "08:00" }, period: "last_month", sections: ["summary", "sources", "pages", "places", "ai", "leads", ...(r.search_console ? ["search_console"] : []), "notes"], notes: "", footer: "", agency_logo: true, paused: false };
  const sc = s.schedule;
  const name = input({ value: s.name, maxlength: "80", required: true, placeholder: "Monthly traffic report" });
  const recipients = h("textarea", { rows: "3", spellcheck: "false", placeholder: "client@example.com" }, (s.recipients || []).join("\n"));
  const kind = select({}, [["weekly", "Weekly"], ["monthly", "Monthly"], ["custom", "Every few days"]], sc.kind);
  const weekday = select({ "aria-label": "Weekday" }, WEEKDAYS.map((d, i) => [i, d]), sc.weekday ?? 0);
  const day = input({ type: "number", min: "1", max: "31", value: sc.day ?? 1, inputmode: "numeric", "aria-label": "Day of the month" });
  const every = input({ type: "number", min: "1", max: "92", value: sc.every ?? 14, inputmode: "numeric", "aria-label": "Every how many days" });
  const start = input({ type: "date", value: sc.start || today(), "aria-label": "Starting on" });
  const at = input({ type: "time", value: sc.at || "08:00", "aria-label": "At" });
  const parts = { weekly: field("On", weekday), monthly: field("On day", day, "A shorter month: its last day."), custom: h("div", { class: "rp-two" }, field("Every … days", every), field("Starting on", start)) };
  const whenRow = h("div", { class: "rp-when" }, field("Goes", kind), ...Object.values(parts), field(`At (${r.timezone})`, at));
  const showKind = () => Object.entries(parts).forEach(([k, el]) => { el.hidden = k !== kind.value; });
  kind.addEventListener("change", showKind);
  showKind();
  const period = select({}, Object.entries(r.periods), s.period);
  const boxes = r.sections.map((k) => {
    const off = k === "search_console" && !r.search_console;
    const el = h("input", { type: "checkbox", value: k, checked: !off && s.sections.includes(k), disabled: off });
    return h("label", { class: "chk" }, el, h("span", null, h("b", null, r.section_words[k]), off ? h("small", null, "Not connected for this site: Settings > Leads & integrations > Search Console & Bing") : null));
  });
  const notes = h("textarea", { rows: "4", maxlength: "2000", placeholder: "What we did this month, and what comes next." }, s.notes || "");
  const footer = input({ value: s.footer || "", maxlength: "160", placeholder: "Example Agency · hello@example.com" });
  const logo = h("input", { type: "checkbox", checked: s.agency_logo !== false });
  const paused = h("input", { type: "checkbox", checked: !!s.paused });
  const body = () => ({
    name: name.value.trim(), recipients: recipients.value.split(/[\s,;]+/).filter(Boolean),
    schedule: { kind: kind.value, at: at.value || "08:00", weekday: Number(weekday.value), day: Number(day.value), every: Number(every.value), start: start.value },
    period: period.value, sections: boxes.map((b) => b.querySelector("input")).filter((c) => c.checked).map((c) => c.value),
    notes: notes.value, footer: footer.value.trim(), agency_logo: logo.checked, paused: paused.checked,
  });
  const msg = status();
  const preview = previewBox();
  const save = h("button", { type: "submit", class: "btn primary" }, report ? "Save" : "Create the report");
  const look = h("button", { type: "button", class: "btn" }, "Preview");
  const pdf = h("button", { type: "button", class: "btn" }, "Download PDF");
  const cancel = h("button", { type: "button", class: "btn" }, "Cancel");
  look.addEventListener("click", async () => {
    look.disabled = true; msg.textContent = "Building the report…"; msg.className = "msg";
    const got = await call("settings/report-preview", body());
    look.disabled = false;
    if (!got.ok) { msg.say(why(got, "The preview could not be built.")); return; }
    msg.say(""); preview.show(got);
  });
  pdf.addEventListener("click", () => downloadPdf(body(), msg));
  cancel.addEventListener("click", () => done(null));
  const form = h("form", { class: "af-col rp-form", novalidate: true },
    field("Name", name, "What the client sees on top."),
    field("Recipients", recipients, "One address per line. Each one gets a confirm link first and nothing else until they confirm."),
    whenRow, field("Period", period, "Last week runs Monday to Sunday. Month to date on the 1st is the whole month before."),
    h("fieldset", { class: "af-set" }, h("legend", null, "Sections"), boxes),
    field("Notes", notes, "Your own words, shown as typed. Leave empty to leave the section out."),
    field("Footer", footer, "One line at the foot of every page."),
    h("label", { class: "chk" }, logo, h("span", null, h("b", null, "Show the agency logo"))),
    h("label", { class: "chk" }, paused, h("span", null, h("b", null, "Paused"), h("small", null, "Kept, but not sent on its schedule."))),
    h("div", { class: "mp-row" }, save, look, pdf, cancel));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    save.disabled = true;
    const got = await call("settings/report-save", { ...(report ? { id: report.id } : {}), ...body() });
    save.disabled = false;
    if (!got.ok) { msg.say(why(got)); return; }
    done(got.report, got.confirm);
  });
  return h("section", { class: "sheet acct-card" }, h("h2", null, report ? `Edit: ${s.name}` : "New report"), form, msg, preview);
}
