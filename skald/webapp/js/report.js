// Exports and reports. "Export" in the top bar: every table on this tab as
// one ZIP of CSV files, the same as JSON, a printable report of this tab,
// and the report builder - pick tabs, period, page group and filters, then
// preview, print (or save as PDF from the print dialog) or download.
//
// A report is the tabs themselves, drawn once more into #report with every
// table row shown, under a title page: what, when, which filters.

import { h, n, long, toast, ICON } from "./ui.js";
import * as S from "./state.js";
import { rangeOf, viewList, figures } from "./data.js";
import { TAB_RENDER } from "./tabs/index.js";
import { REGISTRY, csv, download, showAllRows } from "./table.js";
import { zip } from "./zip.js";
import { shown, shownKeys } from "./labels.js";
import { rangeWords, setContext } from "./tabs/common.js";
import { withFlag } from "./tabs/readers.js";
import { decode, treeWords } from "./rules.js";
import { BUILD, buildLine, toolName, toolTagline } from "./build.js";
import { openDrawer } from "./drawer.js";

const FILTER_WORDS = { country: "Country", path: "Page path", source: "Source", device: "Device", browser: "Browser", campaign: "Campaign", referrer: "Referring site", rules: "Rules" };
const slug = (x) => String(x).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "table";
const tabName = (k) => S.nameOf(k);
const stamp = () => new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "").replace(/^(\d{8})(\d{4})$/, "$1-$2");

// The tables a render registered, as files: [{name, data}] under an optional folder.
function tableFiles(regs, folder = "") {
  return regs.map((t) => ({ name: `${folder}${t.file || `${slug(t.caption)}.csv`}`, data: csv(t.columns, t.rows()) }));
}
function tableJSON(regs) {
  return regs.map((t) => ({
    caption: t.caption, file: t.file || null, columns: t.columns.map((c) => c.label),
    rows: t.rows().map((r) => Object.fromEntries(t.columns.map((c) => [c.label, shown(c.csv ? c.csv(r) : r[c.key] ?? null)]))),
  }));
}
// The single filters, then the advanced rules in words (js/rules.js).
function filtersOf(s) {
  const out = S.FILTERS.filter((k) => s[k]).map((k) => [k, s[k]]);
  const rules = decode(s.rules);
  if (rules.items.length) out.push(["rules", treeWords(rules, (d, v) => (d === "country" ? withFlag(v) : v))]);
  return out;
}
function meta(m, s) {
  const r = rangeOf(m, s);
  return { site: m.site, view: viewList(m).find(([k]) => k === (s.view || "all"))?.[1] || s.view, period: r.kind === "today" ? { today: m.today } : { first: r.first, last: r.last, days: r.length },
    filters: Object.fromEntries(filtersOf(s).map(([k, v]) => [k, shown(v)])), compare: !!s.cmp, timezone: m.tz, exported_at: new Date().toISOString(),
    tool: BUILD ? { name: BUILD.name, version: BUILD.version, release: BUILD.release, commit: BUILD.commit } : null };
}

// ----------------------------------------------------------- one tab
export function exportZip(m, s) {
  if (!REGISTRY.length) return toast("This tab has no tables to export.");
  const files = tableFiles(REGISTRY);
  files.push({ name: "README.txt", data: readme(m, s, [s.tab]) });
  download(`${slug(m.site)}-${s.tab}-${stamp()}.zip`, zip(files));
}
export function exportJSON(m, s) {
  const t = figures(m, s).t;
  const body = { ...meta(m, s), tab: s.tab, totals: t ? strip(t) : null, tables: tableJSON(REGISTRY) };
  download(`${slug(m.site)}-${s.tab}-${stamp()}.json`, JSON.stringify(body, null, 2), "application/json");
}
// Range totals without the per-day bookkeeping the app adds.
function strip(t) { const { unmeasured, days, ...rest } = t; return { days_counted: days, ...shownKeys(rest) }; }

function readme(m, s, tabs) {
  const md = meta(m, s);
  return [`Traffic report for ${m.site}`, `Tabs: ${tabs.map(tabName).join(", ")}`, ...(BUILD ? [`Made with ${buildLine()}`] : []),
    `Period: ${md.period.today ? `today so far (${md.period.today})` : `${md.period.first} to ${md.period.last} (${md.period.days} days)`}`,
    `Page group: ${md.view}`, `Filters: ${filtersOf(s).map(([k, v]) => `${FILTER_WORDS[k]} ${v}`).join(", ") || "none"}`,
    `Time zone: ${m.tz}`, `Exported: ${md.exported_at}`, "",
    "Figures come from verified whole days only; withheld, partial and missing days are left out, never counted as zero.",
    "A cell starting with = + - or @ is prefixed with an apostrophe so a spreadsheet does not run it."].join("\r\n");
}

// ------------------------------------------------------------ the report
const reportEl = () => document.getElementById("report") || document.body.appendChild(h("div", { id: "report", hidden: true }));

function cover(m, s, tabs) {
  const r = rangeOf(m, s);
  const f = filtersOf(s);
  return h("header", { class: "r-cover" },
    h("p", { class: "r-site" }, `${toolName()}${toolTagline() ? `: ${toolTagline()}` : ""}`),
    h("p", { class: "r-for" }, m.site),
    h("h1", null, tabs.length === 1 ? `${tabName(tabs[0])} report` : "Traffic report"),
    h("dl", null,
      h("dt", null, "Period"), h("dd", null, r.kind === "today" ? `Today so far, ${long(m.today)}` : `${long(r.first)} to ${long(r.last)} (${n(r.length)} days)`),
      h("dt", null, "Page group"), h("dd", null, viewList(m).find(([k]) => k === (s.view || "all"))?.[1] || s.view),
      h("dt", null, "Filters"), h("dd", null, f.length ? f.map(([k, v]) => `${FILTER_WORDS[k]}: ${k === "country" ? withFlag(v) : v}`).join("; ") : "none"),
      h("dt", null, "Sections"), h("dd", null, tabs.map(tabName).join(", ")),
      h("dt", null, "Prepared"), h("dd", null, `${new Date().toLocaleString("en-US", { dateStyle: "long", timeStyle: "short" })}, times in ${m.tz}`),
      BUILD ? h("dt", null, "Version") : null, BUILD ? h("dd", null, buildLine()) : null),
    h("p", { class: "r-note" }, "From the server's own access log. Figures come from verified whole days; a day that did not add up is withheld and left out, never shown as zero."));
}

/* Draw the chosen tabs into #report. Returns {el, files} - files are each
   tab's tables, in a folder per tab, for the ZIP. */
function build(m, s, tabs) {
  const el = reportEl();
  const doc = h("div", { class: "r-doc" }, cover(m, s, tabs));
  const files = [], start = REGISTRY.length;
  showAllRows(true);
  try {
    for (const tab of tabs) {
      const before = REGISTRY.length;
      const sT = { ...s, tab, dd: "", page: "" };
      setContext(m, sT);
      let body;
      try { body = TAB_RENDER[tab](m, sT, { first: false }); } catch (e) { body = h("p", { class: "empty" }, `This section could not be drawn: ${e.message || e}`); }
      const sec = h("section", { class: "r-tab" }, h("p", { class: "r-crumb" }, `${m.site}, ${rangeWords(rangeOf(m, sT))}`), ...[body].flat(Infinity).filter(Boolean));
      // A report is read, not used: strip the controls a reader cannot press on paper.
      sec.querySelectorAll(".tbl-tools input, .tbl-tools .btn, .more-rows, .rq-bar, .feed-tools").forEach((x) => x.remove());
      doc.append(sec);
      files.push(...tableFiles(REGISTRY.slice(before), `${tab}/`));
    }
  } finally {
    // The report's tables are not the tab's: "Export" on the tab keeps taking only its own.
    REGISTRY.length = start;
    showAllRows(false);
  }
  files.push({ name: "README.txt", data: readme(m, s, tabs) });
  el.replaceChildren(doc);
  return { el, files };
}

function preview(m, s, tabs) {
  const { el, files } = build(m, s, tabs);
  // Closing redraws the tab: a section drawn into the report may have taken over a shared clock (the request log's).
  const close = () => { el.hidden = true; document.body.classList.remove("reporting"); el.replaceChildren(); S.emit(true); };
  const bar = h("div", { class: "r-bar" },
    h("b", null, "Report preview"), h("span", { class: "grow" }),
    h("button", { type: "button", class: "btn primary", onclick: () => print() }, "Print or save as PDF"),
    h("button", { type: "button", class: "btn", html: ICON.download, onclick: () => download(`${slug(m.site)}-report-${stamp()}.zip`, zip(files)) }, "Tables (ZIP)"),
    h("button", { type: "button", class: "btn", onclick: close }, "Close"));
  el.prepend(bar);
  el.hidden = false;
  document.body.classList.add("reporting");
  el.scrollTop = 0;
  bar.querySelector(".btn.primary").focus();
  el.onkeydown = (e) => { if (e.key === "Escape") close(); };
  return close;
}

export function printTab(m, s) {
  const close = preview(m, s, [s.tab]);
  addEventListener("afterprint", close, { once: true });
  // Give the charts a frame to lay out before the print dialog freezes the page.
  requestAnimationFrame(() => setTimeout(() => print(), 60));
}

// ------------------------------------------------------- report builder
export function builder(m, s, loadView) {
  let d = null;
  const chosen = new Set([s.tab]);
  // The dashboard's tabs, by section (settings pages have no figures to report).
  const boxes = [];
  const groups = S.MENU.map(([group, keys]) => {
    const on = keys.filter(S.shown);
    return on.length ? h("div", { class: "rb-g", role: "group", "aria-label": group }, h("p", { class: "rb-gh" }, group), on.map((k) => {
      const cb = h("input", { type: "checkbox", value: k, checked: chosen.has(k) });
      cb.addEventListener("change", () => { cb.checked ? chosen.add(k) : chosen.delete(k); count(); });
      const box = h("label", { class: "rb-tab" }, cb, tabName(k));
      boxes.push(box);
      return box;
    })) : null;
  });
  if (S.inSettings(s.tab)) chosen.delete(s.tab);
  const note = h("p", { class: "note", "aria-live": "polite" });
  const count = () => { note.textContent = chosen.size ? `${chosen.size} section${chosen.size === 1 ? "" : "s"} chosen.` : "Choose at least one section."; };
  const all = (on) => { boxes.forEach((l) => { const cb = l.querySelector("input"); cb.checked = on; on ? chosen.add(cb.value) : chosen.delete(cb.value); }); count(); };
  const range = h("select", { "aria-label": "Period" }, S.RANGES.filter(([k]) => k !== "custom").map(([k, name]) => h("option", { value: k, selected: k === s.range }, name)),
    s.range === "custom" ? h("option", { value: "custom", selected: true }, `${s.from} to ${s.to}`) : null);
  const view = h("select", { "aria-label": "Page group" }, viewList(m).map(([k, name]) => h("option", { value: k, selected: k === (s.view || "all") }, name)));
  const f = filtersOf(s);
  const keep = h("input", { type: "checkbox", checked: true });
  const cmp = h("input", { type: "checkbox", checked: !!s.cmp });
  const settings = async () => {
    const next = { ...s, range: range.value, view: view.value, cmp: cmp.checked ? "prev" : "" };
    if (!keep.checked) { for (const k of S.FILTERS) next[k] = ""; next.rules = ""; }
    const model = view.value === (s.view || "all") ? m : await loadView(next);
    return [model, next, S.TABS.map(([k]) => k).filter((k) => chosen.has(k))];
  };
  const act = (fn) => async () => {
    if (!chosen.size) { count(); return; }
    const [model, next, tabs] = await settings();
    // At once: the preview takes the focus, and a closing drawer would still hold the page inert.
    d.close({ instant: true, focusBack: false });
    fn(model, next, tabs);
  };
  const body = [
    h("fieldset", { class: "dw-sec" }, h("legend", null, "Sections"), h("div", { class: "rb-tabs" }, groups),
      h("div", { class: "dw-actions" }, h("button", { type: "button", class: "btn", onclick: () => all(true) }, "Choose all"), h("button", { type: "button", class: "btn", onclick: () => all(false) }, "Clear"), note)),
    h("section", { class: "dw-sec" }, h("h3", null, "Period and filters"),
      h("div", { class: "rb-grid" }, h("label", { class: "fld" }, "Period", range), h("label", { class: "fld" }, "Page group", view)),
      h("div", { class: "rb-checks" },
        h("label", { class: "rb-check" }, keep, f.length ? `Apply the current filters: ${f.map(([k, v]) => `${FILTER_WORDS[k]} ${k === "country" ? withFlag(v) : v}`).join(", ")}` : "Apply the current filters (none set)"),
        h("label", { class: "rb-check" }, cmp, "Compare to the previous period, where both are whole"))),
    h("p", { class: "note" }, "To make a PDF, choose \"Save as PDF\" as the printer in the print dialog. Each section starts on a new page; every table row is printed."),
  ];
  const footer = [
    h("button", { type: "button", class: "btn", html: ICON.download, onclick: act((mm, ss, tabs) => { const { files, el } = build(mm, ss, tabs); el.replaceChildren(); download(`${slug(mm.site)}-report-${stamp()}.zip`, zip(files)); }) }, "Tables (ZIP)"),
    h("button", { type: "button", class: "btn", onclick: act((mm, ss, tabs) => { preview(mm, ss, tabs); requestAnimationFrame(() => setTimeout(() => print(), 60)); }) }, "Print or save as PDF"),
    h("button", { type: "button", class: "btn primary", onclick: act((mm, ss, tabs) => preview(mm, ss, tabs)) }, "Preview"),
  ];
  d = openDrawer({ title: "Report builder", subtitle: "Choose the sections, the period and the filters; then preview, print or download the tables.", size: "md", className: "dw-rb", key: "report", body, footer });
  count();
}

// --------------------------------------------------------- the menu
let openMenu = null;
document.addEventListener("pointerdown", (e) => { if (openMenu && !openMenu.wrap.contains(e.target)) openMenu.close(); });

export function exportMenu(getModel, s, loadView) {
  const toggle = h("button", { type: "button", class: "btn x-btn", "aria-expanded": "false", "aria-haspopup": "menu", "aria-label": "Export", title: "Export", html: ICON.download }, h("span", { class: "x-l" }, "Export"));
  const item = (text, sub, fn) => h("button", { type: "button", role: "menuitem", class: "menu-i", onclick: () => { close(); fn(); } }, h("b", null, text), h("small", null, sub));
  const menu = h("div", { class: "pop menu", role: "menu", hidden: true, "aria-label": "Export" },
    item("Tables on this tab (ZIP)", "every table, with the current filters, as CSV files", () => exportZip(getModel(), s)),
    item("This tab as JSON", "the same tables and the range's totals", () => exportJSON(getModel(), s)),
    item("Print this tab", "a clean report; choose Save as PDF to keep it", () => printTab(getModel(), s)),
    item("Report builder", "choose sections, period, page group and filters", () => builder(getModel(), s, loadView)));
  const wrap = h("div", { class: "more" }, toggle, menu);
  const close = () => { menu.hidden = true; toggle.setAttribute("aria-expanded", "false"); openMenu = null; };
  toggle.addEventListener("click", () => {
    if (!menu.hidden) return close();
    menu.hidden = false;
    menu.classList.remove("from-left");
    if (menu.getBoundingClientRect().left < 8) menu.classList.add("from-left");
    toggle.setAttribute("aria-expanded", "true");
    openMenu = { wrap, close };
    menu.querySelector("button")?.focus();
  });
  menu.addEventListener("keydown", (e) => {
    const items = [...menu.querySelectorAll(".menu-i")], i = items.indexOf(document.activeElement);
    if (e.key === "Escape") { close(); toggle.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
  });
  return wrap;
}
