// One request, in full: every field the log line gave, the rule that put it
// in its group, and two actions - narrow the log to its address, or count
// that address as our own traffic from now on.

import { time as tzTime, label as tzLabel } from "../tz.js";
import { h, n, clock, long, toast } from "../ui.js";
import { GROUPS, color } from "../data.js";
import * as S from "../state.js";
import { country, flag } from "./readers.js";
import { call, installOnly, INSTALL_ONLY } from "./ipmanager.js";
import { isViewer, VIEWER } from "../access.js";
import { openDrawer } from "../drawer.js";

export const GROUP_NAME = { ...Object.fromEntries(GROUPS), excluded: "Other hosts (not counted)" };

// The data layer's warning flags on a row, in words: [chip, explanation].
export const FLAG_WORDS = {
  hosting_network: ["cloud network", "From a cloud or hosting network: people rarely browse from one"],
  fan_out: ["many addresses", "The same browser string from 10 or more addresses within 10 seconds"],
  bare_mozilla: ["bare Mozilla", "The user agent is only \"Mozilla/5.0\": no real browser sends that"],
  probe: ["scanner probe", "A path no real site serves, asked for by credential hunters"],
  legacy_path: ["old URL", "An address from the old site, kept out of the probes"],
  old_format: ["old log format", "A line in the old log format: no host or country"],
  duplicate: ["duplicate", "Byte-identical to an earlier line in the same second"],
};
const KIND_WORDS = { page: "a page", rsc: "Next.js page data (_rsc)", asset: "a file (script, style, image)", beacon: "a beacon", crawler_file: "robots.txt, a sitemap or similar",
  redirect: "a redirect", not_modified: "not modified (cached)", not_found: "not found", client_error: "a client error", server_error: "a server error", post: "a form post", other: "other" };

// One row as the screens read it; the file's own fields stay as they are.
export function norm(r) {
  return { ...r, referrer: `${r.ref_host || ""}${r.ref_path && r.ref_path !== "/" ? r.ref_path : ""}`, assistant: r.assistant || "", agent: r.agent || "", flags: r.flags || [] };
}
export function statusTone(st) {
  if (st >= 500) return "s5";
  if (st === 404 || st === 410) return "s404";
  if (st >= 400) return "s4";
  if (st >= 300) return "s3";
  return "s2";
}

export function copyButton(text, what = "address") {
  const b = h("button", { type: "button", class: "copy", "aria-label": `Copy ${what} ${text}` }, "Copy");
  b.addEventListener("click", async (e) => {
    e.stopPropagation();
    try { await navigator.clipboard.writeText(text); toast(`Copied ${text}`); } catch { toast("Copy is not allowed here; select the text instead"); }
  });
  return b;
}

const yes = (v) => (v == null ? "-" : v ? "yes" : "no");
const VERIFIED = { verified: "verified: its address belongs to who it says", unverified: "not verifiable: no published address list", spoofed: "spoofed: claims a name its address does not belong to" };

export function detail(m, row, ours) {
  let d = null;
  const utm = Object.entries(row.utm || {}).map(([k, v]) => `${k}: ${v}`).join(", ");
  const removed = row.ip === "(removed)";
  const dl = (fields) => h("dl", { class: "dw-dl" }, fields.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)]));
  const sec = (title, ...kids) => h("section", { class: "dw-sec" }, h("h3", null, title), ...kids);
  const request = dl([
    ["Time", tzTime(row.at, { seconds: true, date: true })],
    ["Host", row.host || "-"],
    ["Request", h("span", { class: "mono" }, `${row.method || "(no method)"} ${row.path}${row.query ? `?${row.query}` : ""}`)],
    ["What it was", KIND_WORDS[row.kind] || row.kind || "-"],
    ["Status", h("span", { class: `st ${statusTone(row.status)}` }, String(row.status))],
    ["Size", row.bytes == null ? "-" : `${n(row.bytes)} bytes`],
    ["Server time", row.ms == null ? "not logged" : `${n(row.ms)} ms`],
  ]);
  const who = dl([
    ["Address", row.ip && !removed ? h("span", { class: "ip" }, row.ip, copyButton(row.ip)) : removed ? "removed on request" : "-"],
    ["Country", row.country ? `${flag(row.country)} ${row.country_name || country(row.country)}` : "unknown"],
    ["System", [row.os, row.device].filter((x) => x && x !== "Other").join(", ") || "-"],
    ["Agent", row.agent || "-"],
    ["Verified", row.verified ? VERIFIED[row.verified] || row.verified : "only named assistants and search crawlers are checked"],
    ["Warning signs", row.flags.length ? h("ul", { class: "flag-list" }, row.flags.map((f) => h("li", null, FLAG_WORDS[f] ? `${FLAG_WORDS[f][0]}: ${FLAG_WORDS[f][1].toLowerCase()}` : f))) : "none"],
  ]);
  const counted = dl([
    ["Group", h("span", { class: "grp" }, h("i", { style: { background: color(row.group) } }), GROUP_NAME[row.group] || row.group)],
    ["Decided by", row.rule || "-"],
    ["Page view", row.page_view ? "yes, counted as a page view" : "no"],
  ]);
  const from = dl([
    ["Referrer", row.referrer ? h("span", { class: "mono" }, row.referrer) : "none"],
    ["AI assistant", row.assistant || "-"],
    ["Campaign tags", utm || "none"],
  ]);

  // Our own traffic: say so, or offer to add the address (admins only).
  let ownPart = null, showAll = null;
  if (row.ip && !removed) {
    showAll = h("button", { type: "button", class: "btn primary", onclick: () => { d.close({ focusBack: false }); S.set({ tab: "requests", ip: row.ip }); } }, `Show every request from ${row.ip}`);
    const known = ours.get(row.ip);
    const api = m.x.ours?.api;
    if (known || row.group === "ours") {
      ownPart = h("p", { class: "note" }, `Already counted as our own traffic${known ? ` (${known})` : row.rule ? ` (${row.rule.replace(/^ours:\s*/, "")})` : ""}.`);
    } else if (api && isViewer()) {
      ownPart = h("p", { class: "note viewer-note" }, `${VIEWER} Counting an address as our own traffic is for admins.`);
    } else if (api && installOnly()) {
      ownPart = h("p", { class: "note viewer-note" }, `${INSTALL_ONLY} Counting an address as our own traffic is for install admins.`);
    } else if (api) {
      const label = h("input", { type: "text", placeholder: "Label, e.g. Home laptop", maxlength: "60", "aria-label": `Label for ${row.ip}` });
      const msg = h("p", { class: "msg", role: "status", "aria-live": "polite" });
      const add = h("form", { class: "rq-add" }, h("label", null, `Count ${row.ip} as our own traffic from now on`, h("span", { class: "pair" }, label,
        h("button", { type: "submit", class: "btn" }, "Add as internal"))), msg);
      add.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!label.value.trim()) { msg.textContent = "Give it a label first, so the list says whose address it is."; msg.className = "msg err"; label.focus(); return; }
        const r = await call(api.add, { ip: row.ip, label: label.value.trim() });
        if (r.ok) {
          ours.set(row.ip, label.value.trim());
          msg.textContent = `Added. From now on ${row.ip} counts as our own traffic; requests already logged keep their group.`;
          msg.className = "msg ok";
          toast(`${row.ip} added as internal`);
        } else { msg.textContent = r.error; msg.className = "msg err"; }
      });
      ownPart = add;
    }
  }

  d = openDrawer({
    title: row.path, subtitle: `${row.method || "Request"} at ${tzTime(row.at, { seconds: true, date: true })}, status ${row.status}, ${GROUP_NAME[row.group] || row.group}`,
    className: "rq-dw", key: "request", scope: "page",
    body: [
      h("div", { class: "dw-cols" }, sec("The request", request), sec("Who asked", who)),
      h("div", { class: "dw-cols" }, sec("How it was counted", counted, ownPart ? sec("Our own traffic", ownPart) : null), sec("Where it came from", from)),
      h("p", { class: "note" }, "Addresses are shown on this private page only, read from the recent log; they are never stored in history."),
    ],
    footer: [h("button", { type: "button", class: "btn", onclick: () => d.close() }, "Close"), showAll],
  });
  return d.el;
}
