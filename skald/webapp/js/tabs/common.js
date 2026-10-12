// Pieces several tabs share: the heading with its range, the coverage line,
// the "nothing to show" states and the bar lists.

import { h, n, short, long, clock, pct1, stateNote, reduced, ICON } from "../ui.js";
import { ranked, comparison, ghostDay, coverage } from "../data.js";
import { table } from "../table.js";
import * as S from "../state.js";
import { link } from "../drill.js";
import { info } from "./tiles.js";
import { time as tzTime, sameAsSite, siteZone, city, daysNote } from "../tz.js";

export function rangeWords(r) {
  if (r.kind === "today") return "Today so far";
  if (r.length === 1) return long(r.first);
  return `${short(r.first)} to ${short(r.last)}, ${r.length} days`;
}

// The model and state of the draw under way, so every header can name the period and page group the same way.
let CTX = { m: null, s: null };
export function setContext(m, s) { CTX = { m, s }; }

/* The one line that says what every number on the page covers: the period,
   the clock for today, how many days are whole, and the page group. */
export function periodWords(r, cov) {
  const { m, s } = CTX;
  const bits = [];
  if (r.kind === "today") {
    const L = m?.live;
    const day = sameAsSite() ? short(m.today) : `${short(m.today)} (${city(siteZone())} day)`;
    bits.push(L && L.day === m.today && L.generated_at ? `Today, ${day}, ${tzTime(L.from, { label: false })} to ${tzTime(L.generated_at)}` : `Today, ${day}`);
  } else {
    const preset = s && s.range !== "custom";
    bits.push(r.length === 1 ? long(r.first) : preset ? `Last ${r.length} whole days, ${short(r.first)} to ${short(r.last)}` : `${short(r.first)} to ${short(r.last)}, ${r.length} days`);
    if (cov) bits.push(cov.complete ? "every day whole and verified" : `${cov.ok} whole day${cov.ok === 1 ? "" : "s"} recorded, ${r.length - cov.ok} not`);
  }
  const views = m ? [["all", "All pages"], ...(m.views || []).map((v) => [v.slug, v.name])] : [];
  bits.push((views.find(([k]) => k === (s?.view || "all")) || [null, "All pages"])[1]);
  if (daysNote()) bits.push(daysNote());
  return bits.join(" · ");
}

/* The honest banner: a range with some days missing says, once, at the top,
   what its totals cover. A range with no whole day says it in nothing(). */
export function periodBanner(r, cov) {
  if (!cov || r.kind === "today" || cov.complete || !cov.ok) return null;
  const left = [];
  if (cov.partial.length) left.push(`${cov.partial.map(short).join(", ")} (partial)`);
  if (cov.withheld.length) left.push(`${cov.withheld.map(short).join(", ")} (did not add up)`);
  if (cov.missing.length) left.push(`${cov.missing.length} day${cov.missing.length === 1 ? "" : "s"} not collected`);
  if (cov.before) left.push(`${cov.before} day${cov.before === 1 ? "" : "s"} before history began`);
  return h("div", { class: "period-banner", role: "note", html: ICON.info },
    h("div", null, `${r.length} days selected: ${cov.ok} ${cov.ok === 1 ? "is" : "are"} whole and verified, so every total here covers ${cov.ok} day${cov.ok === 1 ? "" : "s"}. Left out, never counted as zero: ${left.join("; ")}.`));
}

/* A tab's header: title, the period line, and the banner when days are
   missing. opts.cov: the range's coverage; opts.banner false for tabs that
   do not total days (data quality, leads); opts.period: words for a tab
   the date range does not govern (alerts, the request log); opts.shown:
   the title shown on the page (a settings page), not only in the top bar. */
export function head(title, r, lede, opts = {}) {
  const cov = opts.cov ?? (r.kind === "history" && r.days ? coverage(r) : null);
  // The header is one line: the title, its help behind an (i), and the period.
  return [
    h("div", { class: opts.shown ? "head shown" : "head" }, h("h1", null, title), lede ? info(lede, title) : null,
      h("span", { class: "period" }, r.kind === "today" && !opts.period ? h("span", { class: "pulse", "aria-hidden": "true" }) : null, opts.period || periodWords(r, cov))),
    opts.banner === false ? null : periodBanner(r, cov),
  ];
}

/* Site health's sub-tabs: Health, Alerts (with its open count), Data quality.
   One section in the sidebar; three pages under it. */
export function healthTabs(m, key) {
  const open = (m.x?.alerts?.open || []).length;
  return h("nav", { class: "subtabs", "aria-label": "Site health" }, [["health", "Health"], ["health/alerts", "Alerts"], ["health/quality", "Data quality"], ["health/speed", "Page speed"], ["health/broken", "Broken links"]].map(([k, name]) =>
    h("a", { href: `#${k}`, class: "subtab", "aria-current": k === key ? "page" : null }, name,
      k === "health/alerts" && open ? h("span", { class: "tab-n", "aria-label": `${open} open` }, String(open)) : null)));
}

// A part whose data file could not be built on the last redraw: said so, never shown empty.
export function notBuiltNote(m, file, what) {
  const err = m.failed?.[file];
  return err ? h("div", { class: "state warn" }, h("div", null, h("strong", null, `${what} could not be built on the last redraw. `), `${file}.json failed: ${err}. Data quality lists it; the next redraw tries again.`)) : null;
}

// The footnote under a tab's figures: the period line and the banner say it all now, so nothing is repeated here.
export function coverageNote() { return null; }

/* A part kept for a fixed period of its own (the last 30 days, the visits'
   last days) that the date range cannot change: folded at the bottom, its
   period in its title, so no card above carries a date of its own. */
export function fixed(title, period, ...body) {
  return h("details", { class: "fold fixed" }, h("summary", null, title, h("span", null, `${period} · not the date range above`)), ...body);
}

// What a tab shows when the chosen range has nothing it may show.
export function nothing(m, r, what = "figures") {
  if (r.kind === "today") {
    const L = m.live;
    if (!L || L.day !== m.today) return stateNote(`No live ${what} for today yet. The live count runs every two minutes; press Refresh now to run it at once.`);
    if (L.state === "withheld") return stateNote(`Withheld: today's ${what} so far do not add up, so none are shown. ${(L.problems || []).join(" ")}`, true);
    if (L.state === "empty") return stateNote("No requests logged yet today.");
  }
  const days = r.days || [];
  const partial = days.filter((d) => d.state === "partial").map((d) => `${short(d.day)}${d.partial ? ` (${d.partial})` : ""}`);
  const withheld = days.filter((d) => d.state === "withheld").length;
  const before = days.filter((d) => d.state === "before" || d.state === "missing").length;
  const left = [partial.length ? `${partial.join(", ")} ${partial.length === 1 ? "is" : "are"} partial` : "",
    withheld ? `${withheld} did not add up` : "", before ? `${before} ${before === 1 ? "was" : "were"} not collected (history begins ${short(m.firstDay || r.first)})` : ""].filter(Boolean);
  const note = stateNote(`${r.length} day${r.length === 1 ? "" : "s"} selected, and none is a whole, verified day yet: ${left.join("; ") || "nothing was recorded"}. Totals would cover 0 days, so no ${what} are shown rather than zeros.`);
  const live = m.live && m.live.day === m.today && m.live.state === "ok";
  if (live) note.lastChild.append(" ", h("button", { type: "button", class: "btn", onclick: () => S.set({ range: "today" }) }, "Show today so far"));
  return note;
}

// Ranked labels with a proportional bar behind each. rows: [[label, n, extra?]]
/* drill: the dimension the labels are (country, path, source...): each label
   then opens its detail, with its mark. from: "drill" inside the detail view. */
export function blist(rows, { color = "var(--g-people)", total, limit = 10, label = (x) => x, empty = "None recorded.", change, drill, from, value = (k) => k } = {}) {
  if (!rows.length) return h("p", { class: "empty" }, empty);
  const max = rows[0][1] || 1, sum = total ?? rows.reduce((s, r) => s + r[1], 0);
  const ul = h("ul", { class: `blist${reduced() ? "" : " play"}` });
  rows.slice(0, limit).forEach(([k, v], i) => {
    const bar = h("span", { class: "bl-bar", style: { width: `${(v / max) * 100}%`, background: color, animationDelay: `${i * 0.03}s` } });
    // A row may carry a third item: the value to drill into, when its label is not the value itself.
    const lab = drill ? link(drill, value(k), { from, text: typeof label(k) === "string" && label(k) !== value(k) ? label(k) : undefined }) : label(k);
    ul.append(h("li", null, bar, h("span", { class: "bl-l", title: typeof lab === "string" ? lab : k }, lab), h("span", { class: "bl-v" }, n(v)),
      change ? h("span", { class: "bl-c" }, change(k)) : h("span", { class: "bl-p" }, pct1(v, sum))));
  });
  return ul;
}

// A {label: n} breakdown as a searchable, sortable table with CSV.
export function countTable(obj, { caption, file, key = "Label", value = "Count", keep, label, path = false, total, limit = 12, empty, drill } = {}) {
  const rows = ranked(obj, keep).map(([k, v]) => ({ k, v, label: label ? label(k) : k }));
  const sum = total ?? rows.reduce((s, r) => s + r.v, 0);
  const cols = [
    { key: "label", label: key, path, ...(drill ? { fmt: (v, r) => link(drill, r.k, { text: v }), csv: (r) => r.label } : {}) },
    { key: "v", label: value, num: true },
    { key: "share", label: "Share", num: true, sort: (r) => r.v, fmt: (_, r) => pct1(r.v, sum), csv: (r) => (sum ? (r.v / sum).toFixed(4) : "") },
  ];
  return table(cols, { caption, rows, file, limit, empty });
}

export function panel(title, sub, ...body) {
  return h("div", { class: "sheet" }, h("h3", null, title), sub ? h("p", { class: "sub" }, sub) : null, ...body);
}

export function fileName(base, r) {
  return `${base}-${r.kind === "today" ? `today-${r.first}` : `${r.first}-to-${r.last}`}.csv`;
}

/* The "Compare to previous period" switch, as a tab uses it: `prev` for the
   charts (null when off or not possible) and a note saying why not. */
export function compareFor(m, s) {
  const c = comparison(m, s);
  return {
    ...c,
    prev: c.ok ? ghostDay(m, c.shift) : null,
    note: c.on && !c.ok ? h("p", { class: "cmp-why", role: "note" }, c.why) : null,
    legend: c.ok ? [["Previous period", "var(--ink-3)", "ghost"]] : [],
  };
}
