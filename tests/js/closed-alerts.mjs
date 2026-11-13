// #55: closed alerts are listed by when they CLOSED, the last closed on top, on both alert
// pages (Site › Alerts, js/tabs/si-alerts.js; Health › Alerts, js/tabs/alerts.js). With more
// closed alerts than the 10 shown, the 10 closed last are the ones shown. Sample data only.
//
//   node tests/js/closed-alerts.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true }) });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
const SI = await import(new URL("tabs/si-alerts.js", JS));
const AL = await import(new URL("tabs/alerts.js", JS));
ME.user = "owner@example.com";
const flat = (out) => { const box = document.createElement("div"); box.append(...[out].flat(Infinity).filter((x) => x instanceof Node)); document.body.replaceChildren(box); return box; };

// Twelve closed alerts: #k opened on day k (Oct 1..12) but the first opened closed LAST
// (Oct 25 - k), so opening order and closing order are opposite.
const pad = (d) => String(d).padStart(2, "0");
const closed = Array.from({ length: 12 }, (_, i) => ({
  id: `server_errors-1-${i}`, cause: "server_errors", severity: "medium", subject: `/p${i}/`, title: `Server errors on /p${i}/`, detail: "",
  opened_at: `2026-10-${pad(i + 1)}T10:00:00+00:00`, closed_at: `2026-10-${pad(24 - i)}T10:00:00+00:00` }));
const file = { open: [], closed, rules: [{ cause: "server_errors", on: true, setting: "alerts.server_errors" }], enabled: true, mail: true, checked_at: "2026-10-26T10:00:00+00:00" };
const m = { site: "example.com", today: "2026-10-26", anchor: "2026-10-25", x: { alerts: file }, byDay: new Map() };

function titles(box) {
  const t = box.querySelectorAll("table").find((x) => (x.querySelector("caption")?.textContent || "") === "Closed alerts");
  assert.ok(t, "the closed alerts table");
  return t.querySelectorAll("tbody tr").map((r) => (r.textContent.match(/Server errors on \/p\d+\//) || [""])[0]);
}
const want = Array.from({ length: 10 }, (_, i) => `Server errors on /p${i}/`);

// ---- Site › Alerts: the fold opens on the table
history.replaceState(null, "", "#site/alerts");
let box = flat(SI.default(m, S.read()));
const f = box.querySelectorAll("details.ui-fold").find((d) => d.querySelector("summary").textContent.includes("closed in the last 30 days"));
assert.ok(f, "the closed fold");
f.fill();
assert.deepEqual(titles(box), want, "Site › Alerts: the last closed on top, the 10 closed last kept");

// ---- Health › Alerts
history.replaceState(null, "", "#health/alerts");
box = flat(AL.default(m, S.read()));
assert.deepEqual(titles(box), want, "Health › Alerts: the last closed on top, the 10 closed last kept");
assert.ok(box.textContent.includes("Closed"), "a Closed column");

console.log("closed-alerts: all passed");
process.exit(0);
