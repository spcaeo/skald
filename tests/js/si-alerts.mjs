// Site › Alerts in groups (2.41, js/tabs/si-alerts.js, js/alert-groups.js): one card per
// kind, the most urgent first; the count of what needs you (the Site badge, the bell and
// the page say the same); one primary Fix on the page; Fix opens "Who will do it?" with
// that kind's steps, kept in the address (alfix=<kind>&by=me); a kind with nothing to fix
// lists its pages; closed alerts fold; which alerts are on is one line to Settings › Alerts
// (set-alerts.js), and an old alerts_view=switches link opens that page (routes.js).
//
//   node tests/js/si-alerts.mjs
import assert from "node:assert/strict";
import { install } from "./dom-lite.mjs";

install();
Element.prototype.showModal = function showModal() { this.open = true; };
Element.prototype.close = function close() { this.open = false; };
Object.assign(globalThis.location, { origin: "https://app.example.com", pathname: "/traffic/example.com/", href: "https://app.example.com/traffic/example.com/" });
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ ok: true }) });
const tick = (ms = 5) => new Promise((r) => setTimeout(r, ms));
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const S = await import(new URL("state.js", JS));
await import(new URL("sections.js", JS));
const { ME } = await import(new URL("access.js", JS));
const G = await import(new URL("alert-groups.js", JS));
const A = await import(new URL("tabs/si-alerts.js", JS));
const { primaries } = await import(new URL("ui/primary.js", JS));
const { bell } = await import(new URL("extras.js", JS));
const site = (await import(new URL("tabs/s-site.js", JS))).default;
ME.user = "owner@example.com";
const go = (hash) => history.replaceState(null, "", hash);
const flat = (out) => { const box = document.createElement("div"); box.append(...[out].flat(Infinity).filter((x) => x instanceof Node)); document.body.replaceChildren(box); return box; };

// ---- the sample's 14 open alerts: 10 AI stopped reading, 3 advisories, 1 exposure
const ai = ["ByteDance: /guides/webhooks", "Common Crawl: /features/", "Common Crawl: /guides/team-roles", "Meta: /", "Meta: /blog/ai-crawlers-explained",
  "Meta: /blog/server-logs-vs-tags.md", "Meta: /guides/getting-started", "OpenAI: /blog/old-launch-post.md", "Perplexity: /blog/fall-launch.md", "Perplexity: /customers/"]
  .map((subject, i) => ({ id: `ai_stopped_reading-1-${i}`, cause: "ai_stopped_reading", severity: "medium", subject, opened_at: "2026-10-26T21:12:00+00:00",
    title: `${subject.split(": ")[0]} stopped reading ${subject.split(": ")[1]}`, detail: `It fetched ${subject.split(": ")[1]} in 4 of the 4 weeks before; none in the last 7 days. From figures already checked twice.` }));
const stack = [["php 8.3.10 on media.example.com: Update needed", "a09ac33204129"], ["php 8.1.2 on example.com: No official fix: upgrade the branch", "aa2ca6d392741"],
  ["nodejs version not shown on app.example.com: Check your version", "ad15a272f8aea"]]
  .map(([t, item], i) => ({ id: `stack_advisory-1-${i}`, cause: "stack_advisory", severity: "high", subject: item, opened_at: "2026-10-26T21:12:00+00:00",
    title: `Advisory for example.com: ${t}`, detail: "Update to the fixed release (Security > Your stack lists it).", data: { item } }));
const exposure = { id: "security_exposure-1-13", cause: "security_exposure", severity: "high", subject: "example.com/.env.production", opened_at: "2026-10-26T21:12:00+00:00",
  title: "Possible exposure: example.com/.env.production answered 200 (1,873 bytes)", detail: "A scanner asked for /.env.production and got a 200 with 1,873 bytes.",
  data: { category: "secrets", host: "example.com", path: "/.env.production" } };
const rules = [{ cause: "site_down", on: true, setting: "alerts.site_down" }, { cause: "ai_stopped_reading", on: true, setting: "alerts.ai_stopped_reading" }, { cause: "sale", on: false, setting: "alerts.sale" }];
const file = { open: [...ai, ...stack, exposure], closed: [], rules, enabled: true, mail: true, checked_at: "2026-10-26T21:12:00+00:00" };
const m = { site: "example.com", today: "2026-10-26", x: { alerts: file } };

// ---- the groups and the one count
const groups = G.groupsOf(file.open);
assert.deepEqual(groups.map((g) => g.cause), ["stack_advisory", "security_exposure", "ai_stopped_reading"], "urgent first (the larger first), then worth a look");
assert.deepEqual(groups.map((g) => g.alerts.length), [3, 1, 10]);
assert.equal(G.needsYou(file), 3, "3 things need you, not 14 rows");
assert.equal(G.needsYou({ open: [{ cause: "sale", severity: "low" }] }), 0, "news does not need you");
assert.equal(G.needsYou(null), 0);
assert.equal(G.pagesOf(ai).length, 10);
// The badge on the Site tab and the bell say the same.
const alertsRow = site.find((t) => t[0] === "alerts");
assert.deepEqual(alertsRow[3].badge(m), [3, "3 need you (14 open alerts)"]);
const b = bell(m);
assert.equal(b.querySelector(".bell-n").textContent, "3");
assert.ok(b.getAttribute("aria-label").startsWith("Alerts: 3 need you"));

// ---- the titles: one alert's own, or what the group shares, counted the same way
assert.equal(A.titleOf(groups[0]), "3 security advisories match your stack");
assert.equal(A.titleOf(groups[1]), exposure.title);
assert.equal(A.titleOf(groups[2]), "AI stopped reading 10 pages");
const twice = { cause: "ai_stopped_reading", alerts: [ai[0], { ...ai[0], subject: "Meta: /guides/webhooks" }] };
assert.equal(A.titleOf(twice), "AI stopped reading 1 page (2 alerts: some pages by more than one assistant)", "two counts on one card say why they differ");

// ---- the page
go("#site/alerts");
let panel = flat(A.default(m, S.read()));
const cards = panel.querySelectorAll("article.ui-card");
assert.equal(cards.length, 3, "three groups, not 14 cards");
assert.equal(panel.querySelector(".ui-lede").textContent, "3 things need you. 2 have a Fix button.");
assert.equal(primaries(panel), 1, "one primary button on the screen");
assert.equal(cards[0].querySelector(".ui-primary").textContent, "Fix", "the first Fix is the primary");
assert.equal(cards[1].querySelector(".ui-primary"), null);
assert.ok(cards[1].querySelectorAll("button").some((x) => x.textContent === "Fix"));
assert.deepEqual(cards.map((c) => c.querySelector(".ui-pill").textContent), ["Urgent", "Urgent", "Worth a look"]);
assert.equal(cards[2].querySelectorAll("button").some((x) => x.textContent === "Fix"), false, "nothing to fix: no Fix");
assert.ok(cards[2].querySelector("summary").textContent.includes("See the 10 pages"));
assert.ok(cards[2].querySelector(".ui-meta").textContent.startsWith("ByteDance, Common Crawl, Meta, OpenAI, Perplexity"));
assert.ok(panel.querySelector(".ui-help"), "the method is behind the ?");
assert.equal(panel.textContent.includes("An alert opens when its rule is met"), true, "in the popover, closed");
assert.ok(panel.querySelector(".ui-help-pop").hidden);
assert.ok(panel.textContent.includes("Nothing closed in the last 30 days."));
const sw = panel.querySelector("p.al-on");
assert.ok(sw.textContent.startsWith("Which alerts are on: 2 of 3."), sw.textContent);
assert.ok(!panel.querySelectorAll("details.ui-fold").find((d) => d.querySelector("summary").textContent.startsWith("Which alerts are on")), "no fold: one line");
assert.ok(sw.querySelector("a").getAttribute("href").startsWith("#settings/site/alerts"), "the line links to Settings › Alerts");
const { resolve } = await import(new URL("routes.js", JS));
const old = resolve("site/alerts", {}, new URLSearchParams("alerts_view=switches"));
assert.equal(old.tab, "settings/site/alerts", "an old switches link opens the settings page");
assert.equal(old.patch.alerts_view, "");
assert.equal(resolve("site/alerts", {}, new URLSearchParams("alerts_view=ai")).tab, "site/alerts", "other views stay");
// ---- Settings › This site › Alerts: the switches, on a page of their own
const { alertsSettings } = await import(new URL("tabs/set-alerts.js", JS));
const sp = flat(alertsSettings(m));
assert.ok(sp.querySelector(".set-alerts .set-strip"), "its state line (tests/js/set-alerts.mjs has the rest)");
assert.ok(sp.querySelector(".set-alerts .al-fold"), "the rules in folds by area");
assert.ok(sp.querySelector(".ui-help"), "what it is for, behind the ?");
assert.ok(flat(alertsSettings({ x: {} })).textContent.includes("No alerts file yet"));
go("#site/alerts");

// ---- Fix: Who will do it? with this kind's steps, in the address
panel = flat(A.default(m, S.read()));
panel.querySelectorAll("article.ui-card")[1].querySelectorAll("button").find((x) => x.textContent === "Fix").click();
const drawerOf = () => document.body.childNodes.find((x) => String(x.className || "").includes("ui-who-dw"));
for (let i = 0; i < 100 && !drawerOf(); i += 1) await tick(10);
let s = S.read();
assert.equal(s.alfix, "security_exposure", "the dialog is in the address by its kind");
const dlg = drawerOf();
assert.ok(dlg.textContent.includes("Who will do it?"));
assert.deepEqual(dlg.querySelectorAll(".ui-who-c").map((x) => x.dataset.who), ["me", "dev"], "no AI agent job for an exposure: not offered");
assert.equal(dlg.querySelector('[aria-checked="true"]').dataset.who, "me", "Me by default");
await tick(20);
assert.ok(dlg.textContent.includes("Deny dotfiles and key files at the web server"), "the advice Security gives");
assert.ok(dlg.textContent.includes("location ~ /\\. { deny all; }"));
assert.ok(dlg.querySelector(".ui-who-path .ua-copy"), "the line has its copy icon");
dlg.querySelector('[data-who="dev"]').click();
await tick(20);
assert.equal(S.read().by, "dev");
assert.ok(dlg.querySelector(".ui-msg").textContent.includes("Skald found this on example.com: Possible exposure"));
assert.ok(dlg.querySelector(".ui-msg").textContent.includes("deny all"));
assert.ok(dlg.querySelector(".ua-open"), "the link to this place has its open icon");
// I have done it: closes, and says when Skald checks again.
dlg.querySelectorAll("button").find((x) => x.textContent === "I have done it").click();
await tick(400);
assert.equal(S.read().alfix, "", "closed");

// A link opens it; a kind that is not open says so in plain words.
assert.equal(await A.openFixKey("site_down", m), "That alert is closed now, or it is not available to you.");
const logs = { ...m, x: { alerts: { ...file, open: [{ id: "logging_stopped-1-0", cause: "logging_stopped", severity: "high", subject: "", title: "No log lines for 2 hours", detail: "The last line was read at 09:00.", opened_at: "2026-10-26T11:00:00+00:00" }] } } };
go("#site/alerts?alfix=logging_stopped&by=agent");
const d2 = await A.openFixKey("logging_stopped", logs);
assert.deepEqual(d2.el.querySelectorAll(".ui-who-c").map((x) => x.dataset.who), ["me", "dev", "agent"], "logging stopped: the agent kit's logs job");
assert.equal(d2.who.choice(), "agent", "the address opens on its answer");
d2.close({ instant: true });

// The steps keep the places the old cards linked to: the request log of a path, Your stack.
const path = A._parts.stepsOf({ cause: "server_errors", alerts: [{ title: "Server errors on /api/", subject: "/api/", detail: "40 answers 5xx." }] });
assert.ok(flat(path).textContent.includes("See the recent requests to /api/"));
const st = flat(A._parts.stepsOf(groups[0]));
assert.equal(st.querySelectorAll("button").filter((x) => x.textContent === "Open Security › Your stack").length, 3, "each advisory opens its item on Your stack");

// Nothing open: says so, no primary.
panel = flat(A.default({ ...m, x: { alerts: { ...file, open: [] } } }, S.read()));
assert.ok(panel.textContent.includes("No alert is open."));
assert.equal(primaries(panel), 0);

console.log("si-alerts: all passed");
process.exit(0);
