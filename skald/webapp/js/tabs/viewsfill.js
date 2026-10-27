// Settings > Site > Views: "Fill past days for the new groups" (views_fill_api.py,
// docs/SETTINGS.md). A page group counts from the next run; its past days stay
// empty until they are counted again from the raw log, which holds only the
// last days the server keeps. A save that adds or changes a group answers which
// ones (`views`); with the box under Views ticked (the default) the page then
// starts the fill at once, else it offers it with a button. The fill runs on the
// server in the background, one at a time per install, and this box shows its
// progress ("Filling 9 days… 4 of 9") until it ends ("Done: 9 days filled, all
// audited"). Days the raw log no longer holds are said plainly, never filled
// with 0. Admins and owners only; everyone else sees nothing here.

import { h, short } from "../ui.js";
import { call } from "./ipmanager.js";

export const timing = { poll: 2000 };   // ms between two reads of the progress (a test makes it short)
const choice = { auto: true };   // the box under Views, read when a save comes back
let pending = null;              // that save's `views` answer, for the page drawn after it

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const names = (list) => (list || []).map((v) => v.name).join(", ");

// The tick box under the Views field: ticked, a save with new groups fills their past days.
export function fillChoice() {
  const box = h("input", { type: "checkbox", checked: choice.auto, class: "vf-auto" });
  box.addEventListener("change", () => { choice.auto = box.checked; });
  return h("label", { class: "chk vf-choice" }, box, h("span", null, h("b", null, "Fill past days for the new groups"),
    h("small", null, "After saving, new or changed groups are counted again for every day the raw log still holds, and audited.")));
}

// Called with a save's answer before the page is drawn again.
export function remember(views) {
  pending = views && (views.changed?.length || views.removed?.length) ? { ...views, auto: choice.auto } : null;
}

// The Sites card's "Saved" line when the save starts a fill: say so, not "from the next run".
export function fillNote() {
  return pending?.auto && pending.changed?.length ? "Saved. The new groups' past days are filled in the box below; everything else applies from the next run." : "";
}

// What the raw log cannot give back, in one sentence (or none).
export function reachWords(reach) {
  if (!reach) return "";
  if (!reach.days) return "The raw log holds no whole day yet, so there is nothing to fill: the groups count from the next run.";
  return `Days before ${short(reach.first)} can't be filled: the raw log is kept ${plural(reach.kept_days, "day")}. They show as "not recorded for this group", never as 0.`;
}

// The fill's state in words: [headline, detail].
export function stateWords(f) {
  if (!f) return ["", ""];
  const days = f.days || 0;
  if (f.state === "busy") return ["Another fill is running on this server. Try again when it ends.", ""];
  if (f.state === "queued") return [`Filling ${plural(days, "day")}… starting`, names(f.views)];
  if (f.state === "running") return [`Filling ${plural(days, "day")}… ${f.done || 0} of ${days}`, names(f.views) + (f.current ? ` (counting ${short(f.current)})` : "")];
  if (f.state === "failed") return [`The fill stopped${f.done ? ` after ${f.done} of ${days} days` : ""}: ${f.error || "it did not finish"}`, ""];
  if (f.state !== "done") return ["", ""];
  const bits = [];
  if (f.withheld) bits.push(`${plural(f.withheld, "day")} withheld: the audit's recount did not match, so ${f.withheld === 1 ? "it is" : "they are"} not shown`);
  if (f.empty) bits.push(`${plural(f.empty, "day")} had no line in the log and ${f.empty === 1 ? "stays" : "stay"} not recorded`);
  const head = !bits.length ? `Done: ${plural(f.filled || 0, "day")} filled, all audited.` : `Done: ${plural(f.filled || 0, "day")} filled and audited; ${bits.join("; ")}.`;
  return [head, names(f.views) + (f.finished_at ? `, finished ${short(f.finished_at.slice(0, 10))}` : "")];
}

// The box below the Sites card. `m.site` only names the page; every call is the page's own.
export function viewsFill(m) {
  const said = h("p", { class: "vf-said" });
  const head = h("p", { class: "vf-head", role: "status", "aria-live": "polite" });
  const detail = h("p", { class: "vf-detail muted" });
  const bar = h("progress", { class: "vf-bar", max: "1", value: "0", hidden: true });
  const reachLine = h("p", { class: "note vf-reach" });
  const acts = h("div", { class: "acts" });
  const extra = h("div");
  const box = h("section", { class: "sheet acct-card vf", hidden: true }, h("h2", null, "Past days for page groups"), said, head, bar, detail, extra, acts, reachLine);
  let timer = null;

  function show(f, reach) {
    box.hidden = false;
    const [a, b] = stateWords(f);
    head.textContent = a;
    detail.textContent = b;
    if (f?.state === "done") said.textContent = "";   // "counted … below" was for while it ran
    const going = f && (f.state === "running" || f.state === "queued");
    bar.hidden = !going;
    if (going) { bar.setAttribute("max", String(f.days || 1)); bar.setAttribute("value", String(f.done || 0)); bar.value = f.done || 0; }
    extra.replaceChildren(...(f?.state === "done" && f.problems?.length ? [h("details", null, h("summary", null, "What did not match"), h("ul", null, f.problems.map((p) => h("li", null, p))))] : []));
    if (reach) reachLine.textContent = reachWords(reach);
    acts.replaceChildren();
    if (going) { clearTimeout(timer); timer = setTimeout(poll, timing.poll); }
  }

  async function poll() {
    if (box.isConnected === false) return;    // the page moved on
    const r = await call("settings/views-fill");
    if (!r.ok) { head.textContent = r.error || "The fill's progress could not be read."; return; }
    show(r.fill, r.reach);
  }

  async function start(slugs, reach) {
    acts.replaceChildren();
    show({ state: "queued", days: reach?.days || 0, views: [] }, reach);
    const r = await call("settings/views-fill-start", { views: slugs });
    if (!r.ok) {
      if (r.fill) { show(r.fill, r.reach || reach); return; }
      head.textContent = r.error || "The fill could not be started.";
      bar.hidden = true;
      offer(pendingOffer, reach);
      return;
    }
    show(r.fill, r.reach || reach);
  }

  let pendingOffer = null;
  function offer(v, reach) {
    pendingOffer = v;
    box.hidden = false;
    const btn = h("button", { type: "button", class: "btn primary vf-start" }, "Fill past days for the new groups");
    btn.addEventListener("click", () => start(v.changed.map((x) => x.slug), reach));
    acts.replaceChildren(...(reach?.days ? [btn] : []));
    reachLine.textContent = reachWords(reach);
  }

  const v = pending;
  pending = null;
  if (v) {
    box.hidden = false;
    const lines = [];
    if (v.changed?.length) lines.push(`${v.changed.length === 1 ? "New group" : "New groups"}: ${names(v.changed)}. ${v.changed.length === 1 ? "Its" : "Their"} past days are counted from the raw log in the box below.`);
    if (v.removed?.length) lines.push(`Removed: ${names(v.removed)}. ${v.removed.length === 1 ? "It leaves" : "They leave"} the page-group menu; nothing needs counting again.`);
    said.textContent = lines.join(" ");
    if (v.changed?.length && v.can_fill) {
      const busy = v.fill && (v.fill.state === "running" || v.fill.state === "queued" || v.fill.state === "busy");
      if (busy) show(v.fill, v.reach);
      else if (v.auto && v.reach?.days) start(v.changed.map((x) => x.slug), v.reach);
      else { head.textContent = v.reach?.days ? `The raw log holds ${plural(v.reach.days, "whole day")} (${short(v.reach.first)} to ${short(v.reach.last)}) to fill them from.` : ""; offer(v, v.reach); }
    }
    return box;
  }
  // No save just now: show a fill that runs, or the last one for this site.
  call("settings/views-fill").then((r) => { if (r.ok && r.fill) show(r.fill, r.reach); });
  return box;
}
