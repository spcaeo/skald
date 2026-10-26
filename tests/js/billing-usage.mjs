// Settings > Billing & usage's usage bar and the usage banner (js/tabs/billing.js), drawn from the
// helper's real answers (tests/test_saas_usage_page.py writes them to BILLING_JSON):
// /me and GET billing for an owner, an admin and a viewer, at 85 % of the plan.
//   owner   the banner "85% of this month's requests used" with "Choose a bigger plan",
//           the bar with its 80/90/100 marks, the Choose buttons
//   admin   the same banner with "Open Billing", the bar, no Choose or Manage button
//   viewer  no banner, and Billing says only an owner
// Then made-up variants: 100 % ("used up"), over the limit (the over banner alone), the
// switch off (mark null: no banner, the bar stays).
//
//   BILLING_JSON=answers.json node tests/js/billing-usage.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install } from "./dom-lite.mjs";

install();
const answers = JSON.parse(readFileSync(process.env.BILLING_JSON, "utf8"));
let billingAnswer = null;
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => billingAnswer });
const JS = new URL("../../skald/webapp/js/", import.meta.url);
const { ME } = await import(new URL("access.js", JS));
const { planBanner, usageBar } = await import(new URL("tabs/billing.js", JS));
const billing = (await import(new URL("tabs/billing.js", JS))).default;

function as(who, plan) {
  const me = answers[who].me;
  Object.assign(ME, { mode: "sessions", role: me.role, user: me.user, org: me.org, saas: !!me.saas, plan: plan === undefined ? me.plan : plan });
  billingAnswer = answers[who].billing || null;
}
// Each warn box drawn: one, two (inside one .plan-banners element) or none.
const banners = () => { const b = planBanner(); return !b ? [] : b.className === "plan-banners" ? b.children : [b]; };
const text = (els) => els.map((e) => e.textContent).join(" | ");
async function page() {
  const root = document.createElement("div");
  root.append(...billing());
  await new Promise((r) => setTimeout(r, 20));
  return root;
}

// ---- owner: the banner and the bar
as("owner");
let got = banners();
assert.equal(got.length, 1, text(got));
assert.match(got[0].textContent, /85% of this month's requests used\./);
assert.match(got[0].textContent, /850 of the 1,000 requests the small plan allows this month \(85%\)/);
assert.match(got[0].textContent, /starts again on 1 November 2026/);
let link = got[0].querySelector("a");
assert.equal(link.getAttribute("href"), "#settings/org/billing");
assert.equal(link.textContent, "Choose a bigger plan");
let root = await page();
let meter = root.querySelector("[role]");
meter = root.querySelectorAll("div").find((d) => d.getAttribute("role") === "meter");
assert.ok(meter, "the bar is a meter");
assert.equal(meter.getAttribute("aria-valuenow"), "85");
assert.equal(root.querySelectorAll("span.ub-mark").length, 3);
assert.deepEqual(root.querySelectorAll(".ub-scale span").map((s) => s.textContent), ["80%", "90%", "100%"]);
assert.ok(root.querySelector("i.ub-fill.near"), "85 % is drawn as near the limit");
assert.match(root.textContent, /850 of 1,000 requests used this month \(85%\)/);
assert.ok(root.querySelectorAll("button").some((b) => /^Choose |Current plan/.test(b.textContent)), "owners choose");

// ---- admin: the banner, the page read-only
as("admin");
got = banners();
assert.equal(got.length, 1);
link = got[0].querySelector("a");
assert.equal(link.getAttribute("href"), "#settings/org/billing");
assert.equal(link.textContent, "Open Billing");
root = await page();
assert.ok(root.querySelectorAll("div").some((d) => d.getAttribute("role") === "meter"), "admins see the bar");
assert.equal(root.querySelectorAll("button").length, 0, "no Choose or Manage button for an admin");
assert.match(root.textContent, /Only an owner can choose a plan or change the payment\./);

// ---- viewer: nothing
as("viewer");
assert.equal(banners().length, 0, "members see no usage banner");
root = await page();
assert.match(root.textContent, /Only an owner of the organisation can see and change billing\./);
assert.equal(answers.viewer.billing_status, 403);

// ---- variants of the owner's plan
const base = answers.owner.me.plan;
as("owner", { ...base, usage: { ...base.usage, requests: 1000, percent: 100, mark: 100 } });
got = banners();
assert.match(got[0].textContent, /This month's requests are used up\./);
assert.match(got[0].textContent, /new log lines are turned away until 1 November 2026 or a bigger plan/);
assert.ok(usageBar(ME.plan).querySelector("i.ub-fill.full"));
as("owner", { ...base, over: ["requests_month"], usage: { ...base.usage, requests: 1200, percent: 120, mark: 100 } });
got = banners();
assert.equal(got.length, 1, "over the limit: the over banner only");
assert.match(got[0].textContent, /Over the plan\./);
assert.equal(usageBar(ME.plan).querySelectorAll("div").find((d) => d.getAttribute("role") === "meter").getAttribute("aria-valuenow"), "100");
as("owner", { ...base, over: ["sites"] });
assert.equal(banners().length, 2, "over another limit and at 85 %: both lines");
as("owner", { ...base, usage: { ...base.usage, mark: null } });
assert.equal(banners().length, 0, "the switch off: no banner");
assert.ok(usageBar(ME.plan), "the bar stays");
as("owner", { ...base, usage: { ...base.usage, requests: null, percent: null, mark: null } });
assert.equal(usageBar(ME.plan), null, "no day recorded: no bar");

console.log("billing-usage: all passed");
