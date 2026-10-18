// Settings › AI answers (accounts, access.mode: sessions): the site's own lists (the
// questions buyers ask, brand terms, competitors, how long answers are kept), which a
// profile uses when it has none of its own, and the tracking profiles: make, edit (a new
// version; earlier runs keep theirs), duplicate, pause, resume, run now and delete. A
// deleted profile leaves the list and its results stay; nothing is erased (the same rule
// as internal traffic). The keys are in Settings › Integrations. GET/POST
// <page>/ai-answers (answers/api.py). The questions are sent to the providers chosen.

import { h, n } from "../ui.js";
import { call } from "./ipmanager.js";
import { sessions, VIEWER } from "../access.js";
import { head1, field, input, status, confirmIn, why } from "./forms.js";
import { profileEditor, costWords, usd, FREQ } from "./ai-answers-edit.js";
import { profileLabel } from "./ai-answers-parts.js";

let editing = null;      // a profile id, "new", or null

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
    done(r, "Saved. Profiles that use the site's lists ask with them from the next run.");
  });
  return h("section", { class: "sheet acct-card" }, h("h2", null, "The site's lists"),
    h("p", { class: "sub" }, "What a profile asks with when it has no list of its own."), form);
}

function profileRow(api, p, done) {
  const ro = !api.editable;
  const paused = p.paused?.length && p.paused.at(-1)[1] == null;
  const e = p.estimate;
  const acts = h("span", { class: "acts" });
  const act = (path, label, words) => h("button", { type: "button", class: "btn", disabled: ro, onclick: async () => {
    const r = await call(`ai-answers/profiles/${path}`, { id: p.id });
    if (r.ok) done(r, words); else done(null, why(r));
  } }, label);
  // replaceChildren writes a null as the text "null": the absent buttons are left out.
  const draw = () => acts.replaceChildren(...[
    h("button", { type: "button", class: "btn", onclick: () => { editing = editing === p.id ? null : p.id; done(api, ""); } }, editing === p.id ? "Close" : ro ? "View" : "Edit"),
    act("duplicate", "Duplicate", "Duplicated."),
    paused ? act("resume", "Resume", "Resumed: it runs again from its next time.") : act("pause", "Pause", "Paused: nothing is asked until you resume it."),
    act("run", "Run now", "Asked: the run starts within 15 minutes."),
    ro ? null : h("button", { type: "button", class: "btn danger", onclick: () => confirmIn(acts, `Delete ${p.name}? Its results stay.`, "Delete",
      async () => { const r = await call("ai-answers/profiles/delete", { id: p.id }); if (r.ok) done(r, "Deleted. Its runs and answers stay until they are older than the days kept."); else done(null, why(r)); }, draw) }, "Delete")].filter(Boolean));
  draw();
  const w = costWords({ answers: e.answers, questions: e.questions, tries: e.tries, assistants: e.assistants, perRun: e.per_run, cap: e.cap, fits: e.fits, days: e.days });
  return h("li", { class: "aa-prow" },
    h("div", null, h("b", null, p.name), " ", profileLabel(p), paused ? h("span", { class: "tag warn" }, "Paused") : h("span", { class: "tag good" }, "Active"),
      h("small", null, `${FREQ.find(([k]) => k === p.frequency)?.[1] || p.frequency}, ${p.repeats} tr${p.repeats === 1 ? "y" : "ies"} a question, ${n(p.asks_questions)} questions, daily cap ${usd(p.cap)}. About ${usd(e.per_month)} a month.`),
      h("small", { class: e.fits ? "aa-ok" : "aa-bad" }, w.cap)),
    acts,
    editing === p.id ? profileEditor(api, p, (r) => done(r, "")) : null);
}

export default function aiAnswersSettings() {
  const title = head1("AI answers", "What AI assistants say about this site: the questions, brand terms and competitors, and the tracking profiles that ask them.");
  if (!sessions()) return [title, h("div", { class: "state" }, h("div", null, "AI answers are set up here with accounts. On this server, see docs/AI-ANSWERS.md."))];
  const box = h("div", { class: "set-cards" }, h("p", { class: "empty" }, "Loading..."));
  const msg = status();
  const draw = (r, said) => {
    if (r && !r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "AI answers could not be loaded.")))); return; }
    if (!r) { msg.say(said); return; }
    if (said) msg.say(said, true);
    const done = (got, words) => (got ? draw(got, words) : msg.say(words));
    const keys = r.providers.filter((p) => p.key).map((p) => p.name);
    box.replaceChildren(...[
      r.editable ? null : h("p", { class: "note" }, VIEWER),
      h("div", { class: `state ${keys.length ? "ok" : "warn"}` }, h("div", null, keys.length ? `Keys set: ${keys.join(", ")}. ` : "No assistant has an API key yet. ",
        "An install admin adds them in ", h("a", { href: "#settings/integrations" }, "Settings › Integrations"), ". The questions are sent to the providers you choose; read docs/INTEGRATIONS.md before turning one on.")),
      listsCard(r, done),
      h("section", { class: "sheet acct-card" }, h("h2", null, "Tracking profiles"),
        h("p", { class: "sub" }, "Each profile asks from its own place and language, as often as you choose, under its own daily cap. At most 10."),
        r.profiles.length ? h("ul", { class: "aa-plist" }, r.profiles.map((p) => profileRow(r, p, done))) : h("p", { class: "empty" }, "No profile yet."),
        r.editable ? h("button", { type: "button", class: "btn", onclick: () => { editing = editing === "new" ? null : "new"; draw(r, ""); } }, editing === "new" ? "Close" : "New profile") : null,
        editing === "new" ? profileEditor(r, {}, (got) => { editing = null; draw(got, "Profile made."); }) : null),
      msg].filter(Boolean));
  };
  call("ai-answers").then((r) => draw(r, ""));
  return [title, box];
}
