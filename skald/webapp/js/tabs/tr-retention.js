// Traffic > Retention: of the visitors first seen in a week (or on a day), how
// many came back in each later week (day). The figures are retention.json's
// (retention_page.py), counted from what is kept (retention.py) and recounted by
// the audit (audit_retention.py); nothing is summed here but the curve's
// weighted average, and only from cells that are counted.
//
//   the triangle   one row per cohort, one column per week (day) after it; a cell
//                  shows the share and the count, shaded one hue light to dark
//                  (the people colour's ramp, css/retention.css). A period not
//                  over is blank; a cell never counted is "not recorded", hatched;
//                  a day not verified holds the cell back, hatched. A click lists
//                  the visitors behind it (people/cohort, admins and owners), each
//                  opening in the visitor drawer (visitor.js).
//   the curve      the share back at each step, over every cohort counted there
//   on a phone     the same figures as tables (css: the grid hides, the tables show)
//
// Split by the first visit's source type, country, device or landing page; count
// "came back" or "came back and read 2 or more pages" (not on the 30-day code).

import { h, n, pct1, short, long, tip, untip, esc, MIN_SHARE, stateNote } from "../ui.js";
import * as S from "../state.js";
import { openDrawer } from "../drawer.js";
import { withUrl } from "../urlactions.js";
import { shown } from "../labels.js";
import { rove } from "../place.js";
import { DEMO, demoFile } from "../demo.js";
import { info, tiles } from "./tiles.js";
import { countryName } from "./readers.js";
import { call } from "./ipmanager.js";
import { mayFind } from "./person.js";
import { openVisitor } from "./visitor.js";
import { time as tzTime } from "../tz.js";

const SPLITS = [["", "Everyone"], ["source", "First source type"], ["country", "Country"], ["device", "Device"], ["landing", "Landing page"]];
const GRAINS = [["week", "Weeks"], ["day", "Days"]];
const STEPS = 5;
const ROAD = {
  address: (i) => `the same IP address with the same browser and system, from the visits kept ${n(i.horizon)} days (Settings › Data retention › People)`,
  hash: (i) => `the 30-day visitor code (an address and browser family, hashed with a secret; no address kept), kept ${n(i.horizon)} days`,
};
const NOT = {
  pending: "not over yet",
  held: "held back: a day in it is not verified (withheld, partial or not collected)",
  nr: "not recorded: later than this identity can follow",
  "nr-pruned": "not recorded: its inputs were pruned before it could be counted",
};

const unit = (g) => (g === "week" ? "week" : "day");
const step = (g, k) => `${unit(g)} +${k}`;
function cohortName(g, c) { return g === "week" ? `${short(c.start)} – ${short(c.end)}` : long(c.start); }
function valueName(dim, v) {
  if (v === "(other)") return "Other";
  if (dim === "country") return v === "Unknown" ? "Not recorded" : `${countryName(v) || v}`;
  if (dim === "source") return shown(v) || v;
  return v === "Unknown" ? "Not recorded" : v;
}

/* The part of a cohort a split value picks: {size, cells} (the cohort itself for Everyone). */
function partOf(c, dim, value) {
  if (!dim) return { size: c.size, cells: c.cells || {} };
  return (c.split?.[dim] || {})[value] || { size: 0, cells: {} };
}

/* Every value of a split across the cohorts, biggest first. */
function valuesOf(cohorts, dim) {
  const tot = new Map();
  for (const c of cohorts) for (const [v, p] of Object.entries(c.split?.[dim] || {})) tot.set(v, (tot.get(v) || 0) + (p.size || 0));
  return [...tot.entries()].sort((a, b) => (a[0] === "(other)") - (b[0] === "(other)") || b[1] - a[1]).map(([v]) => v);
}

/* What one cell is: {state, back, size, share} - state one of ok, pending, held, nr, nr-pruned. */
function cellOf(c, k, part, deep) {
  const state = c.status?.[String(k)] || "nr";
  if (state !== "ok") return { state };
  const v = part.cells?.[String(k)];
  if (!v) return { state: "ok", back: 0, size: part.size };
  return { state: "ok", back: deep ? v[1] : v[0], size: part.size };
}

// ------------------------------------------------------------------ the curve
/* The share back at each step, over every cohort with that cell counted: the
   visitors back summed over the visitors in those cohorts (a weighted average). */
export function curve(cohorts, K, pick) {
  const out = [];
  for (let k = 1; k <= K; k += 1) {
    let back = 0, size = 0, count = 0;
    for (const c of cohorts) {
      const x = pick(c, k);
      if (x.state !== "ok" || x.back == null || !x.size) continue;
      back += x.back; size += x.size; count += 1;
    }
    out.push({ k, back, size, cohorts: count, share: size ? back / size : null });
  }
  return out;
}

function curveChart(points, g, metric) {
  const shown = points.filter((p) => p.share != null);
  if (!shown.length) return h("p", { class: "empty" }, "No cell is counted yet: the curve starts once a cohort has a whole period after it.");
  const W = 640, H = 220, L = 46, R = 14, T = 14, B = 30, pw = W - L - R, ph = H - T - B;
  // Round ticks: the smallest step (in whole percents) that covers the top in 5 or fewer.
  const topPct = Math.max(1, ...shown.map((p) => p.share * 100));
  const stepPct = [1, 2, 5, 10, 20, 25].find((st) => Math.ceil(topPct / st) <= 5) || 25;
  const ticks = Math.max(1, Math.ceil(topPct / stepPct));
  const max = Math.min(1, (ticks * stepPct) / 100);
  const x = (k) => L + ((k - 1) / Math.max(1, points.length - 1)) * pw;
  const y = (v) => T + ph - (v / max) * ph;
  const grid = Array.from({ length: ticks + 1 }, (_, i) => i / ticks).map((f) => {
    const v = max * f, yy = y(v).toFixed(1);
    return `<line class="ret-grid" x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}"/><text class="ret-ax" x="${L - 8}" y="${(+yy + 4).toFixed(1)}" text-anchor="end">${Math.round(v * 100)}%</text>`;
  }).join("");
  const xs = points.map((p) => `<text class="ret-ax" x="${x(p.k).toFixed(1)}" y="${H - 10}" text-anchor="middle">+${p.k}</text>`).join("");
  const segs = [];
  let run = [];
  for (const p of points) {
    if (p.share == null) { if (run.length) segs.push(run); run = []; } else run.push(p);
  }
  if (run.length) segs.push(run);
  const lines = segs.map((sg) => (sg.length > 1 ? `<polyline class="ret-line" points="${sg.map((p) => `${x(p.k).toFixed(1)},${y(p.share).toFixed(1)}`).join(" ")}"/>` : "")).join("");
  const dots = shown.map((p) => `<circle class="ret-dot" cx="${x(p.k).toFixed(1)}" cy="${y(p.share).toFixed(1)}" r="4"/>`).join("");
  // Direct labels on the first and the last point only.
  const ends = [shown[0], shown[shown.length - 1]].filter((p, i, a) => i === 0 || p !== a[0])
    .map((p) => `<text class="ret-lab" x="${x(p.k).toFixed(1)}" y="${(y(p.share) - 10).toFixed(1)}" text-anchor="middle">${pct1(p.back, p.size)}</text>`).join("");
  const slot = pw / Math.max(1, points.length - 1);
  const hits = points.map((p) => `<rect class="ret-hit" data-k="${p.k}" tabindex="0" x="${(x(p.k) - slot / 2).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${ph}" aria-label="${esc(curveWords(p, g, metric))}"/>`).join("");
  const el = h("div", { class: "ret-curve", html: `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Share of new visitors who ${metric === "deep" ? "came back and read 2 or more pages" : "came back"}, by ${unit(g)} after their first">${grid}${xs}${lines}${dots}${ends}${hits}</svg>` });
  el.querySelectorAll(".ret-hit").forEach((r) => {
    const p = points[Number(r.dataset.k) - 1];
    const show = (cx, cy) => tip(cx, cy, `${step(g, p.k)} after the first visit`, p.share == null ? [{ value: "", label: "no cohort counted here yet" }]
      : [{ value: pct1(p.back, p.size), label: metric === "deep" ? "came back and read 2 or more pages" : "came back" },
        { value: n(p.back), label: `of ${n(p.size)} new visitors` }, { value: n(p.cohorts), label: p.cohorts === 1 ? "cohort counted" : "cohorts counted" }]);
    r.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    r.addEventListener("pointerleave", untip);
    r.addEventListener("focus", () => { const b = r.getBoundingClientRect(); show(b.left + b.width / 2, b.top + 20); });
    r.addEventListener("blur", untip);
  });
  rove(el.querySelectorAll(".ret-hit"), { start: 0 });
  return el;
}

function curveWords(p, g, metric) {
  if (p.share == null) return `${step(g, p.k)}: no cohort counted yet`;
  return `${step(g, p.k)}: ${pct1(p.back, p.size)} ${metric === "deep" ? "came back and read 2 or more pages" : "came back"}, ${n(p.back)} of ${n(p.size)} new visitors in ${n(p.cohorts)} cohorts`;
}

// ------------------------------------------------------------------ the triangle
function shade(share, top) {
  if (share == null || top <= 0) return 0;
  if (share <= 0) return 0;
  return Math.max(1, Math.min(STEPS, Math.ceil((share / top) * STEPS)));
}

function cellTip(g, c, k, x, metric, few) {
  const head = `${cohortName(g, c)}, ${step(g, k)}`;
  if (x.state !== "ok") return [head, [{ value: "", label: NOT[x.state] || NOT.nr }]];
  const rows = [{ value: few ? n(x.back) : pct1(x.back, x.size), label: metric === "deep" ? "came back and read 2 or more pages" : "came back" },
    { value: n(x.back), label: `of ${n(x.size)} new visitors` }];
  if (few) rows.push({ value: "", label: `fewer than ${MIN_SHARE} new visitors: the count only, no share` });
  if (!c.checkable) rows.push({ value: "", label: `inputs expired: as last counted on ${short(c.computed)}` });
  return [head, rows];
}

function triangle(cohorts, g, K, dim, value, metric, onPick) {
  const pick = (c, k) => cellOf(c, k, partOf(c, dim, value), metric === "deep");
  let top = 0;
  for (const c of cohorts) for (let k = 1; k <= K; k += 1) {
    const x = pick(c, k);
    if (x.state === "ok" && x.size >= MIN_SHARE && x.back != null) top = Math.max(top, x.back / x.size);
  }
  const head = h("tr", null, h("th", { scope: "col" }, g === "week" ? "First week" : "First day"), h("th", { scope: "col", class: "num" }, "New visitors"),
    Array.from({ length: K }, (_, i) => h("th", { scope: "col", class: "num" }, `+${i + 1}`)));
  const cells = [];
  const rows = cohorts.map((c) => {
    const part = partOf(c, dim, value);
    const label = h("th", { scope: "row" }, cohortName(g, c), mark(c));
    if (c.state !== "ok") {
      return h("tr", { class: "ret-off" }, label, h("td", { class: "num", colspan: String(K + 1) },
        c.state === "withheld" ? h("span", { class: "pp-bad" }, "withheld: its recount did not match") : c.state === "held" ? "held back: a day in it is not verified" : "not recorded"));
    }
    const few = part.size < MIN_SHARE;
    const size = h("td", { class: "num ret-size" }, h("button", { type: "button", class: "ret-c ret-n", "aria-label": `${cohortName(g, c)}: ${n(part.size)} new visitors`, onclick: () => onPick(c, 0, part) }, n(part.size)));
    cells.push(size.firstChild);
    const tds = Array.from({ length: K }, (_, i) => {
      const k = i + 1, x = pick(c, k);
      if (x.state === "pending") return h("td", { class: "ret-pend" });
      const [th, tr] = cellTip(g, c, k, x, metric, few);
      const words = `${th}: ${tr.map((r) => `${r.value} ${r.label}`.trim()).join(", ")}`;
      const s = x.state === "ok" ? (few ? 0 : shade(x.back / (x.size || 1), top)) : -1;
      const body = x.state === "ok" ? [h("b", null, few ? n(x.back) : pct1(x.back, x.size)), few ? null : h("small", null, n(x.back))] : h("small", null, x.state === "held" ? "held" : "n/r");
      const b = h("button", { type: "button", class: `ret-c ${x.state === "ok" ? `s${s}` : "ret-nr"}`, "aria-label": words,
        onclick: x.state === "ok" ? () => onPick(c, k, part) : null, "aria-disabled": x.state === "ok" ? null : "true" }, body);
      b.addEventListener("pointermove", (e) => tip(e.clientX, e.clientY, th, tr));
      b.addEventListener("pointerleave", untip);
      b.addEventListener("focus", () => { const r = b.getBoundingClientRect(); tip(r.left + r.width / 2, r.top, th, tr); });
      b.addEventListener("blur", untip);
      cells.push(b);
      return h("td", null, b);
    });
    return h("tr", null, label, size, tds);
  });
  const table = h("table", { class: "ret-tri" }, h("caption", { class: "vh" }, `Retention by ${unit(g)}: new visitors of each cohort, and the share back in each ${unit(g)} after`),
    h("thead", null, head), h("tbody", null, rows));
  rove(cells, { start: 0 });
  const ramp = h("div", { class: "scale ret-scale" }, "0%",
    h("span", { class: "ret-ramp", "aria-hidden": "true" }, Array.from({ length: STEPS }, (_, i) => h("i", { class: `s${i + 1}` }))),
    top ? `${Math.round(top * 100)}% (the highest here)` : "",
    h("span", { class: "ret-key" }, h("i", { class: "ret-nr", "aria-hidden": "true" }), "not recorded or held back"),
    h("span", { class: "ret-key" }, h("i", { class: "ret-pend", "aria-hidden": "true" }), "not over yet"));
  return h("div", { class: "ret-wrap" }, h("div", { class: "scroll" }, table), ramp);
}

function mark(c) {
  const bits = [];
  if (c.state === "ok" && !c.checkable) bits.push(h("small", { class: "ret-m", title: `Its inputs are past their keeping: as last counted on ${long(c.computed)}${c.audit?.on ? `, last checked ${long(c.audit.on)}` : ""}. Not checkable now.` }, "inputs expired"));
  else if (c.state === "ok" && !c.audit) bits.push(h("small", { class: "ret-m", title: "Counted on the last run; the audit recounts it on the next daily run." }, "not checked yet"));
  return bits;
}

// ------------------------------------------------------------------ phone tables
function phoneTables(cohorts, g, K, dim, value, metric, points) {
  const pick = (c, k) => cellOf(c, k, partOf(c, dim, value), metric === "deep");
  const avg = h("table", { class: "ret-list" }, h("caption", null, `Back in each ${unit(g)} after, over every cohort counted`),
    h("thead", null, h("tr", null, ["After", "Back", "Of new", "Cohorts"].map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", null, points.map((p) => h("tr", null, h("th", { scope: "row" }, step(g, p.k)),
      h("td", null, p.share == null ? "-" : pct1(p.back, p.size)), h("td", null, p.share == null ? "-" : `${n(p.back)} of ${n(p.size)}`), h("td", null, n(p.cohorts))))));
  const ks = g === "week" ? [1, 2, 4, 8] : [1, 3, 7, 14];
  const each = h("table", { class: "ret-list" }, h("caption", null, "Each cohort"),
    h("thead", null, h("tr", null, h("th", { scope: "col" }, "Cohort"), h("th", { scope: "col" }, "New"), ks.filter((k) => k <= K).map((k) => h("th", { scope: "col" }, `+${k}`)))),
    h("tbody", null, cohorts.map((c) => {
      const part = partOf(c, dim, value);
      return h("tr", null, h("th", { scope: "row" }, cohortName(g, c)), h("td", null, c.state === "ok" ? n(part.size) : "-"),
        ks.filter((k) => k <= K).map((k) => {
          if (c.state !== "ok") return h("td", null, "-");
          const x = pick(c, k);
          return h("td", null, x.state === "ok" ? (part.size < MIN_SHARE ? n(x.back) : pct1(x.back, x.size)) : x.state === "pending" ? "" : "n/r");
        }));
    })));
  return h("div", { class: "ret-phone" }, avg, each);
}

// ------------------------------------------------------------------ the visitors behind a cell
function askUrl(g, c, k, dim, value, metric) {
  let u = `people/cohort?grain=${g}&start=${c.start}&k=${k}`;
  if (dim) u += `&split=${encodeURIComponent(dim)}&value=${encodeURIComponent(value)}`;
  if (metric === "deep" && k > 0) u += "&deep=1";
  return u;
}

async function openCell(g, c, k, part, dim, value, metric, road) {
  const what = k === 0 ? "New visitors" : metric === "deep" ? `Came back and read 2 or more pages, ${step(g, k)}` : `Came back, ${step(g, k)}`;
  const seg = dim ? ` · ${SPLITS.find(([d]) => d === dim)?.[1]}: ${valueName(dim, value)}` : "";
  const figure = k === 0 ? part.size : (part.cells?.[String(k)] || [0, 0])[metric === "deep" ? 1 : 0];
  // In the address as cohort=<first day>.<step> (the grain, count and split are rg, rm, rs, rv).
  const d = openDrawer({ title: what, subtitle: `First ${unit(g)} ${cohortName(g, c)}${seg}: ${n(figure)} visitor${figure === 1 ? "" : "s"}`, key: "cohort", scope: "page",
    body: h("p", { class: "empty" }, "Looking in the kept visits…"), route: { key: "cohort", value: `${c.start}.${k}` } });
  const url = askUrl(g, c, k, dim, value, metric);
  if (road !== "address") { d.body.replaceChildren(h("p", { class: "note" }, "The 30-day code names nobody: only kept visits (Settings › Data retention › People, keep IP addresses) can list the visitors behind a cell.")); return d; }
  if (!(mayFind() || (DEMO.on && demoFile(url)))) {
    d.body.replaceChildren(h("p", { class: "note" }, DEMO.on ? "In the demo, the visitors behind this cell need a running Skald." : "Admins and owners see the visitors behind a cell here, each opening in the visitor drawer."));
    return d;
  }
  const got = await call(url);
  if (!d.el.isConnected) return d;
  if (!got.ok) { d.body.replaceChildren(h("p", { class: "note" }, got.error || "The visitors could not be read.")); return d; }
  if (!got.found) { d.body.replaceChildren(h("p", { class: "note" }, got.why || "No kept visit is behind this cell.")); return d; }
  const rows = got.rows.map((r) => h("tr", { class: "ret-row", tabindex: "0", onclick: () => openVisitor(r), onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openVisitor(r); } } },
    h("td", null, tzTime(r.start, { date: true, label: false }) || short(r.day)), h("td", null, shown(r.via || r.source) || "-"),
    h("td", null, withUrl(h("span", { class: "mono" }, r.landing || "-"), r.landing)), h("td", { class: "num" }, n(r.pages)),
    h("td", null, r.country ? countryName(r.country) || r.country : "-"), h("td", null, shown(r.device) || "-")));
  d.body.replaceChildren(...[
    h("p", { class: "note" }, k === 0 ? "Each new visitor's first visit of the cohort. A row opens the visitor." : `Each visitor's first visit in ${step(g, k)}${metric === "deep" ? " that read 2 or more pages" : ""}. A row opens the visitor.`),
    h("div", { class: "scroll" }, h("table", { class: "rows-mid ret-rows" }, h("caption", { class: "vh" }, what),
      h("thead", null, h("tr", null, ["When", "Came from", "Landing", "Pages", "Country", "Device"].map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", null, rows))),
    got.listed > got.rows.length ? h("p", { class: "note" }, `The first ${n(got.rows.length)} of ${n(got.listed)}.`) : null,
    got.differs ? h("p", { class: "note" }, got.differs) : null,
    h("p", { class: "note" }, "Shown to admins and owners, and written to the audit log (never the address).")].filter(Boolean));
  return d;
}

/* What the tab shows for a state: the grain, the cohorts, the count and the split. */
function viewOf(file, s) {
  const g = s.rg === "day" ? "day" : "week";
  const cohorts = [...(file.grains?.[g]?.cohorts || [])].filter((c) => !file.begun || c.start >= file.begun).reverse();
  const hash = file.identity.by === "hash";
  const metric = s.rm === "deep" && !hash ? "deep" : "back";
  const dims = hash ? SPLITS.slice(0, 2) : SPLITS;
  const dim = dims.some(([d]) => d === s.rs) ? s.rs : "";
  const values = dim ? valuesOf(cohorts, dim) : [];
  const value = dim ? (values.includes(s.rv) ? s.rv : values[0] || "") : "";
  return { g, cohorts, hash, metric, dims, dim, values, value };
}

/* cohort=<first day>.<step>, from a link: the cell's visitors, else the plain line. */
export function openCohortKey(m, s, v) {
  const file = m?.x?.retention;
  const [, start, k] = /^(\d{4}-\d\d-\d\d)\.(\d+)$/.exec(String(v)) || [];
  if (!file?.identity || !start) return "That group of visitors is not in the figures on this page.";
  const { g, cohorts, dim, value, metric } = viewOf(file, s);
  const c = cohorts.find((x) => x.start === start && x.state === "ok");
  if (!c) return `That group of visitors is no longer in the figures (${g === "week" ? "the last 12 weeks" : "the last 30 days"} of first visits are shown).`;
  return openCell(g, c, Number(k), partOf(c, dim, value), dim, value, metric, file.identity.by);
}

// ------------------------------------------------------------------ the tab
function identityLine(file) {
  const i = file.identity;
  const by = ROAD[i.by] ? ROAD[i.by](i) : i.by;
  return h("div", { class: "state ret-id" }, h("div", null,
    h("b", null, "The same visitor: "), `${by}. `,
    h("b", null, "New: "), `no visit of the same visitor in the ${n(i.lookback)} days before. `,
    h("b", null, "Followed: "), `${n(i.reach)} days after the first visit; a later cell is not recorded, never 0.`,
    i.by === "hash" ? " The code keeps a day and a source type only: no country, device, landing page or page count." : "",
    file.begun && file.kept_from && file.begun > file.kept_from ? ` What is kept begins ${long(file.begun)}: for now "new" means first seen since then.` : "",
    " The page script's visitor ID is not used here: it is kept 30 days and only for visits that ran the script."));
}

export default function retention(m, s) {
  const file = m.x.retention;
  const g = s.rg === "day" ? "day" : "week";
  const out = [h("div", { class: "head" }, h("h1", null, "Retention"),
    info("Of the visitors first seen in a week (or on a day), how many came back in each week (day) after. Counted from what is kept, by the site's own days (a week starts on Monday), and recounted by the audit each night.", "Retention"),
    h("span", { class: "period" }, `${g === "week" ? "The last 12 weeks" : "The last 30 days"} of first visits · the date range above does not apply`))];
  if (!file) return [...out, stateNote("Retention is not counted yet: the next daily run writes retention.json.")];
  if (!file.identity) return [...out, stateNote(file.words || "Retention is not counted for this site.")];
  const K = file.offsets?.[g] || (g === "week" ? 8 : 14);
  // Newest first; none from before what is kept begins (nothing there to count).
  const { cohorts, hash, metric, dims, dim, values, value } = viewOf(file, s);

  const seg = (label, opts, cur, set) => h("div", { class: "seg plain", role: "group", "aria-label": label },
    opts.map(([k, w, off]) => h("button", { type: "button", "aria-pressed": String(cur === k), disabled: off || null, title: off || null, onclick: () => set(k) }, w)));
  const select = (label, opts, cur, set) => h("label", { class: "ret-sel" }, h("span", { class: "add-l" }, label),
    h("select", { onchange: (e) => set(e.target.value) }, opts.map(([k, w]) => h("option", { value: k, selected: k === cur || null }, w))));
  const controls = h("div", { class: "ret-ctl" },
    seg("Cohorts by", GRAINS, g, (k) => S.set({ rg: k === "week" ? "" : k }, { replace: true })),
    seg("Count", [["back", "Came back"], ["deep", "Read 2+ pages", hash ? "Not on the 30-day code: pages are not kept" : ""]], metric, (k) => S.set({ rm: k === "back" ? "" : k }, { replace: true })),
    select("Split by", dims, dim, (k) => S.set({ rs: k, rv: "" }, { replace: true })),
    dim ? select("Value", values.map((v) => [v, valueName(dim, v)]), value, (v) => S.set({ rv: v }, { replace: true })) : null);

  const pick = (c, k) => cellOf(c, k, partOf(c, dim, value), metric === "deep");
  const counted = cohorts.filter((c) => c.state === "ok");
  const points = curve(counted, K, pick);
  const newTotal = counted.reduce((a, c) => a + (partOf(c, dim, value).size || 0), 0);
  const p1 = points[0], pLate = points[g === "week" ? 3 : 6];
  const removed = counted.reduce((a, c) => a + (c.removed || 0), 0);
  const word = metric === "deep" ? "came back and read 2+ pages" : "came back";
  const onPick = (c, k, part) => openCell(g, c, k, part, dim, value, metric, file.identity.by);

  out.push(identityLine(file), controls,
    tiles([
      { label: "New visitors", value: newTotal, line: `first seen in the ${n(counted.length)} ${unit(g)}s counted${dim ? `, ${valueName(dim, value)}` : ""}` },
      { label: `Back the next ${unit(g)}`, value: p1?.share == null ? null : pct1(p1.back, p1.size), line: p1?.share == null ? "no whole period after a cohort yet" : `${n(p1.back)} of ${n(p1.size)} ${word}` },
      pLate ? { label: `Back ${step(g, pLate.k)}`, value: pLate.share == null ? null : pct1(pLate.back, pLate.size),
        line: pLate.share == null ? "not counted yet, or later than the identity can follow" : `${n(pLate.back)} of ${n(pLate.size)} ${word}` } : null]),
    h("section", { class: "s" }, h("h2", null, `New visitors, and the share back each ${unit(g)} after`),
      h("p", { class: "sub" }, `Each row is the visitors first seen that ${unit(g)}; each column a later ${unit(g)}. A cell opens the visitors behind it.`),
      h("div", { class: "sheet ret-desk" }, triangle(cohorts, g, K, dim, value, metric, onPick)),
      phoneTables(cohorts, g, K, dim, value, metric, points)),
    h("section", { class: "s ret-desk" }, h("h2", null, "Retention curve"),
      h("p", { class: "sub" }, `The share of new visitors who ${word} in each ${unit(g)} after their first, over every cohort counted there.`),
      h("div", { class: "sheet" }, curveChart(points, g, metric))),
    h("p", { class: "note" }, [
      "A cohort is counted from the kept visits while every day it reads is still kept, and recounted by the audit; once its inputs are pruned it stays as last counted (\"inputs expired\").",
      removed ? ` ${n(removed)} visits of forgotten addresses are in no cohort.` : "",
      " One address can be several people (an office), and one person on two devices is two visitors."].join("")));
  return out;
}
