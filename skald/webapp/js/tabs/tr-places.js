// Traffic > Places & devices (2.7.0): visitors by device, browser, system and country.
//
// Devices, browsers and systems stay short cards (readers.js audience's figures);
// countries are one grid with their leads, the only country list in Traffic now
// (it replaces the "Countries" card and "All countries, with their leads").

import { h, n, share } from "../ui.js";
import { figures, ranked } from "../data.js";
import { link } from "../drill.js";
import { grid } from "../grid.js";
import { head, nothing, blist, panel, fileName } from "./common.js";
import { country } from "./readers.js";
import { leadsBy, leadNote, viewNote } from "./leadfigs.js";
import { leadRows, labelCol, countCols, leadCols, compareOf, compareRows, compareCols, compareNote } from "./tr-grid.js";
import { noCompare } from "../mode-compare.js";

const TOUCH = "the lead's country, from the tool or the visitor's address";
const only = (value) => (value ? (k) => k === value : () => true);

// The country grid's columns, in one place (compare mode adds B and ± here).
export const countryColumns = (leads, c) => [labelCol("Country"), ...countCols("Visitors"), ...compareCols(c), ...(leads ? leadCols() : [])];

// Devices as one bar of parts, as readers.js draws it (not exported there).
const DEVICE_TONES = { Desktop: "var(--g-people)", Mobile: "var(--views)", Tablet: "var(--g-bots)" };
function meter(obj, whole, pick) {
  const rows = ranked(obj);
  if (!rows.length) return h("p", { class: "empty" }, "None recorded.");
  return h("div", null,
    h("div", { class: "meter", role: "img", "aria-label": rows.map(([k, v]) => `${k} ${n(v)}`).join(", ") },
      rows.map(([k, v]) => h("i", { style: { flexGrow: String(v), background: DEVICE_TONES[k] || "var(--ink-3)", opacity: pick && pick !== k ? ".3" : "1" } }))),
    h("ul", { class: "legend", style: { marginTop: "10px" } }, rows.map(([k, v]) => h("li", null,
      h("span", { class: "sw", style: { background: DEVICE_TONES[k] || "var(--ink-3)" } }), link("device", k), ` ${n(v)}${share(v, whole) ? ` (${share(v, whole)})` : ""}`))));
}

function unmeasured(t) {
  return t.unmeasured?.by ? h("p", { class: "note" }, `${t.unmeasured.by} of these days were collected before breakdowns existed. They are left out of every list here, so the lists add up to fewer visitors than the headline.`) : null;
}

export default function places(m, s) {
  const { r, t } = figures(m, s);
  const out = [...head("Places & devices", r, "Visitors by country, device, browser and system, each counted once, at their first page. Browser, system and device are what the browser says about itself.")];
  if (!t || !t.by) return [...out, nothing(m, r, "breakdowns")];
  const c = compareOf(m, s);
  out.push(noCompare(s, "devices, browsers and systems show this period only; countries below are set against B"));
  out.push(h("div", { class: "cols three" },
    panel("Devices", null, meter(t.by.device, t.readers, s.device)),
    panel("Browsers", "Brave counts as Chrome; an in-app browser by its app", blist(ranked(t.by.browser, only(s.browser)), { drill: "browser", total: t.readers, limit: 8, color: "var(--views)" })),
    panel("Systems", "An iPad asking for the desktop site counts as macOS", blist(ranked(t.by.os), { drill: "os", total: t.readers, limit: 8, color: "var(--ink-3)" }))));
  const lb = leadsBy(m, s, r, t, "country");
  const leads = !!(lb && lb.days);
  const g = grid({ ns: "ct", caption: "Visitors by country", file: fileName("countries", r), columns: countryColumns(leads, c),
    rows: compareRows(c, leadRows(t.by.country, lb, { dim: "country", keep: only(s.country), label: country, whole: t.readers }), c.bT?.by?.country,
      { dim: "country", keep: only(s.country), label: country, whole: t.readers }), sortKey: "v",
    placeholder: "Search countries", empty: s.country ? "No visitor from this country in this range." : "No country recorded." });
  g.classList.add("tr-grid", "lead-tbl");
  const credit = m.credit ? h("p", { class: "note" }, h("a", { href: m.credit.url || null, rel: "noreferrer" }, m.credit.text)) : null;
  out.push(h("section", { class: "s" }, h("h2", null, "Countries, with their leads"),
    h("p", { class: "sub" }, "From the log's country field; Not recorded when it had none, never guessed."),
    g, compareNote(c), lb ? leadNote(lb, TOUCH) : null, viewNote(m, s), credit));
  out.push(unmeasured(t));
  return out;
}
