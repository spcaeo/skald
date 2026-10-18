// Is the site up? Two views side by side on Site health: our own heartbeat
// (a request every five minutes from the server itself, ours.json) and an
// outside check from another server (ours.json `outside`, owned by the relay
// part; null until the owner approves it, and then said so).

import { h, n, short } from "../ui.js";
import { time as tzTime } from "../tz.js";
import { heartbeatOn } from "../notset.js";

// A heartbeat never seen is "not set up" (notset.js heartbeatOn): no 0%, no outages.
export { heartbeatOn };

function heartbeat(f, r) {
  if (!heartbeatOn(f)) {
    return h("div", { class: "sheet up-card off" }, h("h3", null, "Our heartbeat"), h("p", { class: "sub" }, "The server asks for its own page every 5 minutes"),
      h("p", { class: "up-off" }, h("b", null, "Heartbeat not set up. "), "No heartbeat has reached the log yet, so there is no uptime figure and no outage list. To set it up: a cron line on the server asks for one small page of your site every 5 minutes with the heartbeat's own user agent, and the config labels that agent as the heartbeat (DEPLOY.md, the heartbeat line)."));
  }
  const days = (f?.days || []).filter((d) => d.day >= r.first && d.day <= r.last && d.heartbeat);
  if (r.kind === "today" && f?.today?.heartbeat) days.push(f.today);
  const exp = days.reduce((a, d) => a + (d.heartbeat.expected || 0), 0), ok = days.reduce((a, d) => a + (d.heartbeat.ok || 0), 0);
  const gaps = days.flatMap((d) => d.heartbeat.gaps || []);
  return h("div", { class: "sheet up-card" }, h("h3", null, "Our heartbeat"), h("p", { class: "sub" }, "The server asks for its own page every 5 minutes"),
    exp ? [h("p", { class: "up-v" }, `${Math.min(100, (100 * ok) / exp).toFixed(2)}%`), h("p", { class: "up-n" }, `${ok >= exp ? `All ${n(exp)} expected beats answered` : `${n(ok)} of ${n(exp)} expected beats answered`}${gaps.length ? `; ${gaps.length} gap${gaps.length === 1 ? "" : "s"} longer than 10 minutes` : ""}. `, h("a", { href: "#site/health" }, "Every gap"))]
      : h("p", { class: "empty" }, "No heartbeat recorded for this range."));
}

function outside(o, r) {
  const head = [h("h3", null, "Outside check"), h("p", { class: "sub" }, "From another server, as a visitor would see it")];
  if (!o || o.enabled === false) return h("div", { class: "sheet up-card off" }, head, h("p", { class: "up-off" }, "Not set up. An outside check runs from a second server and posts its result here; your server admin can set it up."));
  if (!o.last) return h("div", { class: "sheet up-card" }, head, h("p", { class: "empty" }, "Set up; no check has run yet."));
  const days = (o.days || []).filter((d) => r.kind === "today" ? true : d.day >= r.first && d.day <= r.last);
  const checks = days.reduce((a, d) => a + (d.checks || 0), 0), ok = days.reduce((a, d) => a + (d.ok || 0), 0);
  const outs = (o.outages || []).filter((x) => r.kind === "today" || (x.from.slice(0, 10) >= r.first && x.from.slice(0, 10) <= r.last));
  return h("div", { class: "sheet up-card" }, head,
    checks ? h("p", { class: "up-v" }, `${Math.min(100, (100 * ok) / checks).toFixed(2)}%`) : null,
    h("p", { class: "up-n" }, `Last check ${tzTime(o.last.at, { date: true })}: `, h("b", { class: o.last.ok ? "up-ok" : "up-bad" }, o.last.ok ? `up, ${n(o.last.ms)} ms` : `down (${o.last.status || "no answer"})`),
      checks ? `. ${n(ok)} of ${n(checks)} checks answered, every ${o.checked_every_min || 1} min.` : "."),
    outs.length ? h("ul", { class: "up-outs" }, outs.slice(0, 5).map((x) => h("li", null, `${tzTime(x.from, { date: true })}, ${n(x.minutes)} min down`))) : null);
}

export function uptime(m, r) {
  const f = m.x.ours;
  if (!f) return null;
  return h("section", { class: "s" }, h("h2", null, "Is the site up?"), h("div", { class: "cols" }, heartbeat(f, r), outside(f.outside, r)));
}
