// Exports and reports. "Export" in the top bar: every table on this tab as
// one ZIP of CSV files, the same as JSON, a printable report of this tab,
// and a report of several tabs (2.42: the Export dialog, export-dialog.js), then
// preview, print (or save as PDF from the print dialog) or download.
//
// A report is the tabs themselves, drawn once more into #report with every
// table row shown, under a title page: what, when, which filters.

import { h, n, long, toast, ICON } from "./ui.js";
import * as S from "./state.js";
import { rangeOf, viewList, figures, need } from "./data.js";
import { TAB_RENDER } from "./tabs/index.js";
import { REGISTRY, csv, download, showAllRows } from "./table.js";
import { zip } from "./zip.js";
import { shown, shownKeys } from "./labels.js";
import { rangeWords, setContext } from "./tabs/common.js";
import { withFlag } from "./tabs/readers.js";
import { decode, treeWords } from "./rules.js";
import { BUILD, buildLine, toolName, toolTagline } from "./build.js";

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

// ------------------------------------------------------------ several tabs
// 2.42: the report builder became the Export dialog's "A PDF of this page" (export-dialog.js):
// this page by default, more sections behind "Change". makeReport is what its buttons do.

/* The sections chosen, as a report: then "print" (the print dialog, Save as PDF), "preview"
   (the report on screen, with Print and Tables (ZIP)) or "zip" (the tables only).
   keepFilters false: the report without the current filters. */
export async function makeReport(m, s, tabs, loadView, { then = "print", keepFilters = true, close = null } = {}) {
  const next = { ...s };
  if (!keepFilters) { for (const k of S.FILTERS) next[k] = ""; next.rules = ""; }
  const model = (next.view || "all") === (s.view || "all") ? m : await loadView(next);
  const want = S.TABS.map(([k]) => k).filter((k) => tabs.includes(k));
  if (!want.length) return false;
  // A report is drawn once: every big file its sections and their panels stand on, first (data.js LAZY).
  const { tabFiles } = await import("./sections.js");
  await need(model, want.flatMap((t) => tabFiles(t, next, { panels: true }))).catch(() => null);
  // At once: the preview takes the focus, and a closing drawer would still hold the page inert.
  if (close) close();
  if (then === "zip") { const { files, el } = build(model, next, want); el.replaceChildren(); download(`${slug(model.site)}-report-${stamp()}.zip`, zip(files)); return true; }
  preview(model, next, want);
  if (then === "print") requestAnimationFrame(() => setTimeout(() => print(), 60));
  return true;
}

export { filtersOf, FILTER_WORDS, slug, stamp };
