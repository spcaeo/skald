// Settings > Billing & usage (saas, docs/SAAS.md): shown only when /me says the server sells
// plans, to the organisation's owners, and to its admins to read (the usage alerts mail
// them and link here). GET <page>/billing gives the plan, its status, this month's usage
// against the limits and the plans to choose from. "Choose" asks the helper for a Stripe
// Checkout address (POST billing/checkout) and goes there; "Manage billing" does the same
// for Stripe's customer portal; both are owners' only. The page never sees a card number
// or a Stripe key. `planBanner` is the line every page shows when the organisation is
// over a limit or read-only, and, to owners and admins, when this month's requests reach
// 80, 90 or 100 % of the plan (saas/usage_alerts.py; `usage.mark`, null when switched off).

import { h } from "../ui.js";
import { call } from "./ipmanager.js";
import { ME } from "../access.js";
import { head1, status, why } from "./forms.js";

const STATUS = { trialing: "trial", active: "active", past_due: "payment overdue", canceled: "cancelled", none: "no plan chosen" };
const LIMIT_NAME = { sites: "Sites", requests_month: "Requests this month", members: "Members", retention_days_max: "Detail kept (days)" };
const OVER_WORDS = { sites: "more sites", requests_month: "more requests this month", members: "more members" };
const STRIPE = /^https:\/\/(?:checkout|billing)\.stripe\.com\//;
export const MARKS = [80, 90, 100];
const num = (n) => (n == null ? "no limit" : Number(n).toLocaleString("en-US"));
const canSee = () => ME.role === "owner" || ME.role === "admin";

// The usage line for owners and admins at 80 % or more; never for viewers.
export function usageBanner(p = ME.plan) {
  const u = p?.usage, mark = u?.mark;
  if (!canSee() || !mark || (p.over || []).includes("requests_month")) return null;
  const counts = `${num(u.requests)} of the ${num(p.limits?.requests_month)} requests the ${p.name} plan allows this month (${u.percent}%)`;
  const lead = mark >= 100 ? "This month's requests are used up. " : `${u.percent}% of this month's requests used. `;
  const then = mark >= 100 ? `Past the limit, new log lines are turned away until ${u.resets_on} or a bigger plan.`
    : `The count starts again on ${u.resets_on}. Past 100%, new log lines are turned away.`;
  return h("div", { class: "state warn usage-banner", role: "status" }, h("div", null, h("strong", null, lead),
    `This organisation has used ${counts}. ${then} `, h("a", { href: "#settings/org/billing" }, ME.role === "owner" ? "Choose a bigger plan" : "Open Billing")));
}

// The banners over every page: read-only (payment overdue); else over a limit (nothing is
// lost) and the usage line. One element (both lines in one box when both apply), or null.
export function planBanner() {
  const p = ME.plan;
  if (!p) return null;
  if (p.read_only) {
    return h("div", { class: "state warn", role: "status" }, h("div", null, h("strong", null, "Read-only. "), p.read_only_why || "Settings cannot be changed now.",
      ME.role === "owner" ? [" ", h("a", { href: "#settings/org/billing" }, "Open Billing")] : null));
  }
  const over = (p.over || []).map((k) => OVER_WORDS[k] || k);
  const got = [over.length ? h("div", { class: "state warn", role: "status" }, h("div", null, h("strong", null, "Over the plan. "),
    `This organisation has ${over.join(" and ")} than the ${p.name} plan allows. Nothing is deleted.`,
    ME.role === "owner" ? [" ", h("a", { href: "#settings/org/billing" }, "Choose a bigger plan")] : " Ask an owner to choose a bigger plan.")) : null,
  usageBanner(p)].filter(Boolean);
  return got.length > 1 ? h("div", { class: "plan-banners" }, got) : got[0] || null;
}

// This month's requests as a bar with the 80, 90 and 100 % marks; null without a limit or a count.
export function usageBar(p) {
  const u = p?.usage, limit = p?.limits?.requests_month;
  if (limit == null || u?.requests == null || u?.percent == null) return null;
  const fill = Math.min(100, u.percent);
  const level = u.percent >= 100 ? "full" : u.percent >= 80 ? "near" : "ok";
  return h("div", { class: "usage-bar" },
    h("p", { class: "sub" }, h("b", null, `${num(u.requests)} of ${num(limit)}`), ` requests used this month (${u.percent}%). The count starts again on ${u.resets_on}.`),
    h("div", { class: "ub-track", role: "meter", "aria-label": "Requests used this month", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(fill), "aria-valuetext": `${u.percent}%` },
      h("i", { class: `ub-fill ${level}`, style: { width: `${fill}%` } }),
      MARKS.map((m) => h("span", { class: "ub-mark", style: { left: `${m}%` }, "aria-hidden": "true" }))),
    h("div", { class: "ub-scale", "aria-hidden": "true" }, MARKS.map((m) => h("span", { style: { left: `${m}%` } }, `${m}%`))),
    h("p", { class: "note" }, "Owners and admins get one mail at 80%, 90% and 100% each month. Past 100%, new log lines are turned away: Skald's shipper keeps them and sends them again, a Cloudflare Worker's are lost."));
}

function usageRows(plan) {
  const used = { sites: plan.used?.sites, members: plan.used?.members, requests_month: plan.usage?.requests, retention_days_max: null };
  return Object.keys(LIMIT_NAME).map((k) => {
    let now = used[k] == null ? "" : num(used[k]);
    if (k === "requests_month" && plan.usage?.withheld) now = "withheld";
    else if (k === "requests_month" && plan.usage?.requests == null) now = "no day recorded yet";
    const over = (plan.over || []).includes(k);
    return h("tr", null, h("th", { scope: "row" }, LIMIT_NAME[k]), h("td", { class: "n" }, now), h("td", { class: "n" }, num(plan.limits?.[k])),
      h("td", { class: "c" }, over ? h("span", { class: "tf off" }, "over") : ""));
  });
}

export default function billing() {
  const title = head1("Billing", ME.org ? `${ME.org}'s plan, usage and payment.` : "The plan, usage and payment.");
  if (!ME.saas) return [title, h("div", { class: "state" }, h("div", null, "This server does not sell plans."))];
  if (!canSee()) return [title, h("div", { class: "state" }, h("div", null, "Only an owner of the organisation can see and change billing."))];
  const box = h("div", { class: "acct" }, h("p", { class: "empty" }, "Loading the plan..."));
  const msg = status();
  const back = new URLSearchParams(location.hash.split("?")[1] || "").get("checkout");
  if (back === "done") msg.say("Thank you. Stripe confirms the payment in a moment; this page shows it after a reload.", true);
  if (back === "cancelled") msg.say("Nothing was charged.");

  async function go(path, body, button) {
    button.disabled = true;
    const r = await call(path, body);
    button.disabled = false;
    if (!r.ok || !STRIPE.test(r.url || "")) { msg.say(why(r, "Stripe could not be reached. Try again in a minute.")); return; }
    location.assign(r.url);
  }

  function draw(r) {
    if (!r.ok) { box.replaceChildren(h("div", { class: "state" }, h("div", null, why(r, "The plan could not be loaded.")))); return; }
    const p = r.plan, owner = r.can_change !== false;
    const now = h("section", { class: "s" }, h("h2", null, "Your plan"),
      p ? [h("p", { class: "sub" }, h("b", null, p.name), ` (${STATUS[p.status] || p.status})`,
        p.trial_days_left != null ? `: ${p.trial_days_left} day${p.trial_days_left === 1 ? "" : "s"} of the trial left` : "",
        p.read_only ? `. ${p.read_only_why}` : "."),
        usageBar(p),
        h("div", { class: "scroll" }, h("table", null, h("caption", { class: "vh" }, "Usage against the plan's limits"),
          h("thead", null, h("tr", null, [["", null], ["Now", "n"], ["Plan allows", "n"], ["", "c"]].map(([t, cls]) => h("th", { scope: "col", class: cls }, t)))),
          h("tbody", null, usageRows(p)))),
        h("p", { class: "note" }, `Requests are every request the server logged for your sites in ${p.usage?.month || "this month"}, people and machines alike. Over a limit, nothing is deleted.`)]
        : h("p", { class: "sub" }, "This organisation has no plan, and no limits."));
    const manage = h("button", { type: "button", class: "btn" }, "Manage billing");
    manage.addEventListener("click", () => go("billing/portal", {}, manage));
    const cards = (r.plans || []).map((pl) => {
      const pick = h("button", { type: "button", class: "btn primary", disabled: !r.billing || !pl.can_buy || (pl.current && p?.status === "active") }, pl.current ? "Current plan" : `Choose ${pl.name}`);
      pick.addEventListener("click", () => go("billing/checkout", { plan: pl.name }, pick));
      return h("div", { class: "sheet" }, h("h3", null, pl.name), pl.label ? h("p", { class: "sub" }, pl.label) : null,
        h("p", { class: "muted" }, `${num(pl.sites)} sites, ${num(pl.requests_month)} requests a month, ${num(pl.members)} members, detail kept ${num(pl.retention_days_max)} days`),
        !pl.can_buy ? h("p", { class: "muted" }, "Not sold here.") : owner ? pick : pl.current ? h("p", { class: "muted" }, "Current plan") : null);
    });
    box.replaceChildren(now,
      h("section", { class: "s" }, h("h2", null, "Plans"), r.billing ? null : h("p", { class: "note" }, "Payment is not switched on on this server."),
        owner ? null : h("p", { class: "note" }, "Only an owner can choose a plan or change the payment."),
        h("div", { class: "cols tops" }, cards)),
      owner && r.billing && r.has_customer ? h("section", { class: "s" }, h("h2", null, "Payment"),
        h("p", { class: "sub" }, "Card, invoices and cancelling: on Stripe's own page."), manage) :"");
  }

  call("billing").then(draw);
  return [title, box, msg];
}
