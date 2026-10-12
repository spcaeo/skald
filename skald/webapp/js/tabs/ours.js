// Our own traffic: the office, our crawler, our tests and the heartbeat, by
// label. Not traffic - it is shown so the five groups add up. The heartbeat
// doubles as an uptime check; its uptime and gaps are on Site > Health.

import { h, n, long, counter } from "../ui.js";
import * as S from "../state.js";
import { figures, color, chartDays } from "../data.js";
import { columns, legend, bars } from "../charts.js";
import { head, nothing, coverageNote, blist, panel, countTable, fileName, compareFor } from "./common.js";
import { ipManager } from "./ipmanager.js";

const TONES = ["var(--g-ours)", "var(--g-people)", "var(--views)", "var(--g-bots)", "var(--ink-3)"];
const HEARTBEAT = /heartbeat/i;

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
  // Uptime and every heartbeat gap live on Site > Health (2.7.0): one place for "is the site up?".
  out.push(h("p", { class: "tr-goto" }, "Uptime from the heartbeat, with every outage and gap, is under ",
    h("a", { href: S.hashFor({ ...s, tab: "site/health", dd: "" }) }, "Site › Health", h("span", { "aria-hidden": "true" }, " ›"))));
  if (r.kind === "history") {
    const last = [...(m.x.ours?.days || [])].reverse().find((d) => d.state === "ok" && d.hours && d.day <= r.last);
    if (last) {
      const hrs = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
      out.push(h("section", { class: "s" }, panel(`How fast the server answered, ${long(last.day)}`, "95th percentile of server time per hour, every request to the site (milliseconds)",
        bars(hrs.map((hh) => ({ label: hh, title: `${hh}:00, p50 ${last.hours[hh]?.p50_ms ?? "-"} ms`, value: last.hours[hh]?.p95_ms || 0, color: "var(--g-people)" })), { label: "p95 server time by hour", unit: "ms (p95)", every: 3, H: 180 }))));
    }
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
