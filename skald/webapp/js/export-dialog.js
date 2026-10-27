// Export (2.42, the UX audit's task 6). Before: four export items under More (the tables as a
// ZIP, the tab as JSON, Print this tab, the Report builder with 33 tick boxes), and the client
// reports far away in Settings. Now one button asks "What do you need?" and shows only that path:
//
//   pdf      A PDF of this page      this page as on screen; "Change" opens the sections, the
//                                    period, the page group and the filters (the old builder)
//   csv      The tables, as CSV      each table of this page on its own, or all in a ZIP
//   monthly  A report someone gets   who gets it, how often, what is in it (this page by
//            every month             default), Preview, Start sending (settings/report-save);
//                                    owners and admins with accounts; no mail server: says so
//   tools    Everything, for my      this page as JSON; the API and MCP pages
//            own tools
//
// In the address: dlg=export&kind=<kind>&xch=1 (xch: the Change part open), and by= when the
// mail server note asks who sets it up. dlg=report (the old builder's links) opens kind=pdf
// with Change open. Every press is the same function the old items called (report.js).
//
//   openExport(m, s, loadView, { kind, change })   -> the drawer

import { h, n, ICON } from "./ui.js";
import * as S from "./state.js";
import { openDrawer } from "./drawer.js";
import { stepped } from "./overlays.js";
import { primary } from "./ui/primary.js";
import { help } from "./ui/help.js";
import { REGISTRY, csv, download } from "./table.js";
import { exportZip, exportJSON, makeReport, filtersOf, FILTER_WORDS, slug, stamp } from "./report.js";
import { rangeOf, viewList } from "./data.js";
import { rangeWords } from "./tabs/common.js";
import { withFlag } from "./tabs/readers.js";
import { ME, sessions } from "./access.js";
import { DEMO } from "./demo.js";

export const KINDS = ["pdf", "csv", "monthly", "tools"];
const ALIAS = { client: "monthly", report: "pdf", zip: "csv", json: "tools", api: "tools" };
export const kindOf = (v) => { const k = ALIAS[v] || v; return KINDS.includes(k) ? k : ""; };
const ROUTE = { key: "dlg", value: "export" };
// The last choice, in this browser: Export opens on it, so a PDF again is More, Export, Print.
const MEM = "ti-export-kind";
export function lastKind() { try { return kindOf(JSON.parse(localStorage.getItem(MEM) || "null") || ""); } catch { return ""; } }
const keepKind = (k) => { try { localStorage.setItem(MEM, JSON.stringify(k)); } catch { /* private mode: not kept */ } };

const svg = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICONS = {
  pdf: svg('<path d="M4 1.8h5.5L12.5 5v9.2H4z"/><path d="M9.5 1.8V5h3M6 8.5h4.5M6 11h4.5"/>'),
  csv: svg('<rect x="2" y="2.5" width="12" height="11" rx="1.5"/><path d="M2 6.5h12M2 10h12M6.5 2.5v11"/>'),
  monthly: svg('<rect x="2" y="3" width="12" height="11" rx="1.5"/><path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3M5 9.5h2M9 9.5h2M5 12h2"/>'),
  tools: svg('<path d="M5.5 4 2 8l3.5 4M10.5 4 14 8l-3.5 4M9 2.5 7 13.5"/>'),
  api: svg('<path d="M2.5 8h3l1.5-3 2 6 1.5-3h3"/>'),
  mcp: svg('<rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M5 7l2 1.5L5 10M8.5 10.5H11"/>'),
};

/* Who may set up a report by mail: owners and admins of a site with accounts (client_reports_api.py). */
export const mayMail = () => !DEMO.on && sessions() && (["owner", "admin"].includes(ME.role) || !!ME.install_admin);
const where = (s) => {
  const sec = S.sectionOf(s.tab);
  const tab = S.nameOf(s.tab);
  return sec && sec.name !== tab ? `${sec.name} › ${tab}` : tab;
};
// A page with figures: Settings, Help and About have none to print.
const hasFigures = (tab) => !!S.sectionOf(tab);

/* The choices, with only the ones this person may use. */
export function choices(m, s) {
  const r = rangeOf(m, s);
  const page = hasFigures(s.tab) ? `${where(s)}, ${rangeWords(r).toLowerCase()}, as on screen` : "Choose the sections";
  return [
    ["pdf", "A PDF of this page", page],
    ["csv", "The tables, as CSV", REGISTRY.length ? `${REGISTRY.length === 1 ? "The table" : `Each of the ${REGISTRY.length} tables`} on this page, or all in a ZIP` : "This page has no tables"],
    ...(mayMail() ? [["monthly", "A report someone gets every month", "A PDF by mail, with your logo"]] : []),
    ["tools", "Everything, for my own tools", "This page as JSON, the API or your AI assistant"],
  ];
}

export function openExport(m, s, loadView, { kind = "", change = false } = {}) {
  const offered = choices(m, s);
  const keys = offered.map(([k]) => k);
  // The address's choice, else the last one (when offered here), else the question alone.
  let now = [kindOf(kind), kind ? "" : lastKind()].find((k) => k && keys.includes(k)) || "";
  let open = !!change;
  const foot = h("div", { style: { display: "contents" } });
  const path = h("div", { class: "ui-who-path ex-path", "aria-live": "polite" });
  const list = h("div", { class: "ui-who-list", role: "radiogroup", "aria-label": "What do you need?" });
  const btns = offered.map(([k, title, sub]) => {
    const b = h("button", { type: "button", role: "radio", class: "ui-who-c", "data-kind": k, "aria-checked": "false" },
      h("span", { class: "ui-ic", html: ICONS[k] }), h("span", null, h("b", null, title), h("small", null, sub)));
    b.addEventListener("click", () => pick(k));
    b.addEventListener("keydown", (e) => {
      const i = keys.indexOf(k);
      const to = e.key === "ArrowDown" || e.key === "ArrowRight" ? keys[(i + 1) % keys.length]
        : e.key === "ArrowUp" || e.key === "ArrowLeft" ? keys[(i - 1 + keys.length) % keys.length] : null;
      if (!to) return;
      e.preventDefault();
      pick(to);
      list.querySelector(`[data-kind="${to}"]`)?.focus();
    });
    return b;
  });
  list.append(...btns);
  const ctx = { m, s, loadView, foot, close: () => d.close({ instant: true, focusBack: false }), isOpen: () => open, setOpen: (on) => { open = on; stepped(ROUTE.key, ROUTE.value, { xch: on ? "1" : "" }); } };
  function mark() {
    btns.forEach((b) => {
      const on = b.dataset.kind === now;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on || (!now && b === btns[0]) ? 0 : -1;
    });
  }
  function draw() {
    foot.replaceChildren();
    if (!now) { path.replaceChildren(); return; }
    const got = PATHS[now](ctx);
    Promise.resolve(got).then((nodes) => path.replaceChildren(...[nodes].flat(Infinity).filter((x) => x != null && x !== false && x !== "")));
  }
  function pick(k) {
    if (!keys.includes(k)) return;
    if (k !== now) { open = false; stepped(ROUTE.key, ROUTE.value, { kind: k, xch: "", by: "" }); }
    now = k;
    keepKind(k);
    mark();
    draw();
  }
  const head = h("div", { class: "ui-who" },
    h("div", { class: "ui-card-h" }, h("p", { class: "ui-who-q" }, "What do you need?"), help("Export", {
      text: ["Each file is made from verified whole days. A day that did not add up is left out, never shown as zero.",
        "A PDF: choose Save as PDF in the print dialog. Each section starts on a new page, with every row."],
      guide: "getting-started#export" })),
    list);
  const d = openDrawer({ title: "Export", subtitle: m.site, size: "md", key: "export", className: "ex-dw", body: [head, path], footer: [foot], route: ROUTE });
  // Written once the drawer has its key (a link without kind opens on the question).
  if (now) stepped(ROUTE.key, ROUTE.value, { kind: now, xch: open ? "1" : "" });
  mark();
  draw();
  d.pick = pick;
  return d;
}

// ---------------------------------------------------------------- the paths
const PATHS = { pdf: pdfPath, csv: csvPath, monthly: monthlyPath, tools: toolsPath };

const changeLine = (what, ctx, body) => {
  const box = h("div", { class: "ex-change", hidden: !ctx.isOpen() }, body);
  const btn = h("button", { type: "button", class: "btn link", "aria-expanded": String(ctx.isOpen()) }, "Change");
  btn.addEventListener("click", () => { const on = box.hidden; box.hidden = !on; btn.setAttribute("aria-expanded", String(on)); ctx.setOpen(on); });
  return [h("p", { class: "ex-what" }, h("span", null, "What is in it: "), what, " ", btn), box];
};

function pdfPath(ctx) {
  const { m, s, loadView } = ctx;
  const own = hasFigures(s.tab);
  const chosen = new Set(own ? [s.tab] : []);
  if (!own) ctx.setOpen(true);
  const what = h("b");
  const say = () => { what.textContent = chosen.size === 1 && chosen.has(s.tab) ? `this page (${where(s)})` : chosen.size ? `${chosen.size} section${chosen.size === 1 ? "" : "s"}` : "nothing yet: choose a section"; };
  const groups = S.MENU.map(([group, tabs]) => {
    const on = tabs.filter(S.shown);
    return on.length ? h("fieldset", { class: "ex-g" }, h("legend", null, group), on.map((k) => {
      const cb = h("input", { type: "checkbox", value: k, checked: chosen.has(k) });
      cb.addEventListener("change", () => { cb.checked ? chosen.add(k) : chosen.delete(k); say(); });
      return h("label", { class: "chk" }, cb, S.nameOf(k));
    })) : null;
  });
  const range = h("select", { "aria-label": "Period" }, S.RANGES.filter(([k]) => k !== "custom").map(([k, name]) => h("option", { value: k, selected: k === s.range }, name)),
    s.range === "custom" ? h("option", { value: "custom", selected: true }, `${s.from} to ${s.to}`) : null);
  const view = h("select", { "aria-label": "Page group" }, viewList(m).map(([k, name]) => h("option", { value: k, selected: k === (s.view || "all") }, name)));
  range.value = s.range;
  view.value = s.view || "all";
  const f = filtersOf(s);
  const keep = h("input", { type: "checkbox", checked: true });
  const lines = changeLine(what, ctx, [
    h("div", { class: "ex-groups" }, groups),
    h("div", { class: "ex-two" }, h("label", { class: "fld" }, "Period", range), h("label", { class: "fld" }, "Page group", view)),
    f.length ? h("label", { class: "chk" }, keep, `With the filters: ${f.map(([k, v]) => `${FILTER_WORDS[k]} ${k === "country" ? withFlag(v) : v}`).join(", ")}`) : null,
  ]);
  say();
  const next = () => ({ ...s, range: range.value, view: view.value });
  const go = (then) => async () => {
    if (!chosen.size) { say(); ctx.setOpen(true); lines[1].hidden = false; return; }
    await makeReport(m, next(), [...chosen], loadView, { then, keepFilters: keep.checked, close: ctx.close });
  };
  ctx.foot.append(h("button", { type: "button", class: "btn", onclick: go("preview") }, "Preview"), primary("Print or save as PDF", go("print"), { icon: ICON.download }));
  return lines;
}

function csvPath(ctx) {
  const { m, s } = ctx;
  if (!REGISTRY.length) return h("p", { class: "empty" }, "This page has no tables. Open a page with a table, or choose A PDF of this page.");
  const rows = REGISTRY.map((t) => {
    const name = t.file || `${slug(t.caption)}.csv`;
    const count = (() => { try { return t.rows().length; } catch { return null; } })();
    const get = h("button", { type: "button", class: "btn icon", html: ICON.download, "aria-label": `Download ${t.caption} as CSV`, title: "Download as CSV" });
    get.addEventListener("click", () => download(`${slug(m.site)}-${name.replace(/\.csv$/, "")}-${stamp()}.csv`, csv(t.columns, t.rows())));
    return h("li", { class: "ex-t" }, h("span", { class: "ui-ic", html: ICONS.csv }), h("span", { class: "ex-tn" }, h("b", null, t.caption), count == null ? null : h("small", null, `${n(count)} row${count === 1 ? "" : "s"}`)), get);
  });
  ctx.foot.append(primary("Download all (ZIP)", () => { exportZip(m, s); ctx.close(); }, { icon: ICON.download }));
  return [h("p", { class: "ui-meta" }, `With this page's period and filters: ${rangeWords(rangeOf(m, s)).toLowerCase()}.`), h("ul", { class: "ex-tables" }, rows)];
}

async function monthlyPath(ctx) {
  const { m, s } = ctx;
  const { call } = await import("./tabs/ipmanager.js");
  const r = await call("settings/reports");
  if (!r.ok) return h("p", { class: "msg err" }, r.error || "The reports could not be read.");
  const { mailServerNote, mailReady } = await import("./mail-ready.js");
  const { previewBox, downloadPdf } = await import("./tabs/reportform.js");
  const { status, why } = await import("./tabs/forms.js");
  const last = (r.reports || []).slice(-1)[0]?.spec;
  const to = h("input", { type: "email", multiple: true, spellcheck: "false", autocomplete: "email", placeholder: "client@example.com", value: (last?.recipients || []).join(", ") });
  const how = h("select", null, h("option", { value: "monthly" }, "Every month, on the 1st"), h("option", { value: "weekly" }, "Every week, on Monday"));
  to.value = (last?.recipients || []).join(", ");
  how.value = "monthly";
  // This page's part of the report: Overview is the summary; the others by their section.
  const PART = { overview: "summary", traffic: s.tab === "traffic/pages" ? "pages" : s.tab === "traffic/places" ? "places" : "sources", ai: "ai", sales: "leads" };
  const mine = PART[String(s.tab).split("/")[0]] || "summary";
  const want = new Set(["summary", mine]);
  const boxes = (r.sections || []).map((k) => {
    const off = k === "search_console" && !r.search_console;
    const cb = h("input", { type: "checkbox", value: k, checked: !off && want.has(k), disabled: off });
    cb.addEventListener("change", () => { cb.checked ? want.add(k) : want.delete(k); say(); });
    return h("label", { class: "chk" }, cb, r.section_words?.[k] || k);
  });
  const what = h("b");
  const say = () => { what.textContent = want.size <= 2 && want.has(mine) ? `this page (${where(s)})` : `${want.size} parts`; };
  const lines = changeLine(what, ctx, h("fieldset", { class: "ex-g" }, h("legend", null, "Parts of the report"), boxes));
  say();
  const body = () => {
    const monthly = how.value === "monthly";
    return { name: `${monthly ? "Monthly" : "Weekly"} report for ${m.site}`, recipients: to.value.split(/[\s,;]+/).filter(Boolean),
      schedule: monthly ? { kind: "monthly", day: 1, at: "08:00" } : { kind: "weekly", weekday: 0, at: "08:00" },
      period: monthly ? "last_month" : "last_week", sections: (r.sections || []).filter((k) => want.has(k)), notes: "", footer: "", agency_logo: true, paused: false };
  };
  const msg = status();
  const preview = previewBox();
  const look = h("button", { type: "button", class: "btn" }, "Preview");
  look.addEventListener("click", async () => {
    look.disabled = true; msg.textContent = "Building the report…"; msg.className = "msg";
    const got = await call("settings/report-preview", body());
    look.disabled = false;
    if (!got.ok) { msg.say(why(got, "The preview could not be built.")); return; }
    msg.say(""); preview.show(got);
  });
  const form = [h("label", { class: "fld" }, "Who gets it", to), h("label", { class: "fld" }, "How often", how), ...lines, msg, preview];
  if (mailReady(r) === false) {
    // No mail server: say so, offer the PDF now, and who sets the server up.
    ctx.foot.append(look, primary("Download the PDF now", () => downloadPdf(body(), msg), { icon: ICON.download }));
    return [mailServerNote(r, { what: "a report by mail", site: m.site, route: ROUTE }), ...form];
  }
  const start = primary("Start sending", async () => {
    const b = body();
    if (!b.recipients.length) { msg.say("Type who gets it."); to.focus(); return; }
    start.disabled = true;
    const got = await call("settings/report-save", b);
    start.disabled = false;
    if (!got.ok) { msg.say(why(got)); return; }
    const asked = got.confirm === "asked";
    ctx.foot.replaceChildren();
    const done = h("div", { class: "ui-card good" },
      h("div", { class: "ui-card-h" }, h("h3", null, "Done. The report is on its way.")),
      h("p", { class: "ui-meta" }, `${b.recipients.join(", ")} get${b.recipients.length === 1 ? "s" : ""} it ${how.value === "monthly" ? "every month, on the 1st" : "every Monday"}.${asked ? " Each new address gets a link to confirm first." : ""}`),
      h("p", null, h("a", { class: "btn", href: "#settings/site/mail?sub=reports" }, "See it in Client reports")));
    ctx.foot.append(h("button", { type: "button", class: "btn", onclick: ctx.close }, "Close"));
    form[0].parentNode?.replaceChildren(done);
  });
  ctx.foot.append(look, start);
  return form;
}

function toolsPath(ctx) {
  const { m, s } = ctx;
  const row = (icon, title, sub, href) => h("a", { class: "ui-card quiet ex-link", href },
    h("span", { class: "ui-ic", html: ICONS[icon] }), h("span", null, h("b", null, title), h("small", null, sub)));
  ctx.foot.append(primary("Download JSON", () => { exportJSON(m, s); ctx.close(); }, { icon: ICON.download }));
  return [h("p", { class: "ui-meta" }, `This page's tables and the period's totals, as one JSON file (${rangeWords(rangeOf(m, s)).toLowerCase()}).`),
    S.shown("settings/ai/assistants") ? row("api", "Read figures with the API", "A token, then any figure as JSON", "#settings/ai/assistants?sub=api") : null,
    S.shown("settings/ai/assistants") ? row("mcp", "Ask your AI assistant (MCP)", "Claude, ChatGPT or Cursor reads the figures", "#settings/ai/assistants?sub=mcp") : null];
}
