// AI & bots › AI answers, its parts (ai_answers.json, answers/data.py):
//   chainCard    cited → read → sent → converted for one assistant and page: four
//                counts, each from its own road, joined by page and days, never added
//   sovChart     how often each assistant names the site, per run of one profile (share
//                of the run's answered tries); a withheld run is a gap, hatched
//   matrix       one question, every profile × every assistant: "x of N" tries and a dot
//                per try (filled: it named the site)
//   questionsTable  one profile's last run: each question, tries that named the site,
//                the page cited, the others named, and a line from one answer
//   competitorsTable  each competitor's answers naming it, by assistant
// Provider colours are the app's four categorical hues in a fixed order (css/answers.css);
// every series is also named in a legend and at its line's end, never by colour alone.

import { h, n, short, long, esc, tip, untip } from "../ui.js";
import { table, csv, download } from "../table.js";
import { exportButton } from "../tabletools.js";
import { link } from "../drill.js";
import { flagEl, country, countryName } from "./readers.js";
import { copyIf } from "../urlactions.js";

export const COLOR = { openai: "var(--p-openai)", perplexity: "var(--p-perplexity)", gemini: "var(--p-gemini)", anthropic: "var(--p-anthropic)" };
const pctOf = (a, b) => (b ? Math.round((a / b) * 100) : null);

export function profileLabel(p) {
  // A country as everywhere (2.13): the flag and the alpha-3 code, the full name in the tooltip and for a screen reader.
  const cc = p.country ? country(p.country) : "";
  return h("span", { class: "aa-pl", title: p.country ? `${p.city || p.name}, ${countryName(p.country)}` : null }, flagEl(p.country),
    h("span", null, p.city || p.name, cc ? h("span", { "aria-hidden": "true" }, `, ${cc}`) : null, p.country ? h("span", { class: "vh" }, `, ${countryName(p.country)}`) : null),
    h("span", { class: "aa-lang" }, p.language || "en"));
}
export const profileText = (p) => `${p.city || p.name}${p.country ? `, ${country(p.country)}` : ""} · ${p.language || "en"}`;

/* The chain: the first assistant and page with a citation, or the one picked. */
export function chainCard(x, ch, provName, onPick) {
  if (!ch.length) {
    return h("section", { class: "s aa-card" }, h("h2", null, "From an answer to a lead"),
      h("p", { class: "empty" }, `No assistant cited one of your pages in an answer${x.chain_first && x.chain_last ? ` from ${short(x.chain_first)} to ${short(x.chain_last)}` : ""} yet. When one does, this shows what its fetcher then read and the visitors it sent.`));
  }
  const c = ch[0];
  const nr = (v) => (v == null ? "not recorded" : n(v));
  const steps = [
    ["Cited", nr(c.cited), "answers", `${provName(c.provider)} cited ${c.page}`, `AI answers sample, ${n(c.cited)} of ${n(c.of)} answers`, "cited"],
    ["Read", nr(c.read), "fetches", `Its fetcher read ${c.page} for people asking`, "server log, the assistant's user fetcher", "read"],
    ["Sent", nr(c.sent), "visitors", `Clicked through to ${c.page}`, `server log, from ${x.providers.find((p) => p.id === c.provider)?.assistant || ""}`, "sent"],
    ["Converted", nr(c.leads), "leads", "First visit from an AI answer, landing on this page (any assistant)", "your forms and booking tool", "leads"],
  ];
  const pick = ch.length > 1 ? h("select", { "aria-label": "Assistant and page", onchange: (e) => onPick(Number(e.target.value)) },
    ch.map((r, i) => h("option", { value: String(i) }, `${provName(r.provider)} · ${r.page} (${r.cited})`))) : null;
  return h("section", { class: "s aa-card", "aria-labelledby": "aa-chain-h" },
    h("div", { class: "aa-cardhead" }, h("div", null, h("h2", { id: "aa-chain-h" }, "From an answer to a lead"),
      h("p", { class: "sub" }, `${provName(c.provider)} and the page `, link("path", c.page), `, ${short(x.chain_first)} to ${short(x.chain_last)}. Only Skald sees all four, because it reads your server log.`)),
    pick || h("a", { href: "#ai/assistants" }, `AI assistants › ${provName(c.provider)}`)),
    h("ol", { class: "aa-chain" }, steps.map(([step, v, unit, what, road, k]) => h("li", { class: `k-${k}` },
      h("span", { class: "dot", "aria-hidden": "true" }), h("span", { class: "st" }, step),
      h("span", { class: "nv" }, h("b", null, v), h("small", null, unit)), h("span", { class: "wh" }, what), h("small", { class: "rd" }, road)))),
    c.likely != null ? h("p", { class: "note" }, `Also ${n(c.likely)} visit${c.likely === 1 ? "" : "s"} to ${c.page} likely sent by an AI answer with no referrer (inferred, any assistant, never added to the visitors above).`) : null,
    h("p", { class: "note" }, "Each step is counted on its own: answers from the sample, fetches and visits from the log, leads from your forms and booking tool. They are joined by page and day, not by person, so the steps show a path, not one buyer."));
}

/* Share of answers naming the site, per run of one profile. */
export function sovChart(runs, providers, subtitle) {
  const used = providers.filter((p) => runs.some((r) => r.providers[p.id]));
  if (!runs.length || !used.length) return h("section", { class: "s aa-card" }, h("h2", null, "How often each assistant names you"), h("p", { class: "empty" }, "No run of this profile is complete and checked yet."));
  const W = 1000, H = 230, L = 40, R = 130, T = 10, B = 26, pw = W - L - R, ph = H - T - B;
  const X = (i) => L + (runs.length === 1 ? pw / 2 : (i / (runs.length - 1)) * pw);
  const Y = (v) => T + ph - (v / 100) * ph;
  const share = (r, p) => { const f = r.providers[p]; return f && f.answered ? pctOf(f.mentioned, f.answered) : null; };
  const out = [];
  for (const v of [0, 25, 50, 75, 100]) out.push(`<line class="aa-grid" x1="${L}" x2="${L + pw}" y1="${Y(v)}" y2="${Y(v)}"/><text class="aa-ax" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`);
  runs.forEach((r, i) => {
    if (r.withheld) out.push(`<rect x="${X(i) - 6}" y="${T}" width="12" height="${ph}" class="aa-held"><title>Withheld: the recount did not match</title></rect>`);
    out.push(`<text class="aa-ax" x="${X(i)}" y="${H - 6}" text-anchor="middle">${esc(short(r.day))}</text>`);
  });
  const ends = [];
  for (const p of used) {
    let seg = [];
    const segs = [];
    runs.forEach((r, i) => { const v = share(r, p.id); if (v == null) { if (seg.length) segs.push(seg); seg = []; } else seg.push([X(i), Y(v)]); });
    if (seg.length) segs.push(seg);
    for (const s of segs) {
      if (s.length > 1) out.push(`<polyline points="${s.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")}" fill="none" stroke="${COLOR[p.id]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`);
      for (const [x, y] of s) out.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" fill="${COLOR[p.id]}" stroke="var(--surface)" stroke-width="2"/>`);
    }
    const lastI = runs.map((r) => share(r, p.id)).findLastIndex((v) => v != null);
    if (lastI >= 0) ends.push({ name: p.name, v: share(runs[lastI], p.id), y: Y(share(runs[lastI], p.id)) });
  }
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 16) ends[i].y = ends[i - 1].y + 16;
  for (const e of ends) out.push(`<text class="aa-end" x="${L + pw + 10}" y="${e.y + 4}">${esc(e.name)} <tspan font-weight="650">${e.v}%</tspan></text>`);
  out.push(`<line class="aa-hair" x1="0" x2="0" y1="${T}" y2="${T + ph}" opacity="0"/>`);
  const slot = runs.length === 1 ? pw : pw / (runs.length - 1);
  runs.forEach((r, i) => out.push(`<rect class="hit" data-i="${i}" tabindex="0" x="${X(i) - slot / 2}" y="${T}" width="${slot}" height="${ph}" fill="transparent" aria-label="${esc(`Run of ${long(r.day)}: ${r.withheld ? "withheld" : used.map((p) => `${p.name} ${share(r, p.id) ?? "-"}%`).join(", ")}`)}"/>`));
  const svg = h("div", { class: "aa-chart", html: `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Share of answers naming the site, per run">${out.join("")}</svg>` });
  const hair = svg.querySelector(".aa-hair");
  svg.querySelectorAll(".hit").forEach((el) => {
    const i = Number(el.dataset.i), r = runs[i];
    const show = (x, y) => {
      hair.setAttribute("x1", X(i)); hair.setAttribute("x2", X(i)); hair.setAttribute("opacity", "1");
      const rows = r.withheld ? [{ value: "", label: "withheld: the second count did not match" }]
        : used.map((p) => { const f = r.providers[p.id]; return { color: COLOR[p.id], value: share(r, p.id) == null ? "-" : `${share(r, p.id)}%`, label: f ? `${p.name}, ${f.mentioned} of ${f.answered} answers` : `${p.name} not asked` }; });
      tip(x, y, `Run of ${long(r.day)}`, rows);
    };
    el.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    el.addEventListener("pointerleave", () => { hair.setAttribute("opacity", "0"); untip(); });
    el.addEventListener("focus", () => { const b = el.getBoundingClientRect(); show(b.left + b.width / 2, b.top + 30); });
    el.addEventListener("blur", () => { hair.setAttribute("opacity", "0"); untip(); });
  });
  return h("section", { class: "s aa-card", "aria-labelledby": "aa-sov-h" },
    h("h2", { id: "aa-sov-h" }, "How often each assistant names you"), h("p", { class: "sub" }, subtitle),
    h("ul", { class: "legend" }, used.map((p) => h("li", null, h("span", { class: "sw line", style: { background: COLOR[p.id] } }), p.name))), svg);
}

/* One question across profiles: x of N tries per assistant. */
export function matrix(question, rows, providers, onProfile) {
  // The CSV of what it shows: one row per profile, "x of N" per assistant (the shared export, table.js).
  const cols = [{ key: "profile", label: "Profile", csv: (r) => profileText(r.profile) },
    ...providers.map((p) => ({ key: p.id, label: p.name, csv: (r) => { const c = r.cells[p.id]; return !c ? "not asked" : c.answered ? `${c.mentioned} of ${c.answered}` : "no answer"; } }))];
  const dl = exportButton(() => download("ai-answers-profiles.csv", csv(cols, rows)));
  return h("section", { class: "s aa-card", "aria-labelledby": "aa-mx-h" },
    h("div", { class: "aa-cardhead" }, h("h2", { id: "aa-mx-h" }, "Every profile, every assistant"), dl),
    h("p", { class: "sub" }, `“${question}”, last run. A filled dot is a try that named you; select a question below to change it.`),
    h("div", { class: "scroll" }, h("div", { class: "aa-mx", role: "table", "aria-label": "Mentions by profile and assistant", style: { "--cols": providers.length } },
      h("div", { role: "row", class: "aa-mx-r" }, h("span", { role: "columnheader" }, "Profile"),
        providers.map((p) => h("span", { role: "columnheader" }, h("span", null, h("span", { class: "sw", style: { background: COLOR[p.id] } }), p.name),
          h("small", { class: p.location === "api" ? "aa-ok" : "aa-warn" }, p.location === "api" ? "location passed to the API" : "place written into the question")))),
      rows.map((r) => h("div", { role: "row", class: `aa-mx-r${r.on ? " on" : ""}` }, h("span", { role: "rowheader" },
        r.on || !onProfile ? profileLabel(r.profile) : h("button", { type: "button", class: "linkish aa-mx-pick", title: `Open the profile ${profileText(r.profile)}`, onclick: () => onProfile(r.profile) }, profileLabel(r.profile))),
        providers.map((p) => {
          const c = r.cells[p.id];
          if (!c || !c.answered) return h("span", { role: "cell", class: "aa-cell none" }, c ? `${c.tries} tr${c.tries === 1 ? "y" : "ies"}, no answer` : "not asked");
          const tint = Math.round((c.mentioned / c.answered) * 5);
          return h("span", { role: "cell", class: `aa-cell t${tint}`, title: `${profileText(r.profile)}, ${p.name}: named you in ${c.mentioned} of ${c.answered} tries` },
            h("b", null, `${c.mentioned} of ${c.answered}`),
            h("span", { class: "aa-dots", "aria-hidden": "true" }, Array.from({ length: c.answered }, (_, i) => h("i", { class: i < c.mentioned ? "on" : null }))));
        }))))));
}

/* One profile's last run, question by question. */
export function questionsTable(last, providers, prof, onPick, onOpen, selected) {
  const names = Object.fromEntries(providers.map((p) => [p.id, p.name]));
  const rows = last.questions.map((q) => {
    const by = Object.entries(q.by);
    const named = by.reduce((a, [, c]) => a + c.mentioned, 0), of = by.reduce((a, [, c]) => a + c.answered, 0);
    const pages = [...new Set(by.flatMap(([, c]) => c.pages))];
    const comps = [...new Set(by.flatMap(([, c]) => c.competitors))];
    const quote = by.find(([, c]) => c.line?.mark) || by.find(([, c]) => c.line);
    return { __k: String(q.qi), qi: q.qi, question: q.question, named, of, pages, comps, by, quote };
  });
  const cols = [
    { key: "question", label: "Question", title: "Each question, and a line from one answer that named you", fmt: (v, r) => h("span", { class: "aa-q" }, h("span", null, v),
      r.quote ? h("small", null, h("b", null, `${names[r.quote[0]]}: `), r.quote[1].line.pre, h("mark", null, r.quote[1].line.mark), r.quote[1].line.post, " ",
        h("button", { type: "button", class: "linkish", onclick: () => onOpen(r.quote[1].answer_id) }, "Full answer")) : null), csv: (r) => r.question },
    { key: "named", label: "Named you", num: true, fmt: (v, r) => h("span", { class: "aa-named" }, h("span", { class: `pill ${r.of && v / r.of >= 0.5 ? "good" : r.of && v / r.of >= 0.25 ? "" : "bad"}` }, `${v} of ${r.of}`),
      h("span", { class: "aa-bars", "aria-hidden": "true" }, r.by.map(([p, c]) => h("i", { style: { background: COLOR[p], opacity: c.answered ? (0.2 + (c.mentioned / c.answered) * 0.8).toFixed(2) : "0.1" } })))), csv: (r) => `${r.named} of ${r.of}` },
    { key: "pages", label: "Page it cited", fmt: (v) => (v.length ? h("span", { class: "aa-pages" }, v.map((p) => link("path", p))) : h("span", { class: "muted" }, "No page cited")), csv: (r) => r.pages.join(" ") },
    { key: "comps", label: "Others it named", fmt: (v) => (v.length ? h("span", { class: "aa-chips" }, v.map((c) => copyIf("text", h("span", { class: "aa-chip" }, c), c, { label: "competitor" }))) : h("span", { class: "muted" }, "None")), csv: (r) => r.comps.join("; ") },
  ];
  return h("section", { class: "s aa-card", "aria-labelledby": "aa-qs-h" },
    h("h2", { id: "aa-qs-h" }, `Questions, ${prof}`),
    h("p", { class: "sub" }, `Run of ${long(last.day)}, ${last.providers.map((p) => names[p]).join(", ")}, ${last.repeats} tr${last.repeats === 1 ? "y" : "ies"} each. Select a row for its question across profiles.`),
    table(cols, { caption: `Questions, ${prof}`, rows, file: "ai-answers-questions", sortKey: null, limit: 50,
      onRow: (r) => onPick(r.question), rowClass: (r) => (r.question === selected ? "sel" : null) }));
}

export function competitorsTable(list, providers, prof, days) {
  const cols = [{ key: "name", label: "Competitor" }, { key: "answers", label: "Answers naming it", num: true },
    ...providers.map((p) => ({ key: p.id, label: p.name, num: true, sort: (r) => r.by[p.id] || 0, fmt: (_, r) => (r.of[p.id] ? `${r.by[p.id] || 0} of ${r.of[p.id]}` : "-"), csv: (r) => r.by[p.id] || 0 }))];
  return h("section", { class: "s aa-card" }, h("h2", null, "Competitors in the answers"),
    h("p", { class: "sub" }, `${prof}, last ${days} days: answers that name each competitor, of each assistant's answers.`),
    table(cols, { caption: "Competitors named in AI answers", rows: list.map((c) => ({ ...c, __k: c.name })), file: "ai-answers-competitors", sortKey: "answers", empty: "No competitor named yet, or none listed (Settings › AI answers)." }));
}
