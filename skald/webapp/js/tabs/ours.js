// Our own traffic: the office, our crawler, our tests and the heartbeat, by
// label. Not traffic - it is shown so the five groups add up - but the
// heartbeat doubles as an uptime check: one request every five minutes.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, short, long, tip, untip, counter, clock } from "../ui.js";
import { figures, color, chartDays } from "../data.js";
import { columns, legend, bars } from "../charts.js";
import { head, nothing, coverageNote, blist, panel, countTable, fileName, compareFor } from "./common.js";
import { ipManager } from "./ipmanager.js";
import { table } from "../table.js";

const TONES = ["var(--g-ours)", "var(--g-people)", "var(--views)", "var(--g-bots)", "var(--ink-3)"];
const HEARTBEAT = /heartbeat/i;
const PER_HOUR = 12;   // one heartbeat every five minutes

// Hours a heartbeat should have reached the server and did not: an outage, or the heartbeat itself stopped.
function heartbeatOf(d) {
  if (d.state !== "ok") return null;
  if (d.heartbeat?.hours) return d.heartbeat.hours;
  return null;
}

// From ours.json: uptime per day as the heartbeat measured it, and every gap.
function heartbeatFile(f, r) {
  const days = (f.days || []).filter((d) => d.day >= r.first && d.day <= r.last);
  const el = h("div", { class: "uptime", role: "img" });
  let ok = 0, expected = 0;
  const gaps = [];
  for (const d of days) {
    const hb = d.state === "ok" ? d.heartbeat : null;
    const label = hb ? `${long(d.day)}: ${hb.uptime_pct == null ? "not measured" : `${hb.uptime_pct}% answered`}${hb.gaps?.length ? `, ${hb.gaps.length} gap${hb.gaps.length === 1 ? "" : "s"}` : ""}` : `${long(d.day)}: not shown`;
    if (hb) { ok += hb.ok || 0; expected += hb.expected || 0; gaps.push(...(hb.gaps || []).map((g) => ({ ...g, day: d.day }))); }
    const cell = h("i", { class: hb ? (hb.gaps?.length || hb.failed ? "gap" : "") : "none", tabindex: "0", "aria-label": label });
    const show = (x, y) => tip(x, y, short(d.day), [{ value: "", label: label.split(": ")[1] }]);
    cell.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    cell.addEventListener("pointerleave", untip);
    cell.addEventListener("focus", () => { const b = cell.getBoundingClientRect(); show(b.left + b.width / 2, b.top); });
    cell.addEventListener("blur", untip);
    el.append(cell);
  }
  el.setAttribute("aria-label", `Heartbeat uptime by day, ${days.length} days`);
  return { el, share: expected ? ok / expected : null, gaps };
}

function strip(days) {
  const el = h("div", { class: "uptime", role: "img" });
  let up = 0, all = 0;
  const words = [];
  for (const d of days) {
    if (d.state === "before") continue;
    const hours = heartbeatOf(d);
    const count = d.state === "ok" ? Object.entries(d.ours_by || {}).filter(([k]) => HEARTBEAT.test(k)).reduce((a, [, v]) => a + v, 0) : null;
    let cls = "none", label = `${long(d.day)}: not shown`;
    if (hours) {
      const missed = Object.values(hours).filter((v) => v < PER_HOUR).length + (24 - Object.keys(hours).length);
      all += 24; up += 24 - missed;
      cls = missed ? "gap" : "";
      label = `${long(d.day)}: ${missed ? `${missed} hour${missed === 1 ? "" : "s"} with missed heartbeats` : "every hour answered"}`;
    } else if (count != null) {
      const expected = 24 * PER_HOUR;
      all += expected; up += Math.min(count, expected);
      cls = count < expected * 0.98 ? "gap" : "";
      label = `${long(d.day)}: ${n(count)} of ${n(expected)} heartbeats answered`;
    }
    words.push(label);
    const cell = h("i", { class: cls, tabindex: "0", "aria-label": label });
    const show = (x, y) => tip(x, y, short(d.day), [{ value: "", label: label.split(": ")[1] }]);
    cell.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
    cell.addEventListener("pointerleave", untip);
    cell.addEventListener("focus", () => { const b = cell.getBoundingClientRect(); show(b.left + b.width / 2, b.top); });
    cell.addEventListener("blur", untip);
    el.append(cell);
  }
  el.setAttribute("aria-label", `Heartbeat by day: ${words.length} days`);
  return { el, share: all ? up / all : null };
}

export default function ours(m, s, { first }) {
  const { r, t, cov } = figures(m, s);
  const out = [...head("Our own traffic", r, "Requests from our own machines and tools: the office, our crawler, browser tests and the heartbeat. They are not visitors; they are counted here so that the five groups add up to the log.", { shown: true })];
  const manager = h("section", { class: "s" }, h("h2", null, "Internal addresses"),
    h("p", { class: "sub" }, "Requests from these addresses count as our own traffic, not as visitors. Add the office, home connections and test machines."),
    h("div", { class: "sheet" }, m.x.ours?.api ? ipManager(m.x.ours.api)
      : h("p", { class: "empty" }, "Managing internal addresses here is coming with the next data update. Until then they are set in the config file.")));
  if (!t) return [...out, nothing(m, r), manager];
  const labels = Object.keys(t.ours_by || {}).sort((a, b) => (t.ours_by[b] || 0) - (t.ours_by[a] || 0));
  out.push(h("section", { class: "s" }, h("div", { class: "kpis" },
    h("div", { class: "kpi" }, h("div", { class: "k-l" }, "Our own requests"), h("div", { class: "k-n" }, "every machine and tool together"),
      h("div", { class: "k-v" }, first ? counter(t.hits?.ours ?? 0) : n(t.hits?.ours ?? 0)), h("div", { class: "k-c" }, h("span", { class: "sw", style: { background: color("ours") } }), "requests")),
    ...labels.slice(0, 3).map((k, i) => h("div", { class: "kpi" }, h("div", { class: "k-l" }, k), h("div", { class: "k-n" }, HEARTBEAT.test(k) ? "one request every five minutes" : "requests"),
      h("div", { class: "k-v" }, n(t.ours_by[k])), h("div", { class: "k-c" }, h("span", { class: "sw", style: { background: TONES[i % TONES.length] } }), "requests"))))));
  if (r.kind === "history" && m.x.ours) {
    const { el, share, gaps } = heartbeatFile(m.x.ours, r);
    out.push(h("section", { class: "s" }, h("h2", null, "Uptime, from the heartbeat"),
      h("p", { class: "sub" }, share == null ? "No heartbeat recorded in this range." : `${(share * 100).toFixed(share > 0.999 ? 2 : 1)}% of heartbeats were answered. A red day had a gap of more than 10 minutes or a failed answer: the site was down, or the heartbeat itself stopped.`),
      h("div", { class: "sheet" }, el, h("div", { class: "scale" }, h("span", { class: "sw", style: { background: "var(--good)" } }), "all answered",
        h("span", { class: "sw", style: { background: "var(--bad)", marginLeft: "12px" } }), "gap or failure", h("span", { class: "sw", style: { background: "var(--sunk)", marginLeft: "12px" } }), "not shown")),
      table([{ key: "from", label: "From", fmt: (v) => tzTime(v, { date: true }) }, { key: "to", label: "To", fmt: (v) => tzTime(v) }, { key: "minutes", label: "Minutes", num: true }],
        { caption: "Outages and heartbeat gaps", rows: gaps, file: fileName("heartbeat-gaps", r), search: false, sortKey: "from", dir: -1, empty: "No gap longer than 10 minutes in this range." })));
    const last = [...(m.x.ours.days || [])].reverse().find((d) => d.state === "ok" && d.hours && d.day <= r.last);
    if (last) {
      const hrs = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
      out.push(h("section", { class: "s" }, panel(`How fast the server answered, ${long(last.day)}`, "95th percentile of server time per hour, every request to the site (milliseconds)",
        bars(hrs.map((hh) => ({ label: hh, title: `${hh}:00, p50 ${last.hours[hh]?.p50_ms ?? "-"} ms`, value: last.hours[hh]?.p95_ms || 0, color: "var(--g-people)" })), { label: "p95 server time by hour", unit: "ms (p95)", every: 3, H: 180 }))));
    }
  } else if (r.kind === "history") {
    const { el, share } = strip(chartDays(r));
    out.push(h("section", { class: "s" }, h("h2", null, "Uptime, from the heartbeat"),
      h("p", { class: "sub" }, share == null ? "No heartbeat recorded in this range." : `${(share * 100).toFixed(share > 0.999 ? 2 : 1)}% of heartbeats were answered. A red day missed some: the site was down, or the heartbeat itself stopped.`),
      h("div", { class: "sheet" }, el, h("div", { class: "scale" }, h("span", { class: "sw", style: { background: "var(--good)" } }), "all answered",
        h("span", { class: "sw", style: { background: "var(--bad)", marginLeft: "12px" } }), "some missed", h("span", { class: "sw", style: { background: "var(--sunk)", marginLeft: "12px" } }), "not shown"))));
    if (r.length > 1 && labels.length) {
      const series = labels.slice(0, 5).map((k, i) => ({ name: k, color: TONES[i], get: (d) => d.ours_by?.[k] || 0 }));
      out.push(h("section", { class: "s" }, h("h2", null, "Per day, by machine or tool"),
        h("div", { class: "sheet" }, legend([...series.map((x) => [x.name, x.color]), ["Not shown", "", "hatch"]]), columns(chartDays(r), series, { label: "Our own requests per day", H: 210, prev: compareFor(m, s).prev }))));
    }
  }
  out.push(h("div", { class: "cols" },
    panel("By machine or tool", "Labels come from the config: addresses and user agents we know are ours", blist(labels.map((k) => [k, t.ours_by[k]]), { color: color("ours"), empty: "None of our own traffic in this range." })),
    t.ours_speed ? panel("How fast the heartbeat was answered", "Server time, by bucket", blist(Object.entries(t.ours_speed), { color: "var(--good)" })) : null));
  out.push(manager);
  out.push(h("section", { class: "s" }, h("h2", null, "All our own traffic"),
    countTable(t.ours_by, { caption: "Our own traffic by label", file: fileName("ours", r), key: "Machine or tool", value: "Requests" })));
  out.push(coverageNote(cov, r));
  return out;
}
