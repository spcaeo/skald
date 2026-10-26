// AI answers: one tracking profile's settings (the aside on AI & bots › AI answers,
// and Settings › AI answers › Profiles). A place (city, region, ISO country, optional
// coordinates and time zone) and a language; its questions (or the site's list); brand
// terms and competitors (or the site's); the assistants to ask, each saying how it is
// told the place (passed in the API's location field, or written into the question);
// how often; tries per question (1-5); the daily spending cap; and the estimated cost
// (questions × tries × assistants with a key × each one's price an answer, × runs a
// month). Saved with POST <page>/ai-answers/profiles/save (answers/api.py); a viewer
// sees it read-only. Nothing secret is here: a key only says set or not.

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { VIEWER } from "../access.js";
import { field, input, status, why } from "./forms.js";

export const FREQ = [["daily", "Daily"], ["weekly", "Weekly"], ["monthly", "Monthly"]];
const PER_MONTH = { daily: 30, weekly: 4.3, monthly: 1 };
const MAX_Q = 50, MAX_TRIES = 5;
export const usd = (v, d = 2) => `$${Number(v || 0).toFixed(d)}`;

/* The estimate, as the server works it out (answers.estimate): only assistants with a key. */
export function estimate(p, questions, providers) {
  const on = providers.filter((x) => (p.providers || []).includes(x.id) && x.key);
  const tries = Number(p.repeats || 1);
  const perRun = on.reduce((a, x) => a + questions * tries * x.price, 0);
  const cap = Number(p.cap || 0);
  return { answers: questions * tries * on.length, questions, tries, assistants: on.length, perRun,
    month: perRun * (PER_MONTH[p.frequency] || 4.3), cap, fits: perRun <= cap + 1e-9, days: cap && perRun > cap ? Math.ceil(perRun / cap - 1e-9) : 1 };
}

export function costWords(e) {
  const line = `${e.answers} answers a run (${e.questions} question${e.questions === 1 ? "" : "s"} × ${e.tries} tr${e.tries === 1 ? "y" : "ies"} × ${e.assistants} assistant${e.assistants === 1 ? "" : "s"}), about ${usd(e.perRun)} a run.`;
  // Say what is missing: the questions, an assistant with a key, or both.
  const need = [!e.questions ? "questions" : null, !e.assistants ? "an assistant with an API key (Settings › AI answers › API keys)" : null].filter(Boolean);
  const cap = !e.answers ? `Nothing to ask yet: add ${need.join(" and ") || "questions"}.`
    : e.fits ? `A run stays under the ${usd(e.cap)} daily cap.`
      : `A run would pass the ${usd(e.cap)} daily cap: Skald stops at the cap and finishes over ${e.days} days.`;
  return { line, cap };
}

// An editable list of short texts as chips, with an Add field.
function chips(label, values, { ro, placeholder, max, hint }) {
  let items = [...values];
  const box = h("div", { class: "aa-chips" });
  const add = input({ placeholder, maxlength: "80", disabled: ro, "aria-label": `Add to ${label.toLowerCase()}` });
  const btn = h("button", { type: "button", class: "btn", disabled: ro }, "Add");
  const draw = () => box.replaceChildren(...items.map((v, i) => h("span", { class: "aa-chip" }, v,
    ro ? null : h("button", { type: "button", class: "x", "aria-label": `Remove ${v}`, onclick: () => { items.splice(i, 1); draw(); } }, "×"))),
  ro ? "" : h("span", { class: "aa-add" }, add, btn));
  const push = () => { const v = add.value.trim(); if (v && items.length < max && !items.some((x) => x.toLowerCase() === v.toLowerCase())) items.push(v); add.value = ""; draw(); add.focus(); };
  btn.addEventListener("click", push);
  add.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); push(); } });
  draw();
  const el = h("div", { class: "aa-fs" }, h("span", { class: "aa-lab" }, label), box, hint ? h("small", { class: "muted" }, hint) : null);
  return { el, get: () => items };
}

// The questions: the site's list, or the profile's own (ordered, at most 50).
function questionBox(p, site, ro, changed) {
  let own = [...(p.questions || [])];
  let useSite = !!p.use_site_questions || (!own.length && site.length > 0 && !p.id);
  const count = h("span", { class: "muted" });
  const list = h("ol", { class: "aa-qs" });
  const add = input({ placeholder: "A question your buyers ask", maxlength: "300", disabled: ro, "aria-label": "Add a question" });
  const btn = h("button", { type: "button", class: "btn", disabled: ro }, "Add a question");
  const pick = h("input", { type: "checkbox", checked: useSite, disabled: ro });
  const draw = () => {
    const shown = useSite ? site : own;
    count.textContent = `${shown.length} of ${MAX_Q}`;
    list.replaceChildren(...shown.map((q, i) => h("li", null, h("span", null, q),
      useSite || ro ? null : h("button", { type: "button", class: "x", "aria-label": `Remove question: ${q}`, onclick: () => { own.splice(i, 1); draw(); } }, "×"))));
    if (!shown.length) list.append(h("li", { class: "muted" }, useSite ? "The site's list is empty: Settings › AI answers." : "No question yet."));
    add.hidden = btn.hidden = useSite || ro;
    changed();
  };
  pick.addEventListener("change", () => { useSite = pick.checked; draw(); });
  const push = () => { const v = add.value.trim(); if (v.length >= 3 && own.length < MAX_Q && !own.includes(v)) own.push(v); add.value = ""; draw(); add.focus(); };
  btn.addEventListener("click", push);
  add.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); push(); } });
  draw();
  const el = h("div", { class: "aa-fs" }, h("div", { class: "aa-row" }, h("span", { class: "aa-lab" }, "Questions"), count), list,
    h("div", { class: "aa-add" }, add, btn),
    h("label", { class: "chk" }, pick, h("span", null, `Use the site's list (${site.length})`)));
  return { el, get: () => ({ use_site_questions: useSite, questions: useSite ? [] : own }), count: () => (useSite ? site.length : own.length) };
}

/* The editor. api: GET ai-answers's answer; p: a profile (or {} for a new one);
   onSaved(answer) after a save or an action. */
export function profileEditor(api, p, onSaved) {
  const ro = !api.editable;
  const msg = status();
  const providers = api.providers || [];
  const lists = api.lists || { questions: [], brands: [], competitors: [] };
  const v = { providers: p.providers || providers.filter((x) => x.key).map((x) => x.id), frequency: p.frequency || "weekly", repeats: p.repeats || 1, cap: p.cap ?? 2 };
  const name = input({ value: p.name || "", maxlength: "60", disabled: ro });
  const city = input({ value: p.city || "", maxlength: "80", disabled: ro, placeholder: "Toronto" });
  const region = input({ value: p.region || "", maxlength: "80", disabled: ro, placeholder: "Ontario" });
  const country = input({ value: p.country || "", maxlength: "2", disabled: ro, placeholder: "CA", class: "aa-cc", autocapitalize: "characters" });
  const lang = input({ value: p.language || "en", maxlength: "20", disabled: ro, placeholder: "en, fr-CA" });
  const lat = input({ value: p.lat ?? "", inputmode: "decimal", disabled: ro, placeholder: "43.65" });
  const lon = input({ value: p.lon ?? "", inputmode: "decimal", disabled: ro, placeholder: "-79.38" });
  const zone = input({ value: p.timezone || "", maxlength: "64", disabled: ro, placeholder: "America/Toronto" });
  let refresh = () => {};
  const qs = questionBox(p, lists.questions || [], ro, () => refresh());
  const brands = chips("Brand terms", p.brands || [], { ro, placeholder: "Your brand or domain", max: 20, hint: p.brands?.length || !lists.brands?.length ? null : `Empty: the site's (${lists.brands.join(", ")}).` });
  const comps = chips("Competitors to watch for", p.competitors || [], { ro, placeholder: "A name or a domain", max: 30, hint: p.competitors?.length || !lists.competitors?.length ? null : `Empty: the site's (${lists.competitors.length}).` });
  const est = h("div", { class: "aa-est", "aria-live": "polite" });
  refresh = () => {
    const e = estimate({ ...v }, qs.count(), providers);
    const w = costWords(e);
    est.replaceChildren(h("div", { class: "aa-row" }, h("span", { class: "aa-lab" }, "Estimated cost"), h("span", { class: "aa-month" }, usd(e.month), h("small", null, " a month"))),
      h("small", null, w.line), h("small", { class: e.fits ? "aa-ok" : "aa-bad" }, w.cap));
  };
  // Assistants: a switch each, with how the place reaches it and its price an answer.
  const switches = providers.map((x) => {
    const on = () => v.providers.includes(x.id);
    const b = h("button", { type: "button", role: "switch", class: "aa-sw", "aria-checked": String(on()), disabled: ro },
      h("span", { class: "box", "aria-hidden": "true" }),
      h("span", { class: "aa-sw-t" }, h("b", null, x.name), h("small", null, `${x.how}. About ${usd(x.price, 3)} an answer.${x.key ? "" : " No API key yet: Settings › AI answers › API keys."}`)),
      h("span", { class: `tag ${x.location === "api" ? "good" : "warn"}` }, x.location === "api" ? "API location" : "In question"));
    b.addEventListener("click", () => { v.providers = on() ? v.providers.filter((y) => y !== x.id) : [...v.providers, x.id]; b.setAttribute("aria-checked", String(on())); refresh(); });
    return b;
  });
  const seg = h("span", { class: "aa-seg", role: "group", "aria-label": "How often" }, FREQ.map(([k, label]) => {
    const b = h("button", { type: "button", "aria-pressed": String(v.frequency === k), disabled: ro }, label);
    b.addEventListener("click", () => { v.frequency = k; seg.querySelectorAll("button").forEach((x, i) => x.setAttribute("aria-pressed", String(FREQ[i][0] === k))); refresh(); });
    return b;
  }));
  const tries = h("span", { role: "status", class: "aa-n" }, String(v.repeats));
  const step = (d) => h("button", { type: "button", class: "btn", disabled: ro, "aria-label": d < 0 ? "Fewer tries" : "More tries",
    onclick: () => { v.repeats = Math.max(1, Math.min(MAX_TRIES, v.repeats + d)); tries.textContent = String(v.repeats); refresh(); } }, d < 0 ? "−" : "+");
  const cap = input({ value: Number(v.cap).toFixed(2), inputmode: "decimal", size: "5", disabled: ro, "aria-label": "Daily spending cap in US dollars" });
  cap.addEventListener("input", () => { v.cap = Number(cap.value) || 0; refresh(); });
  refresh();

  async function send(path, body, done) {
    const r = await call(`ai-answers/${path}`, body);
    if (!r.ok) { msg.say(why(r)); return; }
    msg.say(done, true);
    onSaved(r);
  }
  const save = h("button", { type: "button", class: "btn primary", disabled: ro }, "Save profile");
  save.addEventListener("click", () => send("profiles/save", {
    id: p.id ?? null, name: name.value, city: city.value, region: region.value, country: country.value.toUpperCase(), language: lang.value,
    lat: lat.value === "" ? null : Number(lat.value), lon: lon.value === "" ? null : Number(lon.value), timezone: zone.value,
    ...qs.get(), brands: brands.get(), competitors: comps.get(), providers: v.providers, frequency: v.frequency, repeats: v.repeats, cap: v.cap,
    gbp_location_id: p.gbp_location_id || null,
  }, p.id ? "Saved: a new version, used from the next run." : "Profile made. Its first run starts from 06:00 in the site's time zone."));
  const run = p.id ? h("button", { type: "button", class: "btn", disabled: ro || p.run_requested_at, title: "Asked at the next 15-minute tick" }, p.run_requested_at ? "Run asked" : "Run now") : null;
  if (run) run.addEventListener("click", () => send("profiles/run", { id: p.id }, "Asked: the run starts within 15 minutes."));

  return h("div", { class: "aa-edit" },
    ro ? h("p", { class: "note" }, VIEWER) : null,
    h("div", { class: "aa-fs" }, field("Profile name", name),
      h("div", { class: "aa-grid3" }, field("City", city), field("Region", region), field("Country", country, "ISO, 2 letters")),
      field("Language", lang, "BCP-47: en, fr-CA, de"),
      h("details", { class: "aa-more" }, h("summary", null, "Coordinates and time zone (optional)"),
        h("div", { class: "aa-grid3" }, field("Latitude", lat), field("Longitude", lon), field("Time zone", zone))),
      h("small", { class: "muted" }, "Google Business Profile location: not linked (coming later).")),
    qs.el, brands.el, comps.el,
    h("div", { class: "aa-fs" }, h("span", { class: "aa-lab" }, "Assistants to ask"), switches),
    h("div", { class: "aa-fs" }, h("div", { class: "aa-row" }, h("span", { class: "aa-lab" }, "How often"), seg),
      h("div", { class: "aa-row" }, h("span", { class: "aa-lab" }, "Tries per question"), h("span", { class: "aa-step" }, step(-1), tries, step(1)))),
    h("div", { class: "aa-fs" }, h("label", { class: "aa-row" }, h("span", { class: "aa-lab" }, "Daily spending cap"), h("span", { class: "aa-usd" }, "$", cap)), est),
    h("div", { class: "acts" }, run, save), msg);
}
