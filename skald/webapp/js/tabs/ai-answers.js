// AI & bots › AI answers: what ChatGPT, Perplexity, Gemini and Claude SAY when asked the
// questions buyers ask, asked through their APIs on a schedule as if from each tracking
// profile's place and language (answers/, ai_answers.json), joined with what Skald alone
// sees: what the assistant then READ (its user fetcher in the log) and SENT (visits, leads).
//
// On top, always: "a sample of API answers, not what every user sees". Then the profiles
// (ap in the address), and two columns: the chain, how often each assistant names the site
// per run, the profile × assistant matrix for one question (aq) in "x of N tries", the
// questions of the profile's last run, the competitors; beside them the profile's
// settings with the cost estimate and the daily cap (ai-answers-edit.js, sessions mode).
// Only figures the second count verified are in the file; a withheld run says so.

import { h, long, short } from "../ui.js";
import { opened as routeOpened, closed as routeClosed } from "../overlays.js";
import * as S from "../state.js";
import { figures } from "../data.js";
import { sessions } from "../access.js";
import { head, notBuiltNote } from "./common.js";
import { call } from "./ipmanager.js";
import { why } from "./forms.js";
import { stamp } from "../tz.js";
import { profileEditor, estimate, costWords, usd, FREQ } from "./ai-answers-edit.js";
import { chainCard, sovChart, matrix, questionsTable, competitorsTable, profileLabel, profileText } from "./ai-answers-parts.js";
import { withUrl } from "../urlactions.js";

const LEDE = "What ChatGPT, Perplexity, Gemini and Claude say when asked the questions your buyers ask. Skald asks each one through its API on a schedule, as if from the place and language of a profile, and reads every answer.";
const SAMPLE = [h("b", null, "A sample of API answers, not what every user sees. "),
  "Each provider answers people differently by account, history, place and wording, and its API can differ from its app. Read these figures as a direction over weeks, never as a count of people. Every answer is kept, so you can read what was said."];

let api = null;          // GET ai-answers (sessions mode): the editable settings
let asked = false;
let chainAt = 0;
let fresh = null;        // a profile list newer than the data file, after a save

const at = (iso) => (!iso ? "" : iso.length <= 10 ? long(iso) : stamp(iso));

// One stored answer in full, in a dialog headed by its assistant (ChatGPT, not openai): the
// question as sent, the text, the cited URLs.
// In the address as ans=<id> while it is open (js/overlays.js): a link opens it again.
export async function openAnswer(id, provName = (x) => x) {
  const box = h("dialog", { class: "aa-dlg", "aria-label": "Full answer" });
  const close = h("button", { type: "button", class: "btn", onclick: () => box.close() }, "Close");
  box.addEventListener("close", () => { box.remove(); routeClosed("ans", String(id)); });
  box.append(h("p", { class: "empty" }, "Loading the answer..."), close);
  document.body.append(box);
  box.showModal();
  routeOpened("ans", String(id), { close: () => box.close(), isOpen: () => box.isConnected });
  const r = await call(`ai-answers/answer?id=${encodeURIComponent(id)}`);
  if (!r.ok) { box.replaceChildren(h("p", { class: "msg err" }, why(r, "Full answers open with accounts (sessions mode).")), close); return; }
  const a = r.answer;
  box.replaceChildren(h("h2", null, `${provName(a.provider)} · ${a.model}`),
    h("p", { class: "sub" }, `Try ${a.try}, asked ${at(a.asked_at)}. One try, kept as the API answered.`),
    h("p", { class: "aa-asked" }, h("b", null, "Asked: "), a.sent || a.question),
    h("div", { class: "aa-text" }, a.text || `No answer: ${a.error}`),
    a.citations.length ? h("ol", { class: "aa-cites" }, a.citations.map((c) => h("li", null,
      withUrl(h("a", { href: c.url, target: "_blank", rel: "noopener noreferrer nofollow" }, c.title || c.url), c.url, { label: c.title || c.url, cls: "ua-after" }), c.domain ? ` (${c.domain}, page not known)` : ""))) : h("p", { class: "muted" }, "It cited no URL."),
    h("div", { class: "acts" }, close));
}

function setupCard(x) {
  return h("section", { class: "s aa-card" }, h("h2", null, "Set up AI answers"),
    h("p", { class: "sub" }, "Four steps. Nothing is asked, and nothing costs, until a key and a profile exist. The questions are sent to the providers you choose."),
    h("ol", { class: "aa-steps" }, x.setup.steps.map((st) => h("li", { class: st.done ? "done" : null },
      h("span", { class: "tick", "aria-hidden": "true" }, st.done ? "✓" : ""), h("span", null, st.words, st.done ? h("span", { class: "vh" }, " Done.") : null)))));
}

// The aside: the profile's settings (sessions mode), else what the file says.
function aside(m, x, prof, redraw) {
  const box = h("aside", { class: "aa-aside", "aria-labelledby": "aa-set-h" },
    h("div", { class: "aa-row" }, h("h2", { id: "aa-set-h" }, prof ? "Profile settings" : "New profile"), prof ? h("span", { class: "muted" }, profileText(prof)) : null));
  if (!sessions()) {
    if (!prof) return null;
    const e = estimate(prof, prof.asks?.questions?.length || 0, x.providers);
    const w = costWords(e);
    box.append(h("p", { class: "note" }, "Profiles are changed here with accounts; on this server, with the API on the server (docs/AI-ANSWERS.md)."),
      h("dl", { class: "aa-dl" }, h("dt", null, "How often"), h("dd", null, FREQ.find(([k]) => k === prof.frequency)?.[1] || prof.frequency),
        h("dt", null, "Tries per question"), h("dd", null, String(prof.repeats)), h("dt", null, "Daily cap"), h("dd", null, usd(prof.cap)),
        h("dt", null, "Estimated cost"), h("dd", null, `${usd(e.month)} a month`)), h("small", null, w.line), h("small", null, w.cap));
    return box;
  }
  if (!api) {
    box.append(h("p", { class: "empty" }, "Loading the settings..."));
    if (!asked) { asked = true; call("ai-answers").then((r) => { api = r.ok ? r : { ok: false, error: why(r) }; redraw(); }); }
    return box;
  }
  if (!api.ok) { box.append(h("p", { class: "msg err" }, api.error)); return box; }
  const p = prof ? (api.profiles || []).find((q) => q.id === prof.id) || prof : {};
  box.append(profileEditor(api, p, (r) => { api = r; fresh = r.profiles; if (!prof && r.profiles?.length) S.set({ ap: String(r.profiles.at(-1).id) }, { replace: true }); else redraw(); }));
  return box;
}

export default function aiAnswers(m, s) {
  const x = m.x.ai_answers;
  const { r } = figures(m, s);
  const profs = fresh && x ? fresh.map((p) => ({ ...(x.profiles.find((q) => q.id === p.id) || {}), ...p })) : x?.profiles || [];
  const prof = s.ap === "new" ? null : profs.find((p) => String(p.id) === s.ap) || profs[0] || null;
  const period = prof ? [prof.last_run ? `Last run ${at(prof.last_run.finished_at ? prof.last_run.finished_at : prof.last_run.day)}.` : "No run yet.",
    prof.state === "paused" ? " Paused." : prof.next_run ? ` Next run ${at(prof.next_run)}.` : ""].join("") : "Not set up";
  // The tab keeps its own period (the chip in the bar says so); the header says it in the same words as Alerts and Insights.
  const said = `${period.replace(/\.$/, "")} · the date range above does not apply`;
  const out = [...head("AI answers", r, LEDE, { banner: false, period: said })];
  out.push(notBuiltNote(m, "ai_answers", "AI answers"));
  if (!x) return [...out, h("div", { class: "state" }, h("div", null, "AI answers come with this server's next release: the file ai_answers.json is not written yet."))];
  out.push(h("div", { class: "state aa-sample", role: "note" }, h("div", null, ...SAMPLE)));
  const redraw = () => S.emit(true);
  const provName = (id) => x.providers.find((p) => p.id === id)?.name || id;

  // The profiles, as chips; "New profile" for admins.
  const chips = h("div", { class: "aa-profiles", role: "group", "aria-label": "Tracking profiles" }, h("span", { class: "aa-lab" }, "Tracking profiles"),
    profs.map((p) => h("button", { type: "button", class: "aa-pchip", "aria-pressed": String(prof?.id === p.id), onclick: () => S.set({ ap: String(p.id), aq: "" }, { replace: true }) },
      profileLabel(p), p.state === "paused" ? h("small", null, " paused") : null)),
    sessions() ? h("button", { type: "button", class: "aa-pchip new", "aria-pressed": String(s.ap === "new"), onclick: () => S.set({ ap: "new" }, { replace: true }) }, "+ New profile") : null);
  // No profile and nothing to make one with (a viewer, or no accounts): the setup card says how.
  if (profs.length || sessions()) out.push(chips);

  const left = h("div", { class: "aa-main" });
  if (x.state !== "ok") left.append(setupCard(x));
  if (x.chain.length) chainAt = Math.min(chainAt, x.chain.length - 1);
  left.append(chainCard(x, [...x.chain.slice(chainAt), ...x.chain.slice(0, chainAt)], provName, (i) => { chainAt = (chainAt + i) % x.chain.length; redraw(); }));
  if (prof) {
    const runs = x.trend.filter((t) => t.profile === prof.id);
    const last = x.last[String(prof.id)];
    const per = last ? `${last.questions.length} question${last.questions.length === 1 ? "" : "s"}, ${last.repeats} tr${last.repeats === 1 ? "y" : "ies"} each` : "";
    left.append(sovChart(runs, x.providers, `Share of answers that name you, ${profileText(prof)}, ${FREQ.find(([k]) => k === prof.frequency)?.[1].toLowerCase() || ""} runs${per ? `: ${per}` : ""}. Hover or focus a run.`));
    const withheld = runs.filter((t) => t.withheld);
    if (withheld.length) left.append(h("div", { class: "state warn", role: "alert" }, h("div", null, h("b", null, `${withheld.length} run${withheld.length === 1 ? " is" : "s are"} withheld. `), "The second count of their answers did not match the stored figures, so they are not shown. Data quality and the run's log say why.")));
    if (last) {
      const qs = last.questions.map((q) => q.question);
      const q = qs.includes(s.aq) ? s.aq : qs[0];
      const rows = profs.filter((p) => x.last[String(p.id)]).map((p) => {
        const l = x.last[String(p.id)];
        const hit = l.questions.find((qq) => qq.question === q);
        return { profile: p, on: p.id === prof.id, cells: hit ? hit.by : {} };
      });
      left.append(matrix(q, rows, x.providers.filter((p) => rows.some((rw) => rw.cells[p.id])), (p) => S.set({ ap: String(p.id) }, { replace: true })));
      left.append(questionsTable(last, x.providers, profileText(prof), (text) => S.set({ aq: text }, { replace: true }), (id) => openAnswer(id, provName), q));
    } else {
      left.append(h("section", { class: "s aa-card" }, h("h2", null, "Questions"), h("p", { class: "empty" },
        prof.open_run ? `A run started ${short(prof.open_run.day)} is still going (the daily cap, or answers still coming). Its figures appear when every answer is in and checked.` : "No run of this profile is complete and checked yet.")));
    }
    left.append(competitorsTable(x.competitors[String(prof.id)] || [], x.providers, profileText(prof), x.competitor_days));
  }
  out.push(h("div", { class: "aa-cols" }, left, aside(m, x, prof, redraw)));
  return out;
}
