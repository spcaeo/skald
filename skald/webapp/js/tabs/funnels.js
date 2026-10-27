// Funnels: how many visits went through a chosen series of pages, in order,
// and where the rest left; a saved funnel can end in steps from the lead
// store. The page steps are counted here from the anonymous journeys the page
// already holds (the last `journey_days` days and today), with the server's
// own rules (funnels.py), so a funnel shows the same figures here and in
// funnels.json. The lead steps come from the server, counted by first-touch
// source and never divided per visit. A funnel lives in the link (fn, fsrc);
// saved funnels are the server's when it has them, else this browser's.

import { h, n, short } from "../ui.js";
import { rangeOf } from "../data.js";
import * as S from "../state.js";
import { store } from "../extras.js";
import { head } from "./common.js";
import { todayNote } from "./sa-options.js";
import { journey, journeyFilter } from "./visits.js";
import { call, installOnly, INSTALL_ONLY } from "./ipmanager.js";
import { isViewer, VIEWER } from "../access.js";
// Saved funnels are shared by every site of the install: with accounts only an install admin saves them.
const lockWhy = () => (isViewer() ? VIEWER : INSTALL_ONLY);
import { eventLabel, everSent, howToSend } from "./events.js";
import { neverRecorded, neverSentAny } from "../notset.js";
import { history } from "./funnelhistory.js";
import { howTo } from "./help.js";
import { connectCard } from "../ui/connect.js";
import { funnelFlowOf, check } from "../flow.js";
import { sankey } from "../sankey.js";
import { shown } from "../labels.js";

const MATCH = [["any", "Any page"], ["equals", "Page is"], ["starts_with", "Starts with"], ["segment", "Page named"]];
const LEAD = { signup: "Sign-up", contact: "Contact form", waitlist: "Early access", demo_opened: "Opened Book a demo", demo_booked: "Demo booked" };
const MAX_STEPS = 8;
const KEY = "ti-funnels";
let ADDING = false, REFOCUS = null, NOTE = "";

// ---------------------------------------------------------------- the link
// "*" any page; "/a/" the page; "/a/*" starts with; "~a" a page named a;
// "a|b" either; "lead:signup,contact" a step from the lead store; "event:cta_click" one from the beacon.
export function parse(fn) {
  return String(fn || "").split(">").map((x) => x.trim()).filter(Boolean).slice(0, MAX_STEPS).map((g) => {
    if (g.startsWith("lead:")) return { kind: "lead", types: g.slice(5).split(",").filter((t) => LEAD[t]) };
    if (g.startsWith("event:")) return { kind: "event", events: g.slice(6).split(",").filter(Boolean) };
    if (g === "*") return { kind: "path", match: "starts_with", paths: ["/"] };
    const parts = g.split("|").map((x) => x.trim()).filter(Boolean);
    if (parts.every((x) => x.length > 2 && x.startsWith("*") && x.endsWith("*"))) return { kind: "path", match: "contains", paths: parts.map((x) => x.slice(1, -1)) };
    if (parts.every((x) => x.startsWith("~"))) return { kind: "path", match: "segment", paths: parts.map((x) => x.slice(1)) };
    if (parts.every((x) => x.endsWith("*"))) return { kind: "path", match: "starts_with", paths: parts.map((x) => x.slice(0, -1)) };
    return { kind: "path", match: "equals", paths: parts };
  }).filter((x) => (x.kind === "lead" ? x.types.length : x.kind === "event" ? x.events.length : x.paths.length));
}
export function glob(steps) {
  return steps.map((x) => {
    if (x.kind === "lead") return `lead:${x.types.join(",")}`;
    if (x.kind === "event") return `event:${x.events.join(",")}`;
    if (x.kind === "any" || isAny(x)) return "*";
    if (x.match === "contains") return x.paths.map((p) => `*${p}*`).join("|");
    return x.paths.map((p) => (x.match === "segment" ? `~${p}` : x.match === "starts_with" ? `${p}*` : p)).join("|");
  }).join(" > ");
}
const isAny = (x) => x.kind === "path" && x.match === "starts_with" && x.paths.length === 1 && x.paths[0] === "/";
const kindOf = (x) => (isAny(x) ? "any" : x.match);

// ------------------------------------------------------- the server's rules
const bare = (p) => p.split("?")[0];
const slash = (p) => p.replace(/\/+$/, "") || "/";
function hits(step, path) {
  path = bare(path);
  return step.paths.some((want) => (step.match === "equals" ? slash(path) === slash(want)
    : step.match === "starts_with" ? path.startsWith(want)
      : step.match === "contains" ? path.includes(want)
      : slash(path).split("/").pop().toLowerCase() === want.replace(/^\/+|\/+$/g, "").toLowerCase()));
}
// How many of the page steps, in order, a visit reached; the page that met one step may meet the next.
export function reached(j, steps) {
  const pages = j.trail.map((t) => t.path);
  let at = 0, k = 0;
  for (const step of steps) {
    let i = at;
    while (i < pages.length && !hits(step, pages[i])) i++;
    if (i >= pages.length) break;
    k++; at = i;
  }
  return k;
}
// The starting source: a source type, an assistant or a referring host.
const fromSource = (fsrc) => {
  const want = (fsrc || "").trim().toLowerCase();
  return want ? (j) => [j.source, j.via, j.ref_host].some((x) => (x || "").toLowerCase() === want) : () => true;
};
let EVNAMES = null;   // events.json, for event steps' names
const stepName = (x) => (x.kind === "event" ? x.events.map((e) => eventLabel(EVNAMES, e)).join(" or ") : x.kind === "lead" ? x.types.map((t) => LEAD[t]).join(" or ") : isAny(x) ? "Any page" : x.paths.map((p) => (x.match === "segment" ? `named ${p}` : x.match === "starts_with" ? `${p}…` : p)).join(" or "));

// --------------------------------------------------------------- saved ones
const server = (m) => (m.x.funnels && Array.isArray(m.x.funnels.funnels) ? m.x.funnels : null);
function savedList(m) {
  const f = server(m);
  if (f) return f.funnels.map((x) => ({ name: x.name, fn: glob(x.steps.map((st) => ({ ...st, kind: st.kind || "path" }))), fsrc: x.source || "", labels: x.steps.map((st) => st.label), by: x.saved_by, result: x.result, long: x.long, history: x.history, def: x.saved_by === "default" }));
  const v = store.get(KEY, []);
  return Array.isArray(v) ? v.filter((x) => x && x.name && x.fn) : [];
}
function knownPages(m) {
  const seen = new Map();
  for (const j of m.journeys) for (const t of j.trail) seen.set(t.path, (seen.get(t.path) || 0) + 1);
  const byVisits = [...seen.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k);
  return [...new Set([...(m.x.pages?.pages || []).map((p) => p.path), ...byVisits])].filter((p) => !/\.\w+$/.test(p));
}
// With nothing chosen or saved: any page, then the most read page that is not the home page.
function starter(m) {
  const top = knownPages(m).find((p) => p !== "/");
  return top ? `* > ${top}` : "* > /";
}

async function save(m, s, steps, name) {
  const f = server(m);
  if (!f) {
    store.set(KEY, [...savedList(m).filter((x) => x.name !== name), { name, fn: glob(steps), fsrc: s.fsrc || "" }].slice(-20));
    NOTE = `Saved "${name}" on this browser.`;
    return S.emit(true);
  }
  const body = { name, source: s.fsrc || null, steps: steps.map((x, i) => (x.kind === "event" ? { label: stepName(x), kind: "event", events: x.events } : x.kind === "lead" ? { label: stepName(x), kind: "lead", types: x.types }
    : { label: i === 0 && isAny(x) ? "Landed" : stepName(x), kind: "path", match: x.match, paths: x.paths })) };
  const r = await call(f.api?.save || "funnels/save", body);
  if (r.ok && Array.isArray(r.funnels)) m.x.funnels = { ...f, funnels: r.funnels };
  NOTE = r.ok ? `Saved "${name}" for everyone.` : `Not saved: ${r.error}`;
  S.emit(true);
}
async function remove(m, x) {
  const f = server(m);
  if (!f) { store.set(KEY, savedList(m).filter((y) => y.name !== x.name)); return S.emit(true); }
  const r = await call(f.api?.delete || "funnels/delete", { name: x.name });
  if (r.ok && Array.isArray(r.funnels)) m.x.funnels = { ...f, funnels: r.funnels };
  NOTE = r.ok ? `Deleted "${x.name}".` : `Not deleted: ${r.error}`;
  S.emit(true);
}

// -------------------------------------------------------------- the builder
function builder(m, s, steps) {
  const viewer = (isViewer() || installOnly()) && server(m);
  const sources = [...new Set(m.journeys.map((j) => j.source).filter(Boolean))].sort();
  const assistants = [...new Set(m.journeys.filter((j) => j.source === "AI assistant" && j.via).map((j) => j.via))].sort();
  const list = h("datalist", { id: "fn-pages" }, knownPages(m).slice(0, 200).map((p) => h("option", { value: p })));
  // A change redraws the page: the control that made it gets the focus back.
  const commit = (next) => { REFOCUS = document.activeElement?.getAttribute("aria-label") || null; ADDING = false; NOTE = ""; S.set({ fn: glob(next), fstep: "" }, { replace: true }); };
  const src = h("select", { "aria-label": "Starting source", onchange: (e) => S.set({ fsrc: e.target.value, fstep: "" }, { replace: true }) },
    h("option", { value: "" }, "Any source"), sources.map((x) => h("option", { value: x, selected: s.fsrc === x }, x)),
    assistants.length ? h("optgroup", { label: "One assistant" }, assistants.map((a) => h("option", { value: a, selected: s.fsrc === a }, a))) : null,
    s.fsrc && ![...sources, ...assistants].includes(s.fsrc) ? h("option", { value: s.fsrc, selected: true }, s.fsrc) : null);
  const read = (v) => v.split("|").map((p) => p.trim()).filter(Boolean);
  const rows = steps.map((x, i) => {
    const del = steps.length > 1 ? h("button", { type: "button", class: "btn icon fn-x", "aria-label": `Remove step ${i + 1}`, title: "Remove step", onclick: () => commit(steps.filter((_, k) => k !== i)) }, "×") : null;
    if (x.kind === "event") {
      return h("li", { class: "fn-step lead" }, h("span", { class: "fn-n", "aria-hidden": "true" }, String(i + 1)),
        h("span", { class: "fn-lead ev" }, "Beacon"), h("span", { class: "fn-lead-t" }, stepName(x)), del);
    }
    if (x.kind === "lead") {
      return h("li", { class: "fn-step lead" }, h("span", { class: "fn-n", "aria-hidden": "true" }, String(i + 1)),
        h("span", { class: "fn-lead" }, "Lead store"), h("span", { class: "fn-lead-t" }, stepName(x)), del);
    }
    const kind = h("select", { "aria-label": `Step ${i + 1}: which pages`, onchange: (e) => {
      const k = e.target.value;
      commit(steps.map((y, j) => (j !== i ? y : k === "any" ? { kind: "path", match: "starts_with", paths: ["/"] } : { kind: "path", match: k, paths: isAny(y) ? [k === "segment" ? "pricing" : "/"] : y.paths })));
    } }, MATCH.map(([k, w]) => h("option", { value: k, selected: kindOf(x) === k }, w)));
    const path = h("input", { type: "text", value: isAny(x) ? "" : x.paths.join(" | "), list: "fn-pages", placeholder: x.match === "segment" ? "pricing" : "/pricing/", "aria-label": `Step ${i + 1}: page`, disabled: isAny(x), spellcheck: "false",
      title: "Several pages: separate them with |", onchange: (e) => { const p = read(e.target.value); if (p.length) commit(steps.map((y, j) => (j === i ? { ...y, paths: p } : y))); } });
    return h("li", { class: `fn-step${isAny(x) ? " is-any" : ""}` }, h("span", { class: "fn-n", "aria-hidden": "true" }, String(i + 1)), kind, path, del);
  });
  // A new step waits here until its page is typed; an empty step would match nothing.
  if (ADDING && steps.length < MAX_STEPS) {
    const i = steps.length;
    const evs = (m.x.events?.events || []).filter((e) => e.name !== "page_view");
    const kind = h("select", { "aria-label": `Step ${i + 1}: which pages`, onchange: (e) => { if (e.target.value.startsWith("event:")) commit([...steps, { kind: "event", events: [e.target.value.slice(6)] }]); } },
      MATCH.filter(([k]) => k !== "any").map(([k, w]) => h("option", { value: k }, w)),
      evs.length ? h("optgroup", { label: "An event, from the beacon" }, evs.map((e) => h("option", { value: `event:${e.name}` }, e.label))) : null);
    const path = h("input", { type: "text", list: "fn-pages", placeholder: "Type a page, e.g. /pricing/", "aria-label": `Step ${i + 1}: page`, spellcheck: "false",
      onchange: (e) => { const p = read(e.target.value); if (p.length) commit([...steps, { kind: "path", match: kind.value, paths: p }]); } });
    const del = h("button", { type: "button", class: "btn icon fn-x", "aria-label": "Cancel the new step", title: "Cancel", onclick: () => { ADDING = false; S.emit(true); } }, "×");
    rows.push(h("li", { class: "fn-step new" }, h("span", { class: "fn-n", "aria-hidden": "true" }, String(i + 1)), kind, path, del));
    requestAnimationFrame(() => path.focus());
  }
  const add = steps.length < MAX_STEPS && !ADDING ? h("button", { type: "button", class: "btn", onclick: () => { ADDING = true; S.emit(true); } }, "Add a step") : null;
  const name = h("input", { type: "text", placeholder: "Name this funnel", "aria-label": "Funnel name", maxlength: "60", disabled: viewer, title: viewer ? lockWhy() : null });
  const saveBtn = h("button", { type: "button", class: "btn", disabled: viewer, title: viewer ? lockWhy() : null,
    onclick: () => save(m, s, steps, name.value.trim() || steps.map(stepName).join(" then ").slice(0, 60)) }, "Save funnel");
  if (REFOCUS) { const want = REFOCUS; REFOCUS = null; requestAnimationFrame(() => [...document.querySelectorAll(".fn-build [aria-label]")].find((e) => e.getAttribute("aria-label") === want)?.focus()); }
  return h("div", { class: "sheet fn-build" },
    h("div", { class: "fn-src" }, h("label", { class: "ctl" }, h("span", null, "Starting from"), src)),
    h("ol", { class: "fn-steps" }, rows), list,
    h("div", { class: "fn-acts" }, add, h("span", { class: "grow" }), name, saveBtn),
    viewer ? h("p", { class: "note viewer-note" }, lockWhy()) : null,
    NOTE ? h("p", { class: "note", role: "status" }, NOTE) : null);
}

function savedRow(m, s, fn) {
  const all = savedList(m);
  if (!all.length) return null;
  const viewer = (isViewer() || installOnly()) && server(m);
  return h("div", { class: "fn-saved", role: "group", "aria-label": "Saved funnels" }, h("span", { class: "add-l" }, server(m) ? "Saved for everyone" : "Saved on this browser"),
    all.map((x) => h("span", { class: `fn-chip${x.fn === fn && (x.fsrc || "") === (s.fsrc || "") ? " on" : ""}`, title: x.by && !x.def ? `Saved by ${x.by}` : null },
      h("button", { type: "button", onclick: () => { NOTE = ""; S.set({ fn: x.fn, fsrc: x.fsrc || "", fstep: "" }); } }, x.name),
      x.def ? null : h("button", { type: "button", class: "fn-del", disabled: viewer, title: viewer ? lockWhy() : null, "aria-label": `Delete the saved funnel ${x.name}`, onclick: () => remove(m, x) }, "×"))));
}

// ------------------------------------------------------------- the results
/* A step that relies on something the site never sends: an event never sent, or a
   lead kind the lead store has never recorded. Its words say so, never 0. */
export function unsentStep(m, x) {
  if (x.kind === "event") {
    const off = x.events.filter((e) => !everSent(m.x.events, e));
    return off.length === x.events.length ? `Not set up: ${off.map((e) => eventLabel(m.x.events, e)).join(" or ")} never sent. ${howToSend(off[0])}` : null;
  }
  if (x.kind === "lead") {
    const f = m.x.leads;
    if (!f || f.available === false) return null;
    const never = neverRecorded(f);
    if (!x.types.every((t) => never.has(t))) return null;
    const demo = x.types.some((t) => t.startsWith("demo_"));
    return `Not set up: the lead store has never recorded ${x.types.map((t) => LEAD[t].toLowerCase()).join(" or ")}${f.since ? ` (read since ${short(f.since)})` : ""}.${demo ? " Demo bookings are counted from the booking tool, on Leads & sales › Calendar bookings." : ""}`;
  }
  return null;
}

/* The bars: page steps are visits, as a share of the visits at step 1. Lead and
   event steps are other systems with other units: each group is drawn apart, under
   its own heading, on its own scale (the longest bar of the group), never as a
   share of visits. */
function chart(m, steps, counts, s, lead, labels, evCounts) {
  const start = counts[0] || 0;
  const name = (x, i) => labels?.[i] || stepName(x);
  const leadTop = Math.max(0, ...steps.map((x, i) => (x.kind === "lead" ? lead?.[i]?.n || 0 : 0)));
  const evTop = Math.max(0, ...steps.map((x, i) => (x.kind === "event" ? evCounts[i] || 0 : 0)));
  const open = Number(s.fstep) || 0;
  let prevPath = null;
  const scaleNote = (kind) => (kind === "lead"
    ? h("p", { class: "fn-scale" }, h("b", null, "Lead store steps, on their own scale"), ` (the longest bar is ${n(leadTop)} lead${leadTop === 1 ? "" : "s"}). Leads by first-touch source: not a share of the visits above, never joined to them.`)
    : h("p", { class: "fn-scale" }, h("b", null, "Beacon steps, on their own scale"), ` (the longest bar is ${n(evTop)} event${evTop === 1 ? "" : "s"}). Events on the same days: not a share of the visits above, never joined to them.`));
  return h("ol", { class: "fn-chart", "aria-label": "Visits at each step" },
    steps.some((x) => x.kind === "path") ? h("li", { class: "fn-scale-li" }, h("p", { class: "fn-scale first" }, h("b", null, "Page steps: visits"), `, each bar a share of the ${n(start)} visit${start === 1 ? "" : "s"} at step 1.`)) : null,
    steps.map((x, i) => {
    const unsent = x.kind === "path" ? null : unsentStep(m, x);
    if (x.kind === "event") {
      const v = unsent ? null : evCounts[i];
      const first = !steps.slice(0, i).some((y) => y.kind === "event");
      return h("li", null, first ? scaleNote("event") : null, h("div", { class: "fn-bar static" },
        h("span", { class: "fn-l" }, h("b", null, `${i + 1}`), h("span", { class: "any" }, name(x, i))),
        h("span", { class: "fn-track ev" }, h("i", { style: { width: v && evTop ? `${Math.max(1.5, (v / evTop) * 100)}%` : "0%" } })),
        h("span", { class: "fn-v" }, h("b", null, unsent ? "Not set up" : v == null ? "-" : n(v)), h("small", null, unsent ? "never sent" : v == null ? "not split by this source" : "events"))),
        unsent ? h("p", { class: "fn-unsent" }, unsent) : null);
    }
    if (x.kind === "lead") {
      const v = unsent ? null : lead?.[i]?.n;
      const first = !steps.slice(0, i).some((y) => y.kind === "lead");
      return h("li", null, first ? scaleNote("lead") : null, h("div", { class: "fn-bar static" },
        h("span", { class: "fn-l" }, h("b", null, `${i + 1}`), h("span", { class: "any" }, name(x, i))),
        h("span", { class: "fn-track lead" }, h("i", { style: { width: v && leadTop ? `${Math.max(1.5, (v / leadTop) * 100)}%` : "0%" } })),
        h("span", { class: "fn-v" }, h("b", null, unsent ? "Not set up" : v == null ? "-" : n(v)), h("small", null, unsent ? "never recorded" : v == null ? "counted once saved" : "leads, lead store"))),
        unsent ? h("p", { class: "fn-unsent" }, unsent) : null);
    }
    const v = counts[i], prev = prevPath;
    prevPath = v;
    const of = start ? (v / start) * 100 : 0;
    const drop = prev ? Math.round(((prev - v) / prev) * 100) : null;
    return h("li", null, h("button", { type: "button", class: "fn-bar", "aria-pressed": String(open === i + 1),
      "aria-label": `Step ${i + 1}, ${name(x, i)}: ${n(v)} visits${i ? `, ${Math.round(of)}% of the start` : ""}. Show these visits`,
      onclick: () => S.set({ fstep: open === i + 1 ? "" : String(i + 1), fmode: "" }, { replace: true }) },
      h("span", { class: "fn-l" }, h("b", null, `${i + 1}`), h("span", { class: isAny(x) || labels?.[i] ? "any" : null }, name(x, i))),
      h("span", { class: "fn-track" }, h("i", { style: { width: `${Math.max(v ? 1.5 : 0, of)}%` } })),
      h("span", { class: "fn-v" }, h("b", null, n(v)), h("small", null, i ? `${start ? Math.round(of) : 0}% of start` : "visits"))),
    drop != null ? h("p", { class: `fn-drop${drop >= 50 ? " big" : ""}` }, `${drop}% left before this step (${n(prev - v)})`) : null);
  }));
}

function drill(list, steps, s) {
  const k = Number(s.fstep);
  const at = steps.slice(0, k).filter((x) => x.kind === "path").length;   // the k-th step's place among the page steps
  const pages = steps.filter((x) => x.kind === "path").length;
  const left = s.fmode === "left" && at < pages;
  const rows = list.filter((x) => (left ? x.r === at : x.r >= at)).map((x) => x.j);
  let shown = 20;
  const ul = h("ul", { class: "journeys", style: { listStyle: "none", margin: 0, padding: 0 } });
  const more = h("button", { type: "button", class: "btn more-rows" });
  const draw = () => {
    ul.replaceChildren(...rows.slice(0, shown).map(journey));
    if (!rows.length) ul.append(h("li", { class: "empty" }, left ? "No visit left at this step." : "No visit reached this step."));
    more.hidden = rows.length <= shown;
    more.textContent = `Show ${n(Math.min(20, rows.length - shown))} more`;
  };
  more.addEventListener("click", () => { shown += 20; draw(); });
  draw();
  const seg = at < pages ? h("div", { class: "seg plain", role: "group", "aria-label": "Which visits" },
    h("button", { type: "button", "aria-pressed": String(!left), onclick: () => S.set({ fmode: "" }, { replace: true }) }, "Reached it"),
    h("button", { type: "button", "aria-pressed": String(left), onclick: () => S.set({ fmode: "left" }, { replace: true }) }, "Left after it")) : null;
  return h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, `Step ${k}: ${stepName(steps[k - 1])}`), seg,
    h("span", { class: "tbl-count fn-count" }, `${n(rows.length)} visit${rows.length === 1 ? "" : "s"}`)), ul, more);
}

// An event step: the beacon's events of these kinds on the funnel's days, from the
// starting source when it is a source type (events keep only the visit's source type).
function eventCounts(m, steps, days, fsrc) {
  const f = m.x.events;
  const types = new Set(m.journeys.map((j) => j.source));
  return steps.map((x) => {
    if (x.kind !== "event") return null;
    if (!f) return null;
    if (fsrc && !types.has(fsrc)) return null;
    const want = new Set(x.events), on = new Set(days);
    const ok = new Set((f.days || []).filter((d) => d.state === "ok").map((d) => d.day));
    let v = (f.rows || []).filter((row) => on.has(row[0]) && ok.has(row[0]) && want.has(row[1]) && (!fsrc || row[4] === fsrc)).reduce((a, row) => a + row[5], 0);
    if (on.has(m.today) && f.today?.state === "ok") v += (f.today.rows || []).filter((row) => want.has(row[0]) && (!fsrc || row[3] === fsrc)).reduce((a, row) => a + row[4], 0);
    return v;
  });
}

/* The same visits as a flow: source, then each page step, with those that left
   between steps. Built from the list the chart counts, so its step nodes are the
   chart's figures; withheld if it does not add up. A step opens its visits. */
function flowBetween(list, steps, s, labels) {
  const at = steps.map((x, i) => (x.kind === "path" ? i : -1)).filter((i) => i >= 0);
  const names = at.map((i) => labels?.[i] || stepName(steps[i]));
  const flow = funnelFlowOf(list, names);
  const off = check(flow);
  const body = off.length ? h("div", { class: "state bad", role: "alert" }, h("div", null, `The flow is withheld: it does not add up (${off[0]}).`))
    : sankey(flow, {
      label: "Visits between the funnel's steps", unit: "visits", file: "funnel-flow.csv", pickAll: true,
      kindWords: { start: "Starting source", step: "A funnel step", left: "Left between steps" },
      say: (nd) => (nd.kind === "start" ? shown(nd.label) : nd.kind === "step" ? `${nd.step}. ${nd.label}` : nd.label),
      onPick: (nd) => (nd.kind === "start" ? S.set({ fsrc: nd.drill[1], fstep: "" }, { replace: true })
        : S.set({ fstep: String(at[nd.step - 1] + 1), fmode: nd.kind === "left" ? "left" : "" }, { replace: true })),
      empty: "No visit met the first step.",
      note: "Each visit once: its source, then each page step it reached in order; a visit that went no further flows to Left after that step. The step figures are the chart's above. Click a step for its visits, a source to start from it.",
    });
  return h("section", { class: "s" }, h("h2", null, "Flow between the steps"),
    h("p", { class: "sub" }, "Where the funnel's visits came from, and where they dropped off."), h("div", { class: "sheet" }, body));
}

export default function funnels(m, s) {
  EVNAMES = m.x.events;
  const r = rangeOf(m, s);
  const saved = savedList(m);
  const fn = s.fn || saved[0]?.fn || starter(m);
  const steps = parse(fn);
  const pathSteps = steps.filter((x) => x.kind === "path");
  const inRange = r.kind === "today" ? (j) => j.day === m.today : (j) => j.day >= r.first && j.day <= r.last;
  const kept = m.journeys.filter(inRange);
  const days = [...new Set(kept.map((j) => j.day))].sort();
  // The period above reaches only as far back as the journeys kept: a longer one is said, never silently cut.
  const span = days.length ? (days.length === 1 ? short(days[0]) : `${short(days[0])} to ${short(days[days.length - 1])}`) : "";
  const covers = !days.length ? "no journeys kept for this range"
    : r.kind === "history" && r.length > days.length ? `Visits: ${span} only, the days journeys are kept (${m.journey_days || 7}); the period above is longer`
      : `${span}, the days journeys are kept`;
  const out = [...head("Funnels", r, `How many visits went through these pages in order, and where the rest left. The page that met one step may also meet the next, so Any page then /pricing/ counts a visit that landed on pricing. Built from each visit's pages in order, kept ${m.journey_days || 7} days. A saved funnel may end with steps from the lead store, counted by the lead's first-touch source and never joined to a visit.`, { period: covers, banner: false }), todayNote(m, s, r)].filter(Boolean);
  out.push(savedRow(m, s, fn), builder(m, s, steps));
  // 2.43: a goal step whose source is not connected (the script tag never sent it, the lead
  // store never recorded it): one line, with how to connect it (js/ui/connect.js).
  const off = steps.filter((x) => unsentStep(m, x));
  if (off.some((x) => x.kind === "event") && neverSentAny(m.x.events)) {
    out.push(connectCard(m, "script", { s, mode: "line", title: "Event steps need the script tag", line: "It sends clicks, form steps and bookings from your pages." }));
  } else if (off.some((x) => x.kind === "lead")) {
    out.push(connectCard(m, "leads", { s, mode: "line", title: "Lead steps need a lead source", line: "Your forms or your server tell Skald about each lead." }));
  }
  const match = saved.find((x) => x.fn === fn && (x.fsrc || "") === (s.fsrc || "") && x.result);
  // A saved funnel's daily history covers any range; an unsaved one has none yet.
  const past = match?.history ? history(m, r, match)
    : server(m) && !match ? [h("p", { class: "note" }, "Save this funnel to keep its history: from the day it is saved it is counted every day, for any range.")] : [];
  const list = kept.filter(journeyFilter(s)).filter(fromSource(s.fsrc)).map((j) => ({ j, r: reached(j, pathSteps) }));
  if (!list.length) {
    out.push(h("p", { class: "empty" }, kept.length ? "No visit matches this starting source and the filters." : `No visit journeys are kept for this range. They are kept ${m.journey_days || 7} days: choose Today or 7 days${past.length ? ", or see the history below" : ""}.`), ...past,
      howTo("funnels-and-goals", "How do I build a funnel and keep its history?"));
    return out;
  }
  // Each step's visits: a page step by how many page steps a visit reached; a lead step from the server.
  let k = 0;
  const counts = steps.map((x) => (x.kind === "path" ? (k++, list.filter((e) => e.r >= k).length) : null));
  const lead = match ? match.result.steps : null;
  const lastPath = counts.filter((c) => c != null).pop() ?? 0, start = counts[0] ?? 0;
  out.push(h("section", { class: "s" }, h("div", { class: "card-h start" }, h("h2", null, `${n(lastPath)} of ${n(start)} visits went through every page step`),
    h("span", { class: "tbl-count" }, start ? `${((lastPath / start) * 100).toFixed(start >= 100 ? 1 : 0)}%` : "")),
    h("div", { class: "sheet" }, chart(m, steps, counts, s, lead, match?.labels, eventCounts(m, steps, days, s.fsrc))),
    h("p", { class: "note" }, `Click a page step for its visits. Out of ${n(list.length)} visit${list.length === 1 ? "" : "s"} from ${s.fsrc || "any source"}${S.activeFilters(s).length || s.rules ? " that match the filters" : ""}.`,
      steps.some((x) => x.kind === "lead") ? ` The lead steps cover ${match ? `${short(match.result.first)} to ${short(match.result.last)}` : "the days of the last save"}, by first-touch source${match && (match.result.first !== days[0] || match.result.last !== days[days.length - 1]) ? `: their own period (the last save's), not the visits' ${span}` : ""}.` : "",
      match?.long?.first_step != null ? ` Over ${match.long.days} days, ${n(match.long.first_step)} visits met the first step.` : "")));
  if (pathSteps.length >= 2) out.push(flowBetween(list, steps, s, match?.labels));
  const opened = Number(s.fstep);
  if (opened >= 1 && opened <= steps.length && steps[opened - 1].kind === "path") out.push(drill(list, steps, s));
  out.push(...past);
  return out;
}
