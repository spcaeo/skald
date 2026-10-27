// Settings › AI answers (accounts, access.mode: sessions): the site's own lists (the
// questions buyers ask, brand terms, competitors, how long answers are kept), which a
// profile uses when it has none of its own, and the tracking profiles: make, edit (a new
// version; earlier runs keep theirs), duplicate, pause, resume, run now and delete. A
// deleted profile leaves the list and its results stay; nothing is erased (the same rule
// as internal traffic). The keys are in Settings › AI answers › API keys. GET/POST
// <page>/ai-answers (answers/api.py). The questions are sent to the providers chosen.
//
// v2 (Settings v2): the lists and the profiles are rows (a profile's pill: Active, Paused,
// Over its cap); "New profile" is the page's one button. The lists' form, a profile (its
// actions and its form) and a new profile open in a drawer, in the address: edit=ailists,
// profile-<id>, profile-new (set-edit.js).

import { h, n, toast } from "../ui.js";
import * as S from "../state.js";
import { call } from "./ipmanager.js";
import { sessions, isViewer, VIEWER } from "../access.js";
import { head1, field, input, status, confirmIn, why } from "./forms.js";
import { profileEditor, costWords, usd, FREQ } from "./ai-answers-edit.js";
import { profileLabel } from "./ai-answers-parts.js";
import { editPart, openEdit } from "./set-edit.js";
import { primary, rowsCard, statusRow, help, strip, quietLine, pill } from "./set-ui.js";

// The answer drawn last (GET ai-answers), and the page's reload, for the drawers.
const st = { r: null, reload: () => {} };
const BASIC = "AI answers are set up here with accounts. On this server, see docs/AI-ANSWERS.md.";
async function answer() {
  if (st.r) return st.r;
  const r = await call("ai-answers");
  if (r.ok) st.r = r;
  return r;
}
/* A change saved in a drawer: a toast, the page drawn again, the drawer closed. */
const after = (ctx, words) => (got) => { if (got) st.r = got; if (words) toast(words); st.reload(); ctx.close(); };

function listsCard(api, done) {
  const ro = !api.editable;
  const l = api.lists;
  const area = (value, rows, ph) => h("textarea", { rows: String(rows), spellcheck: "false", disabled: ro, placeholder: ph }, (value || []).join("\n"));
  const qs = area(l.questions, 6, "What is the best web analytics tool that works from server logs?");
  const brands = area(l.brands, 3, "Example Analytics\nexample.com");
  const comps = area(l.competitors, 3, "Northwind Analytics\nnorthwind.example");
  const keep = input({ type: "number", min: "30", max: "3650", value: l.keep_days, disabled: ro });
  const msg = status();
  const save = h("button", { type: "submit", class: "btn primary", disabled: ro }, "Save");
  const lines = (el) => el.value.split("\n").map((x) => x.trim()).filter(Boolean);
  const form = h("form", { class: "af-col", novalidate: true },
    field("Questions buyers ask (one per line, at most 50)", qs, "Asked as written, in each profile's language. Write them as a customer would."),
    field("Brand terms (one per line)", brands, "A brand is named when one of these appears as a whole word. A term written as a domain also marks the site's own citations."),
    field("Competitors (one per line)", comps, "Names, or domains: a domain also counts when an answer cites it."),
    field("Days answers are kept", keep, "30 to 3650. Older runs, their answers and figures are removed by the next run."),
    h("div", null, save), msg);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    save.disabled = true;
    const r = await call("ai-answers/lists", { questions: lines(qs), brands: lines(brands), competitors: lines(comps), keep_days: Number(keep.value) || null });
    save.disabled = false;
    if (!r.ok) { msg.say(why(r)); return; }
    done(r);
  });
  return h("div", { class: "acct-card set-form" }, h("p", { class: "set-edit-sub" }, "What a profile asks with when it has no list of its own."), form);
}

const pausedOf = (p) => !!(p.paused?.length && p.paused.at(-1)[1] == null);
const pillOf = (p) => (pausedOf(p) ? ["off", "Paused"] : p.estimate?.fits === false ? ["warn", "Over its cap"] : ["good", "Active"]);
const factsOf = (p) => `${FREQ.find(([k]) => k === p.frequency)?.[1] || p.frequency}, ${p.repeats} tr${p.repeats === 1 ? "y" : "ies"} a question, ${n(p.asks_questions)} questions, daily cap ${usd(p.cap)}. About ${usd(p.estimate?.per_month)} a month.`;

/* One profile in its drawer (edit=profile-<id>): its facts, Duplicate, Pause or Resume, Run
   now, Delete, then its form (a new version; earlier runs keep theirs). */
function profileBody(api, p, ctx) {
  const ro = !api.editable;
  const e = p.estimate;
  const msg = status();
  const acts = h("div", { class: "acts" });
  const act = (path, label, words) => h("button", { type: "button", class: "btn", disabled: ro, onclick: async () => {
    const r = await call(`ai-answers/profiles/${path}`, { id: p.id });
    if (r.ok) after(ctx, words)(r); else msg.say(why(r));
  } }, label);
  const draw = () => acts.replaceChildren(...[
    act("duplicate", "Duplicate", "Duplicated."),
    pausedOf(p) ? act("resume", "Resume", "Resumed: it runs again from its next time.") : act("pause", "Pause", "Paused: nothing is asked until you resume it."),
    act("run", "Run now", "Asked: the run starts within 15 minutes."),
    ro ? null : h("button", { type: "button", class: "btn danger", onclick: () => confirmIn(acts, `Delete ${p.name}? Its results stay.`, "Delete",
      async () => { const r = await call("ai-answers/profiles/delete", { id: p.id }); if (r.ok) after(ctx, "Deleted. Its runs and answers stay until they are older than the days kept.")(r); else msg.say(why(r)); }, draw) }, "Delete")].filter(Boolean));
  draw();
  const w = costWords({ answers: e.answers, questions: e.questions, tries: e.tries, assistants: e.assistants, perRun: e.per_run, cap: e.cap, fits: e.fits, days: e.days });
  const [kind, word] = pillOf(p);
  return [h("div", { class: "aa-prow" }, h("p", null, profileLabel(p), " ", pill(kind, word)), h("p", { class: "set-edit-sub" }, factsOf(p)),
    h("p", { class: e.fits ? "aa-ok" : "aa-bad" }, w.cap)), acts, msg,
    h("section", { class: "set-sec" }, h("h3", null, ro ? "Its settings" : "Change it"), profileEditor(api, p, after(ctx, "Saved: a new version; earlier runs keep theirs.")))];
}

editPart("ailists", { title: "The site's lists", body: async (m, s, ctx) => {
  if (!sessions()) return BASIC;
  const r = await answer();
  return r.ok ? [listsCard(r, after(ctx, "Saved. Profiles that use the site's lists ask with them from the next run."))] : why(r, "AI answers could not be loaded.");
} });
editPart("profile-new", { title: "New profile", size: "lg", body: async (m, s, ctx) => {
  if (!sessions()) return BASIC;
  const r = await answer();
  if (!r.ok) return why(r, "AI answers could not be loaded.");
  return r.editable ? [profileEditor(r, {}, after(ctx, "Profile made."))] : VIEWER;
} });
editPart("profile-", { prefix: true, size: "lg", title: (m, id) => st.r?.profiles.find((p) => `profile-${p.id}` === id)?.name || "Profile", body: async (m, s, ctx, id) => {
  if (!sessions()) return BASIC;
  const r = await answer();
  const p = r.ok && r.profiles.find((x) => `profile-${x.id}` === id);
  return p ? profileBody(r, p, ctx) : "That profile is no longer kept.";
} });

/* The site's lists as rows: how many of each, the first ones; each opens the lists' drawer. */
function listRows(r, m) {
  const l = r.lists;
  const open = () => openEdit("ailists", m);
  const some = (v, none) => (v?.length ? v.slice(0, 3).join(", ") + (v.length > 3 ? `, and ${v.length - 3} more` : "") : none);
  return rowsCard("The site's lists", [
    statusRow({ iconName: "", title: `Questions buyers ask (${(l.questions || []).length})`, line: some(l.questions, "Add the questions a buyer would ask an assistant"), kind: l.questions?.length ? "" : "warn", word: l.questions?.length ? "" : "None yet", label: "Change the questions", onOpen: open }),
    statusRow({ iconName: "", title: "Brand terms", line: some(l.brands, "None yet"), label: "Change the brand terms", onOpen: open }),
    statusRow({ iconName: "", title: "Competitors", line: some(l.competitors, "None yet"), label: "Change the competitors", onOpen: open }),
    statusRow({ iconName: "", title: "Days answers are kept", line: `${l.keep_days} days`, label: "Change the days kept", onOpen: open }),
  ], { help: help("The site's lists", { text: "What a profile asks with when it has no list of its own. Questions are asked as written, in each profile's language. A brand is named when one of its terms appears as a whole word; a competitor's domain also counts when an answer cites it." }) });
}

function profileRow(p, m) {
  const [kind, word] = pillOf(p);
  return statusRow({ iconName: "", title: p.name, line: factsOf(p), kind, word, label: `${p.name}: ${word}. Open it`, onOpen: () => openEdit(`profile-${p.id}`, m) });
}

export default function aiAnswersSettings(m) {
  const title = head1("AI answers", "What AI assistants say about this site: the questions, brand terms and competitors, and the tracking profiles that ask them.");
  if (!sessions()) return [title, h("div", { class: "state" }, h("div", null, BASIC))];
  const box = h("div", { class: "set-cards" }, h("p", { class: "empty" }, "Loading..."));
  const draw = (r) => {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "AI answers could not be loaded.")))); return; }
    st.r = r;
    const keys = r.providers.filter((p) => p.key).map((p) => p.name);
    box.replaceChildren(...[
      r.editable ? null : h("p", { class: "note" }, VIEWER),
      keys.length ? null : strip("No API key", "No assistant has an API key yet: an install admin adds them under API keys. The questions are sent to the providers you choose.", () => S.set({ sub: "keys" }), { kind: "warn" }),
      listRows(r, m),
      r.profiles.length ? rowsCard(`Tracking profiles (${r.profiles.length})`, r.profiles.map((p) => profileRow(p, m)),
        { help: help("Tracking profiles", { text: `Each profile asks from its own place and language, as often as you choose, under its own daily cap. At most 10.${keys.length ? ` Keys set: ${keys.join(", ")}.` : ""}` }) })
        : quietLine("No profile yet", "A profile asks the questions from one place and language, as often as you choose."),
    ].filter(Boolean));
  };
  st.reload = () => call("ai-answers").then(draw);
  st.reload();
  // The one button, drawn at once (the frame puts it by the title); a viewer has none.
  const go = isViewer() ? null : primary("New profile", () => openEdit("profile-new", m), { iconName: "plus" });
  return [title, go, box];
}
