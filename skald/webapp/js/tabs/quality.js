// Data quality: can the figures be trusted, day by day. Lines read, lines
// the parser could not read, duplicates, stretches with no line at all, the
// verify step and the independent audit - and when each job last ran.
// Green: nothing to worry about; amber: look; red: withheld or mismatched.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, short, long, tip, untip, duration, zoned, ICON } from "../ui.js";
import { rangeOf } from "../data.js";
import { rove } from "../place.js";
import { table } from "../table.js";
import { head, rangeWords, healthTabs, CDN_GUIDE } from "./common.js";
import { quietLimit } from "../notset.js";

const GRADE = { green: "Good", amber: "Worth a look", red: "Not trusted", none: "Not checked" };
const AUDIT = { ok: "recount matched", mismatch: "recount did not match", "not run": "not run" };
const share = (d) => (d.lines ? (d.unparsed / d.lines) * 100 : null);
const fmtPct = (v) => (v == null ? "-" : v === 0 ? "0%" : v < 0.01 ? "<0.01%" : `${v.toFixed(v < 1 ? 2 : 1)}%`);
const UNREADABLE_AMBER = 0.5;   // percent of lines
// A silent stretch is worth a look only when it is long for this site (notset.js quietLimit).
const longGaps = (d) => (d.gaps || []).filter((g) => g.minutes >= quietLimit(d));
// The log files a day was read from: a list of names, or a count.
const files = (f) => { const k = Array.isArray(f) ? f.length : f; return k ? `, ${k} file${k === 1 ? "" : "s"}` : ""; };

/* The audit runs with the daily run. Where the daily run has never run (a history
   filled by backfill, the demo), "the audit did not run" is true of every day and
   tells nothing about one: it is said once above the days, not graded per day. */
let AUDITS = true;

// quality.json's not_pages ({entry: {requests, people}}): [requests, people, "entry N, ..."].
const notPages = (v) => {
  const rows = Object.entries(v || {});
  return [rows.reduce((t, [, x]) => t + (x.requests || 0), 0), rows.reduce((t, [, x]) => t + (x.people || 0), 0),
    rows.map(([k, x]) => `${k} ${n(x.requests)}`).join(", ")];
};

// SKALD-17/23: a log whose addresses are mostly a CDN's edges, not the visitors' (the site's
// server logs Cloudflare's address instead of CF-Connecting-IP). quality.json cdn_lines.
export const CDN_SHARE = 0.5;
export const cdnShare = (d) => (d && d.cdn_lines != null && d.lines ? d.cdn_lines / d.lines : null);
const cdnWhy = (d) => {
  const k = cdnShare(d);
  return k != null && k >= CDN_SHARE ? `${fmtPct(k * 100)} of lines carry a CDN's address, not the visitor's: cities, crawler checks, scanners and the block list are not reliable` : null;
};

// SKALD-34: posts the log endpoint refused on a day (quality.json intake_refused, by
// ingest_status.py reason). Only a Worker's ("edge_limited") make a day worth a look: those
// records are lost, as it never sends them again. The rest (a shipper waiting, a stranger's
// post with no token) are in the column and its hover, not in the grade.
const INTAKE = { edge_limited: "from the edge, lost", rate_limited: "too many batches at once", no_token: "no token", bad_token: "bad token",
  wrong_site: "token for another site", not_sending: "not a sending token", not_verified: "site not verified yet", removed: "site removed",
  not_here: "site not processed here", day_full: "the day's limit used up", plan_limit: "over the plan's limit", read_only: "organisation read-only",
  disk: "server short of disk", bad_format: "wrong log format", bad_batch: "malformed", too_large: "too large", no_accounts: "accounts off", off: "endpoint off", other: "other" };
const intakeTotal = (v) => Object.values(v || {}).reduce((t, k) => t + (k || 0), 0);
// The day's cell: a count, "0" when none, "not recorded" before Skald counted them.
export const intakeWords = (v) => (v == null ? "not recorded" : n(intakeTotal(v)));
const lostWhy = (v) => {
  const k = (v && v.edge_limited) || 0;
  return k ? `${n(k)} edge post${k === 1 ? "" : "s"} refused at the log endpoint: those records are lost` : null;
};
function intakeWhy(v) {
  const k = intakeTotal(v);
  if (!k) return null;
  const parts = Object.entries(v).filter(([, c]) => c).sort(([a, x], [b, y]) => (b === "edge_limited") - (a === "edge_limited") || y - x)
    .map(([r, c]) => `${n(c)} ${INTAKE[r] || r}`);
  return `${n(k)} post${k === 1 ? "" : "s"} refused at the log endpoint (${parts.join("; ")})`;
}

// Why a day is the colour it is: the first reasons are the worst.
export function grade(d) {
  // A day with no figures may still be one whose every post was refused (SKALD-34).
  if (!d || d.lines == null && d.verify == null) return lostWhy(d?.intake_refused) ? ["amber", [lostWhy(d.intake_refused)]] : ["none", []];
  const red = [], amber = [];
  if (d.verify === "withheld") red.push(d.problems || "withheld: the figures did not add up");
  if (d.audit?.state === "mismatch") red.push(`the recount did not match${d.audit.problems?.length ? `: ${d.audit.problems.join("; ")}` : ""}`);
  if (d.verify === "partial") amber.push("partial: the log did not cover the whole day");
  const long = longGaps(d);
  if (long.length) amber.push(`${long.length} long stretch${long.length === 1 ? "" : "es"} with no log line (longest ${Math.max(...long.map((g) => g.minutes))} min; ${quietLimit(d)} min or more is long for this site)`);
  if ((share(d) ?? 0) >= UNREADABLE_AMBER) amber.push(`${fmtPct(share(d))} of lines unreadable`);
  const cdn = cdnWhy(d);
  if (cdn) amber.push(cdn);
  if (d.duplicates) amber.push(`${n(d.duplicates)} duplicate lines (kept in the figures)`);
  if (d.old_format) amber.push(`${n(d.old_format)} lines in the old log format`);
  if (AUDITS && d.audit && d.audit.state === "not run" && d.verify !== "withheld") amber.push("the audit did not run");
  const lost = lostWhy(d.intake_refused);
  if (lost) amber.push(lost);
  if (d.clock_skew_s != null && Math.abs(d.clock_skew_s) > 600) red.push(`the newest log line is ${duration(Math.abs(d.clock_skew_s))} old: logging may have stopped`);
  return red.length ? ["red", [...red, ...amber]] : amber.length ? ["amber", amber] : ["green", []];
}

/* Why the days are not all good, said on the page: each reason with how many days
   it covers and which, the worst first. Never only behind a hover. */
function reasons(days) {
  const by = new Map();
  for (const d of days) {
    const [g, why] = grade(d);
    if (g !== "amber" && g !== "red") continue;
    for (const w of why) {
      // One line per kind of reason: counts, details after a colon and the bracket left out of the key.
      const key = w.split(":")[0].replace(/\(.*\)/, "").replace(/\d[\d,.]*%?/g, "#").replace(/stretches/, "stretch").replace(/lines?/, "line").trim();
      const e = by.get(key) || { g, words: w, days: [] };
      if (g === "red") e.g = "red";
      e.days.push(d.day);
      by.set(key, e);
    }
  }
  if (!by.size) return null;
  const list = [...by.values()].sort((a, b) => (b.g === "red") - (a.g === "red") || b.days.length - a.days.length);
  const many = (w) => w.split(":")[0].replace(/\(.*\)/, "").replace(/^\d[\d,.]*%?\s*/, "").trim();
  return h("ul", { class: "q-why-list" }, list.map((e) => h("li", null, h("span", { class: `q-tag q-${e.g}` }, GRADE[e.g]), " ",
    e.days.length === 1 ? `${short(e.days[0])}: ${e.words}` : `${e.days.length} days (${e.days.slice(0, 3).map(short).join(", ")}${e.days.length > 3 ? "…" : ""}): ${many(e.words)}`)));
}

function strip(days) {
  const el = h("div", { class: "uptime q-strip", role: "img", "aria-label": `Data quality by day, ${days.length} days` });
  for (const d of days) {
    const [g, why] = grade(d);
    const label = `${long(d.day)}: ${GRADE[g]}${why.length ? `, ${why.join("; ")}` : ""}`;
    const cell = h("i", { class: `q-${g}`, tabindex: "0", "aria-label": label });
    const show = (x, y) => tip(x, y, short(d.day), [{ value: "", label: label.split(": ").slice(1).join(": ") }]);
    cell.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    cell.addEventListener("pointerleave", untip);
    cell.addEventListener("focus", () => { const b = cell.getBoundingClientRect(); show(b.left + b.width / 2, b.top); });
    cell.addEventListener("blur", untip);
    el.append(cell);
  }
  rove(el.children);  // one Tab stop for the strip; arrow keys move between days
  return el;
}

// 2.41: the verdict is today's log lines'; a scheduled job that is late, failed or never ran is
// named beside it, so "Good" never sits above red jobs with no word (the UX audit's count rule).
/* SKALD-25: what a duplicate line is, and that it stays in the figures (COUNTING-TRAPS.md 7): with
   no request ID (rid=) in the log, a line written twice and a real repeat look the same. Lines
   that repeat a request ID are the same request, and were dropped. */
export function dupNote(t) {
  const gone = t?.duplicates_removed;
  return `the same line twice in one second: kept in the figures${gone ? `; ${n(gone)} more repeated a request ID and were dropped` : ""}`;
}

function todayCard(t, tz, jobsOff = 0) {
  if (!t) return h("p", { class: "empty" }, "Today has not been checked yet: the live count writes it every few minutes.");
  const [g, why] = grade(t);
  const cell = (label, v, note) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, label), h("div", { class: "k-n" }, note || ""), h("div", { class: "k-v" }, v), h("div", { class: "k-c" }));
  return h("div", null,
    h("div", { class: `q-now q-${g}` }, h("span", { class: "q-dot", "aria-hidden": "true" }),
      h("div", null, h("b", null, `Today's log lines so far: ${GRADE[g]}`), h("small", null, why.length ? why.join("; ") : "No problem found in today's lines.",
        jobsOff ? ` ${jobsOff} scheduled job${jobsOff === 1 ? " is" : "s are"} late, failed or never ran: see Scheduled jobs, below.` : ""))),
    h("div", { class: "kpis" },
      cell("Lines read", n(t.lines), t.first_line ? `from ${t.first_line} to ${t.last_line}${files(t.files)}` : ""),
      cell("Unreadable lines", n(t.unparsed), fmtPct(share(t))),
      cell("Duplicate lines", n(t.duplicates), dupNote(t)),
      cell("Newest line", t.newest_line ? tzTime(t.newest_line) : "-", t.clock_skew_s != null ? `${duration(Math.abs(t.clock_skew_s))} before the server's clock` : ""),
      cell("Silent stretches", n(t.gaps?.length ?? null), "more than 10 minutes with no line at all"),
      cell("Browser-like requests moved to bots", n(t.not_rendered?.requests ?? null), movedNote(t.not_rendered)),
      cdnShare(t) != null ? cell("Lines from a CDN's addresses", fmtPct(cdnShare(t) * 100), "the edge's address, not the visitor's") : null,
      t.intake_refused != null ? cell("Refused at the log endpoint", intakeWords(t.intake_refused), "posts Skald's server turned away today") : null));
}

/* The fix, said once above the days (SKALD-23): the site's server must log the visitor's real
   address (nginx real_ip from the CDN's ranges and its client-address header). */
function mostlyCdn(f, r) {
  const seen = [f.today, ...(f.days || []).filter((d) => d.day >= r.first && d.day <= r.last)].filter((d) => cdnShare(d) != null);
  if (!seen.some((d) => cdnShare(d) >= CDN_SHARE)) return null;
  return h("p", { class: "q-cdn note", role: "note" }, h("span", { class: "q-tag q-amber" }, GRADE.amber), " ",
    "Most addresses in this log are a CDN's (Cloudflare's), not the visitors': cities and countries, crawler checks, scanners and the block list are not reliable. Ask the site's admin to log the visitor's real address. ",
    h("a", { href: CDN_GUIDE }, "How"));
}

// A job is late when it has not succeeded for twice its interval (the measured one when known, #54); failed when its last run failed.
function jobState(j, now) {
  const ok = j.last_ok ? Date.parse(j.last_ok) : 0, bad = j.last_fail ? Date.parse(j.last_fail) : 0;
  if (bad > ok) return "failed";
  if (!ok) return "never";
  if (j.expected_every_min && now - ok > j.expected_every_min * 2 * 60000) return "late";
  return "ok";
}
const JOB_WORDS = { live: "Live count (today so far)", "run-daily": "Daily run: record yesterday, audit, mail", "verify-bots": "Crawler address lists",
  alerts: "Alert check", backup: "History backup", pagespeed: "Page speed (Google PageSpeed Insights)", heartbeat: "Heartbeat (our own, every 5 minutes)" };
// Requests sent with a browser's name whose visit never loaded the page's scripts and styles (rendering.py).
const movedNote = (x) => (x ? `${n(x.readers)} visits that would have counted as visitors; their pages never rendered` : "not recorded");
const every = (min) => (!min ? "-" : min < 60 ? `every ${Math.max(1, Math.round(min))} min` : min === 1440 ? "daily" : `every ${Math.round(min / 60)} h`);
// How often a job runs, in plain words: the measured gap between its successes when known (#54).
// A live round of many sites takes longer than planned, and late is judged against this.
const runsWords = (j) => {
  const m = j.measured_every_min;
  if (!m || m >= 60) return every(j.expected_every_min);
  const k = Math.max(1, Math.round(m));
  return h("span", { title: "The gap between its last few runs. A job is late only after twice this." }, `every ${k} minute${k === 1 ? "" : "s"} (measured)`);
};


export default function quality(m, s) {
  const r = rangeOf(m, s);
  const out = [healthTabs(m, "health/quality"), ...head("Data quality", r, "Whether the figures can be trusted, day by day: how much of the log was read, what could not be read, and whether the independent recount matched. A day that fails is withheld everywhere, never shown as zero.", { banner: false })];
  const f = m.x.quality;
  if (!f) return [...out, h("div", { class: "state", html: ICON.info }, h("div", null, "No quality file beside this page yet. It comes with the next data update. Meanwhile each tab's footnote says how many days were verified, and which were withheld."))];
  AUDITS = !!f.runs?.["run-daily"]?.last_ok;
  // Today's card belongs to Today; a range shows its days.
  const jobsOff = Object.values(f.runs || {}).filter((j) => jobState(j, Date.now()) !== "ok").length;
  if (r.kind === "today") out.push(h("section", { class: "s" }, todayCard(f.today, m.tz, jobsOff)));
  const cdnNote = mostlyCdn(f, r);
  if (cdnNote) out.push(cdnNote);
  const byDay = new Map((f.days || []).map((d) => [d.day, d]));
  const days = r.kind === "today" ? [] : r.days.filter((d) => d.state !== "before").map((d) => byDay.get(d.day) || { day: d.day, state: "missing" });
  if (days.length) {
    const c = { green: 0, amber: 0, red: 0, none: 0 };
    for (const d of days) c[grade(d)[0]] += 1;
    out.push(h("section", { class: "s" }, h("h2", null, `Each day: ${rangeWords(r)}`),
      h("p", { class: "sub" }, `${c.green} good, ${c.amber} worth a look, ${c.red} not trusted${c.none ? `, ${c.none} not checked (collected before these checks existed, or not collected)` : ""}.`),
      reasons(days),
      AUDITS ? null : h("p", { class: "note" }, "No day here was recounted by the independent audit: it runs with the daily run, which has not run on this install yet (Scheduled jobs, below). Each day's own checks above still apply."),
      h("div", { class: "sheet" }, strip(days), h("div", { class: "scale" },
        h("span", { class: "sw", style: { background: "var(--good)" } }), "good", h("span", { class: "sw", style: { background: "var(--warn)", marginLeft: "12px" } }), "worth a look",
        h("span", { class: "sw", style: { background: "var(--bad)", marginLeft: "12px" } }), "not trusted", h("span", { class: "sw", style: { background: "var(--sunk)", marginLeft: "12px" } }), "not checked")),
      table([
        { key: "day", label: "Day", cls: "q-day", fmt: (v) => long(v) },
        { key: "grade", label: "Grade", type: "badge", sort: (x) => ["red", "amber", "green", "none"].indexOf(grade(x)[0]), fmt: (_, x) => h("span", { class: `q-tag q-${grade(x)[0]}` }, GRADE[grade(x)[0]]), csv: (x) => grade(x)[0] },
        // Why next to its grade: on screen at any width, never past the right edge.
        { key: "why", label: "Why", cls: "q-why", sort: (x) => grade(x)[1].join("; "), fmt: (_, x) => grade(x)[1].join("; "), csv: (x) => grade(x)[1].join("; ") },
        { key: "lines", label: "Lines", num: true },
        { key: "unparsed", label: "Unreadable", num: true, fmt: (v, x) => (v == null ? "-" : `${n(v)} (${fmtPct(share(x))})`) },
        { key: "duplicates", label: "Duplicates", num: true },
        // Lines repeating an earlier line's request id, dropped before counting (null: collected before this was recorded).
        { key: "duplicates_removed", label: "Duplicates removed", num: true, fmt: (v) => (v == null ? h("span", { class: "muted", title: "Not recorded on this day" }, "not recorded") : n(v)), csv: (x) => x.duplicates_removed ?? "" },
        // Browser-like requests whose visit never rendered a page, moved to bots (null: collected before this rule).
        { key: "not_rendered", label: "Browser-like requests moved to bots", num: true, sort: (x) => x.not_rendered?.requests ?? null,
          fmt: (v) => (v == null ? h("span", { class: "muted", title: "Not recorded on this day" }, "not recorded") : h("span", { title: movedNote(v) }, `${n(v.requests)} (${n(v.readers)} visits)`)),
          csv: (x) => x.not_rendered?.requests ?? "" },
        // 2.35: requests shaped like pages that the site's not-a-page list kept out of the page views (Settings > Data > What counts), by entry.
        { key: "not_pages", label: "Not counted as pages", num: true, sort: (x) => (x.not_pages ? notPages(x.not_pages)[0] : null),
          fmt: (v) => (v == null ? h("span", { class: "muted", title: "Not recorded on this day" }, "not recorded") : h("span", { title: notPages(v)[2] || "None" }, `${n(notPages(v)[0])} (${n(notPages(v)[1])} people)`)),
          csv: (x) => (x.not_pages ? notPages(x.not_pages)[0] : "") },
        { key: "first_line", label: "Log covers (site time)", type: "date", fmt: (v, x) => (v ? `${v} to ${x.last_line}` : "-") },
        { key: "gaps", label: "Silent stretches", num: true, sort: (x) => x.gaps?.length ?? null, fmt: (v) => (v == null ? "-" : v.length ? h("span", { class: "gaps", title: v.map((g) => `${g.from}-${g.to}`).join(", ") }, v.length > 2 ? `${n(v.length)}: ${v[0].from}-${v[0].to} and ${n(v.length - 1)} more` : v.map((g) => `${g.from}-${g.to}`).join(", ")) : "0"), csv: (x) => (x.gaps || []).map((g) => `${g.from}-${g.to}`).join(" ") },
        { key: "audit", label: "Audit", fmt: (v) => (v ? AUDIT[v.state] || v.state : "-"), csv: (x) => x.audit?.state || "" },
        // SKALD-34: only for a site that sends to the log endpoint (some day recorded).
        ...(days.some((d) => d.intake_refused != null) ? [{ key: "intake_refused", label: "Refused at the log endpoint", num: true, sort: (x) => (x.intake_refused == null ? null : intakeTotal(x.intake_refused)),
          fmt: (v) => (v == null ? h("span", { class: "muted", title: "Not recorded on this day" }, "not recorded") : h("span", { title: intakeWhy(v) || "None" }, intakeWords(v))),
          csv: (x) => (x.intake_refused == null ? "" : intakeTotal(x.intake_refused)) }] : []),
      ], { caption: "Data quality by day", rows: days.slice().reverse().map((d) => ({ ...d, __k: d.day })), file: `data-quality-${r.first}-to-${r.last}.csv`, sortKey: "day", dir: -1, limit: 10,
        rowClass: (x) => (grade(x)[0] === "red" ? "withheld" : null) })));
  }
  const now = f.generated_at ? Date.parse(f.generated_at) : Date.now();
  const stamp = (v) => (v ? tzTime(v, { date: true }) : "never");
  // Data files whose builder failed on the last redraw: shown as "could not be built" on their tabs, listed here.
  const failing = f.builders_failing;
  if (Array.isArray(failing)) out.push(h("section", { class: "s" }, h("h2", null, "Data files, last redraw"),
    failing.length ? [h("p", { class: "sub" }, `${failing.length} file${failing.length === 1 ? "" : "s"} could not be built; every other file was. The tabs that stand on them say so instead of showing empty figures.`),
      table([{ key: "file", label: "File", copyValue: (x) => x.file, fmt: (v) => h("span", null, h("span", { class: "q-tag q-amber" }, "Not built"), " ", v), csv: (x) => x.file }, { key: "error", label: "Why" }, { key: "since", label: "Failing since", type: "date", fmt: (v) => (v ? stamp(v) : "-") }],
        { caption: "Data files that could not be built", rows: failing.map((b) => ({ ...b, __k: b.file })), file: "builders-failing.csv", search: false, rowClass: () => "q-fail" })]
      : h("p", { class: "q-ok" }, h("span", { class: "q-tag q-green" }, "All built"), " Every data file was built on the last redraw.")));
  const jobs = Object.entries(f.runs || {}).map(([job, j]) => ({ job, ...j, state: jobState(j, now), __k: job }));
  out.push(h("section", { class: "s" }, h("h2", null, "Scheduled jobs, now"), h("p", { class: "sub" }, "When each job last succeeded and last failed; the date range does not apply. A late or failed job is why figures stop moving."),
    table([
      { key: "state", label: "State", type: "badge", sort: (x) => ["failed", "never", "late", "ok"].indexOf(x.state),
        fmt: (v) => h("span", { class: `q-tag q-${v === "ok" ? "green" : v === "late" ? "amber" : "red"}` }, v === "ok" ? "on time" : v === "never" ? "never ran" : v) },
      { key: "job", label: "Job", fmt: (v) => JOB_WORDS[v] || v },
      { key: "expected_every_min", label: "Runs", fmt: (_, x) => runsWords(x), csv: (x) => x.measured_every_min ?? x.expected_every_min ?? "" },
      { key: "last_ok", label: "Last succeeded", type: "date", fmt: stamp },
      { key: "last_fail", label: "Last failed", type: "date", fmt: (v, x) => (v ? `${stamp(v)}${x.last_exit ? ` (exit ${x.last_exit})` : ""}` : "-") },
    ], { caption: "Scheduled jobs", rows: jobs, file: `jobs-${m.today}.csv`, search: false, sortKey: "state", dir: 1, empty: "No job runs recorded yet." }),
    f.rotation?.files?.length ? h("p", { class: "note" }, `Log files on disk: ${f.rotation.files.map((x) => `${x.name} (${n(Math.round(x.bytes / 1024))} KB)`).join(", ")}.`) : null,
    m.x.markers?.website_version ? h("p", { class: "note" }, `The live website says it is ${m.x.markers.website_version}.`) : null));
  return out;
}
