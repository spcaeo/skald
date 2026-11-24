// SKALD-55: Google Analytics' figures on Overview (js/tabs/ov-tools.js, ov-tools-drawer.js),
// against an answer shaped as yourtools/api.py gives it (no network):
//  - the card: a share reads as a percent, seconds as minutes, each figure's change against
//    the tool's own 28 days before ("previous"), a share's in points; Today's card says the
//    figures are the tool's own days, never today's; "All figures from Google Analytics" only
//    when the tool gave a table
//  - the drawer (ytool=ga4): the totals against the days before, then channels, sources,
//    landing pages, devices, countries and events in that order, the tool's rows in its own
//    order, each row's share of the tool's own total, the tool's notes; opened from the
//    address too; a tool not connected opens nothing, with one plain line
//
//   node tests/js/ga-figures.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
const SITE = "example.com";
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: `/traffic/${SITE}/` });
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
globalThis.matchMedia = () => ({ matches: true, addEventListener() {}, addListener() {} });
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

const fig = (name, label, value, dim = null, rank = null, unit) => ({ name, label, value, dim, rank, ...(unit ? { unit } : {}) });
const table = (title, rows, tot) => ({ title, start: "2026-10-27", end: "2026-11-23", flags: [], figures: [
  fig("sessions", "Sessions", tot[0]), fig("keyEvents", "Key events", tot[1]),
  ...rows.flatMap(([dim, s, k], i) => [fig("sessions", "Sessions", s, dim, i), fig("keyEvents", "Key events", k, dim, i)])] });
const GA = { id: "ga4", name: "Google Analytics", state: "answering", pill: "good", words: "Answering", ago: "2 h ago",
  counted_from: "Counted from: Google Analytics",
  period: { start: "2026-10-27", end: "2026-11-23", note: "the property's own days, America/New_York" },
  headline: [fig("sessions", "Sessions", 1234), fig("totalUsers", "Users", 980), fig("newUsers", "New users", 812),
    fig("engagementRate", "Engagement rate", 0.5680713128, null, null, "share"),
    fig("averageSessionDuration", "Average session", 94.27, null, null, "seconds"), fig("keyEvents", "Key events", 37)],
  before: { sessions: 1100, totalUsers: 980, newUsers: null, engagementRate: 0.5436363636, averageSessionDuration: 88.4, keyEvents: 0 },
  before_period: { start: "2026-09-29", end: "2026-10-26" },
  reports: {
    totals: { title: "Totals", start: "2026-10-27", end: "2026-11-23", flags: ["Thresholded: Google hid some small numbers"], figures: [
      fig("sessions", "Sessions", 1234), fig("engagementRate", "Engagement rate", 0.5680713128, null, null, "share"), fig("keyEvents", "Key events", 37)] },
    previous: { title: "The 28 days before", start: "2026-09-29", end: "2026-10-26", flags: [], figures: [
      fig("sessions", "Sessions", 1100), fig("engagementRate", "Engagement rate", 0.5436363636, null, null, "share"), fig("keyEvents", "Key events", 0)] },
    landing: table("Landing pages", [["/", 512, 9], ["/pricing/", 201, 14]], [1234, 37]),
    events: { title: "Events, key events first", start: "2026-10-27", end: "2026-11-23", flags: [], figures: [
      fig("keyEvents", "Key events", 37), fig("eventCount", "Events", 6420),
      fig("keyEvents", "Key events", 22, "generate_lead", 0), fig("eventCount", "Events", 22, "generate_lead", 0)] },
    channels: { ...table("Channels", [["Organic Search", 610, 21], ["Direct", 402, 9]], [1234, 37]), flags: ["Sampled: Google counted part of the data"] },
  } };
let figures = { ok: true, site: SITE, tools: [GA], connected: 1 };
globalThis.fetch = async (path) => {
  const answer = (data, st = 200) => ({ ok: st < 300, status: st, json: async () => structuredClone(data), headers: { get: () => null } });
  if (path === "integrations/yourtools/figures") return answer(figures);
  return answer({ ok: false, error: "not found" }, 404);
};

const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
Object.assign(ME, { mode: "sessions", role: "viewer", user: "viewer@example.com" });
const T = await import(new URL("tabs/ov-tools.js", JS));
const D = await import(new URL("tabs/ov-tools-drawer.js", JS));
const { read: readState } = await import(new URL("state.js", JS));
const dialog = () => document.body.querySelectorAll("dialog").filter((d) => d.open).pop();
history.replaceState(null, "", "#overview/summary");

// ---- the words: a share, seconds, a count; a change in percent, a share's in points
assert.equal(T.said(0.5680713128, "share"), "56.8%");
assert.equal(T.said(94.27, "seconds"), "1m 34s");
assert.equal(T.said(42, "seconds"), "42s");
assert.equal(T.said(null, "share"), "Not given");
assert.deepEqual(T.change(1234, 1100), { dir: "up", text: "+12%" });
assert.deepEqual(T.change(0.5680713128, 0.5436363636, "share"), { dir: "up", text: "+2.4 pts" });
assert.deepEqual(T.change(90, 100), { dir: "down", text: "−10%" });
assert.equal(T.change(37, 0), null, "nothing before: no percent");
assert.equal(T.change(812, null), null, "not given before: no change");

// ---- the card on a period: the units, the changes, the button
let card = T.toolsCard();
await tick(40);
let line = card.querySelector(".yt-line");
assert.deepEqual(line.querySelectorAll(".yt-fig b").map((b) => b.textContent), ["1,234", "980", "812", "56.8%", "1m 34s", "37"]);
assert.deepEqual(line.querySelectorAll(".yt-chg").map((c) => c.textContent), ["▲ +12%", "0%", "▲ +2.4 pts", "▲ +6.6%"]);
assert.ok(line.querySelector(".yt-chg.up").getAttribute("title").includes("2026-09-29 to 2026-10-26"), "the days compared, on hover");
assert.ok(line.textContent.includes("Changes: against its own 2026-09-29 to 2026-10-26"));
assert.ok(!card.classList.contains("yt-today"));
const open = line.querySelector("button.yt-open");
assert.equal(open.textContent, "All figures from Google Analytics");

// ---- the drawer: the totals now and before, then the tables in order, shares, notes
open.click();
await tick(40);
const d = dialog();
assert.ok(d, "the drawer opened");
assert.equal(readState().ytool, "ga4", "its address");
assert.equal(d.querySelector(".dw-title").textContent, "Google Analytics: all its figures");
assert.deepEqual(d.querySelectorAll(".yt-sec").map((s) => s.getAttribute("data-report")), ["totals", "channels", "landing", "events"],
  "totals, then channels before landing pages, events last");
const tot = d.querySelector('.yt-sec[data-report="totals"]');
assert.deepEqual(tot.querySelectorAll("thead th").map((x) => x.textContent), ["Figure", "2026-10-27 to 2026-11-23", "2026-09-29 to 2026-10-26", "Change"]);
assert.deepEqual(tot.querySelectorAll("tbody tr")[1].querySelectorAll("td").map((x) => x.textContent), ["56.8%", "54.4%", "+2.4 pts"]);
assert.equal(tot.querySelectorAll("tbody tr")[2].querySelectorAll("td")[2].textContent, "-", "37 key events from 0: no percent");
const ch = d.querySelector('.yt-sec[data-report="channels"]');
assert.deepEqual(ch.querySelectorAll("tbody th").map((x) => x.textContent), ["Organic Search", "Direct"], "the tool's own order");
assert.deepEqual(ch.querySelectorAll("tbody tr")[0].querySelectorAll("td").map((x) => x.textContent), ["610", "21", "49%"]);
assert.deepEqual(ch.querySelectorAll("tfoot td").map((x) => x.textContent), ["1,234", "37", "100%"]);
assert.ok(ch.textContent.includes("Sampled: Google counted part of the data"), "the tool's note on its table");
assert.ok(ch.textContent.includes("may add up to less"));
const ev = d.querySelector('.yt-sec[data-report="events"]');
assert.deepEqual(ev.querySelectorAll("thead th").map((x) => x.textContent), ["Events, key events first", "Key events", "Events", "Share"]);
assert.ok(d.textContent.includes("never added to Skald's figures"));
d.querySelector(".dw-x")?.click();
await tick(20);

// ---- from the address: the figures fetched, the drawer drawn; a tool not connected: a line
const again = await D.openToolKey("ga4");
assert.ok(again && again.el, "a link opens it");
again.close();
assert.match(await D.openToolKey("vercel"), /not connected on this site/);
assert.match(await D.openToolKey("../x"), /not connected/);

// ---- Overview › Today: the same card, saying whose days these are
card = T.toolsCard(null, { today: true });
await tick(40);
assert.ok(card.classList.contains("yt-today"));
assert.ok(card.querySelector(".td-sub").textContent.includes("never today's"));
assert.ok(card.classList.contains("td-card"), "a card as Today's others");
assert.equal(card.querySelectorAll(".sheet").length, 0, "no card inside the card");
assert.ok(card.querySelector(".yt-t .ui-help"), "the ? beside the title");
assert.ok(card.querySelector("button.yt-open"));

// ---- no table beyond the totals (an older answer): no button; withheld: no figure, no button
figures = { ok: true, site: SITE, tools: [{ ...GA, before: undefined, before_period: undefined, reports: { totals: GA.reports.totals } }] };
card = T.toolsCard();
await tick(40);
assert.equal(card.querySelectorAll("button.yt-open").length, 0);
assert.equal(card.querySelectorAll(".yt-chg").length, 0, "no days before: no change");
figures = { ok: true, site: SITE, tools: [{ ...GA, withheld: "Withheld: Skald's recheck did not match.", headline: [] }] };
card = T.toolsCard();
await tick(40);
assert.equal(card.querySelectorAll("button.yt-open").length, 0);

console.log("ga-figures: all passed");
process.exit(0);
