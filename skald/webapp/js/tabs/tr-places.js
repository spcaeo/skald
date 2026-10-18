// Traffic > Places & devices (2.7.0): visitors by device, browser, system and country.
//
// Devices, browsers and systems stay short cards (readers.js audience's figures);
// countries are one grid with their leads, the only country list in Traffic now
// (it replaces the "Countries" card and "All countries, with their leads").
// Cities (2.12.0) are a grid of their own under it: only where a city file is set
// (logs.city_db), from the days counted with it (people_city_visits).

import { h, n, share } from "../ui.js";
import { figures, ranked } from "../data.js";
import { link, drillRow } from "../drill.js";
import { grid } from "../grid.js";
import { head, nothing, blist, panel, fileName } from "./common.js";
import { country, city, cityCode } from "./readers.js";
import { leadsBy, leadNote, viewNote } from "./leadfigs.js";
import { leadRows, labelCol, countCols, leadCols, countRows, compareOf, compareRows, compareCols, compareNote } from "./tr-grid.js";
import { noCompare } from "../mode-compare.js";

const TOUCH = "the lead's country, from the tool or the visitor's address";
const only = (value) => (value ? (k) => k === value : () => true);

// The country grid's columns, in one place (compare mode adds B and ± here).
// The CSV writes each country's full name and its code (table.js, country:).
export const countryColumns = (leads, c) => [{ ...labelCol("Country"), country: (x) => x.k },...countCols("Visitors"), ...compareCols(c), ...(leads ? leadCols() : [])];

// Devices as one bar of parts, as readers.js draws it (not exported there).
const DEVICE_TONES = { Desktop: "var(--g-people)", Mobile: "var(--views)", Tablet: "var(--g-bots)" };
function meter(obj, whole, pick) {
  const rows = ranked(obj);
  if (!rows.length) return h("p", { class: "empty" }, "None recorded.");
  return h("div", null,
    h("div", { class: "meter", role: "img", "aria-label": rows.map(([k, v]) => `${k} ${n(v)}`).join(", ") },
      rows.map(([k, v]) => h("i", { style: { flexGrow: String(v), background: DEVICE_TONES[k] || "var(--ink-3)", opacity: pick && pick !== k ? ".3" : "1" } }))),
    h("ul", { class: "legend", style: { marginTop: "10px" } }, rows.map(([k, v]) => {
      const li = h("li", null, h("span", { class: "sw", style: { background: DEVICE_TONES[k] || "var(--ink-3)" } }), link("device", k), ` ${n(v)}${share(v, whole) ? ` (${share(v, whole)})` : ""}`);
      drillRow(li);   // the whole line opens the device (drill.js)
      return li;
    })));
}

function unmeasured(t) {
  return t.unmeasured?.by ? h("p", { class: "note" }, `${t.unmeasured.by} of these days were collected before breakdowns existed. They are left out of every list here, so the lists add up to fewer visitors than the headline.`) : null;
}

/* Visitors by city: each visitor's city at their first page. Only the days
   counted with a city file hold cities; a range with others says how many. */
function cities(m, s, r, t, c, credit) {
  const ok = r.kind === "today" ? [] : r.days.filter((d) => d.state === "ok" && d.by);
  const without = ok.filter((d) => !d.by.city).length;
  const obj = t.by.city || {};
  const keep = s.country ? (k) => cityCode(k) === s.country : () => true;
  const sub = h("p", { class: "sub" }, "Each visitor's city at their first page, from the city file (DB-IP's free city file). A city is the city's own point on the map, never the visitor's street; Not recorded when the file had no city for the address, or named one in another country than the visit's.");
  if (!Object.values(obj).some(Boolean)) {
    const why = m.cities
      ? "No city is recorded in this range yet: cities are counted from the first day the city file was set."
      : "Cities are not recorded: no city file is set. Set logs.city_db (in Docker, SKALD_CITY_DB) to DB-IP's free \"IP to City Lite\" file; Help > Getting started > Cities says how.";
    return h("section", { class: "s" }, h("h2", null, "Cities"), sub, h("p", { class: "empty" }, why));
  }
  const whole = Object.values(obj).reduce((a, v) => a + (v || 0), 0);
  const g = grid({ ns: "cy", caption: "Visitors by city", file: fileName("cities", r), columns: [labelCol("City"), ...countCols("Visitors"), ...compareCols(c)],
    rows: compareRows(c, countRows(obj, { dim: "city", keep, label: city, whole }), c.bT?.by?.city, { dim: "city", keep, label: city, whole }), sortKey: "v",
    placeholder: "Search cities", empty: s.country ? "No visitor from a city of this country in this range." : "No city recorded." });
  g.classList.add("tr-grid", "lead-tbl");
  const part = without ? h("p", { class: "note" }, `${without} of these ${ok.length} days were counted before the city file was set: the cities hold the visitors of the other ${ok.length - without} day${ok.length - without === 1 ? "" : "s"} only.`) : null;
  return h("section", { class: "s" }, h("h2", null, "Cities"), sub, g, compareNote(c), part, credit);
}

export default function places(m, s) {
  const { r, t } = figures(m, s);
  const out = [...head("Places & devices", r, "Visitors by country, city, device, browser and system, each counted once, at their first page. Browser, system and device are what the browser says about itself.")];
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
    h("p", { class: "sub" }, "From the log's country field, or the GeoIP file for a line without one; Not recorded when neither had it, never guessed."),
    g, compareNote(c), lb ? leadNote(lb, TOUCH) : null, viewNote(m, s), credit));
  out.push(cities(m, s, r, t, c, credit ? credit.cloneNode(true) : null));
  out.push(unmeasured(t));
  return out;
}
